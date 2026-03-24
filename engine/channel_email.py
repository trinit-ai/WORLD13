"""
13TMOS Email Channel — Resend Inbound/Outbound

Inbound email to handle@tmos13.ai is forwarded by Resend as a webhook POST.
The session runner processes the message. The reply is sent back via Resend API.

Thread continuity via In-Reply-To and References headers — standard email threading.

Endpoints:
  POST /channels/email/inbound  — Resend inbound webhook
  GET  /channels/email/status   — Channel health check
  GET  /channels/email/handles  — Handle → pack routing map

Environment variables:
  RESEND_API_KEY         — Resend API key (already in Railway for outbound)
  EMAIL_DEFAULT_PACK     — default pack for unmapped handles (optional)
"""
from __future__ import annotations

import logging
import os
import re

import httpx
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("13tmos.channel.email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_API = "https://api.resend.com"
EMAIL_DEFAULT_PACK = os.getenv("EMAIL_DEFAULT_PACK", "enlightened_duck")

# Handle → pack routing: each email address is a different pack
HANDLE_PACK_MAP = {
    "duck": "enlightened_duck",
    "intake": "legal_intake",
    "hello": "guest",
}

# Lazy runner
_runner = None


def _get_runner():
    global _runner
    if _runner is None:
        from session_runner import SessionRunner
        _runner = SessionRunner()
    return _runner


def get_pack_for_handle(handle: str) -> str:
    """Map email handle to pack ID."""
    return HANDLE_PACK_MAP.get(handle.lower(), EMAIL_DEFAULT_PACK)


def extract_reply_text(body: str) -> str:
    """Strip quoted reply history from email body.

    Removes everything after common reply markers.
    Returns only the new message text.
    """
    separators = [
        r"^On .+ wrote:$",
        r"^From: .+$",
        r"^-{3,}.*Original Message.*-{3,}$",
        r"^_{3,}$",
        r"^\[.*\] wrote:$",
    ]
    lines = body.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        for sep in separators:
            if re.match(sep, stripped, re.IGNORECASE):
                return "\n".join(lines[:i]).strip()
    return body.strip()


async def send_email_reply(
    to: str,
    from_address: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    references: str = "",
) -> bool:
    """Send reply via Resend API. Returns True on success."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.error("RESEND_API_KEY not set")
        return False

    headers = {}
    if in_reply_to:
        headers["In-Reply-To"] = in_reply_to
    if references:
        headers["References"] = references

    payload = {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if headers:
        payload["headers"] = headers

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{RESEND_API}/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        if r.status_code == 200:
            logger.info("Email sent to %s", to)
            return True
        logger.error("Resend error: %d %s", r.status_code, r.text[:200])
        return False


# Email channel constraint
EMAIL_CONSTRAINT = (
    "\n\n---\nCHANNEL CONSTRAINT — Email:\n"
    "- Write in plain text. No markdown, no HTML.\n"
    "- Responses can be longer than messaging channels — up to 3000 characters.\n"
    "- Write with the cadence of a letter. The reader is not watching you type.\n"
    "- No need for greetings like 'Hi!' — the subject line has already opened the door.\n"
)


def register_email_channel(app: FastAPI) -> None:
    """Register email inbound webhook and status endpoints."""

    @app.post("/channels/email/inbound")
    async def email_inbound(request: Request) -> Response:
        """Resend inbound webhook. Resend posts JSON with email data."""
        try:
            data = await request.json()
        except Exception:
            form = await request.form()
            data = dict(form)

        from_address = data.get("from", "")
        to_addresses = data.get("to", "")
        subject = data.get("subject", "")
        body_text = data.get("text", "") or data.get("body", "")
        message_id = data.get("message_id", "") or data.get("messageId", "")
        in_reply_to = data.get("in_reply_to", "") or data.get("inReplyTo", "")
        references = data.get("references", "")

        # Extract sender email — may be "Sofia <sofia@gmail.com>" or bare address
        sender_match = re.search(r"<(.+?)>", from_address)
        sender_email = sender_match.group(1) if sender_match else from_address.strip()

        # Extract destination handle (duck from duck@tmos13.ai)
        to_str = to_addresses if isinstance(to_addresses, str) else ", ".join(to_addresses) if isinstance(to_addresses, list) else str(to_addresses)
        handle_match = re.search(r"(\w+)@tmos13\.ai", to_str)
        handle = handle_match.group(1) if handle_match else "duck"
        from_bot = f"{handle}@tmos13.ai"

        pack_id = get_pack_for_handle(handle)

        # Strip quoted reply history — only process new text
        clean_body = extract_reply_text(body_text)
        if not clean_body:
            return Response(content="ok")

        # sender_id for session keying is the email address
        sender_id = sender_email.lower()

        logger.info("Email inbound: %s → %s@tmos13.ai | %s", sender_id, handle, subject[:40])

        # Inject email constraint into session_runner's channel constraints
        from session_runner import CHANNEL_CONSTRAINTS
        if "email" not in CHANNEL_CONSTRAINTS:
            CHANNEL_CONSTRAINTS["email"] = EMAIL_CONSTRAINT

        runner = _get_runner()
        try:
            reply = await runner.handle_message(
                channel="email",
                sender_id=sender_id,
                text=clean_body,
                default_pack=pack_id,
            )
        except Exception:
            logger.exception("Session runner error for email")
            reply = "Something went wrong processing your message. Please try again."

        # Build reply subject
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

        # Thread continuity via standard email headers
        reply_references = f"{references} {message_id}".strip() if references else message_id

        # Determine display name for from address
        pack_names = {
            "duck": "The Duck",
            "intake": "Legal Intake",
            "hello": "TMOS13",
        }
        display_name = pack_names.get(handle, "TMOS13")

        await send_email_reply(
            to=sender_email,
            from_address=f"{display_name} <{from_bot}>",
            subject=reply_subject,
            body=reply,
            in_reply_to=message_id,
            references=reply_references,
        )

        return Response(content="ok")

    @app.get("/channels/email/status")
    async def email_status():
        """Email channel health check."""
        api_key = os.getenv("RESEND_API_KEY", "")
        configured = bool(api_key)

        active_sessions = 0
        try:
            runner = _get_runner()
            row = runner.conn.execute(
                "SELECT COUNT(*) as cnt FROM channel_sessions WHERE channel = 'email' AND status IN ('active', 'seeded')"
            ).fetchone()
            active_sessions = row["cnt"] if row else 0
        except Exception:
            pass

        return {
            "channel": "email",
            "status": "configured" if configured else "unconfigured",
            "resend_api_key": "set" if configured else "missing",
            "default_pack": EMAIL_DEFAULT_PACK,
            "handles": {f"{h}@tmos13.ai": p for h, p in HANDLE_PACK_MAP.items()},
            "active_sessions": active_sessions,
            "inbound_webhook": "/channels/email/inbound",
        }

    @app.get("/channels/email/handles")
    async def email_handles():
        """Show which email handles route to which packs."""
        return {
            "handles": {f"{h}@tmos13.ai": p for h, p in HANDLE_PACK_MAP.items()},
            "default": EMAIL_DEFAULT_PACK,
        }

    logger.info("Email channel registered: POST /channels/email/inbound, GET /channels/email/status")
