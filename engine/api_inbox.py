"""
Inbox REST API — Mission control for forward-deployed agents.

Endpoints:
  GET    /api/inbox              — List conversations with filters
  GET    /api/inbox/stats        — Aggregate inbox statistics
  GET    /api/inbox/deployments  — Deployment site summary
  GET    /api/inbox/:id          — Get single conversation
  PUT    /api/inbox/:id/status   — Update conversation status
  POST   /api/inbox              — Record new conversation

Registration: register_inbox_endpoints(app, service)
"""
import logging
import re
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from auth import require_auth, UserProfile
from config import TMOS13_OWNER_ID
from inbox import InboxService

logger = logging.getLogger("tmos13.inbox_api")


# ── Request Models ──────────────────────────────────────

class RecordConversationRequest(BaseModel):
    deployment_id: str
    deployment_name: str
    deployment_domain: Optional[str] = None
    pack_id: str = ""
    visitor_name: Optional[str] = None
    visitor_email: Optional[str] = None
    session_id: Optional[str] = None
    transcript: Optional[list[dict]] = None
    classification: Optional[str] = None
    summary: Optional[str] = None
    priority: str = "normal"
    turns: int = 0
    duration_seconds: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    model: Optional[str] = None
    agent_name: Optional[str] = None
    deliverable_ids: Optional[list[str]] = None
    status: str = "needs_review"


class UpdateStatusRequest(BaseModel):
    status: str


class BatchDeleteRequest(BaseModel):
    ids: list[str]


class BatchStatusRequest(BaseModel):
    ids: list[str]
    status: str


# ── Response Models ─────────────────────────────────────

class InboxConversationResponse(BaseModel):
    id: str
    owner_id: str
    deployment_id: str
    deployment_name: str
    deployment_domain: Optional[str]
    pack_id: str
    visitor_name: Optional[str]
    visitor_email: Optional[str]
    contact_id: Optional[str]
    session_id: Optional[str]
    transcript: list[dict]
    classification: Optional[str]
    summary: Optional[str]
    summary_detailed: Optional[str] = None
    summary_full: Optional[str] = None
    priority: str
    turns: int
    duration_seconds: int
    tokens_used: int
    cost_usd: float
    quality_score: Optional[int]
    model: Optional[str]
    agent_name: Optional[str]
    deliverable_ids: list[str]
    status: str
    resolved_at: Optional[str]
    reviewed_by: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class InboxListResponse(BaseModel):
    conversations: list[InboxConversationResponse]
    total: int
    needs_review: int
    escalated: int


class InboxDeploymentResponse(BaseModel):
    deployment_id: str
    name: str
    domain: Optional[str]
    pack_id: Optional[str]
    active: bool
    total_conversations: int
    needs_review: int
    escalated: int


class InboxStatsResponse(BaseModel):
    total: int
    needs_review: int
    escalated: int
    resolved: int
    abandoned: int
    blocked: int
    avg_turns: float
    avg_duration_seconds: int
    avg_cost_usd: float
    by_classification: list[dict]


# ── Helpers ─────────────────────────────────────────────

