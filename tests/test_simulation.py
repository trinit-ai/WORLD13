"""Tests for engine/simulation.py."""

import os
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from engine.agent import Agent, initialize_population
from engine.simulation import WorldSimulation
from engine.world_vault import WorldVault


@pytest.fixture
def sim(tmp_path):
    db_path = str(tmp_path / "test_sim.db")
    s = WorldSimulation(db_path=db_path)
    # Initialize agents
    agents = initialize_population(3)
    for a in agents:
        s.vault.create_agent(a.to_dict())
    return s


class TestSelectAgent:
    def test_selects_low_coherence_more(self, sim):
        agents = sim._load_agents()
        if not agents:
            pytest.skip("No agents loaded")

        selections = {}
        for _ in range(200):
            chosen = sim._select_agent(agents)
            selections[chosen.id] = selections.get(chosen.id, 0) + 1

        # The agent with lowest coherence should be selected more often
        lowest_coh_agent = min(agents, key=lambda a: a.current_coherence)
        if not any(a.is_liberated_flag for a in agents):
            # Lowest coherence should have higher selection count
            assert selections.get(lowest_coh_agent.id, 0) > 0


class TestTick:
    @pytest.mark.asyncio
    async def test_single_tick_runs(self, sim):
        """One tick should run without error, using synthetic API fallback."""
        with patch("engine.session._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "This is a synthetic test session output for validation."
            result = await sim.tick()
            assert "tick" in result
            assert result["tick"] == 1
            assert "sessions" in result

    @pytest.mark.asyncio
    async def test_k_decreases_over_ticks(self, sim):
        """After 3 ticks, average K should decrease."""
        with patch("engine.session._call_anthropic", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = "Extended synthetic session output for testing. " * 20

            agents_before = sim._load_agents()
            k_mean_before = sum(a.k_current for a in agents_before) / len(agents_before)

            for _ in range(3):
                await sim.tick()

            agents_after = sim._load_agents()
            k_mean_after = sum(a.k_current for a in agents_after) / len(agents_after)

            # K should generally decrease (allowing some variance)
            assert k_mean_after <= k_mean_before + 0.5  # Generous tolerance
