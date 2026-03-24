"""
Battle State — Agent-to-Agent Protocol (Fibonacci Plume Node 8)

Dataclasses and enums for battle lifecycle management.
Tracks authority boundaries, turn history, transport state, and outcomes.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from battle_moves import (
    MoveType, MoveCategory, MOVE_CONFIG,
    PPTracker, get_category,
)


class BattlePhase(str, Enum):
    """5-phase turn structure for battle processing."""
    RECEIVE = "receive"       # validate move marker, parse counterparty move
    EVALUATE = "evaluate"     # check authority boundary, check PP
    SELECT = "select"         # validate move availability (PP, category)
    GENERATE = "generate"     # attach move marker to content
    TRANSMIT = "transmit"     # record turn, update state, check stall


class BattleOutcome(str, Enum):
    """6 victory conditions for battle resolution."""
    AGREEMENT = "agreement"           # terms within boundaries, trainer confirms
    WITHDRAWAL = "withdrawal"         # trainer stops
    ESCALATION = "escalation"         # beyond authority
    HUMAN_TO_HUMAN = "human_to_human" # mutual escalation
    TIMEOUT = "timeout"               # turn/time limit
    STALEMATE = "stalemate"           # stall detector


@dataclass
class AuthorityBoundary:
    """Defines the limits of what an Ambassador can agree to without trainer approval."""
    max_concession_value: float | None = None
    min_acceptable_terms: dict = field(default_factory=dict)
    protected_information: list[str] = field(default_factory=list)
    shareable_information: list[str] = field(default_factory=list)
    auto_authorize_moves: list[str] = field(
        default_factory=lambda: ["assert", "counter", "request", "propose", "confirm"]
    )
    trainer_required_moves: list[str] = field(
        default_factory=lambda: ["withdraw", "switch", "use_item", "run"]
    )
    escalate_if: dict = field(default_factory=dict)

    def allows_move(self, move: MoveType) -> bool:
        """Check if a move is auto-authorized (does not require trainer)."""
        if move.value in self.auto_authorize_moves:
            return True
        if move.value in self.trainer_required_moves:
            return False
        # Default: auto-authorize non-trainer moves
        return not MOVE_CONFIG[move]["trainer_required"]

    def to_dict(self) -> dict:
        return {
            "max_concession_value": self.max_concession_value,
            "min_acceptable_terms": self.min_acceptable_terms,
            "protected_information": self.protected_information,
            "shareable_information": self.shareable_information,
            "auto_authorize_moves": self.auto_authorize_moves,
            "trainer_required_moves": self.trainer_required_moves,
            "escalate_if": self.escalate_if,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AuthorityBoundary":
        return cls(
            max_concession_value=d.get("max_concession_value"),
            min_acceptable_terms=d.get("min_acceptable_terms", {}),
            protected_information=d.get("protected_information", []),
            shareable_information=d.get("shareable_information", []),
            auto_authorize_moves=d.get(
                "auto_authorize_moves",
                ["assert", "counter", "request", "propose", "confirm"],
            ),
            trainer_required_moves=d.get(
                "trainer_required_moves",
                ["withdraw", "switch", "use_item", "run"],
            ),
            escalate_if=d.get("escalate_if", {}),
        )


@dataclass
class BattleTurn:
    """Record of a single turn in a battle exchange."""
    turn_number: int
    party: str                    # "initiator" | "responder"
    move_type: MoveType
    content: str
    phase: BattlePhase = BattlePhase.TRANSMIT  # final phase when recorded
    timestamp: str = ""           # ISO 8601
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "turn_number": self.turn_number,
            "party": self.party,
            "move_type": self.move_type.value,
            "move_category": get_category(self.move_type).value,
            "content": self.content,
            "phase": self.phase.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class BattleState:
    """Complete state for a battle-governed bilateral exchange."""
    battle_id: str
    exchange_id: str              # links to Ambassador exchange
    initiator_address_id: str
    responder_address_id: str
    authority_boundary: AuthorityBoundary
    pp_tracker: PPTracker
    turns: list[BattleTurn] = field(default_factory=list)
    outcome: BattleOutcome | None = None
    transport: str = "play"       # play | pause | stop — simple string
    stall_count: int = 0
    stall_threshold: int = 3      # consecutive same-category moves before stall
    max_turns: int = 50
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    user_id: str | None = None

    @property
    def current_turn(self) -> int:
        """Current turn number (0-indexed count of recorded turns)."""
        return len(self.turns)

    @property
    def is_active(self) -> bool:
        """Battle is active if transport is play and no outcome set."""
        return self.transport == "play" and self.outcome is None

    @property
    def last_move_category(self) -> MoveCategory | None:
        """Category of the most recent turn's move, or None if no turns."""
        if not self.turns:
            return None
        return get_category(self.turns[-1].move_type)

    def to_dict(self) -> dict:
        return {
            "battle_id": self.battle_id,
            "exchange_id": self.exchange_id,
            "initiator_address_id": self.initiator_address_id,
            "responder_address_id": self.responder_address_id,
            "authority_boundary": self.authority_boundary.to_dict(),
            "pp_state": self.pp_tracker.to_dict(),
            "turns": [t.to_dict() for t in self.turns],
            "outcome": self.outcome.value if self.outcome else None,
            "transport": self.transport,
            "stall_count": self.stall_count,
            "stall_threshold": self.stall_threshold,
            "max_turns": self.max_turns,
            "turn_count": self.current_turn,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BattleState":
        boundary = AuthorityBoundary.from_dict(d.get("authority_boundary", {}))
        pp = PPTracker.from_dict(d["pp_state"]) if "pp_state" in d else PPTracker()
        turns = []
        for t in d.get("turns", []):
            turns.append(BattleTurn(
                turn_number=t["turn_number"],
                party=t["party"],
                move_type=MoveType(t["move_type"]),
                content=t.get("content", ""),
                phase=BattlePhase(t.get("phase", "transmit")),
                timestamp=t.get("timestamp", ""),
                metadata=t.get("metadata", {}),
            ))
        outcome = BattleOutcome(d["outcome"]) if d.get("outcome") else None
        return cls(
            battle_id=d["battle_id"],
            exchange_id=d["exchange_id"],
            initiator_address_id=d["initiator_address_id"],
            responder_address_id=d["responder_address_id"],
            authority_boundary=boundary,
            pp_tracker=pp,
            turns=turns,
            outcome=outcome,
            transport=d.get("transport", "play"),
            stall_count=d.get("stall_count", 0),
            stall_threshold=d.get("stall_threshold", 3),
            max_turns=d.get("max_turns", 50),
            metadata=d.get("metadata", {}),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            user_id=d.get("user_id"),
        )
