# 13TMOS Slash Commands — Implementation Audit

**Date:** 2026-03-16
**Source:** `docs/slash-commands-spec.md` (96 commands) vs `engine/console.py`

---

## 1. Session Lifecycle (9 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/back` | MISSING | Not recognized. Spec: "save and return to deck menu" — same as `/save`. |
| `/save` | IMPLEMENTED | Deck mode only. Returns `{"action": "save"}` to deck loop. |
| `/pause` | IMPLEMENTED | Deck mode only. Returns `{"action": "pause"}`. Prints resume hint. |
| `/close` | IMPLEMENTED | Deck mode only. Triggers session-complete (vault, deliverable, post-session menu). |
| `/resume <id>` | MISSING | `--session` CLI flag inherits vault but does not resume conversation state. |
| `/quit` | IMPLEMENTED | Both paths. Prompts to save if turns > 0 in deck mode. |
| `/undo` | MISSING | Not recognized. Falls through to LLM. |
| `/retry` | MISSING | Not recognized. Falls through to LLM. |
| `/clear` | MISSING | Not recognized. No terminal clear. |

---

## 2. Output & Deliverables (8 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/fields` | MISSING | `fields` dict exists in session but no command to display it. |
| `/summarize` | MISSING | Falls through to LLM. |
| `/deliverable` | MISSING | Falls through to LLM. |
| `/export <format>` | MISSING | Session-complete writes JSON + MD automatically but no on-demand export. |
| `/download` | MISSING | Falls through to LLM. |
| `/print` | MISSING | Falls through to LLM. |
| `/send <email>` | MISSING | Falls through to LLM. |
| `/redact` | MISSING | Falls through to LLM. |

---

## 3. Spaces (3 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/ink` | MISSING | No ephemeral/zero-persistence mode. |
| `/private` | PARTIAL | Auth infrastructure works but no browsing/listing command. User must know pack_id. |
| `/builder` | MISSING | `pack_builder` pack exists but no `/builder` shortcut. |

---

## 4. Discovery & Navigation (8 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/library` | IMPLEMENTED | Lists deployed + library packs by category. Aliased: `/list`, `library`, `packs`. |
| `/browse <category>` | MISSING | `/library` shows categories but no filter command. |
| `/search <term>` | MISSING | No fuzzy search. `resolve_pack_from_input` does partial match for launch only. |
| `/recent` | MISSING | `/history` exists but `/recent` is not aliased to it. |
| `/new` | MISSING | No "recently added packs" view. |
| `/random` | MISSING | No random pack launcher. |
| `/info` | MISSING | `/status` shows pack name but not full metadata. |
| `/switch <pack>` | MISSING | `launch` field-signal exists but not user-invocable. |

---

## 5. Reading & Reference (5 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/read <session_id>` | MISSING | `/vault show <id>` exists but no full transcript display. |
| `/read <pack_id>` | MISSING | No manifest/protocol reader. |
| `/read <file>` | MISSING | No file reader. |
| `/read last` | MISSING | No "last deliverable" reader. |
| `/open <target>` | MISSING | No system editor launch. |

---

## 6. Data & Vault (10 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/vault` | IMPLEMENTED | Both paths. Lists recent 20 records. |
| `/vault show <id>` | IMPLEMENTED | Full record detail including fields, summary, hash chain. |
| `/vault last` | MISSING | No "most recent vault write" shortcut. |
| `/vault search <term>` | MISSING | No content search. `_vault_find` does ID prefix match only. |
| `/push` | MISSING | `/bridge push` exists but no bare `/push` alias. |
| `/pull` | MISSING | `/bridge pull` exists but no bare `/pull` alias. |
| `/sync` | MISSING | `/bridge status` exists but no bare `/sync` alias. |
| `/verify <pack_id>` | IMPLEMENTED | Both paths. Verifies vault hash chain integrity. |
| `/promote <session_id>` | IMPLEMENTED | Both paths. Calls `promote_record()`. |
| `/manifest` | IMPLEMENTED | Both paths. Lists promoted manifest records. |

