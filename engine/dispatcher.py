"""
TMOS13 Action Dispatcher for Proactive Triggers

Receives TriggerEvents from the evaluator and routes them to
appropriate action handlers. Every dispatched action is logged
to the trigger_audit table.

SAFETY PRINCIPLE: The dispatcher validates that the requested action
is permitted by the handlers registry before executing. It never
executes actions that aren't declared. Template structure is enforced;
the model only generates content within LLM_SECTION blocks.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from triggers import TriggerEvent

logger = logging.getLogger("tmos13.dispatcher")

# Global rate limit: max outbound emails per pack per hour
_DEFAULT_RATE_LIMIT = 20
_rate_counters: dict[str, list[float]] = {}  # pack_id → [timestamps]


# ─── Template Rendering ─────────────────────────────────────

_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w[\w.]*)\}\}")
_LLM_SECTION_RE = re.compile(
    r"\{\{LLM_SECTION:\s*(\w+)\}\}(.*?)\{\{/LLM_SECTION\}\}",
    re.DOTALL,
)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _resolve_template_var(path: str, context: dict) -> str:
    """Resolve a dotted path against a context dict."""
    parts = path.split(".")
    current = context
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return str(current) if current is not None else ""


def render_template(
    template_text: str,
    context: dict,
    llm_fn=None,
) -> dict:
    """
    Render an email template with variable substitution and optional LLM sections.

    Args:
        template_text: Raw template with {{vars}} and optional {{LLM_SECTION}} blocks
        context: Variable context (captured_fields, pack_display_name, etc.)
        llm_fn: Optional async function(prompt, context) → str for LLM sections.
                If None, LLM sections use their body text as fallback.

    Returns:
        {subject, from_name, reply_to, body_html, body_text}
    """
    # Parse frontmatter
    subject = ""
    from_name = ""
    reply_to = ""
    body = template_text

    fm_match = _FRONTMATTER_RE.match(template_text)
    if fm_match:
        frontmatter = fm_match.group(1)
        body = template_text[fm_match.end():]
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip().strip('"').strip("'")
                if key == "subject":
                    subject = val
                elif key == "from_name":
                    from_name = val
                elif key == "reply_to":
                    reply_to = val

    # Replace LLM sections with placeholders or generated content
    def _replace_llm(match):
        section_name = match.group(1)
        prompt_text = match.group(2).strip()
        if llm_fn:
            # LLM generation would happen here in production
            # For now, use a descriptive placeholder
            return f"[Generated content for {section_name}]"
        return f"[{section_name}]"

    body = _LLM_SECTION_RE.sub(_replace_llm, body)

    # Substitute template variables in subject and body
    def _sub_var(match):
        return _resolve_template_var(match.group(1), context)

    subject = _TEMPLATE_VAR_RE.sub(_sub_var, subject)
    from_name = _TEMPLATE_VAR_RE.sub(_sub_var, from_name)
    reply_to = _TEMPLATE_VAR_RE.sub(_sub_var, reply_to)
    body = _TEMPLATE_VAR_RE.sub(_sub_var, body)

    return {
        "subject": subject,
        "from_name": from_name,
        "reply_to": reply_to,
        "body_html": body.strip(),
        "body_text": _strip_html(body.strip()),
    }


def _strip_html(html: str) -> str:
    """Naive HTML to plain text (for the text/plain email version)."""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_template(pack_protocol_dir: Path, template_name: str) -> str | None:
    """Load a template file from a pack's templates/ directory."""
    template_path = pack_protocol_dir / "templates" / f"{template_name}.md"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    # Try without .md extension
    template_path = pack_protocol_dir / "templates" / template_name
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return None


# ─── Rate Limiting ───────────────────────────────────────────

def _check_rate_limit(pack_id: str, limit: int = _DEFAULT_RATE_LIMIT) -> bool:
    """
    Check if pack has exceeded outbound email rate limit.
    Returns True if the send should be BLOCKED.
    """
    import time
    now = time.time()
    hour_ago = now - 3600

    if pack_id not in _rate_counters:
        _rate_counters[pack_id] = []

    # Prune old timestamps
    _rate_counters[pack_id] = [t for t in _rate_counters[pack_id] if t > hour_ago]

    if len(_rate_counters[pack_id]) >= limit:
        return True  # blocked

    _rate_counters[pack_id].append(now)
    return False


