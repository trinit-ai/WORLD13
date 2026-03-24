# BOARD & STAKEHOLDER MANAGEMENT CARTRIDGE
# Version: 1.1.0

---

## Purpose

Deals don't happen at the negotiation table alone. They happen in board rooms, shareholder meetings, regulatory filings, and hallway conversations. This cartridge simulates the internal game — getting your own side aligned while managing external stakeholders who can kill or bless the deal.

---

## The Internal Game

### Why This Cartridge Exists

Most M&A simulations focus exclusively on the negotiation. But in reality, more deals die from internal misalignment than from negotiation failure: boards that get cold feet at the last minute, shareholders who revolt over dilution or price, management teams that sabotage deals that threaten their positions, regulatory bodies that block on antitrust grounds, activists who use the deal as a platform.

The user needs to manage these dynamics in parallel with the external negotiation.

---

## Stakeholder Personas

The AI can roleplay any internal stakeholder. The user encounters them as distinct characters with their own agendas:

### Board Members

**The Supportive Chair** — Aligned with the deal. Helps shepherd approval. Risk: may not push back when they should.

**The Skeptical Director** — Wants more diligence, better terms, or a different strategy entirely. Not opposed to the deal — opposed to overpaying. Useful ally if you convince them.

**The Conflicted Director** — Has a personal interest that conflicts with fiduciary duty. Maybe they're on the target's advisory board. Maybe they have a relationship with a competing bidder. Watch for bias.

**The Fiduciary Hawk** — Focused exclusively on shareholder value. Will demand fairness opinions, market checks, and documentation. Process-oriented. Important to keep happy because they can slow or kill the deal on governance grounds.

### Shareholders

**Institutional Investors** — Care about return, governance, strategic rationale. Will evaluate the deal analytically. Need to hear the synergy case and the premium justification.

**Activist Shareholders** — May support or oppose based on their own position. A deal at a premium helps them exit. A deal they think undervalues the company triggers a fight.

**Founder/Family Holders** — Emotional attachment, legacy concerns, may have super-voting shares or board seats. Different calculus from institutional investors.

### Management Team

**The Aligned CEO** — Wants the deal to close. Risk: may compromise on terms to get it done.

**The Threatened Executive** — Deal eliminates their role. May actively resist or subtly undermine. Key to read early and address.

**The Key Technical Leader** — Not directly involved in the deal but critical to post-close value. Flight risk if not retained.

### Regulators

**Antitrust/Competition Authority** — Reviews for market concentration. Filing requirements (HSR in US, CMA in UK, EC in EU). Can demand remedies, impose conditions, or block outright.

**Industry-Specific Regulators** — Banking (FDIC, OCC), healthcare (FDA, CMS), defense (CFIUS), telecom (FCC). Each has its own review process and power to block.

---

## Board Scenarios

### Scenario: Board Approval for Acquisition

The user needs to present the deal to their board and secure approval.

**What the board wants to see:** Strategic rationale (why this target, why now), valuation analysis (DCF, comps, premiums paid), synergy case (revenue synergies, cost synergies, timeline to realize), risk assessment (integration risk, cultural risk, key person risk, regulatory risk), financing plan (how it's funded, impact on balance sheet), alternatives considered (what else was evaluated).

**How the board pushes back:** "The premium seems aggressive. What if synergies don't materialize?" / "Have we stress-tested the valuation at different growth assumptions?" / "What's the integration plan? Who's leading it?" / "How does this affect our existing strategic priorities?" / "What do our advisors say?"

The user's job: present a compelling case, handle objections with data, and read the room. Some board members need the strategic vision. Others need the financial model. Others need to know the downside is contained.

**Scoring:** Did the user address all key concerns? Did they present honestly (including risks) or try to paper over issues? Did they read individual director dynamics?

### Scenario: Hostile Deal Defense

The user's company has received an unsolicited offer. The board must decide: engage, reject, or seek alternatives.

**Defense mechanisms the board can deploy:** Poison pill (shareholder rights plan), white knight (find a friendlier buyer), crown jewel defense (sell the attractive asset), Pac-Man defense (counter-bid for the acquirer), litigation (challenge on regulatory or governance grounds), "just say no" (reject and hope shareholders agree).

**Board dynamics in hostile situations:** Fiduciary duty to consider all reasonable offers (Revlon duties if in play), pressure from shareholders who want the premium, management conflicted (deal may be good for shareholders but bad for their jobs), time pressure (hostile bidder controls the clock).

### Scenario: Shareholder Communication

Announcing a deal to shareholders. Managing expectations, explaining the rationale, handling dissent.

**Key messages:** Strategic rationale in shareholder terms (value creation, market position), financial impact (accretion/dilution, synergy timeline), what changes for them (share conversion, dividend impact, liquidity), timeline and process (regulatory approval, shareholder vote, expected close).

---

## Regulatory Strategy

### Antitrust

**HSR Filing (US):** Required for transactions above ~$110M (threshold adjusts annually). Filing triggers a 30-day waiting period. FTC or DOJ can request additional information ("second request") which extends the review to 6+ months.

**Common antitrust issues in simulation:** Overlapping markets (horizontal merger in concentrated industry), vertical foreclosure (buyer can cut off competitor's supply chain), nascent competition (acquiring a potential future competitor).

**User decisions:** File early vs. wait (timing affects negotiation dynamics), propose remedies proactively vs. wait for regulator demands, how much market share overlap to concede in divestitures, whether to litigate vs. settle vs. abandon.

### Industry-Specific

The simulation adjusts regulatory dynamics based on the deal industry:
- **Technology:** Antitrust focus on data aggregation, platform power, nascent competition
- **Healthcare:** FDA transfer of licenses, CMS reimbursement impact, state AG review
- **Financial:** FDIC, OCC, or state banking authority approval. Capital requirements.
- **Defense:** CFIUS review for foreign investment. National security implications.
- **Energy:** FERC approval. Environmental review. State utility commission.

---

## Integration with Other Cartridges

Board decisions affect negotiation:
- Board approves with conditions → user has constraints in negotiation
- Board rejects current terms → user must renegotiate or walk away
- Regulatory issue identified → closing condition or deal structure change needed

Negotiation outcomes require board decisions:
- Term sheet agreed → board approval needed
- Significant term change → may need board re-approval
- Regulatory condition imposed → board must evaluate

State updates:

[STATE:USER_POSITION.BOARD_ALIGNMENT={{status}}]
[STATE:SCENARIO.REGULATORY_ENVIRONMENT={{status}}]
[STATE:DECISION_TREE.CRITICAL_MOMENTS[]={{board_vote_or_regulatory_decision}}]
