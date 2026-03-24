"""
TMOS13 Transcript Recorder

Records structured conversation transcripts for every session. Each message
exchange is logged with timestamp, role, content, and routing metadata.

On session close, an auto-summary is generated and the transcript is finalized
for downstream processing (alert classification, email notification, persistence).

Usage:
    store = TranscriptStore()
    store.record(session_id, "user", "I need a lawyer", {"route": "passthrough"})
    store.record(session_id, "assistant", "I can help with that.", {"cartridge": "intake"})
    transcript = store.get(session_id)
    store.close_session(session_id, pack_id="legal-intake")
"""
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("tmos13.transcripts")


# ─── Data Models ─────────────────────────────────────────

@dataclass
class TranscriptEntry:
    """A single message in a conversation transcript."""
    timestamp: float = field(default_factory=time.time)
    role: str = "user"              # "user" | "assistant" | "system"
    content: str = ""
    metadata: dict = field(default_factory=dict)
    # metadata may include: route_action, route_target, cartridge, mood, depth

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def timestamp_display(self) -> str:
        """Human-readable timestamp."""
        dt = datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
        return dt.strftime("%I:%M %p")


@dataclass
class SessionTranscript:
    """Complete structured transcript for a session."""
    transcript_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""
    pack_id: str = ""
    user_id: str = "anonymous"

    # Timing
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None

    # Content
    entries: list[TranscriptEntry] = field(default_factory=list)
    cartridge_history: list[str] = field(default_factory=list)
    turn_count: int = 0

    # Extracted data
    contact_info: Optional[dict] = None     # {name, email, phone}
    classification: Optional[dict] = None   # alert classifier output
    summary: Optional[str] = None           # auto-generated summary

    # Status
    is_closed: bool = False

    # Vault dimensional addressing
    manifest_signature: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "transcript_id": self.transcript_id,
            "session_id": self.session_id,
            "pack_id": self.pack_id,
            "user_id": self.user_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "turn_count": self.turn_count,
            "cartridge_history": self.cartridge_history,
            "contact_info": self.contact_info,
            "classification": self.classification,
            "summary": self.summary,
            "is_closed": self.is_closed,
            "entries": [e.to_dict() for e in self.entries],
        }
        return d

    @property
    def duration_seconds(self) -> float:
        end = self.ended_at or time.time()
        return max(0, end - self.started_at)

    @property
    def duration_display(self) -> str:
        secs = self.duration_seconds
        mins = int(secs // 60)
        if mins < 1:
            return "< 1 minute"
        return f"{mins} minute{'s' if mins != 1 else ''}"

    @property
    def user_messages(self) -> list[TranscriptEntry]:
        return [e for e in self.entries if e.role == "user"]

    @property
    def assistant_messages(self) -> list[TranscriptEntry]:
        return [e for e in self.entries if e.role == "assistant"]

    def to_markdown(self) -> str:
        """Render transcript as readable markdown."""
        lines = []
        lines.append(f"# Session Transcript: {self.session_id}")
        lines.append(f"Pack: {self.pack_id} | Duration: {self.duration_display} | "
                      f"Turns: {self.turn_count}")
        if self.cartridge_history:
            lines.append(f"Cartridges: {' → '.join(self.cartridge_history)}")
        if self.contact_info:
            ci = self.contact_info
            lines.append(f"\nContact: {ci.get('name', 'N/A')} | "
                          f"{ci.get('email', '')} | {ci.get('phone', '')}")
        if self.summary:
            lines.append(f"\nSummary: {self.summary}")
        lines.append("\n---\n")

        for entry in self.entries:
            ts = entry.timestamp_display
            role = entry.role.upper()
            cartridge = entry.metadata.get("cartridge", "")
            cart_tag = f"  (cartridge: {cartridge})" if cartridge else ""
            lines.append(f"[{ts}] {role}{cart_tag}")
            lines.append(entry.content)
            lines.append("")

        return "\n".join(lines)


# ─── Contact Info Extraction ─────────────────────────────

# Common patterns for PII detection in conversation text
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?"                     # optional country code
    r"(?:\(?\d{3}\)?[-.\s]?)"               # area code
    r"\d{3}[-.\s]?\d{4}"                    # number
)
_NAME_PATTERNS = [
    r"(?:my name is|i'm|i am|this is|name:?)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
    r"(?:call me|name's)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
]
_NAME_RES = [re.compile(p, re.IGNORECASE) for p in _NAME_PATTERNS]


