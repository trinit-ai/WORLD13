"""
Desk Vault Query — search vault_items, deliverables, and transcripts.

POST /api/desk/vault-query
Returns unified results from all three vault tables.
Used by the vault_query tool for on-demand retrieval.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from api_desk_query import resolve_temporal, extract_search_terms

logger = logging.getLogger("tmos13.desk_vault")


# ─── Request / Response Models ──────────────────────────

class VaultQueryRequest(BaseModel):
    q: Optional[str] = None
    limit: int = 10
    include_content: bool = False


class VaultQueryResultItem(BaseModel):
    source_table: str = ""
    artifact_id: Optional[str] = None
    name: Optional[str] = None
    artifact_type: Optional[str] = None
    pack: Optional[str] = None
    department: Optional[str] = None
    date: Optional[str] = None
    session_id: Optional[str] = None
    content_preview: Optional[str] = None
    content: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    size_bytes: int = 0
    match_score: float = 0.0
    matched_on: list[str] = []


class VaultQueryResponse(BaseModel):
    results: list[VaultQueryResultItem] = []
    total: int = 0
    query: Optional[str] = None


# ─── Type hint detection ────────────────────────────────

_FILE_HINTS = {"file", "upload", "uploaded", "document", "attachment"}
_DELIVERABLE_HINTS = {"deliverable", "brief", "memo", "report", "artifact", "output"}
_TRANSCRIPT_HINTS = {"transcript", "session log", "session record", "conversation log"}


def _detect_table_hints(q: str) -> set[str]:
    """Detect which tables to query based on keyword hints."""
    if not q:
        return {"vault_items", "deliverables", "transcripts"}

    q_lower = q.lower()
    tables = set()

    if any(h in q_lower for h in _FILE_HINTS):
        tables.add("vault_items")
    if any(h in q_lower for h in _DELIVERABLE_HINTS):
        tables.add("deliverables")
    if any(h in q_lower for h in _TRANSCRIPT_HINTS):
        tables.add("transcripts")

    return tables if tables else {"vault_items", "deliverables", "transcripts"}


# ─── Query Execution ────────────────────────────────────

def execute_vault_query(db, owner_id: str, req: VaultQueryRequest) -> VaultQueryResponse:
    """
    Execute a vault query across vault_items, deliverables, and transcripts.
    """
    limit = min(req.limit or 10, 20)
    q = req.q or ""
    include_content = req.include_content

    # Resolve temporal phrases
    date_from, date_to, q_remaining = resolve_temporal(q)
    search_terms = extract_search_terms(q_remaining)
    tables = _detect_table_hints(q)

    scored: list[tuple[float, VaultQueryResultItem]] = []

    # ── vault_items ──
    if "vault_items" in tables:
        try:
            query = (
                db.table("vault_items")
                .select("id, owner_id, filename, mime_type, size_bytes, tier, source, "
                        "department, pack_id, session_id, tags, created_at")
                .eq("owner_id", owner_id)
                .order("created_at", desc=True)
            )
            if date_from:
                query = query.gte("created_at", date_from)
            if date_to:
                query = query.lte("created_at", date_to)
            query = query.limit(limit * 3)

            result = query.execute()
            rows = result.data if result and result.data else []

            for row in rows:
                score = 1.0
                matched_on = []
                filename = row.get("filename") or ""
                filename_lower = filename.lower()

                for term in search_terms:
                    tl = term.lower()
                    if tl in filename_lower:
                        score += 5.0
                        if "filename" not in matched_on:
                            matched_on.append("filename")
                    elif tl in (row.get("tier") or "").lower():
                        score += 3.0
                        if "tier" not in matched_on:
                            matched_on.append("tier")
                    elif tl in (row.get("department") or "").lower():
                        score += 3.0
                        if "department" not in matched_on:
                            matched_on.append("department")

                # Recency boost for "just uploaded" style queries
                if any(w in (q or "").lower() for w in ("just", "recent", "latest", "new")):
                    created = row.get("created_at") or ""
                    if created:
                        try:
                            ct = datetime.fromisoformat(created.replace("Z", "+00:00"))
                            age_hours = (datetime.now(timezone.utc) - ct).total_seconds() / 3600
                            if age_hours < 1:
                                score += 4.0
                            elif age_hours < 24:
                                score += 2.0
                        except (ValueError, TypeError):
                            pass

                # Skip non-matching when search terms present
                if search_terms and not matched_on:
                    continue

                item = VaultQueryResultItem(
                    source_table="vault_items",
                    artifact_id=str(row.get("id", "")),
                    name=filename,
                    artifact_type=row.get("tier") or "upload",
                    pack=row.get("pack_id"),
                    department=row.get("department"),
                    date=(row.get("created_at") or "")[:10],
                    session_id=row.get("session_id"),
                    file_name=filename,
                    file_type=row.get("mime_type"),
                    size_bytes=row.get("size_bytes") or 0,
                    match_score=round(score, 2),
                    matched_on=matched_on,
                )
                scored.append((score, item))

        except Exception as e:
            logger.warning("Vault query (vault_items) failed: %s", e)

    # ── deliverables ──
    if "deliverables" in tables:
        try:
            query = (
                db.table("deliverables")
                .select("id, spec_name, artifact_type, content, dimensions, created_at")
                .eq("dimensions->>user", owner_id)
                .order("created_at", desc=True)
            )
            if date_from:
                query = query.gte("created_at", date_from)
            if date_to:
                query = query.lte("created_at", date_to)
            query = query.limit(limit * 3)

            result = query.execute()
            rows = result.data if result and result.data else []

            for row in rows:
                score = 1.0
                matched_on = []
                spec_name = row.get("spec_name") or ""
                art_type = row.get("artifact_type") or ""
                dims = row.get("dimensions") or {}
                content_text = row.get("content") or ""

                for term in search_terms:
                    tl = term.lower()
                    if tl in spec_name.lower():
                        score += 5.0
                        if "name" not in matched_on:
                            matched_on.append("name")
                    elif tl in art_type.lower():
                        score += 3.0
                        if "type" not in matched_on:
                            matched_on.append("type")
                    elif tl in content_text[:500].lower():
                        score += 1.5
                        if "content" not in matched_on:
                            matched_on.append("content")

                if search_terms and not matched_on:
                    continue

                preview = content_text[:200] + "..." if len(content_text) > 200 else content_text

                item = VaultQueryResultItem(
                    source_table="deliverables",
                    artifact_id=str(row.get("id", "")),
                    name=spec_name or art_type,
                    artifact_type=art_type,
                    pack=dims.get("pack"),
                    department=dims.get("department"),
                    date=(row.get("created_at") or "")[:10],
                    session_id=dims.get("session"),
                    content_preview=preview if preview else None,
                    content=content_text if include_content else None,
                    match_score=round(score, 2),
                    matched_on=matched_on,
                )
                scored.append((score, item))

        except Exception as e:
            logger.warning("Vault query (deliverables) failed: %s", e)

    # ── transcripts ──
    if "transcripts" in tables:
        try:
            query = (
                db.table("transcripts")
                .select("id, session_id, dimensions, transcript, created_at")
                .eq("dimensions->>user", owner_id)
                .order("created_at", desc=True)
            )
            if date_from:
                query = query.gte("created_at", date_from)
            if date_to:
                query = query.lte("created_at", date_to)
            query = query.limit(limit * 3)

            result = query.execute()
            rows = result.data if result and result.data else []

            for row in rows:
                score = 1.0
                matched_on = []
                dims = row.get("dimensions") or {}
                transcript = row.get("transcript") or ""
                if isinstance(transcript, list):
                    transcript = " ".join(
                        t.get("content", "") for t in transcript if isinstance(t, dict)
                    )
                sess_type = dims.get("type") or "transcript"

                for term in search_terms:
                    tl = term.lower()
                    if tl in (dims.get("pack") or "").lower():
                        score += 3.0
                        if "pack" not in matched_on:
                            matched_on.append("pack")
                    elif tl in sess_type.lower():
                        score += 3.0
                        if "type" not in matched_on:
                            matched_on.append("type")
                    elif tl in transcript[:500].lower():
                        score += 1.5
                        if "content" not in matched_on:
                            matched_on.append("content")

                if search_terms and not matched_on:
                    continue

                preview = transcript[:200] + "..." if len(transcript) > 200 else transcript

                item = VaultQueryResultItem(
                    source_table="transcripts",
                    artifact_id=str(row.get("id", "")),
                    name=f"{dims.get('pack', 'unknown')} session ({sess_type})",
                    artifact_type=sess_type,
                    pack=dims.get("pack"),
                    department=dims.get("department"),
                    date=(row.get("created_at") or "")[:10],
                    session_id=row.get("session_id"),
                    content_preview=preview if preview else None,
                    content=transcript if include_content else None,
                    match_score=round(score, 2),
                    matched_on=matched_on,
                )
                scored.append((score, item))

        except Exception as e:
            logger.warning("Vault query (transcripts) failed: %s", e)

    # ── Sort and limit ──
    scored.sort(key=lambda x: x[0], reverse=True)
    items = [item for _, item in scored[:limit]]

    return VaultQueryResponse(
        results=items,
        total=len(items),
        query=req.q,
    )


# ─── Tool Result Formatting ─────────────────────────────

def format_tool_result(response: VaultQueryResponse) -> str:
    """Format vault query results for injection into model context."""
    if not response.results:
        return (
            f"[TOOL RESULT: vault_query]\n"
            f"query: \"{response.query or ''}\"\n"
            f"results: 0 artifacts found\n\n"
            f"No matching vault items found. Tell the operator plainly."
        )

    lines = [
        f"[TOOL RESULT: vault_query]",
        f"query: \"{response.query or ''}\"",
        f"results: {response.total} artifact{'s' if response.total != 1 else ''} found",
        "",
    ]

    for i, item in enumerate(response.results, 1):
        name = item.name or "Untitled"
        source = item.source_table.replace("_", " ").title()
        art_type = item.artifact_type or "unknown"
        pack = item.pack or "—"
        dept = item.department or "—"
        date = item.date or "unknown"

        lines.append(f"ARTIFACT {i}")
        lines.append(f"Name: {name}")
        lines.append(f"Source: {source} | Type: {art_type}")
        lines.append(f"Pack: {pack} | Dept: {dept}")

        size_str = ""
        if item.size_bytes:
            if item.size_bytes > 1_048_576:
                size_str = f" · {item.size_bytes / 1_048_576:.1f}MB"
            elif item.size_bytes > 1024:
                size_str = f" · {item.size_bytes / 1024:.0f}KB"
            else:
                size_str = f" · {item.size_bytes}B"

        file_info = ""
        if item.file_type:
            file_info = f" · {item.file_type}"

        lines.append(f"Date: {date}{size_str}{file_info}")

        if item.content_preview:
            lines.append(f"Preview: {item.content_preview}")
        if item.content:
            lines.append(f"Content: {item.content[:2000]}")
        lines.append("")

    lines.append("Present these results to the operator. If they want the full content of a specific artifact, offer to retrieve it with include_content=true.")
    return "\n".join(lines)


# ─── Route Registration ─────────────────────────────────

def register_vault_query_endpoints(app, db_client):
    """Register vault query routes on the FastAPI app."""
    from auth import get_current_user, UserProfile

    @app.post("/api/desk/vault-query", response_model=VaultQueryResponse, tags=["desk"])
    async def vault_query_endpoint(req: VaultQueryRequest, user: UserProfile = Depends(get_current_user)):
        """Search vault items, deliverables, and transcripts."""
        if not user:
            raise HTTPException(401, "Authentication required")

        from config import TMOS13_OWNER_ID
        owner_id = TMOS13_OWNER_ID
        if not owner_id:
            raise HTTPException(500, "TMOS13_OWNER_ID not configured")

        return execute_vault_query(db_client, owner_id, req)
