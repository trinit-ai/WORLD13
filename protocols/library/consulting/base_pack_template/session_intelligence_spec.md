# SESSION INTELLIGENCE — Output Specification
# This defines what the engine produces from every session.
# Not a protocol file — this is a system spec for engine/parser and transcript generation.

---

## Session Intelligence Output

Every completed session produces a structured intelligence package. This is what the business receives — either pushed via notifications, pulled via dashboard, or downloaded as a transcript.

### Output Structure

```json
{
  "session_id": "fff80596",
  "session_url": "https://[domain]/session/fff80596",
  "pack_id": "legal_intake",
  "started_at": "2026-02-10T22:50:00Z",
  "ended_at": "2026-02-10T23:05:00Z",
  "duration_minutes": 15,
  "turn_count": 12,

  "classification": {
    "category": "personal_injury_intake",
    "intent": "legal_consultation_request",
    "outcome": "qualified_lead",
    "spam_score": 0.02,
    "confidence": 0.91
  },

  "qualification": {
    "score": 87,
    "urgency": "high",
    "sentiment_trajectory": ["neutral", "concerned", "hopeful"],
    "flags": ["statute_concern", "active_treatment", "evidence_available"],
    "disqualifiers": []
  },

  "contact": {
    "name": "Jane Doe",
    "email": "jane@email.com",
    "phone": "5551234567",
    "preferred_method": "phone",
    "company": null,
    "role": null,
    "collected_at": "2026-02-10T22:55:00Z"
  },

  "summary": {
    "one_line": "Slip-and-fall at grocery store, back injury, ER visit, seeking consultation.",
    "detailed": "Potential client describing slip-and-fall incident at SafeMart grocery store on Feb 8. Reports back injury with ER visit same day. Store manager witnessed the incident and generated an internal report. Medical documentation available. Client has not yet contacted insurance. Requesting attorney consultation. Time-sensitive: surveillance footage preservation may be needed.",
    "key_facts": [
      "Incident date: February 8, 2026",
      "Location: SafeMart, 123 Main St",
      "Injury: back injury, ER visit same day",
      "Witness: store manager present, internal report filed",
      "Medical records: available from ER visit",
      "Insurance: not yet contacted"
    ],
    "decisions": [],
    "action_items": [
      "Contact client by phone (preferred, evenings)",
      "Request surveillance footage preservation from SafeMart",
      "Schedule initial consultation within 48 hours",
      "Request ER medical records release"
    ]
  },

  "entities": {
    "people": ["Jane Doe", "store manager (unnamed)"],
    "organizations": ["SafeMart"],
    "locations": ["SafeMart, 123 Main St"],
    "dates": ["2026-02-08"],
    "medical": ["back injury", "ER visit"],
    "legal": ["slip and fall", "premises liability"]
  },

  "recommended_actions": [
    {
      "action": "Call client",
      "priority": "high",
      "reason": "Preferred contact method is phone, evenings",
      "deadline": "Within 24 hours"
    },
    {
      "action": "Preserve evidence",
      "priority": "urgent",
      "reason": "Store surveillance footage may be overwritten",
      "deadline": "Within 48 hours"
    },
    {
      "action": "Schedule consultation",
      "priority": "high",
      "reason": "Client is actively seeking representation",
      "deadline": "Within 72 hours"
    }
  ],

  "transcript": {
    "format": "markdown",
    "message_count": 12,
    "download_url": "https://[domain]/session/fff80596/transcript",
    "messages": [
      { "role": "system", "content": "...", "timestamp": "..." },
      { "role": "user", "content": "...", "timestamp": "..." }
    ]
  },

  "notifications_sent": [
    {
      "template": "urgent_lead",
      "channel": "sms",
      "sent_at": "2026-02-10T23:05:30Z",
      "recipient": "intake@firm.com"
    },
    {
      "template": "urgent_lead",
      "channel": "email",
      "sent_at": "2026-02-10T23:05:31Z",
      "recipient": "intake@firm.com"
    }
  ]
}
```

### Transcript Format (User-Facing Download)

The downloadable transcript is a clean markdown document:

```markdown
# Session Transcript
## [Pack Name] — [Date]

### Summary
[One-line summary]

### Details
[Detailed summary paragraph]

### Key Information
| Field | Value |
|-------|-------|
| [Key] | [Value] |
| ...   | ...   |

### Qualification
- **Score:** XX/100
- **Urgency:** [Level]
- **Intent:** [Classification]

### Recommended Next Steps
1. [Action 1]
2. [Action 2]
3. [Action 3]

---

### Full Conversation

**[Timestamp]** — System:
[Message]

**[Timestamp]** — Visitor:
[Message]

[... full conversation ...]

---

*Session ID: [ID] | Generated: [Timestamp] | Powered by TMOS13*
```

### Business Dashboard View

The CRM/dashboard shows session intelligence as a card:

```
┌─────────────────────────────────────────┐
│ ● HIGH URGENCY                    87/100 │
│                                          │
│ Jane Doe — Personal Injury Intake        │
│ Slip-and-fall, back injury, seeking atty │
│                                          │
│ 📞 (555) 123-4567 (phone, evenings)     │
│ 📧 jane@email.com                        │
│                                          │
│ ⚡ Preserve surveillance footage         │
│ 📅 Schedule consultation within 48h      │
│                                          │
│ [View Transcript] [Assign] [Dismiss]     │
└─────────────────────────────────────────┘
```

### Notification Templates

**qualified_lead (email):**
```
Subject: New Qualified Lead — [Score]/100 — [One-line summary]

[Visitor Name] just completed a session via [Pack Name].

Summary: [Detailed summary]

Contact: [Name, phone, email, preferred method]
Score: [XX]/100 | Urgency: [Level]

Next Steps:
- [Action 1]
- [Action 2]

[View Full Transcript →]
```

**urgent_lead (SMS):**
```
🔴 URGENT LEAD ([Score]/100): [Visitor Name] — [One-line summary]. Preferred: [contact method]. [View →]
```

**spam_flag (log only):**
```
Session [ID] flagged as spam (score: [X.XX]). Reason: [detection reason]. No notification sent.
```
