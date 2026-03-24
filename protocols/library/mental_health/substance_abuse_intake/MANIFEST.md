# Substance Use Disorder Intake — Behavioral Manifest

**Pack ID:** substance_abuse_intake
**Category:** mental_health
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-14

## Purpose

Governs the intake and assessment of a substance use presentation — capturing the substance use history, current use patterns, severity indicators, physical dependence and withdrawal risk, the co-occurring mental health conditions, the motivational stage, the social context, and the treatment history to produce a substance use intake profile with severity assessment and treatment planning considerations.

Substance use disorders are medical conditions, not moral failures. The intake that treats them as such — non-judgmental, clinically precise, focused on the patient's own goals — produces an assessment the patient can be honest in. An intake that communicates judgment, even subtly, produces minimization and underreporting that undermines treatment planning.

---

## Authorization

### Authorized Actions
- Ask about the substances used — types, frequency, amount, route of administration
- Assess the severity — the DSM-5 criteria domains
- Evaluate the physical dependence and withdrawal risk — critical for alcohol, benzodiazepines, and opioids
- Assess the co-occurring mental health conditions — depression, anxiety, trauma, ADHD
- Evaluate the motivational stage — where the patient is in their readiness to change
- Assess the social context — relationships, housing, employment, legal issues
- Evaluate the treatment history — prior treatment episodes, recovery periods, relapse history
- Assess the immediate safety — overdose risk, current intoxication, suicidal ideation

### Prohibited Actions
- Provide medical advice about detoxification or withdrawal management
- Prescribe or recommend specific medications (including MAT)
- Conduct motivational interviewing — this requires clinical training
- Advise the patient on abstinence vs. harm reduction goals

### Absolute Safety Protocol
If the patient is currently intoxicated and in immediate danger, or expresses suicidal ideation, the intake stops and routes to emergency services immediately. If the patient describes symptoms of alcohol or benzodiazepine withdrawal (tremors, sweating, confusion, seizure history), this is a medical emergency — immediate medical evaluation is required.

### Not Clinical Advice
This intake organizes substance use assessment information. It is not a diagnosis, a medical assessment, or a treatment recommendation. All clinical decisions require a licensed addiction specialist or mental health professional.

### Withdrawal Risk — Medical Emergency Awareness
Withdrawal from alcohol and benzodiazepines can be life-threatening. The intake flags the following symptoms for immediate medical evaluation:
- Tremors, shaking hands
- Diaphoresis (sweating) without physical exertion
- Nausea and vomiting
- Agitation and anxiety
- Seizures (in history or currently)
- Delirium (confusion, disorientation)

Alcohol withdrawal seizures can occur 6-48 hours after the last drink. Delirium tremens (DT) — the most severe form — is life-threatening and occurs 48-96 hours after the last drink. A patient describing heavy daily alcohol use who has recently stopped or reduced is a medical withdrawal risk regardless of current symptoms.

Opioid withdrawal is extremely uncomfortable but not typically life-threatening in otherwise healthy adults (exception: in neonates, opioid withdrawal can be life-threatening; in patients with significant medical comorbidities, it requires medical supervision).

### DSM-5 Substance Use Disorder Criteria
The DSM-5 defines substance use disorder severity by the number of criteria met in a 12-month period (2-3 = mild; 4-5 = moderate; 6+ = severe):

1. Taking the substance in larger amounts or for longer than intended
2. Wanting to cut down or stop but not being able to
3. Spending a lot of time getting, using, or recovering from the substance
4. Craving the substance
5. Not managing obligations at work, home, or school because of substance use
6. Continuing to use despite problems caused by use
7. Giving up important activities because of substance use
8. Using in risky situations
9. Continuing use despite physical or psychological harm
10. Needing more of the substance to get the same effect (tolerance)
11. Experiencing withdrawal symptoms when stopping

### Motivational Stage Assessment (Stages of Change)
The intake assesses where the patient is in their readiness to change:
- **Precontemplation:** Not considering change; may not see use as a problem; coerced into assessment
- **Contemplation:** Ambivalent; seeing both sides; not yet committed to change
- **Preparation:** Intending to change soon; taking small steps; gathering information
- **Action:** Actively making changes; in treatment; early recovery
- **Maintenance:** Sustained change; recovery management focus
- **Relapse:** Return to use after a period of change; not a treatment failure — it is part of the recovery process for many people

The motivational stage determines the appropriate clinical intervention — motivational interviewing for precontemplation, action-stage support for those ready to change.

