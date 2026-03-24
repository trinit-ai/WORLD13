#!/usr/bin/env python3
"""
scripts/init_world.py — Bootstrap the WORLD13 simulation.

Creates the SQLite database, initializes 10 agents, writes them to the Vault.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.agent import initialize_population
from engine.world_vault import WorldVault


def main():
    db_path = os.environ.get("WORLD13_DB_PATH", "data/world13.db")

    # Remove existing DB for fresh init
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")

    vault = WorldVault(db_path)
    agents = initialize_population(10)

    for agent in agents:
        vault.create_agent(agent.to_dict())

    # Write initial world state
    agent_dicts = [a.to_dict() for a in agents]
    vault.write_world_state(tick=0, agents=agent_dicts, sessions_this_tick=0)

    print()
    print("WORLD13 initialized.")
    print(f"Database: {db_path}")
    print()
    print("AGENT POPULATION (10 agents):")
    print(f"  {'Name':12s}  {'Plane':5s}  {'Arch':4s}  {'K₀':>6s}  {'λ':>5s}  {'Phase':5s}  {'Coh':>5s}")
    print("  " + "─" * 52)
    for a in agents:
        print(
            f"  {a.name:12s}  P{a.tvr.plane:<4d}  {a.tvr.primary_arch:4s}"
            f"  {a.tvr.k0:5.2f}  {a.tvr.lambda_coeff:5.2f}  {a.tvr.cycle_phase:5s}"
            f"  {a.current_coherence:.3f}"
        )
    print()
    print("World ready. Run 'make sim' to start the simulation.")


if __name__ == "__main__":
    main()
