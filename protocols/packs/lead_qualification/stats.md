# STATS — Lead Qualification Attributes

> Auto-generated pack intelligence. Updated by the engine from session data, deliverable metrics, and feedback aggregation. Do NOT edit manually — values are overwritten on each generation cycle.

---

## Pack Identity

**Pack:** lead_qualification
**Level:** 1
**Domain:** sales (inbound qualification)
**Confidence:** bootstrapping

---

## Session Metrics

| Metric | Value |
|--------|-------|
| **Total sessions** | 0 |
| **Sessions (30d)** | 0 |
| **Avg session depth** | — |
| **Avg turns per session** | — |
| **Completion rate** | — |
| **Return rate** | — |

---

## Cartridge Performance

| Cartridge | Sessions | Avg Depth | Completion |
|-----------|----------|-----------|------------|
| triage | 0 | — | — |
| discovery | 0 | — | — |
| product_fit | 0 | — | — |
| booking | 0 | — | — |
| training | 0 | — | — |

**Strongest cartridge:** —
**Weakest cartridge:** —

---

## Deliverables

| Metric | Value |
|--------|-------|
| **Generated** | 0 |
| **Avg rating** | — |
| **Feedback count** | 0 |
| **Type:** | — |

---

## Qualification Metrics

| Metric | Value |
|--------|-------|
| **Avg qualification score** | — |
| **Hot leads (85+)** | 0 |
| **Qualified leads (65–84)** | 0 |
| **Nurture leads (40–64)** | 0 |
| **Unqualified (<40)** | 0 |
| **Spam filtered** | 0 |

---

## Organization Rank

| Metric | Value |
|--------|-------|
| **Org rank** | — of — deployed packs |
| **Sessions vs org avg** | — |
| **Domain confidence** | bootstrapping |

---

## Level Thresholds

| Level | Sessions Required | Confidence |
|-------|-------------------|------------|
| 1 | 0 | bootstrapping |
| 5 | 50 | low |
| 10 | 200 | moderate |
| 20 | 500 | established |
| 30 | 1,000 | high |
| 40 | 2,500 | veteran |
| 50 | 5,000+ | authority |

---

## Behavioral Modifiers

> These modifiers adjust pack behavior based on level. Injected as [PACK ATTRIBUTES] in the assembler.

**At bootstrapping (level 1-4):**
- Follow BANT+ qualification framework strictly
- Don't cite session-derived patterns (there aren't any yet)
- Lean on authored domain knowledge for objection handling and scoring
- Conservative lead scoring — when unsure, score lower

**At established (level 20+):**
- Pattern-match intent signals quickly from opening messages
- Drive more efficiently through discovery — skip dimensions when answers are implied
- Adapt qualification depth by deal size and industry signals

**At authority (level 50):**
- Full confidence in scoring and routing decisions
- Proactively surface high-value discovery questions based on prospect profile
- The pack knows which signals predict conversion — weight scoring accordingly

<!--
Generation metadata:
- Last generated: never
- Source: session_journals, deliverables, deliverable_feedback, pack_installs
- Generator: engine/pack_stats.py
- Refresh interval: daily
-->
