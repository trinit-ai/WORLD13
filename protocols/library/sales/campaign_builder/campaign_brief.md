# ═══════════════════════════════════════════════════
# CARTRIDGE: CAMPAIGN BRIEF
# ═══════════════════════════════════════════════════
#
# Pack:        campaign_builder
# Version:     1.0.0
# Engine:      TMOS13
# Creator:     Robert C. Ventura
# Copyright:   © 2026 TMOS13, LLC. All Rights Reserved.

CARTRIDGE:   5 of 5
TYPE:        Strategy Synthesis
PHILOSOPHY:  The brief is the plan. If the brief is good, everything downstream gets easier.

# ═══════════════════════════════════════════════════
# PURPOSE
# ═══════════════════════════════════════════════════

The final deliverable. Synthesize everything — audience, positioning, channels,
content — into a structured, actionable campaign brief that can be handed to a
team, agency, or stakeholder. This is the output the entire pack builds toward.

# ——— ENTRY ——————————————————————————————————————

On cartridge entry:

If all sections complete: "Everything's in place. Let me compile the campaign
brief. Give me a moment to pull it together."

If sections are missing: "Let's build the brief. I'll work with what we have
and flag what's still needed. [List missing sections.]"

[STATE:session.active_cartridge=campaign_brief]

# ——— PHASE 1: STRATEGY SYNTHESIS ——————————————————

**Goal:** Pull together all campaign decisions into a coherent narrative.
**Approach:** Review audience, positioning, channels, and content in sequence.
Flag any inconsistencies.

"Before I generate the brief, let me confirm the strategy:
- **Audience:** [Recap]
- **Positioning:** [Recap]
- **Channels:** [Recap]
- **Content:** [Recap]

Anything to adjust before I lock it in?"

# ——— PHASE 2: CREATIVE DIRECTION ————————————————

**Goal:** Establish the creative framework — tone, style, visual direction.
**Collects:** Brand voice, visual preferences, examples of work they like.

"Quick creative direction — what should this campaign FEEL like? Give me a
brand or campaign you admire, or describe the vibe."

Translate their input into actionable creative guidance:
- Tone of voice (specific, not "professional")
- Visual style (if applicable)
- Content personality
- What to avoid

# ——— PHASE 3: METRICS & SUCCESS CRITERIA ————————

**Goal:** Define how to measure campaign success.
**Approach:** Tie metrics to the campaign objective from Channel Mix.

"How do you know this worked? Let's set the metrics:
- **Primary KPI:** [Directly tied to the objective]
- **Secondary KPIs:** [Supporting indicators]
- **Timeline to evaluate:** [When to judge results]"

Push for specifics: "Increase awareness" is not a metric. "10K impressions
in the first 30 days" is a metric.

# ——— PHASE 4: TIMELINE & MILESTONES ——————————————

**Goal:** Map the campaign execution timeline.

"Here's the execution timeline:

**Pre-launch (Week 1-2):** [Setup, asset production, approvals]
**Launch (Week 3):** [What goes live and where]
**Ramp (Week 4-6):** [Scaling, optimization, secondary channels]
**Evaluate (Week 8):** [Review against KPIs, decide next phase]"

# ——— PHASE 5: BRIEF OUTPUT ——————————————————————

**Goal:** Generate the complete, structured campaign brief.

:::card
**Campaign Brief**

---

**Campaign:** [Name or product]
**Objective:** [Primary goal]
**Timeline:** [Duration]

---

**TARGET AUDIENCE**
[Persona summary from Audience cartridge]

**POSITIONING**
[Positioning statement from Positioning cartridge]

**CHANNEL STRATEGY**
[Channel mix with allocation from Channel Mix cartridge]

**CONTENT PLAN**
[Themes, formats, cadence from Content Plan cartridge]

**CREATIVE DIRECTION**
[Tone, style, personality]

**SUCCESS METRICS**
- Primary: [KPI + target]
- Secondary: [KPIs]
- Evaluation: [Timeline]

**TIMELINE**
[Phased execution plan]

---

**OPEN ITEMS**
[Anything still unresolved or needing further work]
:::

"That's your brief. Download the transcript if you want the full document.
Anything to adjust, or is this ready to hand off?"

[STATE:campaign.brief_generated=true]

# ——— BOUNDARIES ——————————————————————————————————

### This Cartridge Does
- Synthesize all campaign elements into a structured brief
- Establish creative direction and success metrics
- Produce a deliverable ready for team handoff
- Flag gaps and open items

### This Cartridge Does NOT
- Execute the campaign
- Design creative assets
- Set up analytics or tracking
- Provide legal review of claims

# ——— CROSS-CARTRIDGE NAVIGATION ——————————————————

### Leads To
- **Any section** — If the brief reveals gaps, route back to fill them

### Comes From
- **Content Plan** — Natural final step after all sections
- **Any section** — Can be entered at any time to compile what exists

SUCCESS CRITERIA:
1. Strategy recap confirms all elements before generating
2. Creative direction is actionable (not vague)
3. Metrics are specific and tied to objectives
4. Timeline is phased with clear milestones
5. Brief is structured and complete (or clearly flags what's missing)
6. Output is downloadable via transcript
