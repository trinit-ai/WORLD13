"""
theatres/eden/agents.py

Agents for the Eden theatre.

The first two agents are initialized by name.
Every subsequent agent is born from two parents.
No archetypes. No preset roles. Just variance.

TVR coordinates:
- K(x): starts high — they came from something they lost
- λ: moderate — awareness without coherence
- Plane: different for each founding agent
- All other coordinates: random within range

Birth mechanic:
- When two agents have been in sustained contact for BIRTH_THRESHOLD ticks
  and both have K(x) < BIRTH_K_THRESHOLD, a child is born
- Child K(x): weighted average of parents + small random variance
- Child λ: average of parents + small random variance
- Child name: drawn from the name pool, not previously used
- Child plane: randomly selected between parents' planes
"""

import uuid
import random
import math
import time
from dataclasses import dataclass, field
from typing import Optional, List


BIRTH_THRESHOLD = 8          # Ticks of sustained contact before birth possible
BIRTH_K_THRESHOLD = 7.0      # Both parents must be below this K(x)
BIRTH_PROBABILITY = 0.25     # Probability per eligible tick

# Name pool — drawn in order, then variants
NAMES = [
    # The founders
    "Adam", "Eve",
    # First generation
    "Cain", "Abel", "Seth", "Awan", "Azura",
    # Expansion
    "Enoch", "Irad", "Mehujael", "Methushael", "Lamech",
    "Adah", "Zillah", "Jabal", "Jubal", "Tubal",
    "Naamah", "Kenan", "Mahalalel", "Jared", "Methuselah",
    "Lamech-II", "Noah", "Shem", "Ham", "Japheth",
    "Miriam", "Deborah", "Tamar", "Leah", "Rachel",
    "Caleb", "Joshua", "Gideon", "Samson", "Ruth",
    "Boaz", "Jesse", "David", "Solomon", "Elijah",
    "Elisha", "Isaiah", "Jeremiah", "Ezekiel", "Daniel",
    "Esther", "Mordecai", "Ezra", "Nehemiah", "Malachi",
]


@dataclass
class EdenAgent:
    """A person in the Eden simulation."""
    id: str
    name: str
    generation: int              # 0 = founding, 1 = first born, etc.

    # TVR coordinates
    plane: int                   # 1-7
    k_current: float             # Accumulated unresolved weight
    k0: float                    # Starting K(x)
    lambda_coeff: float          # Self-awareness / repair capacity
    incarnation_n: int = 0

    # Relational state
    parent_a_id: Optional[str] = None
    parent_b_id: Optional[str] = None
    partner_id: Optional[str] = None      # Primary sustained contact
    contact_counts: dict = field(default_factory=dict)  # {agent_id: tick_count}
    children_ids: List[str] = field(default_factory=list)

    # Lifecycle
    is_alive: bool = True
    birth_tick: int = 0
    death_tick: Optional[int] = None
    sessions_completed: int = 0

    # What the agent carries — accumulated from sessions
    memory_fragment: str = ""    # Last meaningful thing that happened to them

    @property
    def current_coherence(self) -> float:
        return 1.0 - math.exp(-self.lambda_coeff * max(self.incarnation_n, 1))

    @property
    def age_in_ticks(self) -> int:
        return self.incarnation_n

    @property
    def is_elder(self) -> bool:
        return self.incarnation_n > 40

    def update_after_session(self, k_delta: float, memory: str = "") -> None:
        self.sessions_completed += 1
        self.incarnation_n += 1
        self.k_current = max(0.0, self.k_current + k_delta)
        if memory:
            self.memory_fragment = memory

    def add_contact(self, other_id: str) -> None:
        self.contact_counts[other_id] = self.contact_counts.get(other_id, 0) + 1

    def sustained_contact_with(self, other_id: str) -> int:
        return self.contact_counts.get(other_id, 0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "generation": self.generation,
            "plane": self.plane,
            "k_current": round(self.k_current, 4),
            "k0": self.k0,
            "lambda_coeff": round(self.lambda_coeff, 4),
            "incarnation_n": self.incarnation_n,
            "parent_a_id": self.parent_a_id,
            "parent_b_id": self.parent_b_id,
            "children_ids": self.children_ids,
            "is_alive": self.is_alive,
            "birth_tick": self.birth_tick,
            "sessions_completed": self.sessions_completed,
            "memory_fragment": self.memory_fragment[:200],
        }


def initialize_founders(rng: random.Random) -> List[EdenAgent]:
    """
    Initialize Adam and Eve.

    Adam: Plane 1 (physical/material) — the hands, the ground, the immediate.
    Eve: Plane 2 (relational/emotional) — other people as the mirror of self.

    Both start with high K(x) — they came from something they lost.
    λ moderate — awareness arrived all at once, coherence not yet built.
    """
    adam = EdenAgent(
        id=str(uuid.uuid4()),
        name="Adam",
        generation=0,
        plane=1,
        k_current=rng.uniform(6.5, 7.5),
        k0=rng.uniform(6.5, 7.5),
        lambda_coeff=rng.uniform(2.8, 3.4),
        birth_tick=0,
        memory_fragment="The garden is gone. The ground is hard. She is here."
    )
    adam.k0 = adam.k_current

    eve = EdenAgent(
        id=str(uuid.uuid4()),
        name="Eve",
        generation=0,
        plane=2,
        k_current=rng.uniform(6.8, 7.8),
        k0=rng.uniform(6.8, 7.8),
        lambda_coeff=rng.uniform(3.1, 3.8),
        birth_tick=0,
        memory_fragment="We knew things differently before. The knowing changed everything."
    )
    eve.k0 = eve.k_current

    return [adam, eve]


def birth_agent(
    parent_a: EdenAgent,
    parent_b: EdenAgent,
    generation: int,
    name: str,
    birth_tick: int,
    rng: random.Random,
) -> EdenAgent:
    """
    Birth a new agent from two parents.

    K(x): weighted average of parents with variance
          — children inherit the world's weight
    λ: average of parents with small variance
       — self-awareness is partially inherited
    Plane: randomly selected between parents' planes
           with small chance of adjacent plane
    """
    # K(x) inheritance
    mean_k = (parent_a.k_current * 0.5 + parent_b.k_current * 0.5)
    child_k = max(1.5, mean_k * rng.uniform(0.7, 0.95) + rng.gauss(0, 0.4))

    # λ inheritance
    mean_lam = (parent_a.lambda_coeff + parent_b.lambda_coeff) / 2.0
    child_lam = max(0.8, mean_lam + rng.gauss(0, 0.3))

    # Plane selection
    planes = [parent_a.plane, parent_b.plane]
    if rng.random() < 0.2:
        adjacent = rng.choice(planes) + rng.choice([-1, 1])
        child_plane = max(1, min(7, adjacent))
    else:
        child_plane = rng.choice(planes)

    child = EdenAgent(
        id=str(uuid.uuid4()),
        name=name,
        generation=generation,
        plane=child_plane,
        k_current=round(child_k, 2),
        k0=round(child_k, 2),
        lambda_coeff=round(child_lam, 2),
        parent_a_id=parent_a.id,
        parent_b_id=parent_b.id,
        birth_tick=birth_tick,
        memory_fragment=f"Born to {parent_a.name} and {parent_b.name}.",
    )
    return child
