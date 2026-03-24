"""
TMOS13 Rate Guard — Distillation Rate Limiting

Enforces per-user and per-session rate limits designed to prevent
industrial-scale distillation attacks:

  - Max 20 sessions per hour per user
  - Max 50 exchanges per session
  - Max 3 concurrent sessions per user

These limits are above normal human usage thresholds but below what
automated extraction tools would require to systematically distill
protocol content.
"""
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("tmos13.rate_guard")

# ─── Defaults ───────────────────────────────────────────

DEFAULT_MAX_SESSIONS_PER_HOUR = 20
DEFAULT_MAX_EXCHANGES_PER_SESSION = 50
DEFAULT_MAX_CONCURRENT_SESSIONS = 3
DEFAULT_SESSION_WINDOW_SECONDS = 3600  # 1 hour


@dataclass
class RateGuardResult:
    """Result of a rate guard check."""
    allowed: bool = True
    reason: str = ""
    limit_type: str = ""  # "session_rate" | "exchange_limit" | "concurrent_sessions"


class DistillationRateGuard:
    """
    Per-user rate limiter focused on distillation prevention.

    Tracks:
      - session_counts: user_id → list of session start timestamps (sliding window)
      - exchange_counts: session_id → int exchange count
      - concurrent_sessions: user_id → set of active session IDs
    """

    def __init__(
        self,
        max_sessions_per_hour: int = DEFAULT_MAX_SESSIONS_PER_HOUR,
        max_exchanges_per_session: int = DEFAULT_MAX_EXCHANGES_PER_SESSION,
        max_concurrent_sessions: int = DEFAULT_MAX_CONCURRENT_SESSIONS,
        session_window_seconds: int = DEFAULT_SESSION_WINDOW_SECONDS,
    ):
        self.max_sessions_per_hour = max_sessions_per_hour
        self.max_exchanges_per_session = max_exchanges_per_session
        self.max_concurrent_sessions = max_concurrent_sessions
        self.session_window_seconds = session_window_seconds

        # user_id → list of session start timestamps
        self._session_counts: dict[str, list[float]] = {}

        # session_id → exchange count
        self._exchange_counts: dict[str, int] = {}

        # user_id → set of active session IDs
        self._concurrent_sessions: dict[str, set[str]] = {}

    def register_session(self, session_id: str, user_id: str) -> RateGuardResult:
        """
        Register a new session. Checks session rate and concurrent limits.

        Should be called when a session is created.
        """
        if user_id == "anonymous":
            # Track anonymous sessions but don't enforce rate limits
            self._exchange_counts[session_id] = 0
            return RateGuardResult(allowed=True)

        now = time.time()

        # ─── Session rate check ───────────────────────
        if user_id not in self._session_counts:
            self._session_counts[user_id] = []

        # Prune expired entries
        cutoff = now - self.session_window_seconds
        self._session_counts[user_id] = [
            ts for ts in self._session_counts[user_id] if ts >= cutoff
        ]

        if len(self._session_counts[user_id]) >= self.max_sessions_per_hour:
            logger.warning(
                "Rate guard: session_rate limit user=%s count=%d",
                user_id, len(self._session_counts[user_id]),
            )
            return RateGuardResult(
                allowed=False,
                reason=f"Too many sessions. Please wait before starting a new session.",
                limit_type="session_rate",
            )

        # ─── Concurrent session check ─────────────────
        if user_id not in self._concurrent_sessions:
            self._concurrent_sessions[user_id] = set()

        if len(self._concurrent_sessions[user_id]) >= self.max_concurrent_sessions:
            logger.warning(
                "Rate guard: concurrent_sessions limit user=%s count=%d",
                user_id, len(self._concurrent_sessions[user_id]),
            )
            return RateGuardResult(
                allowed=False,
                reason="Too many active sessions. Please close an existing session first.",
                limit_type="concurrent_sessions",
            )

        # Register
        self._session_counts[user_id].append(now)
        self._concurrent_sessions[user_id].add(session_id)
        self._exchange_counts[session_id] = 0

        return RateGuardResult(allowed=True)

    def check(self, session_id: str, user_id: str = "anonymous") -> RateGuardResult:
        """
        Check rate limits for an exchange within a session.

        Should be called before each Claude API call in the pipeline.
        """
        # ─── Exchange count check ─────────────────────
        if session_id not in self._exchange_counts:
            self._exchange_counts[session_id] = 0

        self._exchange_counts[session_id] += 1

        if self._exchange_counts[session_id] > self.max_exchanges_per_session:
            logger.warning(
                "Rate guard: exchange_limit session=%s count=%d",
                session_id, self._exchange_counts[session_id],
            )
            return RateGuardResult(
                allowed=False,
                reason="Session exchange limit reached. Please start a new session.",
                limit_type="exchange_limit",
            )

        return RateGuardResult(allowed=True)

    def close_session(self, session_id: str, user_id: str = "anonymous") -> None:
        """
        Clean up when a session closes.

        Should be called on session teardown.
        """
        self._exchange_counts.pop(session_id, None)

        if user_id != "anonymous" and user_id in self._concurrent_sessions:
            self._concurrent_sessions[user_id].discard(session_id)
            if not self._concurrent_sessions[user_id]:
                del self._concurrent_sessions[user_id]

    def get_stats(self, user_id: str = "") -> dict:
        """Return current rate guard statistics for diagnostics."""
        if user_id and user_id != "anonymous":
            now = time.time()
            cutoff = now - self.session_window_seconds
            session_timestamps = self._session_counts.get(user_id, [])
            recent = [ts for ts in session_timestamps if ts >= cutoff]
            return {
                "user_id": user_id,
                "sessions_in_window": len(recent),
                "max_sessions_per_hour": self.max_sessions_per_hour,
                "concurrent_sessions": len(
                    self._concurrent_sessions.get(user_id, set())
                ),
                "max_concurrent": self.max_concurrent_sessions,
            }
        return {
            "total_tracked_users": len(self._session_counts),
            "total_active_sessions": len(self._exchange_counts),
        }

    def reset(self) -> None:
        """Reset all state (for testing)."""
        self._session_counts.clear()
        self._exchange_counts.clear()
        self._concurrent_sessions.clear()


# ─── Module-level singleton ─────────────────────────────

_rate_guard: DistillationRateGuard | None = None


def get_rate_guard() -> DistillationRateGuard:
    """Get or create the singleton rate guard instance."""
    global _rate_guard
    if _rate_guard is None:
        _rate_guard = DistillationRateGuard()
    return _rate_guard
