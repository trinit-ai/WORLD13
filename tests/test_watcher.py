"""
Tests for Watcher condition evaluation and formatting.

Tests standalone functions: evaluate_condition, _resolve_field, _format_message.
No filesystem watching or external dependencies needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from watcher import evaluate_condition, _resolve_field, _format_message, VaultWatcher


# ── Test Records ───────────────────────────────────────────────

LEGAL_RECORD = {
    "pack": "legal_intake",
    "user": "local",
    "date": "2026-03-17",
    "session": "sess-001",
    "type": "session_record",
    "fields": {
        "urgency": "high",
        "matter_type": "personal_injury",
        "retainer": "5000",
    },
    "_session_count": 5,
}

SUPPORT_RECORD = {
    "pack": "customer_support",
    "user": "local",
    "date": "2026-03-17",
    "session": "sess-002",
    "type": "session_record",
    "fields": {
        "urgency": "low",
        "category": "billing",
    },
    "_session_count": 12,
}


# ── Condition Evaluation Tests ─────────────────────────────────

class TestSimpleCondition:

    def test_simple_condition(self):
        """'pack == legal_intake' matches the legal record."""
        assert evaluate_condition(LEGAL_RECORD, "pack == legal_intake") is True
        assert evaluate_condition(SUPPORT_RECORD, "pack == legal_intake") is False

    def test_nested_field_condition(self):
        """'fields.urgency == high' resolves dotted path."""
        assert evaluate_condition(LEGAL_RECORD, "fields.urgency == high") is True
        assert evaluate_condition(SUPPORT_RECORD, "fields.urgency == high") is False

    def test_missing_field_returns_false(self):
        """Condition on a nonexistent field returns False (not an error)."""
        assert evaluate_condition(LEGAL_RECORD, "fields.nonexistent == foo") is False


class TestBooleanConditions:

    def test_and_condition(self):
        """'pack == legal_intake AND fields.urgency == high' requires both."""
        cond = "pack == legal_intake and fields.urgency == high"
        assert evaluate_condition(LEGAL_RECORD, cond) is True

        # Fails when urgency is wrong
        cond2 = "pack == legal_intake and fields.urgency == low"
        assert evaluate_condition(LEGAL_RECORD, cond2) is False

    def test_or_condition(self):
        """'pack == legal_intake OR pack == customer_support' matches either."""
        cond = "pack == legal_intake or pack == customer_support"
        assert evaluate_condition(LEGAL_RECORD, cond) is True
        assert evaluate_condition(SUPPORT_RECORD, cond) is True

        # Neither pack matches
        other = {"pack": "medical", "fields": {}}
        assert evaluate_condition(other, cond) is False


class TestComparisonOperators:

    def test_not_equal(self):
        assert evaluate_condition(LEGAL_RECORD, "pack != customer_support") is True
        assert evaluate_condition(LEGAL_RECORD, "pack != legal_intake") is False

    def test_greater_than(self):
        assert evaluate_condition(LEGAL_RECORD, "_session_count > 3") is True
        assert evaluate_condition(LEGAL_RECORD, "_session_count > 10") is False

    def test_less_than(self):
        assert evaluate_condition(LEGAL_RECORD, "_session_count < 10") is True
        assert evaluate_condition(LEGAL_RECORD, "_session_count < 3") is False

    def test_greater_equal(self):
        assert evaluate_condition(LEGAL_RECORD, "_session_count >= 5") is True
        assert evaluate_condition(LEGAL_RECORD, "_session_count >= 6") is False

    def test_less_equal(self):
        assert evaluate_condition(LEGAL_RECORD, "_session_count <= 5") is True
        assert evaluate_condition(LEGAL_RECORD, "_session_count <= 4") is False


class TestRuleMatching:

    def test_rule_fires_on_match(self):
        """A matching record triggers the rule."""
        watcher = VaultWatcher.__new__(VaultWatcher)
        watcher.rules = [
            {
                "name": "legal_alert",
                "condition": "pack == legal_intake and fields.urgency == high",
                "action": "notify",
                "message": "High urgency legal intake received.",
            },
        ]

        matched = watcher.evaluate_rules(LEGAL_RECORD)
        assert len(matched) == 1
        assert matched[0]["name"] == "legal_alert"

    def test_rule_skips_on_mismatch(self):
        """A non-matching record skips the rule."""
        watcher = VaultWatcher.__new__(VaultWatcher)
        watcher.rules = [
            {
                "name": "legal_alert",
                "condition": "pack == legal_intake and fields.urgency == high",
                "action": "notify",
                "message": "Alert!",
            },
        ]

        matched = watcher.evaluate_rules(SUPPORT_RECORD)
        assert len(matched) == 0


class TestFormatMessage:

    def test_format_message_template(self):
        """'{pack} session complete' renders correctly."""
        result = _format_message("{pack} session complete", LEGAL_RECORD)
        assert result == "legal_intake session complete"

    def test_format_fields_template(self):
        """'{fields.urgency}' resolves to field value."""
        result = _format_message("Urgency: {fields.urgency}", LEGAL_RECORD)
        assert result == "Urgency: high"

    def test_format_session_count(self):
        """{session_count} resolves to _session_count."""
        result = _format_message("Total sessions: {session_count}", LEGAL_RECORD)
        assert result == "Total sessions: 5"

    def test_format_missing_field(self):
        """Missing fields render as '?'."""
        result = _format_message("{fields.nonexistent}", LEGAL_RECORD)
        assert result == "?"

    def test_format_session_id(self):
        """{session_id} resolves to the session field."""
        result = _format_message("Session: {session_id}", LEGAL_RECORD)
        assert result == "Session: sess-001"


class TestResolveField:

    def test_top_level(self):
        assert _resolve_field(LEGAL_RECORD, "pack") == "legal_intake"

    def test_dotted_path(self):
        assert _resolve_field(LEGAL_RECORD, "fields.urgency") == "high"

    def test_session_count_special(self):
        assert _resolve_field(LEGAL_RECORD, "session_count") == 5

    def test_missing_returns_none(self):
        assert _resolve_field(LEGAL_RECORD, "nonexistent") is None

    def test_deep_missing_returns_none(self):
        assert _resolve_field(LEGAL_RECORD, "fields.nonexistent") is None


class TestWatcherActions:
    """Test the new watcher action methods."""

    def _make_watcher(self, tmp_path):
        """Create a VaultWatcher with no rules file (we set rules manually)."""
        rules_path = tmp_path / "watchers.yaml"
        rules_path.write_text("watchers: []")
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        return VaultWatcher(
            vault_dir=str(vault_dir),
            rules_path=str(rules_path),
            identity_path=str(tmp_path / "identity.json"),
        )

    def test_send_email_fires(self, tmp_path):
        """send_email action calls email_service.send_email with formatted fields."""
        from unittest.mock import patch, MagicMock

        watcher = self._make_watcher(tmp_path)
        rule = {
            "name": "test_email",
            "action": "send_email",
            "to": "{fields.email}",
            "subject": "Intake complete: {pack}",
            "body": "Matter type: {fields.matter_type}",
        }
        record = {
            "pack": "legal_intake",
            "fields": {"email": "alice@example.com", "matter_type": "contract"},
            "session": "s1", "date": "2026-03-17", "user": "local",
        }

        mock_send = MagicMock(return_value={"success": True, "message_id": "msg_123"})
        with patch("watcher.send_email", mock_send, create=True):
            # Import send_email inside fire_rule via email_service
            with patch.dict("sys.modules", {"email_service": MagicMock(send_email=mock_send)}):
                watcher.fire_rule(rule, record)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs[1]["to"] == "alice@example.com"
        assert "legal_intake" in call_kwargs[1]["subject"]

    def test_send_email_missing_fields(self, tmp_path):
        """send_email with missing to/subject/body logs error, doesn't crash."""
        watcher = self._make_watcher(tmp_path)
        rule = {"name": "bad_email", "action": "send_email"}
        # Should not raise
        watcher.fire_rule(rule, LEGAL_RECORD)

    def test_send_channel_fires(self, tmp_path):
        """send_channel action calls session runner with formatted message."""
        from unittest.mock import patch, MagicMock, AsyncMock

        watcher = self._make_watcher(tmp_path)
        rule = {
            "name": "test_channel",
            "action": "send_channel",
            "channel": "telegram",
            "sender_id": "12345",
            "message": "Your {pack} session is complete.",
            "pack_id": "guest",
        }

        mock_runner = MagicMock()
        mock_runner.handle_message = AsyncMock(return_value="OK")

        with patch("session_runner.SessionRunner", return_value=mock_runner):
            watcher.fire_rule(rule, LEGAL_RECORD)

        mock_runner.handle_message.assert_called_once()
        args = mock_runner.handle_message.call_args
        assert args[0][0] == "telegram"
        assert args[0][1] == "12345"
        assert "legal_intake" in args[0][2]

    def test_send_channel_missing_fields(self, tmp_path):
        """send_channel with missing fields logs error, doesn't crash."""
        watcher = self._make_watcher(tmp_path)
        rule = {"name": "bad_channel", "action": "send_channel"}
        watcher.fire_rule(rule, LEGAL_RECORD)

    def test_start_session_fires(self, tmp_path):
        """start_session action seeds a session via session runner."""
        from unittest.mock import patch, MagicMock

        watcher = self._make_watcher(tmp_path)
        rule = {
            "name": "test_seed",
            "action": "start_session",
            "channel": "whatsapp",
            "sender_id": "+1555000{fields.urgency}",
            "pack": "follow_up",
            "name": "Client",
            "context": "Follow up on {pack} session",
        }

        mock_runner = MagicMock()
        mock_runner.seed_session.return_value = {
            "session_id": "new_sess",
            "status": "seeded",
        }

        with patch("session_runner.SessionRunner", return_value=mock_runner):
            watcher.fire_rule(rule, LEGAL_RECORD)

        mock_runner.seed_session.assert_called_once()
        call_kwargs = mock_runner.seed_session.call_args[1]
        assert call_kwargs["channel"] == "whatsapp"
        assert call_kwargs["pack_id"] == "follow_up"
        assert "legal_intake" in call_kwargs["context"]

    def test_start_session_missing_fields(self, tmp_path):
        """start_session with missing fields logs error, doesn't crash."""
        watcher = self._make_watcher(tmp_path)
        rule = {"name": "bad_seed", "action": "start_session"}
        watcher.fire_rule(rule, LEGAL_RECORD)

    def test_fire_rule_dispatches_new_actions(self, tmp_path):
        """fire_rule correctly dispatches to new action types without errors."""
        from unittest.mock import patch, MagicMock

        watcher = self._make_watcher(tmp_path)

        # Verify unknown actions don't crash
        rule = {"name": "unknown", "action": "teleport"}
        watcher.fire_rule(rule, LEGAL_RECORD)  # should log warning, not crash
