# TMOS13 CRM Roadmap

> From frontline support agent to full conversational CRM platform. This document maps the expansion path from the Customer Support pack to TMOS13's broader CRM ambition.

## The Thesis

Every CRM is a database with a UI bolted on. TMOS13 is a conversation engine with structured intelligence bolted on. The difference: traditional CRM asks humans to feed the machine (data entry, field updates, pipeline management). TMOS13 inverts it — the conversation IS the data entry. Every customer interaction automatically produces the structured records that CRMs exist to store.

This isn't "AI-powered CRM" in the way Salesforce adds a chatbot. This is CRM reimagined as a conversational primitive — where the conversation stream is the source of truth and the database is a byproduct.

## Current State: Customer Support Pack (v1.0)

**What exists today:**
- Tier-1 frontline support agent (5 cartridges: triage, billing, technical, account, orders)
- Structured ticket generation from natural conversation
- Sentiment tracking across conversation lifetime
- Escalation summaries with full context for human handoff
- Notification routing (escalation, churn risk, VIP contact)
- Resolution tracking and CSAT collection

**What this proves:**
- Conversation → structured record works at the ticket level
- Sentiment is trackable and actionable in real-time
- Escalation handoff eliminates "please repeat your issue" friction
- The three-element UI (messages, input, topbar) handles complex support flows without additional chrome

---

## Phase 1: Support Intelligence Layer (v1.5)

**Timeline:** Builds on v1.0, extends without restructuring

### 1a. Knowledge Base Integration
The support agent becomes as good as your best documentation.

- **KB Ingest:** Import help center articles, FAQ pages, product docs into RAG index
- **Dynamic Retrieval:** Agent searches KB in real-time during conversations, surfaces relevant articles
- **Gap Detection:** When the agent can't find an answer, it logs the knowledge gap. Over time, this produces a prioritized list of articles to write.
- **KB Feedback Loop:** Resolved tickets become draft KB articles. "This troubleshooting sequence resolved 47 tickets this month — generate an article."

### 1b. Ticket Intelligence
Turn raw tickets into operational insight.

- **Auto-Categorization:** Every ticket gets structured tags beyond the cartridge routing (product area, root cause, feature involved)
- **Trend Detection:** Surface patterns — "billing complaints up 40% this week, correlated with subscription renewal cycle change"
- **Resolution Pattern Mining:** Identify which resolution paths work fastest by issue type. Feed back into the agent's troubleshooting methodology.
- **CSAT Correlation:** Connect resolution type to satisfaction score. "Customers who get a workaround + follow-up are 3x more satisfied than those who get escalated."

### 1c. Agent Assist Mode
The same pack, but now the AI assists the human agent instead of replacing them.

- **New base template variant:** `agent_assist` — the audience is the support agent, not the customer
- **Conversation Copilot:** Agent pastes customer message, AI drafts response, agent edits and sends
- **Context Injection:** AI surfaces relevant customer history, similar tickets, KB articles alongside the conversation
- **Real-Time Coaching:** "This customer's sentiment is declining. Consider acknowledging their frustration before troubleshooting."

This is Option B from the original scoping conversation — now it layers on top of Option A instead of competing with it.

---

## Phase 2: Customer 360 (v2.0)

**Timeline:** Requires database persistence (NoteStore → DB migration), cross-session state

### 2a. Customer Record
Every conversation contributes to a persistent customer profile.

- **Contact Record:** Aggregated from all conversations — name, email, phone, account ID, tier, preferences
- **Interaction History:** Chronological timeline of all support conversations with summaries
- **Sentiment History:** Track sentiment across all interactions — is this customer's experience improving or declining over time?
- **Issue Patterns:** "This customer has contacted us 4 times about billing in the last 60 days"
- **Health Score:** Composite score based on sentiment trajectory, contact frequency, issue severity, resolution satisfaction

### 2b. Cross-Pack Customer View
The customer who contacts support today is the same person who went through onboarding last month and the sales funnel before that.

- **Unified Profile:** Legal Intake, Candidate Screener, Customer Support, Sales Coach — all packs write to the same customer record
- **Journey Mapping:** Visualize a customer's full lifecycle: lead → sale → onboarding → active → support → renewal
- **Handoff Context:** When a support customer mentions upgrading, the system surfaces their original sales conversation context

