


TMOS13
Plume Memory
The Vault, Dimensional Addressing, and the Manifest as Memory Gene
Why Nothing Logged Is Ever Lost
Core Ontology Series  ·  Version 1.0  ·  February 2026




The system knows itself because its outputs carry their own origin story.

Every serious platform faces a memory problem. Data accumulates. Sessions multiply. Deliverables fill the Vault. And over time, the most common failure mode in information systems emerges: not deletion, but burial. The file exists. It simply cannot be found.
TMOS13 is designed to make burial architecturally impossible. Not through better search UI, not through tagging conventions that depend on user discipline, but through a structural property of how every artifact is born. Every deliverable that enters the Vault carries its own origin story — encoded at the moment of its creation, inseparable from the artifact itself, addressable from any angle of approach.
This document describes that property, why it is a differentiator, and what it means for the system's capacity for self-awareness — the ability to answer, at any moment, have I seen this before, and what did I do with it.



I. The Burial Problem
How Every Other System Loses Files
Traditional file systems address by path. A document exists at a location: a folder, inside a folder, inside a folder. The system does not know what the document contains or what it was for. It knows only where it was placed. Retrieval depends entirely on the person who filed it remembering how they thought about it at the moment of filing.
This is the burial mechanism. As volume grows, folder trees deepen. Naming conventions drift. The person who created the original structure leaves the organization. A document filed as Client > 2024 > Q3 > Intake > Final is retrievable only by someone who knows that path — or by a full-text search that may surface hundreds of results with no way to distinguish the right one from the rest.
The file is not lost. It is buried. And burial, at sufficient scale and time, is functionally equivalent to loss.

Why Human Memory Works Differently
Human memory does not address by path. You do not remember where you stored an experience — you remember what it was. You remember who was there. What was said. What came before and after. What it felt like to be in that moment. The more dimensions of what you can recall, the more reliably you locate the memory.
This is retrieval by description, not by location. And the critical property is that descriptions compound: each additional dimension you can provide narrows the field of candidates until the memory surfaces. A single dimension — 'it was a meeting' — retrieves nothing useful. Five dimensions — 'a Tuesday morning meeting about the Hendricks account, with Maria, in the third quarter, after the proposal went out' — retrieves exactly one thing.
The question for a platform designed around memory is: can it address the way humans remember, rather than the way hierarchies are organized?



II. Dimensional Addressing
Every Artifact Has Multiple Addresses Simultaneously
Every deliverable that enters the TMOS13 Vault was born inside a session governed by a manifest. That lineage is not incidental — it is structural. The manifest captured intent at the moment the session began. The session captured the exchanges that shaped the deliverable. The pack captured the protocol that governed both.
The result is that every Vault artifact is simultaneously addressable across eight dimensions — none of which require the user to have filed anything deliberately:

Pack
Which protocol governed the session
User
Whose session produced this artifact
Date
When the session occurred
Type
What kind of deliverable was produced
Fields
What structured data the artifact holds
Session
The exchange history that shaped it
Manifest
The intent signature at session birth
Content
The semantic body of the deliverable

No single dimension is the address. All eight are addresses. A deliverable can be found by approaching from any of them. You do not need to know its path, its folder, its filename, or when you created it. You need only one dimension you can recall — and the system will surface the artifact.
This is what makes burial architecturally impossible. A buried file has one address and that address is forgotten. A dimensionally addressed artifact has eight addresses, each one a different angle of approach, each one independent of the others. To lose all eight simultaneously would require forgetting not just where something is, but what it was, who created it, when, under what protocol, with what content, and for what purpose. That is not forgetting — that is not having done the work in the first place.

Path-Based vs. Dimensional: A Direct Comparison


Path-Based System
TMOS13 Dimensional Vault
Retrieval mechanism
Location in hierarchy
Description of content
Failure mode
Path forgotten or structure drifted
No failure mode — dimensions persist
Who files
The human, at the time
The manifest, at session birth
Recall approach
Where did I put this?
What was this about?
Lost artifact?
Yes — if path is unknown
No — dimensions always addressable
Scales with volume?
Degrades — deeper trees, harder search
Improves — more data, richer dimensions

