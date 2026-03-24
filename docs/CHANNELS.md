# 13TMOS Channels

Nine channel connectors. One session runner. Any pack. Any person.

---

## Channel Map

| Channel   | File                    | Webhook Path                         | Credentials Required     | Session |
|-----------|-------------------------|--------------------------------------|--------------------------|---------|
| Telegram  | channel_telegram.py     | POST /channels/telegram/{token}      | TELEGRAM_BOT_TOKEN       | 15      |
| WhatsApp  | channel_whatsapp.py     | POST /channels/whatsapp/webhook      | TWILIO_*                 | 14      |
| Email     | channel_email.py        | POST /channels/email/inbound         | RESEND_API_KEY           | 16      |
| SMS       | channel_sms.py          | POST /channels/sms/webhook           | TWILIO_* (shared)        | 17      |
| Discord   | channel_discord.py      | POST /channels/discord/webhook       | DISCORD_BOT_TOKEN        | 17      |
| Slack     | channel_slack.py        | POST /channels/slack/webhook         | SLACK_BOT_TOKEN          | 17      |
| Messenger | channel_messenger.py    | POST /channels/messenger/webhook     | META_PAGE_TOKEN          | 17      |
| Instagram | channel_instagram.py    | POST /channels/instagram/webhook     | META_PAGE_TOKEN (shared) | 17      |
| Web       | channel_web.py          | WS /channels/web/{token}             | None                     | 17      |

---

## Railway Environment Variables

```bash
# ── Telegram ──────────────────────────────────────
TELEGRAM_BOT_TOKEN=              # From @BotFather on Telegram
TELEGRAM_DEFAULT_PACK=enlightened_duck

# ── Twilio (WhatsApp + SMS) ──────────────────────
TWILIO_ACCOUNT_SID=              # From twilio.com console
TWILIO_AUTH_TOKEN=               # From twilio.com console
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TMOS13_WHATSAPP_PACK=enlightened_duck
SMS_DEFAULT_PACK=enlightened_duck

# ── Email (Resend) ───────────────────────────────
RESEND_API_KEY=                  # From resend.com dashboard
EMAIL_DEFAULT_PACK=enlightened_duck

# ── Discord ──────────────────────────────────────
DISCORD_BOT_TOKEN=               # From discord.com/developers → Bot
DISCORD_PUBLIC_KEY=              # From discord.com/developers → General Info
DISCORD_DEFAULT_PACK=enlightened_duck

# ── Slack ────────────────────────────────────────
SLACK_BOT_TOKEN=                 # xoxb-* from api.slack.com → OAuth
SLACK_SIGNING_SECRET=            # From api.slack.com → Basic Info
SLACK_DEFAULT_PACK=enlightened_duck

# ── Meta (Messenger + Instagram) ────────────────
META_PAGE_TOKEN=                 # From developers.facebook.com
META_VERIFY_TOKEN=tmos13duck     # You choose this
MESSENGER_DEFAULT_PACK=enlightened_duck
INSTAGRAM_DEFAULT_PACK=enlightened_duck

# ── Web ──────────────────────────────────────────
WEB_DEFAULT_PACK=enlightened_duck
# No credentials needed — live immediately
```

---

## Webhook Registration

Base URL: `https://13tmos-production.up.railway.app`

| Platform  | Where to Configure | URL to Register |
|-----------|--------------------|-----------------|
| Telegram  | `curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" -H "Content-Type: application/json" -d '{"url":"{BASE}/channels/telegram/{TOKEN}"}'` | |
| WhatsApp  | Twilio Console → Phone Numbers → WhatsApp Sandbox → Webhook | `{BASE}/channels/whatsapp/webhook` |
| SMS       | Twilio Console → Phone Numbers → Your Number → Messaging Webhook | `{BASE}/channels/sms/webhook` |
| Email     | Resend Dashboard → Domains → tmos13.ai → Inbound | `{BASE}/channels/email/inbound` |
| Discord   | Discord Developer Portal → App → General Info → Interactions Endpoint URL | `{BASE}/channels/discord/webhook` |
| Slack     | api.slack.com → Your App → Event Subscriptions → Request URL | `{BASE}/channels/slack/webhook` |
| Messenger | developers.facebook.com → App → Webhooks → Callback URL | `{BASE}/channels/messenger/webhook` |
| Instagram | developers.facebook.com → App → Webhooks → Instagram → Callback URL | `{BASE}/channels/instagram/webhook` |
| Web       | Nothing to register — connect directly | `wss://{BASE}/channels/web/{any_token}` |

---

## Per-Channel Setup

### Telegram

1. Message @BotFather on Telegram, send `/newbot`
2. Copy the bot token
3. Set `TELEGRAM_BOT_TOKEN` in Railway
4. Register webhook: `curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" -H "Content-Type: application/json" -d '{"url":"https://13tmos-production.up.railway.app/channels/telegram/{TOKEN}"}'`
5. Verify: `curl "https://api.telegram.org/bot{TOKEN}/getWebhookInfo"`

