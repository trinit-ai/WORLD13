"""
Tests for WebSearchProvider.

All HTTP calls are mocked. No real Brave Search API calls.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))


# ── Helpers ────────────────────────────────────────────────────

def _get_provider():
    from tool_providers.web_search import WebSearchProvider
    return WebSearchProvider()


def _brave_response_json():
    """Fake Brave Search API response."""
    return {
        "web": {
            "results": [
                {
                    "title": "Example Result",
                    "description": "This is a test search result.",
                    "url": "https://example.com/result1",
                },
                {
                    "title": "Second Result",
                    "description": "Another test result.",
                    "url": "https://example.com/result2",
                },
            ]
        }
    }


# ── Tests ──────────────────────────────────────────────────────

class TestWebSearchProvider:

    def test_search_missing_api_key(self):
        """Returns error message when BRAVE_SEARCH_API_KEY is not set."""
        provider = _get_provider()

        with patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}, clear=False), \
             patch("config.WEB_SEARCH_ENABLED", True), \
             patch("config.WEB_SEARCH_MAX_RESULTS", 5):
            result = asyncio.run(
                provider.execute("search", {"query": "test"}, {})
            )

        assert result["success"] is False
        assert "API key" in result["message"] or "not configured" in result["message"]

    def test_search_disabled(self):
        """Returns error when WEB_SEARCH_ENABLED is False."""
        provider = _get_provider()

        with patch("config.WEB_SEARCH_ENABLED", False):
            result = asyncio.run(
                provider.execute("search", {"query": "test"}, {})
            )

        assert result["success"] is False
        assert "disabled" in result["message"].lower()

    def test_search_empty_query(self):
        """Returns error for empty query."""
        provider = _get_provider()

        with patch("config.WEB_SEARCH_ENABLED", True), \
             patch("config.WEB_SEARCH_MAX_RESULTS", 5), \
             patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=False):
            result = asyncio.run(
                provider.execute("search", {"query": ""}, {})
            )

        assert result["success"] is False
        assert "query" in result["message"].lower()

    def test_search_success(self):
        """Mock httpx, verify structured results."""
        provider = _get_provider()

        mock_response = MagicMock()
        mock_response.json.return_value = _brave_response_json()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("config.WEB_SEARCH_ENABLED", True), \
             patch("config.WEB_SEARCH_MAX_RESULTS", 5), \
             patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=False), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                provider.execute("search", {"query": "test search"}, {})
            )

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Example Result"
        assert result["results"][0]["url"] == "https://example.com/result1"
        assert result["query"] == "test search"

    def test_search_api_error(self):
        """Mock httpx error, verify graceful handling."""
        import httpx

        provider = _get_provider()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Rate limited",
            request=MagicMock(),
            response=mock_response,
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("config.WEB_SEARCH_ENABLED", True), \
             patch("config.WEB_SEARCH_MAX_RESULTS", 5), \
             patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=False), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                provider.execute("search", {"query": "test"}, {})
            )

        assert result["success"] is False
        assert "error" in result["message"].lower() or "429" in result["message"]

    def test_search_timeout(self):
        """Mock timeout, verify graceful handling."""
        import httpx

        provider = _get_provider()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("config.WEB_SEARCH_ENABLED", True), \
             patch("config.WEB_SEARCH_MAX_RESULTS", 5), \
             patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"}, clear=False), \
             patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                provider.execute("search", {"query": "test"}, {})
            )

        assert result["success"] is False
        assert "timed out" in result["message"].lower()

    def test_unsupported_operation(self):
        """Unsupported operation returns error."""
        provider = _get_provider()
        result = asyncio.run(
            provider.execute("delete", {"query": "test"}, {})
        )
        assert result["success"] is False
        assert "Unsupported" in result["message"]
