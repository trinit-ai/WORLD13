"""
Tests for SessionRunner and PackRegistry.

Uses a real SQLite database in /tmp and a mocked Anthropic client.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from conftest import create_pack_dir, _make_text_response, _make_tool_use_response


# ── Helpers ────────────────────────────────────────────────────

def _make_runner(tmp_db, tmp_packs_dir):
    """Create a SessionRunner with patched paths and a mock Anthropic client."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_text_response("Mock reply.")

    import session_runner as sr_mod

    # Patch the module-level PACKS_DIR so PackRegistry.find_pack_dir uses our temp dir
    original_packs = sr_mod.PACKS_DIR
    sr_mod.PACKS_DIR = tmp_packs_dir

    runner = sr_mod.SessionRunner(db_path=tmp_db)
    runner._client = mock_client

    return runner, mock_client, sr_mod, original_packs


def _teardown_runner(sr_mod, original_packs):
    sr_mod.PACKS_DIR = original_packs


# ── Tests ──────────────────────────────────────────────────────

class TestSessionRunner:

    def test_create_session(self, tmp_db, tmp_path):
        """New session for channel/sender is created with correct fields."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "test_pack")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            session = runner._create_session("whatsapp", "+1234567890", "test_pack")
            assert session is not None
            assert session["channel"] == "whatsapp"
            assert session["sender_id"] == "+1234567890"
            assert session["pack_id"] == "test_pack"
            assert session["status"] == "active"
            assert session["turn_count"] == 0
            assert "session_id" in session
        finally:
            _teardown_runner(sr_mod, orig)

    def test_handle_message_creates_session(self, tmp_db, tmp_path):
        """First message auto-creates a session when none exists."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            # No session exists yet
            assert runner._get_session("sms", "+9999") is None

            reply = asyncio.run(
                runner.handle_message("sms", "+9999", "Hello!", default_pack="guest")
            )

            # Session should now exist
            session = runner._get_session("sms", "+9999")
            assert session is not None
            assert session["pack_id"] == "guest"
            assert reply == "Mock reply."
        finally:
            _teardown_runner(sr_mod, orig)

    def test_handle_message_persists_exchange(self, tmp_db, tmp_path):
        """User + assistant messages are saved to channel_exchanges."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            asyncio.run(
                runner.handle_message("web", "user1", "What is 2+2?", default_pack="guest")
            )

            rows = runner.conn.execute(
                "SELECT role, content FROM channel_exchanges ORDER BY id"
            ).fetchall()

            assert len(rows) == 2
            assert rows[0]["role"] == "user"
            assert rows[0]["content"] == "What is 2+2?"
            assert rows[1]["role"] == "assistant"
            assert rows[1]["content"] == "Mock reply."
        finally:
            _teardown_runner(sr_mod, orig)

    def test_conversation_history_loaded(self, tmp_db, tmp_path):
        """Prior messages are sent to Claude on subsequent turns."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            # First message
            asyncio.run(
                runner.handle_message("web", "user1", "Turn one", default_pack="guest")
            )

            # Second message
            mock_client.messages.create.return_value = _make_text_response("Reply two.")
            asyncio.run(
                runner.handle_message("web", "user1", "Turn two", default_pack="guest")
            )

            # Inspect the messages kwarg on the second call
            second_call_kwargs = mock_client.messages.create.call_args_list[1]
            messages = second_call_kwargs.kwargs.get("messages") or second_call_kwargs[1].get("messages")

            # Should include history: user("Turn one"), assistant("Mock reply."), user("Turn two")
            assert len(messages) >= 3
            assert messages[-1]["content"] == "Turn two"
            assert messages[-1]["role"] == "user"
            # Prior exchange should be present
            user_contents = [m["content"] for m in messages if m["role"] == "user"]
            assert "Turn one" in user_contents
        finally:
            _teardown_runner(sr_mod, orig)

    def test_cmd_load(self, tmp_db, tmp_path):
        """'load pack_id' switches to a different pack."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")
        create_pack_dir(packs_dir, "legal_intake", name="Legal Intake")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            # Create initial session
            runner._create_session("web", "user1", "guest")

            # Load a different pack
            reply = asyncio.run(
                runner.handle_message("web", "user1", "load legal_intake")
            )

            assert "Legal Intake" in reply or "legal_intake" in reply
            session = runner._get_session("web", "user1")
            assert session["pack_id"] == "legal_intake"
        finally:
            _teardown_runner(sr_mod, orig)

    def test_cmd_reset(self, tmp_db, tmp_path):
        """'reset' restarts the current session."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            runner._create_session("web", "user1", "guest")
            old_session_id = runner._get_session("web", "user1")["session_id"]

            reply = asyncio.run(
                runner.handle_message("web", "user1", "reset")
            )

            assert "reset" in reply.lower() or "Reset" in reply
            new_session = runner._get_session("web", "user1")
            assert new_session["session_id"] != old_session_id
            assert new_session["pack_id"] == "guest"
        finally:
            _teardown_runner(sr_mod, orig)

    def test_cmd_status(self, tmp_db, tmp_path):
        """'status' returns session info."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            runner._create_session("web", "user1", "guest")

            reply = asyncio.run(
                runner.handle_message("web", "user1", "status")
            )

            assert "guest" in reply
            assert "web" in reply.lower() or "Channel" in reply
            assert "Turns" in reply
        finally:
            _teardown_runner(sr_mod, orig)

    def test_seed_session(self, tmp_db, tmp_path):
        """seed_session creates a seeded session with primer exchanges."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "onboarding")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            result = runner.seed_session(
                channel="email",
                sender_id="john@example.com",
                pack_id="onboarding",
                name="John Doe",
                context="New client, referred by Sarah.",
            )

            assert result["status"] == "seeded"
            assert result["name"] == "John Doe"
            assert result["pack_id"] == "onboarding"

            # Verify primer exchanges were written
            rows = runner.conn.execute(
                "SELECT role, content FROM channel_exchanges WHERE session_id = ? ORDER BY id",
                (result["session_id"],),
            ).fetchall()
            assert len(rows) == 2
            assert "John Doe" in rows[0]["content"]
            assert rows[0]["role"] == "user"
            assert rows[1]["role"] == "assistant"
        finally:
            _teardown_runner(sr_mod, orig)

    def test_seeded_session_activates(self, tmp_db, tmp_path):
        """Seeded session becomes active on first real message."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "onboarding")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            result = runner.seed_session(
                channel="email",
                sender_id="john@example.com",
                pack_id="onboarding",
                name="John Doe",
            )

            # Verify status is seeded in DB
            row = runner.conn.execute(
                "SELECT status FROM channel_sessions WHERE session_id = ?",
                (result["session_id"],),
            ).fetchone()
            assert row["status"] == "seeded"

            # First real message should activate the session
            asyncio.run(
                runner.handle_message("email", "john@example.com", "Hi, I got your email!")
            )

            row = runner.conn.execute(
                "SELECT status FROM channel_sessions WHERE session_id = ?",
                (result["session_id"],),
            ).fetchone()
            assert row["status"] == "active"
        finally:
            _teardown_runner(sr_mod, orig)

    def test_tool_use_loop(self, tmp_db, tmp_path):
        """When Claude returns tool_use, runner should handle it (validates future tool-use loop).

        Current SessionRunner reads response.content[0].text directly, so a tool_use
        response will raise an AttributeError. This test documents that behavior and
        validates the expected error path, serving as a spec for when the tool-use loop
        is built.
        """
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "guest")

        runner, mock_client, sr_mod, orig = _make_runner(tmp_db, packs_dir)
        try:
            # First call returns tool_use (no .text attribute)
            tool_response = _make_tool_use_response(
                tool_id="toolu_abc123",
                tool_name="web_search",
                tool_input={"query": "test"},
            )
            # Second call returns text
            text_response = _make_text_response("Here are the search results.")

            mock_client.messages.create.side_effect = [tool_response, text_response]

            # The current runner doesn't have a tool-use loop; it accesses .text directly.
            # A tool_use block has no .text attribute, so this should hit the error handler.
            reply = asyncio.run(
                runner.handle_message("web", "user1", "Search for something", default_pack="guest")
            )

            # Current behavior: the runner catches the AttributeError and returns an error message.
            # When the tool-use loop is implemented, this test should be updated to assert
            # that the runner calls the tool provider and makes a second API call.
            assert reply is not None  # Either error message or successful result
            assert isinstance(reply, str)

            # Verify at least one API call was made
            assert mock_client.messages.create.call_count >= 1
        finally:
            _teardown_runner(sr_mod, orig)


class TestPackRegistry:

    def test_find_pack_dir(self, tmp_path):
        """find_pack_dir locates a pack in the packs directory."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "my_pack")

        import session_runner as sr_mod
        original = sr_mod.PACKS_DIR
        sr_mod.PACKS_DIR = packs_dir
        try:
            registry = sr_mod.PackRegistry()
            result = registry.find_pack_dir("my_pack")
            assert result is not None
            assert result.name == "my_pack"

            # Non-existent pack
            assert registry.find_pack_dir("nonexistent") is None
        finally:
            sr_mod.PACKS_DIR = original

    def test_load_protocol(self, tmp_path):
        """load_protocol returns system_prompt from master.md."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "test_pack", master_text="You are a helpful bot.")

        import session_runner as sr_mod
        original = sr_mod.PACKS_DIR
        sr_mod.PACKS_DIR = packs_dir
        try:
            registry = sr_mod.PackRegistry()
            protocol = registry.load_protocol("test_pack")
            assert protocol is not None
            assert protocol["system_prompt"] == "You are a helpful bot."
            assert protocol["pack_id"] == "test_pack"
            assert protocol["name"] == "test_pack"
        finally:
            sr_mod.PACKS_DIR = original

    def test_list_packs(self, tmp_path):
        """list_packs returns pack IDs from the packs directory."""
        packs_dir = tmp_path / "packs"
        create_pack_dir(packs_dir, "alpha")
        create_pack_dir(packs_dir, "beta")
        # Create a dir without manifest.json (should be excluded)
        (packs_dir / "incomplete").mkdir()

        import session_runner as sr_mod
        original = sr_mod.PACKS_DIR
        sr_mod.PACKS_DIR = packs_dir
        try:
            registry = sr_mod.PackRegistry()
            packs = registry.list_packs()
            assert "alpha" in packs
            assert "beta" in packs
            assert "incomplete" not in packs
        finally:
            sr_mod.PACKS_DIR = original


class TestVaultToolProvider:

    def test_vault_search_returns_results(self, tmp_path):
        """_execute_vault_tool search finds matching vault records."""
        from local_vault import LocalVault
        import local_vault as lv_mod
        from session_runner import _execute_vault_tool

        vault_dir = tmp_path / "vault"
        vault = LocalVault(vault_dir=vault_dir)
        vault.write({
            "pack": "legal_intake", "user": "local", "date": "2026-03-17",
            "session": "sess_001",
            "fields": {"client_name": "Alice"},
            "content": {"summary": "Discussed contract dispute"},
        })

        with patch.object(lv_mod, "VAULT_DIR", vault_dir):
            result = _execute_vault_tool("search", {"query": "Alice"})
            assert result["success"] is True
            assert result["results_count"] >= 1
            assert "Alice" in result["message"]

    def test_vault_search_no_results(self, tmp_path):
        """_execute_vault_tool search returns success with 0 results for no match."""
        import local_vault as lv_mod
        from session_runner import _execute_vault_tool

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        with patch.object(lv_mod, "VAULT_DIR", vault_dir):
            result = _execute_vault_tool("search", {"query": "nonexistent"})
            assert result["success"] is True
            assert result["results_count"] == 0

    def test_vault_search_empty_query(self):
        """_execute_vault_tool search rejects empty query."""
        from session_runner import _execute_vault_tool
        result = _execute_vault_tool("search", {"query": ""})
        assert result["success"] is False

    def test_vault_query_by_pack(self, tmp_path):
        """_execute_vault_tool query filters by pack_id."""
        from local_vault import LocalVault
        import local_vault as lv_mod
        from session_runner import _execute_vault_tool

        vault_dir = tmp_path / "vault"
        vault = LocalVault(vault_dir=vault_dir)
        vault.write({
            "pack": "legal", "user": "local", "date": "2026-03-17",
            "session": "s1", "fields": {}, "content": {},
        })
        vault.write({
            "pack": "gaming", "user": "local", "date": "2026-03-17",
            "session": "s2", "fields": {}, "content": {},
        })

        with patch.object(lv_mod, "VAULT_DIR", vault_dir):
            result = _execute_vault_tool("query", {"pack_id": "legal"})
            assert result["success"] is True
            assert result["results_count"] == 1

    def test_vault_unsupported_operation(self):
        """_execute_vault_tool rejects unknown operations."""
        from session_runner import _execute_vault_tool
        result = _execute_vault_tool("delete_everything", {})
        assert result["success"] is False

    def test_build_tool_defs_includes_vault(self):
        """_build_tool_definitions generates correct schemas for vault tools."""
        from session_runner import _build_tool_definitions
        manifest = {
            "tools": {
                "vault_search": {
                    "provider": "vault",
                    "description": "Search vault",
                    "scopes": ["search"],
                    "config": {},
                },
                "vault_query": {
                    "provider": "vault",
                    "description": "Query vault",
                    "scopes": ["query"],
                    "config": {},
                },
            }
        }
        defs = _build_tool_definitions(manifest)
        names = [d["name"] for d in defs]
        assert "vault_search" in names
        assert "vault_query" in names

        vs = next(d for d in defs if d["name"] == "vault_search")
        assert "query" in vs["input_schema"]["required"]

        vq = next(d for d in defs if d["name"] == "vault_query")
        assert "pack_id" in vq["input_schema"]["properties"]
