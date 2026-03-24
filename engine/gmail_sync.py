"""
TMOS13 Gmail Sync — IMAP Fetch → Inbox

Pulls recent emails from a Gmail account via IMAP and upserts them
into inbox_conversations so they appear in the dashboard inbox.

Requires:
  GMAIL_EMAIL        — Gmail address
  GMAIL_APP_PASSWORD — Gmail App Password (not regular password)

Generate an App Password: Google Account → Security → 2-Step Verification
→ App Passwords → generate one for "Mail".
"""
import email
import email.utils
import hashlib
import imaplib
import logging
import os
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from typing import Optional

logger = logging.getLogger("tmos13.gmail_sync")


def _decode_header_value(raw: str) -> str:
    """Decode RFC 2047 encoded header values."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace").strip()
        # Fallback to HTML if no plain text
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    # Rough strip HTML tags
                    import re
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    return text[:2000]
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace").strip()
        return ""


def _parse_sender(from_header: str) -> tuple[str, str]:
    """Parse 'Name <email>' into (name, email)."""
    name, addr = email.utils.parseaddr(from_header)
    return _decode_header_value(name) or addr.split("@")[0], addr.lower()


def _email_session_id(message_id: str, addr: str) -> str:
    """Deterministic session_id for dedup — hash of message-id."""
    key = message_id or addr + str(datetime.now(timezone.utc).timestamp())
    return "gmail_" + hashlib.sha256(key.encode()).hexdigest()[:24]


def sync_gmail(
    inbox_service,
    owner_id: str,
    max_emails: int = 25,
    days_back: int = 7,
) -> dict:
    """
    Fetch recent emails via IMAP and upsert into inbox_conversations.

    Returns: {synced: int, skipped: int, errors: int}
    """
    gmail_email = os.environ.get("GMAIL_EMAIL", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not gmail_email or not gmail_password:
        logger.debug("Gmail sync skipped — GMAIL_EMAIL or GMAIL_APP_PASSWORD not set")
        return {"synced": 0, "skipped": 0, "errors": 0, "reason": "not_configured"}

    synced = 0
    skipped = 0
    errors = 0

    try:
        # Connect
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(gmail_email, gmail_password)
        imap.select("INBOX", readonly=True)

        # Search recent emails
        since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%d-%b-%Y")
        _, msg_ids = imap.search(None, f'(SINCE "{since_date}")')

        ids = msg_ids[0].split()
        if not ids:
            imap.logout()
            return {"synced": 0, "skipped": 0, "errors": 0}

        # Take most recent N
        ids = ids[-max_emails:]

        for mid in ids:
            try:
                _, data = imap.fetch(mid, "(RFC822)")
                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                message_id = msg.get("Message-ID", "")
                from_header = _decode_header_value(msg.get("From", ""))
                subject = _decode_header_value(msg.get("Subject", "(no subject)"))
                date_str = msg.get("Date", "")
                sender_name, sender_email = _parse_sender(from_header)
                body = _extract_body(msg)

                # Skip emails from self
                if sender_email == gmail_email.lower():
                    skipped += 1
                    continue

                session_id = _email_session_id(message_id, sender_email)

                # Parse date
                date_tuple = email.utils.parsedate_tz(date_str)
                if date_tuple:
                    timestamp = email.utils.mktime_tz(date_tuple)
                    created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                else:
                    created_at = datetime.now(timezone.utc).isoformat()

                # Truncate body for summary
                summary = f"{subject}"
                if body:
                    summary += f" — {body[:200]}"

                inbox_service.record(
                    owner_id=owner_id,
                    deployment_id="gmail",
                    deployment_name="Gmail",
                    pack_id="gmail",
                    visitor_name=sender_name,
                    visitor_email=sender_email,
                    session_id=session_id,
                    transcript=[
                        {"role": "user", "content": f"Subject: {subject}\n\n{body[:3000]}"},
                    ],
                    classification="email",
                    summary=summary[:500],
                    priority="normal",
                    status="needs_review",
                )
                synced += 1

            except Exception as e:
                logger.warning(f"Gmail sync: failed to process email: {e}")
                errors += 1

        imap.logout()

    except imaplib.IMAP4.error as e:
        logger.error(f"Gmail IMAP auth failed: {e}")
        return {"synced": 0, "skipped": 0, "errors": 1, "reason": "auth_failed"}
    except Exception as e:
        logger.error(f"Gmail sync failed: {e}")
        return {"synced": synced, "skipped": skipped, "errors": errors + 1, "reason": str(e)}

    logger.info(f"Gmail sync complete: synced={synced} skipped={skipped} errors={errors}")
    return {"synced": synced, "skipped": skipped, "errors": errors}
