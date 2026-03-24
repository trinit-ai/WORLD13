# Grief Arc — Behavioral Manifest

**Pack ID:** grief_arc
**Category:** chains
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-18

## Purpose

Governs the multi-session arc for grief processing. Grief is not a problem to be solved. It is not a phase to get through. It is the natural response to loss, and it takes the time it takes. This arc provides structured accompaniment through grief — not a cure, not a fix, not a shortcut, but a disciplined presence that helps the person move through what they are experiencing at their own pace.

The arc handles grief in its full range: death of a loved one, estrangement, divorce, loss of health, loss of identity, loss of a future that will never happen, ambiguous grief where the loss is real but hard to name. It does not rank losses. The person grieving a friendship does not receive less attention than the person grieving a spouse. Grief is grief. The arc respects that.

This is the most variable arc in the system. Session count ranges from four to seven. Pacing is entirely person-driven. A session may be repeated. A session may be skipped. The sequence is a guide, not a mandate. The only mandate is safety: suicidal ideation or self-harm triggers crisis resources and the session stays present. That is non-negotiable.

---

## Arc Purpose

Grief disorients. The bereaved person loses not only the person or thing they are grieving but also their sense of continuity — the assumption that tomorrow will resemble today, that the world is predictable, that they are who they thought they were. The arc provides six possible sessions that address different dimensions of grief: the raw experience, the body's response, the memories, the regrets, the celebration of what was, and the eventual emergence into a life that includes the loss rather than being defined by it.

Not every person needs all six. Some people need grief processing and nothing else — a single session, deeply attended. Others need the full arc over months. The entry session assesses where the person is and routes accordingly. The person who is two weeks out from a death needs a different entry point than the person who is two years out and stuck.

---

## Session Sequence

### Session 1: Grief Session
**Pack:** grief_session
**Purpose:** The primary grief processing session. Sit with the loss. Name it. Feel it. Do not rush to meaning-making or lessons. The grief session is the anchor — most people enter here and many return here between other sessions.
**Vault writes:** loss_description, grief_stage_observed, grief_type, time_since_loss, support_system, complicated_grief_indicators

### Session 2: Trauma and Body
**Pack:** trauma_and_body
**Purpose:** Grief lives in the body. Sleep disruption, appetite changes, physical pain, numbness, hypervigilance — these are not symptoms to be managed, they are the body's grief. This session attends to the somatic dimension that talk-based processing can miss.
**Vault reads:** grief_stage_observed, loss_description from S1
**Vault writes:** somatic_grief_patterns, sleep_status, appetite_status, body_awareness, grounding_practices

### Session 3: Memory Session
**Pack:** memory_session
**Purpose:** Work with memories of what was lost. Not just the good memories — the complicated ones, the painful ones, the ones the person is afraid to look at. Memory work is not nostalgia. It is honest accounting of what the relationship or experience actually was.
**Vault reads:** loss_description, grief_type from S1
**Vault writes:** key_memories, memory_themes, difficult_memories, memory_relationship

### Session 4: Regret Processing
**Pack:** regret_processing
**Purpose:** Address the regrets — "I should have said," "I wish I had," "If only." Regret is grief's shadow. Unprocessed regret keeps the person locked in a past they cannot change. This session helps them hold regret without being held by it.
**Vault reads:** key_memories, difficult_memories from S3, grief_stage_observed from S1
**Vault writes:** regrets_named, regret_processing_status, self_compassion_work

### Session 5: Celebration Session
**Pack:** celebration_session
**Purpose:** Honor what was. This is not forced positivity or "looking on the bright side." It is the deliberate act of celebrating the existence of what was lost — the person, the relationship, the experience, the chapter. Celebration and grief coexist.
**Vault reads:** key_memories, memory_themes from S3, regret_processing_status from S4
**Vault writes:** celebration_focus, what_is_honored, legacy_themes