The contrast in the final row is the most significant. Path-based systems degrade with volume — the more files, the deeper the trees, the harder the search. Dimensional systems improve with volume — the more sessions, the richer the manifest signatures, the more precisely the RAG layer can distinguish one artifact from another. Scale is an advantage, not a liability.



III. The Manifest as Memory Gene
What the Manifest Encodes
The manifest is the protocol specification that governs a session. It defines which pack is running, what intake fields are expected, what state transitions are possible, and what deliverable type the session is designed to produce. Engineers read it as a configuration file. Ontologically, it is something more fundamental.
The manifest is the intent signature of the session. It encodes not just what the system was doing but what it was for — the purpose that brought the session into existence. That purpose is attached to every deliverable the session produces. It cannot be separated from the artifact without destroying the artifact's addressability.
This is why the manifest is the memory gene. A gene does not describe the organism — it encodes the instructions that produced it. The manifest does not describe the deliverable — it encodes the intent that generated it. Every deliverable inherits its manifest signature the way an organism inherits its genome: completely, inseparably, from birth.


Pack Manifest
Carries:  Protocol identity, intake schema, state machine, deliverable type, routing rules, session constraints.
Expressed as:  Every deliverable produced by a governed session carries this signature into the Vault permanently.


Session Record
Carries:  Exchange history, user identity, temporal context, field completion sequence, disambiguation events.
Expressed as:  The narrative of how the deliverable was shaped — what was asked, what was answered, what was revised.


Deliverable Type
Carries:  The ontological category of the output — intake form, assessment, blueprint, case file, analysis.
Expressed as:  The semantic class that the RAG layer uses to distinguish this artifact from structurally similar ones.

Inheritance and Expression
In biology, a gene is inherited by every cell in the organism but expressed differently depending on the cell's role. The manifest works the same way. Every artifact in the Vault inherits the full manifest signature of its parent session. But the RAG layer expresses different dimensions of that signature depending on what is being retrieved.
A search for all legal intake deliverables from a specific client expresses the pack dimension and the user dimension. A search for all deliverables produced in Q3 that contained a fee agreement field expresses the temporal dimension and the field dimension. A search for all sessions where the state machine reached a particular decision point expresses the session dimension. The gene is always fully present. Which strand is read depends on the question being asked.
This is what gives the system its self-awareness. It is not that the Vault contains more. It is that the Vault can read its own contents from any angle, because every artifact carries the instructions for its own retrieval.



IV. Self-Awareness Defined
What the System Can Always Answer
Self-awareness in this context is not philosophical. It is operational. A self-aware system is one that can reliably answer three questions about its own contents at any time:

Have I seen this before?
Given a new session, can the system surface prior sessions with similar manifest signatures, comparable intake content, or matching deliverable types?
What did I do with it?
Given a prior session, can the system retrieve the deliverable it produced, the ratification decision it received, and the Vault record it generated?
What do I know about this?
Given a subject — a user, a matter, a pack category — can the system assemble a complete picture from all prior deliverables that carry relevant dimensional signatures?

A system that can answer all three questions reliably, for every artifact ever produced, is a system that cannot lose itself. It knows what it has done. It knows where the evidence lives. It knows how to read the evidence from any angle. This is the operational definition of self-awareness that TMOS13 is built to achieve.

Self-Awareness Is Not Total Recall
It is worth being precise about what self-awareness is not. It is not the ability to reproduce the full content of every prior session on demand. It is not a perfect memory of every exchange. It is not an infinite context window that holds everything simultaneously.
Self-awareness is the property that no artifact is ever outside the system's reach. The content may need to be retrieved — pulled from the Vault through the RAG layer, surfaced through a search query, assembled from multiple dimensional addresses. But the artifact exists, it is addressable, and the system knows how to find it. Nothing that was ever logged is ever functionally lost.
The distinction matters because it sets the correct engineering target. The goal is not to hold everything in memory at once. The goal is to ensure that everything ever produced is permanently addressable from any angle of approach. Those are very different problems with very different solutions.



