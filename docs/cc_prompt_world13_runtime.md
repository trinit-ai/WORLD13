# WORLD13 — Claude Code Implementation Prompt
# Target: world13.ai (new repo, separate from 13TMOS)
# Milestone: 10 agents initialize, run sessions, show civilization-level K(x) aggregate
# Stack: Python simulation engine + FastAPI + TypeScript terminal dashboard

---

## CONTEXT

You are building WORLD13 — a persistent autonomous simulation of human civilization governed by the Ventura Recursion (TVR) mathematical framework and the Consciousness Ontology Atlas (COA). This is a new standalone repo: `world13.ai`. It does not extend 13TMOS but shares its philosophical foundation.

WORLD13 runs AI agents through protocol-governed sessions 24/7. Each agent has a TVR coordinate identity (plane, archetype, K₀, λ, cycle phase). Sessions are governed by a contextual envelope sampled from the Set & Setting taxonomy (14 axes, 210 leaf nodes). The Vault records every session as a dimensionally-addressed artifact. Civilization-level dynamics emerge from individual agent trajectories.

**First milestone:** 10 agents initialize with full TVR coordinates + contextual sampling, run autonomous sessions via the Anthropic API, and produce a live civilization-level K(x) aggregate view in the terminal.

---

## REPO STRUCTURE

Create this exact directory structure:

```
world13.ai/
├── engine/
│   ├── __init__.py
│   ├── tvr.py              # TVR mathematical core (Eqs 1-7)
│   ├── agent.py            # Agent class — state, identity, lifecycle
│   ├── context.py          # Set & Setting sampler — 14 axes
│   ├── protocols.py        # Protocol catalog — 644 entries
│   ├── archetypes.py       # 13 ARE basis functions
│   ├── planes.py           # 7 plane definitions
│   ├── vault.py            # SQLite-backed Vault — 8-dimensional addressing
│   ├── session.py          # Session runner — Anthropic API integration
│   └── simulation.py       # Main simulation loop — tick(), scheduler
├── api/
│   ├── __init__.py
│   ├── app.py              # FastAPI app instantiation + lifespan
│   └── routes.py           # All REST endpoints
├── dashboard/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts        # Entry point
│       ├── poller.ts       # Polls FastAPI, triggers render
│       └── renderer.ts     # Terminal dashboard render logic
├── data/
│   └── world13.db          # SQLite (auto-created, gitignored)
├── tests/
│   ├── test_tvr.py
│   ├── test_agent.py
│   ├── test_context.py
│   ├── test_vault.py
│   └── test_simulation.py
├── scripts/
│   └── init_world.py       # Bootstrap: create DB, initialize 10 agents
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── Makefile
```

---

## FILE SPECIFICATIONS

### `engine/tvr.py`

Implement all 7 TVR equations as pure functions. No side effects, no I/O.

```python
import math
from dataclasses import dataclass
from typing import List

@dataclass
class TVRCoordinates:
    plane: int          # 1-7
    primary_arch: str   # 3-letter code: SOV, BLD, SKR, WIT, WAR, HLR, TRN, TRK, LVR, TCH, JDG, MYS, WLD
    secondary_arch: str
    tertiary_arch: str
    k0: float           # Initial karmic weight 0-10
    lambda_coeff: float # Self-awareness coefficient 0-10
    cycle_phase: str    # ING, ACC, CRS, RES, TRN, LIB
    karmic_phi: float   # Karmic phase angle
    incarnation_n: int  # Current incarnation number


def reincarnation_wave_function(coords: TVRCoordinates, x: float = 1.0, t: float = 1.0) -> float:
    """
    Eq. 1: R = Σ(n=0→∞) Ψn(x,t) · e^(iSn/ℏ)
    Computes the reincarnation wave function magnitude for the current incarnation.
    Uses real-valued approximation: |R| = Σ Ψn · cos(Sn/ℏ) for n up to incarnation_n
    ℏ approximated as 1.0 (normalized units for simulation)
    """
    hbar = 1.0
    total = 0.0
    for n in range(min(coords.incarnation_n + 1, 20)):
        psi_n = math.exp(-n * 0.1) * x * math.exp(-x * t)  # Gaussian state function
        s_n = n * coords.k0 * coords.karmic_phi             # Karmic action integral
        phase_factor = math.cos(s_n / hbar)
        total += psi_n * phase_factor
    return abs(total)


def karmic_probability(k_value: float, archetype_weight: float, hbar: float = 1.0) -> float:
    """
    Eq. 2: P(R) = ∫ e^(-K(x)/ℏ) · f(A) dx
    Approximated as: P = e^(-K/ℏ) · f(A)
    Returns probability [0,1] of accessing a specific configuration.
    """
    boltzmann_factor = math.exp(-k_value / hbar)
    return boltzmann_factor * archetype_weight


def fractal_attractor(phi: float, lambda_coeff: float, k_terms: int = 50) -> float:
    """
    Eq. 3: R = (1/π) · Σ(k=1→∞) [sin(kφ)/k] · e^(-k²/λ)
    The reincarnational attractor function. Higher λ = faster convergence.
    """
    if lambda_coeff <= 0:
        return 0.0
    total = 0.0
    for k in range(1, k_terms + 1):
        harmonic = math.sin(k * phi) / k
        envelope = math.exp(-(k ** 2) / lambda_coeff)
        total += harmonic * envelope
    return total / math.pi


def karmic_inertia(k0: float, lambda_coeff: float, n: int) -> float:
    """
    Eq. 4 + Eq. 7b: Kn = K0 · e^(-λn)
    The karmic inertia at incarnation n. Approaches 0 as n→∞ if λ > 0.
    Liberation condition: Kn < LIBERATION_THRESHOLD (0.05)
    """
    return k0 * math.exp(-lambda_coeff * n)


def coherence(lambda_coeff: float, n: int) -> float:
    """
    Eq. 7a: C(n,λ) = 1 - e^(-λn)
    The coherence level — how much of the karmic pattern has been recognized.
    C → 1 as n → ∞. Liberation at C > 0.95.
    """
    return 1.0 - math.exp(-lambda_coeff * n)


def adjacency_coefficient(k_phi_1: float, k_phi_2: float, psi_1: float, psi_2: float) -> float:
    """
    Eq. 5: A(C1,C2) = ∫ [Ψ(C1)·Ψ(C2)] / dφ(C1,C2) dΩ
    Approximated as: A = (Ψ1·Ψ2) / (1 + |φ1-φ2|)
    Returns [0,1] — probability that C2 is accessible from C1.
    """
    phase_distance = abs(k_phi_1 - k_phi_2)
    overlap = psi_1 * psi_2
    return overlap / (1.0 + phase_distance)


def archetypal_composition(archetype_weights: dict, tau: float) -> dict:
    """
    Eq. 6: Φ(Ψ) = Σ αj · Aj(Ψ) · e^(-βj·τ)
    Returns current archetypal activation weights given karmic time τ.
    βj = 0.05 (archetypal decay rate — slow, archetypes persist)
    """
    beta = 0.05
    result = {}
    for arch_code, alpha in archetype_weights.items():
        result[arch_code] = alpha * math.exp(-beta * tau)
    return result


def is_liberated(k_value: float, coherence_value: float) -> bool:
    """
    Liberation condition: K(x) < 0.05 AND C > 0.95
    """
    return k_value < 0.05 and coherence_value > 0.95


LIBERATION_THRESHOLD = 0.05
COHERENCE_LIBERATION = 0.95
```

