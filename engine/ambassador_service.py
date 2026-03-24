"""
Ambassador Service Layer

Connects Ambassador types (engine/ambassador.py) to Supabase tables
(supabase/migrations/004_ambassador.sql). Provides CRUD for addresses,
protocols, routing rules, and exchange lifecycle management.

Follows the same singleton + init pattern as engine/auth.py.
"""
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from ambassador import (
    Address, AddressStatus,
    Protocol, ProtocolType,
    RoutingRule, MatchType,
    Exchange, ExchangeStatus, ExchangeDirection, ExchangeChannel, CounterpartyType,
    ExchangeTurn,
    Resolution,
)

logger = logging.getLogger("tmos13.ambassador")


class AmbassadorService:
    """Service layer for Ambassador address-based AI representation."""

    def __init__(self, supabase_client):
        self._db = supabase_client
        logger.info("Ambassador service initialized")

    # ─── Address CRUD ─────────────────────────────────────

    def create_address(
        self,
        owner_id: str,
        handle: str,
        domain: str = "tmos13.ai",
        display_name: Optional[str] = None,
        settings: Optional[dict] = None,
    ) -> Address:
        """Create a new ambassador address."""
        if not handle or not handle.strip():
            raise HTTPException(400, "Handle is required")

        # Check for duplicate handle+domain
        existing = (
            self._db.table("addresses")
            .select("id")
            .eq("handle", handle)
            .eq("domain", domain)
            .execute()
        )
        if existing.data:
            raise HTTPException(400, f"Address {handle}@{domain} already exists")

        address_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": address_id,
            "owner_id": owner_id,
            "handle": handle,
            "domain": domain,
            "display_name": display_name,
            "status": AddressStatus.ACTIVE.value,
            "settings": settings or {},
            "created_at": now,
            "updated_at": now,
        }

        result = self._db.table("addresses").insert(row).execute()
        logger.info(f"Address created: {handle}@{domain} (id={address_id})")
        return self._row_to_address(result.data[0])

    def get_address(self, address_id: str) -> Address:
        """Get an address by ID."""
        result = (
            self._db.table("addresses")
            .select("*")
            .eq("id", address_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(404, f"Address {address_id} not found")
        return self._row_to_address(result.data[0])

    def get_address_by_handle(self, handle: str, domain: str = "tmos13.ai") -> Address:
        """Get an address by handle and domain."""
        result = (
            self._db.table("addresses")
            .select("*")
            .eq("handle", handle)
            .eq("domain", domain)
            .execute()
        )
        if not result.data:
            raise HTTPException(404, f"Address {handle}@{domain} not found")
        return self._row_to_address(result.data[0])

    def check_address_availability(self, address_id: str) -> tuple[bool, Optional[str]]:
        """Check if an address is available for new exchanges.

        Returns (available: bool, fallback_message: Optional[str]).
        If not available, fallback_message is the configured auto-response.
        """
        address = self.get_address(address_id)

        if address.status == AddressStatus.ACTIVE:
            return True, None

        if address.status == AddressStatus.CLOSED:
            return False, "This address is no longer accepting exchanges."

        # Paused or away — check settings for custom messages
        settings = address.settings or {}
        if address.status == AddressStatus.PAUSED:
            msg = settings.get("paused_message",
                               "This address is temporarily paused. Your message has been queued.")
            return False, msg

        if address.status == AddressStatus.AWAY:
            msg = settings.get("away_message",
                               "The owner of this address is currently away. Your message has been queued.")
            return False, msg

        return True, None

    def list_addresses(self, owner_id: str) -> list[Address]:
        """List all addresses for an owner."""
        result = (
            self._db.table("addresses")
            .select("*")
            .eq("owner_id", owner_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._row_to_address(r) for r in result.data]

    def update_address(self, address_id: str, changed_by: str = None, **kwargs) -> Address:
        """Update an address. Accepts any Address field except id."""
        # Verify exists
        current = self.get_address(address_id)

        update_data = {}
        allowed = {"handle", "domain", "display_name", "status", "settings", "default_protocol_id"}
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                if key == "status" and isinstance(value, AddressStatus):
                    value = value.value
                update_data[key] = value

        if not update_data:
            return self.get_address(address_id)

        # Audit status transitions
        if "status" in update_data:
            new_status = update_data["status"]
            old_status = current.status.value if isinstance(current.status, AddressStatus) else current.status
            if new_status != old_status:
                try:
                    self._db.table("address_audit_log").insert({
                        "address_id": address_id,
                        "old_status": old_status,
                        "new_status": new_status,
                        "changed_by": changed_by,
                    }).execute()
                except Exception as e:
                    logger.warning("Address audit log write failed (non-fatal): %s", e)

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = (
            self._db.table("addresses")
            .update(update_data)
            .eq("id", address_id)
            .execute()
        )
        logger.info(f"Address updated: {address_id}")
        return self._row_to_address(result.data[0])

    def delete_address(self, address_id: str) -> None:
        """Delete an address and all associated data (cascading)."""
        # Verify exists
        self.get_address(address_id)
        self._db.table("addresses").delete().eq("id", address_id).execute()
        logger.info(f"Address deleted: {address_id}")

    # ─── Protocol CRUD ────────────────────────────────────

    def create_protocol(
        self,
        address_id: str,
        pack_id: str,
        name: str,
        type: str = "receive",
        boundaries: Optional[dict] = None,
        personality: Optional[dict] = None,
    ) -> Protocol:
        """Create a new protocol for an address."""
        # Verify address exists
        self.get_address(address_id)

        protocol_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": protocol_id,
            "address_id": address_id,
            "pack_id": pack_id,
            "name": name,
            "type": type,
            "boundaries": boundaries or {},
            "personality": personality or {},
            "active": True,
            "created_at": now,
        }

        result = self._db.table("protocols").insert(row).execute()
        logger.info(f"Protocol created: {name} (id={protocol_id}) for address {address_id}")
        return self._row_to_protocol(result.data[0])

    def get_protocol(self, protocol_id: str) -> Protocol:
        """Get a protocol by ID."""
        result = (
            self._db.table("protocols")
            .select("*")
            .eq("id", protocol_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(404, f"Protocol {protocol_id} not found")
        return self._row_to_protocol(result.data[0])

    def list_protocols(self, address_id: str) -> list[Protocol]:
        """List all protocols for an address."""
        result = (
            self._db.table("protocols")
            .select("*")
            .eq("address_id", address_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._row_to_protocol(r) for r in result.data]

    def update_protocol(self, protocol_id: str, **kwargs) -> Protocol:
        """Update a protocol."""
        self.get_protocol(protocol_id)

        update_data = {}
        allowed = {"name", "type", "boundaries", "personality", "active", "pack_id"}
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                if key == "type" and isinstance(value, ProtocolType):
                    value = value.value
                update_data[key] = value

        if not update_data:
            return self.get_protocol(protocol_id)

        result = (
            self._db.table("protocols")
            .update(update_data)
            .eq("id", protocol_id)
            .execute()
        )
        logger.info(f"Protocol updated: {protocol_id}")
        return self._row_to_protocol(result.data[0])

    def delete_protocol(self, protocol_id: str) -> None:
        """Delete a protocol."""
        self.get_protocol(protocol_id)
        self._db.table("protocols").delete().eq("id", protocol_id).execute()
        logger.info(f"Protocol deleted: {protocol_id}")

    # ─── Routing Rule CRUD ────────────────────────────────

    def create_routing_rule(
        self,
        address_id: str,
        protocol_id: str,
        priority: int = 100,
        match_type: str = "default",
        match_value: Optional[str] = None,
    ) -> RoutingRule:
        """Create a routing rule for an address."""
        self.get_address(address_id)
        self.get_protocol(protocol_id)

        rule_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": rule_id,
            "address_id": address_id,
            "protocol_id": protocol_id,
            "priority": priority,
            "match_type": match_type,
            "match_value": match_value,
            "active": True,
            "created_at": now,
        }

        result = self._db.table("routing_rules").insert(row).execute()
        logger.info(f"Routing rule created: {rule_id} (match={match_type})")
        return self._row_to_routing_rule(result.data[0])

    def list_routing_rules(self, address_id: str) -> list[RoutingRule]:
        """List routing rules for an address, sorted by priority."""
        result = (
            self._db.table("routing_rules")
            .select("*")
            .eq("address_id", address_id)
            .order("priority")
            .execute()
        )
        return [self._row_to_routing_rule(r) for r in result.data]

    def update_routing_rule(self, rule_id: str, **kwargs) -> RoutingRule:
        """Update a routing rule."""
        existing = (
            self._db.table("routing_rules")
            .select("*")
            .eq("id", rule_id)
            .execute()
        )
        if not existing.data:
            raise HTTPException(404, f"Routing rule {rule_id} not found")

        update_data = {}
        allowed = {"priority", "match_type", "match_value", "active", "protocol_id"}
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                if key == "match_type" and isinstance(value, MatchType):
                    value = value.value
                update_data[key] = value

        if not update_data:
            return self._row_to_routing_rule(existing.data[0])

        result = (
            self._db.table("routing_rules")
            .update(update_data)
            .eq("id", rule_id)
            .execute()
        )
        logger.info(f"Routing rule updated: {rule_id}")
        return self._row_to_routing_rule(result.data[0])

    def delete_routing_rule(self, rule_id: str) -> None:
        """Delete a routing rule."""
        existing = (
            self._db.table("routing_rules")
            .select("id")
            .eq("id", rule_id)
            .execute()
        )
        if not existing.data:
            raise HTTPException(404, f"Routing rule {rule_id} not found")
        self._db.table("routing_rules").delete().eq("id", rule_id).execute()
        logger.info(f"Routing rule deleted: {rule_id}")

    # ─── Exchange Lifecycle ───────────────────────────────

    def create_exchange(
        self,
        address_id: str,
        protocol_id: Optional[str] = None,
        direction: str = "inbound",
        channel: str = "portal",
        counterparty_type: Optional[str] = None,
        counterparty_identifier: Optional[str] = None,
        counterparty_name: Optional[str] = None,
    ) -> Exchange:
        """Create a new exchange for an address."""
        self.get_address(address_id)

        # Check address availability — exchange is still created (queued),
        # but state carries fallback message for client/channel to display
        available, fallback = self.check_address_availability(address_id)
        exchange_state = {"fallback_message": fallback} if fallback else {}

        exchange_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": exchange_id,
            "address_id": address_id,
            "protocol_id": protocol_id,
            "direction": direction,
            "channel": channel,
            "status": ExchangeStatus.ACTIVE.value,
            "counterparty_type": counterparty_type,
            "counterparty_identifier": counterparty_identifier,
            "counterparty_name": counterparty_name,
            "state": exchange_state,
            "created_at": now,
            "updated_at": now,
        }

        result = self._db.table("exchanges").insert(row).execute()
        logger.info(f"Exchange created: {exchange_id} ({direction}/{channel})")
        return self._row_to_exchange(result.data[0])

    def get_exchange(self, exchange_id: str) -> Exchange:
        """Get an exchange by ID."""
        result = (
            self._db.table("exchanges")
            .select("*")
            .eq("id", exchange_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(404, f"Exchange {exchange_id} not found")
        return self._row_to_exchange(result.data[0])

    def list_exchanges(
        self,
        address_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Exchange]:
        """List exchanges for an address with optional status filter."""
        query = (
            self._db.table("exchanges")
            .select("*")
            .eq("address_id", address_id)
        )
        if status:
            query = query.eq("status", status)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return [self._row_to_exchange(r) for r in result.data]

    def add_turn(
        self,
        exchange_id: str,
        direction: str = "inbound",
        sender_type: str = "human",
        content_raw: Optional[str] = None,
        content_parsed: Optional[dict] = None,
        content_response: Optional[str] = None,
        cartridge: Optional[str] = None,
        state_changes: Optional[dict] = None,
        latency_ms: Optional[int] = None,
    ) -> ExchangeTurn:
        """Add a turn to an exchange."""
        # Verify exchange exists
        self.get_exchange(exchange_id)

        # Determine sequence number
        existing_turns = (
            self._db.table("exchange_turns")
            .select("sequence")
            .eq("exchange_id", exchange_id)
            .order("sequence", desc=True)
            .limit(1)
            .execute()
        )
        sequence = 1
        if existing_turns.data:
            sequence = existing_turns.data[0]["sequence"] + 1

        turn_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": turn_id,
            "exchange_id": exchange_id,
            "sequence": sequence,
            "direction": direction,
            "sender_type": sender_type,
            "content_raw": content_raw,
            "content_parsed": content_parsed,
            "content_response": content_response,
            "cartridge": cartridge,
            "state_changes": state_changes,
            "latency_ms": latency_ms,
            "created_at": now,
        }

        result = self._db.table("exchange_turns").insert(row).execute()

        # Update exchange's updated_at
        self._db.table("exchanges").update(
            {"updated_at": now}
        ).eq("id", exchange_id).execute()

        logger.debug(f"Turn added to exchange {exchange_id}: seq={sequence}")
        return self._row_to_turn(result.data[0])

    def get_turns(self, exchange_id: str) -> list[ExchangeTurn]:
        """Get all turns for an exchange, ordered by sequence."""
        result = (
            self._db.table("exchange_turns")
            .select("*")
            .eq("exchange_id", exchange_id)
            .order("sequence")
            .execute()
        )
        return [self._row_to_turn(r) for r in result.data]

    def resolve_exchange(
        self,
        exchange_id: str,
        resolution_type: str,
        summary: str,
        structured_data: Optional[dict] = None,
        actions_taken: Optional[list] = None,
        requires_review: bool = False,
    ) -> Resolution:
        """Create a resolution for an exchange and mark it resolved."""
        # Verify exchange exists
        self.get_exchange(exchange_id)

        resolution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": resolution_id,
            "exchange_id": exchange_id,
            "type": resolution_type,
            "summary": summary,
            "structured_data": structured_data or {},
            "actions_taken": actions_taken or [],
            "requires_review": requires_review,
            "owner_reviewed": False,
            "created_at": now,
        }

        result = self._db.table("resolutions").insert(row).execute()

        # Update exchange status to resolved
        self._db.table("exchanges").update({
            "status": ExchangeStatus.RESOLVED.value,
            "resolved_at": now,
            "updated_at": now,
        }).eq("id", exchange_id).execute()

        logger.info(f"Exchange {exchange_id} resolved: {resolution_type}")
        return self._row_to_resolution(result.data[0])

    def initiate_outbound_exchange(
        self,
        address_id: str,
        protocol_id: Optional[str] = None,
        counterparty_identifier: Optional[str] = None,
        counterparty_name: str = "",
        channel: str = "agent",
        delivery_payload: Optional[dict] = None,
    ) -> Exchange:
        """
        Create an outbound exchange for proactive delivery (Plume Node 4).

        Creates a new exchange in 'outbound' direction and adds an initial
        turn containing the delivery payload. Uses existing create_exchange()
        and add_turn() — no new Supabase logic needed.
        """
        exchange = self.create_exchange(
            address_id=address_id,
            protocol_id=protocol_id,
            direction="outbound",
            channel=channel,
            counterparty_type="ambassador",
            counterparty_identifier=counterparty_identifier,
            counterparty_name=counterparty_name,
        )

        # Add initial turn with delivery payload
        payload_text = ""
        if delivery_payload:
            import json
            payload_text = json.dumps(delivery_payload)

        self.add_turn(
            exchange_id=exchange.id,
            direction="outbound",
            sender_type="ambassador",
            content_raw=payload_text,
            content_parsed=delivery_payload,
        )

        logger.info(
            "Outbound exchange initiated: %s → %s (address=%s)",
            exchange.id, counterparty_name or counterparty_identifier, address_id,
        )
        return exchange

    def get_resolution(self, exchange_id: str) -> Resolution:
        """Get the resolution for an exchange."""
        result = (
            self._db.table("resolutions")
            .select("*")
            .eq("exchange_id", exchange_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(404, f"No resolution for exchange {exchange_id}")
        return self._row_to_resolution(result.data[0])

    def update_exchange_status(self, exchange_id: str, status: str) -> Exchange:
        """Update an exchange's status."""
        self.get_exchange(exchange_id)
        now = datetime.now(timezone.utc).isoformat()

        update_data = {"status": status, "updated_at": now}
        if status == ExchangeStatus.RESOLVED.value:
            update_data["resolved_at"] = now

        result = (
            self._db.table("exchanges")
            .update(update_data)
            .eq("id", exchange_id)
            .execute()
        )
        logger.info(f"Exchange {exchange_id} status → {status}")
        return self._row_to_exchange(result.data[0])

    def expire_stale_exchanges(self, max_age_hours: int = 24) -> int:
        """Expire active exchanges older than max_age_hours. Returns count expired."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cutoff_str = cutoff.isoformat()

        # Find stale active exchanges
        result = (
            self._db.table("exchanges")
            .select("id")
            .eq("status", ExchangeStatus.ACTIVE.value)
            .lt("updated_at", cutoff_str)
            .execute()
        )

        if not result.data:
            return 0

        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for row in result.data:
            self._db.table("exchanges").update({
                "status": ExchangeStatus.EXPIRED.value,
                "updated_at": now,
            }).eq("id", row["id"]).execute()
            count += 1

        logger.info(f"Expired {count} stale exchange(s) (older than {max_age_hours}h)")
        return count

    # ─── Row → Dataclass Converters ───────────────────────

    def _row_to_address(self, row: dict) -> Address:
        return Address(
            id=row["id"],
            handle=row["handle"],
            domain=row.get("domain", "tmos13.ai"),
            owner_id=row.get("owner_id", ""),
            display_name=row.get("display_name"),
            status=AddressStatus(row.get("status", "active")),
            default_protocol_id=row.get("default_protocol_id"),
            settings=row.get("settings", {}),
            created_at=self._parse_timestamp(row.get("created_at")),
            updated_at=self._parse_timestamp(row.get("updated_at")),
        )

    def _row_to_protocol(self, row: dict) -> Protocol:
        return Protocol(
            id=row["id"],
            address_id=row["address_id"],
            pack_id=row["pack_id"],
            name=row["name"],
            type=ProtocolType(row.get("type", "receive")),
            boundaries=row.get("boundaries", {}),
            personality=row.get("personality", {}),
            active=row.get("active", True),
            created_at=self._parse_timestamp(row.get("created_at")),
        )

    def _row_to_routing_rule(self, row: dict) -> RoutingRule:
        return RoutingRule(
            id=row["id"],
            address_id=row["address_id"],
            protocol_id=row["protocol_id"],
            priority=row.get("priority", 100),
            match_type=MatchType(row.get("match_type", "default")),
            match_value=row.get("match_value"),
            active=row.get("active", True),
            created_at=self._parse_timestamp(row.get("created_at")),
        )

    def _row_to_exchange(self, row: dict) -> Exchange:
        return Exchange(
            id=row["id"],
            address_id=row["address_id"],
            protocol_id=row.get("protocol_id"),
            direction=ExchangeDirection(row.get("direction", "inbound")),
            channel=ExchangeChannel(row.get("channel", "portal")),
            status=ExchangeStatus(row.get("status", "active")),
            counterparty_type=CounterpartyType(row["counterparty_type"]) if row.get("counterparty_type") else None,
            counterparty_identifier=row.get("counterparty_identifier"),
            counterparty_name=row.get("counterparty_name"),
            counterparty_ambassador_id=row.get("counterparty_ambassador_id"),
            intent_detected=row.get("intent_detected"),
            intent_confidence=row.get("intent_confidence"),
            intent_summary=row.get("intent_summary"),
            state=row.get("state", {}),
            created_at=self._parse_timestamp(row.get("created_at")),
            updated_at=self._parse_timestamp(row.get("updated_at")),
            resolved_at=self._parse_timestamp(row.get("resolved_at")),
        )

    def _row_to_turn(self, row: dict) -> ExchangeTurn:
        return ExchangeTurn(
            id=row["id"],
            exchange_id=row["exchange_id"],
            sequence=row["sequence"],
            direction=ExchangeDirection(row.get("direction", "inbound")),
            sender_type=CounterpartyType(row.get("sender_type", "human")),
            content_raw=row.get("content_raw"),
            content_parsed=row.get("content_parsed"),
            content_response=row.get("content_response"),
            cartridge=row.get("cartridge"),
            state_changes=row.get("state_changes"),
            latency_ms=row.get("latency_ms"),
            created_at=self._parse_timestamp(row.get("created_at")),
        )

    def _row_to_resolution(self, row: dict) -> Resolution:
        return Resolution(
            id=row["id"],
            exchange_id=row["exchange_id"],
            type=row["type"],
            summary=row["summary"],
            structured_data=row.get("structured_data", {}),
            actions_taken=row.get("actions_taken", []),
            requires_review=row.get("requires_review", False),
            owner_reviewed=row.get("owner_reviewed", False),
            created_at=self._parse_timestamp(row.get("created_at")),
        )

    @staticmethod
    def _parse_timestamp(value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        return None


# ─── Singleton ────────────────────────────────────────────

_ambassador_service: Optional[AmbassadorService] = None


def init_ambassador_service(supabase_client) -> AmbassadorService:
    """Initialize the global ambassador service. Called during app lifespan."""
    global _ambassador_service
    _ambassador_service = AmbassadorService(supabase_client)
    return _ambassador_service


def get_ambassador_service() -> AmbassadorService:
    """Get the global ambassador service instance."""
    if _ambassador_service is None:
        raise HTTPException(503, "Ambassador service not initialized")
    return _ambassador_service
