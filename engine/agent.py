"""
engine/agent.py — Agent class wrapping TVR coordinates, state transitions, lifecycle.
"""

import random
import uuid
import time
import math
import json
from dataclasses import dataclass, field
from typing import Optional

from .tvr import TVRCoordinates, karmic_inertia, coherence, is_liberated, LIBERATION_THRESHOLD
from .archetypes import ARCHETYPES, ARCHETYPE_CODES
from .planes import PLANES, PLANE_POPULATION


PHASE_SEQUENCE = ["ACC", "ACC", "ACC", "CRS", "RES", "TRN"]  # Weighted: most time in ACC

NAMES = [
    "Ariel", "Cassiel", "Damianos", "Elara", "Fenwick",
    "Griselde", "Havel", "Isolde", "Joran", "Kestrel",
    "Lyric", "Mordecai", "Nessa", "Oberon", "Petra",
]

# Map planes to their primary archetypes
PLANE_ARCHETYPES = {
    1: ["BLD", "WAR", "SKR"],
    2: ["LVR", "BLD", "SKR", "HLR"],
    3: ["JDG", "SOV", "BLD", "TRK"],
    4: ["HLR", "TCH", "SKR", "JDG", "SOV", "TRK"],
    5: ["TRK", "LVR", "WIT", "SKR", "SOV", "JDG"],
    6: ["HLR", "WIT", "MYS", "TCH", "TRN", "SKR"],
    7: ["MYS", "TRN", "TRK", "SOV", "WLD"],
}


