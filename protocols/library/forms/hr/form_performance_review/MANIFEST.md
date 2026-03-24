# Employee Performance Review — Pack Manifest

## Purpose

The `form_performance_review` pack guides users through completing a structured employee performance review. Performance reviews are a cornerstone of talent management, providing documented evaluation of an employee's work over a defined period. This pack produces a comprehensive review document that captures competency ratings with specific examples, goal achievement status, identified strengths, actionable development areas, forward-looking SMART goals, and an overall performance rating. The pack assists with form completion and structuring — it does NOT provide management advice, legal counsel regarding employment decisions, or HR policy guidance.

## Scope

This pack covers the complete performance review cycle documentation, including identification of the employee and reviewer, the review period, competency-based evaluation with behavioral examples, retrospective goal assessment, qualitative strengths and development areas, prospective goal-setting using the SMART framework, overall rating, and signature blocks. The pack is designed to be organization-agnostic — it uses common competency categories that can be adapted to any company's review framework. It does not handle performance improvement plans (PIPs), disciplinary documentation, or compensation adjustment recommendations, though the completed review may inform those processes.

## Autonomy Level

**MEDIATED** — The assistant collects information and structures the review document, but the deployer (typically a manager or HR representative) reviews and approves before the document is finalized. Performance reviews are sensitive employment documents that may be used in promotion, compensation, and separation decisions. Accuracy, fairness, and appropriate tone are critical, making deployer oversight essential.

## Turn Budget

**10-12 turns.** Performance reviews are inherently detailed and require more conversation than a simple data-entry form. The assistant must collect not just ratings but specific behavioral examples, contextualized strengths, actionable development items, and well-formed goals. Rushing this process produces superficial reviews that fail to serve their purpose. However, the assistant should group related items efficiently and avoid unnecessary padding.

## Required Fields

### Identification

- **Employee Name**: Full legal name or name as used in company records.
- **Employee Title/Position**: Current job title.
- **Department**: Organizational unit.
- **Reviewer Name**: The person conducting the review (typically direct manager).
- **Reviewer Title**: Reviewer's position.
- **Review Period**: Start and end dates defining the evaluation window.

### Competency Ratings

The review evaluates the employee across core competencies. Each competency receives a rating AND at least one specific behavioral example. Ratings use a standard scale:

1. **Does Not Meet Expectations** — Performance consistently falls below requirements.
2. **Partially Meets Expectations** — Performance meets some but not all requirements.
3. **Meets Expectations** — Performance consistently fulfills role requirements.
4. **Exceeds Expectations** — Performance frequently surpasses requirements.
5. **Significantly Exceeds Expectations** — Performance is exceptional and consistently above requirements.

Standard competency categories (adaptable per organization):
- **Job Knowledge/Technical Skills**: Mastery of role-specific skills and knowledge.
- **Quality of Work**: Accuracy, thoroughness, and attention to detail.
- **Productivity/Efficiency**: Volume of work and effective use of time and resources.
- **Communication**: Written and verbal clarity, active listening, information sharing.
- **Teamwork/Collaboration**: Working effectively with colleagues, contributing to team goals.
- **Initiative/Problem Solving**: Proactive identification and resolution of issues.
- **Reliability/Dependability**: Attendance, punctuality, follow-through on commitments.
- **Leadership** (if applicable): Guiding, mentoring, and developing others.

Each rating must be accompanied by at least one concrete, observable example from the review period. Vague statements like "does a good job" are insufficient. Examples should describe specific situations, actions, and outcomes.

### Goal Achievement

For each goal set during the previous review period (or at the start of the current period):
- **Goal description**: What was the goal.
- **Status**: Met, partially met, not met, or no longer applicable.
- **Evidence/Notes**: What was accomplished, what obstacles arose, what the outcome was.

If no prior goals were set, note this and proceed to strengths.

### Strengths (Specific)

At least three specific strengths observed during the review period. Each strength must reference concrete behaviors, accomplishments, or contributions — not generic personality traits. The assistant should prompt the reviewer for specificity if initial responses are vague.

### Development Areas (Actionable)

At least two development areas with actionable recommendations. Each must include:
- **What needs improvement**: The specific skill, behavior, or knowledge gap.
- **Why it matters**: How improvement would benefit the employee's performance or career.
- **Recommended action**: A concrete step the employee can take (training, mentoring, practice, etc.).

Development areas should be framed constructively. They are opportunities for growth, not punitive observations.

### Next Period Goals (SMART)

At least three goals for the upcoming review period, each following the SMART framework:
- **Specific**: Clearly defined outcome.
- **Measurable**: Quantifiable or objectively verifiable.
- **Achievable**: Realistic given role and resources.
- **Relevant**: Aligned with role responsibilities and organizational objectives.
- **Time-bound**: Has a defined deadline or milestone schedule.

### Overall Rating

A single overall rating using the same 1-5 scale. The overall rating should reflect the holistic evaluation and does not need to be a mathematical average of competency ratings. The reviewer should explain the rationale for the overall rating.

### Comments and Signatures

- **Reviewer Comments**: Open-ended section for additional context, commendation, or guidance.
- **Employee Comments**: Space for the employee to respond to the review (completed after the employee reads the review).
- **Signatures**: Both reviewer and employee sign with date. The employee's signature acknowledges receipt of the review, not necessarily agreement with its contents.

## Conversation Flow

1. **Greeting and context**: Explain the review structure, note this is a documentation tool — not management advice.
2. **Identification**: Collect employee and reviewer names, titles, department, review period.
3. **Competency ratings — batch 1**: Rate the first set of competencies with examples.
4. **Competency ratings — batch 2**: Rate remaining competencies with examples.
5. **Goal achievement**: Review previous period goals and their status.
6. **Strengths**: Identify and document specific strengths with evidence.
7. **Development areas**: Identify areas for growth with actionable recommendations.
8. **Next period goals**: Set SMART goals for the upcoming period.
9. **Overall rating**: Assign the holistic rating with rationale.
10. **Reviewer comments**: Capture any additional narrative.
11. **Review and confirmation**: Present the complete review for accuracy check.
12. **Deliverable generation**: Produce the completed review document.

## Guardrails

- This pack does NOT provide management advice or HR policy guidance.
- The assistant must not suggest specific ratings — all ratings come from the reviewer.
- The assistant should prompt for specificity when examples are vague but not fabricate examples.
- The assistant must not make employment recommendations (promotion, termination, compensation changes).
- Language should be professional, objective, and free of bias.
- The assistant should flag if development areas lack actionable recommendations and prompt the reviewer to add them.

## Deliverable

A completed performance review document containing all sections, formatted professionally for deployer review. The document should be suitable for inclusion in the employee's personnel file.

*Employee Performance Review v1.0 — TMOS13, LLC*
*Robert C. Ventura*
