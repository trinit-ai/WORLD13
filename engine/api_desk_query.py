"""
Desk Inbox Query — search inbox conversations by name, date, topic, or interest.

POST /api/desk/query
Returns session summaries matching natural-language queries.
Used by the desk_query tool for on-demand retrieval.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("tmos13.desk_query")


# ─── Request / Response Models ──────────────────────────

class DeskQueryFilters(BaseModel):
    name: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    pack: Optional[str] = None
    status: Optional[str] = None


class DeskQueryRequest(BaseModel):
    q: Optional[str] = None
    filters: Optional[DeskQueryFilters] = None
    limit: int = 10


class DeskQueryResultItem(BaseModel):
    session_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    pack: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[str] = None
    duration_seconds: int = 0
    turns: int = 0
    cost_usd: float = 0.0
    summary_brief: Optional[str] = None
    summary_full: Optional[str] = None
    match_score: float = 0.0
    matched_on: list[str] = []


class DeskQueryResponse(BaseModel):
    results: list[DeskQueryResultItem] = []
    total: int = 0
    query: Optional[str] = None


# ─── Temporal Phrase Resolution ─────────────────────────

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "about", "for", "with",
    "from", "to", "in", "on", "at", "by", "of", "up", "out", "off",
    "so", "if", "or", "and", "but", "not", "no", "all", "any", "some",
    "my", "me", "i", "you", "your", "we", "us", "our", "they", "them",
    "their", "it", "its", "this", "that", "these", "those", "what",
    "who", "whom", "which", "where", "when", "how", "show", "pull",
    "find", "get", "tell", "give", "see", "look", "looking",
    "everything", "anything", "something", "everyone", "anyone",
    "still", "just", "also", "very", "really",
}


def resolve_temporal(q: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Parse common temporal phrases from query text.
    Returns (date_from, date_to, remaining_query) with temporal parts removed.
    """
    if not q:
        return None, None, q or ""

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    q_lower = q.lower().strip()

    # Ordered: check multi-word patterns first
    temporal_patterns = [
        (r"\bthis\s+morning\b",
         today_start,
         today_start.replace(hour=12)),
        (r"\bthis\s+week\b",
         today_start - timedelta(days=today_start.weekday()),
         now),
        (r"\blast\s+week\b",
         today_start - timedelta(days=7),
         today_start - timedelta(seconds=1)),
        (r"\byesterday\b",
         today_start - timedelta(days=1),
         today_start - timedelta(seconds=1)),
        (r"\btoday\b", today_start, now),
    ]

    for pattern, start, end in temporal_patterns:
        if re.search(pattern, q_lower):
            cleaned = re.sub(pattern, "", q_lower).strip()
            return start.isoformat(), end.isoformat(), cleaned

    # "last N days"
    m = re.search(r"\blast\s+(\d+)\s+days?\b", q_lower)
    if m:
        days = int(m.group(1))
        cleaned = re.sub(r"\blast\s+\d+\s+days?\b", "", q_lower).strip()
        return (
            (today_start - timedelta(days=days)).isoformat(),
            now.isoformat(),
            cleaned,
        )

    # Explicit ISO date: 2026-03-08
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q_lower)
    if iso_match:
        date_str = iso_match.group(1)
        try:
            dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            cleaned = q_lower.replace(date_str, "").strip()
            return dt.isoformat(), (dt + timedelta(days=1) - timedelta(seconds=1)).isoformat(), cleaned
        except ValueError:
            pass

    # "March 8", "March 8th"
    month_match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b",
        q_lower,
    )
    if month_match:
        month_name = month_match.group(1)
        day = int(month_match.group(2))
        month_num = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }[month_name]
        try:
            dt = datetime(now.year, month_num, day, tzinfo=timezone.utc)
            cleaned = re.sub(
                r"\b" + re.escape(month_name) + r"\s+\d{1,2}(?:st|nd|rd|th)?\b",
                "", q_lower,
            ).strip()
            return dt.isoformat(), (dt + timedelta(days=1) - timedelta(seconds=1)).isoformat(), cleaned
        except ValueError:
            pass

    return None, None, q


