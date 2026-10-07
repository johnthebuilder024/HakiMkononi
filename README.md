# HakiMkononi — Kenyan Legal AI

> *"Ujue haki yako"* — Know your rights.

AI-powered legal information for every Kenyan. Type your situation in Swahili or English (or a mix), get real Kenyan law with a citation, a plain-language explanation, your rights, and a draft letter — for free.

---

## What's Built

### ✅ Core AI Engine
- Django project with `cases` app
- `Law` model — 4,231 sections across 31+ Kenyan Acts, all with Gemini embeddings
- RAG search with query expansion for Swahili/Sheng, topic-aware boosting, tenant/landlord fix
- Groq AI (free tier) for fast answers
- 4-box answer: Law citation, Plain explanation, Your rights, Demand letter
- Conversation memory — multi-turn history, correction detection, follow-up threading
- Section parser handles both `## headers` and `**bold**` AI response formats

### ✅ Web Interface (chat.html)
- Full AI chat interface — ChatGPT-style layout
- Left sidebar with conversation history (localStorage, 20 conversations)
- New Chat button in navbar
- Bot avatar on every message
- County selector above input
- Editable demand letter with clickable placeholder chips
- PDF download (letter + full answer)
- Voice input via browser mic → Groq Whisper transcription
- Greeting/thanks/serious-case detection (no wasted AI calls)
- 5-minute timeout with 30s reassurance message
- 2-language support: Kiswahili and English
- Mobile responsive

### ✅ Telegram Bot
- Full conversational bot with language picker
- Voice messages — Groq Whisper transcription
- Conversation memory — multi-turn history, correction detection
- Letter personalisation flow — name → phone → fills letter
- Name validation with distress/sentence detection
- Typing indicator + bilingual reassurance after 8s
- Persistent keyboard with voice button
- Greeting/thank-you/serious-case detection
- /start, /language, /help, /stop, /clear, /skip commands
- Runs as background thread inside gunicorn (no separate server)

### ✅ Other Channels
- **Meta WhatsApp** — webhook live, number approval pending
- **Twilio WhatsApp** — webhook built, blocked by trial restrictions
- **Africa's Talking SMS** — webhook built, needs AT account setup

### ✅ Lawyer System (KYC)
- Full `Lawyer` model with 6-state KYC: pending → level1_pass → docs_submitted → verified → rejected → suspended
- LSK number validation (format: P.XXX/XXXX/YYYY)
- Document uploads: practicing cert, national ID, selfie, KRA PIN, optional video
- Lawyer registration at `/lawyers/register/`
- Document upload at `/lawyers/documents/<id>/`
- KYC status check at `/lawyers/status/<id>/` and self-service lookup by email at `/lawyers/check-status/`
- Lawyer matching — county-first, then specialty, shows to users after each answer, with inline county picker on the answer card
- `Lead` model tracks user→lawyer connections
- WhatsApp + Telegram contact links per lawyer, plus a link to their public profile
- Profile photo via direct image URL (`profile_photo_url`) — shown on the public profile, the dashboard, and the lawyer card on the answer

### ✅ Lawyer Landing Page (`/lawyers/`)
- Explains how the platform works for lawyers, KYC requirements, and pricing tiers
- "Join as a Lawyer" CTA → registration
- "Already applied? Check your application status" → `/lawyers/check-status/`

### ✅ Lawyer Admin Review Flow
- Admin gets notified by email when a lawyer submits documents (`_notify_admin_new_submission`)
- Admin approves/rejects in Django admin (`verify_lawyers` / `reject_lawyers` actions)
- Approval sends a password-setup email so the lawyer can access their dashboard
- Rejection sends an email with the rejection reason (or a generic message if none was given)

### ✅ Lawyer Public Profile (`/lawyers/<id>/`)
- Shareable page: name, firm, county, specialties, years of experience, bio, photo
- WhatsApp + Telegram contact buttons

### ✅ Lawyer Dashboard (`/lawyers/dashboard/`)
- Login with email + password (`/lawyers/login/`), password set via emailed link (`/lawyers/set-password/`)
- View leads (users who connected with them)
- Edit profile: firm, bio, specialties, counties, photo URL

### ✅ Admin Dashboard (`/dashboard/`)
- Queries per day/week/month
- Satisfaction rate (👍/👎)
- 👎 answers for review with correction tool
- Top counties asking questions
- Most cited laws
- Bot user breakdown (Telegram, WhatsApp, Meta, SMS)

### ✅ Quality & Accuracy
- Automated test suite: `python test_quality.py` — 10 cases, 36 checks
- Slang keyword DB — admin-managed Swahili/Sheng mappings
- Context-aware letter deadline (immediately for arrest, 14 days for employment)
- Lowercase `[date]` placeholder fix

---

## Laws Loaded (4,231 Sections)

Constitution of Kenya 2010, Employment Act 2007, Criminal Procedure Code (Cap 75),
Children Act 2022, Land Act 2012, Law of Succession Act, Traffic Act (Cap 403),
Marriage Act 2014, Consumer Protection Act 2012, Land Registration Act 2012,
Data Protection Act 2019, Data Protection Regulations (3 sets),
Sexual Offences Act 2006, Community Land Act 2016,
Protection Against Domestic Violence Act, Rent Restriction Act,
Land Control Act, Matrimonial Property Act 2013,
Fair Administrative Action Act 2015, Landlord & Tenant Acts (3),
Distress for Rent Act, Widows and Children's Pensions Act, Marriage Rules (5 sets)

---

## What's Next — Lawyer Side (Current Focus)

