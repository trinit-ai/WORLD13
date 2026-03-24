"""
Session ↔ Contact Reconciler

Joins sessions (inbox_conversations) and contacts that were created
independently during a guest intake. Two matching strategies:

1. Exact match by correlation_id (stamped at session birth)
2. Fallback: email + temporal proximity (5-minute window)

Runs on:
- Session finalization (inline, after inbox record)
- Periodic sweep (every 2 minutes, retries unmatched)
- Manual trigger (POST /api/admin/reconcile/sweep)
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("tmos13.reconciler")

_db = None


def init_reconciler(supabase_client):
    global _db
    _db = supabase_client
    logger.info("Reconciler initialized")


def get_db():
    global _db
    if _db:
        return _db
    try:
        from app import db as app_db
        _db = app_db
        return _db
    except Exception:
        return None


def reconcile_session(session_id: str, owner_id: str = None) -> dict:
    """
    Attempt to link an inbox_conversation to a contact.

    Strategy 1: correlation_id match
    Strategy 2: email + time window fallback
    """
    db = get_db()
    if not db:
        return {"matched": False, "status": "no_db"}

    # Fetch the inbox conversation
    try:
        result = (
            db.table("inbox_conversations")
            .select("id, session_id, correlation_id, visitor_email, visitor_name, contact_id, match_status, created_at")
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return {"matched": False, "status": "no_inbox_record"}
        inbox = result.data[0]
    except Exception as e:
        logger.warning("Reconciler: failed to fetch inbox record for %s: %s", session_id, e)
        return {"matched": False, "status": "error", "error": str(e)}

    # Already matched — skip
    if inbox.get("match_status") == "matched":
        return {"matched": True, "status": "already_matched"}

    inbox_id = inbox["id"]
    corr_id = inbox.get("correlation_id")
    email = inbox.get("visitor_email")

    # Strategy 1: correlation_id match
    if corr_id:
        try:
            contact_result = (
                db.table("contacts")
                .select("id, email, name, match_status")
                .eq("correlation_id", str(corr_id))
                .limit(1)
                .execute()
            )
            if contact_result.data:
                contact = contact_result.data[0]
                _link(db, inbox_id, contact["id"], session_id, "correlation_id")
                return {"matched": True, "method": "correlation_id", "contact_id": contact["id"]}
        except Exception as e:
            logger.debug("Reconciler: correlation_id lookup failed: %s", e)

    # Strategy 2: email + time window
    if email:
        try:
            inbox_created = inbox.get("created_at", "")
            if inbox_created:
                ts = datetime.fromisoformat(inbox_created.replace("Z", "+00:00"))
            else:
                ts = datetime.now(timezone.utc)
            window_start = (ts - timedelta(minutes=5)).isoformat()
            window_end = (ts + timedelta(minutes=5)).isoformat()

            candidates = (
                db.table("contacts")
                .select("id, email, name, match_status")
                .eq("email", email.lower().strip())
                .gte("created_at", window_start)
                .lte("created_at", window_end)
                .execute()
            )
            rows = candidates.data if candidates and candidates.data else []

            # Filter out already-matched contacts
            rows = [r for r in rows if r.get("match_status") != "matched"]

            if len(rows) == 1:
                _link(db, inbox_id, rows[0]["id"], session_id, "email_window")
                return {"matched": True, "method": "email_window", "contact_id": rows[0]["id"]}
            elif len(rows) > 1:
                _flag_ambiguous(db, inbox_id, session_id, [r["id"] for r in rows])
                return {"matched": False, "status": "ambiguous", "candidates": len(rows)}
        except Exception as e:
            logger.debug("Reconciler: email window lookup failed: %s", e)

    # No match found
    _flag_unmatched(db, inbox_id, session_id)
    return {"matched": False, "status": "unmatched"}


def sweep_unmatched() -> dict:
    """
    Retry reconciliation for unmatched sessions older than 2 minutes.
    Returns summary counts.
    """
    db = get_db()
    if not db:
        return {"swept": 0, "matched": 0, "error": "no_db"}

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    try:
        result = (
            db.table("inbox_conversations")
            .select("session_id, owner_id")
            .eq("match_status", "unmatched")
            .lt("updated_at", cutoff)
            .limit(50)
            .execute()
        )
        rows = result.data if result and result.data else []
    except Exception as e:
        logger.warning("Reconciler sweep: query failed: %s", e)
        return {"swept": 0, "matched": 0, "error": str(e)}

    matched = 0
    for row in rows:
        sid = row.get("session_id")
        oid = row.get("owner_id")
        if sid:
            r = reconcile_session(sid, oid)
            if r.get("matched"):
                matched += 1

    if rows:
        logger.info("Reconciler sweep: %d checked, %d matched", len(rows), matched)
    return {"swept": len(rows), "matched": matched, "still_unmatched": len(rows) - matched}


# ── Internal helpers ──────────────────────────────────────


def _link(db, inbox_id: str, contact_id: str, session_id: str, method: str):
    """Link an inbox conversation and a contact as matched.
    Also attaches the latest transcript snapshot to the contact record."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.table("inbox_conversations").update({
            "contact_id": contact_id,
            "match_status": "matched",
            "match_method": method,
            "updated_at": now,
        }).eq("id", inbox_id).execute()
    except Exception as e:
        logger.warning("Reconciler: inbox update failed: %s", e)

    # Attach latest transcript snapshot to contact
    contact_update = {
        "session_id": session_id,
        "match_status": "matched",
        "updated_at": now,
    }
    try:
        from transcripts import get_latest_snapshot
        snapshot = get_latest_snapshot(session_id)
        if snapshot:
            contact_update["transcript_id"] = snapshot["id"]
            contact_update["transcript_logged_at"] = snapshot.get("logged_at", now)
    except Exception:
        logger.debug("Reconciler: transcript snapshot lookup skipped")

    try:
        db.table("contacts").update(contact_update).eq("id", contact_id).execute()
    except Exception as e:
        logger.warning("Reconciler: contact update failed: %s", e)

    logger.info("Reconciled: inbox=%s ↔ contact=%s via %s", inbox_id, contact_id, method)


def _flag_ambiguous(db, inbox_id: str, session_id: str, contact_ids: list):
    """Mark inbox and candidate contacts as ambiguous."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.table("inbox_conversations").update({
            "match_status": "ambiguous",
            "updated_at": now,
        }).eq("id", inbox_id).execute()
    except Exception as e:
        logger.warning("Reconciler: ambiguous flag failed on inbox: %s", e)

    for cid in contact_ids:
        try:
            db.table("contacts").update({
                "match_status": "ambiguous",
                "updated_at": now,
            }).eq("id", cid).execute()
        except Exception:
            pass

    logger.info("Reconciler: ambiguous match for session %s (%d candidates)", session_id, len(contact_ids))


def _flag_unmatched(db, inbox_id: str, session_id: str):
    """Mark inbox conversation as unmatched for sweep retry."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.table("inbox_conversations").update({
            "match_status": "unmatched",
            "updated_at": now,
        }).eq("id", inbox_id).execute()
    except Exception as e:
        logger.debug("Reconciler: unmatched flag failed: %s", e)
