"""
TMOS13 Email — Resend Integration

Transactional email for authentication, billing, and engagement.
Sends welcome emails, password resets, subscription confirmations,
and engagement notifications.
"""
import logging
from typing import Optional

logger = logging.getLogger("tmos13.email")

_resend = None
_initialized = False
_from_email = "TMOS13 <noreply@tmos13.ai>"


def init_email(api_key: str, from_email: str = "TMOS13 <noreply@tmos13.ai>"):
    """Initialize Resend email service."""
    global _resend, _initialized, _from_email

    if not api_key:
        logger.info("Resend API key not configured — email disabled")
        return

    try:
        import resend
        resend.api_key = api_key
        _resend = resend
        _from_email = from_email
        _initialized = True
        logger.info("Email service initialized (Resend)")
    except ImportError:
        logger.warning("resend not installed — email disabled")
    except Exception as e:
        logger.error(f"Email init failed: {e}")


def send_email(to: str, subject: str, html: str, text: str = "") -> dict:
    """Send a single email. Returns structured result dict."""
    if not _resend or not _initialized:
        logger.warning(f"Email suppressed — RESEND_API_KEY not set: to={to} subject={subject}")
        return {"success": False, "message_id": None, "recipient": to, "error": "RESEND_API_KEY not configured"}

    try:
        result = _resend.Emails.send({
            "from": _from_email,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text or subject,
        })
        msg_id = result.get("id", "unknown")
        logger.info(f"Email sent: to={to} subject={subject} id={msg_id}")
        return {"success": True, "message_id": msg_id, "recipient": to, "error": None}
    except Exception as e:
        logger.error(f"Email send failed: to={to} error={e}")
        return {"success": False, "message_id": None, "recipient": to, "error": str(e)}


# ─── Template Emails ─────────────────────────────────────

EMERALD = "#34d399"
BG = "#060d0a"
CARD_BG = "#0a1510"
TEXT = "#e2e8f0"
MUTED = "#64748b"

BASE_STYLE = f"""
  <div style="background:{BG}; color:{TEXT}; font-family:'DM Sans',sans-serif;
       padding:40px 24px; max-width:560px; margin:0 auto;">
    <div style="font-family:'JetBrains Mono',monospace; font-size:18px;
         color:{EMERALD}; font-weight:700; letter-spacing:3px; margin-bottom:32px;">
      TMOS13
    </div>
"""

BASE_FOOTER = f"""
    <div style="margin-top:40px; padding-top:20px; border-top:1px solid #1e3a2f;
         font-size:12px; color:{MUTED}; font-family:'JetBrains Mono',monospace;">
      &copy; 2026 TMOS13, LLC &middot; Jersey City, NJ<br>
      <a href="mailto:support@tmos13.ai" style="color:{EMERALD}; text-decoration:none;">
        support@tmos13.ai
      </a>
    </div>
  </div>
"""


def send_welcome(to: str, display_name: str):
    """Welcome email after sign-up."""
    name = display_name or "Explorer"
    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:24px; margin-bottom:8px;">Welcome to the Orchard, {name}.</h2>
    <p style="color:{MUTED}; line-height:1.7; margin-bottom:24px;">
      Your account is ready. TMOS13 is a recursive experience engine —
      each cartridge is a world waiting to unfold.
    </p>
    <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
         padding:20px; margin-bottom:24px;">
      <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:14px; margin:0 0 8px;">
        Getting Started:
      </p>
      <p style="color:{TEXT}; font-size:14px; line-height:1.7; margin:0;">
        Type <strong style="color:{EMERALD}">333</strong> to boot the system.<br>
        Choose a cartridge to begin your first experience.<br>
        The deeper you go, the more the Orchard reveals.
      </p>
    </div>
    {BASE_FOOTER}"""
    return send_email(to, "Welcome to TMOS13", html)


def send_password_reset(to: str, reset_link: str):
    """Password reset email."""
    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:24px; margin-bottom:8px;">Reset Your Password</h2>
    <p style="color:{MUTED}; line-height:1.7; margin-bottom:24px;">
      We received a request to reset your TMOS13 password.
      Click the button below to set a new one.
    </p>
    <a href="{reset_link}" style="display:inline-block; background:{EMERALD}; color:{BG};
       padding:14px 32px; border-radius:6px; text-decoration:none;
       font-family:'JetBrains Mono',monospace; font-size:14px; font-weight:600;">
      Reset Password
    </a>
    <p style="color:{MUTED}; font-size:12px; margin-top:16px; line-height:1.6;">
      This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
    </p>
    {BASE_FOOTER}"""
    return send_email(to, "Reset your TMOS13 password", html)


