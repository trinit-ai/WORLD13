"""
13TMOS Channel Management API

Seed sessions, list active channel sessions, close sessions.

Endpoints:
  POST   /channels/seed              — pre-seed a session for a recipient
  GET    /channels/sessions          — list channel sessions
  DELETE /channels/sessions/{id}     — close a channel session
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("13tmos.api.channels")

SUPPORTED_CHANNELS = [
    "telegram", "whatsapp", "email",
    "sms", "discord", "slack",
    "messenger", "instagram", "web",
]

# Lazy runner — shared with channel handlers
_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


class SeedRequest(BaseModel):
    channel: str          # telegram | whatsapp | email
    sender_id: str        # channel-specific ID (chat_id, phone, or email address)
    pack_id: str          # which pack to run
    name: str             # recipient's first name
    context: str = ""     # optional: how you met, a detail, anything
    opening_email: bool = False       # send the opening email automatically
    opening_subject: str = "Something strange is waiting for you"  # email subject


def register_channel_api(app: FastAPI) -> None:
    """Register channel management endpoints."""

    @app.post("/channels/seed")
    async def seed_session(req: SeedRequest):
        """Pre-seed a session for a recipient.

        Example:
            POST /channels/seed
            {
                "channel": "telegram",
                "sender_id": "123456789",
                "pack_id": "enlightened_duck",
                "name": "Sofia",
                "context": "met at the gallery on Spring St, talked about Basquiat"
            }
        """
        runner = _get_runner()

        result = runner.seed_session(
            channel=req.channel,
            sender_id=req.sender_id,
            pack_id=req.pack_id,
            name=req.name,
            context=req.context,
        )

        if "error" in result:
            raise HTTPException(404, result["error"])

        # Send opening email if requested
        if req.opening_email and req.channel == "email":
            from channel_email import send_email_reply
            opening = await runner.get_opening_message(
                pack_id=req.pack_id,
                name=req.name,
                context=req.context,
            )
            sender_email = req.sender_id  # email address
            sent = await send_email_reply(
                to=sender_email,
                from_address="The Duck <duck@tmos13.ai>",
                subject=req.opening_subject,
                body=opening,
            )
            result["opening_email_sent"] = sent
            # Persist the opening as an assistant exchange so thread continues
            if sent:
                import time
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                runner.conn.execute(
                    "INSERT INTO channel_exchanges (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (result["session_id"], "assistant", opening, now),
                )
                runner.conn.commit()

        return result

    @app.get("/channels/sessions")
    async def list_channel_sessions(
        channel: str = None,
        status: str = None,
        limit: int = 20,
    ):
        """List channel sessions across all messengers."""
        runner = _get_runner()

        query = "SELECT session_id, channel, sender_id, pack_id, status, turn_count, seed_name, created_at, last_active FROM channel_sessions WHERE 1=1"
        params = []

        if channel:
            query += " AND channel = ?"
            params.append(channel)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY last_active DESC LIMIT ?"
        params.append(limit)

        rows = runner.conn.execute(query, params).fetchall()
        return {
            "sessions": [dict(r) for r in rows],
            "count": len(rows),
        }

    @app.delete("/channels/sessions/{session_id}")
    async def close_channel_session(session_id: str):
        """Close a specific channel session."""
        runner = _get_runner()
        runner.conn.execute(
            "UPDATE channel_sessions SET status = 'closed' WHERE session_id = ?",
            (session_id,),
        )
        runner.conn.commit()
        return {"session_id": session_id, "status": "closed"}

    @app.get("/channels")
    async def channel_map():
        """All registered channels and their status endpoints."""
        return {
            "channels": SUPPORTED_CHANNELS,
            "count": len(SUPPORTED_CHANNELS),
            "status_endpoints": {
                ch: f"/channels/{ch}/status" for ch in SUPPORTED_CHANNELS
            },
        }

    logger.info("Channel API registered: /channels, /channels/seed, /channels/sessions")
