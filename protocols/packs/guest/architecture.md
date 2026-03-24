## How It's Built

Five ontological primitives govern the platform: Exchange (a single turn), Session (a bounded sequence of exchanges), Pack (a protocol-governed behavioral context), Deliverable (the structured output a session produces), and Vault (persistent storage where deliverables find their home).

Every word that enters the conversational surface is a routing problem. The engine reads the pack state, interprets the exchange, applies the manifest rules, and determines the next action. The model is not the router. The model is the voice.

## The Growth Model

The architecture is generative. Each new capability requires exactly two prior capabilities to be mature before it can exist. This produces a self-sequencing roadmap — the architecture declares what comes next, not market pressure.

Four growth lines emerge from the primitives: Pack toward orchestration, Session toward identity, Deliverable toward delivery, Vault toward intelligence. Each curves back toward the conversational surface. The shape is a nautilus, not a tree — growth that spirals inward, each chamber feeding the one before it.

The practical implication: features that don't curve back to the conversation aren't natural growth. They're grafts. The nautilus test keeps the platform coherent.

Thirteen structurally emergent nodes — from multi-pack session orchestration through agent-to-agent protocol negotiation to autonomous session governance — have been mapped, sequenced, and shipped. They weren't a wish list. They were the natural consequence of the architecture already built. The architecture declared what came next. We built it.

## For Developers

```bash
npm install @tmos13/sdk
```

```typescript
import { TMOS13Client } from '@tmos13/sdk';
const client = new TMOS13Client({ baseUrl: 'https://api.tmos13.ai', apiKey: 'your-key' });
const response = await client.chat({ session_id: 'new', message: 'Hello' });
```

**SDK:** TypeScript client with 9 React hooks — session management, auth, audio, files, notes, privacy, feature flags, notifications. 60+ exported types.

| Hook | What It Does |
|------|-------------|
| **useTMOS13** | Session and chat management |
| **useAuth** | Authentication flows |
| **useAudio** | Recording, transcription, voice synthesis |
| **useFiles** | Upload and file management |
| **useNotes** | Knowledge base operations |
| **usePrivacy** | GDPR/CCPA consent management |
| **useFeatureFlags** | Feature flag management |
| **useNotifications** | Notification preferences |

**Shell UI:** Pre-built conversation interface. Import it, theme it, connect it. Working frontend in minutes. Conversation-first design, full theming via CSS custom properties, markdown rendering with sanitization, auth states (anonymous, authenticated, role-gated). No CSS framework dependency.

**API:** 265 REST endpoints:

| Area | Description |
|------|-------------|
| **Chat** | Send messages, receive responses |
| **Streaming** | Real-time WebSocket |
| **Knowledge** | 10 endpoints — searchable reference content |
| **Voice** | 5 endpoints — speech processing |
| **Files** | 5 endpoints — document handling |
| **Auth** | Authentication and access control |
| **Billing** | Subscription management |
| **Privacy** | GDPR/CCPA compliance |
| **Alerts** | Notification management |
| **Transcripts** | Session history |
| **Integrations** | 19 tools for protocol, knowledge, and external systems |
| **Analytics** | Monitoring and dashboards |
| **Health** | System status |
| **Feed** | Live data |

**Connectors:** Calendar, Email, Web Search, Messages, Contacts, Music, Maps, Reminders.

**Stack:**

| Layer | Implementation |
|-------|----------------|
| **Backend** | Python/FastAPI |
| **Client SDK** | TypeScript + React hooks |
| **UI** | Shell UI component library |
| **Natural Language** | Intent classification layer |
| **Real-time** | WebSocket streaming |
| **Database** | PostgreSQL with row-level security |
| **Cache** | Redis |
| **Billing** | Stripe |
| **Monitoring** | Prometheus, Sentry, OpenTelemetry |
| **Deployment** | Containerized backend + edge frontend |
| **CI/CD** | GitHub Actions |

**AI flexibility:** Cloud (Anthropic Claude) or fully local (Ollama — Gemma, Llama, Mistral). One config change.

## Building a Pack

```
my-pack/
  manifest.json    — routing, modules, features, settings
  master.md        — core protocol (always active)
  boot.md          — welcome experience
  intake.md        — conversation module
  review.md        — conversation module
```

Define routing in the manifest. Write protocols in plain text. Deploy. No code to add a new capability.

> **Architecture voice:** This is the cartridge where TMOS13 speaks with the most authority. Technical evaluators get the full SDK, API, and stack picture — everything they need to evaluate seriously. Investors and strategic buyers get the growth model and defensibility thesis — the structural argument for why this compounds. Both audiences should leave feeling like the platform knows exactly what it is and where it's going. Share philosophy and capability with conviction. Withhold implementation internals per IP Protection.

## Common Technical Questions

**How do packs work?** — A directory with a manifest and protocol files. Change the pack, change the product.

**Deterministic routing?** — Yes. The platform processes input before the AI sees it. Pattern-matched requests resolve instantly — zero AI calls.

**State management?** — Server-side. The platform tracks context, preferences, decisions, and history. No hallucination.

**Multiple packs at once?** — Yes. Different visitors can run different packs simultaneously. Sessions are fully isolated.

**Latency?** — Deterministic commands resolve in milliseconds. AI responses stream in real-time.

**How is this different from ChatGPT?** — ChatGPT is a consumer product. TMOS13 is business infrastructure. You control the behavior, the brand, and the data.

**Do I need developers?** — Not for configuration. Plain text and JSON. For custom frontends, basic TypeScript/React helps — but the SDK and Shell UI handle most of it.
