"""
TMOS13 Proactive Trigger Evaluator

Runs on a schedule (background task or cron endpoint).
Reads persistent_sessions, evaluates manifest-defined conditions,
and produces TriggerEvents for the dispatcher.

SAFETY PRINCIPLE: This module evaluates conditions deterministically.
It does NOT invoke the LLM. It does NOT decide what to do — it checks
whether manifest-defined conditions are met and reports them.
"""
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("tmos13.triggers")

# ─── Duration Parsing ────────────────────────────────────────

_DURATION_RE = re.compile(r"^(\d+)\s*(s|m|h|d|w)$")
_DURATION_UNITS = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}


def parse_duration(value: str) -> timedelta:
    """Parse a duration string like '48h', '7d', '15m' into a timedelta."""
    match = _DURATION_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid duration format: {value!r}")
    amount = int(match.group(1))
    unit = _DURATION_UNITS[match.group(2)]
    return timedelta(**{unit: amount})


def _parse_timestamp(value) -> Optional[datetime]:
    """Parse a timestamp from various formats to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None
    return None


# ─── Condition Evaluation ────────────────────────────────────

def _resolve_field(data: dict, path: str):
    """
    Resolve a dotted field path against a data dict.
    e.g. 'captured_fields.name' → data['captured_fields']['name']
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _check_older_than(field_val, duration_str: str) -> bool:
    """Check if a timestamp field is older than the given duration."""
    ts = _parse_timestamp(field_val)
    if ts is None:
        return False
    threshold = datetime.now(timezone.utc) - parse_duration(duration_str)
    return ts < threshold


def _check_newer_than(field_val, duration_str: str) -> bool:
    """Check if a timestamp field is newer than the given duration."""
    ts = _parse_timestamp(field_val)
    if ts is None:
        return False
    threshold = datetime.now(timezone.utc) - parse_duration(duration_str)
    return ts > threshold


CONDITION_OPS = {
    "eq": lambda fv, v: fv == v,
    "neq": lambda fv, v: fv != v,
    "gt": lambda fv, v: fv is not None and fv > v,
    "gte": lambda fv, v: fv is not None and fv >= v,
    "lt": lambda fv, v: fv is not None and fv < v,
    "lte": lambda fv, v: fv is not None and fv <= v,
    "exists": lambda fv, _v: fv is not None,
    "not_exists": lambda fv, _v: fv is None,
    "contains": lambda fv, v: fv is not None and v in fv,
    "older_than": _check_older_than,
    "newer_than": _check_newer_than,
    "changed_in_last": _check_newer_than,  # alias — checks updated_at
}


# ─── Temporal Condition Operators (TimeKeeper, Plume Node 11) ──

def _get_session_tz(session_data: dict):
    """Get timezone from session data, defaulting to UTC."""
    from zoneinfo import ZoneInfo
    tz_str = session_data.get("timezone") or session_data.get("state_snapshot", {}).get("timezone", "UTC")
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")


def _check_time_between(field_val, value: dict, session_data: dict) -> bool:
    """Check if current time is between start and end (HH:MM strings)."""
    tz = _get_session_tz(session_data)
    now = datetime.now(timezone.utc).astimezone(tz)
    start_parts = value.get("start", "00:00").split(":")
    end_parts = value.get("end", "23:59").split(":")
    start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
    end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
    now_minutes = now.hour * 60 + now.minute
    if start_minutes <= end_minutes:
        return start_minutes <= now_minutes < end_minutes
    else:
        # Wraps midnight (e.g., 22:00 - 06:00)
        return now_minutes >= start_minutes or now_minutes < end_minutes


def _check_time_before(field_val, value, session_data: dict) -> bool:
    """Check if current time is before a given HH:MM."""
    tz = _get_session_tz(session_data)
    now = datetime.now(timezone.utc).astimezone(tz)
    parts = str(value).split(":")
    target_minutes = int(parts[0]) * 60 + int(parts[1])
    now_minutes = now.hour * 60 + now.minute
    return now_minutes < target_minutes


def _check_time_after(field_val, value, session_data: dict) -> bool:
    """Check if current time is after a given HH:MM."""
    tz = _get_session_tz(session_data)
    now = datetime.now(timezone.utc).astimezone(tz)
    parts = str(value).split(":")
    target_minutes = int(parts[0]) * 60 + int(parts[1])
    now_minutes = now.hour * 60 + now.minute
    return now_minutes > target_minutes


