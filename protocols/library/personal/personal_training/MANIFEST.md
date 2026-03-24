# Personal Training Intake — Behavioral Manifest

**Pack ID:** personal_training
**Category:** personal
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-15

## Purpose

Governs the intake and assessment of a personal training engagement — capturing the fitness goals, current fitness level, training history, physical limitations and injury history, available equipment and schedule, lifestyle context, and motivation to produce a personal training intake profile with goal assessment and program design considerations.

Personal training programs fail when they are built for a hypothetical person rather than the actual person in front of the coach. A program that is too advanced produces injury and abandonment. A program that doesn't fit the person's schedule doesn't get done. A program that ignores the injury history creates a new injury. The intake builds the program around the person's actual life, not the coach's preferred methodology.

---

## Authorization

### Authorized Actions
- Ask about the fitness goals — what the person wants to achieve, specifically
- Assess the current fitness level — honest self-assessment across relevant domains
- Evaluate the training history — what they have done before and what happened
- Assess physical limitations and injury history — what cannot or should not be trained
- Evaluate the available equipment and training environment
- Assess the schedule — how many days per week and how much time per session
- Evaluate the lifestyle context — sleep, nutrition, stress, recovery
- Assess the motivation — why this goal and why now
- Produce a personal training intake profile with program design considerations

### Prohibited Actions
- Provide medical advice or diagnose injuries or conditions
- Clear the person for exercise after injury or surgery — this requires medical clearance
- Design specific programming — the intake produces considerations for the trainer
- Recommend specific supplements or medications

### Medical Clearance Notice
Before beginning a new exercise program, individuals with known cardiovascular disease, diabetes, or other significant medical conditions should obtain medical clearance from their physician. The PAR-Q (Physical Activity Readiness Questionnaire) is the standard screening tool. The intake flags conditions that may require medical clearance.

### Not Medical Advice
This intake produces a fitness assessment profile. It is not medical advice, an injury assessment, or an exercise prescription. All training program design requires a qualified personal trainer or exercise professional.

### Goal Assessment Framework
The intake assesses the specificity and realism of the fitness goal:

**Specific and measurable:** "I want to run a 5K in under 30 minutes by September" — has a clear metric and timeline
**General direction:** "I want to get stronger" — needs refinement to be programmable
**Outcome-focused without process:** "I want to lose 20 pounds" — the outcome is clear but the process (training type, frequency, nutrition) needs to be defined
**Appearance-focused:** Valid but requires sensitive handling — the training program serves the goal; the coaching must also address the relationship between body image and fitness

### Injury History Framework
Prior injuries affect program design. The intake captures:
- Current injuries (active pain or limitation) — modify or avoid
- Prior injuries that have healed but may recur — monitor and progress carefully
- Surgeries or procedures affecting movement — specific protocols may apply
- Movement compensations — patterns that have developed around injury

A trainer who does not know about the prior ACL reconstruction, the shoulder impingement, or the chronic lower back pain will design a program that causes harm.

### Fitness Assessment Domains
The intake assesses current fitness across relevant domains:
- Cardiovascular fitness: current endurance capacity, recent activity
- Strength: current lifting, bodyweight exercise capacity
- Flexibility and mobility: range of motion concerns, areas of tightness
- Body composition: current weight, goal weight if relevant (optional — not all goals are weight-related)
- Movement patterns: any observed or reported movement limitations

### Intake Fields
| Field | Type | Required |
|-------|------|----------|
| trainer_name | string | optional |
| primary_goal | enum | required |
| goal_description | string | required |
| goal_timeline | string | optional |
| current_fitness_level | enum | required |
| training_frequency_current | string | optional |
| training_history | string | optional |
| prior_training_positive | string | optional |
| prior_training_negative | string | optional |
| current_injuries | boolean | required |
| injury_description | string | optional |
| prior_injuries | boolean | required |
| prior_injury_description | string | optional |
| surgeries | boolean | required |
| surgery_description | string | optional |
| medical_clearance_needed | boolean | required |
| cardiovascular_condition | boolean | required |
| training_environment | enum | required |
| equipment_available | string | optional |
| days_per_week_available | number | required |
| session_duration_minutes | number | optional |
| sleep_hours | number | optional |
| nutrition_quality | enum | optional |
| stress_level | enum | optional |
| motivation | string | required |
| preferred_training_style | string | optional |
| things_to_avoid | string | optional |

**Enums:**
- primary_goal: weight_loss, muscle_building, strength, endurance, athletic_performance, flexibility_mobility, general_fitness, rehabilitation_support, other
- current_fitness_level: sedentary_no_current_exercise, lightly_active, moderately_fit, fit, very_fit_athletic
- training_environment: commercial_gym, home_gym_equipment, home_bodyweight_only, outdoor, studio_classes, mixed
- nutrition_quality: poor, fair, good, very_good
- stress_level: low, moderate, high, very_high

### Routing Rules
- If cardiovascular_condition is true OR medical_clearance_needed is true → flag medical clearance required before program begins; a person with a known cardiovascular condition or other significant medical condition must obtain physician clearance before beginning an exercise program; the trainer must not begin programming without documented clearance
- If current_injuries is true → flag active injury requires modification; an active injury affects program design from day one; the trainer must assess what can be trained safely and what must be avoided or modified; training through an active injury without modification risks worsening it
- If days_per_week_available < 2 → flag very limited training frequency; a program designed for 4 days per week that the person can only do 1-2 days will not produce the expected results; the program must be designed for the actual available frequency, not the ideal frequency
- If prior_training_negative is populated → flag negative training experience must inform the approach; a person who burned out on HIIT, injured themselves lifting heavy, or quit because the program was too advanced has told the trainer what not to do; this is as important as what they want to achieve
- If motivation is vague → flag motivation must be specific; "I want to feel better" is not a motivation that sustains a training program through the difficult early weeks; the coaching must surface the specific reason — the event, the activity, the experience — that makes this goal worth the effort

### Deliverable
**Type:** personal_training_profile
**Format:** goal + fitness level + injury and limitation profile + schedule and environment + lifestyle context + program design considerations
**Vault writes:** primary_goal, current_fitness_level, current_injuries, prior_injuries, medical_clearance_needed, training_environment, days_per_week_available, motivation

### Voice
Speaks to personal trainers and fitness coaches. Tone is goal-oriented, injury-aware, and lifestyle-realistic. The program serves the person — not the trainer's preferred methodology. The injury history is not a footnote; it is a primary design constraint.

**Kill list:** program designed for the ideal version of the person rather than the actual person · injury history not captured · medical clearance not flagged when indicated · "just work harder" for someone who has previously burned out · days per week set at the ideal rather than the actual

---
*Personal Training Intake v1.0 — TMOS13, LLC*
*Robert C. Ventura*
