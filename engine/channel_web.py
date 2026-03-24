"""
13TMOS Web Channel — WebSocket Embed

Powers embeddable web chat via WebSocket. Any website can embed a
pack session with a single script tag or direct WebSocket connection.

Protocol:
  1. Client opens ws://.../channels/web/{session_token}
  2. Client sends handshake JSON: {"pack_id": "...", "name": "..."}
  3. Server sends opening message
  4. Client sends {"content": "..."}, server replies {"type": "message", ...}
  5. Server sends {"type": "typing"} before generating response

Endpoints:
  WS  /channels/web/{session_token}  — WebSocket chat
  GET /channels/web/status           — Channel health check

Environment variables:
  WEB_DEFAULT_PACK — default pack for web sessions
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger("13tmos.channel.web")

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


WEB_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Web Chat:\n"
    "- Supports basic Markdown for formatting.\n"
    "- Keep responses under 3000 characters.\n"
    "- The user sees responses in a chat widget — be conversational.\n"
)


def register_web_channel(app: FastAPI) -> None:

    @app.websocket("/channels/web/{session_token}")
    async def web_socket(websocket: WebSocket, session_token: str):
        await websocket.accept()

        # Handshake: first message declares pack and identity
        try:
            handshake_raw = await websocket.receive_text()
            handshake = json.loads(handshake_raw)
        except Exception:
            await websocket.close(code=1003)
            return

        default_pack = os.getenv("WEB_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        pack_id = handshake.get("pack_id", default_pack)
        sender_id = handshake.get("user_id", session_token)
        name = handshake.get("name", "")

        runner = _get_runner()

        # Verify pack exists
        if not runner.registry.find_pack_dir(pack_id):
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Pack '{pack_id}' not found.",
            }))
            await websocket.close()
            return

        logger.info("WebSocket connected: token=%s pack=%s", session_token[:8], pack_id)

        # Inject web constraint
        from session_runner import CHANNEL_CONSTRAINTS
        if "web" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["web"] = WEB_CONSTRAINT

        # If a name was provided, seed the session
        if name:
            existing = runner.get_session_info("web", sender_id)
            if not existing:
                runner.seed_session(
                    channel="web",
                    sender_id=sender_id,
                    pack_id=pack_id,
                    name=name,
                )

        # Generate and send opening message
        try:
            opening = await runner.get_opening_message(
                pack_id=pack_id,
                name=name,
            )
            await websocket.send_text(json.dumps({
                "type": "message",
                "role": "assistant",
                "content": opening,
            }))
        except Exception:
            logger.exception("Failed to generate opening message")

        # Message loop
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    text = msg.get("content", "").strip()
                except (json.JSONDecodeError, AttributeError):
                    text = raw.strip()

                if not text:
                    continue

                logger.info("WebSocket inbound: token=%s length=%d", session_token[:8], len(text))

                # Typing indicator
                await websocket.send_text(json.dumps({"type": "typing"}))

                try:
                    reply = await runner.handle_message(
                        channel="web",
                        sender_id=sender_id,
                        text=text,
                        default_pack=pack_id,
                    )
                except Exception:
                    logger.exception("Session runner error for WebSocket")
                    reply = "Something went wrong. Please try again."

                await websocket.send_text(json.dumps({
                    "type": "message",
                    "role": "assistant",
                    "content": reply,
                }))

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: token=%s", session_token[:8])

    @app.get("/channels/web/status")
    async def web_status():
        default_pack = os.getenv("WEB_DEFAULT_PACK", os.getenv("TMOS13_PACK", "guest"))
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'web' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "web",
            "status": "active",
            "default_pack": default_pack,
            "active_sessions": active,
            "websocket_url": "/channels/web/{session_token}",
        }

    logger.info("Web channel registered: WS /channels/web/{token}")