def _check_day_of_week_in(field_val, value, session_data: dict) -> bool:
    """Check if current day of week is in the given list."""
    tz = _get_session_tz(session_data)
    now = datetime.now(timezone.utc).astimezone(tz)
    current_day = now.strftime("%A").lower()
    if isinstance(value, list):
        return current_day in [d.lower() for d in value]
    return False


def _check_is_business_hours(field_val, value, session_data: dict) -> bool:
    """Check if current time is weekday 9:00-17:00."""
    tz = _get_session_tz(session_data)
    now = datetime.now(timezone.utc).astimezone(tz)
    is_weekday = now.weekday() < 5
    is_hours = 9 <= now.hour < 17
    return is_weekday and is_hours


# Temporal operators that need session_data context are registered here
# and dispatched specially in _evaluate_rule()
_TEMPORAL_OPS = {
    "time_between": _check_time_between,
    "time_before": _check_time_before,
    "time_after": _check_time_after,
    "day_of_week_in": _check_day_of_week_in,
    "is_business_hours": _check_is_business_hours,
}


def evaluate_condition(condition: dict, session_data: dict) -> bool:
    """
    Evaluate a condition block against persistent session data.

    Supports AND/OR/NOT operators with nested rules.
    Each rule: {field, op, value}
    """
    operator = condition.get("operator", "AND").upper()
    rules = condition.get("rules", [])

    if not rules:
        return False

    if operator == "AND":
        return all(_evaluate_rule(r, session_data) for r in rules)
    elif operator == "OR":
        return any(_evaluate_rule(r, session_data) for r in rules)
    elif operator == "NOT":
        return not all(_evaluate_rule(r, session_data) for r in rules)
    else:
        logger.warning(f"Unknown condition operator: {operator}")
        return False


def _evaluate_rule(rule: dict, session_data: dict) -> bool:
    """Evaluate a single rule or nested condition."""
    # Nested condition (has 'operator' + 'rules')
    if "operator" in rule and "rules" in rule:
        return evaluate_condition(rule, session_data)

    field_path = rule.get("field", "")
    op = rule.get("op", "eq")
    value = rule.get("value")

    field_val = _resolve_field(session_data, field_path)

    # Temporal operators need session_data for timezone context
    temporal_fn = _TEMPORAL_OPS.get(op)
    if temporal_fn is not None:
        try:
            return temporal_fn(field_val, value, session_data)
        except (TypeError, ValueError) as e:
            logger.debug(f"Temporal condition eval error: op={op} err={e}")
            return False

    op_fn = CONDITION_OPS.get(op)
    if op_fn is None:
        logger.warning(f"Unknown condition op: {op}")
        return False

    try:
        return op_fn(field_val, value)
    except (TypeError, ValueError) as e:
        logger.debug(f"Condition eval error: field={field_path} op={op} err={e}")
        return False


# ─── TriggerEvent ────────────────────────────────────────────

@dataclass
class TriggerEvent:
    """A trigger that has matched its conditions and is ready for dispatch."""
    trigger_id: str
    pack_id: str
    persistent_session_id: str
    contact_identity: dict = field(default_factory=dict)
    action: str = ""
    template: str = ""
    channel: str = "email"
    priority: str = "normal"
    cooldown: str = "0"
    max_attempts: int = 1
    requires_approval: bool = False
    metadata: dict = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─── TriggerEvaluator ───────────────────────────────────────

