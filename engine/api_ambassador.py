"""
Ambassador API Endpoints

REST endpoints for address-based AI representation. All endpoints require
authentication via existing auth.py dependencies. Write operations are
role-gated (admin for addresses/protocols, editor for routing rules).

Registered by `register_ambassador_endpoints(app, ambassador_service)`.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, require_role, UserProfile
from ambassador_service import AmbassadorService

logger = logging.getLogger("tmos13.ambassador")


# ─── Pydantic Request/Response Models ──────────────────

class CreateAddressRequest(BaseModel):
    handle: str
    domain: str = "tmos13.ai"
    display_name: Optional[str] = None
    settings: Optional[dict] = None


class UpdateAddressRequest(BaseModel):
    handle: Optional[str] = None
    domain: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[dict] = None


class AddressResponse(BaseModel):
    id: str
    handle: str
    domain: str
    owner_id: str
    display_name: Optional[str]
    status: str
    default_protocol_id: Optional[str]
    settings: dict
    full_address: str
    created_at: Optional[str]
    updated_at: Optional[str]


class CreateProtocolRequest(BaseModel):
    pack_id: str
    name: str
    type: str = "receive"
    boundaries: Optional[dict] = None
    personality: Optional[dict] = None


class UpdateProtocolRequest(BaseModel):
    name: Optional[str] = None
    pack_id: Optional[str] = None
    type: Optional[str] = None
    boundaries: Optional[dict] = None
    personality: Optional[dict] = None
    active: Optional[bool] = None


class ProtocolResponse(BaseModel):
    id: str
    address_id: str
    pack_id: str
    name: str
    type: str
    boundaries: dict
    personality: dict
    active: bool
    created_at: Optional[str]


class CreateRoutingRuleRequest(BaseModel):
    protocol_id: str
    priority: int = 100
    match_type: str = "default"
    match_value: Optional[str] = None


class UpdateRoutingRuleRequest(BaseModel):
    protocol_id: Optional[str] = None
    priority: Optional[int] = None
    match_type: Optional[str] = None
    match_value: Optional[str] = None
    active: Optional[bool] = None


class RoutingRuleResponse(BaseModel):
    id: str
    address_id: str
    protocol_id: str
    priority: int
    match_type: str
    match_value: Optional[str]
    active: bool
    created_at: Optional[str]


class CreateExchangeRequest(BaseModel):
    protocol_id: Optional[str] = None
    direction: str = "inbound"
    channel: str = "portal"
    counterparty_type: Optional[str] = None
    counterparty_identifier: Optional[str] = None
    counterparty_name: Optional[str] = None


class ExchangeResponse(BaseModel):
    id: str
    address_id: str
    protocol_id: Optional[str]
    direction: str
    channel: str
    status: str
    counterparty_type: Optional[str]
    counterparty_identifier: Optional[str]
    counterparty_name: Optional[str]
    intent_detected: Optional[str]
    intent_confidence: Optional[float]
    intent_summary: Optional[str]
    state: dict
    created_at: Optional[str]
    updated_at: Optional[str]
    resolved_at: Optional[str]


class ExchangeListResponse(BaseModel):
    exchanges: list[ExchangeResponse]
    count: int


class CreateTurnRequest(BaseModel):
    direction: str = "inbound"
    sender_type: str = "human"
    content_raw: Optional[str] = None
    content_parsed: Optional[dict] = None
    content_response: Optional[str] = None
    cartridge: Optional[str] = None
    state_changes: Optional[dict] = None
    latency_ms: Optional[int] = None


class TurnResponse(BaseModel):
    id: str
    exchange_id: str
    sequence: int
    direction: str
    sender_type: str
    content_raw: Optional[str]
    content_parsed: Optional[dict]
    content_response: Optional[str]
    cartridge: Optional[str]
    state_changes: Optional[dict]
    latency_ms: Optional[int]
    created_at: Optional[str]


class ResolveExchangeRequest(BaseModel):
    resolution_type: str
    summary: str
    structured_data: Optional[dict] = None
    actions_taken: Optional[list] = None
    requires_review: bool = False


class ResolutionResponse(BaseModel):
    id: str
    exchange_id: str
    type: str
    summary: str
    structured_data: dict
    actions_taken: list
    requires_review: bool
    owner_reviewed: bool
    created_at: Optional[str]


# ─── Helpers ──────────────────────────────────────────────

def _ts(dt) -> Optional[str]:
    """Convert datetime to ISO string, or None."""
    return dt.isoformat() if dt else None


def _address_response(addr) -> AddressResponse:
    return AddressResponse(
        id=addr.id,
        handle=addr.handle,
        domain=addr.domain,
        owner_id=addr.owner_id,
        display_name=addr.display_name,
        status=addr.status.value if hasattr(addr.status, "value") else addr.status,
        default_protocol_id=addr.default_protocol_id,
        settings=addr.settings,
        full_address=addr.full,
        created_at=_ts(addr.created_at),
        updated_at=_ts(addr.updated_at),
    )


def _protocol_response(proto) -> ProtocolResponse:
    return ProtocolResponse(
        id=proto.id,
        address_id=proto.address_id,
        pack_id=proto.pack_id,
        name=proto.name,
        type=proto.type.value if hasattr(proto.type, "value") else proto.type,
        boundaries=proto.boundaries,
        personality=proto.personality,
        active=proto.active,
        created_at=_ts(proto.created_at),
    )


def _rule_response(rule) -> RoutingRuleResponse:
    return RoutingRuleResponse(
        id=rule.id,
        address_id=rule.address_id,
        protocol_id=rule.protocol_id,
        priority=rule.priority,
        match_type=rule.match_type.value if hasattr(rule.match_type, "value") else rule.match_type,
        match_value=rule.match_value,
        active=rule.active,
        created_at=_ts(rule.created_at),
    )


def _exchange_response(ex) -> ExchangeResponse:
    return ExchangeResponse(
        id=ex.id,
        address_id=ex.address_id,
        protocol_id=ex.protocol_id,
        direction=ex.direction.value if hasattr(ex.direction, "value") else ex.direction,
        channel=ex.channel.value if hasattr(ex.channel, "value") else ex.channel,
        status=ex.status.value if hasattr(ex.status, "value") else ex.status,
        counterparty_type=ex.counterparty_type.value if ex.counterparty_type and hasattr(ex.counterparty_type, "value") else ex.counterparty_type,
        counterparty_identifier=ex.counterparty_identifier,
        counterparty_name=ex.counterparty_name,
        intent_detected=ex.intent_detected,
        intent_confidence=ex.intent_confidence,
        intent_summary=ex.intent_summary,
        state=ex.state,
        created_at=_ts(ex.created_at),
        updated_at=_ts(ex.updated_at),
        resolved_at=_ts(ex.resolved_at),
    )


def _turn_response(turn) -> TurnResponse:
    return TurnResponse(
        id=turn.id,
        exchange_id=turn.exchange_id,
        sequence=turn.sequence,
        direction=turn.direction.value if hasattr(turn.direction, "value") else turn.direction,
        sender_type=turn.sender_type.value if hasattr(turn.sender_type, "value") else turn.sender_type,
        content_raw=turn.content_raw,
        content_parsed=turn.content_parsed,
        content_response=turn.content_response,
        cartridge=turn.cartridge,
        state_changes=turn.state_changes,
        latency_ms=turn.latency_ms,
        created_at=_ts(turn.created_at),
    )


def _resolution_response(res) -> ResolutionResponse:
    return ResolutionResponse(
        id=res.id,
        exchange_id=res.exchange_id,
        type=res.type,
        summary=res.summary,
        structured_data=res.structured_data,
        actions_taken=res.actions_taken,
        requires_review=res.requires_review,
        owner_reviewed=res.owner_reviewed,
        created_at=_ts(res.created_at),
    )


def _verify_owner(user: UserProfile, address, service: AmbassadorService):
    """Verify user owns the address. Admin bypasses this check."""
    if user.is_at_least("admin"):
        return
    if address.owner_id != user.user_id:
        raise HTTPException(403, "You do not own this address")


def _get_address_verified(address_id: str, user: UserProfile, service: AmbassadorService):
    """Get an address and verify ownership."""
    address = service.get_address(address_id)
    _verify_owner(user, address, service)
    return address


# ─── Endpoint Registration ────────────────────────────────

def register_ambassador_endpoints(app, ambassador_service: AmbassadorService):
    """Register all /ambassador/* endpoints on the FastAPI app."""

    # ─── Addresses ────────────────────────────────────────

    @app.post("/ambassador/addresses", response_model=AddressResponse, tags=["ambassador"])
    async def create_address(
        req: CreateAddressRequest,
        user: UserProfile = Depends(require_role("admin")),
    ):
        """Create a new ambassador address."""
        addr = ambassador_service.create_address(
            owner_id=user.user_id,
            handle=req.handle,
            domain=req.domain,
            display_name=req.display_name,
            settings=req.settings,
        )
        return _address_response(addr)

    @app.get("/ambassador/addresses", response_model=list[AddressResponse], tags=["ambassador"])
    async def list_addresses(user: UserProfile = Depends(require_auth)):
        """List addresses owned by the authenticated user."""
        addresses = ambassador_service.list_addresses(user.user_id)
        return [_address_response(a) for a in addresses]

    @app.get("/ambassador/addresses/{address_id}", response_model=AddressResponse, tags=["ambassador"])
    async def get_address(address_id: str, user: UserProfile = Depends(require_auth)):
        """Get an address by ID (owner only)."""
        addr = _get_address_verified(address_id, user, ambassador_service)
        return _address_response(addr)

    @app.patch("/ambassador/addresses/{address_id}", response_model=AddressResponse, tags=["ambassador"])
    async def update_address(
        address_id: str,
        req: UpdateAddressRequest,
        user: UserProfile = Depends(require_role("admin")),
    ):
        """Update an address."""
        _get_address_verified(address_id, user, ambassador_service)
        kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
        addr = ambassador_service.update_address(address_id, **kwargs)
        return _address_response(addr)

    @app.delete("/ambassador/addresses/{address_id}", tags=["ambassador"])
    async def delete_address(
        address_id: str,
        user: UserProfile = Depends(require_role("admin")),
    ):
        """Delete an address and all associated data."""
        _get_address_verified(address_id, user, ambassador_service)
        ambassador_service.delete_address(address_id)
        return {"deleted": True, "address_id": address_id}

    # ─── Protocols ────────────────────────────────────────

    @app.post("/ambassador/addresses/{address_id}/protocols", response_model=ProtocolResponse, tags=["ambassador"])
    async def create_protocol(
        address_id: str,
        req: CreateProtocolRequest,
        user: UserProfile = Depends(require_role("admin")),
    ):
        """Create a protocol for an address."""
        _get_address_verified(address_id, user, ambassador_service)
        proto = ambassador_service.create_protocol(
            address_id=address_id,
            pack_id=req.pack_id,
            name=req.name,
            type=req.type,
            boundaries=req.boundaries,
            personality=req.personality,
        )
        return _protocol_response(proto)

    @app.get("/ambassador/addresses/{address_id}/protocols", response_model=list[ProtocolResponse], tags=["ambassador"])
    async def list_protocols(address_id: str, user: UserProfile = Depends(require_auth)):
        """List protocols for an address."""
        _get_address_verified(address_id, user, ambassador_service)
        protocols = ambassador_service.list_protocols(address_id)
        return [_protocol_response(p) for p in protocols]

    @app.patch("/ambassador/protocols/{protocol_id}", response_model=ProtocolResponse, tags=["ambassador"])
    async def update_protocol(
        protocol_id: str,
        req: UpdateProtocolRequest,
        user: UserProfile = Depends(require_role("admin")),
    ):
        """Update a protocol."""
        kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
        proto = ambassador_service.update_protocol(protocol_id, **kwargs)
        return _protocol_response(proto)

    @app.delete("/ambassador/protocols/{protocol_id}", tags=["ambassador"])
    async def delete_protocol(
        protocol_id: str,
        user: UserProfile = Depends(require_role("admin")),
    ):
        """Delete a protocol."""
        ambassador_service.delete_protocol(protocol_id)
        return {"deleted": True, "protocol_id": protocol_id}

    # ─── Routing Rules ────────────────────────────────────

    @app.post("/ambassador/addresses/{address_id}/rules", response_model=RoutingRuleResponse, tags=["ambassador"])
    async def create_routing_rule(
        address_id: str,
        req: CreateRoutingRuleRequest,
        user: UserProfile = Depends(require_role("editor")),
    ):
        """Create a routing rule for an address."""
        _get_address_verified(address_id, user, ambassador_service)
        rule = ambassador_service.create_routing_rule(
            address_id=address_id,
            protocol_id=req.protocol_id,
            priority=req.priority,
            match_type=req.match_type,
            match_value=req.match_value,
        )
        return _rule_response(rule)

    @app.get("/ambassador/addresses/{address_id}/rules", response_model=list[RoutingRuleResponse], tags=["ambassador"])
    async def list_routing_rules(address_id: str, user: UserProfile = Depends(require_auth)):
        """List routing rules for an address."""
        _get_address_verified(address_id, user, ambassador_service)
        rules = ambassador_service.list_routing_rules(address_id)
        return [_rule_response(r) for r in rules]

    @app.patch("/ambassador/rules/{rule_id}", response_model=RoutingRuleResponse, tags=["ambassador"])
    async def update_routing_rule(
        rule_id: str,
        req: UpdateRoutingRuleRequest,
        user: UserProfile = Depends(require_role("editor")),
    ):
        """Update a routing rule."""
        kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
        rule = ambassador_service.update_routing_rule(rule_id, **kwargs)
        return _rule_response(rule)

    @app.delete("/ambassador/rules/{rule_id}", tags=["ambassador"])
    async def delete_routing_rule(
        rule_id: str,
        user: UserProfile = Depends(require_role("editor")),
    ):
        """Delete a routing rule."""
        ambassador_service.delete_routing_rule(rule_id)
        return {"deleted": True, "rule_id": rule_id}

    # ─── Exchanges ────────────────────────────────────────

    @app.post("/ambassador/addresses/{address_id}/exchanges", response_model=ExchangeResponse, tags=["ambassador"])
    async def create_exchange(
        address_id: str,
        req: CreateExchangeRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Create a new exchange for an address."""
        _get_address_verified(address_id, user, ambassador_service)
        ex = ambassador_service.create_exchange(
            address_id=address_id,
            protocol_id=req.protocol_id,
            direction=req.direction,
            channel=req.channel,
            counterparty_type=req.counterparty_type,
            counterparty_identifier=req.counterparty_identifier,
            counterparty_name=req.counterparty_name,
        )
        return _exchange_response(ex)

    @app.get("/ambassador/addresses/{address_id}/exchanges", response_model=ExchangeListResponse, tags=["ambassador"])
    async def list_exchanges(
        address_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        user: UserProfile = Depends(require_auth),
    ):
        """List exchanges for an address with optional status filter."""
        _get_address_verified(address_id, user, ambassador_service)
        exchanges = ambassador_service.list_exchanges(address_id, status=status, limit=limit)
        return ExchangeListResponse(
            exchanges=[_exchange_response(e) for e in exchanges],
            count=len(exchanges),
        )

    @app.get("/ambassador/exchanges/{exchange_id}", response_model=ExchangeResponse, tags=["ambassador"])
    async def get_exchange(exchange_id: str, user: UserProfile = Depends(require_auth)):
        """Get an exchange by ID."""
        ex = ambassador_service.get_exchange(exchange_id)
        # Verify owner of the parent address
        _get_address_verified(ex.address_id, user, ambassador_service)
        return _exchange_response(ex)

    @app.get("/ambassador/exchanges/{exchange_id}/turns", response_model=list[TurnResponse], tags=["ambassador"])
    async def get_turns(exchange_id: str, user: UserProfile = Depends(require_auth)):
        """Get all turns for an exchange."""
        ex = ambassador_service.get_exchange(exchange_id)
        _get_address_verified(ex.address_id, user, ambassador_service)
        turns = ambassador_service.get_turns(exchange_id)
        return [_turn_response(t) for t in turns]

    @app.post("/ambassador/exchanges/{exchange_id}/turns", response_model=TurnResponse, tags=["ambassador"])
    async def add_turn(
        exchange_id: str,
        req: CreateTurnRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Add a turn to an exchange."""
        ex = ambassador_service.get_exchange(exchange_id)
        _get_address_verified(ex.address_id, user, ambassador_service)
        turn = ambassador_service.add_turn(
            exchange_id=exchange_id,
            direction=req.direction,
            sender_type=req.sender_type,
            content_raw=req.content_raw,
            content_parsed=req.content_parsed,
            content_response=req.content_response,
            cartridge=req.cartridge,
            state_changes=req.state_changes,
            latency_ms=req.latency_ms,
        )
        return _turn_response(turn)

    @app.post("/ambassador/exchanges/{exchange_id}/resolve", response_model=ResolutionResponse, tags=["ambassador"])
    async def resolve_exchange(
        exchange_id: str,
        req: ResolveExchangeRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Resolve an exchange with a structured outcome."""
        ex = ambassador_service.get_exchange(exchange_id)
        _get_address_verified(ex.address_id, user, ambassador_service)
        resolution = ambassador_service.resolve_exchange(
            exchange_id=exchange_id,
            resolution_type=req.resolution_type,
            summary=req.summary,
            structured_data=req.structured_data,
            actions_taken=req.actions_taken,
            requires_review=req.requires_review,
        )
        return _resolution_response(resolution)

    # ─── Resolutions ──────────────────────────────────────

    @app.get("/ambassador/exchanges/{exchange_id}/resolution", response_model=ResolutionResponse, tags=["ambassador"])
    async def get_resolution(exchange_id: str, user: UserProfile = Depends(require_auth)):
        """Get the resolution for an exchange."""
        ex = ambassador_service.get_exchange(exchange_id)
        _get_address_verified(ex.address_id, user, ambassador_service)
        resolution = ambassador_service.get_resolution(exchange_id)
        return _resolution_response(resolution)

    logger.info("Ambassador endpoints registered: /ambassador/*")
