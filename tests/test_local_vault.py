"""
Tests for LocalVault — dimensional memory system.

Uses a temporary directory for all vault operations.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from local_vault import LocalVault


# ── Helpers ────────────────────────────────────────────────────

def _make_record(
    pack="test_pack",
    user="local",
    date="2026-03-17",
    session="sess-001",
    record_type="session_record",
    fields=None,
    content=None,
):
    return {
        "pack": pack,
        "user": user,
        "date": date,
        "session": session,
        "type": record_type,
        "fields": fields or {},
        "content": content or {"summary": "Test session summary."},
    }


# ── Tests ──────────────────────────────────────────────────────

class TestVaultWrite:

    def test_write_creates_file(self, tmp_vault):
        """write() creates a JSON file at the correct dimensional path."""
        vault = LocalVault(vault_dir=tmp_vault)
        record = _make_record()

        path = vault.write(record)

        assert path.exists()
        assert path.suffix == ".json"
        assert path.name == "sess-001.json"
        # Verify path structure: vault/pack/user/date/session.json
        assert "test_pack" in str(path)
        assert "local" in str(path)
        assert "2026-03-17" in str(path)

        # Verify content is valid JSON
        data = json.loads(path.read_text())
        assert data["pack"] == "test_pack"
        assert data["session"] == "sess-001"

    def test_write_prev_hash_genesis(self, tmp_vault):
        """First record in a directory gets prev_hash=GENESIS."""
        vault = LocalVault(vault_dir=tmp_vault)
        record = _make_record()

        vault.write(record)

        # Re-read the written file
        written = json.loads(
            (tmp_vault / "test_pack" / "local" / "2026-03-17" / "sess-001.json").read_text()
        )
        assert written["prev_hash"] == "GENESIS"

    def test_write_prev_hash_chain(self, tmp_vault):
        """Second record hashes the first record's content."""
        vault = LocalVault(vault_dir=tmp_vault)

        # Write first record
        rec1 = _make_record(session="sess-001")
        path1 = vault.write(rec1)
        # Small delay to ensure different mtime
        time.sleep(0.05)

        # Write second record in same directory
        rec2 = _make_record(session="sess-002")
        vault.write(rec2)

        # Re-read second record
        written2 = json.loads(
            (tmp_vault / "test_pack" / "local" / "2026-03-17" / "sess-002.json").read_text()
        )

        # prev_hash should be SHA-256 of the first file's bytes
        expected_hash = hashlib.sha256(path1.read_bytes()).hexdigest()
        assert written2["prev_hash"] == expected_hash


class TestVaultRead:

    def test_read_by_session_id(self, tmp_vault):
        """read() finds a record by session ID across all paths."""
        vault = LocalVault(vault_dir=tmp_vault)
        record = _make_record(session="unique-sess-42")
        vault.write(record)

        result = vault.read("unique-sess-42")
        assert result is not None
        assert result["session"] == "unique-sess-42"
        assert result["pack"] == "test_pack"

    def test_read_missing(self, tmp_vault):
        """read() returns None for an unknown session ID."""
        vault = LocalVault(vault_dir=tmp_vault)
        result = vault.read("nonexistent-session")
        assert result is None


class TestVaultQuery:

    def test_query_by_pack(self, tmp_vault):
        """query() filters by pack dimension."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(pack="legal", session="s1"))
        vault.write(_make_record(pack="medical", session="s2"))

        results = vault.query({"pack": "legal"})
        assert len(results) == 1
        assert results[0]["pack"] == "legal"

    def test_query_by_fields(self, tmp_vault):
        """query() filters by field key/value pairs."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(session="s1", fields={"urgency": "high", "matter": "injury"}))
        vault.write(_make_record(session="s2", fields={"urgency": "low"}))

        results = vault.query({"fields": {"urgency": "high"}})
        assert len(results) == 1
        assert results[0]["fields"]["urgency"] == "high"

    def test_query_by_content(self, tmp_vault):
        """query() does case-insensitive substring match on content."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(session="s1", content={"summary": "Contract review completed."}))
        vault.write(_make_record(session="s2", content={"summary": "Medical intake done."}))

        results = vault.query({"content": "contract"})
        assert len(results) == 1
        assert "Contract" in json.dumps(results[0]["content"])

    def test_query_combined_dimensions(self, tmp_vault):
        """Multiple filters AND together."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(pack="legal", session="s1", fields={"urgency": "high"}))
        vault.write(_make_record(pack="legal", session="s2", fields={"urgency": "low"}))
        vault.write(_make_record(pack="medical", session="s3", fields={"urgency": "high"}))

        results = vault.query({"pack": "legal", "fields": {"urgency": "high"}})
        assert len(results) == 1
        assert results[0]["session"] == "s1"


