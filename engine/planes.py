"""
engine/planes.py — The 7 planes of consciousness.

Each plane maps to a Vedantic kosha, Kabbalistic sephira, Theosophical plane,
and Buddhist realm. Planes carry population weights and characteristic K/λ values.
"""

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
    1: Plane(
        id=1, name="Material/Physical", symbol="🜃",
        description="Direct engagement with material reality, physical laws, the body as instrument.",
        domains=["Agriculture", "Sports", "Embodiment", "Physical Skills", "Nature", "Maker", "Lifestyle"],
        avg_k=3.2, avg_lambda=2.3,
        vedanta="Sthula Sharira (gross body / food sheath)",
        kabbalah="Assiah (world of action) / Malkuth (Kingdom)",
        theosophy="Physical and Etheric Planes",
        buddhism="Lower Desire Realm (Kamadhatu)",
    ),
    2: Plane(
        id=2, name="Vital/Relational", symbol="🜁",
        description="Life force, bonding, sensory appreciation, emotional connection.",
        domains=["Dyadic (Relationship)", "Parenting", "Small Group", "Hospitality", "Collecting", "Connoisseurship"],
        avg_k=4.5, avg_lambda=3.1,
        vedanta="Pranamaya Kosha (vital/pranic sheath)",
        kabbalah="Yesod (Foundation) — gateway sephira",
        theosophy="Astral Plane",
        buddhism="Upper Desire Realm / Lower Form-adjacent",
    ),
    3: Plane(
        id=3, name="Mental/Formal", symbol="🜄",
        description="Rule systems, formal structures, institutional frameworks, logical operations.",
        domains=["Legal", "Finance", "Government", "Architecture", "Engineering", "Technology", "Real Estate", "Human Resources", "Business", "Insurance"],
        avg_k=5.1, avg_lambda=3.2,
        vedanta="Manomaya Kosha (mental sheath — lower mind)",
        kabbalah="Hod (Splendor) + Netzach (Victory)",
        theosophy="Lower Mental Plane",
        buddhism="Lower Form Realm (Rupadhatu)",
    ),
    4: Plane(
        id=4, name="Integrative/Professional", symbol="☿",
        description="Application of knowledge systems to human welfare. Professional discernment.",
        domains=["Medical", "Social Work", "Education", "Consulting", "Sales", "Research", "Criminal Justice", "Diplomatic", "Media"],
        avg_k=5.8, avg_lambda=3.9,
        vedanta="Vijnanamaya Kosha lower (discriminative intelligence)",
        kabbalah="Tiferet (Beauty) — the heart of the Tree",
        theosophy="Higher Mental Plane",
        buddhism="Upper Form Realm",
    ),
    5: Plane(
        id=5, name="Creative/Expressive", symbol="✦",
        description="Generative capacity, pattern-making, artistic intelligence, cultural participation.",
        domains=["Creative", "Creative Workshops", "Music Learning", "Media Engagement", "Science Exploration", "Personal Finance", "Professional Consumer", "News Literacy"],
        avg_k=4.8, avg_lambda=4.2,
        vedanta="Vijnanamaya Kosha upper (intuitive intelligence)",
        kabbalah="Chesed (Mercy) + Geburah (Severity)",
        theosophy="Causal Plane",
        buddhism="Form Realm apex",
    ),
    6: Plane(
        id=6, name="Self/Reflective", symbol="☽",
        description="Self-knowledge, psychological integration, contemplative depth, the examined life.",
        domains=["Mental Health", "Psychoeducation", "Personal", "Temporal", "Exploratory", "Self", "AI Interaction"],
        avg_k=6.2, avg_lambda=5.5,
        vedanta="Anandamaya Kosha (bliss sheath — causal body)",
        kabbalah="Binah (Understanding) + Chokmah (Wisdom)",
        theosophy="Buddhic Plane",
        buddhism="Lower Formless Realm (Arupadhatu)",
    ),
    7: Plane(
        id=7, name="Transpersonal/Unitive", symbol="✡",
        description="Identity dissolution, archetypal union, collective consciousness, meta-awareness.",
        domains=["Spiritual Practices", "Chains (Arc Sessions)", "Simulations", "Public"],
        avg_k=5.8, avg_lambda=7.6,
        vedanta="Atman / Brahman — beyond the sheaths",
        kabbalah="Kether (Crown) + the three veils of negative existence",
        theosophy="Atmic and Adic Planes",
        buddhism="Formless Realm + Nibbana",
    ),
}

# Population weights per plane (from COA): how many protocols live on each plane
PLANE_POPULATION = {1: 80, 2: 75, 3: 146, 4: 144, 5: 76, 6: 85, 7: 38}
