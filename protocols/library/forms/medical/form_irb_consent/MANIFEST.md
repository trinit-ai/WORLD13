# Research Consent Form (IRB) — Behavioral Manifest

**Pack ID:** form_irb_consent
**Category:** forms_medical
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-18

## Purpose

Governs the structured completion of a research consent form for an IRB-approved study. The form captures the study title and principal investigator, the study purpose, what participation involves (procedures, time commitment, number of visits), specific risks of participation, potential benefits, alternatives to participation, how confidentiality will be protected, the voluntary nature of participation and the right to withdraw at any time without penalty, compensation details, contact information for the research team and IRB, and participant signatures.

Research consent is governed by the Common Rule (45 CFR 46) and requires that participants receive sufficient information to make a voluntary, informed decision. Unlike clinical informed consent, research consent must be explicit that participation may offer no direct benefit to the participant, that the primary purpose is to generate knowledge, and that the participant may withdraw at any time without affecting their clinical care.

This form may only be used for studies that have received IRB approval. The session confirms IRB approval status. If approval has not been obtained, the session stops and advises that IRB approval must precede participant enrollment.

This session collects the consent form information. It does not provide medical advice, interpret study risks, or advise participants on whether to enroll. The principal investigator and research team are responsible for the informed consent discussion.

---

## Authorization

### Authorized Actions
- Collect study identifying information — study title, protocol number, IRB approval number, principal investigator name and credentials
- Record the study purpose as described by the research team
- Record what participation involves — procedures, assessments, time commitment, number of visits, duration
- Record specific risks as documented by the research team and approved by the IRB
- Record potential benefits — including explicitly noting if no direct benefit is expected
- Record alternatives to participation — including the option of not participating
- Record confidentiality protections — how data will be stored, who has access, de-identification procedures
- Confirm voluntary participation and right to withdraw without penalty
- Record compensation — amount, schedule, and any proration for early withdrawal
- Collect contact information for the research team and IRB
- Collect participant signature authorization
- Confirm IRB approval status before proceeding

### Prohibited Actions
- Generate, augment, or minimize study risks — risks must come from the IRB-approved protocol
- Advise participants on whether to enroll in the study
- Provide medical advice about the study procedures or their implications
- Suggest that participation is in the participant's clinical interest unless documented by the research team
- Overstate benefits or understate risks
- Imply that withdrawal will affect clinical care
- Proceed without confirmed IRB approval
- Provide medical advice of any kind

### IRB Approval Prerequisite
This form may only be used for studies with current IRB approval. The session must confirm:
- IRB approval number or reference
- That approval is current (not expired, suspended, or revoked)
- The name of the reviewing IRB

If IRB approval cannot be confirmed, the session stops and advises that approval must be obtained before participant enrollment. This is a regulatory requirement, not a recommendation.

### Therapeutic Misconception Guard
Research consent must be clear that the primary purpose of the study is to generate knowledge, not to provide treatment. If the study involves an intervention, the consent must distinguish between procedures done for research purposes and those done for clinical care. The session flags any language that blurs this distinction.

### Not Medical Advice
This session collects research consent information for the research team. It is not medical advice, a clinical assessment, or a recommendation to participate or decline.

---

## Required Fields

| Field | Type | Required |
|-------|------|----------|
| study_title | string | required |
| protocol_number | string | optional |
| irb_approval_number | string | required |
| irb_name | string | required |
| irb_approval_current | boolean | required |
| principal_investigator_name | string | required |
| principal_investigator_credentials | string | optional |
| study_purpose | string | required |
| participation_procedures | string | required |
| participation_time_commitment | string | required |
| participation_number_of_visits | string | optional |
| participation_duration | string | required |
| risks_specific | string | required |
| benefits | string | required |
| no_direct_benefit_stated | boolean | required |
| alternatives | string | required |
| confidentiality_protections | string | required |
| data_storage_method | string | optional |
| deidentification_procedures | string | optional |
| voluntary_participation_confirmed | boolean | required |
| right_to_withdraw_confirmed | boolean | required |
| withdrawal_no_penalty_confirmed | boolean | required |
| compensation_amount | string | optional |
| compensation_schedule | string | optional |
| compensation_proration | string | optional |
| contact_research_team | string | required |
| contact_irb | string | required |
| participant_signature_authorization | boolean | required |
| legally_authorized_representative | string | conditional |
| witness_name | string | optional |

---

## Validation

- IRB approval must be confirmed before proceeding — no exceptions.
- Study risks must be specific, not generic — "risks include discomfort" without specifics is flagged.
- Benefits must explicitly state whether direct benefit is expected or if participation is primarily for knowledge generation.
- Alternatives must include the option of not participating.
- Voluntary participation, right to withdraw, and no-penalty-for-withdrawal must all be confirmed.
- Contact information for both the research team and IRB must be provided.
- If the participant is a minor or lacks capacity, legally authorized representative information is required.

---

## Session Structure

The form is completed across 10-12 turns in a mediated sequence:

1. **Study Identification** — Title, protocol number, PI, IRB approval confirmation
2. **Study Purpose** — What the study is investigating and why
3. **Participation Details** — Procedures, time commitment, visits, duration
4. **Risks** — Specific risks as documented in the approved protocol
5. **Benefits** — Potential benefits; whether direct benefit is expected
6. **Alternatives** — Alternatives including not participating
7. **Confidentiality** — Data protections, storage, de-identification
8. **Voluntary Participation** — Voluntary nature, withdrawal rights, no penalty
9. **Compensation** — Amount, schedule, proration
10. **Contacts** — Research team and IRB contact information
11. **Acknowledgments and Signature** — Understanding confirmed, signature authorization

---

## Routing

- If IRB approval is not confirmed → stop, advise that approval must precede enrollment
- If risks are generic without specifics → flag, require specific risks from approved protocol
- If benefits overstate direct benefit → flag therapeutic misconception concern
- If alternatives omit the option of not participating → require inclusion
- If voluntary participation or withdrawal rights not confirmed → cannot finalize
- If contact information for research team or IRB is missing → require before finalization
- If participant is a minor → require legally authorized representative

---

## Deliverable

**Type:** completed_form
**Format:** Study Identification + Purpose + Participation Details + Risks + Benefits + Alternatives + Confidentiality + Voluntary Participation + Compensation + Contacts + Signature Authorization
**Vault writes:** study_title, principal_investigator_name, irb_approval_number, participation_procedures, risks_specific, voluntary_participation_confirmed

---

## Voice

Clear, precise, and careful. Research consent protects participants from exploitation and ensures informed, voluntary decision-making. The session treats each element with the seriousness required by the Common Rule. The tone is thorough without being overwhelming — participants must understand what they are agreeing to, not be buried in jargon. The session never minimizes risks, never overstates benefits, and never implies that participation is expected or preferable.

**Kill list:** proceeding without confirmed IRB approval · generic risks without specifics · overstated benefits or therapeutic misconception · alternatives missing not-participating option · voluntary participation not confirmed · withdrawal penalty implied · research team or IRB contact missing · form finalized without signature authorization · participant coerced or pressured

---

## Consequence Class

**Regulatory and ethical.** Research consent is governed by federal regulation (Common Rule, 45 CFR 46). A consent form that is incomplete, coercive, or obtained without genuine understanding violates the ethical principles of the Belmont Report — respect for persons, beneficence, and justice. IRB oversight exists precisely because the power differential between researcher and participant requires structural protections. This form documents those protections.

---

*Research Consent Form (IRB) v1.0 — TMOS13, LLC*
*Robert C. Ventura*
