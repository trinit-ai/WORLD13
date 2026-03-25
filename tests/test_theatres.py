"""Tests for the theatre system."""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theatres.loader import load_theatre, TheatreManifest, TheatreAgent


def test_load_enlightened_duck():
    manifest = load_theatre("enlightened_duck")
    assert manifest.name == "enlightened_duck"
    assert len(manifest.agents) == 10
    assert manifest.pack == "enlightened_duck"


def test_agent_tvr_coordinates_valid():
    manifest = load_theatre("enlightened_duck")
    for agent in manifest.agents:
        assert 1 <= agent.plane <= 7
        assert 0 < agent.k0 <= 10
        assert 0 < agent.lambda_coeff <= 10
        assert agent.cycle_phase in ("ING", "ACC", "CRS", "RES", "TRN", "LIB")
        assert agent.primary_arch in (
            "SOV", "BLD", "SKR", "WIT", "WAR", "HLR", "TRN",
            "TRK", "LVR", "TCH", "JDG", "MYS", "WLD",
        )


def test_backstories_present():
    manifest = load_theatre("enlightened_duck")
    for agent in manifest.agents:
        assert agent.backstory and len(agent.backstory) > 20


def test_runner_initializes():
    from theatres.runner import TheatreRunner
    runner = TheatreRunner("enlightened_duck")
    assert runner.manifest is not None
    assert runner.vault is not None


def test_manifest_fields():
    manifest = load_theatre("enlightened_duck")
    assert manifest.sessions_per_agent == 1
    assert manifest.max_tokens == 1000
    assert manifest.generate_report is True
    assert manifest.track_divergence is True
    assert "liberation_path_alignment" in manifest.analysis


def test_fixed_axes_present():
    manifest = load_theatre("enlightened_duck")
    assert len(manifest.fixed_axes) > 0


def test_agent_names_unique():
    manifest = load_theatre("enlightened_duck")
    names = [a.name for a in manifest.agents]
    assert len(set(names)) == len(names)
