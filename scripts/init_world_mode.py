#!/usr/bin/env python3
"""Seven agents. One per plane. Small enough to follow."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from engine.agent import Agent
from engine.world_vault import WorldVault
from engine.world_renewal import WORLD_NAMES

DB_PATH = "data/world13_world.db"

def init_world():
    print("WORLD13 — seven planes, seven agents.")
    print()

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    vault = WorldVault(DB_PATH)

    for plane in range(1, 8):
        name = WORLD_NAMES[plane - 1]
        agent = Agent.initialize(plane=plane, name=name)
        vault.create_agent(agent.to_dict())
        print(f"  {name:<12s}  Plane {plane}  K:{agent.k_current:.2f}  "
              f"λ:{agent.tvr.lambda_coeff:.2f}  {agent.tvr.cycle_phase}")

    print()
    print("Run:  make world")

if __name__ == "__main__":
    init_world()
