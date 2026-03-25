#!/usr/bin/env python3
"""
scripts/init_shadow_world.py — Bootstrap the WORLD13 shadow simulation.

Creates DB, initializes mixed population: 70% pure, 30% pre-seeded shadow agents.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.agent import Agent, initialize_population
from engine.world_vault import WorldVault


# Shadow agent pre-seeds: (plane, primary_arch, shadow_arch, name)
SHADOW_SEEDS = [
    (2, "LVR", "PRD", "Narcissa"),     # Predator — relational plane
    (3, "SOV", "IDL", "Torquemada"),    # Ideologue — formal/institutional
    (5, "TRK", "ADC", "Tantalus"),      # Addict — creative plane
    (6, "WIT", "DSS", "Legion"),        # Dissociator — self/reflective
    (3, "WAR", "CVL", "Ares"),          # Collective Violence — formal
    (4, "SOV", "CRP", "Achan"),         # Corruptor — professional/institutional
]


def main():
    db_path = os.environ.get("WORLD13_DB_PATH", "data/world13.db")

    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")

    vault = WorldVault(db_path)

    # Pure agents (first 7 — one per plane, + 3 random)
    pure_agents = initialize_population(10)

    # Shadow agents (6 pre-seeded)
    shadow_agents = []
    for plane, arch, shadow_arch, name in SHADOW_SEEDS:
        agent = Agent.initialize(plane=plane, primary_arch=arch, name=name)
        # Increase K for shadow agents to make shadow accessible
        agent.k_current = agent.tvr.k0 * 1.2
        shadow_agents.append((agent, shadow_arch))

    # Write all agents
    for agent in pure_agents:
        vault.create_agent(agent.to_dict())

    for agent, shadow_arch in shadow_agents:
        vault.create_agent(agent.to_dict())
        vault.update_shadow_state(agent.id, {
            "shadow_arch": shadow_arch,
            "shadow_entry_tick": 0,
        })

    # Write initial world state
    all_agents = pure_agents + [a for a, _ in shadow_agents]
    agent_dicts = [a.to_dict() for a in all_agents]
    vault.write_world_state(tick=0, agents=agent_dicts, sessions_this_tick=0)

    print()
    print("WORLD13 SHADOW initialized.")
    print(f"Database: {db_path}")
    print()
    print("PURE AGENTS (10):")
    print(f"  {'Name':12s}  {'Plane':5s}  {'Arch':4s}  {'K₀':>6s}  {'λ':>5s}  {'Phase':5s}")
    print("  " + "─" * 45)
    for a in pure_agents:
        print(
            f"  {a.name:12s}  P{a.tvr.plane:<4d}  {a.tvr.primary_arch:4s}"
            f"  {a.tvr.k0:5.2f}  {a.tvr.lambda_coeff:5.2f}  {a.tvr.cycle_phase:5s}"
        )

    print()
    print("SHADOW AGENTS (6):")
    print(f"  {'Name':12s}  {'Plane':5s}  {'Arch':4s}  {'Shadow':4s}  {'K':>6s}  {'λ':>5s}")
    print("  " + "─" * 50)
    for agent, shadow_arch in shadow_agents:
        print(
            f"  {agent.name:12s}  P{agent.tvr.plane:<4d}  {agent.tvr.primary_arch:4s}"
            f"  {shadow_arch:4s}    {agent.k_current:5.2f}  {agent.tvr.lambda_coeff:5.2f}"
        )

    print()
    print(f"Total agents: {len(all_agents)} ({len(pure_agents)} pure + {len(shadow_agents)} shadow)")
    print()
    print("Run 'make shadow-sim' to start the shadow simulation.")


if __name__ == "__main__":
    main()