---

## 7. Annotation & Organization (7 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/pin <message>` | MISSING | Falls through to LLM. |
| `/note <text>` | MISSING | Falls through to LLM. |
| `/flag` | MISSING | Falls through to LLM. |
| `/tag <label>` | MISSING | Falls through to LLM. |
| `/find <tag>` | MISSING | Falls through to LLM/pack resolution. |
| `/diff` | MISSING | Falls through to LLM. |
| `/compare <s> <s>` | MISSING | Falls through to LLM/pack resolution. |

---

## 8. Session Reuse & Chaining (3 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/template <pack>` | MISSING | Falls through to LLM. |
| `/clone <session>` | MISSING | `--session` CLI flag does vault inheritance but no `/clone`. |
| `/chain <pack> → <pack>` | MISSING | Web routing exists at session-complete but no interactive `/chain`. |

---

## 9. Time, Schedule & Tasks (10 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/time` | MISSING | |
| `/schedule` | MISSING | |
| `/schedule add` | MISSING | |
| `/schedule list` | MISSING | |
| `/schedule clear` | MISSING | |
| `/todo` | MISSING | |
| `/todo add` | MISSING | |
| `/todo done` | MISSING | |
| `/todo list` | MISSING | |
| `/todo clear` | MISSING | |

---

## 10. User Profile & Preferences (5 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/me` | MISSING | `load_identity()` exists but no `/me` command. |
| `/me set` | MISSING | No write path to identity.json. |
| `/me prefs` | MISSING | No preferences system. |
| `/me reset` | MISSING | |
| `/who` | MISSING | |

---

## 11. System & Diagnostics (8 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/help` | IMPLEMENTED | Both paths. |
| `/version` | MISSING | `get_version()` exists but no command. Shown in boot header. |
| `/status` | PARTIAL | Session only. Shows pack/session/turn/fields/vault/model. Missing system-level stats. Not in deck. |
| `/model` | MISSING | Model shown in `/status` but no switch command. |
| `/cost` | MISSING | No token tracking in console. |
| `/stats` | MISSING | No usage stats aggregation. |
| `/config` | MISSING | |
| `/log` | MISSING | |

---

## 12. Dev & Administration (9 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/compile` | MISSING | Compilation done via separate CLI tools. |
| `/compile --all` | MISSING | |
| `/compile --category` | MISSING | |
| `/watcher` | IMPLEMENTED | Session only. Subcommands: start, stop, rules, simulate. |
| `/bridge` | IMPLEMENTED | Session only. Subcommands: status, diff, push, pull. |
| `/frontier` | IMPLEMENTED | Both paths. Subcommands: (overview), stub, develop. |
| `/dept <name>` | IMPLEMENTED | Deck only. |
| `/dept list` | IMPLEMENTED | Deck only. |
| `/dept clear` | IMPLEMENTED | Deck only. |
| `/reset-passphrase` | IMPLEMENTED | Session only. |

---

## 13. Power User & Customization (8 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/shortcut` | MISSING | No alias system. |
| `/json` | MISSING | No JSON output toggle. |
| `/quiet` | MISSING | No quiet mode. |
| `/batch <file>` | MISSING | No batch input. |
| `/theme <name>` | MISSING | `NO_COLOR` env var exists but no theme system. |
| `/lang <code>` | MISSING | |
| `/streak` | MISSING | |
| `/random` | MISSING | No random pack. |

---

## 14. Audio — Future (2 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/voice` | MISSING | Future. |
| `/listen` | MISSING | Future. |

---

## 15. Alerts & Automation — Future (2 commands)

| Command | Status | Notes |
|---------|--------|-------|
| `/alert` | MISSING | Future. |
| `/cron` | MISSING | Future. |

---

## Summary

| Status | Count | % |
|--------|------:|--:|
| IMPLEMENTED | 21 | 22% |
| PARTIAL | 2 | 2% |
| STUBBED | 0 | 0% |
| MISSING | 73 | 76% |
| **Total** | **96** | |