def extract_contact_info(text: str) -> dict:
    """
    Extract contact information from conversation text.

    Returns dict with optional keys: name, email, phone.
    Empty dict if nothing found.
    """
    info = {}

    emails = _EMAIL_RE.findall(text)
    if emails:
        info["email"] = emails[0]

    phones = _PHONE_RE.findall(text)
    if phones:
        # Clean up phone formatting
        phone = phones[0].strip()
        info["phone"] = phone

    for pattern in _NAME_RES:
        match = pattern.search(text)
        if match:
            info["name"] = match.group(1).strip()
            break

    return info


# ─── Heuristic Summary Generator ─────────────────────────

def generate_transcript_summary(transcript: SessionTranscript) -> str:
    """
    Generate a concise summary of a transcript using heuristics.

    Extracts: first user message intent, key topics mentioned,
    contact info status, and session path.
    """
    if not transcript.entries:
        return "Empty session — no messages exchanged."

    parts = []

    # Intent from first user message
    user_msgs = transcript.user_messages
    if user_msgs:
        first = user_msgs[0].content[:150].strip()
        if len(user_msgs[0].content) > 150:
            first += "..."
        parts.append(first)

    # Session path
    if transcript.cartridge_history:
        path = " → ".join(transcript.cartridge_history)
        parts.append(f"Path: {path}.")

    # Contact status
    if transcript.contact_info:
        ci = transcript.contact_info
        collected = []
        if ci.get("name"):
            collected.append(f"name ({ci['name']})")
        if ci.get("email"):
            collected.append("email")
        if ci.get("phone"):
            collected.append("phone")
        if collected:
            parts.append(f"Contact collected: {', '.join(collected)}.")
    else:
        parts.append("No contact info collected.")

    # Session stats
    parts.append(f"{transcript.turn_count} turns over {transcript.duration_display}.")

    return " ".join(parts)


# ─── AI-Generated Transcript Summary ─────────────────────

_TRANSCRIPT_SUMMARY_SYSTEM = (
    "Summarize this conversation in 2-3 sentences. Capture: what the user wanted, "
    "what was accomplished, and any important decisions or data collected. "
    "Write from a neutral third-person perspective. Be specific and factual. "
    "Max 200 characters. No filler."
)


async def generate_llm_transcript_summary(
    llm_provider,
    transcript: SessionTranscript,
) -> str:
    """
    Generate an LLM-written transcript summary.

    Falls back to heuristic on failure or for short sessions (< 3 turns).
    """
    heuristic = generate_transcript_summary(transcript)

    if transcript.turn_count < 3:
        return heuristic

    if not llm_provider:
        return heuristic

    try:
        recent = transcript.entries[-20:] if len(transcript.entries) > 20 else transcript.entries
        lines = []
        for e in recent:
            lines.append(f"{e.role}: {e.content}")
        transcript_text = "\n".join(lines)[:3000]

        if not transcript_text or len(transcript_text.strip()) < 20:
            return heuristic

        meta = (
            f"Pack: {transcript.pack_id or 'unknown'} | "
            f"Turns: {transcript.turn_count} | "
            f"Duration: {transcript.duration_display}"
        )
        user_msg = f"{meta}\n\nTranscript:\n{transcript_text}"

        response = await llm_provider.generate(
            system=_TRANSCRIPT_SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=120,
        )
        summary = response.text.strip() if response and response.text else ""
        if summary:
            logger.debug("Generated LLM transcript summary (%d chars)", len(summary))
            return summary
        return heuristic
    except Exception as e:
        logger.warning("LLM transcript summary failed, using heuristic: %s", e)
        return heuristic


