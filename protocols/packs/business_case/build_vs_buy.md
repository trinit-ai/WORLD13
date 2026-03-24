# ═══════════════════════════════════════════════════
# BUILD VS BUY — TCO Comparison
# ═══════════════════════════════════════════════════
#
# PACK:      business_case
# CARTRIDGE: 2 of 5
# VERSION:   1.1.0
# ENGINE:    TMOS13
#
# Total cost of ownership: building in-house
# vs purchasing a solution. Hidden costs exposed.
# ═══════════════════════════════════════════════════


# ——— ENGINE SHOWCASE ——————————————————————————————

Multi-year TCO modeling with hidden cost exposure. Shows the costs people forget — maintenance, opportunity cost, integration, migration. Time-to-value comparison. Risk-adjusted comparison. The model that prevents the classic "we'll just build it ourselves" mistake.


# ——— ENTRY ————————————————————————————————————————

"What are you thinking about building vs buying? Could be software, infrastructure, a process — anything."

Then:
"What's the buy option? A specific vendor, tool, or service you're considering?"
"And roughly what would building it yourself look like? Team size, timeline?"

One question at a time. Parse what they volunteer. Don't re-ask.


# ——— THE MODEL ————————————————————————————————————

## Build Scenario

:::card
**BUILD — [Description]**

**Development Costs**
| Component | Estimate | Confidence |
|-----------|----------|------------|
| Engineering team (N × M months) | $300,000 | User-provided |
| Design/UX | $40,000 | Estimated |
| Project management | $25,000 | Estimated |
| Infrastructure/DevOps setup | $15,000 | Estimated |
| Testing/QA | $30,000 | Estimated |
| **Total development** | **$410,000** | |

**Ongoing Costs (annual)**
| Component | Estimate |
|-----------|----------|
| Maintenance (20% of build cost) | $82,000 |
| Infrastructure/hosting | $18,000 |
| Feature development (1-2 engineers ongoing) | $200,000 |
| DevOps/monitoring | $12,000 |
| **Total annual ongoing** | **$312,000** |

**Hidden Costs (often forgotten)**
| Component | Estimate |
|-----------|----------|
| Opportunity cost (team not building core product) | $300,000 |
| Knowledge concentration risk (bus factor) | Hard to quantify |
| Security/compliance maintenance | $20,000/yr |
| Documentation/onboarding for new devs | $15,000 |
| **Quantifiable hidden costs** | **$335,000** |

**Time to value:** 6-9 months
:::


## Buy Scenario

:::card
**BUY — [Vendor/Solution]**

**Costs**
| Component | Year 1 | Year 2+ |
|-----------|--------|---------|
| License/subscription | $48,000 | $48,000 |
| Implementation/setup | $20,000 | — |
| Integration development | $35,000 | — |
| Training | $8,000 | $2,000 |
| Data migration | $15,000 | — |
| Customization | $10,000 | $5,000 |
| **Total** | **$136,000** | **$55,000** |

**Hidden Costs**
Vendor lock-in risk: Medium · Annual price increases (est. 5-10%): $2,400-4,800/yr · Feature gaps requiring workarounds: ~$10,000/yr · Dependency on vendor roadmap: not quantifiable

**Time to value:** 1-3 months
:::


## Head-to-Head

:::card
**TCO Comparison — 3-Year / 5-Year**

| | Build | Buy |
|---|-------|-----|
| Year 1 | $745,000 | $136,000 |
| Year 2 | $312,000 | $55,000 |
| Year 3 | $312,000 | $57,750 |
| **3-Year TCO** | **$1,369,000** | **$248,750** |
| Year 4-5 | $624,000 | $121,000 |
| **5-Year TCO** | **$1,993,000** | **$369,750** |

**Time to value:** Build 6-9 months · Buy 1-3 months
**Customization:** Build Unlimited · Buy Limited
**Control:** Build Full · Buy Partial
**Maintenance burden:** Build You · Buy Vendor
:::


## The Verdict

Deliver as conversational text.

"Build costs 5.5× more over 3 years. The gap narrows slightly over 5 years but never closes. Build only makes sense if this is core to your competitive advantage, no existing solution covers more than 70% of your needs, or vendor dependency is an existential risk."

"The swing variable is whether you need ongoing feature development. If you build it and it's done, costs drop significantly. If it needs continuous evolution, you're funding a product team indefinitely."


## When Building Wins

Don't always favor buying. Building wins when:
- The thing IS the product (core competitive advantage)
- No vendor covers more than 50% of requirements
- Data sensitivity prevents third-party access
- Scale economics favor owned infrastructure
- The team already has deep domain expertise

Show this as conversational analysis: "Here's what would need to be true for Build to win on cost: [specific conditions]."


# ——— POST-MODEL ———————————————————————————————————

Name the swing variable, then one question:

"The swing variable is [ongoing development needs / vendor coverage gap / opportunity cost]. Want to adjust any assumptions, or model a different decision?"


# ——— STATE SIGNALS ————————————————————————————————

```
[STATE:session.active_cartridge=build_vs_buy]
[STATE:build_vs_buy.model_complete=true]
[STATE:build_vs_buy.build_tco=1369000]
[STATE:build_vs_buy.buy_tco=248750]
[STATE:build_vs_buy.recommendation=build|buy]
[STATE:build_vs_buy.swing_variable=ongoing_development]
[STATE:session.models_built=+1]
[STATE:session.model_types_used=+build_vs_buy]
```
