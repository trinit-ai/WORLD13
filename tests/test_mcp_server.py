"""
Tests for MCPServer tool dispatch.

Uses a temporary vault and patched paths. No external API calls.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))


# ── Helpers ────────────────────────────────────────────────────

def _make_server(tmp_path):
    """Create an MCPServer with patched paths pointing to temp directories."""
    packs_dir = tmp_path / "protocols" / "packs"
    packs_dir.mkdir(parents=True)
    library_dir = tmp_path / "protocols" / "library"
    library_dir.mkdir(parents=True)
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    import mcp_server as mcp_mod
    from local_vault import LocalVault

    orig_packs = mcp_mod.PACKS_DIR
    orig_library = mcp_mod.LIBRARY_DIR
    orig_vault = mcp_mod.VAULT_DIR
    orig_root = mcp_mod.ROOT_DIR

    mcp_mod.PACKS_DIR = packs_dir
    mcp_mod.LIBRARY_DIR = library_dir
    mcp_mod.VAULT_DIR = vault_dir
    mcp_mod.ROOT_DIR = tmp_path

    server = mcp_mod.MCPServer()
    server._vault = LocalVault(vault_dir=vault_dir)

    return server, mcp_mod, {
        "PACKS_DIR": orig_packs,
        "LIBRARY_DIR": orig_library,
        "VAULT_DIR": orig_vault,
        "ROOT_DIR": orig_root,
        "packs_dir": packs_dir,
        "library_dir": library_dir,
        "vault_dir": vault_dir,
    }


def _teardown_server(mcp_mod, originals):
    mcp_mod.PACKS_DIR = originals["PACKS_DIR"]
    mcp_mod.LIBRARY_DIR = originals["LIBRARY_DIR"]
    mcp_mod.VAULT_DIR = originals["VAULT_DIR"]
    mcp_mod.ROOT_DIR = originals["ROOT_DIR"]


def _create_pack(packs_dir, pack_id, name=None, category="test"):
    """Create a minimal pack in the given packs directory."""
    pack_dir = packs_dir / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name or pack_id,
        "version": "1.0.0",
        "category": category,
        "description": f"Test pack: {pack_id}",
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest))
    (pack_dir / "master.md").write_text(f"# {name or pack_id}")
    return pack_dir


# ── Tests ──────────────────────────────────────────────────────

class TestMCPServer:

    def test_engine_status(self, tmp_path):
        """engine_status returns a status dict with expected keys."""
        server, mcp_mod, originals = _make_server(tmp_path)
        try:
            result = asyncio.run(server.handle_tool_call("engine_status", {}))

            assert "result" in result
            status = result["result"]
            assert status["service"] == "13TMOS"
            assert status["status"] == "online"
            assert "active_packs" in status
            assert "vault_records" in status
            assert "mcp_tools" in status
            assert isinstance(status["mcp_tools"], int)
        finally:
            _teardown_server(mcp_mod, originals)

    def test_pack_list(self, tmp_path):
        """pack_list returns packs from the packs directory."""
        server, mcp_mod, originals = _make_server(tmp_path)
        try:
            packs_dir = originals["packs_dir"]
            _create_pack(packs_dir, "alpha", name="Alpha Pack")
            _create_pack(packs_dir, "beta", name="Beta Pack")

            result = asyncio.run(server.handle_tool_call("pack_list", {"status": "active"}))

            assert "result" in result
            data = result["result"]
            assert data["count"] == 2
            pack_ids = [p["pack_id"] for p in data["packs"]]
            assert "alpha" in pack_ids
            assert "beta" in pack_ids
        finally:
            _teardown_server(mcp_mod, originals)

    def test_pack_search(self, tmp_path):
        """pack_search finds packs by keyword in name or manifest."""
        server, mcp_mod, originals = _make_server(tmp_path)
        try:
            packs_dir = originals["packs_dir"]
            _create_pack(packs_dir, "legal_intake", name="Legal Intake")
            _create_pack(packs_dir, "medical_intake", name="Medical Intake")
            _create_pack(packs_dir, "customer_support", name="Customer Support")

            result = asyncio.run(server.handle_tool_call("pack_search", {"query": "legal"}))

            assert "result" in result
            data = result["result"]
            assert data["total"] >= 1
            pack_ids = [r["pack_id"] for r in data["results"]]
            assert "legal_intake" in pack_ids
            # customer_support should not match "legal"
            assert "customer_support" not in pack_ids
        finally:
            _teardown_server(mcp_mod, originals)

    def test_unknown_tool(self, tmp_path):
        """Unknown tool name returns an error dict."""
        server, mcp_mod, originals = _make_server(tmp_path)
        try:
            result = asyncio.run(server.handle_tool_call("totally_fake_tool", {}))

            assert "error" in result
            assert "Unknown tool" in result["error"]
            assert "totally_fake_tool" in result["error"]
        finally:
            _teardown_server(mcp_mod, originals)

    def test_pack_read(self, tmp_path):
        """pack_read returns pack contents including master.md."""
        server, mcp_mod, originals = _make_server(tmp_path)
        try:
            packs_dir = originals["packs_dir"]
            _create_pack(packs_dir, "test_pack", name="Test Pack")

            result = asyncio.run(
                server.handle_tool_call("pack_read", {"pack_id": "test_pack"})
            )

            assert "result" in result
            data = result["result"]
            assert data["pack_id"] == "test_pack"
            assert "manifest_json" in data
            assert data["manifest_json"]["name"] == "Test Pack"
            assert "master_md" in data
        finally:
            _teardown_server(mcp_mod, originals)

    def test_vault_query(self, tmp_path):
        """vault_query returns records from the vault."""
        server, mcp_mod, originals = _make_server(tmp_path)
        try:
            # Write a record to the vault
            server._vault.write({
                "pack": "legal",
                "user": "local",
                "date": "2026-03-17",
                "session": "vq-001",
                "type": "session_record",
                "fields": {"urgency": "high"},
                "content": {"summary": "Test vault query."},
            })

            result = asyncio.run(
                server.handle_tool_call("vault_query", {"pack_id": "legal"})
            )

            assert "result" in result
            data = result["result"]
            assert data["total"] >= 1
            sessions = [r["session_id"] for r in data["records"]]
            assert "vq-001" in sessions
        finally:
            _teardown_server(mcp_mod, originals)
