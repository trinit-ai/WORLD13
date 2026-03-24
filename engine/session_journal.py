"""
TMOS13 Session Journal — Fibonacci Plume Node 2

Cross-session memory via structured journal entries. On session close,
captures what happened (pack, cartridges, depth, captured fields, outcome,
deliverables) and optionally an LLM-generated insight (compound memory).
On session start, loads the user's recent journals and injects a
[SESSION MEMORY] block with per-session summaries + an aggregated user model.

Journals are per-user (not per-user+pack), enabling cross-pack continuity.

Compound memory: generate_session_insight() produces a 2-3 sentence LLM
insight capturing what the user cared about, what approach worked, and what
to remember. Stored in session_journals.insight and surfaced in the memory block.

Ontological basis: "each return session richer."
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import get_pack

logger = logging.getLogger("tmos13.session_journal")

# ─── Configuration ─────────────────────────────────────────
SESSION_JOURNAL_ENABLED = os.environ.get("SESSION_JOURNAL_ENABLED", "true").lower() in ("true", "1", "yes")
SESSION_JOURNAL_MAX_ENTRIES = int(os.environ.get("SESSION_JOURNAL_MAX_ENTRIES", "10"))
SESSION_JOURNAL_LOOKBACK_DAYS = int(os.environ.get("SESSION_JOURNAL_LOOKBACK_DAYS", "90"))
SESSION_JOURNAL_MAX_TOKENS = int(os.environ.get("SESSION_JOURNAL_MAX_TOKENS", "1500"))

COMPOUND_MEMORY_ENABLED = os.environ.get("TMOS13_COMPOUND_MEMORY_ENABLED", "true").lower() in ("true", "1", "yes")
INSIGHT_MAX_TOKENS = int(os.environ.get("TMOS13_INSIGHT_MAX_TOKENS", "150"))

_INSIGHT_SYSTEM = (
    "You are a session analyst. Given a session transcript and metadata, "
    "produce a 2-3 sentence insight capturing: (1) what the user really "
    "cared about, (2) what approach or tone worked well, and (3) what to "
    "remember for next time. Be specific and actionable. No pleasantries."
)


# ─── Compound Memory: LLM Insight Generation ─────────────

async def generate_session_insight(
    llm_provider,
    state,
    transcript_text: str,
) -> str:
    """
    Generate a 2-3 sentence LLM insight from the session.

    Returns "" on failure, when disabled, or when inputs are insufficient.
    Non-fatal — compound memory is an enhancement, not a requirement.
    """
    if not COMPOUND_MEMORY_ENABLED:
        return ""
    if not llm_provider:
        return ""
    if not transcript_text or len(transcript_text.strip()) < 20:
        return ""

    pack_id = getattr(state, "pack_id", "unknown")
    depth = getattr(state, "depth", 0)
    cartridges = list(getattr(state, "games_played", []))

    user_msg = (
        f"Pack: {pack_id} | Depth: {depth} | Cartridges: {', '.join(cartridges) or 'none'}\n\n"
        f"Transcript (last exchanges):\n{transcript_text[:3000]}"
    )

    try:
        response = await llm_provider.generate(
            system=_INSIGHT_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=INSIGHT_MAX_TOKENS,
        )
        insight = response.text.strip() if response and response.text else ""
        if insight:
            logger.debug("Generated session insight (%d chars) for pack=%s", len(insight), pack_id)
        return insight
    except Exception as e:
        logger.warning("Session insight generation failed: %s", e)
        return ""


# ─── Session Close: Create + Save ──────────────────────────

def create_journal_entry(
    state,
    transcript_summary: Optional[str] = None,
    session_outcome: Optional[str] = None,
    insight: Optional[str] = None,
) -> dict:
    """
    Extract a structured journal entry from session state.

    Returns a dict matching the session_journals table schema.
    """
    # Pack info
    pack_id = getattr(state, "pack_id", "unknown")
    pack_name = None
    try:
        pack = get_pack(pack_id)
        if pack:
            pack_name = getattr(pack, "name", None)
    except Exception:
        pass

    # Cartridges visited
    cartridges = list(getattr(state, "games_played", []))

    # Captured fields (union of forms + prior_captured_fields)
    captured = {}
    forms = getattr(state, "forms", {})
    if forms:
        for form_id, form_data in forms.items():
            for k, v in form_data.items():
                if k != "submitted_at" and v is not None:
                    captured[k] = v
    prior = getattr(state, "prior_captured_fields", {})
    if prior:
        for k, v in prior.items():
            if k not in captured and v is not None:
                captured[k] = v

    # Forms submitted (list of form_ids)
    forms_submitted = list(forms.keys()) if forms else []

    # Deliverables generated (from transcript classification if available)
    deliverables = []

    # Session timestamps
    session_started_at = None
    start = getattr(state, "session_start", None)
    if start:
        try:
            session_started_at = datetime.fromtimestamp(start, tz=timezone.utc).isoformat()
        except (ValueError, OSError, TypeError):
            pass

    # Entity refs for causal chain tracking
    entity_refs = []
    if pack_id:
        entity_refs.append({"type": "system", "name": pack_id})
    for cart in cartridges:
        entity_refs.append({"type": "service", "name": cart})
    if session_outcome:
        entity_refs.append({"type": "event", "name": session_outcome[:60]})
    # Deduplicate
    seen = set()
    unique_refs = []
    for ref in entity_refs:
        key = (ref["type"], ref["name"])
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)

    entry = {
        "session_id": getattr(state, "session_id", ""),
        "pack_id": pack_id,
        "pack_name": pack_name,
        "cartridges_visited": cartridges,
        "depth": getattr(state, "depth", 0),
        "turn_count": getattr(state, "turn_count", 0),
        "captured_fields": captured,
        "session_outcome": session_outcome,
        "transcript_summary": transcript_summary,
        "deliverables_generated": deliverables,
        "forms_submitted": forms_submitted,
        "session_started_at": session_started_at,
        "entity_refs": unique_refs,
    }
    if insight:
        entry["insight"] = insight
    return entry


def save_journal_entry(supabase_client, user_id: str, entry: dict) -> bool:
    """
    Insert a journal entry into the session_journals table.

    Returns False on failure (non-fatal).
    """
    if not supabase_client:
        return False
    if not user_id or user_id == "anonymous":
        return False

    try:
        row = {**entry, "user_id": user_id}
        supabase_client.table("session_journals").insert(row).execute()
        logger.debug("Saved session journal for user=%s pack=%s", user_id, entry.get("pack_id"))
        return True
    except Exception as e:
        logger.warning("Failed to save session journal: %s", e)
        return False


# ─── Session Start: Fetch + Format ─────────────────────────

def fetch_session_memory(
    supabase_client,
    user_id: str,
    current_pack_id: Optional[str] = None,
    max_entries: int = SESSION_JOURNAL_MAX_ENTRIES,
    lookback_days: int = SESSION_JOURNAL_LOOKBACK_DAYS,
    max_tokens: int = SESSION_JOURNAL_MAX_TOKENS,
) -> str:
    """
    Fetch recent session journals and format as a [SESSION MEMORY] block.

    Returns "" for: anonymous users, no client, disabled, no results.
    """
    if not SESSION_JOURNAL_ENABLED:
        return ""
    if not supabase_client:
        return ""
    if not user_id or user_id == "anonymous":
        return ""

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        result = (
            supabase_client.table("session_journals")
            .select("*")
            .eq("user_id", user_id)
            .gte("session_ended_at", cutoff)
            .order("session_ended_at", desc=True)
            .limit(max_entries)
            .execute()
        )
        journals = result.data if result and result.data else []
    except Exception as e:
        logger.warning("Session journal query failed: %s", e)
        return ""

    if not journals:
        return ""

    # When relevance scoring is enabled, rerank journals by relevance to current pack
    import config as _cfg
    if _cfg.RELEVANCE_SCORING_ENABLED and current_pack_id and journals:
        try:
            from relevance import compute_text_relevance, blend_scores
            original_order = [j.get("id") for j in journals]
            for j in journals:
                insight = j.get("insight", "")
                pack = j.get("pack_id", "")
                text = f"{pack} {insight}"
                j["_relevance"] = compute_text_relevance(current_pack_id, text)
            # Assign recency scores (index 0 = most recent)
            for i, j in enumerate(journals):
                j["_recency"] = 1.0 - (i / max(len(journals), 1))
            journals.sort(
                key=lambda j: blend_scores(
                    j.get("_recency", 0), j.get("_relevance", 0), _cfg.RELEVANCE_BOOST_FACTOR
                ),
                reverse=True,
            )
            new_order = [j.get("id") for j in journals]
            if original_order != new_order:
                logger.debug("Session memory reranked: relevance changed order for %s", current_pack_id)
        except Exception as e:
            logger.debug("Journal relevance reranking skipped: %s", e)

    user_model = aggregate_user_model(journals)
    return _format_session_memory(journals, user_model, current_pack_id, max_tokens)


def aggregate_user_model(journals: list[dict]) -> dict:
    """
    Pure computation: aggregate user patterns across journals.

    Returns:
        {total_sessions, packs_used: {pack_id: count}, captured_fields_aggregate: [keys],
         first_session_date, last_session_date}
    """
    if not journals:
        return {
            "total_sessions": 0,
            "packs_used": {},
            "captured_fields_aggregate": [],
            "first_session_date": None,
            "last_session_date": None,
        }

    packs_used: dict[str, int] = {}
    all_field_keys: set[str] = set()
    dates = []

    for j in journals:
        pack_id = j.get("pack_id", "unknown")
        packs_used[pack_id] = packs_used.get(pack_id, 0) + 1

        fields = j.get("captured_fields", {})
        if isinstance(fields, dict):
            all_field_keys.update(fields.keys())

        ended = j.get("session_ended_at")
        if ended:
            dates.append(ended)

    return {
        "total_sessions": len(journals),
        "packs_used": packs_used,
        "captured_fields_aggregate": sorted(all_field_keys),
        "first_session_date": min(dates) if dates else None,
        "last_session_date": max(dates) if dates else None,
    }


def _format_session_memory(
    journals: list[dict],
    user_model: dict,
    current_pack_id: Optional[str] = None,
    max_tokens: int = SESSION_JOURNAL_MAX_TOKENS,
) -> str:
    """
    Format journals + user model into a compact [SESSION MEMORY] block.

    Token budget enforced by char counting (4 chars ~ 1 token).
    """
    char_budget = max_tokens * 4

    # Header
    total = user_model["total_sessions"]
    packs = user_model["packs_used"]
    first_date = user_model.get("first_session_date", "")
    if first_date and isinstance(first_date, str):
        first_date = first_date[:10]

    lines = ["[SESSION MEMORY — Cross-session context]"]
    packs_str = ", ".join(f"{pid} ({cnt})" for pid, cnt in packs.items())
    lines.append(f"User: {total} sessions across {len(packs)} packs since {first_date}")
    lines.append(f"Packs used: {packs_str}")
    lines.append("")
    lines.append("Recent sessions:")

    header_len = sum(len(line) for line in lines)

    instruction = (
        "\nINSTRUCTION: Use this memory to personalize. Reference prior sessions when relevant. "
        "Do NOT re-collect information already captured unless the user indicates it has changed."
    )
    instruction_len = len(instruction)

    used = header_len

    for j in journals:
        entry = _format_single_journal(j)
        entry_len = len(entry)

        if used + entry_len + instruction_len > char_budget:
            break

        lines.append(entry)
        used += entry_len

    lines.append(instruction)
    return "\n".join(lines)


def _format_single_journal(journal: dict) -> str:
    """Format one journal entry into a compact summary line."""
    pack_id = journal.get("pack_id", "unknown")
    ended_at = journal.get("session_ended_at", "")
    date_str = ""
    if ended_at and isinstance(ended_at, str):
        date_str = ended_at[:10]

    cartridges = journal.get("cartridges_visited", [])
    cart_str = ", ".join(cartridges) if cartridges else "none"

    depth = journal.get("depth", 0)
    outcome = journal.get("session_outcome", "")

    captured = journal.get("captured_fields", {})
    field_names = list(captured.keys())[:6] if isinstance(captured, dict) else []
    fields_str = ", ".join(field_names) if field_names else ""

    insight = journal.get("insight", "")

    parts = [f"- {date_str} {pack_id}"]
    parts.append(f"| Cartridges: {cart_str}")
    parts.append(f"| Depth: {depth}")
    if fields_str:
        parts.append(f"| Fields: {fields_str}")
    if outcome:
        parts.append(f"| Outcome: {outcome}")
    if insight:
        parts.append(f"| Insight: {insight}")

    return " ".join(parts)
