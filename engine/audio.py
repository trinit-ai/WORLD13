"""
TMOS13 Audio Processing Service

Provider-agnostic speech-to-text (STT) and text-to-speech (TTS) service.
Supports OpenAI Whisper, Google Cloud Speech, Azure Cognitive Services for STT,
and OpenAI TTS, ElevenLabs, Azure TTS for synthesis.

Usage:
    audio = AudioService(stt_provider="openai", tts_provider="openai")
    transcript = await audio.transcribe(audio_bytes, format="wav")
    speech = await audio.synthesize("Hello world", voice="alloy")
"""
import asyncio
import base64
import io
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional

logger = logging.getLogger("tmos13.audio")


# ─── Data Models ─────────────────────────────────────────

class AudioFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    WEBM = "webm"
    FLAC = "flac"
    PCM = "pcm"


@dataclass
class TranscriptionResult:
    """Result from a speech-to-text transcription."""
    text: str
    language: str = "en"
    confidence: float = 1.0
    duration_seconds: float = 0.0
    segments: list = field(default_factory=list)  # word-level timestamps

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "confidence": self.confidence,
            "duration_seconds": self.duration_seconds,
            "segments": self.segments,
        }


@dataclass
class SynthesisResult:
    """Result from a text-to-speech synthesis."""
    audio: bytes
    format: str = "mp3"
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    voice_id: str = ""

    def to_base64(self) -> str:
        return base64.b64encode(self.audio).decode("ascii")


@dataclass
class VoiceInfo:
    """Metadata for an available TTS voice."""
    voice_id: str
    name: str
    language: str = "en"
    gender: str = "neutral"
    preview_url: str = ""
    provider: str = ""


# ─── STT Provider Interface ──────────────────────────────

class STTProvider(ABC):
    """Abstract base for speech-to-text providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        ...

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        format: str = "wav",
        language: Optional[str] = None,
    ) -> AsyncIterator[TranscriptionResult]:
        ...


class OpenAISTT(STTProvider):
    """Speech-to-text via OpenAI Whisper API."""

    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.api_key = api_key
        self.model = model

    async def transcribe(
        self,
        audio: bytes,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed; falling back to stub transcription")
            return TranscriptionResult(text="[transcription unavailable]")

        file_name = f"audio.{format}"
        mime = _format_to_mime(format)

        data = {"model": self.model}
        if language:
            data["language"] = language
        data["response_format"] = "verbose_json"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files={"file": (file_name, io.BytesIO(audio), mime)},
            )
            response.raise_for_status()
            result = response.json()

        segments = []
        if "segments" in result:
            segments = [
                {"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "")}
                for s in result["segments"]
            ]

        return TranscriptionResult(
            text=result.get("text", ""),
            language=result.get("language", "en"),
            confidence=1.0,
            duration_seconds=result.get("duration", 0.0),
            segments=segments,
        )

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        format: str = "wav",
        language: Optional[str] = None,
    ) -> AsyncIterator[TranscriptionResult]:
        # Whisper doesn't support true streaming — buffer and transcribe
        chunks = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        full_audio = b"".join(chunks)
        result = await self.transcribe(full_audio, format, language)
        yield result


class GoogleSTT(STTProvider):
    """Speech-to-text via Google Cloud Speech-to-Text API."""

    def __init__(self, credentials_json: Optional[str] = None):
        self.credentials_json = credentials_json

    async def transcribe(
        self,
        audio: bytes,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        try:
            from google.cloud import speech_v1 as speech
        except ImportError:
            logger.warning("google-cloud-speech not installed")
            return TranscriptionResult(text="[google stt unavailable]")

        client = speech.SpeechClient()
        audio_obj = speech.RecognitionAudio(content=audio)
        encoding_map = {
            "wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "flac": speech.RecognitionConfig.AudioEncoding.FLAC,
            "ogg": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "webm": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            "mp3": speech.RecognitionConfig.AudioEncoding.MP3,
        }
        config = speech.RecognitionConfig(
            encoding=encoding_map.get(format, speech.RecognitionConfig.AudioEncoding.LINEAR16),
            language_code=language or "en-US",
            enable_word_time_offsets=True,
        )

        response = await asyncio.to_thread(client.recognize, config=config, audio=audio_obj)
        if not response.results:
            return TranscriptionResult(text="")

        best = response.results[0]
        alt = best.alternatives[0] if best.alternatives else None
        return TranscriptionResult(
            text=alt.transcript if alt else "",
            language=language or "en",
            confidence=alt.confidence if alt else 0.0,
        )

    async def transcribe_stream(self, audio_stream, format="wav", language=None):
        chunks = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        result = await self.transcribe(b"".join(chunks), format, language)
        yield result


class AzureSTT(STTProvider):
    """Speech-to-text via Azure Cognitive Services."""

    def __init__(self, subscription_key: str, region: str = "eastus"):
        self.subscription_key = subscription_key
        self.region = region

    async def transcribe(
        self,
        audio: bytes,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        try:
            import httpx
        except ImportError:
            return TranscriptionResult(text="[azure stt unavailable]")

        url = f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        params = {"language": language or "en-US"}
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": f"audio/{format}",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, params=params, headers=headers, content=audio)
            response.raise_for_status()
            result = response.json()

        return TranscriptionResult(
            text=result.get("DisplayText", ""),
            language=language or "en",
            confidence=result.get("NBest", [{}])[0].get("Confidence", 0.0) if result.get("NBest") else 1.0,
            duration_seconds=result.get("Duration", 0) / 10_000_000,  # ticks to seconds
        )

    async def transcribe_stream(self, audio_stream, format="wav", language=None):
        chunks = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        result = await self.transcribe(b"".join(chunks), format, language)
        yield result


# ─── TTS Provider Interface ──────────────────────────────

class TTSProvider(ABC):
    """Abstract base for text-to-speech providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        format: str = "mp3",
        speed: float = 1.0,
    ) -> SynthesisResult:
        ...

    @abstractmethod
    async def list_voices(self) -> list[VoiceInfo]:
        ...


