"""
TMOS13 Notifications — OneSignal Integration

Push notifications for session reminders, new module alerts,
achievement unlocks, and billing events.
"""
import logging
from typing import Optional

logger = logging.getLogger("tmos13.notifications")

_onesignal = None
_app_id = ""
_initialized = False


def init_notifications(api_key: str, app_id: str):
    """Initialize OneSignal push notification service."""
    global _onesignal, _app_id, _initialized

    if not api_key or not app_id:
        logger.info("OneSignal not configured — notifications disabled")
        return

    _app_id = app_id
    try:
        import onesignal_sdk.client
        _onesignal = onesignal_sdk.client.Client(
            app_id=app_id,
            rest_api_key=api_key,
        )
        _initialized = True
        logger.info("OneSignal notifications initialized")
    except ImportError:
        logger.warning("onesignal-sdk not installed — notifications disabled")
    except Exception as e:
        logger.error(f"OneSignal init failed: {e}")


def send_to_user(user_id: str, title: str, message: str, data: dict = None,
                 url: str = None) -> Optional[str]:
    """Send a push notification to a specific user."""
    if not _onesignal or not _initialized:
        logger.info(f"Notification suppressed: user={user_id} title={title}")
        return None

    try:
        body = {
            "include_external_user_ids": [user_id],
            "headings": {"en": title},
            "contents": {"en": message},
        }
        if data:
            body["data"] = data
        if url:
            body["url"] = url

        response = _onesignal.send_notification(body)
        notif_id = response.body.get("id", "unknown")
        logger.info(f"Notification sent: user={user_id} id={notif_id}")
        return notif_id
    except Exception as e:
        logger.error(f"Notification send failed: {e}")
        return None


def send_to_segment(segment: str, title: str, message: str, data: dict = None):
    """Send a push notification to a user segment."""
    if not _onesignal or not _initialized:
        return None

    try:
        body = {
            "included_segments": [segment],
            "headings": {"en": title},
            "contents": {"en": message},
        }
        if data:
            body["data"] = data
        return _onesignal.send_notification(body)
    except Exception as e:
        logger.error(f"Segment notification failed: {e}")
        return None


# ─── TMOS13-Specific Notifications ──────────────────────

def notify_new_cartridge(user_id: str, cartridge_name: str):
    send_to_user(
        user_id,
        "New Cartridge Available",
        f"'{cartridge_name}' has been added. Ready to explore?",
        data={"type": "new_cartridge", "cartridge": cartridge_name},
    )


def notify_egg_found(user_id: str, egg_name: str):
    send_to_user(
        user_id,
        "Dinosaur Egg Discovered",
        f"You found '{egg_name}'! Check your Fossil Record.",
        data={"type": "egg_found", "egg": egg_name},
    )


def notify_subscription_expiring(user_id: str, days_left: int):
    send_to_user(
        user_id,
        "Subscription Expiring",
        f"Your TMOS13 Pro subscription expires in {days_left} day{'s' if days_left != 1 else ''}.",
        data={"type": "sub_expiring", "days": days_left},
    )


def notify_session_reminder(user_id: str, last_cartridge: str = None):
    msg = "Your session is waiting. Come back and explore."
    if last_cartridge:
        msg = f"Your last session in '{last_cartridge}' is waiting. Pick up where you left off."
    send_to_user(user_id, "Session Available", msg, data={"type": "session_reminder"})


def get_status() -> dict:
    return {
        "enabled": _initialized,
        "backend": "onesignal" if _initialized else "none",
    }
