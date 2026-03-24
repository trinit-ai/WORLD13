"""
Tests for LocalIntelligence — synaptic awareness layer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from local_intelligence import LocalIntelligence


def _write_vault_record(vault_dir, pack, date="2026-03-17", session="s1",
                        content=None, fields=None):
    """Write a minimal vault record."""
    record_dir = vault_dir / pack / "local" / date
    record_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "pack": pack,
        "user": "local",
        "date": date,
        "session": session,
        "type": "session_record",
        "fields": fields or {},
        "content": content or {"summary": f"{pack} session", "transcript": []},
    }
    (record_dir / f"{session}.json").write_text(json.dumps(record))
    return record


class TestScanVault:

    def test_scans_records(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")
        _write_vault_record(vault, "gaming", session="s2")

        intel = LocalIntelligence(vault)
        sessions = intel._scan_vault()
        assert len(sessions) == 2

    def test_empty_vault(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        intel = LocalIntelligence(vault)
        assert intel._scan_vault() == []

    def test_skips_intelligence_cache(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")
        # Write a cache file in intelligence dir
        intel_dir = vault / "intelligence"
        intel_dir.mkdir(parents=True)
        (intel_dir / "cache.json").write_text("{}")

        intel = LocalIntelligence(vault)
        sessions = intel._scan_vault()
        assert len(sessions) == 1


class TestEngagement:

    def test_counts_per_pack(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1", date="2026-03-15")
        _write_vault_record(vault, "legal_intake", session="s2", date="2026-03-16")
        _write_vault_record(vault, "gaming", session="s3", date="2026-03-17")

        intel = LocalIntelligence(vault)
        engagement = intel.get_engagement_summary()
        assert engagement["legal_intake"]["count"] == 2
        assert engagement["gaming"]["count"] == 1

    def test_tracks_last_run(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1", date="2026-03-15")
        _write_vault_record(vault, "legal_intake", session="s2", date="2026-03-17")

        intel = LocalIntelligence(vault)
        engagement = intel.get_engagement_summary()
        assert engagement["legal_intake"]["last_run"] == "2026-03-17"


class TestDomainInterests:

    def test_ranks_by_count(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")
        _write_vault_record(vault, "legal_intake", session="s2")
        _write_vault_record(vault, "real_estate", session="s3")

        intel = LocalIntelligence(vault)
        interests = intel.get_domain_interests()
        assert interests[0][0] == "legal"
        assert interests[0][1] == 2

    def test_empty_for_no_sessions(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        intel = LocalIntelligence(vault)
        assert intel.get_domain_interests() == []


class TestDeskContext:

    def test_returns_context_block(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")
        _write_vault_record(vault, "gaming", session="s2")

        intel = LocalIntelligence(vault)
        context = intel.get_desk_context()
        assert "[SYSTEM INTELLIGENCE" in context
        assert "Sessions logged: 2" in context

    def test_empty_vault_returns_empty(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        intel = LocalIntelligence(vault)
        assert intel.get_desk_context() == ""


class TestPackContext:

    def test_returns_history_for_known_pack(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")
        _write_vault_record(vault, "legal_intake", session="s2")

        intel = LocalIntelligence(vault)
        context = intel.get_pack_context("legal_intake")
        assert "[SESSION HISTORY" in context
        assert "Prior sessions: 2" in context

    def test_empty_for_unknown_pack(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")

        intel = LocalIntelligence(vault)
        assert intel.get_pack_context("never_ran") == ""


class TestFormatPulse:

    def test_pulse_with_sessions(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")
        _write_vault_record(vault, "legal_intake", session="s2")
        _write_vault_record(vault, "gaming", session="s3")

        intel = LocalIntelligence(vault)
        pulse = intel.format_pulse()
        assert "Sessions logged:  3" in pulse
        assert "legal_intake" in pulse
        assert "Pack activity" in pulse

    def test_pulse_empty_vault(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        intel = LocalIntelligence(vault)
        pulse = intel.format_pulse()
        assert "No sessions yet" in pulse


class TestSuggestions:

    def test_suggests_adjacent_packs(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "legal_intake", session="s1")

        intel = LocalIntelligence(vault)
        engagement = intel.get_engagement_summary()
        suggestions = intel._get_unstarted_suggestions(engagement)
        # Should suggest legal-adjacent packs
        assert len(suggestions) > 0
        assert "legal_intake" not in suggestions  # shouldn't suggest already-ran

    def test_no_suggestions_for_unknown_domain(self, tmp_path):
        vault = tmp_path / "vault"
        _write_vault_record(vault, "xyz_unknown", session="s1")

        intel = LocalIntelligence(vault)
        engagement = intel.get_engagement_summary()
        suggestions = intel._get_unstarted_suggestions(engagement)
        assert suggestions == []
