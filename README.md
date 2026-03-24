# 13TMOS

**The 13TMOS engine. Stripped to its pure form.**

Protocol-driven AI sessions. Pack manifests govern behavior. Claude executes.
The vault remembers. The watcher routes. Nine channels deliver.

This is not a chat interface. This is not a wrapper. This is the kernel.

---

## What It Is

13TMOS is the local distillation of the TMOS13 platform — the protocol engine
and pack manifests running without a GUI, without a cloud database, without a
dashboard. SQLite. Flat JSON vault. Terminal interface. Claude API.

The thesis: the protocol engine and pack manifests are the complete product.
The interface is cosmetic.

---

## Live

```
Engine:   https://13tmos-production.up.railway.app
MCP:      https://13tmos-production.up.railway.app/sse
Health:   https://13tmos-production.up.railway.app/health
Vault:    https://13tmos-production.up.railway.app/vault/status
Channels: https://13tmos-production.up.railway.app/channels
```

---

## Architecture

```
13tmos/
├── engine/                 Python FastAPI engine
│   ├── app.py              All routes + channel registration
│   ├── session_runner.py   Pack session execution (never changes per channel)
│   ├── local_vault.py      SQLite vault — dimensional addressing
│   ├── watcher.py          Event-driven vault routing
│   ├── mcp_server.py       12 MCP tools via SSE transport
│   ├── channel_*.py        Nine channel adapters (9 files)
│   └── ...
├── protocols/
│   ├── packs/              28 deployed packs (full manifests)
│   ├── library/            379 library packs across 24 categories
│   ├── shared/             Shared protocol fragments
│   └── private/            Private packs (.gitignore'd)
├── vault/                  Persistent SQLite + JSON records
├── output/                 Deliverable output (ephemeral)
├── config/
│   └── watchers.yaml       Watcher routing rules
├── docs/                   Architecture + deployment docs
├── deploy.sh               Interactive instance provisioner
├── docker-compose.yml      Self-contained Docker deployment
└── run.sh                  CLI console wrapper
```

---

## Pack Library

```
Total:      381 packs (deduplicated)
Deployed:   28  (protocols/packs/ — full manifests, runnable)
Library:    379 (protocols/library/ — authored with manifests)
Categories: 24
```

Run `GET /frontier` or use MCP tool `frontier` for live coverage map.

---

## Nine Channels

Every channel uses the same session runner. The pack never changes for the
channel. The channel adapts to the pack.

| Channel   | Webhook                              | Credentials          |
|-----------|--------------------------------------|----------------------|
| Telegram  | POST /channels/telegram/{token}      | TELEGRAM_BOT_TOKEN   |
| WhatsApp  | POST /channels/whatsapp/webhook      | TWILIO_*             |
| Email     | POST /channels/email/inbound         | RESEND_API_KEY       |
| SMS       | POST /channels/sms/webhook           | TWILIO_* (shared)    |
| Discord   | POST /channels/discord/webhook       | DISCORD_BOT_TOKEN    |
| Slack     | POST /channels/slack/webhook         | SLACK_BOT_TOKEN      |
| Messenger | POST /channels/messenger/webhook     | META_PAGE_TOKEN      |
| Instagram | POST /channels/instagram/webhook     | META_PAGE_TOKEN      |
| Web       | WS   /channels/web/{token}           | None — live now      |

See [docs/CHANNELS.md](docs/CHANNELS.md) for full activation guide.

---

## Vault

Eight-dimensional addressing. Every completed session writes a record.
Retrievable by: Pack, User, Date, Type, Fields, Session, Manifest, Content.

```
Local:    ~/13tmos/vault/sessions.db
Railway:  /app/vault/sessions.db (persistent volume)
```

Status: `GET /vault/status`

---

## MCP Tools (12)

Connect Claude Desktop or any MCP client to:
`https://13tmos-production.up.railway.app/sse`

Tools: `engine_status` `pack_list` `pack_read` `pack_search` `frontier`
`vault_query` `vault_inherit` `session_history` `session_start`
`deliverable_read` `watcher_rules` `github_commits`

---

## Session Seeding

Pre-load any session with context before the recipient sends their first message:

```bash
curl -X POST https://13tmos-production.up.railway.app/channels/seed \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "telegram",
    "sender_id": "123456789",
    "pack_id": "enlightened_duck",
    "name": "Sofia",
    "context": "met at the gallery on Spring St"
  }'
```

For email, add `"opening_email": true` to have the pack reach out first.

---

## Running Locally

```bash
# Install
cd ~/13tmos/engine
pip install -e .

# Configure
cp ../.env.example ../.env
# Add ANTHROPIC_API_KEY and TMOS13_MODEL=claude-sonnet-4-6

# Start engine (API server)
uvicorn app:app --reload --port 8000

# CLI console (deck mode)
./run.sh

# Direct pack launch
./run.sh --pack enlightened_duck

# List all packs
./run.sh --list
```

---

## Docker Deployment

```bash
# Interactive provisioning (generates .env, builds, launches)
./deploy.sh

# Or manual
cp .env.example .env   # fill in your keys
docker compose up -d

# Verify
curl http://localhost:8000/health
```

See [docs/DEPLOY.md](docs/DEPLOY.md) for enterprise deployment guide.

---

## Build Sessions (20 complete)

| # | What was built |
|---|----------------|
| 01 | Project structure, engine, protocols directory |
| 02 | SQLite vault, console.py terminal interface |
| 03 | Vault dimensional query + session inheritance |
| 04 | Orchestrator (pending) |
| 05 | Meta-session console, progressive pack loading |
| 06 | Pack library, 24 categories, frontier endpoint |
| 07 | Pack Builder Pack — recursive pack authoring via session |
| 08 | Private library, Robert C. Ventura pack |
| 09 | Watcher — event-driven vault routing via watchers.yaml |
| 10 | Vault Audit Pack — compliance surface |
| 11 | Bridge — local/production vault sync |
| 12 | MCP SSE transport, 12 tools, Claude Desktop integration |
| 13 | Railway deployment, clean MCP server |
| 14 | WhatsApp channel (Twilio) |
| 15 | Telegram channel + session seeding API |
| 16 | Email channel (Resend inbound) |
| 17 | Six more channels (SMS, Discord, Slack, Messenger, Instagram, Web) |
| 18 | Railway volume mount — vault persistence |
| 19 | 96-command CLI, library wired into pack loader (381 packs visible) |
| 20 | Enterprise delivery package — deploy.sh, Docker, deployment guide |

See [docs/SESSIONS.md](docs/SESSIONS.md) for expanded build history.

---

## Related

- Production platform: [tmos13.ai](https://tmos13.ai)
- Railway engine: [13tmos-production.up.railway.app](https://13tmos-production.up.railway.app)
- Parent repo: trinit-ai/tmos13.ai (private)

---

*Deploy Yourself — TMOS13, LLC*
