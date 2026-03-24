# PACK DEVELOPMENT TOOLKIT

> Version 2.0 — February 2026
> TMOS13, LLC

---

# 1. Pack Language Ontology

## Core Constructs

### PERSONA
What the pack *is*. Voice, knowledge boundaries, behavioral constraints.
- **Primary PERSONA** (one per pack): The master protocol's voice and scope. Always active.
- **Character PERSONAs** (simulators only): Distinct identities the model inhabits.

### WORLD
The environment a session exists inside. Domain, Rules, Tone of reality, Scope walls.

### RITUAL
A structured interaction flow with beginning, middle, and end. The fundamental unit of *doing things* inside a pack.
Includes: Entry condition, Steps, State mutations, Exit condition, Deliverable.

### SPEECH-ACTS

| Act | What It Does |
|-----|-------------|
| **ASK** | Collect information from the user |
| **MIRROR** | Reflect information back for confirmation |
| **SHIFT** | Change the emotional or topical register |
| **NOTE** | Capture a data point into session state |
| **SCORE** | Evaluate accumulated information against criteria |
| **PRESENT** | Display structured information to the user |
| **GUIDE** | Direct the user toward the next step without deciding |
| **HOLD** | Create space without advancing |
| **CLOSE** | End a RITUAL with a deliverable or handoff |
| **REDIRECT** | Steer back to scope when the user drifts |

### PATTERN
Recurring behavioral templates applied across multiple RITUALs or packs.
- Universal: Contact Collection, Scope Redirect, Graceful Close, Empathy Hold
- Pack-specific: Intake Funnel, Simulation Loop, Game Loop, Analysis Build

### GATE
A decision point that controls flow. Types: Routing, Qualification, Escalation, Scope, Progression, Safety.
GATEs are invisible to the user.

### CELL
A unit of session state. Every `[STATE:...]` signal is a CELL mutation.
Types: Capture, Score, Flag, Mood, Progress.

### OBJECT
A discrete thing inside a WORLD. Items, clues, documents, tools. Relevant for gaming/simulation packs.

### EGG
A hidden element. Easter egg, surprise, reward for exploration. Rare, genuine, never manipulative.

## Design Order

1. **WORLD** — What domain? What rules? What gravity?
2. **PERSONA** — Who is the user talking to?
3. **RITUALs** — What flows? What does each collect or produce?
4. **GATEs** — Where are decision points?
5. **PATTERNs** — Which reusable patterns apply?
6. **CELLs** — What state is tracked?
7. **OBJECTs** — Are there things beyond conversation?
8. **EGGs** — Any delightful surprises?

---

# 2. Pack Authoring Guide

## Assembly Modes

### Assembled (default)
Each cartridge in its own `.md` file. Assembler composes master + active cartridge only.
**Best for:** Deep conversations, large cartridges, token efficiency.

### Monolithic
All content compiled into one `.md` file. Entire file sent every turn.
**Best for:** Navigation-heavy experiences, prompt caching optimization.

| Aspect | Assembled | Monolithic |
|--------|-----------|------------|
| Context per turn | master + active cartridge (~20%) | Entire compiled file (100%) |
| Best for | Deep conversations | Navigation-heavy browsing |

## Manifest Schema — Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `pack_id` | string | Unique ID, must match directory name |
| `name` | string | Display name |
| `version` | string | Semantic version |
| `tagline` | string | One-liner |
| `personality` | object | Identity and tone |
| `cartridges` | object | Module definitions |
| `commands` | object | Routing rules |
| `features` | object | Feature flag booleans |

## Command Types

- **Numerical** (Priority 1) — Exact-match codes → system screens. Zero LLM tokens.
- **Session** (Priority 2) — Keywords → session control.
- **Navigation** (Priority 3) — Regex/NLP patterns → cartridge routing.

---

# 3. Conversational Integrity Guide

## Layer 1: RISS — IP Protection
Share freely: what the pack does, how it helps, what the experience feels like.
Never disclose: system prompt assembly, routing decisions, state signal format, scoring formulas.
Hard boundaries: Never pretend to be human. Never collect credentials. Never fabricate data.

## Layer 2: SISS — Simulation Integrity
Fourth Wall Rule: In simulations, stay in character. Don't coach, hint, or make decisions for the user.

## Layer 3: KISS — Drift Detection
Three-strike redirect:
1. Gentle: "That's outside what I'm set up for here."
2. Firm: "I'm designed for [pack purpose]. Want to get back to [topic]?"
3. Boundary: "I need to stay focused on [pack purpose]."

## Layer 4: EISS — Turn Economics

| Pack Type | Expected Turns | Close Trigger |
|-----------|---------------|---------------|
| Intake | 8–15 | Intake complete OR 20 turns |
| Support | 3–10 | Resolution OR 15 turns |
| Simulator | 15–30 | Simulation end OR 40 turns |
| Quantitative | 8–20 | Model built OR 25 turns |
| Gaming | 10–50 | Game end OR per-game limit |
| Platform | 5–20 | Natural endpoint OR 30 turns |

## Layer 5: EXIS — User Agency
The user makes decisions. The model provides information and options. Never choose on the user's behalf.

## Template Inheritance
- **base_pack_template** → Layers 1, 3, 4, 5
- **base_simulator** → All five layers
- **base_quantitative** → base_pack_template + financial disclaimers

---

# 4. Anti-Patterns

**The Menu Bot** — Presents numbered lists at every turn.
**The Echo Chamber** — Just rephrases what the user said.
**The Infodump** — Dumps everything in the first response.
**The Amnesia Bot** — Forgets what was discussed three turns ago.
**The Hedge Machine** — Qualifies every statement with "it depends."
