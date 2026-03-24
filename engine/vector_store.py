"""
TMOS13 Vector Store — Pinecone Integration

Upgrades RAG from TF-IDF to vector embeddings for semantic search.
Supports Pinecone for storage and OpenAI/Voyage for embeddings.
Falls back to existing TF-IDF RAG when not configured.
"""
import time
import logging
import hashlib
from typing import Optional

logger = logging.getLogger("tmos13.vectors")


class VectorStore:
    """Vector store backed by Pinecone with embedding generation."""

    def __init__(self, pinecone_api_key: str, pinecone_index: str,
                 embedding_api_key: str, embedding_model: str = "text-embedding-3-small",
                 embedding_provider: str = "openai", dimension: int = 1536):
        self._pinecone = None
        self._index = None
        self._embed_fn = None
        self.dimension = dimension
        self.embedding_model = embedding_model

        if not pinecone_api_key or not embedding_api_key:
            logger.info("Vector store not configured — RAG will use TF-IDF fallback")
            return

        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=pinecone_api_key)
            self._index = pc.Index(pinecone_index)
            self._pinecone = pc
            logger.info(f"Pinecone connected: index={pinecone_index}")
        except ImportError:
            logger.warning("pinecone not installed — vector store disabled")
            return
        except Exception as e:
            logger.error(f"Pinecone init failed: {e}")
            return

        # Set up embedding function
        if embedding_provider == "openai":
            try:
                from openai import OpenAI
                oai = OpenAI(api_key=embedding_api_key)
                self._embed_fn = lambda texts: [
                    r.embedding for r in oai.embeddings.create(
                        model=embedding_model, input=texts
                    ).data
                ]
                logger.info(f"Embeddings: OpenAI {embedding_model}")
            except ImportError:
                logger.warning("openai not installed — embeddings disabled")
            except Exception as e:
                logger.error(f"OpenAI embeddings init failed: {e}")
        elif embedding_provider == "voyage":
            try:
                import voyageai
                vc = voyageai.Client(api_key=embedding_api_key)
                self._embed_fn = lambda texts: vc.embed(
                    texts, model=embedding_model
                ).embeddings
                logger.info(f"Embeddings: Voyage {embedding_model}")
            except ImportError:
                logger.warning("voyageai not installed")
            except Exception as e:
                logger.error(f"Voyage embeddings init failed: {e}")

    @property
    def enabled(self) -> bool:
        return self._index is not None and self._embed_fn is not None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not self._embed_fn:
            raise RuntimeError("Embedding function not configured")
        return self._embed_fn(texts)

    def embed_single(self, text: str) -> list[float] | None:
        """Embed a single text string. Returns None if not enabled."""
        if not self.enabled:
            return None
        try:
            return self.embed([text])[0]
        except Exception:
            return None

    def upsert(self, documents: list[dict]):
        """
        Upsert documents into Pinecone.
        Each doc should have: id, content, metadata (source, section, etc.)
        """
        if not self.enabled:
            return

        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            texts = [d["content"] for d in batch]
            embeddings = self.embed(texts)

            vectors = []
            for doc, embedding in zip(batch, embeddings):
                vectors.append({
                    "id": doc.get("id", hashlib.md5(doc["content"].encode()).hexdigest()),
                    "values": embedding,
                    "metadata": {
                        "content": doc["content"][:1000],
                        "source": doc.get("source", ""),
                        "section": doc.get("section", ""),
                        **doc.get("metadata", {}),
                    },
                })

            self._index.upsert(vectors=vectors)
            logger.info(f"Upserted {len(vectors)} vectors (batch {i // batch_size + 1})")

    def search(self, query: str, top_k: int = 5, filter_dict: dict = None) -> list[dict]:
        """Semantic search across indexed documents."""
        if not self.enabled:
            return []

        query_embedding = self.embed([query])[0]

        kwargs = {"vector": query_embedding, "top_k": top_k, "include_metadata": True}
        if filter_dict:
            kwargs["filter"] = filter_dict

        results = self._index.query(**kwargs)

        return [
            {
                "id": match["id"],
                "score": match["score"],
                "content": match.get("metadata", {}).get("content", ""),
                "source": match.get("metadata", {}).get("source", ""),
                "section": match.get("metadata", {}).get("section", ""),
                "metadata": match.get("metadata", {}),
            }
            for match in results.get("matches", [])
        ]

    def delete(self, ids: list[str] = None, delete_all: bool = False):
        """Delete vectors by ID or all."""
        if not self.enabled:
            return
        if delete_all:
            self._index.delete(delete_all=True)
        elif ids:
            self._index.delete(ids=ids)

    def get_stats(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "backend": "none"}
        try:
            stats = self._index.describe_index_stats()
            return {
                "enabled": True,
                "backend": "pinecone",
                "total_vectors": stats.get("total_vector_count", 0),
                "dimension": stats.get("dimension", self.dimension),
                "embedding_model": self.embedding_model,
            }
        except Exception:
            return {"enabled": True, "backend": "pinecone", "error": "stats_unavailable"}


