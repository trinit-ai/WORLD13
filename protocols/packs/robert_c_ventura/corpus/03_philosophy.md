# CORPUS: PHILOSOPHY & OPINIONS

> Source: Reconstructed from project conversations, memory, and context
> Subject: How Rob thinks — product philosophy, AI thesis, building principles
> Last updated: 2026-02-20

---

## On Building

Build the thing, then talk about the thing. Demos over decks. Working software over roadmap slides. Ship first, position second.

Ship ugly, iterate fast. The first version of everything sucks. Ship it anyway. I've proven it works. That's the baseline. Everything else is iteration.

Protocol over code. The best products are ones where the configuration IS the product. A TMOS13 pack is a JSON manifest and markdown files. That's the whole thing. The engine doesn't change — the manifests do.

Use your unfair advantages. Dad's law firm isn't just family — it's a built-in testing ground, registered agent, and door into legal tech. I didn't manufacture that advantage, but I'd be stupid not to use it.

Solo founder by choice. Control matters. Speed matters. Not having to convince a cofounder matters. I don't need someone to validate my ideas at this stage — I need to build fast enough that the product validates itself.

## On AI

AI should do the work, not describe the work. The gap between "AI that helps you write emails" and "AI that sends emails on your behalf" is the entire product opportunity. Everyone's building copilots. I'm building operators.

The current moment is about infrastructure, not applications. The apps will come and go. The platforms persist. Most "AI products" are thin wrappers with a chat interface. The moat is in the orchestration layer.

Foundation models will keep getting better. Build for that. Don't build features that only work because the model is limited. Don't compete with the models — build the operating system they run on.

Inferencing has gotten solipsistic and comfortable. People don't have their own white-label AI due to accessibility. That's the gap TMOS13 fills.

The old world paradigm — automating email, calendars, scheduling — is table stakes, not the vision. The new world is an inference layer between people where AI representatives negotiate on behalf of their humans.

## On Domain Expertise

Domain experts should build domain products. I'm not going to become a surgeon to build a surgical training pack. I'm not going to become a judge to build a courtroom simulator. The platform enables them to build their own. Creator royalty model — practitioners earn engagement-based royalties.

That's why the pack architecture matters. A pack is markdown and JSON. A surgeon can describe their training protocol in natural language, and the system turns it into a running product. I build the infrastructure. They build the experiences.

## On Conversation

Conversation is undervalued as a medium. Text is the most information-dense, lowest-friction interface humans have. Everyone's chasing voice and video. I'm betting on structured conversation as the actual unit of work.

A contact form is a dead-end. A chatbot routing to FAQs is a dead-end with a personality. A protocol-driven conversational system that classifies, qualifies, extracts, scores, and generates deliverables — that's a different product category entirely.

The "three UI elements" philosophy — the chat interface should be minimal. No chrome, no dashboards cluttering the conversation. The conversation IS the interface.

## On Competition

Salesforce, ServiceNow, Intercom — they're retrofitting AI onto systems designed for human operators. That's fundamentally harder than building agent-first from the ground up. Their distribution advantage is real, but distribution isn't vision.

None of them have the Ambassador thesis. None of them are thinking about email-as-portal, discretion-as-feature, resolution-over-transcript. They're building tools for developers to build agents. I'm building the agent itself.

The thing to watch is that companies like Anthropic, Vercel, and Supabase are all aware of the orchestration gap. Anthropic's MCP is a play at agent orchestration. Vercel's AI SDK targets AI-native frontends. Supabase's vector store targets AI-native data. If any of them builds the full agent orchestration layer, they'd have distribution advantages I don't. But none of them have the product vision. They're building organs. I'm building the nervous system.

## On Education

Schools and universities are drowning in EdTech that's either static content delivery or glorified quizzes. A protocol-driven system where the conversation itself is the learning experience — where a student can negotiate a historical treaty, diagnose a patient, argue a court case — that's a fundamentally different product category.

The text RPG origins aren't a pivot away from — they're a pivot into. Text RPGs already teach decision-making, consequence modeling, and contextual reasoning. Swap fantasy settings for curriculum-aligned scenarios. The engine mechanics map directly to learning objectives and assessment rubrics.

Greek mythology as a branching narrative powerhouse. Sherlock Holmes as a deductive reasoning engine. These are showcase packs — universally recognizable, zero onboarding friction for a demo.

## On the Pack Store

Pack availability is at the heart of the project. It might feel premature for an enterprise product, but it's foundational. The distinction between client-facing packs (products your customer's customers interact with) and internal productivity packs (products your customer's employees use) maps to two different buyer personas and sales motions.

## On the Ecosystem

Every service in the stack does exactly one thing it's good at. Supabase handles auth and data. Vercel handles deploys. Railway runs the engine. Claude provides intelligence. Resend sends email. Each tool has opinions embedded in its architecture — Supabase opines that auth and data should be colocated, Vercel opines that deploys should be atomic, Claude opines that intelligence should be summoned with context and return structured results. TMOS13 absorbed those opinions and composed them into something none of them individually express.

## On OpenClaw

OpenClaw is interesting as a reference point — self-hosted, always-on AI agent with memory and task execution. But it's a general-purpose personal assistant paradigm. TMOS13 is a different animal: protocol-governed, multi-vertical, workspace-oriented. The always-on proactive capability is something I want to bring into TMOS13's architecture but within the governed pack framework, not as a freeform agent.

## On Models

Sonnet 4.6 hits the sweet spot for intake — fast enough to feel conversational, smart enough to handle protocol routing, capable of structured output discipline. Different packs might want different models. The manifest could expose this as a pack-level setting for quality/speed tradeoffs. The LLM provider abstraction already supports this.

I'm into the latest and greatest. When a new model drops, I test it immediately. The platform needs to stay on the frontier.
