"""Tests for engine/world_vault.py."""

import os
import pytest
import tempfile
from engine.world_vault import WorldVault
from engine.tvr import TVRCoordinates
from engine.context import ContextualEnvelope, LeafNode


@pytest.fixture
def vault(tmp_path):
    db_path = str(tmp_path / "test_world13.db")
    return WorldVault(db_path)


@pytest.fixture
def sample_agent():
    return {
        "id": "test-agent-001",
        "name": "TestAriel",
        "plane": 2,
        "primary_arch": "LVR",
        "secondary_arch": "HLR",
        "tertiary_arch": "WIT",
        "k_current": 4.5,
        "k0": 5.0,
        "lambda_coeff": 3.1,
        "coherence": 0.35,
        "cycle_phase": "ACC",
        "karmic_phi": 1.234,
        "incarnation_n": 3,
        "sessions_completed": 0,
        "liberation_events": 0,
        "is_liberated": 0,
        "archetype_weights": '{"LVR": 1.0, "HLR": 0.6, "WIT": 0.3}',
        "last_session_at": None,
        "created_at": 1711000000.0,
    }


class TestVaultInit:
    def test_creates_tables(self, vault):
        conn = vault._conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "agents" in table_names
        assert "vault_records" in table_names
        assert "world_state" in table_names
        conn.close()


class TestAgentCRUD:
    def test_create_and_get(self, vault, sample_agent):
        vault.create_agent(sample_agent)
        retrieved = vault.get_agent("test-agent-001")
        assert retrieved is not None
        assert retrieved["name"] == "TestAriel"
        assert retrieved["plane"] == 2

    def test_update(self, vault, sample_agent):
        vault.create_agent(sample_agent)
        vault.update_agent("test-agent-001", {"k_current": 4.2, "sessions_completed": 1})
        updated = vault.get_agent("test-agent-001")
        assert updated["k_current"] == 4.2
        assert updated["sessions_completed"] == 1

    def test_get_all(self, vault, sample_agent):
        vault.create_agent(sample_agent)
        agent2 = {**sample_agent, "id": "test-agent-002", "name": "TestCassiel", "plane": 6}
        vault.create_agent(agent2)
        all_agents = vault.get_all_agents()
        assert len(all_agents) == 2


class TestWorldState:
    def test_write_and_read(self, vault, sample_agent):
        vault.create_agent(sample_agent)
        agents = vault.get_all_agents()
        vault.write_world_state(tick=1, agents=agents, sessions_this_tick=3)
        states = vault.get_world_state(limit=1)
        assert len(states) == 1
        assert states[0]["tick"] == 1
        assert states[0]["agent_count"] == 1
        assert states[0]["k_mean"] == 4.5


class TestVaultRecords:
    def test_query_by_dimension(self, vault, sample_agent):
        vault.create_agent(sample_agent)
        coords = TVRCoordinates(
            plane=2, primary_arch="LVR", secondary_arch="HLR", tertiary_arch="WIT",
            k0=5.0, lambda_coeff=3.1, cycle_phase="ACC", karmic_phi=1.234, incarnation_n=3,
        )
        ctx = ContextualEnvelope(
            agent_id="test-agent-001", sampled_at=1711000000.0,
            leaves={}, k_total_modifier=0.5, lambda_total_modifier=0.3,
        )
        protocol = {"name": "Test Protocol", "domain": "Testing"}
        record_id = vault.write_session(
            agent_id="test-agent-001", protocol=protocol,
            tvr_coords=coords, context=ctx,
            session_content="Test session output content here.",
            k_delta=-0.05,
        )
        assert record_id is not None

        records = vault.get_agent_vault_records("test-agent-001")
        assert len(records) == 1
        assert records[0]["dim_user"] == "test-agent-001"

        by_pack = vault.query_by_dimension("dim_pack", "Test Protocol")
        assert len(by_pack) == 1
