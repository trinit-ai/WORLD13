# 13TMOS Slash Commands — Master Spec

**Status:** brainstorm / design
**Date:** 2026-03-13

---

## Session Lifecycle

| Command | What it does | Context |
|---------|-------------|---------|
| `/back` | Save and return to deck menu | session |
| `/save` | Save session state | session |
| `/pause` | Pause session (resume later) | session |
| `/close` | End session and write deliverable | session |
| `/resume <id>` | Resume a paused session | deck |
| `/quit` | Exit 13TMOS | both |
| `/undo` | Drop the last exchange (user + assistant) | session |
| `/retry` | Re-run the last assistant turn | session |
| `/clear` | Clear terminal screen, keep session alive | both |

---

## Output & Deliverables

| Command | What it does | Context |
|---------|-------------|---------|
| `/fields` | Show all captured fields and their values | session |
| `/summarize` | Plain-language summary of session so far — covered, outstanding | session |
| `/deliverable` | Generate the pack's deliverable from current data | session |
| `/export <format>` | Export transcript or deliverable — `md`, `json`, `pdf`, `txt` | session |
| `/download` | Write last deliverable to `output/` | session |
| `/print` | Dump deliverable to stdout (pipe-friendly) | session |
| `/send <email>` | Email deliverable or transcript to someone | session |
| `/redact` | Scrub PII from current session before export | session |

---

## Spaces

| Command | What it does | Context |
|---------|-------------|---------|
| `/ink` | Ephemeral chat — zero persistence, RAM only, gone on close | deck |
| `/private` | Access passphrase-protected packs | deck |
| `/builder` | Open pack authoring environment — write manifests, compile, test | deck |

---

## Discovery & Navigation

| Command | What it does | Context |
|---------|-------------|---------|
| `/library` | List all available packs (deployed + library) | deck |
| `/browse <category>` | List packs in a category | deck |
| `/search <term>` | Fuzzy search pack names and descriptions | deck |
| `/recent` | Show last 5 sessions with pack, turns, timestamp | deck |
| `/new` | Show recently added packs | deck |
| `/random` | Launch a random pack | deck |
| `/info` | Show current pack metadata — category, author, version, turns | session |
| `/switch <pack>` | Save current session and launch another pack | session |

---

## Reading & Reference

| Command | What it does | Context |
|---------|-------------|---------|
| `/read <session_id>` | Display a past session transcript | both |
| `/read <pack_id>` | Display a pack's MANIFEST.md | both |
| `/read <file>` | Display a file from output/ or vault | both |
| `/read last` | Display the last session or deliverable | both |
| `/open <target>` | Open target in system editor | both |

---

## Data & Vault

| Command | What it does | Context |
|---------|-------------|---------|
| `/vault` | Vault browser | both |
| `/vault show` | Show current session's vault data | session |
| `/vault last` | Show most recent vault write | both |
| `/vault search <term>` | Search vault records by content | both |
| `/push` | Push local vault to production | both |
| `/pull` | Pull production vault to local | both |
| `/sync` | Show bridge sync status | both |
| `/verify <pack_id>` | Verify vault chain integrity | both |
| `/promote <session_id>` | Promote vault record to manifest | both |
| `/manifest` | List promoted manifest records | both |

---

## Annotation & Organization

| Command | What it does | Context |
|---------|-------------|---------|
| `/pin <message>` | Pin a key finding — persists to vault as highlight | session |
| `/note <text>` | Quick margin note attached to current session | session |
| `/flag` | Flag current session for review | session |
| `/tag <label>` | Tag session — client name, project, case number | session |
| `/find <tag>` | Find sessions by tag | both |
| `/diff` | Show what changed since last save | session |
| `/compare <session> <session>` | Side-by-side diff of two session deliverables | deck |

---

## Session Reuse & Chaining

| Command | What it does | Context |
|---------|-------------|---------|
| `/template <pack>` | Save current field values as reusable template | session |
| `/clone <session>` | Start new session pre-filled from a previous one | deck |
| `/chain <pack> → <pack>` | Run packs in sequence — output feeds forward (web potential) | deck |

---

## Time, Schedule & Tasks

