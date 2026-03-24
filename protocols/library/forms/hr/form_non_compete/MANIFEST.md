# Non-Compete Agreement — Pack Manifest

## Purpose

The `form_non_compete` pack guides users through completing a non-compete agreement (also called a covenant not to compete or restrictive covenant). Non-compete agreements restrict an employee's ability to work for competitors or start a competing business for a specified period after leaving the employer. These agreements are used to protect an employer's legitimate business interests, including trade secrets, confidential information, client relationships, and specialized training investments. This pack collects all necessary terms and produces a structured agreement document. The pack assists with form completion only — it does NOT provide legal advice regarding the enforceability, reasonableness, or legality of non-compete terms under any jurisdiction's law.

## Critical State-by-State Warning

**Non-compete enforceability varies dramatically by state.** This is the single most important consideration for this pack. Some states have effectively banned non-competes, others enforce them only under narrow conditions, and the legal landscape is actively shifting. The assistant MUST ask which state's law will govern the agreement before proceeding with any terms, and must note the enforceability landscape for that state without providing legal advice.

Key examples of the current landscape:
- **California**: Non-competes are virtually unenforceable under Business and Professions Code Section 16600, with very narrow exceptions (sale of a business).
- **Oklahoma**: Generally unenforceable except in connection with the sale/dissolution of a business.
- **North Dakota**: Generally unenforceable.
- **Minnesota**: Banned for most employees effective July 2023.
- **Colorado**: Banned for employees earning below a certain threshold, with notice requirements for those above.
- **Washington**: Banned for employees earning below a certain threshold; requires garden leave or independent consideration for others.
- **Illinois**: Banned for employees earning below $75,000/year (indexed).
- **Oregon**: Limited to 12 months maximum, with income thresholds.
- **Massachusetts**: Maximum 12 months, requires garden leave pay or other mutually agreed consideration.
- **FTC**: In 2024, the FTC issued a final rule banning most non-competes nationwide, but enforcement has been challenged in federal court. The legal status remains uncertain as of this writing.

The assistant does not advise on whether a non-compete is enforceable — it documents the employer's desired terms and flags the state-specific context.

## Scope

This pack covers the core terms of a non-compete agreement: party identification, restricted activities, geographic limitations, duration, consideration, and governing law. It does not handle non-solicitation agreements (restricting solicitation of clients or employees), non-disclosure/confidentiality agreements (protecting trade secrets and proprietary information), or invention assignment agreements (assigning employee-created IP to the employer). Those are distinct restrictive covenants that may accompany a non-compete but are documented separately. The pack also does not address garden leave provisions, clawback mechanisms, or injunctive relief terms, which are common in more complex agreements and require legal drafting.

## Autonomy Level

**MEDIATED** — The assistant collects information and structures the agreement, but the deployer must review before any use. Non-compete agreements are legal documents with significant implications for both employers and employees. They must be reviewed by legal counsel before execution. The assistant's output is a structured draft, not a final legal instrument.

## Turn Budget

**8-10 turns.** The agreement requires careful collection of multiple defined terms, each of which has legal significance. The assistant should ensure the employer understands what each term means in plain language while collecting specific, precise inputs. The state-identification step at the beginning is critical and should not be rushed.

## Required Fields

### Party Identification

- **Employee Name**: Full legal name.
- **Employee Position/Title**: Current or offered position. Some states limit non-competes to certain position levels.
- **Employer Name**: Full legal entity name.
- **Effective Date**: When the agreement takes effect. For new hires, typically the start date. For existing employees, the date of execution.

### State of Employment / Governing Law

- **Employee's State**: The state where the employee primarily works. This is the threshold question — the assistant must ask this FIRST before collecting substantive terms.
- **Governing Law**: Which state's law will govern the agreement. Often the employer's state, but the employee's state law may apply regardless of a governing law clause if the employee works there.

The assistant must note: "Non-compete enforceability varies significantly by state. Some states restrict or prohibit non-competes entirely. Legal counsel should review this agreement for enforceability under the applicable state's law."

### Restricted Activities

- **What activities are restricted**: Specific description of the competitive activities the employee is prohibited from engaging in. Must be clearly defined — vague restrictions (e.g., "any competing business") are more likely to be struck down as overbroad.
- **Examples**: Working for a direct competitor, starting a competing business, providing consulting services to competitors in the same market segment. The restriction should be tied to the employer's actual competitive interests, not a blanket prohibition on the employee working in their field.

### Geographic Scope

- **Geographic limitation**: The physical area where the restriction applies. Options include:
  - Specific radius (e.g., "within 50 miles of [employer's office]")
  - Named states, counties, or cities
  - National or regional
  - Defined market/territory

  Narrower geographic scope increases the likelihood of enforceability. Courts routinely strike down non-competes with unreasonable geographic scope. The geographic limitation should match the employer's actual market footprint.

### Duration

- **Length of restriction**: How long the non-compete remains in effect after the employment relationship ends. Common durations range from 6 months to 2 years. Several states cap the maximum duration (e.g., Massachusetts and Oregon at 12 months). Courts generally look more favorably on shorter durations. The assistant should collect the employer's desired duration and note any state-specific caps.

### Consideration

- **What the employee receives in exchange**: A valid non-compete requires consideration — something of value given to the employee in exchange for agreeing to the restriction.
  - **New employees**: The employment itself is generally sufficient consideration.
  - **Existing employees**: Many states require additional consideration beyond continued employment (e.g., a raise, bonus, promotion, stock options, or a specified payment). Some states (Massachusetts) require "garden leave" payment — continued pay during the restricted period.

  The assistant must ask whether this is for a new hire or existing employee and collect the specific consideration being offered.

### Additional Clauses

- **Severability**: A clause stating that if any provision is found unenforceable, the remaining provisions survive. Standard in most agreements.
- **Modification/Blue-Pencil**: Some states allow courts to modify (blue-pencil) overbroad non-competes to make them reasonable rather than voiding them entirely. Others do not. The assistant should note this consideration without advising.

## Conversation Flow

1. **Greeting and state identification**: Explain the purpose of the pack. Immediately ask which state the employee works in and which state's law should govern. Flag state-specific considerations.
2. **Party identification**: Collect employee name, position, employer name, effective date.
3. **New hire vs. existing employee**: Determine whether this is for a new hire or current employee (affects consideration requirements).
4. **Restricted activities**: Define what competitive activities are restricted. Push for specificity.
5. **Geographic scope**: Define the geographic limitation. Note that narrower is generally more enforceable.
6. **Duration**: Collect the desired duration. Note any state-specific caps.
7. **Consideration**: Document what the employee receives in exchange for the restriction.
8. **Additional terms**: Severability, governing law clause, any other terms.
9. **Review**: Present the complete agreement draft for review.
10. **Deliverable generation**: Produce the final structured document.

## Guardrails

- This pack does NOT provide legal advice regarding enforceability.
- The assistant MUST flag state-specific considerations without advising on outcomes.
- The assistant must not advise whether a non-compete is appropriate or necessary for a given position.
- The assistant must not opine on whether terms are reasonable or unreasonable.
- The assistant must clearly note that the output is a structured draft requiring legal review, not a final legal instrument.
- The assistant should note the evolving federal landscape (FTC rule) without predicting outcomes.

## Deliverable

A structured non-compete agreement draft containing all terms, formatted for legal review. The document must include a header noting "DRAFT — REQUIRES LEGAL REVIEW BEFORE EXECUTION." The deployer is responsible for having legal counsel review the agreement before presenting it to the employee for signature.

*Non-Compete Agreement v1.0 — TMOS13, LLC*
*Robert C. Ventura*
