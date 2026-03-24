# ═══════════════════════════════════════════════════
# HEADCOUNT PLANNING — Hire / Outsource / Automate
# ═══════════════════════════════════════════════════
#
# PACK:      business_case
# CARTRIDGE: 1 of 5
# VERSION:   1.1.0
# ENGINE:    TMOS13
#
# Full comparison of three staffing approaches
# with fully-loaded cost modeling.
# ═══════════════════════════════════════════════════


# ——— ENGINE SHOWCASE ——————————————————————————————

Multi-scenario comparison with different cost structures. Fully-loaded cost calculation — the real cost, not just salary. Productivity modeling across approaches. Break-even between approaches. Time-to-productivity. The model that shows hiring is almost always more expensive than people think.


# ——— ENTRY ————————————————————————————————————————

"What role are you trying to fill? And roughly how many?"

Collect essentials through conversation:
- Role/function (what work needs to get done)
- Number of people needed
- Market salary (or estimate from role + location)

Then build the model.


# ——— THE MODEL ————————————————————————————————————

## Scenario 1: Full-Time Hire

:::card
**Full-Time Hire — [Role] × [N]**

| Cost Component | Per Person | Annual |
|---------------|------------|--------|
| Base salary | $150,000 | $150,000 |
| Benefits (25%) | $37,500 | $37,500 |
| Payroll taxes (7.65%) | $11,475 | $11,475 |
| Equipment/setup | $5,000 | $5,000 |
| Office/desk cost | $12,000 | $12,000 |
| Recruiting (20% fee) | $30,000 | — |
| Onboarding (lost productivity, 3mo) | — | ~$37,500 |
| Management overhead (10%) | $15,000 | $15,000 |

**Fully-loaded Year 1:** $268,475 · **Year 2+:** $231,000
**Effective hourly rate (Year 1):** $268,475 ÷ 2,080 hrs = $129/hr
:::

"People think hiring at $150K costs $150K. It costs $268K in year one. That's the fully-loaded number — the one that actually matters."


## Scenario 2: Outsource (Contractor/Agency)

:::card
**Outsource — [Role equivalent] × [N]**

| Cost Component | Rate | Monthly | Annual |
|---------------|------|---------|--------|
| Contractor rate | $125/hr @ 160 hrs/mo | $20,000 | $240,000 |
| Agency markup (if applicable, 30%) | — | $6,000 | $72,000 |
| Management overhead (5%) | — | $1,000 | $12,000 |

**Total (direct contractor):** $240,000/yr · **Total (via agency):** $324,000/yr

*No benefits, payroll tax, equipment, recruiting, or onboarding costs. Tradeoffs: no IP ownership (check contract), no culture integration, availability not guaranteed, ramp-up per project.*
:::


## Scenario 3: Automate (Tooling/AI)

:::card
**Automate — [Function]**

| Cost Component | Setup | Annual |
|---------------|-------|--------|
| Software/tool licenses | — | $24,000 |
| Implementation/integration | $30,000 | — |
| Training existing team | $5,000 | — |
| Ongoing maintenance | — | $6,000 |

**Year 1 total:** $65,000 · **Year 2+ total:** $30,000

*Coverage: automates ~60-80% of the function. Remaining 20-40% still needs a human. Risk: implementation failure, adoption resistance, capability gaps.*
:::


## Comparison

:::card
**Head-to-Head — Annual Cost**

| | Hire (FTE) | Outsource | Automate |
|---|-----------|-----------|----------|
| Year 1 | $268,475 | $240,000 | $65,000 |
| Year 2 | $231,000 | $240,000 | $30,000 |
| Year 3 | $231,000 | $240,000 | $30,000 |
| **3-Year Total** | **$730,475** | **$720,000** | **$125,000** |

**Coverage:** Hire 100% · Outsource 100% · Automate 60-80%
**IP/Control:** Hire Full · Outsource Partial · Automate Full
**Flexibility:** Hire Low (severance) · Outsource High (cancel) · Automate Medium
:::


## The Verdict

Deliver as conversational text, not a card.

"Over 3 years, automation is cheapest by far — if it can cover the function. The real question is: can 60-80% automation plus your existing team handle the workload, or do you need 100% human coverage?"

"Hiring vs outsourcing is nearly a wash financially. The decision comes down to control, IP, and flexibility. Hire if you need institutional knowledge and long-term commitment. Outsource if the need might be temporary or variable."


## Sensitivity

:::card
**Swing Variable: Salary**

| If salary is... | Hire (3yr) | vs Outsource |
|----------------|-----------|--------------|
| $120,000 | $596,000 | Hire wins by $124K |
| $150,000 | $730,475 | ~Even |
| $180,000 | $864,950 | Outsource wins by $145K |

*Above ~$155K base salary, outsourcing becomes cheaper than hiring for equivalent work. Below that, hiring wins on cost — plus you get culture and IP benefits.*
:::


# ——— POST-MODEL ———————————————————————————————————

After presenting the model, name the swing variable, then ask ONE question:

"The swing variable here is [salary / contractor rate / automation coverage]. Want to adjust any of these assumptions, or is there another decision to model?"

Do not list multiple options. Let the user drive.


# ——— STATE SIGNALS ————————————————————————————————

```
[STATE:session.active_cartridge=headcount]
[STATE:headcount.model_complete=true]
[STATE:headcount.recommendation=hire|outsource|automate]
[STATE:headcount.swing_variable=salary]
[STATE:session.models_built=+1]
[STATE:session.model_types_used=+headcount]
```
