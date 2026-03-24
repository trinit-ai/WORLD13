"""
13TMOS Session Runner — Channel-Agnostic Message Handler

Handles message routing for any channel (WhatsApp, SMS, email, voice).
Session continuity keyed on channel + sender identifier.

The runner:
  1. Looks up or creates a session for the sender
  2. Loads the governing pack protocol
  3. Builds conversation history + system prompt
  4. Calls Claude (with tools if declared in manifest)
  5. Loops on tool_use responses — execute tool, feed result back
  6. Persists the exchange
  7. Returns the response text

Commands:
  load {pack_id}  — switch to a different pack
  reset           — restart current session
  status          — show session state
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import anthropic

logger = logging.getLogger("13tmos.session_runner")

# Maximum tool-use round-trips per message to prevent infinite loops
MAX_TOOL_LOOPS = 5

# Strip engine signals from model output before returning to channels
_STATE_SIGNAL_RE = re.compile(r'\[STATE:[^\]]+\]')
_ENGINE_SIGNAL_RE = re.compile(r'\[(NAVIGATE|ACTION|FIELD|CARTRIDGE|TOOL_REQUEST|REQUIRES_CONFIRMATION):[^\]]*\]')


def _strip_signals(text: str) -> str:
    """Remove [STATE:...], [NAVIGATE:...], :::fences, and other engine signals from channel output."""
    text = _STATE_SIGNAL_RE.sub('', text)
    text = _ENGINE_SIGNAL_RE.sub('', text)
    # Strip :::directive fences (:::card, :::note, etc.)
    text = re.sub(r'^:::\w*\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKS_DIR = ROOT_DIR / "protocols" / "packs"
LIBRARY_DIR = ROOT_DIR / "protocols" / "library"
USER_PACKS_DIR = ROOT_DIR / "protocols" / "user"
BOOKS_DIR = ROOT_DIR / "protocols" / "books"
DB_PATH = ROOT_DIR / "config" / "13tmos.db"

# Channel rendering constraints injected at system level
CHANNEL_CONSTRAINTS = {
    "whatsapp": (
        "\n\n---\nCHANNEL CONSTRAINT — WhatsApp:\n"
        "- No markdown headers, bold, italic, or code blocks. Plain text only.\n"
        "- Keep responses under 1500 characters. WhatsApp truncates long messages.\n"
        "- Use line breaks for structure. No bullet points.\n"
        "- Emojis are acceptable sparingly.\n"
    ),
    "sms": (
        "\n\n---\nCHANNEL CONSTRAINT — SMS:\n"
        "- Maximum 1600 characters per response.\n"
        "- Plain text only. No formatting.\n"
        "- Be extremely concise.\n"
    ),
}


class PackRegistry:
    """Loads pack protocol files for the session runner."""

    def find_pack_dir(self, pack_id: str) -> Path | None:
        # Check user packs first (personal forks)
        d = USER_PACKS_DIR / pack_id
        if d.exists() and d.is_dir():
            return d
        # Check living books
        d = BOOKS_DIR / pack_id
        if d.exists() and d.is_dir():
            return d
        d = PACKS_DIR / pack_id
        if d.exists() and d.is_dir():
            return d
        if LIBRARY_DIR.exists():
            for cat in LIBRARY_DIR.iterdir():
                if not cat.is_dir():
                    continue
                d = cat / pack_id
                if d.exists() and d.is_dir():
                    return d
        return None

    def load_protocol(self, pack_id: str) -> dict | None:
        """Load a pack's protocol files. Returns dict with system_prompt, name, etc."""
        pack_dir = self.find_pack_dir(pack_id)
        if not pack_dir:
            return None

        result = {"pack_id": pack_id, "pack_dir": str(pack_dir)}

        # master.md is the primary protocol
        master = pack_dir / "master.md"
        if master.exists():
            result["master"] = master.read_text()

        # MANIFEST.md as fallback / supplement
        manifest_md = pack_dir / "MANIFEST.md"
        if manifest_md.exists():
            result["manifest_md"] = manifest_md.read_text()

        # manifest.json for metadata
        manifest_json = pack_dir / "manifest.json"
        if manifest_json.exists():
            try:
                meta = json.loads(manifest_json.read_text())
                result["name"] = meta.get("name", pack_id)
                result["version"] = meta.get("version", "")
                result["category"] = meta.get("category", "")
            except (json.JSONDecodeError, OSError):
                pass

        result.setdefault("name", pack_id)

        # Build system prompt: master.md is authoritative
        system_prompt = result.get("master", result.get("manifest_md", ""))
        result["system_prompt"] = system_prompt

        return result

    def load_manifest(self, pack_id: str) -> dict | None:
        """Load a pack's manifest.json. Returns None if not found."""
        pack_dir = self.find_pack_dir(pack_id)
        if not pack_dir:
            return None
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def list_packs(self) -> list[str]:
        """List available pack IDs."""
        packs = []
        if PACKS_DIR.exists():
            for d in sorted(PACKS_DIR.iterdir()):
                if d.is_dir() and (d / "manifest.json").exists():
                    packs.append(d.name)
        return packs


