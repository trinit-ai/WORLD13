"""
TMOS13 Session Store

Unified session management with in-memory primary and optional Redis persistence.
Sessions survive page refreshes when Redis is available.
"""
import logging
from dataclasses import asdict
from typing import Optional

from state import SessionState

logger = logging.getLogger("tmos13.sessions")

SESSION_TTL = 3600  # 1 hour


class SessionStore:
    """
    Two-tier session store: fast in-memory dict + optional Redis persistence.

    - get() checks memory first, then Redis (restoring on cache hit).
    - put() writes to both memory and Redis.
    - remove() deletes from both.
    """

    def __init__(self, cache=None):
        self._sessions: dict[str, SessionState] = {}
        self._cache = cache  # RedisCache instance (optional)

    # ─── Public API ──────────────────────────────────────

    def get(self, session_id: str) -> Optional[SessionState]:
        """Get a session by ID. Checks memory, then Redis."""
        state = self._sessions.get(session_id)
        if state is not None:
            return state

        # Try to restore from Redis
        if self._cache:
            data = self._cache.get_cached_session(session_id)
            if data:
                state = self._deserialize(data)
                self._sessions[session_id] = state
                logger.debug(f"Session {session_id} restored from cache")
                return state

        return None

    def put(self, state: SessionState) -> None:
        """Store a session. Writes to memory and Redis."""
        self._sessions[state.session_id] = state
        self._persist(state)

    def remove(self, session_id: str) -> Optional[SessionState]:
        """Remove a session. Returns the state if it existed."""
        state = self._sessions.pop(session_id, None)
        if self._cache:
            self._cache.delete_session(session_id)
        return state

    def touch(self, state: SessionState) -> None:
        """Persist current state to Redis without modifying memory."""
        self._persist(state)

    @property
    def count(self) -> int:
        return len(self._sessions)

    @property
    def all(self) -> dict[str, SessionState]:
        return self._sessions

    def ids(self) -> list[str]:
        return list(self._sessions.keys())

    # ─── Serialization ───────────────────────────────────

    def _persist(self, state: SessionState) -> None:
        """Write session to Redis (best-effort)."""
        if not self._cache:
            return
        try:
            data = asdict(state)
            self._cache.cache_session(state.session_id, data, SESSION_TTL)
        except Exception as e:
            logger.warning(f"Failed to persist session {state.session_id}: {e}")

    @staticmethod
    def _deserialize(data: dict) -> SessionState:
        """Reconstruct a SessionState from a dict.

        IMPORTANT: Every field that matters for session continuity must be
        restored here. Missing fields caused contact data loss (forms,
        receipt_tokens) when sessions were restored from Redis.
        """
        state = SessionState(
            session_id=data.get("session_id", ""),
            correlation_id=data.get("correlation_id", ""),
            user_id=data.get("user_id", "anonymous"),
            pack_id=data.get("pack_id", "guest"),
            current_game=data.get("current_game"),
            depth=data.get("depth", 0),
            games_played=data.get("games_played", []),
            mood=data.get("mood", "curious"),
            turn_count=data.get("turn_count", 0),
            session_start=data.get("session_start", 0.0),
            settings=data.get("settings", {}),
            history=data.get("history", []),
            max_history=data.get("max_history", 20),
            forms=data.get("forms", {}),
            receipt_tokens=data.get("receipt_tokens", []),
            tokens_input=data.get("tokens_input", 0),
            tokens_output=data.get("tokens_output", 0),
            playstop_state=data.get("playstop_state", "play"),
            active_channel=data.get("active_channel", "web"),
            timezone=data.get("timezone", "UTC"),
            is_returning=data.get("is_returning", False),
            prior_captured_fields=data.get("prior_captured_fields", {}),
            total_lifetime_turns=data.get("total_lifetime_turns", 0),
            session_number=data.get("session_number", 1),
            pack_source=data.get("pack_source", "system"),
            pack_owner_id=data.get("pack_owner_id"),
            company_name=data.get("company_name", ""),
            company_industry=data.get("company_industry", ""),
            company_location=data.get("company_location", ""),
            company_hours=data.get("company_hours", ""),
            company_contact_email=data.get("company_contact_email", ""),
            company_contact_phone=data.get("company_contact_phone", ""),
            company_website=data.get("company_website", ""),
            company_faqs=data.get("company_faqs", []),
            company_disclaimers=data.get("company_disclaimers", []),
            company_policies=data.get("company_policies", []),
        )
        return state