class TestVaultInherit:

    def test_inherit_builds_field_index(self, tmp_vault):
        """inherit() merges fields from prior sessions for the same user."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(session="s1", fields={"name": "John", "email": "j@x.com"}))
        time.sleep(0.02)
        vault.write(_make_record(session="s2", fields={"phone": "555-1234", "email": "john@new.com"}))

        result = vault.inherit("s1", "next_pack")
        assert result["user_id"] == "local"
        assert result["source_session"] == "s1"
        assert result["target_pack"] == "next_pack"

        # field_index should have merged fields (last-write wins for email)
        fi = result["field_index"]
        assert fi["name"] == "John"
        assert fi["phone"] == "555-1234"
        assert fi["email"] == "john@new.com"  # last-write wins

        # prior_sessions should include both
        assert len(result["prior_sessions"]) == 2

    def test_inherit_missing_source(self, tmp_vault):
        """inherit() handles missing source session gracefully."""
        vault = LocalVault(vault_dir=tmp_vault)
        result = vault.inherit("nonexistent", "target_pack")

        assert result["user_id"] == "unknown"
        assert result["prior_sessions"] == []
        assert result["field_index"] == {}


class TestVaultChain:

    def test_verify_chain_intact(self, tmp_vault):
        """Chain verification passes for clean records written in sequence."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(session="s1"))
        time.sleep(0.05)
        vault.write(_make_record(session="s2"))
        time.sleep(0.05)
        vault.write(_make_record(session="s3"))

        breaks = vault.verify_chain("test_pack", "local")
        assert breaks == []


class TestVaultList:

    def test_list_sessions(self, tmp_vault):
        """list_sessions() returns summaries sorted by date desc."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(date="2026-03-15", session="s1"))
        vault.write(_make_record(date="2026-03-17", session="s2"))
        vault.write(_make_record(date="2026-03-16", session="s3"))

        summaries = vault.list_sessions()
        assert len(summaries) == 3
        # Sorted by date descending
        assert summaries[0]["date"] == "2026-03-17"
        assert summaries[-1]["date"] == "2026-03-15"

    def test_list_sessions_filtered(self, tmp_vault):
        """list_sessions() filters by pack_id."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(pack="legal", session="s1"))
        vault.write(_make_record(pack="medical", session="s2"))

        summaries = vault.list_sessions(pack_id="legal")
        assert len(summaries) == 1
        assert summaries[0]["pack"] == "legal"


class TestVaultSearch:

    def test_search_by_pack_name(self, tmp_vault):
        """Search matches pack ID."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(pack="legal_intake", session="s1"))
        vault.write(_make_record(pack="gaming", session="s2"))

        results = vault.search("legal")
        assert len(results) == 1
        assert results[0]["record"]["pack"] == "legal_intake"
        assert results[0]["score"] >= 5

    def test_search_by_field_value(self, tmp_vault):
        """Search matches field values."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(
            session="s1",
            fields={"client_name": "Alice Johnson", "matter": "contract dispute"},
        ))
        vault.write(_make_record(session="s2", fields={"topic": "weather"}))

        results = vault.search("Alice")
        assert len(results) == 1
        assert results[0]["score"] >= 4

    def test_search_by_content_summary(self, tmp_vault):
        """Search matches content summary."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(
            session="s1",
            content={"summary": "Discussed patent infringement case details"},
        ))
        vault.write(_make_record(session="s2", content={"summary": "Weather chat"}))

        results = vault.search("patent")
        assert len(results) == 1
        assert "summary" in results[0]["matched"]

    def test_search_returns_ranked(self, tmp_vault):
        """Higher relevance scores sort first."""
        vault = LocalVault(vault_dir=tmp_vault)
        # Pack name match (score 5)
        vault.write(_make_record(pack="legal_intake", session="s1"))
        # Content match only (score 2-3)
        vault.write(_make_record(
            pack="gaming", session="s2",
            content={"summary": "legal question during game"},
        ))

        results = vault.search("legal")
        assert len(results) == 2
        assert results[0]["score"] > results[1]["score"]

    def test_search_no_results(self, tmp_vault):
        """Search with no matches returns empty."""
        vault = LocalVault(vault_dir=tmp_vault)
        vault.write(_make_record(session="s1"))

        results = vault.search("xyznonexistent")
        assert results == []

    def test_search_limit(self, tmp_vault):
        """Search respects limit parameter."""
        vault = LocalVault(vault_dir=tmp_vault)
        for i in range(5):
            vault.write(_make_record(
                pack="test_pack", session=f"s{i}",
                date=f"2026-03-{15+i:02d}",
            ))

        results = vault.search("test_pack", limit=3)
        assert len(results) == 3