class OpenAITTS(TTSProvider):
    """Text-to-speech via OpenAI TTS API."""

    VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]

    def __init__(self, api_key: str, model: str = "tts-1"):
        self.api_key = api_key
        self.model = model

    async def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        format: str = "mp3",
        speed: float = 1.0,
    ) -> SynthesisResult:
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed; TTS unavailable")
            return SynthesisResult(audio=b"", format=format)

        payload = {
            "model": self.model,
            "input": text,
            "voice": voice if voice in self.VOICES else "alloy",
            "response_format": format if format in ("mp3", "opus", "aac", "flac", "wav", "pcm") else "mp3",
            "speed": max(0.25, min(4.0, speed)),
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            audio_bytes = response.content

        return SynthesisResult(
            audio=audio_bytes,
            format=format,
            voice_id=voice,
        )

    async def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(voice_id=v, name=v.capitalize(), provider="openai")
            for v in self.VOICES
        ]


class ElevenLabsTTS(TTSProvider):
    """Text-to-speech via ElevenLabs API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        format: str = "mp3",
        speed: float = 1.0,
    ) -> SynthesisResult:
        try:
            import httpx
        except ImportError:
            return SynthesisResult(audio=b"", format=format)

        # ElevenLabs uses voice_id in URL
        voice_id = voice if voice != "default" else "21m00Tcm4TlvDq8ikWAM"  # Rachel default
        output_format = "mp3_44100_128" if format == "mp3" else "pcm_24000"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                params={"output_format": output_format},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "speed": speed,
                    },
                },
            )
            response.raise_for_status()

        return SynthesisResult(
            audio=response.content,
            format=format,
            voice_id=voice_id,
        )

    async def list_voices(self) -> list[VoiceInfo]:
        try:
            import httpx
        except ImportError:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/voices",
                headers={"xi-api-key": self.api_key},
            )
            response.raise_for_status()
            data = response.json()

        return [
            VoiceInfo(
                voice_id=v["voice_id"],
                name=v.get("name", "Unknown"),
                language=v.get("labels", {}).get("language", "en"),
                gender=v.get("labels", {}).get("gender", "neutral"),
                preview_url=v.get("preview_url", ""),
                provider="elevenlabs",
            )
            for v in data.get("voices", [])
        ]


class AzureTTS(TTSProvider):
    """Text-to-speech via Azure Cognitive Services."""

    def __init__(self, subscription_key: str, region: str = "eastus"):
        self.subscription_key = subscription_key
        self.region = region

    async def synthesize(
        self,
        text: str,
        voice: str = "en-US-JennyNeural",
        format: str = "mp3",
        speed: float = 1.0,
    ) -> SynthesisResult:
        try:
            import httpx
        except ImportError:
            return SynthesisResult(audio=b"", format=format)

        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        output_format_map = {
            "mp3": "audio-24khz-96kbitrate-mono-mp3",
            "wav": "riff-24khz-16bit-mono-pcm",
            "ogg": "ogg-24khz-16bit-mono-opus",
        }
        rate_pct = f"{int((speed - 1.0) * 100):+d}%"

        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'<voice name="{voice}">'
            f'<prosody rate="{rate_pct}">{text}</prosody>'
            f'</voice></speak>'
        )

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self.subscription_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": output_format_map.get(format, "audio-24khz-96kbitrate-mono-mp3"),
                },
                content=ssml,
            )
            response.raise_for_status()

        return SynthesisResult(audio=response.content, format=format, voice_id=voice)

    async def list_voices(self) -> list[VoiceInfo]:
        try:
            import httpx
        except ImportError:
            return []

        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                headers={"Ocp-Apim-Subscription-Key": self.subscription_key},
            )
            response.raise_for_status()
            voices = response.json()

        return [
            VoiceInfo(
                voice_id=v.get("ShortName", ""),
                name=v.get("DisplayName", ""),
                language=v.get("Locale", "en-US"),
                gender=v.get("Gender", "neutral").lower(),
                provider="azure",
            )
            for v in voices[:50]  # limit response size
        ]


# ─── Stub Provider (for dev/testing) ────────────────────

class StubSTT(STTProvider):
    """Stub STT that returns placeholder text. Used when no provider is configured."""

    async def transcribe(self, audio, format="wav", language=None):
        return TranscriptionResult(
            text="[Speech-to-text not configured. Set TMOS13_STT_PROVIDER and API keys.]",
            language=language or "en",
            confidence=0.0,
        )

    async def transcribe_stream(self, audio_stream, format="wav", language=None):
        async for _ in audio_stream:
            pass
        yield await self.transcribe(b"", format, language)


class StubTTS(TTSProvider):
    """Stub TTS that returns empty audio. Used when no provider is configured."""

    async def synthesize(self, text, voice="default", format="mp3", speed=1.0):
        return SynthesisResult(audio=b"", format=format, voice_id="stub")

    async def list_voices(self):
        return [VoiceInfo(voice_id="stub", name="Stub Voice", provider="stub")]


# ─── Provider Factory ───────────────────────────────────

STT_PROVIDERS = {
    "openai": lambda cfg: OpenAISTT(api_key=cfg.get("openai_api_key", "")),
    "google": lambda cfg: GoogleSTT(credentials_json=cfg.get("google_credentials")),
    "azure": lambda cfg: AzureSTT(
        subscription_key=cfg.get("azure_speech_key", ""),
        region=cfg.get("azure_speech_region", "eastus"),
    ),
    "stub": lambda cfg: StubSTT(),
}

TTS_PROVIDERS = {
    "openai": lambda cfg: OpenAITTS(
        api_key=cfg.get("openai_api_key", ""),
        model=cfg.get("openai_tts_model", "tts-1"),
    ),
    "elevenlabs": lambda cfg: ElevenLabsTTS(api_key=cfg.get("elevenlabs_api_key", "")),
    "azure": lambda cfg: AzureTTS(
        subscription_key=cfg.get("azure_speech_key", ""),
        region=cfg.get("azure_speech_region", "eastus"),
    ),
    "stub": lambda cfg: StubTTS(),
}


# ─── Audio Service (main entry point) ────────────────────

class AudioService:
    """
    Unified audio service for STT and TTS.

    Delegates to configured providers. Falls back to stub providers
    when no API keys are configured.
    """

    def __init__(
        self,
        stt_provider: str = "stub",
        tts_provider: str = "stub",
        config: Optional[dict] = None,
    ):
        cfg = config or {}
        self.stt_name = stt_provider
        self.tts_name = tts_provider

        factory_stt = STT_PROVIDERS.get(stt_provider, STT_PROVIDERS["stub"])
        factory_tts = TTS_PROVIDERS.get(tts_provider, TTS_PROVIDERS["stub"])

        self.stt: STTProvider = factory_stt(cfg)
        self.tts: TTSProvider = factory_tts(cfg)
        self.enabled = stt_provider != "stub" or tts_provider != "stub"

        logger.info(f"AudioService initialized: STT={stt_provider}, TTS={tts_provider}")

    async def transcribe(
        self,
        audio: bytes,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio to text."""
        if not audio:
            return TranscriptionResult(text="")
        return await self.stt.transcribe(audio, format, language)

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        format: str = "mp3",
        speed: float = 1.0,
    ) -> SynthesisResult:
        """Synthesize text to speech audio."""
        if not text:
            return SynthesisResult(audio=b"", format=format)
        return await self.tts.synthesize(text, voice, format, speed)

    async def list_voices(self) -> list[VoiceInfo]:
        """List available TTS voices."""
        return await self.tts.list_voices()

    def get_status(self) -> dict:
        """Return audio service status for health checks."""
        return {
            "enabled": self.enabled,
            "stt_provider": self.stt_name,
            "tts_provider": self.tts_name,
        }


