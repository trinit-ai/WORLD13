"""
TMOS13 Knowledge Bridge — Fibonacci Plume Node 7

Pack-aware proactive knowledge base. Mid-session, the system consults its own
history, surfaces relevant prior work without prompting, and adapts behavior
based on accumulated organizational memory.

Key distinction from Vault RAG (Node 3):
  - [VAULT CONTEXT] (Node 3) = explicit prior deliverable lookup (passive)
  - [VAULT KNOWLEDGE] (Node 7) = proactive organizational memory (active)

Parents: RAG Layer (Node 3) + Session (base primitive).

Design principle (from ontology): use structured dimensional queries first,
text search as fallback. No vector embeddings — Postgres B-tree + TF-IDF.

Follows delivery_service.py / pipeline_service.py singleton pattern.
"""
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("tmos13.knowledge_bridge")

# ─── Configuration ─────────────────────────────────────────

KNOWLEDGE_BRIDGE_ENABLED = os.environ.get(
    "KNOWLEDGE_BRIDGE_ENABLED", "true"
).lower() in ("true", "1", "yes")

KNOWLEDGE_BRIDGE_MAX_TOKENS = int(
    os.environ.get("KNOWLEDGE_BRIDGE_MAX_TOKENS", "1200")
)

KNOWLEDGE_BRIDGE_CONFIDENCE_THRESHOLD = float(
    os.environ.get("KNOWLEDGE_BRIDGE_CONFIDENCE_THRESHOLD", "0.4")
)

KNOWLEDGE_BRIDGE_MAX_INJECTIONS = int(
    os.environ.get("KNOWLEDGE_BRIDGE_MAX_INJECTIONS", "3")
)

_LOOKBACK_DAYS = 90


# ─── Data Structures ──────────────────────────────────────

@dataclass
class RetrievalSignal:
    """A signal indicating potentially relevant organizational memory."""
    signal_type: str       # "prior_deliverable" | "similar_session" | "known_pattern" | "relevant_note" | "vault_item" | "inbox_conversation"
    confidence: float      # 0.0–1.0
    query_params: dict = field(default_factory=dict)
    reason: str = ""


# ─── Service ──────────────────────────────────────────────