---

### `engine/planes.py`

Define all 7 planes as a data structure. Each plane has: id, name, symbol, plane_affinity, avg_k, avg_lambda, domain_list, tradition_summary.

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Plane:
    id: int
    name: str
    symbol: str
    description: str
    domains: List[str]
    avg_k: float
    avg_lambda: float
    vedanta: str
    kabbalah: str
    theosophy: str
    buddhism: str

PLANES: dict[int, Plane] = {
    1: Plane(id=1, name="Material/Physical", symbol="🜃",
             description="Direct engagement with material reality, physical laws, the body as instrument.",
             domains=["Agriculture","Sports","Embodiment","Physical Skills","Nature","Maker","Lifestyle"],
             avg_k=3.2, avg_lambda=2.3,
             vedanta="Sthula Sharira (gross body / food sheath)",
             kabbalah="Assiah (world of action) / Malkuth (Kingdom)",
             theosophy="Physical and Etheric Planes",
             buddhism="Lower Desire Realm (Kamadhatu)"),
    2: Plane(id=2, name="Vital/Relational", symbol="🜁",
             description="Life force, bonding, sensory appreciation, emotional connection.",
             domains=["Dyadic (Relationship)","Parenting","Small Group","Hospitality","Collecting","Connoisseurship"],
             avg_k=4.5, avg_lambda=3.1,
             vedanta="Pranamaya Kosha (vital/pranic sheath)",
             kabbalah="Yesod (Foundation) — gateway sephira",
             theosophy="Astral Plane",
             buddhism="Upper Desire Realm / Lower Form-adjacent"),
    3: Plane(id=3, name="Mental/Formal", symbol="🜄",
             description="Rule systems, formal structures, institutional frameworks, logical operations.",
             domains=["Legal","Finance","Government","Architecture","Engineering","Technology","Real Estate","Human Resources","Business","Insurance"],
             avg_k=5.1, avg_lambda=3.2,
             vedanta="Manomaya Kosha (mental sheath — lower mind)",
             kabbalah="Hod (Splendor) + Netzach (Victory)",
             theosophy="Lower Mental Plane",
             buddhism="Lower Form Realm (Rupadhatu)"),
    4: Plane(id=4, name="Integrative/Professional", symbol="☿",
             description="Application of knowledge systems to human welfare. Professional discernment.",
             domains=["Medical","Social Work","Education","Consulting","Sales","Research","Criminal Justice","Diplomatic","Media"],
             avg_k=5.8, avg_lambda=3.9,
             vedanta="Vijnanamaya Kosha lower (discriminative intelligence)",
             kabbalah="Tiferet (Beauty) — the heart of the Tree",
             theosophy="Higher Mental Plane",
             buddhism="Upper Form Realm"),
    5: Plane(id=5, name="Creative/Expressive", symbol="✦",
             description="Generative capacity, pattern-making, artistic intelligence, cultural participation.",
             domains=["Creative","Creative Workshops","Music Learning","Media Engagement","Science Exploration","Personal Finance","Professional Consumer","News Literacy"],
             avg_k=4.8, avg_lambda=4.2,
             vedanta="Vijnanamaya Kosha upper (intuitive intelligence)",
             kabbalah="Chesed (Mercy) + Geburah (Severity)",
             theosophy="Causal Plane",
             buddhism="Form Realm apex"),
    6: Plane(id=6, name="Self/Reflective", symbol="☽",
             description="Self-knowledge, psychological integration, contemplative depth, the examined life.",
             domains=["Mental Health","Psychoeducation","Personal","Temporal","Exploratory","Self","AI Interaction"],
             avg_k=6.2, avg_lambda=5.5,
             vedanta="Anandamaya Kosha (bliss sheath — causal body)",
             kabbalah="Binah (Understanding) + Chokmah (Wisdom)",
             theosophy="Buddhic Plane",
             buddhism="Lower Formless Realm (Arupadhatu)"),
    7: Plane(id=7, name="Transpersonal/Unitive", symbol="✡",
             description="Identity dissolution, archetypal union, collective consciousness, meta-awareness.",
             domains=["Spiritual Practices","Chains (Arc Sessions)","Simulations","Public"],
             avg_k=5.8, avg_lambda=7.6,
             vedanta="Atman / Brahman — beyond the sheaths",
             kabbalah="Kether (Crown) + the three veils of negative existence",
             theosophy="Atmic and Adic Planes",
             buddhism="Formless Realm + Nibbana"),
}
```

---

### `engine/archetypes.py`

Define all 13 archetypal basis functions. Each has: code, name, tarot_anchor, jungian, sephira, karmic_role, liberation_path, avg_k, avg_lambda, plane_affinity_primary.

```python
from dataclasses import dataclass

