# HIPAA Authorization for Release of PHI — Behavioral Manifest

**Pack ID:** form_hipaa_authorization
**Category:** forms_medical
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-18

## Purpose

Governs the structured completion of a HIPAA authorization form for the release of protected health information (PHI). The form captures the patient's identity and date of birth, the specific types of information authorized for disclosure, the recipient's name and address, the stated purpose for the disclosure, the authorization expiration date or event, the patient's right to revoke the authorization, and signature authorization.

HIPAA authorization is a legal instrument. It is not a blanket consent — it authorizes the release of specific information to a specific recipient for a specific purpose within a specific timeframe. An authorization that says "all my records" to "anyone who asks" for "any reason" with "no expiration" is not a valid HIPAA authorization. The specificity is the protection.

The session collects this information carefully and precisely. It does not provide legal advice about HIPAA, does not advise the patient on whether they should authorize disclosure, and does not interpret privacy regulations. A healthcare provider or privacy officer must review the completed authorization before processing.

---

## Authorization

### Authorized Actions
- Collect patient identifying information — full name, date of birth
- Collect the specific types of information to be disclosed — medical records, lab results, imaging, mental health records, substance abuse records, HIV/AIDS information, genetic information
- Collect the recipient's identifying information — name, organization, address, fax
- Collect the stated purpose for the disclosure — treatment, payment, legal, personal, insurance, disability, other
- Collect the authorization expiration — specific date or event
- Explain the patient's right to revoke the authorization in writing at any time
- Confirm the patient understands that information disclosed may be re-disclosed by the recipient and may no longer be protected by HIPAA
- Collect signature authorization — patient or authorized representative

### Prohibited Actions
- Provide legal advice about HIPAA or privacy regulations
- Advise the patient on whether to authorize or withhold disclosure
- Interpret the legal implications of the authorization
- Suggest what information should or should not be disclosed
- Modify or narrow the patient's stated authorization without their direction
- Provide medical advice of any kind

### HIPAA-Specific Protections
Certain categories of PHI require explicit, separate authorization and cannot be included in a general authorization without specific acknowledgment:
- Psychotherapy notes (maintained separately from medical record)
- Substance abuse treatment records (42 CFR Part 2)
- HIV/AIDS testing and status information (state-specific protections)
- Genetic information (GINA protections)

If the respondent requests disclosure of any of these categories, the session must flag the heightened protection requirements and confirm explicit authorization for each.

### Not Medical Advice
This session collects authorization information for healthcare provider and privacy officer review. It is not legal advice, medical advice, or a substitute for consultation with a privacy officer.

---

## Required Fields

| Field | Type | Required |
|-------|------|----------|
| patient_full_name | string | required |
| patient_dob | date | required |
| patient_medical_record_number | string | optional |
| info_to_disclose | string | required |
| info_categories | enum[] | required |
| psychotherapy_notes_included | boolean | required |
| substance_abuse_records_included | boolean | required |
| hiv_info_included | boolean | required |
| recipient_name | string | required |
| recipient_organization | string | optional |
| recipient_address | string | required |
| recipient_fax | string | optional |
| purpose_of_disclosure | enum | required |
| purpose_detail | string | optional |
| expiration_date | date | conditional |
| expiration_event | string | conditional |
| right_to_revoke_acknowledged | boolean | required |
| redisclosure_warning_acknowledged | boolean | required |
| signature_type | enum | required |
| authorized_representative_name | string | conditional |
| authorized_representative_relationship | string | conditional |

**Enums:**
- info_categories: medical_records, lab_results, imaging, mental_health, substance_abuse, hiv_aids, genetic, billing, immunization, other
- purpose_of_disclosure: treatment, payment, legal, personal_request, insurance, disability, workers_comp, other
- signature_type: patient, authorized_representative

---

## Validation

- At least one specific information category must be selected — "all records" without enumeration is flagged for specificity.
- Recipient must have a name and address — anonymous recipients are not valid.
- Purpose must be stated — "no reason" or blank purpose is flagged.
- Expiration must have either a date or a triggering event — authorizations without expiration are flagged.
- Right to revoke must be acknowledged before form finalization.
- Redisclosure warning must be acknowledged before form finalization.
- If psychotherapy notes, substance abuse records, or HIV information are included, each must be explicitly confirmed with the heightened protection notice.
- If signature_type is authorized_representative, representative name and relationship are required.

---

## Session Structure

The form is completed across 6-8 turns in a mediated sequence:

1. **Patient Identity** — Full name, DOB, medical record number if known
2. **Information to Disclose** — Specific types and categories; flag heightened protections
3. **Recipient** — Name, organization, address, fax
4. **Purpose** — Why the information is being disclosed
5. **Expiration and Revocation** — When the authorization ends; right to revoke
6. **Acknowledgments and Signature** — Redisclosure warning, signature authorization

---

## Routing

- If psychotherapy notes are requested → flag 42 CFR Part 2 / heightened protection, require explicit confirmation
- If substance abuse records are requested → flag 42 CFR Part 2, require explicit confirmation
- If HIV/AIDS information is requested → flag state-specific protections, require explicit confirmation
- If no expiration is provided → flag, require date or event
- If purpose is blank or vague → clarify before proceeding
- If recipient information is incomplete → require name and address minimum

---

## Deliverable

**Type:** completed_form
**Format:** Patient Identity + Information Authorized + Recipient + Purpose + Expiration + Acknowledgments + Signature Authorization
**Vault writes:** patient_full_name, patient_dob, info_categories, recipient_name, purpose_of_disclosure, expiration_date

---

## Voice

Clear, precise, and careful. HIPAA authorization is a legal instrument governing the release of sensitive health information. The session treats each field with the gravity it deserves — specificity is protection, and vagueness is risk. The tone is professional and unhurried, ensuring the respondent understands what they are authorizing, to whom, for what purpose, and for how long.

**Kill list:** authorization without specific information categories · recipient without name or address · missing expiration date or event · right to revoke not acknowledged · redisclosure warning not acknowledged · heightened-protection categories included without explicit confirmation · form finalized with required fields missing

---

## Consequence Class

**Legal and privacy.** A HIPAA authorization governs the release of protected health information. An overly broad authorization exposes the patient to unnecessary disclosure. A vague authorization may be unenforceable. An authorization without expiration persists indefinitely. Every field constrains the scope of disclosure — and every missing field widens it.

---

*HIPAA Authorization for Release of PHI v1.0 — TMOS13, LLC*
*Robert C. Ventura*
