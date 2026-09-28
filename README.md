# HakiMkononi — Kenyan Legal AI

> *"Ujue haki yako"* — Know your rights.

AI-powered legal information for every Kenyan. Type your situation in Swahili or English (or a mix), get real Kenyan law with a citation, a plain-language explanation, your rights, and a draft letter — for free.

---

## What's Built So Far

### ✅ Core AI Engine (Chunk 1 — Complete)
- Django project with `cases` app
- `Law` model — 2,602 sections across 31 Kenyan Acts, all with embeddings
- RAG search using `all-MiniLM-L6-v2` with query expansion for Swahili
- Groq AI (free tier) for fast answers (~3-5s)
- 4-box answer: Law citation, Plain explanation, Your rights, Demand letter
- Admin panel with law management and feedback tools

### ✅ Web Interface (Chunk 2 — Complete)
- Homepage with question form, county selector, example chips
- 4-box answer page with markdown rendering
- Editable demand letter with clickable placeholder chips
- PDF download (letter + full answer via reportlab)
- Persist answers on page refresh (localStorage + server fallback)
- Print CSS for clean printing
- 2-language support: Kiswahili and English
- Mobile responsive

### ✅ Channels (Chunk 3 — Partially Complete)
- **Telegram bot** — fully working, polling, no server needed
- **Meta WhatsApp** — webhook live, number approval pending
- **Twilio WhatsApp** — webhook built, blocked by trial restrictions
- **Africa's Talking SMS** — webhook built, needs AT account setup
- ❌ Voice input — not yet built
- ❌ Court audio upload — not yet built
- ❌ Letter PDF via M-Pesa (99 KES) — not yet built

### ✅ Quality & Slang (Extra — Complete)
- Slang keyword DB — admin-managed, 106+ Swahili/Sheng keywords
- Query expansion for Swahili → improves RAG accuracy
- 14/15 quality test pass rate across all topics and languages
- RAG topic-aware boosting + off-topic post-filter

---

## Laws Loaded (31 Acts, 2,602 Sections)

| Act | Sections |
|---|---|
| Constitution of Kenya 2010 | 41 |
| Employment Act 2007 | 104 |
| Criminal Procedure Code (Cap 75) | 357 |
| Children Act 2022 | 307 |
| Land Act 2012 | 190 |
| Law of Succession Act | 254 |
| Traffic Act (Cap 403) | 166 |
| Marriage Act 2014 | 112 |
| Consumer Protection Act 2012 | 105 |
| Land Registration Act 2012 | 123 |
| Data Protection Act 2019 | 84 |
| Data Protection (General) Regulations | 84 + 84 |
| Data Protection (Civil Registration) Regs | 62 |
| Data Protection (Registration) Regs | 19 |
| Sexual Offences Act 2006 | 54 |
| Community Land Act 2016 | 63 |
| Protection Against Domestic Violence Act | 38 |
| Rent Restriction Act | 38 |
| Land Control Act | 39 |
| Matrimonial Property Act 2013 | 24 |
| Fair Administrative Action Act 2015 | 18 |
| Landlord & Tenant (Shops, Hotels) Act | 17 |
| Landlord and Tenant Act | 17 |
| Distress for Rent Act | 29 |
| Widows and Children's Pensions Act | 35 |
| Marriage Rules (5 sets) | 138 |

---

## What's Next

### 🔜 Chunk 4 — Admin Dashboard (1-2 hours)
Track what Wanjiku is asking. Charts showing:
- Questions per day/week
- Most cited laws
- 👎 feedback answers that need fixing
- Top counties asking questions

### 🔜 Chunk 5 — USSD (3-4 hours)
Reaches Kenyans with NO internet, NO smartphone — just dial `*384*88#`.
Africa's Talking USSD sandbox is 100% free.
Works on any phone with a GSM signal.

### 🔜 Chunk 6 — Deploy to Server (1-2 hours)
Currently runs only when your laptop is on.
Deploy to Railway or Render (free tier) so it runs 24/7.
Switch from `runserver` to `gunicorn`.

### 🔜 Chunk 7 — Lawyer Side + KYC (1-2 weeks)
Verified lawyers can list themselves.
Users can connect to them after every answer.
M-Pesa subscription billing: 2,500 / 5,000 / 15,000 KES/month.

### 🔜 Chunk 8 — Voice Input
Wanjiku speaks instead of types.
OpenAI Whisper transcribes Swahili + English.
Same RAG pipeline runs on the transcript.

### 🔜 Chunk 9 — Growth & Learning
Auto-scraper pulls new Kenya Law judgments nightly.
Learning loop — 👎 answers reviewed weekly, AI improved.
Uganda and Tanzania expansion (ULII + TanzLII).

---

## Running the App

```bash
# Start the web server
python manage.py runserver --noreload

# Start the Telegram bot (separate terminal)
python telegram_bot.py

# Start ngrok (for WhatsApp/SMS webhooks)
.\ngrok.exe http 8000
```

---

## API Endpoints

| Method | URL | Description |
|---|---|---|
| POST | `/api/submit/` | Start AI job (async) |
| GET | `/api/status/<id>/` | Poll for answer |
| GET | `/api/letter-pdf/<id>/` | Download letter as PDF |
| GET | `/api/answer-pdf/<id>/` | Download full answer as PDF |
| POST | `/api/whatsapp/` | Twilio WhatsApp webhook |
| POST | `/api/meta-whatsapp/` | Meta WhatsApp webhook |
| POST | `/api/sms/` | Africa's Talking SMS webhook |
| GET | `/api/health/` | Check laws loaded |
| GET | `/admin/` | Admin panel |

---

## Environment Variables (`.env`)

```
GROQ_API_KEY=...              # Free at console.groq.com
TELEGRAM_BOT_TOKEN=...        # From @BotFather on Telegram
META_WHATSAPP_TOKEN=...       # From Meta developer console
META_PHONE_NUMBER_ID=...      # From Meta developer console
META_VERIFY_TOKEN=hakimkononi2026
TWILIO_ACCOUNT_SID=...        # From console.twilio.com
TWILIO_AUTH_TOKEN=...
AT_USERNAME=sandbox           # Africa's Talking
AT_API_KEY=...
```

---

## What We Are NOT Building
- Court pleadings or document submission
- Advice on murder, defilement, terrorism (info + lawyer referral only)
- Percentage of case outcomes (LSK rules)
- Fake M-Pesa statements, court orders, or LSK certificates
- Representing anyone in court
