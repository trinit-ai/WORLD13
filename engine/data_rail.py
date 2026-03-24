"""
TMOS13 DataRail — Secure Structured Data Capture

Data entered through the rail NEVER enters the LLM prompt context.
It goes directly to encrypted Supabase storage via this service.
The AI receives only a receipt token: {rail:cartridge_id:rail_id:completed}

Architecture:
  Chat input → Assembler → LLM  (substance, no PII)
  Data Rail  → This service → Supabase vault  (PII, no LLM)
  Receipt token links the two at application layer only.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any

logger = logging.getLogger("tmos13.data_rail")


# ─── Field Definition ─────────────────────────────────────

@dataclass
class RailFieldDef:
    """Definition of a single field in a data rail."""

    id: str
    type: str  # text, email, password, number, date, address, phone, select
    label: str
    required: bool = True
    pii: bool = False
    options: list[str] = field(default_factory=list)  # for select type
    validation: str | None = None  # regex pattern


# ─── Allowed field types ──────────────────────────────────

ALLOWED_FIELD_TYPES = {
    "text", "email", "password", "number", "date",
    "address", "phone", "select",
}


# ─── Service ──────────────────────────────────────────────

class DataRailService:
    """
    Supabase-backed data rail service.

    Follows the singleton pattern from ambassador_service.py:
    class with __init__(supabase_client), module-level _service,
    init_data_rail_service() and get_data_rail_service() functions.
    """

    def __init__(self, supabase_client):
        self._db = supabase_client
        logger.info("DataRail service initialized")

    def generate_receipt_token(
        self,
        session_id: str,
        cartridge_id: str,
        rail_id: str,
    ) -> str:
        """
        Generate a receipt token that links substance to identity.

        Format: rail:{cartridge_id}:{rail_id}:{short_uuid}
        """
        short = uuid.uuid4().hex[:12]
        return f"rail:{cartridge_id}:{rail_id}:{short}"

    async def submit(
        self,
        session_id: str,
        pack_id: str,
        cartridge_id: str,
        rail_id: str,
        fields: dict[str, Any],
        field_defs: list[RailFieldDef] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Submit structured data to a rail.

        Separates PII fields (where field def has pii=True) into
        encrypted_pii column. Non-PII fields go into fields column.
        Generates receipt token. Inserts into Supabase.

        Returns:
            { receipt_token, rail_id, field_count, pii_field_count }
        """
        # Determine PII vs non-PII fields
        pii_field_ids = set()
        if field_defs:
            pii_field_ids = {fd.id for fd in field_defs if fd.pii}

        non_pii_data = {}
        pii_data = {}

        for key, value in fields.items():
            if key in pii_field_ids:
                pii_data[key] = value
            else:
                non_pii_data[key] = value

        receipt_token = self.generate_receipt_token(
            session_id, cartridge_id, rail_id
        )

        now = datetime.now(timezone.utc).isoformat()

        row = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "pack_id": pack_id,
            "cartridge_id": cartridge_id,
            "rail_id": rail_id,
            "fields": non_pii_data,
            "encrypted_pii": pii_data if pii_data else None,
            "receipt_token": receipt_token,
            "status": "completed",
            "submitted_at": now,
            "metadata": metadata or {},
        }

        import asyncio
        await asyncio.to_thread(
            lambda: self._db.table("rail_submissions").insert(row).execute()
        )

        logger.info(
            "Rail submission: session=%s cartridge=%s rail=%s "
            "fields=%d pii=%d token=%s",
            session_id,
            cartridge_id,
            rail_id,
            len(non_pii_data),
            len(pii_data),
            receipt_token,
        )

        return {
            "receipt_token": receipt_token,
            "rail_id": rail_id,
            "field_count": len(non_pii_data),
            "pii_field_count": len(pii_data),
        }

    async def get_submission(self, receipt_token: str) -> dict | None:
        """
        Look up submission by receipt token.

        Returns full record including encrypted PII.
        This is for human operators / dashboard only — never called
        during LLM assembly.
        """
        import asyncio
        result = await asyncio.to_thread(
            lambda: (
                self._db.table("rail_submissions")
                .select("*")
                .eq("receipt_token", receipt_token)
                .execute()
            )
        )

        if not result.data:
            return None
        return result.data[0]

    async def get_session_submissions(self, session_id: str) -> list[dict]:
        """
        All submissions for a session, ordered by submitted_at.
        """
        import asyncio
        result = await asyncio.to_thread(
            lambda: (
                self._db.table("rail_submissions")
                .select("*")
                .eq("session_id", session_id)
                .order("submitted_at")
                .execute()
            )
        )
        return result.data

    async def get_receipt_tokens(self, session_id: str) -> list[str]:
        """
        Just the receipt tokens for a session.

        This IS called during assembly to inject tokens into the LLM
        context without exposing PII.
        """
        import asyncio
        result = await asyncio.to_thread(
            lambda: (
                self._db.table("rail_submissions")
                .select("receipt_token")
                .eq("session_id", session_id)
                .order("submitted_at")
                .execute()
            )
        )
        return [r["receipt_token"] for r in result.data]

    def backfill_contact_id(self, session_id: str, contact_id: str):
        """Set contact_id on all rail_submissions for a session."""
        self._db.table("rail_submissions").update(
            {"contact_id": contact_id}
        ).eq("session_id", session_id).is_("contact_id", "null").execute()

    async def get_contact_submissions(self, contact_id: str) -> list[dict]:
        """All submissions linked to a contact, ordered by submitted_at."""
        import asyncio
        result = await asyncio.to_thread(
            lambda: (
                self._db.table("rail_submissions")
                .select("*")
                .eq("contact_id", contact_id)
                .order("submitted_at")
                .execute()
            )
        )
        return result.data


# ─── Singleton ────────────────────────────────────────────

_service: Optional[DataRailService] = None


def init_data_rail_service(supabase_client) -> DataRailService:
    """Initialize the global DataRail service. Called during app lifespan."""
    global _service
    _service = DataRailService(supabase_client)
    return _service


def get_data_rail_service() -> DataRailService:
    """Get the global DataRail service instance."""
    if _service is None:
        from fastapi import HTTPException
        raise HTTPException(503, "DataRail service not initialized")
    return _service
