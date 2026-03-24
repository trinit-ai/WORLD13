# Lead Qualification Pack — v1.1.0

> AI-powered inbound lead qualification — discovery conversations, scored leads, AE routing, with auth-gated sales training mode.

**Pack ID:** `lead_qualification`
**Category:** Verticals (CRM)
**Base:** Public-facing
**Version:** 1.1.0 · February 2026

---

## What This Pack Does

An inbound SDR that qualifies leads through conversation, not forms. Prospects chat naturally, the AI runs structured discovery (BANT/MEDDPICC), scores the lead, and produces a handoff summary that makes the AE's first meeting productive from minute one.

For internal teams, the same pack includes an auth-gated training mode where the AI plays realistic buyer personas while scoring the rep's discovery technique.

---

## Files

| File | Purpose |
|------|---------|
| `manifest.json` | Pack metadata, cartridges, state schema, notifications, theme |
| `master.md` | Identity, voice, scoring rubrics, formatting rules, domain boundaries |
| `boot.md` | First-message handling, greeting variants, edge cases |
| `menu.md` | Menu screens (public, authenticated, mid-conversation, training) |
| `triage.md` | Intent detection and routing — first-touch qualification |
| `discovery.md` | BANT/MEDDPICC discovery — the core qualification conversation |
| `product_fit.md` | Capability matching, objection handling, fit assessment |
| `booking.md` | Scheduling, AE routing, handoff summary generation |
| `training.md` | Auth-gated sales training — AI-as-prospect roleplay with scoring |

---

## Configuration Variables

This pack is a deployable template. Before going live, search-and-replace these tokens across all `.md` files:

| Variable | Description | Used In | Example |
|----------|-------------|---------|---------|
| `[Product]` | Product or platform name | boot, triage, product_fit, menu | "Acme CRM" |
| `[Company]` | Company / vendor name | master, boot | "Acme Inc." |
| `[ICP]` | Ideal customer profile description | triage, product_fit | "B2B SaaS companies, 50–500 employees" |
| `[Pricing]` | Starting price or pricing summary | boot, triage | "$49/seat/month" |
| `[Scheduling_Link]` | Calendly or booking URL (optional) | booking | "https://calendly.com/acme/demo" |

If a variable doesn't apply to your deployment, rephrase the surrounding sentence to remove it naturally rather than leaving a blank placeholder.

---

## Cartridge Flow

```
Prospect arrives
      │
      ▼
   TRIAGE ─── identify intent, route
      │
      ├── ready to buy ──────────────────► BOOKING
      ├── specific question ─────────────► PRODUCT FIT
      ├── evaluating / researching ──────► DISCOVERY
      │                                       │
      │                                       ▼
      │                                  PRODUCT FIT
      │                                       │
      │                                       ▼
      └──────────────────────────────────► BOOKING
                                              │
                                              ▼
                                     Handoff Summary → AE
```

State carries across cartridges. Information collected in triage isn't re-asked in discovery.

---

## Qualification Scoring

100-point composite across six dimensions:

| Dimension | Range | What It Measures |
|-----------|-------|-----------------|
| Budget | 0–20 | Budget allocated, range known, approval status |
| Authority | 0–20 | Decision-making power, buying process clarity |
| Need | 0–20 | Pain specificity, quantified impact, failed prior attempts |
| Timeline | 0–20 | Urgency, trigger events, forcing functions |
| Fit | 0–10 | ICP alignment, product-need match |
| Engagement | 0–10 | Conversation depth, buying signals, champion behavior |

**Thresholds:** 85+ hot lead (SMS + email), 65+ qualified (email), 40–64 nurture, <40 low priority.

Enterprise deals (500+ employees or $50K+ deal size) additionally layer MEDDPICC scoring.

---

## Notification Triggers

| Trigger | Condition | Channels |
|---------|-----------|----------|
| Qualified Lead | Score ≥ 65 | Email |
| Hot Lead | Score ≥ 85 | SMS + Email |
| Enterprise Lead | Enterprise size or deal ≥ $50K | SMS + Email + Push |
| Demo Booked | Outcome = demo_booked | Email |
| Competitor Mention | Competitor flag set | Email |
| Spam Detected | Spam score ≥ 0.8 | Log |

---

## Training Mode

Auth-gated (requires `internal`, `admin`, or `sales_team` role). Five built-in scenarios:

| Scenario | Difficulty | Tests |
|----------|-----------|-------|
| The Friendly Evaluator | 🟢 | Fundamentals — clean discovery flow |
| The Skeptical VP | 🟡 | Differentiation, value articulation |
| The Technical Gatekeeper | 🟡 | Product knowledge, honesty about gaps |
| The Hidden Objection | 🔴 | Probing below surface engagement |
| The Enterprise Gauntlet | 🔴 | MEDDPICC, strategic qualification |

Scoring: 100 points across Discovery (25), Questioning (25), Objection Handling (25), Qualification Completeness (25). Post-session coaching reveals hidden state and provides specific improvement guidance.

---

## Deployment

1. Copy this directory to `protocols/packs/lead_qualification/`
2. Search-and-replace the five configuration variables across all `.md` files
3. Set `TMOS13_PACK=lead_qualification` in your environment
4. Configure notification channels in your infrastructure (email, SMS, push)
5. Set up AE routing rules in your CRM integration
6. (Optional) Configure `[Scheduling_Link]` for calendar integration

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | January 2026 | Initial release |
| 1.1.0 | February 2026 | Standardized configuration variables, formatting compliance (cards only), consistent placeholder tokens across all files, training scenario detail expansion, discovery phase structure refinement |

---

TMOS13, LLC | Robert C. Ventura | Jersey City, NJ
Copyright © 2026 TMOS13, LLC. All Rights Reserved.
