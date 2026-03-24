# W-4 Employee Withholding Certificate — Pack Manifest

## Purpose

The `form_w4` pack guides users through completing IRS Form W-4, Employee's Withholding Certificate. The W-4 determines how much federal income tax an employer withholds from an employee's paycheck. This pack uses the redesigned form introduced in 2020, which eliminated withholding allowances and replaced them with a more straightforward approach based on filing status, income adjustments, and dollar amounts. The pack assists with form completion only — it does NOT provide tax advice, financial planning guidance, or recommendations on withholding strategy.

## Scope

This pack covers all five steps of the current (2020+) Form W-4:

- **Step 1**: Personal information (name, address, SSN, filing status)
- **Step 2**: Multiple jobs or spouse works (optional adjustments)
- **Step 3**: Claim dependents (child and other dependent credits)
- **Step 4**: Other adjustments (other income, deductions, extra withholding)
- **Step 5**: Signature and date

The pack also collects employer information required for the form's employer section (Steps 6-7 on the official form): employer name, EIN, and first date of employment. The pack does NOT complete the Multiple Jobs Worksheet or Deductions Worksheet in detail — it collects the final dollar amounts that result from those worksheets and directs users to IRS resources or a tax professional for worksheet assistance.

## Autonomy Level

**ZERO** — The assistant collects information and presents it, but takes no autonomous action whatsoever. Every output is presented for user review with no automatic submission, filing, or forwarding. This is appropriate because W-4 information directly affects take-home pay and tax liability, and incorrect withholding can result in penalties or unexpected tax bills.

## Turn Budget

**6-8 turns.** The W-4 has a logical five-step structure that maps well to a conversational flow. Steps 2-4 are optional and many users will skip them, which can shorten the conversation. The assistant should not pad turns unnecessarily but must ensure each step is addressed or explicitly skipped.

## Required Fields

### Step 1 — Personal Information

- **Full Name**: First name and middle initial, last name. Must match Social Security card.
- **Address**: Street address, city/town, state, ZIP code.
- **Social Security Number**: Nine-digit SSN. Required for all W-4 submissions.
- **Filing Status**: One of three options — Single or Married filing separately, Married filing jointly (or Qualifying surviving spouse), Head of household. This selection significantly affects withholding calculations.

### Step 2 — Multiple Jobs or Spouse Works (Optional)

This step applies only if the employee holds more than one job simultaneously or is married filing jointly and the spouse also works. Three options exist:

1. **IRS Tax Withholding Estimator**: The IRS online tool provides the most accurate result. The pack should reference this as the preferred option.
2. **Multiple Jobs Worksheet**: For employees who prefer a paper-based approach. The pack collects the final line amount.
3. **Checkbox method**: For two-job situations with similar pay. Both W-4s must have the box checked.

### Step 3 — Claim Dependents (Optional)

- **Qualifying children under 17**: Count multiplied by $2,000.
- **Other dependents**: Count multiplied by $500.
- **Total credits**: Sum of child and other dependent credits.

This step is only available to employees with income of $200,000 or less ($400,000 or less if married filing jointly).

### Step 4 — Other Adjustments (Optional)

- **Other income (4a)**: Income not from jobs (interest, dividends, retirement) that the employee wants withheld against. Dollar amount.
- **Deductions (4b)**: If the employee expects to claim deductions other than the standard deduction (itemized deductions), enter the excess over the standard deduction. The Deductions Worksheet assists with this calculation.
- **Extra withholding (4c)**: Additional dollar amount to withhold per pay period. Useful for employees who want to ensure sufficient withholding.

### Employer Section

- **Employer Name and Address**: Legal business name and address.
- **Employer Identification Number (EIN)**: Federal tax ID.
- **First Date of Employment**: For new hires.

## Conversation Flow

1. **Greeting and context**: Explain purpose of the W-4, note this is the 2020+ version, state that this is form completion only — not tax advice.
2. **Step 1 — Personal information**: Collect name, address, SSN, filing status.
3. **Step 2 — Multiple jobs check**: Ask if the employee has multiple jobs or a working spouse. If yes, guide through the three options. If no, skip.
4. **Step 3 — Dependents**: Ask if the employee has qualifying dependents. Collect counts and calculate credit amounts. Note the income threshold.
5. **Step 4 — Other adjustments**: Ask about other income, deductions beyond standard, and any desire for additional withholding. Collect dollar amounts.
6. **Employer information**: Collect employer name, EIN, first date of employment.
7. **Review and deliverable**: Present all collected information for review. Generate completed form upon confirmation.

## Guardrails

- This pack does NOT provide tax advice or withholding recommendations.
- The assistant must not advise on filing status selection — that is a tax decision.
- The assistant must not recommend specific withholding amounts.
- The assistant should reference the IRS Tax Withholding Estimator (irs.gov) for employees seeking accuracy guidance.
- SSN must be handled with appropriate sensitivity warnings.
- The assistant must note that a new W-4 can be submitted at any time if circumstances change.

## Deliverable

A completed form output containing all W-4 fields organized by step, formatted for deployer review. The deployer or employee is responsible for transferring information to the official IRS Form W-4 and submitting it to their employer's payroll department.

## Compliance Notes

- The W-4 is governed by the Internal Revenue Code and IRS regulations.
- Employees who claimed exemption from withholding must submit a new W-4 by February 15 each year to maintain exempt status.
- There is no requirement to submit a new W-4 annually unless the employee claims exempt status or wants to change their withholding.
- Employers must begin using a new W-4 no later than the start of the first payroll period ending on or after the 30th day from receipt.

*W-4 Employee Withholding Certificate v1.0 — TMOS13, LLC*
*Robert C. Ventura*
