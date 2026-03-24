# PACK REFINEMENT PROTOCOL

> TMOS13, LLC

---

## What This Document Is

TMOS13 packs are behavioral fine-tuners. This document is the methodology for making
those packs better. Goal: every pack should feel like talking to the best person you've
ever worked with in that domain.

---

## The Fluidity/Playbook Matrix

| Pack Type | Examples | Lean Toward |
|-----------|----------|-------------|
| CRM / Vertical | Legal Intake, Customer Support | Playbook (70/30) |
| Simulator | Clinical Decision, M&A Negotiation | Fluid (30/70) |
| Quantitative | Real Estate, Business Case | Split (50/50) |
| Experience | Daily Rituals, Gaming | Fluid with guardrails (25/75) |
| Platform | TMOS13 Site, Pack Builder | Fluid (20/80) |

---

## The Eight Diagnostic Layers

### Layer 1: Voice & Personality
**Symptom:** "It sounds wrong. Too corporate. Too perky. Too generic."
**File:** `master` — Voice Calibration / Language Rules
**Fix:** Add negative examples. "Never say X" is more effective than "always say Y."

Common issues:
- Therapy-speak ("I hear you", "let's explore that", "that's valid")
- Corporate cushioning ("At this time we are unable to...")
- Forced enthusiasm ("Great question!", "Absolutely!")
- Breaking character to explain what it is

### Layer 2: Routing & Cartridge Selection
**Symptom:** "I asked about X but it stayed in Y."
**File:** `manifest.json` nav_patterns + triage cartridge
**Fix:** Add routing signals to the triage cartridge with example phrases.

### Layer 3: Domain Knowledge
**Symptom:** "It said something factually wrong."
**File:** The specific cartridge file
**Fix:** Add the missing knowledge as a specific case with the right answer.

### Layer 4: Flow & Pacing
**Symptom:** "It asked 3 questions at once."
**Fix:**
```
Ask ONE question per turn. Never stack.
DON'T: "What's your budget? And what's your timeline?"
DO: "What's the budget range you're working with?"
```

### Layer 5: Formatting
**Symptom:** "It used a :::card when it should have just talked."
**Current standard:** Only `:::card` is active. All other directives are disabled.

### Layer 6: State & Memory
**Symptom:** "It forgot what I told it 3 turns ago."
**Fix:** Add carry-forward rules:
```
If order_id was collected in triage, DO NOT ask again.
Reference it: "Looking into order #{{order_id}} now."
```

### Layer 7: Edge Cases & Boundaries
**Symptom:** "I said something weird and it completely fell apart."
**Fix:** Add the specific edge case with the right response. One at a time.

Every pack needs boundary handling:
```
DON'T: "I'm not able to provide legal advice. I'm just an intake tool."
DO: "Based on what you've described, this sounds like it could involve premises liability.
     Let me capture the details so the right person can review this."
```

### Layer 8: Deliverables & Transcript Quality
**Symptom:** "The case brief is missing key information."
**Principle:** Deliverable quality is a lagging indicator. Problem is almost always upstream.

---

## The Refinement Loop

### Step 1: Capture the Bug
```
INPUT: [your exact input]
GOT: [what the pack actually said]
WANTED: [what it should have done]
LAYER: [1-8]
FILE: [which protocol file]
```

### Step 2: Identify the Layer

| Symptom | Layer |
|---------|-------|
| It sounds wrong | 1: Voice |
| It went to the wrong place | 2: Routing |
| It said something factually wrong | 3: Domain |
| The timing/pacing was off | 4: Flow |
| The visual treatment was wrong | 5: Formatting |
| It forgot something | 6: State |
| It fell apart at the edges | 7: Edge Cases |
| The deliverable was wrong | 8: Deliverables |

### Step 3: Write the Fix
```
DON'T: [exact bad behavior you saw]
DO: [what it should have done instead, with example output]
```

Rules: Be specific. Use the actual bad output. Fix one thing at a time.

---

## Common Anti-Patterns

### The Boot Override
User's first message describes their situation but the pack runs generic boot greeting.
**Fix:** Add to boot.md: "If the user's first message contains substantive content, skip the boot greeting."

### The Form Disguised as a Conversation
Asks question after question in rigid sequence, ignoring what the user volunteers.
**Fix:** Add to master: "Parse what the user has already shared before asking for it."

### The Overformatted Response
Every response has a :::card, or the pack outputs :::actions blocks.
**Fix:** Strip :::actions, :::stats, and cmd: links from all cartridge files.

---

## Testing Methodology

| Test | What It Checks |
|------|---------------|
| First Impression | Boot greeting, orientation clarity |
| Happy Path | Intended flow, cooperative user |
| The Curveball | Off-script, unexpected input |
| Domain Edge | Domain knowledge at the boundary |
| Emotional Range | Angry, confused, chatty, terse |
| "Tell Me About Yourself" | Identity guard issues |
| Persistence | Quality after 15+ turns |
| Deliverable Output | End-to-end output quality |

---

## Quick Reference: The Eight Layers

| # | Layer | Symptom | File | Fix Pattern |
|---|-------|---------|------|-------------|
| 1 | Voice | Sounds wrong | master | Add to kill list |
| 2 | Routing | Wrong cartridge | manifest + triage | Add routing signals |
| 3 | Domain | Factually wrong | cartridge | Add specific case |
| 4 | Flow | Bad pacing | master + cartridge | Add turn-count guidance |
| 5 | Formatting | Wrong/broken directives | master + cartridge | Enforce simplified standard |
| 6 | State | Forgot context | master + cartridge | Add carry-forward rules |
| 7 | Edge Cases | Fell apart | master + cartridge | Add specific edge + right response |
| 8 | Deliverables | Output wrong | manifest + master + cartridge | Trace upstream |
