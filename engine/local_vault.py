"""
13TMOS Local Vault — Dimensional Memory System

Every record is addressable from 8 independent angles simultaneously.
Burial is architecturally impossible.

Dimensional addressing via file path:
  vault/{pack_id}/{user_id}/{date}/{session_id}.json

The 8 dimensions:
  pack, user, date, type, fields, session, manifest, content

The Vault is not storage. It is inheritance.
Every session inherits the state of every session that preceded it.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("13tmos.local_vault")

VAULT_DIR = Path(__file__).resolve().parent.parent / "vault"


class LocalVault:
    """Flat JSON vault with dimensional addressing."""

    def __init__(self, vault_dir: Path = None):
        self.vault_dir = vault_dir or VAULT_DIR

    # ── Write ─────────────────────────────────────────────

    def write(self, record: dict) -> Path:
        """Write a vault record to the correct dimensional path.

        Includes prev_hash for tamper-evident hash chain.
        """
        pack_id = record.get("pack", "unknown")
        user_id = record.get("user", "local")
        date = record.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        session_id = record.get("session", "unknown")

        dir_path = self.vault_dir / pack_id / user_id / date
        dir_path.mkdir(parents=True, exist_ok=True)

        # Hash chain: link to previous record
        record["prev_hash"] = self._get_chain_head(dir_path)

        file_path = dir_path / f"{session_id}.json"
        file_path.write_text(json.dumps(record, indent=2, default=str))
        logger.info(f"Vault record written: {file_path}")
        return file_path

    def _get_chain_head(self, dir_path: Path) -> str:
        """SHA-256 hash of the most recent record in dir, or GENESIS."""
        if not dir_path.exists():
            return "GENESIS"
        records = sorted(dir_path.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not records:
            return "GENESIS"
        return hashlib.sha256(records[-1].read_bytes()).hexdigest()

    def verify_chain(self, pack_id: str, user_id: str = "local") -> list[dict]:
        """Verify hash chain integrity. Returns list of breaks (empty = intact)."""
        breaks = []
        search = self.vault_dir / pack_id / user_id
        if not search.exists():
            return breaks
        for date_dir in sorted(search.iterdir()):
            if not date_dir.is_dir():
                continue
            records = sorted(date_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
            expected = "GENESIS"
            for rpath in records:
                try:
                    rec = json.loads(rpath.read_text())
                except Exception:
                    breaks.append({"file": str(rpath), "error": "unreadable"})
                    continue
                actual = rec.get("prev_hash", "")
                # Legacy records without prev_hash are fine at chain start
                if not actual and expected == "GENESIS":
                    pass
                elif actual != expected:
                    breaks.append({
                        "file": rpath.name,
                        "expected": expected[:16],
                        "found": (actual or "missing")[:16],
                    })
                expected = hashlib.sha256(rpath.read_bytes()).hexdigest()
        return breaks

    # ── Read (single record) ──────────────────────────────

    def read(self, session_id: str) -> dict | None:
        """Retrieve a record by session_id (searches all paths)."""
        for path in self.vault_dir.rglob(f"{session_id}.json"):
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read vault record {path}: {e}")
        return None

    # Alias for spec compatibility
    get = read

    # ── Query (dimensional search) ────────────────────────

    def query(self, dimensions: dict) -> list[dict]:
        """Return all records matching provided dimension values.

        All 8 dimensions supported:
          pack, user, date, type, session, manifest — exact string match
          fields — dict of key/value pairs, all must match (partial OK)
          content — substring match (case-insensitive)

        All provided filters are AND-combined.
        """
        if not self.vault_dir.exists():
            return []

        results = []

        # Narrow file walk using path components where possible
        pack_filter = dimensions.get("pack", "*")
        user_filter = dimensions.get("user", "*")
        date_filter = dimensions.get("date", "*")

        search_pattern = f"{pack_filter}/{user_filter}/{date_filter}/*.json"
        for path in self.vault_dir.glob(search_pattern):
            try:
                record = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            if self._matches(record, dimensions):
                results.append(record)

        return results

    def _matches(self, record: dict, dimensions: dict) -> bool:
        """Check if a record matches all provided dimension filters."""
        for dim_key, dim_val in dimensions.items():
            # Path-level dimensions already filtered by glob
            if dim_key in ("pack", "user", "date"):
                continue

            # Fields: dict match — all provided k/v pairs must exist
            if dim_key == "fields":
                if not isinstance(dim_val, dict):
                    continue
                record_fields = record.get("fields", {})
                if not isinstance(record_fields, dict):
                    return False
                for fk, fv in dim_val.items():
                    if record_fields.get(fk) != fv:
                        return False
                continue

            # Content: substring match (case-insensitive)
            if dim_key == "content":
                record_content = record.get("content", "")
                if isinstance(record_content, dict):
                    record_content = json.dumps(record_content)
                if not isinstance(record_content, str):
                    record_content = str(record_content)
                if dim_val.lower() not in record_content.lower():
                    return False
                continue

            # All other dimensions: exact string match
            if dim_key in record and str(record[dim_key]) != str(dim_val):
                return False

        return True

    # ── Search (fuzzy text search with scoring) ─────────

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Fuzzy text search across all vault records.

        Searches pack ID, type, field keys/values, content summary,
        and full content text. Returns results ranked by relevance score.

        Scoring:
          +5  query matches pack ID
          +4  query matches a field value
          +3  query matches content summary
          +2  query matches full content text
          +1  query matches field key name
        """
        if not self.vault_dir.exists():
            return []

        query_lower = query.lower()
        scored = []

        for path in self.vault_dir.rglob("*.json"):
            try:
                record = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            score = 0
            matched_fields = []

            # Pack ID
            pack = record.get("pack", "")
            if query_lower in pack.lower():
                score += 5
                matched_fields.append(f"pack:{pack}")

            # Type
            rec_type = record.get("type", "")
            if rec_type and query_lower in rec_type.lower():
                score += 3
                matched_fields.append(f"type:{rec_type}")

            # Fields — values and keys
            fields = record.get("fields", {})
            if isinstance(fields, dict):
                for fk, fv in fields.items():
                    fv_str = str(fv).lower() if fv is not None else ""
                    if query_lower in fv_str:
                        score += 4
                        matched_fields.append(f"{fk}={fv}")
                    elif query_lower in fk.lower():
                        score += 1
                        matched_fields.append(f"field:{fk}")

            # Content summary
            content = record.get("content", {})
            summary = ""
            content_text = ""
            if isinstance(content, dict):
                summary = content.get("summary", "")
                content_text = json.dumps(content)
            elif isinstance(content, str):
                content_text = content
                summary = content[:200]

            if summary and query_lower in summary.lower():
                score += 3
                matched_fields.append("summary")
            elif content_text and query_lower in content_text.lower():
                score += 2
                matched_fields.append("content")

            if score > 0:
                scored.append({
                    "record": record,
                    "score": score,
                    "matched": matched_fields[:5],
                })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    # ── List Sessions ─────────────────────────────────────

    def list_sessions(self, pack_id: str = None, user_id: str = None) -> list[dict]:
        """Return summary list of all vault records, optionally filtered.

        Returns list of dicts with: session, pack, user, date, type.
        Sorted by date descending.
        """
        if not self.vault_dir.exists():
            return []

        # Build glob pattern from filters
        pack_pat = pack_id or "*"
        user_pat = user_id or "*"
        pattern = f"{pack_pat}/{user_pat}/*/*.json"

        summaries = []
        for path in self.vault_dir.glob(pattern):
            try:
                record = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            summaries.append({
                "session": record.get("session", path.stem),
                "pack": record.get("pack", ""),
                "user": record.get("user", ""),
                "date": record.get("date", ""),
                "type": record.get("type", ""),
            })

        # Sort by date descending, then pack
        summaries.sort(key=lambda r: (r["date"], r["pack"]), reverse=True)
        return summaries

    # ── Inherit (the key method) ──────────────────────────

    def inherit(self, session_id: str, target_pack_id: str) -> dict:
        """Build inheritance context for a new session from prior vault records.

        Given a completed session_id, find all records for the same user,
        return them chronologically with a merged field_index.

        The field_index is the single dict that can be injected into the next
        session's context so it never re-asks for what it already knows.
        Last-write wins on field conflicts.

        Returns:
            {
                "user_id": "local",
                "source_session": session_id,
                "target_pack": target_pack_id,
                "prior_sessions": [...],
                "field_index": {...}
            }
        """
        # Find the source record to get user_id
        source = self.read(session_id)
        if not source:
            logger.warning(f"Vault inherit: source session {session_id} not found")
            return {
                "user_id": "unknown",
                "source_session": session_id,
                "target_pack": target_pack_id,
                "prior_sessions": [],
                "field_index": {},
            }

        user_id = source.get("user", "local")

        # Find all records for this user, sorted by date ascending (chronological)
        all_records = self.query({"user": user_id})
        all_records.sort(key=lambda r: (r.get("date", ""), r.get("session", "")))

        # Build prior sessions list and merged field index
        prior_sessions = []
        field_index = {}

        for record in all_records:
            # Build summary for each prior session
            prior = {
                "pack": record.get("pack", ""),
                "date": record.get("date", ""),
                "session_id": record.get("session", ""),
                "type": record.get("type", ""),
                "fields": record.get("fields", {}),
            }

            # Include content summary if available
            content = record.get("content", {})
            if isinstance(content, dict):
                summary = content.get("summary", "")
                if summary:
                    prior["summary"] = summary
            elif isinstance(content, str) and len(content) < 500:
                prior["content"] = content

            prior_sessions.append(prior)

            # Merge fields — last-write wins
            record_fields = record.get("fields", {})
            if isinstance(record_fields, dict):
                for k, v in record_fields.items():
                    if v is not None and str(v).lower() not in ("null", "none", ""):
                        field_index[k] = v

        return {
            "user_id": user_id,
            "source_session": session_id,
            "target_pack": target_pack_id,
            "prior_sessions": prior_sessions,
            "field_index": field_index,
        }
