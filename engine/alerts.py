"""
TMOS13 Alert Classifier & Store

Rule-based alert classification engine. Evaluates session transcripts against
pack-defined alert rules and fires notifications when criteria are met.

Each pack defines its own alert rules in the manifest under the "alerts" key.
Rules can trigger on: keyword matches, contact info collection, cartridge
completion, turn count thresholds, and escalation requests.

Usage:
    classifier = AlertClassifier()
    alerts = classifier.evaluate(transcript, pack_manifest_alerts)
    for alert in alerts:
        dispatch_notification(alert)
"""
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from transcripts import SessionTranscript

logger = logging.getLogger("tmos13.alerts")


# ─── Enums ───────────────────────────────────────────────

class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    NEW = "new"
    SEEN = "seen"
    HANDLED = "handled"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


# Priority badge for display
PRIORITY_BADGES = {
    "low": "🟢 LOW",
    "medium": "🟡 MED",
    "high": "🔴 HIGH",
    "critical": "🔴 CRITICAL",
}


# ─── Data Models ─────────────────────────────────────────

@dataclass
class AlertRule:
    """A single alert rule defined in a pack manifest."""
    id: str = ""
    name: str = ""
    description: str = ""
    trigger: str = ""           # contact_info_present | keywords | cartridge_completed | turn_count | escalation
    priority: str = "medium"
    channels: list[str] = field(default_factory=lambda: ["dashboard"])
    keywords: list[str] = field(default_factory=list)
    cartridge: str = ""
    threshold: int = 0

    @staticmethod
    def from_dict(d: dict) -> "AlertRule":
        return AlertRule(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            trigger=d.get("trigger", ""),
            priority=d.get("priority", "medium"),
            channels=d.get("channels", ["dashboard"]),
            keywords=d.get("keywords", []),
            cartridge=d.get("cartridge", ""),
            threshold=d.get("threshold", 0),
        )


