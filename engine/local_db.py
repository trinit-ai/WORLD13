"""
13TMOS Local Database — SQLite Adapter

Minimal session persistence for the local distillation.
DB file: config/13tmos.db

Three tables:
  - sessions:   session lifecycle and manifest binding
  - exchanges:  turn-by-turn conversation record
  - state:      key/value session state (captured fields, routing, etc.)
"""
import json
import sqlite3
import time
import uuid
import logging
from pathlib import Path

logger = logging.getLogger("13tmos.local_db")

DB_PATH = Path(__file__).resolve().parent.parent / "config" / "13tmos.db"


def _connect(db_path: Path = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = None) -> sqlite3.Connection:
    """Create tables and return a connection."""
    conn = _connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            pack_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local',
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            manifest TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS exchanges (
            exchange_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            turn_number INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_exchanges_session
            ON exchanges(session_id, turn_number);

        CREATE TABLE IF NOT EXISTS state (
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            key TEXT NOT NULL,
            value TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (session_id, key)
        );
    """)
    conn.commit()
    logger.info(f"Local DB initialized at {db_path or DB_PATH}")
    return conn


class LocalDB:
    """SQLite adapter for 13TMOS local sessions."""

    def __init__(self, db_path: Path = None):
        self.conn = init_db(db_path)

    # ── Sessions ──────────────────────────────────────────

    def create_session(self, pack_id: str, user_id: str = "local",
                       manifest: dict = None) -> str:
        session_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            "INSERT INTO sessions (session_id, pack_id, user_id, created_at, status, manifest) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (session_id, pack_id, user_id, now, json.dumps(manifest or {})),
        )
        self.conn.commit()
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["manifest"] = json.loads(d["manifest"])
            return d
        return None

    def complete_session(self, session_id: str):
        self.conn.execute(
            "UPDATE sessions SET status = 'complete' WHERE session_id = ?",
            (session_id,),
        )
        self.conn.commit()

    # ── Exchanges ─────────────────────────────────────────

    def add_exchange(self, session_id: str, role: str, content: str,
                     turn_number: int) -> str:
        exchange_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            "INSERT INTO exchanges (exchange_id, session_id, role, content, created_at, turn_number) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (exchange_id, session_id, role, content, now, turn_number),
        )
        self.conn.commit()
        return exchange_id

    def get_exchanges(self, session_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM exchanges WHERE session_id = ? ORDER BY turn_number",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── State ─────────────────────────────────────────────

    def set_state(self, session_id: str, key: str, value: str):
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            "INSERT OR REPLACE INTO state (session_id, key, value, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, key, value, now),
        )
        self.conn.commit()

    def get_state(self, session_id: str, key: str = None) -> dict | str | None:
        if key:
            row = self.conn.execute(
                "SELECT value FROM state WHERE session_id = ? AND key = ?",
                (session_id, key),
            ).fetchone()
            return row["value"] if row else None
        rows = self.conn.execute(
            "SELECT key, value FROM state WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def count_fields(self, session_id: str) -> tuple[int, int]:
        """Return (non_null_count, total_count) of state keys for a session."""
        rows = self.conn.execute(
            "SELECT key, value FROM state WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        total = len(rows)
        filled = sum(1 for r in rows if r["value"] and r["value"] != "null")
        return filled, total