| Command | What it does | Context |
|---------|-------------|---------|
| `/time` | Current time, session duration, today's total usage | both |
| `/schedule` | View scheduled sessions or reminders | both |
| `/schedule add "<desc>" <when>` | Schedule a future task | both |
| `/schedule list` | Show upcoming | both |
| `/schedule clear <id>` | Remove a scheduled item | both |
| `/todo` | View task list | both |
| `/todo add "<desc>"` | Add task | both |
| `/todo done <id>` | Mark complete | both |
| `/todo list` | Show all with status | both |
| `/todo clear` | Remove completed tasks | both |
| `/todo auto` | Auto-suggest todos from deliverable next_steps / recommendations | session |

---

## User Profile & Preferences

| Command | What it does | Context |
|---------|-------------|---------|
| `/me` | Show identity — name, org, role, tier | both |
| `/me set <key> <value>` | Update identity or preference | both |
| `/me prefs` | Show all preferences | both |
| `/me reset` | Reset to defaults | both |
| `/who` | Quick identity glance | both |

### Settable preferences:
- `name` — display name
- `email` — default for `/send`
- `model` — default LLM model
- `editor` — default editor for `/open`
- `export_format` — default export format (md/json/pdf/txt)
- `department` — default department filter
- `quiet` — suppress chrome (on/off)
- `theme` — terminal color theme
- `lang` — session language preference

---

## System & Diagnostics

| Command | What it does | Context |
|---------|-------------|---------|
| `/help` | Show available commands | both |
| `/version` | Show 13TMOS version | both |
| `/status` | System health — db size, vault count, pending syncs, uptime | both |
| `/model` | Show or switch active model | both |
| `/cost` | Token usage and estimated cost for current session | session |
| `/stats` | Usage stats — sessions, packs used, categories, total turns | both |
| `/config` | Show current config | both |
| `/log` | Tail session log | both |

---

## Dev & Administration

| Command | What it does | Context |
|---------|-------------|---------|
| `/compile` | Recompile current pack | session |
| `/compile --all` | Recompile all library packs | deck |
| `/compile --category <cat>` | Recompile a category | deck |
| `/watcher` | Vault watcher controls | both |
| `/bridge` | Vault bridge controls | both |
| `/frontier` | Library exploration / frontier tools | both |
| `/dept <name>` | Enter department scope | deck |
| `/dept list` | List departments | deck |
| `/dept clear` | Clear department filter | deck |
| `/reset-passphrase` | Reset pack passphrase | both |

---

## Power User & Customization

| Command | What it does | Context |
|---------|-------------|---------|
| `/shortcut <name> <command>` | Create personal alias | both |
| `/json` | Toggle JSON output mode (structured, pipe-friendly) | both |
| `/quiet` | Toggle minimal output | both |
| `/batch <file>` | Feed a file of inputs (non-interactive mode) | both |
| `/theme <name>` | Switch terminal color theme | both |
| `/lang <code>` | Set session language | both |
| `/streak` | Days active, sessions this week | deck |
| `/random` | Launch a random pack | deck |

---

## Audio (Future)

| Command | What it does | Context |
|---------|-------------|---------|
| `/voice` | Toggle voice input | session |
| `/listen` | TTS the last response | session |

---

## Alerts & Automation (Future)

| Command | What it does | Context |
|---------|-------------|---------|
| `/alert <condition>` | Set watcher alert — e.g. "score below 3 on any dimension" | both |
| `/cron <schedule> <command>` | Schedule recurring commands | deck |

---

## Summary

| Category | Count |
|----------|-------|
| Session Lifecycle | 9 |
| Output & Deliverables | 8 |
| Spaces | 3 |
| Discovery & Navigation | 8 |
| Reading & Reference | 5 |
| Data & Vault | 10 |
| Annotation & Organization | 7 |
| Session Reuse & Chaining | 3 |
| Time, Schedule & Tasks | 10 |
| User Profile & Preferences | 4 |
| System & Diagnostics | 8 |
| Dev & Administration | 9 |
| Power User & Customization | 8 |
| Audio (Future) | 2 |
| Alerts & Automation (Future) | 2 |
| **Total** | **96** |
