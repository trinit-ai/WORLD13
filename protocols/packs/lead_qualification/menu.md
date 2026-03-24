# MENU — LEAD QUALIFICATION

---

## Public Menu (No Auth)

When `menu` is triggered by an unauthenticated visitor:

"Here's what I can help with:"

:::card
**How can I help?**

**Learn about [Product]** — What it does, how it works, who it's for

**See if it's a fit** — Tell me about your situation and I'll give you an honest assessment

**Talk to the team** — Book a demo or connect with someone directly

**Get pricing** — Understand plans and what makes sense for your needs
:::

Then follow with: "What sounds most useful?"

---

## Authenticated Menu (Internal User)

When `menu` is triggered by an authenticated internal user:

"What mode do you want to work in?"

:::card
**Qualification Engine**

**Live Mode** — Handle inbound prospect conversations. Qualify leads, route to AEs, produce scored summaries.

**Training Mode** 🔒 — Practice discovery calls with AI-simulated prospects. Get scored on technique, receive coaching feedback. Available scenarios by difficulty level.
:::

---

## Mid-Conversation Menu (Public)

When `menu` is triggered during an active qualification:

:::card
**Current Conversation**

**Company:** {lead.company || "Not yet shared"}
**Interest:** {lead.use_cases[0] || "Exploring"}
**Phase:** {qualification_phase_label}
:::

Then follow with: "Want to keep going, or is there something else I can help with?"

---

## Status Screen

When `status` is triggered:

:::card
**Conversation Progress**

**Your needs:** {needs_status}
**Product fit:** {fit_status}
**Logistics:** {logistics_status}
**Next steps:** {nextsteps_status}
:::

If discovery is strong:
"I've got a good picture of what you're looking for. Ready to connect with the team?"

If discovery is early:
"I'd love to learn a bit more so I can point you to the right person. What's the main problem you're trying to solve?"

---

## Transcript Screen

When `transcript` is triggered:

:::card
**Conversation Summary**

Your conversation about **{lead.use_cases[0] || "[Product]"}** is available for download. Includes what we discussed, your requirements, and recommended next steps.
:::

---

## Training Menu (Auth-Gated)

When `menu` is triggered inside training mode:

:::card
**Training Mode** 🔒

**Current Session:** {training.scenario || "No active scenario"}
**Difficulty:** {training.difficulty || "Not set"}
**Score:** {training.rep_score || "—"}/100
:::

Then follow with: "Want to start a new scenario, review your last session, or pick a different difficulty?"
