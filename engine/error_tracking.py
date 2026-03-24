"""
TMOS13 Error Tracking — Sentry Integration

Captures exceptions, performance traces, and user context.
Gracefully disabled when SENTRY_DSN is not set.
"""
import logging
from typing import Optional
from functools import wraps

from fastapi import Request

logger = logging.getLogger("tmos13.errors")

_sentry_sdk = None
_initialized = False


def init_sentry(dsn: str, environment: str = "development", release: str = "2.2.0",
                traces_sample_rate: float = 0.2, profiles_sample_rate: float = 0.1):
    """Initialize Sentry SDK."""
    global _sentry_sdk, _initialized

    if not dsn:
        logger.info("Sentry DSN not configured — error tracking disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=f"tmos13@{release}",
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],
            send_default_pii=False,
            before_send=_before_send,
        )
        _sentry_sdk = sentry_sdk
        _initialized = True
        logger.info(f"Sentry initialized: env={environment}")
    except ImportError:
        logger.warning("sentry-sdk not installed — error tracking disabled")
    except Exception as e:
        logger.error(f"Sentry init failed: {e}")


def _before_send(event, hint):
    """Scrub sensitive data before sending to Sentry."""
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        # Remove auth tokens
        event["request"]["headers"] = {
            k: v for k, v in headers.items()
            if k.lower() not in ("authorization", "cookie", "x-api-key")
        }
    return event


def capture_exception(error: Exception, **context):
    """Capture an exception with optional context."""
    if _sentry_sdk and _initialized:
        with _sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            _sentry_sdk.capture_exception(error)
    logger.error(f"Captured exception: {error}", exc_info=True)


def capture_message(message: str, level: str = "info", **context):
    """Capture a message event."""
    if _sentry_sdk and _initialized:
        with _sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            _sentry_sdk.capture_message(message, level=level)


def set_user(user_id: str, email: str = None, tier: str = None):
    """Set user context for Sentry events."""
    if _sentry_sdk and _initialized:
        _sentry_sdk.set_user({
            "id": user_id,
            "email": email,
            "subscription": tier,
        })


def set_tag(key: str, value: str):
    """Set a tag on the current scope."""
    if _sentry_sdk and _initialized:
        _sentry_sdk.set_tag(key, value)


def start_transaction(name: str, op: str = "task"):
    """Start a performance transaction."""
    if _sentry_sdk and _initialized:
        return _sentry_sdk.start_transaction(name=name, op=op)
    return _NoOpContext()


class _NoOpContext:
    """No-op context manager when Sentry is disabled."""
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def set_status(self, status): pass
    def finish(self): pass


def get_status() -> dict:
    """Get error tracking status."""
    return {
        "enabled": _initialized,
        "backend": "sentry" if _initialized else "none",
    }
