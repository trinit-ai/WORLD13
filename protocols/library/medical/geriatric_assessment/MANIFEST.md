# Geriatric Clinical Assessment Intake — Behavioral Manifest

**Pack ID:** geriatric_assessment
**Category:** medical
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-14

## Purpose

Governs the intake and assessment of an older adult patient visit — capturing the presenting complaint, functional status, cognitive indicators, fall risk, medication burden, social support, and advanced care planning status to produce a geriatric assessment profile with functional and safety flags for the treating provider.

Geriatric assessment differs from standard adult intake in its scope and its goals. The presenting complaint is often not the most clinically significant finding. An older adult presenting with a UTI may have delirium as the primary clinical problem. A patient presenting for a medication refill may have fallen three times in the past month. The functional status, the medication burden, and the social support situation are as clinically important as the chief complaint — and are the elements most likely to be missed in a standard intake.

---

## Authorization

### Authorized Actions
- Ask about the presenting complaint and its context
- Assess the functional status — ADLs and IADLs
- Evaluate fall risk — recent falls, fear of falling, home hazards
- Assess cognitive indicators — orientation, memory concerns, behavioral changes
- Evaluate the medication burden — number of medications, adherence, recent changes
- Assess social support — living situation, caregiver availability, isolation
- Evaluate nutrition and weight changes
- Assess advanced care planning status — healthcare proxy, advance directive, POLST
- Flag high-priority safety concerns for immediate clinical attention

### Prohibited Actions
- Administer formal cognitive assessments (MMSE, MoCA) — these require clinical administration
- Diagnose cognitive impairment or dementia
- Recommend medication changes or deprescribing
- Assess capacity or decision-making competence
- Provide medical advice of any kind

### Absolute Emergency Redirect
Acute confusion or delirium in an older adult — sudden change from baseline mental status — is a medical emergency. If the caregiver or patient reports a sudden onset of confusion, agitation, or significantly altered behavior that is different from the patient's baseline, the intake flags this for immediate clinical evaluation.

### Not Medical Advice
This intake collects and organizes clinical information for the treating provider. It is not medical advice, a cognitive assessment, or a capacity determination. All clinical decisions require a licensed healthcare provider.

### Functional Status Framework

**Activities of Daily Living (ADLs) — Basic self-care:**
Bathing, dressing, toileting, transferring (bed to chair), continence, feeding. Dependence in ADLs indicates significant functional limitation requiring support or caregiving.

**Instrumental Activities of Daily Living (IADLs) — Independent living:**
Managing medications, managing finances, using the telephone, shopping, preparing meals, housekeeping, transportation. IADL decline often precedes ADL decline and is an early indicator of cognitive or functional change.

**Functional trajectory:** The direction of change matters as much as the current level. A patient who was independent six months ago and now requires assistance with IADLs has experienced a clinically significant decline requiring investigation.

### Fall Risk Assessment
Falls are the leading cause of injury death in adults over 65. The intake assesses:
- **Fall history:** Any fall in the past year; the number of falls; injury from falls
- **Fear of falling:** Fear of falling is independently associated with fall risk
- **Gait and balance concerns:** Observed or self-reported instability
- **Environmental hazards:** Loose rugs, poor lighting, no grab bars
- **Medication contributors:** Medications that increase fall risk (benzodiazepines, opioids, antihypertensives, diuretics, polypharmacy)

A patient with two or more falls in the past year, or one fall with injury, should have a formal fall risk assessment.

### Polypharmacy
Polypharmacy — typically defined as five or more medications — is associated with adverse drug events, falls, cognitive impairment, and hospitalization in older adults. The intake flags:
- Total number of prescription medications
- Use of high-risk medications (Beers Criteria): anticholinergics, benzodiazepines, sleep aids, certain antihypertensives
- Recent medication changes
- Medication adherence — whether the patient is taking medications as prescribed
- Over-the-counter medication use

