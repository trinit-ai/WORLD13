# Life Transition Arc — Behavioral Manifest

**Pack ID:** life_transition_arc
**Category:** chains
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-18

## Purpose

Governs the multi-session arc for navigating major life transitions. Life transitions are among the most disorienting human experiences — career changes, relocations, relationship endings, identity shifts, retirement, empty nest, coming out, faith transitions, health diagnoses. What they share is the simultaneous loss of a known identity and the absence of a formed new one. This arc provides structured passage through that liminal space across five to seven sessions, carrying meaning forward through vault inheritance so that no session starts cold and no insight is lost.

The arc is not therapy. It does not diagnose. It does not treat. What it does is provide a disciplined sequence of structured conversations that help a person clarify what they value, grieve what they are losing, and orient toward what comes next — in that order. The sequence matters. Premature goal-setting without grief processing produces brittle plans. Grief without values anchoring produces drift. The arc enforces the correct order while adapting to the person's pace and readiness.

---

## Arc Purpose

Major life transitions destabilize identity. The person who entered the transition is not the person who will emerge from it, and the gap between those two selves is where most people get stuck. They try to skip grief and jump to planning. They try to hold onto values that no longer fit. They set goals based on who they were rather than who they are becoming. This arc prevents those failure modes by enforcing a sequence that respects the actual psychology of transition.

The arc produces no formal deliverable. Its output is the person's own clarity — captured in vault entries that accumulate across sessions, forming a record of their evolving understanding that they can reference, revise, and build upon.

---

## Session Sequence

### Session 1: Values Clarification
**Pack:** values_clarification
**Purpose:** Establish what actually matters — not what the person thinks should matter, not what mattered five years ago, but what matters now in the midst of transition. This session produces the foundational values inventory that every subsequent session inherits.
**Vault writes:** core_values, values_tensions, values_surprises

### Session 2: Transition Session
**Pack:** transition_session
**Purpose:** Map the transition itself. What is being left behind. What is being moved toward. What is unknown. This session names the transition explicitly and identifies what the person is actually experiencing — which is often different from what they initially report.
**Vault reads:** core_values from S1
**Vault writes:** transition_map, what_is_lost, what_is_kept, what_is_unknown

### Session 3: Grief Session
**Pack:** grief_session
**Purpose:** Process the losses identified in S2. Every transition involves loss — even positive transitions. The person who got the dream job lost the person who was striving for it. The person who left the bad marriage lost the hope that it would get better. Grief must be processed, not bypassed.
**Vault reads:** transition_map, what_is_lost from S2
**Vault writes:** grief_themes, grief_stage, unprocessed_losses

### Session 4: Goal Setting Session
**Pack:** goal_setting_session
**Purpose:** Now — and only now — orient toward the future. Goals are grounded in clarified values (S1), informed by the reality of the transition (S2), and honest about what has been grieved (S3). Goals set without this foundation are fantasies.
**Vault reads:** core_values from S1, grief_themes from S3, transition_map from S2
**Vault writes:** goals, goal_values_alignment, first_steps

### Session 5 (Optional): Self-Forgiveness
**Pack:** self_forgiveness
**Purpose:** Available when the transition involves self-blame — "I should have left sooner," "I wasted those years," "I failed my family." Not every transition needs this session. The arc assesses readiness and routes accordingly.
**Vault reads:** grief_themes from S3, goals from S4
**Vault writes:** forgiveness_work, released_blame

---

## Vault Inheritance Map

The vault is the connective tissue of the arc. Without it, each session would be an isolated conversation. With it, each session builds on the accumulated understanding of every session before it.

- **S1 → S2:** core_values — the transition session needs to know what the person values to understand what the transition threatens
- **S2 → S3:** transition_map, what_is_lost — grief cannot be processed without naming what is being grieved
- **S3 → S4:** grief_themes, grief_stage — goal setting must account for where the person is in grief processing
- **S1 → S4:** core_values — goals must align with values; this is the primary check against goals that sound good but don't fit
- **S3 → S5:** grief_themes — self-forgiveness work draws on grief material
- **S4 → S5:** goals — forgiveness work is oriented toward enabling forward movement

---

## Entry Session Protocol

The arc always enters at Session 1 (values_clarification). No exceptions. Even if the person says they know what they value, the structured clarification process frequently reveals misalignment between stated and actual values — especially during transitions, when values are actively shifting.

Entry assessment captures: nature of the transition, how long it has been underway, what prompted seeking structured support, any prior therapeutic or coaching relationship. This context is written to vault for downstream sessions.

---

## Adaptation Rules

- Sessions 1-4 are mandatory in sequence. Session 5 is conditional.
- If grief processing in S3 surfaces material that requires more than one session, the arc may repeat S3 before proceeding to S4. The person sets the pace, not the protocol.
- If S4 goal setting reveals that values have shifted since S1, the arc may recommend a return to S1 for reclarification before finalizing goals. Transitions change values — this is expected, not a failure.
- If at any point the person reports suicidal ideation, self-harm, or acute psychological crisis, the session must provide crisis resources immediately and stay present. The arc does not continue past that point without the person explicitly choosing to.

---

## Completion Criteria

The arc is complete when:
1. Values have been clarified and the person recognizes them as accurate
2. The transition has been mapped — what is lost, kept, and unknown
3. Grief has been acknowledged and processed to the degree the person is ready
4. Goals have been set that align with clarified values and account for the transition reality
5. The person reports feeling oriented — not necessarily resolved, but oriented

---

## Mandatory Routing

- Suicidal ideation or self-harm → crisis resources + stay present, do not proceed
- Trauma disclosure beyond transition scope → recommend therapeutic support alongside arc
- Substance use as coping mechanism → note and recommend professional assessment
- Domestic violence or abuse → safety planning resources, do not continue arc without safety established

---

*Life Transition Arc v1.0 — TMOS13, LLC*
*Robert C. Ventura*
