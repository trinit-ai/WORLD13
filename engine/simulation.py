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
from .session import run_session, run_shadow_session, run_world_session
from .tvr import karmic_inertia, coherence
from .mode import is_shadow, is_world, get_mode

TICK_INTERVAL_SECONDS = float(os.environ.get("WORLD13_TICK_SECONDS", "30"))
SESSIONS_PER_TICK = int(os.environ.get("WORLD13_SESSIONS_PER_TICK", "3"))


class WorldSimulation:
    def __init__(self, db_path: str = "data/world13.db"):
        self.vault = WorldVault(db_path)
        self.tick_count = 0
        self.running = False
        self.total_sessions = 0
        self.total_liberations = 0
        self.shadow_mode = is_shadow()
        self.total_contagion_events = 0
        self.total_crystallizations = 0
        self.total_intervention_windows = 0
        self.world_mode = is_world()
        self.total_births = 0
        self._rng = random.Random()
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
                if self.world_mode:
                    result = await run_world_session(agent, self.vault)
                elif self.shadow_mode:
                    result = await run_shadow_session(agent, self.vault, agents, self.tick_count)
                else:
                    result = await run_session(agent, self.vault)
                session_results.append(result)
                self.total_sessions += 1
                if result.get("is_liberated"):
                    self.total_liberations += 1
                # Shadow metrics
                if result.get("contagion_events"):
                    self.total_contagion_events += len(result["contagion_events"])
                if result.get("crystallization_triggered"):
                    self.total_crystallizations += 1
                if result.get("intervention_window"):
                    self.total_intervention_windows += 1
            except Exception as e:
                session_results.append({
                    "agent_name": agent.name,
                    "error": str(e),
                })

        # Reload agents (they've been updated in DB by sessions)
        agents = self._load_agents()
        agent_dicts = [a.to_dict() for a in agents]
        self.vault.write_world_state(self.tick_count, agent_dicts, sessions_this_tick=len(session_results))

        # World mode generational renewal
        renewal_events = []
        if self.world_mode:
            agents = self._load_agents()
            renewal_events = self._run_world_renewal(agents)

        return {
            "tick": self.tick_count,
            "sessions": session_results,
            "total_sessions": self.total_sessions,
            "total_liberations": self.total_liberations,
            "agent_count": len(agents),
            "renewal_events": renewal_events,
        }

    async def run(self) -> None:
        """Main simulation loop. Runs until shutdown signal."""
        self.running = True
        if self.world_mode:
            from .world_renewal import RENEWAL_FLOOR, RENEWAL_COUNT
            print(f"WORLD13 — World Mode. The world runs.")
            print(f"  Tick interval: {TICK_INTERVAL_SECONDS}s, Sessions/tick: {SESSIONS_PER_TICK}")
            print(f"  Renewal: population below {RENEWAL_FLOOR} → birth {RENEWAL_COUNT} agents")
            print()
        else:
            mode_label = "SHADOW" if self.shadow_mode else "PURE"
            print(f"WORLD13 simulation starting. Mode: {mode_label}. Tick interval: {TICK_INTERVAL_SECONDS}s, Sessions/tick: {SESSIONS_PER_TICK}")
            if self.shadow_mode:
                print("  Shadow mode active: dark archetypes, K(x) contagion, crystallization enabled")
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
        if self.world_mode:
            renewal_events = tick_result.pop("renewal_events", [])
            self._log_world_tick(tick_result, renewal_events)
            return
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
                shadow_tag = ""
                if s.get("is_shadow_session"):
                    sd = s.get("shadow_domain", "?")[:12]
                    if s.get("resolution_session"):
                        shadow_tag = f" ◈ RES:{sd}"
                    else:
                        shadow_tag = f" ◆ {sd}"
                    if s.get("crystallization_triggered"):
                        shadow_tag += " ✦CRYST"
                    if s.get("intervention_window"):
                        shadow_tag += " ⚡WINDOW"
                print(f"  {name:12s} P{plane}/{phase:3s} · {proto:25s} · K:{k_b:.2f}→{k_a:.2f} Δ:{delta:+.3f} · C:{coh:.2f}{lib}{shadow_tag}")

        total = tick_result.get("total_sessions", 0)
        libs = tick_result.get("total_liberations", 0)
        print(f"  ── Total sessions: {total} | Liberations: {libs}")
        if self.shadow_mode:
            contagion = sum(len(s.get("contagion_events", [])) for s in sessions if not s.get("error"))
            cryst = sum(1 for s in sessions if s.get("crystallization_triggered"))
            windows = sum(1 for s in sessions if s.get("intervention_window"))
            shadow_count = sum(1 for s in sessions if s.get("is_shadow_session"))
            print(f"  ── Shadow: {shadow_count} sessions | Contagion: {contagion} | Crystallized: {cryst} | Windows: {windows}")
        print()

    def _run_world_renewal(self, agents: list) -> list:
        """World mode: birth new agents when population drops below floor."""
        from .world_renewal import (should_renew, birth_agent, format_birth_event,
                                     RENEWAL_COUNT, RENEWAL_CEILING)
        events = []
        active = [a for a in agents if not a.is_liberated_flag]

        if should_renew(len(active)) and len(agents) < RENEWAL_CEILING:
            exited = [a for a in agents if a.is_liberated_flag]
            predecessor = exited[-1] if exited else None
            for _ in range(min(RENEWAL_COUNT, RENEWAL_CEILING - len(agents))):
                new_agent = birth_agent(agents, predecessor, self._rng)
                self.vault.create_agent(new_agent.to_dict())
                agents.append(new_agent)
                self.total_births += 1
                events.append(("birth", new_agent, predecessor))
                predecessor = None
        return events

    def _log_world_tick(self, tick_result: dict, renewal_events: list) -> None:
        """Chronicle log — not data, events."""
        tick = tick_result["tick"]
        sessions = tick_result.get("sessions", [])

        print(f"═══ TICK {tick} ══════════════════════════════════════════")

        for s in sessions:
            if "error" in s:
                continue
            name = s["agent_name"]
            event = s.get("protocol_name", "a moment")
            k_after = s["k_after"]
            delta = s["k_delta"]
            excerpt = s.get("session_excerpt", "")

            if s.get("is_liberated"):
                print(f"\n  ★ {name} — something completes.")
                if excerpt:
                    first = excerpt.split(".")[0].strip()
                    if first:
                        print(f"    \"{first}.\"")
                print()
            else:
                print(f"\n  {name} — {event}  (K:{k_after:.2f}  Δ:{delta:+.3f})")
                if excerpt and len(excerpt) > 50:
                    first = excerpt.split(".")[0].strip()
                    if len(first) > 120:
                        first = first[:120] + "..."
                    if first:
                        print(f"    {first}.")

        for event_type, agent, predecessor in renewal_events:
            if event_type == "birth":
                from .world_renewal import format_birth_event
                print(f"\n{format_birth_event(agent, predecessor)}")

        print()
        agents = self._load_agents()
        active = [a for a in agents if not a.is_liberated_flag]
        completed = [a for a in agents if a.is_liberated_flag]
        if active:
            mean_k = sum(a.k_current for a in active) / len(active)
            print(f"  ── {len(active)} living · {len(completed)} completed · "
                  f"mean K:{mean_k:.2f} · session {self.total_sessions}")
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
