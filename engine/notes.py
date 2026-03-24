"""
TMOS13 Notes Service — Persistent Markdown Knowledge Base

Core knowledge layer for the TMOS13 intelligence system. Provides CRUD
operations, full-text search, tagging, auto-linking between related notes,
conversation summarization, and export compilation.

Notes are stored as structured objects with markdown content and indexed
in the RAG engine for semantic retrieval and context injection.

Usage:
    store = NoteStore()
    note = await store.create("Meeting Notes", "## Key Points\n- Decision on pricing", tags=["meeting"])
    results = store.search("pricing decision")
    related = store.find_related(note.note_id, max_results=5)
    compiled = store.compile_export(tag="meeting")
"""
import hashlib
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

logger = logging.getLogger("tmos13.notes")


# ─── Constants ───────────────────────────────────────────

MAX_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 100_000  # ~100KB per note
MAX_TAGS = 50
MAX_LINKS = 100


# ─── Enums ───────────────────────────────────────────────

class NoteType(str, Enum):
    NOTE = "note"
    SUMMARY = "summary"
    DOCUMENT = "document"
    MEMORY = "memory"


# ─── Data Models ─────────────────────────────────────────

@dataclass
class Note:
    """A persistent knowledge note with metadata."""
    note_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str = ""
    content: str = ""
    note_type: str = "note"
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)  # note_ids of related notes

    # Ownership
    user_id: str = "anonymous"
    session_id: str = ""

    # Pack / Vault
    pack_id: str = ""
    manifest_signature: dict = field(default_factory=dict)

    # Provenance
    source: str = ""  # e.g. "conversation", "upload", "manual"
    source_id: str = ""  # e.g. conversation/file ID

    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Ephemeral workbench
    ephemeral: bool = False
    expires_at: float | None = None  # epoch timestamp; None = never

    # Computed
    word_count: int = 0
    checksum: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def preview(self) -> str:
        """First 200 chars of content for display cards."""
        if len(self.content) <= 200:
            return self.content
        return self.content[:200] + "..."


@dataclass
class NoteSearchResult:
    """A note search result with relevance score."""
    note: Note
    score: float = 0.0
    match_context: str = ""

    def to_dict(self) -> dict:
        return {
            "note": self.note.to_dict(),
            "score": round(self.score, 4),
            "match_context": self.match_context,
        }


@dataclass
class ConversationSummary:
    """Structured summary of a conversation."""
    title: str = ""
    key_points: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    topic_segments: list[dict] = field(default_factory=list)
    message_count: int = 0
    duration_estimate: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        """Render as a markdown note."""
        parts = [f"# {self.title}\n"]
        if self.key_points:
            parts.append("## Key Points")
            for p in self.key_points:
                parts.append(f"- {p}")
            parts.append("")
        if self.decisions:
            parts.append("## Decisions")
            for d in self.decisions:
                parts.append(f"- {d}")
            parts.append("")
        if self.action_items:
            parts.append("## Action Items")
            for a in self.action_items:
                parts.append(f"- [ ] {a}")
            parts.append("")
        if self.topic_segments:
            parts.append("## Topics Discussed")
            for seg in self.topic_segments:
                parts.append(f"### {seg.get('topic', 'Untitled')}")
                if seg.get("summary"):
                    parts.append(seg["summary"])
                parts.append("")
        if self.tags:
            parts.append(f"*Tags: {', '.join(self.tags)}*")
        return "\n".join(parts)


# ─── Text Analysis Helpers ───────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer for search and similarity."""
    return re.findall(r"[a-z0-9']+", text.lower())


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total."""
    counts: dict[str, int] = defaultdict(int)
    for t in tokens:
        counts[t] += 1
    total = len(tokens) or 1
    return {t: c / total for t, c in counts.items()}


def _cosine_similarity(tf_a: dict[str, float], tf_b: dict[str, float]) -> float:
    """Cosine similarity between two TF vectors."""
    terms = set(tf_a) | set(tf_b)
    dot = sum(tf_a.get(t, 0) * tf_b.get(t, 0) for t in terms)
    mag_a = sum(v ** 2 for v in tf_a.values()) ** 0.5
    mag_b = sum(v ** 2 for v in tf_b.values()) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _extract_key_sentences(text: str, max_sentences: int = 5) -> list[str]:
    """Extract the most informative sentences from text using simple heuristics."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= max_sentences:
        return [s.strip() for s in sentences if s.strip()]

    # Score sentences by: length, position, keyword density
    scored = []
    keywords = {"decided", "agree", "important", "conclusion", "action",
                "next", "plan", "deadline", "issue", "solution", "need",
                "must", "should", "will", "goal", "result", "key"}
    for i, s in enumerate(sentences):
        if not s.strip():
            continue
        words = s.lower().split()
        score = 0.0
        # Prefer longer sentences (but not too long)
        score += min(len(words) / 20, 1.0)
        # Prefer early sentences
        score += max(0, 1.0 - i / len(sentences))
        # Keyword bonus
        score += sum(0.3 for w in words if w in keywords)
        scored.append((score, s.strip()))

    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:max_sentences]]