def send_subscription_confirmed(to: str, tier: str, amount: str, interval: str):
    """Subscription confirmation email."""
    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:24px; margin-bottom:8px;">Subscription Confirmed</h2>
    <p style="color:{MUTED}; line-height:1.7; margin-bottom:24px;">
      You're now on the <strong style="color:{EMERALD}">{tier.upper()}</strong> plan.
    </p>
    <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
         padding:20px; margin-bottom:24px;">
      <p style="color:{TEXT}; font-size:14px; margin:0;">
        <strong>Plan:</strong> {tier.title()}<br>
        <strong>Amount:</strong> {amount}/{interval}<br>
        <strong>Status:</strong> <span style="color:{EMERALD};">Active</span>
      </p>
    </div>
    <p style="color:{MUTED}; font-size:13px; line-height:1.7;">
      You can manage your subscription anytime from Settings.
    </p>
    {BASE_FOOTER}"""
    return send_email(to, f"TMOS13 {tier.title()} — Subscription Confirmed", html)


def send_subscription_cancelled(to: str, tier: str, end_date: str):
    """Subscription cancellation confirmation."""
    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:24px; margin-bottom:8px;">Subscription Cancelled</h2>
    <p style="color:{MUTED}; line-height:1.7; margin-bottom:24px;">
      Your {tier.title()} subscription has been cancelled.
      You'll retain access until <strong style="color:{TEXT}">{end_date}</strong>.
    </p>
    <p style="color:{MUTED}; font-size:13px; line-height:1.7;">
      Changed your mind? You can resubscribe anytime from Settings.
      The Orchard remembers.
    </p>
    {BASE_FOOTER}"""
    return send_email(to, "TMOS13 — Subscription Cancelled", html)


