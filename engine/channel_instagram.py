"""
13TMOS Instagram DM Channel — Meta Webhook

Same Meta platform as Messenger, nearly identical webhook shape.
Shares META_PAGE_TOKEN with Messenger.

Endpoints:
  GET  /channels/instagram/webhook  — Meta verification handshake
  POST /channels/instagram/webhook  — Inbound DM events
  GET  /channels/instagram/status   — Channel health check

Environment variables:
  META_PAGE_TOKEN         — shared with Messenger
  META_VERIFY_TOKEN       — shared with Messenger
  INSTAGRAM_DEFAULT_PACK  — default pack
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.instagram")

META_API = "https://graph.facebook.com/v18.0"

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


async def _send_instagram_message(recipient_id: str, text: str) -> None:
    token = os.getenv("META_PAGE_TOKEN", "")
    if not token:
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{META_API}/me/messages",
            params={"access_token": token},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text[:1000]},
            },
            timeout=15.0,
        )


INSTAGRAM_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Instagram:\n"
    "- Maximum 1000 characters per message.\n"
    "- Plain text only. No formatting.\n"
    "- Keep it brief and conversational.\n"
    "- Emojis are natural here.\n"
)


def register_instagram_channel(app: FastAPI) -> None:

    @app.get("/channels/instagram/webhook")
    async def instagram_verify(request: Request) -> Response:
        verify_token = os.getenv("META_VERIFY_TOKEN", "tmos13duck")
        params = dict(request.query_params)
        if (
            params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == verify_token
        ):
            return Response(content=params.get("hub.challenge", ""))
        return Response(content="Forbidden", status_code=403)

    @app.post("/channels/instagram/webhook")
    async def instagram_webhook(request: Request) -> Response:
        data = await request.json()

        if data.get("object") != "instagram":
            return Response(content="ok")

        from session_runner import CHANNEL_CONSTRAINTS
        if "instagram" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["instagram"] = INSTAGRAM_CONSTRAINT

        runner = _get_runner()
        default_pack = os.getenv("INSTAGRAM_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id", "")
                message = event.get("message", {})
                text = message.get("text", "").strip()

                if not text or not sender_id:
                    continue

                logger.info("Instagram inbound: user=%s length=%d", sender_id[-4:], len(text))

                try:
                    reply = await runner.handle_message(
                        channel="instagram",
                        sender_id=sender_id,
                        text=text,
                        default_pack=default_pack,
                    )
                except Exception:
                    logger.exception("Session runner error for Instagram")
                    reply = "Something went wrong. Please try again."

                if len(reply) > 1000:
                    reply = reply[:997] + "..."

                await _send_instagram_message(sender_id, reply)

        return Response(content="ok")

    @app.get("/channels/instagram/status")
    async def instagram_status():
        configured = bool(os.getenv("META_PAGE_TOKEN"))
        default_pack = os.getenv("INSTAGRAM_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'instagram' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "instagram",
            "status": "configured" if configured else "unconfigured",
            "default_pack": default_pack,
            "active_sessions": active,
        }

    logger.info("Instagram channel registered: POST /channels/instagram/webhook")
