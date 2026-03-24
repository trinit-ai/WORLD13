"""
Living Book Retriever — loads indexed book data and provides search/retrieval.
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml


PROTOCOLS_BASE = Path(__file__).resolve().parent.parent.parent / "protocols" / "books"


class BookRetriever:
    """Loads and searches a book's chunked text and index."""

    def __init__(self, book_id: str):
        self.book_id = book_id
        self.book_dir = PROTOCOLS_BASE / book_id
        self.text_dir = self.book_dir / "text"

        # Load chunks
        chunks_path = self.text_dir / "chunks.json"
        if not chunks_path.exists():
            raise FileNotFoundError(f"No chunks.json found for book '{book_id}' at {chunks_path}")
        chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
        self.chunks: list[dict] = chunks_data["chunks"]
        self.chunk_count: int = chunks_data["chunk_count"]

        # Build lookup maps
        self._by_id: dict[str, dict] = {c["id"]: c for c in self.chunks}
        self._by_number: dict[int, dict] = {c["number"]: c for c in self.chunks}

        # Load index
        index_path = self.text_dir / "index.yaml"
        if index_path.exists():
            self.index = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
        else:
            self.index = {}

        self.cross_references: dict[str, list[str]] = self.index.get("cross_references", {})

    def get_chunk(self, chunk_id: str) -> dict | None:
        """Retrieve a chunk by its ID."""
        return self._by_id.get(chunk_id)

    def get_chapter(self, number: int) -> dict | None:
        """Retrieve a chunk by its chapter/verse/paragraph number."""
        return self._by_number.get(number)

    def search_keyword(self, keyword: str, max_results: int = 5) -> list[dict]:
        """Search for chunks whose text contains the keyword."""
        keyword_lower = keyword.lower()
        results = []
        for chunk in self.chunks:
            if keyword_lower in chunk["text"].lower():
                results.append(chunk)
                if len(results) >= max_results:
                    break
        return results

    def search_theme(self, theme: str, max_results: int = 5) -> list[dict]:
        """Search for chunks matching a keyword or theme tag."""
        theme_lower = theme.lower()
        results = []
        for chunk in self.chunks:
            tags = [k.lower() for k in chunk.get("keywords", []) + chunk.get("themes", [])]
            if any(theme_lower in tag for tag in tags):
                results.append(chunk)
                if len(results) >= max_results:
                    break
        return results

    def get_cross_references(self, term: str) -> list[str]:
        """Return chunk IDs that share a cross-reference term."""
        term_lower = term.lower()
        # Exact match first
        if term_lower in self.cross_references:
            return self.cross_references[term_lower]
        # Partial match fallback
        for key, chunk_ids in self.cross_references.items():
            if term_lower in key or key in term_lower:
                return chunk_ids
        return []

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        General search scoring chunks by keyword overlap and text matches.
        Returns top-scoring chunks.
        """
        query_words = set(re.findall(r"[a-zA-Z]+", query.lower()))
        scored: list[tuple[float, dict]] = []

        for chunk in self.chunks:
            score = 0.0
            text_lower = chunk["text"].lower()
            chunk_keywords = set(k.lower() for k in chunk.get("keywords", []))

            # Keyword overlap score
            overlap = query_words & chunk_keywords
            score += len(overlap) * 3.0

            # Text match score
            for word in query_words:
                if len(word) >= 3 and word in text_lower:
                    score += 1.0

            # Exact phrase bonus
            if query.lower() in text_lower:
                score += 5.0

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:max_results]]

    def format_chunk_for_session(self, chunk: dict) -> str:
        """Format a chunk for display in a session."""
        return f"[{chunk['label']}]\n{chunk['text']}"

    def build_retrieval_context(self, query: str, max_chunks: int = 3) -> str:
        """Build formatted context from relevant passages for a query."""
        results = self.search(query, max_results=max_chunks)
        if not results:
            return "[No relevant passages found for this query.]"

        sections = []
        for chunk in results:
            sections.append(self.format_chunk_for_session(chunk))

        return "\n\n---\n\n".join(sections)