def send_payment_failed(to: str, amount: str):
    """Payment failure notification."""
    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:24px; margin-bottom:8px;">Payment Failed</h2>
    <p style="color:{MUTED}; line-height:1.7; margin-bottom:24px;">
      We were unable to process your payment of <strong>{amount}</strong>.
      Please update your payment method to avoid service interruption.
    </p>
    <a href="https://tmos13.ai/settings" style="display:inline-block; background:{EMERALD}; color:{BG};
       padding:14px 32px; border-radius:6px; text-decoration:none;
       font-family:'JetBrains Mono',monospace; font-size:14px; font-weight:600;">
      Update Payment
    </a>
    {BASE_FOOTER}"""
    return send_email(to, "TMOS13 — Payment Failed", html)


def send_contact_form(
    to: str,
    name: str,
    sender_email: str,
    subject: str = "",
    company: str = "",
    message: str = "",
    role: str = "",
    session_id: str = "",
) -> dict:
    """Send a contact form submission notification."""
    subject_line = f"New inquiry from {name}" + (f" at {company}" if company else "")

    company_html = ""
    if company:
        company_html = f"<strong>Company:</strong> {company}<br>"

    role_html = ""
    if role:
        role_html = f"<strong>Role:</strong> {role}<br>"

    dashboard_html = ""
    if session_id:
        dashboard_url = f"https://tmos13.ai/dashboard/inbox?session={session_id}"
        dashboard_html = f"""
    <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
         padding:16px; margin-bottom:16px;">
      <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:13px;
         margin:0 0 8px; font-weight:600;">Session</p>
      <p style="color:{TEXT}; font-size:14px; line-height:1.7; margin:0;">
        Full conversation transcript is available in the dashboard.
      </p>
      <a href="{dashboard_url}" style="display:inline-block; color:{EMERALD};
         font-family:'JetBrains Mono',monospace; font-size:13px; margin-top:8px;
         text-decoration:none;">
        View in Dashboard &rarr;
      </a>
    </div>"""

    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:22px; margin-bottom:4px;">New Contact Submission</h2>
    <p style="color:{MUTED}; font-size:14px; margin-bottom:20px;">via tmos13.ai Data Rail</p>

    <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
         padding:20px; margin-bottom:16px;">
      <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:13px;
         margin:0 0 8px; font-weight:600;">Sender</p>
      <p style="color:{TEXT}; font-size:14px; line-height:1.8; margin:0;">
        <strong>Name:</strong> {name}<br>
        <strong>Email:</strong> <a href="mailto:{sender_email}" style="color:{EMERALD}; text-decoration:none;">{sender_email}</a><br>
        {company_html}
        {role_html}
      </p>
    </div>

    <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
         padding:20px; margin-bottom:16px;">
      <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:13px;
         margin:0 0 8px; font-weight:600;">Message</p>
      <p style="color:{TEXT}; font-size:14px; line-height:1.7; margin:0;
         white-space:pre-wrap;">{message or '(No message provided)'}</p>
    </div>

    {dashboard_html}

    <a href="mailto:{sender_email}" style="display:inline-block; background:{EMERALD}; color:{BG};
       padding:12px 28px; border-radius:6px; text-decoration:none;
       font-family:'JetBrains Mono',monospace; font-size:14px; font-weight:600;">
      Reply to {name}
    </a>
    {BASE_FOOTER}"""

    text = (
        f"New Contact Submission — tmos13.ai\n\n"
        f"Name: {name}\n"
        f"Email: {sender_email}\n"
        f"Company: {company}\n"
        f"Role: {role}\n\n"
        f"Message:\n{message}\n"
    )
    if session_id:
        text += f"\nDashboard: https://tmos13.ai/dashboard/inbox?session={session_id}\n"

    return send_email(to, subject_line, html, text)


