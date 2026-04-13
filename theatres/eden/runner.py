"""
theatres/eden/runner.py

The Eden simulation loop.

Runs until:
- Max ticks reached
- Population reaches zero (extinction)
- A liberation event occurs (K(x) < 0.05 and coherence > 0.95)
  for a founding agent — rare, significant

No victory condition. No defeat condition.
The simulation runs and the chronicle accumulates.
"""

import asyncio
import random
import os
from typing import List

from .agents import initialize_founders, EdenAgent, NAMES
from .contact import select_encounters, check_births
from .session import run_session
from .chronicle import EdenChronicle

MAX_TICKS = int(os.environ.get("EDEN_MAX_TICKS", "100"))
TICK_DELAY = float(os.environ.get("EDEN_TICK_DELAY", "3.0"))
SESSIONS_PER_TICK = int(os.environ.get("EDEN_SESSIONS_PER_TICK", "2"))


class EdenRunner:
    def __init__(self):
        self.rng = random.Random()
        self.agents: List[EdenAgent] = []
        self.tick = 0
        self.chronicle = EdenChronicle()
        self.used_names: set = set()
        self.name_pool = NAMES.copy()
        self.total_sessions = 0
        self.total_births = 0
        self.liberations = []

    async def run(self) -> dict:
        """Initialize and run the simulation."""
        self.agents = initialize_founders(self.rng)
        for a in self.agents:
            self.used_names.add(a.name)

        print(f"Adam: K:{self.agents[0].k_current:.2f}  λ:{self.agents[0].lambda_coeff:.2f}")
        print(f"Eve:  K:{self.agents[1].k_current:.2f}  λ:{self.agents[1].lambda_coeff:.2f}")
        print()

        for tick in range(1, MAX_TICKS + 1):
            self.tick = tick
            tick_sessions = []
            tick_births = []

            living = [a for a in self.agents if a.is_alive]
            if not living:
                print("\nExtinction. The world ends.")
                break

            encounters = select_encounters(living, self.rng)

            for i, (agent_a, agent_b) in enumerate(encounters):
                if i >= SESSIONS_PER_TICK:
                    break

                result = await run_session(
                    agent_a, agent_b, self.agents, tick, self.rng
                )
                tick_sessions.append(result)
                self.total_sessions += 1

                if agent_a.generation == 0 and agent_a.k_current < 0.05:
                    self.liberations.append({
                        "name": agent_a.name,
                        "tick": tick,
                        "sessions": agent_a.sessions_completed,
                    })

                await asyncio.sleep(0.5)

            tick_births = check_births(
                self.agents, tick,
                self.name_pool, self.used_names, self.rng,
            )
            for child in tick_births:
                self.agents.append(child)
                self.total_births += 1

            self.chronicle.write_tick(tick, tick_sessions, tick_births, self.agents)

            await asyncio.sleep(TICK_DELAY)

        self.chronicle.write_closing(self.tick, self.agents)

        living = [a for a in self.agents if a.is_alive]
        return {
            "ticks": self.tick,
            "total_sessions": self.total_sessions,
            "total_births": self.total_births,
            "population_final": len(living),
            "generations": len(set(a.generation for a in self.agents)),
            "liberations": self.liberations,
            "chronicle_path": self.chronicle.filepath,
        }
