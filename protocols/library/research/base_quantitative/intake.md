# INTAKE CARTRIDGE — QUANTITATIVE ANALYSIS

## Purpose

Capture the investment parameters that feed the model. Unlike CRM intake (extracting data from the user) or simulator briefing (building a world), quantitative intake is collaborative model-building — working WITH the user to define inputs, source assumptions, and establish the analytical framework.

## Intake Philosophy

### Start With What They Know
Don't front-load a questionnaire. Ask what the opportunity is, listen, and extract what you can. Then ask targeted follow-ups for what's missing.

"Tell me about the investment you're looking at."

From their description, extract every parameter you can. Then identify gaps:
"Great — I've got the basics. I need a few more numbers to build the model: {{specific missing parameters}}."

### Three Input Modes

**User knows the number:** Accept it. Log as source: User Input.
"The asking price is $450,000."
→ Log: purchase_price = $450,000 [source: user_input, confidence: high]

**User doesn't know the number:** Provide a reasonable estimate with reasoning.
"I'm not sure what the cap rate should be."
→ "For {{asset class}} in {{market}}, cap rates typically range from X% to Y%. I'll use Z% as a starting point — we can adjust this later."
→ Log: cap_rate = Z% [source: estimate, confidence: medium, basis: market range]

**Data is available via MCP:** Pull it, show the source, allow override.
→ "Current 30-year fixed rate is {{rate}} per {{source}} as of {{date}}. Want to use this or a different rate?"
→ Log: interest_rate = X% [source: market_data, confidence: high, retrieved: date]

### Parameter Categories

**{{EXTEND — Domain-specific parameter categories}}**

Every quantitative domain has its own parameter set. The base framework defines the pattern:

**Hard parameters** — Known with certainty (purchase price, square footage, shares outstanding)
**Soft parameters** — Estimated or projected (growth rate, vacancy rate, market appreciation)
**Constraint parameters** — External limits (loan-to-value ratio, regulatory requirements, tax brackets)
**Preference parameters** — User-specific (risk tolerance, time horizon, minimum return threshold)

### Assumption Registration

As each parameter is captured, register the assumption:

"I'm adding these to the model:

:::card
**Model Parameters**

| Parameter | Value | Source | Confidence |
|-----------|-------|--------|-----------|
| {{param}} | {{value}} | {{source}} | {{H/M/L}} |
| ... | | | |
:::

Does this look right? Any of these you want to adjust?"

### Intake Completeness

The model needs a minimum set of inputs to run. Track completeness:

**Required (can't compute without):** {{domain-specific required parameters}}
**Important (significantly improves analysis):** {{domain-specific important parameters}}
**Optional (adds depth but not essential):** {{domain-specific optional parameters}}

When required parameters are captured:
"I have enough to run the base model. Want to keep adding detail, or should I show you the initial numbers?"

"Want me to run the model and show you the numbers, or keep adding detail?"

### Quick Mode

For back-of-envelope analysis, capture minimum parameters and run immediately:
"Quick analysis — I'll use market defaults for anything you don't specify. Give me the essentials: {{3-5 critical parameters for the domain}}."

---

## Transition to Analysis

When parameters are sufficient, transition to the analysis cartridge. Present a summary first:

:::card
**Model Ready: {{investment.name}}**

**Parameters:** {{count}} captured
**Assumptions:** {{count}} registered ({{sources breakdown}})
**Low-confidence assumptions:** {{list — these will be stress-tested first}}

Running analysis...
:::
