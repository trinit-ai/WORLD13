"""
engine/archetypes.py — The 13 Archetypal Basis Functions (ARE).

Each archetype is a stable attractor basin in karmic phase space,
anchored to Tarot, Jungian, and Kabbalistic coordinates.
"""

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
    "SOV": Archetype(
        "SOV", "Sovereign", "IV Emperor", "Self / Persona", "Kether",
        "Structures order; accrues power karma",
        "Release of control; service beyond position",
        5.8, 3.5, 3, "LP-05",
    ),
    "BLD": Archetype(
        "BLD", "Builder", "III Empress", "Mother / Anima", "Malkuth",
        "Manifests reality; accrues possession karma",
        "Offering the work; non-attachment to creation",
        4.8, 2.8, 1, "LP-01",
    ),
    "SKR": Archetype(
        "SKR", "Seeker", "0 Fool", "Hero", "Chokmah",
        "Seeks experience; accrues curiosity karma",
        "Arriving — recognizing destination was always now",
        5.2, 3.6, 2, "LP-02",
    ),
    "WIT": Archetype(
        "WIT", "Witness", "II High Priestess", "Anima / Self", "Binah",
        "Receives and holds; accrues observation karma",
        "Pure presence; the watcher dissolving into watched",
        5.7, 6.8, 6, "LP-06",
    ),
    "WAR": Archetype(
        "WAR", "Warrior", "VII Chariot", "Shadow", "Geburah",
        "Defends and contests; accrues conflict karma",
        "Laying down arms; protection through presence",
        6.1, 3.2, 2, "LP-05",
    ),
    "HLR": Archetype(
        "HLR", "Healer", "XVII Star", "Wise Elder", "Chesed",
        "Heals others; lightest karmic weight of all archetypes",
        "Healing the self; the wound as the gift",
        4.8, 5.5, 4, "LP-04",
    ),
    "TRN": Archetype(
        "TRN", "Transmuter", "XIII Death", "Self", "Tiferet",
        "Crosses thresholds; accrues transformation karma",
        "The last crossing — no more cycles to enter",
        7.2, 4.8, 5, "LP-07",
    ),
    "TRK": Archetype(
        "TRK", "Trickster", "I Magician", "Trickster", "Hod",
        "Subverts structure; accrues creative-chaos karma",
        "Becoming still; the trick that didn't need playing",
        5.4, 4.2, 3, "LP-08",
    ),
    "LVR": Archetype(
        "LVR", "Lover", "VI The Lovers", "Animus/Anima", "Netzach",
        "Bonds and seeks union; accrues attachment karma",
        "Love without object; agape beyond eros",
        6.0, 4.0, 2, "LP-02",
    ),
    "TCH": Archetype(
        "TCH", "Teacher", "V Hierophant", "Wise Elder", "Binah",
        "Transmits knowledge; accrues authority karma",
        "Learning from students; teaching by absence",
        5.1, 4.5, 4, "LP-01",
    ),
    "JDG": Archetype(
        "JDG", "Judge", "VIII Justice", "Shadow / Self", "Hod + Geburah",
        "Adjudicates; accrues judgment karma",
        "Mercy without compromise; law fulfilling itself",
        6.3, 3.8, 3, "LP-03",
    ),
    "MYS": Archetype(
        "MYS", "Mystic", "IX Hermit", "Self", "Chokmah",
        "Withdraws and illumines; accrues solitude karma",
        "Return: mystic who enters the marketplace",
        5.5, 7.2, 6, "LP-06",
    ),
    "WLD": Archetype(
        "WLD", "World", "XXI The World", "Self (integrated)", "Kether + Malkuth",
        "Completes cycle; K(x) = 0 by definition",
        "The World IS the liberation attractor",
        0.0, 10.0, 7, "LP-01",
    ),
}

ARCHETYPE_CODES = list(ARCHETYPES.keys())
