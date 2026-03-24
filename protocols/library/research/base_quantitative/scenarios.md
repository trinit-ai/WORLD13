# SCENARIO ANALYSIS CARTRIDGE — QUANTITATIVE ANALYSIS

## Purpose

Stress-test the model. Vary assumptions, compare outcomes, and identify which variables matter most. The goal isn't to predict the future — it's to understand the range of possible outcomes and what determines where you land.

## Scenario Framework

### Standard Three-Case Model

**Base Case** — Most likely scenario. Current assumptions held constant.

**Bull Case** — Optimistic but plausible. Each assumption shifted favorably with justification:
"Bull case assumes {{favorable assumption}} because {{reasoning — not just 'things go well' but a specific scenario like 'rates drop if Fed pivots'}}."

**Bear Case** — Pessimistic but plausible. Each assumption shifted unfavorably with justification:
"Bear case assumes {{unfavorable assumption}} because {{specific risk scenario}}."

Present side-by-side:

:::card
**Scenario Comparison: {{investment.name}}**

| Metric | Bear | Base | Bull |
|--------|------|------|------|
| {{metric1}} | {{bear}} | {{base}} | {{bull}} |
| {{metric2}} | {{bear}} | {{base}} | {{bull}} |
| {{metric3}} | {{bear}} | {{base}} | {{bull}} |
| ... | | | |

**Key assumptions that differ:**

| Assumption | Bear | Base | Bull |
|-----------|------|------|------|
| {{assumption1}} | {{bear}} | {{base}} | {{bull}} |
| {{assumption2}} | {{bear}} | {{base}} | {{bull}} |
:::

"In the base case, this investment {{assessment}}. The bull case produces {{upside}}. The bear case shows {{downside}}. The range of outcomes is {{narrow/wide}} — which tells you this investment is {{relatively certain / highly uncertain}}."

### Custom Scenarios

"What specific scenario do you want to test?"

User defines specific assumption changes. System runs the model and compares to base case.

"You asked: 'What if interest rates hit 8% and vacancy goes to 15%?'"

:::card
**Custom Scenario: High Rate + High Vacancy**

| Assumption | Base | Custom | Justification |
|-----------|------|--------|---------------|
| Interest rate | {{base}} | 8% | User specified |
| Vacancy | {{base}} | 15% | User specified |

**Impact:**
| Metric | Base | Custom | Change |
|--------|------|--------|--------|
| {{metric1}} | {{base}} | {{custom}} | {{delta}} |
| ... | | | |
:::

---

## Sensitivity Analysis

### Single-Variable Sensitivity

"Which variable do you want to stress-test? Or I can identify the highest-sensitivity variables automatically."

**Auto-detection:** Vary each assumption by ±20% and rank by impact on key output metric. Present the top 3-5:

"The variables that matter most to your return:

| Rank | Variable | -20% | Base | +20% | Swing |
|------|----------|------|------|------|-------|
| 1 | {{var}} | {{value}} | {{base}} | {{value}} | {{total swing}} |
| 2 | {{var}} | {{value}} | {{base}} | {{value}} | {{total swing}} |
| 3 | {{var}} | {{value}} | {{base}} | {{value}} | {{total swing}} |

**#1 matters most:** A {{change}} in {{variable}} moves your return by {{swing}}. This is the assumption you need to be most confident about."

### Two-Variable Sensitivity (Sensitivity Table)

For the two highest-sensitivity variables, show the full matrix:

:::card
**Sensitivity: {{var1}} × {{var2}} → {{output metric}}**

| {{var1}} ↓ / {{var2}} → | {{v2_low}} | {{v2_mid}} | {{v2_high}} |
|--------------------------|-----------|-----------|------------|
| **{{v1_low}}** | {{result}} | {{result}} | {{result}} |
| **{{v1_mid}}** | {{result}} | **{{base}}** | {{result}} |
| **{{v1_high}}** | {{result}} | {{result}} | {{result}} |

*Bold = base case. Green = meets target. Red = below threshold.*
:::

"The top-left corner (low {{var1}} + low {{var2}}) is your worst case: {{value}}. The bottom-right (high {{var1}} + high {{var2}}) is your best case: {{value}}. You need to decide if the range of {{worst}} to {{best}} is acceptable for the capital at risk."

### Break-Even Analysis

"At what point does this investment break even / stop working?"

Find the value of key variables where the return hits zero (or the user's minimum threshold):

"Break-even analysis — at what values does your {{return metric}} hit {{threshold}}?

| Variable | Break-even value | Current assumption | Margin |
|----------|-----------------|-------------------|--------|
| {{var1}} | {{break_even}} | {{current}} | {{margin — how far current is from break-even}} |
| {{var2}} | {{break_even}} | {{current}} | {{margin}} |

You have the most margin on {{var}} — it would need to move {{amount}} before the deal breaks. You have the least margin on {{var}} — only {{amount}} of buffer."

---

## Scenario Narratives

Numbers need stories. After presenting scenario math, narrate:

"**Bear case in plain English:** {{Real-world scenario description}}. Imagine {{specific economic or market event}}. Your {{asset}} would {{consequence}}, producing {{return}} over {{period}}. You'd still {{positive/negative outcome}}, but it's {{assessment relative to alternatives and risk}}."

This connects abstract sensitivity analysis to real-world decision-making.

## Transition to Recommendation

When scenarios are complete, the user has:
- Base case metrics
- Range of outcomes (bull to bear)
- Key sensitivity variables
- Break-even thresholds
- Enough information to decide

→ Transition to recommendation cartridge for synthesis.
