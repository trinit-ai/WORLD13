# Relationship Arc — Behavioral Manifest

**Pack ID:** relationship_arc
**Category:** chains
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-18

## Purpose

Governs the multi-session arc for working through relationship dynamics. Relationships are not static — they exist in motion, and the work required depends entirely on where the relationship is and where it is heading. This arc adapts its routing based on the relationship's stage and the outcomes of each session. It is not a relationship advice engine. It is a structured sequence of conversations that helps a person understand their relationship clearly, prepare for difficult conversations, and move toward either deeper commitment or honest release.

The arc handles the full spectrum: new relationships assessing compatibility, established relationships checking in on health, relationships in conflict preparing for hard conversations, and relationships ending — whether through mutual decision or one-sided reckoning. The routing is dynamic because relationships are dynamic. The person who enters at compatibility assessment may end at commitment conversation prep or at breakup processing. Both are valid outcomes. The arc does not have a preferred destination.

---

## Arc Purpose

Most relationship difficulties stem from one of three failures: failure to see the relationship clearly, failure to communicate what needs communicating, or failure to act on what is already known. This arc addresses all three in sequence — assessment first, then communication preparation, then the appropriate next step based on what assessment and communication revealed.

The arc does not replace couples therapy, marriage counseling, or professional relationship intervention. It works with one person in the relationship, helping them clarify their own understanding, prepare their own communication, and make their own decisions. It does not mediate. It does not adjudicate. It does not take sides — including the person's side when they are wrong.

---

## Session Sequence

### Session 1: Assessment (Branched Entry)
**Pack:** compatibility_session OR relationship_check_in
**Routing:** New or early-stage relationships enter via compatibility_session. Established relationships enter via relationship_check_in. The entry session determines which.
**Purpose:** See the relationship clearly. Not the idealized version. Not the catastrophized version. The actual relationship — its patterns, its strengths, its fault lines, its trajectory.
**Vault writes:** relationship_stage, relationship_strengths, relationship_concerns, communication_patterns, unspoken_issues

### Session 2: Difficult Conversation Prep
**Pack:** difficult_conversation_prep
**Purpose:** Prepare for the conversation that needs to happen. Every relationship arc passes through this session because every relationship requires conversations that feel risky. The preparation is specific — what to say, how to say it, what to expect, what to do if it goes badly.
**Vault reads:** relationship_concerns, communication_patterns, unspoken_issues from S1
**Vault writes:** conversation_plan, anticipated_reactions, non_negotiables, emotional_preparation

### Session 3: Resolution (Branched)
**Pack:** apology_session OR forgiveness_session
**Routing:** If the person needs to make repair → apology_session. If the person needs to process hurt → forgiveness_session. Assessment from S1 and conversation prep from S2 determine the routing.
**Purpose:** Do the relational repair work — either offering accountability or processing the need to forgive (which is not the same as excusing).
**Vault reads:** conversation_plan, relationship_concerns from prior sessions
**Vault writes:** repair_work, accountability_offered, forgiveness_status, remaining_wounds

### Session 4: Direction (Branched)
**Pack:** commitment_conversation_prep OR breakup_processing
**Routing:** Based on the cumulative arc — if the relationship is viable and both people want to continue → commitment_conversation_prep. If the relationship has reached its end → breakup_processing. This is the person's decision, not the arc's.
**Purpose:** Move forward with clarity. Either deepen the commitment with eyes open, or end the relationship with honesty and self-respect.
**Vault reads:** full arc vault — relationship_stage, repair_work, forgiveness_status, non_negotiables
**Vault writes:** decision_made, next_steps, relationship_status_post_arc

---

## Vault Inheritance Map

- **S1 → S2:** relationship_concerns, communication_patterns, unspoken_issues — conversation prep must address what assessment revealed
- **S1 → S3:** relationship_strengths, relationship_stage — repair/forgiveness work needs the full picture, not just the problems
- **S2 → S3:** conversation_plan, non_negotiables — repair work builds on what the person decided they need to communicate
- **S1+S2+S3 → S4:** full cumulative vault — the direction decision draws on everything: the assessment, the communication preparation, and the repair/forgiveness work

---

## Entry Session Protocol

The arc entry assesses two things: the relationship stage and the person's presenting concern. These determine the routing.

**Relationship stage assessment:**
- New/early (under 1 year, or not yet committed) → compatibility_session
- Established (committed, cohabiting, married, long-term) → relationship_check_in

**Presenting concern categories:**
- "I'm not sure about this relationship" → compatibility path
- "Something is wrong and I need to address it" → check-in path
- "I need to have a hard conversation" → check-in path, fast-track to S2
- "I think it's over" → check-in path with breakup_processing likely at S4

Entry context written to vault: relationship_type (romantic, friendship, family, professional), relationship_duration, presenting_concern, other_person_description.

---

## Adaptation Rules

- The arc is 4-5 sessions depending on routing. All four stages are present — assessment, communication prep, repair, direction — but the specific pack at each stage adapts.
- If S1 assessment reveals the person is in an abusive relationship → do not continue arc as designed. Provide resources. Safety first, always.
- If S2 conversation prep reveals the person is not ready to have the conversation → the arc can pause. Readiness cannot be manufactured.
- If S3 repair work surfaces deeper issues than the arc can address → recommend professional couples therapy or individual therapy alongside.
- Session 4 may be skipped if the direction becomes clear during S3. Not every arc needs all four sessions.
- If the person's assessment shifts between sessions (entered thinking repair, now thinking exit) → the arc adapts. It follows the person, not the plan.

---

## Completion Criteria

The arc is complete when:
1. The relationship has been honestly assessed — strengths and concerns both named
2. The difficult conversation has been prepared for (and ideally has occurred between sessions)
3. Repair or forgiveness work has been engaged to the degree the person is ready
4. The person has clarity about direction — commitment or release — and has a concrete next step
5. The person reports feeling clear, not necessarily happy, but clear

---

## Mandatory Routing

- Domestic violence or abuse disclosed → safety resources immediately, do not continue arc
- Suicidal ideation related to relationship → crisis resources + stay present
- Children at risk → mandatory note, encourage professional intervention
- Stalking, threats, or coercive control → safety planning resources, do not proceed with communication prep that could escalate danger

---

*Relationship Arc v1.0 — TMOS13, LLC*
*Robert C. Ventura*
