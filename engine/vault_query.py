"""Vault Dimensional Query — retrieve artifacts by dimensional intersection.

The RAG layer reads dimensions, not paths.  Each dimension narrows the
result set.  More dimensions = more precise.

Usage:
    results = await query_vault(client, pack_id="legal_intake", user_id="abc")
    results = await query_vault(client, artifact_type="transcript", date_from="2026-01-01")
"""
import logging
from typing import Optional

logger = logging.getLogger("tmos13.vault")


async def query_vault_by_dimensions(
    supabase_client,
    pack_id: Optional[str] = None,
    user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    artifact_type: Optional[str] = None,
    session_id: Optional[str] = None,
    table: str = "deliverables",
    limit: int = 100,
) -> list[dict]:
    """Query Vault artifacts by any combination of dimensions.

    Each supplied dimension narrows the result set.

    Args:
        supabase_client: Supabase client with table access.
        pack_id: Filter by pack dimension.
        user_id: Filter by user dimension.
        date_from: ISO date string — artifacts on or after this date.
        date_to: ISO date string — artifacts on or before this date.
        artifact_type: Filter by type dimension (e.g. "transcript", "case_brief").
        session_id: Filter by session dimension.
        table: Which table to query ("deliverables" or "transcripts").
        limit: Max results to return.

    Returns:
        List of row dicts from the matched table.
    """
    if not supabase_client:
        return []

    try:
        query = supabase_client.table(table).select("*")

        if pack_id:
            query = query.eq("dimensions->>pack", pack_id)
        if user_id:
            query = query.eq("dimensions->>user", user_id)
        if date_from:
            query = query.gte("created_at", date_from)
        if date_to:
            query = query.lte("created_at", date_to)
        if artifact_type:
            if table == "deliverables":
                query = query.eq("artifact_type", artifact_type)
            else:
                query = query.eq("dimensions->>type", artifact_type)
        if session_id:
            query = query.eq("dimensions->>session", session_id)

        query = query.order("created_at", desc=True).limit(limit)
        result = query.execute()
        return result.data or []

    except Exception as e:
        logger.warning(f"Vault dimensional query failed on {table}: {e}")
        return []


async def query_vault_multi_table(
    supabase_client,
    pack_id: Optional[str] = None,
    user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    artifact_type: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
) -> dict[str, list[dict]]:
    """Query both deliverables and transcripts tables by dimensions.

    Returns a dict keyed by table name with matching rows.
    """
    results: dict[str, list[dict]] = {}
    for table in ("deliverables", "transcripts"):
        rows = await query_vault_by_dimensions(
            supabase_client,
            pack_id=pack_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            artifact_type=artifact_type,
            session_id=session_id,
            table=table,
            limit=limit,
        )
        if rows:
            results[table] = rows
    return results
