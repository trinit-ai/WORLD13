"""
Inbox: Mission control for forward-deployed agents.

Every conversation from every deployment site records here. Conversations
arrive when a deployed agent's session completes or when the agent flags
the conversation for human review.

Pipeline on record():
  1. Create inbox_conversations row
  2. Resolve/create contact via ContactsService
  3. Log inbox_received to Manifest
  4. If needs_review or escalated → trigger notification

Singleton: init_inbox_service(supabase, manifest, contacts) → get_inbox_service()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("tmos13.inbox")


# ── Quality Scoring ─────────────────────────────────────

def score_conversation_quality(
    turns: int,
    duration_seconds: int,
    tokens_used: int,
    visitor_name: str | None,
    visitor_email: str | None,
    transcript: list[dict] | None,
    classification: str | None,
) -> tuple[int, str]:
    """
    Heuristic quality scorer for inbox conversations.
    Returns (score 0–100, priority string).
    Runs at finalization and per-turn upserts — no LLM call needed.
    """
    score = 0

    # Turn depth (high weight)
    if turns >= 8:
        score += 30
    elif turns >= 4:
        score += 20
    elif turns >= 2:
        score += 10

    # Duration (medium weight)
    if duration_seconds >= 120:
        score += 15
    elif duration_seconds >= 30:
        score += 10

    # Contact info (high weight)
    if visitor_email:
        score += 25
    if visitor_name:
        score += 10

    # Classification present (low-medium weight)
    if classification:
        score += 10

    # Average user message length (medium weight)
    if transcript:
        user_messages = [
            m.get("content", "") for m in transcript
            if m.get("role") == "user" and m.get("content")
        ]
        if user_messages:
            avg_len = sum(len(msg) for msg in user_messages) / len(user_messages)
            if avg_len > 100:
                score += 15
            elif avg_len > 50:
                score += 10

    # Token cost (low weight)
    if tokens_used > 20000:
        score += 10
    elif tokens_used > 5000:
        score += 5

    # Clamp to 100
    score = min(score, 100)

    # Map score to priority
    if score >= 80:
        priority = "critical"
    elif score >= 60:
        priority = "high"
    elif score >= 40:
        priority = "normal"
    elif score >= 20:
        priority = "low"
    else:
        priority = "none"

    return score, priority


VALID_STATUSES = {"active", "needs_review", "escalated", "resolved", "abandoned", "blocked"}
VALID_PRIORITIES = {"none", "low", "normal", "high", "critical"}


# ── Dataclass ───────────────────────────────────────────

@dataclass
class InboxConversation:
    id: str
    owner_id: str

    # Deployment context
    deployment_id: str
    deployment_name: str
    deployment_domain: Optional[str] = None
    pack_id: str = ""

    # Visitor
    visitor_name: Optional[str] = None
    visitor_email: Optional[str] = None
    contact_id: Optional[str] = None

    # Session
    session_id: Optional[str] = None
    transcript: list[dict] = field(default_factory=list)

    # Classification
    classification: Optional[str] = None
    summary: Optional[str] = None
    summary_detailed: Optional[str] = None
    summary_full: Optional[str] = None
    priority: str = "normal"

    # Metrics
    turns: int = 0
    duration_seconds: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    quality_score: int = 0
    model: Optional[str] = None
    agent_name: Optional[str] = None

    # Deliverables
    deliverable_ids: list[str] = field(default_factory=list)

    # Status
    status: str = "active"
    resolved_at: Optional[str] = None
    reviewed_by: Optional[str] = None

    # Reconciliation
    correlation_id: Optional[str] = None
    match_status: Optional[str] = None
    match_method: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> InboxConversation:
        return cls(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            deployment_id=row["deployment_id"],
            deployment_name=row["deployment_name"],
            deployment_domain=row.get("deployment_domain"),
            pack_id=row.get("pack_id", ""),
            visitor_name=row.get("visitor_name"),
            visitor_email=row.get("visitor_email"),
            contact_id=str(row["contact_id"]) if row.get("contact_id") else None,
            session_id=row.get("session_id"),
            transcript=row.get("transcript") or [],
            classification=row.get("classification"),
            summary=row.get("summary"),
            summary_detailed=row.get("summary_detailed"),
            summary_full=row.get("summary_full"),
            priority=row.get("priority", "normal"),
            turns=row.get("turns", 0),
            duration_seconds=row.get("duration_seconds", 0),
            tokens_used=row.get("tokens_used", 0),
            cost_usd=float(row.get("cost_usd", 0)),
            quality_score=row.get("quality_score") or 0,
            model=row.get("model"),
            agent_name=row.get("agent_name"),
            deliverable_ids=[str(d) for d in (row.get("deliverable_ids") or [])],
            status=row.get("status", "active"),
            resolved_at=row.get("resolved_at"),
            reviewed_by=str(row["reviewed_by"]) if row.get("reviewed_by") else None,
            correlation_id=row.get("correlation_id"),
            match_status=row.get("match_status"),
            match_method=row.get("match_method"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


# ── Service ─────────────────────────────────────────────

class InboxService:
    """
    Mission control for forward-deployed agents.
    Records conversations, resolves contacts, logs to Manifest.
    """

    def __init__(self, supabase_client, manifest_service=None, contacts_service=None):
        self._db = supabase_client
        self._manifest = manifest_service
        self._contacts = contacts_service
        self._table = "inbox_conversations"
        logger.info("InboxService initialized")

    # ── Core: Record a conversation ─────────────────────

    def record(
        self,
        owner_id: str,
        deployment_id: str,
        deployment_name: str,
        pack_id: str,
        deployment_domain: Optional[str] = None,
        visitor_name: Optional[str] = None,
        visitor_email: Optional[str] = None,
        session_id: Optional[str] = None,
        transcript: Optional[list[dict]] = None,
        classification: Optional[str] = None,
        summary: Optional[str] = None,
        summary_detailed: Optional[str] = None,
        summary_full: Optional[str] = None,
        priority: str = "normal",
        turns: int = 0,
        duration_seconds: int = 0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        quality_score: int = 0,
        model: Optional[str] = None,
        agent_name: Optional[str] = None,
        deliverable_ids: Optional[list[str]] = None,
        status: str = "needs_review",
        correlation_id: Optional[str] = None,
    ) -> InboxConversation:
        """
        Record a deployed agent conversation.

        Pipeline:
        1. Validate and resolve contact from visitor info
        2. Create inbox_conversations row
        3. Log inbox_received to Manifest
        """
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        # Step 1: Resolve contact (sync — ContactsService is sync)
        contact_id = None
        if self._contacts and visitor_email:
            try:
                contact = self._contacts.resolve_or_create(
                    owner_id=owner_id,
                    email=visitor_email,
                    name=visitor_name,
                    source="inbox",
                    session_id=session_id,
                )
                contact_id = contact.id

                self._contacts.add_touchpoint(
                    contact_id=contact_id,
                    touchpoint_type="session",
                    summary=summary or f"Inbox conversation via {deployment_name}",
                    source_id=session_id,
                    detail={
                        "deployment_id": deployment_id,
                        "deployment_name": deployment_name,
                        "classification": classification,
                        "status": status,
                        "turns": turns,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to resolve contact for inbox: {e}")

        # Step 2: Insert conversation
        # IMPORTANT: Only include visitor_name/visitor_email/contact_id when
        # we have actual values. Writing None would overwrite data patched by
        # datarail submit (the "revert to anonymous" bug).
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "owner_id": owner_id,
            "deployment_id": deployment_id,
            "deployment_name": deployment_name,
            "deployment_domain": deployment_domain,
            "pack_id": pack_id,
            "session_id": session_id,
            "transcript": transcript or [],
            "classification": classification,
            "summary": summary,
            "summary_detailed": summary_detailed,
            "summary_full": summary_full,
            "priority": priority,
            "turns": turns,
            "duration_seconds": duration_seconds,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "quality_score": quality_score,
            "model": model,
            "agent_name": agent_name,
            "deliverable_ids": deliverable_ids or [],
            "status": status,
            "resolved_at": now if status == "resolved" else None,
            "created_at": now,
            "updated_at": now,
        }
        # Only set contact fields when we have values — never regress to null
        if visitor_name:
            row["visitor_name"] = visitor_name
        if visitor_email:
            row["visitor_email"] = visitor_email
        if contact_id:
            row["contact_id"] = contact_id
        if correlation_id:
            row["correlation_id"] = correlation_id

        result = self._db.table(self._table).upsert(row, on_conflict="session_id").execute()
        conversation = InboxConversation.from_row(result.data[0])

        # Manifest auto-logging removed — manifest is for explicitly promoted content only.
        # Inbox data lives in inbox_conversations table; manifest entries require promotion.

        logger.info(
            f"Inbox recorded: {conversation.id} [{status}] "
            f"from {deployment_name} — {classification or 'unclassified'}"
        )
        return conversation

    # ── Read ────────────────────────────────────────────

    def get(self, conversation_id: str) -> Optional[InboxConversation]:
        """Get single conversation by ID."""
        result = (
            self._db.table(self._table)
            .select("*")
            .eq("id", conversation_id)
            .execute()
        )
        if not result.data:
            return None
        return InboxConversation.from_row(result.data[0])

    def list(
        self,
        owner_id: str,
        status: Optional[str] = None,
        deployment_id: Optional[str] = None,
        priority: Optional[str] = None,
        classification: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[InboxConversation], int]:
        """
        List conversations with filters.
        Returns (conversations, total_count).
        Ordered by created_at DESC (newest first).

        since/until: ISO 8601 timestamps for date range filtering on created_at.
        """
        query = self._db.table(self._table).select("*", count="exact")
        query = query.eq("owner_id", owner_id)

        if status:
            query = query.eq("status", status)
        if deployment_id:
            query = query.eq("deployment_id", deployment_id)
        if priority:
            query = query.eq("priority", priority)
        if classification:
            query = query.eq("classification", classification)
        if since:
            query = query.gte("created_at", since)
        if until:
            query = query.lte("created_at", until)
        if min_score is not None:
            query = query.gte("quality_score", min_score)

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()
        conversations = [InboxConversation.from_row(row) for row in result.data]
        total = result.count or 0

        return conversations, total

    # ── Status Management ───────────────────────────────

    def update_status(
        self,
        conversation_id: str,
        status: str,
        reviewed_by: Optional[str] = None,
    ) -> InboxConversation:
        """
        Update conversation status.
        Sets resolved_at when status transitions to 'resolved'.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "status": status,
            "updated_at": now,
        }

        if reviewed_by:
            updates["reviewed_by"] = reviewed_by

        if status == "resolved":
            updates["resolved_at"] = now

        result = (
            self._db.table(self._table)
            .update(updates)
            .eq("id", conversation_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"Conversation not found: {conversation_id}")

        return InboxConversation.from_row(result.data[0])

    # ── Batch Status Update ──────────────────────────────

    def batch_update_status(
        self,
        conversation_ids: list[str],
        status: str,
        reviewed_by: str | None = None,
    ) -> int:
        """Update status for multiple conversations at once. Returns count updated."""
        from datetime import datetime, timezone
        valid = {"active", "needs_review", "escalated", "resolved", "abandoned", "blocked"}
        if status not in valid:
            raise ValueError(f"Invalid status: {status}")

        now = datetime.now(timezone.utc).isoformat()
        updates: dict = {"status": status, "updated_at": now}
        if reviewed_by:
            updates["reviewed_by"] = reviewed_by
        if status == "resolved":
            updates["resolved_at"] = now

        result = (
            self._db.table(self._table)
            .update(updates)
            .in_("id", conversation_ids)
            .execute()
        )
        count = len(result.data) if result.data else 0
        logger.info("Batch updated %d conversations to %s", count, status)
        return count

    # ── Delete ──────────────────────────────────────────

    def delete(self, conversation_id: str) -> bool:
        """Hard-delete a conversation by ID. Returns True if deleted."""
        result = (
            self._db.table(self._table)
            .delete()
            .eq("id", conversation_id)
            .execute()
        )
        deleted = len(result.data) > 0 if result.data else False
        if deleted:
            logger.info("Deleted inbox conversation %s", conversation_id)
        return deleted

    # ── Deployments ─────────────────────────────────────

    def get_deployments(self, owner_id: str) -> list[dict]:
        """
        Get deployment site summary.
        Aggregates from inbox_conversations to show each deployment site
        with counts and active status.
        """
        result = (
            self._db.table(self._table)
            .select("deployment_id, deployment_name, deployment_domain, pack_id, status")
            .eq("owner_id", owner_id)
            .execute()
        )

        deployments: dict[str, dict] = {}
        for row in result.data:
            dep_id = row["deployment_id"]
            if dep_id not in deployments:
                deployments[dep_id] = {
                    "deployment_id": dep_id,
                    "name": row["deployment_name"],
                    "domain": row.get("deployment_domain"),
                    "pack_id": row.get("pack_id"),
                    "active": True,
                    "total_conversations": 0,
                    "needs_review": 0,
                    "escalated": 0,
                }
            deployments[dep_id]["total_conversations"] += 1
            if row["status"] == "needs_review":
                deployments[dep_id]["needs_review"] += 1
            if row["status"] == "escalated":
                deployments[dep_id]["escalated"] += 1

        return list(deployments.values())

    # ── Stats ───────────────────────────────────────────

    def stats(self, owner_id: str) -> dict:
        """Aggregate inbox stats for dashboard display."""
        result = (
            self._db.table(self._table)
            .select("status, classification, turns, duration_seconds, cost_usd")
            .eq("owner_id", owner_id)
            .execute()
        )

        rows = result.data
        if not rows:
            return {
                "total": 0,
                "needs_review": 0,
                "escalated": 0,
                "resolved": 0,
                "abandoned": 0,
                "blocked": 0,
                "avg_turns": 0,
                "avg_duration_seconds": 0,
                "avg_cost_usd": 0,
                "by_classification": [],
            }

        status_counts: dict[str, int] = {}
        classification_counts: dict[str, int] = {}
        total_turns = 0
        total_duration = 0
        total_cost = 0.0

        for row in rows:
            s = row["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

            c = row.get("classification") or "unclassified"
            classification_counts[c] = classification_counts.get(c, 0) + 1

            total_turns += row.get("turns", 0)
            total_duration += row.get("duration_seconds", 0)
            total_cost += float(row.get("cost_usd", 0))

        n = len(rows)
        return {
            "total": n,
            "needs_review": status_counts.get("needs_review", 0),
            "escalated": status_counts.get("escalated", 0),
            "resolved": status_counts.get("resolved", 0),
            "abandoned": status_counts.get("abandoned", 0),
            "blocked": status_counts.get("blocked", 0),
            "avg_turns": round(total_turns / n, 1),
            "avg_duration_seconds": round(total_duration / n),
            "avg_cost_usd": round(total_cost / n, 4),
            "by_classification": [
                {"classification": k, "count": v}
                for k, v in sorted(classification_counts.items(), key=lambda x: -x[1])
            ],
        }

    # ── Action counts (for sidebar badge) ───────────────

    def action_count(self, owner_id: str) -> int:
        """Count of conversations needing attention (needs_review + escalated)."""
        # No .in_() in this Supabase client version — use or_() with PostgREST syntax
        result = (
            self._db.table(self._table)
            .select("id", count="exact")
            .eq("owner_id", owner_id)
            .or_("status.eq.needs_review,status.eq.escalated")
            .execute()
        )
        return result.count or 0


# ── Singleton ───────────────────────────────────────────

_inbox_service: Optional[InboxService] = None


def init_inbox_service(supabase_client, manifest_service=None, contacts_service=None) -> InboxService:
    """Initialize the InboxService singleton. Call once in app lifespan."""
    global _inbox_service
    _inbox_service = InboxService(supabase_client, manifest_service, contacts_service)
    return _inbox_service


def get_inbox_service() -> InboxService:
    """Get the InboxService singleton. Raises if not initialized."""
    if _inbox_service is None:
        raise HTTPException(503, "InboxService not initialized")
    return _inbox_service
