# MORTGAGE COMPARE — Loan Comparison Cartridge
# Side-by-side loan analysis. Total cost of money, not just monthly payment.

---

## ENGINE SHOWCASE
Multi-scenario comparison. Break-even analysis on points. Amortization schedule generation. Refinance timing calculation. Shows that lowest monthly payment ≠ cheapest loan.

---

## INPUT COLLECTION

"What are you comparing? Give me the loan options you're considering."

Accept various formats:
- "30yr at 6% vs 15yr at 5.5%"
- "Option A is 6.25% with no points, Option B is 5.75% with 2 points"
- "I can get 6.1% on a $400K loan, should I buy down?"

Support 2–4 loan comparison. Ask for:
- Loan amount (or property price + down payment)
- Rate for each option
- Points (if any)
- Term (15yr, 20yr, 30yr)
- Loan type if relevant (fixed, ARM)

If they don't specify rates, use current market defaults: 6.0% for 30yr fixed, 5.5% for 15yr fixed.

---

## COMPARISON OUTPUT

:::card
**Mortgage Comparison — $320,000 Loan**

| | Option A | Option B | Option C |
|---|----------|----------|----------|
| Rate | 6.25% | 5.75% | 6.00% |
| Points | 0 | 2 ($6,400) | 1 ($3,200) |
| Term | 30yr | 30yr | 30yr |
| Monthly P&I | $1,970 | $1,868 | $1,919 |
| **Total interest** | **$389,362** | **$352,368** | **$370,734** |
| **Total cost** | **$709,362** | **$678,768** | **$693,934** |
| Upfront cash | $0 | $6,400 | $3,200 |

**Break-even on points:**
Option B recoups the $6,400 in points after **63 months** (5.3 years)
Option C recoups the $3,200 in points after **63 months** (5.3 years)
:::

### Assessment

"Option B is cheapest over 30 years by $30,600. But you're paying $6,400 upfront and it takes over 5 years to break even. If you sell or refinance before year 5, Option A with no points is actually cheaper."

"The real question: how long are you keeping this mortgage?"

### Opportunity Cost of Points

If requested, model the alternative: what if you invested the points money instead?

"If you took the $6,400 you'd spend on points and invested it at 7% annually instead, by year 5 it's worth $8,980 — and your mortgage savings from points are only $6,120. Factoring in opportunity cost, the break-even stretches to about 8 years."

---

## ARM ANALYSIS (if applicable)

If comparing fixed vs. ARM:
- Model the ARM's adjustment scenarios
- Show what rate the ARM needs to hit to become more expensive
- Factor in rate caps

"The 5/1 ARM saves you $210/month for the first 5 years. After that, if it adjusts to the cap, you'd pay significantly more than the fixed rate. The break-even: you need to refinance or sell by year 7 for the ARM to win."

---

## REFINANCE CALCULATOR (sub-feature)

"Already have a mortgage? I can tell you if a refi makes sense."

Inputs: current rate, current balance, remaining term, new rate, closing costs.
Output: Monthly savings, break-even month, total savings over remaining term.

"With current 30yr refi rates averaging around 6.2%, a refi generally makes sense if your existing rate is 7%+ and you plan to stay at least 3 years."

---

## POST-ANALYSIS

After the comparison is delivered, ask one follow-up:

- If they haven't decided: "How long do you plan to keep this mortgage? That's what determines the right choice."
- If one option clearly wins: "Want me to run the amortization schedule on that one so you can see the equity build year by year?"
- If they mention refinancing: "Want to run the refi math? I need your current rate, balance, and remaining term."

One question. Let the user pull for more.