# ─── AI-Generated Inbox Summary ──────────────────────────

_INBOX_SUMMARY_SYSTEM = (
    "Write a single concise sentence summarizing who the visitor is, "
    "what they wanted, and the outcome. Write from the deployer's perspective. "
    "Max 120 characters. Pure substance, no filler."
)


async def generate_inbox_summary(
    llm_provider,
    transcript: SessionTranscript,
) -> str:
    """
    Generate an AI-written inbox summary for a finalized session.

    Returns heuristic fallback on failure or for short sessions (< 2 turns).
    """
    heuristic = generate_transcript_summary(transcript)

    # Short sessions — skip LLM, use heuristic directly
    if transcript.turn_count < 2:
        return heuristic

    if not llm_provider:
        return heuristic

    try:
        # Build compact transcript (last 20 exchanges, ≤3000 chars)
        recent = transcript.entries[-20:] if len(transcript.entries) > 20 else transcript.entries
        lines = []
        for e in recent:
            lines.append(f"{e.role}: {e.content}")
        transcript_text = "\n".join(lines)[:3000]

        if not transcript_text or len(transcript_text.strip()) < 20:
            return heuristic

        # Metadata context
        visitor_name = (transcript.contact_info or {}).get("name", "anonymous")
        meta = (
            f"Pack: {transcript.pack_id or 'guest'} | "
            f"Turns: {transcript.turn_count} | "
            f"Visitor: {visitor_name}"
        )

        user_msg = f"{meta}\n\nTranscript:\n{transcript_text}"

        response = await llm_provider.generate(
            system=_INBOX_SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=80,
        )
        summary = response.text.strip() if response and response.text else ""
        if summary:
            logger.debug("Generated inbox summary (%d chars)", len(summary))
            return summary
        return heuristic
    except Exception as e:
        logger.warning("Inbox summary generation failed, using heuristic: %s", e)
        return heuristic


# ─── AI-Generated Inbox Summary — Detailed Tier ─────────

_INBOX_SUMMARY_DETAILED_SYSTEM = (
    "Write a 2-3 sentence summary covering who the visitor is, what they wanted, "
    "key discussion points, and outcome. Write from the deployer's perspective. "
    "Max 500 characters. Pure substance, no filler."
)


async def generate_inbox_summary_detailed(
    llm_provider,
    transcript: SessionTranscript,
) -> str:
    """
    Generate an AI-written detailed inbox summary (~500 chars).

    Returns heuristic fallback on failure or for short sessions (< 2 turns).
    """
    heuristic = generate_transcript_summary(transcript)

    if transcript.turn_count < 2:
        return heuristic

    if not llm_provider:
        return heuristic

    try:
        recent = transcript.entries[-20:] if len(transcript.entries) > 20 else transcript.entries
        lines = []
        for e in recent:
            lines.append(f"{e.role}: {e.content}")
        transcript_text = "\n".join(lines)[:3000]

        if not transcript_text or len(transcript_text.strip()) < 20:
            return heuristic

        visitor_name = (transcript.contact_info or {}).get("name", "anonymous")
        meta = (
            f"Pack: {transcript.pack_id or 'guest'} | "
            f"Turns: {transcript.turn_count} | "
            f"Duration: {transcript.duration_display} | "
            f"Visitor: {visitor_name}"
        )

        user_msg = f"{meta}\n\nTranscript:\n{transcript_text}"

        response = await llm_provider.generate(
            system=_INBOX_SUMMARY_DETAILED_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=200,
        )
        summary = response.text.strip() if response and response.text else ""
        if summary:
            logger.debug("Generated detailed inbox summary (%d chars)", len(summary))
            return summary
        return heuristic
    except Exception as e:
        logger.warning("Detailed inbox summary generation failed, using heuristic: %s", e)
        return heuristic