def _conversation_response(conv) -> InboxConversationResponse:
    """Convert InboxConversation dataclass to response model."""
    return InboxConversationResponse(
        id=conv.id,
        owner_id=conv.owner_id,
        deployment_id=conv.deployment_id,
        deployment_name=conv.deployment_name,
        deployment_domain=conv.deployment_domain,
        pack_id=conv.pack_id,
        visitor_name=conv.visitor_name,
        visitor_email=conv.visitor_email,
        contact_id=conv.contact_id,
        session_id=conv.session_id,
        transcript=conv.transcript,
        classification=conv.classification,
        summary=conv.summary,
        summary_detailed=conv.summary_detailed,
        summary_full=conv.summary_full,
        priority=conv.priority,
        turns=conv.turns,
        duration_seconds=conv.duration_seconds,
        tokens_used=conv.tokens_used,
        cost_usd=conv.cost_usd,
        quality_score=conv.quality_score,
        model=conv.model,
        agent_name=conv.agent_name,
        deliverable_ids=conv.deliverable_ids,
        status=conv.status,
        resolved_at=conv.resolved_at,
        reviewed_by=conv.reviewed_by,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


def _verify_conversation_owner(conv, user: UserProfile):
    """Verify the authenticated user can access this conversation.

    All deployer inbox conversations use TMOS13_OWNER_ID as owner.
    Any authenticated dashboard user may view them.
    """
    if conv.owner_id != TMOS13_OWNER_ID and conv.owner_id != user.user_id:
        raise HTTPException(404, "Conversation not found")


# ── Registration ────────────────────────────────────────

def register_inbox_endpoints(app, inbox_service: InboxService):
    """Register all inbox endpoints. Called in app.py lifespan."""

    # ── GET /api/inbox ───────────────────────────────────

    @app.get("/api/inbox", response_model=InboxListResponse, tags=["inbox"])
    async def list_conversations(
        status: Optional[str] = None,
        deployment_id: Optional[str] = None,
        priority: Optional[str] = None,
        classification: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        user: UserProfile = Depends(require_auth),
    ):
        """List inbox conversations with filters. Always includes badge counts.

        since/until: ISO 8601 timestamps for date range filtering.
        """
        limit = min(limit, 200)

        conversations, total = inbox_service.list(
            owner_id=TMOS13_OWNER_ID,
            status=status,
            deployment_id=deployment_id,
            priority=priority,
            classification=classification,
            since=since,
            until=until,
            min_score=min_score,
            limit=limit,
            offset=offset,
        )

        # Always include action badge counts regardless of filters
        action_counts = inbox_service.action_count(TMOS13_OWNER_ID)
        # Get escalated separately for the badge
        escalated_count = 0
        needs_review_count = 0
        if action_counts > 0:
            stats = inbox_service.stats(TMOS13_OWNER_ID)
            needs_review_count = stats.get("needs_review", 0)
            escalated_count = stats.get("escalated", 0)

        return InboxListResponse(
            conversations=[_conversation_response(c) for c in conversations],
            total=total,
            needs_review=needs_review_count,
            escalated=escalated_count,
        )

    # ── GET /api/inbox/stats ─────────────────────────────
    # Registered before /api/inbox/:id to avoid path conflict

    @app.get("/api/inbox/stats", response_model=InboxStatsResponse, tags=["inbox"])
    async def inbox_stats(
        user: UserProfile = Depends(require_auth),
    ):
        """Aggregate inbox statistics for dashboard display."""
        stats = inbox_service.stats(TMOS13_OWNER_ID)
        return InboxStatsResponse(**stats)

    # ── GET /api/inbox/deployments ───────────────────────

    @app.get("/api/inbox/deployments", tags=["inbox"])
    async def inbox_deployments(
        user: UserProfile = Depends(require_auth),
    ):
        """Get deployment site summary with conversation counts."""
        deployments = inbox_service.get_deployments(TMOS13_OWNER_ID)
        return {"deployments": deployments}

    # ── GET /api/inbox/:id ───────────────────────────────

    @app.get(
        "/api/inbox/{conversation_id}",
        response_model=InboxConversationResponse,
        tags=["inbox"],
    )
    async def get_conversation(
        conversation_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Get a single inbox conversation with full transcript."""
        conv = inbox_service.get(conversation_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        _verify_conversation_owner(conv, user)
        return _conversation_response(conv)

    # ── PUT /api/inbox/:id/status ────────────────────────

    @app.put(
        "/api/inbox/{conversation_id}/status",
        response_model=InboxConversationResponse,
        tags=["inbox"],
    )
    async def update_conversation_status(
        conversation_id: str,
        req: UpdateStatusRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update conversation status. Sets reviewed_by to current user."""
        conv = inbox_service.get(conversation_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        _verify_conversation_owner(conv, user)

        try:
            updated = inbox_service.update_status(
                conversation_id=conversation_id,
                status=req.status,
                reviewed_by=user.user_id,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        return _conversation_response(updated)

    # ── POST /api/inbox/batch-status ──────────────────────

    @app.post("/api/inbox/batch-status", tags=["inbox"])
    async def batch_update_status(
        req: BatchStatusRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Update status for multiple conversations in one call."""
        if not req.ids:
            return {"updated": 0}
        if len(req.ids) > 200:
            raise HTTPException(400, "Maximum 200 conversations per batch")
        try:
            count = inbox_service.batch_update_status(
                conversation_ids=req.ids,
                status=req.status,
                reviewed_by=user.user_id,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"updated": count, "status": req.status}

    # ── POST /api/inbox/batch-delete ──────────────────────

    @app.post("/api/inbox/batch-delete", tags=["inbox"])
    async def batch_delete_conversations(
        req: BatchDeleteRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Delete multiple conversations by ID."""
        if not req.ids:
            return {"deleted": 0, "ids": []}
        if len(req.ids) > 100:
            raise HTTPException(400, "Maximum 100 conversations per batch")
        deleted_ids = []
        for cid in req.ids:
            conv = inbox_service.get(cid)
            if not conv:
                continue
            try:
                _verify_conversation_owner(conv, user)
            except HTTPException:
                continue
            if inbox_service.delete(cid):
                deleted_ids.append(cid)
        return {"deleted": len(deleted_ids), "ids": deleted_ids}

    # ── DELETE /api/inbox/:id ─────────────────────────────

    @app.delete("/api/inbox/{conversation_id}", tags=["inbox"])
    async def delete_conversation(
        conversation_id: str,
        user: UserProfile = Depends(require_auth),
    ):
        """Permanently delete a conversation."""
        conv = inbox_service.get(conversation_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        _verify_conversation_owner(conv, user)
        deleted = inbox_service.delete(conversation_id)
        if not deleted:
            raise HTTPException(500, "Failed to delete conversation")
        return {"deleted": True, "id": conversation_id}

    # ── POST /api/inbox/resummarize ──────────────────────

    @app.post("/api/inbox/resummarize", tags=["inbox"])
    async def resummarize_conversations(
        conversation_id: Optional[str] = None,
        user: UserProfile = Depends(require_auth),
    ):
        """Re-generate AI summaries for existing inbox conversations.

        Pass ?conversation_id=<id> for a single row, or omit to backfill all.
        Processes in parallel batches of 5 for speed.
        """
        import asyncio
        from llm_provider import get_llm_provider
        from transcripts import (
            generate_inbox_summary, generate_inbox_summary_detailed,
            generate_inbox_summary_full, SessionTranscript, TranscriptEntry,
        )
        from datetime import datetime, timezone

        llm = get_llm_provider()
        if not llm:
            raise HTTPException(503, "LLM provider not available")

        # Fetch target conversations
        if conversation_id:
            conv = inbox_service.get(conversation_id)
            if not conv:
                raise HTTPException(404, "Conversation not found")
            _verify_conversation_owner(conv, user)
            conversations = [conv]
        else:
            conversations, _ = inbox_service.list(
                owner_id=TMOS13_OWNER_ID, limit=500
            )

        updated = 0
        errors = 0
        results = []

        BATCH_SIZE = 5

        async def _summarize_one(conv):
            entries = [
                TranscriptEntry(
                    timestamp=m.get("timestamp", 0),
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                )
                for m in (conv.transcript or [])
            ]
            t = SessionTranscript(
                session_id=conv.session_id or "",
                pack_id=conv.pack_id or "",
                entries=entries,
                turn_count=conv.turns,
                contact_info={"name": conv.visitor_name} if conv.visitor_name else None,
            )
            brief, detailed, full = await asyncio.gather(
                generate_inbox_summary(llm, t),
                generate_inbox_summary_detailed(llm, t),
                generate_inbox_summary_full(llm, t),
            )
            inbox_service._db.table(inbox_service._table).update({
                "summary": brief,
                "summary_detailed": detailed,
                "summary_full": full,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", conv.id).execute()
            return {
                "id": conv.id,
                "old_summary": conv.summary,
                "new_summary": brief,
                "summary_detailed": detailed,
                "summary_full": full,
            }

        # Process in parallel batches
        for i in range(0, len(conversations), BATCH_SIZE):
            batch = conversations[i:i + BATCH_SIZE]
            tasks = []
            for conv in batch:
                tasks.append(_summarize_one(conv))
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, Exception):
                    logger.warning("Resummarize failed: %s", r)
                    errors += 1
                else:
                    results.append(r)
                    updated += 1

        return {
            "updated": updated,
            "errors": errors,
            "results": results,
        }

    # ── POST /api/inbox/:id/generate-deliverable ─────────

    class GenerateDeliverableRequest(BaseModel):
        spec_id: str = "summary"
        format: str = "markdown"  # "markdown" | "docx"

    @app.post("/api/inbox/{conversation_id}/generate-deliverable", tags=["inbox"])
    async def generate_inbox_deliverable(
        conversation_id: str,
        req: GenerateDeliverableRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Generate a deliverable from an inbox conversation on demand."""
        from deliverables import generate_from_inbox
        from datetime import datetime, timezone

        conv = inbox_service.get(conversation_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        _verify_conversation_owner(conv, user)

        valid_specs = {"case_file", "pitch", "proposal", "blueprint", "summary", "full_review"}
        if req.spec_id not in valid_specs:
            raise HTTPException(400, f"Invalid spec_id. Must be one of: {', '.join(sorted(valid_specs))}")

        try:
            deliverable = await generate_from_inbox(conv, req.spec_id)
        except Exception as e:
            logger.exception("Deliverable generation failed for conversation %s", conversation_id)
            raise HTTPException(500, f"Deliverable generation failed: {e}")

        # Update conversation's deliverable_ids
        current_ids = conv.deliverable_ids or []
        if deliverable.deliverable_id not in current_ids:
            current_ids.append(deliverable.deliverable_id)
            inbox_service._db.table(inbox_service._table).update({
                "deliverable_ids": current_ids,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", conv.id).execute()

        if req.format == "docx":
            from docx_export import markdown_to_docx
            from starlette.responses import Response

            docx_bytes = markdown_to_docx(
                title=deliverable.title,
                markdown_body=deliverable.body,
                metadata={
                    "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
                    "pack": conv.pack_id,
                    "visitor_name": conv.visitor_name,
                },
            )
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", deliverable.title[:50])
            filename = f"{safe_name}.docx"
            return Response(
                content=docx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        # Default: return JSON
        return {
            "deliverable_id": deliverable.deliverable_id,
            "spec_id": deliverable.spec_id,
            "title": deliverable.title,
            "body": deliverable.body,
            "sections": deliverable.sections,
            "extracted_data": deliverable.extracted_data,
            "created_at": getattr(deliverable, "created_at", None),
        }

    # ── POST /api/inbox/:id/forward ─────────────────────

    class ForwardConversationRequest(BaseModel):
        recipient_email: str
        include_transcript: bool = False

    @app.post("/api/inbox/{conversation_id}/forward", tags=["inbox"])
    async def forward_conversation(
        conversation_id: str,
        req: ForwardConversationRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Forward a conversation summary (and optionally transcript) via email."""
        from email_service import send_email

        conv = inbox_service.get(conversation_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        _verify_conversation_owner(conv, user)

        # Validate email
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", req.recipient_email):
            raise HTTPException(400, "Invalid email address")

        visitor = conv.visitor_name or "Anonymous Visitor"
        summary = conv.summary_full or conv.summary_detailed or conv.summary or "No summary available."

        # Build HTML
        html_parts = [
            f"<h2>Conversation Forward: {visitor}</h2>",
            f"<p><strong>Pack:</strong> {conv.pack_id or 'N/A'} &bull; "
            f"<strong>Status:</strong> {conv.status} &bull; "
            f"<strong>Turns:</strong> {conv.turns}</p>",
            f"<h3>Summary</h3><p>{summary}</p>",
        ]
        if req.include_transcript and conv.transcript:
            html_parts.append("<h3>Transcript</h3>")
            for msg in conv.transcript:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                label = "Visitor" if role == "user" else "Agent"
                html_parts.append(f"<p><strong>{label}:</strong> {content}</p>")

        html = "\n".join(html_parts)
        subject = f"Forwarded Conversation: {visitor} — {conv.pack_id or 'inbox'}"

        email_result = send_email(req.recipient_email, subject, html)
        if not email_result.get("success"):
            raise HTTPException(502, f"Email delivery failed: {email_result.get('error', 'unknown')}")

        return {"forwarded": True, "message_id": email_result.get("message_id"), "recipient": req.recipient_email}

    # ── POST /api/inbox ──────────────────────────────────

    @app.post(
        "/api/inbox",
        response_model=InboxConversationResponse,
        status_code=201,
        tags=["inbox"],
    )
    async def record_conversation(
        req: RecordConversationRequest,
        user: UserProfile = Depends(require_auth),
    ):
        """Record a new inbox conversation from a deployed agent."""
        try:
            conv = inbox_service.record(
                owner_id=user.user_id,
                deployment_id=req.deployment_id,
                deployment_name=req.deployment_name,
                pack_id=req.pack_id,
                deployment_domain=req.deployment_domain,
                visitor_name=req.visitor_name,
                visitor_email=req.visitor_email,
                session_id=req.session_id,
                transcript=req.transcript,
                classification=req.classification,
                summary=req.summary,
                priority=req.priority,
                turns=req.turns,
                duration_seconds=req.duration_seconds,
                tokens_used=req.tokens_used,
                cost_usd=req.cost_usd,
                model=req.model,
                agent_name=req.agent_name,
                deliverable_ids=req.deliverable_ids,
                status=req.status,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        return _conversation_response(conv)