def _detect_action_items(text: str) -> list[str]:
    """Detect action items from conversational text."""
    patterns = [
        r"(?:need to|should|must|will|going to|plan to|have to)\s+(.+?)(?:\.|$)",
        r"(?:action item|todo|task|reminder):\s*(.+?)(?:\.|$)",
        r"(?:let's|let us)\s+(.+?)(?:\.|$)",
    ]
    items = []
    for line in text.split("\n"):
        for pat in patterns:
            matches = re.findall(pat, line.lower())
            for m in matches:
                cleaned = m.strip().rstrip(".")
                if len(cleaned) > 10 and cleaned not in items:
                    items.append(cleaned)
    return items[:10]


def _detect_topics(messages: list[dict]) -> list[dict]:
    """Segment a conversation into topic clusters."""
    if not messages:
        return []

    segments = []
    current_topic_words: list[str] = []
    current_messages: list[str] = []
    last_tokens: set[str] = set()

    for msg in messages:
        content = msg.get("content", "")
        tokens = set(_tokenize(content))

        # If vocabulary shifts significantly, start a new topic
        if last_tokens and len(tokens & last_tokens) / max(len(tokens | last_tokens), 1) < 0.15:
            if current_messages:
                topic_text = " ".join(current_messages)
                key_words = _tokenize(topic_text)
                # Use most frequent words as topic name
                freq: dict[str, int] = defaultdict(int)
                stop_words = {"the", "a", "is", "are", "was", "were", "it", "i", "you",
                              "we", "they", "to", "and", "of", "in", "for", "on", "with",
                              "that", "this", "be", "have", "do", "at", "from", "but", "not"}
                for w in key_words:
                    if w not in stop_words and len(w) > 2:
                        freq[w] += 1
                top = sorted(freq.items(), key=lambda x: -x[1])[:3]
                topic_name = " ".join(w for w, _ in top).title() if top else "Discussion"
                segments.append({
                    "topic": topic_name,
                    "summary": " ".join(current_messages[:2])[:200],
                    "message_count": len(current_messages),
                })
            current_messages = []
            current_topic_words = []

        current_messages.append(content)
        current_topic_words.extend(_tokenize(content))
        last_tokens = tokens

    # Final segment
    if current_messages:
        freq = defaultdict(int)
        stop_words = {"the", "a", "is", "are", "was", "were", "it", "i", "you",
                      "we", "they", "to", "and", "of", "in", "for", "on", "with",
                      "that", "this", "be", "have", "do", "at", "from", "but", "not"}
        for w in current_topic_words:
            if w not in stop_words and len(w) > 2:
                freq[w] += 1
        top = sorted(freq.items(), key=lambda x: -x[1])[:3]
        topic_name = " ".join(w for w, _ in top).title() if top else "Discussion"
        segments.append({
            "topic": topic_name,
            "summary": " ".join(current_messages[:2])[:200],
            "message_count": len(current_messages),
        })

    return segments


# ─── Conversation Summarizer ─────────────────────────────

