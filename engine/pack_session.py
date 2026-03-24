"""
TMOS13 Multi-Pack Session — Fibonacci Plume Node 1

Sequential pack execution within a single conversational context. The mouth
of one pack becomes the input of the next: when a user (or client UI)
triggers a pack switch, the system captures specified fields from the current
pack, records the transition in pack history, switches state.pack_id, and
injects the carried context into the new pack's assembler output.

The new pack runs in full isolation — it doesn't know it was preceded by
another pack. Only the explicit carry-forward fields are injected.

Ontological basis: "the mouth of one pack feeds the next."
"""
import logging
import os
import time
from typing import Optional

from config import get_pack

logger = logging.getLogger("tmos13.pack_session")

# ─── Configuration ─────────────────────────────────────────
MULTI_PACK_ENABLED = os.environ.get("MULTI_PACK_ENABLED", "true").lower() in ("true", "1", "yes")
MAX_PACK_SWITCHES = int(os.environ.get("MAX_PACK_SWITCHES", "10"))


def switch_pack(
    state,
    target_pack_id: str,
    carry_fields: Optional[list[str]] = None,
    target_cartridge: Optional[str] = None,
    context_note: Optional[str] = None,
) -> dict:
    """
    Switch the session from its current pack to a new pack.

    Validates constraints, captures carry-forward fields, records the
    transition in pack_history, and sets up state for the new pack.

    Returns:
        {"success": bool, "error": str, "carried": dict, "source_pack": str}
    """
    source_pack_id = state.pack_id

    # ─── Guard: feature disabled
    if not MULTI_PACK_ENABLED:
        return {"success": False, "error": "Multi-pack sessions are disabled", "carried": {}, "source_pack": source_pack_id}

    # ─── Guard: same pack
    if target_pack_id == source_pack_id:
        return {"success": False, "error": f"Already on pack '{target_pack_id}'", "carried": {}, "source_pack": source_pack_id}

    # ─── Guard: target pack exists
    target_pack = get_pack(target_pack_id)
    if not target_pack:
        return {"success": False, "error": f"Pack '{target_pack_id}' not found", "carried": {}, "source_pack": source_pack_id}

    # ─── Guard: max switches
    history = getattr(state, "pack_history", [])
    if len(history) >= MAX_PACK_SWITCHES:
        return {"success": False, "error": f"Maximum pack switches ({MAX_PACK_SWITCHES}) reached", "carried": {}, "source_pack": source_pack_id}

    # ─── Build carryover context
    carried = build_carryover_context(state, carry_fields)

    # ─── Record exit in pack_history
    entry = {
        "pack_id": source_pack_id,
        "entered_at": state.session_start,
        "exited_at": time.time(),
        "carry_fields_out": list(carried.keys()),
    }
    if not hasattr(state, "pack_history") or state.pack_history is None:
        state.pack_history = []
    state.pack_history.append(entry)

    # ─── Switch pack
    state.pack_id = target_pack_id

    # ─── Reset cartridge state for new pack
    state.current_game = target_cartridge
    state.games_played = []

    # ─── Format and set handoff context
    state.pack_handoff_context = format_handoff_context(carried, source_pack_id, context_note)

    logger.info(
        "Pack switch: %s → %s (session=%s, carried=%d fields)",
        source_pack_id, target_pack_id, state.session_id, len(carried),
    )

    return {"success": True, "error": "", "carried": carried, "source_pack": source_pack_id}


def build_carryover_context(state, carry_fields: Optional[list[str]] = None) -> dict:
    """
    Extract fields to carry forward from the current pack.

    Sources (priority order): state.forms > state.prior_captured_fields > state attributes.
    Only declared fields are carried — enforces explicit transfer (ontological requirement).
    """
    if not carry_fields:
        return {}

    carried = {}
    for field_name in carry_fields:
        # 1. Check forms (submitted in-chat form data)
        if state.forms:
            for form_id, form_data in state.forms.items():
                if field_name in form_data and form_data[field_name] is not None:
                    carried[field_name] = form_data[field_name]
                    break

        # 2. Check prior_captured_fields (from persistence)
        if field_name not in carried:
            prior = getattr(state, "prior_captured_fields", {})
            if prior and field_name in prior and prior[field_name] is not None:
                carried[field_name] = prior[field_name]

        # 3. Check state attributes
        if field_name not in carried:
            val = getattr(state, field_name, None)
            if val is not None:
                carried[field_name] = val

    return carried


def format_handoff_context(
    carry_data: dict,
    source_pack_id: str,
    context_note: Optional[str] = None,
) -> str:
    """
    Format carried data into a context block for assembler injection.

    Returns "" if no data to carry.
    """
    if not carry_data:
        return ""

    lines = [f"[PACK HANDOFF CONTEXT — Carried from {source_pack_id}]"]

    # Fields
    fields_str = ", ".join(f"{k}: {v}" for k, v in carry_data.items())
    lines.append(f"Fields: {fields_str}")

    # Optional context note
    if context_note:
        lines.append(f"Context: {context_note}")

    # Instruction
    lines.append(
        "INSTRUCTION: Use this context from the prior pack. "
        "Do NOT ask for information already provided."
    )

    return "\n".join(lines)
