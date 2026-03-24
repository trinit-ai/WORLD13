"""
Battle Move System — Agent-to-Agent Protocol (Fibonacci Plume Node 8)

Core move vocabulary for battle-governed bilateral exchange.
13 move types across 6 categories with PP (Power Point) limits.

Each move type has a default PP allocation that limits how many times
it can be used in a single battle. PP overrides allow per-pack customization.
"""
import re
from enum import Enum


class MoveType(str, Enum):
    """13 move types available in battle-governed exchanges."""
    # Offensive
    ASSERT = "assert"
    COUNTER = "counter"
    PROPOSE = "propose"
    ANCHOR = "anchor"         # limited PP — high-impact positioning
    # Defensive
    CONCEDE = "concede"
    DEFER = "defer"           # pauses for trainer input
    # Neutral
    REQUEST = "request"
    # Special
    ESCALATE = "escalate"     # forces trainer decision
    WITHDRAW = "withdraw"     # trainer-authorized exit
    # Closing
    CONFIRM = "confirm"
    # Trainer-only
    SWITCH = "switch"         # type substitution
    USE_ITEM = "use_item"     # context injection
    RUN = "run"               # immediate exit


class MoveCategory(str, Enum):
    """6 move categories for classification and stall detection."""
    OFFENSIVE = "offensive"
    DEFENSIVE = "defensive"
    NEUTRAL = "neutral"
    SPECIAL = "special"
    CLOSING = "closing"
    TRAINER = "trainer"


# ─── Move Configuration ────────────────────────────────────

MOVE_CONFIG: dict[MoveType, dict] = {
    MoveType.ASSERT:   {"category": MoveCategory.OFFENSIVE, "default_pp": 15, "trainer_required": False},
    MoveType.COUNTER:  {"category": MoveCategory.OFFENSIVE, "default_pp": 10, "trainer_required": False},
    MoveType.PROPOSE:  {"category": MoveCategory.OFFENSIVE, "default_pp": 10, "trainer_required": False},
    MoveType.ANCHOR:   {"category": MoveCategory.OFFENSIVE, "default_pp": 3,  "trainer_required": False},
    MoveType.CONCEDE:  {"category": MoveCategory.DEFENSIVE, "default_pp": 8,  "trainer_required": False},
    MoveType.DEFER:    {"category": MoveCategory.DEFENSIVE, "default_pp": 5,  "trainer_required": False},
    MoveType.REQUEST:  {"category": MoveCategory.NEUTRAL,   "default_pp": 12, "trainer_required": False},
    MoveType.ESCALATE: {"category": MoveCategory.SPECIAL,   "default_pp": 3,  "trainer_required": False},
    MoveType.WITHDRAW: {"category": MoveCategory.SPECIAL,   "default_pp": 1,  "trainer_required": True},
    MoveType.CONFIRM:  {"category": MoveCategory.CLOSING,   "default_pp": 5,  "trainer_required": False},
    MoveType.SWITCH:   {"category": MoveCategory.TRAINER,   "default_pp": 3,  "trainer_required": True},
    MoveType.USE_ITEM: {"category": MoveCategory.TRAINER,   "default_pp": 5,  "trainer_required": True},
    MoveType.RUN:      {"category": MoveCategory.TRAINER,   "default_pp": 1,  "trainer_required": True},
}


# ─── PP Tracker ────────────────────────────────────────────

class PPExhausted(Exception):
    """Raised when a move's PP is depleted."""
    pass


class PPTracker:
    """Per-battle move usage tracking with PP limits."""

    def __init__(self, overrides: dict[str, int] | None = None):
        self._pp: dict[str, int] = {}
        for move_type, config in MOVE_CONFIG.items():
            self._pp[move_type.value] = config["default_pp"]
        if overrides:
            for move_str, pp_val in overrides.items():
                if move_str in self._pp:
                    self._pp[move_str] = pp_val

    def can_use(self, move: MoveType) -> bool:
        """Check if a move has remaining PP."""
        return self._pp.get(move.value, 0) > 0

    def use(self, move: MoveType) -> None:
        """Consume one PP for a move. Raises PPExhausted if depleted."""
        remaining = self._pp.get(move.value, 0)
        if remaining <= 0:
            raise PPExhausted(f"Move {move.value} has no remaining PP")
        self._pp[move.value] = remaining - 1

    def remaining(self, move: MoveType) -> int:
        """Get remaining PP for a move."""
        return self._pp.get(move.value, 0)

    def available_moves(self) -> list[MoveType]:
        """Return all move types that still have PP remaining."""
        return [
            MoveType(k) for k, v in self._pp.items()
            if v > 0
        ]

    def to_dict(self) -> dict:
        """Serialize PP state."""
        return dict(self._pp)

    @classmethod
    def from_dict(cls, d: dict) -> "PPTracker":
        """Reconstruct PPTracker from serialized state."""
        tracker = cls.__new__(cls)
        tracker._pp = dict(d)
        return tracker


# ─── Helper Functions ──────────────────────────────────────

_MOVE_MARKER_RE = re.compile(r"\[MOVE:([\w]+)\]")


def is_trainer_move(move: MoveType) -> bool:
    """Check if a move requires trainer authorization."""
    return MOVE_CONFIG[move]["trainer_required"]


def get_category(move: MoveType) -> MoveCategory:
    """Get the category for a move type."""
    return MOVE_CONFIG[move]["category"]


def parse_move_marker(text: str) -> MoveType | None:
    """Extract [MOVE:type] signal from text. Returns None if not found or invalid."""
    match = _MOVE_MARKER_RE.search(text)
    if not match:
        return None
    try:
        return MoveType(match.group(1).lower())
    except ValueError:
        return None


def format_move_marker(move: MoveType) -> str:
    """Produce [MOVE:type] string for embedding in responses."""
    return f"[MOVE:{move.value}]"
