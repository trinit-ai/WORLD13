# Legal Intake Pack — v1.0.0 → v1.1.0 Changelog

## Summary
Upgraded legal_intake pack to integrate deliverables pipeline awareness, align with updated toolkit documentation, strengthen scoring/integrity, and apply current formatting standards.

---

## manifest.json
- **Version bump:** 1.0.0 → 1.1.0
- **Description updated:** Now mentions case brief generation
- **New feature flag:** `deliverables_pipeline: true`
- **New state fields:** `case.lost_wages`, `case.reporting_date`, `case.warning_signage` — align with fields discovered during Ventura case brief generation
- **New deliverable fields:** `lost_wages`, `warning_signage`, `reporting_delay`, `insurance_status` — extracted from PI intake patterns that appeared in case_brief_ventura but weren't in original manifest
- **Template sections expanded:** 12 sections (was 7) matching realized case brief structure — cover, overview, narrative, liability, damages, scoring, contact, action_plan, followup_emails, transcript, metadata, state_snapshot
- **Reference implementation link:** `reference_implementation: "case_brief_ventura.docx"` added to deliverables block
- **Inbound greeting genericized:** Removed `{firm_name}` placeholder

## master.md
- **Version header:** Updated to v1.1.0
- **NEW: Deliverables Pipeline Awareness section** — How state signals feed the case brief, signal-to-deliverable mapping table, writing guidance for protocol authors
- **NEW: Conversational Integrity section** — Legal-specific manipulation resistance (fishing for advice, pressuring for predictions, claiming special access, seeking document help)
- **Scoring expanded:** Full 6-factor breakdown with point values (was narrative description), explicit scoring thresholds with notification routing tiers (80-100/60-79/40-59/below 40)
- **Card interior formatting:** Added guidance per Formatting Style Guide (middle-dot separators, sectioned cards, no bullets for key-value pairs)
- **Emoji rule clarified:** "legal intake: no emoji"

## boot.md
- **Card formatting:** Returning visitor card uses middle-dot inline layout instead of multi-line
- No structural changes (CRITICAL RULE and boot logic were already correct)

## menu.md
- **Card formatting:** Status/mid-session cards use middle-dot inline layout
- No structural changes

## intake.md
- **NEW: Deliverables Note section** — Explains that intake is a required trigger cartridge, narrative quality guidance
- **Genericized:** State bar referral language (removed bracket placeholders)

## personal_injury.md
- **NEW: Deliverables Note section** — Field-to-brief mapping, specificity guidance, evidence completeness impact
- **New state signals:** `case.warning_signage`, `case.reporting_date`, `case.lost_wages` — align with new manifest fields
- **Premises liability expansion:** Warning signs and condition reporting questions added to evidence section (previously only in sub-type specifics)
- **Genericized:** SLA placeholder → "one business day", state bar referral language
- **Card formatting:** Summary card uses middle-dot inline layout
- **NEW: Scoring Guidance section** — Explicit high/medium/low factor descriptions

## family_law.md
- **NEW: Deliverables Note section** — Sensitivity guidance for briefs, privacy note requirements, key state signal mapping
- **Genericized:** Removed `[firm phone]` placeholder
- **Card formatting:** Summary cards use middle-dot inline layout, sectioned for different matter types
- **NEW: Scoring Guidance section** — Explicit scoring factors by matter type
- **NEW: Tone Notes section** — Family-specific emotional handling guidance

## criminal_defense.md
- **NEW: Deliverables Note section** — Urgency-first brief generation, notification timing for detained clients
- **Genericized:** Removed `[firm phone]` placeholder → "you can call the firm directly"
- **Card formatting:** Summary card uses middle-dot inline layout

## estate_planning.md
- **NEW: Deliverables Note section** — Planning vs. administration brief divergence, key state signal mapping for each path
- **Genericized:** Removed `[firm phone]` placeholder
- **Card formatting:** Summary cards use middle-dot inline layout, separate templates for planning vs. administration