class KnowledgeBridge:
    """
    Proactive organizational memory bridge.

    Evaluates each turn for relevant prior work, retrieves context chunks,
    and formats them for assembler injection as [VAULT KNOWLEDGE].
    """

    def __init__(self, db=None, notes_store=None):
        self._db = db
        self._notes = notes_store
        logger.info("Knowledge bridge initialized")

    # ─── Core API ─────────────────────────────────────────

    async def evaluate_turn(
        self,
        state,
        user_message: str,
        owner_id: str,
        pack_config: dict,
    ) -> list[RetrievalSignal]:
        """
        Evaluate the current turn for proactive knowledge retrieval signals.

        Runs signal generators in sequence, filters by confidence threshold,
        caps at max_injections, returns sorted (highest confidence first).
        """
        if not KNOWLEDGE_BRIDGE_ENABLED:
            return []
        if not owner_id or owner_id == "anonymous":
            return []
        if not pack_config or not pack_config.get("enabled"):
            return []

        sources = set(pack_config.get("sources", []))
        threshold = pack_config.get(
            "confidence_threshold", KNOWLEDGE_BRIDGE_CONFIDENCE_THRESHOLD
        )
        max_inj = pack_config.get(
            "max_injections", KNOWLEDGE_BRIDGE_MAX_INJECTIONS
        )
        departments = pack_config.get("departments_scope", [])

        signals: list[RetrievalSignal] = []

        # Dimensional query priority: exact → partial → tag → text
        if "prior_deliverables" in sources:
            signals.extend(await self._check_prior_deliverables(state, owner_id))

        if "similar_sessions" in sources:
            signals.extend(await self._check_similar_sessions(state, owner_id))

        if "patterns" in sources:
            signals.extend(await self._check_patterns(state, owner_id))

        if "notes" in sources:
            signals.extend(
                await self._check_notes(state, user_message, owner_id)
            )

        if "vault_items" in sources:
            signals.extend(
                await self._check_vault_relevance(
                    state, user_message, owner_id, departments
                )
            )

        if "inbox" in sources:
            signals.extend(
                await self._check_inbox(state, user_message, owner_id)
            )

        if "manifest" in sources:
            signals.extend(
                await self._check_manifest(state, user_message, owner_id)
            )

        if "contacts" in sources:
            signals.extend(
                await self._check_contacts(state, owner_id)
            )

        if "entity_trace" in sources:
            signals.extend(
                await self._check_entity_trace(state, owner_id)
            )

        if "semantic" in sources:
            signals.extend(
                await self._check_semantic_similarity(
                    state, user_message, owner_id
                )
            )

        # Apply feedback-based confidence adjustment
        pack_id = getattr(state, "pack_id", None)
        if pack_id:
            for sig in signals:
                adj = self.get_confidence_adjustment(pack_id, sig.signal_type)
                sig.confidence = min(sig.confidence * adj, 1.0)

        # Filter by threshold, sort by confidence desc, cap
        signals = [s for s in signals if s.confidence >= threshold]
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals[:max_inj]

    async def retrieve_context(
        self, signals: list[RetrievalSignal], owner_id: str
    ) -> list[dict]:
        """
        Execute retrieval for each signal.

        Each chunk: {source, content, relevance_score, metadata}
        Content is summary/excerpt, never full documents.
        """
        chunks = []
        retrievers = {
            "prior_deliverable": self._retrieve_deliverable_context,
            "similar_session": self._retrieve_session_context,
            "known_pattern": self._retrieve_pattern_context,
            "relevant_note": self._retrieve_note_context,
            "vault_item": self._retrieve_vault_context,
            "inbox_conversation": self._retrieve_inbox_context,
            "semantic_match": self._retrieve_semantic_context,
            "manifest_entry": self._retrieve_manifest_context,
            "contact": self._retrieve_contact_context,
            "entity_trace": self._retrieve_entity_trace_context,
        }
        for sig in signals:
            retriever = retrievers.get(sig.signal_type)
            if not retriever:
                continue
            try:
                chunk = await retriever(sig, owner_id)
                if chunk:
                    chunks.append(chunk)
            except Exception as e:
                logger.warning(
                    "Knowledge retrieval failed for %s: %s",
                    sig.signal_type, e,
                )
        return chunks

    def format_knowledge_context(
        self, chunks: list[dict], max_tokens: int = KNOWLEDGE_BRIDGE_MAX_TOKENS
    ) -> str:
        """
        Build [VAULT KNOWLEDGE] block from retrieved chunks.

        Token budget enforced by char counting (4 chars ~ 1 token).
        """
        if not chunks:
            return ""

        char_budget = max_tokens * 4

        # Detect what sources are present to frame the header accurately
        sources_present = set(c.get("source", "") for c in chunks)
        has_notes = any(s in sources_present for s in ("notes", "relevant_note", "note"))
        has_inbox = "inbox_conversation" in sources_present
        has_vault = "vault_item" in sources_present
        has_manifest = "manifest_entry" in sources_present
        has_contacts = "contact" in sources_present

        source_labels = []
        if has_notes:
            source_labels.append("saved notes")
        if has_inbox:
            source_labels.append("inbox conversations")
        if has_vault:
            source_labels.append("vault documents")
        if has_manifest:
            source_labels.append("manifest events")
        if has_contacts:
            source_labels.append("contacts")
        if not source_labels:
            source_labels.append("organizational memory")

        source_desc = ", ".join(source_labels)
        lines = [
            f"[VAULT KNOWLEDGE — {source_desc}]",
            f"The following contains your {source_desc}.",
            "Notes are tagged with [Saved Note] or [Note:]. Inbox entries are tagged with [Inbox]. Manifest entries are tagged with [Manifest].",
            "These are DISTINCT from session memories.",
            "",
        ]
        header_len = sum(len(l) + 1 for l in lines)
        used = header_len
        footer = "\n[/VAULT KNOWLEDGE]"
        footer_len = len(footer)

        added = 0
        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue
            entry_len = len(content) + 1  # +1 for newline
            if used + entry_len + footer_len > char_budget:
                break
            lines.append(content)
            used += entry_len
            added += 1

        if added == 0:
            return ""

        return "\n".join(lines) + footer

    async def record_feedback(
        self, session_id: str, signal_type: str, was_useful: bool,
        owner_id: str = "", pack_id: str = "",
    ):
        """Persist feedback for confidence tuning."""
        logger.info(
            "Knowledge feedback: session=%s type=%s useful=%s",
            session_id, signal_type, was_useful,
        )
        if self._db and owner_id:
            try:
                self._db.table("knowledge_feedback").insert({
                    "session_id": session_id,
                    "owner_id": owner_id,
                    "pack_id": pack_id or None,
                    "signal_type": signal_type,
                    "was_useful": was_useful,
                }).execute()
            except Exception as e:
                logger.debug("Knowledge feedback persist failed: %s", e)

    def get_confidence_adjustment(self, pack_id: str, signal_type: str) -> float:
        """
        Compute confidence adjustment from historical feedback.

        Returns a multiplier (0.5–1.5) based on hit rate for this
        signal type in this pack. Defaults to 1.0 if no data.
        """
        if not self._db or not pack_id:
            return 1.0
        try:
            result = (
                self._db.table("knowledge_feedback")
                .select("was_useful")
                .eq("pack_id", pack_id)
                .eq("signal_type", signal_type)
                .limit(50)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception:
            return 1.0

        if len(rows) < 5:
            return 1.0  # Not enough data

        useful = sum(1 for r in rows if r.get("was_useful"))
        hit_rate = useful / len(rows)
        # Map 0.0–1.0 hit rate to 0.5–1.5 multiplier
        return 0.5 + hit_rate

    # ─── Signal Generators ────────────────────────────────

    async def _check_prior_deliverables(
        self, state, owner_id: str
    ) -> list[RetrievalSignal]:
        """Check for prior deliverables in this pack for this owner."""
        if not self._db:
            return []
        pack_id = getattr(state, "pack_id", None)
        if not pack_id:
            return []
        try:
            result = (
                self._db.table("deliverables")
                .select("id, spec_name, created_at")
                .eq("user_id", owner_id)
                .eq("pack_id", pack_id)
                .gte("created_at", _lookback_timestamp(_LOOKBACK_DAYS))
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: deliverable check failed: %s", e)
            return []

        if not rows:
            return []

        signals = []
        for row in rows:
            age_days = _age_in_days(row.get("created_at"))
            confidence = 0.7 if age_days <= 30 else 0.5
            signals.append(RetrievalSignal(
                signal_type="prior_deliverable",
                confidence=confidence,
                query_params={"deliverable_id": row["id"], "pack_id": pack_id},
                reason=f"Prior {row.get('spec_name', 'deliverable')} ({age_days}d ago)",
            ))
        return signals

    async def _check_similar_sessions(
        self, state, owner_id: str
    ) -> list[RetrievalSignal]:
        """Check for sessions in other packs with overlapping captured fields."""
        if not self._db:
            return []
        pack_id = getattr(state, "pack_id", None)
        if not pack_id:
            return []
        try:
            result = (
                self._db.table("persistent_sessions")
                .select("id, pack_id, captured_fields")
                .eq("owner_id", owner_id)
                .neq("pack_id", pack_id)
                .gte("updated_at", _lookback_timestamp(_LOOKBACK_DAYS))
                .order("updated_at", desc=True)
                .limit(10)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: session check failed: %s", e)
            return []

        if not rows:
            return []

        # Current session field keys
        current_fields = set()
        forms = getattr(state, "forms", {})
        if forms:
            for form_data in forms.values():
                current_fields.update(
                    k for k, v in form_data.items()
                    if k != "submitted_at" and v is not None
                )

        signals = []
        for row in rows:
            captured = row.get("captured_fields") or {}
            if not isinstance(captured, dict):
                continue
            other_keys = set(captured.keys())
            overlap = current_fields & other_keys
            if len(overlap) >= 2:
                signals.append(RetrievalSignal(
                    signal_type="similar_session",
                    confidence=0.5,
                    query_params={
                        "session_id": row["id"],
                        "pack_id": row.get("pack_id"),
                        "overlap_fields": list(overlap),
                    },
                    reason=f"Session in {row.get('pack_id')} shares {len(overlap)} fields",
                ))
        return signals[:3]  # cap at 3

    async def _check_patterns(
        self, state, owner_id: str
    ) -> list[RetrievalSignal]:
        """Find common field values across this owner's deliverables (>60% occurrence)."""
        if not self._db:
            return []
        pack_id = getattr(state, "pack_id", None)
        if not pack_id:
            return []
        try:
            result = (
                self._db.table("deliverables")
                .select("extracted_data")
                .eq("user_id", owner_id)
                .eq("pack_id", pack_id)
                .gte("created_at", _lookback_timestamp(_LOOKBACK_DAYS))
                .limit(20)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: pattern check failed: %s", e)
            return []

        if len(rows) < 3:
            return []

        # Aggregate field values
        field_values: dict[str, Counter] = {}
        for row in rows:
            extracted = row.get("extracted_data") or {}
            if not isinstance(extracted, dict):
                continue
            for k, v in extracted.items():
                if v is not None:
                    field_values.setdefault(k, Counter())[str(v)] += 1

        # Find patterns (>60% occurrence)
        total = len(rows)
        patterns = {}
        for field_name, counter in field_values.items():
            most_common_val, count = counter.most_common(1)[0]
            if count / total >= 0.6:
                patterns[field_name] = {
                    "value": most_common_val,
                    "pct": round(count / total * 100),
                }

        if not patterns:
            return []

        return [RetrievalSignal(
            signal_type="known_pattern",
            confidence=0.4,
            query_params={"pack_id": pack_id, "patterns": patterns},
            reason=f"{len(patterns)} recurring pattern(s) across {total} deliverables",
        )]

    async def _check_notes(
        self, state, user_message: str, owner_id: str
    ) -> list[RetrievalSignal]:
        """Keyword search on user's notes via NoteStore.search()."""
        if not self._notes:
            return []
        if not user_message or len(user_message) < 3:
            return []

        # Ensure this user's notes are loaded from Supabase
        # (load_user_notes is a no-op if already loaded for this user)
        try:
            await self._notes.load_user_notes(owner_id)
        except Exception as e:
            logger.debug("Knowledge: notes lazy-load failed: %s", e)

        try:
            results = self._notes.search(
                query=user_message, user_id=owner_id, max_results=3
            )
        except Exception as e:
            logger.warning("Knowledge: notes search failed: %s", e)
            return []

        signals = []
        for res in results:
            score = getattr(res, "score", 0.0)
            if score > 0.3:
                note = getattr(res, "note", None)
                note_id = getattr(note, "note_id", None) if note else None
                title = getattr(note, "title", "") if note else ""
                signals.append(RetrievalSignal(
                    signal_type="relevant_note",
                    confidence=0.6,
                    query_params={"note_id": note_id, "title": title},
                    reason=f"Note '{title}' matches (score={score:.2f})",
                ))

        # Fallback: if TF-IDF found nothing but user has notes, surface all of them.
        # This handles generic queries like "check my notes" where terms don't overlap
        # with note content.
        if not signals:
            try:
                all_notes = await self._notes.list_notes(user_id=owner_id, limit=5)
                for note in all_notes:
                    signals.append(RetrievalSignal(
                        signal_type="relevant_note",
                        confidence=0.5,
                        query_params={"note_id": note.note_id, "title": note.title},
                        reason=f"User note '{note.title}' (fallback)",
                    ))
            except Exception as e:
                logger.debug("Knowledge: notes fallback listing failed: %s", e)

        return signals

    async def _check_vault_relevance(
        self, state, user_message: str, owner_id: str,
        departments: list[str] | None = None,
    ) -> list[RetrievalSignal]:
        """Check vault items by owner + department + tags matching pack context."""
        if not self._db:
            return []
        try:
            query = (
                self._db.table("vault_items")
                .select("id, filename, department, tags")
                .eq("owner_id", owner_id)
                .limit(10)
            )
            if departments:
                query = query.in_("department", departments)
            result = query.execute()
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: vault check failed: %s", e)
            return []

        if not rows:
            return []

        signals = []
        for row in rows:
            signals.append(RetrievalSignal(
                signal_type="vault_item",
                confidence=0.45,
                query_params={
                    "vault_id": row["id"],
                    "filename": row.get("filename"),
                    "department": row.get("department"),
                },
                reason=f"Vault item '{row.get('filename', 'unknown')}' in {row.get('department', 'unknown')}",
            ))
        return signals[:3]

    async def _check_semantic_similarity(
        self, state, user_message: str, owner_id: str
    ) -> list[RetrievalSignal]:
        """Semantic search across all indexed content for this user."""
        try:
            from embedding_pipeline import get_embedding_pipeline
            ep = get_embedding_pipeline()
            if not ep or not ep.enabled:
                return []
        except ImportError:
            return []

        if not user_message or len(user_message) < 5:
            return []

        try:
            results = ep.search_user_memories(
                user_id=owner_id, query=user_message, top_k=3
            )
        except Exception as e:
            logger.warning("Knowledge: semantic search failed: %s", e)
            return []

        signals = []
        for r in results:
            score = r.get("score", 0.5)
            signals.append(RetrievalSignal(
                signal_type="semantic_match",
                confidence=min(score, 0.95),  # dynamic from vector similarity
                query_params={
                    "content": r.get("content", ""),
                    "metadata": r.get("metadata", {}),
                },
                reason=f"Semantic match (score={score:.2f})",
            ))
        return signals

    # ─── Context Retrievers ───────────────────────────────

    async def _retrieve_deliverable_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Load deliverable, extract spec_name + field summary."""
        if not self._db:
            return None
        del_id = signal.query_params.get("deliverable_id")
        if not del_id:
            return None
        try:
            result = (
                self._db.table("deliverables")
                .select("spec_name, extracted_data, created_at")
                .eq("id", del_id)
                .eq("user_id", owner_id)
                .single()
                .execute()
            )
            row = result.data if result else None
        except Exception as e:
            logger.warning("Knowledge: deliverable retrieval failed: %s", e)
            return None
        if not row:
            return None

        spec = row.get("spec_name", "Deliverable")
        created = row.get("created_at", "")
        date_str = _format_date(created)
        extracted = row.get("extracted_data") or {}
        field_summary = _summarize_fields(extracted, max_fields=8, max_chars=200)

        content = f"Prior {spec} ({date_str}):"
        if field_summary:
            content += f"\n  Fields: {field_summary}"

        return {
            "source": "prior_deliverable",
            "content": content[:250],
            "relevance_score": signal.confidence,
            "metadata": {"deliverable_id": del_id},
        }

    async def _retrieve_session_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Load persistent session, extract overlapping field values."""
        if not self._db:
            return None
        sess_id = signal.query_params.get("session_id")
        if not sess_id:
            return None
        try:
            result = (
                self._db.table("persistent_sessions")
                .select("pack_id, captured_fields")
                .eq("id", sess_id)
                .eq("owner_id", owner_id)
                .single()
                .execute()
            )
            row = result.data if result else None
        except Exception as e:
            logger.warning("Knowledge: session retrieval failed: %s", e)
            return None
        if not row:
            return None

        pack_id = row.get("pack_id", "unknown")
        captured = row.get("captured_fields") or {}
        overlap = signal.query_params.get("overlap_fields", [])
        field_parts = []
        for k in overlap[:6]:
            v = captured.get(k)
            if v is not None:
                field_parts.append(f"{k}={_truncate(str(v), 30)}")

        content = f"Session in {pack_id} captured: {', '.join(field_parts)}" if field_parts else ""
        if not content:
            return None

        return {
            "source": "similar_session",
            "content": content[:250],
            "relevance_score": signal.confidence,
            "metadata": {"session_id": sess_id, "pack_id": pack_id},
        }

    async def _retrieve_pattern_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Format aggregated patterns as prose."""
        patterns = signal.query_params.get("patterns", {})
        if not patterns:
            return None

        parts = []
        for field_name, info in list(patterns.items())[:4]:
            pct = info.get("pct", 0)
            val = _truncate(str(info.get("value", "")), 30)
            parts.append(f"{pct}% of intakes have {field_name}={val}")

        content = "Owner patterns: " + "; ".join(parts)

        return {
            "source": "known_pattern",
            "content": content[:200],
            "relevance_score": signal.confidence,
            "metadata": {"pattern_count": len(patterns)},
        }

    async def _retrieve_note_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Load note, return title + first 200 chars of content."""
        if not self._notes:
            return None
        note_id = signal.query_params.get("note_id")
        if not note_id:
            return None
        try:
            note = await self._notes.get(note_id)
        except Exception as e:
            logger.warning("Knowledge: note retrieval failed: %s", e)
            return None
        if not note:
            return None

        title = getattr(note, "title", "Untitled")
        body = getattr(note, "content", "") or ""
        content = f"[Saved Note] {title}"
        if body:
            content += f"\nContent: {_truncate(body, 200)}"

        return {
            "source": "relevant_note",
            "content": content[:300],
            "relevance_score": signal.confidence,
            "metadata": {"note_id": note_id},
        }

    async def _check_inbox(
        self, state, user_message: str, owner_id: str
    ) -> list[RetrievalSignal]:
        """Surface recent inbox conversations for the deployer."""
        if not self._db:
            return []

        try:
            result = (
                self._db.table("inbox_conversations")
                .select("id, visitor_name, visitor_email, classification, summary, status, created_at")
                .eq("owner_id", owner_id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: inbox check failed: %s", e)
            return []

        if not rows:
            return []

        signals = []
        for row in rows:
            signals.append(RetrievalSignal(
                signal_type="inbox_conversation",
                confidence=0.6,
                query_params={
                    "inbox_id": row["id"],
                    "visitor_name": row.get("visitor_name"),
                    "visitor_email": row.get("visitor_email"),
                    "classification": row.get("classification"),
                    "summary": row.get("summary"),
                    "status": row.get("status"),
                    "created_at": row.get("created_at"),
                },
                reason=f"Inbox: {row.get('summary', 'conversation')[:60]}",
            ))
        return signals

    async def _check_contacts(
        self, state, owner_id: str
    ) -> list[RetrievalSignal]:
        """Surface contacts for the deployer."""
        if not self._db:
            return []

        try:
            result = (
                self._db.table("contacts")
                .select("id, name, email, phone, organization, entity_type, status, department, source, last_touch_at")
                .eq("owner_id", owner_id)
                .order("last_touch_at", desc=True)
                .limit(15)
                .execute()
            )
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: contacts check failed: %s", e)
            return []

        if not rows:
            return []

        signals = []
        for row in rows:
            signals.append(RetrievalSignal(
                signal_type="contact",
                confidence=0.65,
                query_params={
                    "contact_id": row["id"],
                    "name": row.get("name"),
                    "email": row.get("email"),
                    "phone": row.get("phone"),
                    "organization": row.get("organization"),
                    "entity_type": row.get("entity_type"),
                    "status": row.get("status"),
                    "department": row.get("department"),
                    "source": row.get("source"),
                    "last_touch_at": row.get("last_touch_at"),
                },
                reason=f"Contact: {row.get('name', 'unknown')}",
            ))
        return signals

    async def _check_manifest(
        self, state, user_message: str, owner_id: str
    ) -> list[RetrievalSignal]:
        """Surface recent manifest entries for the deployer."""
        if not self._db:
            return []
        pack_id = getattr(state, "pack_id", None)

        try:
            query = (
                self._db.table("manifest_entries")
                .select("id, event_type, category, summary, department, created_at")
                .eq("owner_id", owner_id)
                .gte("created_at", _lookback_timestamp(_LOOKBACK_DAYS))
                .order("created_at", desc=True)
                .limit(10)
            )
            # Desk pack sees all manifest entries (deployer workspace).
            # Other packs see only their own entries.
            if pack_id and pack_id != "desk":
                query = query.eq("pack_id", pack_id)
            result = query.execute()
            rows = result.data if result and result.data else []
        except Exception as e:
            logger.warning("Knowledge: manifest check failed: %s", e)
            return []

        if not rows:
            return []

        signals = []
        for row in rows:
            age_days = _age_in_days(row.get("created_at"))
            confidence = 0.55 if age_days <= 14 else 0.4
            signals.append(RetrievalSignal(
                signal_type="manifest_entry",
                confidence=confidence,
                query_params={
                    "manifest_id": row["id"],
                    "event_type": row.get("event_type"),
                    "category": row.get("category"),
                    "summary": row.get("summary"),
                    "department": row.get("department"),
                    "created_at": row.get("created_at"),
                },
                reason=f"Manifest: {row.get('summary', 'event')[:60]}",
            ))
        return signals

    async def _retrieve_manifest_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Format manifest entry for knowledge injection."""
        event_type = signal.query_params.get("event_type") or ""
        category = signal.query_params.get("category") or ""
        summary = signal.query_params.get("summary") or ""
        department = signal.query_params.get("department") or ""
        created = signal.query_params.get("created_at") or ""

        parts = [f"[Manifest] {event_type}"]
        if category:
            parts.append(f"Category: {category}")
        if department:
            parts.append(f"Dept: {department}")
        if summary:
            parts.append(f"Summary: {_truncate(summary, 150)}")
        if created:
            parts.append(f"Date: {created[:10]}")

        return {
            "source": "manifest_entry",
            "content": " | ".join(parts),
            "relevance_score": signal.confidence,
            "metadata": {"manifest_id": signal.query_params.get("manifest_id")},
        }

    async def _check_entity_trace(
        self, state, owner_id: str
    ) -> list[RetrievalSignal]:
        """Trace entity references across manifest and journals for causal chains."""
        if not self._db:
            return []
        pack_id = getattr(state, "pack_id", None)
        if not pack_id:
            return []

        # Build current entity set from pack_id + cartridges visited
        current_entities = {pack_id}
        cartridges = getattr(state, "games_played", [])
        for c in cartridges:
            current_entities.add(c)

        if not current_entities:
            return []

        # Query manifest entries that share entity refs with current session
        signals = []
        try:
            for entity_name in list(current_entities)[:3]:
                # JSONB containment query: entity_refs @> '[{"name": "..."}]'
                result = (
                    self._db.table("manifest_entries")
                    .select("id, event_type, summary, created_at")
                    .eq("owner_id", owner_id)
                    .contains("entity_refs", [{"name": entity_name}])
                    .gte("created_at", _lookback_timestamp(_LOOKBACK_DAYS))
                    .order("created_at", desc=True)
                    .limit(3)
                    .execute()
                )
                rows = result.data if result and result.data else []
                for row in rows:
                    signals.append(RetrievalSignal(
                        signal_type="entity_trace",
                        confidence=0.5,
                        query_params={
                            "source_table": "manifest",
                            "entry_id": row["id"],
                            "event_type": row.get("event_type"),
                            "summary": row.get("summary"),
                            "created_at": row.get("created_at"),
                            "traced_entity": entity_name,
                        },
                        reason=f"Entity trace '{entity_name}': {row.get('summary', '')[:50]}",
                    ))
        except Exception as e:
            logger.warning("Knowledge: entity trace check failed: %s", e)

        # Deduplicate by entry_id
        seen_ids = set()
        unique = []
        for sig in signals:
            eid = sig.query_params.get("entry_id")
            if eid not in seen_ids:
                seen_ids.add(eid)
                unique.append(sig)
        return unique[:5]

    async def _retrieve_entity_trace_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Format entity trace result for knowledge injection."""
        entity = signal.query_params.get("traced_entity", "")
        event_type = signal.query_params.get("event_type", "")
        summary = signal.query_params.get("summary", "")
        created = signal.query_params.get("created_at", "")
        source = signal.query_params.get("source_table", "")

        parts = [f"[Trace:{entity}] {event_type}"]
        if summary:
            parts.append(_truncate(summary, 120))
        if created:
            parts.append(f"({created[:10]})")

        return {
            "source": "entity_trace",
            "content": " — ".join(parts),
            "relevance_score": signal.confidence,
            "metadata": {
                "entry_id": signal.query_params.get("entry_id"),
                "source_table": source,
                "traced_entity": entity,
            },
        }

    async def _retrieve_inbox_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Format inbox conversation for knowledge injection."""
        name = signal.query_params.get("visitor_name") or "Unknown"
        email = signal.query_params.get("visitor_email") or ""
        classification = signal.query_params.get("classification") or ""
        summary = signal.query_params.get("summary") or ""
        status = signal.query_params.get("status") or ""
        created = signal.query_params.get("created_at") or ""

        parts = [f"[Inbox] {name}"]
        if email:
            parts[0] += f" ({email})"
        if classification:
            parts.append(f"Type: {classification}")
        if status:
            parts.append(f"Status: {status}")
        if summary:
            parts.append(f"Summary: {_truncate(summary, 150)}")
        if created:
            parts.append(f"Date: {created[:10]}")

        return {
            "source": "inbox_conversation",
            "content": " | ".join(parts),
            "relevance_score": signal.confidence,
            "metadata": {"inbox_id": signal.query_params.get("inbox_id")},
        }

    async def _retrieve_contact_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Format contact for knowledge injection."""
        name = signal.query_params.get("name") or "Unknown"
        email = signal.query_params.get("email") or ""
        org = signal.query_params.get("organization") or ""
        entity_type = signal.query_params.get("entity_type") or ""
        status = signal.query_params.get("status") or ""
        dept = signal.query_params.get("department") or ""
        source = signal.query_params.get("source") or ""
        last_touch = signal.query_params.get("last_touch_at") or ""

        parts = [f"[Contact] {name}"]
        if email:
            parts[0] += f" ({email})"
        if org:
            parts.append(f"Org: {org}")
        if entity_type:
            parts.append(f"Type: {entity_type}")
        if status:
            parts.append(f"Status: {status}")
        if dept:
            parts.append(f"Dept: {dept}")
        if source:
            parts.append(f"Source: {source}")
        if last_touch:
            parts.append(f"Last touch: {last_touch[:10]}")

        return {
            "source": "contact",
            "content": " | ".join(parts),
            "relevance_score": signal.confidence,
            "metadata": {"contact_id": signal.query_params.get("contact_id")},
        }

    async def _retrieve_vault_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Load vault item metadata (filename, department, tags)."""
        filename = signal.query_params.get("filename", "unknown")
        department = signal.query_params.get("department", "")
        content = f"Vault item: {filename}"
        if department:
            content += f" (dept: {department})"

        return {
            "source": "vault_item",
            "content": content[:200],
            "relevance_score": signal.confidence,
            "metadata": {"vault_id": signal.query_params.get("vault_id")},
        }

    async def _retrieve_semantic_context(
        self, signal: RetrievalSignal, owner_id: str
    ) -> Optional[dict]:
        """Return the content from a semantic search result directly."""
        content = signal.query_params.get("content", "")
        if not content:
            return None
        metadata = signal.query_params.get("metadata", {})
        source_type = metadata.get("source_type", "semantic")
        return {
            "source": f"semantic:{source_type}",
            "content": content[:300],
            "relevance_score": signal.confidence,
            "metadata": metadata,
        }


# ─── Helpers ──────────────────────────────────────────────

def _lookback_timestamp(days: int) -> str:
    """Return ISO timestamp for N days ago."""
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat()


def _age_in_days(created_at) -> int:
    """Compute age in days from a created_at value."""
    if not created_at:
        return 999
    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            dt = created_at
        delta = datetime.now(timezone.utc) - dt
        return max(0, delta.days)
    except (ValueError, AttributeError, TypeError):
        return 999


def _format_date(created_at) -> str:
    """Format a created_at value to YYYY-MM-DD."""
    if not created_at:
        return "unknown"
    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            dt = created_at
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError, TypeError):
        return str(created_at)[:10]


def _summarize_fields(extracted: dict, max_fields: int = 8, max_chars: int = 200) -> str:
    """Summarize extracted_data fields into a compact string."""
    if not extracted or not isinstance(extracted, dict):
        return ""
    parts = []
    for k, v in list(extracted.items())[:max_fields]:
        if v is not None:
            parts.append(f"{k} ({_truncate(str(v), 25)})")
    summary = ", ".join(parts)
    return summary[:max_chars]


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ─── Singleton ────────────────────────────────────────────

_knowledge_bridge: Optional[KnowledgeBridge] = None


def init_knowledge_bridge(
    db=None, notes_store=None
) -> KnowledgeBridge:
    """Initialize the global KnowledgeBridge singleton."""
    global _knowledge_bridge
    _knowledge_bridge = KnowledgeBridge(db=db, notes_store=notes_store)
    return _knowledge_bridge


def get_knowledge_bridge() -> Optional[KnowledgeBridge]:
    """Return the global KnowledgeBridge or None."""
    return _knowledge_bridge
