"""
TMOS13 LLM Provider Interface

Provider-agnostic LLM abstraction. The engine calls a single interface;
the implementation decides whether inference runs on Anthropic's API,
a local Ollama instance, or any other backend.

Providers:
    AnthropicProvider  — Claude API (cloud)
    OllamaProvider     — Ollama local inference (Gemma, Llama, Mistral, etc.)
    StubProvider       — Deterministic responses for testing

Usage:
    from llm_provider import init_llm_provider, get_llm_provider

    provider = init_llm_provider()  # auto-detects from env
    response = await provider.generate(system="...", messages=[...])
"""
import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Union

logger = logging.getLogger("tmos13.llm")


# ─── Response Model ──────────────────────────────────────

@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    text: str
    model: str
    provider: str
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    finish_reason: str = "end_turn"
    raw: Optional[dict] = field(default=None, repr=False)
    # Structured output (tool_use results)
    tool_results: list[dict] = field(default_factory=list)
    # Citations from document sources
    citations: list[dict] = field(default_factory=list)
    has_citations: bool = False


# ─── Abstract Provider ───────────────────────────────────

class LLMProvider(ABC):
    """Base interface for all LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'anthropic', 'ollama', 'stub')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Active model identifier."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether this provider is configured and ready."""
        return True

    @abstractmethod
    async def generate(
        self,
        system: Union[str, list[dict]],
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate a response.

        Args:
            system: System prompt — either a plain string or a list of
                    content blocks with cache_control markers.
            messages: Conversation history in OpenAI-style format
                      [{"role": "user", "content": "..."}, ...]
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with the generated text and metadata.
        """
        ...

    async def generate_with_tools(
        self,
        system: Union[str, list[dict]],
        messages: list[dict],
        tools: list[dict],
        tool_choice: Optional[dict] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate a response with tool use (structured outputs).

        Args:
            system: System prompt — string or content blocks.
            messages: Conversation history.
            tools: List of tool definitions with input_schema.
            tool_choice: Optional tool selection constraint
                         (e.g. {"type": "tool", "name": "produce_deliverable"}).
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with tool_results populated from tool_use content blocks.
        """
        # Default: fall back to regular generate (providers without tool support)
        return await self.generate(system, messages, max_tokens)

    async def health_check(self) -> dict:
        """Check provider health. Returns {"ok": bool, "detail": str}."""
        return {"ok": self.enabled, "detail": f"{self.name} provider active"}


# ─── Utility: Document blocks for citations ─────────────

def format_document_block(
    content: str,
    title: str = "",
    media_type: str = "text/plain",
    citations_enabled: bool = True,
) -> dict:
    """
    Format a document as a citation-enabled content block for the Messages API.

    Args:
        content: Document text content (or base64 for binary).
        title: Document title / filename.
        media_type: MIME type. Use "application/pdf" for base64 PDFs.
        citations_enabled: Whether to enable inline citations.

    Returns:
        A content block dict for inclusion in a user message's content list.
    """
    if media_type == "application/pdf":
        source = {
            "type": "base64",
            "media_type": "application/pdf",
            "data": content,
        }
    else:
        source = {
            "type": "text",
            "media_type": media_type,
            "data": content,
        }

    block: dict = {
        "type": "document",
        "source": source,
    }
    if title:
        block["title"] = title
    if citations_enabled:
        block["citations"] = {"enabled": True}
    return block


# ─── Anthropic Provider ──────────────────────────────────

class AnthropicProvider(LLMProvider):
    """Claude API via Anthropic's SDK.

    When a fallback_model is configured (env: TMOS13_FALLBACK_MODEL),
    the provider automatically retries on overload (529) and rate-limit
    (429) errors using the cheaper/faster fallback model.
    """

    # Overload: retry once on the fallback model after this delay
    OVERLOAD_RETRY_DELAY = 1.0

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6",
                 fallback_model: str = ""):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._fallback_model = fallback_model
        self._api_key = api_key
        fallback_info = f", fallback={fallback_model}" if fallback_model else ""
        logger.info(f"AnthropicProvider initialized: model={model}{fallback_info}")

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    # Maximum seconds to wait for a single LLM API call before timing out
    LLM_TIMEOUT_SECONDS = 90

    async def generate(
        self,
        system: Union[str, list[dict]],
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import anthropic

        try:
            return await self._call_model(
                self._model, system, messages, max_tokens
            )
        except (anthropic.InternalServerError, anthropic.RateLimitError) as e:
            status = getattr(e, "status_code", 0)
            if not self._fallback_model or self._fallback_model == self._model:
                raise  # no fallback configured — propagate

            logger.warning(
                "Primary model %s returned %d — falling back to %s",
                self._model, status, self._fallback_model,
            )
            await asyncio.sleep(self.OVERLOAD_RETRY_DELAY)
            return await self._call_model(
                self._fallback_model, system, messages, max_tokens
            )

    @staticmethod
    def _ensure_system_blocks(system: Union[str, list[dict]]) -> list[dict]:
        """
        Ensure system prompt is in content-block format with cache_control.

        If system is a plain string, wraps it in a single block with
        cache_control for prompt caching. If already a list of blocks,
        returns as-is (the assembler handles cache_control placement).
        """
        if isinstance(system, str):
            return [{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }]
        return system

    @staticmethod
    def _parse_citations(content_blocks) -> list[dict]:
        """Extract citation data from response content blocks."""
        citations = []
        for block in content_blocks:
            block_citations = getattr(block, "citations", None)
            if not block_citations:
                continue
            for cite in block_citations:
                citations.append({
                    "type": getattr(cite, "type", "document"),
                    "document_index": getattr(cite, "document_index", None),
                    "start_char_index": getattr(cite, "start_char_index", None),
                    "end_char_index": getattr(cite, "end_char_index", None),
                    "cited_text": getattr(cite, "cited_text", ""),
                })
        return citations

    async def _call_model(
        self,
        model: str,
        system: Union[str, list[dict]],
        messages: list[dict],
        max_tokens: int,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[dict] = None,
    ) -> LLMResponse:
        start = time.perf_counter()

        # Ensure system prompt uses block format with cache_control
        system_blocks = self._ensure_system_blocks(system)

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.messages.create,
                    **kwargs,
                ),
                timeout=self.LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"LLM API call timed out after {self.LLM_TIMEOUT_SECONDS}s"
            )

        latency_ms = (time.perf_counter() - start) * 1000

        # Extract text and tool_use results from content blocks
        text_parts = []
        tool_results = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                text_parts.append(block.text)
            elif getattr(block, "type", "") == "tool_use":
                tool_results.append({
                    "tool_id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        text = "\n".join(text_parts) if text_parts else ""

        # Parse citations from content blocks
        citations = self._parse_citations(response.content)

        usage = response.usage
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

        if cache_read > 0:
            logger.debug(f"Prompt cache hit: {cache_read} tokens read")
        elif cache_creation > 0:
            logger.debug(f"Prompt cache write: {cache_creation} tokens written")
        if citations:
            logger.debug(f"Citations returned: {len(citations)}")

        return LLMResponse(
            text=text,
            model=model,
            provider="anthropic",
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            finish_reason=response.stop_reason or "end_turn",
            raw={"id": response.id, "usage": {"input": usage.input_tokens, "output": usage.output_tokens}},
            tool_results=tool_results,
            citations=citations,
            has_citations=len(citations) > 0,
        )

    async def generate_with_tools(
        self,
        system: Union[str, list[dict]],
        messages: list[dict],
        tools: list[dict],
        tool_choice: Optional[dict] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import anthropic

        try:
            return await self._call_model(
                self._model, system, messages, max_tokens,
                tools=tools, tool_choice=tool_choice,
            )
        except (anthropic.InternalServerError, anthropic.RateLimitError) as e:
            status = getattr(e, "status_code", 0)
            if not self._fallback_model or self._fallback_model == self._model:
                raise

            logger.warning(
                "Primary model %s returned %d — falling back to %s (tools)",
                self._model, status, self._fallback_model,
            )
            await asyncio.sleep(self.OVERLOAD_RETRY_DELAY)
            return await self._call_model(
                self._fallback_model, system, messages, max_tokens,
                tools=tools, tool_choice=tool_choice,
            )

    async def health_check(self) -> dict:
        try:
            # Minimal API call to verify connectivity
            response = await asyncio.to_thread(
                self._client.messages.create,
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"ok": True, "detail": f"Anthropic API reachable, model={self._model}"}
        except Exception as e:
            return {"ok": False, "detail": f"Anthropic API error: {e}"}


# ─── Ollama Provider ─────────────────────────────────────

class OllamaProvider(LLMProvider):
    """
    Local LLM inference via Ollama.

    Supports any model available in Ollama: Gemma 3B, Llama 3, Mistral,
    Phi-3, etc. Communicates via Ollama's HTTP API.

    Env vars:
        OLLAMA_HOST  — Ollama server URL (default: http://localhost:11434)
        OLLAMA_MODEL — Model to use (default: gemma3:4b)
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "gemma3:4b",
    ):
        self._host = host.rstrip("/")
        self._model = model
        logger.info(f"OllamaProvider initialized: host={self._host}, model={model}")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        system: Union[str, list[dict]],
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        import json
        from urllib.request import Request, urlopen
        from urllib.error import URLError

        # Normalize system prompt to string
        if isinstance(system, list):
            system_text = "\n".join(
                block.get("text", "") for block in system if isinstance(block, dict)
            )
        else:
            system_text = system

        # Build Ollama chat payload
        ollama_messages = [{"role": "system", "content": system_text}]
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"] if isinstance(msg["content"], str) else str(msg["content"]),
            })

        payload = json.dumps({
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }).encode("utf-8")

        start = time.perf_counter()

        def _call():
            req = Request(
                f"{self._host}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())

        try:
            result = await asyncio.to_thread(_call)
        except URLError as e:
            raise ConnectionError(
                f"Ollama server unreachable at {self._host}. "
                f"Is Ollama running? Error: {e}"
            ) from e

        latency_ms = (time.perf_counter() - start) * 1000

        text = result.get("message", {}).get("content", "")
        eval_count = result.get("eval_count", 0)
        prompt_eval_count = result.get("prompt_eval_count", 0)

        return LLMResponse(
            text=text,
            model=self._model,
            provider="ollama",
            latency_ms=latency_ms,
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            finish_reason=result.get("done_reason", "stop"),
            raw=result,
        )

    async def health_check(self) -> dict:
        import json
        from urllib.request import Request, urlopen
        from urllib.error import URLError

        try:
            req = Request(f"{self._host}/api/tags", method="GET")
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            has_model = any(self._model in m for m in models)
            return {
                "ok": True,
                "detail": f"Ollama running, {len(models)} models available",
                "models": models,
                "requested_model_available": has_model,
            }
        except URLError as e:
            return {"ok": False, "detail": f"Ollama unreachable at {self._host}: {e}"}


# ─── Stub Provider ───────────────────────────────────────

class StubProvider(LLMProvider):
    """Deterministic provider for testing. Returns canned responses."""

    def __init__(self, response: str = "[TMOS13 stub response]"):
        self._response = response
        self._model = "stub"

    @property
    def name(self) -> str:
        return "stub"

    @property
    def model(self) -> str:
        return "stub"

    async def generate(
        self,
        system: Union[str, list[dict]],
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return LLMResponse(
            text=self._response,
            model="stub",
            provider="stub",
            latency_ms=0.1,
            input_tokens=0,
            output_tokens=len(self._response.split()),
        )


# ─── Factory / Singleton ─────────────────────────────────

_provider: Optional[LLMProvider] = None


def init_llm_provider(
    provider_type: str = "",
    api_key: str = "",
    model: str = "",
    ollama_host: str = "",
) -> LLMProvider:
    """
    Initialize the LLM provider.

    Auto-detection priority:
        1. Explicit provider_type parameter
        2. TMOS13_LLM_PROVIDER env var
        3. If ANTHROPIC_API_KEY is set → anthropic
        4. If OLLAMA_HOST is set → ollama
        5. Fallback → stub

    Args:
        provider_type: 'anthropic', 'ollama', or 'stub'
        api_key: API key (Anthropic)
        model: Model identifier override
        ollama_host: Ollama server URL override
    """
    global _provider

    ptype = (
        provider_type
        or os.environ.get("TMOS13_LLM_PROVIDER", "")
        or ""
    ).lower()

    # Auto-detect
    if not ptype:
        if api_key or os.environ.get("ANTHROPIC_API_KEY"):
            ptype = "anthropic"
        elif ollama_host or os.environ.get("OLLAMA_HOST"):
            ptype = "ollama"
        else:
            ptype = "anthropic"  # default if ANTHROPIC_API_KEY will be checked later

    if ptype == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        mdl = model or os.environ.get("TMOS13_MODEL") or os.environ.get("RABBITHOLE_MODEL", "claude-sonnet-4-6")
        fallback = os.environ.get("TMOS13_FALLBACK_MODEL", "")
        _provider = AnthropicProvider(api_key=key, model=mdl, fallback_model=fallback)

    elif ptype == "ollama":
        host = ollama_host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        mdl = model or os.environ.get("OLLAMA_MODEL", "gemma3:4b")
        _provider = OllamaProvider(host=host, model=mdl)

    elif ptype == "stub":
        _provider = StubProvider()

    else:
        logger.warning(f"Unknown LLM provider '{ptype}', falling back to stub")
        _provider = StubProvider()

    logger.info(f"LLM provider: {_provider.name} (model={_provider.model})")
    return _provider


def get_llm_provider() -> LLMProvider:
    """Get the active LLM provider instance."""
    if _provider is None:
        raise RuntimeError("LLM provider not initialized. Call init_llm_provider() first.")
    return _provider