# ─── Helpers ────────────────────────────────────────────

def _format_to_mime(format: str) -> str:
    """Convert audio format string to MIME type."""
    mime_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "webm": "audio/webm",
        "flac": "audio/flac",
        "pcm": "audio/pcm",
    }
    return mime_map.get(format, "audio/wav")


def init_audio_service(
    stt_provider: str = "",
    tts_provider: str = "",
    openai_api_key: str = "",
    elevenlabs_api_key: str = "",
    azure_speech_key: str = "",
    azure_speech_region: str = "eastus",
    google_credentials: str = "",
    openai_tts_model: str = "tts-1",
) -> AudioService:
    """
    Factory function called from app.py lifespan to initialize audio.

    Auto-detects providers based on available API keys if not explicitly set.
    """
    config = {
        "openai_api_key": openai_api_key,
        "elevenlabs_api_key": elevenlabs_api_key,
        "azure_speech_key": azure_speech_key,
        "azure_speech_region": azure_speech_region,
        "google_credentials": google_credentials,
        "openai_tts_model": openai_tts_model,
    }

    # Auto-detect STT provider
    if not stt_provider:
        if openai_api_key:
            stt_provider = "openai"
        elif azure_speech_key:
            stt_provider = "azure"
        elif google_credentials:
            stt_provider = "google"
        else:
            stt_provider = "stub"

    # Auto-detect TTS provider
    if not tts_provider:
        if elevenlabs_api_key:
            tts_provider = "elevenlabs"
        elif openai_api_key:
            tts_provider = "openai"
        elif azure_speech_key:
            tts_provider = "azure"
        else:
            tts_provider = "stub"

    return AudioService(
        stt_provider=stt_provider,
        tts_provider=tts_provider,
        config=config,
    )
