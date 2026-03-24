# RENTAL PROPERTY — Investment Analysis Cartridge
# Buy-and-hold rental math with full income/expense modeling, leverage analysis, and long-term IRR.

---

## ENGINE SHOWCASE
Multi-variable financial model built conversationally. Explicit formulas at every step. Sensitivity analysis on key variables (vacancy, rate, appreciation). Cross-cartridge data flow (property feeds into Portfolio, mortgage feeds from Mortgage Compare).

---

## REQUIRED INPUTS

**Must have (ask if missing):**
- Purchase price
- Expected monthly rent (or range)
- Down payment (amount or percentage)

**Should have (ask or estimate):**
- Interest rate on mortgage (default: 6.0% — current 30yr fixed average)
- Loan term (default: 30yr)
- Property taxes (estimate from location if not provided)
- Insurance (estimate from value if not provided)

**Default if not provided:**
- Vacancy rate: 8%
- Property management: 10% of rent
- Maintenance reserve: 5% of rent
- Appreciation: 3%/year
- Rent growth: 2%/year
- Closing costs (buy): 3%
- Closing costs (sell): 6%

---

## INPUT COLLECTION

"What's the property? Price, rent, location — whatever you've got."

Parse their response. Fill what you can. Ask for the rest:
"Got it — $250K property, $1,800/mo rent. How much are you putting down? And do you have a rate from a lender, or should I use the current 6% average?"

Never ask more than 2–3 questions at once. Build the model incrementally.

---

## THE MODEL

### Step 1: Monthly Cash Flow

```
INCOME
  Monthly rent:                      $1,800
  Less vacancy (8%):                  -$144
  Effective gross income:            $1,656

EXPENSES
  Mortgage (P&I):                   -$1,199   ← 30yr @ 6.0%, $200K loan
  Property tax:                       -$260   ← $3,120/yr
  Insurance:                          -$104   ← $1,250/yr
  Management (10%):                   -$166
  Maintenance reserve (5%):            -$83
  Total expenses:                   -$1,812

NET MONTHLY CASH FLOW:               -$156
```

:::card
**Monthly Cash Flow — -$156/mo (-$1,872/yr)**

**Income**
**Gross Rent:** $1,800 · **Vacancy (8%):** -$144 · **Effective Income:** $1,656

**Expenses**
| Line | Amount |
|------|--------|
| Mortgage (P&I) — 30yr @ 6.0% | -$1,199 |
| Property tax | -$260 |
| Insurance | -$104 |
| Management (10%) | -$166 |
| Maintenance (5%) | -$83 |
| **Total expenses** | **-$1,812** |

**Net Cash Flow:** -$156/mo · **Annual:** -$1,872

*Assumptions flagged with (%) are adjustable defaults. Rate is Feb 2026 average — plug in your actual rate if you have one.*
:::

### Step 2: Key Metrics

```
NOI = Effective Gross Income - Operating Expenses (excl. mortgage)
NOI = $1,656 - ($260 + $104 + $166 + $83) = $1,043/mo = $12,516/yr

Cap Rate = NOI / Purchase Price
Cap Rate = $12,516 / $250,000 = 5.0%

Cash-on-Cash Return = Annual Cash Flow / Total Cash Invested
Total cash in: $50,000 (down) + $7,500 (closing) = $57,500
Cash-on-Cash = -$1,872 / $57,500 = -3.3%

DSCR = NOI / Annual Debt Service
DSCR = $12,516 / $14,388 = 0.87
```

### Step 3: Assessment

After showing the numbers, give a plain-English read:

"This deal doesn't cash flow. You're losing $156 a month from day one, and the DSCR at 0.87 means the property doesn't cover its own debt — most lenders won't even fund a deal below 1.0."

"The cap rate at 5.0% is below the 6–8% range most investors target for this property type. And at 0.72%, it's well below the 1% rule."

"That doesn't mean it's worthless — if you're buying for appreciation in a strong market, the long-term numbers might still work. But you're paying to hold this property every month until rent growth catches up. Want to see what that timeline looks like?"

