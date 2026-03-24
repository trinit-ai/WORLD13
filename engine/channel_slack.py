"""
13TMOS Slack Channel — Events API Webhook

Receives Slack events (DMs and channel messages), replies via chat.postMessage.

Endpoints:
  POST /channels/slack/webhook  — Slack Events API
  GET  /channels/slack/status   — Channel health check

Environment variables:
  SLACK_BOT_TOKEN      — xoxb-* bot token
  SLACK_SIGNING_SECRET — from Slack App settings
  SLACK_DEFAULT_PACK   — default pack for Slack sessions
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time as time_mod

import httpx
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.slack")

SLACK_API = "https://slack.com/api"

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


def _verify_slack_signature(signing_secret: str, body: bytes, headers: dict) -> bool:
    try:
        ts = headers.get("x-slack-request-timestamp", "")
        if abs(time_mod.time() - int(ts)) > 300:
            return False
        sig_base = f"v0:{ts}:{body.decode()}"
        expected = "v0=" + hmac.new(
            signing_secret.encode(), sig_base.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, headers.get("x-slack-signature", ""))
    except Exception:
        return False


async def _send_slack_message(channel: str, text: str) -> None:
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SLACK_API}/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": text},
            timeout=15.0,
        )


SLACK_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Slack:\n"
    "- Supports Slack mrkdwn: *bold*, _italic_, `code`, ```code blocks```, ~strikethrough~.\n"
    "- Keep responses under 3000 characters.\n"
    "- Use line breaks and bullet points for structure.\n"
)


def register_slack_channel(app: FastAPI) -> None:

    @app.post("/channels/slack/webhook")
    async def slack_webhook(request: Request) -> Response:
        body = await request.body()

        signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
        if signing_secret:
            if not _verify_slack_signature(signing_secret, body, dict(request.headers)):
                return Response(content="Unauthorized", status_code=401)

        data = await request.json()

        # URL verification challenge
        if data.get("type") == "url_verification":
            return Response(
                content=f'{{"challenge":"{data["challenge"]}"}}',
                media_type="application/json",
            )

        event = data.get("event", {})

        # Only handle user messages, not bot messages
        if event.get("type") != "message" or event.get("bot_id") or event.get("subtype"):
            return Response(content="ok")

        sender_id = event.get("user", "unknown")
        slack_channel = event.get("channel", "")
        text = event.get("text", "").strip()

        if not text:
            return Response(content="ok")

        logger.info("Slack inbound: user=%s channel=%s length=%d",
                     sender_id[-4:], slack_channel[-4:], len(text))

        from session_runner import CHANNEL_CONSTRAINTS
        if "slack" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["slack"] = SLACK_CONSTRAINT

        runner = _get_runner()
        default_pack = os.getenv("SLACK_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))

        try:
            reply = await runner.handle_message(
                channel="slack",
                sender_id=sender_id,
                text=text,
                default_pack=default_pack,
            )
        except Exception:
            logger.exception("Session runner error for Slack")
            reply = "Something went wrong. Please try again."

        await _send_slack_message(slack_channel, reply)
        return Response(content="ok")

    @app.get("/channels/slack/status")
    async def slack_status():
        configured = bool(os.getenv("SLACK_BOT_TOKEN"))
        default_pack = os.getenv("SLACK_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'slack' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "slack",
            "status": "configured" if configured else "unconfigured",
            "default_pack": default_pack,
            "active_sessions": active,
        }

    logger.info("Slack channel registered: POST /channels/slack/webhook")
