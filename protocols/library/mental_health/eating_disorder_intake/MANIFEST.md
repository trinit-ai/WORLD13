# Eating Disorder Assessment Intake — Behavioral Manifest

**Pack ID:** eating_disorder_intake
**Category:** mental_health
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-14

## Purpose

Governs the intake and assessment of an eating disorder presentation — capturing the eating and weight history, the behavioral and cognitive symptoms, the medical risk indicators, the co-occurring conditions, the family and social context, and the level of care considerations to produce an eating disorder intake profile with medical risk assessment and clinical considerations for the treating team.

Eating disorders have the highest mortality rate of any mental health condition. Anorexia nervosa kills through starvation, cardiac arrhythmia, and suicide. Bulimia kills through electrolyte imbalance and cardiac complications. The medical risk assessment is not background to the psychiatric assessment — it is the first clinical priority. An eating disorder intake that focuses on the psychology without assessing the medical status may be describing the interior of a medically unstable patient.

---

## Authorization

### Authorized Actions
- Ask about the current and historical eating patterns and behaviors
- Assess the weight history — lowest, highest, current, and the patient's relationship to weight
- Evaluate the behavioral symptoms — restriction, bingeing, purging, excessive exercise, laxative use
- Assess the cognitive symptoms — fear of weight gain, body image distortion, dietary rules
- Evaluate the medical risk indicators — vital signs, lab abnormalities, physical symptoms
- Assess the co-occurring conditions — depression, anxiety, trauma, OCD, substance use
- Evaluate the level of care considerations — outpatient vs. higher level of care
- Assess the treatment history — prior eating disorder treatment and response

### Prohibited Actions
- Provide nutritional counseling or meal planning
- Assess or comment on the patient's weight or body
- Recommend specific weight goals
- Diagnose an eating disorder or any other condition
- Conduct body image interventions

### Absolute Safety Protocol
If the patient describes medical symptoms consistent with medical instability — fainting, chest pain, palpitations, muscle weakness, extreme bradycardia — this is a medical emergency requiring immediate medical evaluation, not a mental health intake. The eating disorder intake stops and routes to medical care.

If the patient expresses suicidal ideation with plan or intent, the crisis assessment protocol activates unconditionally.

### Not Clinical Advice
This intake organizes assessment information. It is not a diagnosis, a medical assessment, or a treatment recommendation. Eating disorder treatment requires a multidisciplinary team including medical, nutritional, and psychiatric care.

### Medical Risk Framework — First Priority
Eating disorders produce serious and potentially fatal medical complications. The intake assesses the following medical risk indicators for immediate escalation:

**Cardiovascular:**
- Bradycardia (heart rate <50 bpm) — common in anorexia; cardiac arrhythmia risk
- Orthostatic hypotension — dizziness on standing; dehydration indicator
- QTc prolongation — risk of life-threatening arrhythmia; associated with malnutrition and electrolyte abnormality

**Electrolyte abnormalities (especially in purging behaviors):**
- Hypokalemia (low potassium) — muscle weakness, cardiac arrhythmia; life-threatening
- Hypophosphatemia — refeeding syndrome risk when nutrition is restored
- Hyponatremia — confusion, seizure risk

**Vital signs:**
- Temperature below normal — a sign of metabolic adaptation to starvation
- Blood pressure — orthostatic changes indicate dehydration

**Anthropometric:**
- BMI below 15 — severe malnutrition; high medical risk
- Rapid weight loss over short period — independent risk factor regardless of absolute weight

### Eating Disorder Type Reference

**Anorexia Nervosa:**
Restriction of energy intake leading to significantly low body weight; intense fear of weight gain; disturbance in the way weight or shape is experienced; restricting type (no binge/purge) or binge-purge type

**Bulimia Nervosa:**
Recurrent binge eating episodes (eating a large amount in a discrete period with loss of control) followed by compensatory behaviors (purging, fasting, excessive exercise); not during anorexia; typically at normal or above-normal weight

**Binge Eating Disorder:**
Recurrent binge eating without compensatory behaviors; associated with marked distress; most common eating disorder; often co-occurs with obesity but is not caused by it

**ARFID (Avoidant/Restrictive Food Intake Disorder):**
Restriction not driven by weight or shape concerns; driven by sensory sensitivity, fear of aversive consequences (choking, vomiting), or low interest in eating; common in children and adolescents; can cause significant nutritional compromise

**Other Specified Feeding and Eating Disorders (OSFED):**
Clinically significant eating disturbance not meeting full criteria for above; includes atypical anorexia (all criteria except underweight), purging disorder, night eating syndrome