def _build_tool_definitions(manifest: dict) -> list[dict]:
    """Build Claude API tool definitions from a pack manifest's tools section.

    Returns a list of tool dicts in Anthropic's tool schema format.
    Only includes enabled tools.
    """
    tools_section = manifest.get("tools", {})
    if not tools_section:
        return []

    definitions = []
    for tool_id, tool_decl in tools_section.items():
        if not tool_decl.get("enabled", True):
            continue

        # Build input schema from provider type
        provider = tool_decl.get("provider", "internal")
        scopes = tool_decl.get("scopes", [])

        # Default schema — just query string
        properties = {
            "query": {
                "type": "string",
                "description": "The query or input for this tool",
            }
        }
        required = ["query"]

        # Provider-specific schemas
        if provider == "web_search":
            properties = {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results (1-10, default 5)",
                },
            }
            required = ["query"]
        elif provider == "vault":
            if scopes and scopes[0] == "search":
                properties = {
                    "query": {
                        "type": "string",
                        "description": "Search query — matches pack names, field values, content summaries",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                    },
                }
                required = ["query"]
            else:
                properties = {
                    "pack_id": {
                        "type": "string",
                        "description": "Filter by pack ID",
                    },
                    "query": {
                        "type": "string",
                        "description": "Text search within content",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                    },
                }
                required = []

        definitions.append({
            "name": tool_id,
            "description": tool_decl.get("description", ""),
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        })

    return definitions


def _execute_vault_tool(operation: str, params: dict) -> dict:
    """Execute a vault tool operation using the local vault.

    Supported operations:
      search — fuzzy ranked search across all records
      query  — dimensional query with optional text filter
    """
    from local_vault import LocalVault
    vault = LocalVault()

    if operation == "search":
        query = params.get("query", "").strip()
        if not query:
            return {"success": False, "message": "Missing required parameter: query"}
        limit = params.get("limit", 10)
        scored = vault.search(query, limit=limit)

        lines = [f"Vault search results for: {query}\n"]
        for item in scored:
            r = item["record"]
            content = r.get("content", {})
            summary = ""
            if isinstance(content, dict):
                summary = content.get("summary", "")
            elif isinstance(content, str):
                summary = content[:200]

            lines.append(f"- [{r.get('date', '?')}] {r.get('pack', '?')} (score: {item['score']})")
            if summary:
                lines.append(f"  Summary: {summary[:150]}")
            fields = r.get("fields", {})
            if fields:
                field_str = ", ".join(f"{k}={v}" for k, v in list(fields.items())[:5])
                lines.append(f"  Fields: {field_str}")
            lines.append("")

        return {
            "success": True,
            "message": "\n".join(lines) if scored else f"No vault records found for: {query}",
            "results_count": len(scored),
            "query": query,
        }

    elif operation == "query":
        dimensions = {}
        if params.get("pack_id"):
            dimensions["pack"] = params["pack_id"]
        if params.get("query"):
            dimensions["content"] = params["query"]
        limit = params.get("limit", 10)

        if dimensions:
            records = vault.query(dimensions)
        else:
            records = [
                vault.read(s["session"])
                for s in vault.list_sessions()
                if vault.read(s["session"])
            ]

        lines = [f"Vault query results ({len(records)} found):\n"]
        for r in records[:limit]:
            content = r.get("content", {})
            summary = ""
            if isinstance(content, dict):
                summary = content.get("summary", "")
            lines.append(f"- [{r.get('date', '?')}] {r.get('pack', '?')} — {r.get('session', '?')[:8]}")
            if summary:
                lines.append(f"  {summary[:150]}")
            lines.append("")

        return {
            "success": True,
            "message": "\n".join(lines) if records else "No vault records found.",
            "results_count": len(records),
        }

    return {"success": False, "message": f"Unsupported vault operation: {operation}"}


