# FMLA Leave Request — Pack Manifest

## Purpose

The `form_fmla` pack guides users through completing a leave request under the Family and Medical Leave Act (FMLA). FMLA provides eligible employees with up to 12 workweeks of unpaid, job-protected leave per year for specified family and medical reasons, with continuation of group health insurance coverage under the same terms as if the employee had not taken leave. This pack collects all information needed to initiate an FMLA leave request, including employee and employer identification, leave type, duration, scheduling details, and certification requirements. The pack assists with form completion only — it does NOT provide legal advice, interpret FMLA eligibility, or make determinations about whether a specific situation qualifies for FMLA protection.

## Scope

This pack covers the employee's initial leave request documentation. It collects the information typically required on Department of Labor forms WH-380-E (Certification of Health Care Provider for Employee's Serious Health Condition), WH-380-F (Certification of Health Care Provider for Family Member's Serious Health Condition), and WH-381 (Notice of Eligibility and Rights & Responsibilities). The pack does NOT complete the physician certification itself — that must be completed by the healthcare provider. The pack identifies when physician certification is required and documents that requirement. It also does not handle state-specific family leave laws (such as California CFRA, New York PFL, etc.), which may provide additional or different protections.

## Autonomy Level

**MEDIATED** — The assistant collects information and structures the leave request, but the deployer (typically HR) reviews and processes the request. FMLA requests involve sensitive medical information, eligibility determinations, and legal compliance obligations. Errors in processing can expose the employer to liability. Deployer oversight is essential at every stage.

## Turn Budget

**6-8 turns.** The FMLA request is structured but not overly complex from a data collection perspective. The assistant must efficiently gather employee information, leave type, dates, and certification requirements. The key is accuracy and completeness, not extensive conversation.

## Eligibility Requirements

Before collecting leave details, the assistant should confirm basic eligibility awareness (though the actual eligibility determination is made by the employer/HR):

- **12 months of employment**: The employee must have worked for the employer for at least 12 months (need not be consecutive).
- **1,250 hours**: The employee must have worked at least 1,250 hours during the 12-month period immediately preceding the leave.
- **Employer size**: The employer must have at least 50 employees within a 75-mile radius.

The assistant collects the employee's self-reported tenure and notes that HR will confirm eligibility. The assistant does NOT make eligibility determinations.

## Required Fields

### Employee Information

- **Employee Name**: Full legal name.
- **Employee ID**: If applicable.
- **Department**: Organizational unit.
- **Position/Title**: Current role.
- **Date of Hire**: For eligibility reference.
- **Contact Information**: Phone and email for communication during leave.

### Employer Information

- **Employer Name**: Legal business name.
- **Employer Address**: Business address.
- **HR Contact**: Name and contact for the HR representative handling the request.

### Leave Details

- **Leave Type**: The qualifying reason for FMLA leave. The assistant presents the eligible categories:
  1. **Birth and bonding**: Birth of a child and bonding with the newborn within one year of birth.
  2. **Placement for adoption or foster care**: Placement of a child for adoption or foster care and bonding within one year of placement.
  3. **Employee's own serious health condition**: A serious health condition that makes the employee unable to perform essential job functions.
  4. **Family member's serious health condition**: Care for a spouse, child, or parent with a serious health condition.
  5. **Qualifying exigency**: A qualifying exigency arising from a spouse, child, or parent being on covered active duty or called to covered active duty in the Armed Forces.
  6. **Military caregiver leave**: Care for a covered servicemember with a serious injury or illness (up to 26 workweeks in a single 12-month period).

- **Leave Start Date**: Requested first day of leave. For foreseeable leave, the employee must provide at least 30 days advance notice. For unforeseeable leave, notice must be provided as soon as practicable.

- **Leave Duration**: Expected length of leave in days or weeks, up to the 12-week maximum (26 weeks for military caregiver leave).

- **Continuous or Intermittent**: Whether the leave will be taken as a continuous block or on an intermittent/reduced schedule basis. Intermittent leave is available for the employee's own serious health condition or to care for a family member with a serious health condition when medically necessary.

- **Intermittent Schedule** (if applicable): Expected frequency and duration of intermittent absences (e.g., "twice per week for physical therapy appointments, approximately 3 hours each").

### Family Member Information (if applicable)

- **Family Member Name**: If leave is to care for a family member.
- **Relationship**: Must be spouse, child, or parent (FMLA does not cover siblings, grandparents, or in-laws unless they stood in loco parentis).

### Certification Requirements

- **Physician Certification Required**: Yes/No. Certification is required for leave based on a serious health condition (employee's own or family member's). The employer may require the certification within 15 calendar days.
- **Certification Form**: Reference the applicable DOL form (WH-380-E for employee's condition, WH-380-F for family member's condition).
- **Recertification**: Note that the employer may request recertification in certain circumstances (every 30 days, upon changed circumstances, or if duration/frequency differs from certification).

## Conversation Flow

1. **Greeting and context**: Explain the purpose of FMLA, note the basic eligibility requirements, and state that this is form completion only — not legal advice.
2. **Eligibility awareness**: Confirm the employee's awareness of the 12-month/1,250-hour/50-employee requirements. Note that HR will make the formal determination.
3. **Employee and employer information**: Collect names, IDs, department, contact details.
4. **Leave type**: Present the qualifying reasons and collect the applicable category.
5. **Leave scheduling**: Collect start date, duration, continuous vs. intermittent, and intermittent details if applicable.
6. **Family member information**: If applicable, collect name and relationship.
7. **Certification**: Identify whether physician certification is required and document the requirement.
8. **Review and deliverable**: Present all collected information for review. Generate the completed request form.

## Guardrails

- This pack does NOT provide legal advice or interpret FMLA provisions.
- The assistant must not determine eligibility — that is the employer's responsibility.
- The assistant must not request specific medical diagnoses. FMLA certification asks about the serious health condition, but the leave request itself does not require a diagnosis.
- The assistant must handle all medical information with sensitivity and note that FMLA medical records must be kept in a separate confidential file, not the regular personnel file.
- The assistant should note that employees cannot be retaliated against for requesting or taking FMLA leave.
- State-specific leave laws may provide additional protections — the assistant should note this without attempting to advise on state law.

## Deliverable

A completed FMLA leave request form containing all employee, employer, and leave detail fields, formatted for HR review and processing. The document identifies certification requirements and applicable DOL forms. The deployer is responsible for issuing the formal eligibility notice (WH-381) and designation notice (WH-382) within the required timeframes.

## Compliance Notes

- FMLA is codified at 29 U.S.C. 2601 et seq. and regulated under 29 C.F.R. Part 825.
- Employers must post the FMLA general notice (WH-1420) in a conspicuous place.
- Employers must provide the eligibility notice (WH-381) within five business days of the employee's request or the employer's knowledge of a qualifying reason.
- Employers must provide the designation notice (WH-382) within five business days of having enough information to determine FMLA qualification.

*FMLA Leave Request v1.0 — TMOS13, LLC*
*Robert C. Ventura*
