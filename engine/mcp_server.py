"""
13TMOS MCP Server — Distilled Kernel Tools

13 tools exposing the full pack library, vault, and session infrastructure.
Written from scratch for 13TMOS — not a copy of tmos13.ai.

The critical difference: pack_read reads from protocols/packs/ and
protocols/library/ — the full pack library, not just the active cartridge.

Endpoints:
  POST /mcp/tools  — list available tools with input schemas
  POST /mcp/call   — invoke a tool: {"tool": "name", "arguments": {...}}
  GET  /mcp/health — MCP server health check
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger("13tmos.mcp")

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKS_DIR = ROOT_DIR / "protocols" / "packs"
LIBRARY_DIR = ROOT_DIR / "protocols" / "library"
CONFIG_DIR = ROOT_DIR / "config"
VAULT_DIR = ROOT_DIR / "vault"
OUTPUT_DIR = ROOT_DIR / "output"


# ─── Tool Schema Definitions ──────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "engine_status",
        "description": "Returns 13TMOS engine status: service, model, active packs, vault records, tools count.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "pack_list",
        "description": "List available packs from the full pack library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., legal, medical, games). Optional.",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "stub", "development", "all"],
                    "description": "Filter by pack status. Default: active.",
                },
            },
        },
    },
    {
        "name": "pack_read",
        "description": "Read a pack's full governing protocol — MANIFEST.md, header.yaml, and manifest.json. Searches protocols/packs/ and protocols/library/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pack_id": {
                    "type": "string",
                    "description": "Pack ID to read (e.g., legal_intake, vault_audit).",
                },
            },
            "required": ["pack_id"],
        },
    },
    {
        "name": "pack_search",
        "description": "Full-text search across all pack manifests in protocols/packs/ and protocols/library/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return. Default: 10.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "frontier",
        "description": "Returns the pack library coverage map: total packs, active vs stubs, breakdown by category.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "vault_search",
        "description": "Fuzzy text search across all vault records — searches pack names, field values, content summaries, and full text. Returns ranked results by relevance. Use this when you need to find sessions by topic, keyword, or natural language.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — matches against pack IDs, field values, content summaries, and text.",
                },
                "limit": {"type": "integer", "description": "Max results. Default: 10."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "vault_query",
        "description": "Query the local Vault for session records by pack, user, date range, or text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Filter by pack ID."},
                "user_id": {"type": "string", "description": "Filter by user ID."},
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)."},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)."},
                "query": {"type": "string", "description": "Text search within content (case-insensitive substring match)."},
                "limit": {"type": "integer", "description": "Max records. Default: 10."},
            },
        },
    },
    {
        "name": "vault_inherit",
        "description": "Retrieve field inheritance context from a prior session for a new pack session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Source session ID."},
                "target_pack_id": {"type": "string", "description": "Target pack to inherit into."},
            },
            "required": ["session_id", "target_pack_id"],
        },
    },
    {
        "name": "session_history",
        "description": "List recent sessions from the local database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max sessions. Default: 10."},
                "pack_id": {"type": "string", "description": "Filter by pack ID."},
                "status": {"type": "string", "description": "Filter by status (active, complete)."},
            },
        },
    },
    {
        "name": "session_start",
        "description": "Initialize a new pack session with optional vault inheritance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Pack ID to load."},
                "user_id": {"type": "string", "description": "User ID. Default: mcp_user."},
                "inherit_session_id": {
                    "type": "string",
                    "description": "Prior session ID to inherit vault context from.",
                },
            },
            "required": ["pack_id"],
        },
    },
    {
        "name": "deliverable_read",
        "description": "Read a session deliverable from the output directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID."},
                "format": {
                    "type": "string",
                    "enum": ["full", "summary"],
                    "description": "Output format. Default: summary.",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "watcher_rules",
        "description": "List active watcher rules from config/watchers.yaml.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "draft_packs",
        "description": "List all draft packs in the library. Drafts are auto-generated manifests awaiting human review before promotion to active.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category. Optional.",
                },
                "requires_review": {
                    "type": "boolean",
                    "description": "Filter to only sensitive packs requiring domain expert review.",
                },
            },
        },
    },
    {
        "name": "github_commits",
        "description": "Query git commit history for the 13TMOS repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "file_history"],
                    "description": "Action: list recent commits, or file_history for a specific path.",
                },
                "branch": {"type": "string", "description": "Branch name. Default: main."},
                "limit": {"type": "integer", "description": "Max commits. Default: 10."},
                "path": {"type": "string", "description": "File path for file_history action."},
                "since": {"type": "string", "description": "Since date (YYYY-MM-DD)."},
            },
        },
    },
]


# ─── MCP Server ────────────────────────────────────────────────

class MCPServer:
    """13TMOS kernel MCP server. 12 tools, full pack library access."""

    def __init__(self):
        self._handlers = {
            "engine_status": self._tool_engine_status,
            "pack_list": self._tool_pack_list,
            "pack_read": self._tool_pack_read,
            "pack_search": self._tool_pack_search,
            "frontier": self._tool_frontier,
            "vault_search": self._tool_vault_search,
            "vault_query": self._tool_vault_query,
            "vault_inherit": self._tool_vault_inherit,
            "session_history": self._tool_session_history,
            "session_start": self._tool_session_start,
            "deliverable_read": self._tool_deliverable_read,
            "watcher_rules": self._tool_watcher_rules,
            "draft_packs": self._tool_draft_packs,
            "github_commits": self._tool_github_commits,
        }

        # Lazy-init heavy deps
        self._vault = None
        self._db = None

    @property
    def vault(self):
        if self._vault is None:
            from local_vault import LocalVault
            self._vault = LocalVault()
        return self._vault

    @property
    def db(self):
        if self._db is None:
            from local_db import LocalDB
            self._db = LocalDB()
        return self._db

    @property
    def active_pack_count(self) -> int:
        count = 0
        if PACKS_DIR.exists():
            for d in PACKS_DIR.iterdir():
                if d.is_dir() and (d / "manifest.json").exists():
                    count += 1
        if LIBRARY_DIR.exists():
            for cat in LIBRARY_DIR.iterdir():
                if not cat.is_dir():
                    continue
                for d in cat.iterdir():
                    if d.is_dir() and (d / "manifest.json").exists():
                        count += 1
        return count

    @property
    def stub_count(self) -> int:
        count = 0
        if LIBRARY_DIR.exists():
            for cat in LIBRARY_DIR.iterdir():
                if not cat.is_dir():
                    continue
                for d in cat.iterdir():
                    if d.is_dir() and (d / "header.yaml").exists() and not (d / "manifest.json").exists():
                        count += 1
        return count

    @property
    def tool_count(self) -> int:
        return len(TOOL_DEFINITIONS)

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """Dispatch a tool call. Returns {"result": ...} or {"error": ...}."""
        handler = self._handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = await handler(arguments)
            return {"result": result}
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            return {"error": str(e)}

    # ── Tool Handlers ──────────────────────────────────────

    async def _tool_engine_status(self, args: dict) -> dict:
        vault_records = len(self.vault.list_sessions())
        return {
            "service": "13TMOS",
            "version": "0.1.0",
            "model": os.getenv("TMOS13_MODEL", "claude-sonnet-4-6"),
            "active_packs": self.active_pack_count,
            "stub_count": self.stub_count,
            "vault_records": vault_records,
            "mcp_tools": self.tool_count,
            "status": "online",
        }

    async def _tool_pack_list(self, args: dict) -> dict:
        category_filter = args.get("category")
        status_filter = args.get("status", "active")

        packs = []

        # Active packs from protocols/packs/
        if status_filter in ("active", "all"):
            if PACKS_DIR.exists():
                for d in sorted(PACKS_DIR.iterdir()):
                    if not d.is_dir() or not (d / "manifest.json").exists():
                        continue
                    try:
                        manifest = json.loads((d / "manifest.json").read_text())
                        cat = manifest.get("category", "")
                        if category_filter and cat != category_filter:
                            continue
                        header = self._load_header(d)
                        packs.append({
                            "pack_id": d.name,
                            "name": manifest.get("name", d.name),
                            "category": cat,
                            "status": "active",
                            "description": manifest.get("description", ""),
                            "estimated_turns": header.get("estimated_turns", ""),
                            "version": manifest.get("version", ""),
                        })
                    except (json.JSONDecodeError, OSError):
                        continue

        # Library stubs
        if status_filter in ("stub", "development", "all"):
            if LIBRARY_DIR.exists():
                for cat_dir in sorted(LIBRARY_DIR.iterdir()):
                    if not cat_dir.is_dir():
                        continue
                    if category_filter and cat_dir.name != category_filter:
                        continue
                    for d in sorted(cat_dir.iterdir()):
                        if not d.is_dir():
                            continue
                        has_manifest = (d / "manifest.json").exists()
                        has_header = (d / "header.yaml").exists()
                        if not has_header:
                            continue
                        if has_manifest and status_filter == "stub":
                            continue
                        if not has_manifest and status_filter not in ("stub", "development", "all"):
                            continue
                        header = self._load_header(d)
                        status = "active" if has_manifest else "stub"
                        packs.append({
                            "pack_id": d.name,
                            "name": header.get("name", d.name),
                            "category": cat_dir.name,
                            "status": status,
                            "description": header.get("description", ""),
                            "estimated_turns": header.get("estimated_turns", ""),
                        })

        return {"packs": packs, "count": len(packs)}

    async def _tool_pack_read(self, args: dict) -> dict:
        pack_id = args.get("pack_id", "")
        if not pack_id:
            return {"error": "pack_id required"}

        # Search: packs/ first, then library/
        pack_dir = self._find_pack_dir(pack_id)
        if not pack_dir:
            return {"error": f"Pack '{pack_id}' not found in packs/ or library/"}

        result = {"pack_id": pack_id, "location": str(pack_dir.relative_to(ROOT_DIR))}

        # header.yaml
        header_path = pack_dir / "header.yaml"
        if header_path.exists():
            result["header"] = self._load_header(pack_dir)

        # manifest.json
        manifest_path = pack_dir / "manifest.json"
        if manifest_path.exists():
            try:
                result["manifest_json"] = json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                result["manifest_json"] = None

        # MANIFEST.md — the governing protocol
        manifest_md = pack_dir / "MANIFEST.md"
        if manifest_md.exists():
            result["manifest_md"] = manifest_md.read_text()

        # master.md
        master_md = pack_dir / "master.md"
        if master_md.exists():
            result["master_md"] = master_md.read_text()

        # List all files in the pack
        result["files"] = [f.name for f in sorted(pack_dir.iterdir()) if f.is_file()]

        return result

    async def _tool_pack_search(self, args: dict) -> dict:
        query = args.get("query", "").lower()
        max_results = args.get("max_results", 10)
        if not query:
            return {"error": "query required"}

        results = []

        # Search packs/
        for search_dir, label in [(PACKS_DIR, "packs"), (LIBRARY_DIR, "library")]:
            if not search_dir.exists():
                continue
            dirs = []
            if label == "library":
                for cat in search_dir.iterdir():
                    if cat.is_dir():
                        dirs.extend(d for d in cat.iterdir() if d.is_dir())
            else:
                dirs = [d for d in search_dir.iterdir() if d.is_dir()]

            for d in dirs:
                score = 0
                context_lines = []

                # Check pack ID match
                if query in d.name:
                    score += 5

                # Check header.yaml
                header = self._load_header(d)
                if header:
                    name = header.get("name", "").lower()
                    desc = header.get("description", "").lower()
                    if query in name:
                        score += 4
                    if query in desc:
                        score += 2
                        context_lines.append(header.get("description", "")[:200])

                # Check MANIFEST.md
                manifest_md = d / "MANIFEST.md"
                if manifest_md.exists():
                    try:
                        content = manifest_md.read_text().lower()
                        if query in content:
                            score += 3
                            # Find context line
                            for line in manifest_md.read_text().split("\n"):
                                if query in line.lower():
                                    context_lines.append(line.strip()[:200])
                                    break
                    except OSError:
                        pass

                if score > 0:
                    results.append({
                        "pack_id": d.name,
                        "location": label,
                        "score": score,
                        "name": header.get("name", d.name),
                        "context": context_lines[:3],
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return {"results": results[:max_results], "total": len(results)}

    async def _tool_frontier(self, args: dict) -> dict:
        by_category = {}
        total_active = 0
        total_stubs = 0

        # Count active packs
        if PACKS_DIR.exists():
            for d in PACKS_DIR.iterdir():
                if d.is_dir() and (d / "manifest.json").exists():
                    try:
                        m = json.loads((d / "manifest.json").read_text())
                        cat = m.get("category", "_uncategorized")
                    except Exception:
                        cat = "_uncategorized"
                    by_category.setdefault(cat, {"active": 0, "stubs": 0})
                    by_category[cat]["active"] += 1
                    total_active += 1

        # Count library stubs
        if LIBRARY_DIR.exists():
            for cat_dir in LIBRARY_DIR.iterdir():
                if not cat_dir.is_dir():
                    continue
                cat = cat_dir.name
                by_category.setdefault(cat, {"active": 0, "stubs": 0})
                for d in cat_dir.iterdir():
                    if d.is_dir() and (d / "header.yaml").exists():
                        is_active = (d / "manifest.json").exists()
                        if not is_active:
                            try:
                                import yaml
                                h = yaml.safe_load((d / "header.yaml").read_text()) or {}
                                is_active = h.get("status") == "active"
                            except Exception:
                                pass
                        if is_active:
                            by_category[cat]["active"] += 1
                            total_active += 1
                        else:
                            by_category[cat]["stubs"] += 1
                            total_stubs += 1

        return {
            "total_packs": total_active + total_stubs,
            "active": total_active,
            "stubs": total_stubs,
            "categories": len(by_category),
            "by_category": dict(sorted(by_category.items())),
        }

    async def _tool_vault_search(self, args: dict) -> dict:
        query = args.get("query", "").strip()
        if not query:
            return {"error": "query required"}

        limit = args.get("limit", 10)
        scored = self.vault.search(query, limit=limit)

        results = []
        for item in scored:
            r = item["record"]
            content = r.get("content", {})
            summary = ""
            if isinstance(content, dict):
                summary = content.get("summary", "")
            elif isinstance(content, str):
                summary = content[:200]

            results.append({
                "session_id": r.get("session", ""),
                "pack": r.get("pack", ""),
                "user": r.get("user", ""),
                "date": r.get("date", ""),
                "type": r.get("type", ""),
                "score": item["score"],
                "matched": item["matched"],
                "summary": summary,
                "fields": r.get("fields", {}),
            })

        return {"results": results, "total": len(results), "query": query}

    async def _tool_vault_query(self, args: dict) -> dict:
        dimensions = {}
        if args.get("pack_id"):
            dimensions["pack"] = args["pack_id"]
        if args.get("user_id"):
            dimensions["user"] = args["user_id"]
        if args.get("query"):
            dimensions["content"] = args["query"]

        limit = args.get("limit", 10)

        if dimensions:
            records = self.vault.query(dimensions)
        else:
            summaries = self.vault.list_sessions()
            records = []
            for s in summaries:
                r = self.vault.read(s["session"])
                if r:
                    records.append(r)

        # Filter by date range
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        if date_from or date_to:
            filtered = []
            for r in records:
                d = r.get("date", "")
                if date_from and d < date_from:
                    continue
                if date_to and d > date_to:
                    continue
                filtered.append(r)
            records = filtered

        # Summarize
        results = []
        for r in records[:limit]:
            summary = {
                "session_id": r.get("session", ""),
                "pack": r.get("pack", ""),
                "user": r.get("user", ""),
                "date": r.get("date", ""),
                "type": r.get("type", ""),
                "fields": r.get("fields", {}),
            }
            content = r.get("content", {})
            if isinstance(content, dict):
                summary["summary"] = content.get("summary", "")
            results.append(summary)

        return {"records": results, "total": len(records)}

    async def _tool_vault_inherit(self, args: dict) -> dict:
        session_id = args.get("session_id", "")
        target = args.get("target_pack_id", "")
        if not session_id or not target:
            return {"error": "session_id and target_pack_id required"}

        result = self.vault.inherit(session_id, target)
        return result

    async def _tool_session_history(self, args: dict) -> dict:
        limit = args.get("limit", 10)
        pack_filter = args.get("pack_id")
        status_filter = args.get("status")

        # Query SQLite
        conn = self.db.conn
        query = "SELECT session_id, pack_id, user_id, created_at, status FROM sessions"
        conditions = []
        params = []

        if pack_filter:
            conditions.append("pack_id = ?")
            params.append(pack_filter)
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row[0],
                "pack_id": row[1],
                "user_id": row[2],
                "created_at": row[3],
                "status": row[4],
            })

        return {"sessions": sessions, "count": len(sessions)}

    async def _tool_session_start(self, args: dict) -> dict:
        pack_id = args.get("pack_id", "")
        if not pack_id:
            return {"error": "pack_id required"}

        user_id = args.get("user_id", "mcp_user")
        inherit_id = args.get("inherit_session_id")

        # Verify pack exists
        pack_dir = self._find_pack_dir(pack_id)
        if not pack_dir:
            return {"error": f"Pack '{pack_id}' not found"}

        # Load manifest
        manifest_path = pack_dir / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        # Create session
        session_id = self.db.create_session(
            pack_id=pack_id,
            user_id=user_id,
            manifest={"name": manifest.get("name", pack_id), "version": manifest.get("version", "0.1")},
        )

        # Handle inheritance
        inherited_fields = {}
        if inherit_id:
            inherited = self.vault.inherit(inherit_id, pack_id)
            inherited_fields = inherited.get("field_index", {})
            for k, v in inherited_fields.items():
                self.db.set_state(session_id, k, str(v))

        return {
            "session_id": session_id,
            "pack_id": pack_id,
            "manifest_version": manifest.get("version", "unknown"),
            "inherited_fields": len(inherited_fields),
        }

    async def _tool_deliverable_read(self, args: dict) -> dict:
        session_id = args.get("session_id", "")
        fmt = args.get("format", "summary")
        if not session_id:
            return {"error": "session_id required"}

        # Search output directory
        if OUTPUT_DIR.exists():
            for path in OUTPUT_DIR.glob(f"*{session_id}*"):
                try:
                    content = path.read_text()
                    if fmt == "summary" and len(content) > 2000:
                        # Try to parse JSON and return summary
                        try:
                            data = json.loads(content)
                            return {
                                "pack": data.get("pack", ""),
                                "type": data.get("type", ""),
                                "date": data.get("date", ""),
                                "fields": data.get("fields", {}),
                                "summary": data.get("content", {}).get("summary", ""),
                            }
                        except json.JSONDecodeError:
                            content = content[:2000] + "..."
                    return {"content": content, "file": path.name}
                except OSError:
                    continue

        # Also check vault
        record = self.vault.read(session_id)
        if record:
            if fmt == "summary":
                return {
                    "pack": record.get("pack", ""),
                    "type": record.get("type", ""),
                    "date": record.get("date", ""),
                    "fields": record.get("fields", {}),
                    "summary": record.get("content", {}).get("summary", "")
                    if isinstance(record.get("content"), dict) else "",
                }
            return record

        return {"error": f"No deliverable found for session {session_id}"}

    async def _tool_watcher_rules(self, args: dict) -> dict:
        rules_path = CONFIG_DIR / "watchers.yaml"
        if not rules_path.exists():
            return {"rules": [], "message": "No watchers.yaml found"}

        try:
            import yaml
            data = yaml.safe_load(rules_path.read_text())
            rules = data.get("watchers", []) if data else []
            return {"rules": rules, "count": len(rules)}
        except ImportError:
            return {"error": "PyYAML not installed"}

    async def _tool_draft_packs(self, args: dict) -> dict:
        category_filter = args.get("category")
        review_filter = args.get("requires_review")

        drafts = []
        if LIBRARY_DIR.exists():
            for cat_dir in sorted(LIBRARY_DIR.iterdir()):
                if not cat_dir.is_dir():
                    continue
                if category_filter and cat_dir.name != category_filter:
                    continue
                for pack_dir in sorted(cat_dir.iterdir()):
                    if not pack_dir.is_dir():
                        continue
                    header = self._load_header(pack_dir)
                    if header.get("status") != "draft":
                        continue
                    if review_filter is not None and header.get("requires_review") != review_filter:
                        continue
                    drafts.append({
                        "pack_id": header.get("pack_id", pack_dir.name),
                        "name": header.get("name"),
                        "category": cat_dir.name,
                        "description": header.get("description", ""),
                        "requires_review": header.get("requires_review", False),
                        "draft_date": header.get("draft_date"),
                    })

        return {"drafts": drafts, "total": len(drafts)}

    async def _tool_github_commits(self, args: dict) -> dict:
        action = args.get("action", "list")
        branch = args.get("branch", "main")
        limit = args.get("limit", 10)
        path = args.get("path")
        since = args.get("since")

        # Use local git — no GitHub API needed
        try:
            cmd = ["git", "log", f"--max-count={limit}", "--format=%H|%an|%ai|%s", branch]
            if since:
                cmd.append(f"--since={since}")

            if action == "file_history" and path:
                cmd.extend(["--", path])

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(ROOT_DIR), timeout=10
            )

            if result.returncode != 0:
                return {"error": f"git error: {result.stderr[:200]}"}

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "sha": parts[0][:8],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    })

            return {"commits": commits, "count": len(commits), "branch": branch}

        except subprocess.TimeoutExpired:
            return {"error": "git command timed out"}
        except FileNotFoundError:
            return {"error": "git not found"}

    # ── Helpers ────────────────────────────────────────────

    def _find_pack_dir(self, pack_id: str) -> Path | None:
        """Find a pack directory — checks packs/ then library/."""
        # Check packs/ first
        d = PACKS_DIR / pack_id
        if d.exists() and d.is_dir():
            return d

        # Check library/ (all categories)
        if LIBRARY_DIR.exists():
            for cat in LIBRARY_DIR.iterdir():
                if not cat.is_dir():
                    continue
                d = cat / pack_id
                if d.exists() and d.is_dir():
                    return d

        return None

    def _load_header(self, pack_dir: Path) -> dict:
        """Load header.yaml from a pack directory."""
        header_path = pack_dir / "header.yaml"
        if not header_path.exists():
            return {}
        try:
            import yaml
            return yaml.safe_load(header_path.read_text()) or {}
        except Exception:
            return {}


# ─── FastAPI Endpoints ─────────────────────────────────────────

class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict = {}


def register_mcp_endpoints(app: FastAPI, mcp: MCPServer) -> None:
    """Register /mcp/tools, /mcp/call, /mcp/health endpoints."""

    @app.post("/mcp/tools")
    async def list_tools():
        return {"tools": TOOL_DEFINITIONS}

    @app.post("/mcp/call")
    async def call_tool(request: ToolCallRequest):
        result = await mcp.handle_tool_call(request.tool, request.arguments)
        return result

    @app.get("/mcp/health")
    async def mcp_health():
        return {"status": "online", "tools": len(TOOL_DEFINITIONS)}

    logger.info("MCP endpoints registered: %d tools", len(TOOL_DEFINITIONS))
