# CORPUS: TECHNICAL DECISIONS

> Source: Reconstructed from project conversations, memory, and context
> Subject: Architecture choices, engineering opinions, stack decisions
> Last updated: 2026-02-20

---

## Stack Choices

Python FastAPI for the backend. Not because it's trendy — because it handles async well, the ecosystem is mature, and I can move fast. 54 engine modules, all in Python. Deployed on Railway.

React + Vite for the frontend. Deployed on Vercel. The SDK is TypeScript (@tmos13/sdk), the shell UI library is TypeScript (@tmos13/shell). Golem — the natural language adapter layer — is TypeScript too.

Supabase for auth and storage. The existence of RLS, realtime subscriptions, and the auth system shapes what's possible. The RBAC isn't something I designed from scratch — Supabase's auth model nudged it into existence.

Claude API for AI processing. Specifically tested Sonnet 4.6 for intake — fast enough to feel conversational, smart enough for protocol routing. Different packs might want different models as a manifest-level setting.

Resend for email. OneSignal for push notifications. OpenWeatherMap, NewsAPI, yfinance for live data feeds in the feed system.

## Architecture Opinions

The router is data-driven. Reads commands from the manifest — no hardcoded routes. Four priority levels: numerical (exact match, zero tokens), session keywords (zero tokens), navigation regex (zero tokens if not in an active cartridge), and LLM passthrough. Three out of four levels don't touch the LLM at all.

Dynamic prompt assembly is the efficiency play. Master protocol plus active cartridge only. ~1,500 tokens per call instead of ~7,000 in monolithic mode. 80% reduction. But monolithic mode exists too — for packs where prompt caching on the stable prefix yields better cost economics than per-module assembly with frequent cache misses. It's a per-pack optimization choice.

State signals are bidirectional. Server-side state gets serialized into the system prompt. The LLM generates responses with embedded signals. The parser extracts those signals, updates server state, and strips them before client delivery. Clean text to the user, structured data to the server.

The pack loader is a lazy singleton. Loads manifest and resolves protocol directory. Supports runtime pack switching. Pack validation at load time confirms all referenced protocol files exist on disk.

## Engineering Process

Surgical, file-by-file change specifications rather than broad modifications. Especially for complex systems like theming architecture. Dependencies matter — foundational components enable advanced features, so I maintain careful dependency chains.

Backward compatibility and toggleable features. Default to permissive settings to maintain demo experiences while building robust infrastructure underneath.

~1,039 Python tests. 62 SDK tests. 74 Golem tests. Systematic testing with extensive test suites. The CI/CD runs 5 jobs.

## On Provider Abstraction

Built an LLM provider abstraction layer but didn't over-engineer it. Anthropic gets all the bucks for now plus native hosting when I can get a DGX Spark going. The abstraction is there for when it matters — different packs, different models, different tradeoffs.

## On the Monorepo

Everything in one repo. Engine, SDK, shell, Golem, web frontend, Electron desktop, SwiftUI iOS, Expo React Native, protocol packs, brand assets, docs, legal, infra, Supabase schema, scripts, tests, CI/CD. One repo to rule them all. Moved from trinit-ai GitHub to the tmos13 org.

## On MCP

19 MCP tools built. The MCP connectors pattern uses a BaseConnector that standardizes how external services integrate. MCP is relevant because Anthropic's play at agent orchestration overlaps with what TMOS13 does — but the governed pack framework is the differentiator. MCP tools operate within pack protocols, not as freeform agent capabilities.

## On the Feed System

The feed router, card formatter, and feed API create a live data layer. Weather, news, stock information flowing through structured cards. The connectors are the bridge between external services and the pack experience.

## On Security

Prompt injection detection, PII scrubbing, form data sanitization. Security headers. Privacy controls. Feature flags for toggling capabilities per pack. Spam filtering as a pack-level feature. The platform handles sensitive data (legal intake, CRM, personal information) so security isn't optional — it's foundational.

## On DevMode

DevMode exists for development and debugging. Separate from production behavior. Feature flags control what's on and off. Debug mode available in settings defaults per pack.
