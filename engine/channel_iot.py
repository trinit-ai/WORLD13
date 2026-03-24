"""
13TMOS IoT Channel — Governed Sessions for Connected Devices

Any device that can open a WebSocket can run a governed session.
The device sends a JSON handshake identifying itself; the engine
resolves the pack from device_type and begins the session.

Handshake (device → server):
  {"type": "handshake", "device_id": "fridge-01", "device_type": "refrigerator",
   "location": "kitchen", "sensor_data": {}}

Message (device → server):
  {"type": "message", "text": "what can I make for dinner",
   "sensor_data": {"items_detected": ["eggs", "milk"]}}

Response (server → device):
  {"type": "response", "text": "...", "pack_id": "...", "complete": false}

Endpoints:
  WS  /channels/iot/{device_id}  — WebSocket session
  GET /channels/iot/status       — Channel health check

Environment variables:
  IOT_DEFAULT_PACK — fallback pack (default: desk)
"""
from __future__ import annotations

import json
import logging
import os
import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger("13tmos.channel.iot")

_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


# Device type → default pack mapping
DEVICE_PACK_MAP = {
    "refrigerator":    "nutrition_intake",
    "smart_fridge":    "nutrition_intake",
    "scale":           "health_checkin",
    "doorbell":        "visitor_intake",
    "security_panel":  "incident_report",
    "medical_device":  "vitals_intake",
    "thermostat":      "comfort_intake",
    "speaker":         "desk",
    "display":         "desk",
    "generic":         "desk",
}

IOT_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — IoT device:\n"
    "- Maximum 3 sentences per response.\n"
    "- No markdown, no bullet points, no headers, no emoji.\n"
    "- Plain conversational language only.\n"
    "- Voice-ready: responses should read naturally when spoken aloud.\n"
    "- If a list is needed, say it as a sentence: \"You have eggs, milk, and pasta.\"\n"
    "- End with a clear single question or action prompt.\n"
)

IOT_MAX_LENGTH = 500

# Handshake greetings by device type
_HANDSHAKE_GREETINGS = {
    "refrigerator":    "Hello. I'm checking in from the kitchen. What would you like help with today?",
    "smart_fridge":    "Hello. I'm checking in from the kitchen. What would you like help with today?",
    "scale":           "Good morning. Ready when you are.",
    "doorbell":        "Someone is at the door.",
    "security_panel":  "Security panel active. What happened?",
    "medical_device":  "Device connected. Ready to begin.",
    "thermostat":      "Thermostat connected. How can I help?",
}


def _format_sensor_context(sensor_data: dict) -> str:
    """Format sensor data as a brief context string for injection."""
    if not sensor_data:
        return ""
    parts = []
    for key, value in list(sensor_data.items())[:3]:
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _truncate_for_device(text: str) -> str:
    """Truncate to IOT_MAX_LENGTH at sentence boundary."""
    if len(text) <= IOT_MAX_LENGTH:
        return text
    truncated = text[:IOT_MAX_LENGTH]
    last_period = truncated.rfind('.')
    if last_period > IOT_MAX_LENGTH * 0.7:
        return truncated[:last_period + 1]
    return truncated.rstrip() + "..."


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting for voice-ready output."""
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)     # bold/italic
    text = re.sub(r'#{1,6}\s+', '', text)              # headers
    text = re.sub(r'`([^`]+)`', r'\1', text)           # code
    text = re.sub(r'\n[-*\u2022]\s+', '. ', text)      # bullets → sentences
    text = re.sub(r'\n+', ' ', text)                    # newlines → spaces
    return text.strip()


def register_iot_channel(app: FastAPI) -> None:

    @app.websocket("/channels/iot/{device_id}")
    async def iot_ws(websocket: WebSocket, device_id: str):
        await websocket.accept()

        runner = _get_runner()
        default_pack = os.getenv("IOT_DEFAULT_PACK", "desk")

        # Inject IoT constraint
        from session_runner import CHANNEL_CONSTRAINTS
        if "iot" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["iot"] = IOT_CONSTRAINT

        logger.info("IoT device connected: %s", device_id)

        pack_id = default_pack
        device_type = "generic"

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"type": "message", "text": raw}

                msg_type = payload.get("type", "message")
                device_type = payload.get("device_type", device_type)
                location = payload.get("location", "")
                sensor_data = payload.get("sensor_data", {})

                # Resolve pack from device type or override
                pack_id = (
                    payload.get("pack_override")
                    or DEVICE_PACK_MAP.get(device_type, default_pack)
                )

                # Build message text
                if msg_type == "handshake":
                    text = _HANDSHAKE_GREETINGS.get(
                        device_type,
                        "Device connected. How can I help?",
                    )
                    # Seed session with device identity
                    existing = runner.get_session_info("iot", device_id)
                    if not existing:
                        name = f"{device_type} @ {location}" if location else device_type
                        runner.seed_session(
                            channel="iot",
                            sender_id=device_id,
                            pack_id=pack_id,
                            name=name,
                            context=f"Device type: {device_type}. Location: {location}.",
                        )
                else:
                    text = payload.get("text", "").strip()
                    if not text:
                        continue

                # Enrich with sensor context
                if sensor_data and msg_type != "handshake":
                    context = _format_sensor_context(sensor_data)
                    if context:
                        text = f"{text} [sensor context: {context}]"

                # Send typing indicator
                await websocket.send_text(json.dumps({"type": "typing"}))

                try:
                    reply = await runner.handle_message(
                        channel="iot",
                        sender_id=device_id,
                        text=text,
                        default_pack=pack_id,
                    )
                except Exception:
                    logger.exception("Session runner error for IoT device %s", device_id)
                    reply = "Something went wrong. Please try again."

                # Format for device: strip markdown, truncate
                reply = _strip_markdown(reply)
                reply = _truncate_for_device(reply)

                await websocket.send_text(json.dumps({
                    "type": "response",
                    "text": reply,
                    "pack_id": pack_id,
                    "device_type": device_type,
                    "complete": False,
                }))

        except WebSocketDisconnect:
            logger.info("IoT device disconnected: %s", device_id)
        except Exception as e:
            logger.error("IoT WebSocket error: %s — %s", device_id, e)
            try:
                await websocket.close()
            except Exception:
                pass

    @app.get("/channels/iot/status")
    async def iot_status():
        default_pack = os.getenv("IOT_DEFAULT_PACK", "desk")
        active = 0
        try:
            row = _get_runner().conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions "
                "WHERE channel = 'iot' AND status IN ('active', 'seeded')"
            ).fetchone()
            active = row["cnt"] if row else 0
        except Exception:
            pass
        return {
            "channel": "iot",
            "status": "live",
            "default_pack": default_pack,
            "active_sessions": active,
            "websocket_url": "/channels/iot/{device_id}",
            "device_pack_map": DEVICE_PACK_MAP,
        }

    logger.info("IoT channel registered: WS /channels/iot/{device_id}")
