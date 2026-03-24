# 13TMOS Console — FAQ & Reference

## Starting the Console

```bash
# Deck mode (launcher menu)
./run.sh

# Direct pack launch
./run.sh --pack legal_intake

# With vault inheritance from a prior session
./run.sh --pack legal_intake --session a446ea6e

# Resume a paused session
./run.sh --resume <session_id>

# List available packs
./run.sh --list
```

No `--pack` flag = deck mode. The deck shows all active packs grouped by category. Type a pack name to launch it.

---

## Deck Mode

The deck is the launcher. It renders a menu of active packs and accepts natural language routing.

**Navigating:**
- Type a pack name: `legal intake`, `enlightened duck`, `desk`
- Type a pack ID: `legal_intake`, `rpg_dungeon`
- Partial matches work: `legal` resolves to `legal_intake` (if unambiguous)
- Slash prefix works: `/welcome` resolves to `welcome`

**After a session:** You return to the deck menu. A "recent" line shows your last session.

---

## 96 Commands

The console has 96 unique commands across two contexts: deck (launcher) and session (inside a pack). Many commands are available in both.

### Deck Commands (55)

| Section | Commands |
|---------|----------|
| **Discovery** | `/library` `/search` `/browse` `/dept` `/info` `/random` `/private` `/builder` `/size` `/tree` `/schema` |
| **Sessions** | `/resume` `/recent` `/read` `/read last` `/find` `/clone` `/diff` `/purge` `/count` `/top` `/grep` `/calendar` `/rename` `/replay` `/favorites` |
| **Data** | `/vault` `/vault show` `/promote` `/manifest` `/verify` `/env` `/import` `/map` `/inbox` |
| **Dev** | `/compile` `/config` `/frontier` `/open` `/alias` `/debug` `/log` `/health` `/batch` |
| **System** | `/stats` `/streak` `/version` `/model` `/who` `/me` `/theme` `/uptime` `/welcome` `/clear` `/help` `/commands` `/quit` |

### Session Commands (74)

| Section | Commands |
|---------|----------|
| **Session** | `/status` `/fields` `/undo` `/retry` `/summarize` `/time` `/history` `/chain` `/last` `/label` `/context` `/benchmark` |
| **Annotate** | `/note` `/tag` `/pin` `/flag` `/find` `/todo` `/todo done` `/rate` `/wipe` |
| **Output** | `/export` `/download` `/print` `/json` `/raw` `/copy` `/read` `/read last` `/cost` `/tokens` `/deliverable` `/template` `/redact` |
| **Navigate** | `/switch` `/clone` `/chain` `/search` `/browse` `/info` |
| **Lifecycle** | `/save` `/back` `/pause` `/close` `/reset` `/snap` `/quit` |
| **Data** | `/vault` `/promote` `/manifest` `/diff` `/merge` `/env` `/import` |
| **Dev** | `/compile` `/config` `/open` `/alias` `/cartridge` `/protocol` `/schema` `/debug` `/log` |
| **System** | `/stats` `/streak` `/version` `/model` `/who` `/me` `/theme` `/quiet` `/health` `/uptime` `/welcome` `/clear` `/help` `/commands` |

---

## Departments

Departments filter which packs appear in the deck menu. Defined in `config/departments.yaml`:

```yaml
departments:
  legal:
    name: Legal
    packs:
      - legal_intake
      - manda_negotiation
  sales:
    name: Sales
    packs:
      - lead_qualification
      - campaign_builder
```

Usage:
```
You: /dept legal        # Filter to legal packs only
You: /dept clear        # Show all packs again
You: /dept list         # Show available departments
```

Add or edit departments by modifying `config/departments.yaml`. Changes take effect immediately — no restart needed.

---

## Annotations

Tag, flag, note, pin, and rate sessions during or after use:

```
/note Met with client — ready to proceed
/tag priority, legal
/pin "Key finding: liability cap at $2M"
/flag
/rate 4
/todo Follow up with opposing counsel
/todo done 1
```

Annotations persist to vault state and are searchable via `/find` and `/favorites`.

---

## Vault

Every completed session writes a JSON record to `vault/{pack}/{user}/{date}/{session}.json`. Eight retrieval dimensions: pack, user, date, type, fields, session, manifest, content.

**Hash chain:** Each vault record includes a `prev_hash` field — the SHA-256 hash of the previous record in the same directory. First record uses `"GENESIS"`. This makes the chain tamper-evident.

**Verify integrity:**
```
You: /verify legal_intake
  Vault chain intact: legal_intake
```

**Inheritance:** New sessions can inherit fields from prior vault records:
```bash
./run.sh --pack legal_intake --session a446ea6e
```

**Browsing the vault:**
```
You: /vault                    # List all vault records
You: /vault legal_intake       # Filter by pack
You: /vault show a446ea6e      # Show full record as JSON
```

Partial session IDs work (first 8 characters).

---

## Manifest

The manifest is a curated ledger of promoted vault records. Vault = raw archive. Manifest = deliberate record.

```
You: /promote a446ea6e         # Promote a session
You: /manifest                 # View promoted records
```

Promoted records are read-only. They include a `promoted_at` timestamp.

---

## Session Lifecycle

1. Pack loads: system prompt assembled from protocol files
2. Boot screen renders (if `## BOOT SCREEN` section exists in boot.md)
3. Otherwise: LLM generates greeting from boot.md instructions
4. Exchange loop: user input → Claude response → STATE signal extraction
5. On `/close`: deliverable written to `output/`, vault record written
6. On `/save` or `/pause`: state preserved, return to deck menu (no vault write)

---

## Troubleshooting

**"ANTHROPIC_API_KEY not set"** — Add your key to `.env` or export it:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**"No pack found matching X"** — Check available packs with `/library`. Use the exact pack ID or a recognized name.

**Vault chain breaks** — A break means a record was modified or deleted after writing. Use `/verify <pack>` to identify which records are affected.

**Pack not loading** — Ensure the pack has a `manifest.json` in `protocols/packs/{pack_id}/` or `protocols/library/{category}/{pack_id}/`.