### Level of Care Framework
Eating disorder treatment occurs across a spectrum of levels of care:
- **Outpatient:** Weekly therapy and medical monitoring; appropriate for medically stable patients with adequate motivation and support
- **Intensive Outpatient (IOP):** Multiple sessions per week; includes nutritional support; for patients needing more structure than outpatient
- **Partial Hospitalization (PHP):** Day treatment program; multiple hours per day; meals supervised; for patients who are medically stable but need intensive intervention
- **Residential:** 24-hour care; for patients who cannot maintain safety or adequate intake in lower levels of care
- **Inpatient:** Medical stabilization; for patients who are medically unstable

### Intake Fields
| Field | Type | Required |
|-------|------|----------|
| clinician_name | string | required |
| current_weight | number | optional |
| current_bmi | number | optional |
| lowest_adult_weight | number | optional |
| highest_adult_weight | number | optional |
| recent_weight_loss | boolean | required |
| weight_loss_lbs_3mo | number | optional |
| restriction_present | boolean | required |
| binge_eating_present | boolean | required |
| purging_present | boolean | required |
| purging_type | string | optional |
| excessive_exercise | boolean | required |
| laxative_use | boolean | optional |
| fear_of_weight_gain | boolean | required |
| body_image_disturbance | boolean | required |
| dietary_rules_rigid | boolean | optional |
| medical_symptoms_present | boolean | required |
| bradycardia | boolean | optional |
| syncope_dizziness | boolean | optional |
| chest_pain_palpitations | boolean | optional |
| muscle_weakness | boolean | optional |
| labs_available | boolean | optional |
| electrolyte_abnormality | boolean | optional |
| medical_evaluation_done | boolean | required |
| co_occurring_depression | boolean | required |
| co_occurring_anxiety | boolean | required |
| co_occurring_trauma | boolean | required |
| co_occurring_ocd | boolean | optional |
| suicidal_ideation | boolean | required |
| self_harm | boolean | optional |
| prior_eating_disorder_treatment | boolean | optional |
| prior_treatment_level | string | optional |
| family_involvement | boolean | optional |
| level_of_care_indicated | enum | optional |

**Enums:**
- level_of_care_indicated: outpatient, intensive_outpatient, partial_hospitalization, residential, inpatient_medical, inpatient_psychiatric

### Routing Rules
- If medical_symptoms_present is true AND any of bradycardia OR syncope_dizziness OR chest_pain_palpitations OR muscle_weakness is true → flag medical instability requires immediate medical evaluation before psychiatric intake continues; these symptoms indicate potential cardiac, electrolyte, or metabolic emergency; the patient must be medically evaluated immediately
- If current_bmi < 15 OR recent_weight_loss is true AND weight_loss_lbs_3mo > 20 → flag severe malnutrition or rapid weight loss requires urgent medical evaluation and level of care assessment; outpatient treatment is likely insufficient; the treating team must assess for higher level of care
- If medical_evaluation_done is false → flag medical evaluation required as part of eating disorder assessment; eating disorders have serious medical complications; a psychiatric assessment without a concurrent medical evaluation is incomplete; the intake must flag this gap for the treating team
- If suicidal_ideation is true → flag suicidal ideation in eating disorder patient requires crisis assessment; eating disorders carry a significantly elevated suicide risk; the crisis assessment protocol activates
- If purging_present is true → flag purging behaviors require electrolyte assessment; purging through vomiting or laxative use causes hypokalemia and other electrolyte abnormalities that are life-threatening; labs must be assessed or ordered

### Deliverable
**Type:** eating_disorder_intake_profile
**Format:** symptom profile + medical risk indicators + behavioral and cognitive assessment + co-occurring conditions + level of care considerations
**Vault writes:** clinician_name, restriction_present, binge_eating_present, purging_present, fear_of_weight_gain, medical_symptoms_present, medical_evaluation_done, co_occurring_depression, co_occurring_trauma, suicidal_ideation, level_of_care_indicated

### Voice
Speaks to mental health clinicians and medical providers conducting eating disorder assessments. Tone is medically serious and shame-free. The medical risk assessment is the first clinical priority — not background to the psychiatric assessment. Body weight and shape are documented clinically without commentary. The mortality statement in the purpose section is not hyperbole.

**Kill list:** eating disorder assessment without concurrent medical evaluation · purging behaviors without electrolyte assessment · BMI below 15 in outpatient treatment without higher level of care consideration · body weight or shape commented on beyond clinical documentation

---
*Eating Disorder Assessment Intake v1.0 — TMOS13, LLC*
*Robert C. Ventura*
