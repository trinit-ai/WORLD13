"""
TMOS13 Autonomous Deliverable Pipeline

Transforms conversation transcripts into structured deliverables — proposals,
case briefs, investment analyses, project plans. The conversation IS the intake;
the transcript data seeds autonomous document generation.

Pipeline flow:
    Session Close → Extract structured data → Check eligibility → Generate deliverable

Each pack defines its deliverable types in the manifest under "deliverables":
    - What fields to extract from conversation (patterns + categories)
    - What data is required before generation can begin
    - Template sections for the output document
    - Output format and delivery channels

Phase 1: Heuristic extraction (regex patterns, no LLM). Matches the existing
approach in transcripts.py (contact extraction) and notes.py (summarization).

Usage:
    pipeline = DeliverablePipeline()
    results = pipeline.evaluate(transcript, pack_manifest)
    for deliverable in results:
        send_to_channel(deliverable)
"""
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from transcripts import SessionTranscript

logger = logging.getLogger("tmos13.deliverables")


# ─── Tool Schema for Structured Outputs ─────────────────

def deliverable_to_tool_schema(spec_or_manifest: dict) -> dict:
    """
    Convert a pack's deliverable config to an Anthropic tool definition.

    Accepts either:
      - A deliverable spec dict (from pack manifest "deliverables.types[]")
      - A pack manifest dict with a top-level "deliverable_schema"

    If the manifest provides an explicit "deliverable_schema", that JSON Schema
    is used directly as the tool's input_schema. Otherwise, the schema is
    auto-generated from the spec's fields list.

    Returns:
        A tool definition dict with name, description, and input_schema.
    """
    # Check for explicit schema first (pack manifest level)
    explicit_schema = spec_or_manifest.get("deliverable_schema")
    if explicit_schema:
        return {
            "name": "produce_deliverable",
            "description": "Produce the structured deliverable for this session.",
            "input_schema": explicit_schema,
        }

    # Auto-generate from fields list
    fields = spec_or_manifest.get("fields", [])
    spec_id = spec_or_manifest.get("id", "deliverable")
    spec_name = spec_or_manifest.get("name", "Deliverable")

    properties: dict = {}
    required: list[str] = []

    for f in fields:
        if isinstance(f, str):
            # Simple string field ID — default to string type
            properties[f] = {"type": "string"}
            continue

        field_id = f.get("id", "")
        if not field_id:
            continue

        field_type = f.get("type", "string")
        is_required = f.get("required", False)

        if field_type == "array":
            properties[field_id] = {
                "type": "array",
                "items": {"type": "string"},
            }
        elif field_type == "number":
            properties[field_id] = {"type": "number"}
        elif field_type == "boolean":
            properties[field_id] = {"type": "boolean"}
        else:
            properties[field_id] = {"type": "string"}

        # Add name as description if available
        if f.get("name"):
            properties[field_id]["description"] = f["name"]

        if is_required:
            required.append(field_id)

    schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return {
        "name": "produce_deliverable",
        "description": f"Produce the structured {spec_name} deliverable for this session.",
        "input_schema": schema,
    }


# ─── Data Models ─────────────────────────────────────────

@dataclass
class ExtractionPattern:
    """A single pattern for extracting a field value from conversation text."""
    pattern: str            # regex pattern with a capture group
    flags: int = re.IGNORECASE
    transform: str = ""     # "lower", "upper", "title", "number", "currency"

    @staticmethod
    def from_dict(d: dict) -> "ExtractionPattern":
        flags = re.IGNORECASE if d.get("case_insensitive", True) else 0
        return ExtractionPattern(
            pattern=d.get("pattern", ""),
            flags=flags,
            transform=d.get("transform", ""),
        )


@dataclass
class FieldSpec:
    """Specification for a single extractable field."""
    id: str = ""
    name: str = ""
    category: str = ""         # groups fields: "project", "budget", "timeline", etc.
    required: bool = False     # must be present for deliverable eligibility
    patterns: list[ExtractionPattern] = field(default_factory=list)
    default: str = ""          # fallback if not extracted

    @staticmethod
    def from_dict(d: dict) -> "FieldSpec":
        return FieldSpec(
            id=d.get("id", ""),
            name=d.get("name", ""),
            category=d.get("category", ""),
            required=d.get("required", False),
            patterns=[ExtractionPattern.from_dict(p) for p in d.get("patterns", [])],
            default=d.get("default", ""),
        )


@dataclass
class TemplateSection:
    """A section of the deliverable output template."""
    id: str = ""
    heading: str = ""
    body: str = ""             # markdown with {{field_id}} placeholders
    condition: str = ""        # field_id that must be present for section to render
    order: int = 0
    llm_enrich: bool = False   # if True and LLM available, generate content via LLM
    prompt: str = ""           # LLM prompt template (uses {{field_id}} placeholders)

    @staticmethod
    def from_dict(d: dict) -> "TemplateSection":
        return TemplateSection(
            id=d.get("id", ""),
            heading=d.get("heading", ""),
            body=d.get("body", ""),
            condition=d.get("condition", ""),
            order=d.get("order", 0),
            llm_enrich=d.get("llm_enrich", False),
            prompt=d.get("prompt", ""),
        )


