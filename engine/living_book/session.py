"""
Living Book Session — builds governed session context for book interactions.
"""

from pathlib import Path

from .retriever import BookRetriever


PROTOCOLS_BASE = Path(__file__).resolve().parent.parent.parent / "protocols" / "books"


class LivingBookSession:
    """Manages a governed session for interacting with a Living Book."""

    def __init__(self, book_id: str):
        self.book_id = book_id
        self.book_dir = PROTOCOLS_BASE / book_id
        self.retriever = BookRetriever(book_id)

    def get_system_prompt(self) -> str:
        """Load the master.md execution rules as the system prompt."""
        master_path = self.book_dir / "master.md"
        if not master_path.exists():
            return f"You are a Living Book session for book '{self.book_id}'. The text is authoritative."
        return master_path.read_text(encoding="utf-8")

    def get_book_context(self) -> str:
        """Build [LIVING BOOK CONTEXT] block with the full chunk index."""
        lines = [
            "[LIVING BOOK CONTEXT]",
            f"Book: {self.book_id}",
            f"Total chunks: {self.retriever.chunk_count}",
            "",
            "## Chunk Index",
        ]
        for chunk in self.retriever.chunks:
            keywords = ", ".join(chunk.get("keywords", [])[:5])
            preview = chunk["text"][:120].replace("\n", " ")
            lines.append(f"- **{chunk['id']}** | {chunk['label']} | keywords: {keywords} | {preview}...")

        lines.append("")
        lines.append("[/LIVING BOOK CONTEXT]")
        return "\n".join(lines)

    def retrieve_for_query(self, query: str) -> str:
        """Retrieve relevant passages for a query."""
        return self.retriever.build_retrieval_context(query)

    def build_augmented_message(self, user_message: str) -> str:
        """Prepend retrieved passages to the user's message."""
        context = self.retrieve_for_query(user_message)
        return (
            f"[RETRIEVED PASSAGES]\n{context}\n[/RETRIEVED PASSAGES]\n\n"
            f"{user_message}"
        )
