"""
TMOS13 Cross-Session State Persistence

Saves and restores SessionState across sessions so returning users
pick up where they left off. State is server-enforced — the model
reads authoritative values from a JSONB snapshot, not reconstructed
conversation history.

Identity tiers (priority order):
  1. user_id (Supabase Auth UUID) — strongest
  2. contact_email (from Ambassador / form capture)
  3. fingerprint_hash (device/browser fingerprint) — weakest

Usage:
    svc = PersistenceService(supabase_client)
    prior = await svc.find_prior_session(pack_id, user_id=uid)
    if prior:
        session = svc.restore_to_session(prior, fresh_session)
"""
import logging
import time
from dataclasses import asdict, fields as dc_fields
from datetime import datetime, timezone
from typing import Optional

from state import SessionState

logger = logging.getLogger("tmos13.persistence")

# Fields that should NEVER be persisted (ephemeral per-session data)
_EPHEMERAL_FIELDS = frozenset({
    "session_id", "session_start", "history", "max_history",
    "is_returning", "persistent_session_id", "prior_captured_fields",
    "session_number",
    "pack_history", "pack_handoff_context",  # Multi-Pack Session (Plume Node 1)
    "session_memory",                         # Session Memory (Plume Node 2)
    "is_ai_session", "ai_turn_count", "ai_empty_turns",  # AI-to-AI (Plume Node 4)
    "identity_context", "prepopulated_fields",             # User Identity (Plume Node 6)
    "pipeline_context", "pipeline_instance_id",            # Pack Pipeline (Plume Node 5)
    "knowledge_context",                                   # Vault Knowledge (Plume Node 7)
    "consultation_context",                                # Self-Consulting (Plume Node 10)
    "battle_context", "pending_battle_move",               # Battle Protocol (Plume Node 8)
    "schedule_context",                                    # TimeKeeper (Plume Node 11)
    "registry_context",                                    # Pack Install (Plume Node 12)
    "is_loop_session", "loop_initiated_by",                # The Loop (Plume Node 13)
    "loop_chain_source", "loop_context",                   # The Loop (Plume Node 13)
    "feedback_context",                                    # Deliverable Feedback
    "consolidated_memory",                                 # Semantic Memory L2
    "pack_stats_context",                                  # Pack Intelligence
    "prior_transcript",                                    # Prior Conversation Snippet
})

# Fields restored from the persistent record metadata, not state_snapshot
_META_FIELDS = frozenset({
    "is_returning", "persistent_session_id", "prior_captured_fields",
    "total_lifetime_turns", "session_number",
})


def _serialize_state(state: SessionState, persistence_fields: list[str] | None = None) -> dict:
    """
    Serialize SessionState to a JSON-safe dict for JSONB storage.

    If persistence_fields is provided, only those top-level fields are
    included in captured_fields. The full state_snapshot always includes
    everything except ephemeral fields.
    """
    full = asdict(state)

    # Build state_snapshot (everything except ephemeral)
    snapshot = {k: v for k, v in full.items() if k not in _EPHEMERAL_FIELDS}

    # Build captured_fields (form data + any manifest-specified fields)
    captured = {}
    if state.forms:
        for form_id, form_data in state.forms.items():
            for fk, fv in form_data.items():
                if fk != "submitted_at" and fv is not None:
                    captured[fk] = fv

    if persistence_fields:
        for pf in persistence_fields:
            if pf in full and full[pf] is not None:
                captured[pf] = full[pf]

    return {
        "state_snapshot": snapshot,
        "captured_fields": captured,
    }


def _deserialize_state(snapshot: dict, target: SessionState) -> SessionState:
    """
    Restore fields from a state_snapshot into an existing SessionState.

    Only restores fields that exist on the SessionState dataclass.
    Conversation history is explicitly NOT restored (fresh start).
    """
    valid_field_names = {f.name for f in dc_fields(SessionState)}

    for key, value in snapshot.items():
        if key in _EPHEMERAL_FIELDS or key in _META_FIELDS:
            continue
        if key not in valid_field_names:
            continue
        try:
            setattr(target, key, value)
        except (TypeError, AttributeError):
            logger.debug(f"Skipping restore of field '{key}': incompatible type")

    return target


