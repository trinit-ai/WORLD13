# MENU — M&A NEGOTIATION SIMULATOR
# Version: 1.1.0

---

## Fresh Session

:::card
**M&A Negotiation Simulator**

**Your Deal** — Bring a real or hypothetical transaction and war-game the negotiation
**Pre-Built Scenarios** — Practice with classic deal archetypes from friendly tuck-ins to hostile bids
:::

"Describe your deal situation or pick a pre-built scenario to get started."

---

## Mid-Deal Menu

:::card
**Deal: {{scenario.title}}**

**Your Position**
**Role:** {{user_position.role}} ({{user_position.side}}) · **Objective:** {{user_position.objectives[0]}}
**Walk-away:** {{user_position.walk_away_point || "Not defined"}}

**Counterparty: {{counterparty.name}}**
**Role:** {{counterparty.role}} · **Style:** {{counterparty.persona_type}}
**Known position:** {{last known counterparty stance}}

**Current Terms**
**Offer on table:** {{terms.current_offer || "None yet"}}
**Premium:** {{terms.premium_to_market || "—"}} · **Structure:** {{terms.cash_component || "TBD"}} cash / {{terms.stock_component || "TBD"}} stock
:::

"What's your next move?"

---

## Status Screen (Detailed)

:::card
**Deal Dashboard**

| Dimension | Status |
|-----------|--------|
| Valuation alignment | {{how far apart on price}} |
| Structure agreement | {{cash/stock/earnout status}} |
| Diligence progress | {{what's been investigated}} |
| Regulatory status | {{any filings needed/made}} |
| Board/stakeholder | {{alignment status}} |
| Timeline | {{closing timeline status}} |

**Offer History:** {{chronological list of offers and counteroffers}}

**Branch Points Passed:** {{decision_tree.branch_points count}} · **Critical Moments:** {{decision_tree.critical_moments count}}
:::

---

## Help

"You can say **status** anytime for a full deal dashboard, **what if** to explore an alternative path from any decision point, **debrief** to end the simulation and get your strategic analysis, **transcript** to download the complete deal analysis document, or **reset** to start a new scenario. Or just keep negotiating — tell me your next move and I'll respond in character."