def summarize_conversation(
    messages: list[dict],
    title: str = "",
    max_key_points: int = 5,
) -> ConversationSummary:
    """
    Produce a structured summary from a list of conversation messages.

    Each message is a dict with at least 'role' and 'content' keys.
    This is a heuristic-based summarizer (no LLM call required).
    """
    if not messages:
        return ConversationSummary(title=title or "Empty Conversation")

    # Combine all content
    all_text = "\n".join(m.get("content", "") for m in messages)
    user_messages = [m for m in messages if m.get("role") == "user"]
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]

    # Auto-generate title from first user message if not provided
    if not title:
        first_user = user_messages[0]["content"] if user_messages else "Conversation"
        title = first_user[:80].strip()
        if len(first_user) > 80:
            title += "..."

    # Extract key points from assistant responses (they contain the conclusions)
    assistant_text = "\n".join(m.get("content", "") for m in assistant_messages)
    key_points = _extract_key_sentences(assistant_text, max_key_points)

    # Detect action items
    action_items = _detect_action_items(all_text)

    # Detect decisions (sentences with decision language)
    decision_patterns = re.findall(
        r"(?:decided|agreed|conclusion|settled on|going with|chosen?)\s+(.+?)(?:\.|$)",
        all_text.lower()
    )
    decisions = [d.strip().rstrip(".") for d in decision_patterns if len(d.strip()) > 10][:5]

    # Auto-tag based on content
    tags = _auto_tag(all_text)

    # Topic segmentation
    topic_segments = _detect_topics(messages)

    return ConversationSummary(
        title=title,
        key_points=key_points,
        decisions=decisions,
        action_items=action_items,
        tags=tags,
        topic_segments=topic_segments,
        message_count=len(messages),
        duration_estimate=f"{len(messages) * 30}s",  # rough estimate
    )


def _auto_tag(text: str) -> list[str]:
    """Generate tags from text content using keyword detection."""
    tag_keywords = {
        "pricing": ["price", "pricing", "cost", "budget", "revenue", "monetiz"],
        "technical": ["api", "code", "bug", "deploy", "server", "database", "endpoint"],
        "design": ["design", "ui", "ux", "layout", "wireframe", "mockup", "figma"],
        "meeting": ["meeting", "discuss", "agenda", "standup", "sync"],
        "planning": ["plan", "roadmap", "milestone", "sprint", "backlog", "timeline"],
        "hiring": ["hire", "hiring", "candidate", "interview", "recrui"],
        "launch": ["launch", "release", "ship", "deploy", "go live"],
        "research": ["research", "study", "analysis", "survey", "competitor"],
        "marketing": ["marketing", "campaign", "brand", "social media", "seo"],
        "security": ["security", "auth", "permission", "encrypt", "vulnerab"],
    }
    text_lower = text.lower()
    tags = []
    for tag, keywords in tag_keywords.items():
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
    return tags[:10]


# ─── Note Store ──────────────────────────────────────────

