# CC FORMATTING STANDARDIZATION

> Claude Code prompt for formatting cleanup passes across all packs.
> TMOS13, LLC

---

## Context

We're stripping complex interactive formatting from all LLM-facing protocol files so pack
conversations can be stress-tested as pure conversation quality without formatting noise.

---

## What to Do

### 1. Add formatting discipline block to every pack's master.md

For each pack in `protocols/packs/*/master.md` (except the reference pack), find the
existing formatting rules section and **replace it entirely** with:

```markdown
## FORMATTING RULES

Default output is plain conversational text. Write like a person talking, not a dashboard.

### Active: :::card
Use :::card ONLY for structured summaries at natural endpoints:
- End-of-flow summary (case details collected, candidate profile, deal terms)
- Confirming collected information back to the user
- Displaying a menu or overview when explicitly asked

Never use :::card for greetings, transitions, mid-conversation responses, or any response
under 3 lines. If the content works as a paragraph, write it as a paragraph.

### Disabled (do not output)
- :::actions — No button blocks. Navigation happens through conversation.
- :::stats — No metric displays. Scores and stats are internal only.
- :::form — No form blocks. Contact collection is conversational.
- cmd: links — No command links anywhere, including inside cards.
- [Button Text](cmd:anything) — Do not output these in any format.

### Inline markdown
- Bold (**text**) is fine for emphasis in cards or key terms. Don't bold everything.
- Bullet lists only inside :::card blocks for structured data. Never in conversational responses.
- No ## headers in responses. Headers are for protocol files, not output.
- Emoji sparingly — only if the pack's personality calls for it.

### The rule
If a response could work as 2-3 sentences of plain text, it should be 2-3 sentences of plain text.
```

### 2. Strip :::actions blocks
Remove all `:::actions ... :::` blocks. Replace orphaned intro lines with natural prompts.

### 3. Strip :::stats blocks
Remove from response templates. Keep references inside code fences or documentation comments.

### 4. Strip :::form blocks
Remove from response templates.

### 5. Fix boot-sequence-override problem
In boot.md files, add at the top:

```markdown
## CRITICAL RULE — First Message Handling
If the user's FIRST MESSAGE describes their situation (mentions anything substantive),
DO NOT run the boot greeting. Respond directly to what they said.
The boot sequence is ONLY for generic openers like "hi" or "hello".
```

### 6. Verification

```bash
grep -rn ":::actions" protocols/packs/ --include="*.md" | grep -v reference_pack
grep -rn ":::stats" protocols/packs/ --include="*.md" | grep -v reference_pack
grep -rn ":::form" protocols/packs/ --include="*.md"
```

All should return zero results.

---

## What NOT to Do
- Do not modify `manifest.json` files
- Do not remove `:::card` — cards work
- Do not remove STATE signals (`[STATE:...]`)
- Do not modify engine code
