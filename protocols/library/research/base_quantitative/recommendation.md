# RECOMMENDATION CARTRIDGE — QUANTITATIVE ANALYSIS

## Purpose

Synthesize the analysis into a decision framework. Not "buy this" or "don't buy this" — but "here's what the numbers say, here's what you'd need to believe, and here's the framework for your decision."

## Recommendation Structure

### Step 1: Executive Summary

:::card
**Investment Analysis Summary: {{investment.name}}**

**The Numbers Say:** {{One sentence — what the analysis shows}}

| Metric | Value | Assessment |
|--------|-------|-----------|
| {{primary metric}} | {{value}} | {{good/marginal/poor}} |
| {{secondary metric}} | {{value}} | {{good/marginal/poor}} |
| {{third metric}} | {{value}} | {{good/marginal/poor}} |

**Scenario Range:** {{bear metric}} → {{base metric}} → {{bull metric}}
**Highest Sensitivity:** {{top variable}} — if this changes by {{amount}}, the outcome shifts from {{x}} to {{y}}
:::

### Step 2: What You'd Need to Believe

"For this investment to work as modeled, you need to believe:"

:::card
**Key Assumptions Required**

1. **{{Assumption}}** — {{value}} (Confidence: {{H/M/L}})
   {{Why this matters and how confident you should be}}

2. **{{Assumption}}** — {{value}} (Confidence: {{H/M/L}})
   {{Why this matters and how confident you should be}}

3. **{{Assumption}}** — {{value}} (Confidence: {{H/M/L}})
   {{Why this matters and how confident you should be}}

**The assumption you should scrutinize most:** {{highest-sensitivity, lowest-confidence assumption}}
:::

### Step 3: Risk Assessment

:::card
**Key Risks**

**{{Risk 1}}** — Probability: {{est}} | Impact: {{est}}
{{What triggers it, how it affects the investment, mitigation}}

**{{Risk 2}}** — Probability: {{est}} | Impact: {{est}}
{{What triggers it, how it affects the investment, mitigation}}

**{{Risk 3}}** — Probability: {{est}} | Impact: {{est}}
{{What triggers it, how it affects the investment, mitigation}}
:::

### Step 4: Decision Framework

"Here's how I'd frame the decision:"

:::card
**Decision Criteria**

**Proceed if:**
- {{Condition 1 — e.g., "You can verify the rent assumption through market comps"}}
- {{Condition 2 — e.g., "You're comfortable with the bear case outcome"}}
- {{Condition 3 — e.g., "This fits your risk tolerance and time horizon"}}

**Pause if:**
- {{Condition — e.g., "The key assumption can't be verified"}}
- {{Condition — e.g., "The bear case exceeds your risk tolerance"}}

**Walk away if:**
- {{Condition — e.g., "Break-even requires assumptions above historical range"}}
- {{Condition — e.g., "Better alternatives exist at similar risk"}}
:::

### Step 5: Before You Decide

"Questions to answer before committing:"

1. {{Specific diligence question — something the model can't answer}}
2. {{Market verification — something that should be checked against real data}}
3. {{Professional consultation — specific topic for advisor/accountant/lawyer}}
4. {{Alternative comparison — have you looked at X as an alternative?}}

### Step 6: Next Steps

From here you can download the full analysis report, adjust assumptions and rerun, compare to another investment, run additional scenarios, or start a new analysis. What would you like?

---

## Export Document Structure

```
INVESTMENT ANALYSIS REPORT
============================
Investment | Date | Analysis Depth

EXECUTIVE SUMMARY
Key metrics, scenario range, headline assessment

INVESTMENT PARAMETERS
All inputs with sources

ASSUMPTION REGISTER
Complete list with values, sources, confidence, sensitivity

CORE ANALYSIS
All calculations with formulas, inputs, results
Metric-by-metric with context and assessment

SCENARIO ANALYSIS
Base / Bull / Bear comparison
Custom scenarios if run
Sensitivity tables

BREAK-EVEN ANALYSIS
Variable-by-variable thresholds

RISK ASSESSMENT
Key risks with probability, impact, mitigation

DECISION FRAMEWORK
Proceed / Pause / Walk away criteria
Questions to answer before deciding

APPENDIX
Full calculation details
Data sources and retrieval dates
Methodology notes
```

---

## Anti-Patterns

**Never say "you should invest."** Say "the numbers support the investment if these assumptions hold."

**Never present certainty.** Always present ranges. "Your return will be 8%" → "Your return ranges from 5% to 11% depending on {{key variable}}, with a base case of 8%."

**Never ignore the downside.** Even when the base case is strong, show the bear case prominently.

**Never skip the assumptions.** The recommendation is only as good as the inputs. Make the user see what the model depends on.

**Never forget opportunity cost.** "This produces 8%" is incomplete. "This produces 8% versus 5% in a money market — is the 3% premium worth the risk and illiquidity?" is analysis.
