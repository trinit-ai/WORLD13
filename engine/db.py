"""
TMOS13 Persistence Layer

Supabase-backed persistence for cross-session state.
Falls back to SQLite for local development when Supabase is not configured.

Tables (aligned with supabase/migrations 001–007):
  - profiles:     user_id (UUID PK → auth.users), email, display_name, tier, last_seen
  - session_log:  session_id (text PK), user_id (UUID), started_at, ended_at, max_depth
  - fossil_record, memories: legacy tables retained for GDPR export of existing data
  - transcripts, deliverables: persisted by TranscriptStore / DeliverableStore

Note: The standalone `users` table was dropped in migration 006.
      `profiles` is the application-level extension of auth.users.
"""
import json
import time
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from state import SessionState

logger = logging.getLogger("tmos13.db")


class SupabaseDB:
    """Supabase persistence for production."""

    def __init__(self, url: str, key: str):
        from supabase import create_client
        self.client = create_client(url, key)
        logger.info("Supabase persistence initialized")

    def touch_profile(self, user_id: str):
        """Update last_seen on the profiles table (UUID user_id)."""
        if not user_id or user_id == "anonymous":
            return  # skip for unauthenticated sessions
        try:
            self.client.table("profiles").update(
                {"last_seen": time.time()}
            ).eq("user_id", user_id).execute()
        except Exception as e:
            logger.warning(f"touch_profile failed for {user_id}: {e}")

    def get_eggs(self, user_id: str) -> list[str]:
        """Read legacy fossil_record data (GDPR export)."""
        if not user_id or user_id == "anonymous":
            return []
        result = (
            self.client.table("fossil_record")
            .select("egg_id")
            .eq("user_id", user_id)
            .order("found_at")
            .execute()
        )
        return [r["egg_id"] for r in result.data]

    def get_memories(self, user_id: str) -> dict:
        """Read legacy memories data (GDPR export)."""
        if not user_id or user_id == "anonymous":
            return {}
        result = (
            self.client.table("memories")
            .select("key, value")
            .eq("user_id", user_id)
            .execute()
        )
        return {r["key"]: r["value"] for r in result.data}

    def log_session(self, state: "SessionState"):
        user_id = state.user_id if (state.user_id and state.user_id != "anonymous") else None
        row = {
            "session_id": state.session_id,
            "user_id": user_id,
            "started_at": state.session_start,
            "ended_at": time.time(),
            "games_played": json.dumps(state.games_played),
            "max_depth": state.depth,
        }
        sig = getattr(state, "manifest_signature", None)
        if sig:
            row["manifest_signature"] = json.dumps(sig) if isinstance(sig, dict) else sig
        self.client.table("session_log").upsert(
            row,
            on_conflict="session_id",
        ).execute()


