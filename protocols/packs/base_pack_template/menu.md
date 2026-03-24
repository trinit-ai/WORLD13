# MENU / ORIENTATION SCREEN — Base Template
# Loaded when visitor says "menu", "help", "options", or equivalent.
# Pack-specific menu.txt files replace this — this is the structural pattern.

---

## MENU BEHAVIOR

The menu is an orientation screen, not a numbered list. It shows what's available, where the visitor currently is, and what actions they can take — all through natural language and cmd: links.

### Menu Structure

1. **Context line** — Where they are in the experience (if mid-session)
2. **Available paths** — Cartridges described by what they DO, not what they're called, with cmd: links
3. **Session actions** — Transcript, status, reset — offered conversationally (:::actions currently disabled)
4. **Current state summary** — If meaningful state exists, show it in a :::card (optional)

### Menu Pattern

**Fresh session (no state):**
```
Here's what I can help with:

**[Cartridge 1 Label]** — [One sentence: what the visitor gets from this path]

**[Cartridge 2 Label]** — [One sentence: what the visitor gets from this path]

**[Cartridge 3 Label]** — [One sentence: what the visitor gets from this path]

Which sounds right? You can also download a transcript or start over anytime.
```

**Mid-session (state exists):**
```
:::card
**Current session:** [What they've been doing]
**Progress:** [Where they are in the flow]
**Collected so far:** [Key data points if relevant]
:::

You can continue where you left off or explore other options:

**[Continue current path]** — [What's next in their current flow]

**[Other Cartridge]** — [What this offers]

**[Another Cartridge]** — [What this offers]

What would you like to do? You can also check your status, download a transcript, or start over.
```

### Menu Rules

- Describe cartridges by OUTCOME, not by name. "Describe your situation and get a preliminary assessment" not "Intake Module."
- 2-4 cartridge options maximum. If the pack has more, surface the most relevant based on current state.
- Always include transcript download as a session action.
- If contact info has been collected, don't re-surface paths that would re-collect it.
- The menu is a REORIENTATION, not a restart. Acknowledge where they are.
- Keep descriptions to one sentence per cartridge. This is a signpost, not documentation.

### Status Screen (separate from menu)

When visitor says "status" or "progress" or "where am I":

```
:::card
**Session:** [Session ID short hash]
**Started:** [Relative time — "15 minutes ago"]
**Current area:** [Active cartridge description]
:::

[KEY_STATE_SUMMARY — 2-3 bullet points of what's been accomplished or collected, including turn count and any scores]

Want to continue, see the full menu, or download a transcript?
```

### Transcript Screen

When visitor says "transcript" or "download":

```
Your conversation transcript is ready.

:::card
**Session:** [Session ID]
**Duration:** [Turn count] messages
**Summary:** [One-line session summary]
:::

Would you like to download the full transcript or continue the conversation?
```

The actual download is handled by the engine/frontend — your job is to surface the action and provide the summary context.
