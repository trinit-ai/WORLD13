"""
Tests for IoT channel adapter.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from channel_iot import (
    DEVICE_PACK_MAP,
    _format_sensor_context,
    _truncate_for_device,
    _strip_markdown,
    IOT_MAX_LENGTH,
)


class TestDevicePackMap:

    def test_refrigerator_maps(self):
        assert DEVICE_PACK_MAP["refrigerator"] == "nutrition_intake"

    def test_scale_maps(self):
        assert DEVICE_PACK_MAP["scale"] == "health_checkin"

    def test_generic_falls_back(self):
        assert DEVICE_PACK_MAP["generic"] == "desk"

    def test_unknown_device_not_in_map(self):
        assert "toaster" not in DEVICE_PACK_MAP


class TestSensorContext:

    def test_empty_sensor_data(self):
        assert _format_sensor_context({}) == ""

    def test_single_sensor(self):
        result = _format_sensor_context({"temperature": 37})
        assert "temperature=37" in result

    def test_multiple_sensors(self):
        result = _format_sensor_context({"temp": 37, "humidity": 65})
        assert "temp=37" in result
        assert "humidity=65" in result

    def test_caps_at_three(self):
        data = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
        result = _format_sensor_context(data)
        assert result.count("=") == 3


class TestTruncation:

    def test_short_text_unchanged(self):
        text = "Hello, this is short."
        assert _truncate_for_device(text) == text

    def test_long_text_truncated(self):
        text = "Word. " * 200
        result = _truncate_for_device(text)
        assert len(result) <= IOT_MAX_LENGTH + 3  # +3 for "..."

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. " + "x" * 500
        result = _truncate_for_device(text)
        assert result.endswith(".") or result.endswith("...")


class TestStripMarkdown:

    def test_strips_bold(self):
        assert _strip_markdown("This is **bold** text") == "This is bold text"

    def test_strips_italic(self):
        assert _strip_markdown("This is *italic* text") == "This is italic text"

    def test_strips_headers(self):
        assert _strip_markdown("## Header\nContent") == "Header Content"

    def test_strips_code(self):
        assert _strip_markdown("Run `pip install`") == "Run pip install"

    def test_converts_bullets_to_sentences(self):
        text = "Items:\n- eggs\n- milk\n- bread"
        result = _strip_markdown(text)
        assert "-" not in result
        assert "eggs" in result

    def test_plain_text_unchanged(self):
        text = "Just plain text here."
        assert _strip_markdown(text) == text
