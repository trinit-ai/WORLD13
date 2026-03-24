"""
Ambassador — Address-based AI representation layer.

Tentative foundation. Does not replace existing session/pack system.

Core concept: an email address (e.g., rob@tmos13.ai) becomes a portal
to an AI Ambassador that processes inbound communication using pack
protocols and produces structured resolutions.

Current mapping from existing system:
  session   → exchange
  pack      → protocol
  cartridge → routing rule target
  transcript → turn log
  (new)     → resolution (structured outcome)

This module defines the foundational types only. No business logic,
no API endpoints, no wiring. The interfaces will stabilize before
tests and service layers are added.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum


# ─── Enums ───────────────────────────────────────────────────────

class AddressStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    AWAY = "away"
    CLOSED = "closed"


class ExchangeStatus(str, Enum):
    ACTIVE = "active"
    PENDING_HUMAN = "pending_human"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExchangeDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ExchangeChannel(str, Enum):
    EMAIL = "email"
    PORTAL = "portal"
    AGENT = "agent"
    API = "api"


class CounterpartyType(str, Enum):
    HUMAN = "human"
    AMBASSADOR = "ambassador"


class ProtocolType(str, Enum):
    RECEIVE = "receive"
    SEND = "send"
    BILATERAL = "bilateral"


class MatchType(str, Enum):
    KEYWORD = "keyword"
    SENDER_DOMAIN = "sender_domain"
    INTENT = "intent"
    REGEX = "regex"
    DEFAULT = "default"


class ResolutionType(str, Enum):
    """Common resolution types. Packs may define additional types."""
    MEETING_BOOKED = "meeting_booked"
    LEAD_QUALIFIED = "lead_qualified"
    INFO_PROVIDED = "info_provided"
    REQUEST_DECLINED = "request_declined"
    ESCALATED = "escalated"
    SPAM_FILTERED = "spam_filtered"


# ─── Data Classes ────────────────────────────────────────────────

@dataclass
class Address:
    """A public-facing portal (e.g., rob@tmos13.ai) bound to an owner."""
    id: str
    handle: str
    domain: str = "tmos13.ai"
    owner_id: str = ""
    display_name: Optional[str] = None
    status: AddressStatus = AddressStatus.ACTIVE
    default_protocol_id: Optional[str] = None
    settings: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def full(self) -> str:
        """Full address string, e.g. rob@tmos13.ai."""
        return f"{self.handle}@{self.domain}"


@dataclass
class Protocol:
    """A pack configured with boundaries and personality for an address."""
    id: str
    address_id: str
    pack_id: str
    name: str
    type: ProtocolType = ProtocolType.RECEIVE
    boundaries: dict = field(default_factory=dict)
    personality: dict = field(default_factory=dict)
    active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class RoutingRule:
    """Maps inbound communication patterns to protocols."""
    id: str
    address_id: str
    protocol_id: str
    priority: int = 100
    match_type: MatchType = MatchType.DEFAULT
    match_value: Optional[str] = None
    active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Exchange:
    """A single directional interaction with a counterparty."""
    id: str
    address_id: str
    protocol_id: Optional[str] = None
    direction: ExchangeDirection = ExchangeDirection.INBOUND
    channel: ExchangeChannel = ExchangeChannel.PORTAL
    status: ExchangeStatus = ExchangeStatus.ACTIVE
    counterparty_type: Optional[CounterpartyType] = None
    counterparty_identifier: Optional[str] = None
    counterparty_name: Optional[str] = None
    counterparty_ambassador_id: Optional[str] = None
    intent_detected: Optional[str] = None
    intent_confidence: Optional[float] = None
    intent_summary: Optional[str] = None
    state: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class ExchangeTurn:
    """A single turn within an exchange (message + response)."""
    id: str
    exchange_id: str
    sequence: int
    direction: ExchangeDirection = ExchangeDirection.INBOUND
    sender_type: CounterpartyType = CounterpartyType.HUMAN
    content_raw: Optional[str] = None
    content_parsed: Optional[dict] = None
    content_response: Optional[str] = None
    cartridge: Optional[str] = None
    state_changes: Optional[dict] = None
    latency_ms: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class Resolution:
    """Structured outcome of an exchange — what was decided, not what was said."""
    id: str
    exchange_id: str
    type: str
    summary: str
    structured_data: dict = field(default_factory=dict)
    actions_taken: list = field(default_factory=list)
    requires_review: bool = False
    owner_reviewed: bool = False
    created_at: Optional[datetime] = None
