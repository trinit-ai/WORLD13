"""
TMOS13 Chain Executor — The Loop (Fibonacci Plume Node 13)

Deliverable-to-session chaining: when a deliverable is produced, evaluate
pack manifest on_deliverable.chains[] rules and create downstream sessions.

Supports staged (human approval) and auto (immediate execution) modes.

Singleton: init_chain_executor(session_factory, db, manifest_service) / get_chain_executor()
"""
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("tmos13.chain_executor")


@dataclass
class ChainIntent:
    """A pending or executed chain from deliverable to downstream session."""
    id: str
    chain_id: str
    source_pack: str
    source_deliverable_id: str
    target_pack: str
    carried_context: dict = field(default_factory=dict)
    carry_deliverable: bool = False
    status: str = "pending"    # pending | approved | executed | rejected
    mode: str = "staged"       # staged | auto
    user_id: str = ""
    session_id: str = ""       # set when executed
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "chain_id": self.chain_id,
            "source_pack": self.source_pack,
            "source_deliverable_id": self.source_deliverable_id,
            "target_pack": self.target_pack,
            "carried_context": self.carried_context,
            "carry_deliverable": self.carry_deliverable,
            "status": self.status,
            "mode": self.mode,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
        }


class ChainExecutor:
    """Evaluates deliverable chains and creates downstream sessions."""

    def __init__(self, session_factory=None, db=None, manifest_service=None):
        self._session_factory = session_factory
        self._db = db
        self._manifest_service = manifest_service
        self._pending: dict[str, ChainIntent] = {}  # id -> intent

    def evaluate_chains(self, deliverable, pack, state) -> list[ChainIntent]:
        """
        Evaluate on_deliverable.chains[] for a produced deliverable.

        Args:
            deliverable: Generated deliverable object (has spec_id, deliverable_id, etc.)
            pack: PackLoader instance for the source pack
            state: SessionState of the producing session
        """
        from config import LOOP_ENABLED, LOOP_CHAIN_ENABLED

        if not LOOP_ENABLED or not LOOP_CHAIN_ENABLED:
            return []

        if not pack or not hasattr(pack, "manifest"):
            return []

        on_deliverable = pack.manifest.get("on_deliverable", {})
        if not on_deliverable.get("enabled", False):
            return []

        chains = on_deliverable.get("chains", [])
        if not chains:
            return []

        # Get deliverable type from the deliverable object
        deliverable_type = getattr(deliverable, "spec_id", "") or ""
        deliverable_id = getattr(deliverable, "deliverable_id", "") or ""
        user_id = getattr(state, "user_id", "anonymous")
        source_pack = getattr(state, "pack_id", "")

        intents = []
        for chain_def in chains:
            try:
                # Type filter
                required_type = chain_def.get("deliverable_type", "")
                if required_type and deliverable_type != required_type:
                    continue

                # Condition evaluation
                condition = chain_def.get("condition", "")
                if condition and not self._evaluate_condition(condition, state):
                    continue

                # Extract carried context
                carry_fields = chain_def.get("carry_fields", [])
                carried_context = {}
                for f in carry_fields:
                    val = getattr(state, f, None)
                    if val is None and hasattr(state, "forms"):
                        for form_data in state.forms.values():
                            if f in form_data:
                                val = form_data[f]
                                break
                    if val is None:
                        prior = getattr(state, "prior_captured_fields", {})
                        val = prior.get(f)
                    if val is not None:
                        carried_context[f] = val

                intent = ChainIntent(
                    id=str(uuid.uuid4()),
                    chain_id=chain_def.get("id", "unnamed"),
                    source_pack=source_pack,
                    source_deliverable_id=deliverable_id,
                    target_pack=chain_def.get("target_pack", ""),
                    carried_context=carried_context,
                    carry_deliverable=chain_def.get("carry_deliverable", False),
                    mode=chain_def.get("mode", "staged"),
                    user_id=user_id,
                )

                # Persist to DB
                self._persist_intent(intent)

                # Auto-execute if mode is "auto"
                if intent.mode == "auto":
                    self._execute_intent(intent)
                else:
                    self._pending[intent.id] = intent

                intents.append(intent)

                logger.info(
                    "Chain intent created: %s → %s (mode=%s, status=%s)",
                    source_pack, intent.target_pack, intent.mode, intent.status,
                )

            except Exception as e:
                logger.warning("Chain evaluation error: %s", e)

        return intents

    def approve_intent(self, intent_id: str) -> Optional[str]:
        """Approve a staged intent. Returns session_id or None."""
        intent = self._pending.get(intent_id)
        if not intent:
            # Try loading from DB
            intent = self._load_intent(intent_id)
        if not intent or intent.status != "pending":
            return None

        intent.status = "approved"
        self._execute_intent(intent)
        self._update_intent_status(intent)

        if intent_id in self._pending:
            del self._pending[intent_id]

        return intent.session_id

    def reject_intent(self, intent_id: str) -> bool:
        """Reject a pending intent."""
        intent = self._pending.get(intent_id)
        if not intent:
            intent = self._load_intent(intent_id)
        if not intent or intent.status != "pending":
            return False

        intent.status = "rejected"
        self._update_intent_status(intent)

        if intent_id in self._pending:
            del self._pending[intent_id]

        return True

    def get_pending_intents(self, user_id: str = "") -> list[ChainIntent]:
        """Get pending intents, optionally filtered by user."""
        if user_id:
            return [i for i in self._pending.values() if i.user_id == user_id]
        return list(self._pending.values())

    def _execute_intent(self, intent: ChainIntent) -> None:
        """Execute a chain intent by creating a downstream session."""
        if not self._session_factory:
            logger.warning("Chain executor: no session factory, cannot execute intent %s", intent.id)
            return

        try:
            state = self._session_factory.create_session(
                user_id=intent.user_id,
                pack_id=intent.target_pack,
                initiated_by="chain",
                chain_source=intent.source_pack,
                carried_context=intent.carried_context,
            )
            intent.session_id = state.session_id
            intent.status = "executed"

            # Audit log
            if self._db:
                try:
                    self._db.table("loop_sessions").insert({
                        "session_id": state.session_id,
                        "user_id": intent.user_id,
                        "pack_id": intent.target_pack,
                        "entry_id": intent.chain_id,
                        "initiated_by": "chain",
                        "chain_source": intent.source_pack,
                        "status": "active",
                    }).execute()
                except Exception:
                    pass

            # Manifest log
            if self._manifest_service:
                try:
                    from config import TMOS13_OWNER_ID
                    self._manifest_service.log(
                        owner_id=TMOS13_OWNER_ID,
                        event_type="chain_triggered",
                        category="session",
                        summary=f"Chain: {intent.source_pack} → {intent.target_pack}",
                        detail={
                            "chain_id": intent.chain_id,
                            "source_deliverable": intent.source_deliverable_id,
                            "carried_fields": list(intent.carried_context.keys()),
                        },
                        pack_id=intent.target_pack,
                        session_id=state.session_id,
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.warning("Chain execute failed for intent %s: %s", intent.id, e)
            intent.status = "pending"  # revert

    def _evaluate_condition(self, condition: str, state) -> bool:
        """Evaluate a simple condition string like 'completeness > 0.7'."""
        # Simple pattern: field_name operator value
        m = re.match(r"(\w+)\s*(>|<|>=|<=|==|!=)\s*([0-9.]+)", condition.strip())
        if not m:
            return True  # no parseable condition = pass

        field_name, op, raw_value = m.group(1), m.group(2), m.group(3)
        try:
            threshold = float(raw_value)
        except ValueError:
            return True

        # Look up field value on state or forms
        val = getattr(state, field_name, None)
        if val is None:
            return False  # field not present = fail

        try:
            val = float(val)
        except (ValueError, TypeError):
            return False

        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        return ops[op](val, threshold)

    def _persist_intent(self, intent: ChainIntent) -> None:
        """Persist intent to DB."""
        if not self._db:
            return
        try:
            self._db.table("chain_intents").insert({
                "id": intent.id,
                "chain_id": intent.chain_id,
                "source_pack": intent.source_pack,
                "source_deliverable_id": intent.source_deliverable_id,
                "target_pack": intent.target_pack,
                "carried_context": intent.carried_context,
                "carry_deliverable": intent.carry_deliverable,
                "status": intent.status,
                "mode": intent.mode,
                "user_id": intent.user_id,
            }).execute()
        except Exception as e:
            logger.debug("Chain intent persist failed (non-fatal): %s", e)

    def _update_intent_status(self, intent: ChainIntent) -> None:
        """Update intent status in DB."""
        if not self._db:
            return
        try:
            self._db.table("chain_intents").update({
                "status": intent.status,
                "session_id": intent.session_id or None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", intent.id).execute()
        except Exception as e:
            logger.debug("Chain intent update failed (non-fatal): %s", e)

    def _load_intent(self, intent_id: str) -> Optional[ChainIntent]:
        """Load an intent from DB by ID."""
        if not self._db:
            return None
        try:
            result = (
                self._db.table("chain_intents")
                .select("*")
                .eq("id", intent_id)
                .limit(1)
                .execute()
            )
            if not result.data:
                return None
            row = result.data[0]
            return ChainIntent(
                id=row["id"],
                chain_id=row["chain_id"],
                source_pack=row["source_pack"],
                source_deliverable_id=row.get("source_deliverable_id", ""),
                target_pack=row["target_pack"],
                carried_context=row.get("carried_context", {}),
                carry_deliverable=row.get("carry_deliverable", False),
                status=row["status"],
                mode=row["mode"],
                user_id=row["user_id"],
                session_id=row.get("session_id", ""),
                created_at=row.get("created_at", ""),
            )
        except Exception:
            return None


# ─── Singleton ────────────────────────────────────────────

_chain_executor: Optional[ChainExecutor] = None


def init_chain_executor(
    session_factory=None, db=None, manifest_service=None,
) -> ChainExecutor:
    """Initialize the global ChainExecutor. Called during app lifespan."""
    global _chain_executor
    _chain_executor = ChainExecutor(
        session_factory=session_factory,
        db=db,
        manifest_service=manifest_service,
    )
    logger.info("ChainExecutor initialized (Loop Node 13)")
    return _chain_executor


def get_chain_executor() -> Optional[ChainExecutor]:
    """Get the global ChainExecutor instance."""
    return _chain_executor
