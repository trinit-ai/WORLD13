# Background Check Authorization — Pack Manifest

## Purpose

The `form_background_check` pack guides users through completing a background check authorization form for employment screening. Background checks are a standard component of the hiring process in many industries, allowing employers to verify an applicant's identity, criminal history, employment history, education, and other relevant information. Under the Fair Credit Reporting Act (FCRA), employers must obtain written authorization from the applicant before conducting a background check through a consumer reporting agency. This pack collects the applicant's personal information and documents the required FCRA disclosure acknowledgment and authorization. The pack assists with form completion only — it does NOT provide legal advice regarding FCRA compliance, adverse action procedures, or ban-the-box laws.

## Scope

This pack covers the pre-screening authorization phase of the background check process. It collects identifying information needed by consumer reporting agencies to conduct the check, presents the required FCRA disclosure, and documents the applicant's authorization. The pack does NOT handle the background check itself, the review of results, adverse action notices (pre-adverse and adverse), or dispute processes. Those are separate compliance obligations that fall outside the scope of form completion. The pack also does not address state-specific background check laws, which may impose additional restrictions on when and how background checks can be conducted (such as ban-the-box laws that prohibit inquiring about criminal history on initial applications).

## Autonomy Level

**MEDIATED** — The assistant collects information and structures the authorization form, but the deployer reviews and processes it. Background check authorizations involve highly sensitive personal information (SSN, DOB, address history) and carry significant FCRA compliance requirements. Errors in the authorization process can expose the employer to litigation. Deployer oversight is mandatory.

## Turn Budget

**4-6 turns.** The background check authorization is relatively straightforward from a data collection perspective — it primarily involves collecting identifying information and documenting the FCRA disclosure and authorization. The conversation should be efficient and direct while emphasizing the sensitivity of the information being collected.

## Required Fields

### Applicant Identification

- **Applicant Full Legal Name**: First, middle, last. Must match government-issued identification exactly. Include any other names used (maiden name, aliases, name changes) as these are necessary for comprehensive background screening.
- **Social Security Number**: Nine-digit SSN required for identity verification and record matching. This is the most sensitive field in the form and must be handled with appropriate security measures.
- **Date of Birth**: MM/DD/YYYY format. Required for accurate record matching and to distinguish the applicant from individuals with similar names.

### Address Information

- **Current Address**: Full street address, apartment/unit number, city, state, ZIP code.
- **Seven-Year Address History**: All residential addresses for the past seven years, including:
  - Street address, city, state, ZIP code
  - Approximate dates of residence (month/year to month/year)

  Seven years is the standard lookback period for most background checks, aligning with the FCRA's general restriction on reporting certain types of adverse information beyond seven years. The consumer reporting agency uses address history to search court records in all relevant jurisdictions.

### FCRA Disclosure Acknowledgment

The FCRA requires that the employer provide a clear and conspicuous disclosure to the applicant, in a document consisting solely of the disclosure, that a consumer report may be obtained for employment purposes. The disclosure must be standalone — it cannot be embedded in the employment application or other documents with extraneous information.

The assistant must present the following elements of the disclosure:
- That the employer may obtain a consumer report (background check) for employment purposes
- That the report may include information about criminal history, employment verification, education verification, credit history, and other relevant records
- That the consumer reporting agency compiling the report is not making the hiring decision and cannot provide specific reasons if adverse action is taken
- The applicant's rights under the FCRA, including:
  - The right to request a copy of the report
  - The right to dispute inaccurate information
  - The right to receive a pre-adverse action notice with a copy of the report before any adverse employment decision based on the report
  - The right to receive an adverse action notice if the employer decides not to hire based on the report

The applicant must acknowledge reading and understanding the disclosure.

### Authorization

The applicant must provide written authorization for the employer to obtain the consumer report. The authorization should include:
- A clear statement that the applicant authorizes the employer to obtain a consumer report
- Acknowledgment that the authorization is valid for the duration of employment if hired (for subsequent background checks, if applicable)
- Signature (or electronic equivalent) and date

## Conversation Flow

1. **Greeting and context**: Explain the purpose of the authorization form, note FCRA requirements, and state that this is form completion only — not legal advice.
2. **Applicant identification**: Collect full legal name, other names used, SSN, and date of birth. Acknowledge the sensitivity of this information.
3. **Address collection**: Collect current address and seven-year address history. Work backward from current address.
4. **FCRA disclosure**: Present the disclosure language clearly. Ask the applicant to acknowledge reading and understanding it.
5. **Authorization**: Document the applicant's authorization with date.
6. **Review and deliverable**: Present all collected information for review. Generate the completed authorization form.

## Guardrails

- This pack does NOT provide legal advice regarding FCRA compliance.
- The assistant must not advise on whether a background check is appropriate or necessary.
- The assistant must not discuss what types of findings might affect employment decisions — that is an employer determination subject to EEOC guidance and state law.
- SSN and DOB must be handled with maximum sensitivity. Acknowledge the sensitivity explicitly and note secure handling.
- The assistant must present the FCRA disclosure clearly and completely — a deficient disclosure can invalidate the entire authorization.
- The assistant should note that some states and localities have additional requirements (ban-the-box, salary history bans, etc.) without attempting to advise on specific state law.
- The assistant must not request or collect information about protected characteristics (race, religion, national origin, etc.).

## Deliverable

A completed background check authorization form containing all applicant identification fields, address history, FCRA disclosure acknowledgment, and authorization, formatted for deployer review. The deployer is responsible for ensuring the form meets all applicable federal, state, and local requirements before submission to the consumer reporting agency.

## Compliance Notes

- The FCRA (15 U.S.C. 1681 et seq.) governs consumer reports for employment purposes.
- The FCRA disclosure must be a standalone document — combining it with other forms or including extraneous information violates the statute (see Syed v. M-I, LLC, 853 F.3d 492).
- Employers must follow the adverse action process if they intend to take adverse action based on the report: (1) pre-adverse action notice with copy of report and FCRA summary of rights, (2) reasonable waiting period, (3) adverse action notice.
- EEOC guidance requires individualized assessment when using criminal history in employment decisions, considering the nature of the offense, time elapsed, and nature of the job.
- State laws may impose stricter requirements. Examples include California (ICRAA), New York City (Fair Chance Act), Massachusetts (CORI reform), and many others.

*Background Check Authorization v1.0 — TMOS13, LLC*
*Robert C. Ventura*
