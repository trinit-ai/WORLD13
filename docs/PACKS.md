# 13TMOS Packs

A pack is a behavioral contract. Not a prompt. Not a template.
It governs what the AI does, how it speaks, what it captures,
when it stops, and what it delivers.

---

## What a Pack Is

A pack defines a complete session experience: identity, voice, routing
rules, turn limits, field capture, deliverable format, and domain boundaries.
The protocol engine executes the pack. The channel delivers it. The vault
remembers it.

Any pack runs on any channel. The pack never changes for the channel.

---

## Pack File Structure

Active packs live in `protocols/packs/{pack_id}/` with up to four files:

| File | Purpose | Required |
|------|---------|----------|
| `master.md` | Primary session protocol — acts, routing, voice, boundaries | Authoritative when present |
| `MANIFEST.md` | Governing behavioral specification | Fallback if no master.md |
| `header.yaml` | Pack metadata — name, version, category, description | For stubs and discovery |
| `manifest.json` | Machine-readable spec — fields, routing graph, features | For engine configuration |

Not every pack has all four files. `master.md` is loaded as the system prompt
when present. `MANIFEST.md` serves as fallback. `manifest.json` provides
structured metadata for the engine.

---

## Deployed vs Library

**Deployed packs** (28): Full manifests in `protocols/packs/`. Runnable via
any channel or the terminal console. These take priority during resolution.

**Library packs** (379): Authored packs in `protocols/library/{category}/`.
Full manifests with `manifest.json`. Visible to the engine and launchable
from the CLI or any channel.

**Total visible** (381): Deduplicated across both directories. Deployed packs
take priority when a pack ID exists in both locations.

---

## Current Coverage

```
Total:      381 packs (deduplicated)
Deployed:   28
Library:    379 (with manifest.json)
Categories: 24
```

---

## Deployed Packs

| Pack ID | Name | Category |
|---------|------|----------|
| base_quantitative | Base Quantitative | quantitative |
| base_simulator | Base Simulator | simulator |
| business_case | Business Case Builder | quantitative |
| campaign_builder | Campaign Builder | marketing |
| candidate_screener | Candidate Screener | verticals |
| classroom | Classroom | education |
| clinical_decision | Patient Intake | scenarios |
| customer_support | Customer Support | verticals |
| deck | Deck | platform |
| desk | Desk | platform |
| enlightened_duck | The Enlightened Duck | games |
| feed_portal | Feed Portal | platform |
| gaming | Game Room | — |
| guest | Guest | — |
| ink | Disappearing Ink | platform |
| lead_qualification | Lead Qualification | verticals |
| legal_intake | Legal Intake | verticals |
| manda_negotiation | Strategy Room | scenarios |
| onboarding | Welcome | system |
| operator | Operator | platform |
| pack_builder | Pack Builder | _meta |
| pack_finder | Pack Finder | — |
| real_estate | Real Estate Advisor | quantitative |
| rituals | Daily Rituals | experiences |
| robert_c_ventura | Robert C. Ventura | — |
| rpg_dungeon | RPG Dungeon | games |
| vault_audit | Vault Audit | _meta |
| welcome | Welcome | platform |

Plus `base_pack_template` — a template directory (not a runnable pack).

---

## Library Category Map

| Category | Packs |
|----------|-------|
| agriculture | 15 |
| architecture | 15 |
| consulting | 19 |
| creative | 16 |
| criminal_justice | 15 |
| diplomatic | 15 |
| education | 15 |
| engineering | 17 |
| finance | 16 |
| government | 15 |
| hospitality | 17 |
| hr | 15 |
| insurance | 15 |
| legal | 15 |
| media | 16 |
| medical | 16 |
| mental_health | 15 |
| personal | 16 |
| real_estate | 16 |
| research | 17 |
| sales | 17 |
| simulations | 17 |
| social_work | 15 |
| sports | 15 |
| **Total** | **380** |

---

## How to Author a Pack

Run the Pack Builder Pack:

```bash
./run.sh --pack pack_builder
```

The Pack Builder conducts a structured session to define your pack's identity,
voice, routing rules, turn limits, field capture, deliverable format, and
domain boundaries. It generates all four pack files.

Alternatively, create the files manually in `protocols/packs/{pack_id}/`.

---

## Pack Distribution

```
protocols/
├── packs/          Deployed packs — full manifests, runnable (priority)
├── library/        Library packs — organized by category
│   ├── agriculture/
│   ├── architecture/
│   ├── consulting/
│   ├── ...         24 category directories
│   └── sports/
├── shared/         Shared protocols — branding, company_profile (always),
│                   NARRATIVE_ARCHITECTURE, FORMATTING_STYLE_GUIDE (always),
│                   plus toolkit/refinement/instructions (pack_builder only)
└── private/        Private/proprietary packs (.gitignore'd)
```

---

## The Frontier Endpoint

`GET /frontier` returns the live coverage map:

```json
{
  "total_packs": 381,
  "deployed": 28,
  "library": 379,
  "categories": 24,
  "by_category": {
    "legal": {"count": 15},
    "medical": {"count": 16},
    "sales": {"count": 17}
  }
}
```

Also available as MCP tool `frontier` from Claude Desktop.

---

## Private Packs

`protocols/private/` is in `.gitignore`. Use this directory for personal
or proprietary packs that should never be committed to the repository.
The engine searches `protocols/packs/` first, then `protocols/library/`.
Private packs are not indexed by the MCP server.
