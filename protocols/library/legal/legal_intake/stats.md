# STATS — Legal Intake Attributes

> Auto-generated pack intelligence. Updated by the engine from session data, deliverable metrics, and feedback aggregation. Do NOT edit manually — values are overwritten on each generation cycle.

---

## Pack Identity

**Pack:** legal_intake
**Level:** 1
**Domain:** legal (client intake)
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
| case_evaluation | 0 | — | — |
| personal_injury | 0 | — | — |
| family_law | 0 | — | — |
| criminal_defense | 0 | — | — |
| estate_planning | 0 | — | — |

**Strongest cartridge:** —
**Weakest cartridge:** —

---

## Deliverables

| Metric | Value |
|--------|-------|
| **Generated** | 0 |
| **Avg rating** | — |
| **Feedback count** | 0 |
| **Type:** | case_brief |

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
- Follow intake protocol strictly
- Don't cite session-derived patterns (there aren't any yet)
- Lean on authored domain knowledge for practice area routing

**At established (level 20+):**
- Pattern-match case types quickly from opening statements
- Drive more efficiently through qualification — skip questions when answers are implied
- Adapt pacing based on cartridge performance data

**At authority (level 50):**
- Full confidence in routing and qualification decisions
- Proactively surface follow-up questions based on case type patterns
- The pack knows what attorneys need — lead the intake accordingly

<!--
Generation metadata:
- Last generated: never
- Source: session_journals, deliverables, deliverable_feedback, pack_installs
- Generator: engine/pack_stats.py
- Refresh interval: daily
-->
