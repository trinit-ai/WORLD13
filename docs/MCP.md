# 13TMOS MCP Server

12 tools over SSE transport. Connect Claude Desktop or any MCP client.

---

## What It Is

The MCP (Model Context Protocol) server exposes the full 13TMOS engine
surface as tools usable from Claude Desktop, Claude Code, or any MCP-compatible
client. Read packs, query the vault, inspect the library frontier, start
sessions — all through natural language via Claude with tool access.

---

## Connection

**SSE Endpoint:** `https://13tmos-production.up.railway.app/sse`

**API Key:** Required. Set `MCP_API_KEY` in Railway env. Pass as Bearer token
or `api_key` query parameter.

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "13tmos": {
      "url": "https://13tmos-production.up.railway.app/sse",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_API_KEY"
      }
    }
  }
}
```

Restart Claude Desktop. The 12 tools appear in the tool list.

---

## Tools

| Tool | What It Does | Key Parameters |
|------|-------------|----------------|
| `engine_status` | Engine health: service, model, pack counts, vault records, tool count | — |
| `pack_list` | List available packs from the full library | `category`, `status` (active/stub/all) |
| `pack_read` | Read a pack's full protocol — MANIFEST.md, header.yaml, manifest.json | `pack_id` (required) |
| `pack_search` | Full-text search across all pack manifests | `query` (required), `max_results` |
| `frontier` | Library coverage map: total packs, active vs stubs, by category | — |
| `vault_query` | Query vault for session records by pack, user, date range | `pack_id`, `user_id`, `date_from`, `date_to`, `limit` |
| `vault_inherit` | Retrieve field inheritance context from a prior session | `session_id` (required), `target_pack_id` (required) |
| `session_history` | List recent sessions from local database | `limit`, `pack_id`, `status` |
| `session_start` | Initialize a new pack session with optional inheritance | `pack_id` (required), `user_id`, `inherit_session_id` |
| `deliverable_read` | Read a session deliverable from output directory | `session_id` (required), `format` (full/summary) |
| `watcher_rules` | List active watcher rules from watchers.yaml | — |
| `github_commits` | Query git commit history (uses local git, not GitHub API) | `action` (list/file_history), `branch`, `limit`, `path`, `since` |

---

## Example Workflows

**"What packs are available?"**
```
→ pack_list (status: "active")
← 27 active packs with names, categories, descriptions
```

**"Read the legal_intake manifest"**
```
→ pack_read (pack_id: "legal_intake")
← Full MANIFEST.md, header.yaml, manifest.json content
```

**"What sessions have run this week?"**
```
→ session_history (limit: 20)
→ vault_query (date_from: "2026-03-10")
← Recent sessions with pack, user, date, status
```

**"What's the library frontier look like?"**
```
→ frontier
← 382 total packs, 27 active, 355 stubs, 34 categories with breakdown
```

**"Start an enlightened_duck session"**
```
→ session_start (pack_id: "enlightened_duck")
← Session ID, pack version, ready to run
```

**"Find packs related to healthcare"**
```
→ pack_search (query: "healthcare")
← Matching packs from packs/ and library/ with relevance scores
```

---

## Endpoints

| Method | Path | What It Does |
|--------|------|-------------|
| GET | `/sse` | Open SSE stream (MCP transport) |
| POST | `/messages/{session_id}` | Send JSON-RPC message to SSE session |
| GET | `/mcp/manifest` | Server manifest (name, version, tools count) |
| POST | `/mcp/tools` | List all tool definitions with schemas |
| POST | `/mcp/call` | Invoke a tool directly (non-SSE) |
| GET | `/mcp/health` | MCP server health check |

---

## Security

- `MCP_API_KEY` is required for all SSE connections. No dev mode bypass.
- Vault queries are read-only — the MCP server cannot delete or modify vault records.
- `session_start` creates sessions but does not execute turns (use channels for that).
- `github_commits` reads local git history only — no GitHub API access required.
- Pack manifests are readable but not writable through MCP.

---

## Protocol

MCP SSE transport specification `2024-11-05`. JSON-RPC 2.0 over Server-Sent Events.

1. Client opens `GET /sse` with Bearer auth
2. Server sends `endpoint` event with session-specific POST URL
3. Client sends `initialize` via POST → server returns capabilities
4. Client sends `notifications/initialized` acknowledgment
5. Client sends `tools/list` → server returns all 12 tool definitions
6. Client sends `tools/call` → server executes and returns result
7. Keepalive comments every 30 seconds to prevent timeout
