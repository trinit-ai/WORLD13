# 13TMOS Architecture

## The Protocol Engine

The core claim: the protocol engine and pack manifests are the complete
product. Everything else is delivery infrastructure.

```
Pack manifest    — governs session behavior (routing, turns, deliverables)
Session runner   — executes any pack, never changes per channel
Vault            — writes every completed session to 8-dimensional storage
Watcher          — routes vault events to downstream actions
Channels         — nine front doors, all feeding the same runner
MCP              — 12 tools for Claude Desktop / any MCP client
```

## Session Lifecycle

```
1. Channel receives message (Telegram, WhatsApp, email, etc.)
2. channel_*.py normalizes to handle_message(channel, sender_id, text, pack)
3. SessionRunner looks up or creates session keyed on (channel, sender_id)
4. session_runner.py loads pack protocol from protocols/packs/{pack_id}/
5. Conversation history loaded from channel_exchanges table
6. Assembler builds system prompt:
   branding → company_profile → master.md → skill.md → memory.md
   → shared protocols (narrative architecture, formatting guide;
     pack_builder also gets toolkit, refinement, project instructions)
   → active cartridge → session state → special instructions
7. Claude generates response within protocol constraints
8. Exchange persisted to channel_exchanges, turn_count incremented
9. On completion: vault writes 8-dimensional record, watcher fires rules
10. Deliverable written to output/
```

## Pack Manifest Structure

Every active pack has protocol files in `protocols/packs/{pack_id}/`:

```
master.md       — primary session protocol (acts, routing rules, voice)
MANIFEST.md     — governing behavioral spec (routing, personas, rules, deliverables)
header.yaml     — pack metadata (name, version, category, description)
manifest.json   — machine-readable spec (fields, routing graph, features)
```

Not every pack has all four files. `master.md` is authoritative when present;
`MANIFEST.md` is the fallback. `manifest.json` provides metadata and structured
configuration.

Stubs in `protocols/library/{category}/{pack_id}/` have only `header.yaml` —
reserved names awaiting full authoring.

## Vault — Dimensional Addressing

Eight retrieval dimensions for every session record:

| Dimension | What it captures | Example |
|-----------|-----------------|---------|
| Pack | Which protocol governed the session | `legal_intake` |
| User | Who ran it (channel-prefixed) | `telegram:123456`, `email:x@y.com` |
| Date | When (ISO 8601) | `2026-03-12T14:30:00Z` |
| Type | Deliverable type | `case_brief`, `pilgrimage_record` |
| Fields | Structured fields captured | `{client_name, matter_type}` |
| Session | UUID session identifier | `a1b2c3d4-...` |
| Manifest | Manifest version at session birth | `legal_intake@1.0.0` |
| Content | Full deliverable content | Complete markdown/JSON |

Burial is architecturally impossible. Eight independent retrieval angles.

## Watcher

Reads `config/watchers.yaml`. Fires rules when vault records match conditions.
Supports condition operators: `==`, `!=`, `>=`, `<=`, `>`, `<`, `in`, `not in`,
`%` (modulo), boolean combinators (`and`, `or`, `not`), and nested field access.

Four action types: `notify`, `route`, `archive`, `webhook`.

Background mode: `start_background()` runs as a daemon thread in the console.

## Channel Architecture

All nine channels share one pattern:

```python
# Every channel_*.py follows this structure:
_runner = None

def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner

def register_{channel}_channel(app: FastAPI) -> None:
    @app.post("/channels/{channel}/webhook")
    async def webhook(request: Request):
        # Parse platform-specific inbound format
        sender_id = ...
        text = ...
        # Route through session runner
        reply = await _get_runner().handle_message(
            channel="{channel}", sender_id=sender_id,
            text=text, default_pack=DEFAULT_PACK,
        )
        # Reply in platform-specific format
        ...
```

`CHANNEL_CONSTRAINTS` injects rendering rules per platform:
- WhatsApp/SMS: plain text, character limits
- Telegram: basic Markdown
- Discord: Markdown, 2000 char limit
- Slack: mrkdwn formatting
- Email: letter-like cadence, longer responses
- Web: full Markdown

Session continuity is keyed on `(channel, sender_id)`. The same person
messaging from the same account always resumes the same session.

## Session Seeding

Pre-loads a session before the recipient sends their first message.
A seed primer exchange pair is written to `channel_exchanges`. When the
recipient messages, `_get_session()` finds the seeded session, flips
status from `seeded` to `active`, and Claude sees the primer in history.

For email, `opening_email: true` generates and sends the first message
via Resend — the pack reaches out before the recipient has contacted it.

## MCP Integration

SSE transport at `/sse`. API key required (`MCP_API_KEY` env var).
JSON-RPC 2.0 over Server-Sent Events per MCP spec `2024-11-05`.

12 tools expose the full engine surface to Claude Desktop:

| Category | Tools |
|----------|-------|
| Observability | `engine_status`, `frontier` |
| Library | `pack_list`, `pack_read`, `pack_search` |
| Memory | `vault_query`, `vault_inherit` |
| Sessions | `session_history`, `session_start` |
| Output | `deliverable_read` |
| Routing | `watcher_rules` |
| History | `github_commits` |

## Key Principles

- The manifest does not change for the channel. The channel adapts to the pack.
- The session runner never changes per channel. New channel = new `channel_*.py` file.
- Vault records are permanent. Deliverables are ephemeral.
- Every pack is a behavioral contract, not a prompt template.
- Eight-dimensional addressing makes burial architecturally impossible.
