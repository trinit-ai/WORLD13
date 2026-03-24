"""Vault Admission Gate — dimensional address validation.

Every artifact entering the Vault (transcripts, deliverables) must carry
a complete dimensional address.  This module validates completeness before
persistence and flags gaps without dropping data.

The eight Vault dimensions:
  1. pack      — which protocol governed the session
  2. user      — whose session produced this artifact
  3. date      — when the session occurred
  4. type      — what kind of artifact
  5. fields    — structured key-value data (recommended, not gate-blocking)
  6. session   — the session that produced it
  7. manifest  — intent signature (pack version, cartridges, features, settings)
  8. content   — semantic body / content_hash (recommended, not gate-blocking)
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("tmos13.vault")

# Dimensions that MUST be present for Vault admission.
# "fields" and "content"/"content_hash" are recommended but not gate-blocking.
REQUIRED_DIMENSIONS = ["pack", "user", "date", "type", "session", "manifest"]


def validate_vault_admission(dimensions: dict) -> tuple[bool, list[str]]:
    """Validate that an artifact has all required dimensional addresses.

    Returns (is_valid, missing_dimensions).  Fields and content are
    recommended but not gate-blocking — some artifacts legitimately
    have empty fields.
    """
    missing = [d for d in REQUIRED_DIMENSIONS if not dimensions.get(d)]
    return (len(missing) == 0, missing)


def build_deliverable_dimensions(
    pack_id: str,
    user_id: str,
    session_id: str,
    artifact_type: str,
    extracted_fields: dict,
    manifest_signature: dict,
    content: str = "",
    created_at: Optional[float] = None,
) -> dict:
    """Assemble the full eight-dimensional address for a deliverable."""
    if created_at:
        date_str = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
    else:
        date_str = datetime.now(timezone.utc).isoformat()

    dimensions = {
        "pack": pack_id,
        "user": user_id,
        "date": date_str,
        "type": artifact_type,
        "fields": extracted_fields or {},
        "session": session_id,
        "manifest": manifest_signature or {},
        "content_hash": hashlib.sha256(content.encode()).hexdigest() if content else "",
    }
    return dimensions


def build_transcript_dimensions(
    pack_id: str,
    user_id: str,
    session_id: str,
    manifest_signature: dict,
    cartridge: Optional[str] = None,
    created_at: Optional[float] = None,
) -> dict:
    """Assemble the dimensional address for a transcript."""
    if created_at:
        date_str = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
    else:
        date_str = datetime.now(timezone.utc).isoformat()

    dimensions = {
        "pack": pack_id,
        "user": user_id,
        "date": date_str,
        "type": "transcript",
        "fields": {},
        "session": session_id,
        "manifest": manifest_signature or {},
    }
    if cartridge:
        dimensions["cartridge"] = cartridge
    return dimensions


def build_note_dimensions(
    pack_id: str,
    user_id: str,
    session_id: str,
    note_type: str,
    tags: list[str],
    manifest_signature: dict,
    content: str = "",
    created_at: Optional[float] = None,
) -> dict:
    """Assemble the dimensional address for a note."""
    if created_at:
        date_str = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
    else:
        date_str = datetime.now(timezone.utc).isoformat()
    return {
        "pack": pack_id or "",
        "user": user_id,
        "date": date_str,
        "type": f"note:{note_type}",
        "fields": {"tags": tags} if tags else {},
        "session": session_id or "",
        "manifest": manifest_signature or {},
        "content_hash": hashlib.sha256(content.encode()).hexdigest() if content else "",
    }


def gate_and_log(dimensions: dict, artifact_id: str, artifact_kind: str) -> bool:
    """Run admission gate, log result, return whether dimensions are complete."""
    is_valid, missing = validate_vault_admission(dimensions)
    if not is_valid:
        logger.warning(
            f"Vault admission: incomplete dimensions for {artifact_kind} "
            f"{artifact_id} — missing: {missing}"
        )
    return is_valid