# ─── Audit Logging ───────────────────────────────────────────

async def log_trigger_audit(
    db,
    event: TriggerEvent,
    status: str,
    recipient: str = "",
    subject: str = "",
    error_message: str = "",
    provider_response: dict = None,
    attempt_number: int = 1,
) -> str | None:
    """Log a trigger dispatch to the audit table."""
    if db is None:
        return None

    audit_id = str(uuid.uuid4())
    row = {
        "id": audit_id,
        "trigger_id": event.trigger_id,
        "pack_id": event.pack_id,
        "persistent_session_id": event.persistent_session_id or None,
        "action": event.action,
        "channel": event.channel,
        "template": event.template,
        "status": status,
        "recipient": recipient,
        "subject": subject,
        "error_message": error_message,
        "provider_response": provider_response or {},
        "requires_approval": event.requires_approval,
        "fired_at": datetime.now(timezone.utc).isoformat(),
        "attempt_number": attempt_number,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        db.table("trigger_audit").insert(row).execute()
        return audit_id
    except Exception as e:
        logger.warning(f"Failed to log trigger audit: {e}")
        return None


# ─── ActionDispatcher ────────────────────────────────────────

class ActionDispatcher:
    """Routes trigger events to action handlers."""

    def __init__(
        self,
        supabase_client=None,
        email_fn=None,
        escalation_email: str = "owner@tmos13.ai",
        rate_limit: int = _DEFAULT_RATE_LIMIT,
    ):
        """
        Args:
            supabase_client: For audit logging
            email_fn: Callable(to, subject, html, text) → message_id.
                      Defaults to email_service.send_email.
            escalation_email: Default recipient for escalation alerts
            rate_limit: Max outbound emails per pack per hour
        """
        self.db = supabase_client
        self._email_fn = email_fn
        self.escalation_email = escalation_email
        self.rate_limit = rate_limit

        self._handlers = {
            "send_email": self._handle_send_email,
            "escalate": self._handle_escalate,
            "send_notification": self._handle_notification,
            "update_status": self._handle_status_update,
        }

    @property
    def supported_actions(self) -> list[str]:
        return list(self._handlers.keys())

    async def dispatch(self, event: TriggerEvent) -> dict:
        """
        Execute a trigger event:
        1. Validate action is in handlers registry
        2. If requires_approval, queue for approval
        3. Execute the action handler
        4. Log to trigger_audit table
        5. Return result summary
        """
        action = event.action
        if action not in self._handlers:
            error = f"Unknown action: {action}"
            logger.warning(f"Dispatch rejected: {error}")
            await log_trigger_audit(self.db, event, "failed", error_message=error)
            return {"status": "failed", "error": error}

        # Approval gate
        if event.requires_approval:
            await log_trigger_audit(self.db, event, "approval_pending")
            logger.info(
                f"Trigger {event.trigger_id} queued for approval "
                f"(pack={event.pack_id} session={event.persistent_session_id})"
            )
            return {"status": "approval_pending", "trigger_id": event.trigger_id}

        # Rate limit check (email actions)
        if action in ("send_email", "escalate"):
            if _check_rate_limit(event.pack_id, self.rate_limit):
                error = f"Rate limit exceeded for pack {event.pack_id}"
                logger.warning(error)
                await log_trigger_audit(self.db, event, "failed", error_message=error)
                return {"status": "rate_limited", "error": error}

        # Execute handler
        handler = self._handlers[action]
        try:
            result = await handler(event)
            status = result.get("status", "dispatched")
            await log_trigger_audit(
                self.db,
                event,
                status=status,
                recipient=result.get("recipient", ""),
                subject=result.get("subject", ""),
                provider_response=result.get("provider_response"),
            )
            return result
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Dispatch failed: {event.trigger_id} → {error_msg}")
            await log_trigger_audit(
                self.db, event, "failed", error_message=error_msg
            )
            return {"status": "failed", "error": error_msg}

    async def _handle_send_email(self, event: TriggerEvent) -> dict:
        """
        Send a proactive email.

        Uses the template from the pack's templates/ directory if available,
        otherwise constructs a basic email from event metadata.
        """
        email = event.contact_identity.get("email")
        if not email:
            return {"status": "failed", "error": "No contact email available"}

        name = event.contact_identity.get("name", "there")
        subject = f"Following up — {event.metadata.get('description', event.trigger_id)}"
        body = (
            f"Hi {name},\n\n"
            f"We wanted to follow up on your recent interaction.\n\n"
            f"Best regards"
        )

        # Try to load and render template
        template_text = event.metadata.get("rendered_template")
        if template_text and isinstance(template_text, dict):
            subject = template_text.get("subject", subject)
            body = template_text.get("body_html", body)

        # Send via email function
        email_fn = self._email_fn
        if email_fn is None:
            try:
                from email_service import send_email as default_send
                email_fn = default_send
            except ImportError:
                return {"status": "failed", "error": "Email service not available"}

        msg_id = email_fn(to=email, subject=subject, html=body, text=_strip_html(body))

        return {
            "status": "dispatched" if msg_id else "failed",
            "recipient": email,
            "subject": subject,
            "provider_response": {"message_id": msg_id} if msg_id else None,
            "error": "" if msg_id else "Email send returned None",
        }

    async def _handle_escalate(self, event: TriggerEvent) -> dict:
        """Send an internal alert to the business owner/team."""
        identity = event.contact_identity
        session_meta = event.metadata.get("session_data", {})

        subject = (
            f"[TMOS13 Escalation] {event.priority.upper()} — "
            f"{event.metadata.get('description', event.trigger_id)}"
        )
        body_lines = [
            f"<h2>Trigger: {event.trigger_id}</h2>",
            f"<p><strong>Pack:</strong> {event.pack_id}</p>",
            f"<p><strong>Priority:</strong> {event.priority}</p>",
            f"<p><strong>Description:</strong> {event.metadata.get('description', '')}</p>",
        ]
        if identity.get("name"):
            body_lines.append(f"<p><strong>Contact:</strong> {identity['name']}")
            if identity.get("email"):
                body_lines.append(f" ({identity['email']})")
            body_lines.append("</p>")
        if session_meta:
            body_lines.append("<p><strong>Session:</strong> ")
            body_lines.append(
                f"Score={session_meta.get('qualification_score', 0)} "
                f"Depth={session_meta.get('depth', 0)} "
                f"Turns={session_meta.get('total_turns', 0)}"
            )
            body_lines.append("</p>")

        body = "\n".join(body_lines)

        email_fn = self._email_fn
        if email_fn is None:
            try:
                from email_service import send_email as default_send
                email_fn = default_send
            except ImportError:
                return {"status": "failed", "error": "Email service not available"}

        msg_id = email_fn(
            to=self.escalation_email, subject=subject,
            html=body, text=_strip_html(body),
        )

        return {
            "status": "dispatched" if msg_id else "failed",
            "recipient": self.escalation_email,
            "subject": subject,
            "provider_response": {"message_id": msg_id} if msg_id else None,
        }

    async def _handle_notification(self, event: TriggerEvent) -> dict:
        """Send an internal notification (logged to alerts)."""
        logger.info(
            f"Notification trigger: {event.trigger_id} "
            f"pack={event.pack_id} session={event.persistent_session_id}"
        )
        return {
            "status": "dispatched",
            "channel": "notification",
            "trigger_id": event.trigger_id,
        }

    async def _handle_status_update(self, event: TriggerEvent) -> dict:
        """Update a persistent session's status."""
        new_status = event.metadata.get("new_status", "resolved")
        if not self.db or not event.persistent_session_id:
            return {"status": "failed", "error": "No DB or session ID"}

        try:
            self.db.table("persistent_sessions").update(
                {
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", event.persistent_session_id).execute()

            return {
                "status": "dispatched",
                "new_session_status": new_status,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