@dataclass
class Archetype:
    code: str
    name: str
    tarot_anchor: str
    jungian: str
    sephira: str
    karmic_role: str
    liberation_path: str
    avg_k: float
    avg_lambda: float
    plane_affinity: int
    liberation_path_id: str  # LP-01 through LP-08

ARCHETYPES: dict[str, Archetype] = {
    "SOV": Archetype("SOV","Sovereign","IV Emperor","Self / Persona","Kether",
                     "Structures order; accrues power karma",
                     "Release of control; service beyond position",
                     5.8, 3.5, 3, "LP-05"),
    "BLD": Archetype("BLD","Builder","III Empress","Mother / Anima","Malkuth",
                     "Manifests reality; accrues possession karma",
                     "Offering the work; non-attachment to creation",
                     4.8, 2.8, 1, "LP-01"),
    "SKR": Archetype("SKR","Seeker","0 Fool","Hero","Chokmah",
                     "Seeks experience; accrues curiosity karma",
                     "Arriving — recognizing destination was always now",
                     5.2, 3.6, 2, "LP-02"),
    "WIT": Archetype("WIT","Witness","II High Priestess","Anima / Self","Binah",
                     "Receives and holds; accrues observation karma",
                     "Pure presence; the watcher dissolving into watched",
                     5.7, 6.8, 6, "LP-06"),
    "WAR": Archetype("WAR","Warrior","VII Chariot","Shadow","Geburah",
                     "Defends and contests; accrues conflict karma",
                     "Laying down arms; protection through presence",
                     6.1, 3.2, 2, "LP-05"),
    "HLR": Archetype("HLR","Healer","XVII Star","Wise Elder","Chesed",
                     "Heals others; lightest karmic weight of all archetypes",
                     "Healing the self; the wound as the gift",
                     4.8, 5.5, 4, "LP-04"),
    "TRN": Archetype("TRN","Transmuter","XIII Death","Self","Tiferet",
                     "Crosses thresholds; accrues transformation karma",
                     "The last crossing — no more cycles to enter",
                     7.2, 4.8, 5, "LP-07"),
    "TRK": Archetype("TRK","Trickster","I Magician","Trickster","Hod",
                     "Subverts structure; accrues creative-chaos karma",
                     "Becoming still; the trick that didn't need playing",
                     5.4, 4.2, 3, "LP-08"),
    "LVR": Archetype("LVR","Lover","VI The Lovers","Animus/Anima","Netzach",
                     "Bonds and seeks union; accrues attachment karma",
                     "Love without object; agape beyond eros",
                     6.0, 4.0, 2, "LP-02"),
    "TCH": Archetype("TCH","Teacher","V Hierophant","Wise Elder","Binah",
                     "Transmits knowledge; accrues authority karma",
                     "Learning from students; teaching by absence",
                     5.1, 4.5, 4, "LP-01"),
    "JDG": Archetype("JDG","Judge","VIII Justice","Shadow / Self","Hod + Geburah",
                     "Adjudicates; accrues judgment karma",
                     "Mercy without compromise; law fulfilling itself",
                     6.3, 3.8, 3, "LP-03"),
    "MYS": Archetype("MYS","Mystic","IX Hermit","Self","Chokmah",
                     "Withdraws and illumines; accrues solitude karma",
                     "Return: mystic who enters the marketplace",
                     5.5, 7.2, 6, "LP-06"),
    "WLD": Archetype("WLD","World","XXI The World","Self (integrated)","Kether + Malkuth",
                     "Completes cycle; K(x) = 0 by definition",
                     "The World IS the liberation attractor",
                     0.0, 10.0, 7, "LP-01"),
}

