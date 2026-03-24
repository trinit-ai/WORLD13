"""
13TMOS Discord Channel — Bot Interactions Endpoint

Handles Discord interactions (PING verification) and gateway
MESSAGE_CREATE events forwarded via webhook. Replies via REST.

Endpoints:
  POST /channels/discord/webhook  — Discord interactions endpoint
  GET  /channels/discord/status   — Channel health check

Environment variables:
  DISCORD_BOT_TOKEN    — Bot token from Developer Portal
  DISCORD_PUBLIC_KEY   — Application public key (Ed25519 verification)
  DISCORD_DEFAULT_PACK — Default pack for Discord sessions
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.discord")

DISCORD_API = "https://discord.com/api/v10"

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


def _verify_discord_signature(public_key: str, signature: str, timestamp: str, body: bytes) -> bool:
    try:
        from nacl.signing import VerifyKey
        vk = VerifyKey(bytes.fromhex(public_key))
        vk.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except Exception:
        return False


async def _send_discord_message(channel_id: str, content: str) -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if not token:
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": content[:2000]},
            timeout=15.0,
        )


DISCORD_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Discord:\n"
    "- Maximum 2000 characters per message.\n"
    "- Supports basic Markdown: **bold**, *italic*, `code`, ```code blocks```.\n"
    "- Use line breaks for structure.\n"
)


def register_discord_channel(app: FastAPI) -> None:

    @app.post("/channels/discord/webhook")
    async def discord_webhook(request: Request) -> Response:
        body = await request.body()

        # Ed25519 signature verification
        public_key = os.getenv("DISCORD_PUBLIC_KEY", "")
        if public_key:
            sig = request.headers.get("X-Signature-Ed25519", "")
            ts = request.headers.get("X-Signature-Timestamp", "")
            if not _verify_discord_signature(public_key, sig, ts, body):
                return Response(content="Unauthorized", status_code=401)

        data = await request.json()

        # PING — required for Discord webhook verification
        if data.get("type") == 1:
            return Response(content='{"type":1}', media_type="application/json")

        # MESSAGE_CREATE from gateway forwarding
        if data.get("t") == "MESSAGE_CREATE":
            d = data.get("d", {})
            author = d.get("author", {})
            if author.get("bot"):
                return Response(content="ok")

            channel_id = d.get("channel_id", "")
            sender_id = author.get("id", "unknown")
            content = d.get("content", "").strip()

            if not content:
                return Response(content="ok")

            logger.info("Discord inbound: user=%s length=%d", sender_id[-4:], len(content))

            from session_runner import CHANNEL_CONSTRAINTS
            if "discord" not in CHANNEL_CONSTRAINTS:
                CHANNEL_CONSTRAINTS["discord"] = DISCORD_CONSTRAINT

            runner = _get_runner()
            default_pack = os.getenv("DISCORD_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

            try:
                reply = await runner.handle_message(
                    channel="discord",
                    sender_id=sender_id,
                    text=content,
                    default_pack=default_pack,
                )
            except Exception:
                logger.exception("Session runner error for Discord")
                reply = "Something went wrong. Please try again."

            if len(reply) > 2000:
                reply = reply[:1997] + "..."

            await _send_discord_message(channel_id, reply)

        return Response(content="ok")

    @app.get("/channels/discord/status")
    async def discord_status():
        configured = bool(os.getenv("DISCORD_BOT_TOKEN"))
        default_pack = os.getenv("DISCORD_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'discord' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "discord",
            "status": "configured" if configured else "unconfigured",
            "default_pack": default_pack,
            "active_sessions": active,
        }

    logger.info("Discord channel registered: POST /channels/discord/webhook")
