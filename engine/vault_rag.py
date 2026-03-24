"""
TMOS13 Vault RAG Layer — Fibonacci Plume Node 3

Mid-session retrieval of prior deliverables and knowledge. A pack running in
a session can consult the Vault in real time, surfacing relevant prior work
without user direction.

Design principle: index-first retrieval via Postgres compound index, NOT
vector RAG. Metadata first, content second, never load what you don't need.
When vector search is available, results are reranked by semantic relevance.

The ontology is explicit: "the nest feeds the mouth." This closes that loop.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import config as _cfg

logger = logging.getLogger("tmos13.vault_rag")

# ─── Configuration ─────────────────────────────────────────
VAULT_RAG_ENABLED = os.environ.get("VAULT_RAG_ENABLED", "true").lower() in ("true", "1", "yes")
VAULT_RAG_MAX_ARTIFACTS = int(os.environ.get("VAULT_RAG_MAX_ARTIFACTS", "5"))
VAULT_RAG_LOOKBACK_DAYS = int(os.environ.get("VAULT_RAG_LOOKBACK_DAYS", "90"))
VAULT_RAG_MAX_TOKENS = int(os.environ.get("VAULT_RAG_MAX_TOKENS", "2000"))


def fetch_vault_context(
    supabase_client,
    user_id: str,
    pack_id: str,
    current_cartridge: Optional[str] = None,
    max_artifacts: int = VAULT_RAG_MAX_ARTIFACTS,
    lookback_days: int = VAULT_RAG_LOOKBACK_DAYS,
    max_tokens: int = VAULT_RAG_MAX_TOKENS,
) -> str:
    """
    Fetch prior deliverables for this user+pack and format as context.

    Returns "" for: anonymous users, no Supabase client, disabled flag,
    query failure, or no results.
    """
    if not VAULT_RAG_ENABLED:
        return ""
    if not supabase_client:
        return ""
    if not user_id or user_id == "anonymous":
        return ""
    if not pack_id:
        return ""

    try:
        result = (
            supabase_client.table("deliverables")
            .select("id, spec_name, artifact_type, status, metadata, extracted_data, created_at")
            .eq("user_id", user_id)
            .eq("pack_id", pack_id)
            .gte("created_at", _lookback_timestamp(lookback_days))
            .order("created_at", desc=True)
            .limit(max_artifacts)
            .execute()
        )
        rows = result.data if result and result.data else []
    except Exception as e:
        logger.warning("Vault RAG query failed: %s", e)
        return ""

    if not rows:
        return ""

    # When relevance scoring is enabled, rerank rows by semantic relevance
    if _cfg.RELEVANCE_SCORING_ENABLED and rows:
        try:
            from relevance import rerank_by_relevance
            # Build a text representation for each row for scoring
            original_order = [r.get("id") for r in rows]
            for row in rows:
                row["_text"] = _row_to_text(row)
            context_query = f"{pack_id} {current_cartridge or ''}"
            rows = rerank_by_relevance(
                items=rows,
                query=context_query,
                content_key="_text",
                top_k=max_artifacts,
                boost_factor=_cfg.RELEVANCE_BOOST_FACTOR,
            )
            new_order = [r.get("id") for r in rows]
            if original_order != new_order:
                logger.debug("Vault RAG reranked: relevance changed order for %s", pack_id)
        except Exception as e:
            logger.debug("Relevance reranking skipped: %s", e)

    return _format_vault_context(rows, max_tokens, current_cartridge)


def _format_vault_context(
    rows: list[dict],
    max_tokens: int = VAULT_RAG_MAX_TOKENS,
    current_cartridge: Optional[str] = None,
) -> str:
    """
    Format deliverable rows into a compact context block.

    Token budget enforced by char counting (4 chars ~ 1 token).
    Stops adding entries when budget is exhausted.
    """
    if not rows:
        return ""

    char_budget = max_tokens * 4
    lines = ["[VAULT CONTEXT — Prior deliverables for this pack]"]
    header_len = len(lines[0])
    used = header_len

    instruction = (
        "\nINSTRUCTION: Reference prior deliverables when relevant. Do NOT re-collect "
        "information already captured unless the user indicates it has changed."
    )
    instruction_len = len(instruction)

    for row in rows:
        entry = _format_single_row(row)
        entry_len = len(entry)

        if used + entry_len + instruction_len > char_budget:
            break

        lines.append(entry)
        used += entry_len

    if len(lines) == 1:
        return ""

    lines.append(instruction)
    return "\n".join(lines)


def _format_single_row(row: dict) -> str:
    """Format one deliverable row into a compact summary line."""
    spec_name = row.get("spec_name") or row.get("artifact_type") or "Deliverable"
    artifact_type = row.get("artifact_type") or ""
    status = row.get("status") or ""
    created_at = row.get("created_at") or ""
    metadata = row.get("metadata") or {}
    extracted_data = row.get("extracted_data") or {}

    # Format date
    date_str = ""
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                dt = created_at
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date_str = str(created_at)[:10]

    # Format completeness as percentage
    completeness = metadata.get("completeness")
    completeness_str = ""
    if completeness is not None:
        if isinstance(completeness, (int, float)):
            completeness_str = f"{int(completeness * 100)}%" if completeness <= 1 else f"{int(completeness)}%"

    # Status decoration
    status_str = ""
    if status == "sent":
        status_str = "(sent)"
    elif status == "draft":
        status_str = "(draft)"
    elif status == "error":
        status_str = "(error)"

    # Build the summary line
    parts = [f"- {spec_name}"]
    if artifact_type:
        parts.append(f"[{artifact_type}]")
    if completeness_str:
        parts.append(completeness_str)
    if status_str:
        parts.append(status_str)
    if date_str:
        parts.append(date_str)

    line = " ".join(parts)

    # Add field names from extracted_data
    if extracted_data and isinstance(extracted_data, dict):
        field_names = [k for k in extracted_data.keys() if extracted_data[k] is not None]
        if field_names:
            line += f"\n  Fields: {', '.join(field_names[:8])}"

    return line


def _row_to_text(row: dict) -> str:
    """Build a text representation of a deliverable row for relevance scoring."""
    parts = []
    if row.get("spec_name"):
        parts.append(row["spec_name"])
    if row.get("artifact_type"):
        parts.append(row["artifact_type"])
    extracted = row.get("extracted_data") or {}
    if isinstance(extracted, dict):
        for k, v in list(extracted.items())[:6]:
            if v is not None:
                parts.append(f"{k}: {v}")
    return " ".join(parts)


def _lookback_timestamp(days: int) -> str:
    """Return ISO timestamp for N days ago."""
    from datetime import timedelta
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat()