class NoteStore:
    """
    In-memory note store with full-text search, auto-linking,
    and export compilation.

    Integrates with the RAG engine for semantic retrieval.
    """

    def __init__(self, rag_engine=None, supabase_client=None):
        self._notes: dict[str, Note] = {}
        self._tf_cache: dict[str, dict[str, float]] = {}
        self._loaded_users: set[str] = set()  # Track which users have been loaded from Supabase
        self.rag_engine = rag_engine
        self._db = supabase_client
        logger.info("NoteStore initialized")

    # ─── CRUD ─────────────────────────────────────────────

    async def create(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        note_type: str = "note",
        user_id: str = "anonymous",
        session_id: str = "",
        source: str = "manual",
        source_id: str = "",
        ephemeral: bool = False,
        expires_at: float | None = None,
        pack_id: str = "",
        manifest_signature: dict | None = None,
    ) -> Note:
        """Create a new note and index it.

        If ephemeral=True and no expires_at is given, defaults to 24 hours from now.
        """
        if not title:
            raise ValueError("Title is required")
        if len(title) > MAX_TITLE_LENGTH:
            title = title[:MAX_TITLE_LENGTH]
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Content exceeds maximum length of {MAX_CONTENT_LENGTH} characters")
        if tags and len(tags) > MAX_TAGS:
            tags = tags[:MAX_TAGS]

        # Default ephemeral TTL: 24 hours
        if ephemeral and expires_at is None:
            expires_at = time.time() + 86400

        note = Note(
            title=title,
            content=content,
            note_type=note_type,
            tags=tags or [],
            user_id=user_id,
            session_id=session_id,
            pack_id=pack_id,
            manifest_signature=manifest_signature or {},
            source=source,
            source_id=source_id,
            ephemeral=ephemeral,
            expires_at=expires_at,
            word_count=len(content.split()),
            checksum=hashlib.sha256(content.encode()).hexdigest()[:16],
        )

        self._notes[note.note_id] = note
        self._index_note(note)

        # Auto-link to related notes
        related = self.find_related(note.note_id, max_results=5, min_score=0.15)
        if related:
            note.links = [r.note.note_id for r in related]
            # Bidirectional linking
            for r in related:
                if note.note_id not in r.note.links:
                    r.note.links.append(note.note_id)
                    if len(r.note.links) > MAX_LINKS:
                        r.note.links = r.note.links[:MAX_LINKS]

        self._persist_note(note)
        logger.info(f"Note created: {note.note_id} '{title}' ({note.word_count} words, {len(note.links)} links)")
        return note

    async def get(self, note_id: str) -> Optional[Note]:
        """Get a note by ID. Checks memory, then Supabase."""
        note = self._notes.get(note_id)
        if note is not None:
            return note

        # Fall back to Supabase
        if self._db:
            try:
                result = (
                    self._db.table("notes")
                    .select("*")
                    .eq("id", note_id)
                    .execute()
                )
                if result.data:
                    note = self._row_to_note(result.data[0])
                    self._notes[note.note_id] = note
                    self._index_note(note)
                    logger.debug(f"Note {note_id} restored from Supabase")
                    return note
            except Exception as e:
                logger.warning(f"Supabase note fetch failed for {note_id}: {e}")

        return None

    async def update(
        self,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> Optional[Note]:
        """Update a note's title, content, or tags."""
        note = self._notes.get(note_id)
        if not note:
            return None

        if title is not None:
            note.title = title[:MAX_TITLE_LENGTH]
        if content is not None:
            if len(content) > MAX_CONTENT_LENGTH:
                raise ValueError(f"Content exceeds maximum length of {MAX_CONTENT_LENGTH} characters")
            note.content = content
            note.word_count = len(content.split())
            note.checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        if tags is not None:
            note.tags = tags[:MAX_TAGS]

        note.updated_at = time.time()
        self._index_note(note)
        self._persist_note(note)

        logger.info(f"Note updated: {note_id}")
        return note

    async def delete(self, note_id: str) -> bool:
        """Delete a note and remove it from all link lists."""
        if note_id not in self._notes:
            return False

        # Remove from other notes' link lists
        for other in self._notes.values():
            if note_id in other.links:
                other.links.remove(note_id)

        del self._notes[note_id]
        self._tf_cache.pop(note_id, None)
        self._delete_note_from_db(note_id)

        logger.info(f"Note deleted: {note_id}")
        return True

    async def list_notes(
        self,
        user_id: str | None = None,
        tag: str | None = None,
        note_type: str | None = None,
        ephemeral: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        """List notes with optional filters, sorted by updated_at descending."""
        notes = list(self._notes.values())
        if user_id:
            notes = [n for n in notes if n.user_id == user_id]
        if tag:
            notes = [n for n in notes if tag in n.tags]
        if note_type:
            notes = [n for n in notes if n.note_type == note_type]
        if ephemeral is not None:
            notes = [n for n in notes if n.ephemeral == ephemeral]
        notes.sort(key=lambda n: n.updated_at, reverse=True)
        return notes[offset:offset + limit]

    # ─── Search ───────────────────────────────────────────

    def _index_note(self, note: Note):
        """Index a note's content for search."""
        text = f"{note.title} {' '.join(note.tags)} {note.content}"
        tokens = _tokenize(text)
        self._tf_cache[note.note_id] = _compute_tf(tokens)

        # Also add to RAG engine if available
        if self.rag_engine:
            from rag import Document
            doc = Document(
                f"note:{note.note_id}",
                "notes",
                note.title,
                f"{note.title}\n{note.content}",
            )
            self.rag_engine.index.add_document(doc)

    def search(
        self,
        query: str,
        user_id: str | None = None,
        tag: str | None = None,
        max_results: int = 10,
    ) -> list[NoteSearchResult]:
        """Full-text search across all notes using TF-IDF scoring."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_tf = _compute_tf(query_tokens)
        results: list[NoteSearchResult] = []

        # Compute IDF across all notes
        n_docs = len(self._notes) or 1
        df: dict[str, int] = defaultdict(int)
        for tf in self._tf_cache.values():
            for term in tf:
                df[term] += 1

        for note_id, note in self._notes.items():
            if user_id and note.user_id != user_id:
                continue
            if tag and tag not in note.tags:
                continue

            tf = self._tf_cache.get(note_id, {})
            score = 0.0
            matched_terms = []
            for qt in query_tokens:
                if qt in tf:
                    idf = (n_docs / (df.get(qt, 1))) + 1
                    score += tf[qt] * idf
                    matched_terms.append(qt)

            if score > 0:
                # Build match context
                context = ""
                content_lower = note.content.lower()
                for term in matched_terms[:3]:
                    idx = content_lower.find(term)
                    if idx >= 0:
                        start = max(0, idx - 40)
                        end = min(len(note.content), idx + len(term) + 40)
                        context = "..." + note.content[start:end] + "..."
                        break

                results.append(NoteSearchResult(
                    note=note,
                    score=score,
                    match_context=context,
                ))

        results.sort(key=lambda r: -r.score)
        return results[:max_results]

    # ─── Auto-Linking ─────────────────────────────────────

    def find_related(
        self,
        note_id: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> list[NoteSearchResult]:
        """Find notes related to the given note using cosine similarity."""
        target_tf = self._tf_cache.get(note_id)
        if not target_tf:
            return []

        results: list[NoteSearchResult] = []
        for other_id, other_tf in self._tf_cache.items():
            if other_id == note_id:
                continue
            similarity = _cosine_similarity(target_tf, other_tf)
            if similarity >= min_score:
                note = self._notes.get(other_id)
                if note:
                    results.append(NoteSearchResult(note=note, score=similarity))

        results.sort(key=lambda r: -r.score)
        return results[:max_results]

    # ─── Context Injection ────────────────────────────────

    def get_context_for_query(
        self,
        query: str,
        user_id: str | None = None,
        max_tokens: int = 500,
    ) -> str:
        """
        Retrieve relevant note content for injection into conversation context.
        Returns a formatted string suitable for prepending to LLM prompts.
        """
        results = self.search(query, user_id=user_id, max_results=8)

        # Fallback: if TF-IDF found nothing but user has notes, inject all of them
        # (handles generic queries like "check my notes" where terms don't overlap)
        if not results and user_id:
            user_notes = [n for n in self._notes.values() if n.user_id == user_id]
            if user_notes:
                user_notes.sort(key=lambda n: n.updated_at, reverse=True)
                results = [NoteSearchResult(note=n, score=0.5) for n in user_notes[:8]]

        if not results:
            return ""

        context_parts = []
        token_count = 0
        for r in results:
            chunk = f"[Note: {r.note.title}] {r.note.content[:300]}"
            chunk_tokens = len(chunk) // 4
            if token_count + chunk_tokens > max_tokens:
                break
            context_parts.append(chunk)
            token_count += chunk_tokens

        if not context_parts:
            return ""

        return (
            "[USER NOTES — Manually saved notes from Notes & Logs]\n"
            "These are the user's personal notes, NOT session memories or conversation history.\n"
            + "\n---\n".join(context_parts)
        )

    # ─── Conversation Summary → Note ──────────────────────

    async def save_conversation_summary(
        self,
        messages: list[dict],
        title: str = "",
        user_id: str = "anonymous",
        session_id: str = "",
    ) -> tuple[ConversationSummary, Note]:
        """
        Summarize a conversation and save it as a note.
        Returns (summary, note).
        """
        summary = summarize_conversation(messages, title=title)
        note = await self.create(
            title=summary.title,
            content=summary.to_markdown(),
            tags=summary.tags,
            note_type="summary",
            user_id=user_id,
            session_id=session_id,
            source="conversation",
        )
        return summary, note

    # ─── Export Compilation ────────────────────────────────

    def compile_export(
        self,
        note_ids: list[str] | None = None,
        tag: str | None = None,
        user_id: str | None = None,
        title: str = "Compiled Notes",
    ) -> str:
        """
        Compile multiple notes into a single formatted markdown document.
        Provide note_ids explicitly, or filter by tag/user.
        """
        if note_ids:
            notes = [self._notes[nid] for nid in note_ids if nid in self._notes]
        else:
            notes = list(self._notes.values())
            if user_id:
                notes = [n for n in notes if n.user_id == user_id]
            if tag:
                notes = [n for n in notes if tag in n.tags]

        if not notes:
            return f"# {title}\n\n*No matching notes found.*"

        notes.sort(key=lambda n: n.created_at)

        parts = [f"# {title}\n"]
        parts.append(f"*Compiled {len(notes)} notes — {time.strftime('%Y-%m-%d %H:%M')}*\n")

        # Table of contents
        parts.append("## Table of Contents\n")
        for i, note in enumerate(notes, 1):
            parts.append(f"{i}. {note.title}")
        parts.append("")

        # Note sections
        for note in notes:
            parts.append(f"---\n\n## {note.title}\n")
            if note.tags:
                parts.append(f"*Tags: {', '.join(note.tags)}*\n")
            parts.append(note.content)
            parts.append("")

        return "\n".join(parts)

    # ─── Ephemeral Workbench ─────────────────────────────

    async def promote_to_manifest(
        self,
        note_id: str,
        owner_id: str,
        manifest_service=None,
    ) -> dict:
        """Promote a note to a permanent Manifest entry.

        Ephemeral notes are deleted after promotion. Regular notes are kept.
        Returns a dict with the ManifestEntry summary and the note_id.
        Raises ValueError if the note doesn't exist.
        """
        note = self._notes.get(note_id)
        if not note:
            raise ValueError(f"Note not found: {note_id}")

        # Resolve manifest service
        if manifest_service is None:
            try:
                from manifest import get_manifest_service
                manifest_service = get_manifest_service()
            except Exception:
                raise ValueError("ManifestService not available")

        entry = manifest_service.log(
            owner_id=owner_id,
            event_type="system_event",
            category="system",
            summary=f"Promoted note: {note.title}",
            detail={
                "note_id": note.note_id,
                "title": note.title,
                "content": note.content,
                "tags": note.tags,
                "source": note.source,
                "word_count": note.word_count,
            },
            tags=note.tags,
        )

        # Ephemeral notes get cleaned up; regular notes persist
        deleted = False
        if note.ephemeral:
            await self.delete(note_id)
            deleted = True

        logger.info(f"Note promoted to manifest: {note_id} → {entry.id} (deleted={deleted})")
        return {"manifest_id": entry.id, "note_id": note_id, "title": note.title, "deleted": deleted}

    async def cleanup_expired(self) -> int:
        """Delete all ephemeral notes past their expires_at. Returns count deleted."""
        now = time.time()
        expired_ids = [
            nid for nid, note in self._notes.items()
            if note.ephemeral and note.expires_at is not None and note.expires_at <= now
        ]
        for nid in expired_ids:
            await self.delete(nid)
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired ephemeral notes")
        return len(expired_ids)

    # ─── Supabase Persistence ────────────────────────────

    def _persist_note(self, note: Note) -> None:
        """Upsert note to Supabase + vault fire-and-forget (best-effort)."""
        if not self._db:
            return
        try:
            from datetime import datetime, timezone as tz
            from vault_gate import build_note_dimensions, gate_and_log

            now = datetime.now(tz.utc).isoformat()

            # Assemble Vault dimensional address
            dimensions = build_note_dimensions(
                pack_id=note.pack_id,
                user_id=note.user_id,
                session_id=note.session_id,
                note_type=note.note_type,
                tags=note.tags,
                manifest_signature=note.manifest_signature,
                content=note.content,
                created_at=note.created_at,
            )
            gate_and_log(dimensions, note.note_id, "note")

            row = {
                "id": note.note_id,
                "session_id": note.session_id,
                "pack_id": note.pack_id,
                "title": note.title,
                "content": note.content,
                "note_type": note.note_type,
                "tags": note.tags,
                "links": note.links,
                "source": note.source,
                "source_id": note.source_id,
                "ephemeral": note.ephemeral,
                "word_count": note.word_count,
                "checksum": note.checksum,
                "dimensions": dimensions,
                "created_at": now,
                "updated_at": now,
            }

            if note.expires_at is not None:
                row["expires_at"] = datetime.fromtimestamp(
                    note.expires_at, tz=tz.utc
                ).isoformat()

            # Only set user_id if it's a valid UUID
            uid = self._parse_user_id(note.user_id)
            if uid:
                row["user_id"] = uid

            self._db.table("notes").upsert(row, on_conflict="id").execute()

            # ── Vault output registration (fire-and-forget, non-ephemeral only) ──
            if not note.ephemeral:
                try:
                    from vault import get_vault_service
                    vault_svc = get_vault_service()
                    content_bytes = note.content.encode("utf-8")
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(vault_svc.register_output(
                            owner_id=note.user_id,
                            filename=f"note_{note.note_id[:8]}.md",
                            storage_path="",
                            file_data=content_bytes,
                            source="note_export",
                            source_id=note.note_id,
                            size_bytes=len(content_bytes),
                            mime_type="text/markdown",
                            pack_id=note.pack_id,
                            session_id=note.session_id,
                            dimensions=dimensions,
                        ))
                except Exception as ve:
                    logger.debug("Vault output registration skipped: %s", ve)

        except Exception as e:
            logger.warning(f"Supabase note persist failed for {note.note_id}: {e}")

    def _delete_note_from_db(self, note_id: str) -> None:
        """Delete a note from Supabase (best-effort)."""
        if not self._db:
            return
        try:
            self._db.table("notes").delete().eq("id", note_id).execute()
        except Exception as e:
            logger.warning(f"Supabase note delete failed for {note_id}: {e}")

    @staticmethod
    def _row_to_note(row: dict) -> Note:
        """Reconstruct a Note from a Supabase row."""
        created_at = time.time()
        if row.get("created_at"):
            try:
                from datetime import datetime as dt_cls
                parsed = dt_cls.fromisoformat(
                    str(row["created_at"]).replace("Z", "+00:00")
                )
                created_at = parsed.timestamp()
            except (ValueError, AttributeError):
                pass

        updated_at = created_at
        if row.get("updated_at"):
            try:
                from datetime import datetime as dt_cls
                parsed = dt_cls.fromisoformat(
                    str(row["updated_at"]).replace("Z", "+00:00")
                )
                updated_at = parsed.timestamp()
            except (ValueError, AttributeError):
                pass

        expires_at = None
        if row.get("expires_at"):
            try:
                from datetime import datetime as dt_cls
                parsed = dt_cls.fromisoformat(
                    str(row["expires_at"]).replace("Z", "+00:00")
                )
                expires_at = parsed.timestamp()
            except (ValueError, AttributeError):
                pass

        return Note(
            note_id=row.get("id", ""),
            title=row.get("title", ""),
            content=row.get("content", ""),
            note_type=row.get("note_type", "note"),
            tags=row.get("tags") or [],
            links=row.get("links") or [],
            user_id=str(row.get("user_id", "anonymous")),
            session_id=row.get("session_id") or "",
            pack_id=row.get("pack_id") or "",
            manifest_signature={},
            source=row.get("source") or "",
            source_id=row.get("source_id") or "",
            created_at=created_at,
            updated_at=updated_at,
            ephemeral=row.get("ephemeral", False),
            expires_at=expires_at,
            word_count=row.get("word_count", 0),
            checksum=row.get("checksum") or "",
        )

    @staticmethod
    def _parse_user_id(user_id: str) -> Optional[str]:
        """Return user_id if it looks like a valid UUID, else None."""
        if not user_id or user_id == "anonymous":
            return None
        try:
            uuid.UUID(user_id)
            return user_id
        except (ValueError, AttributeError):
            return None

    async def load_user_notes(self, user_id: str, limit: int = 200, force: bool = False) -> int:
        """Bulk load a user's notes from Supabase into memory + TF-IDF index.

        Returns the number of notes loaded. Skips if already loaded unless force=True.
        """
        if not self._db:
            return 0
        uid = self._parse_user_id(user_id)
        if not uid:
            return 0
        if uid in self._loaded_users and not force:
            return 0
        try:
            result = (
                self._db.table("notes")
                .select("*")
                .eq("user_id", uid)
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning(f"Supabase load_user_notes failed for {user_id}: {e}")
            return 0

        loaded = 0
        for row in rows:
            note_id = row.get("id", "")
            if note_id in self._notes:
                continue  # already in memory
            note = self._row_to_note(row)
            self._notes[note.note_id] = note
            self._index_note(note)
            loaded += 1

        self._loaded_users.add(uid)
        if loaded:
            logger.info(f"Loaded {loaded} notes from Supabase for user {user_id[:8]}…")
        return loaded

    # ─── Stats ────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._notes)

    def get_stats(self) -> dict:
        """Return note store statistics."""
        type_counts: dict[str, int] = defaultdict(int)
        tag_counts: dict[str, int] = defaultdict(int)
        total_words = 0
        total_links = 0
        ephemeral_count = 0
        for note in self._notes.values():
            type_counts[note.note_type] += 1
            total_words += note.word_count
            total_links += len(note.links)
            if note.ephemeral:
                ephemeral_count += 1
            for tag in note.tags:
                tag_counts[tag] += 1

        return {
            "total_notes": self.count,
            "ephemeral_notes": ephemeral_count,
            "total_words": total_words,
            "total_links": total_links,
            "by_type": dict(type_counts),
            "top_tags": dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:20]),
        }
