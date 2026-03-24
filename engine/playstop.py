"""
TMOS13 PlayStop — Unified Transport State Machine

Three-state model (PLAY, PAUSE, STOP) that unifies the 6+ independent status
vocabularies across pipeline, delivery, ambassador, exchange, session, and
workflow subsystems.

Naming: "Transport Rail" for UI surface, "PlayStop" for code.
NOT "Data Rail" — that's the PII side-channel.

No database migration needed — state lives on SessionState.playstop_state
and persists via the existing session store / persistence layer.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("tmos13.playstop")

# ─── Config ──────────────────────────────────────────────────

PLAYSTOP_ENABLED = os.environ.get("PLAYSTOP_ENABLED", "true").lower() in ("true", "1", "yes")


# ─── Enums ───────────────────────────────────────────────────

class PlayStopState(str, Enum):
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"


class StopReason(str, Enum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ERROR = "error"
    EXTERNAL = "external"


# ─── Data Models ─────────────────────────────────────────────

@dataclass
class PlayStopTransition:
    """Record of a single state transition."""
    from_state: PlayStopState
    to_state: PlayStopState
    actor: str                    # user_id, "system", "engine", "scheduler"
    reason: str = ""
    stop_reason: Optional[StopReason] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "actor": self.actor,
            "reason": self.reason,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ─── State Machine ───────────────────────────────────────────

class PlayStopMachine:
    """
    Session-scoped transport state machine.

    Singleton that tracks transition history per session_id. The actual
    state lives on SessionState.playstop_state (persisted by session store).
    This mirrors the singleton pattern used by pipeline_service,
    delivery_service, etc.
    """

    VALID_TRANSITIONS = {
        PlayStopState.PLAY: {PlayStopState.PAUSE, PlayStopState.STOP},
        PlayStopState.PAUSE: {PlayStopState.PLAY, PlayStopState.STOP},
        PlayStopState.STOP: {PlayStopState.PLAY},  # Only if restartable
    }

    def __init__(self):
        # Per-session transition history: {session_id: [PlayStopTransition, ...]}
        self._history: dict[str, list[PlayStopTransition]] = {}

    def _get_state(self, session_state) -> PlayStopState:
        """Read current PlayStopState from a SessionState object."""
        raw = getattr(session_state, "playstop_state", "play")
        try:
            return PlayStopState(raw)
        except ValueError:
            return PlayStopState.PLAY

    def can_transition(
        self, session_state, to_state: PlayStopState, *, restartable: bool = False
    ) -> bool:
        """Check whether a transition is valid without performing it."""
        current = self._get_state(session_state)

        if current == to_state:
            return True  # idempotent — no-op

        if to_state not in self.VALID_TRANSITIONS.get(current, set()):
            return False

        # stop→play requires restartable
        if current == PlayStopState.STOP and to_state == PlayStopState.PLAY:
            return restartable

        return True

    def transition(
        self,
        session_state,
        to_state: PlayStopState,
        *,
        actor: str = "system",
        reason: str = "",
        stop_reason: Optional[StopReason] = None,
        restartable: bool = False,
        metadata: Optional[dict] = None,
    ) -> PlayStopTransition:
        """
        Execute a state transition on the given session state.

        Raises ValueError for invalid transitions.
        Returns the transition record (also appended to history).
        """
        current = self._get_state(session_state)

        # Idempotent — same state, no-op
        if current == to_state:
            transition = PlayStopTransition(
                from_state=current,
                to_state=to_state,
                actor=actor,
                reason=reason or "no-op (already in target state)",
                stop_reason=stop_reason,
                metadata=metadata or {},
            )
            return transition

        # Validate transition
        if to_state not in self.VALID_TRANSITIONS.get(current, set()):
            raise ValueError(
                f"Invalid transition: {current.value} → {to_state.value}"
            )

        # stop→play requires restartable
        if current == PlayStopState.STOP and to_state == PlayStopState.PLAY:
            if not restartable:
                raise ValueError(
                    "Cannot restart stopped session (restartable=False)"
                )

        # Build transition record
        transition = PlayStopTransition(
            from_state=current,
            to_state=to_state,
            actor=actor,
            reason=reason,
            stop_reason=stop_reason,
            metadata=metadata or {},
        )

        # Apply state change
        session_state.playstop_state = to_state.value

        # Record history
        sid = getattr(session_state, "session_id", "unknown")
        self._history.setdefault(sid, []).append(transition)

        logger.info(
            "PlayStop transition: session=%s %s→%s actor=%s reason=%s",
            sid, current.value, to_state.value, actor, reason,
        )

        return transition

    # ─── Convenience methods ─────────────────────────────────

    def play(self, session_state, *, actor: str = "system", reason: str = "", restartable: bool = False) -> PlayStopTransition:
        """Transition to PLAY state."""
        return self.transition(session_state, PlayStopState.PLAY, actor=actor, reason=reason, restartable=restartable)

    def pause(self, session_state, *, actor: str = "system", reason: str = "") -> PlayStopTransition:
        """Transition to PAUSE state."""
        return self.transition(session_state, PlayStopState.PAUSE, actor=actor, reason=reason)

    def stop(self, session_state, *, actor: str = "system", reason: str = "", stop_reason: Optional[StopReason] = None) -> PlayStopTransition:
        """Transition to STOP state."""
        return self.transition(session_state, PlayStopState.STOP, actor=actor, reason=reason, stop_reason=stop_reason)

    # ─── Query helpers ───────────────────────────────────────

    def is_playing(self, session_state) -> bool:
        return self._get_state(session_state) == PlayStopState.PLAY

    def is_paused(self, session_state) -> bool:
        return self._get_state(session_state) == PlayStopState.PAUSE

    def is_stopped(self, session_state) -> bool:
        return self._get_state(session_state) == PlayStopState.STOP

    def get_history(self, session_id: str) -> list[PlayStopTransition]:
        """Return transition history for a session."""
        return list(self._history.get(session_id, []))

    def to_dict(self, session_state) -> dict:
        """Snapshot of current state + recent history for a session."""
        sid = getattr(session_state, "session_id", "unknown")
        history = self._history.get(sid, [])
        return {
            "state": self._get_state(session_state).value,
            "session_id": sid,
            "history": [t.to_dict() for t in history[-10:]],  # last 10 transitions
        }


# ─── Scheduled PlayStop (TimeKeeper, Plume Node 11) ─────────

def evaluate_scheduled_playstop(session_state, schedule_cache) -> Optional[tuple[str, str]]:
    """
    Check if a schedule-driven PlayStop transition is due for the session's pack.

    Args:
        session_state: SessionState with pack_id, timezone, playstop_state
        schedule_cache: ScheduleCache instance

    Returns:
        (target_state, reason) if a transition is due, else None.
        Only returns transport actions (pause, play, stop), not 'notify'.
    """
    if schedule_cache is None:
        return None

    from zoneinfo import ZoneInfo

    pack_id = getattr(session_state, "pack_id", "")
    if not pack_id:
        return None

    # Get session timezone
    tz_str = getattr(session_state, "timezone", "UTC") or "UTC"
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("UTC")

    now = datetime.now(timezone.utc)

    entries = schedule_cache.get_entries_for_pack(pack_id)
    if not entries:
        return None

    # Find the first due entry with a transport action
    for entry in entries:
        if not entry.enabled:
            continue
        if entry.action not in ("pause", "play", "stop"):
            continue

        try:
            from schedule_cache import next_occurrence

            # Use _last_fired or 1 hour ago as the reference point
            reference = entry._last_fired or (now - timedelta(hours=1))
            nxt = next_occurrence(entry, reference)
            if nxt <= now:
                # Check it's not a no-op (already in target state)
                current = getattr(session_state, "playstop_state", "play")
                if current == entry.action:
                    schedule_cache.mark_fired(entry, now)
                    continue

                schedule_cache.mark_fired(entry, now)
                return (entry.action, entry.reason)
        except Exception as e:
            logger.debug("Schedule eval error for %s/%s: %s", entry.pack_id, entry.entry_id, e)

    return None


# ─── Autonomous Session Initiation (The Loop, Plume Node 13) ──

async def evaluate_scheduled_initiation(
    schedule_cache,
    session_factory,
    pack_install_service=None,
    db=None,
    manifest_service=None,
    owner_id: str = "",
) -> list[dict]:
    """
    Evaluate due "initiate" schedule entries and create sessions.

    Returns list of {pack_id, entry_id, user_id, session_id} for each created session.
    """
    from config import LOOP_ENABLED, LOOP_MAX_AUTO_SESSIONS

    if not LOOP_ENABLED:
        return []

    now = datetime.now(timezone.utc)
    due_entries = schedule_cache.get_due_entries(now)
    initiate_entries = [(e, t) for e, t in due_entries if e.action == "initiate"]

    if not initiate_entries:
        return []

    results = []
    created = 0

    for entry, fired_at in initiate_entries:
        if created >= LOOP_MAX_AUTO_SESSIONS:
            logger.warning("Loop: max auto-sessions (%d) reached this cycle", LOOP_MAX_AUTO_SESSIONS)
            break

        targets = _resolve_initiate_targets(entry, pack_install_service, db)
        if not targets:
            schedule_cache.mark_fired(entry, now)
            continue

        for user_id in targets:
            if created >= LOOP_MAX_AUTO_SESSIONS:
                break

            # Idempotency: skip if already initiated today
            if db and _has_loop_session_today(db, user_id, entry.pack_id, entry.entry_id):
                continue

            try:
                state = session_factory.create_session(
                    user_id=user_id,
                    pack_id=entry.pack_id,
                    initiated_by="schedule",
                )

                # Audit log
                if db:
                    _audit_loop_session(db, state, entry, fired_at)

                # Manifest log
                if manifest_service and owner_id:
                    try:
                        manifest_service.log(
                            owner_id=owner_id,
                            event_type="session_initiated",
                            category="session",
                            summary=f"Loop auto-initiated {entry.pack_id} session for user",
                            detail={"entry_id": entry.entry_id, "reason": entry.reason},
                            pack_id=entry.pack_id,
                            session_id=state.session_id,
                        )
                    except Exception:
                        pass  # manifest logging is best-effort

                results.append({
                    "pack_id": entry.pack_id,
                    "entry_id": entry.entry_id,
                    "user_id": user_id,
                    "session_id": state.session_id,
                })
                created += 1

            except Exception as e:
                logger.warning(
                    "Loop: failed to create session for pack=%s user=%s: %s",
                    entry.pack_id, user_id, e,
                )

        schedule_cache.mark_fired(entry, now)

    if results:
        logger.info("Loop: initiated %d session(s) this cycle", len(results))

    return results


def _resolve_initiate_targets(
    entry, pack_install_service=None, db=None,
) -> list[str]:
    """Resolve initiate_for field to a list of user IDs."""
    target_spec = entry.initiate_for
    if not target_spec:
        return []

    if target_spec == "installed_users":
        if pack_install_service is None:
            return []
        try:
            installs = pack_install_service.get_installs_for_pack(entry.pack_id)
            return [i["user_id"] for i in installs if i.get("status") == "active"]
        except Exception as e:
            logger.debug("Loop: failed to resolve installed_users for %s: %s", entry.pack_id, e)
            return []

    if target_spec == "active_contacts":
        if db is None:
            return []
        try:
            result = (
                db.table("contacts")
                .select("user_id")
                .eq("status", "active")
                .limit(100)
                .execute()
            )
            return [r["user_id"] for r in (result.data or []) if r.get("user_id")]
        except Exception as e:
            logger.debug("Loop: failed to resolve active_contacts: %s", e)
            return []

    # Comma-separated user IDs
    return [uid.strip() for uid in target_spec.split(",") if uid.strip()]


def _has_loop_session_today(db, user_id: str, pack_id: str, entry_id: str) -> bool:
    """Check if a loop session was already created today for this user/pack/entry."""
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0,
        ).isoformat()
        result = (
            db.table("loop_sessions")
            .select("id")
            .eq("user_id", user_id)
            .eq("pack_id", pack_id)
            .eq("entry_id", entry_id)
            .gte("created_at", today_start)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False  # fail open — allow creation


def _audit_loop_session(db, state, entry, fired_at: datetime) -> None:
    """Write audit record for a loop-initiated session."""
    try:
        db.table("loop_sessions").insert({
            "session_id": state.session_id,
            "user_id": state.user_id,
            "pack_id": entry.pack_id,
            "entry_id": entry.entry_id,
            "initiated_by": "schedule",
            "status": "active",
        }).execute()
    except Exception as e:
        logger.debug("Loop: audit write failed (non-fatal): %s", e)


# ─── Status Mapping Functions ────────────────────────────────
#
# Read-only projections from subsystem-specific status vocabularies
# into the unified PlayStop state. These never modify source status fields.

def map_pipeline_status(status: str) -> PlayStopState:
    """Map PipelineInstance.status → PlayStopState."""
    _map = {
        "active": PlayStopState.PLAY,
        "waiting_approval": PlayStopState.PAUSE,
        "completed": PlayStopState.STOP,
        "failed": PlayStopState.STOP,
        "cancelled": PlayStopState.STOP,
    }
    return _map.get(status, PlayStopState.PLAY)


def map_delivery_status(status: str) -> PlayStopState:
    """Map DeliveryRecord.status → PlayStopState."""
    _map = {
        "pending": PlayStopState.PAUSE,
        "approved": PlayStopState.PLAY,
        "dispatching": PlayStopState.PLAY,
        "sent": PlayStopState.STOP,
        "failed": PlayStopState.STOP,
        "cancelled": PlayStopState.STOP,
    }
    return _map.get(status, PlayStopState.PLAY)


def map_address_status(status: str) -> PlayStopState:
    """Map Ambassador address status → PlayStopState."""
    _map = {
        "active": PlayStopState.PLAY,
        "paused": PlayStopState.PAUSE,
        "away": PlayStopState.PAUSE,
        "closed": PlayStopState.STOP,
    }
    return _map.get(status, PlayStopState.PLAY)


def map_exchange_status(status: str) -> PlayStopState:
    """Map Ambassador exchange status → PlayStopState."""
    _map = {
        "active": PlayStopState.PLAY,
        "pending_human": PlayStopState.PAUSE,
        "resolved": PlayStopState.STOP,
        "rejected": PlayStopState.STOP,
        "expired": PlayStopState.STOP,
    }
    return _map.get(status, PlayStopState.PLAY)


def map_session_status(status: str) -> PlayStopState:
    """Map session-level status → PlayStopState."""
    _map = {
        "active": PlayStopState.PLAY,
        "waiting": PlayStopState.PAUSE,
        "resolved": PlayStopState.STOP,
    }
    return _map.get(status, PlayStopState.PLAY)


def map_workflow_status(status: str) -> PlayStopState:
    """Map Orchestrator workflow status → PlayStopState."""
    _map = {
        "active": PlayStopState.PLAY,
        "pending": PlayStopState.PAUSE,
        "waiting": PlayStopState.PAUSE,
        "completed": PlayStopState.STOP,
        "failed": PlayStopState.STOP,
        "timed_out": PlayStopState.STOP,
        "cancelled": PlayStopState.STOP,
    }
    return _map.get(status, PlayStopState.PLAY)


# ─── Reverse Mappers ────────────────────────────────────────

def playstop_to_session_status(ps: PlayStopState) -> str:
    """Map PlayStopState → session status string."""
    return {
        PlayStopState.PLAY: "active",
        PlayStopState.PAUSE: "waiting",
        PlayStopState.STOP: "resolved",
    }[ps]


def playstop_to_pipeline_status(ps: PlayStopState) -> str:
    """Map PlayStopState → pipeline status string."""
    return {
        PlayStopState.PLAY: "active",
        PlayStopState.PAUSE: "waiting_approval",
        PlayStopState.STOP: "completed",
    }[ps]


# ─── Unified Status Builder ─────────────────────────────────

def build_unified_status(
    session_state,
    pipeline_service=None,
    delivery_service=None,
    ambassador_service=None,
) -> dict:
    """
    Build a unified transport dashboard for a session.

    Returns a dict with the session's PlayStop state and mapped subsystem statuses.
    """
    raw = getattr(session_state, "playstop_state", "play")
    try:
        ps = PlayStopState(raw)
    except ValueError:
        ps = PlayStopState.PLAY

    sid = getattr(session_state, "session_id", "unknown")
    uid = getattr(session_state, "user_id", "anonymous")

    result = {
        "session_id": sid,
        "user_id": uid,
        "transport_state": ps.value,
        "subsystems": {},
    }

    # Pipeline subsystem
    if pipeline_service:
        try:
            instance_id = getattr(session_state, "pipeline_instance_id", "")
            if instance_id and hasattr(pipeline_service, "_instances"):
                inst = pipeline_service._instances.get(instance_id)
                if inst:
                    result["subsystems"]["pipeline"] = {
                        "native_status": inst.status,
                        "transport_state": map_pipeline_status(inst.status).value,
                    }
        except Exception:
            pass

    # Delivery subsystem — no active state to inspect without async DB call,
    # so we report availability only
    if delivery_service:
        result["subsystems"]["delivery"] = {"available": True}

    # Ambassador subsystem
    if ambassador_service:
        result["subsystems"]["ambassador"] = {"available": True}

    return result


# ─── Singleton ───────────────────────────────────────────────

_playstop_machine: Optional[PlayStopMachine] = None


def init_playstop() -> PlayStopMachine:
    """Initialize the global PlayStop machine. Called during app lifespan."""
    global _playstop_machine
    _playstop_machine = PlayStopMachine()
    logger.info("PlayStop transport rail initialized (enabled=%s)", PLAYSTOP_ENABLED)
    return _playstop_machine


def get_playstop() -> Optional[PlayStopMachine]:
    """Get the global PlayStop machine instance."""
    return _playstop_machine
