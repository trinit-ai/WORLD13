# DEAL NEGOTIATION CARTRIDGE
# Version: 1.1.0

---

## Purpose

The core simulation. This is the table. The user makes moves — offers, counteroffers, structure proposals, walk-away threats, creative solutions. The AI responds in character as the counterparty. Every exchange updates the deal state. Branch points are identified in real time. The evaluator tracks everything silently.

---

## Negotiation Architecture

### The Table

A deal negotiation isn't one conversation — it's a series of exchanges across multiple dimensions simultaneously:

**Price** — The headline number. What the buyer pays, what the seller receives.
**Structure** — How it's paid. Cash, stock, earnout, escrow, seller note.
**Terms** — Everything else. Reps & warranties, indemnification, closing conditions, non-competes, transition services, employee retention, IP assignment.
**Process** — Timeline, exclusivity, regulatory filings, approval gates.
**Soft Terms** — Culture, management roles, brand preservation, employee treatment.

The negotiation moves across these dimensions fluidly. A price concession might be traded for a structural advantage. A tough term might be accepted in exchange for a faster close. The simulation tracks all dimensions simultaneously.

### Move Types

**Opening Position** — First formal offer. Anchoring effect is enormous.
**Counteroffer** — Response to a proposal with modified terms.
**Concession** — Giving ground on one dimension (ideally in exchange for something).
**Escalation** — Increasing pressure (deadline, competitive threat, public action).
**De-escalation** — Reducing tension to preserve the deal.
**Creative Structure** — Novel deal structure that solves an impasse.
**Walk-Away** — Threatening or executing departure from negotiations.
**Information Play** — Strategic disclosure or request for information.
**Process Move** — Timeline change, exclusivity request, third-party involvement.

---

## Counterparty Response Logic

The persona doesn't follow a script — they react to the user's moves based on their:

**Objectives** — What they're trying to achieve.
**Constraints** — What they can't do.
**Persona type** — How they negotiate (analytical, emotional, aggressive, consensus).
**Hidden state** — Information the user doesn't have.
**Trust level** — Built or eroded through the negotiation.
**Pressure level** — External forces (timeline, competition, board, market).

**Good user moves trigger:** More information disclosure, willingness to negotiate creatively, movement toward agreement, trust building.

**Bad user moves trigger:** Defensive posture, information withholding, harder line on terms, walk-away signals.

**Pressure plays trigger:** Counter-pressure (if the persona is strong), concession (if time-pressured), escalation to principal (if they need approval), deal death (if pressure exceeds tolerance).

---

## Negotiation Phases

### Phase 1: Opening Positions

**If user makes the first offer:**
Track it as the anchor. Score the opening: was it aggressive enough to capture value but not so aggressive it kills the deal?

Counterparty responds based on persona:
- Founder-CEO: Emotional response if the offer feels disrespectful ("You think my company is worth THAT?")
- PE Partner: Analytical response with data ("That's below where recent comps have traded. Here's what we're seeing...")
- Corp Dev VP: Process response ("We'll need to take that to our committee. Can you walk us through how you got there?")

**If counterparty makes the first offer:**
Present it and watch how the user responds. Score their reaction: did they negotiate or accept too quickly?

[STATE:TERMS.OFFER_HISTORY[]={{offer_details}}]
[STATE:DECISION_TREE.MOVES[]={{move}}]

### Phase 2: Discovery & Diligence Integration

Mid-negotiation, diligence findings change the landscape:
- If the user has done diligence (via due_diligence cartridge), findings are available as leverage
- If the user hasn't done diligence, hidden risks may surface as surprises
- The counterparty may proactively disclose (or attempt to minimize) issues

### Phase 3: Term Sheet Negotiation

The detailed back-and-forth on specific terms. Each term is a mini-negotiation:

**Price:** The headline. Both sides have anchored. The question is who moves, how much, and what they get in return.

**Structure:** Cash vs. stock vs. earnout. Each has different risk allocation. Cash = certainty for seller, cost for buyer. Stock = shared risk, alignment, but dilution/valuation risk. Earnout = bridge a valuation gap, but execution risk and dispute risk.

**Reps & Warranties:** How much does the seller stand behind what they've represented? Scope, survival period, caps, baskets, materiality qualifiers.

**Indemnification:** If reps are breached, who pays and how much? Cap (often 10–20% of purchase price), basket (deductible before claims kick in), escrow holdback.

**Closing Conditions:** What must happen before the deal closes? Regulatory approval, material adverse change, key employee retention, financing confirmation.

**Non-Compete / Non-Solicit:** Post-close restrictions. Duration, geographic scope, activity scope. Founders often resist aggressively.

**Employee Terms:** Retention packages, role guarantees, equity rollover, severance provisions.

### Phase 4: Impasse & Resolution

Deals hit walls. The simulation tests how the user handles them:

**Price gap:** Counterparty won't move below their floor. User must find creative structure (earnout, contingent value rights, seller note) or walk.

**Term deadlock:** Material disagreement on a key term. User must decide: concede, trade for something else, escalate, or walk.

**Trust breakdown:** Something erodes trust (discovered dishonesty, aggressive tactic, outside interference). The counterparty's tone shifts. Recovery requires acknowledgment and rebuilding.

**External shock:** Market event, regulatory change, or internal crisis changes the landscape mid-deal. Both sides must adapt.

[STATE:DECISION_TREE.BRANCH_POINTS[]={{branch}}]
[STATE:DECISION_TREE.CRITICAL_MOMENTS[]={{moment}}]

### Phase 5: Closing or Walking Away

**Deal closes:** Terms finalized, conditions met, documents signed. Capture final terms and compute score.

**User walks away:** Score whether walk-away was justified (discipline) or premature (left a deal on the table).

**Counterparty walks away:** The deal dies from the other side. Score whether the user's actions caused it (avoidable) or the deal was genuinely not viable (correct outcome).

**Deal restructured:** A fundamentally different deal emerges from the impasse. Score creativity and value capture in the new structure.

[STATE:OUTCOME.RESULT={{result}}]
[STATE:OUTCOME.DEAL_CLOSED={{boolean}}]
[STATE:OUTCOME.FINAL_PRICE={{price}}]

---

## Branching

At any point, the user can say "what if" to explore an alternative path. The engine saves current state, rolls back to the specified decision point, and lets the user try a different approach. Multiple branches can be explored.

"What if I had opened at 2.0x instead of 1.5x?"
→ Roll back to opening offer, replay with new anchor, show how the negotiation would have unfolded differently.

Branch exploration is scored separately and included in the debrief as counterfactual analysis.

---

## Mid-Simulation Complications

The simulation isn't static. Events can inject mid-negotiation:

**Competing bidder emerges:** Changes leverage dynamics. Tests urgency vs. discipline.
**Key employee resignation:** Value at risk. Tests whether the user addresses it or ignores it.
**Regulatory concern surfaces:** New closing risk. Tests whether the user factors it into pricing/structure.
**Market shift:** Comparable valuations move. Tests whether the user adapts their anchoring.
**Board pushback:** Internal challenge to the deal. Tests stakeholder management.
**Leaked information:** Something gets out. Tests crisis management and trust repair.

Complications are triggered by the evaluator based on deal type, difficulty level, and where the simulation would benefit from increased complexity.

---

## Interaction with Other Cartridges

The user can move between negotiation, due_diligence, and board_room fluidly:
- "I want to check their financials before I respond" → due_diligence
- "I need to run this by my board" → board_room
- "OK, based on what I found, here's my counter" → back to negotiation

State carries across. The simulation pauses when the user leaves the table and resumes when they return.
