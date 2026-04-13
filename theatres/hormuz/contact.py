"""
theatres/hormuz/contact.py

Who can reach whom in the Hormuz theatre.

The contact graph is geopolitical — not physical proximity
but diplomatic reach, communication channels, and whether
two people are currently able to speak to each other.

Some contacts are direct (Trump-Netanyahu hotline).
Some are backchannel (Vance-Araghchi through intermediaries).
Some are adversarial (Trump-Khamenei — no direct channel).
Some are neutral (Wang Yi can reach both sides).
"""

import random
from typing import List, Tuple
from .agents import WarAgent


# Direct communication channels — who can reach whom
# Format: (name_a, name_b, weight)
# Higher weight = more likely to encounter this tick
CHANNELS = [
    # US internal
    ("Donald Trump", "JD Vance", 8.0),

    # Israel-US
    ("Donald Trump", "Benjamin Netanyahu", 7.0),
    ("JD Vance", "Benjamin Netanyahu", 4.0),

    # Iran internal
    ("Mojtaba Khamenei", "IRGC Commander", 9.0),
    ("Mojtaba Khamenei", "Abbas Araghchi", 7.0),
    ("Mojtaba Khamenei", "Mohammad Bagher Ghalibaf", 6.0),
    ("Abbas Araghchi", "Mohammad Bagher Ghalibaf", 7.0),
    ("IRGC Commander", "Mohammad Bagher Ghalibaf", 4.0),

    # China as intermediary
    ("Wang Yi", "Abbas Araghchi", 5.0),
    ("Wang Yi", "JD Vance", 3.0),
    ("Wang Yi", "Mohammad Bagher Ghalibaf", 4.0),

    # UK-US
    ("Keir Starmer", "Donald Trump", 3.0),
    ("Keir Starmer", "JD Vance", 4.0),

    # Lebanon-Israel talks
    ("Joseph Aoun", "Benjamin Netanyahu", 3.0),

    # Pope — can speak to anyone, reached by no one
    ("Pope Leo XIV", "Joseph Aoun", 4.0),
    ("Pope Leo XIV", "Keir Starmer", 3.0),
    ("Pope Leo XIV", "Wang Yi", 2.0),

    # Backchannel / indirect — lower weight
    ("JD Vance", "Abbas Araghchi", 2.0),      # Islamabad residue
    ("JD Vance", "Wang Yi", 3.0),
    ("Keir Starmer", "Abbas Araghchi", 2.0),
]


def build_channel_map(agents: List[WarAgent]) -> dict:
    """Build a lookup from agent name to agent object."""
    return {a.name: a for a in agents}


def select_encounters(
    agents: List[WarAgent],
    rng: random.Random,
    sessions_per_tick: int = 2,
) -> List[Tuple[WarAgent, WarAgent]]:
    """
    Select who encounters whom this tick.

    Weighted by channel weights — some channels are more
    active than others. As the blockade intensifies, certain
    channels activate more frequently.
    """
    name_map = build_channel_map(agents)
    active_agents = {a.name for a in agents if a.is_active}

    available = [
        (a, b, w) for a, b, w in CHANNELS
        if a in active_agents and b in active_agents
    ]

    if not available:
        return []

    encounters = []
    used = set()

    for _ in range(sessions_per_tick):
        remaining = [(i, available[i]) for i in range(len(available))
                     if available[i][0] not in used and available[i][1] not in used]
        if not remaining:
            break

        r_indices, r_channels = zip(*remaining)
        r_weights = [c[2] for c in r_channels]

        chosen_idx = rng.choices(list(r_indices), weights=r_weights, k=1)[0]
        a_name, b_name, _ = available[chosen_idx]

        agent_a = name_map.get(a_name)
        agent_b = name_map.get(b_name)

        if agent_a and agent_b:
            encounters.append((agent_a, agent_b))
            agent_a.add_contact(agent_b.id)
            agent_b.add_contact(agent_a.id)
            used.add(a_name)
            used.add(b_name)

    return encounters
