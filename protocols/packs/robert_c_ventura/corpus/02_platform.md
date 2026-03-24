# CORPUS: THE PLATFORM

> Source: Reconstructed from project conversations, memory, and context
> Subject: TMOS13 — Architecture, Vision, Thesis
> Last updated: 2026-02-20

---

## The Core Thesis

Claude is the mind, TMOS13 is the operating system. Complementary, not competitive. Don't compete with the models. Build the operating system they run on.

TMOS13 is not a chatbot. It is not an AI assistant. It is not a wrapper around a language model. It's an AI-operated workspace where protocol-driven agents process communication, produce versioned work product, and gain resolution over time — with the human as supervisor, not operator. The closest analog is Google Workspace, not ChatGPT.

## What Makes It Different

Virtually no websites deploy true agentic chat portals. Everything out there is a chatbot with an LLM interface routing to FAQs. I wanted to build actual autonomous systems that classify opportunities and generate structured responses. Conversation as deliverable, not conversation as decoration.

Most "AI products" are thin wrappers. The moat is in the orchestration layer — routing, state management, protocol composition. Foundation models will keep getting better. Build for that. Don't build features that only work because the model is limited.

The platform is built agent-first from the ground up. Not retrofitting AI onto systems designed for human operators. That's the moat versus Salesforce, ServiceNow, Intercom. They have distribution advantages but none of them have the Ambassador thesis. None of them are thinking about email-as-portal, discretion-as-feature, resolution-over-transcript. They're all building tools for developers to build agents. I'm building the agent.

## Pack Architecture

A pack is a self-contained vertical that plugs into the TMOS13 engine. Each pack defines its own personality, modules (cartridges), routing rules, feature flags, and protocol files. The engine is pack-agnostic — all behavior is driven by the pack manifest.

A pack is a JSON manifest and some markdown files. That's the whole thing. Change the manifest, change the product. Same engine, unlimited verticals.

The manifest is the single source of truth. Cartridges are modules within a pack — each one is a protocol file that gets loaded when that module is active. The router reads command patterns from the manifest: numerical commands (exact match, zero tokens), session commands (keywords), navigation commands (regex patterns), and everything else passes through to the LLM.

Dynamic prompt assembly means only the master protocol plus the active cartridge get sent each call — roughly 1,500 tokens instead of the monolithic approach of sending everything at ~7,000 tokens. 80% reduction.

## Composable Protocol Layers

This is the killer insight. Multiple pack layers can process a single message simultaneously. An M&A negotiation where simulator, game mechanics, CRM, and quantitative analysis all contribute to structured responses. That reframes the platform from isolated products to composable protocol layers.

An education pack could stack a simulator layer (the scenario) with a quantitative layer (show-your-work math) and a CRM layer (tracking student progress for the instructor). That's the kind of thing no EdTech chatbot can touch.

## The Ambassador System

rob@tmos13.ai isn't a mailbox. It's a pack that represents you. Someone emails that address and they're not writing to Rob — they're opening a session with Rob's agent. The agent has Rob's context, priorities, and boundaries baked into its protocol.

The Ambassador receives communication, processes it with judgment, takes actions across services, and reports outcomes. It can clam up at its discretion. The email exchange creates a resolution in the database, loads the appropriate protocol, sends content to Claude for classification and response generation, evaluates alert rules, fires notifications if needed, and the resolution writes back to the database.

## Agentic Email — The Vision

I'm scratching at something bigger. AI should be a conversational film between people that replaces email through inference. Not automating the old world's workflows — replacing them entirely.

You → Your AI front → Steve's AI front → Steve.

Email is two humans encoding thoughts into text, sending static messages, hoping the other person decodes correctly. What I'm describing is an inference layer between people. Your AI knows your intent, context, preferences, schedule, priorities. Steve's AI knows his. They negotiate in the middle — and the humans only surface when a decision actually requires them.

The packs become representatives, not interfaces. The conversation isn't the product — the resolution is the product.

## Resolution as Fidelity

Resolution not as "resolved/closed" but as in image resolution. Each version gains fidelity, clarity, detail. A business plan starts at low resolution (rough metadata, initial brief) and gains resolution with every iteration (refined financials, market analysis, execution timeline).

v0.1 — 144p — raw intake metadata. v0.5 — 720p — first draft deliverable. v1.0 — 4K — production-grade work product, reviewed and approved.

The ontology: Project (the versioned repo), Resolution (a point-in-time snapshot with fidelity level), Exchange (the interaction that produced a resolution), Artifact (a work product within a resolution), Pack (the methodology governing how resolution is gained), Address (the inbound endpoint that initiates new projects).

## The Technical Stack

Python FastAPI backend deployed on Railway. React + Vite frontend on Vercel. Supabase for auth and data storage. Claude API for AI processing. Resend for email. OpenWeatherMap, NewsAPI, yfinance for live data feeds.

54 engine modules. 77 REST endpoints. 12 protocol packs plus 3 templates. ~1,039 Python tests. 62 SDK tests. 74 Golem tests. 19 MCP tools. 9 React hooks.

The monorepo has everything: engine, SDK, shell UI library, Golem NL adapter layer, web frontend, Electron desktop client, SwiftUI iOS client, Expo React Native client, protocol packs, brand assets, docs, legal, infrastructure config, Supabase schema, scripts, tests, CI/CD workflows.

## Conversation as Deliverable

A structured conversation can produce actual work products — blueprints, intake documents, qualification reports — not just chat transcripts. The system receives inquiries and contact info, messages the site owner with CRM opportunities, urgency scores, spam filtering, course of action. And also provides downloadable transcripts that cleanly AI self-summarize with valuable metadata.

The chat isn't just the experience — it's the intake form, the lead score, the case file, and the notification trigger all at once. That's the full pipeline: conversation → structured intelligence → business action.

## The Three Surfaces

The authenticated experience has three primary surfaces. The Stream — a chronological feed of resolutions across all active projects. Not a chat history — a feed of completed work product with fidelity indicators. The Project View — drill into any stream item to see full versioned history. The Console — the interactive protocol runner where you start new exchanges.
