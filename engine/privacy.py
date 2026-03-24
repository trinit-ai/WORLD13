"""
TMOS13 Privacy — Data Protection & Compliance

GDPR/CCPA compliant data management: export, deletion, consent,
PII scrubbing, ephemeral sessions, audit logging, and retention policies.
"""
import re
import time
import json
import hashlib
import logging
from typing import Optional
from datetime import datetime

from fastapi import HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger("tmos13.privacy")


# ─── PII Patterns ───────────────────────────────────────

PII_PATTERNS = [
    (re.compile(r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b'), '[SSN_REDACTED]'),
    (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD_REDACTED]'),
]


# ─── Models ─────────────────────────────────────────────

class ConsentSettings(BaseModel):
    analytics: bool = True
    session_logging: bool = True
    cross_game_memory: bool = True
    personalization: bool = True
    marketing_email: bool = False

class ConsentUpdateRequest(BaseModel):
    analytics: Optional[bool] = None
    session_logging: Optional[bool] = None
    cross_game_memory: Optional[bool] = None
    personalization: Optional[bool] = None
    marketing_email: Optional[bool] = None

class DataExportResponse(BaseModel):
    user_id: str
    export_date: str
    profile: dict
    memories: dict
    eggs_found: list[str]
    session_history: list[dict]
    consent: dict
    orders: list[dict]

class DeletionResponse(BaseModel):
    user_id: str
    deleted_at: str
    tables_purged: list[str]
    status: str

class MemoryRedactRequest(BaseModel):
    keys: list[str]

class AuditEntry(BaseModel):
    user_id: str
    action: str
    resource: str
    timestamp: float
    ip_address: Optional[str] = None
    details: Optional[str] = None


# ─── PII Scrubber ───────────────────────────────────────

def scrub_pii(text: str) -> str:
    """Remove PII patterns from text before sending to Claude API."""
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def scrub_pii_from_messages(messages: list[dict]) -> list[dict]:
    """Scrub PII from a list of conversation messages."""
    return [
        {**msg, "content": scrub_pii(msg["content"])} if "content" in msg else msg
        for msg in messages
    ]


# ─── Privacy Service ───────────────────────────────────

class PrivacyService:
    """Handles all privacy and data protection operations."""

    def __init__(self, db, auth_service=None):
        self.db = db
        self.auth_service = auth_service
        self._ephemeral_sessions: set[str] = set()
        logger.info("Privacy service initialized")

    # ─── Consent Management ──────────────────────────────

    def get_consent(self, user_id: str) -> ConsentSettings:
        """Get user's current consent settings."""
        try:
            if hasattr(self.db, 'client'):
                result = self.db.client.table("consent").select("*").eq("user_id", user_id).execute()
                if result.data:
                    d = result.data[0]
                    return ConsentSettings(**{k: d[k] for k in ConsentSettings.model_fields if k in d})
            else:
                row = self.db.conn.execute(
                    "SELECT * FROM consent WHERE user_id = ?", (user_id,)
                ).fetchone()
                if row:
                    cols = ["user_id", "analytics", "session_logging", "cross_game_memory",
                            "personalization", "marketing_email"]
                    d = dict(zip(cols, row))
                    return ConsentSettings(**{k: bool(d[k]) for k in ConsentSettings.model_fields if k in d})
        except Exception as e:
            logger.warning(f"Failed to load consent for {user_id}: {e}")
        return ConsentSettings()

    def update_consent(self, user_id: str, updates: ConsentUpdateRequest) -> ConsentSettings:
        """Update user's consent settings."""
        current = self.get_consent(user_id)
        update_dict = updates.model_dump(exclude_none=True)
        for k, v in update_dict.items():
            setattr(current, k, v)

        try:
            data = {"user_id": user_id, **current.model_dump(), "updated_at": time.time()}
            if hasattr(self.db, 'client'):
                self.db.client.table("consent").upsert(data, on_conflict="user_id").execute()
            else:
                self.db.conn.execute(
                    """INSERT OR REPLACE INTO consent
                       (user_id, analytics, session_logging, cross_game_memory, personalization, marketing_email, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, current.analytics, current.session_logging, current.cross_game_memory,
                     current.personalization, current.marketing_email, time.time())
                )
                self.db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save consent for {user_id}: {e}")

        self._log_audit(user_id, "consent_update", "consent", json.dumps(update_dict))
        return current

    def check_consent(self, user_id: str, category: str) -> bool:
        """Check if user has consented to a specific data category."""
        consent = self.get_consent(user_id)
        return getattr(consent, category, True)

    # ─── Data Export ─────────────────────────────────────

    def export_user_data(self, user_id: str) -> DataExportResponse:
        """Export all user data (GDPR Article 15)."""
        self._log_audit(user_id, "data_export", "all", "Full data export requested")

        profile = {}
        memories = {}
        eggs = []
        sessions = []
        consent = self.get_consent(user_id).model_dump()
        orders = []

        try:
            if hasattr(self.db, 'client'):
                # Profile
                p = self.db.client.table("profiles").select("*").eq("user_id", user_id).execute()
                profile = p.data[0] if p.data else {}

                # Memories
                m = self.db.client.table("memories").select("key, value").eq("user_id", user_id).execute()
                memories = {r["key"]: r["value"] for r in m.data}

                # Eggs
                e = self.db.client.table("fossil_record").select("egg_id, found_at, context").eq("user_id", user_id).execute()
                eggs = [r["egg_id"] for r in e.data]

                # Sessions
                s = self.db.client.table("session_log").select("*").eq("user_id", user_id).order("started_at", desc=True).limit(100).execute()
                sessions = s.data

                # Orders
                o = self.db.client.table("orders").select("*").eq("user_id", user_id).execute()
                orders = o.data
            else:
                # SQLite fallback
                memories = self.db.get_memories(user_id)
                eggs = self.db.get_eggs(user_id)

                rows = self.db.conn.execute(
                    "SELECT * FROM session_log WHERE user_id = ? ORDER BY started_at DESC LIMIT 100",
                    (user_id,)
                ).fetchall()
                sessions = [{"session_id": r[0], "started_at": r[2], "ended_at": r[3]} for r in rows]

                try:
                    rows = self.db.conn.execute("SELECT * FROM orders WHERE user_id = ?", (user_id,)).fetchall()
                    orders = [{"id": r[0], "amount": r[2], "status": r[4]} for r in rows]
                except Exception:
                    pass

                try:
                    row = self.db.conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
                    if row:
                        profile = {"user_id": row[0], "email": row[1], "display_name": row[2]}
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Data export failed for {user_id}: {e}")

        return DataExportResponse(
            user_id=user_id,
            export_date=datetime.utcnow().isoformat(),
            profile=profile,
            memories=memories,
            eggs_found=eggs,
            session_history=sessions,
            consent=consent,
            orders=orders,
        )

    # ─── Account Deletion ────────────────────────────────

    def delete_user_data(self, user_id: str) -> DeletionResponse:
        """Delete all user data (GDPR Article 17)."""
        self._log_audit(user_id, "account_deletion", "all", "Full account deletion requested")

        tables_purged = []

        try:
            # Note: `users` table was dropped in migration 006.
            # `profiles` is now the sole identity table; `auth.users` is deleted
            # via auth_service below.
            tables = ["billing_events", "orders", "subscriptions", "session_log",
                       "memories", "fossil_record", "consent", "audit_log",
                       "deletion_requests", "profiles"]

            if hasattr(self.db, 'client'):
                for table in tables:
                    try:
                        self.db.client.table(table).delete().eq("user_id", user_id).execute()
                        tables_purged.append(table)
                    except Exception:
                        pass
            else:
                for table in tables:
                    try:
                        self.db.conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                        tables_purged.append(table)
                    except Exception:
                        pass
                self.db.conn.commit()

            # Delete from Supabase Auth if available
            if self.auth_service and self.auth_service.enabled:
                try:
                    self.auth_service._admin_client.auth.admin.delete_user(user_id)
                    tables_purged.append("auth.users")
                except Exception as e:
                    logger.error(f"Failed to delete auth user {user_id}: {e}")

        except Exception as e:
            logger.error(f"Account deletion failed for {user_id}: {e}")
            raise HTTPException(500, "Account deletion failed")

        return DeletionResponse(
            user_id=user_id,
            deleted_at=datetime.utcnow().isoformat(),
            tables_purged=tables_purged,
            status="deleted",
        )

    # ─── Memory Redaction ────────────────────────────────

    def redact_memories(self, user_id: str, keys: list[str]) -> int:
        """Delete specific cross-game memories."""
        count = 0
        try:
            for key in keys:
                if hasattr(self.db, 'client'):
                    self.db.client.table("memories").delete().eq("user_id", user_id).eq("key", key).execute()
                else:
                    self.db.conn.execute(
                        "DELETE FROM memories WHERE user_id = ? AND key = ?", (user_id, key)
                    )
                count += 1
            if not hasattr(self.db, 'client'):
                self.db.conn.commit()
        except Exception as e:
            logger.error(f"Memory redaction failed: {e}")

        self._log_audit(user_id, "memory_redact", "memories", f"Redacted {count} keys: {keys}")
        return count

    # ─── Ephemeral Sessions ──────────────────────────────

    def mark_ephemeral(self, session_id: str):
        """Mark a session as ephemeral — no data will be persisted."""
        self._ephemeral_sessions.add(session_id)

    def is_ephemeral(self, session_id: str) -> bool:
        """Check if a session is in ephemeral mode."""
        return session_id in self._ephemeral_sessions

    def clear_ephemeral(self, session_id: str):
        """Remove ephemeral marker when session ends."""
        self._ephemeral_sessions.discard(session_id)

    # ─── Data Retention ──────────────────────────────────

    def enforce_retention(self, max_age_days: int = 90):
        """Purge data older than retention period."""
        cutoff = time.time() - (max_age_days * 86400)
        purged = {}

        try:
            if hasattr(self.db, 'client'):
                # Purge old sessions
                r = self.db.client.table("session_log").delete().lt("ended_at", cutoff).execute()
                purged["session_log"] = len(r.data) if r.data else 0

                # Purge old billing events
                r = self.db.client.table("billing_events").delete().lt("created_at", cutoff).execute()
                purged["billing_events"] = len(r.data) if r.data else 0

                # Purge old audit entries
                r = self.db.client.table("audit_log").delete().lt("timestamp", cutoff).execute()
                purged["audit_log"] = len(r.data) if r.data else 0
            else:
                for table, col in [("session_log", "ended_at"), ("billing_events", "created_at"), ("audit_log", "timestamp")]:
                    try:
                        cursor = self.db.conn.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))
                        purged[table] = cursor.rowcount
                    except Exception:
                        pass
                self.db.conn.commit()
        except Exception as e:
            logger.error(f"Retention enforcement failed: {e}")

        logger.info(f"Retention enforcement: purged {purged} (cutoff={max_age_days} days)")
        return purged

    # ─── Audit Logging ───────────────────────────────────

    def _log_audit(self, user_id: str, action: str, resource: str, details: str = "",
                   ip_address: str = ""):
        """Record an audit entry for data access/modification."""
        try:
            entry = {
                "user_id": user_id,
                "action": action,
                "resource": resource,
                "details": details,
                "ip_address": ip_address,
                "timestamp": time.time(),
            }
            if hasattr(self.db, 'client'):
                self.db.client.table("audit_log").insert(entry).execute()
            else:
                self.db.conn.execute(
                    """INSERT INTO audit_log (user_id, action, resource, details, ip_address, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, action, resource, details, ip_address, time.time())
                )
                self.db.conn.commit()
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

    def get_audit_log(self, user_id: str, limit: int = 50) -> list[dict]:
        """Get audit log entries for a user."""
        try:
            if hasattr(self.db, 'client'):
                result = self.db.client.table("audit_log").select("*").eq("user_id", user_id).order("timestamp", desc=True).limit(limit).execute()
                return result.data
            else:
                rows = self.db.conn.execute(
                    "SELECT * FROM audit_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit)
                ).fetchall()
                return [
                    {"user_id": r[0], "action": r[1], "resource": r[2],
                     "details": r[3], "ip_address": r[4], "timestamp": r[5]}
                    for r in rows
                ]
        except Exception:
            return []


# ─── Module State ───────────────────────────────────────

_privacy_service: Optional[PrivacyService] = None


def init_privacy_service(db, auth_service=None) -> PrivacyService:
    global _privacy_service
    _privacy_service = PrivacyService(db, auth_service)
    return _privacy_service


# ─── Endpoint Registration ──────────────────────────────

def register_privacy_endpoints(app, privacy_service: PrivacyService):
    """Register all /privacy/* endpoints."""

    from auth import require_auth, UserProfile

    @app.get("/privacy/consent", response_model=ConsentSettings)
    async def get_consent(user: UserProfile = Depends(require_auth)):
        return privacy_service.get_consent(user.user_id)

    @app.patch("/privacy/consent", response_model=ConsentSettings)
    async def update_consent(req: ConsentUpdateRequest, user: UserProfile = Depends(require_auth)):
        return privacy_service.update_consent(user.user_id, req)

    @app.get("/privacy/export", response_model=DataExportResponse)
    async def export_data(user: UserProfile = Depends(require_auth)):
        return privacy_service.export_user_data(user.user_id)

    @app.delete("/privacy/account", response_model=DeletionResponse)
    async def delete_account(user: UserProfile = Depends(require_auth)):
        return privacy_service.delete_user_data(user.user_id)

    @app.post("/privacy/memories/redact")
    async def redact_memories(req: MemoryRedactRequest, user: UserProfile = Depends(require_auth)):
        count = privacy_service.redact_memories(user.user_id, req.keys)
        return {"redacted": count, "keys": req.keys}

    @app.post("/privacy/session/ephemeral")
    async def enable_ephemeral(session_id: str, user: UserProfile = Depends(require_auth)):
        privacy_service.mark_ephemeral(session_id)
        return {"session_id": session_id, "ephemeral": True}

    @app.get("/privacy/audit")
    async def get_audit_log(limit: int = 50, user: UserProfile = Depends(require_auth)):
        return privacy_service.get_audit_log(user.user_id, limit)

    @app.get("/legal/privacy")
    async def privacy_policy():
        return {
            "provider": "TMOS13, LLC",
            "contact": "privacy@tmos13.ai",
            "data_collected": ["email", "display_name", "session_data", "billing_info"],
            "data_retention_days": 90,
            "third_parties": ["Anthropic (AI processing)", "Stripe (payments)", "Supabase (database)"],
            "rights": ["access", "export", "deletion", "consent_management", "memory_redaction"],
            "endpoints": {
                "export": "GET /privacy/export",
                "delete": "DELETE /privacy/account",
                "consent": "GET/PATCH /privacy/consent",
                "redact": "POST /privacy/memories/redact",
                "audit": "GET /privacy/audit",
            },
        }

    logger.info("Privacy endpoints registered: /privacy/*, /legal/privacy")