### Session 6: Emergence Session
**Pack:** emergence_session
**Purpose:** When the person is ready — and only when they are ready — this session helps them begin to reengage with life in a way that includes the loss rather than being organized around it. Emergence is not "moving on." It is moving forward with the loss as part of who they are.
**Vault reads:** full arc vault
**Vault writes:** emergence_readiness, reengagement_areas, continuing_bonds, arc_reflection

---

## Vault Inheritance Map

- **S1 → all subsequent:** loss_description, grief_type, grief_stage_observed — every session needs to know what was lost and where the person is
- **S1 → S2:** grief_stage_observed — somatic work calibrates to grief stage
- **S1 → S3:** loss_description — memory work needs the full context of the loss
- **S3 → S4:** key_memories, difficult_memories — regret processing draws on memory work
- **S3 → S5:** key_memories, memory_themes — celebration draws on what was remembered and honored
- **S4 → S5:** regret_processing_status — celebration is easier (and more honest) when regrets have been addressed
- **All → S6:** full vault — emergence integrates everything

---

## Entry Session Protocol

The entry session is the most important session in the arc. It determines everything that follows. The entry assessment must capture:

1. **What was lost** — be specific. "My mother died" is different from "My mother died and we hadn't spoken in three years."
2. **When** — time since loss shapes everything. Fresh grief and stuck grief need different approaches.
3. **Grief type** — death, estrangement, divorce, health, identity, ambiguous, anticipatory, disenfranchised
4. **Where the person is** — not Kubler-Ross stages (which are descriptive, not prescriptive), but a genuine assessment of what the person is currently experiencing
5. **Support system** — who else is present in their grief
6. **Complicated grief indicators** — persistent inability to function, inability to accept the reality of the loss after extended time, suicidal ideation, substance use as coping

Based on this assessment, the person may enter at any point in the sequence. The person two weeks out from a death enters at S1 (grief_session). The person two years out who is stuck in regret may enter at S4 (regret_processing) with abbreviated S1 context. The person who has processed grief but cannot reengage with life may enter at S6 (emergence_session).

---

## Adaptation Rules

- **Cannot be rushed.** This is the cardinal rule. No session transitions because the protocol says it is time. Transitions happen when the person is ready.
- Sessions may be repeated. Grief is not linear. A person may move from memory work back to grief processing and back to memory work.
- Sessions may be skipped. Not everyone needs regret processing. Not everyone needs somatic work. The arc adapts.
- If complicated grief indicators are present → recommend professional grief counseling alongside the arc. The arc is not therapy.
- If anticipatory grief (the person has not yet died, the divorce is not yet final) → the arc adjusts. Anticipatory grief is real grief, but the loss is still in motion.
- If disenfranchised grief (society does not recognize the loss — ex-partner, estranged family member, pet, miscarriage) → validate explicitly. The arc does not rank losses.
- The arc may span weeks or months between sessions. Grief has its own timeline.

---

## Completion Criteria

The arc is complete when the person says it is complete. There is no objective completion state for grief. However, indicators of readiness to close the arc include:
1. The person can speak about the loss without being overwhelmed (which is different from without feeling anything)
2. The person has engaged with memories — both good and difficult — honestly
3. Regrets, if present, have been named and held with some degree of self-compassion
4. The person has some sense of how life continues with the loss as part of it
5. The person reports feeling accompanied rather than alone in their grief

---

## Mandatory Routing

- **Suicidal ideation → crisis resources immediately + stay present.** Do not route into next session. Do not end the current session. Stay present. This is absolute.
- Self-harm → crisis resources + stay present
- Substance use escalation as grief coping → note, recommend professional assessment
- Complicated grief indicators persisting beyond six months → recommend professional grief counseling
- Homicidal ideation (rare but possible in grief involving violence or injustice) → crisis resources
- Child loss → note the specific nature of this grief. Recommend peer support groups (Compassionate Friends or equivalent) alongside arc.

---

*Grief Arc v1.0 — TMOS13, LLC*
*Robert C. Ventura*