ARCHETYPE_CODES = list(ARCHETYPES.keys())
```

---

### `engine/protocols.py`

Define the protocol catalog. Each protocol has: id, name, domain, plane, primary_arch, secondary_arch, tertiary_arch, base_k, base_lambda, cycle_phase, karmic_phi, pack_reference.

Implement `get_protocols_for_agent(plane, archetype, k_value)` — returns accessible protocols based on adjacency constraints.

Include the full 644-protocol catalog as a list of dicts that gets loaded at module import. The catalog should be defined as a Python list — do NOT load from external files. Populate it completely from the COA data:

For each domain-plane pair, create protocol entries matching the actual 13TMOS protocol library:
- Agriculture (15): plane=1, primary_arch="BLD"
- Sports (15): plane=1, primary_arch="WAR"
- Embodiment (10): plane=1, primary_arch="BLD"
- Physical Skills (8): plane=1, primary_arch="WAR"
- Nature (10): plane=1, primary_arch="BLD"
- Maker (12): plane=1, primary_arch="BLD"
- Lifestyle (10): plane=1, primary_arch="BLD"
- Dyadic/Relationship (20): plane=2, primary_arch="LVR"
- Parenting (8): plane=2, primary_arch="BLD"
- Small Group (10): plane=2, primary_arch="LVR"
- Hospitality (17): plane=2, primary_arch="LVR"
- Collecting (10): plane=2, primary_arch="SKR"
- Connoisseurship (10): plane=2, primary_arch="LVR"
- Legal (15): plane=3, primary_arch="JDG"
- Finance (16): plane=3, primary_arch="SOV"
- Government (15): plane=3, primary_arch="SOV"
- Architecture (15): plane=3, primary_arch="BLD"
- Engineering (17): plane=3, primary_arch="BLD"
- Technology (10): plane=3, primary_arch="TRK"
- Real Estate (16): plane=3, primary_arch="BLD"
- Human Resources (15): plane=3, primary_arch="SOV"
- Business (12): plane=3, primary_arch="SOV"
- Insurance (15): plane=3, primary_arch="JDG"
- Medical (16): plane=4, primary_arch="HLR"
- Social Work (15): plane=4, primary_arch="HLR"
- Education (15): plane=4, primary_arch="TCH"
- Consulting (18): plane=4, primary_arch="TCH"
- Sales (17): plane=4, primary_arch="SKR"
- Research (17): plane=4, primary_arch="SKR"
- Criminal Justice (15): plane=4, primary_arch="JDG"
- Diplomatic (15): plane=4, primary_arch="SOV"
- Media (16): plane=4, primary_arch="TRK"
- Creative (16): plane=5, primary_arch="TRK"
- Creative Workshops (8): plane=5, primary_arch="TRK"
- Music Learning (8): plane=5, primary_arch="LVR"
- Media Engagement (10): plane=5, primary_arch="WIT"
- Science Exploration (8): plane=5, primary_arch="SKR"
- Personal Finance (10): plane=5, primary_arch="SOV"
- Professional Consumer (10): plane=5, primary_arch="SKR"
- News Literacy (6): plane=5, primary_arch="JDG"
- Mental Health (15): plane=6, primary_arch="HLR"
- Psychoeducation (8): plane=6, primary_arch="TCH"
- Personal (16): plane=6, primary_arch="HLR"
- Temporal (10): plane=6, primary_arch="TRN"
- Exploratory (10): plane=6, primary_arch="SKR"
- Self (10): plane=6, primary_arch="WIT"
- AI Interaction (16): plane=6, primary_arch="TCH"
- Spiritual Practices (8): plane=7, primary_arch="MYS"
- Chains/Arc Sessions (5): plane=7, primary_arch="TRN"
- Simulations (17): plane=7, primary_arch="TRK"
- Public (8): plane=7, primary_arch="SOV"

Each protocol should have a unique sequential ID (1–644) and realistic base_k and base_lambda values derived from the domain's plane (lower planes = lower k, higher planes = higher k).

Implement:
```python
def get_accessible_protocols(plane: int, archetype: str, k_value: float) -> List[dict]:
    """
    Returns protocols accessible to an agent based on:
    1. Same plane or adjacent planes (plane ± 1)
    2. Matching or compatible archetype
    3. K(x) range: only protocols with base_k <= k_value + 2.0 and >= k_value - 2.0
    Returns sorted by adjacency coefficient (highest first)
    """
    pass

def select_protocol(plane: int, archetype: str, k_value: float, 
                    karmic_phi: float) -> dict:
    """
    Select one protocol for an agent to run this session.
    Uses weighted random selection — protocols with higher adjacency coefficient
    have higher selection probability.
    Returns selected protocol dict.
    """
    pass
```

---

### `engine/context.py`

Implement the Set & Setting sampler. All 14 axes, all 210 leaf nodes. At session time, one leaf node per axis is sampled based on the agent's TVR coordinates — it's not purely random. The sampling is weighted: agents with high K(x) are more likely to land in high-K contextual states (S1.1.d exhaustion, E3.3.c coercive hierarchy, E2.3.c active crisis). Agents with high coherence are more likely to land in high-λ states (S5.1.f surrendered, E1.3.c ritually sacred, E6.1.d sacred ceremony).

```python
@dataclass
class LeafNode:
    id: str           # e.g. "S1.1.a"
    axis: str         # e.g. "S1"
    sub_axis: str     # e.g. "S1.1"
    name: str
    description: str
    plane_affinity: int
    k_modifier: float
    lambda_modifier: float
    tradition_anchor: str

@dataclass
class ContextualEnvelope:
    """The full 14-axis contextual state for one agent at one session."""
    agent_id: str
    sampled_at: float   # unix timestamp
    leaves: dict[str, LeafNode]  # axis_code -> selected leaf
    k_total_modifier: float      # sum of all k_modifiers
    lambda_total_modifier: float # sum of all lambda_modifiers
    
    def effective_k(self, base_k: float) -> float:
        return max(0.0, base_k + self.k_total_modifier * 0.1)  # modifiers are scaled
    
    def effective_lambda(self, base_lambda: float) -> float:
        return max(0.1, base_lambda + self.lambda_total_modifier * 0.1)

