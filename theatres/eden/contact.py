"""
theatres/eden/contact.py

Contact graph for the Eden theatre.

Who encounters whom each tick.

Rules:
- In the beginning: Adam and Eve always encounter each other.
- As population grows: encounter probability weighted by
  proximity (sustained contact history) and generation.
- Parents always have high encounter probability with children.
- Strangers can encounter each other — this is how
  alliances, conflicts, and new relationships form.
- One encounter per agent per tick (they have limited time).

The contact graph is not spatial. It is relational.
Closeness = accumulated encounter history.
"""

import random
from typing import List, Tuple
from .agents import EdenAgent


def select_encounters(
    agents: List[EdenAgent],
    rng: random.Random,
) -> List[Tuple[EdenAgent, EdenAgent]]:
    """
    Select who encounters whom this tick.

    Returns a list of (agent_a, agent_b) pairs.
    Each living agent participates in at most one encounter per tick.
    Small populations: all agents may encounter someone.
    Large populations: encounter probability weighted by closeness.
    """
    living = [a for a in agents if a.is_alive]
    if len(living) < 2:
        return []

    encounters = []
    paired = set()

    candidates = living.copy()
    rng.shuffle(candidates)

    for agent in candidates:
        if agent.id in paired:
            continue

        possible = [a for a in living if a.id != agent.id and a.id not in paired]
        if not possible:
            continue

        weights = []
        for other in possible:
            sustained = agent.sustained_contact_with(other.id)
            w = 1.0 + sustained * 0.3
            if other.id in (agent.parent_a_id, agent.parent_b_id):
                w += 3.0
            if agent.id in other.children_ids or other.id in agent.children_ids:
                w += 3.0
            if other.id == agent.partner_id:
                w += 5.0
            weights.append(w)

        partner = rng.choices(possible, weights=weights, k=1)[0]
        encounters.append((agent, partner))
        paired.add(agent.id)
        paired.add(partner.id)

        agent.add_contact(partner.id)
        partner.add_contact(agent.id)

        if agent.sustained_contact_with(partner.id) > 12:
            agent.partner_id = partner.id
            partner.partner_id = agent.id

    return encounters


def check_births(
    agents: List[EdenAgent],
    tick: int,
    name_pool: List[str],
    used_names: set,
    rng: random.Random,
    birth_threshold: int = 8,
    birth_k_threshold: float = 7.0,
    birth_probability: float = 0.25,
) -> List[EdenAgent]:
    """
    Check all sustained contact pairs for birth eligibility.

    Birth conditions:
    - Two agents of different planes (proxy for reproductive pairing)
    - Sustained contact above threshold
    - Both K(x) below birth threshold
    - Random probability gate
    """
    from .agents import birth_agent

    living = [a for a in agents if a.is_alive]
    newborns = []
    birth_pairs = set()

    for agent in living:
        for other_id, contact_count in agent.contact_counts.items():
            pair_key = tuple(sorted([agent.id, other_id]))
            if pair_key in birth_pairs:
                continue

            other = next((a for a in living if a.id == other_id), None)
            if not other:
                continue

            if contact_count < birth_threshold:
                continue
            if agent.k_current >= birth_k_threshold:
                continue
            if other.k_current >= birth_k_threshold:
                continue
            if agent.plane == other.plane:
                continue
            if rng.random() > birth_probability:
                continue

            available = [n for n in name_pool if n not in used_names]
            if not available:
                name = f"Child-{tick}-{len(newborns)}"
            else:
                name = available[0]
            used_names.add(name)

            gen = max(agent.generation, other.generation) + 1

            child = birth_agent(agent, other, gen, name, tick, rng)
            agent.children_ids.append(child.id)
            other.children_ids.append(child.id)
            newborns.append(child)
            birth_pairs.add(pair_key)

    return newborns