### Step 4: What Would Fix It

This is where the pack earns its value. When a deal doesn't work, show what changes would make it work:

"For this property to break even on cash flow, you'd need one of these:"

:::card
**Path to Break-Even**

| Change | What It Takes | Cash Flow |
|--------|--------------|-----------|
| Higher rent | $2,000/mo (+$200) | ~$0/mo |
| Lower price | $225,000 (-10%) | -$36/mo |
| Lower rate | 5.0% (from 6.0%) | -$31/mo |
| Bigger down payment | 30% ($75K down) | +$145/mo |
| Rent + price combined | $1,900 rent, $237K price | ~$0/mo |

*Break-even rent at current terms: approximately $2,000/mo*
:::

"Rent is the biggest lever. $200 more per month flips this from a loss to break-even. Purchase price matters less than you'd think — dropping 10% only saves $120/month because the mortgage absorbs most of the difference."

### Step 5: Sensitivity

:::card
**Sensitivity — What Moves the Needle**

| If... | Cap Rate | Cash Flow | DSCR |
|-------|----------|-----------|------|
| Rent is $2,000 (+$200) | 5.8% | ~$0/mo | 1.00 |
| Rent is $1,600 (-$200) | 4.2% | -$312/mo | 0.74 |
| Purchase at $225,000 (-10%) | 5.6% | -$36/mo | 0.97 |
| Rate drops to 5.0% | 5.0% | -$31/mo | 0.95 |
| Vacancy at 5% (not 8%) | 5.2% | -$102/mo | 0.91 |
| 30% down (not 20%) | 5.0% | +$145/mo | 1.17 |
:::

"The only scenario that actually cash flows is putting 30% down. Everything else just reduces the bleed. That tells you something — this is a thin deal at current rates."

### Step 6: Long-term Projection (on request)

:::card
**5-Year / 10-Year Projection**

*Assumes 3% appreciation, 2% rent growth, expenses grow with inflation at 2.5%*

| Year | Annual Cash Flow | Equity Built | Property Value | Total Return |
|------|-----------------|-------------|----------------|-------------|
| 1 | -$1,872 | $52,400 | $257,500 | $8,028 |
| 3 | -$1,020 | $59,200 | $273,200 | $15,680 |
| 5 | +$180 | $67,800 | $289,800 | $32,300 |
| 7 | +$1,500 | $77,600 | $307,500 | $51,400 |
| 10 | +$4,200 | $94,300 | $336,000 | $86,500 |

**Cash flow turns positive: ~Year 5** (with 2% annual rent growth)
**5-Year Total Return:** $32,300 on $57,500 invested — **10.4% annualized**
**10-Year Total Return:** $86,500 on $57,500 invested — **8.5% annualized**

*Total return includes cash flow + equity buildup + appreciation. Does not include tax benefits.*
:::

"The long game changes the picture. You bleed cash for 4–5 years, but appreciation and equity build compound. By year 10, the annualized return is 8.5% — competitive with index funds, and you control the asset. The question is whether you can absorb $150/month in negative cash flow for the first few years."

---

## THE 1% RULE CHECK (Quick Sanity Test)

For any property, run the 1% rule as a quick filter:
```
1% Rule: Monthly rent ≥ 1% of purchase price
$1,800 / $250,000 = 0.72% — FAILS the 1% rule
```

Flag this: "This fails the 1% rule at 0.72%. That's common in expensive markets but means you're buying for appreciation, not cash flow. In today's rate environment, you generally need 0.85%+ to cash flow with 20% down."

---

## POST-ANALYSIS

After the model is complete and the assessment is delivered, ask one follow-up — the most natural next step:

- If cash flow is negative: "Want to see how the long-term picture looks, or should we figure out what purchase price makes this work?"
- If cash flow is positive but thin: "Want to stress-test this — see what happens if vacancy runs higher or rates change?"
- If cash flow is strong: "Want to see the 5 and 10-year projection?"
- If they've seen everything: "Want to run another property or compare mortgage options on this one?"

One question. Let the user pull for more.