@dataclass
class DeliverableSpec:
    """
    Full specification for a deliverable type, loaded from pack manifest.

    Example manifest entry:
        {
            "id": "case_brief",
            "name": "Case Brief",
            "description": "Preliminary case assessment document",
            "fields": [...],
            "template": { "title": "...", "sections": [...] },
            "trigger": { "cartridges_required": [...], "min_turns": 5 },
            "channels": ["email", "download"]
        }
    """
    id: str = ""
    name: str = ""
    description: str = ""
    fields: list[FieldSpec] = field(default_factory=list)
    template_title: str = ""
    template_sections: list[TemplateSection] = field(default_factory=list)
    trigger_cartridges: list[str] = field(default_factory=list)
    trigger_min_turns: int = 3
    trigger_contact_required: bool = True
    channels: list[str] = field(default_factory=lambda: ["download"])
    include_transcript: bool = False
    include_state_snapshot: bool = False

    @staticmethod
    def from_dict(d: dict) -> "DeliverableSpec":
        template = d.get("template", {})
        trigger = d.get("trigger", {})
        return DeliverableSpec(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            fields=[FieldSpec.from_dict(f) for f in d.get("fields", [])],
            template_title=template.get("title", "{{name}} — {{date}}"),
            template_sections=[
                TemplateSection.from_dict(s)
                for s in template.get("sections", [])
            ],
            trigger_cartridges=trigger.get("cartridges_required", []),
            trigger_min_turns=trigger.get("min_turns", 3),
            trigger_contact_required=trigger.get("contact_required", True),
            channels=d.get("channels", ["download"]),
            include_transcript=d.get("include_transcript", False),
            include_state_snapshot=d.get("include_state_snapshot", False),
        )

    @property
    def required_fields(self) -> list[FieldSpec]:
        return [f for f in self.fields if f.required]


@dataclass
class ExtractedData:
    """Structured data extracted from a conversation transcript."""
    deliverable_id: str = ""
    session_id: str = ""
    fields: dict[str, str] = field(default_factory=dict)        # field_id → value
    field_sources: dict[str, str] = field(default_factory=dict)  # field_id → source message excerpt
    categories: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    extraction_count: int = 0
    missing_required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "deliverable_id": self.deliverable_id,
            "session_id": self.session_id,
            "fields": self.fields,
            "field_sources": self.field_sources,
            "categories": dict(self.categories),
            "extraction_count": self.extraction_count,
            "missing_required": self.missing_required,
        }

    @property
    def completeness(self) -> float:
        """Fraction of required fields that have been extracted (0.0 – 1.0)."""
        if not self.missing_required and self.extraction_count == 0:
            return 0.0
        total_required = self.extraction_count + len(self.missing_required)
        if total_required == 0:
            return 1.0
        filled = self.extraction_count
        return min(1.0, filled / total_required)

    @property
    def is_eligible(self) -> bool:
        """True when all required fields are present."""
        return len(self.missing_required) == 0 and self.extraction_count > 0


@dataclass
class Deliverable:
    """A generated deliverable document."""
    deliverable_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    spec_id: str = ""
    spec_name: str = ""
    session_id: str = ""
    transcript_id: str = ""
    pack_id: str = ""
    user_id: str = "anonymous"

    # Content
    title: str = ""
    body: str = ""             # rendered markdown
    sections: list[dict] = field(default_factory=list)  # [{heading, content}]
    extracted_data: dict = field(default_factory=dict)

    # Context from transcript
    contact_info: Optional[dict] = None
    transcript_summary: str = ""
    cartridge_path: list[str] = field(default_factory=list)
    turn_count: int = 0

    # Metadata
    completeness: float = 0.0
    channels: list[str] = field(default_factory=list)
    status: str = "generated"  # generated | sent | viewed | archived
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Vault dimensional addressing
    artifact_type: str = ""
    dimensions: dict = field(default_factory=dict)
    manifest_signature: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def created_at_display(self) -> str:
        dt = datetime.fromtimestamp(self.created_at, tz=timezone.utc)
        return dt.strftime("%b %d, %Y at %I:%M %p %Z")


# ─── Delivery Intent (Fibonacci Plume Node 4) ─────────────

@dataclass
class DeliveryIntent:
    """
    A delivery intent — a deliverable scheduled for transmission.

    Created by the delivery pipeline when a deliverable is generated.
    AI sessions force staged mode (human approval required).
    """
    delivery_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deliverable_id: str = ""
    user_id: str = ""
    pack_id: str = ""
    session_id: str = ""

    # Recipient
    recipient_type: str = "email"          # email | ambassador | webhook | internal
    recipient_address: str = ""
    recipient_name: str = ""

    # Delivery control
    mode: str = "staged"                   # auto | staged | manual
    status: str = "pending"                # pending | approved | sent | delivered | failed | cancelled
    channel: str = "email"                 # email | ambassador | webhook | internal
    is_ai_session: bool = False

    # Ambassador linkage
    exchange_id: Optional[str] = None

    # Approval
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    sent_at: Optional[float] = None

    # Error tracking
    error_message: str = ""

    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Extractor ───────────────────────────────────────────

# Built-in extraction patterns for common field types.
# Packs can override these or define their own in the manifest.