### Extra commands in console.py NOT in spec

- `/menu` — session status + options (deck mode)
- `/history` — recent vault sessions (deck)
- `/vault fields <id>` — show captured fields
- `NAV_ALIASES` — bare word navigation (library, vault, etc.)
- Numbered selection (1-5) for featured packs

---

## Demo-Critical Path

| Step | Status |
|------|--------|
| Boot | WORKS |
| Deck menu with featured packs | WORKS |
| Type number or pack name → session | WORKS |
| 5 turns of conversation | WORKS |
| `/close` → deliverable saves | WORKS |
| Post-session menu (1/2/3) | WORKS |
| Return to menu | WORKS |
| Second pack → `/close` | WORKS |

**The demo path is fully functional.** All gaps are ancillary commands.

---

## Quick Wins (< 1 hour each, high demo value)

| Command | Effort | Approach |
|---------|--------|----------|
| `/clear` | 10 min | `print('\033[2J\033[H')`, add to both loops |
| `/back` | 5 min | Alias to `/save` in session loop |
| `/version` | 10 min | `print(f"13TMOS v{get_version()}")` in both loops |
| `/fields` | 20 min | Print live `fields` dict from session state |
| `/info` | 20 min | Load manifest, print name/version/category/description |
| `/me` / `/who` | 20 min | Print `load_identity()` result |
| `/recent` | 5 min | Alias to existing `_print_history()` |
| `/push` / `/pull` / `/sync` | 15 min | Aliases to bridge subcommands |
| `/random` | 15 min | `random.choice(list_packs())` then launch |
| `/cost` | 30 min | Track `response.usage` per turn, accumulate, display |
| `/model` | 20 min | Show current; `/model <name>` reassigns variable |
| `/builder` | 5 min | Alias to `pack_builder` in deck |
| `/private` | 30 min | List packs in PRIVATE_DIR, prompt for selection |

**~13 commands in ~3.5 hours**

---

## Larger Gaps (> 1 hour, defer post-demo)

| Feature | Commands | Effort |
|---------|----------|--------|
| Undo/Retry | `/undo`, `/retry` | 2-3h |
| Export system | `/export`, `/download`, `/print`, `/send` | 4-6h |
| Read system | `/read` (5 variants), `/open` | 3-4h |
| Annotation | `/pin`, `/note`, `/flag`, `/tag`, `/find`, `/diff`, `/compare` | 6-8h |
| Session reuse | `/template`, `/clone`, `/chain` | 4-5h |
| Task/Schedule | `/todo` (5), `/schedule` (4), `/time` | 6-8h |
| User prefs | `/me set`, `/me prefs`, `/me reset` | 2-3h |
| Search/Browse | `/search`, `/browse`, `/new` | 2-3h |
| Compile | `/compile` (3 variants) | 2h |
| Ink mode | `/ink` | 2-3h |
| Power user | `/shortcut`, `/json`, `/quiet`, `/batch`, `/theme`, `/lang`, `/streak` | 6-8h |
| Audio | `/voice`, `/listen` | 8h+ |
| Alerts | `/alert`, `/cron` | 4h+ |

---

## Architecture Notes

1. **Session commands are NOT available in deck, and vice versa.** `/watcher`, `/bridge`, `/reset-passphrase` are session-only. `/dept`, `/history`, numbered selection are deck-only. `/vault`, `/promote`, `/manifest`, `/verify`, `/frontier`, `/help` are in both.

2. **`DECK_COMMANDS` and `SESSION_COMMANDS` are display-only** — they feed `/help` but do not drive dispatch. Dispatch is hardcoded if/elif chains. Adding a command requires both the handler AND updating the help list.

3. **Unrecognized commands in session become LLM turns.** `/fields`, `/note`, etc. silently consume a turn. Consider adding an "unknown command" catch for `/`-prefixed input before sending to model.

4. **Unrecognized commands in deck try pack resolution.** `/browse legal` would try to find a pack named "browse legal" and fail. Less harmful but still confusing.