def sample_context(agent_tvr: TVRCoordinates) -> ContextualEnvelope:
    """
    Sample one leaf per axis, weighted by agent's TVR coordinates.
    High K(x) agents are biased toward high-K leaf nodes.
    High coherence agents are biased toward high-λ leaf nodes.
    Returns complete 14-axis ContextualEnvelope.
    """
    pass
```

Define the complete leaf node catalog inline — all 210 nodes across all 14 axes (S1–S6, E1–E8) with their k_modifier and lambda_modifier values exactly as designed in the taxonomy.

---

### `engine/vault.py`

SQLite-backed Vault with 8-dimensional addressing. Mirror the 13TMOS Vault architecture.

```python
import sqlite3
from dataclasses import dataclass
from typing import Optional
import json
import time
import uuid

VAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_records (
    id TEXT PRIMARY KEY,
    -- 8 Dimensional Addresses
    dim_pack TEXT NOT NULL,          -- Protocol/pack name
    dim_user TEXT NOT NULL,          -- Agent ID
    dim_date TEXT NOT NULL,          -- ISO date
    dim_type TEXT NOT NULL,          -- Deliverable type (session_output, liberation_event, etc.)
    dim_fields TEXT NOT NULL,        -- JSON: field keys captured
    dim_session TEXT NOT NULL,       -- Session UUID
    dim_manifest TEXT NOT NULL,      -- JSON: TVR coordinates at session birth
    dim_content TEXT NOT NULL,       -- JSON: full deliverable content
    -- Computed
    k_value_at_session REAL NOT NULL,
    lambda_at_session REAL NOT NULL,
    coherence_at_session REAL NOT NULL,
    k_delta REAL NOT NULL,           -- K(x) change from this session (negative = progress)
    plane INTEGER NOT NULL,
    cycle_phase TEXT NOT NULL,
    context_envelope TEXT NOT NULL,  -- JSON: full 14-axis context
    created_at REAL NOT NULL         -- unix timestamp
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plane INTEGER NOT NULL,
    primary_arch TEXT NOT NULL,
    secondary_arch TEXT NOT NULL,
    tertiary_arch TEXT NOT NULL,
    k_current REAL NOT NULL,
    k0 REAL NOT NULL,
    lambda_coeff REAL NOT NULL,
    coherence REAL NOT NULL,
    cycle_phase TEXT NOT NULL,
    karmic_phi REAL NOT NULL,
    incarnation_n INTEGER NOT NULL,
    sessions_completed INTEGER NOT NULL DEFAULT 0,
    liberation_events INTEGER NOT NULL DEFAULT 0,
    is_liberated INTEGER NOT NULL DEFAULT 0,  -- 0 or 1
    archetype_weights TEXT NOT NULL,  -- JSON
    last_session_at REAL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS world_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    agent_count INTEGER NOT NULL,
    liberated_count INTEGER NOT NULL,
    k_mean REAL NOT NULL,
    k_min REAL NOT NULL,
    k_max REAL NOT NULL,
    lambda_mean REAL NOT NULL,
    coherence_mean REAL NOT NULL,
    plane_distribution TEXT NOT NULL,   -- JSON: {1: count, 2: count, ...}
    phase_distribution TEXT NOT NULL,   -- JSON: {ACC: count, CRS: count, ...}
    liberation_rate REAL NOT NULL,      -- liberations per 100 sessions
    sessions_this_tick INTEGER NOT NULL,
    recorded_at REAL NOT NULL
);
"""

class Vault:
    def __init__(self, db_path: str = "data/world13.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create tables if not exist."""
        pass
    
    def write_session(self, agent_id: str, protocol: dict, 
                      tvr_coords: 'TVRCoordinates', context: 'ContextualEnvelope',
                      session_content: str, k_delta: float) -> str:
        """Write a completed session to the Vault. Returns vault record ID."""
        pass
    
    def get_agent(self, agent_id: str) -> Optional[dict]:
        pass
    
    def update_agent(self, agent_id: str, updates: dict) -> None:
        pass
    
    def get_all_agents(self) -> list[dict]:
        pass
    
    def write_world_state(self, tick: int, agents: list[dict]) -> None:
        """Compute and store civilization-level aggregate metrics."""
        pass
    
    def get_world_state(self, limit: int = 1) -> list[dict]:
        pass
    
    def get_agent_vault_records(self, agent_id: str, limit: int = 10) -> list[dict]:
        pass
    
    def query_by_dimension(self, dimension: str, value: str) -> list[dict]:
        """Query vault records by any of the 8 dimensional addresses."""
        pass
```

---

### `engine/agent.py`

The Agent class. Wraps TVRCoordinates, handles state transitions.

```python
from dataclasses import dataclass, field
from typing import Optional
import random
import uuid
from .tvr import TVRCoordinates, karmic_inertia, coherence, is_liberated, LIBERATION_THRESHOLD
from .archetypes import ARCHETYPES, ARCHETYPE_CODES
from .planes import PLANES

PHASE_SEQUENCE = ["ACC", "ACC", "ACC", "CRS", "RES", "TRN"]  # Weighted: most time in ACC