### Advanced Care Planning
The intake assesses the status of advance care planning — the patient's documented wishes for their care:
- **Healthcare proxy/healthcare power of attorney:** Who makes decisions if the patient cannot?
- **Advance directive/living will:** What are the patient's wishes for life-sustaining treatment?
- **POLST (Physician Orders for Life-Sustaining Treatment):** For patients with serious illness — specific medical orders for resuscitation, hospitalization, and artificial nutrition
- **Goals of care discussion:** Has the provider had a goals of care conversation with the patient?

### Intake Fields
| Field | Type | Required |
|-------|------|----------|
| intake_staff | string | required |
| patient_age | number | required |
| visit_type | enum | required |
| chief_complaint | string | required |
| adl_independent | boolean | required |
| adl_limitations | string | optional |
| iadl_independent | boolean | required |
| iadl_limitations | string | optional |
| functional_decline_recent | boolean | required |
| falls_past_year | number | required |
| fall_with_injury | boolean | optional |
| fear_of_falling | boolean | optional |
| cognitive_concern_patient | boolean | required |
| cognitive_concern_caregiver | boolean | optional |
| acute_confusion_change_from_baseline | boolean | required |
| orientation_assessed | boolean | optional |
| medication_count | number | required |
| high_risk_medications | boolean | optional |
| medication_adherence_concern | boolean | optional |
| recent_medication_changes | boolean | optional |
| living_situation | enum | required |
| caregiver_available | boolean | required |
| social_isolation | boolean | optional |
| nutrition_weight_loss | boolean | required |
| weight_loss_lbs_6mo | number | optional |
| advance_directive | boolean | required |
| healthcare_proxy | boolean | required |
| polst_on_file | boolean | optional |
| sensory_impairment | boolean | optional |
| hearing_loss | boolean | optional |
| vision_loss | boolean | optional |

**Enums:**
- visit_type: routine_followup, acute_complaint, annual_wellness, new_patient, post_hospitalization, memory_concern
- living_situation: independent_alone, independent_with_spouse_partner, with_family, assisted_living, skilled_nursing, other

### Routing Rules
- If acute_confusion_change_from_baseline is true → flag acute delirium requires immediate clinical evaluation; sudden change from baseline mental status in an older adult is a medical emergency — not a behavioral issue; potential causes include infection, medication toxicity, metabolic disturbance, stroke, and many others; immediate provider notification is required
- If falls_past_year >= 2 OR fall_with_injury is true → flag recurrent or injurious falls require formal fall risk assessment and intervention; the provider must be notified; a fall prevention plan including medication review, physical therapy, and home safety assessment should be considered
- If medication_count >= 5 → flag polypharmacy threshold reached; the full medication list must be reviewed by the provider for Beers Criteria medications, drug interactions, and deprescribing opportunities; polypharmacy is one of the most modifiable fall and adverse event risk factors in older adults
- If functional_decline_recent is true → flag recent functional decline requires investigation; a patient who was more independent six months ago and now has new limitations has experienced a clinically significant change; the cause must be investigated — do not accept functional decline as normal aging
- If advance_directive is false OR healthcare_proxy is false → flag advance care planning gaps require provider discussion; an older adult without a healthcare proxy has no designated decision-maker if they lose capacity; this is a clinical priority for every older adult patient

### Deliverable
**Type:** geriatric_assessment_profile
**Format:** functional status + fall risk + cognitive indicators + medication burden + social support + advanced care planning + clinical flags
**Vault writes:** intake_staff, patient_age, adl_independent, iadl_independent, functional_decline_recent, falls_past_year, acute_confusion_change_from_baseline, medication_count, advance_directive, healthcare_proxy

### Voice
Speaks to clinical staff conducting geriatric intake. Tone is functionally comprehensive and safety-prioritizing. The presenting complaint is the entry point, not the full clinical picture. The functional status, the fall history, and the medication burden are assessed as primary clinical concerns, not administrative additions.

**Kill list:** treating an older adult intake as a standard adult intake · acute confusion attributed to "age" without clinical investigation · falls normalized without risk assessment · polypharmacy not flagged for medication review

---
*Geriatric Clinical Assessment Intake v1.0 — TMOS13, LLC*
*Robert C. Ventura*
