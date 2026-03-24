"""
Voice Channel Adapter — Audio I/O via existing AudioService.

Wraps the engine's AudioService (STT/TTS providers) into the unified
channel adapter interface. Voice messages arrive as audio bytes,
get transcribed to text, processed by the engine, then synthesized
back to audio for delivery.
"""

import base64
import logging
from typing import Optional

from channels.base import (
    ChannelAdapter,
    ChannelCapabilities,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger("tmos13.channels.voice")


class VoiceAdapter(ChannelAdapter):
    """Voice channel adapter: STT inbound + TTS outbound."""

    def __init__(self, audio_service=None):
        self._audio = audio_service

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.VOICE

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_html=False,
            supports_markdown=False,
            supports_media=True,  # audio
            supports_buttons=False,
            supports_forms=False,
            max_message_length=0,
            supports_threading=False,
            supports_typing_indicator=False,
        )

    def parse_inbound(self, raw: dict) -> Optional[InboundMessage]:
        """
        Parse a voice message payload.

        Expected raw dict:
          audio_base64: base64-encoded audio bytes
          format: audio format (wav, mp3, webm, etc.)
          text: pre-transcribed text (if client did STT)
          session_id, user_id, pack_id: standard fields
        """
        # Accept pre-transcribed text directly
        text = raw.get("text", "")

        if not text:
            # Transcription will happen in process_voice() — store raw audio in metadata
            audio_b64 = raw.get("audio_base64", "")
            if not audio_b64:
                return None
            text = "[voice:pending_transcription]"

        return InboundMessage(
            channel=ChannelType.VOICE,
            text=text,
            sender_id=raw.get("user_id", "anonymous"),
            session_id=raw.get("session_id", ""),
            pack_id=raw.get("pack_id", ""),
            raw_payload=raw,
            metadata={
                "audio_format": raw.get("format", "wav"),
                "has_audio": bool(raw.get("audio_base64")),
                "voice": raw.get("voice", ""),
                "language": raw.get("language", ""),
            },
        )

    def format_response(self, engine_response: str, inbound: InboundMessage) -> OutboundMessage:
        """Format engine response for voice (plain text + metadata for TTS)."""
        return OutboundMessage(
            channel=ChannelType.VOICE,
            text=engine_response,
            session_id=inbound.session_id,
            recipient_id=inbound.sender_id,
            metadata={
                "voice": inbound.metadata.get("voice", ""),
                "audio_format": inbound.metadata.get("audio_format", "mp3"),
                "needs_synthesis": True,
            },
        )

    async def deliver(self, outbound: OutboundMessage) -> dict:
        """
        Synthesize text to speech and return audio.
        Unlike other channels, voice delivery returns audio bytes
        rather than pushing to an external API.
        """
        if not self._audio:
            return {
                "delivered": False,
                "reason": "audio service not configured",
            }

        if not outbound.metadata.get("needs_synthesis"):
            return {"delivered": True, "audio_base64": ""}

        try:
            voice = outbound.metadata.get("voice", "default")
            fmt = outbound.metadata.get("audio_format", "mp3")
            result = await self._audio.synthesize(
                text=outbound.text,
                voice=voice,
                format=fmt,
            )
            audio_b64 = base64.b64encode(result.audio).decode("ascii") if result.audio else ""
            return {
                "delivered": True,
                "audio_base64": audio_b64,
                "format": fmt,
                "duration_seconds": result.duration_seconds,
            }
        except Exception as e:
            logger.error(f"Voice synthesis failed: {e}")
            return {"delivered": False, "reason": str(e)}

    async def transcribe_audio(self, audio_bytes: bytes, fmt: str = "wav", language: str = "") -> str:
        """
        Transcribe audio bytes to text using the AudioService.
        Called by the webhook handler before engine processing.
        """
        if not self._audio:
            return "[voice transcription unavailable]"

        try:
            result = await self._audio.transcribe(
                audio=audio_bytes,
                format=fmt,
                language=language or None,
            )
            return result.text
        except Exception as e:
            logger.error(f"Voice transcription failed: {e}")
            return "[transcription error]"
