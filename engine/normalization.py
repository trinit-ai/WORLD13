"""
TMOS13 Normalization Service

Always-on message normalization layer. Intercepts every human message
before the main LLM pipeline and rewrites it into precise machine
diction using a lightweight model (haiku).

Purpose:
  - Resolve pronouns using session context ("it" → "the pricing tier")
  - Expand shorthand ("ur" → "your", "asap" → "as soon as possible")
  - De-noise typos and fragments
  - Preserve raw intent — never add information, never interpret

The normalized message replaces the raw input for the main Claude call.
Original message is preserved in metadata for auditing.

Singleton: init_normalization_service(provider) → get_normalization_service()
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger("tmos13.normalization")


# ─── Config ──────────────────────────────────────────────

# Messages shorter than this bypass normalization entirely
MIN_MESSAGE_LENGTH = 8

# Max tokens for the normalization response
NORMALIZATION_MAX_TOKENS = 512

# System prompt for the normalization model
NORMALIZATION_SYSTEM = """You are a message normalizer. Your ONLY job is to rewrite the user's message into clear, precise English.

Rules:
- Resolve pronouns using the provided session context
- Expand shorthand and abbreviations (ur→your, asap→as soon as possible, pls→please, etc.)
- Fix obvious typos and fragments
- NEVER add information that isn't in the original message
- NEVER interpret, answer, or respond to the message — only rewrite it
- NEVER add greetings, politeness, or filler
- If the message is already clear, return it unchanged
- Return ONLY the rewritten message, nothing else — no quotes, no explanation"""


# ─── Data Types ──────────────────────────────────────────

@dataclass
class NormalizationResult:
    """Result of normalizing a single message."""
    original: str
    normalized: str
    changed: bool
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class NormalizationStats:
    """Aggregate statistics for the normalization service."""
    total_calls: int = 0
    total_changed: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    avg_latency_ms: float = 0.0
    _latency_sum: float = field(default=0.0, repr=False)


# ─── Service ─────────────────────────────────────────────

class NormalizationService:
    """
    Normalizes incoming user messages using a lightweight LLM.

    Requires a dedicated LLM provider (typically haiku) that is
    separate from the main session provider.
    """

    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._stats = NormalizationStats()
        self._enabled = True
        logger.info(
            f"NormalizationService initialized: model={provider.model}"
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def stats(self) -> NormalizationStats:
        return self._stats

    def _extract_context(self, session_state) -> str:
        """
        Extract relevant context from session state for pronoun resolution.
        Returns a short context block the normalizer can reference.
        """
        parts = []

        # Pack / cartridge context
        pack_id = getattr(session_state, "pack_id", None)
        if pack_id:
            parts.append(f"Pack: {pack_id}")

        cartridge = getattr(session_state, "current_game", None)
        if cartridge:
            parts.append(f"Active cartridge: {cartridge}")

        depth = getattr(session_state, "depth", 0)
        if depth > 0:
            parts.append(f"Depth: {depth}")

        # Recent conversation for pronoun resolution
        history = getattr(session_state, "history", [])
        if history:
            # Last 3 turns only — enough for pronoun resolution
            recent = history[-3:]
            for msg in recent:
                role = msg.get("role", "?")
                content = msg.get("content", "")
                # Truncate long messages
                if len(content) > 200:
                    content = content[:200] + "..."
                parts.append(f"[{role}]: {content}")

        # Form data for entity resolution
        forms = getattr(session_state, "forms", {})
        if forms:
            form_keys = list(forms.keys())
            if form_keys:
                parts.append(f"Forms submitted: {', '.join(form_keys)}")
                # Include latest form fields for entity resolution
                latest_form = forms[form_keys[-1]]
                if isinstance(latest_form, dict):
                    field_summary = ", ".join(
                        f"{k}={v}" for k, v in latest_form.items()
                        if v and isinstance(v, str) and len(str(v)) < 50
                    )
                    if field_summary:
                        parts.append(f"Latest form data: {field_summary}")

        return "\n".join(parts) if parts else "No session context available."

    def _build_messages(self, raw_message: str, context: str) -> list[dict]:
        """Build the message list for the normalization LLM call."""
        user_content = f"Session context:\n{context}\n\nMessage to normalize:\n{raw_message}"
        return [{"role": "user", "content": user_content}]

    async def normalize(
        self,
        raw_message: str,
        session_state=None,
    ) -> NormalizationResult:
        """
        Normalize a single user message.

        Args:
            raw_message: The raw user input.
            session_state: Optional SessionState for context extraction.

        Returns:
            NormalizationResult with original, normalized text, and metadata.
        """
        # Skip if disabled
        if not self._enabled:
            self._stats.total_skipped += 1
            return NormalizationResult(
                original=raw_message,
                normalized=raw_message,
                changed=False,
                skipped=True,
                skip_reason="disabled",
            )

        # Skip very short messages — they're usually commands or greetings
        if len(raw_message.strip()) < MIN_MESSAGE_LENGTH:
            self._stats.total_skipped += 1
            return NormalizationResult(
                original=raw_message,
                normalized=raw_message,
                changed=False,
                skipped=True,
                skip_reason="too_short",
            )

        # Extract context for pronoun resolution
        context = self._extract_context(session_state) if session_state else "No session context available."

        # Build normalization request
        messages = self._build_messages(raw_message, context)

        start = time.perf_counter()
        try:
            response: LLMResponse = await self._provider.generate(
                system=NORMALIZATION_SYSTEM,
                messages=messages,
                max_tokens=NORMALIZATION_MAX_TOKENS,
            )
        except Exception as e:
            # On failure, pass through the original message — never block the pipeline
            logger.warning(f"Normalization LLM call failed: {e}")
            self._stats.total_errors += 1
            return NormalizationResult(
                original=raw_message,
                normalized=raw_message,
                changed=False,
                skipped=True,
                skip_reason=f"error: {e}",
            )

        latency_ms = (time.perf_counter() - start) * 1000
        normalized = response.text.strip()

        # Detect if normalization actually changed the message
        changed = normalized.lower() != raw_message.strip().lower()

        # Update stats
        self._stats.total_calls += 1
        if changed:
            self._stats.total_changed += 1
        self._stats.total_input_tokens += response.input_tokens
        self._stats.total_output_tokens += response.output_tokens
        self._stats._latency_sum += latency_ms
        self._stats.avg_latency_ms = (
            self._stats._latency_sum / self._stats.total_calls
        )

        if changed:
            logger.debug(
                f"Normalized: '{raw_message[:60]}...' → '{normalized[:60]}...'"
            )

        return NormalizationResult(
            original=raw_message,
            normalized=normalized,
            changed=changed,
            latency_ms=round(latency_ms, 2),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            model=response.model,
        )

    async def normalize_for_manifest(
        self,
        raw_message: str,
        session_state=None,
    ) -> tuple[str, Optional[dict]]:
        """
        Convenience wrapper: returns (message_to_use, normalization_metadata).

        The first element is the normalized message (or raw if unchanged/skipped).
        The second element is metadata dict for including in ChatResponse, or None.
        """
        result = await self.normalize(raw_message, session_state)

        metadata = None
        if not result.skipped:
            metadata = {
                "original": result.original,
                "normalized": result.normalized,
                "changed": result.changed,
                "latency_ms": result.latency_ms,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

        return result.normalized, metadata


# ─── Singleton ───────────────────────────────────────────

_normalization_service: Optional[NormalizationService] = None


def init_normalization_service(provider: LLMProvider) -> NormalizationService:
    """Initialize the NormalizationService singleton. Call once in app lifespan."""
    global _normalization_service
    _normalization_service = NormalizationService(provider)
    return _normalization_service


def get_normalization_service() -> Optional[NormalizationService]:
    """
    Get the NormalizationService singleton.

    Returns None instead of raising — normalization is optional
    and should never block the pipeline if not initialized.
    """
    return _normalization_service