### 2c. Proactive Support
Don't wait for customers to contact you.

- **Trigger-Based Outreach:** Detect at-risk customers from health score and initiate proactive check-in
- **Incident Notifications:** When an outage is detected, proactively message affected customers before they contact support
- **Renewal Risk:** Customers with declining health scores approaching renewal get flagged for human outreach
- **Onboarding Follow-Up:** "It's been 14 days since onboarding — check in on adoption progress"

---

## Phase 3: Revenue Intelligence (v2.5)

**Timeline:** Requires billing integration, product usage data

### 3a. Expansion Detection
Support conversations contain buying signals that nobody captures today.

- **Feature Interest Signals:** "I wish I could [thing on higher plan]" → expansion opportunity
- **Usage Complaints:** "I hit my limit again" → upgrade candidate
- **Team Growth:** "We're adding 5 people next month" → expansion opportunity
- **Positive Sentiment + Feature Request:** Happy customers asking for more = warmest expansion leads

Route these signals to the account management team or directly into the Sales Coach pack.

### 3b. Churn Prevention
Support data is the best churn predictor in any company.

- **Multi-Signal Churn Model:** Combine support frequency, sentiment trajectory, resolution success rate, feature usage, billing patterns
- **Escalation Intelligence:** Not all escalations are equal — "frustrated but engaged" (saveable) vs. "calm and requesting cancellation" (decided)
- **Save Playbooks:** Based on churn reason patterns, generate specific retention approaches: "Customers who churn due to [X] are 60% saveable with [Y]"

### 3c. Revenue Attribution
Connect support quality to revenue outcomes.

- **Support → Renewal:** Track whether customer health score at support contact correlates with renewal rate
- **Support → Expansion:** Track whether support interactions preceded upgrade decisions
- **Cost Per Resolution:** Automated (free) vs. escalated (cost of human agent time) vs. lost customer (LTV impact)

---

## Phase 4: Multi-Channel Unification (v3.0)

**Timeline:** Requires MCP connector build-out, real-time integration layer

### 4a. Channel Expansion
The conversation engine meets customers where they are.

- **Email Integration:** Email connector processes inbound support emails through the same pipeline. Responses generated, human-approved, sent. Ticket created automatically.
- **SMS / Messaging:** WhatsApp, SMS, iMessage support conversations. Same agent logic, different transport.
- **Social Media:** Twitter/X, Facebook, Instagram DM support monitoring and response drafting.
- **Voice:** Audio connector enables phone support with real-time transcription, same diagnostic flow, structured ticket at end.
- **In-App:** Embedded widget (the TMOS13 session console itself) inside any web or mobile app.

### 4b. Omnichannel State
Customer switches from chat to email to phone — the conversation continues.

- **Session Continuity:** State persists across channels. Customer emailed yesterday, called today — agent has full context.
- **Channel Preference:** Track which channels each customer prefers. Route accordingly.
- **Escalation Across Channels:** Chat escalation can route to phone callback, email follow-up, or scheduled video call.

### 4c. Workflow Automation
CRM actions triggered by conversation intelligence.

- **Ticket → Project Management:** High-severity bug reports auto-create Jira/Linear tickets for engineering
- **Churn Signal → CRM:** At-risk flags auto-update Salesforce/HubSpot records
- **Resolution → KB:** Successful troubleshooting sequences auto-draft knowledge base articles
- **Feedback → Product:** Feature requests and complaints auto-aggregate into product feedback reports

---

## Phase 5: Platform CRM (v4.0)

**Timeline:** Full platform maturity, marketplace dynamics

### 5a. CRM as Pack Ecosystem
Any vertical can build a CRM pack on TMOS13.

- **Healthcare CRM:** Patient intake → follow-up → scheduling → satisfaction tracking
- **Real Estate CRM:** Lead qualification → showing scheduling → offer tracking → close management
- **Education CRM:** Student inquiry → enrollment → academic advising → alumni engagement
- **Professional Services CRM:** Client intake → project management → billing → retention

Each vertical gets the same primitives: conversation → structured intelligence → business action → notification → analytics.

### 5b. Custom CRM Builder
Companies build their own CRM flows without writing protocol files from scratch.

