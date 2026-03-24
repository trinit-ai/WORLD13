# TMOS13 Base Pack Template — Public-Facing

> Template for public-facing conversational experiences. Not deployable on its own — fork this, customize it, ship it.

## What This Is

The structural DNA for any TMOS13 pack that faces external users: prospects, clients, customers, patients, applicants, students — anyone arriving at a business website or app expecting a conversational experience.

This base pack assumes the conversation is **both the experience AND the data capture**. Every session produces structured intelligence: scored, summarized, routable.

## Files

| File | Purpose |
|------|---------|
| `manifest.template.json` | Universal manifest structure with all required fields, sensible defaults, and documentation comments |
| `master.md` | Universal protocol rules: voice patterns, state management, contact collection, scoring, formatting, boundaries |
| `boot.md` | Boot sequence template: greeting, orientation, transparency line, returning-session handling |
| `menu.md` | Orientation screen template: available paths, current status, session actions |

## How to Use

1. Copy this directory as `protocols/packs/{your_pack_id}/`
2. Rename `manifest.template.json` → `manifest.json`
3. Fill in your cartridges, commands, state schema, theme
4. Write your cartridge `.md` files following the patterns in `master.md`
5. Customize `boot.md` and `menu.md` for your domain
6. Set `TMOS13_PACK={your_pack_id}` and run

## Design Principles

- **Conversation over numbered menus** — Navigation surfaces contextually through conversation, not memorized commands (cmd: links currently disabled)
- **Ambient transparency over consent walls** — Users know what's happening without friction
- **Conversational collection over form fields** — Contact info gathered naturally, not demanded
- **Session intelligence by default** — Every session produces a scored, summarized, actionable output
- **The conversation IS the product** — Not a wrapper around a chatbot, an interactive environment

## Data Tiers

Set `privacy.data_tier` in your manifest:

| Tier | Use Case | Disclosure Level |
|------|----------|-----------------|
| `contact_form` | Standard business inquiry | Light — single transparency line |
| `sensitive_intake` | Legal, medical, financial | Strong — explicit about data sharing |
| `internal_workflow` | Employee-facing tools | Minimal — covered by employment terms |
| `anonymous` | No contact collection | None — no CRM routing |

## Other Base Packs (Future)

This is the **public-facing** base pack. Other base packs planned:

- `_base_workflow` — Internal task/todo/process management
- `_base_training` — Learning, assessment, certification
- `_base_creative` — Gaming, narrative, interactive fiction
- `_base_marketplace` — Third-party pack creator template
