# M&A Negotiation Simulator — v1.1.0
## TMOS13 Pack Bundle

> War-game mergers, acquisitions, and corporate transactions. Roleplay counterparties, stress-test deal structures, explore negotiation branches.

---

## Pack Files

| File | Purpose |
|------|---------|
| `manifest.json` | Pack configuration — cartridges, commands, routing, state schema, settings, theme |
| `master.md` | Core identity, voice, dual cognitive mode, deal taxonomy, persona archetypes, scoring, formatting rules |
| `boot.md` | Boot sequence — greeting, pre-built scenarios, returning session, edge cases |
| `menu.md` | Navigation — fresh session, mid-deal status, detailed dashboard, help |
| `briefing.md` | Deal Briefing cartridge — builds the simulation from user's situation |
| `negotiation.md` | Deal Negotiation cartridge — core simulation, counterparty roleplay, branching |
| `due_diligence.md` | Due Diligence & Discovery cartridge — information warfare gameplay |
| `board_room.md` | Board & Stakeholder Management cartridge — internal politics, regulatory strategy |
| `debrief.md` | Deal Debrief cartridge — post-simulation scoring, analysis, recommendations |
| `roadmap.md` | Development roadmap — v1.5 through v4.0 vision |

---

## v1.1 Changes from v1.0

- **Version bump** to 1.1.0 across manifest and all protocol files
- **Assembly mode** explicitly declared in manifest (`assembled`)
- **Formatting compliance** — all files aligned to current TMOS13 formatting standard (plain conversational text default, :::card only at natural endpoints, no :::actions/:::stats/:::form/cmd: links)
- **Card interior formatting** refined per Formatting Style Guide (bold labels with inline values, spaced middle dot separators, no bullets for key-value pairs)
- **Menu help section** converted from bullet list to conversational text
- **Dual Cognitive Mode** section added to master.md — explicit separation of persona vs. evaluator modes
- **Strategic Grade Scale** added to scoring section
- **Scope & Boundaries** section formalized in master.md with redirect pattern
- **Language Rules** expanded with specific DON'T/DO patterns
- **Boot sequence** confirmed with critical rule for substantive first messages
- **Edge cases** added to briefing.md for minimal info, mid-briefing changes, wall-of-text inputs
- **Debrief scoring breakdown** added as Step 2 with per-dimension assessment
- **Protocol file headers** standardized with version, pack ID, engine
- **Toolkit alignment** — constructs (PERSONA, WORLD, RITUAL, GATE, CELL) inform protocol design

---

## Pack Type

**Category:** Simulator
**Fluidity/Playbook:** Fluid (30/70) — persona must feel real, user's choices drive the flow, scoring happens silently
**Assembly Mode:** Assembled — modular per-cartridge files

---

## How to Deploy

1. Place all files in `protocols/packs/manda_negotiation/`
2. Set `TMOS13_PACK=manda_negotiation`
3. Engine reads manifest.json, loads master.md always, loads active cartridge when routed

## How to Test in Claude Projects

1. Upload all pack files as project knowledge
2. Set project instructions per PACK_PROJECT_INSTRUCTIONS.md
3. Default to Live Mode — Claude IS the pack
4. Say "dev mode" to switch to development partner mode

---

TMOS13, LLC | Robert C. Ventura | Jersey City, NJ
Copyright © 2026 TMOS13, LLC. All Rights Reserved.