async def _execute_tool(tool_name: str, tool_input: dict, manifest: dict) -> dict:
    """Execute a tool by name using the appropriate provider.

    Returns a dict with 'success', 'message', and provider-specific data.
    """
    tools_section = manifest.get("tools", {})
    tool_decl = tools_section.get(tool_name)

    if not tool_decl:
        return {"success": False, "message": f"Unknown tool: {tool_name}"}

    provider_name = tool_decl.get("provider", "internal")
    scopes = tool_decl.get("scopes", [])
    operation = scopes[0] if scopes else tool_name
    config = tool_decl.get("config", {})

    # Load provider
    try:
        if provider_name == "web_search":
            from tool_providers.web_search import WebSearchProvider
            provider = WebSearchProvider()
            return await provider.execute(
                operation=operation,
                parameters=tool_input,
                config=config,
            )
        elif provider_name == "vault":
            return _execute_vault_tool(operation, tool_input)
        else:
            return {"success": False, "message": f"Provider '{provider_name}' not available in kernel mode."}
    except Exception as e:
        logger.error("Tool execution failed: %s.%s: %s", tool_name, operation, e)
        return {"success": False, "message": f"Tool failed: {e}"}


class SessionRunner:
    """Channel-agnostic session runner. One runner per engine instance."""

    def __init__(self, db_path: Path = None):
        self.registry = PackRegistry()
        self.db_path = db_path or DB_PATH
        self._conn = None
        self._client = None
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def _init_db(self):
        """Create channel_sessions and channel_exchanges tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS channel_sessions (
                channel TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                turn_count INTEGER NOT NULL DEFAULT 0,
                seed_name TEXT DEFAULT NULL,
                seed_context TEXT DEFAULT NULL,
                PRIMARY KEY (channel, sender_id)
            );

            CREATE TABLE IF NOT EXISTS channel_exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ch_exchanges_session
                ON channel_exchanges(session_id, created_at);
        """)
        # Schema migration: add seed columns if table predates them
        try:
            self.conn.execute("ALTER TABLE channel_sessions ADD COLUMN seed_name TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            self.conn.execute("ALTER TABLE channel_sessions ADD COLUMN seed_context TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()
        logger.info("Session runner DB initialized")

    # ── Public API ────────────────────────────────────────

    async def handle_message(
        self, channel: str, sender_id: str, text: str, default_pack: str = None
    ) -> str:
        """Process an inbound message. Returns response text."""
        text = text.strip()

        # Handle commands
        lower = text.lower()
        if lower.startswith("load "):
            return self._cmd_load(channel, sender_id, text[5:].strip())
        if lower == "reset":
            return self._cmd_reset(channel, sender_id)
        if lower == "status":
            return self._cmd_status(channel, sender_id)

        # Get or create session
        session = self._get_session(channel, sender_id)
        if not session:
            pack_id = default_pack or os.getenv("TMOS13_PACK", "guest")
            session = self._create_session(channel, sender_id, pack_id)
            if not session:
                return f"Pack '{pack_id}' not found. Send 'load <pack_id>' to choose a pack."

        pack_id = session["pack_id"]
        session_id = session["session_id"]

        # Load protocol
        protocol = self.registry.load_protocol(pack_id)
        if not protocol:
            return f"Pack '{pack_id}' protocol files not found."

        # Build messages
        system_prompt = protocol["system_prompt"]

        # Inject channel constraint
        constraint = CHANNEL_CONSTRAINTS.get(channel, "")
        if constraint:
            system_prompt += constraint

        # Load conversation history
        history = self._get_history(session_id)
        messages = [{"role": ex["role"], "content": ex["content"]} for ex in history]
        messages.append({"role": "user", "content": text})

        # Build tool definitions from manifest
        manifest = self.registry.load_manifest(pack_id) or {}
        tool_defs = _build_tool_definitions(manifest)

        # Call Claude (with tool-use loop)
        model = os.getenv("TMOS13_MODEL", "claude-sonnet-4-6")
        try:
            raw_reply = await self._call_with_tools(
                model, system_prompt, messages, tool_defs, manifest
            )
            reply = _strip_signals(raw_reply)
        except Exception as e:
            logger.exception("Claude API call failed")
            return f"The duck is momentarily distracted. (Error: {str(e)[:100]})"

        # Persist exchange
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            "INSERT INTO channel_exchanges (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "user", text, now),
        )
        self.conn.execute(
            "INSERT INTO channel_exchanges (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "assistant", reply, now),
        )
        self.conn.execute(
            "UPDATE channel_sessions SET last_active = ?, turn_count = turn_count + 1 WHERE session_id = ?",
            (now, session_id),
        )
        self.conn.commit()

        return reply

    async def _call_with_tools(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict],
        tool_defs: list[dict],
        manifest: dict,
    ) -> str:
        """Call Claude with tool-use loop.

        If Claude returns tool_use blocks, execute each tool, append results,
        and re-call until Claude produces a text response (or we hit the loop cap).
        """
        api_kwargs = {
            "model": model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages,
        }
        if tool_defs:
            api_kwargs["tools"] = tool_defs

        for loop_i in range(MAX_TOOL_LOOPS + 1):
            response = self.client.messages.create(**api_kwargs)

            # Check for tool_use blocks
            tool_use_blocks = [
                b for b in response.content
                if getattr(b, "type", None) == "tool_use"
            ]

            if not tool_use_blocks:
                # No tool calls — extract text and return
                text_parts = [
                    b.text for b in response.content
                    if getattr(b, "type", None) == "text"
                ]
                return "\n".join(text_parts) if text_parts else ""

            if loop_i >= MAX_TOOL_LOOPS:
                logger.warning("Tool loop cap reached (%d), returning partial text", MAX_TOOL_LOOPS)
                text_parts = [
                    b.text for b in response.content
                    if getattr(b, "type", None) == "text"
                ]
                return "\n".join(text_parts) if text_parts else "(Tool loop limit reached.)"

            # Append assistant response (with tool_use blocks) to messages
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool and build tool_result blocks
            tool_results = []
            for block in tool_use_blocks:
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_input)[:200])

                result = await _execute_tool(tool_name, tool_input, manifest)
                result_content = result.get("message", json.dumps(result))

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_content,
                })

            # Append tool results as user message and loop
            messages.append({"role": "user", "content": tool_results})
            api_kwargs["messages"] = messages

        return ""

    def seed_session(
        self,
        channel: str,
        sender_id: str,
        pack_id: str,
        name: str,
        context: str = "",
    ) -> dict:
        """Pre-seed a session before the recipient sends their first message.

        Creates a session with status='seeded' and stores the recipient's name
        and context. When they message, handle_message picks up the seeded session
        and injects the primer into conversation history.
        """
        if not self.registry.find_pack_dir(pack_id):
            return {"error": f"Pack '{pack_id}' not found"}

        # Close any existing session for this sender
        self.conn.execute(
            "UPDATE channel_sessions SET status = 'complete' WHERE channel = ? AND sender_id = ? AND status IN ('active', 'seeded')",
            (channel, sender_id),
        )

        session_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self.conn.execute(
            "INSERT INTO channel_sessions (channel, sender_id, session_id, pack_id, created_at, last_active, status, turn_count, seed_name, seed_context) "
            "VALUES (?, ?, ?, ?, ?, ?, 'seeded', 0, ?, ?)",
            (channel, sender_id, session_id, pack_id, now, now, name, context),
        )

        # Write the seed primer as the first exchange pair
        primer = f"[SESSION SEEDED]\nRecipient name: {name}"
        if context:
            primer += f"\nContext: {context}"
        primer += (
            "\n\nWhen this recipient sends their first message, address them by name. "
            "The experience should feel made for them — because it was."
        )
        self.conn.execute(
            "INSERT INTO channel_exchanges (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "user", primer, now),
        )
        self.conn.execute(
            "INSERT INTO channel_exchanges (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "assistant", f"[Understood. Session seeded for {name}. Ready.]", now),
        )
        self.conn.commit()

        logger.info("Session seeded: channel=%s sender=%s pack=%s name=%s",
                     channel, sender_id[:6], pack_id, name)
        return {
            "session_id": session_id,
            "channel": channel,
            "sender_id": sender_id,
            "pack_id": pack_id,
            "name": name,
            "context": context,
            "status": "seeded",
            "message": f"Session ready for {name}. When they text the bot, they drop in by name.",
        }

    async def get_opening_message(
        self, pack_id: str, name: str, context: str = ""
    ) -> str:
        """Generate a pack's opening message for a named recipient.

        Used by the seed endpoint to send the first email/message
        before the recipient has contacted the bot.
        """
        protocol = self.registry.load_protocol(pack_id)
        if not protocol:
            return f"Welcome, {name}."

        system_prompt = protocol["system_prompt"]
        prompt = f"Open the session for {name}."
        if context:
            prompt += f" Context: {context}."
        prompt += " Write only the opening message. No preamble."

        model = os.getenv("TMOS13_MODEL", "claude-sonnet-4-6")
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.exception("Failed to generate opening message")
            return f"Welcome, {name}."

    def get_session_info(self, channel: str, sender_id: str) -> dict | None:
        """Get session info for a channel/sender pair."""
        return self._get_session(channel, sender_id)

    # ── Commands ──────────────────────────────────────────

    def _cmd_load(self, channel: str, sender_id: str, pack_id: str) -> str:
        pack_id = pack_id.strip().lower().replace(" ", "_")
        protocol = self.registry.load_protocol(pack_id)
        if not protocol:
            available = self.registry.list_packs()
            pack_list = ", ".join(available[:10]) if available else "none"
            return f"Pack '{pack_id}' not found.\n\nAvailable: {pack_list}"

        # Create new session for this pack
        session = self._create_session(channel, sender_id, pack_id)
        if not session:
            return f"Failed to create session for '{pack_id}'."

        name = protocol.get("name", pack_id)
        return f"Loaded: {name}\n\nSend your first message to begin."

    def _cmd_reset(self, channel: str, sender_id: str) -> str:
        session = self._get_session(channel, sender_id)
        if not session:
            return "No active session to reset."

        pack_id = session["pack_id"]
        self._create_session(channel, sender_id, pack_id)
        return f"Session reset. Pack: {pack_id}\n\nSend your first message to begin."

    def _cmd_status(self, channel: str, sender_id: str) -> str:
        session = self._get_session(channel, sender_id)
        if not session:
            return "No active session.\n\nSend 'load <pack_id>' to start."

        return (
            f"Channel: {channel}\n"
            f"Pack: {session['pack_id']}\n"
            f"Session: {session['session_id'][:8]}\n"
            f"Turns: {session['turn_count']}\n"
            f"Started: {session['created_at']}\n"
            f"Last active: {session['last_active']}"
        )

    # ── Internal ──────────────────────────────────────────

    def _get_session(self, channel: str, sender_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM channel_sessions WHERE channel = ? AND sender_id = ? AND status IN ('active', 'seeded')",
            (channel, sender_id),
        ).fetchone()
        if not row:
            return None
        session = dict(row)
        # Activate seeded sessions on first real message
        if session["status"] == "seeded":
            self.conn.execute(
                "UPDATE channel_sessions SET status = 'active' WHERE session_id = ?",
                (session["session_id"],),
            )
            self.conn.commit()
            session["status"] = "active"
        return session

    def _create_session(self, channel: str, sender_id: str, pack_id: str) -> dict | None:
        # Verify pack exists
        if not self.registry.find_pack_dir(pack_id):
            return None

        # Remove any existing session for this channel/sender (PK constraint)
        self.conn.execute(
            "DELETE FROM channel_sessions WHERE channel = ? AND sender_id = ?",
            (channel, sender_id),
        )

        session_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        self.conn.execute(
            "INSERT INTO channel_sessions (channel, sender_id, session_id, pack_id, created_at, last_active, status, turn_count) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', 0)",
            (channel, sender_id, session_id, pack_id, now, now),
        )
        self.conn.commit()

        logger.info("New session: channel=%s sender=%s pack=%s session=%s",
                     channel, sender_id[:6], pack_id, session_id[:8])
        return {
            "channel": channel,
            "sender_id": sender_id,
            "session_id": session_id,
            "pack_id": pack_id,
            "created_at": now,
            "last_active": now,
            "status": "active",
            "turn_count": 0,
        }

    def _get_history(self, session_id: str, limit: int = 50) -> list[dict]:
        """Load conversation history for a session."""
        rows = self.conn.execute(
            "SELECT role, content FROM channel_exchanges WHERE session_id = ? ORDER BY created_at LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