### 🔜 Lawyer Subscription Billing (M-Pesa)
- Safaricom Daraja STK Push — lawyer pays monthly subscription
- Subscription tiers: Basic / Pro / Premium
- After payment confirmed → activate lawyer profile visibility to users
- Currently verified lawyers show for free — billing not yet implemented

### 🔜 Lead Analytics on Dashboard
- How many users contacted them this month
- Which questions triggered their profile
- Currently the dashboard shows the lead list but not aggregated stats

---

## Future Features (Parked — Build After Lawyer Side Is Done)

### 💡 Premium Self-Representation Pack (KES 99/case)
For Kenyans who want to represent themselves in court — Employment & Labour Court,
Magistrate Court, Rent Tribunal, Business Premises Tribunal.

**What it gives:**
- Which court/tribunal to go to and how to file
- Statement of Claim / Memorandum of Appearance templates (pre-filled)
- Evidence checklist specific to their case
- Step-by-step timeline: what to do on Day 1, Day 7, Day 14 before hearing
- Counter-argument anticipator: "the other side will likely argue X, respond with Y"
- Unlimited follow-up questions on the same case
- Full case file downloadable as PDF

**How it works technically:**
- M-Pesa Daraja STK Push — user pays KES 99 per case or KES 299/month
- Payment confirmation → unlock premium section (no account needed, phone = identity)
- Extended system prompt in `ai_engine.py` for court documents
- New answer boxes: Court Document, Evidence Checklist, Procedure Timeline
- Works on both website and Telegram bot
- `WhatsAppUser` model gets `premium_expires_at` + `premium_phone` fields
- Wanjiku free tier stays exactly as is — premium is a separate door, not a gate

### 💡 User Accounts (Required for Premium)
- Lightweight: phone number + OTP (no email/password needed)
- Unlocks: conversation history across devices, premium access, saved letters
- M-Pesa number IS the identity — no separate signup needed

### 💡 USSD — Feature Phones (*384*88#)
- Reaches Kenyans with NO internet, NO smartphone
- Africa's Talking USSD sandbox (100% free)
- Simplified 3-step flow: choose topic → describe → get summary + demand letter via SMS
- Works on any phone with a GSM signal

### 💡 Auto-Learning from Court Judgments
- Nightly scraper pulls new Kenya Law judgments from kenyalaw.org
- Extracts cited sections → adds to law DB
- Learning loop: 👎 answers reviewed weekly, system prompt refined
- Law is constantly being interpreted — judgments are the real teacher

### 💡 Uganda & Tanzania Expansion
- Uganda: ULII (Uganda Legal Information Institute)
- Tanzania: TanzLII
- Same RAG architecture, different law DB
- Switch prompts to reference correct jurisdiction

---

## Running the App

```bash
# Start the web server (bot starts automatically as background thread)
python manage.py runserver --noreload

# Run quality tests against live site
python test_quality.py

# Run quality tests against local server
TEST_BASE_URL=http://localhost:8000 python test_quality.py
```

---

## API Endpoints

| Method | URL | Description |
|---|---|---|
| POST | `/api/submit/` | Start AI job (async) |
| GET | `/api/status/<id>/` | Poll for answer |
| POST | `/api/transcribe/` | Voice → text (Groq Whisper) |
| GET | `/api/letter-pdf/<id>/` | Download letter as PDF |
| GET | `/api/answer-pdf/<id>/` | Download full answer as PDF |
| POST | `/api/feedback/` | Save 👍/👎 feedback |
| GET | `/api/health/` | Check server + law data status |
| POST | `/api/whatsapp/` | Twilio WhatsApp webhook |
| POST | `/api/meta-whatsapp/` | Meta WhatsApp webhook |
| POST | `/api/sms/` | Africa's Talking SMS webhook |
| GET | `/dashboard/` | Admin dashboard (staff only) |
| GET | `/lawyers/` | Lawyer landing page |
| GET | `/lawyers/register/` | Lawyer registration form |
| GET | `/lawyers/documents/<id>/` | Document upload |
| GET | `/lawyers/status/<id>/` | KYC status check (by registration id) |
| GET/POST | `/lawyers/check-status/` | KYC status check (by email, no login) |
| POST | `/lawyers/connect/` | User → lawyer connection (creates Lead) |
| GET | `/lawyers/for-query/<id>/` | Matched lawyers for a query (supports `?county=`) |
| GET | `/lawyers/<id>/` | Public lawyer profile |
| GET/POST | `/lawyers/login/` | Lawyer dashboard login |
| GET | `/lawyers/logout/` | Lawyer logout |
| GET/POST | `/lawyers/set-password/` | Set password from emailed setup link |
| GET/POST | `/lawyers/dashboard/` | Lawyer dashboard (leads + profile editing) |

---

## Environment Variables (`.env`)

```
GROQ_API_KEY=...              # Free at console.groq.com
GEMINI_API_KEY=...            # For embeddings — free at ai.google.dev
TELEGRAM_BOT_TOKEN=...        # From @BotFather on Telegram
META_WHATSAPP_TOKEN=...       # From Meta developer console
META_PHONE_NUMBER_ID=...      # From Meta developer console
META_VERIFY_TOKEN=hakimkononi2026
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
AT_USERNAME=sandbox           # Africa's Talking
AT_API_KEY=...
SECRET_KEY=...                # Django secret key
DATABASE_URL=...              # Supabase PostgreSQL
```

---

## What We Are NOT Building
- Court pleadings or document submission (premium self-rep pack handles guidance only)
- Advice on murder, defilement, terrorism (NLAS referral only)
- Percentage of case outcomes (LSK rules)
- Fake M-Pesa statements, court orders, or LSK certificates
- Representing anyone in court
