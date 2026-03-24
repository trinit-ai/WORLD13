"""
TMOS13 Relevance Scoring — local TF-IDF cosine similarity + vector reranking.

Used by vault_rag, session_journal, and knowledge_bridge for message-aware
retrieval. Pure computation, no IO, no external dependencies.

When Pinecone is available, vector similarity scores are blended with
TF-IDF. When not available, TF-IDF alone provides a meaningful relevance
signal that beats recency-only ordering.
"""
import math
import re
import logging
from collections import Counter

logger = logging.getLogger("tmos13.relevance")

# Tokenizer: same pattern as rag.py for consistency
_TOKEN_RE = re.compile(r"[a-z0-9']+")

# Common English stop words (minimal set — keeps scoring lightweight)
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "to", "of", "and", "or", "for",
    "on", "at", "by", "with", "this", "that", "was", "are", "be", "has",
    "had", "have", "do", "does", "did", "will", "would", "could", "should",
    "not", "but", "from", "they", "we", "he", "she", "you", "i", "my",
    "me", "your", "its", "our", "their", "so", "if", "no", "yes", "as",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens, removing stop words."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS]


def compute_text_relevance(query: str, document: str) -> float:
    """
    Compute TF-IDF cosine similarity between query and document.

    Returns a float 0.0–1.0. Pure computation, no IO.
    Handles edge cases: empty strings → 0.0, identical strings → ~1.0.
    """
    if not query or not document:
        return 0.0

    query_tokens = _tokenize(query)
    doc_tokens = _tokenize(document)

    if not query_tokens or not doc_tokens:
        return 0.0

    # Build term frequency vectors
    query_tf = Counter(query_tokens)
    doc_tf = Counter(doc_tokens)

    # Vocabulary is the union
    vocab = set(query_tf.keys()) | set(doc_tf.keys())
    if not vocab:
        return 0.0

    # IDF approximation: treat query and document as two "documents"
    # Terms in both get lower IDF weight, terms in one get higher weight
    doc_count = 2  # we have two "documents"
    idf = {}
    for term in vocab:
        df = (1 if term in query_tf else 0) + (1 if term in doc_tf else 0)
        idf[term] = math.log((doc_count + 1) / (df + 1)) + 1  # smoothed IDF

    # Build TF-IDF vectors
    q_vec = {t: query_tf[t] * idf.get(t, 1) for t in query_tf}
    d_vec = {t: doc_tf[t] * idf.get(t, 1) for t in doc_tf}

    # Cosine similarity
    dot = sum(q_vec.get(t, 0) * d_vec.get(t, 0) for t in vocab)
    mag_q = math.sqrt(sum(v * v for v in q_vec.values()))
    mag_d = math.sqrt(sum(v * v for v in d_vec.values()))

    if mag_q == 0 or mag_d == 0:
        return 0.0

    similarity = dot / (mag_q * mag_d)
    return max(0.0, min(1.0, similarity))


def blend_scores(
    recency_score: float,
    relevance_score: float,
    boost_factor: float = 0.3,
) -> float:
    """
    Weighted blend of recency and relevance scores.

    boost_factor controls weight: 0.0 = pure recency, 1.0 = pure relevance.
    Default 0.3 means 70% recency + 30% relevance.
    """
    boost_factor = max(0.0, min(1.0, boost_factor))
    return (1.0 - boost_factor) * recency_score + boost_factor * relevance_score


def rerank_by_relevance(
    items: list[dict],
    query: str,
    content_key: str = "content",
    score_key: str = "relevance",
    top_k: int = 5,
    boost_factor: float = 0.3,
) -> list[dict]:
    """
    Compute relevance for each item, blend with recency (position-based),
    sort by blended score, return top_k.

    Each item gets:
      - item[score_key] = raw TF-IDF relevance
      - item["_blended"] = blended recency+relevance score (used for sorting)

    Items are assumed to be in recency order (index 0 = most recent).
    """
    if not items or not query:
        return items[:top_k]

    n = len(items)
    for i, item in enumerate(items):
        text = item.get(content_key, "")
        relevance = compute_text_relevance(query, str(text))
        recency = 1.0 - (i / max(n, 1))
        item[score_key] = relevance
        item["_blended"] = blend_scores(recency, relevance, boost_factor)

    items.sort(key=lambda x: x.get("_blended", 0), reverse=True)
    return items[:top_k]
