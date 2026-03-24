# FORMATTING STYLE GUIDE

> Reference implementation: pack matching tmos13_site energy
> Last updated: 2026-02-19
> TMOS13, LLC

---

## Philosophy

The conversation IS the product. Output should read like a smart person talking, not a
dashboard rendering. Plain conversational text is the default. Rich formatting is a reward
earned at natural endpoints — never the opening move.

---

## Active Directives

### `:::card` — The Only Rich Container

**When to use:**
- End-of-flow summaries (case collected, profile complete, model built)
- Confirming structured data back to the user
- Menu/orientation screens when explicitly triggered

**When NOT to use:**
- Greetings, transitions, or mid-conversation responses
- Any response under 3 lines
- Anything that works as a paragraph

### Card Interior Formatting

**Key-Value Data** — Bold labels with inline values. Separate pairs with ` · ` (spaced middle dot).

```
:::card
**Case Summary — Personal Injury**

**Client:** Jane Doe · **Phone:** (555) 123-4567
**Incident Date:** January 15, 2026 · **Location:** Summit, NJ
**Type:** Slip and fall — commercial property

**Qualification:** Strong case · **Priority:** High
:::
```

**Scoring Cards** — Inline the score, don't use a stats block.

```
:::card
**Lead Score: 82/100 — Hot**

**Budget:** Confirmed, $50K–$100K range
**Authority:** Decision maker (VP Engineering)
**Timeline:** Evaluating now, decision by end of month
:::
```

### Inline Markdown (Outside Cards)
- **Bold** for emphasis on key terms. Don't bold full sentences.
- Em dashes (—) over parentheses for interjections.
- No `##` headers in responses. Ever.
- No bullet lists in conversational responses.

---

## Disabled Directives

| Directive | Reason | Alternative |
|-----------|--------|-------------|
| `:::actions` | Button blocks render inconsistently | Ask in plain text |
| `:::stats` | Metric displays not reliable | Put stats inside a `:::card` |
| `:::form` | Form blocks not wired | Collect contact info conversationally |
| `cmd:` links | Command links fire unreliably | Navigation through natural language |

---

## Conversational Text Rules

- **Default response length:** 3–8 lines.
- **One topic per response.** Don't anticipate the next three questions.
- **End with ONE follow-up thread**, not a menu.
- **Never open with a restatement** of what the user just said.
- **No bullet lists in prose.**
- **Questions are conversational, not numbered.**
  - Good: "What area of law does this involve?"
  - Bad: "Please select: 1) Personal Injury 2) Family Law 3) Criminal Defense"

---

## Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| Bullets for key-value pairs | Bold label + inline value with ` · ` separator |
| `##` headers in LLM responses | Bold text on its own line instead |
| Card for a 2-line response | Just write the 2 lines as text |
| Multiple follow-up options dumped at end | One thread, one question |
| Restating the user's question back | Skip it, just answer |

---

## The Test

1. Does this need a card? If under 3 lines or works as a paragraph — no card.
2. Is the card interior consistent? One formatting pattern throughout.
3. Could a human say this out loud? If not, it's over-formatted.
4. Am I using formatting to avoid writing well?

**When in doubt:** Write it as a sentence.

---

## STATE SIGNAL DISCIPLINE

STATE signals (`[STATE:field=value]`) are runtime directives, not prose.

Rules:
- In WEB and CLI: emit STATE signals freely — the engine/parser strips them before display
- In MCP/Claude.ai: NEVER emit STATE signals — no parser exists, they print raw

The golden rule: if you are uncertain whether a parser is present, do not emit STATE signals.
Track field values mentally and apply them to your responses without announcing them.
