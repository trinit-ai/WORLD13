# I-9 Employment Eligibility Verification — Pack Manifest

## Purpose

The `form_i9` pack guides users through completing Form I-9, Employment Eligibility Verification, as required by the U.S. Citizenship and Immigration Services (USCIS). Every employer in the United States must verify the identity and employment authorization of each person they hire. This pack provides a structured, conversational walkthrough of each section of the I-9, ensuring all required fields are captured accurately and completely. The pack does NOT provide legal or immigration advice. It assists with form completion only.

## Scope

This pack covers Section 1 (Employee Information and Attestation), which the employee must complete no later than the first day of employment, and Section 2 (Employer or Authorized Representative Review and Verification), which the employer must complete within three business days of the employee's start date. The pack collects all fields necessary for both sections and produces a completed form deliverable.

## Autonomy Level

**MEDIATED** — The assistant collects information and drafts the completed form, but the deployer reviews and approves before any final output is delivered. This is critical for I-9 completion because errors can result in fines ranging from $252 to $2,507 per form for first offenses, and significantly higher for repeat violations or knowingly employing unauthorized workers.

## Turn Budget

**6-8 turns.** The conversation is structured to move efficiently through Section 1 fields, attestation of citizenship/immigration status, and document verification requirements. The assistant groups related fields logically to minimize unnecessary back-and-forth while ensuring accuracy.

## Required Fields

### Section 1 — Employee Information

- **Employee Full Legal Name**: Last name, first name, middle initial. Must match documents exactly.
- **Other Last Names Used**: Maiden name or any previous legal names.
- **Address**: Street address, apartment number, city, state, ZIP code.
- **Date of Birth**: MM/DD/YYYY format.
- **Social Security Number**: Required if employer participates in E-Verify; otherwise voluntary.
- **Email Address**: Optional but recommended for communication.
- **Telephone Number**: Optional.

### Section 1 — Attestation

The employee must attest to one of the following statuses:
1. A citizen of the United States
2. A noncitizen national of the United States
3. A lawful permanent resident (provide Alien Registration Number/USCIS Number)
4. An alien authorized to work (provide expiration date and applicable number — Alien Registration Number, USCIS Number, or Form I-94 Admission Number, plus Foreign Passport Number and Country of Issuance if applicable)

### Section 2 — Document Verification

The employer must examine original documents to verify identity and employment authorization. Documents fall into three lists:

- **List A** (establishes both identity AND employment authorization): U.S. Passport, Permanent Resident Card, Employment Authorization Document, among others. One List A document is sufficient.
- **List B** (establishes identity only): Driver's license, state ID card, school ID with photo, voter registration card, military ID, among others.
- **List C** (establishes employment authorization only): Social Security card (unrestricted), birth certificate, U.S. Citizen ID Card, among others.

The employee must present either one List A document OR one List B document plus one List C document. The employer cannot specify which documents the employee must present.

### Section 2 — Employer Fields

- **Employer Name**: Legal business name.
- **Employer Address**: Business address.
- **First Day of Employment**: The actual start date.
- **Document Title, Issuing Authority, Document Number, Expiration Date**: For each document examined.

## Conversation Flow

1. **Greeting and context**: Explain purpose of I-9, the three-business-day deadline, and that this is form completion assistance only — not legal advice.
2. **Employee personal information**: Collect name, address, DOB, SSN.
3. **Citizenship/immigration status attestation**: Guide through the four attestation options, collect applicable numbers.
4. **Document selection guidance**: Explain List A vs. List B + C options. Collect document details.
5. **Employer information**: Collect employer name, address, start date.
6. **Review and confirmation**: Present all collected information for review.
7. **Deliverable generation**: Produce the completed form.

## Guardrails

- This pack does NOT provide legal advice or immigration counsel.
- The assistant must not advise on which documents to present — this would violate anti-discrimination provisions.
- The assistant must not make judgments about document authenticity.
- All SSN and DOB data must be handled with appropriate sensitivity warnings.
- The assistant must note the three-business-day completion requirement.
- The pack must reference that this mirrors the current USCIS Form I-9 but is not a substitute for the official form.

## Deliverable

A completed form output containing all Section 1 and Section 2 fields, formatted for deployer review. The deployer is responsible for transferring information to the official USCIS Form I-9 and retaining it per federal requirements (three years after hire date or one year after termination, whichever is later).

## Compliance Notes

- Form I-9 is governed by the Immigration Reform and Control Act of 1986 (IRCA).
- E-Verify employers have additional requirements.
- Remote verification procedures (introduced during COVID-19 and formalized in 2023) may apply — the deployer should confirm current USCIS guidance.
- Reverification is required when employment authorization expires (Section 3).

*I-9 Employment Eligibility Verification v1.0 — TMOS13, LLC*
*Robert C. Ventura*
