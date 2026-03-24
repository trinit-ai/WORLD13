# FIX & FLIP — Rehab Project Cartridge
# Purchase-rehab-sell analysis with holding cost sensitivity and timeline risk.

---

## ENGINE SHOWCASE
Time-sensitive financial model (holding costs accrue monthly). ARV-based working backwards. Scenario modeling (what if rehab takes 2 months longer?). Clear profit/loss with all costs included.

---

## REQUIRED INPUTS

**Must have:**
- Purchase price (or target purchase price)
- Rehab budget estimate
- After-repair value (ARV) — what it sells for when done

**Should have:**
- Expected rehab timeline (months)
- Financing details (hard money rate, down payment, points)

**Default if not provided:**
- Hard money rate: 12% (current range 11%–13%)
- Points: 2
- Down payment: 20% of purchase + rehab
- Holding costs: taxes + insurance + utilities + interest = estimate from value
- Selling costs: 6% (agent commissions) + 2% (closing costs)
- Rehab timeline: 4 months (standard)

**Note on financing:** If the borrower qualifies for a conventional rehab loan (FHA 203k, Fannie HomeStyle), rates are in the high 5s to low 6s — dramatically cheaper than hard money. Flag this if the user doesn't specify financing type: "Are you using hard money or do you have conventional financing? The rate difference changes the math significantly."

---

## THE MODEL

### Input Collection

"What's the flip? Purchase price, rehab budget, and what you think it sells for when it's done."

Accept rough inputs: "Buying at 200, putting 50 into it, should sell around 310."

### Full P&L

:::card
**Fix & Flip Analysis**

**Acquisition**
**Purchase Price:** $200,000 · **Closing Costs (3%):** $6,000 · **Points (2%):** $4,000
**Total Acquisition:** $210,000

**Rehab**
**Budget:** $50,000 · **Contingency (10%):** $5,000
**Total Rehab:** $55,000

**Holding (4 months)**
| Line | Amount |
|------|--------|
| Interest ($200K @ 12%) | $8,000 |
| Taxes | $2,000 |
| Insurance | $500 |
| Utilities | $600 |
| **Total holding** | **$11,100** |

**Sale**
**ARV:** $310,000 · **Commissions (6%):** -$18,600 · **Closing (2%):** -$6,200
**Net Sale Proceeds:** $285,200

**Profit**
**Net Proceeds:** $285,200 · **Total Costs:** -$276,100
**Net Profit:** $9,100 · **ROI:** 7.1% · **Annualized:** 21.3% (4 months)
:::

### Assessment

"$9,100 profit on a $128K cash investment. The annualized number looks decent at 21.3%, but the absolute profit is thin for the risk. If rehab runs $10K over budget, your profit disappears."

### Timeline Sensitivity

:::card
**What If Rehab Takes Longer?**

| Timeline | Holding Costs | Profit | ROI |
|----------|--------------|--------|-----|
| 3 months | $8,300 | $11,900 | 9.3% |
| **4 months (base)** | **$11,100** | **$9,100** | **7.1%** |
| 5 months | $13,900 | $6,300 | 4.9% |
| 6 months | $16,700 | $3,500 | 2.7% |
| 7 months | $19,500 | $700 | 0.5% |
:::

"Every extra month costs $2,800 in holding. By month 7 you're basically breaking even. This deal requires execution — no delays."

### The 70% Rule

```
Max Purchase = (ARV × 70%) - Rehab
Max Purchase = ($310,000 × 70%) - $50,000 = $167,000

You're buying at $200,000. That's $33,000 above the 70% rule threshold.
```

"Most experienced flippers won't go above 70% of ARV minus rehab. At $200K, you're at 80.6%. The margin for error is slim."

---

## POST-ANALYSIS

After delivering the assessment, ask one follow-up:

- If profit is thin: "Want to figure out what purchase price makes this a solid deal?"
- If timeline is the risk: "Want to stress-test the timeline — see what happens at 6 or 8 months?"
- If the deal looks strong: "Want to run the numbers with conventional financing to see how much more you'd keep?"

One question. Let the user pull for more.
