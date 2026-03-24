"""
13TMOS SMS Channel — Twilio SMS Inbound Webhook

Nearly identical to channel_whatsapp.py minus the whatsapp: prefix.
Uses existing TWILIO_AUTH_TOKEN from Session 14.

Endpoints:
  POST /channels/sms/webhook  — Twilio SMS inbound
  GET  /channels/sms/status   — Channel health check
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.sms")

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return True
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False
    try:
        from urllib.parse import unquote_plus
        form_str = body.decode("utf-8")
        params = {}
        for pair in form_str.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[unquote_plus(k)] = unquote_plus(v)
    except Exception:
        return False
    data_str = str(request.url)
    for key in sorted(params.keys()):
        data_str += key + params[key]
    import base64
    expected = base64.b64encode(
        hmac.new(auth_token.encode(), data_str.encode(), hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def _twiml_response(body: str) -> Response:
    escaped = (
        body.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escaped}</Message></Response>"
    )
    return Response(content=xml, media_type="application/xml")


def register_sms_channel(app: FastAPI) -> None:

    @app.post("/channels/sms/webhook")
    async def sms_webhook(request: Request):
        body = await request.body()
        if not _validate_twilio_signature(request, body):
            return Response(status_code=403, content="Invalid signature")

        form = await request.form()
        from_number = form.get("From", "")
        message_body = form.get("Body", "").strip()

        if not from_number or not message_body:
            return _twiml_response("Empty message received.")

        sender_id = from_number.strip()
        logger.info("SMS inbound: from=%s length=%d", sender_id[-4:], len(message_body))

        runner = _get_runner()
        default_pack = os.getenv("SMS_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

        try:
            reply = await runner.handle_message(
                channel="sms",
                sender_id=sender_id,
                text=message_body,
                default_pack=default_pack,
            )
        except Exception:
            logger.exception("Session runner error for SMS")
            reply = "Something went wrong. Please try again."

        if len(reply) > 1600:
            reply = reply[:1597] + "..."

        return _twiml_response(reply)

    @app.get("/channels/sms/status")
    async def sms_status():
        has_token = bool(os.getenv("TWILIO_AUTH_TOKEN"))
        default_pack = os.getenv("SMS_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'sms' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "sms",
            "status": "configured" if has_token else "unconfigured",
            "default_pack": default_pack,
            "active_sessions": active,
        }

    logger.info("SMS channel registered: POST /channels/sms/webhook")