### WhatsApp

1. Sign up at twilio.com, get Account SID and Auth Token
2. Activate WhatsApp Sandbox (or buy a number with WhatsApp enabled)
3. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` in Railway
4. Set webhook URL in Twilio Console: `https://13tmos-production.up.railway.app/channels/whatsapp/webhook`
5. Recipients must join sandbox first: send "join {sandbox-code}" to the WhatsApp number

### Email

1. Ensure `RESEND_API_KEY` is set in Railway (already present for outbound)
2. Add MX record at your domain registrar for tmos13.ai: `MX 10 inbound.resend.com`
3. In Resend Dashboard → Domains → tmos13.ai → Inbound, set webhook URL: `https://13tmos-production.up.railway.app/channels/email/inbound`
4. Wait for DNS propagation (usually minutes, up to 48h)
5. Handle routing: `duck@tmos13.ai` → enlightened_duck, `intake@tmos13.ai` → legal_intake, `hello@tmos13.ai` → guest

### SMS

1. In Twilio Console, buy a phone number (or use existing)
2. Set the number's Messaging Webhook to: `https://13tmos-production.up.railway.app/channels/sms/webhook`
3. `TWILIO_AUTH_TOKEN` is shared with WhatsApp — no new credentials needed

### Discord

1. Go to discord.com/developers → New Application
2. Create Bot, copy token. Enable Message Content Intent + Server Members Intent
3. Set Interactions Endpoint URL: `https://13tmos-production.up.railway.app/channels/discord/webhook`
4. Set `DISCORD_BOT_TOKEN` and `DISCORD_PUBLIC_KEY` in Railway
5. Generate invite link with `bot` + `applications.commands` scopes, invite to server

### Slack

1. Go to api.slack.com → Create New App → From Scratch
2. Event Subscriptions → Enable → Request URL: `https://13tmos-production.up.railway.app/channels/slack/webhook`
3. Subscribe to: `message.im` (DMs) and `message.channels` (channels)
4. OAuth & Permissions → Bot Token Scopes: `chat:write`, `im:history`, `channels:history`
5. Install to workspace, copy Bot Token
6. Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in Railway

### Messenger

1. Go to developers.facebook.com → Create App (Business type)
2. Add Messenger product
3. Generate Page Access Token
4. Set webhook callback URL: `https://13tmos-production.up.railway.app/channels/messenger/webhook`
5. Set verify token to: `tmos13duck` (must match `META_VERIFY_TOKEN`)
6. Subscribe to `messages` field
7. Set `META_PAGE_TOKEN` and `META_VERIFY_TOKEN` in Railway

### Instagram

1. Uses the same Meta App as Messenger
2. In the same app, add Instagram product
3. Set webhook callback URL: `https://13tmos-production.up.railway.app/channels/instagram/webhook`
4. Same verify token: `tmos13duck`
5. Subscribe to `messages` field
6. `META_PAGE_TOKEN` is shared — no additional credentials

### Web

No setup required. Connect directly:

```javascript
const ws = new WebSocket("wss://13tmos-production.up.railway.app/channels/web/my-session-123");

// Send handshake
ws.onopen = () => {
  ws.send(JSON.stringify({
    pack_id: "enlightened_duck",
    name: "Sofia"
  }));
};

// Receive messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "message") console.log(data.content);
  if (data.type === "typing") console.log("...");
};

// Send message
ws.send(JSON.stringify({ content: "Hello duck" }));
```

---

## DNS Records (Email Only)

```
MX  10  inbound.resend.com    (at tmos13.ai domain registrar)
```

---

## Session Seeding

Pre-load a session before the recipient messages:

**Telegram:**
```bash
curl -X POST https://13tmos-production.up.railway.app/channels/seed \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "telegram",
    "sender_id": "123456789",
    "pack_id": "enlightened_duck",
    "name": "Sofia",
    "context": "met at the gallery on Spring St"
  }'
```

**Email (duck reaches out first):**
```bash
curl -X POST https://13tmos-production.up.railway.app/channels/seed \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "sender_id": "sofia@gmail.com",
    "pack_id": "enlightened_duck",
    "name": "Sofia",
    "context": "met at the gallery on Spring St",
    "opening_email": true,
    "opening_subject": "Something strange is waiting for you"
  }'
```

---

## Status Endpoints

Every channel has a status endpoint:

```
GET /channels/telegram/status
GET /channels/whatsapp/status
GET /channels/email/status
GET /channels/sms/status
GET /channels/discord/status
GET /channels/slack/status
GET /channels/messenger/status
GET /channels/instagram/status
GET /channels/web/status
GET /channels                     # Full channel map
GET /channels/sessions            # All active sessions across channels
```