_BUILTIN_PATTERNS: dict[str, list[ExtractionPattern]] = {
    "budget": [
        ExtractionPattern(r"\$\s*([\d,]+(?:\.\d{2})?)\s*(?:k|K|thousand)?", transform="currency"),
        ExtractionPattern(r"budget\s+(?:is|of|around|about|roughly)?\s*\$?([\d,]+(?:\.\d{2})?)", transform="currency"),
        ExtractionPattern(r"([\d,]+(?:\.\d{2})?)\s*(?:dollars|usd)", transform="currency"),
        ExtractionPattern(r"budget\s+(?:range|between)\s*\$?([\d,]+)\s*(?:to|and|-)\s*\$?([\d,]+)", transform="currency"),
    ],
    "timeline": [
        ExtractionPattern(r"(?:timeline|timeframe|deadline|due|by|within|need it)\s+(?:is|of)?\s*(.+?)(?:\.|$)"),
        ExtractionPattern(r"(\d+)\s*(week|month|year|day)s?(?:\s+(?:from now|out))?"),
        ExtractionPattern(r"(?:by|before|no later than)\s+((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,?\s*\d{4})?)", re.IGNORECASE),
    ],
    "location": [
        ExtractionPattern(r"(?:location|located|address|site|property at|in)\s+(?:is|at)?\s*(.+?)(?:\.|,|$)"),
        ExtractionPattern(r"(\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:St|Ave|Blvd|Dr|Rd|Ln|Ct|Way|Pl|Cir)\.?)"),
    ],
    "square_footage": [
        ExtractionPattern(r"([\d,]+)\s*(?:sq\.?\s*(?:ft|feet)|square\s*(?:feet|foot))", transform="number"),
        ExtractionPattern(r"([\d,]+)\s*(?:sf|sqft)", transform="number"),
    ],
    "project_type": [
        ExtractionPattern(r"(?:looking for|want|need|interested in|planning)\s+(?:a|an)?\s*((?:new|custom|residential|commercial|renovation|remodel|addition|restoration|mixed.use|retail|office|warehouse|industrial|multi.family|single.family|condo|townhouse|duplex)[\w\s]*?)(?:\.|,|$)"),
    ],
    "style": [
        ExtractionPattern(r"(?:style|aesthetic|look|design)\s+(?:is|should be|we want|preference\s+is)?\s*((?:modern|contemporary|traditional|craftsman|colonial|farmhouse|mid.century|minimalist|industrial|rustic|mediterranean|victorian|art deco|tudor)[\w\s]*?)(?:\.|,|$)"),
    ],
    "incident_date": [
        ExtractionPattern(r"(?:happened|occurred|on|date|incident)\s+(?:on|was)?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"),
        ExtractionPattern(r"(?:happened|occurred)\s+(?:on)?\s*((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,?\s*\d{4})?)", re.IGNORECASE),
        ExtractionPattern(r"(\d+)\s*(?:days?|weeks?|months?)\s*ago"),
    ],
    "damages": [
        ExtractionPattern(r"(?:damages?|losses?|cost|harm|injury)\s+(?:of|totaling|around|about)?\s*\$?([\d,]+(?:\.\d{2})?)", transform="currency"),
    ],
    "property_value": [
        ExtractionPattern(r"(?:property|home|house|unit)\s+(?:is worth|is valued at|valued at|asking|listed at|price)\s*\$?([\d,]+(?:\.\d{2})?)", transform="currency"),
        ExtractionPattern(r"(?:purchase|asking)\s*price\s*(?:is|of|was)?\s*\$?([\d,]+(?:\.\d{2})?)", transform="currency"),
    ],
    "num_units": [
        ExtractionPattern(r"(\d+)\s*(?:unit|apartment|bedroom|bed|bath|br|ba|room)s?", transform="number"),
    ],
}


def _apply_transform(value: str, transform: str) -> str:
    """Apply a transform to an extracted value."""
    if not transform or not value:
        return value.strip()
    if transform == "lower":
        return value.strip().lower()
    if transform == "upper":
        return value.strip().upper()
    if transform == "title":
        return value.strip().title()
    if transform == "number":
        return value.replace(",", "").strip()
    if transform == "currency":
        cleaned = value.replace(",", "").strip()
        try:
            num = float(cleaned)
            if num >= 1000:
                return f"${num:,.0f}"
            return f"${num:,.2f}"
        except ValueError:
            return f"${cleaned}"
    return value.strip()


class DeliverableExtractor:
    """
    Extracts structured data from a conversation transcript using
    regex patterns defined in the deliverable spec.

    Falls back to built-in patterns for common field types (budget,
    timeline, location, etc.) when no pack-specific patterns are defined.
    """

    def extract(
        self,
        transcript: SessionTranscript,
        spec: DeliverableSpec,
    ) -> ExtractedData:
        """
        Scan all user messages in the transcript and extract fields
        defined by the deliverable spec.
        """
        data = ExtractedData(
            deliverable_id=spec.id,
            session_id=transcript.session_id,
        )

        # Combine all user message text for scanning
        user_texts = [
            (e.content, e.content[:80])
            for e in transcript.entries
            if e.role == "user" and e.content.strip()
        ]

        if not user_texts:
            data.missing_required = [f.id for f in spec.required_fields]
            return data

        all_user_text = " ".join(text for text, _ in user_texts)

        for field_spec in spec.fields:
            value = self._extract_field(field_spec, all_user_text, user_texts)
            if value:
                data.fields[field_spec.id] = value
                data.extraction_count += 1
                if field_spec.category:
                    data.categories[field_spec.category].append(field_spec.id)
                # Find source excerpt
                for text, excerpt in user_texts:
                    if any(v.lower() in text.lower() for v in value.split()[:3] if len(v) > 2):
                        data.field_sources[field_spec.id] = excerpt
                        break
            elif field_spec.default:
                data.fields[field_spec.id] = field_spec.default
                data.extraction_count += 1
            elif field_spec.required:
                data.missing_required.append(field_spec.id)

        # Also inject contact info as fields if available
        if transcript.contact_info:
            ci = transcript.contact_info
            if ci.get("name") and "contact_name" not in data.fields:
                data.fields["contact_name"] = ci["name"]
            if ci.get("email") and "contact_email" not in data.fields:
                data.fields["contact_email"] = ci["email"]
            if ci.get("phone") and "contact_phone" not in data.fields:
                data.fields["contact_phone"] = ci["phone"]

        logger.info(
            f"Extraction complete: spec={spec.id} "
            f"extracted={data.extraction_count} "
            f"missing={len(data.missing_required)} "
            f"completeness={data.completeness:.0%}"
        )
        return data

    def _extract_field(
        self,
        field_spec: FieldSpec,
        all_text: str,
        message_pairs: list[tuple[str, str]],
    ) -> str:
        """Try to extract a single field value using spec patterns, then builtins."""
        # Try spec-defined patterns first
        for ep in field_spec.patterns:
            value = self._try_pattern(ep, all_text)
            if value:
                return value

        # Fall back to built-in patterns for known field IDs
        builtins = _BUILTIN_PATTERNS.get(field_spec.id, [])
        for ep in builtins:
            value = self._try_pattern(ep, all_text)
            if value:
                return value

        return ""

    def _try_pattern(self, ep: ExtractionPattern, text: str) -> str:
        """Apply a single extraction pattern to text."""
        try:
            match = re.search(ep.pattern, text, ep.flags)
            if match:
                # Use the first capture group, or the whole match
                value = match.group(1) if match.lastindex else match.group(0)
                return _apply_transform(value, ep.transform)
        except re.error as e:
            logger.warning(f"Invalid extraction pattern: {ep.pattern} — {e}")
        return ""


# ─── Generator ───────────────────────────────────────────