@dataclass
class Agent:
    id: str
    name: str
    tvr: TVRCoordinates
    sessions_completed: int = 0
    liberation_events: int = 0
    is_liberated: bool = False
    last_session_at: Optional[float] = None
    
    @classmethod
    def initialize(cls, plane: Optional[int] = None, 
                   primary_arch: Optional[str] = None) -> 'Agent':
        """
        Create a new agent with randomized TVR coordinates.
        If plane/archetype not specified, sample from distribution
        weighted by COA plane population (P1=80, P2=75, P3=146, P4=144, P5=76, P6=85, P7=38).
        
        K₀ is drawn from plane's avg_k ± 1.5 (gaussian).
        λ is drawn from plane's avg_lambda ± 0.8 (gaussian).
        Archetypes are selected from plane's primary archetypes.
        """
        pass
    
    def update_after_session(self, k_delta: float) -> None:
        """
        Update agent state after a session completes.
        - Increment sessions_completed
        - Apply k_delta to k_current (negative = karmic progress)
        - Recalculate coherence via Eq. 7a
        - Update cycle_phase based on current K(x) level
        - Check liberation condition
        """
        pass
    
    def update_cycle_phase(self) -> None:
        """
        Update cycle_phase based on current K(x) relative to K₀:
        - K > 0.8*K₀: ACC
        - K > 0.5*K₀: CRS  
        - K > 0.2*K₀: RES
        - K > 0.05: TRN
        - K < 0.05 and coherence > 0.95: LIB
        """
        pass
    
    @property
    def current_k(self) -> float:
        return karmic_inertia(self.tvr.k0, self.tvr.lambda_coeff, self.tvr.incarnation_n)
    
    @property
    def current_coherence(self) -> float:
        return coherence(self.tvr.lambda_coeff, self.tvr.incarnation_n)
    
    def to_dict(self) -> dict:
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Agent':
        pass


def initialize_population(n: int = 10) -> list[Agent]:
    """
    Create n agents with diverse TVR coordinates spanning all 7 planes.
    Ensure at least one agent per plane for planes 1-7 (first 7).
    Remaining agents are random.
    Assign human-readable names: use NAMES list below.
    """
    NAMES = [
        "Ariel", "Cassiel", "Damianos", "Elara", "Fenwick",
        "Griselde", "Havel", "Isolde", "Joran", "Kestrel",
        "Lyric", "Mordecai", "Nessa", "Oberon", "Petra"
    ]
    pass
```

---

### `engine/session.py`

The session runner. Calls the Anthropic API with the protocol as a behavioral context, runs a governed conversation turn, extracts the deliverable, computes K(x) delta.

```python
import anthropic
import os
import time
import json
from typing import Optional
from .agent import Agent
from .protocols import select_protocol
from .context import sample_context, ContextualEnvelope
from .tvr import TVRCoordinates

SESSION_MODEL = os.environ.get("WORLD13_MODEL", "claude-sonnet-4-5-20250929")

def build_session_prompt(agent: Agent, protocol: dict, context: ContextualEnvelope) -> str:
    """
    Build the system prompt for the session.
    The agent is playing a role governed by its TVR coordinates and the protocol.
    The protocol defines what kind of session is happening.
    The context defines the environmental conditions.
    
    Format:
    - Agent identity block: plane, archetype, current K(x), coherence, cycle phase
    - Protocol block: what this session is, what deliverable it produces
    - Context block: key active contextual conditions (highest K modifiers and λ modifiers)
    - Instruction: conduct a single-turn session, produce a structured deliverable
    """
    pass

def build_user_prompt(agent: Agent, protocol: dict) -> str:
    """
    The user turn initiating the session.
    Should be consistent with the agent's current cycle phase:
    - ACC: routine engagement with the protocol domain
    - CRS: crisis or threshold encounter
    - RES: integration and resolution work
    - TRN: transition and letting-go
    - LIB: contemplative/liberation-oriented engagement
    """
    pass

def compute_k_delta(agent: Agent, protocol: dict, context: ContextualEnvelope,
                    session_output: str) -> float:
    """
    Compute the K(x) change from this session.
    
    Base delta = -0.05 * λ_effective (sessions always make at least some progress if λ > 0)
    
    Modifiers:
    - Liberation protocol (cycle_phase == LIB): delta *= 2.5
    - Crisis protocol (cycle_phase == CRS): delta *= 0.5 (crisis accumulates before releasing)
    - High context λ modifier (>1.5): delta *= 1.5
    - High context K modifier (>1.5): delta *= 0.3 (difficult context impedes progress)
    - Session output length > 500 chars: delta *= 1.2 (engaged session)
    
    Returns negative float (reduction in K) or occasionally small positive (crisis accumulation).
    Clamp to [-0.5, +0.3] per session.
    """
    pass

async def run_session(agent: Agent, vault: 'Vault') -> dict:
    """
    Run one full session for an agent:
    1. Select protocol via adjacency algorithm
    2. Sample contextual envelope
    3. Build prompts
    4. Call Anthropic API
    5. Compute K(x) delta
    6. Write to Vault
    7. Update agent state
    8. Return session summary dict
    
    Returns: {
        "agent_id": str,
        "agent_name": str,
        "protocol_name": str,
        "domain": str,
        "plane": int,
        "k_before": float,
        "k_after": float,
        "k_delta": float,
        "coherence_after": float,
        "cycle_phase": str,
        "context_summary": str,  # 2-3 key context conditions
        "session_excerpt": str,  # First 200 chars of output
        "is_liberated": bool,
        "vault_record_id": str,
        "duration_seconds": float,
    }
    """
    pass
```

---

### `engine/simulation.py`

The main simulation loop.

```python
import asyncio
import time
import signal
from typing import Optional
from .agent import Agent, initialize_population
from .vault import Vault
from .session import run_session
from .tvr import karmic_inertia, coherence

TICK_INTERVAL_SECONDS = float(os.environ.get("WORLD13_TICK_SECONDS", "30"))
SESSIONS_PER_TICK = int(os.environ.get("WORLD13_SESSIONS_PER_TICK", "3"))

