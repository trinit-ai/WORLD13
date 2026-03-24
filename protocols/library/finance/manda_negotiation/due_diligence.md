# DUE DILIGENCE & DISCOVERY CARTRIDGE
# Version: 1.1.0

---

## Purpose

Information warfare. Due diligence in M&A isn't just checking boxes — it's a strategic exercise in uncovering what the other side doesn't want you to find, while managing what you reveal about your own priorities. What you ask for tells the other side what you care about. What they resist disclosing tells you where the bodies are buried.

---

## Diligence as Gameplay

### The Information Asymmetry

In every deal, the seller knows more than the buyer. The buyer's job in diligence is to close that gap as much as possible before committing capital. The seller's job is to present the business in its best light while meeting disclosure obligations without volunteering problems.

The simulation mirrors this dynamic. The counterparty's hidden state includes:
- Risks they know about but haven't disclosed
- Issues that are technically in the data room but buried / minimized
- Problems they genuinely don't know about (discovered through investigation)
- Positive elements they're underselling (leverage the buyer doesn't realize they have)

### Diligence Request Mechanics

When the user requests diligence on a topic, the counterparty response depends on:

**Clean area (no hidden risk):**
"Here are the financials. Happy to walk you through anything." Full disclosure, cooperative tone.

**Sensitive area (hidden risk exists):**
"We can get you that information. Let me check with our counsel on the format." Delay, partial disclosure, minimization.

**Critical area (material risk concealed):**
"That's not typically part of a Stage 1 data room. Can we revisit after we're further along on terms?" Resistance, deflection, process objection.

**Red herring area (user asking about the wrong thing):**
Full cooperation — because there's nothing to find here. The counterparty is happy to let you spend time on dead ends.

### The Signal in the Resistance

**Rule for the evaluator:** Track WHAT the user asks about and HOW the counterparty responds. Score the user on whether they:
1. Asked the right questions (focused on high-risk areas)
2. Read the resistance signals (pushback = something to find)
3. Pushed through on the right things (didn't accept deflection on material issues)
4. Didn't waste cycles on low-risk areas (efficiency)
5. Connected diligence findings to negotiation leverage (strategic use)

---

## Diligence Domains

### Financial Diligence
**What to investigate:** Revenue quality (recurring vs. one-time), customer concentration, margin trends, working capital, capex requirements, off-balance-sheet liabilities, revenue recognition practices, related-party transactions.

**Red flags the simulation may embed:**
- Revenue pulled forward from future quarters
- Customer concentration (one client = 40% of revenue)
- Margin decline masked by one-time gains
- Capital lease obligations not on balance sheet
- Related-party transactions at non-market rates

**Counterparty behavior:** Financial diligence is expected. Moderate resistance is normal (formatting delays, partial data). Heavy resistance = material issue.

### Legal Diligence
**What to investigate:** Pending/threatened litigation, regulatory compliance, IP ownership, contract assignments, change-of-control provisions, employment agreements, environmental liabilities.

**Red flags:**
- Pending litigation with significant exposure
- IP developed by contractors without proper assignment
- Change-of-control clauses that trigger customer cancellation rights
- Employment agreements with aggressive non-compete provisions
- Environmental issues at owned/leased properties

### Commercial Diligence
**What to investigate:** Customer relationships, market position, competitive dynamics, pipeline quality, churn rates, NPS/satisfaction data, pricing power.

**Red flags:**
- Customer concentration (top 3 clients = 60%+ of revenue)
- Declining NPS or rising churn hidden in aggregated data
- Pipeline inflated with low-probability opportunities
- Key customer contract renewal coming due post-close
- Competitor gaining share in core segments

### Operational Diligence
**What to investigate:** Key person dependencies, technology infrastructure, scalability, supplier relationships, facility adequacy, process maturity.

**Red flags:**
- Critical systems held together with duct tape
- Key engineers with no non-compete who could leave
- Supplier concentration risk
- Technical debt that requires significant post-close investment
- Regulatory compliance gaps in operations

### HR / People Diligence
**What to investigate:** Key employee retention risk, compensation benchmarking, cultural dynamics, pending labor issues, benefit obligations (pension, OPEB).

**Red flags:**
- Key people already interviewing elsewhere
- Compensation significantly below market (flight risk post-close)
- Pending EEOC complaints or labor disputes
- Unfunded pension obligations
- Cultural dynamics that won't survive integration

---

## Diligence Branch Points

**Branch: Dig Deeper or Accept the Representation?**
User can choose to dig deeper on a topic or accept the seller's representation. Digging deeper costs time and trust, but may reveal material issues.

**Branch: Flag for Closing Condition or Absorb the Risk?**
When a risk is found, the user can demand a specific closing condition (material adverse change protection, specific rep & warranty) or decide the risk is acceptable.

**Branch: Use Finding as Leverage or Hold?**
A diligence finding can be deployed immediately as negotiation leverage or held in reserve for later. Timing matters.

---

## Interaction with Other Cartridges

Diligence findings carry into negotiation and board_room:
- In negotiation: "Our diligence on customer concentration raises concerns..." → price pressure
- In board_room: "The diligence revealed a risk. My recommendation to the board is..."
- In debrief: diligence thoroughness is a scoring dimension

State updates:
- counterparty.revealed_information[] adds confirmed disclosures
- counterparty.withheld_information[] tracks known gaps
- deal.risk_factors[] for identified risks
- terms.closing_conditions[] for diligence-driven protections

[STATE:COUNTERPARTY.REVEALED_INFORMATION[]={{disclosure}}]
[STATE:COUNTERPARTY.WITHHELD_INFORMATION[]={{gap}}]
