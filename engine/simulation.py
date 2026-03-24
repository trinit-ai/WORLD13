"""
engine/simulation.py — Main simulation loop for WORLD13.

Manages the world clock, agent scheduling, session execution, and logging.
"""

import asyncio
import os
import time
import random
import signal
from typing import Optional

from .agent import Agent, initialize_population
from .world_vault import WorldVault
from .session import run_session
from .tvr import karmic_inertia, coherence

TICK_INTERVAL_SECONDS = float(os.environ.get("WORLD13_TICK_SECONDS", "30"))
SESSIONS_PER_TICK = int(os.environ.get("WORLD13_SESSIONS_PER_TICK", "3"))


class WorldSimulation:
    def __init__(self, db_path: str = "data/world13.db"):
        self.vault = WorldVault(db_path)
        self.tick_count = 0
        self.running = False
        self.total_sessions = 0
        self.total_liberations = 0
        self._shutdown = asyncio.Event()

    def _load_agents(self) -> list[Agent]:
        """Load all agents from the vault DB."""
        agent_dicts = self.vault.get_all_agents()
        return [Agent.from_dict(d) for d in agent_dicts]

    def _select_agent(self, agents: list[Agent]) -> Agent:
        """
        Select next agent to run.
        Priority: lowest coherence agents run more often.
        Weight = 1 / (coherence + 0.1). Skip liberated agents.
        """
        active = [a for a in agents if not a.is_liberated_flag]
        if not active:
            return random.choice(agents)

        weights = [1.0 / (a.current_coherence + 0.1) for a in active]
        return random.choices(active, weights=weights, k=1)[0]

    async def tick(self) -> dict:
        """One world clock tick. Runs SESSIONS_PER_TICK sessions."""
        self.tick_count += 1
        agents = self._load_agents()

        if not agents:
            return {"tick": self.tick_count, "error": "No agents found. Run init_world.py first."}

        session_results = []
        for _ in range(SESSIONS_PER_TICK):
            agent = self._select_agent(agents)
            try:
                result = await run_session(agent, self.vault)
                session_results.append(result)
                self.total_sessions += 1
                if result.get("is_liberated"):
                    self.total_liberations += 1
            except Exception as e:
                session_results.append({
                    "agent_name": agent.name,
                    "error": str(e),
                })

        # Reload agents (they've been updated in DB by sessions)
        agents = self._load_agents()
        agent_dicts = [a.to_dict() for a in agents]
        self.vault.write_world_state(self.tick_count, agent_dicts, sessions_this_tick=len(session_results))

        return {
            "tick": self.tick_count,
            "sessions": session_results,
            "total_sessions": self.total_sessions,
            "total_liberations": self.total_liberations,
            "agent_count": len(agents),
        }

    async def run(self) -> None:
        """Main simulation loop. Runs until shutdown signal."""
        self.running = True
        print(f"WORLD13 simulation starting. Tick interval: {TICK_INTERVAL_SECONDS}s, Sessions/tick: {SESSIONS_PER_TICK}")
        print()

        # Handle graceful shutdown
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._shutdown.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows or nested event loop

        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(TICK_INTERVAL_SECONDS)
                tick_result = await self.tick()
                self._log_tick(tick_result)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Tick {self.tick_count}: {e}")

        print("\nWORLD13 simulation shutting down gracefully.")
        self.running = False

    def _log_tick(self, tick_result: dict) -> None:
        """Print tick summary in a clean format."""
        tick = tick_result["tick"]
        sessions = tick_result.get("sessions", [])

        print(f"═══ TICK {tick} ═══════════════════════════════════════════")
        for s in sessions:
            if "error" in s:
                print(f"  [ERROR] {s.get('agent_name', '?')}: {s['error']}")
            else:
                name = s["agent_name"]
                plane = s["plane"]
                arch = s.get("domain", "?")[:20]
                proto = s.get("protocol_name", "?")[:25]
                k_b = s["k_before"]
                k_a = s["k_after"]
                delta = s["k_delta"]
                coh = s["coherence_after"]
                phase = s["cycle_phase"]
                lib = " ★ LIBERATED" if s.get("is_liberated") else ""
                print(f"  {name:12s} P{plane}/{phase:3s} · {proto:25s} · K:{k_b:.2f}→{k_a:.2f} Δ:{delta:+.3f} · C:{coh:.2f}{lib}")

        total = tick_result.get("total_sessions", 0)
        libs = tick_result.get("total_liberations", 0)
        print(f"  ── Total sessions: {total} | Liberations: {libs}")
        print()

    def get_world_summary(self) -> dict:
        """Return current civilization-level aggregate metrics."""
        states = self.vault.get_world_state(limit=1)
        agents = self.vault.get_all_agents()

        if not states:
            return {"tick": 0, "agents": len(agents), "message": "No ticks recorded yet"}

        state = states[0]
        return {
            "tick": state["tick"],
            "agent_count": state["agent_count"],
            "liberated_count": state["liberated_count"],
            "k_mean": round(state["k_mean"], 4),
            "k_min": round(state["k_min"], 4),
            "k_max": round(state["k_max"], 4),
            "lambda_mean": round(state["lambda_mean"], 4),
            "coherence_mean": round(state["coherence_mean"], 4),
            "plane_distribution": state["plane_distribution"],
            "phase_distribution": state["phase_distribution"],
            "liberation_rate": round(state["liberation_rate"], 4),
            "sessions_this_tick": state["sessions_this_tick"],
            "total_sessions": self.total_sessions,
            "total_liberations": self.total_liberations,
        }
