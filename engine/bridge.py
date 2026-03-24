#!/usr/bin/env python3
"""
13TMOS Bridge — Local/Production Vault Sync

Deliberate, one-command sync that moves Vault records between
local flat JSON and production Supabase in either direction.
You control when it runs. You control what it syncs.

The Vault format is the protocol. The protocol is portable.
The Bridge proves it.

Usage:
    python engine/bridge.py status
    python engine/bridge.py diff
    python engine/bridge.py push [--pack X] [--since YYYY-MM-DD] [--session ID]
    python engine/bridge.py pull [--pack X] [--since YYYY-MM-DD]
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT_DIR / "engine"
CONFIG_DIR = ROOT_DIR / "config"

sys.path.insert(0, str(ENGINE_DIR))

from local_vault import LocalVault
from remote_adapter import RemoteAdapter

logger = logging.getLogger("13tmos.bridge")

LINE = "─" * 53

# ── Hardcoded Security Constraints ────────────────────────
# These packs NEVER push, regardless of configuration.
# Enforced in code, not just config.
NEVER_PUSH_PACKS = frozenset({
    "robert_c_ventura",
    "vault_audit",
    "pack_builder",
})

PRIVATE_DIR = ROOT_DIR / "protocols" / "private"


def _is_private_pack(pack_id: str) -> bool:
    """Check if a pack lives in protocols/private/ — never pushes."""
    if pack_id in NEVER_PUSH_PACKS:
        return True
    if (PRIVATE_DIR / pack_id).exists():
        return True
    return False


class Bridge:
    """Local/production Vault sync layer."""

    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else CONFIG_DIR / "bridge.yaml"
        self.config = self._load_config()
        self.local_vault = LocalVault()
        self.state_path = ROOT_DIR / self.config.get("state_file", "config/bridge_state.json")
        self.state = self._load_state()
        self._remote = None

    def _load_config(self) -> dict:
        """Load bridge configuration from YAML."""
        if not self.config_path.exists():
            logger.warning("Bridge config not found: %s", self.config_path)
            return {}

        try:
            import yaml
            return yaml.safe_load(self.config_path.read_text()) or {}
        except ImportError:
            logger.error("PyYAML required for bridge config")
            return {}

    def _load_state(self) -> dict:
        """Load sync state from bridge_state.json."""
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "last_push": None,
            "last_pull": None,
            "pushed_sessions": [],
            "pulled_sessions": [],
            "pending_push": [],
            "conflicts": [],
        }

    def _save_state(self):
        """Persist sync state."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2, default=str))

    def _get_remote(self) -> RemoteAdapter | None:
        """Lazy-init remote adapter from env vars."""
        if self._remote:
            return self._remote

        remote_config = self.config.get("remote", {})
        url = os.environ.get("TMOS13_REMOTE_URL", remote_config.get("url", ""))
        key = os.environ.get("TMOS13_REMOTE_KEY", "")

        if not url:
            logger.error("TMOS13_REMOTE_URL not configured")
            return None
        if not key:
            logger.error("TMOS13_REMOTE_KEY not set in .env")
            return None

        self._remote = RemoteAdapter(url, key)
        return self._remote

    def _get_exclude_packs(self) -> set[str]:
        """Get combined exclusion set: hardcoded + configured."""
        configured = set(
            self.config.get("sync", {}).get("push", {}).get("exclude_packs", [])
        )
        return NEVER_PUSH_PACKS | configured

    def _should_exclude(self, record: dict) -> str | None:
        """Check if a record should be excluded from push.

        Returns reason string if excluded, None if OK to push.
        """
        pack_id = record.get("pack", "")

        # Hardcoded: private packs never push
        if _is_private_pack(pack_id):
            return f"private/excluded pack: {pack_id}"

        # Configured exclusions
        if pack_id in self._get_exclude_packs():
            return f"excluded pack: {pack_id}"

        # Vault behavior exclusions
        exclude_behaviors = (
            self.config.get("sync", {}).get("push", {}).get("exclude_vault_behavior", [])
        )
        content = record.get("content", {})
        if isinstance(content, dict):
            vault_mode = content.get("vault_mode", "")
            if vault_mode in exclude_behaviors:
                return f"vault behavior: {vault_mode}"

        return None

    # ── Push ──────────────────────────────────────────────

    def push(self, session_ids: list[str] = None, since: str = None,
             pack_filter: str = None) -> dict:
        """Push local Vault records to production.

        Returns {pushed: N, failed: M, skipped: K, errors: []}
        """
        remote = self._get_remote()
        if not remote:
            return {"pushed": 0, "failed": 0, "skipped": 0,
                    "errors": ["Remote not configured"]}

        # Determine records to push
        if session_ids:
            records = []
            for sid in session_ids:
                r = self.local_vault.read(sid)
                if r:
                    records.append(r)
        else:
            # Get all local records
            summaries = self.local_vault.list_sessions(pack_id=pack_filter)
            records = []
            for s in summaries:
                r = self.local_vault.read(s["session"])
                if r:
                    records.append(r)

        # Filter by date
        if since:
            records = [r for r in records if r.get("date", "") >= since]

        # Filter already pushed (unsynced_only mode)
        push_mode = self.config.get("sync", {}).get("push", {}).get("default", "unsynced_only")
        pushed_set = set(self.state.get("pushed_sessions", []))
        if push_mode == "unsynced_only" and not session_ids:
            records = [r for r in records if r.get("session", "") not in pushed_set]

        result = {"pushed": 0, "failed": 0, "skipped": 0, "errors": []}

        for record in records:
            session_id = record.get("session", "")

            # Security check — enforced in code
            exclusion = self._should_exclude(record)
            if exclusion:
                result["skipped"] += 1
                logger.info("Skipped %s: %s", session_id[:8], exclusion)
                continue

            # Push
            resp = remote.push_record(record)

            if resp["success"]:
                result["pushed"] += 1
                self.state.setdefault("pushed_sessions", []).append(session_id)
                # Remove from pending
                pending = self.state.get("pending_push", [])
                if session_id in pending:
                    pending.remove(session_id)
                print(f"  + {session_id[:8]} -> pushed")
            elif resp["error"] == "already_exists":
                result["skipped"] += 1
                # Still mark as pushed to avoid retrying
                if session_id not in pushed_set:
                    self.state.setdefault("pushed_sessions", []).append(session_id)
                print(f"  - {session_id[:8]} -> skipped (already exists)")
            else:
                result["failed"] += 1
                result["errors"].append(f"{session_id[:8]}: {resp['error']}")
                print(f"  x {session_id[:8]} -> failed: {resp['error']}")

        # Update state
        self.state["last_push"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        return result

    # ── Pull ──────────────────────────────────────────────

    def pull(self, pack_filter: str = None, since: str = None) -> dict:
        """Pull production Vault records to local.

        Never overwrites existing local records.
        Returns {pulled: N, failed: M, skipped: K, errors: []}
        """
        remote = self._get_remote()
        if not remote:
            return {"pulled": 0, "failed": 0, "skipped": 0,
                    "errors": ["Remote not configured"]}

        filters = {}
        if pack_filter:
            filters["pack"] = pack_filter
        if since:
            filters["since"] = since

        records = remote.pull_records(filters)

        result = {"pulled": 0, "failed": 0, "skipped": 0, "errors": []}

        for record in records:
            session_id = record.get("session", "")

            # Never overwrite local records
            existing = self.local_vault.read(session_id)
            if existing:
                result["skipped"] += 1
                print(f"  - {session_id[:8]} -> skipped (already exists locally)")
                continue

            # Set user to "prod" to distinguish remote-origin records
            if record.get("user") != "local":
                record["user"] = record.get("user", "prod")
            else:
                record["user"] = "prod"

            try:
                path = self.local_vault.write(record)
                result["pulled"] += 1
                self.state.setdefault("pulled_sessions", []).append(session_id)
                print(f"  + {session_id[:8]} -> {path}")
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"{session_id[:8]}: {e}")
                print(f"  x {session_id[:8]} -> failed: {e}")

        # Update state
        self.state["last_pull"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        return result

    # ── Status ────────────────────────────────────────────

    def status(self) -> dict:
        """Show sync state."""
        all_sessions = self.local_vault.list_sessions()
        pushed_set = set(self.state.get("pushed_sessions", []))
        excluded_packs = self._get_exclude_packs()

        # Count local records not yet pushed (excluding excluded packs)
        unpushed = []
        for s in all_sessions:
            sid = s.get("session", "")
            pack = s.get("pack", "")
            if sid not in pushed_set and not _is_private_pack(pack) and pack not in excluded_packs:
                unpushed.append(sid)

        remote_config = self.config.get("remote", {})
        url = os.environ.get("TMOS13_REMOTE_URL", remote_config.get("url", ""))

        return {
            "remote_url": url,
            "last_push": self.state.get("last_push"),
            "last_pull": self.state.get("last_pull"),
            "pushed_count": len(self.state.get("pushed_sessions", [])),
            "pulled_count": len(self.state.get("pulled_sessions", [])),
            "pending_push": len(unpushed),
            "pending_push_ids": unpushed,
            "conflicts": self.state.get("conflicts", []),
            "total_local": len(all_sessions),
        }

    # ── Diff (dry run) ───────────────────────────────────

    def diff(self, pack_filter: str = None, since: str = None) -> dict:
        """Show what would sync without syncing."""
        all_sessions = self.local_vault.list_sessions(pack_id=pack_filter)
        pushed_set = set(self.state.get("pushed_sessions", []))

        would_push = []
        would_skip = []

        for s in all_sessions:
            sid = s.get("session", "")
            pack = s.get("pack", "")

            if since and s.get("date", "") < since:
                continue

            if sid in pushed_set:
                continue

            record = self.local_vault.read(sid)
            if not record:
                continue

            exclusion = self._should_exclude(record)
            if exclusion:
                would_skip.append({"session": sid, "pack": pack, "reason": exclusion})
            else:
                would_push.append({
                    "session": sid,
                    "pack": pack,
                    "date": s.get("date", ""),
                    "path": f"vault/{pack}/{s.get('user', 'local')}/{s.get('date', '')}/"
                            f"{sid}.json",
                })

        # Check remote for pull candidates
        remote = self._get_remote()
        remote_count = -1
        if remote:
            filters = {}
            if pack_filter:
                filters["pack"] = pack_filter
            if since:
                filters["since"] = since
            remote_count = remote.remote_count(filters)

        return {
            "would_push": would_push,
            "would_skip": would_skip,
            "remote_available": remote_count,
        }


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def _load_env():
    """Load .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT_DIR / ".env")
    except ImportError:
        pass


def cmd_status(args):
    """Show bridge sync status."""
    bridge = Bridge()
    s = bridge.status()

    # Parse URL for display
    url = s["remote_url"]
    display_url = url.replace("https://", "").replace("http://", "") if url else "not configured"

    print(f"\nBRIDGE STATUS")
    print(LINE)
    print(f"Remote        : {display_url}")
    pushed_note = f" ({s['pushed_count']} records)" if s['pushed_count'] else ""
    pulled_note = f" ({s['pulled_count']} records)" if s['pulled_count'] else ""
    print(f"Last push     : {s['last_push'] or 'never'}{pushed_note}")
    print(f"Last pull     : {s['last_pull'] or 'never'}{pulled_note}")
    print(f"Local records : {s['total_local']}")
    print(f"Pending push  : {s['pending_push']} records")
    if s["conflicts"]:
        print(f"Conflicts     : {len(s['conflicts'])}")
    print()


def cmd_diff(args):
    """Show what would sync."""
    bridge = Bridge()
    d = bridge.diff(pack_filter=args.pack, since=args.since)

    print(f"\nBRIDGE DIFF (dry run)")
    print(LINE)

    if d["would_push"]:
        print(f"Would push: {len(d['would_push'])} records")
        for item in d["would_push"]:
            print(f"  {item['path']}")
    else:
        print("Would push: 0 records")

    if d["would_skip"]:
        print(f"Would skip: {len(d['would_skip'])} records")
        for item in d["would_skip"]:
            print(f"  {item['session'][:8]} ({item['reason']})")

    if d["remote_available"] >= 0:
        print(f"\nRemote available: {d['remote_available']} records")
    else:
        print(f"\nRemote available: unknown (could not connect)")

    print()


def cmd_push(args):
    """Push local records to production."""
    bridge = Bridge()

    session_ids = [args.session] if args.session else None

    print(f"\nPushing to production...")
    print(LINE)

    result = bridge.push(
        session_ids=session_ids,
        since=args.since,
        pack_filter=args.pack,
    )

    print(LINE)
    print(f"{result['pushed']} pushed, {result['skipped']} skipped, {result['failed']} failed")
    if result["errors"]:
        for err in result["errors"]:
            print(f"  Error: {err}")
    print()


def cmd_pull(args):
    """Pull production records to local."""
    bridge = Bridge()

    print(f"\nPulling from production...")
    print(LINE)

    result = bridge.pull(
        pack_filter=args.pack,
        since=args.since,
    )

    print(LINE)
    print(f"{result['pulled']} pulled, {result['skipped']} skipped, {result['failed']} failed")
    if result["errors"]:
        for err in result["errors"]:
            print(f"  Error: {err}")
    print()


def main():
    _load_env()

    parser = argparse.ArgumentParser(
        description="13TMOS Bridge — local/production vault sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The Vault format is the protocol. The protocol is portable. The Bridge proves it.",
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show bridge sync status")

    p_diff = sub.add_parser("diff", help="Show what would sync (dry run)")
    p_diff.add_argument("--pack", "-p", help="Filter by pack ID")
    p_diff.add_argument("--since", help="Since date (YYYY-MM-DD)")

    p_push = sub.add_parser("push", help="Push local records to production")
    p_push.add_argument("--pack", "-p", help="Filter by pack ID")
    p_push.add_argument("--since", help="Since date (YYYY-MM-DD)")
    p_push.add_argument("--session", "-s", help="Push specific session ID")

    p_pull = sub.add_parser("pull", help="Pull production records to local")
    p_pull.add_argument("--pack", "-p", help="Filter by pack ID")
    p_pull.add_argument("--since", help="Since date (YYYY-MM-DD)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        cmd_status(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "push":
        cmd_push(args)
    elif args.command == "pull":
        cmd_pull(args)


if __name__ == "__main__":
    main()