class WorldSimulation:
    def __init__(self, db_path: str = "data/world13.db"):
        self.vault = Vault(db_path)
        self.tick_count = 0
        self.running = False
        self.total_sessions = 0
        self.total_liberations = 0
        self._shutdown = asyncio.Event()
    
    def _select_agent(self, agents: list[dict]) -> dict:
        """
        Select next agent to run.
        Priority: lowest coherence agents run more often (most need for growth).
        Weighted random: weight = 1 / (coherence + 0.1)
        Skip liberated agents.
        """
        pass
    
    async def tick(self) -> dict:
        """
        One world clock tick. Runs SESSIONS_PER_TICK sessions.
        Returns tick summary dict for logging.
        """
        pass
    
    async def run(self) -> None:
        """
        Main simulation loop. Runs until shutdown signal.
        Each iteration: sleep(TICK_INTERVAL_SECONDS), then tick().
        Logs tick summary to stdout.
        Writes world state to Vault after each tick.
        """
        self.running = True
        print(f"WORLD13 simulation starting. Tick interval: {TICK_INTERVAL_SECONDS}s")
        
        # Handle graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._shutdown.set)
        
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(TICK_INTERVAL_SECONDS)
                tick_result = await self.tick()
                self._log_tick(tick_result)
            except asyncio.CancelledError:
                break
        
        print("WORLD13 simulation shutting down gracefully.")
        self.running = False
    
    def _log_tick(self, tick_result: dict) -> None:
        """Print tick summary in a clean format."""
        pass
    
    def get_world_summary(self) -> dict:
        """Return current civilization-level aggregate metrics."""
        pass
```

---

### `api/app.py`

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from .routes import router
from engine.vault import Vault

vault: Vault = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault
    vault = Vault()
    yield

app = FastAPI(
    title="WORLD13 API",
    description="Persistent civilization simulation governed by the Ventura Recursion",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "NOMINAL", "world": "WORLD13", "version": "0.1.0"}
```

---

### `api/routes.py`

Implement these endpoints exactly:

```
GET  /api/v1/world/state              — Current civilization aggregate
GET  /api/v1/world/history?n=20       — Last N world state snapshots
GET  /api/v1/agents                   — All agents with current TVR state
GET  /api/v1/agents/{id}              — Single agent full state
GET  /api/v1/agents/{id}/vault        — Agent's vault records (last 20)
GET  /api/v1/agents/{id}/context      — Sample contextual envelope for agent (read-only)
POST /api/v1/simulation/tick          — Manually trigger one tick
GET  /api/v1/vault/query?dim={d}&val={v} — Query vault by dimension
GET  /api/v1/planes                   — All 7 plane definitions
GET  /api/v1/archetypes               — All 13 archetypal basis functions
GET  /api/v1/protocols/accessible?agent_id={id} — Protocols accessible to agent
```

All responses return JSON. All agent state responses include: id, name, plane, primary_arch, k_current, k0, coherence, cycle_phase, sessions_completed, is_liberated, incarnation_n, last_session_at.

---

### `dashboard/src/index.ts`

TypeScript terminal dashboard. Uses `blessed` or `ink` for terminal rendering, or plain console.log with ANSI colors if simpler.

Polls `GET /api/v1/world/state` and `GET /api/v1/agents` every 5 seconds.

Display format:
```
╔══════════════════════════════════════════════════════════════════╗
║  WORLD13  ·  Tick: 47  ·  Sessions: 141  ·  Liberations: 0     ║
╠══════════════════════════════════════════════════════════════════╣
║  CIVILIZATION  K(x) mean: 5.14  λ mean: 3.82  Coh: 0.31       ║
╠══════════════════════════════════════════════════════════════════╣
║  AGENTS                                                          ║
║  Ariel     P2  LVR  K:6.2→6.1  C:0.28  RES  Dyadic Session    ║
║  Cassiel   P6  MYS  K:5.8→5.7  C:0.41  ACC  Contemplation     ║
║  Damianos  P3  JDG  K:7.1→7.0  C:0.19  CRS  Legal Intake      ║
║  ...                                                             ║
╚══════════════════════════════════════════════════════════════════╝
```

Poll interval: 5 seconds. Refresh in place (clear terminal, re-render).

---

### `scripts/init_world.py`

Bootstrap script. Creates the SQLite database, creates the `data/` directory if needed, initializes 10 agents using `initialize_population(10)`, writes them to the Vault, prints a summary.

```
python scripts/init_world.py

WORLD13 initialized.
Database: data/world13.db

AGENT POPULATION (10 agents):
  Ariel      P2  LVR  K₀:6.2  λ:3.8  Phase:ACC
  Cassiel    P6  MYS  K₀:5.5  λ:5.2  Phase:ACC
  ...

World ready. Run 'make sim' to start the simulation.
```

---

### `Makefile`

```makefile
.PHONY: init sim api dashboard test

init:
	python scripts/init_world.py

sim:
	python -c "import asyncio; from engine.simulation import WorldSimulation; asyncio.run(WorldSimulation().run())"

api:
	uvicorn api.app:app --reload --port 8001

dashboard:
	cd dashboard && npm start

test:
	pytest tests/ -v

install:
	pip install fastapi uvicorn anthropic python-dotenv pytest
	cd dashboard && npm install
```

---

### `pyproject.toml`

