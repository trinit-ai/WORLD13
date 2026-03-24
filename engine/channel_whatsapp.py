"""
13TMOS WhatsApp Channel — Twilio Webhook Handler

Receives inbound WhatsApp messages via Twilio webhook,
routes them through the SessionRunner, returns TwiML responses.

Endpoints:
  POST /channels/whatsapp/webhook  — Twilio inbound webhook
  GET  /channels/whatsapp/status   — Channel health check

Environment variables:
  TWILIO_ACCOUNT_SID   — Twilio account SID
  TWILIO_AUTH_TOKEN     — Twilio auth token
  TWILIO_WHATSAPP_FROM — Twilio WhatsApp sender (e.g., whatsapp:+14155238886)
  TMOS13_WHATSAPP_PACK — Default pack for WhatsApp sessions (optional)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.whatsapp")

# Lazy import — SessionRunner is heavy, only load when needed
_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    """Validate Twilio request signature for webhook security.

    Returns True if validation passes or if auth token is not configured
    (development mode with explicit env flag).
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False

    # Reconstruct the URL Twilio used to sign
    url = str(request.url)
    # Parse form body into sorted params
    try:
        form_str = body.decode("utf-8")
        params = {}
        for pair in form_str.split("&"):
            if "=" in pair:
                from urllib.parse import unquote_plus
                k, v = pair.split("=", 1)
                params[unquote_plus(k)] = unquote_plus(v)
    except Exception:
        return False

    # Build the validation string: URL + sorted param key/value pairs
    data_str = url
    for key in sorted(params.keys()):
        data_str += key + params[key]

    # HMAC-SHA1 comparison
    expected = hmac.new(
        auth_token.encode("utf-8"),
        data_str.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    import base64
    expected_b64 = base64.b64encode(expected).decode("utf-8")
    return hmac.compare_digest(expected_b64, signature)


def _twiml_response(body: str) -> Response:
    """Wrap response text in TwiML MessagingResponse XML."""
    # Escape XML entities
    escaped = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{escaped}</Message>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


def register_whatsapp_channel(app: FastAPI) -> None:
    """Register WhatsApp webhook and status endpoints."""

    @app.post("/channels/whatsapp/webhook")
    async def whatsapp_webhook(request: Request):
        """Twilio inbound WhatsApp webhook."""
        body = await request.body()

        # Validate Twilio signature
        if not _validate_twilio_signature(request, body):
            logger.warning("Invalid Twilio signature — rejecting webhook")
            return Response(status_code=403, content="Invalid signature")

        # Parse form data
        form = await request.form()
        from_number = form.get("From", "")         # e.g. whatsapp:+15551234567
        message_body = form.get("Body", "").strip()
        # profile_name = form.get("ProfileName", "")  # WhatsApp display name

        if not from_number or not message_body:
            return _twiml_response("Empty message received.")

        # Strip whatsapp: prefix for session keying
        sender_id = from_number.replace("whatsapp:", "").strip()

        logger.info("WhatsApp inbound: from=%s length=%d", sender_id[-4:], len(message_body))

        # Route through session runner
        runner = _get_runner()
        default_pack = os.getenv("TMOS13_WHATSAPP_PACK", os.getenv("TMOS13_PACK", "guest"))

        try:
            reply = await runner.handle_message(
                channel="whatsapp",
                sender_id=sender_id,
                text=message_body,
                default_pack=default_pack,
            )
        except Exception as e:
            logger.exception("Session runner error for WhatsApp message")
            reply = "Something went wrong. Please try again."

        # Truncate for WhatsApp limit
        if len(reply) > 1600:
            reply = reply[:1597] + "..."

        logger.info("WhatsApp reply: to=%s length=%d", sender_id[-4:], len(reply))
        return _twiml_response(reply)

    @app.get("/channels/whatsapp/status")
    async def whatsapp_status():
        """WhatsApp channel health check."""
        has_sid = bool(os.getenv("TWILIO_ACCOUNT_SID"))
        has_token = bool(os.getenv("TWILIO_AUTH_TOKEN"))
        has_from = bool(os.getenv("TWILIO_WHATSAPP_FROM"))
        default_pack = os.getenv("TMOS13_WHATSAPP_PACK", os.getenv("TMOS13_PACK", "guest"))

        # Count active WhatsApp sessions
        active_sessions = 0
        try:
            runner = _get_runner()
            row = runner.conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'whatsapp' AND status = 'active'"
            ).fetchone()
            active_sessions = row["cnt"] if row else 0
        except Exception:
            pass

        configured = has_sid and has_token and has_from
        return {
            "channel": "whatsapp",
            "status": "configured" if configured else "unconfigured",
            "twilio_sid": "set" if has_sid else "missing",
            "twilio_token": "set" if has_token else "missing",
            "twilio_from": "set" if has_from else "missing",
            "default_pack": default_pack,
            "active_sessions": active_sessions,
        }

    logger.info("WhatsApp channel registered: POST /channels/whatsapp/webhook, GET /channels/whatsapp/status")
