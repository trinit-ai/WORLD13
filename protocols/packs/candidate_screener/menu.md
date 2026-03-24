# MENU — CANDIDATE SCREENER

## Fresh Session (No Active Screening)

When `menu` is triggered before screening begins:

"Here's what I can help with today:"

:::card
**Available Screening Tracks**

**Engineering & Technical** — Software, data, IT, and technical specialist roles. Includes technical discussion and problem-solving assessment.

**Sales & Business Development** — Sales, account management, BDR/SDR, and partnerships. Covers pipeline experience, deal cycles, and metrics.

**Customer-Facing Roles** — Support, service, retail, and client-facing positions. Focuses on communication, problem resolution, and empathy.

**Management & Leadership** — Manager through executive-level roles. Explores leadership style, team building, and strategic thinking.

**General Screening** — Not sure which track? Start here and I'll route you to the right one based on our conversation.
:::

"Just let me know which area fits best, or describe your background and I'll help figure out the right track."

---

## Mid-Screening

When `menu` is triggered during an active screening:

:::card
**Screening in Progress**

**Role:** {candidate.role_applied || "Not yet specified"} · **Track:** {session.role_category || "General"}
**Phase:** {screening_phase_label}
**Progress:** {completed_count} of {total_sections} sections covered
:::

"We're in the middle of your screening. You can continue where we left off, check your status, download a transcript so far, or start over with a different role. What would you like to do?"

---

## Status Screen

When `status` is triggered:

:::card
**Your Screening Status**

**Contact Information:** {contact_status}
**Background & Experience:** {background_status}
**Motivation & Fit:** {motivation_status}
**Role-Specific Assessment:** {rolespecific_status}
**Logistics & Availability:** {logistics_status}
:::

"We've covered {brief_summary_of_collected_info}. Still to discuss: {remaining_topics}. Ready to continue?"

### Status Values
- ✅ Complete
- 🔄 In Progress
- ⬜ Not Started

---

## Transcript Screen

When `transcript` is triggered:

If screening is complete:

:::card
**Interview Summary Ready**

Your screening for **{candidate.role_applied}** is complete. The summary has been shared with the hiring team.
:::

If screening is in progress:

:::card
**Screening In Progress**

You can download a snapshot of the conversation so far. The final summary with full evaluation hasn't been generated yet.
:::

"Is there anything else you'd like to add before I package this up, or are you good to go?"

---

## Help / Commands

When the candidate seems confused about navigation:

"You can say 'menu' anytime to see your options, 'status' to check where we are, 'transcript' to download a copy of our conversation, or 'start over' to reset and begin fresh. Otherwise, just answer naturally — I'll guide us through the process."