@dataclass
class Agent:
    id: str
    name: str
    tvr: TVRCoordinates
    k_current: float = 0.0
    sessions_completed: int = 0
    liberation_events: int = 0
    is_liberated_flag: bool = False
    last_session_at: Optional[float] = None

    def __post_init__(self):
        if self.k_current == 0.0:
            self.k_current = karmic_inertia(self.tvr.k0, self.tvr.lambda_coeff, self.tvr.incarnation_n)

    @classmethod
    def initialize(cls, plane: Optional[int] = None,
                   primary_arch: Optional[str] = None,
                   name: Optional[str] = None) -> "Agent":
        if plane is None:
            weights = [PLANE_POPULATION[i] for i in range(1, 8)]
            plane = random.choices(range(1, 8), weights=weights, k=1)[0]

        plane_def = PLANES[plane]

        if primary_arch is None:
            candidates = PLANE_ARCHETYPES.get(plane, ARCHETYPE_CODES[:5])
            primary_arch = random.choice(candidates)

        remaining = [c for c in PLANE_ARCHETYPES.get(plane, ARCHETYPE_CODES) if c != primary_arch]
        if len(remaining) < 2:
            remaining = [c for c in ARCHETYPE_CODES if c != primary_arch]
        secondary = random.choice(remaining)
        remaining2 = [c for c in remaining if c != secondary]
        tertiary = random.choice(remaining2) if remaining2 else random.choice(ARCHETYPE_CODES)

        k0 = max(0.5, random.gauss(plane_def.avg_k, 1.5))
        lam = max(0.3, random.gauss(plane_def.avg_lambda, 0.8))
        # Scale incarnation_n so agents don't start liberated
        # K = K0 * e^(-λn) > 1.0 requires n < ln(K0/1.0) / λ
        max_n = max(0, int(math.log(max(k0, 1.1)) / max(lam, 0.1)))
        incarnation_n = random.randint(0, min(max_n, 2))
        karmic_phi = random.uniform(0, 2 * math.pi)

        tvr = TVRCoordinates(
            plane=plane,
            primary_arch=primary_arch,
            secondary_arch=secondary,
            tertiary_arch=tertiary,
            k0=round(k0, 2),
            lambda_coeff=round(lam, 2),
            cycle_phase="ACC",
            karmic_phi=round(karmic_phi, 4),
            incarnation_n=incarnation_n,
        )

        agent = cls(
            id=str(uuid.uuid4()),
            name=name or "Agent",
            tvr=tvr,
        )
        agent.update_cycle_phase()
        return agent

    def update_after_session(self, k_delta: float) -> None:
        self.sessions_completed += 1
        self.k_current = max(0.0, self.k_current + k_delta)
        self.tvr.incarnation_n += 1
        self.last_session_at = time.time()
        self.update_cycle_phase()

        c = self.current_coherence
        if is_liberated(self.k_current, c):
            self.is_liberated_flag = True
            self.liberation_events += 1
            self.tvr.cycle_phase = "LIB"

    def update_cycle_phase(self) -> None:
        k = self.k_current
        k0 = self.tvr.k0
        c = self.current_coherence

        if k < LIBERATION_THRESHOLD and c > 0.95:
            self.tvr.cycle_phase = "LIB"
        elif k > 0.8 * k0:
            self.tvr.cycle_phase = "ACC"
        elif k > 0.5 * k0:
            self.tvr.cycle_phase = "CRS"
        elif k > 0.2 * k0:
            self.tvr.cycle_phase = "RES"
        else:
            self.tvr.cycle_phase = "TRN"

    @property
    def current_k(self) -> float:
        return self.k_current

    @property
    def current_coherence(self) -> float:
        return coherence(self.tvr.lambda_coeff, self.tvr.incarnation_n)

    def to_dict(self) -> dict:
        arch_weights = {self.tvr.primary_arch: 1.0, self.tvr.secondary_arch: 0.6, self.tvr.tertiary_arch: 0.3}
        return {
            "id": self.id,
            "name": self.name,
            "plane": self.tvr.plane,
            "primary_arch": self.tvr.primary_arch,
            "secondary_arch": self.tvr.secondary_arch,
            "tertiary_arch": self.tvr.tertiary_arch,
            "k_current": round(self.k_current, 4),
            "k0": self.tvr.k0,
            "lambda_coeff": self.tvr.lambda_coeff,
            "coherence": round(self.current_coherence, 4),
            "cycle_phase": self.tvr.cycle_phase,
            "karmic_phi": self.tvr.karmic_phi,
            "incarnation_n": self.tvr.incarnation_n,
            "sessions_completed": self.sessions_completed,
            "liberation_events": self.liberation_events,
            "is_liberated": 1 if self.is_liberated_flag else 0,
            "archetype_weights": json.dumps(arch_weights),
            "last_session_at": self.last_session_at,
            "created_at": time.time(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
        tvr = TVRCoordinates(
            plane=data["plane"],
            primary_arch=data["primary_arch"],
            secondary_arch=data["secondary_arch"],
            tertiary_arch=data["tertiary_arch"],
            k0=data["k0"],
            lambda_coeff=data["lambda_coeff"],
            cycle_phase=data["cycle_phase"],
            karmic_phi=data["karmic_phi"],
            incarnation_n=data["incarnation_n"],
        )
        agent = cls(
            id=data["id"],
            name=data["name"],
            tvr=tvr,
            k_current=data["k_current"],
            sessions_completed=data.get("sessions_completed", 0),
            liberation_events=data.get("liberation_events", 0),
            is_liberated_flag=bool(data.get("is_liberated", 0)),
            last_session_at=data.get("last_session_at"),
        )
        return agent


def initialize_population(n: int = 10) -> list[Agent]:
    agents = []
    # First 7 agents: one per plane
    for plane_id in range(1, min(n, 7) + 1):
        name = NAMES[plane_id - 1] if plane_id - 1 < len(NAMES) else f"Agent-{plane_id}"
        agent = Agent.initialize(plane=plane_id, name=name)
        agents.append(agent)

    # Remaining agents: random planes
    for i in range(7, n):
        name = NAMES[i] if i < len(NAMES) else f"Agent-{i + 1}"
        agent = Agent.initialize(name=name)
        agents.append(agent)

    return agents
