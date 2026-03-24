# Clinical Decision Simulator & Medical Education Platform Roadmap

> From clinical encounter simulator to the most comprehensive AI-powered medical education platform. The flight simulator for medicine.

## The Thesis

Medical education relies on a scarce resource: real patients. Clinical rotations provide unpredictable exposure — you might see 50 pneumonias and never encounter a PE. Standardized patients (actors) cost $200-500/hour, can't simulate abnormal labs, and can't adjust difficulty in real time. Board review is multiple choice — nothing like the ambiguity of a real encounter.

There is no clinical flight simulator. Every pilot logs hundreds of hours in a simulator before carrying passengers. Every physician goes from textbook to real patient with nothing in between except whatever cases they happened to see on rotation.

TMOS13 builds the thing that should already exist.

## Current State: Clinical Decision Simulator (v1.1)

**What exists:**
- Case briefing (user describes scenario or picks from library)
- AI patient with realistic persona, behavioral rules, and progressive disclosure
- Full clinical encounter: history, exam, labs, imaging, treatment
- 4-layer hidden state (will volunteer → requires direct ask → requires trust → will deny unless pressed)
- 7 pre-built cases across specialties and difficulty levels
- 5-dimension scoring (diagnostic accuracy, reasoning, communication, treatment, efficiency)
- Post-encounter debrief with hidden state reveal and clinical teaching points

**What v1.1 adds:**
- SISS fourth wall enforcement — the simulation never coaches, hints, or plays both sides
- EXIS user agency — all clinical decisions are user-driven, system never advances on user's behalf
- Multi-PERSONA separation — Patient, Clinical Environment, and Preceptor voices never bleed
- User-driven cartridge transitions — no auto-advancing between encounter phases
- Toolkit ontology alignment — PERSONA, WORLD, RITUAL, GATE, CELL constructs formalized
- Formatting standardization — cards only at endpoints, plain conversational text during simulation

**What this proves:**
- AI can maintain a patient persona with hidden pathology that only emerges through skilled interviewing
- The disclosure mechanic (trust + right question = information) creates genuine clinical gameplay
- Communication quality can be scored — not just "did you get the diagnosis" but "how did you get there"
- The debrief reveals the gap between what was available and what was captured — powerful teaching tool

---

## Phase 1: Clinical Depth (v1.5)

### 1a. Case Library Expansion
Build a comprehensive case library covering:

**By chief complaint:** Chest pain, abdominal pain, headache, shortness of breath, back pain, fever, altered mental status, dizziness, cough, fatigue, skin rash, joint pain, palpitations, syncope, weakness.

**By diagnosis:** Must-not-miss diagnoses for each specialty. Each case designed with a specific teaching objective and at least one significant hidden state element.

**By teaching focus:** History-taking cases (diagnosis from interview alone), physical exam cases (exam finding changes everything), diagnostic reasoning cases (competing diagnoses, Bayesian reasoning), communication cases (breaking bad news, motivational interviewing, goals of care), ethical cases (autonomy, beneficence, justice, futility), systems cases (handoffs, resource allocation, social determinants).

### 1b. Longitudinal Patient Encounters
Real medicine isn't one visit. Support follow-up encounters (chronic disease management), disease progression over simulated time, medication adjustment based on response, patient adherence tracking across visits, evolving patient-clinician relationship.

### 1c. Procedural Simulation
Narrated procedural walkthroughs with decision points: intubation decision tree, central line placement, lumbar puncture, joint injection. Not hands-on skills training — the cognitive decisions surrounding procedures.

### 1d. Interprofessional Encounters
Clinical care is team-based. Simulate: nurse calling with a concern (SBAR), pharmacist questioning an order, consultant disagreeing with management, social work presenting barriers, multidisciplinary rounds.

---

## Phase 2: The Therapeutics Simulator (v2.0)

Separate from but complementary to the encounter simulator. Focus on treatment decision-making: pharmacology simulator (drug selection, interactions, dose adjustment, stewardship), treatment optimization (diabetes, heart failure, anticoagulation, pain, psych), and the patient factor (adherence barriers, shared decision-making, cost conversations).

---

## Phase 3: Assessment & Certification (v3.0)

Standardized assessment cases for competency evaluation. Board-style clinical vignettes with natural language interface. OSCE simulation (Objective Structured Clinical Examination). Competency dashboards and longitudinal tracking.

---

## Phase 4: Platform (v4.0)

Content marketplace for case authoring. Institutional integration (LMS, EHR simulation). Multi-learner simulation (team-based cases). CME accreditation. Research platform for clinical decision-making studies.

---

## Market Opportunity

**Medical education market:** $50B+ globally. Growing driven by simulation technology and competency-based education.

**Standardized patient programs:** $200-500/hour per actor. Most medical schools spend $500K-2M annually. Limited availability, scheduling constraints, no ability to simulate labs or imaging.

**Board preparation:** $2-3B market. Currently dominated by question banks — multiple choice, not clinical simulation.

**CME / MOC:** $3B+ market. Currently lecture-based, low engagement, low retention.

### Competitive Landscape

No existing product combines: natural conversation (NLP-driven interview, not menu selection), hidden state (patient withholding creates discovery gameplay), progressive disclosure (trust + skill = information), branching diagnostic paths, and comprehensive scoring across five dimensions.

### Unit Economics

A standardized patient encounter costs $200-500 including actor pay, space, evaluator time. A simulation encounter costs <$1 in compute. A medical school running 500 SP encounters/year spends $100-250K. The simulation platform replaces 60-80% of those encounters at a fraction of the cost. The remaining 20-40% (hands-on skills, real human interaction) still requires SPs — but the cognitive training shifts to simulation.