class PersistenceService:
    """Manages cross-session state lifecycle."""

    def __init__(self, supabase_client=None):
        self.db = supabase_client

    @property
    def enabled(self) -> bool:
        return self.db is not None

    async def find_prior_session(
        self,
        pack_id: str,
        user_id: str | None = None,
        contact_email: str | None = None,
        fingerprint: str | None = None,
    ) -> dict | None:
        """
        Look up prior persistent session by identity tier.
        Returns the full row as a dict if found, None otherwise.
        Priority: user_id > contact_email > fingerprint.
        """
        if not self.enabled:
            return None

        # Try each identity tier in priority order
        for id_col, id_val in [
            ("user_id", user_id),
            ("contact_email", contact_email),
            ("fingerprint_hash", fingerprint),
        ]:
            if not id_val:
                continue
            try:
                result = (
                    self.db.table("persistent_sessions")
                    .select("*")
                    .eq(id_col, id_val)
                    .eq("pack_id", pack_id)
                    .eq("status", "active")
                    .order("last_seen_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    logger.info(
                        f"Found prior session for {id_col}={id_val} pack={pack_id}"
                    )
                    return result.data[0]
            except Exception as e:
                logger.warning(f"Persistence lookup failed ({id_col}): {e}")

        return None

    async def save_session_state(
        self,
        session_state: SessionState,
        identity: dict,
        pack_id: str,
        persistence_fields: list[str] | None = None,
    ) -> bool:
        """
        Persist current session state.

        Called on interval (every N turns), on disconnect, and on threshold events.
        Upserts by identity + pack_id.
        """
        if not self.enabled:
            return False

        serialized = _serialize_state(session_state, persistence_fields)

        # Build the upsert row
        row = {
            "pack_id": pack_id,
            "cartridge_id": session_state.current_game,
            "state_snapshot": serialized["state_snapshot"],
            "captured_fields": serialized["captured_fields"],
            "depth": session_state.depth,
            "total_turns": session_state.total_lifetime_turns or session_state.turn_count,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "last_cartridge_visited": session_state.current_game,
            "cartridges_visited": list(set(session_state.games_played)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Set identity columns
        user_id = identity.get("user_id")
        contact_email = identity.get("contact_email")
        fingerprint = identity.get("fingerprint")

        if user_id and user_id != "anonymous":
            row["user_id"] = user_id
        if contact_email:
            row["contact_email"] = contact_email
        if fingerprint:
            row["fingerprint_hash"] = fingerprint

        # Determine upsert conflict column
        if user_id and user_id != "anonymous":
            conflict_col = "uq_persistent_sessions_user"
        elif contact_email:
            conflict_col = "uq_persistent_sessions_email"
        else:
            # Fingerprint has no unique index; do a manual check
            return await self._save_fingerprint_session(row, fingerprint, pack_id)

        try:
            # Set fields only for insert (not update)
            if not row.get("first_seen_at"):
                row["first_seen_at"] = datetime.now(timezone.utc).isoformat()

            self.db.table("persistent_sessions").upsert(
                row, on_conflict=conflict_col
            ).execute()
            logger.debug(f"Persisted session state for pack={pack_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to persist session state: {e}")
            return False

    async def _save_fingerprint_session(
        self, row: dict, fingerprint: str, pack_id: str
    ) -> bool:
        """Save/update a fingerprint-identified session (no unique constraint)."""
        if not fingerprint:
            return False
        try:
            # Check for existing
            existing = (
                self.db.table("persistent_sessions")
                .select("id")
                .eq("fingerprint_hash", fingerprint)
                .eq("pack_id", pack_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if existing.data:
                # Update existing
                self.db.table("persistent_sessions").update(row).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            else:
                row["fingerprint_hash"] = fingerprint
                self.db.table("persistent_sessions").insert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"Failed to persist fingerprint session: {e}")
            return False

    def restore_to_session(
        self, persistent_data: dict, current_session: SessionState
    ) -> SessionState:
        """
        Merge persisted state into a fresh session.

        Restores: captured fields, qualification score, depth,
        cartridges_visited, cross_module_memory, form_submissions,
        pack-specific sub-states.

        Does NOT restore: conversation history, mood, session_id.
        """
        snapshot = persistent_data.get("state_snapshot", {})

        # Restore structured state fields
        _deserialize_state(snapshot, current_session)

        # Set persistence metadata
        current_session.is_returning = True
        current_session.persistent_session_id = persistent_data.get("id")
        current_session.prior_captured_fields = persistent_data.get(
            "captured_fields", {}
        )
        current_session.total_lifetime_turns = persistent_data.get("total_turns", 0)
        current_session.session_number = persistent_data.get("total_sessions", 0) + 1

        # Reset ephemeral state for fresh session
        current_session.history = []
        current_session.mood = "curious"
        current_session.turn_count = 0

        logger.info(
            f"Restored persistent session: pack={current_session.pack_id} "
            f"session_number={current_session.session_number} "
            f"lifetime_turns={current_session.total_lifetime_turns}"
        )
        return current_session

    async def mark_resolved(
        self,
        pack_id: str,
        identity: dict,
        resolution_summary: str = "",
    ) -> bool:
        """Mark a persistent session as resolved (case filed, lead converted, etc.)."""
        if not self.enabled:
            return False

        now = datetime.now(timezone.utc).isoformat()
        update = {
            "status": "resolved",
            "resolved_at": now,
            "resolution_summary": resolution_summary,
            "updated_at": now,
        }

        for id_col, id_val in [
            ("user_id", identity.get("user_id")),
            ("contact_email", identity.get("contact_email")),
            ("fingerprint_hash", identity.get("fingerprint")),
        ]:
            if not id_val:
                continue
            try:
                self.db.table("persistent_sessions").update(update).eq(
                    id_col, id_val
                ).eq("pack_id", pack_id).eq("status", "active").execute()
                return True
            except Exception as e:
                logger.warning(f"Failed to mark session resolved: {e}")

        return False

    async def list_sessions(self, user_id: str) -> list[dict]:
        """List all active persistent sessions for a user."""
        if not self.enabled:
            return []

        try:
            result = (
                self.db.table("persistent_sessions")
                .select(
                    "id, pack_id, cartridge_id, total_turns, total_sessions, "
                    "last_seen_at, last_cartridge_visited, status, captured_fields"
                )
                .eq("user_id", user_id)
                .eq("status", "active")
                .order("last_seen_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to list persistent sessions: {e}")
            return []

    async def delete_session(self, user_id: str, pack_id: str) -> bool:
        """Delete a persistent session (user requests fresh start)."""
        if not self.enabled:
            return False

        try:
            self.db.table("persistent_sessions").update(
                {
                    "status": "archived",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("user_id", user_id).eq("pack_id", pack_id).eq(
                "status", "active"
            ).execute()
            return True
        except Exception as e:
            logger.warning(f"Failed to delete persistent session: {e}")
            return False

    async def increment_session_count(
        self, pack_id: str, identity: dict
    ) -> None:
        """Increment total_sessions counter on the persistent record."""
        if not self.enabled:
            return

        for id_col, id_val in [
            ("user_id", identity.get("user_id")),
            ("contact_email", identity.get("contact_email")),
        ]:
            if not id_val:
                continue
            try:
                # Read current value, increment, write back
                result = (
                    self.db.table("persistent_sessions")
                    .select("total_sessions")
                    .eq(id_col, id_val)
                    .eq("pack_id", pack_id)
                    .eq("status", "active")
                    .limit(1)
                    .execute()
                )
                if result.data:
                    current = result.data[0].get("total_sessions", 1)
                    self.db.table("persistent_sessions").update(
                        {"total_sessions": current + 1}
                    ).eq(id_col, id_val).eq("pack_id", pack_id).execute()
                return
            except Exception as e:
                logger.warning(f"Failed to increment session count: {e}")
