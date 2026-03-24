"""
TMOS13 Embedding Pipeline — generates and indexes embeddings for semantic search.

Hooks into deliverable save + journal save. Falls back gracefully when
VectorStore not configured. All methods are non-fatal — log and return on failure.

Singleton pattern: init_embedding_pipeline(vector_store) / get_embedding_pipeline().
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger("tmos13.embedding_pipeline")


class EmbeddingPipeline:
    """Embed-on-save pipeline for deliverables, journals, and consolidations."""

    def __init__(self, vector_store):
        self._vs = vector_store
        logger.info("Embedding pipeline initialized (vector_store.enabled=%s)", vector_store.enabled)

    @property
    def enabled(self) -> bool:
        return self._vs is not None and self._vs.enabled

    def embed_deliverable(self, row: dict) -> bool:
        """
        Embed a deliverable row into the vector store.

        Expects row keys: id, spec_name, extracted_data, metadata, user_id, pack_id, created_at.
        Returns True on success, False on skip/failure.
        """
        if not self.enabled:
            return False

        try:
            text = self._deliverable_to_text(row)
            if not text or len(text.strip()) < 10:
                return False

            doc_id = f"del_{row.get('id', hashlib.md5(text.encode()).hexdigest())}"
            self._vs.upsert([{
                "id": doc_id,
                "content": text[:2000],
                "metadata": {
                    "user_id": str(row.get("user_id", "")),
                    "pack_id": str(row.get("pack_id", "")),
                    "source_type": "deliverable",
                    "spec_name": str(row.get("spec_name", "")),
                    "created_at": str(row.get("created_at", "")),
                },
            }])
            logger.debug("Embedded deliverable %s", doc_id)
            return True
        except Exception as e:
            logger.warning("Embed deliverable failed: %s", e)
            return False

    def embed_journal_insight(self, row: dict) -> bool:
        """
        Embed a session journal insight into the vector store.

        Expects row keys: insight, pack_id, user_id, session_id.
        Returns True on success, False on skip/failure.
        """
        if not self.enabled:
            return False

        insight = row.get("insight", "")
        if not insight or len(insight.strip()) < 10:
            return False

        try:
            pack_id = row.get("pack_id", "")
            text = f"{pack_id}: {insight}" if pack_id else insight

            doc_id = f"jrn_{row.get('session_id', hashlib.md5(text.encode()).hexdigest())}"
            self._vs.upsert([{
                "id": doc_id,
                "content": text[:2000],
                "metadata": {
                    "user_id": str(row.get("user_id", "")),
                    "pack_id": str(pack_id),
                    "source_type": "journal",
                    "session_id": str(row.get("session_id", "")),
                },
            }])
            logger.debug("Embedded journal insight %s", doc_id)
            return True
        except Exception as e:
            logger.warning("Embed journal insight failed: %s", e)
            return False

    def embed_consolidation(self, row: dict) -> bool:
        """
        Embed a consolidated memory summary into the vector store.

        Expects row keys: id, summary, user_id, pack_id.
        Returns True on success, False on skip/failure.
        """
        if not self.enabled:
            return False

        summary = row.get("summary", "")
        if not summary or len(summary.strip()) < 10:
            return False

        try:
            pack_id = row.get("pack_id", "")
            text = f"Consolidated pattern ({pack_id}): {summary}" if pack_id else f"Consolidated pattern: {summary}"

            doc_id = f"con_{row.get('id', hashlib.md5(text.encode()).hexdigest())}"
            self._vs.upsert([{
                "id": doc_id,
                "content": text[:2000],
                "metadata": {
                    "user_id": str(row.get("user_id", "")),
                    "pack_id": str(pack_id),
                    "source_type": "consolidation",
                },
            }])
            logger.debug("Embedded consolidation %s", doc_id)
            return True
        except Exception as e:
            logger.warning("Embed consolidation failed: %s", e)
            return False

    def search_user_memories(
        self,
        user_id: str,
        query: str,
        source_types: list[str] | None = None,
        pack_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Semantic search across all indexed content for a user.

        Returns list of dicts with: id, score, content, source, metadata.
        """
        if not self.enabled:
            return []
        if not user_id or not query:
            return []

        try:
            filter_dict: dict = {"user_id": str(user_id)}
            if source_types:
                filter_dict["source_type"] = {"$in": source_types}
            if pack_id:
                filter_dict["pack_id"] = str(pack_id)

            results = self._vs.search(query, top_k=top_k, filter_dict=filter_dict)
            return results
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)
            return []

    @staticmethod
    def _deliverable_to_text(row: dict) -> str:
        """Extract searchable text from a deliverable row."""
        parts = []
        spec_name = row.get("spec_name", "")
        if spec_name:
            parts.append(spec_name)

        extracted = row.get("extracted_data") or {}
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                if v is not None:
                    parts.append(f"{k}: {v}")

        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict):
            for k in ("title", "summary", "description"):
                v = metadata.get(k)
                if v:
                    parts.append(str(v))

        return " | ".join(parts)


# ─── Singleton ────────────────────────────────────────────

_embedding_pipeline: Optional[EmbeddingPipeline] = None


def init_embedding_pipeline(vector_store) -> EmbeddingPipeline:
    """Initialize the global EmbeddingPipeline singleton."""
    global _embedding_pipeline
    _embedding_pipeline = EmbeddingPipeline(vector_store)
    return _embedding_pipeline


def get_embedding_pipeline() -> Optional[EmbeddingPipeline]:
    """Return the global EmbeddingPipeline or None."""
    return _embedding_pipeline
