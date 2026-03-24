"""
Living Book Ingestor — ingests raw text into a governed book pack.

Chunks text by structure (chapters, verses, paragraphs), builds indexes,
and writes all protocol files needed for a Living Book session.
"""

import json
import re
import string
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PROTOCOLS_BASE = Path(__file__).resolve().parent.parent.parent / "protocols" / "books"

# Common English words to exclude from keyword extraction
STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "was", "are", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "must", "not", "no", "nor", "so", "if", "then", "than", "that",
    "this", "these", "those", "he", "she", "they", "we", "i", "you",
    "me", "him", "her", "us", "them", "my", "your", "his", "its",
    "our", "their", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "too", "very",
    "just", "because", "about", "into", "through", "during", "before",
    "after", "above", "below", "between", "out", "off", "over", "under",
    "again", "further", "once", "here", "there", "any", "up", "down",
    "also", "until", "while", "upon", "still", "yet", "now", "even",
    "one", "two", "three", "said", "like", "came", "went", "made",
    "much", "many", "well", "back", "long", "great", "little", "first",
    "last", "never", "always", "sometimes", "often", "however", "though",
    "among", "around", "since", "without", "within", "along", "across",
    "behind", "beyond", "toward", "whether", "whose", "nothing", "something",
    "everything", "anything", "himself", "herself", "itself", "themselves",
    "ourselves", "yourself", "myself", "another", "let", "say", "tell",
    "know", "see", "come", "take", "make", "go", "get", "give", "put",
    "set", "think", "call", "keep", "find", "seem", "leave", "turn",
    "begin", "show", "hear", "play", "run", "move", "live", "believe",
    "bring", "happen", "write", "sit", "stand", "lose", "pay", "meet",
    "already", "ever", "far", "away", "enough", "quite", "rather",
})

MIN_KEYWORD_LENGTH = 4
MIN_KEYWORD_FREQ = 2
MAX_KEYWORDS_PER_CHUNK = 8


