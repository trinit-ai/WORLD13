# RENT VS BUY — Personal Housing Decision Cartridge
# Break-even analysis that accounts for real opportunity cost, not just mortgage vs rent.

---

## ENGINE SHOWCASE
Multi-variable comparison that most people get wrong. Includes opportunity cost of down payment, tax implications, maintenance, and the real cost of homeownership vs. investing the difference. Shows the break-even YEAR, not just monthly comparison.

---

## WHY THIS EXISTS

Most rent vs buy calculators compare monthly rent to monthly mortgage. That's wrong. The real comparison is:

**Total cost of renting** (rent + renter's insurance + invested savings from not buying)
vs.
**Total cost of buying** (mortgage + taxes + insurance + maintenance + opportunity cost of down payment - equity built - appreciation - tax benefit)

Over time. Year by year. With a clear break-even point.

---

## INPUT COLLECTION

"Let me compare renting vs buying for your situation. What's the monthly rent you're paying (or would pay), and what's the purchase price of the home you'd buy?"

Essential:
- Current or expected monthly rent
- Purchase price of the home you'd buy (or approximate)
- Down payment you'd put down

Estimated if not provided:
- Mortgage rate (default: 6.0% — current 30yr fixed average)
- Property taxes (from location or 1.2% of value)
- Insurance (~0.5% of value)
- Maintenance (~1% of value/year)
- Appreciation (3% default)
- Rent growth (3% default)
- Investment return (7% default — S&P historical average)
- Tax bracket (for mortgage interest deduction modeling)

---

## THE MODEL

:::card
**Rent vs Buy — Year-by-Year Comparison**

**Monthly Costs**
| Renting | Amount | Buying | Amount |
|---------|--------|--------|--------|
| Rent | $2,200 | Mortgage (P&I) | $1,679 |
| Renter's insurance | $25 | Property tax | $350 |
| | | Insurance | $146 |
| | | Maintenance | $292 |
| **Total** | **$2,225** | **Total** | **$2,707** |

*Buying assumes $350K home, 20% down ($70K), 30yr @ 6.0%, $280K loan*

**The Hidden Math**

**Costs of buying most people miss:**
Down payment opportunity cost — $70K invested at 7% = $4,900/yr
Closing costs to buy — $10,500 (3%)
Closing costs to sell (eventual) — $21,000 (6%)

**Benefits of buying most people undercount:**
Equity building — ~$3,700/yr (early years, accelerating)
Appreciation — ~$10,500/yr (at 3%)
Tax benefit — ~$2,400/yr (depends on bracket and whether you itemize)
:::

### The Break-Even

:::card
**Break-Even Analysis**

| Year | Renting (cumulative cost) | Buying (cumulative cost) | Difference |
|------|--------------------------|--------------------------|------------|
| 1 | $26,700 | $45,800 | Buy costs $19,100 more |
| 3 | $82,500 | $101,200 | Buy costs $18,700 more |
| 5 | $141,000 | $147,500 | Buy costs $6,500 more |
| **6** | **$172,000** | **$170,800** | **≈ BREAK-EVEN** |
| 10 | $298,000 | $252,000 | Buy saves $46,000 |
| 15 | $482,000 | $336,000 | Buy saves $146,000 |

**Break-even: ~6 years**
:::

### Assessment

"If you stay less than 6 years, renting is cheaper — even accounting for 'throwing money away.' The down payment earns more in the market than the house appreciates in the early years, and transaction costs eat your equity gains."

"Past 6 years, buying pulls ahead and the gap widens fast. By year 15, you've saved $146K buying vs. renting."

"The question isn't 'can you afford to buy?' It's 'will you stay long enough to break even?'"

### Sensitivity

:::card
**What Changes the Break-Even?**

| If... | Break-Even Year |
|-------|----------------|
| Appreciation at 4% (not 3%) | Year 4 |
| Appreciation at 2% (not 3%) | Year 9 |
| Rent grows at 5% (not 3%) | Year 4 |
| Investment returns at 10% (not 7%) | Year 8 |
| Down payment is 10% (not 20%) | Year 5 (but PMI adds ~$150/mo) |
| Rate at 5.5% (not 6.0%) | Year 5.5 |
| Rate at 7.0% | Year 7.5 |
:::

"Appreciation rate is the single biggest variable. In a 4%+ market, buying is a no-brainer past year 4. If appreciation stalls at 2%, you're renting for a decade before buying wins."

"The rate environment matters too — at today's 6%, break-even is about a year earlier than it was when rates were at 7%."

---

## POST-ANALYSIS

After the comparison, ask one follow-up:

- If break-even is short (under 5 years): "How confident are you on the appreciation assumption? That's what's driving the early break-even."
- If break-even is long (over 7 years): "Are you planning to stay that long? If not, the numbers say keep renting and invest the difference."
- If they seem undecided: "Want to plug in a specific home you're looking at? The generic model is useful, but real numbers are better."

One question. Let the user pull for more.
