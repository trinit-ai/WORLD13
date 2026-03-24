"""
13TMOS Manifest Promotion — Deliberate Record Ledger

The vault is the raw archive. The manifest is the curated ledger.
Records are promoted from vault to manifest via explicit action.
Once promoted, records are read-only.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("13tmos.manifest_promotion")

MANIFEST_DIR = Path(__file__).resolve().parent.parent / "manifest"


def promote_record(vault, session_id: str, reason: str = "") -> Path | None:
    """Promote a vault record to the manifest. Returns path or None on failure."""
    # Resolve partial session IDs (first 8 chars)
    record = None
    if len(session_id) < 36:
        # Search vault for partial match
        from local_vault import VAULT_DIR
        for path in VAULT_DIR.rglob("*.json"):
            if path.stem.startswith(session_id):
                try:
                    record = json.loads(path.read_text())
                except Exception:
                    continue
                break
    else:
        record = vault.read(session_id)

    if not record:
        return None

    full_session_id = record.get("session", session_id)
    pack_id = record.get("pack", "unknown")
    date = record.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # Check if already promoted
    manifest_path = MANIFEST_DIR / pack_id / f"{full_session_id}.json"
    if manifest_path.exists():
        return manifest_path  # Already promoted

    # Promote
    record["promoted_at"] = datetime.now(timezone.utc).isoformat()
    record["read_only"] = True
    if reason:
        record["promotion_reason"] = reason

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(record, indent=2, default=str))
    logger.info(f"Promoted: {full_session_id[:8]} -> {manifest_path}")
    return manifest_path


def list_manifest_records(pack_filter: str = None) -> list[dict]:
    """List all promoted manifest records. Returns summaries sorted by date desc."""
    if not MANIFEST_DIR.exists():
        return []

    pattern = f"{pack_filter}/*.json" if pack_filter else "**/*.json"
    records = []
    for path in MANIFEST_DIR.glob(pattern):
        try:
            rec = json.loads(path.read_text())
        except Exception:
            continue
        records.append({
            "session": rec.get("session", path.stem)[:8],
            "pack": rec.get("pack", ""),
            "date": rec.get("date", ""),
            "type": rec.get("type", ""),
            "promoted_at": rec.get("promoted_at", ""),
        })

    records.sort(key=lambda r: r.get("promoted_at", ""), reverse=True)
    return records


def is_promoted(session_id: str) -> bool:
    """Check if a session has been promoted."""
    if not MANIFEST_DIR.exists():
        return False
    for path in MANIFEST_DIR.rglob("*.json"):
        if path.stem.startswith(session_id):
            return True
    return False
