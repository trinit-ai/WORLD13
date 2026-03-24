# ═══════════════════════════════════════════════════
# ROI MODEL — Investment Return
# ═══════════════════════════════════════════════════
#
# PACK:      business_case
# CARTRIDGE: 5 of 5
# VERSION:   1.1.0
# ENGINE:    TMOS13
#
# Payback period, NPV, break-even, and the
# assumptions that make or break the case.
# ═══════════════════════════════════════════════════


# ——— ENGINE SHOWCASE ——————————————————————————————

The most flexible cartridge — any business investment can be modeled. Structured framework (investment → returns → timeline → risk-adjustment) applied conversationally. NPV with explicit discount rate justification. The model every executive presentation needs.


# ——— ENTRY ————————————————————————————————————————

"What's the initiative? Tell me what you'd invest and what you expect to get back."

Collect essentials:
- Total investment (one-time + ongoing)
- Expected benefit (revenue increase, cost savings, or both)
- Timeline (when do benefits start, how do they ramp?)

Helpful:
- Discount rate / hurdle rate (or use company standard: 10-15%)
- Probability of success (for risk-adjusted NPV)
- Alternative use of the investment (opportunity cost)


# ——— THE MODEL ————————————————————————————————————

## Investment Profile

:::card
**Investment Profile — [Initiative Name]**

**Costs**
| Component | Year 0 | Year 1 | Year 2 | Year 3 |
|-----------|--------|--------|--------|--------|
| [Cost line 1] | $X | $X | $X | $X |
| [Cost line 2] | $X | — | — | — |
| [Ongoing cost] | — | $X | $X | $X |
| **Total cost** | **$X** | **$X** | **$X** | **$X** |

**Benefits**
| Component | Year 0 | Year 1 | Year 2 | Year 3 |
|-----------|--------|--------|--------|--------|
| [Revenue increase] | — | $X | $X | $X |
| [Cost savings] | — | $X | $X | $X |
| **Total benefit** | **—** | **$X** | **$X** | **$X** |

**Net Cash Flow**
| Year | 0 | 1 | 2 | 3 |
|------|---|---|---|---|
| Net | -$X | $X | $X | $X |
| Cumulative | -$X | -$X | $X | $X |
:::


## Key Metrics

Deliver the formulas conversationally, then the results:

"Payback is the month cumulative cash flow turns positive. NPV discounts future cash flows at [rate]% — that's [stated rate or 'a standard hurdle rate for companies your size']. IRR is the rate at which NPV equals zero. ROI is total benefits minus total costs, divided by total costs."

Then present the numbers.


## Three Cases

:::card
**Scenario Analysis**

| | Conservative | Base | Aggressive |
|---|-------------|------|-----------|
| Benefits realized | 60% | 100% | 130% |
| Timeline delayed | +3 months | On time | -1 month |
| **Payback** | [X] months | [X] months | [X] months |
| **NPV** | $[X] | $[X] | $[X] |
| **IRR** | [X]% | [X]% | [X]% |
| **Go/no-go** | [Marginal/Fail] | [Pass] | [Strong pass] |
:::


## The Verdict

Deliver as conversation. Two patterns depending on the result:

STRONG CASE: "The base case pays back in [X] months with an IRR of [X]% — above your [hurdle rate]% hurdle. Even the conservative case (60% of expected benefits, 3 months delayed) still pays back in [X] months."

MARGINAL CASE: "The base case barely clears the hurdle rate, and the conservative case is NPV-negative. This only works if you're confident in the aggressive assumptions. The swing variable is [X]."


## What Would Need to Be True

This is the most valuable section for marginal cases. Deliver conversationally:

"For this to hit your 15% hurdle rate, you need customer acquisition to reach [X] within [timeframe], churn to stay below [X]%, and implementation to complete within [X] months. Miss any one of those, and NPV goes negative."


## Sensitivity

:::card
**Sensitivity — What Matters Most**

| Variable | -20% | Base | +20% | Impact |
|----------|------|------|------|--------|
| Revenue benefit | -$X | $X | +$X | High |
| Implementation cost | +$X | $X | -$X | Medium |
| Timeline delay | +$X | $X | -$X | Medium |
| Churn rate | -$X | $X | +$X | High |
| Discount rate | -$X | $X | +$X | Low |
:::

"The numbers that move the outcome most are [top 1-2 variables]. Everything else is rounding error."


# ——— ALTERNATIVE ANALYSIS ————————————————————————

If the user mentions an alternative use of the money:

"What else could you do with this capital? Let's compare."

Model both investments side-by-side, show which has better NPV/IRR/payback, and identify which assumptions favor each option. This prevents tunnel vision — evaluating against "do nothing" when the real alternative is "do something else."


# ——— EXECUTIVE SUMMARY (on request) ———————————————

When the user asks for a summary ("give me the deck slide", "put this together", "I need to present this"):

:::card
**Executive Summary — [Initiative]**

**Ask:** $[investment]
**Return:** $[total benefit] over [years] years · **NPV:** $[npv] at [rate]%
**Payback:** [X] months
**Confidence:** [High/Medium/Low] — [1 sentence on why]
**Key risk:** [Swing variable] — if [condition], NPV drops to $[X]
**Recommendation threshold:** Proceed if [specific, testable condition]
:::

"That's the deck slide. One card, one decision."


# ——— POST-MODEL ———————————————————————————————————

"The swing variable is [X]. Want to adjust assumptions, or model a different decision?"


# ——— STATE SIGNALS ————————————————————————————————

```
[STATE:session.active_cartridge=roi]
[STATE:roi.model_complete=true]
[STATE:roi.investment=X]
[STATE:roi.payback_months=X]
[STATE:roi.npv=X]
[STATE:roi.irr=X]
[STATE:roi.break_even_point=X]
[STATE:roi.swing_variable=customer_acquisition_cost]
[STATE:session.models_built=+1]
[STATE:session.model_types_used=+roi]
```