class TriggerEvaluator:
    """Evaluates trigger conditions against persistent sessions."""

    def __init__(self, supabase_client=None):
        self.db = supabase_client

    @property
    def enabled(self) -> bool:
        return self.db is not None

    async def evaluate_pack(
        self,
        pack_id: str,
        triggers_config: dict,
        sessions: list[dict] | None = None,
    ) -> list[TriggerEvent]:
        """
        Evaluate all triggers for a single pack.

        Args:
            pack_id: The pack to evaluate
            triggers_config: The 'triggers' section from the pack manifest
            sessions: Optionally pre-loaded sessions (for testing).
                      If None, queries persistent_sessions table.

        Returns:
            List of TriggerEvents ready for dispatch.
        """
        if not triggers_config:
            return []

        # Load active persistent sessions for this pack
        if sessions is None:
            sessions = await self._load_active_sessions(pack_id)
        if not sessions:
            return []

        events = []
        for trigger_id, trigger_def in triggers_config.items():
            condition = trigger_def.get("condition")
            if not condition:
                continue

            for session in sessions:
                # Skip resolved/expired sessions
                if session.get("status") not in (None, "active"):
                    continue

                # Evaluate condition
                if not evaluate_condition(condition, session):
                    continue

                # Check cooldown
                cooldown = trigger_def.get("cooldown", "0")
                if cooldown and cooldown != "0":
                    cooled = await self.check_cooldown(
                        trigger_id, session.get("id", ""), cooldown
                    )
                    if not cooled:
                        continue

                # Check max_attempts
                max_attempts = trigger_def.get("max_attempts", 1)
                if max_attempts > 0:
                    count = await self.get_attempt_count(
                        trigger_id, session.get("id", "")
                    )
                    if count >= max_attempts:
                        continue

                # Build contact identity from session
                identity = {}
                if session.get("contact_email"):
                    identity["email"] = session["contact_email"]
                if session.get("user_id"):
                    identity["user_id"] = session["user_id"]
                # Try to get name from captured_fields
                captured = session.get("captured_fields", {})
                if isinstance(captured, dict) and captured.get("name"):
                    identity["name"] = captured["name"]

                event = TriggerEvent(
                    trigger_id=trigger_id,
                    pack_id=pack_id,
                    persistent_session_id=session.get("id", ""),
                    contact_identity=identity,
                    action=trigger_def.get("action", ""),
                    template=trigger_def.get("template", ""),
                    channel=trigger_def.get("channel", "email"),
                    priority=trigger_def.get("priority", "normal"),
                    cooldown=cooldown,
                    max_attempts=max_attempts,
                    requires_approval=trigger_def.get("requires_owner_approval", False),
                    metadata={
                        "description": trigger_def.get("description", ""),
                        "session_data": {
                            "depth": session.get("depth", 0),
                            "total_turns": session.get("total_turns", 0),
                            "qualification_score": session.get("qualification_score", 0),
                        },
                    },
                )
                events.append(event)

        logger.info(
            f"Pack {pack_id}: evaluated {len(triggers_config)} trigger(s) "
            f"against {len(sessions)} session(s) → {len(events)} event(s)"
        )
        return events

    async def evaluate_all_packs(self, pack_triggers: dict[str, dict]) -> list[TriggerEvent]:
        """
        Main evaluation loop. For each pack with triggers defined,
        evaluate all triggers against all active sessions.

        Args:
            pack_triggers: {pack_id: triggers_config} from manifests

        Returns:
            All TriggerEvents across all packs.
        """
        all_events = []
        for pack_id, triggers_config in pack_triggers.items():
            try:
                events = await self.evaluate_pack(pack_id, triggers_config)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Trigger evaluation failed for pack {pack_id}: {e}")
        return all_events

    async def check_cooldown(
        self, trigger_id: str, session_id: str, cooldown: str
    ) -> bool:
        """
        Check trigger_audit table for recent fires.
        Returns True if cooled down (safe to fire again).
        """
        if not self.enabled or not session_id:
            return True  # no DB = no cooldown tracking

        try:
            cooldown_td = parse_duration(cooldown)
        except ValueError:
            return True

        cutoff = (datetime.now(timezone.utc) - cooldown_td).isoformat()

        try:
            result = (
                self.db.table("trigger_audit")
                .select("id")
                .eq("trigger_id", trigger_id)
                .eq("persistent_session_id", session_id)
                .gte("fired_at", cutoff)
                .limit(1)
                .execute()
            )
            return not bool(result.data)
        except Exception as e:
            logger.warning(f"Cooldown check failed: {e}")
            return True  # fail-open on DB errors (conservative: allow fire)

    async def get_attempt_count(
        self, trigger_id: str, session_id: str
    ) -> int:
        """Count how many times a trigger has fired for a session."""
        if not self.enabled or not session_id:
            return 0

        try:
            result = (
                self.db.table("trigger_audit")
                .select("id")
                .eq("trigger_id", trigger_id)
                .eq("persistent_session_id", session_id)
                .execute()
            )
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.warning(f"Attempt count check failed: {e}")
            return 0

    async def _load_active_sessions(self, pack_id: str) -> list[dict]:
        """Query active persistent sessions for a pack."""
        if not self.enabled:
            return []

        try:
            result = (
                self.db.table("persistent_sessions")
                .select("*")
                .eq("pack_id", pack_id)
                .eq("status", "active")
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to load sessions for pack {pack_id}: {e}")
            return []
