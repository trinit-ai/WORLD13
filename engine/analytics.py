"""
TMOS13 Analytics — PostHog Integration

Product analytics for tracking user engagement, module usage,
depth progression, and feature adoption. Respects user consent.
"""
import time
import logging
from typing import Optional

logger = logging.getLogger("tmos13.analytics")

_posthog = None
_initialized = False


def init_analytics(api_key: str, host: str = "https://app.posthog.com"):
    """Initialize PostHog analytics."""
    global _posthog, _initialized

    if not api_key:
        logger.info("PostHog API key not configured — analytics disabled")
        return

    try:
        import posthog
        posthog.api_key = api_key
        posthog.host = host
        posthog.debug = False
        posthog.on_error = lambda e, items: logger.warning(f"PostHog error: {e}")
        _posthog = posthog
        _initialized = True
        logger.info(f"PostHog analytics initialized: {host}")
    except ImportError:
        logger.warning("posthog not installed — analytics disabled")
    except Exception as e:
        logger.error(f"PostHog init failed: {e}")


def identify(user_id: str, properties: dict = None):
    """Identify a user with properties."""
    if _posthog and _initialized:
        _posthog.identify(user_id, properties or {})


def track(user_id: str, event: str, properties: dict = None):
    """Track an event."""
    if _posthog and _initialized:
        _posthog.capture(
            distinct_id=user_id,
            event=event,
            properties={**(properties or {}), "timestamp": time.time()},
        )


def track_page(user_id: str, page: str, properties: dict = None):
    """Track a page view."""
    track(user_id, "$pageview", {"$current_url": page, **(properties or {})})


# ─── TMOS13-Specific Events ─────────────────────────────

def track_session_start(user_id: str, session_id: str):
    track(user_id, "session_started", {"session_id": session_id})


def track_session_end(user_id: str, session_id: str, duration_s: float, turn_count: int):
    track(user_id, "session_ended", {
        "session_id": session_id,
        "duration_seconds": round(duration_s, 1),
        "turn_count": turn_count,
    })


def track_cartridge_load(user_id: str, cartridge: str, session_id: str):
    track(user_id, "cartridge_loaded", {"cartridge": cartridge, "session_id": session_id})


def track_cartridge_exit(user_id: str, cartridge: str, turns: int, depth: int):
    track(user_id, "cartridge_exited", {
        "cartridge": cartridge, "turns": turns, "depth": depth,
    })


def track_depth_change(user_id: str, old_depth: int, new_depth: int, cartridge: str = None):
    track(user_id, "depth_changed", {
        "old_depth": old_depth, "new_depth": new_depth,
        "cartridge": cartridge, "direction": "up" if new_depth > old_depth else "down",
    })


def track_egg_found(user_id: str, egg_id: str, context: str = ""):
    track(user_id, "egg_found", {"egg_id": egg_id, "context": context})


def track_command(user_id: str, command: str, context: str = ""):
    track(user_id, "command_used", {"command": command, "context": context})


def track_auth_event(user_id: str, action: str, provider: str = "email"):
    track(user_id, "auth_event", {"action": action, "provider": provider})


def track_billing_event(user_id: str, action: str, tier: str = "", amount: int = 0):
    track(user_id, "billing_event", {"action": action, "tier": tier, "amount_cents": amount})


def track_error(user_id: str, error_type: str, message: str):
    track(user_id, "error_occurred", {"error_type": error_type, "message": message[:200]})


def track_claude_call(user_id: str, latency_ms: float, tokens: int, cartridge: str = None):
    track(user_id, "claude_api_call", {
        "latency_ms": round(latency_ms, 1),
        "estimated_tokens": tokens,
        "cartridge": cartridge,
    })


# ─── Feature Flags (via PostHog) ────────────────────────

def is_feature_enabled(user_id: str, feature_key: str, default: bool = False) -> bool:
    """Check if a feature flag is enabled for a user."""
    if _posthog and _initialized:
        try:
            return _posthog.feature_enabled(feature_key, user_id, default)
        except Exception:
            return default
    return default


# ─── Group Analytics ─────────────────────────────────────

def set_group(user_id: str, group_type: str, group_key: str, properties: dict = None):
    """Associate a user with a group (e.g., team, organization)."""
    if _posthog and _initialized:
        _posthog.group_identify(group_type, group_key, properties or {})
        _posthog.capture(user_id, "$groupidentify", {
            "$group_type": group_type,
            "$group_key": group_key,
        })


def flush():
    """Flush pending events."""
    if _posthog and _initialized:
        _posthog.flush()


def shutdown():
    """Graceful shutdown."""
    if _posthog and _initialized:
        _posthog.flush()
        _posthog.shutdown()


def get_status() -> dict:
    return {
        "enabled": _initialized,
        "backend": "posthog" if _initialized else "none",
    }