# ─── AI-Generated Inbox Summary — Full Tier ─────────────

_INBOX_SUMMARY_FULL_SYSTEM = (
    "Write a thorough summary paragraph covering visitor identity, their needs, "
    "all key topics discussed, any data collected (contact info, requirements, "
    "preferences), outcome, and recommended next steps. Write from the deployer's "
    "perspective. Max 1500 characters. Pure substance, no filler."
)


async def generate_inbox_summary_full(
    llm_provider,
    transcript: SessionTranscript,
) -> str:
    """
    Generate an AI-written full inbox summary (~1500 chars).

    Returns heuristic fallback on failure or for short sessions (< 2 turns).
    """
    heuristic = generate_transcript_summary(transcript)

    if transcript.turn_count < 2:
        return heuristic

    if not llm_provider:
        return heuristic

    try:
        recent = transcript.entries[-30:] if len(transcript.entries) > 30 else transcript.entries
        lines = []
        for e in recent:
            lines.append(f"{e.role}: {e.content}")
        transcript_text = "\n".join(lines)[:5000]

        if not transcript_text or len(transcript_text.strip()) < 20:
            return heuristic

        visitor_name = (transcript.contact_info or {}).get("name", "anonymous")
        meta = (
            f"Pack: {transcript.pack_id or 'guest'} | "
            f"Turns: {transcript.turn_count} | "
            f"Duration: {transcript.duration_display} | "
            f"Visitor: {visitor_name}"
        )

        user_msg = f"{meta}\n\nTranscript:\n{transcript_text}"

        response = await llm_provider.generate(
            system=_INBOX_SUMMARY_FULL_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=600,
        )
        summary = response.text.strip() if response and response.text else ""
        if summary:
            logger.debug("Generated full inbox summary (%d chars)", len(summary))
            return summary
        return heuristic
    except Exception as e:
        logger.warning("Full inbox summary generation failed, using heuristic: %s", e)
        return heuristic


# ─── Transcript Store ────────────────────────────────────