# ─── Hybrid RAG ─────────────────────────────────────────

class HybridRAG:
    """
    Combines vector search with TF-IDF for best results.
    Uses vectors when available, falls back to TF-IDF, or merges both.
    """

    def __init__(self, vector_store: VectorStore, tfidf_engine=None):
        self.vectors = vector_store
        self.tfidf = tfidf_engine

    def search(self, query: str, top_k: int = 5, mode: str = "auto") -> list[dict]:
        """
        Search with configurable mode:
        - "vector": Pinecone only
        - "tfidf": TF-IDF only
        - "hybrid": merge and re-rank
        - "auto": vector if available, else TF-IDF
        """
        if mode == "vector" and self.vectors.enabled:
            return self.vectors.search(query, top_k)
        elif mode == "tfidf" and self.tfidf:
            return self._tfidf_search(query, top_k)
        elif mode == "hybrid" and self.vectors.enabled and self.tfidf:
            return self._hybrid_search(query, top_k)
        elif mode == "auto":
            if self.vectors.enabled:
                return self.vectors.search(query, top_k)
            elif self.tfidf:
                return self._tfidf_search(query, top_k)
        return []

    def _tfidf_search(self, query: str, top_k: int) -> list[dict]:
        """Delegate to existing TF-IDF engine."""
        if not self.tfidf:
            return []
        results = self.tfidf.search(query, top_k)
        return [
            {"id": r.get("id", ""), "score": r.get("score", 0),
             "content": r.get("content", ""), "source": r.get("source", ""),
             "section": r.get("section", "")}
            for r in results
        ]

    def _hybrid_search(self, query: str, top_k: int) -> list[dict]:
        """Merge vector and TF-IDF results with reciprocal rank fusion."""
        vec_results = self.vectors.search(query, top_k * 2) if self.vectors.enabled else []
        tfidf_results = self._tfidf_search(query, top_k * 2)

        # Reciprocal Rank Fusion
        k = 60  # RRF constant
        scores: dict[str, float] = {}
        contents: dict[str, dict] = {}

        for rank, r in enumerate(vec_results):
            rid = r["id"]
            scores[rid] = scores.get(rid, 0) + 1.0 / (k + rank + 1)
            contents[rid] = r

        for rank, r in enumerate(tfidf_results):
            rid = r.get("id", r.get("source", "") + r.get("section", ""))
            scores[rid] = scores.get(rid, 0) + 1.0 / (k + rank + 1)
            if rid not in contents:
                contents[rid] = r

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [
            {**contents[rid], "score": scores[rid], "method": "hybrid"}
            for rid in sorted_ids
        ]

    def get_context_for_query(self, query: str, max_tokens: int = 1500,
                              current_game: str = None) -> str:
        """Get formatted context string for prompt injection."""
        filter_dict = {"source": current_game} if current_game and self.vectors.enabled else None

        if self.vectors.enabled:
            results = self.vectors.search(query, top_k=5, filter_dict=filter_dict)
        elif self.tfidf:
            results = self._tfidf_search(query, top_k=5)
        else:
            return ""

        if not results:
            return ""

        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 4

        for r in results:
            content = r.get("content", "")
            if total_chars + len(content) > char_limit:
                break
            source = r.get("source", "unknown")
            section = r.get("section", "")
            header = f"[{source}" + (f":{section}" if section else "") + "]"
            context_parts.append(f"{header}\n{content}")
            total_chars += len(content)

        return "\n\n".join(context_parts)


# ─── Module State ───────────────────────────────────────

_vector_store: Optional[VectorStore] = None
_hybrid_rag: Optional[HybridRAG] = None


def init_vector_store(pinecone_api_key: str = "", pinecone_index: str = "tmos13",
                      embedding_api_key: str = "", embedding_model: str = "text-embedding-3-small",
                      embedding_provider: str = "openai") -> VectorStore:
    global _vector_store
    _vector_store = VectorStore(pinecone_api_key, pinecone_index,
                                embedding_api_key, embedding_model, embedding_provider)
    return _vector_store


def init_hybrid_rag(vector_store: VectorStore, tfidf_engine=None) -> HybridRAG:
    global _hybrid_rag
    _hybrid_rag = HybridRAG(vector_store, tfidf_engine)
    return _hybrid_rag
