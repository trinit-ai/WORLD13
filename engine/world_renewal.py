"""
engine/world_renewal.py

Generational renewal for world mode.

When the active population drops below RENEWAL_FLOOR, new agents are
born into the world. Their K(x) is drawn from the population's
accumulated distribution — not random, not clean. They inherit the
world's mean karmic weight with variance. They are born into a world
that has been running, and they carry that world's weight.

Liberated agents exit cleanly. Crystallized agents exit with a
K(x) inheritance note — their pattern seeds the next agent's
starting conditions at a fraction of the crystallized K.
"""

import random
import math
from typing import List, Optional
from .agent import Agent


RENEWAL_FLOOR = 7
RENEWAL_CEILING = 13
RENEWAL_COUNT = 2
CRYSTALLIZATION_K_INHERITANCE = 0.35

WORLD_NAMES = [
    "Ariel", "Cassiel", "Damianos", "Elara", "Fenwick",
    "Griselde", "Havel", "Isolde", "Joran", "Kestrel",
    "Lyric", "Mordecai", "Nessa", "Oberon", "Petra",
    "Quillon", "Reva", "Sable", "Tavish", "Uriel",
    "Vesper", "Wren", "Xanthe", "Yael", "Zephyr",
    "Aldric", "Brenna", "Caspian", "Delia", "Emrys",
    "Fable", "Gareth", "Hesper", "Idris", "Juniper",
    "Kiran", "Lumen", "Maren", "Naveen", "Orla",
    "Pax", "Quillan", "Rowan", "Seren", "Theron",
    "Una", "Valor", "Waverly", "Xander", "Ysabel", "Zuri",
    "Ashby", "Briar", "Coel", "Davan", "Elan",
    "Fenn", "Grove", "Harlan", "Ivor", "Jessamine",
]


def get_available_name(existing_names: List[str]) -> str:
    used = set(existing_names)
    available = [n for n in WORLD_NAMES if n not in used]
    if available:
        return random.choice(available)
    base = random.choice(WORLD_NAMES)
    return f"{base}-II"


def should_renew(active_count: int) -> bool:
    return active_count < RENEWAL_FLOOR


def compute_birth_k0(
    population_k_values: List[float],
    crystallized_k: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> float:
    if rng is None:
        rng = random.Random()

    if crystallized_k is not None:
        inherited = crystallized_k * CRYSTALLIZATION_K_INHERITANCE
        mean_k = sum(population_k_values) / len(population_k_values) if population_k_values else 4.0
        k0 = inherited * 0.6 + mean_k * 0.4 + rng.gauss(0, 0.8)
    elif population_k_values:
        mean_k = sum(population_k_values) / len(population_k_values)
        std_k = (sum((k - mean_k) ** 2 for k in population_k_values) / len(population_k_values)) ** 0.5
        std_k = max(0.5, std_k)
        k0 = rng.gauss(mean_k, std_k * 0.6)
    else:
        k0 = rng.gauss(4.5, 1.5)

    return round(max(1.0, min(9.5, k0)), 2)


def birth_agent(
    existing_agents: List[Agent],
    crystallized_predecessor: Optional[Agent] = None,
    rng: Optional[random.Random] = None,
) -> Agent:
    if rng is None:
        rng = random.Random()

    existing_names = [a.name for a in existing_agents]
    name = get_available_name(existing_names)

    active_k_values = [a.k_current for a in existing_agents if not a.is_liberated_flag]
    crystallized_k = crystallized_predecessor.k_current if crystallized_predecessor else None
    k0 = compute_birth_k0(active_k_values, crystallized_k, rng)

    agent = Agent.initialize(name=name)
    agent.tvr.k0 = k0
    agent.k_current = k0
    return agent


def format_birth_event(agent: Agent, predecessor: Optional[Agent] = None) -> str:
    if predecessor and not predecessor.is_liberated_flag:
        return (f"  ✦ {agent.name} enters the world, carrying something of "
                f"{predecessor.name}'s unfinished pattern.  (K:{agent.k_current:.2f})")
    return f"  ✦ {agent.name} enters the world.  (K:{agent.k_current:.2f})"