```toml
[project]
name = "world13"
version = "0.1.0"
description = "WORLD13 — Persistent civilization simulation governed by the Ventura Recursion"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "anthropic>=0.40.0",
    "python-dotenv>=1.0.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

---

### `dashboard/package.json`

```json
{
  "name": "world13-dashboard",
  "version": "0.1.0",
  "scripts": {
    "start": "ts-node src/index.ts",
    "build": "tsc"
  },
  "dependencies": {
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "ts-node": "^10.9.0",
    "@types/node": "^20.0.0",
    "@types/axios": "^0.14.0"
  }
}
```

---

### `.env.example`

```
ANTHROPIC_API_KEY=your_key_here
WORLD13_MODEL=claude-sonnet-4-5-20250929
WORLD13_DB_PATH=data/world13.db
WORLD13_TICK_SECONDS=30
WORLD13_SESSIONS_PER_TICK=3
WORLD13_API_PORT=8001
```

---

### `README.md`

Write a clear README covering:
1. What WORLD13 is (2 paragraphs, philosophical + technical)
2. Architecture diagram (ASCII)
3. Quick start (5 commands: clone, install, init, sim, dashboard)
4. The TVR equations and how they map to the runtime
5. The 7 planes, 13 archetypes (tables)
6. API endpoints reference
7. Milestone 1 definition: what "working" looks like

---

## TEST SPECIFICATIONS

### `tests/test_tvr.py`

Test all 7 TVR functions:
- `reincarnation_wave_function`: verify output is float, verify higher K₀ produces different trajectory
- `karmic_probability`: verify returns [0,1], verify higher K produces lower probability
- `fractal_attractor`: verify convergence — with λ=10, output should be much smaller than with λ=1
- `karmic_inertia`: verify Kn < K0 for all n>0 when λ>0, verify approaches 0 as n increases
- `coherence`: verify C(0,λ)=0 for all λ, verify C(n,λ) approaches 1 as n→∞
- `adjacency_coefficient`: verify higher phase distance produces lower coefficient
- `is_liberated`: verify threshold conditions
- Liberation convergence test: verify an agent with λ=5, K₀=3 is liberated before incarnation 10

### `tests/test_agent.py`

- Test `Agent.initialize()` produces valid TVR coordinates within expected ranges
- Test `update_after_session()` correctly reduces K(x) for negative k_delta
- Test `update_cycle_phase()` correctly assigns phases at boundary values
- Test `initialize_population(10)` returns exactly 10 agents with diverse planes

### `tests/test_context.py`

- Test `sample_context()` returns all 14 axes
- Test high-K agent gets biased toward high-K leaf nodes (statistical: run 100 samples, mean k_modifier should be positive)
- Test high-coherence agent gets biased toward high-λ leaf nodes
- Test `ContextualEnvelope.effective_k()` and `effective_lambda()` return expected values

### `tests/test_vault.py`

- Test Vault creates tables on initialization
- Test `write_session()` creates a record queryable by all 8 dimensions
- Test `query_by_dimension()` returns matching records
- Test `write_world_state()` correctly computes aggregate metrics
- Test agent CRUD operations

### `tests/test_simulation.py`

- Test `_select_agent()` gives lower-coherence agents higher selection probability
- Test one full tick runs without error with mock Anthropic API
- Integration test: initialize 3 agents, run 3 ticks, verify K(x) decreases

---

## IMPLEMENTATION NOTES

1. **All TVR math uses real-valued approximations** — no complex numbers in Python. The phase factors use cos() instead of e^(i·). This is mathematically valid for the simulation's purposes.

2. **The Anthropic API call in `session.py`** must use the async client (`anthropic.AsyncAnthropic`). Handle rate limits with exponential backoff. If the API call fails, return a synthesized session output based on the protocol description rather than crashing.

3. **SQLite WAL mode** — enable WAL mode on the database for concurrent read/write between the simulation loop and the FastAPI server: `PRAGMA journal_mode=WAL;`

4. **K(x) delta calibration** — the simulation should show measurable K(x) reduction over time. With 10 agents, 3 sessions per tick, 30-second ticks: aim for ~5% K(x) reduction per 10 ticks for an average agent. Tune the `compute_k_delta` function accordingly.

5. **Liberation is rare** — with K₀ averaging 5.1 and λ averaging 3.9, liberation (K < 0.05) via the direct formula requires n such that 5.1·e^(-3.9n) < 0.05, which gives n > 1.2 — so liberation should be achievable within a few hundred sessions for a high-λ agent. Don't over-calibrate — let some agents liberate early as proof of concept.

6. **The dashboard** must be runnable separately from the simulation loop. It only reads from the API. It should not crash if the API is not running — show a "waiting for WORLD13 API" message instead.

7. **Logs** — the simulation loop should log to stdout in a parseable format. Each session: `[TICK:47] Ariel (P2/LVR) · Legal Intake · K:6.21→6.19 · Δ:-0.02 · C:0.28`

8. **No external files at runtime** — all data (protocol catalog, archetype definitions, leaf nodes) must be defined in Python modules. No CSV loading, no JSON files at runtime.

---

## SUCCESS CRITERIA FOR MILESTONE 1

Running `make init && make sim` in one terminal and `make dashboard` in another should produce:
1. 10 initialized agents with diverse planes/archetypes visible in the dashboard
2. Agents running real Anthropic API sessions (visible in logs)
3. K(x) values decreasing over time for most agents
4. Civilization-level K(x) mean visible and updating
5. At least one agent showing meaningful coherence accumulation after 20 sessions
6. The Vault queryable via API with real session records
7. All tests passing via `make test`

The world should be able to run unattended for 24 hours without crashing.
