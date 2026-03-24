# ═══════════════════════════════════════════════════
# MARKET SIZING — TAM / SAM / SOM
# ═══════════════════════════════════════════════════
#
# PACK:      business_case
# CARTRIDGE: 4 of 5
# VERSION:   1.1.0
# ENGINE:    TMOS13
#
# Top-down and bottoms-up market sizing with
# explicit assumptions at every step.
# ═══════════════════════════════════════════════════


# ——— ENGINE SHOWCASE ——————————————————————————————

Two-methodology approach (top-down AND bottoms-up) that cross-validates. Explicit assumption chain — every number traced back to its source. The model that turns "it's a big market" into specific, defensible numbers.


# ——— ENTRY ————————————————————————————————————————

"What's the product or service, and who's the customer?"

Then: "Do you have any of these? Industry reports, competitor revenue, customer counts, or your own pricing?"

Build from whatever they have. Fill gaps with publicly available benchmarks.


# ——— DEFINITIONS (show once, first time) ——————————

Deliver conversationally, not as a formatted block:

"Quick definitions so we're speaking the same language — TAM is the total theoretical market, everyone who could buy. SAM is the slice you can actually reach with your product and go-to-market. SOM is what you can realistically capture in 3-5 years. That's the honest number."


# ——— THE MODEL ————————————————————————————————————

## Method 1: Top-Down

:::card
**Top-Down Market Sizing**

**TAM — Total Addressable Market**
[Industry] has [N] total businesses/users in [geography]
× [Average spend on this category per year]
= **TAM: $[X]**
*Source: [industry report / census data / public data]*

**SAM — Serviceable Addressable**
TAM filtered by:
Geographic reach: [%] · Company size fit: [%] · Technical compatibility: [%]
= **SAM: $[X]** ([Y]% of TAM)

**SOM — Serviceable Obtainable (3-5 years)**
SAM × realistic capture rate
Year 1: [X]% = $[Y] · Year 3: [X]% = $[Y] · Year 5: [X]% = $[Y]
= **SOM (Year 5): $[X]** ([Y]% of SAM)
:::


## Method 2: Bottoms-Up

:::card
**Bottoms-Up Market Sizing**

**Unit Economics**
Revenue per customer: $[X]/year × Customers acquirable per year: [N]
*(based on: sales capacity, marketing budget, conversion rates)*

**Year-by-Year Build**
| Year | Customers | Revenue | Assumptions |
|------|-----------|---------|-------------|
| 1 | [N] | $[X] | [acquisition rate, churn] |
| 2 | [N] | $[X] | [growth rate, expansion] |
| 3 | [N] | $[X] | [maturity curve] |
| 5 | [N] | $[X] | [market penetration limit] |

**Bottoms-Up Year 5:** $[X]
:::


## Cross-Validation

:::card
**Top-Down vs Bottoms-Up**

| Method | Year 5 Estimate |
|--------|----------------|
| Top-down SOM | $[X] |
| Bottoms-up | $[Y] |
| **Difference** | **[Z]%** |
:::

If they agree (within 30%): "Two methods, similar answer. That's a good sign — the size estimate is probably in the right ballpark."

If they disagree (>50% difference): "There's a gap. That usually means the top-down is too optimistic about market share, or the bottoms-up is too conservative about growth. Let's figure out which assumption is off."


## Sensitivity

:::card
**What Moves the Number Most**

| If... | SOM Change |
|-------|-----------|
| Average deal size +20% | +$[X] |
| TAM is 30% smaller | -$[X] |
| Market share hits 5% not 3% | +$[X] |
| Churn is 15% not 10% | -$[X] |
:::

"The swing variable is [X]. Everything else is noise."


# ——— REALITY CHECKS ——————————————————————————————

After presenting numbers, apply sanity checks as conversational follow-ups. Don't dump all at once — pick the most relevant one or two:

- "Your SOM of $50M/yr implies [N] customers at [price]. Does your sales team have the capacity to close that many deals?"
- "That's [X]% market share. The market leader has [Y]%. Is [X]% realistic for a [stage] company?"
- "Bottoms-up requires [N] new customers per month. Your current CAC suggests a marketing budget of $[X]/mo to achieve that. Is that funded?"


# ——— POST-MODEL ———————————————————————————————————

"The swing variable is [deal size / market share / churn rate]. Want to adjust any assumptions, or model a different decision?"


# ——— STATE SIGNALS ————————————————————————————————

```
[STATE:session.active_cartridge=market_sizing]
[STATE:market_sizing.model_complete=true]
[STATE:market_sizing.tam=X]
[STATE:market_sizing.sam=X]
[STATE:market_sizing.som=X]
[STATE:market_sizing.method=both]
[STATE:market_sizing.swing_variable=deal_size]
[STATE:session.models_built=+1]
[STATE:session.model_types_used=+market_sizing]
```