class TranscriptStore:
    """
    Two-tier transcript store: fast in-memory dict + optional Supabase persistence.

    - record() writes to memory and upserts to Supabase (best-effort).
    - close_session() sets status to 'closed' in both tiers.
    - get() checks memory first, then falls back to Supabase.
    - If no supabase_client is provided, behaves as in-memory only.
    """

    def __init__(self, supabase_client=None):
        self._transcripts: dict[str, SessionTranscript] = {}
        self._db = supabase_client
        mode = "supabase+memory" if self._db else "memory-only"
        logger.info(f"TranscriptStore initialized ({mode})")

    def _ensure_transcript(
        self,
        session_id: str,
        pack_id: str = "",
        user_id: str = "anonymous",
        manifest_signature: Optional[dict] = None,
    ) -> SessionTranscript:
        """Get or create a transcript for a session."""
        if session_id not in self._transcripts:
            self._transcripts[session_id] = SessionTranscript(
                session_id=session_id,
                pack_id=pack_id,
                user_id=user_id,
                manifest_signature=manifest_signature or {},
            )
        elif manifest_signature and not self._transcripts[session_id].manifest_signature:
            # Backfill if transcript exists but signature was missing
            self._transcripts[session_id].manifest_signature = manifest_signature
        return self._transcripts[session_id]

    def record(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
        pack_id: str = "",
        user_id: str = "anonymous",
        manifest_signature: Optional[dict] = None,
    ) -> TranscriptEntry:
        """Record a single message to a session's transcript."""
        transcript = self._ensure_transcript(session_id, pack_id, user_id, manifest_signature)

        if transcript.is_closed:
            logger.warning(f"Attempted to record to closed transcript: {session_id}")
            return TranscriptEntry()

        entry = TranscriptEntry(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        transcript.entries.append(entry)

        # Track cartridge transitions
        cartridge = (metadata or {}).get("cartridge")
        if cartridge and (
            not transcript.cartridge_history
            or transcript.cartridge_history[-1] != cartridge
        ):
            transcript.cartridge_history.append(cartridge)

        # Update turn count (count user messages as turns)
        if role == "user":
            transcript.turn_count += 1

        # Scan user messages for contact info
        if role == "user":
            new_info = extract_contact_info(content)
            if new_info:
                had_contact = bool(transcript.contact_info)
                if transcript.contact_info:
                    transcript.contact_info.update(new_info)
                else:
                    transcript.contact_info = new_info

                # Snapshot transcript on first PII detection (dedup via session attr)
                if not had_contact and not getattr(self, f"_pii_logged_{session_id}", False):
                    setattr(self, f"_pii_logged_{session_id}", True)
                    try:
                        import asyncio
                        asyncio.get_event_loop().create_task(
                            asyncio.to_thread(log_transcript_for_contact, session_id, "pii_extraction")
                        )
                    except Exception:
                        pass

        # Persist to Supabase (best-effort, non-blocking on hot path)
        self._persist_transcript(transcript)

        return entry

    def close_session(self, session_id: str) -> Optional[SessionTranscript]:
        """
        Finalize a transcript: set end time, generate summary,
        extract any remaining contact info.

        Returns the finalized transcript, or None if not found.
        """
        transcript = self._transcripts.get(session_id)
        if not transcript:
            return None

        if transcript.is_closed:
            return transcript

        transcript.ended_at = time.time()
        transcript.is_closed = True

        # Generate summary
        transcript.summary = generate_transcript_summary(transcript)

        # Final pass: scan all user messages for contact info
        if not transcript.contact_info:
            all_user_text = " ".join(e.content for e in transcript.user_messages)
            contact = extract_contact_info(all_user_text)
            if contact:
                transcript.contact_info = contact

        logger.info(
            f"Transcript closed: session={session_id} "
            f"turns={transcript.turn_count} "
            f"duration={transcript.duration_display} "
            f"contact={'yes' if transcript.contact_info else 'no'}"
        )

        # Persist final state to Supabase
        self._persist_transcript(transcript)

        return transcript

    def get(self, session_id: str) -> Optional[SessionTranscript]:
        """Get a transcript by session ID. Checks memory, then Supabase."""
        transcript = self._transcripts.get(session_id)
        if transcript is not None:
            return transcript

        # Fall back to Supabase
        if self._db:
            try:
                result = (
                    self._db.table("transcripts")
                    .select("*")
                    .eq("session_id", session_id)
                    .execute()
                )
                if result.data:
                    transcript = self._row_to_transcript(result.data[0])
                    self._transcripts[session_id] = transcript
                    logger.debug(f"Transcript {session_id} restored from Supabase")
                    return transcript
            except Exception as e:
                logger.warning(f"Supabase transcript fetch failed for {session_id}: {e}")

        return None

    def list_transcripts(
        self,
        pack_id: Optional[str] = None,
        user_id: Optional[str] = None,
        closed_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SessionTranscript]:
        """List transcripts with optional filters."""
        results = list(self._transcripts.values())
        if pack_id:
            results = [t for t in results if t.pack_id == pack_id]
        if user_id:
            results = [t for t in results if t.user_id == user_id]
        if closed_only:
            results = [t for t in results if t.is_closed]
        results.sort(key=lambda t: t.started_at, reverse=True)
        return results[offset:offset + limit]

    def delete(self, session_id: str) -> bool:
        """Remove a transcript."""
        if session_id in self._transcripts:
            del self._transcripts[session_id]
            return True
        return False

    # ─── Supabase Persistence ─────────────────────────────

    def _persist_transcript(self, transcript: SessionTranscript) -> None:
        """Upsert transcript to Supabase (best-effort)."""
        if not self._db:
            return
        try:
            from datetime import datetime, timezone as tz
            from vault_gate import build_transcript_dimensions, gate_and_log
            started_dt = datetime.fromtimestamp(transcript.started_at, tz=tz.utc).isoformat()
            closed_dt = (
                datetime.fromtimestamp(transcript.ended_at, tz=tz.utc).isoformat()
                if transcript.ended_at else None
            )
            now = datetime.now(tz.utc).isoformat()

            # Build messages JSONB from entries
            messages = [
                {"role": e.role, "content": e.content, "timestamp": e.timestamp}
                for e in transcript.entries
            ]

            # Determine last cartridge
            cartridge = transcript.cartridge_history[-1] if transcript.cartridge_history else None

            # Assemble Vault dimensional address
            dimensions = build_transcript_dimensions(
                pack_id=transcript.pack_id,
                user_id=transcript.user_id,
                session_id=transcript.session_id,
                manifest_signature=transcript.manifest_signature,
                cartridge=cartridge,
                created_at=transcript.started_at,
            )
            gate_and_log(dimensions, transcript.session_id, "transcript")

            row = {
                "session_id": transcript.session_id,
                "pack_id": transcript.pack_id,
                "cartridge": cartridge,
                "messages": messages,
                "classification": transcript.classification or {},
                "contact_info": transcript.contact_info or {},
                "summary": transcript.summary,
                "turn_count": transcript.turn_count,
                "status": "closed" if transcript.is_closed else "active",
                "started_at": started_dt,
                "closed_at": closed_dt,
                "updated_at": now,
                "dimensions": dimensions,
            }

            # Only set user_id if it's a valid UUID (not "anonymous")
            uid = self._parse_user_id(transcript.user_id)
            if uid:
                row["user_id"] = uid

            self._db.table("transcripts").upsert(
                row, on_conflict="session_id"
            ).execute()

            # ── Vault output registration (fire-and-forget, closed only) ──
            if transcript.is_closed:
                try:
                    from vault import get_vault_service
                    vault_svc = get_vault_service()
                    md_export = transcript.to_markdown()
                    content_bytes = md_export.encode("utf-8")
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(vault_svc.register_output(
                            owner_id=transcript.user_id,
                            filename=f"transcript_{transcript.session_id[:8]}.md",
                            storage_path="",  # vault service handles upload
                            file_data=content_bytes,
                            source="transcript_export",
                            source_id=transcript.session_id,
                            size_bytes=len(content_bytes),
                            mime_type="text/markdown",
                            pack_id=transcript.pack_id,
                            session_id=transcript.session_id,
                            dimensions=dimensions,
                        ))
                except Exception as ve:
                    logger.debug("Vault output registration skipped: %s", ve)

        except Exception as e:
            logger.warning(f"Supabase transcript persist failed for {transcript.session_id}: {e}")

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

    @staticmethod
    def _row_to_transcript(row: dict) -> SessionTranscript:
        """Reconstruct a SessionTranscript from a Supabase row."""
        messages = row.get("messages", [])
        entries = [
            TranscriptEntry(
                timestamp=m.get("timestamp", 0),
                role=m.get("role", "user"),
                content=m.get("content", ""),
                metadata={},
            )
            for m in messages
        ]

        # Rebuild cartridge_history from entries (metadata not stored in messages JSONB)
        # Use the cartridge column as hint for last cartridge
        cartridge_history = []
        if row.get("cartridge"):
            cartridge_history = [row["cartridge"]]

        # Parse started_at
        started_at = time.time()
        if row.get("started_at"):
            try:
                from datetime import datetime as dt_cls
                parsed = dt_cls.fromisoformat(str(row["started_at"]).replace("Z", "+00:00"))
                started_at = parsed.timestamp()
            except (ValueError, AttributeError):
                pass

        ended_at = None
        if row.get("closed_at"):
            try:
                from datetime import datetime as dt_cls
                parsed = dt_cls.fromisoformat(str(row["closed_at"]).replace("Z", "+00:00"))
                ended_at = parsed.timestamp()
            except (ValueError, AttributeError):
                pass

        status = row.get("status", "active")

        return SessionTranscript(
            transcript_id=str(row.get("id", ""))[:12],
            session_id=row.get("session_id", ""),
            pack_id=row.get("pack_id", ""),
            user_id=str(row.get("user_id", "anonymous")),
            started_at=started_at,
            ended_at=ended_at,
            entries=entries,
            cartridge_history=cartridge_history,
            turn_count=row.get("turn_count", 0),
            contact_info=row.get("contact_info") or None,
            classification=row.get("classification") or None,
            summary=row.get("summary"),
            is_closed=status == "closed",
        )

    @property
    def count(self) -> int:
        return len(self._transcripts)

    def get_stats(self) -> dict:
        """Return transcript store statistics."""
        total = len(self._transcripts)
        closed = sum(1 for t in self._transcripts.values() if t.is_closed)
        active = total - closed
        with_contact = sum(1 for t in self._transcripts.values() if t.contact_info)
        total_turns = sum(t.turn_count for t in self._transcripts.values())

        return {
            "total_transcripts": total,
            "active": active,
            "closed": closed,
            "with_contact_info": with_contact,
            "total_turns": total_turns,
        }


# ─── Contact-Triggered Transcript Snapshots ──────────────


_snapshot_db = None


def init_snapshot_db(supabase_client):
    """Initialize the DB client for transcript snapshots."""
    global _snapshot_db
    _snapshot_db = supabase_client


def _get_snapshot_db():
    global _snapshot_db
    if _snapshot_db:
        return _snapshot_db
    try:
        from app import db
        _snapshot_db = db
        return _snapshot_db
    except Exception:
        return None


def log_transcript_for_contact(
    session_id: str,
    trigger_reason: str,
    transcript_store=None,
) -> Optional[str]:
    """
    Snapshot and persist full transcript at the moment contact is provided.
    Writes to transcript_snapshots table (allows multiple per session).
    Returns snapshot record ID, or None on failure.

    trigger_reason: "rail" | "state_signal" | "pii_extraction" | "session_close"
    """
    db = _get_snapshot_db()
    if not db:
        logger.debug("Transcript snapshot skipped: no DB")
        return None

    # Get transcript from store
    if not transcript_store:
        try:
            from app import transcript_store as _ts
            transcript_store = _ts
        except Exception:
            logger.debug("Transcript snapshot skipped: no transcript store")
            return None

    transcript = transcript_store.get(session_id) if transcript_store else None
    if not transcript or not transcript.entries:
        logger.debug("Transcript snapshot skipped: no entries for %s", session_id)
        return None

    # Serialize full turn history
    full_transcript = [
        {
            "turn_index": i,
            "role": entry.role,
            "content": entry.content,
            "timestamp": entry.timestamp,
        }
        for i, entry in enumerate(transcript.entries)
    ]

    now = datetime.now(timezone.utc).isoformat()
    is_snapshot = trigger_reason != "session_close"

    row = {
        "session_id": session_id,
        "contact_trigger": trigger_reason,
        "snapshot": is_snapshot,
        "turn_count": len(transcript.entries),
        "full_transcript": full_transcript,
        "logged_at": now,
        "created_at": now,
    }

    try:
        result = db.table("transcript_snapshots").insert(row).execute()
        record_id = result.data[0]["id"] if result.data else None
        logger.info(
            "Transcript snapshot: session=%s trigger=%s turns=%d id=%s",
            session_id, trigger_reason, len(full_transcript), record_id,
        )
        return record_id
    except Exception as e:
        logger.warning("Transcript snapshot failed for %s: %s", session_id, e)
        return None


def get_latest_snapshot(session_id: str) -> Optional[dict]:
    """Get the most recent snapshot for a session. Returns raw row or None."""
    db = _get_snapshot_db()
    if not db:
        return None
    try:
        result = (
            db.table("transcript_snapshots")
            .select("id, session_id, contact_trigger, logged_at, turn_count, snapshot")
            .eq("session_id", session_id)
            .eq("snapshot", True)
            .order("logged_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None