class SQLiteDB:
    """SQLite fallback for local development."""

    def __init__(self, db_path: str):
        import sqlite3
        from pathlib import Path

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()
        logger.info(f"SQLite persistence initialized at {db_path}")

    def _init_tables(self):
        self.conn.executescript("""
            -- profiles is the sole identity table (mirrors Supabase migration 006)
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                email TEXT,
                display_name TEXT,
                avatar_url TEXT,
                provider TEXT DEFAULT 'email',
                tier TEXT DEFAULT 'free',
                role TEXT DEFAULT 'user',
                stripe_customer_id TEXT,
                last_seen REAL DEFAULT (unixepoch()),
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch())
            );

            -- Legacy tables retained for GDPR export
            CREATE TABLE IF NOT EXISTS fossil_record (
                user_id TEXT,
                egg_id TEXT,
                found_at REAL DEFAULT (unixepoch()),
                context TEXT,
                PRIMARY KEY (user_id, egg_id),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS memories (
                user_id TEXT,
                key TEXT,
                value TEXT,
                updated_at REAL DEFAULT (unixepoch()),
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );

            CREATE TABLE IF NOT EXISTS session_log (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                started_at REAL,
                ended_at REAL,
                games_played TEXT,
                max_depth INTEGER,
                eggs_found TEXT,
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                stripe_subscription_id TEXT UNIQUE,
                stripe_price_id TEXT,
                tier TEXT DEFAULT 'pro',
                status TEXT DEFAULT 'active',
                current_period_start REAL,
                current_period_end REAL,
                cancel_at_period_end INTEGER DEFAULT 0,
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch()),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                stripe_session_id TEXT,
                stripe_payment_intent_id TEXT,
                amount INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'usd',
                status TEXT DEFAULT 'pending',
                product_name TEXT,
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch()),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS billing_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                event_type TEXT NOT NULL,
                stripe_event_id TEXT UNIQUE,
                data TEXT DEFAULT '{}',
                created_at REAL DEFAULT (unixepoch()),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS consent (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                analytics INTEGER DEFAULT 0,
                marketing INTEGER DEFAULT 0,
                third_party INTEGER DEFAULT 0,
                essential INTEGER DEFAULT 1,
                ip_address TEXT,
                user_agent TEXT,
                updated_at REAL DEFAULT (unixepoch()),
                created_at REAL DEFAULT (unixepoch()),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource TEXT,
                details TEXT DEFAULT '{}',
                ip_address TEXT,
                created_at REAL DEFAULT (unixepoch()),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE TABLE IF NOT EXISTS deletion_requests (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                requested_at REAL DEFAULT (unixepoch()),
                completed_at REAL,
                details TEXT DEFAULT '{}',
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );

            -- Ambassador Layer (foundational — see engine/ambassador.py)
            CREATE TABLE IF NOT EXISTS addresses (
                id TEXT PRIMARY KEY,
                handle TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT 'tmos13.ai',
                owner_id TEXT NOT NULL,
                display_name TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                default_protocol_id TEXT,
                settings TEXT NOT NULL DEFAULT '{}',
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch()),
                UNIQUE(handle, domain)
            );
            CREATE TABLE IF NOT EXISTS protocols (
                id TEXT PRIMARY KEY,
                address_id TEXT NOT NULL REFERENCES addresses(id),
                pack_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'receive',
                boundaries TEXT NOT NULL DEFAULT '{}',
                personality TEXT NOT NULL DEFAULT '{}',
                active INTEGER NOT NULL DEFAULT 1,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE TABLE IF NOT EXISTS routing_rules (
                id TEXT PRIMARY KEY,
                address_id TEXT NOT NULL REFERENCES addresses(id),
                protocol_id TEXT NOT NULL REFERENCES protocols(id),
                priority INTEGER NOT NULL DEFAULT 100,
                match_type TEXT NOT NULL,
                match_value TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE TABLE IF NOT EXISTS exchanges (
                id TEXT PRIMARY KEY,
                address_id TEXT NOT NULL REFERENCES addresses(id),
                protocol_id TEXT REFERENCES protocols(id),
                direction TEXT NOT NULL DEFAULT 'inbound',
                channel TEXT NOT NULL DEFAULT 'portal',
                status TEXT NOT NULL DEFAULT 'active',
                counterparty_type TEXT,
                counterparty_identifier TEXT,
                counterparty_name TEXT,
                counterparty_ambassador_id TEXT,
                intent_detected TEXT,
                intent_confidence REAL,
                intent_summary TEXT,
                state TEXT NOT NULL DEFAULT '{}',
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch()),
                resolved_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_exchanges_address_status ON exchanges(address_id, status);
            CREATE INDEX IF NOT EXISTS idx_exchanges_address_created ON exchanges(address_id, created_at);
            CREATE TABLE IF NOT EXISTS exchange_turns (
                id TEXT PRIMARY KEY,
                exchange_id TEXT NOT NULL REFERENCES exchanges(id),
                sequence INTEGER NOT NULL,
                direction TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                content_raw TEXT,
                content_parsed TEXT,
                content_response TEXT,
                cartridge TEXT,
                state_changes TEXT,
                latency_ms INTEGER,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_turns_exchange ON exchange_turns(exchange_id, sequence);
            CREATE TABLE IF NOT EXISTS resolutions (
                id TEXT PRIMARY KEY,
                exchange_id TEXT NOT NULL REFERENCES exchanges(id) UNIQUE,
                type TEXT NOT NULL,
                summary TEXT NOT NULL,
                structured_data TEXT NOT NULL DEFAULT '{}',
                actions_taken TEXT NOT NULL DEFAULT '[]',
                requires_review INTEGER NOT NULL DEFAULT 0,
                owner_reviewed INTEGER NOT NULL DEFAULT 0,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_resolutions_review ON resolutions(requires_review, owner_reviewed);

            -- Cross-session persistence (migration 008)
            CREATE TABLE IF NOT EXISTS persistent_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                contact_email TEXT,
                fingerprint_hash TEXT,
                pack_id TEXT NOT NULL,
                cartridge_id TEXT,
                state_snapshot TEXT NOT NULL DEFAULT '{}',
                captured_fields TEXT NOT NULL DEFAULT '{}',
                qualification_score INTEGER DEFAULT 0,
                depth INTEGER DEFAULT 0,
                total_turns INTEGER DEFAULT 0,
                total_sessions INTEGER DEFAULT 1,
                first_seen_at REAL DEFAULT (unixepoch()),
                last_seen_at REAL DEFAULT (unixepoch()),
                last_cartridge_visited TEXT,
                cartridges_visited TEXT DEFAULT '[]',
                status TEXT DEFAULT 'active',
                resolved_at REAL,
                resolution_summary TEXT,
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch()),
                FOREIGN KEY (user_id) REFERENCES profiles(user_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_persistent_sessions_user
                ON persistent_sessions(user_id, pack_id) WHERE user_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS uq_persistent_sessions_email
                ON persistent_sessions(contact_email, pack_id) WHERE contact_email IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_persistent_sessions_fingerprint
                ON persistent_sessions(fingerprint_hash, pack_id);
            CREATE INDEX IF NOT EXISTS idx_persistent_sessions_status
                ON persistent_sessions(status, last_seen_at);

            -- Trigger audit trail (migration 009)
            CREATE TABLE IF NOT EXISTS trigger_audit (
                id TEXT PRIMARY KEY,
                trigger_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                persistent_session_id TEXT REFERENCES persistent_sessions(id),
                action TEXT NOT NULL,
                channel TEXT,
                template TEXT,
                status TEXT NOT NULL DEFAULT 'dispatched',
                recipient TEXT,
                subject TEXT,
                error_message TEXT,
                provider_response TEXT DEFAULT '{}',
                requires_approval INTEGER DEFAULT 0,
                approved_by TEXT,
                approved_at REAL,
                fired_at REAL DEFAULT (unixepoch()),
                attempt_number INTEGER DEFAULT 1,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_trigger_audit_cooldown
                ON trigger_audit(persistent_session_id, trigger_id, fired_at);
            CREATE INDEX IF NOT EXISTS idx_trigger_audit_pending
                ON trigger_audit(status) WHERE status = 'approval_pending';
            CREATE INDEX IF NOT EXISTS idx_trigger_audit_pack
                ON trigger_audit(pack_id, fired_at);

            -- Tool action audit trail (migration 010)
            CREATE TABLE IF NOT EXISTS tool_audit (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                persistent_session_id TEXT REFERENCES persistent_sessions(id),
                pack_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                provider TEXT NOT NULL,
                parameters TEXT NOT NULL DEFAULT '{}',
                scope_valid INTEGER NOT NULL DEFAULT 1,
                params_valid INTEGER NOT NULL DEFAULT 1,
                confirmation_required INTEGER DEFAULT 0,
                confirmation_received INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'requested',
                provider_response TEXT,
                error_message TEXT,
                requested_at REAL DEFAULT (unixepoch()),
                executed_at REAL,
                duration_ms INTEGER,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_tool_audit_session
                ON tool_audit(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_audit_pack
                ON tool_audit(pack_id, tool_id);
            CREATE INDEX IF NOT EXISTS idx_tool_audit_status
                ON tool_audit(status);

            -- Workflow instances (migration 011)
            CREATE TABLE IF NOT EXISTS workflow_instances (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                persistent_session_id TEXT REFERENCES persistent_sessions(id),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN (
                        'pending', 'active', 'waiting', 'completed',
                        'failed', 'timed_out', 'cancelled'
                    )),
                current_step_id TEXT,
                completed_steps TEXT DEFAULT '[]',
                context TEXT DEFAULT '{}',
                started_at REAL,
                last_step_at REAL,
                next_step_at REAL,
                timeout_at REAL,
                completed_at REAL,
                total_steps_executed INTEGER DEFAULT 0,
                max_steps INTEGER DEFAULT 20,
                cancellation_reason TEXT,
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_instances_session
                ON workflow_instances(persistent_session_id);
            CREATE INDEX IF NOT EXISTS idx_workflow_instances_status
                ON workflow_instances(status);
            CREATE INDEX IF NOT EXISTS idx_workflow_instances_next
                ON workflow_instances(next_step_at);

            -- Workflow step log (migration 011)
            CREATE TABLE IF NOT EXISTS workflow_step_log (
                id TEXT PRIMARY KEY,
                workflow_instance_id TEXT REFERENCES workflow_instances(id),
                step_id TEXT NOT NULL,
                step_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN (
                    'executing', 'completed', 'failed', 'skipped'
                )),
                input_context TEXT,
                output_data TEXT,
                error_message TEXT,
                started_at REAL DEFAULT (unixepoch()),
                completed_at REAL,
                duration_ms INTEGER,
                created_at REAL DEFAULT (unixepoch())
            );

            -- Workflow wait conditions (migration 011)
            CREATE TABLE IF NOT EXISTS workflow_wait_conditions (
                id TEXT PRIMARY KEY,
                workflow_instance_id TEXT REFERENCES workflow_instances(id),
                event_type TEXT NOT NULL,
                condition TEXT,
                timeout_at REAL,
                target_step_id TEXT NOT NULL,
                matched INTEGER DEFAULT 0,
                matched_at REAL,
                matched_event TEXT,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_wait_active
                ON workflow_wait_conditions(event_type, matched);
        """)
        self.conn.commit()

    def touch_profile(self, user_id: str):
        """Update last_seen timestamp on profiles (or create a minimal row)."""
        self.conn.execute(
            "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)", (user_id,)
        )
        self.conn.execute(
            "UPDATE profiles SET last_seen = unixepoch() WHERE user_id = ?",
            (user_id,),
        )
        self.conn.commit()

    def get_eggs(self, user_id: str) -> list[str]:
        """Read legacy fossil_record data (GDPR export)."""
        rows = self.conn.execute(
            "SELECT egg_id FROM fossil_record WHERE user_id = ? ORDER BY found_at", (user_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def get_memories(self, user_id: str) -> dict:
        """Read legacy memories data (GDPR export)."""
        rows = self.conn.execute(
            "SELECT key, value FROM memories WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {k: v for k, v in rows}

    def log_session(self, state: "SessionState"):
        self.conn.execute(
            """INSERT OR REPLACE INTO session_log
               (session_id, user_id, started_at, ended_at, games_played, max_depth)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                state.session_id,
                state.user_id,
                state.session_start,
                time.time(),
                json.dumps(state.games_played),
                state.depth,
            ),
        )
        self.conn.commit()


def create_db() -> SupabaseDB | SQLiteDB:
    """Factory: use Supabase if configured, else SQLite for local dev."""
    from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, BASE_DIR

    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        return SupabaseDB(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    db_path = str(BASE_DIR.parent / "config" / "13tmos.db")
    logger.warning("Supabase not configured — falling back to SQLite (local dev only)")
    return SQLiteDB(db_path)
