"""
Shared fixtures for 13TMOS kernel tests.

All tests are self-contained: no external API calls, no Supabase, no Anthropic API.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Engine modules import each other without package prefix, so add engine/ to sys.path
ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))


# ── tmp_vault fixture ──────────────────────────────────────────

@pytest.fixture
def tmp_vault(tmp_path):
    """Creates a temporary vault directory, yields its Path, cleans up automatically."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    yield vault_dir
    # tmp_path cleanup is handled by pytest


# ── tmp_db fixture ─────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Creates a temp SQLite database path for SessionRunner."""
    db_path = tmp_path / "test.db"
    yield db_path


# ── mock_anthropic fixture ─────────────────────────────────────

def _make_text_response(text: str):
    """Build a mock Anthropic messages.create() response with a text block."""
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(
        content=[block],
        model="mock-model",
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


def _make_tool_use_response(tool_id: str, tool_name: str, tool_input: dict):
    """Build a mock Anthropic response with a tool_use block."""
    block = SimpleNamespace(
        type="tool_use",
        id=tool_id,
        name=tool_name,
        input=tool_input,
    )
    return SimpleNamespace(
        content=[block],
        model="mock-model",
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


@pytest.fixture
def mock_anthropic():
    """Patches anthropic.Anthropic so no real API calls are made.

    Returns the mock client instance. Configure responses via:
        mock_anthropic.messages.create.return_value = _make_text_response("hello")
    """
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_text_response("Mock reply.")

    with patch("anthropic.Anthropic", return_value=mock_client):
        yield mock_client


# ── Pack directory helper ──────────────────────────────────────

def create_pack_dir(base_dir: Path, pack_id: str, *, name: str = None, master_text: str = None) -> Path:
    """Create a minimal pack directory with manifest.json and master.md.

    Args:
        base_dir: The packs root directory (e.g., protocols/packs/).
        pack_id: Pack identifier / directory name.
        name: Human-readable name (defaults to pack_id).
        master_text: Content of master.md (defaults to a stub).

    Returns:
        Path to the created pack directory.
    """
    pack_dir = base_dir / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": name or pack_id,
        "version": "1.0.0",
        "category": "test",
        "description": f"Test pack: {pack_id}",
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    master = master_text or f"# {name or pack_id}\n\nYou are the {pack_id} assistant."
    (pack_dir / "master.md").write_text(master)

    return pack_dir


# Re-export helpers so test files can import from conftest
__all__ = [
    "create_pack_dir",
    "_make_text_response",
    "_make_tool_use_response",
]
