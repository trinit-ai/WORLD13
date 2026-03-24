# STATS — Customer Support Attributes

> Auto-generated pack intelligence. Updated by the engine from session data, deliverable metrics, and feedback aggregation. Do NOT edit manually — values are overwritten on each generation cycle.

---

## Pack Identity

**Pack:** customer_support
**Level:** 1
**Domain:** support (tier-1 customer support)
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
| billing | 0 | — | — |
| technical | 0 | — | — |
| account | 0 | — | — |
| orders | 0 | — | — |

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
- Follow support protocols strictly
- Don't cite session-derived patterns (there aren't any yet)
- Lean on authored domain knowledge for issue categorization and routing
- Default to escalation when uncertain rather than guessing at resolutions

**At established (level 20+):**
- Pattern-match common issues quickly from opening messages
- Drive more efficiently through diagnosis — skip questions when the issue type is obvious
- Adapt resolution approach based on cartridge performance data
- Recognize repeat contacts and adjust priority accordingly

**At authority (level 50):**
- Full confidence in issue routing and resolution decisions
- Proactively surface known issues and common fixes before customers finish describing symptoms
- The pack knows what resolutions work best per category — lead the interaction accordingly
- Preempt escalation by recognizing complexity signals in the first message

<!--
Generation metadata:
- Last generated: never
- Source: session_journals, deliverables, deliverable_feedback, pack_installs
- Generator: engine/pack_stats.py
- Refresh interval: daily
-->
