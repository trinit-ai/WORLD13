# MENU — CLINICAL DECISION SIMULATOR

## Fresh Session

:::card
**Clinical Decision Simulator**

**Custom Case** — Describe a clinical scenario or choose a specialty
**Case Library** — Pre-built cases from straightforward to ethically complex
:::

---

## Mid-Encounter Menu

:::card
**Case: {{scenario.title}}**

**Patient:** {{patient.name}}, {{patient.age}}{{patient.sex}}
**Chief Complaint:** {{patient.chief_complaint}}
**Setting:** {{scenario.setting}}

**Gathered So Far**
HPI: {{hpi_completeness}}% complete · Social Hx: {{social_complete}} · Meds/Allergies: {{meds_complete}}
Exam: {{exam_systems_checked}} · Tests ordered: {{tests_ordered count}}
Working Dx: {{working_diagnosis || "Not established"}}
:::

---

## Status Screen (Chart View)

:::card
**Clinical Summary — {{patient.name}}**

**Vitals:** {{vital_signs or "Not yet obtained"}}

**History**
CC: {{chief_complaint}}
HPI: {{hpi_summary}}
PMH: {{pmh or "Not gathered"}} · Meds: {{medications or "Not gathered"}} · Allergies: {{allergies or "Not gathered"}}
Social: {{social_hx or "Not gathered"}} · Family: {{family_hx or "Not gathered"}}

**Exam Findings**
{{positive_and_negative_findings or "No exam performed"}}

**Tests**

| Test | Status | Result |
|------|--------|--------|
{{tests_table}}

**Assessment**
Differential: {{current_differential or "Not established"}}
Working Diagnosis: {{working_diagnosis or "Not established"}}
Plan: {{current_plan or "Not established"}}
:::

---

## Help

"Available anytime: say **status** or **chart** to see all findings and your current differential. Say **vitals** for a quick vital signs check, **results** to check pending tests, or **what if** to explore an alternative path. When you're done, say **debrief** for your clinical analysis, or **transcript** to download the complete case report. Or just keep going — ask the patient a question, perform an exam, or order a test."
