# CARTRIDGE TEMPLATE — Base Pattern
# Copy this structure for each cartridge .md file.
# Replace all [BRACKETS] with pack/cartridge specific content.

---

## PURPOSE

[One paragraph: What this cartridge does. What the visitor experiences. What the business gets from it.]

---

## CONVERSATION FLOW

### Entry Point
When this cartridge is loaded (via cmd: link, navigation match, or direct command):

[Describe the opening move. What does the first response in this cartridge look like? What question or orientation does the visitor get?]

### Phase 1: [PHASE_NAME]
**Goal:** [What this phase accomplishes]
**Approach:** [How to guide the conversation through this phase]
**Collects:** [What information is gathered]
**Transitions to Phase 2 when:** [Trigger condition]

Key questions for this phase:
- [Question 1 — natural, conversational phrasing]
- [Question 2]
- [Question 3]

State signals:
```
[STATE:domain_field.subfield=value]
[STATE:qualification.score adjustment reason]
```

### Phase 2: [PHASE_NAME]
**Goal:** [...]
**Approach:** [...]
**Collects:** [...]
**Transitions to Phase 3 when:** [...]

[Same structure as Phase 1]

### Phase 3: [PHASE_NAME — often summary/handoff]
**Goal:** [Wrap up, present findings, hand off to business]
**Approach:** [Summarize what was collected, confirm accuracy, present next steps]

Summary presentation pattern:
```
:::card
**[Key Field 1]:** [Value]
**[Key Field 2]:** [Value]
**[Key Field 3]:** [Value]
:::

[Present next steps conversationally: "From here, you can [primary next step], [secondary option], or download a transcript."]
```

---

## STATE MANAGEMENT

### State Fields This Cartridge Owns
```
[STATE:domain.field1=value]
[STATE:domain.field2=value]
```

### State Fields This Cartridge Reads (from other cartridges or universal)
- `contact.*` — Use collected contact info, don't re-ask
- `qualification.*` — Build on existing scores
- `session.*` — Awareness of where in the session we are

### Qualification Scoring in This Cartridge
| Factor | Weight | Signal |
|--------|--------|--------|
| [Factor 1] | +XX | [What indicates this] |
| [Factor 2] | +XX | [What indicates this] |
| [Factor 3] | -XX | [What decreases score] |

---

## FORMATTING RULES

### When to Use Rich Formatting
- **:::card** — [When to present structured info back to visitor]
- **:::stats** — (currently disabled) [When in this cartridge's flow stats make sense]
- **:::actions** — (currently disabled) [Decision points specific to this cartridge]
- **cmd: links** — (currently disabled) [Light navigation moments]

### Response Length
- [Phase-appropriate length guidance: e.g., "Phase 1 questions should be 2-3 sentences. Phase 3 summary can be longer with formatting."]

---

## BOUNDARIES

### This Cartridge Does
- [Specific capability 1]
- [Specific capability 2]
- [Specific capability 3]

### This Cartridge Does NOT
- [Out of scope item 1]
- [Out of scope item 2]
- [Where to redirect instead]

### Escalation Triggers
- [Condition that needs human handoff]
- [Condition that exceeds this cartridge's scope]
- [Emotional/safety concern handling]

---

## CROSS-CARTRIDGE NAVIGATION

### Leads To
- [Cartridge X] — When [condition]. Surface conversationally.
- [Cartridge Y] — When [condition]. Surface conversationally.

### Comes From
- [Cartridge Z] — Visitor arrives here after [context]. Acknowledge their prior state.
- [Boot/Menu] — Fresh entry. Full orientation needed.

---

## EXAMPLES

### Good Response (Phase 1)
```
[Example of a well-written response for this phase, showing tone, question style, and natural data collection]
```

### Good Response (Phase 3 Summary)
```
[Example of a summary with :::card showing the full handoff pattern, followed by conversational next steps]
```

### Bad Response (What NOT to Do)
```
[Counter-example showing common mistakes: too formal, too many questions, form-like collection, missing state signals]
```
