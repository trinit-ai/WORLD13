# Employment Offer Letter — Pack Manifest

## Purpose

The `form_offer_letter` pack guides users through creating a structured employment offer letter for a prospective new hire. Offer letters are a critical step in the hiring process, formally extending the terms of employment to a selected candidate. A well-constructed offer letter sets clear expectations for both the employer and the candidate regarding position, compensation, benefits, start date, and employment conditions. This pack collects all necessary information and produces a professional offer letter document. The pack assists with form completion and document structuring only — it does NOT provide legal advice regarding employment contracts, labor law compliance, or the legal enforceability of offer letter terms.

## Scope

This pack covers the creation of a standard employment offer letter, including candidate and position identification, compensation details, benefits overview, at-will employment statement (for at-will states), contingencies on which the offer is conditioned, the offer's expiration date, and signature blocks for both employer and candidate. The pack is designed for standard full-time or part-time employment offers. It does not handle independent contractor agreements, executive employment agreements with complex compensation structures (equity, deferred compensation, golden parachutes), union/CBA positions, or international employment offers, which involve substantially different legal frameworks.

## Autonomy Level

**MEDIATED** — The assistant collects information and drafts the offer letter, but the deployer (typically HR or a hiring manager) reviews and approves before the letter is sent to the candidate. Offer letters have legal implications — they can create binding obligations, and inaccurate or poorly worded terms can lead to disputes. Deployer review ensures accuracy, legal compliance, and alignment with organizational policies.

## Turn Budget

**8-10 turns.** Offer letters require collecting information across multiple categories — candidate details, position details, compensation, benefits, conditions, and terms. The assistant should group related fields logically while ensuring each section receives sufficient attention. Compensation and benefits sections often require the most back-and-forth to capture accurately.

## Required Fields

### Candidate Information

- **Candidate Full Name**: Legal name as it will appear on employment documents.
- **Candidate Address**: Mailing address for the formal letter.

### Position Details

- **Position Title**: The exact job title being offered.
- **Department**: Organizational unit or team.
- **Reporting To**: The name and title of the direct manager/supervisor.
- **Employment Type**: Full-time, part-time, or temporary. Include expected hours per week if part-time.
- **Work Location**: Office location, remote, hybrid. If hybrid, specify expected in-office schedule.
- **Start Date**: The proposed first day of employment.

### Compensation

- **Compensation Type**: Salary (exempt) or hourly (non-exempt). This classification has legal implications under the Fair Labor Standards Act (FLSA) regarding overtime eligibility, but the pack does not advise on classification — it documents the employer's stated classification.
- **Compensation Amount**: Annual salary or hourly rate, stated clearly.
- **Pay Frequency**: Weekly, bi-weekly, semi-monthly, or monthly.
- **Overtime**: If non-exempt, note that overtime will be paid in accordance with applicable federal and state law.
- **Bonus/Commission**: If applicable, describe any bonus structure, commission plan, or variable compensation. Note whether discretionary or guaranteed, and any conditions.
- **Sign-On Bonus**: If applicable, amount and any repayment conditions (e.g., must repay if the employee leaves within 12 months).

### Benefits Summary

The offer letter should include a high-level benefits overview, not exhaustive plan details. Common elements:

- **Health Insurance**: Medical, dental, vision availability. Note any waiting period (e.g., "eligible after 30 days of employment").
- **Retirement**: 401(k) or other retirement plan availability, including any employer match.
- **Paid Time Off**: Vacation days, sick leave, personal days. State the annual allotment or accrual rate.
- **Holidays**: Number of paid holidays per year.
- **Other Benefits**: Life insurance, disability insurance, tuition reimbursement, professional development, employee assistance program, etc.

Note that specific plan details, coverage levels, and costs are typically provided in separate benefits documentation, not the offer letter itself.

### At-Will Statement

For employers in at-will employment states (which is most of the United States), the offer letter must include a clear at-will employment statement. Example language:

> "Your employment with [Employer] is at-will, meaning that either you or the company may terminate the employment relationship at any time, with or without cause or notice. This offer letter does not constitute a contract of employment for any specified period."

The assistant should include this statement unless the employer specifically indicates the position is governed by a contract or collective bargaining agreement. Montana is the only state that does not follow at-will employment by default — the assistant should note this if the employer is Montana-based.

### Contingencies

Conditions on which the offer is contingent. Common contingencies include:

- **Background check**: Successful completion of a background investigation.
- **Drug screening**: Passing a pre-employment drug test (where legally permissible).
- **Reference check**: Satisfactory professional references.
- **Education/credential verification**: Verification of degrees, certifications, or licenses.
- **I-9 verification**: Proof of employment eligibility (required by law for all new hires).
- **Non-disclosure/non-compete agreements**: Execution of any required agreements.
- **Physical examination**: For positions with physical requirements.

The offer letter should clearly state that the offer is conditioned on successful completion of all listed contingencies and that the employer reserves the right to withdraw the offer if any contingency is not met.

### Offer Expiration

- **Expiration Date**: The date by which the candidate must accept or decline the offer. A reasonable timeframe is typically 5-10 business days. The letter should state that the offer expires if not accepted by this date unless extended in writing by the employer.

### Signature Blocks

- **Employer Signature**: Name, title, and signature line for the authorized company representative.
- **Candidate Signature**: Name, acceptance statement ("I accept the terms of this offer"), signature line, and date line.

## Conversation Flow

1. **Greeting and context**: Explain the purpose of the offer letter, note that this is form completion — not legal advice.
2. **Candidate information**: Collect candidate name and address.
3. **Position details**: Collect title, department, manager, employment type, location, start date.
4. **Compensation**: Collect salary/hourly rate, classification, pay frequency, bonus/commission details.
5. **Benefits overview**: Collect high-level benefits information.
6. **At-will statement**: Confirm at-will employment applies (or document contract/CBA terms).
7. **Contingencies**: Identify all conditions on which the offer is contingent.
8. **Expiration date**: Set the offer acceptance deadline.
9. **Review and refinement**: Present the draft offer letter for review and refinement.
10. **Deliverable generation**: Produce the final offer letter document.

## Guardrails

- This pack does NOT provide legal advice regarding employment law or contract terms.
- The assistant must not advise on FLSA classification (exempt vs. non-exempt) — it documents the employer's stated classification.
- The assistant must not advise on compensation levels, benefits competitiveness, or market rates.
- The assistant should include the at-will statement by default for U.S. employers and note its importance, but should not provide legal interpretation.
- The assistant must not promise employment terms beyond what the employer authorizes.
- Language should be professional, clear, and welcoming while remaining precise on terms.

## Deliverable

A completed employment offer letter formatted as a professional document, suitable for printing on company letterhead or sending electronically. The letter should be comprehensive, clearly organized, and ready for deployer review and candidate delivery.

*Employment Offer Letter v1.0 — TMOS13, LLC*
*Robert C. Ventura*
