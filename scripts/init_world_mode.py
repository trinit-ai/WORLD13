#!/usr/bin/env python3
"""Initialize the world for world mode. 13 agents, extended name pool."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from engine.agent import Agent
from engine.world_vault import WorldVault
from engine.world_renewal import WORLD_NAMES
import random

DB_PATH = "data/world13_world.db"
POPULATION = 13

def init_world():
    print(f"Initializing WORLD13 world mode — {POPULATION} agents")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    vault = WorldVault(DB_PATH)
    rng = random.Random()
    agents = []

    for plane in range(1, 8):
        agent = Agent.initialize(plane=plane, name=WORLD_NAMES[plane - 1])
        agents.append(agent)

    middle = [3, 3, 4, 4, 4, 5]
    for i in range(6):
        agent = Agent.initialize(plane=rng.choice(middle), name=WORLD_NAMES[7 + i])
        agents.append(agent)

    for agent in agents:
        vault.create_agent(agent.to_dict())
        print(f"  {agent.name:<12s} P{agent.tvr.plane} · {agent.tvr.primary_arch} · "
              f"K:{agent.k_current:.2f} · λ:{agent.tvr.lambda_coeff:.2f}")

    print(f"\nWorld ready. Run:  make world")

if __name__ == "__main__":
    init_world()
