"""
13TMOS Telegram Channel — Bot API Webhook Handler

Receives inbound Telegram messages via Bot API webhook,
routes them through the SessionRunner, replies via Bot API.

No SDK needed — plain HTTP via httpx.

Endpoints:
  POST /channels/telegram/{token}  — Telegram webhook (token in URL for security)
  GET  /channels/telegram/status   — Channel health check

Environment variables:
  TELEGRAM_BOT_TOKEN     — from @BotFather
  TELEGRAM_DEFAULT_PACK  — default pack for Telegram sessions (optional)
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.telegram")

# Lazy runner
_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


async def send_telegram_message(chat_id: int | str, text: str) -> None:
    """Send a message via Telegram Bot API."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=15.0,
        )


# Channel rendering constraint
TELEGRAM_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Telegram:\n"
    "- Telegram supports basic Markdown: *bold*, _italic_, `code`.\n"
    "- Keep responses under 4000 characters.\n"
    "- Use line breaks for structure.\n"
    "- Emojis are fine.\n"
)


def register_telegram_channel(app: FastAPI) -> None:
    """Register Telegram webhook and status endpoints."""

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    @app.post(f"/channels/telegram/{token}" if token else "/channels/telegram/unconfigured")
    async def telegram_webhook(request: Request) -> Response:
        """Telegram Bot API webhook. URL includes token as security."""
        update = await request.json()

        # Only handle text messages
        message = update.get("message")
        if not message:
            return Response(content="ok")

        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        from_user = message.get("from", {})
        first_name = from_user.get("first_name", "")

        if not text:
            return Response(content="ok")

        # sender_id is the chat_id — unique per Telegram user
        sender_id = str(chat_id)

        logger.info("Telegram inbound: chat=%s name=%s length=%d",
                     sender_id[-4:], first_name, len(text))

        runner = _get_runner()
        default_pack = os.getenv("TELEGRAM_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

        # Inject the Telegram constraint into session_runner's channel constraints
        from session_runner import CHANNEL_CONSTRAINTS
        if "telegram" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["telegram"] = TELEGRAM_CONSTRAINT

        try:
            reply = await runner.handle_message(
                channel="telegram",
                sender_id=sender_id,
                text=text,
                default_pack=default_pack,
            )
        except Exception:
            logger.exception("Session runner error for Telegram message")
            reply = "Something went wrong. Please try again."

        # Truncate for Telegram limit
        if len(reply) > 4000:
            reply = reply[:3997] + "..."

        await send_telegram_message(chat_id, reply)
        return Response(content="ok")

    @app.get("/channels/telegram/status")
    async def telegram_status():
        """Telegram channel health check."""
        configured = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        default_pack = os.getenv("TELEGRAM_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

        bot_info = None
        if configured:
            try:
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f"https://api.telegram.org/bot{bot_token}/getMe",
                        timeout=5.0,
                    )
                    bot_info = r.json().get("result", {})
            except Exception:
                pass

        active_sessions = 0
        try:
            runner = _get_runner()
            row = runner.conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'telegram' AND status IN ('active', 'seeded')"
            ).fetchone()
            active_sessions = row["cnt"] if row else 0
        except Exception:
            pass

        return {
            "channel": "telegram",
            "status": "configured" if configured else "unconfigured",
            "bot_token": "set" if configured else "missing",
            "default_pack": default_pack,
            "active_sessions": active_sessions,
            "bot": bot_info,
        }

    logger.info("Telegram channel registered: POST /channels/telegram/{token}, GET /channels/telegram/status")
