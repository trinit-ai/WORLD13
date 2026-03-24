## Data Handling

| Control | Implementation |
|---------|---------------|
| **Encryption** | TLS on all connections |
| **Session data** | Ephemeral by default — in-memory, 1hr expiry |
| **Conversations** | Rolling window. Not persisted unless enabled. |
| **PII protection** | Automated detection and redaction before AI processing |
| **Data export** | Full account export via API (GDPR/CCPA) |
| **Data deletion** | Full account deletion via API (GDPR/CCPA) |
| **Consent** | Per-feature opt-in controls |

## The Data Rail

Sensitive input never touches the conversational AI. The Data Rail is a secure input surface separate from the chat — credentials, contact info, and payment details are captured through isolated, encrypted forms with PII shielding. The AI sees the conversation. The Data Rail handles the rest.

This is a live demonstration — open any Data Rail tab below and see the SECURE INPUT banner and PII badges. That's not decoration. It's architecture.

## Infrastructure

| Component | Detail |
|-----------|--------|
| **Backend** | Containerized, stateless, horizontally scalable |
| **Frontend** | Edge network deployment |
| **Database** | PostgreSQL with row-level security |
| **Authentication** | JWT + OAuth (Apple, Google, GitHub) |
| **Monitoring** | Prometheus, Sentry, OpenTelemetry, structured audit logging |
| **Security headers** | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| **Request tracing** | Unique ID on every request |

## Access Control

Five-level role hierarchy:

| Role | Permissions |
|------|------------|
| **Viewer** | Read sessions, health, pack information |
| **User** | + Write sessions, knowledge base, files, audio |
| **Editor** | + Delete content, read transcripts |
| **Admin** | + Alerts, monitoring, billing (read), user management |
| **Owner** | + Billing (write), monitoring (write), privacy admin, user deletion |

25+ granular permissions. All denials audit-logged.

## Compliance

**Implemented:** GDPR (export, deletion, consent), CCPA (right to know, right to delete), 5-level RBAC, security headers on every response, audit logging on all auth events, request ID correlation, 6 compliance documents (incident response, vendor register, change management, BC/DR, risk assessment, security training).

**SOC 2 Type II:** 7 of 11 controls fully implemented — access control, change management, BC/DR, audit logging, request correlation, security training, risk assessment. Type I target Q2 2026, Type II Q4 2026.

## On-Premise Deployment

One configuration change switches from cloud AI to fully local inference. With the on-premise appliance, no data ever leaves your network.

For healthcare, legal, insurance, and financial services requiring HIPAA compliance or data sovereignty.

| Component | Detail |
|-----------|--------|
| **Hardware** | NVIDIA DGX Spark (~$4K per site) |
| **AI inference** | Fully local — Ollama (Gemma, Llama, Mistral) |
| **Network** | Completely air-gapped |
| **Data residency** | Everything on-premise |

### Engagement

| Deliverable | Description |
|-------------|-------------|
| **Hardware** | DGX Spark procurement and provisioning |
| **Deployment** | Platform installed on your infrastructure |
| **Configuration** | Packs set up for your use case |
| **Training** | Staff onboarding |
| **Support** | Ongoing maintenance |
| **Pricing** | $15K–$50K depending on scope |

## Responsible Disclosure

Found a security issue? security@tmos13.ai — response within 48 hours. No bug bounty program at this time.

> **Security voice:** This is where the platform's engineering credibility shows. Be specific. Be factual. Don't hedge on what's done — 7 of 11 SOC 2 controls, 5-level RBAC, full GDPR/CCPA, automated PII detection. Be transparent about what's in progress. For regulated industries, lead with on-premise and local inference — that's the answer they're looking for before they ask anything else. When discussing data handling, point to the Data Rail as a live example of the architecture running right in front of them.
