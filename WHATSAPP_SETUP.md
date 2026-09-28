# HakiMkononi — WhatsApp Bot Setup Guide

This guide gets you from zero to a working WhatsApp bot on your phone
using the Twilio Sandbox (free, no business verification needed).

---

## What you will need

- A free Twilio account (no credit card)
- ngrok running on your laptop (already installed)
- Your phone with WhatsApp

---

## Step 1 — Create a free Twilio account

1. Go to **https://www.twilio.com/try-twilio**
2. Sign up with your email — no credit card needed
3. Verify your phone number when prompted
4. After signup you land on the Twilio Console dashboard

---

## Step 2 — Get your Twilio credentials

1. On the Twilio Console homepage look for **Account Info** (top of page)
2. Copy your:
   - **Account SID** — looks like `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **Auth Token** — click the eye icon to reveal it
3. Open your `.env` file and paste them:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=8ea06b51884398f13299dddb8889d471
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

> Leave `TWILIO_WHATSAPP_FROM` exactly as-is — that is Twilio's shared
> sandbox number, the same for every free account.

---

## Step 3 — Activate the WhatsApp Sandbox

1. In the Twilio Console go to:
   **Messaging → Try it out → Send a WhatsApp message**
2. You will see a sandbox number (usually **+1 415 523 8886**) and a
   join code like `join lucky-forest`
3. On your phone, open WhatsApp and send that exact message to
   **+1 415 523 8886**
   ```
   join lucky-forest
   ```
4. You will get a reply: *"You have joined the sandbox"*

Anyone who wants to test your bot must do this join step once.

---

## Step 4 — Start the Django server

Open a terminal in the HakiMkononi folder and run:

```powershell
python manage.py runserver --noreload
```

Leave it running. The server listens on `http://127.0.0.1:8000`

---

## Step 5 — Expose your laptop to the internet with ngrok

Open a **second** terminal in the HakiMkononi folder and run:

```powershell
python -m ngrok http 8000
```

ngrok will show output like:

```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8000
```

**Copy that `https://` URL** — you need it in the next step.

> The URL changes every time you restart ngrok (free plan).
> Just update the Twilio webhook URL (Step 6) each time.

---

## Step 6 — Point Twilio to your webhook

1. In the Twilio Console go to:
   **Messaging → Try it out → Send a WhatsApp message**
2. Scroll down to **Sandbox Settings**
3. In the field **"When a message comes in"** paste:
   ```
   https://abc123.ngrok-free.app/api/whatsapp/
   ```
   (replace `abc123` with your actual ngrok URL)
4. Make sure the method is set to **HTTP POST**
5. Click **Save**

---

## Step 7 — Test it on your phone

Send any message from your WhatsApp to **+1 415 523 8886**:

| You send | Bot replies |
|---|---|
| `hi` | Welcome message in Swahili |
| `My boss fired me without notice` | English legal answer |
| `Mwajiri wangu alinifukuza kazi` | Swahili legal answer |
| `Boss wangu alinifukuza job bila notice` | Sheng legal answer |

The bot sends an instant "⏳ Reading the law…" reply, then the full
answer arrives in about 20–30 seconds.

---

## How it works

```
Your WhatsApp
     │  sends message
     ▼
Twilio (+14155238886)
     │  HTTP POST to your ngrok URL
     ▼
ngrok tunnel
     │  forwards to your laptop
     ▼
Django /api/whatsapp/
     │  1. Detects language (sw/en/sheng)
     │  2. Returns instant TwiML ack ("⏳ Reading…")
     │  3. Fires background thread
     ▼
Background thread
     │  RAG: finds top 6 relevant law sections
     │  AI (Groq): generates answer in your language
     │  Twilio REST API: sends reply back to your WhatsApp
     ▼
Your WhatsApp receives the full legal answer
```

---

## Sharing with others (family / testers)

Anyone can use your bot during testing. They just need to:

1. Save **+1 415 523 8886** in their phone as "HakiMkononi Test"
2. Send the join code once (e.g. `join lucky-forest`)
3. Then ask any legal question in Swahili, English, or Sheng

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot not replying | Check ngrok is running and URL in Twilio matches |
| "Error sending" in Django logs | Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env |
| ngrok URL changed | Re-paste the new URL in Twilio Sandbox Settings |
| "You are not in the sandbox" | Send the join code again from your phone |
| Answer takes too long | Normal — AI takes 20-30s. ngrok free has 40s timeout — if it expires, upgrade ngrok or deploy to a real server |

---

## Going to production (when ready)

When you want real Kenyans to use the bot without the join-code step:

1. Apply for a **WhatsApp Business Account** at
   https://www.twilio.com/whatsapp/request-access
2. Deploy HakiMkononi to a real server (Railway, Render, or a VPS)
3. Update `ALLOWED_HOSTS` in `.env` with your domain
4. Point the Twilio webhook to `https://yourdomain.com/api/whatsapp/`

---

*Built for Wanjiku — every Kenyan deserves to know their rights 🇰🇪*