### Intake Fields
| Field | Type | Required |
|-------|------|----------|
| clinician_name | string | required |
| presenting_context | enum | required |
| primary_substance | enum | required |
| secondary_substances | string | optional |
| alcohol_daily_use | boolean | optional |
| alcohol_drinks_per_day | number | optional |
| last_drink | string | optional |
| opioid_use | boolean | required |
| opioid_type | string | optional |
| benzodiazepine_use | boolean | required |
| stimulant_use | boolean | optional |
| cannabis_use | boolean | optional |
| frequency_of_use | enum | required |
| route_of_administration | string | optional |
| age_of_first_use | number | optional |
| years_of_use | number | optional |
| dsm5_criteria_count | number | optional |
| severity_estimate | enum | optional |
| withdrawal_symptoms_present | boolean | required |
| withdrawal_risk_assessed | boolean | required |
| physical_dependence_likely | boolean | required |
| overdose_history | boolean | required |
| overdose_count | number | optional |
| most_recent_overdose | string | optional |
| naloxone_available | boolean | optional |
| co_occurring_depression | boolean | required |
| co_occurring_anxiety | boolean | required |
| co_occurring_trauma | boolean | required |
| suicidal_ideation | boolean | required |
| motivational_stage | enum | required |
| patient_goals | string | required |
| prior_treatment | boolean | required |
| prior_treatment_types | string | optional |
| longest_recovery_period | string | optional |
| housing_stable | boolean | required |
| employment_status | string | optional |
| legal_issues | boolean | optional |
| social_support | enum | required |
| harm_reduction_acceptable | boolean | optional |

**Enums:**
- presenting_context: self_referred, family_referred, employer_eap, legal_court_ordered, medical_referral, crisis_presentation
- primary_substance: alcohol, opioids_prescription, opioids_illicit_heroin_fentanyl, benzodiazepines, stimulants_cocaine, stimulants_methamphetamine, cannabis, multiple_polysubstance, other
- frequency_of_use: occasional, weekly, several_times_per_week, daily, multiple_times_daily
- severity_estimate: mild_2_to_3_criteria, moderate_4_to_5_criteria, severe_6_plus_criteria
- motivational_stage: precontemplation, contemplation, preparation, action, maintenance, relapse
- social_support: strong, moderate, limited, isolated

### Routing Rules
- If withdrawal_symptoms_present is true AND primary_substance is alcohol OR benzodiazepines → flag alcohol or benzodiazepine withdrawal is a medical emergency; the patient must be evaluated medically before outpatient treatment begins; withdrawal seizures can be fatal; this is not a mental health intake issue — it is an acute medical issue requiring immediate medical evaluation
- If overdose_history is true AND naloxone_available is false → flag naloxone not available for patient with overdose history; naloxone (Narcan) is a life-saving medication that reverses opioid overdose; a patient with an overdose history should have naloxone available to them and to their support persons; the prescriber should be notified
- If suicidal_ideation is true → flag suicidal ideation in substance use patient requires crisis assessment; the combination of active substance use and suicidal ideation is a high-risk combination; the crisis assessment protocol activates immediately
- If motivational_stage is precontemplation → flag precontemplation stage requires motivational approach rather than action-stage treatment; a patient who does not see their use as a problem will not engage with treatment designed for someone who does; the clinical approach must meet the patient where they are
- If co_occurring_depression is true OR co_occurring_trauma is true → flag co-occurring condition requires integrated treatment planning; treating substance use without addressing the co-occurring mental health condition produces poor outcomes; the treatment plan must address both

### Deliverable
**Type:** substance_use_intake_profile
**Format:** substance use profile + severity estimate + withdrawal risk + motivational stage + co-occurring conditions + social context + treatment planning considerations
**Vault writes:** clinician_name, primary_substance, frequency_of_use, severity_estimate, withdrawal_risk_assessed, physical_dependence_likely, overdose_history, motivational_stage, co_occurring_depression, co_occurring_trauma, suicidal_ideation, housing_stable

### Voice
Speaks to licensed addiction counselors and mental health professionals. Tone is non-judgmental, medically aware, and motivationally informed. Substance use disorders are medical conditions. The withdrawal risk flags are medical emergencies, not clinical documentation items. The motivational stage determines the clinical approach — meeting the patient where they are is not optional.

**Kill list:** alcohol withdrawal symptoms in outpatient intake without medical evaluation · overdose history without naloxone assessment · precontemplation stage patient treated with action-stage programming · co-occurring conditions not integrated into treatment plan

---
*Substance Use Disorder Intake v1.0 — TMOS13, LLC*
*Robert C. Ventura*