def send_alert_email(
    to: str,
    pack_name: str,
    priority: str,
    priority_badge: str,
    reason: str,
    contact_info: dict = None,
    transcript_summary: str = "",
    session_id: str = "",
    started_at: str = "",
    duration: str = "",
    turn_count: int = 0,
    cartridge_path: str = "",
    transcript_url: str = "",
) -> dict:
    """
    Send an alert notification email with transcript summary.

    This is the primary Phase 1 alert delivery mechanism — a rich HTML email
    sent to the pack owner when an alert rule fires.
    """
    # Priority color mapping
    priority_colors = {
        "low": "#22c55e",       # green
        "medium": "#eab308",    # yellow
        "high": "#ef4444",      # red
        "critical": "#ef4444",  # red
    }
    priority_color = priority_colors.get(priority, EMERALD)

    # Build contact section
    contact_html = ""
    if contact_info:
        contact_lines = []
        if contact_info.get("name"):
            contact_lines.append(f"<strong>Name:</strong> {contact_info['name']}")
        if contact_info.get("email"):
            contact_lines.append(f"<strong>Email:</strong> {contact_info['email']}")
        if contact_info.get("phone"):
            contact_lines.append(f"<strong>Phone:</strong> {contact_info['phone']}")
        if contact_lines:
            contact_html = f"""
            <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
                 padding:16px; margin-bottom:16px;">
              <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:13px;
                 margin:0 0 8px; font-weight:600;">Contact</p>
              <p style="color:{TEXT}; font-size:14px; line-height:1.8; margin:0;">
                {'<br>'.join(contact_lines)}
              </p>
            </div>"""

    # Build summary section
    summary_html = ""
    if transcript_summary:
        summary_html = f"""
            <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
                 padding:16px; margin-bottom:16px;">
              <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:13px;
                 margin:0 0 8px; font-weight:600;">Summary</p>
              <p style="color:{TEXT}; font-size:14px; line-height:1.7; margin:0;">
                {transcript_summary}
              </p>
            </div>"""

    # Session details
    session_html = ""
    if started_at or duration or turn_count:
        details = []
        if started_at:
            details.append(f"<strong>Started:</strong> {started_at}")
        if duration:
            details.append(f"<strong>Duration:</strong> {duration}")
        if turn_count:
            details.append(f"<strong>Turns:</strong> {turn_count}")
        if cartridge_path:
            details.append(f"<strong>Path:</strong> {cartridge_path}")
        session_html = f"""
            <div style="background:{CARD_BG}; border:1px solid #1e3a2f; border-radius:8px;
                 padding:16px; margin-bottom:16px;">
              <p style="color:{EMERALD}; font-family:'JetBrains Mono',monospace; font-size:13px;
                 margin:0 0 8px; font-weight:600;">Session Details</p>
              <p style="color:{TEXT}; font-size:14px; line-height:1.8; margin:0;">
                {'<br>'.join(details)}
              </p>
            </div>"""

    # CTA button
    cta_html = ""
    if transcript_url:
        cta_html = f"""
            <a href="{transcript_url}" style="display:inline-block; background:{EMERALD}; color:{BG};
               padding:12px 28px; border-radius:6px; text-decoration:none;
               font-family:'JetBrains Mono',monospace; font-size:14px; font-weight:600;
               margin-top:8px;">
              View Full Transcript
            </a>"""

    subject = f"[TMOS13] {pack_name} — {priority.upper()} Priority Alert"

    html = f"""{BASE_STYLE}
    <h2 style="color:{TEXT}; font-size:22px; margin-bottom:4px;">New Alert</h2>
    <p style="color:{MUTED}; font-size:14px; margin-bottom:20px;">{pack_name}</p>

    <div style="display:inline-block; background:{priority_color}; color:#fff;
         padding:4px 12px; border-radius:4px; font-size:13px;
         font-family:'JetBrains Mono',monospace; font-weight:600;
         margin-bottom:16px;">
      {priority.upper()}
    </div>

    <p style="color:{TEXT}; font-size:15px; line-height:1.7; margin-bottom:20px;">
      <strong>Reason:</strong> {reason}
    </p>

    {contact_html}
    {summary_html}
    {session_html}
    {cta_html}
    {BASE_FOOTER}"""

    text = (
        f"TMOS13 Alert — {pack_name}\n\n"
        f"Priority: {priority.upper()}\n"
        f"Reason: {reason}\n\n"
        f"Summary: {transcript_summary}\n"
    )

    return send_email(to, subject, html, text)


def sync_to_resend_contacts(
    email: str,
    first_name: str = "",
    last_name: str = "",
    audience_id: str = "",
) -> Optional[str]:
    """Create/update a contact in a Resend Audience. Returns contact ID or None."""
    if not _resend or not _initialized:
        return None

    aid = audience_id
    if not aid:
        import os
        aid = os.environ.get("RESEND_AUDIENCE_ID", "")
    if not aid:
        logger.debug("No RESEND_AUDIENCE_ID — skipping Resend contact sync")
        return None

    try:
        params: dict = {"email": email, "audience_id": aid, "unsubscribed": False}
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        result = _resend.Contacts.create(params)
        contact_id = result.get("id")
        logger.info(f"Resend contact synced: {email} → {contact_id}")
        return contact_id
    except Exception as e:
        logger.warning(f"Resend contact sync failed for {email}: {e}")
        return None


def get_status() -> dict:
    return {
        "enabled": _initialized,
        "backend": "resend" if _initialized else "none",
        "from": _from_email if _initialized else None,
    }
