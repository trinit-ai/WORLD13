# 13TMOS Vault

Persistent session memory. Eight-dimensional addressing.
Burial is architecturally impossible.

---

## What the Vault Is

The vault stores every completed session record in a format designed for
retrieval, not archival. Eight independent dimensions mean any record can
be found from any angle — by pack, by user, by date, by field, by session
ID, by deliverable type, by manifest version, or by content search.

The vault is not a log. It is structured memory with dimensional addressing.

---

## The Eight Dimensions

| Dimension | What It Captures | Example Value |
|-----------|-----------------|---------------|
| Pack | Which protocol governed the session | `legal_intake` |
| User | Who ran the session (channel-prefixed) | `telegram:123456`, `email:sofia@gmail.com` |
| Date | When the session occurred (ISO 8601) | `2026-03-12T14:30:00Z` |
| Type | Deliverable type produced | `case_brief`, `pilgrimage_record`, `audit_report` |
| Fields | Structured data captured during session | `{client_name: "Jane", matter_type: "contract"}` |
| Session | UUID session identifier | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| Manifest | Manifest version signature at session birth | `legal_intake@1.0.0` |
| Content | Full deliverable content | Complete markdown, JSON, or structured output |

Any single dimension is sufficient to locate a record. Cross-dimensional
queries narrow results: "all legal_intake sessions from March 2026 where
matter_type = contract" hits Pack + Date + Fields simultaneously.

---

## Vault File Structure

```
vault/
├── sessions.db         SQLite database (dimensional index + metadata)
└── {session_id}.json   Full session records (one file per session)
```

The SQLite database provides indexed queries across all eight dimensions.
JSON files store the complete session content for each record.

Channel sessions (from the nine channel connectors) are stored in
`config/13tmos.db` in the `channel_sessions` and `channel_exchanges` tables.

---

## Railway Persistence

The vault is mounted on a Railway persistent volume at `/app/vault`.
This volume survives redeploys, restarts, and container replacements.

**Without the volume:** Every redeploy wipes all session records. The
container filesystem is ephemeral.

**With the volume (Session 18):** Data written to `/app/vault` persists
indefinitely. Railway snapshots the volume automatically.

Volume configuration in `railway.toml`:
```toml
[[volumes]]
source = "vault"
target = "/app/vault"
```

Cost: ~$0.25/GB/month. A year of active sessions across all nine channels
will be well under $1.

---

## vault_query MCP Tool

Query the vault from Claude Desktop or any MCP client.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| pack_id | string | Filter by pack ID |
| user_id | string | Filter by user ID |
| date_from | string | Start date (YYYY-MM-DD) |
| date_to | string | End date (YYYY-MM-DD) |
| limit | integer | Max records (default: 10) |

**Example queries:**

All legal intake sessions:
```json
{"tool": "vault_query", "arguments": {"pack_id": "legal_intake"}}
```

Sessions from a specific user in March:
```json
{"tool": "vault_query", "arguments": {"user_id": "telegram:123456", "date_from": "2026-03-01", "date_to": "2026-03-31"}}
```

---

## vault_inherit

Loads prior session context into a new session. When starting a follow-up
session, vault_inherit reads the field index from the source session and
pre-populates state in the new session.

```json
{"tool": "vault_inherit", "arguments": {"session_id": "a1b2c3d4-...", "target_pack_id": "legal_review"}}
```

Fields from the legal_intake session (client name, matter type, etc.) are
inherited into the legal_review session without re-asking.

---

## GET /vault/status

Returns vault health and persistence status.

```json
{
  "vault_dir": "/app/vault",
  "vault_writable": true,
  "vault_db": "/app/vault/sessions.db",
  "vault_db_exists": true,
  "vault_db_size_bytes": 16384,
  "vault_sessions": 12,
  "config_db": "/app/config/13tmos.db",
  "config_db_exists": true,
  "config_db_size_bytes": 32768,
  "channel_sessions": 5
}
```

---

## What Never Goes in the Vault

- Passwords or authentication tokens
- Payment data (credit cards, bank accounts)
- Raw PII beyond what the pack spec explicitly requires
- API keys or secrets

The vault stores session records as defined by pack manifests. If a pack
captures a client name and email for a legal intake, that data is in the
vault. If it doesn't need it, it's not captured.

---

## What Never Goes to GitHub

`vault/` is in `.gitignore`. Session records contain PII and are never
committed to the repository. The Railway volume is the authoritative store.
There is no GitHub backup of vault data. This is intentional.
