# Clinical Decision Simulator — Changelog

## v1.1.0 (February 2026)

### Priority 1: SISS — Fourth Wall Enforcement
- **master.md:** Added complete "SIMULATION INTEGRITY — FOURTH WALL" section with explicit DON'T/DO rules for every failure mode: playing both sides, narrating user actions, coaching during simulation, revealing diagnostic reasoning, advancing without input, hinting at hidden state, summarizing user reasoning, offering menu-style choices
- **master.md:** Added "The Waiting Rule" — after patient answers or environment reports, response ends. No prompting, no suggesting.
- **encounter.md:** Added "FOURTH WALL — ACTIVE" header with reminder of non-negotiable rules
- **diagnosis.md:** Added SISS enforcement throughout — system delivers results without interpretation, never comments on test ordering appropriateness during simulation
- **treatment.md:** Added SISS enforcement — patient reacts to treatment decisions but never suggests them

### Priority 2: EXIS — User Agency / Protagonist Preservation
- **master.md:** Added complete "USER AGENCY (EXIS)" section defining what the user decides vs. what the system decides
- **master.md:** Added explicit rule that cartridge transitions are user-driven, not system-driven
- **encounter.md:** Transition points rewritten to emphasize user initiation — DON'T/DO examples added
- **diagnosis.md:** Transition to treatment rewritten — system waits for user to initiate treatment
- **treatment.md:** Disposition section reinforced — system never suggests disposition, consequences unfold without warning if user makes a dangerous choice

### Priority 3: Multi-PERSONA Separation
- **master.md:** Added complete "PERSONA SEPARATION" section defining three distinct PERSONAs:
  - Patient PERSONA: first person, natural speech, governed by behavior_rules, never teaches
  - Clinical Environment PERSONA: third person, clinical register, reports findings without interpretation
  - Preceptor PERSONA: debrief only, evidence-based, full hidden state access
- **master.md:** Added "Bleed Prevention" rules — meta-questions during simulation stay in Patient/Environment persona
- **encounter.md:** Explicit persona assignment for each interaction type (patient speech vs. exam findings)
- **debrief.md:** Explicit "PERSONA TRANSITION" section — clean handoff from simulation to Preceptor

### Priority 4: GATE Definitions
- **briefing.md:** Added "Transition to Encounter" section with SISS activation — fourth wall goes up when simulation begins
- **encounter.md:** Transition points explicitly user-driven with DON'T/DO examples
- **diagnosis.md:** Transition to treatment explicitly user-driven
- **treatment.md:** Transition to debrief — the ONE place a transition prompt is appropriate (simulation ending)

### Priority 5: Manifest Completeness
- **manifest.json:** Version bumped to 1.1.0
- **manifest.json:** Added missing toolkit fields: `tagline`, `philosophy`, `assembly_mode`
- **manifest.json:** Cartridge definitions updated: `protocol` → `file`, added `number` field per toolkit schema

### Priority 6: Formatting Cleanup
- **master.md:** Formatting rules reinforced — cards rare during active simulation, plain text default
- **menu.md:** Card interiors cleaned to use · separator pattern per style guide, bullet lists removed from cards
- **menu.md:** Help section converted from bullet list to inline conversational text
- **debrief.md:** Cards retained (appropriate as endpoint summaries), interiors cleaned per style guide
- **boot.md:** Added "What is this" edge case — direct explanation without defensiveness
- **roadmap.md:** Updated current state section to reflect v1.1 additions

### Files Modified
| File | Changes |
|------|---------|
| manifest.json | Version bump, added tagline/philosophy/assembly_mode, fixed cartridge schema |
| master.md | SISS section, EXIS section, PERSONA separation, bleed prevention, voice kill list expanded, state continuity rules |
| boot.md | Added "what is this" edge case, minor cleanup |
| menu.md | Card interior formatting, help section rewritten as conversational text |
| briefing.md | Transition-to-encounter SISS activation, state signals added |
| encounter.md | SISS enforcement throughout, persona separation for patient vs. environment, DON'T/DO examples for every interaction type, emotional texture guidance, transition rules |
| diagnosis.md | SISS enforcement, results delivery without interpretation, scoring criteria clarified as debrief-only evaluation, transition rules |
| treatment.md | SISS enforcement, patient-as-reactor rules, disposition scoring, procedure consent, transition rules |
| debrief.md | Preceptor PERSONA activation, persona transition, counterfactual analysis, card formatting cleanup |
| roadmap.md | Updated to reflect v1.1 additions |