class DeliverableGenerator:
    """
    Renders a deliverable document from extracted data and a template spec.

    Templates use {{field_id}} placeholders that are replaced with extracted
    values. Sections with a `condition` field are only rendered when the
    condition field has been extracted.

    When an LLM provider is supplied and a section has `llm_enrich=True`,
    that section's content is generated via LLM instead of template fill.
    Falls back to template rendering if LLM call fails.
    """

    def __init__(self, llm_provider=None):
        self.llm = llm_provider

    def generate(
        self,
        spec: DeliverableSpec,
        data: ExtractedData,
        transcript: SessionTranscript,
        session_state: Optional[dict] = None,
    ) -> Deliverable:
        """Generate a deliverable document."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%B %d, %Y")

        # Build variable context for template rendering
        context = dict(data.fields)
        context["date"] = date_str
        context["name"] = spec.name
        context["pack_id"] = transcript.pack_id
        context["session_id"] = transcript.session_id
        context["turn_count"] = str(transcript.turn_count)
        context["duration"] = transcript.duration_display
        if transcript.contact_info:
            ci = transcript.contact_info
            context["contact_name"] = ci.get("name", "")
            context["contact_email"] = ci.get("email", "")
            context["contact_phone"] = ci.get("phone", "")
        if transcript.cartridge_history:
            context["cartridge_path"] = " → ".join(transcript.cartridge_history)

        # Render title
        title = self._render_template(spec.template_title, context)

        # Render sections
        rendered_sections = []
        body_parts = [f"# {title}\n"]
        body_parts.append(f"*Generated {date_str} from conversation data*\n")

        # Contact header if available
        if transcript.contact_info:
            ci = transcript.contact_info
            contact_parts = []
            if ci.get("name"):
                contact_parts.append(f"**Client:** {ci['name']}")
            if ci.get("email"):
                contact_parts.append(f"**Email:** {ci['email']}")
            if ci.get("phone"):
                contact_parts.append(f"**Phone:** {ci['phone']}")
            if contact_parts:
                body_parts.append(" | ".join(contact_parts))
                body_parts.append("")

        body_parts.append("---\n")

        # Template sections (sorted by order)
        sorted_sections = sorted(spec.template_sections, key=lambda s: s.order)
        for section in sorted_sections:
            # Check condition
            if section.condition and section.condition not in data.fields:
                continue

            heading = self._render_template(section.heading, context)

            # LLM enrichment for sections that request it
            if section.llm_enrich and self.llm and section.prompt:
                content = self._llm_generate_section(section, context, transcript)
            else:
                content = self._render_template(section.body, context)

            rendered_sections.append({
                "id": section.id,
                "heading": heading,
                "content": content,
            })
            body_parts.append(f"## {heading}\n")
            body_parts.append(content)
            body_parts.append("")

        # Auto-generated sections from extracted data (categories not covered by template)
        template_field_ids = set()
        for section in spec.template_sections:
            # Collect field refs from body and prompt
            template_field_ids.update(
                re.findall(r"\{\{(\w+)\}\}", section.body)
            )
            if section.prompt:
                template_field_ids.update(
                    re.findall(r"\{\{(\w+)\}\}", section.prompt)
                )

        uncovered = {
            fid: val for fid, val in data.fields.items()
            if fid not in template_field_ids
            and not fid.startswith("contact_")
        }
        if uncovered:
            body_parts.append("## Additional Details\n")
            for fid, val in uncovered.items():
                label = fid.replace("_", " ").title()
                body_parts.append(f"- **{label}:** {val}")
            body_parts.append("")

        # Transcript summary footer
        if transcript.summary:
            body_parts.append("---\n")
            body_parts.append("## Conversation Summary\n")
            body_parts.append(transcript.summary)
            body_parts.append("")

        # Transcript inclusion
        if spec.include_transcript and transcript.entries:
            body_parts.append("---\n")
            body_parts.append("## Session Transcript\n")
            body_parts.append(
                f"Session ID: {transcript.session_id} | "
                f"Duration: {transcript.turn_count} turns | "
                f"Date: {date_str}\n"
            )
            for entry in transcript.entries:
                role_label = "INTAKE" if entry.role == "assistant" else entry.role.upper()
                body_parts.append(f"**{role_label}**")
                body_parts.append(entry.content)
                body_parts.append("")

        # State snapshot inclusion
        if spec.include_state_snapshot and session_state:
            body_parts.append("---\n")
            body_parts.append("## State Snapshot (Final)\n")
            body_parts.append("Complete session state at close:\n")
            body_parts.append("```")
            for key, value in self._flatten_state(session_state).items():
                body_parts.append(f"{key} = {value}")
            body_parts.append("```")
            body_parts.append("")

        body = "\n".join(body_parts)

        # Derive artifact_type from spec id
        artifact_type = spec.id or "deliverable"

        # Extract manifest signature from session_state if available
        manifest_sig = {}
        if session_state and isinstance(session_state, dict):
            manifest_sig = session_state.get("manifest_signature", {})

        deliverable = Deliverable(
            spec_id=spec.id,
            spec_name=spec.name,
            session_id=transcript.session_id,
            transcript_id=transcript.transcript_id,
            pack_id=transcript.pack_id,
            user_id=transcript.user_id,
            title=title,
            body=body,
            sections=rendered_sections,
            extracted_data=data.to_dict(),
            contact_info=transcript.contact_info,
            transcript_summary=transcript.summary or "",
            cartridge_path=list(transcript.cartridge_history),
            turn_count=transcript.turn_count,
            completeness=data.completeness,
            channels=list(spec.channels),
            artifact_type=artifact_type,
            manifest_signature=manifest_sig,
        )

        logger.info(
            f"Deliverable generated: id={deliverable.deliverable_id} "
            f"spec={spec.id} completeness={data.completeness:.0%} "
            f"sections={len(rendered_sections)}"
        )
        return deliverable

    def _llm_generate_section(
        self,
        section: TemplateSection,
        context: dict,
        transcript: SessionTranscript,
    ) -> str:
        """Generate a section's content via LLM, falling back to template on failure."""
        try:
            # Build the prompt with field values substituted
            rendered_prompt = self._render_template(section.prompt, context)

            system = (
                "You are generating a section of a professional document. "
                "Write in clear, direct prose. No headers, no preamble. "
                "Just the content for this section."
            )
            messages = [{"role": "user", "content": rendered_prompt}]

            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.llm.generate(
                        system=system, messages=messages, max_tokens=1024,
                    ))
                    response = future.result(timeout=30)
            else:
                response = asyncio.run(self.llm.generate(
                    system=system, messages=messages, max_tokens=1024,
                ))

            if response and response.text:
                logger.info(
                    f"LLM enrichment for section '{section.id}': "
                    f"{response.output_tokens} tokens"
                )
                return response.text

        except Exception as e:
            logger.warning(
                f"LLM enrichment failed for section '{section.id}': {e}. "
                f"Falling back to template rendering."
            )

        # Fallback to template rendering
        return self._render_template(section.body, context)

    def extract_with_llm(
        self,
        transcript: SessionTranscript,
        spec: DeliverableSpec,
        tool_schema: dict,
    ) -> ExtractedData:
        """
        Extract structured deliverable data via LLM tool_use.

        Uses Anthropic's structured output (tool_use with forced tool_choice)
        to extract fields. The LLM response is guaranteed to match the schema.

        Falls back to empty ExtractedData if the LLM provider doesn't support
        tool_use or the call fails.

        Args:
            transcript: Session transcript with conversation entries.
            spec: Deliverable specification.
            tool_schema: Tool definition from deliverable_to_tool_schema().
        """
        if not self.llm or not hasattr(self.llm, "generate_with_tools"):
            logger.debug("LLM extraction unavailable — no provider or no tool support")
            return ExtractedData(
                deliverable_id=spec.id,
                session_id=transcript.session_id,
                missing_required=[f.id for f in spec.required_fields],
            )

        # Build conversation text for extraction
        conversation_lines = []
        for entry in transcript.entries:
            role = "USER" if entry.role == "user" else "ASSISTANT"
            conversation_lines.append(f"{role}: {entry.content}")
        conversation_text = "\n".join(conversation_lines)

        system = (
            "You are extracting structured data from a conversation transcript. "
            "Analyze the conversation and use the produce_deliverable tool to "
            "output all fields you can identify. For fields you cannot determine "
            "from the conversation, omit them or use empty strings."
        )
        messages = [{
            "role": "user",
            "content": (
                f"Extract the {spec.name} deliverable fields from this conversation:\n\n"
                f"{conversation_text}"
            ),
        }]

        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            call_kwargs = {
                "system": system,
                "messages": messages,
                "tools": [tool_schema],
                "tool_choice": {"type": "tool", "name": "produce_deliverable"},
                "max_tokens": 2048,
            }

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.llm.generate_with_tools(**call_kwargs),
                    )
                    response = future.result(timeout=60)
            else:
                response = asyncio.run(
                    self.llm.generate_with_tools(**call_kwargs)
                )

            # Extract structured data from tool results
            if response.tool_results:
                tool_data = response.tool_results[0].get("input", {})
                data = ExtractedData(
                    deliverable_id=spec.id,
                    session_id=transcript.session_id,
                )
                for key, value in tool_data.items():
                    if value is not None and value != "":
                        if isinstance(value, list):
                            data.fields[key] = ", ".join(str(v) for v in value)
                        else:
                            data.fields[key] = str(value)
                        data.extraction_count += 1
                        # Categorize based on spec fields
                        for fs in spec.fields:
                            if fs.id == key and fs.category:
                                data.categories[fs.category].append(key)
                                break

                # Check required fields
                for fs in spec.required_fields:
                    if fs.id not in data.fields:
                        data.missing_required.append(fs.id)

                logger.info(
                    f"LLM extraction complete: spec={spec.id} "
                    f"extracted={data.extraction_count} "
                    f"missing={len(data.missing_required)}"
                )
                return data

        except Exception as e:
            logger.warning(f"LLM extraction failed for {spec.id}: {e}")

        # Fallback: return empty extraction
        return ExtractedData(
            deliverable_id=spec.id,
            session_id=transcript.session_id,
            missing_required=[f.id for f in spec.required_fields],
        )

    def _render_template(self, template: str, context: dict) -> str:
        """Replace {{field_id}} placeholders with values from context."""
        def replacer(match):
            key = match.group(1)
            return context.get(key, f"[{key}]")
        return re.sub(r"\{\{(\w+)\}\}", replacer, template)

    @staticmethod
    def _flatten_state(state: dict, prefix: str = "") -> dict:
        """Flatten a nested state dict to dot-notation keys."""
        flat = {}
        for key, value in state.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.update(DeliverableGenerator._flatten_state(value, full_key))
            elif isinstance(value, list):
                flat[full_key] = ", ".join(str(v) for v in value) if value else "[]"
            else:
                flat[full_key] = str(value) if value is not None else "null"
        return flat


