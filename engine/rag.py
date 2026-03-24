"""
TMOS13 RAG — Retrieval-Augmented Generation Pipeline

Provides semantic search over:
  - Protocol files (module rules, system screens, master protocol)
  - Wisdom corpus (philosophy, strategy, psychology references)
  - Session memories (cross-session narrative state)

Uses TF-IDF for lightweight local search (no external vector DB needed).
Optionally integrates with Supabase pgvector for production-grade search.

The RAG pipeline enriches Claude's context with relevant protocol
fragments when the assembled prompt would benefit from targeted retrieval
instead of loading entire protocol files.
"""
import math
import re
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

from config import PROTOCOL_DIR, get_pack, get_cartridges, logger

logger = logging.getLogger("tmos13.rag")


# ─── Document Store ───────────────────────────────────────

class Document:
    """A searchable text chunk with metadata."""
    __slots__ = ("id", "source", "section", "content", "tokens")

    def __init__(self, doc_id: str, source: str, section: str, content: str):
        self.id = doc_id
        self.source = source
        self.section = section
        self.content = content
        self.tokens = _tokenize(content)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"[a-z0-9']+", text.lower())


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total."""
    counts: dict[str, int] = defaultdict(int)
    for t in tokens:
        counts[t] += 1
    total = len(tokens) or 1
    return {t: c / total for t, c in counts.items()}


# ─── TF-IDF Index ─────────────────────────────────────────

class TFIDFIndex:
    """Lightweight in-memory TF-IDF search index."""

    def __init__(self):
        self.documents: list[Document] = []
        self._df: dict[str, int] = defaultdict(int)
        self._tf_cache: dict[str, dict[str, float]] = {}
        self._dirty = True

    def add_document(self, doc: Document):
        self.documents.append(doc)
        self._dirty = True

    def _rebuild_if_dirty(self):
        if not self._dirty:
            return
        self._df.clear()
        self._tf_cache.clear()
        for doc in self.documents:
            tf = _compute_tf(doc.tokens)
            self._tf_cache[doc.id] = tf
            for term in tf:
                self._df[term] += 1
        self._dirty = False

    def search(self, query: str, max_results: int = 5,
               source_filter: Optional[str] = None) -> list[dict]:
        """Search the index and return ranked results."""
        self._rebuild_if_dirty()
        if not self.documents:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        n_docs = len(self.documents)
        scores: list[tuple[float, Document]] = []

        for doc in self.documents:
            if source_filter and doc.source != source_filter:
                continue
            tf = self._tf_cache.get(doc.id, {})
            score = 0.0
            for qt in query_tokens:
                if qt in tf:
                    df = self._df.get(qt, 1)
                    idf = math.log(n_docs / df) + 1
                    score += tf[qt] * idf
            if score > 0:
                scores.append((score, doc))

        scores.sort(key=lambda x: -x[0])

        return [
            {
                "id": doc.id,
                "source": doc.source,
                "section": doc.section,
                "score": round(score, 4),
                "content": doc.content[:300] + ("..." if len(doc.content) > 300 else ""),
            }
            for score, doc in scores[:max_results]
        ]

    @property
    def document_count(self) -> int:
        return len(self.documents)


# ─── Protocol Chunker ─────────────────────────────────────

def _chunk_protocol(filename: str, content: str) -> list[Document]:
    """Split a protocol file into searchable chunks by section headers."""
    docs = []
    current_section = "header"
    current_lines: list[str] = []
    chunk_idx = 0

    for line in content.split("\n"):
        stripped = line.strip()
        # Detect XML-style section boundaries (<entry>, <phases>, etc.)
        if stripped.startswith("<") and stripped.endswith(">") and not stripped.startswith("</"):
            if current_lines:
                chunk_text = "\n".join(current_lines).strip()
                if chunk_text and len(chunk_text) > 20:
                    doc_id = f"{filename}:{current_section}:{chunk_idx}"
                    docs.append(Document(doc_id, filename, current_section, chunk_text))
                    chunk_idx += 1

            tag = stripped.strip("<>").split()[0].lower()
            current_section = tag
            current_lines = [line]
        # Detect markdown-style section headers
        elif stripped.startswith("# ") or stripped.startswith("## "):
            if current_lines:
                chunk_text = "\n".join(current_lines).strip()
                if chunk_text and len(chunk_text) > 20:
                    doc_id = f"{filename}:{current_section}:{chunk_idx}"
                    docs.append(Document(doc_id, filename, current_section, chunk_text))
                    chunk_idx += 1

            current_section = stripped.lstrip("# ").lower().replace(" ", "_")[:30]
            current_lines = [line]
        else:
            current_lines.append(line)

    # Final chunk
    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if chunk_text and len(chunk_text) > 20:
            doc_id = f"{filename}:{current_section}:{chunk_idx}"
            docs.append(Document(doc_id, filename, current_section, chunk_text))

    return docs


# ─── RAG Engine ───────────────────────────────────────────

class RAGEngine:
    """
    Retrieval-Augmented Generation engine for TMOS13.

    Indexes all protocol files on startup and provides semantic search
    that can be used to enrich Claude's context with targeted fragments.
    """

    def __init__(self, protocol_dir: Path = None):
        if protocol_dir is not None:
            self.protocol_dir = protocol_dir
        else:
            pack = get_pack()
            self.protocol_dir = pack.protocol_dir if pack else PROTOCOL_DIR
        self.index = TFIDFIndex()
        self._indexed = False

    def build_index(self):
        """Index all protocol files."""
        if not self.protocol_dir.exists():
            logger.warning(f"RAG: Protocol directory not found: {self.protocol_dir}")
            return

        count = 0
        for f in self.protocol_dir.rglob("*.md"):
            content = f.read_text(encoding="utf-8")
            chunks = _chunk_protocol(f.name, content)
            for doc in chunks:
                self.index.add_document(doc)
            count += 1

        self._indexed = True
        logger.info(
            f"RAG: Indexed {self.index.document_count} chunks "
            f"from {count} protocol files"
        )

    def rebuild_index(self):
        """Force rebuild (e.g. after protocol hot-reload)."""
        self.index = TFIDFIndex()
        self._indexed = False
        self.build_index()

    def add_memory_documents(self, session_id: str, memories: dict):
        """Index a session's cross-game memories for retrieval."""
        for key, value in memories.items():
            doc = Document(
                f"memory:{session_id}:{key}",
                "memory",
                key,
                f"{key}: {value}",
            )
            self.index.add_document(doc)

    def add_uploaded_document(self, file_id: str, filename: str, text: str):
        """
        Index an uploaded text file for RAG search.

        Called by the file processor after a text file is uploaded,
        chunking the content and adding each chunk to the search index.
        """
        from files import chunk_text
        chunks = chunk_text(text, max_chunk_size=2000, overlap=200, file_id=file_id)
        for chunk in chunks:
            doc = Document(
                f"upload:{file_id}:{chunk.index}",
                f"upload:{filename}",
                f"chunk_{chunk.index}",
                chunk.content,
            )
            self.index.add_document(doc)
        logger.info(
            f"RAG: Indexed uploaded file '{filename}' — {len(chunks)} chunks"
        )

    def search(self, query: str, max_results: int = 5,
               source_filter: Optional[str] = None) -> list[dict]:
        """Search the index."""
        if not self._indexed:
            self.build_index()
        return self.index.search(query, max_results, source_filter)

    def get_context_for_query(self, query: str,
                              current_game: Optional[str] = None,
                              max_tokens: int = 500) -> str:
        """
        Retrieve relevant protocol fragments for a user query.
        Returns a formatted string suitable for injection into the system prompt.

        Prioritizes the current game's protocol, then global protocols.
        """
        results = self.search(query, max_results=8)

        # Boost current game's results to the top
        cartridges = get_cartridges()
        if current_game and current_game in cartridges:
            game_file = cartridges[current_game]["file"]
            results.sort(key=lambda r: (0 if r["source"] == game_file else 1, -r["score"]))

        # Build context string within token budget
        context_parts = []
        token_count = 0
        for r in results:
            chunk_tokens = len(r["content"]) // 4
            if token_count + chunk_tokens > max_tokens:
                break
            context_parts.append(f"[{r['source']}:{r['section']}] {r['content']}")
            token_count += chunk_tokens

        if not context_parts:
            return ""

        return "[RAG CONTEXT — Relevant protocol fragments]\n" + "\n---\n".join(context_parts)

    def get_stats(self) -> dict:
        """Return index statistics."""
        sources: dict[str, int] = defaultdict(int)
        for doc in self.index.documents:
            sources[doc.source] += 1
        return {
            "indexed": self._indexed,
            "total_chunks": self.index.document_count,
            "sources": dict(sources),
        }


# ─── RAG Endpoint Registration ────────────────────────────

def register_rag_endpoints(app, rag: RAGEngine):
    """Register /rag/ endpoints."""
    from pydantic import BaseModel

    class SearchRequest(BaseModel):
        query: str
        max_results: int = 5
        source_filter: Optional[str] = None

    class ContextRequest(BaseModel):
        query: str
        current_game: Optional[str] = None
        max_tokens: int = 500

    @app.post("/rag/search")
    async def rag_search(req: SearchRequest):
        """Search the protocol index."""
        results = rag.search(req.query, req.max_results, req.source_filter)
        return {"query": req.query, "results": results}

    @app.post("/rag/context")
    async def rag_context(req: ContextRequest):
        """Get RAG-enriched context for a query."""
        context = rag.get_context_for_query(
            req.query, req.current_game, req.max_tokens
        )
        return {
            "query": req.query,
            "context": context,
            "context_tokens_est": len(context) // 4,
        }

    @app.get("/rag/stats")
    async def rag_stats():
        return rag.get_stats()

    @app.post("/rag/rebuild")
    async def rag_rebuild():
        """Rebuild the search index (e.g. after protocol hot-reload)."""
        rag.rebuild_index()
        return rag.get_stats()