def extract_search_terms(q: str) -> list[str]:
    """Extract meaningful search terms from a query, removing stopwords."""
    if not q:
        return []
    words = re.findall(r"\b[a-zA-Z0-9@._-]+\b", q.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


# ─── Query Execution ────────────────────────────────────

def execute_desk_query(db, owner_id: str, req: DeskQueryRequest) -> DeskQueryResponse:
    """
    Execute a desk inbox query against inbox_conversations + contacts.
    """
    limit = min(req.limit or 10, 20)
    q = req.q or ""
    filters = req.filters or DeskQueryFilters()

    # Resolve temporal phrases from free text
    date_from = filters.date_from
    date_to = filters.date_to
    if not date_from and not date_to:
        date_from, date_to, q_remaining = resolve_temporal(q)
    else:
        q_remaining = q

    search_terms = extract_search_terms(q_remaining)

    # Detect name from capitalized words in original query
    name_filter = filters.name
    if not name_filter and q_remaining:
        cap_words = re.findall(r"\b[A-Z][a-z]+\b", q_remaining)
        if cap_words:
            name_filter = " ".join(cap_words)

    # Detect status keywords
    status_filter = filters.status
    if not status_filter:
        q_low = (q_remaining or "").lower()
        if any(kw in q_low for kw in ("needs review", "needs_review", "unresolved", "unresolve",
                                       "open", "pending", "waiting", "unread", "new lead")):
            status_filter = "needs_review"
        elif "resolved" in q_low or "closed" in q_low or "done" in q_low:
            status_filter = "resolved"
        elif "active" in q_low:
            status_filter = "active"

    # ── Build DB query ──
    query = (
        db.table("inbox_conversations")
        .select(
            "session_id, visitor_name, visitor_email, pack_id, status, "
            "created_at, duration_seconds, turns, cost_usd, "
            "summary, summary_detailed, summary_full, contact_id"
        )
        .eq("owner_id", owner_id)
        .order("created_at", desc=True)
    )

    if filters.pack:
        query = query.eq("pack_id", filters.pack)
    if status_filter:
        query = query.eq("status", status_filter)
    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        query = query.lte("created_at", date_to)

    # Fetch wider than limit for client-side scoring
    query = query.limit(limit * 3)

    try:
        result = query.execute()
        rows = result.data if result and result.data else []
    except Exception as e:
        logger.warning("Desk query failed: %s", e)
        raise HTTPException(500, f"Query failed: {e}")

    # ── Name matching via contacts table ──
    name_contact_ids = set()
    if name_filter:
        try:
            name_result = (
                db.table("contacts")
                .select("id")
                .eq("owner_id", owner_id)
                .ilike("name", f"%{name_filter}%")
                .limit(20)
                .execute()
            )
            if name_result.data:
                name_contact_ids = {str(r["id"]) for r in name_result.data}
        except Exception:
            pass

    name_filter_lower = name_filter.lower() if name_filter else ""

    # ── Score and rank ──
    scored: list[tuple[float, dict, list[str]]] = []

    for row in rows:
        score = 1.0
        matched_on: list[str] = []

        visitor_name = row.get("visitor_name") or ""
        contact_id = str(row.get("contact_id")) if row.get("contact_id") else None

        # Name boost
        if name_filter_lower:
            if name_filter_lower in visitor_name.lower():
                score += 5.0
                matched_on.append("name")
            elif contact_id and contact_id in name_contact_ids:
                score += 5.0
                matched_on.append("name")

        # Summary text match
        summary_brief = row.get("summary") or ""
        summary_full = row.get("summary_full") or row.get("summary_detailed") or ""
        combined_text = f"{summary_brief} {summary_full} {visitor_name}".lower()

        for term in search_terms:
            tl = term.lower()
            if name_filter_lower and tl in name_filter_lower.split():
                continue  # already counted in name
            if tl in summary_brief.lower():
                score += 3.0
                if "summary" not in matched_on:
                    matched_on.append("summary")
            elif tl in combined_text:
                score += 1.5
                if "full_text" not in matched_on:
                    matched_on.append("full_text")

        # Skip non-matching rows when there are active search criteria
        has_criteria = bool(search_terms) or bool(name_filter_lower)
        if has_criteria and not matched_on:
            continue

        scored.append((score, row, matched_on))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:limit]

    # ── Build response ──
    items = []
    for score, row, matched_on in scored:
        items.append(DeskQueryResultItem(
            session_id=row.get("session_id"),
            contact_name=row.get("visitor_name"),
            contact_email=row.get("visitor_email"),
            pack=row.get("pack_id"),
            status=row.get("status"),
            started_at=row.get("created_at"),
            duration_seconds=row.get("duration_seconds") or 0,
            turns=row.get("turns") or 0,
            cost_usd=float(row.get("cost_usd") or 0),
            summary_brief=row.get("summary") or "",
            summary_full=row.get("summary_full") or row.get("summary_detailed") or "",
            match_score=round(score, 2),
            matched_on=matched_on,
        ))

    return DeskQueryResponse(
        results=items,
        total=len(items),
        query=req.q,
    )