# ─── Store ───────────────────────────────────────────────

class DeliverableStore:
    """Two-tier deliverable store: in-memory dict + optional Supabase persistence."""

    def __init__(self, supabase_client=None):
        self._deliverables: dict[str, Deliverable] = {}
        self._db = supabase_client
        mode = "supabase+memory" if self._db else "memory-only"
        logger.info(f"DeliverableStore initialized ({mode})")

    def add(self, deliverable: Deliverable) -> Deliverable:
        self._deliverables[deliverable.deliverable_id] = deliverable
        self._persist_deliverable(deliverable)
        return deliverable

    def get(self, deliverable_id: str) -> Optional[Deliverable]:
        return self._deliverables.get(deliverable_id)

    def get_by_session(self, session_id: str) -> list[Deliverable]:
        return [
            d for d in self._deliverables.values()
            if d.session_id == session_id
        ]

    def update_status(
        self,
        deliverable_id: str,
        status: str,
    ) -> Optional[Deliverable]:
        d = self._deliverables.get(deliverable_id)
        if not d:
            return None
        d.status = status
        d.updated_at = time.time()
        # Persist status update to Supabase
        if self._db:
            try:
                from datetime import datetime, timezone as tz
                self._db.table("deliverables").update({
                    "status": status,
                    "updated_at": datetime.now(tz.utc).isoformat(),
                }).eq("id", deliverable_id).execute()
            except Exception as e:
                logger.warning(f"Supabase deliverable status update failed: {e}")
        return d

    def list_deliverables(
        self,
        pack_id: Optional[str] = None,
        user_id: Optional[str] = None,
        spec_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Deliverable]:
        results = list(self._deliverables.values())
        if pack_id:
            results = [d for d in results if d.pack_id == pack_id]
        if user_id:
            results = [d for d in results if d.user_id == user_id]
        if spec_id:
            results = [d for d in results if d.spec_id == spec_id]
        if status:
            results = [d for d in results if d.status == status]
        results.sort(key=lambda d: d.created_at, reverse=True)
        return results[offset:offset + limit]

    def delete(self, deliverable_id: str) -> bool:
        if deliverable_id in self._deliverables:
            del self._deliverables[deliverable_id]
            return True
        return False

    # ─── Supabase Persistence ─────────────────────────────

    def _persist_deliverable(self, d: Deliverable) -> None:
        """Insert a deliverable into Supabase (best-effort)."""
        if not self._db:
            return
        try:
            from datetime import datetime, timezone as tz
            from vault_gate import build_deliverable_dimensions, gate_and_log
            now = datetime.now(tz.utc).isoformat()

            # Assemble Vault dimensional address
            dimensions = build_deliverable_dimensions(
                pack_id=d.pack_id,
                user_id=d.user_id,
                session_id=d.session_id,
                artifact_type=d.artifact_type or d.spec_id or "deliverable",
                extracted_fields=d.extracted_data or {},
                manifest_signature=d.manifest_signature,
                content=d.body or "",
                created_at=d.created_at,
            )
            gate_and_log(dimensions, d.deliverable_id, "deliverable")

            row = {
                "id": d.deliverable_id,
                "session_id": d.session_id,
                "pack_id": d.pack_id,
                "spec_id": d.spec_id,
                "spec_name": d.spec_name,
                "extracted_data": d.extracted_data or {},
                "rendered_content": d.body,
                "status": d.status,
                "metadata": {
                    "title": d.title,
                    "completeness": d.completeness,
                    "channels": d.channels,
                    "contact_info": d.contact_info,
                    "transcript_summary": d.transcript_summary,
                    "cartridge_path": d.cartridge_path,
                    "turn_count": d.turn_count,
                    "sections": d.sections,
                },
                "dimensions": dimensions,
                "artifact_type": d.artifact_type or d.spec_id or "deliverable",
                "extracted_fields": d.extracted_data or {},
                "created_at": now,
                "updated_at": now,
            }

            # Only set user_id if it's a valid UUID
            uid = self._parse_user_id(d.user_id)
            if uid:
                row["user_id"] = uid

            self._db.table("deliverables").insert(row).execute()

            # ── Vault output registration (fire-and-forget) ──
            try:
                from vault import get_vault_service
                vault_svc = get_vault_service()
                content_bytes = (d.body or "").encode("utf-8")
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(vault_svc.register_output(
                        owner_id=d.user_id,
                        filename=f"{d.spec_name or 'deliverable'}_{d.deliverable_id[:8]}.md",
                        storage_path="",  # vault service handles upload
                        file_data=content_bytes,
                        source="deliverable",
                        source_id=d.deliverable_id,
                        size_bytes=len(content_bytes),
                        mime_type="text/markdown",
                        pack_id=d.pack_id,
                        session_id=d.session_id,
                        dimensions=dimensions,
                    ))
            except Exception as ve:
                logger.debug("Vault output registration skipped: %s", ve)

        except Exception as e:
            logger.warning(f"Supabase deliverable persist failed for {d.deliverable_id}: {e}")

    def get_deliverables_by_user(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query deliverables from Supabase for a user. Returns raw dicts."""
        if not self._db:
            # Fall back to in-memory filtering
            results = [
                d.to_dict() for d in self._deliverables.values()
                if d.user_id == user_id
                and (session_id is None or d.session_id == session_id)
                and (status is None or d.status == status)
            ]
            results.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return results[:limit]

        try:
            query = (
                self._db.table("deliverables")
                .select("*")
                .eq("user_id", user_id)
            )
            if session_id:
                query = query.eq("session_id", session_id)
            if status:
                query = query.eq("status", status)
            result = query.order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Supabase deliverable query failed: {e}")
            return []

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

    @property
    def count(self) -> int:
        return len(self._deliverables)

    def get_stats(self) -> dict:
        by_pack: dict[str, int] = defaultdict(int)
        by_spec: dict[str, int] = defaultdict(int)
        by_status: dict[str, int] = defaultdict(int)
        total_completeness = 0.0
        for d in self._deliverables.values():
            by_pack[d.pack_id] = by_pack.get(d.pack_id, 0) + 1
            by_spec[d.spec_id] = by_spec.get(d.spec_id, 0) + 1
            by_status[d.status] = by_status.get(d.status, 0) + 1
            total_completeness += d.completeness
        n = len(self._deliverables) or 1
        return {
            "total": self.count,
            "avg_completeness": round(total_completeness / n, 2),
            "by_pack": dict(by_pack),
            "by_spec": dict(by_spec),
            "by_status": dict(by_status),
        }


# ─── Pipeline ────────────────────────────────────────────

class DeliverablePipeline:
    """
    Orchestrates the full deliverable generation flow:

        transcript → extract → check eligibility → generate → store

    Called after session close, alongside alert evaluation.
    """

    def __init__(
        self,
        store: Optional[DeliverableStore] = None,
        generator: Optional[DeliverableGenerator] = None,
        supabase_client=None,
    ):
        self.extractor = DeliverableExtractor()
        self.generator = generator or DeliverableGenerator()
        self.store = store or DeliverableStore(supabase_client=supabase_client)

    def evaluate(
        self,
        transcript: SessionTranscript,
        pack_manifest: dict,
        session_state: Optional[dict] = None,
    ) -> list[Deliverable]:
        """
        Evaluate a transcript against all deliverable specs in the pack.

        Returns list of generated Deliverable objects (may be empty if
        no specs are eligible).
        """
        deliverables_config = pack_manifest.get("deliverables", {})
        if not deliverables_config or not deliverables_config.get("enabled", False):
            return []

        specs_data = deliverables_config.get("types", [])
        if not specs_data:
            return []

        # Check for explicit deliverable_schema at manifest level
        manifest_schema = pack_manifest.get("deliverable_schema")

        specs = [DeliverableSpec.from_dict(s) for s in specs_data]
        generated: list[Deliverable] = []

        for spec, spec_data in zip(specs, specs_data):
            # Step 1: Check trigger conditions
            if not self._check_triggers(transcript, spec):
                logger.debug(f"Deliverable {spec.id}: trigger conditions not met")
                continue

            # Step 2: Extract data — use LLM tool_use if schema available,
            # otherwise fall back to heuristic regex extraction.
            spec_schema = spec_data.get("deliverable_schema") or manifest_schema
            if spec_schema and self.generator.llm:
                tool_def = deliverable_to_tool_schema(
                    {**spec_data, "deliverable_schema": spec_schema}
                )
                data = self.generator.extract_with_llm(transcript, spec, tool_def)
                # If LLM extraction yielded nothing, fall back to heuristic
                if data.extraction_count == 0:
                    logger.info(
                        f"Deliverable {spec.id}: LLM extraction empty, "
                        f"falling back to heuristic"
                    )
                    data = self.extractor.extract(transcript, spec)
            else:
                data = self.extractor.extract(transcript, spec)

            # Step 3: Check eligibility
            if not data.is_eligible:
                logger.info(
                    f"Deliverable {spec.id}: not eligible — "
                    f"missing: {data.missing_required}"
                )
                continue

            # Step 4: Generate
            deliverable = self.generator.generate(
                spec, data, transcript, session_state=session_state,
            )

            # Step 5: Store
            self.store.add(deliverable)
            generated.append(deliverable)

            logger.info(
                f"Deliverable pipeline: generated {spec.id} "
                f"for session {transcript.session_id}"
            )

        return generated

    def _check_triggers(
        self,
        transcript: SessionTranscript,
        spec: DeliverableSpec,
    ) -> bool:
        """Check if transcript meets the trigger conditions for a deliverable spec."""
        # Minimum turns
        if transcript.turn_count < spec.trigger_min_turns:
            return False

        # Contact required
        if spec.trigger_contact_required:
            ci = transcript.contact_info
            if not ci or not ci.get("name"):
                return False

        # Required cartridges
        if spec.trigger_cartridges:
            for cartridge in spec.trigger_cartridges:
                if cartridge not in transcript.cartridge_history:
                    return False

        return True

    def extract_preview(
        self,
        transcript: SessionTranscript,
        pack_manifest: dict,
    ) -> list[dict]:
        """
        Preview extraction results without generating deliverables.
        Useful for showing real-time progress during a conversation.

        Returns list of dicts with spec info and extraction completeness.
        """
        deliverables_config = pack_manifest.get("deliverables", {})
        if not deliverables_config or not deliverables_config.get("enabled", False):
            return []

        specs_data = deliverables_config.get("types", [])
        previews = []

        for spec_data in specs_data:
            spec = DeliverableSpec.from_dict(spec_data)
            data = self.extractor.extract(transcript, spec)
            triggers_met = self._check_triggers(transcript, spec)

            previews.append({
                "spec_id": spec.id,
                "spec_name": spec.name,
                "completeness": round(data.completeness, 2),
                "extracted_count": data.extraction_count,
                "missing_required": data.missing_required,
                "eligible": data.is_eligible and triggers_met,
                "triggers_met": triggers_met,
                "fields_found": list(data.fields.keys()),
            })

        return previews


# ─── Inbox Deliverable Generation ────────────────────────

INBOX_SUMMARY_SPEC = {
    "id": "summary",
    "name": "Conversation Summary",
    "description": "Comprehensive summary deliverable from inbox conversation",
    "fields": [],
    "template": {
        "title": "Conversation Summary — {{date}}",
        "sections": [
            {
                "id": "executive_summary",
                "heading": "Executive Summary",
                "body": "",
                "order": 1,
                "llm_enrich": True,
                "prompt": "Write a concise executive summary of this conversation. Cover who the visitor is, what they needed, and the key outcome. Transcript:\n{{transcript_text}}",
            },
            {
                "id": "key_points",
                "heading": "Key Discussion Points",
                "body": "",
                "order": 2,
                "llm_enrich": True,
                "prompt": "List the key discussion points from this conversation as bullet points. Be specific and factual. Transcript:\n{{transcript_text}}",
            },
            {
                "id": "visitor_profile",
                "heading": "Visitor Profile",
                "body": "",
                "order": 3,
                "llm_enrich": True,
                "prompt": "Summarize what we know about this visitor — their identity, role, organization, and any preferences or requirements they expressed. Transcript:\n{{transcript_text}}",
            },
            {
                "id": "data_collected",
                "heading": "Data Collected",
                "body": "",
                "order": 4,
                "llm_enrich": True,
                "prompt": "List all data collected during this conversation: contact information, requirements, preferences, constraints, and any form submissions. Transcript:\n{{transcript_text}}",
            },
            {
                "id": "next_steps",
                "heading": "Recommended Next Steps",
                "body": "",
                "order": 5,
                "llm_enrich": True,
                "prompt": "Based on this conversation, recommend concrete next steps for the deployer. Be actionable and specific. Transcript:\n{{transcript_text}}",
            },
        ],
    },
    "trigger": {"min_turns": 1, "contact_required": False},
    "channels": ["download"],
}

_INBOX_SPEC_MAP = {
    "summary": INBOX_SUMMARY_SPEC,
    "full_review": {
        "id": "full_review",
        "name": "Full Review",
        "description": "Structured intake review shaped by pack context — extracts key details, organizes into actionable sections.",
        "template": {
            "title": "Full Review — {{contact_name}} — {{date}}",
            "format": "markdown",
            "sections": [
                {
                    "id": "chief_concern",
                    "heading": "Chief Concern / Primary Topic",
                    "body": "",
                    "order": 1,
                    "llm_enrich": True,
                    "prompt": "Identify the primary concern, question, or topic the visitor brought to this conversation. Be specific — what exactly did they need? Transcript:\n{{transcript_text}}",
                },
                {
                    "id": "key_details",
                    "heading": "Key Details Extracted",
                    "body": "",
                    "order": 2,
                    "llm_enrich": True,
                    "prompt": "Extract all key details from this conversation: contact information, symptoms/claims/qualifications, specific numbers or dates mentioned, preferences, constraints, and any structured data collected via forms. Present as organized bullet points grouped by category. Transcript:\n{{transcript_text}}",
                },
                {
                    "id": "timeline_context",
                    "heading": "Timeline & Context",
                    "body": "",
                    "order": 3,
                    "llm_enrich": True,
                    "prompt": "Reconstruct the timeline of this conversation: what was discussed first, how the conversation evolved, any pivots or escalations. Note the duration and engagement level. Transcript:\n{{transcript_text}}",
                },
                {
                    "id": "actions_discussed",
                    "heading": "Actions Taken / Discussed",
                    "body": "",
                    "order": 4,
                    "llm_enrich": True,
                    "prompt": "List all actions that were taken during the conversation (information provided, forms completed, links shared) and any actions that were discussed but not yet completed. Transcript:\n{{transcript_text}}",
                },
                {
                    "id": "assessment",
                    "heading": "Assessment / Routing Recommendation",
                    "body": "",
                    "order": 5,
                    "llm_enrich": True,
                    "prompt": "Provide a professional assessment of this conversation: visitor intent clarity, engagement quality, urgency level, and a routing recommendation (e.g., schedule follow-up, escalate to specialist, mark resolved, add to nurture sequence). Transcript:\n{{transcript_text}}",
                },
                {
                    "id": "next_steps",
                    "heading": "Recommended Next Steps",
                    "body": "",
                    "order": 6,
                    "llm_enrich": True,
                    "prompt": "Based on the full conversation, recommend concrete, prioritized next steps for the deployer. Be actionable and specific — include timeframes where appropriate. Transcript:\n{{transcript_text}}",
                },
            ],
        },
        "extraction": {
            "fields": {
                "contact_name": {"source": "contact_info.name", "required": False},
                "contact_email": {"source": "contact_info.email", "required": False},
                "date": {"source": "timestamp", "required": False},
                "pack_context": {"source": "pack_id", "required": False},
            },
        },
        "trigger": {"min_turns": 1, "contact_required": False},
        "channels": ["download"],
    },
    "case_file": {
        **INBOX_SUMMARY_SPEC,
        "id": "case_file",
        "name": "Case File",
        "template": {
            **INBOX_SUMMARY_SPEC["template"],
            "title": "Case File — {{contact_name}} — {{date}}",
        },
    },
    "pitch": {
        **INBOX_SUMMARY_SPEC,
        "id": "pitch",
        "name": "Pitch Brief",
        "template": {
            **INBOX_SUMMARY_SPEC["template"],
            "title": "Pitch Brief — {{contact_name}} — {{date}}",
        },
    },
    "proposal": {
        **INBOX_SUMMARY_SPEC,
        "id": "proposal",
        "name": "Proposal Draft",
        "template": {
            **INBOX_SUMMARY_SPEC["template"],
            "title": "Proposal — {{contact_name}} — {{date}}",
        },
    },
    "blueprint": {
        **INBOX_SUMMARY_SPEC,
        "id": "blueprint",
        "name": "Blueprint",
        "template": {
            **INBOX_SUMMARY_SPEC["template"],
            "title": "Blueprint — {{contact_name}} — {{date}}",
        },
    },
}


async def generate_from_inbox(
    conversation,
    spec_id: str,
) -> Deliverable:
    """
    Generate a deliverable from an inbox conversation.

    Builds a synthetic SessionTranscript from the inbox conversation data,
    runs extraction, generates the deliverable, and stores it.

    Args:
        conversation: InboxConversation instance
        spec_id: One of 'case_file', 'pitch', 'proposal', 'blueprint', 'summary'

    Returns:
        Generated Deliverable object
    """
    from transcripts import SessionTranscript, TranscriptEntry

    # Build synthetic SessionTranscript from inbox conversation
    entries = [
        TranscriptEntry(
            timestamp=m.get("timestamp", 0),
            role=m.get("role", "user"),
            content=m.get("content", ""),
        )
        for m in (conversation.transcript or [])
    ]
    transcript = SessionTranscript(
        session_id=conversation.session_id or "",
        pack_id=conversation.pack_id or "",
        entries=entries,
        turn_count=conversation.turns,
        contact_info={
            k: v for k, v in {
                "name": conversation.visitor_name,
                "email": conversation.visitor_email,
            }.items() if v
        } or None,
    )

    # Build transcript text for LLM context
    lines = []
    for e in entries:
        lines.append(f"{e.role}: {e.content}")
    transcript_text = "\n".join(lines)[:8000]

    # Load spec
    spec_dict = _INBOX_SPEC_MAP.get(spec_id, INBOX_SUMMARY_SPEC)
    spec = DeliverableSpec.from_dict(spec_dict)

    # Get LLM provider for enrichment
    try:
        from llm_provider import get_llm_provider
        llm = get_llm_provider()
    except Exception:
        llm = None

    generator = DeliverableGenerator(llm_provider=llm)

    # Run extraction
    extractor = DeliverableExtractor()
    data = extractor.extract(transcript, spec)

    # Inject transcript_text into extracted data for LLM prompts
    data.fields["transcript_text"] = transcript_text

    # Generate deliverable
    deliverable = generator.generate(spec, data, transcript)

    # Store the deliverable
    try:
        # Try to use the global pipeline's store
        from app import deliverable_pipeline
        if deliverable_pipeline and deliverable_pipeline.store:
            deliverable_pipeline.store.add(deliverable)
    except Exception:
        logger.debug("Deliverable store unavailable, skipping persistence")

    return deliverable
