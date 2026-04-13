"""
theatres/hormuz/runner.py

The Hormuz simulation loop.

Runs until max ticks or until escalation pressure either
locks catastrophically (mean K > 9.5) or breaks open (mean K < 3.0).

No victory. No defeat. Just the war's interior, accumulated.
"""

import asyncio
import random
import os

from .agents import initialize_agents
from .contact import select_encounters
from .session import run_session
from .chronicle import HormuzChronicle

MAX_TICKS = int(os.environ.get("HORMUZ_MAX_TICKS", "50"))
TICK_DELAY = float(os.environ.get("HORMUZ_TICK_DELAY", "3.0"))
SESSIONS_PER_TICK = int(os.environ.get("HORMUZ_SESSIONS_PER_TICK", "2"))


class HormuzRunner:
    def __init__(self):
        self.rng = random.Random()
        self.agents = initialize_agents()
        self.tick = 0
        self.chronicle = HormuzChronicle()
        self.total_sessions = 0

    async def run(self) -> dict:
        print(f"  {len(self.agents)} agents  ·  {SESSIONS_PER_TICK} sessions/tick")
        print()

        for agent in self.agents:
            print(f"  {agent.name:<30} K:{agent.k_current:.2f}  λ:{agent.lambda_coeff:.2f}")
        print()

        for tick in range(1, MAX_TICKS + 1):
            self.tick = tick

            encounters = select_encounters(
                self.agents, self.rng, SESSIONS_PER_TICK
            )

            tick_sessions = []
            for agent_a, agent_b in encounters:
                result = await run_session(
                    agent_a, agent_b, self.agents, tick, self.rng
                )
                tick_sessions.append(result)
                self.total_sessions += 1
                await asyncio.sleep(0.5)

            self.chronicle.write_tick(tick, tick_sessions, self.agents)

            # Check terminal conditions
            active = [a for a in self.agents if a.is_active]
            mean_k = sum(a.k_current for a in active) / len(active)

            if mean_k > 9.5:
                print(f"\n  ◆ Catastrophic escalation threshold reached. K:{mean_k:.2f}")
                break
            if mean_k < 3.0:
                print(f"\n  ★ Escalation pressure collapsed. K:{mean_k:.2f}")
                break

            await asyncio.sleep(TICK_DELAY)

        self.chronicle.write_closing(self.tick, self.agents)

        active = [a for a in self.agents if a.is_active]
        mean_k = sum(a.k_current for a in active) / len(active) if active else 0

        return {
            "ticks": self.tick,
            "total_sessions": self.total_sessions,
            "mean_k_final": round(mean_k, 4),
            "agent_states": [a.to_dict() for a in self.agents],
            "chronicle_path": self.chronicle.filepath,
        }
