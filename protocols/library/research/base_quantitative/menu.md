# MENU — QUANTITATIVE ANALYSIS ENGINE

## Fresh Session

:::card
**Investment Analysis Engine**

**New Analysis** — Describe an investment opportunity and build the model

**Analysis Types** — Browse domain-specific analysis templates
:::

Describe an investment to start, or ask about available analysis types.

---

## Mid-Analysis Menu

:::card
**Model: {{investment.name}}**

**Key Metrics:**
{{primary metrics display — domain-specific}}

**Assumptions:** {{count}} tracked ({{high_confidence}} high confidence, {{medium}} medium, {{low}} low)

**Scenarios:** {{base/bull/bear status}}
:::

What would you like to do? Continue the analysis, adjust an assumption, run sensitivity analysis, compare scenarios, view recommendation, see the full assumption register, download the report, or start a new analysis.

---

## Assumption Register View

:::card
**Assumption Register — {{investment.name}}**

| # | Assumption | Value | Source | Confidence | Sensitivity |
|---|-----------|-------|--------|-----------|-------------|
{{for each assumption in register}}
| {{n}} | {{name}} | {{value}} | {{source}} | {{H/M/L}} | {{H/M/L}} |

*Sources: UI = User Input, MD = Market Data, EST = Estimate, HIST = Historical*
:::

"Want to adjust any of these? Tell me which assumption and the new value — I'll rerun the model."

---

## Help

"Available anytime:

- **'status'** or **'dashboard'** — Key metrics and model summary
- **'assumptions'** — Full assumption register with sources and confidence
- **'adjust [assumption]'** — Change any assumption and see the cascading impact
- **'what if'** — Explore a scenario variation
- **'compare'** — Side-by-side scenario comparison
- **'report'** — Download complete analysis document

Or just ask me a question about the numbers."
