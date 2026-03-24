"""
TMOS13 Session Factory — The Loop (Fibonacci Plume Node 13)

Creates sessions without requiring a human message. Used by:
- Schedule-triggered autonomous session initiation
- Deliverable-to-session chaining (ChainExecutor)
- Proactive Ambassador send

Singleton: init_session_factory(sessions, persistence, db) / get_session_factory()
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from state import SessionState

logger = logging.getLogger("tmos13.session_factory")


class SessionFactory:
    """Creates sessions programmatically (no human message required)."""

    def __init__(self, sessions=None, persistence=None, db=None):
        self._sessions = sessions    # SessionStore
        self._persistence = persistence  # PersistenceService
        self._db = db                # Supabase admin client

    def create_session(
        self,
        user_id: str,
        pack_id: str,
        initiated_by: str = "",
        chain_source: str = "",
        carried_context: Optional[dict] = None,
    ) -> SessionState:
        """
        Create a new loop-initiated session.

        Args:
            user_id: Target user UUID
            pack_id: Pack to run
            initiated_by: Origin — "schedule", "chain", or "send"
            chain_source: Source pack_id if chained from another session
            carried_context: Dict of field names to carry into prior_captured_fields
        """
        session_id = str(uuid.uuid4())[:8]
        state = SessionState(
            session_id=session_id,
            user_id=user_id,
            pack_id=pack_id,
        )

        # Set loop metadata
        state.is_loop_session = True
        state.loop_initiated_by = initiated_by
        state.loop_chain_source = chain_source

        # Apply carried context to prior_captured_fields
        if carried_context:
            state.prior_captured_fields = dict(carried_context)

        # Run prefetch pipeline (mirrors app.py per-turn prefetch)
        self._run_prefetch_pipeline(state)

        # Build [LOOP CONTEXT] block
        state.loop_context = self._build_loop_context(
            initiated_by=initiated_by,
            chain_source=chain_source,
            carried_context=carried_context,
        )

        # Register in session store
        if self._sessions is not None:
            self._sessions.put(state)

        logger.info(
            "SessionFactory: created session %s for user=%s pack=%s initiated_by=%s",
            session_id, user_id, pack_id, initiated_by,
        )
        return state

    def _run_prefetch_pipeline(self, state: SessionState) -> None:
        """Run the same prefetch calls that app.py runs before each Claude call. Non-fatal."""
        try:
            from app import (
                _prefetch_schedule_context,
                _prefetch_registry_context,
            )
            _prefetch_schedule_context(state)
            _prefetch_registry_context(state)
        except Exception as e:
            logger.debug("SessionFactory prefetch partial failure (non-fatal): %s", e)

    def _build_loop_context(
        self,
        initiated_by: str,
        chain_source: str,
        carried_context: Optional[dict],
    ) -> str:
        """Format the [LOOP CONTEXT] assembler injection block."""
        lines = ["[LOOP CONTEXT]"]
        lines.append("This session was initiated autonomously by The Loop (Plume Node 13).")

        if initiated_by == "schedule":
            lines.append("Trigger: Scheduled session initiation.")
        elif initiated_by == "chain":
            lines.append(f"Trigger: Deliverable chain from pack '{chain_source}'.")
        elif initiated_by == "send":
            lines.append("Trigger: Proactive Ambassador outreach.")
        else:
            lines.append(f"Trigger: {initiated_by or 'autonomous'}.")

        if carried_context:
            lines.append("")
            lines.append("Carried context from prior session:")
            for k, v in carried_context.items():
                lines.append(f"  {k}: {v}")

        lines.append("")
        lines.append(
            "INSTRUCTION: This is an autonomous session. Proceed with the pack's "
            "protocol using the carried context. If key information is missing, "
            "note what is needed but continue with what is available."
        )
        lines.append("[/LOOP CONTEXT]")
        return "\n".join(lines)


# ─── Singleton ────────────────────────────────────────────

_session_factory: Optional[SessionFactory] = None


def init_session_factory(
    sessions=None, persistence=None, db=None,
) -> SessionFactory:
    """Initialize the global SessionFactory. Called during app lifespan."""
    global _session_factory
    _session_factory = SessionFactory(
        sessions=sessions, persistence=persistence, db=db,
    )
    logger.info("SessionFactory initialized (Loop Node 13)")
    return _session_factory


def get_session_factory() -> Optional[SessionFactory]:
    """Get the global SessionFactory instance."""
    return _session_factory