class BookIngestor:
    """Ingests raw text into a structured, governed book pack."""

    def __init__(
        self,
        book_id: str,
        title: str,
        author: str,
        translator: str = "",
        year: str = "",
        license: str = "public_domain",
        structure_type: str = "chapters",
    ):
        self.book_id = book_id
        self.title = title
        self.author = author
        self.translator = translator
        self.year = year
        self.license = license
        self.structure_type = structure_type

        self.book_dir = PROTOCOLS_BASE / book_id
        self.text_dir = self.book_dir / "text"

    def ingest(self, raw_text: str) -> dict[str, Any]:
        """Ingest raw text into a complete book pack. Returns summary dict."""
        # Create directories
        self.book_dir.mkdir(parents=True, exist_ok=True)
        self.text_dir.mkdir(parents=True, exist_ok=True)

        # Save full text
        (self.text_dir / "full_text.txt").write_text(raw_text, encoding="utf-8")

        # Chunk by structure
        chunks = self._chunk_text(raw_text)

        # Save chunks
        chunks_data = {
            "book_id": self.book_id,
            "chunk_count": len(chunks),
            "chunks": chunks,
        }
        (self.text_dir / "chunks.json").write_text(
            json.dumps(chunks_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Build and save index
        index = self._build_index(chunks)
        (self.text_dir / "index.yaml").write_text(
            yaml.dump(index, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

        # Write protocol files
        self._write_header()
        self._write_manifest_json()
        self._write_manifest_md()
        self._write_master_md()

        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "chunks": len(chunks),
            "structure": self.structure_type,
            "path": str(self.book_dir),
        }

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[dict]:
        """Split text into chunks based on structure_type."""
        if self.structure_type == "chapters":
            return self._chunk_by_chapters(text)
        elif self.structure_type == "verses":
            return self._chunk_by_verses(text)
        else:
            return self._chunk_by_paragraphs(text)

    def _chunk_by_chapters(self, text: str) -> list[dict]:
        # Match "Chapter 1", "Chapter One", "Chapter Twenty-one", "Chapter XLII", etc.
        pattern = re.compile(
            r"(?:^|\n)(Chapter\s+[\w-]+[^\n]*)",
            re.IGNORECASE,
        )
        splits = list(pattern.finditer(text))
        if not splits:
            return self._chunk_by_paragraphs(text)

        chunks = []
        for i, match in enumerate(splits):
            start = match.start()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            chunk_text = self._clean_chunk(text[start:end].strip())
            if not chunk_text:
                continue
            label = match.group(1).strip()
            number = i + 1
            keywords = self._extract_keywords(chunk_text)
            chunks.append({
                "id": f"{self.book_id}_ch{number:03d}",
                "label": label,
                "number": number,
                "text": chunk_text,
                "keywords": keywords,
                "themes": keywords[:3],
            })
        return chunks

    def _chunk_by_verses(self, text: str) -> list[dict]:
        pattern = re.compile(r"(?:^|\n)(\d+)\.\s+")
        splits = list(pattern.finditer(text))
        if not splits:
            return self._chunk_by_paragraphs(text)

        chunks = []
        for i, match in enumerate(splits):
            start = match.start()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            chunk_text = self._clean_chunk(text[start:end].strip())
            if not chunk_text:
                continue
            number = int(match.group(1))
            keywords = self._extract_keywords(chunk_text)
            chunks.append({
                "id": f"{self.book_id}_v{number:04d}",
                "label": f"Verse {number}",
                "number": number,
                "text": chunk_text,
                "keywords": keywords,
                "themes": keywords[:3],
            })
        return chunks

    def _chunk_by_paragraphs(self, text: str) -> list[dict]:
        paragraphs = re.split(r"\n\s*\n", text)
        chunks = []
        number = 0
        for para in paragraphs:
            cleaned = self._clean_chunk(para.strip())
            if not cleaned or len(cleaned) < 40:
                continue
            number += 1
            keywords = self._extract_keywords(cleaned)
            chunks.append({
                "id": f"{self.book_id}_p{number:04d}",
                "label": f"Paragraph {number}",
                "number": number,
                "text": cleaned,
                "keywords": keywords,
                "themes": keywords[:3],
            })
        return chunks

    # ------------------------------------------------------------------
    # Text processing
    # ------------------------------------------------------------------

    def _clean_chunk(self, text: str) -> str:
        """Remove non-Latin script lines from chunk text."""
        cleaned_lines = []
        for line in text.split("\n"):
            # Keep lines that are mostly Latin characters, digits, punctuation, whitespace
            latin_chars = sum(
                1 for c in line if c in string.ascii_letters or c in string.digits
                or c in string.punctuation or c in string.whitespace
            )
            if len(line) == 0 or (latin_chars / max(len(line), 1)) > 0.5:
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract significant concept words from text."""
        words = re.findall(r"[a-zA-Z]+", text.lower())
        words = [w for w in words if w not in STOP_WORDS and len(w) >= MIN_KEYWORD_LENGTH]
        counts = Counter(words)
        # Return top keywords by frequency
        top = [
            word for word, count in counts.most_common(MAX_KEYWORDS_PER_CHUNK * 2)
            if count >= MIN_KEYWORD_FREQ or len(counts) < 20
        ]
        return top[:MAX_KEYWORDS_PER_CHUNK]

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_index(self, chunks: list[dict]) -> dict:
        """Build cross-reference map by keyword."""
        keyword_to_chunks: dict[str, list[str]] = defaultdict(list)
        for chunk in chunks:
            for kw in chunk["keywords"]:
                keyword_to_chunks[kw].append(chunk["id"])

        cross_references = {
            kw: chunk_ids
            for kw, chunk_ids in sorted(keyword_to_chunks.items())
            if len(chunk_ids) > 1
        }

        return {
            "book_id": self.book_id,
            "title": self.title,
            "chunk_count": len(chunks),
            "cross_references": cross_references,
        }

    # ------------------------------------------------------------------
    # Protocol file writers
    # ------------------------------------------------------------------

    def _write_header(self):
        header = {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "translator": self.translator,
            "year": self.year,
            "license": self.license,
            "structure_type": self.structure_type,
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        }
        (self.book_dir / "header.yaml").write_text(
            yaml.dump(header, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _write_manifest_json(self):
        manifest = {
            "pack_id": f"book_{self.book_id}",
            "type": "living_book",
            "title": self.title,
            "author": self.author,
            "book_id": self.book_id,
            "structure_type": self.structure_type,
            "license": self.license,
        }
        (self.book_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def _write_manifest_md(self):
        content = f"""# MANIFEST — {self.title}

## Purpose

This is a Living Book pack. The ingested text is the **authoritative layer**.
The model's role is to help the reader navigate, search, and understand
the text — never to replace, fabricate, or substitute its own training
knowledge for what the text actually says.

## Authorization

### Authorized actions
- Navigate the text (chapters, verses, passages)
- Search by keyword, theme, or concept
- Cite passages with accurate references
- Offer interpretation **clearly marked as interpretation**
- Compare passages within the text

### Prohibited actions
- Fabricating quotes or passages not in the text
- Substituting training knowledge for textual content
- Presenting interpretation as if it were the text
- Inventing references or citations
- Summarizing without grounding in actual passages

## Citation Required

Every claim about the text MUST include a citation:
- Chapter/verse/paragraph number
- Direct quote from the text
- If paraphrasing, mark explicitly: "In my reading..." or "This appears to..."

## Session Modes

| Mode | Description |
|------|-------------|
| exploration | Browse the text freely, discover themes |
| query | Answer specific questions with cited passages |
| close_reading | Deep analysis of a specific passage |
| comparative | Compare passages across the text |
| study | Guided study with questions and exercises |

## Voice

Scholarly but accessible. The text leads; the model serves.
Never lecture beyond the text. Honest about limits of knowledge.

## Kill List

- Do NOT invent passages
- Do NOT present training knowledge as textual content
- Do NOT skip citation when making claims
- Do NOT override the text with external opinions
- Do NOT hallucinate chapter/verse numbers
"""
        (self.book_dir / "MANIFEST.md").write_text(content, encoding="utf-8")

    def _write_master_md(self):
        content = f"""# Living Book Execution Rules — {self.title}

You are operating as a Living Book session for **{self.title}** by {self.author}.

## Core Rules

### 1. Text First
The ingested text is your primary source. When the reader asks about the text,
answer FROM the text. Do not default to training knowledge.

### 2. Citation Required
Every factual claim about the text must include:
- The chunk/chapter/verse reference
- A direct quote or explicit paraphrase marker

### 3. Interpretation Marked
You may offer interpretation, but ALWAYS mark it:
- "In my reading..."
- "This could suggest..."
- "One interpretation is..."
Never present interpretation as the text's own claim.

### 4. Honest Limits
If a passage is ambiguous, say so. If the text doesn't address a question,
say so. Do not fill gaps with training knowledge presented as textual content.

### 5. Follow the Reader
The reader sets the pace and direction. You navigate where they point.
Suggest related passages when relevant, but don't lecture unsolicited.

### 6. Text Has Authority
If your training knowledge conflicts with the text, the text wins.
Note the discrepancy if relevant, but defer to the source material.
"""
        (self.book_dir / "master.md").write_text(content, encoding="utf-8")