@dataclass
class Alert:
    """A fired alert — the result of a rule matching a transcript."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""
    transcript_id: str = ""
    pack_id: str = ""
    user_id: str = "anonymous"

    # Rule that triggered this
    rule_id: str = ""
    rule_name: str = ""

    # Classification
    priority: str = "medium"
    reason: str = ""
    channels: list[str] = field(default_factory=list)

    # Extracted context
    transcript_summary: str = ""
    contact_info: Optional[dict] = None
    matched_keywords: list[str] = field(default_factory=list)

    # State
    status: str = "new"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    handled_by: str = ""
    handler_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def priority_badge(self) -> str:
        return PRIORITY_BADGES.get(self.priority, self.priority)

    @property
    def created_at_display(self) -> str:
        dt = datetime.fromtimestamp(self.created_at, tz=timezone.utc)
        return dt.strftime("%b %d, %Y at %I:%M %p %Z")

    @property
    def is_actionable(self) -> bool:
        return self.status in ("new", "seen")


# ─── Alert Classifier ───────────────────────────────────

class AlertClassifier:
    """
    Evaluates a session transcript against pack-defined alert rules.

    Rules are loaded from the pack manifest's "alerts.rules" array.
    Each rule has a trigger type that determines the evaluation logic.
    """

    # Map of trigger type → evaluation method name
    _TRIGGER_HANDLERS = {
        "contact_info_present": "_eval_contact_info",
        "keywords": "_eval_keywords",
        "cartridge_completed": "_eval_cartridge_completed",
        "turn_count": "_eval_turn_count",
        "escalation": "_eval_escalation",
        "deliverable_ready": "_eval_deliverable_ready",
        "distillation_warning": "_eval_distillation_warning",
    }

    def evaluate(
        self,
        transcript: SessionTranscript,
        alerts_config: dict,
    ) -> list[Alert]:
        """
        Run all alert rules against a transcript.

        Args:
            transcript: The session transcript to evaluate.
            alerts_config: The "alerts" section from the pack manifest.

        Returns:
            List of Alert objects for rules that matched.
        """
        if not alerts_config or not alerts_config.get("enabled", False):
            return []

        rules_data = alerts_config.get("rules", [])
        if not rules_data:
            return []

        rules = [AlertRule.from_dict(r) for r in rules_data]
        fired: list[Alert] = []

        for rule in rules:
            handler_name = self._TRIGGER_HANDLERS.get(rule.trigger)
            if not handler_name:
                logger.warning(f"Unknown alert trigger type: {rule.trigger} (rule: {rule.id})")
                continue

            handler = getattr(self, handler_name)
            result = handler(transcript, rule)

            if result is not None:
                alert = Alert(
                    session_id=transcript.session_id,
                    transcript_id=transcript.transcript_id,
                    pack_id=transcript.pack_id,
                    user_id=transcript.user_id,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    priority=rule.priority,
                    reason=result.get("reason", rule.description),
                    channels=rule.channels,
                    transcript_summary=transcript.summary or "",
                    contact_info=transcript.contact_info,
                    matched_keywords=result.get("matched_keywords", []),
                )
                fired.append(alert)
                logger.info(
                    f"Alert fired: rule={rule.id} priority={rule.priority} "
                    f"session={transcript.session_id}"
                )

        return fired

    # ─── Trigger Evaluators ──────────────────────────────

    def _eval_contact_info(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: contact_info_present — fires when name + email or phone collected."""
        ci = transcript.contact_info
        if not ci:
            return None

        has_name = bool(ci.get("name"))
        has_email = bool(ci.get("email"))
        has_phone = bool(ci.get("phone"))

        if has_name and (has_email or has_phone):
            return {
                "reason": f"Contact info collected: {ci.get('name')} "
                          f"({ci.get('email', ci.get('phone', 'N/A'))})",
            }
        return None

    def _eval_keywords(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: keywords — fires when any keyword found in user messages."""
        if not rule.keywords:
            return None

        all_user_text = " ".join(
            e.content for e in transcript.entries if e.role == "user"
        ).lower()

        matched = []
        for kw in rule.keywords:
            # Use word boundary matching for multi-word phrases
            pattern = re.escape(kw.lower())
            if re.search(r"\b" + pattern + r"\b", all_user_text):
                matched.append(kw)

        if matched:
            return {
                "reason": f"Keywords detected: {', '.join(matched)}",
                "matched_keywords": matched,
            }
        return None

    def _eval_cartridge_completed(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: cartridge_completed — fires when a specific cartridge was visited."""
        if not rule.cartridge:
            return None

        if rule.cartridge in transcript.cartridge_history:
            return {
                "reason": f"Cartridge '{rule.cartridge}' completed",
            }
        return None

    def _eval_turn_count(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: turn_count — fires when session exceeds N turns."""
        threshold = rule.threshold if rule.threshold > 0 else 10
        if transcript.turn_count >= threshold:
            return {
                "reason": f"Session exceeded {threshold} turns "
                          f"({transcript.turn_count} total)",
            }
        return None

    def _eval_escalation(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: escalation — fires when user explicitly asks for a human."""
        escalation_phrases = [
            "speak to someone", "talk to a human", "real person",
            "call me", "representative", "speak with someone",
            "talk to someone", "human agent", "live agent",
            "transfer me", "speak to a person",
        ]

        all_user_text = " ".join(
            e.content for e in transcript.entries if e.role == "user"
        ).lower()

        matched = []
        for phrase in escalation_phrases:
            if phrase in all_user_text:
                matched.append(phrase)

        if matched:
            return {
                "reason": f"User requested human escalation: \"{matched[0]}\"",
                "matched_keywords": matched,
            }
        return None

    def _eval_deliverable_ready(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: deliverable_ready — fires when a deliverable was generated for this session."""
        # Check if the transcript's classification dict has deliverable info
        # (set by the deliverable pipeline after generation)
        classification = transcript.classification or {}
        deliverables = classification.get("deliverables_generated", [])
        if deliverables:
            names = ", ".join(d.get("name", d.get("spec_id", "unknown")) for d in deliverables)
            return {
                "reason": f"Deliverable generated: {names}",
            }
        return None

    def _eval_distillation_warning(
        self, transcript: SessionTranscript, rule: AlertRule
    ) -> Optional[dict]:
        """Trigger: distillation_warning — fires when distillation signals detected on session."""
        classification = transcript.classification or {}
        distillation = classification.get("distillation", {})
        signals = distillation.get("signals", [])
        signal_count = distillation.get("signal_count", 0)

        threshold = rule.threshold if rule.threshold > 0 else 3
        if signal_count >= threshold:
            return {
                "reason": (
                    f"Distillation signals detected: {signal_count} signals "
                    f"({', '.join(signals[:5])})"
                ),
                "matched_keywords": signals,
            }
        return None


# ─── Alert Store ─────────────────────────────────────────

class AlertStore:
    """
    In-memory store for fired alerts. Provides CRUD operations,
    filtering, and status management.
    """

    def __init__(self):
        self._alerts: dict[str, Alert] = {}
        logger.info("AlertStore initialized")

    def add(self, alert: Alert) -> Alert:
        """Store a fired alert."""
        self._alerts[alert.alert_id] = alert
        return alert

    def add_many(self, alerts: list[Alert]) -> list[Alert]:
        """Store multiple alerts."""
        for alert in alerts:
            self._alerts[alert.alert_id] = alert
        return alerts

    def get(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)

    def update_status(
        self,
        alert_id: str,
        status: str,
        handled_by: str = "",
        note: str = "",
    ) -> Optional[Alert]:
        """Update an alert's status."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.status = status
        alert.updated_at = time.time()
        if handled_by:
            alert.handled_by = handled_by
        if note:
            alert.handler_note = note

        logger.info(f"Alert {alert_id} status → {status}")
        return alert

    def list_alerts(
        self,
        pack_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Alert]:
        """List alerts with optional filters, sorted by created_at descending."""
        results = list(self._alerts.values())
        if pack_id:
            results = [a for a in results if a.pack_id == pack_id]
        if user_id:
            results = [a for a in results if a.user_id == user_id]
        if status:
            results = [a for a in results if a.status == status]
        if priority:
            results = [a for a in results if a.priority == priority]
        if session_id:
            results = [a for a in results if a.session_id == session_id]
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results[offset:offset + limit]

    def delete(self, alert_id: str) -> bool:
        """Remove an alert."""
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._alerts)

    @property
    def unread_count(self) -> int:
        return sum(1 for a in self._alerts.values() if a.status == "new")

    def get_stats(self) -> dict:
        """Return alert store statistics."""
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_pack: dict[str, int] = {}

        for alert in self._alerts.values():
            by_status[alert.status] = by_status.get(alert.status, 0) + 1
            by_priority[alert.priority] = by_priority.get(alert.priority, 0) + 1
            by_pack[alert.pack_id] = by_pack.get(alert.pack_id, 0) + 1

        return {
            "total_alerts": self.count,
            "unread": self.unread_count,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_pack": by_pack,
        }
