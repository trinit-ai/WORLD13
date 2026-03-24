"""Tests for engine/agent.py."""

import pytest
from engine.agent import Agent, initialize_population
from engine.tvr import TVRCoordinates, LIBERATION_THRESHOLD
from engine.archetypes import ARCHETYPE_CODES


class TestAgentInitialize:
    def test_produces_valid_coordinates(self):
        agent = Agent.initialize(plane=3, name="TestAgent")
        assert 1 <= agent.tvr.plane <= 7
        assert agent.tvr.primary_arch in ARCHETYPE_CODES
        assert agent.tvr.k0 > 0
        assert agent.tvr.lambda_coeff > 0
        assert agent.tvr.incarnation_n >= 0

    def test_random_plane_selection(self):
        planes = set()
        for _ in range(50):
            agent = Agent.initialize()
            planes.add(agent.tvr.plane)
        assert len(planes) >= 3  # Should hit multiple planes


class TestAgentUpdate:
    def test_negative_delta_reduces_k(self):
        agent = Agent.initialize(plane=3, name="Test")
        k_before = agent.k_current
        agent.update_after_session(-0.1)
        assert agent.k_current < k_before

    def test_session_count_increments(self):
        agent = Agent.initialize(plane=3, name="Test")
        agent.update_after_session(-0.05)
        assert agent.sessions_completed == 1
        agent.update_after_session(-0.05)
        assert agent.sessions_completed == 2


class TestCyclePhase:
    def test_acc_phase_high_k(self):
        agent = Agent.initialize(plane=3, name="Test")
        agent.k_current = agent.tvr.k0 * 0.9
        agent.update_cycle_phase()
        assert agent.tvr.cycle_phase == "ACC"

    def test_crs_phase_mid_k(self):
        agent = Agent.initialize(plane=3, name="Test")
        agent.k_current = agent.tvr.k0 * 0.6
        agent.update_cycle_phase()
        assert agent.tvr.cycle_phase == "CRS"


class TestPopulation:
    def test_correct_count(self):
        agents = initialize_population(10)
        assert len(agents) == 10

    def test_diverse_planes(self):
        agents = initialize_population(10)
        planes = {a.tvr.plane for a in agents}
        assert len(planes) >= 5  # At least 5 of 7 planes represented

    def test_unique_names(self):
        agents = initialize_population(10)
        names = [a.name for a in agents]
        assert len(set(names)) == 10


class TestSerialization:
    def test_roundtrip(self):
        agent = Agent.initialize(plane=4, name="Roundtrip")
        d = agent.to_dict()
        restored = Agent.from_dict(d)
        assert restored.name == agent.name
        assert restored.tvr.plane == agent.tvr.plane
        assert restored.tvr.primary_arch == agent.tvr.primary_arch
        assert abs(restored.k_current - agent.k_current) < 0.01
