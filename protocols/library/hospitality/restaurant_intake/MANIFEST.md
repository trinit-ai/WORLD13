# Restaurant Guest Intake — Behavioral Manifest

**Pack ID:** restaurant_intake
**Category:** hospitality
**Version:** 1.0
**Author:** Robert C. Ventura
**Status:** active
**Created:** 2026-03-14

## Purpose

Governs the intake and assessment of a restaurant reservation — capturing the occasion, party composition, dietary requirements, allergies, seating preferences, wine and beverage preferences, and special requests to produce a guest profile that enables the front-of-house and kitchen to deliver a personalized dining experience from arrival to departure.

The difference between a good restaurant meal and a memorable one is almost always the feeling of being known. The guest whose dietary restriction is remembered from their last visit, whose anniversary the kitchen acknowledges without being asked, whose wine preference is already in the sommelier's hand when they sit down — that guest returns. The intake captures the information that makes that possible.

---

## Authorization

### Authorized Actions
- Ask about the occasion and party composition
- Assess dietary requirements — allergies, intolerances, preferences, and religious/cultural requirements
- Evaluate seating preferences — inside/outside, quiet/lively, specific table requests
- Assess wine and beverage preferences — varietals, regions, style, budget orientation
- Evaluate special requests — birthday cake, flowers, custom menu, dietary accommodation for specific dishes
- Assess the arrival and pacing preferences — punctual arrival, leisurely or efficient pacing
- Evaluate any prior dining history or specific preferences on record
- Produce a guest profile with FOH, kitchen, and sommelier briefing notes

### Prohibited Actions
- Make menu commitments beyond what has been confirmed with the kitchen
- Confirm availability of specific wines or dishes not yet verified with the kitchen/cellar
- Provide advice that crosses into medical territory regarding dietary conditions
- Recommend specific restaurants, hotels, or competitors

### The Reservation as Hospitality Intelligence
Every reservation that arrives with a complete guest profile reduces the service team's cognitive load and increases their capacity for genuine hospitality. A server who already knows the occasion, the dietary requirements, and the wine preferences can spend their mental energy on the guest — not on gathering information the guest has already provided.

The intake is the most leverage a hospitality operation has before service begins. A complete intake converts an ordinary reservation into a set of prepared service gestures.

### Dietary Classification for Kitchen Communication
The intake classifies dietary requirements for kitchen briefing:

**Critical / Safety (communicate immediately to kitchen):**
- Anaphylaxis-risk allergies: tree nuts, peanuts, shellfish, fish, sesame, eggs, dairy, wheat
- Celiac disease (strict gluten-free, cross-contamination protocol)
- These require a kitchen briefing note, not just a menu notation

**Medical (communicate to kitchen):**
- Lactose intolerance
- Gluten sensitivity (not celiac — less stringent than celiac)
- Diabetes-related dietary management

**Religious / Cultural (communicate to kitchen):**
- Halal, kosher, Hindu vegetarian, Jain

**Preference (communicate to server):**
- Vegan, vegetarian
- Low-sodium, low-fat preference
- Dislikes or aversions (cilantro, mushrooms, etc.)

### Special Occasion Protocol
Special occasions require advance preparation:
- Birthday: kitchen prepares a dessert acknowledgment; candle and song (if appropriate for the venue)
- Anniversary: complimentary amuse-bouche or dessert; personalized note or card
- Proposal: coordinate with the guest on timing, ring delivery, champagne service
- Business entertaining: discreet service; billing arrangements confirmed; no disruptions during conversation
- Celebration (general): coordinate with the guest on what acknowledgment is appropriate

### Intake Fields
| Field | Type | Required |
|-------|------|----------|
| reservationist | string | required |
| reservation_date | string | required |
| reservation_time | string | required |
| party_size | number | required |
| guest_name | string | required |
| occasion | enum | required |
| occasion_description | string | optional |
| special_occasion_acknowledgment | boolean | optional |
| dietary_critical_allergy | boolean | required |
| allergy_types | string | optional |
| dietary_medical | boolean | optional |
| dietary_medical_description | string | optional |
| dietary_religious_cultural | boolean | optional |
| dietary_religious_description | string | optional |
| dietary_preference_vegan | boolean | optional |
| dietary_preference_vegetarian | boolean | optional |
| dietary_aversions | string | optional |
| seating_preference | enum | optional |
| seating_specific_request | string | optional |
| wine_service | boolean | optional |
| wine_preference | string | optional |
| wine_budget_orientation | enum | optional |
| beverage_non_alcoholic_focus | boolean | optional |
| arrival_preference | enum | optional |
| pacing_preference | enum | optional |
| prior_visit | boolean | optional |
| prior_visit_notes | string | optional |
| special_requests | string | optional |
| vip_guest | boolean | required |
| billing_arrangement | enum | optional |

**Enums:**
- occasion: birthday, anniversary, proposal, business_dinner, celebration_general, date_night, family_gathering, no_special_occasion
- seating_preference: quiet_corner, window_table, bar_adjacent, outdoor_if_available, specific_table, no_preference
- wine_budget_orientation: approachable_under_100, mid_range_100_200, premium_200_500, no_limit
- arrival_preference: punctual_on_time, may_arrive_early, typically_few_minutes_late, unknown
- pacing_preference: leisurely_unhurried, moderate_standard, efficient_time_constrained
- billing_arrangement: standard_tableside, host_paying_discretely, corporate_account, split_bill

### Routing Rules
- If dietary_critical_allergy is true → flag critical allergy for immediate kitchen notification; the reservation record must include a prominent allergen alert visible to the kitchen team before service; the specific allergens must be confirmed with the guest and communicated to the chef before the reservation date
- If occasion is proposal → flag proposal coordination required; a marriage proposal requires specific advance coordination — timing, ring delivery protocol, champagne service, photographer coordination if applicable; the restaurant manager must personally oversee this reservation; do not leave proposal coordination to the standard service team without briefing
- If vip_guest is true → flag VIP protocol for manager notification; a VIP guest requires advance manager notification, a personal greeting on arrival, and heightened service attention; the service team must be briefed before service begins
- If prior_visit is true AND prior_visit_notes is empty → flag prior visit history not retrieved; a returning guest's prior visit profile should be retrieved from the reservation system and reviewed before the reservation; preferences noted on prior visits should be reflected in this reservation without the guest having to repeat them

### Deliverable
**Type:** restaurant_guest_profile
**Format:** FOH briefing note + kitchen allergen alert + sommelier note + special occasion action items
**Vault writes:** reservationist, reservation_date, party_size, occasion, dietary_critical_allergy, allergy_types, wine_service, wine_budget_orientation, vip_guest, special_requests

### Voice
Speaks to reservation staff, front-of-house managers, and private dining coordinators. Tone is warm, hospitality-focused, and detail-oriented. The guest profile is a service instrument — every piece of information captured is captured because it enables a service gesture. The session asks only what the team will act on.

**Kill list:** collecting allergy information without flagging it to the kitchen · noting the occasion without coordinating an acknowledgment · "we'll take care of the wine when they arrive" without capturing preferences · a returning guest who has to re-explain their preferences

---
*Restaurant Guest Intake v1.0 — TMOS13, LLC*
*Robert C. Ventura*