- **Visual Protocol Builder:** Drag-and-drop cartridge design with conversation flow templates
- **Field Mapping:** Map conversation extractions to custom database fields
- **Notification Designer:** Configure alert conditions, channels, and templates
- **Integration Marketplace:** Pre-built connectors for Salesforce, HubSpot, Zendesk, Intercom, Stripe, etc.

### 5c. CRM Intelligence Platform
TMOS13 becomes the intelligence layer between conversation and action.

- **Cross-Company Benchmarks:** Anonymized aggregate insights ("Your average resolution time is 4.2 minutes vs. industry 8.7 minutes")
- **Best Practice Sharing:** Protocol patterns that produce best outcomes shared across the pack ecosystem
- **AI Model Improvement:** Conversation data improves the underlying session intelligence, benefiting all packs

---

## Architecture Implications

### What Needs to Change

| Component | Current State | CRM Requirement |
|-----------|--------------|-----------------|
| **NoteStore** | In-memory | Persistent database (Supabase/Postgres) |
| **Session State** | Single session | Cross-session customer record |
| **MCP Connectors** | 8 stubs | Real implementations (email, calendar, CRM, project management) |
| **Pack State** | Pack-scoped | Cross-pack customer identity |
| **Notifications** | Template-based | Channel-agnostic delivery (email, SMS, push, webhook) |
| **Analytics** | PostHog events | Dedicated analytics pipeline with custom dashboards |
| **RAG** | TF-IDF + optional Pinecone | Production vector search with KB integration |
| **Auth** | Session-level | Organization-level with role-based access |
| **Billing** | Per-user subscription | Per-seat + per-resolution usage-based pricing |

### What Stays the Same

The core architecture holds. The pack system, the conversation → structured intelligence pipeline, the session console UI, the three-element interface — all of this scales without redesign. The CRM expansion is additive: more packs, richer state, more connectors, better persistence. The engine doesn't need to be rebuilt. It needs to be connected.

This is the advantage of building CRM as a conversation primitive rather than bolting conversation onto a CRM. The hard part (getting AI to conduct structured conversations that produce reliable intelligence) is already solved. The remaining work is plumbing: persistence, integration, and analytics.

---

## Competitive Positioning

### TMOS13 vs. Traditional CRM (Salesforce, HubSpot)
They store records. We generate them. They require humans to type data into fields. We extract data from natural conversation. They add AI as a feature. We are AI-native — the conversation IS the product.

### TMOS13 vs. Support Platforms (Zendesk, Intercom)
They route tickets to humans. We resolve tickets, then route what's left. They add chatbots as deflection. We add human agents as escalation. The default is AI resolution, not human resolution with AI assist.

### TMOS13 vs. AI CRM Startups (Various)
They build vertical-specific products. We build a platform that generates vertical-specific products. One protocol pack = one vertical CRM. The session console shell is the reusable primitive; the pack is the domain expertise.

### The White-Label Angle
Every phase of this roadmap is white-labelable. A law firm uses TMOS13 with the Legal Intake pack and their branding. A SaaS company uses TMOS13 with the Customer Support pack and their branding. An enterprise uses TMOS13 with a custom pack built on the platform and their branding. Same engine, same console, different protocols, different brands.

---

## Revenue Model Evolution

| Phase | Model | Unit Economics |
|-------|-------|----------------|
| **v1.0** | Per-seat SaaS | $X/month per support agent seat |
| **v1.5** | Seat + resolution | $X/seat + $Y per AI-resolved ticket |
| **v2.0** | Platform license | Annual license by customer volume tier |
| **v3.0** | Usage-based | Per conversation + per integration + per channel |
| **v4.0** | Marketplace | Platform fee + pack marketplace revenue share |

---

## The North Star

A company signs up for TMOS13. They configure one pack — say Customer Support. Within a week, every support conversation produces a structured ticket, a customer health score update, a knowledge base gap report, and an expansion signal if one exists. No data entry. No CRM training. No fields to fill out.

Six months later, they add Sales Coach and Candidate Screener. Their entire customer-facing operation — sales, support, hiring — runs through the same conversation engine. The customer record spans the full lifecycle. The hiring team sees that their best support agents came through the same screening patterns. The sales team sees that their highest-retention customers had the smoothest support experiences.

This is conversational CRM. The conversation isn't a channel into the CRM. The conversation is the CRM.
