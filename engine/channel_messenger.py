"""
13TMOS Facebook Messenger Channel — Meta Webhook

Verify token handshake + inbound message events + reply via Send API.

Endpoints:
  GET  /channels/messenger/webhook  — Meta verification handshake
  POST /channels/messenger/webhook  — Inbound message events
  GET  /channels/messenger/status   — Channel health check

Environment variables:
  META_PAGE_TOKEN       — Page access token from Meta Developer Console
  META_VERIFY_TOKEN     — Webhook verification token (you choose this)
  MESSENGER_DEFAULT_PACK — default pack
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.messenger")

META_API = "https://graph.facebook.com/v18.0"

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


async def _send_messenger_message(recipient_id: str, text: str) -> None:
    token = os.getenv("META_PAGE_TOKEN", "")
    if not token:
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{META_API}/me/messages",
            params={"access_token": token},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text[:2000]},
            },
            timeout=15.0,
        )


MESSENGER_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Messenger:\n"
    "- Maximum 2000 characters per message.\n"
    "- Plain text only. No markdown.\n"
    "- Keep responses conversational and concise.\n"
)


def register_messenger_channel(app: FastAPI) -> None:

    @app.get("/channels/messenger/webhook")
    async def messenger_verify(request: Request) -> Response:
        """Meta webhook verification handshake."""
        verify_token = os.getenv("META_VERIFY_TOKEN", "tmos13duck")
        params = dict(request.query_params)
        if (
            params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == verify_token
        ):
            return Response(content=params.get("hub.challenge", ""))
        return Response(content="Forbidden", status_code=403)

    @app.post("/channels/messenger/webhook")
    async def messenger_webhook(request: Request) -> Response:
        data = await request.json()

        if data.get("object") != "page":
            return Response(content="ok")

        from session_runner import CHANNEL_CONSTRAINTS
        if "messenger" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["messenger"] = MESSENGER_CONSTRAINT

        runner = _get_runner()
        default_pack = os.getenv("MESSENGER_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id", "")
                message = event.get("message", {})
                text = message.get("text", "").strip()

                if not text or not sender_id:
                    continue

                logger.info("Messenger inbound: user=%s length=%d", sender_id[-4:], len(text))

                try:
                    reply = await runner.handle_message(
                        channel="messenger",
                        sender_id=sender_id,
                        text=text,
                        default_pack=default_pack,
                    )
                except Exception:
                    logger.exception("Session runner error for Messenger")
                    reply = "Something went wrong. Please try again."

                await _send_messenger_message(sender_id, reply)

        return Response(content="ok")

    @app.get("/channels/messenger/status")
    async def messenger_status():
        configured = bool(os.getenv("META_PAGE_TOKEN"))
        default_pack = os.getenv("MESSENGER_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'messenger' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "messenger",
            "status": "configured" if configured else "unconfigured",
            "default_pack": default_pack,
            "active_sessions": active,
        }

    logger.info("Messenger channel registered: POST /channels/messenger/webhook")
