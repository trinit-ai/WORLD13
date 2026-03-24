# protocols/shared — Index

> Shared protocol library for 13TMOS.
> All documents in this directory are available to all packs.
> Last updated: 2026-03-12

---

## Documents

| ID | File | Purpose | Load Condition |
|----|------|---------|----------------|
| `pack_project_instructions` | PACK_PROJECT_INSTRUCTIONS.md | Sandbox operating modes, engine contract, deliverables pipeline | Pack development sessions |
| `pack_development_toolkit` | PACK_DEVELOPMENT_TOOLKIT.md | Pack language ontology, authoring guide, assembly modes, manifest schema, integrity layers | Pack authoring, pack_builder sessions |
| `pack_refinement_protocol` | PACK_REFINEMENT_PROTOCOL.md | Eight diagnostic layers, refinement loop, anti-patterns, testing methodology | Pack refinement, dev mode sessions |
| `narrative_architecture` | NARRATIVE_ARCHITECTURE.md | Three-act structure, character, pacing, tension/resolution | All packs (core narrative behavior) |
| `formatting_style_guide` | FORMATTING_STYLE_GUIDE.md | Active/disabled directives, card patterns, conversational text rules | All packs (output formatting) |
| `cc_formatting_standardization` | CC_FORMATTING_STANDARDIZATION.md | Claude Code executable prompt for formatting cleanup passes | CC execution only |

---

## Loading Rules

### Always load (all packs)
- `NARRATIVE_ARCHITECTURE.md` — three-act structure and pacing govern every session
- `FORMATTING_STYLE_GUIDE.md` — output formatting rules apply universally

### Load for pack development sessions
- `PACK_PROJECT_INSTRUCTIONS.md` — sandbox operating instructions
- `PACK_DEVELOPMENT_TOOLKIT.md` — full ontology and authoring guide
- `PACK_REFINEMENT_PROTOCOL.md` — diagnostic framework for testing and fixing packs

### Load on demand
- `CC_FORMATTING_STANDARDIZATION.md` — CC execution prompt only, not injected into sessions

---

## Reference

All documents authored by Robert C. Ventura, TMOS13, LLC.
Engine version: 13TMOS v0.1.0
