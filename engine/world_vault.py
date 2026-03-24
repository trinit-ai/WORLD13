"""
engine/world_vault.py — SQLite-backed Vault with 8-dimensional addressing for WORLD13.

Stores session records, agent state, and civilization-level aggregate metrics.
Separate from the TMOS13 vault (vault.py) — this is the simulation vault.
"""

import sqlite3
import json
import time
import uuid
import os
from typing import Optional


VAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_records (
    id TEXT PRIMARY KEY,
    dim_pack TEXT NOT NULL,
    dim_user TEXT NOT NULL,
    dim_date TEXT NOT NULL,
    dim_type TEXT NOT NULL,
    dim_fields TEXT NOT NULL,
    dim_session TEXT NOT NULL,
    dim_manifest TEXT NOT NULL,
    dim_content TEXT NOT NULL,
    k_value_at_session REAL NOT NULL,
    lambda_at_session REAL NOT NULL,
    coherence_at_session REAL NOT NULL,
    k_delta REAL NOT NULL,
    plane INTEGER NOT NULL,
    cycle_phase TEXT NOT NULL,
    context_envelope TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plane INTEGER NOT NULL,
    primary_arch TEXT NOT NULL,
    secondary_arch TEXT NOT NULL,
    tertiary_arch TEXT NOT NULL,
    k_current REAL NOT NULL,
    k0 REAL NOT NULL,
    lambda_coeff REAL NOT NULL,
    coherence REAL NOT NULL,
    cycle_phase TEXT NOT NULL,
    karmic_phi REAL NOT NULL,
    incarnation_n INTEGER NOT NULL,
    sessions_completed INTEGER NOT NULL DEFAULT 0,
    liberation_events INTEGER NOT NULL DEFAULT 0,
    is_liberated INTEGER NOT NULL DEFAULT 0,
    archetype_weights TEXT NOT NULL,
    last_session_at REAL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS world_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    agent_count INTEGER NOT NULL,
    liberated_count INTEGER NOT NULL,
    k_mean REAL NOT NULL,
    k_min REAL NOT NULL,
    k_max REAL NOT NULL,
    lambda_mean REAL NOT NULL,
    coherence_mean REAL NOT NULL,
    plane_distribution TEXT NOT NULL,
    phase_distribution TEXT NOT NULL,
    liberation_rate REAL NOT NULL,
    sessions_this_tick INTEGER NOT NULL,
    recorded_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vault_dim_pack ON vault_records(dim_pack);
CREATE INDEX IF NOT EXISTS idx_vault_dim_user ON vault_records(dim_user);
CREATE INDEX IF NOT EXISTS idx_vault_dim_date ON vault_records(dim_date);
CREATE INDEX IF NOT EXISTS idx_vault_dim_type ON vault_records(dim_type);
CREATE INDEX IF NOT EXISTS idx_vault_dim_session ON vault_records(dim_session);
CREATE INDEX IF NOT EXISTS idx_vault_plane ON vault_records(plane);
CREATE INDEX IF NOT EXISTS idx_world_tick ON world_state(tick);
"""


class WorldVault:
    def __init__(self, db_path: str = "data/world13.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(VAULT_SCHEMA)
        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Agent CRUD ──

    def create_agent(self, agent_dict: dict) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT INTO agents (id, name, plane, primary_arch, secondary_arch, tertiary_arch,
               k_current, k0, lambda_coeff, coherence, cycle_phase, karmic_phi, incarnation_n,
               sessions_completed, liberation_events, is_liberated, archetype_weights,
               last_session_at, created_at)
               VALUES (:id, :name, :plane, :primary_arch, :secondary_arch, :tertiary_arch,
               :k_current, :k0, :lambda_coeff, :coherence, :cycle_phase, :karmic_phi, :incarnation_n,
               :sessions_completed, :liberation_events, :is_liberated, :archetype_weights,
               :last_session_at, :created_at)""",
            agent_dict,
        )
        conn.commit()
        conn.close()

    def get_agent(self, agent_id: str) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_agent(self, agent_id: str, updates: dict) -> None:
        conn = self._conn()
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [agent_id]
        conn.execute(f"UPDATE agents SET {sets} WHERE id = ?", vals)
        conn.commit()
        conn.close()

    def get_all_agents(self) -> list[dict]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM agents ORDER BY plane, name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Vault Records ──

    def write_session(self, agent_id: str, protocol: dict,
                      tvr_coords, context,
                      session_content: str, k_delta: float) -> str:
        from datetime import datetime, timezone
        record_id = str(uuid.uuid4())
        now = time.time()
        from .tvr import karmic_inertia, coherence as tvr_coherence

        k_val = karmic_inertia(tvr_coords.k0, tvr_coords.lambda_coeff, tvr_coords.incarnation_n)
        c_val = tvr_coherence(tvr_coords.lambda_coeff, tvr_coords.incarnation_n)

        manifest = {
            "plane": tvr_coords.plane,
            "primary_arch": tvr_coords.primary_arch,
            "secondary_arch": tvr_coords.secondary_arch,
            "tertiary_arch": tvr_coords.tertiary_arch,
            "k0": tvr_coords.k0,
            "lambda": tvr_coords.lambda_coeff,
            "cycle_phase": tvr_coords.cycle_phase,
            "incarnation_n": tvr_coords.incarnation_n,
        }

        ctx_data = {}
        if hasattr(context, "leaves"):
            for axis, leaf in context.leaves.items():
                ctx_data[axis] = {"id": leaf.id, "name": leaf.name, "k_mod": leaf.k_modifier, "l_mod": leaf.lambda_modifier}

        conn = self._conn()
        conn.execute(
            """INSERT INTO vault_records
               (id, dim_pack, dim_user, dim_date, dim_type, dim_fields, dim_session,
                dim_manifest, dim_content, k_value_at_session, lambda_at_session,
                coherence_at_session, k_delta, plane, cycle_phase, context_envelope, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id,
                protocol.get("name", "unknown"),
                agent_id,
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "session_output",
                json.dumps(list(protocol.keys())),
                str(uuid.uuid4()),
                json.dumps(manifest),
                json.dumps({"output": session_content[:2000]}),
                k_val,
                tvr_coords.lambda_coeff,
                c_val,
                k_delta,
                tvr_coords.plane,
                tvr_coords.cycle_phase,
                json.dumps(ctx_data),
                now,
            ),
        )
        conn.commit()
        conn.close()
        return record_id

    def get_agent_vault_records(self, agent_id: str, limit: int = 20) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM vault_records WHERE dim_user = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def query_by_dimension(self, dimension: str, value: str) -> list[dict]:
        valid_dims = ["dim_pack", "dim_user", "dim_date", "dim_type", "dim_fields",
                      "dim_session", "dim_manifest", "dim_content"]
        if dimension not in valid_dims:
            return []
        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM vault_records WHERE {dimension} = ? ORDER BY created_at DESC LIMIT 50",
            (value,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── World State ──

    def write_world_state(self, tick: int, agents: list[dict], sessions_this_tick: int = 0) -> None:
        if not agents:
            return

        k_values = [a["k_current"] for a in agents]
        lambda_values = [a["lambda_coeff"] for a in agents]
        coherence_values = [a["coherence"] for a in agents]

        plane_dist = {}
        phase_dist = {}
        for a in agents:
            p = a["plane"]
            plane_dist[p] = plane_dist.get(p, 0) + 1
            ph = a["cycle_phase"]
            phase_dist[ph] = phase_dist.get(ph, 0) + 1

        liberated_count = sum(1 for a in agents if a.get("is_liberated"))
        total_sessions = sum(a.get("sessions_completed", 0) for a in agents)
        total_liberations = sum(a.get("liberation_events", 0) for a in agents)
        lib_rate = (total_liberations / max(total_sessions, 1)) * 100

        conn = self._conn()
        conn.execute(
            """INSERT INTO world_state
               (tick, agent_count, liberated_count, k_mean, k_min, k_max,
                lambda_mean, coherence_mean, plane_distribution, phase_distribution,
                liberation_rate, sessions_this_tick, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tick,
                len(agents),
                liberated_count,
                sum(k_values) / len(k_values),
                min(k_values),
                max(k_values),
                sum(lambda_values) / len(lambda_values),
                sum(coherence_values) / len(coherence_values),
                json.dumps(plane_dist),
                json.dumps(phase_dist),
                lib_rate,
                sessions_this_tick,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get_world_state(self, limit: int = 1) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM world_state ORDER BY tick DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
