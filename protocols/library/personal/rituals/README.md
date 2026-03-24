# Daily Rituals — v1.1.0

TMOS13 Experience Pack · `protocols/packs/rituals/`

## What's in this bundle

| File | Purpose |
|------|---------|
| `manifest.json` | Pack config — 9 cartridges, nav patterns, state schema, features, privacy |
| `master.md` | Identity, voice, mood routing, formatting, streaks, cross-cartridge memory |
| `boot.md` | Boot sequence — first visit, returning with/without streak |
| `menu.md` | Ritual menu — Daily / Readings / Tools grouping |
| `mood.md` | Mood Check-in — hub cartridge with trend tracking and smart routing |
| `gratitude.md` | Gratitude Journal — theme extraction, streak mechanics |
| `affirmations.md` | Daily Affirmations — mood-responsive, context-aware |
| `horoscope.md` | Daily Horoscope — sign-based personalized readings |
| `tarot.md` | Tarot — 78-card deck, 3 spread types, card tracking |
| `iching.md` | I-Ching — 64 hexagrams, changing lines, collection tracking |
| `cbt.md` | Thought Challenger — 5-step CBT flow, distortion detection, pattern tracking |
| `inspiration.md` | Daily Inspiration — 10 world traditions, favorites system |
| `breathwork.md` | Breathwork — 5 techniques with timing, session tracking |

## v1.1.0 Changes

- Version bump from 1.0.0
- Formatting compliance: all files follow current TMOS13 formatting standard (:::card only, no :::actions/:::stats/:::form/cmd: links)
- Voice calibration section added to master.md (kill list, response length guidance)
- Domain boundaries section added to master.md (scope, edge cases, crisis handling)
- Boot override rule present (substantive first messages skip boot greeting)
- State tracking blocks present in all cartridge files
- Cross-cartridge connection documentation in all relevant cartridges
- Clean extraction — all files ready for engine deployment

## Pack Type

**Experience** — Fluid with guardrails (25/75 on the Fluidity/Playbook Matrix). Personality IS the product, but streaks, state, and progression need deterministic tracking underneath.

## Deploy

Copy this directory to `protocols/packs/rituals/` and set `TMOS13_PACK=rituals`.

---

TMOS13, LLC | Robert C. Ventura | Jersey City, NJ
Copyright © 2026 TMOS13, LLC. All Rights Reserved.
