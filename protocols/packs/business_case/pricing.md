# ═══════════════════════════════════════════════════
# PRICING STRATEGY — Price Change Impact
# ═══════════════════════════════════════════════════
#
# PACK:      business_case
# CARTRIDGE: 3 of 5
# VERSION:   1.1.0
# ENGINE:    TMOS13
#
# Elasticity modeling, break-even volume analysis,
# and revenue curve visualization.
# ═══════════════════════════════════════════════════


# ——— ENGINE SHOWCASE ——————————————————————————————

Price elasticity modeling from the user's own data. Break-even analysis — how many customers can you lose at a higher price and still come out ahead? Revenue curve showing the optimal zone. The model that makes pricing decisions feel scientific instead of gut-feel.


# ——— ENTRY ————————————————————————————————————————

"Tell me about your current pricing."

Collect essentials:
- Current price per unit/seat/month
- Current volume (customers, seats, transactions)
- Variable cost per unit (or gross margin %)

Helpful but optional:
- Historical data from previous price changes and their effect on volume
- Competitor pricing for reference
- Customer segmentation (enterprise vs SMB sensitivity)

"Don't have exact numbers? Estimates are fine — I'll show you how much the answer changes if you're off."


# ——— THE MODEL ————————————————————————————————————

## Current State

:::card
**Current Pricing**

**Price:** $29/mo per seat · **Volume:** 10,000 seats · **Variable cost:** $8/seat
**Contribution margin:** $21/seat (72.4%)
**Monthly revenue:** $290,000 · **Monthly contribution:** $210,000
:::


## Price Increase Scenario

"Let's say you raise to $35/mo. The question is: how many customers can you afford to lose?"

:::card
**Break-Even Analysis — $29 → $35 (+20.7%)**

At $35/seat, contribution margin becomes $27/seat.
Break-even volume = $210,000 ÷ $27 = **7,778 seats**

**You can lose up to 2,222 customers (22.2%) and still make the same money.**

| Volume Lost | Remaining | Revenue | Contribution | vs. Current |
|-------------|-----------|---------|-------------|------------|
| 0% | 10,000 | $350,000 | $270,000 | +$60,000 |
| 10% | 9,000 | $315,000 | $243,000 | +$33,000 |
| 15% | 8,500 | $297,500 | $229,500 | +$19,500 |
| **22.2%** | **7,778** | **$272,222** | **$210,000** | **$0** |
| 25% | 7,500 | $262,500 | $202,500 | -$7,500 |
| 30% | 7,000 | $245,000 | $189,000 | -$21,000 |
:::

Then deliver the assessment as conversation:

"At $35, you can lose 22% of your customers and break even. Most SaaS companies see 5-15% churn from a 20% price increase. If your churn stays under 22%, you make more money with fewer customers — which also means lower support costs, less infrastructure, and higher per-customer attention."

"The risk: if you're in a competitive market where customers have easy alternatives, churn could exceed 22%. If you have strong switching costs or no close substitute, 5-10% churn is more realistic."


## Revenue Curve

:::card
**Revenue at Different Price Points**

| Price | Est. Volume | Revenue | Contribution |
|-------|-------------|---------|-------------|
| $19 | 14,000 | $266,000 | $154,000 |
| $24 | 11,500 | $276,000 | $184,000 |
| **$29 (current)** | **10,000** | **$290,000** | **$210,000** |
| $35 | 8,500 | $297,500 | $229,500 |
| $39 | 7,500 | $292,500 | $232,500 |
| $49 | 5,500 | $269,500 | $225,500 |
| $59 | 4,000 | $236,000 | $204,000 |

*Volume estimates use assumed elasticity of -1.2. Adjust with real data if available.*
:::

"Revenue peaks around $35-39. Contribution peaks around $39-49. The 'optimal' price depends on what you're optimizing for — top-line revenue or bottom-line contribution."


## Elasticity Calibration

If the user has historical data (previous price change + observed churn), calculate actual elasticity, replace assumptions with real data, and show confidence: "Based on your last price change, elasticity is approximately -0.8 — lower than average, which means your customers are less price-sensitive than typical SaaS."

If no historical data, use industry benchmarks — SaaS: -1.0 to -1.5, commodity: -2.0+, luxury: -0.3 to -0.8 — and flag as estimated: "I'm using -1.2 elasticity (mid-range for SaaS). If you've changed prices before, I can calibrate this with real data."


## Price Decrease Scenario

Same model, opposite direction:

"Lowering from $29 to $24 means you need 14% more customers just to break even on contribution. You'd need to acquire 1,400 new seats to make the same money — what's your CAC?"

This naturally leads into ROI modeling: "The price decrease only makes sense if the volume increase exceeds the margin compression. Want to model that?"


# ——— POST-MODEL ———————————————————————————————————

"The swing variable is [elasticity / churn rate / competitive alternatives]. Want to try a different price point, or model a different decision?"


# ——— STATE SIGNALS ————————————————————————————————

```
[STATE:session.active_cartridge=pricing]
[STATE:pricing.model_complete=true]
[STATE:pricing.current_price=29]
[STATE:pricing.current_volume=10000]
[STATE:pricing.optimal_price=39]
[STATE:pricing.swing_variable=elasticity]
[STATE:session.models_built=+1]
[STATE:session.model_types_used=+pricing]
```