# ─── Tool Result Formatting ─────────────────────────────

def format_tool_result(response: DeskQueryResponse) -> str:
    """Format query results for injection into model context."""
    if not response.results:
        return (
            f"[TOOL RESULT: desk_query]\n"
            f"query: \"{response.query or ''}\"\n"
            f"results: 0 sessions found\n\n"
            f"No matching sessions found. Tell the operator plainly."
        )

    lines = [
        f"[TOOL RESULT: desk_query]",
        f"query: \"{response.query or ''}\"",
        f"results: {response.total} session{'s' if response.total != 1 else ''} found",
        "",
    ]

    for i, item in enumerate(response.results, 1):
        name = item.contact_name or "Anonymous"
        email = f" ({item.contact_email})" if item.contact_email else ""
        pack = item.pack or "unknown"
        status = item.status or "unknown"
        date = item.started_at[:10] if item.started_at else "unknown"
        turns = item.turns
        dur_min = item.duration_seconds // 60
        dur_sec = item.duration_seconds % 60
        dur_str = f"{dur_min}m {dur_sec}s" if dur_min else f"{dur_sec}s"
        cost = f"${item.cost_usd:.2f}"
        brief = item.summary_brief or "(no summary)"

        lines.append(f"SESSION {i}")
        lines.append(f"Contact: {name}{email}")
        lines.append(f"Pack: {pack} | Status: {status}")
        lines.append(f"Date: {date} · {turns} turns · {dur_str} · {cost}")
        lines.append(f"Brief: {brief}")
        if item.summary_full:
            lines.append(f"Full: {item.summary_full[:500]}")
        lines.append("")

    lines.append("Present these results to the operator. If they want more detail on a specific session, offer to show the full summary.")
    return "\n".join(lines)


# ─── Route Registration ─────────────────────────────────

def register_desk_query_endpoints(app, db_client):
    """Register desk query routes on the FastAPI app."""
    from auth import get_current_user, UserProfile

    @app.post("/api/desk/query", response_model=DeskQueryResponse, tags=["desk"])
    async def desk_query_endpoint(req: DeskQueryRequest, user: UserProfile = Depends(get_current_user)):
        """Search inbox conversations by name, date, topic, or keyword."""
        if not user:
            raise HTTPException(401, "Authentication required")

        from config import TMOS13_OWNER_ID
        owner_id = TMOS13_OWNER_ID
        if not owner_id:
            raise HTTPException(500, "TMOS13_OWNER_ID not configured")

        return execute_desk_query(db_client, owner_id, req)