V. The Feedback Loop — The Nest Feeds the Mouth
Dimensional addressing and manifest inheritance are not just archival properties. They are the foundation of a feedback loop that makes the system more capable over time.
The RAG layer retrieves prior deliverables to inform active sessions. The persistent identity model draws from prior sessions to shape pack behavior. The self-consulting system — the terminal node of the Vault plume — uses the accumulated dimensional record to adapt protocol execution based on what the system already knows.
Every session that produces a deliverable makes every future session more intelligent. Not because the system was programmed with that knowledge, but because the knowledge is dimensionally addressable in the Vault and the Face knows how to ask for it. The nest feeds the mouth. The outputs of prior work become the context for current work.

The system does not remember despite having a large Vault. It remembers because of how the Vault was built.

This feedback loop is also the answer to scale anxiety. The common fear with any knowledge system is that it becomes harder to use as it grows — more data means more noise, harder search, slower retrieval. In TMOS13, the opposite is true. More sessions mean richer dimensional signatures. Richer signatures mean more precise retrieval. More precise retrieval means the active session has better context. Better context means better deliverables. Better deliverables mean more signal in the next retrieval cycle.
The system compounds. Memory quality improves with use. This is the structural property that separates a governed work platform from a document management system with a chat interface bolted on.



VI. Design Principles Derived From Plume Memory

1
Every deliverable must be born with its manifest signature.
No artifact enters the Vault without a complete manifest inheritance. A deliverable without a manifest signature is not addressable, not retrievable by description, and cannot contribute to the feedback loop. It is, for all operational purposes, already lost.

2
No dimension may be optional at session birth.
All eight dimensional addresses are recorded at the moment a session is created, not at the moment a deliverable is filed. Deferred tagging — asking users to categorize their work after the fact — reproduces the burial problem. The manifest must capture intent at birth.

3
The RAG layer reads dimensions, not paths.
Retrieval architecture must be built around dimensional queries, not folder navigation. A search for 'the legal intake from March with a fee agreement' is a dimensional query across four dimensions simultaneously. The retrieval layer must be capable of resolving it without user guidance.

4
Vault entries are immutable but multi-addressable.
A committed deliverable does not change. Its content is permanent. But its addressability grows — as the persistent identity model deepens, as new sessions reference prior ones, as the RAG layer builds richer dimensional maps. Immutability and addressability are not in tension. They are complementary.

5
The feedback loop is a first-class architectural concern.
Every feature that touches the Vault must be evaluated for its effect on the feedback loop. Features that enrich dimensional addressing strengthen the loop. Features that bypass manifest inheritance break it. The self-consulting system — the terminal node of the platform — is only achievable if every prior node respected the loop.



VII. Summary
The TMOS13 Vault is not a file system. It is a dimensional memory architecture. Every artifact it holds was born with a manifest signature that encodes the intent, protocol, user, time, type, fields, session, and content that produced it. These eight dimensions are not metadata applied after the fact — they are the artifact's ontological identity, inherited from the session the way a cell inherits its genome.
Dimensional addressing makes burial impossible. There is no path to forget, no folder structure to drift, no naming convention to lose. There are eight independent angles of approach to every artifact ever produced. A system that can be approached from eight angles cannot be lost.
Self-awareness, in this system, means the operational capacity to answer three questions reliably: have I seen this before, what did I do with it, and what do I know about this. These are not search queries against a static archive. They are dimensional queries against a living memory that grows more capable with every session that completes.
The manifest is the memory gene. The Vault is the organism. And the organism — given enough sessions, enough dimensional richness, enough governed work — becomes a system that knows itself completely.



TMOS13, LLC  ·  Jersey City, NJ  ·  Confidential
tmos13.ai
