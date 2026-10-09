# HakiMkononi — Full Build Plan

> **Core Promise:** Type your story in Swahili or Sheng, get real Kenyan law with a real citation, a simple explanation, your rights, and a letter you can use — for free.
>
> **Who we serve first:** Wanjiku — the common mwananchi in Kitale and everywhere else in Kenya who cannot afford a lawyer and doesn't know their rights.
>
> **What we are NOT:** We are not a law firm. We do not replace a lawyer. We are a legal information tool — like a very knowledgeable friend who has read every Kenyan law.

---

## The Full Feature Map (Everything We Will Build)

This is the complete picture. We will NOT build it all at once. Each chunk is listed below in the order we will build it.

### Side A — Wanjiku (Citizens)
- Ask a question in Swahili, English, or Sheng
- 4-box answer: Law (with real citation), Simple Swahili explanation, Rights/Loopholes, Draft letter to copy
- Voice input — speak instead of type (Whisper AI)
- Upload court audio — get Swahili summary of what the judge said
- Feedback: "Ilisaidia? Ndio / Hapana" (this trains the AI over time)
- Fee guide: "Normal price for this type of case is X–Y KES (LSK Remuneration Order)"
- Download demand letter or affidavit as PDF (99 KES)
- View your past questions
- Consent banner + disclaimer on every answer
- Second opinion on lawyer fees

### Side B — Lawyers (Paid Subscription — Built Later)
- Verified profile with LSK 2026 badge
- Leads dashboard by county and case type
- Direct WhatsApp connect to client (after user consent)
- One public answer per week to build reputation
- M-Pesa subscription billing: 2,500 / 5,000 / 15,000 KES per month
- Analytics: cases by county, case type trends

### Side C — Admin (You)
- Laws manager: upload PDF, split by section, add Swahili meaning
- Monitor all "Hapana" answers and fix them
- KYC queue: verify LSK number, practicing certificate, ID
- Blacklist for fake/rejected lawyers
- County-level stats and usage analytics

---

## The AI Brain (How It Will Work)

We use **RAG — Retrieval-Augmented Generation**. This is what separates a trustworthy legal AI from a hallucinating chatbot.

```
User story → Convert to embedding → Search law database 
→ Find top 3–5 real sections → Feed only those to Groq AI 
→ Answer with real citations from kenyalaw.org
```

**Three modes inside every answer:**
1. **Law Brain** — finds the real section (e.g. Employment Act Section 35)
2. **Simple Brain** — explains it like Class 8 Swahili
3. **Loophole Brain** — what the employer/police/landlord was supposed to do and didn't

**Rules the AI must always follow:**
- Never invent a section — only use what's in the database
- Every claim must cite: Act Name + Section + kenyalaw.org link
- Temperature: 0.1 (low creativity = fewer hallucinations)
- Every answer ends with the legal disclaimer in both English and Swahili
- If law is not found, say so — don't guess

---

## Legal Data We Need (All Free from kenyalaw.org)

| Document | Priority | When to Add |
|---|---|---|
| Constitution of Kenya 2010 — Chapter 4 (Articles 19–59) | Highest | Chunk 1 |
| Employment Act 2007 | Highest | Chunk 1 |
| Criminal Procedure Code — arrest and bail sections | High | Chunk 1 |
| Rent Restriction Act | High | Chunk 2 |
| Children Act 2022 — child support sections | Medium | Chunk 2 |
| Consumer Protection Act — debt harassment sections | Medium | Chunk 2 |
| Penal Code Cap 63 — fraud sections | Medium | Chunk 3 |
| Computer Misuse and Cybercrimes Act 2018 | Medium | Chunk 3 |
| Land Act + Law of Succession Act | Lower | Chunk 4 |
| Daily judgments (auto-scraped from Kenya Law) | Ongoing | Chunk 5 |

**How to split each Act:** One section = one database row. Each row has:
- Title (e.g. Employment Act 2007)
- Section (e.g. Section 35)
- Full text of that section
- Simple Swahili meaning (written by you or a young advocate)
- Related articles (e.g. "Article 47, Section 40")
- Source URL (kenyalaw.org link)

---

## Case Types — Build in This Order

### Tier 1 — Start Here (Weeks 1–4)
These are the most common, the law is clear, and they affect the most people in Kitale.

1. **Employment** — fired without notice, unpaid salary, no NSSF/NHIF, unfair termination
2. **Police and bond** — 24-hour rule, OB number, bail, rights on arrest, Article 49
3. **Landlord and tenant** — eviction without notice, deposit not returned, rent increase
4. **Child support** — father not paying, how to file at Children's Court
5. **Debt harassment** — Tala, Mshwari, CRB blacklisting, illegal debt collection

### Tier 2 — Month 2–3
6. **Financial fraud (victim only)** — M-Pesa fraud, wash wash, fake jobs — reporting steps and evidence checklist
7. **Land and succession** — shamba ya babu, inheritance without a will
8. **GBV and domestic violence** — how to get P3 form, protection order, referral to FIDA
9. **Consumer and business disputes** — fake goods, online scams, breach of contract
10. **Cyber and defamation** — Facebook posts, WhatsApp group admin liability

### Tier 3 — Information + Referral Only (Never AI strategy)
- Murder, robbery with violence, defilement, terrorism — give rights only, immediately refer to LSK/Kituo Cha Sheria
- KRA and tax disputes
- Constitutional petitions and election cases

---

## Tech Stack

| Layer | Tool | Reason |
|---|---|---|
| Backend | Django + Python | Chosen by the builder |
| LLM | Groq (openai/gpt-oss-20b primary, 70b fallback) | Free tier, fast, handles law well |
| Embeddings | Gemini (text-embedding-004) | Free at ai.google.dev, high quality |
| Vector search | Django DB (PostgreSQL / Supabase) | No Pinecone cost |
| Speech-to-text | Groq Whisper (whisper-large-v3) | Fast, understands Swahili and English |
| Payments | Safaricom Daraja (M-Pesa STK Push) | Kenyan, reliable |
| WhatsApp | Twilio sandbox (Meta approval pending) | Built, pending approval |
| PDF parsing | pdfplumber | Split Acts by section |
| Deployment | Render (free tier) | Auto-deploys on git push |
| Database | Supabase PostgreSQL | Free, persistent |

---

## Money Model

### Citizens
- **Free:** Unlimited questions — no rate limit, no account needed
- **Free:** Self-representation pack (court document, evidence checklist, timeline)
- **Free:** Connect to a verified lawyer

### Lawyers (subscription — M-Pesa, parked for now)
- **2,500 KES/month Basic** — profile + 5 leads + appears in county search
- **5,000 KES/month Pro** — top 3 ranking + 15 leads + WhatsApp button
- **15,000 KES/month Firm** — unlimited leads in 2 counties + analytics dashboard

### Future Revenue
- County government contracts to run legal aid chatbots
- NGO and FIDA partnership grants
- USSD version for feature phones (no internet needed)

---

## KYC for Lawyers (Chunk 4)

### Level 1 — Automatic
- LSK number format check (real format: `P.105/1234/2020`)
- Cross-check name against LSK public advocates search
- ID photo + selfie holding ID

### Level 2 — Document Verification (Same Day)
- 2026 Practicing Certificate (current year, has LSK stamp, not expired)
- KRA PIN certificate (confirms firm name for billing)

### Level 3 — Strong Verification (Pro plan only)
- 2-minute WhatsApp video call — ask questions only a real lawyer knows
- Photo or video of physical office with signboard
- Signed declaration: no pending LSK disciplinary action

**Instant rejection triggers:** wrong LSK number format, name mismatch, expired certificate, personal M-Pesa number (no till or paybill), fails video call.

**Result:** "Verified LSK 2026" green badge on profile — the biggest trust signal on the platform.

---

## Legal Protection (What Keeps Us Safe)

1. Every answer ends with: *"Hii ni taarifa ya kisheria, si ushauri wa kisheria. Kwa kesi nzito, tafuta wakili. Source: [kenyalaw.org link]"*
2. Lawyers pay for listing (advertising), not a percentage of case outcome — LSK-compliant
3. All lawyer LSK numbers verified — we verify registration, not their work quality
4. Consent banner at start — per Kenya Data Protection Act 2019, stories stored anonymously
5. Never generate fake M-Pesa statements, fake court orders, or pleadings
6. Positioned as legal information, not legal practice
7. Fraud and serious criminal cases always add: *"TAFUTA WAKILI HARAKA — Hii kesi ni mzito"*

---

---

# BUILD CHUNKS — Start Here

We build in 5 chunks. Each chunk is shippable on its own. We do not move to the next chunk until the current one works.

---

## CHUNK 1 — AI Training + Core Engine (Start NOW)

**Goal:** The AI can answer 3 case types accurately with real citations. No frontend. No lawyer side. Just the brain.

**Why first:** Everything else — the website, the WhatsApp bot, the lawyers — depends on the AI being accurate. If it hallucates, people will get hurt. We train it right before we show it to anyone.

### What to build:
- [ ] Django project setup (`sheria_ai` project, `cases` app)
- [ ] `Law` model — title, section, content, simple_swahili, related_to, source_url, embedding
- [ ] `Query` model — story, answer, was_helpful, what_happened, correct_section
- [ ] PDF parser script — upload Act PDF, auto-split by section, save to Law table
- [ ] Load Constitution Chapter 4 (Articles 19–59) — ~60 rows
- [ ] Load Employment Act 2007 — ~40 key sections
- [ ] Load Criminal Procedure Code — arrest/bail sections ~20 rows
- [ ] SentenceTransformer embedding — convert each law section to vector on save
- [ ] RAG search function — given a user story, find top 5 matching law sections
- [ ] System prompt with strict rules (no invented sections, always cite, Swahili + English, disclaimer)
- [ ] `ask_sheria` API endpoint — accepts story, returns answer with citations
- [ ] Test with 10 real Kitale stories manually — confirm no hallucination
- [ ] Django Admin setup to view and edit law rows

### What we are NOT building in Chunk 1:
- No frontend
- No user accounts
- No lawyer side
- No payments
- No WhatsApp yet

### Done when:
You can hit `http://127.0.0.1:8000/api/ask/?q=Boss amenifukuza bila notice` and get back a real Employment Act section + Article 47 citation + Swahili explanation with a kenyalaw.org link. No fake sections.

---

## CHUNK 2 — Wanjiku Web Interface

**Goal:** A simple, clean webpage where Wanjiku can ask her question and read the 4-box answer. Still no accounts, no payments, no lawyers.

### What to build:
- [ ] Simple homepage — logo, tagline, big textarea: "Eleza kesi yako..."
- [ ] County selector (Kitale, Eldoret, Nairobi, etc.) — for localized context
- [ ] 4-box answer page:
  - Box 1: Sheria Inasema (Act + Section + kenyalaw.org link)
  - Box 2: Tafsiri Rahisi (English simple + Swahili rahisi)
  - Box 3: Haki Yako / Loophole (what must have been done)
  - Box 4: Andika Hivi (copy-paste draft letter)
- [ ] "Ilisaidia? Ndio / Hapana" feedback buttons
- [ ] Disclaimer block on every answer (Swahili + English)
- [ ] "Hatujapata sheria hii" graceful error when law not found
- [ ] Fee guide box — "Bei ya kawaida kwa kesi hii: X–Y KES (LSK Remuneration Order)"
- [ ] Add Rent Restriction Act + Children Act + Consumer Protection Act (Tier 1 complete)
- [ ] Admin dashboard — see all "Hapana" answers, fix wrong citations
- [ ] Mobile responsive — most users will be on phone

### Done when:
A mama mboga in Kitale can open the site on her phone, type her story in Swahili, and read a clear 4-box answer she understands. She clicks "Ndio — Ilinisaidia."

---

## CHUNK 3 — Voice + Court Audio + WhatsApp

**Goal:** Wanjiku doesn't need to type. She can speak her question. She can upload what the judge said and get a Swahili summary.

### What to build:
- [ ] Voice input on the Ask page — record button, send audio to Whisper, transcribe to text, run same RAG flow
- [ ] Court audio upload — user uploads short recording of their hearing
- [ ] Whisper transcription of court audio
- [ ] AI summarizes in Swahili: "Jaji alisema: 1. Lete barua ya kazi 2. Kesi inarudi tarehe 20..."
- [ ] `CaseAudio` model — user, audio file, transcription, summary, court station, date
- [ ] WhatsApp bot via Africa's Talking API
  - User sends: "Bwana aliniharass job akanifukuza bila notice"
  - Bot replies with the same 4-box answer in WhatsApp format
  - Bot also handles: "AUDIO" keyword to request upload link
- [ ] Letter PDF download — generate demand letter as PDF (99 KES via M-Pesa)
- [ ] Basic M-Pesa STK push for PDF download only (simple first payment flow)

### Done when:
A boda rider in Kitale can WhatsApp the bot, describe his case by voice, and get back a Swahili answer with a real Act citation. He can download the demand letter for 99 bob.

---

## CHUNK 4 — Lawyer Side + KYC

**Goal:** Verified lawyers in Kitale and Eldoret can list themselves. Users can connect to them. Lawyers pay monthly.

### What to build:
- [ ] `Lawyer` model — name, LSK number, ID photo, selfie, practicing cert, KRA PIN, county, specialty, plan, verified status
- [ ] Lawyer registration form — upload all KYC documents
- [ ] Admin KYC queue — review documents, run LSK number check, approve/reject
- [ ] Verified badge system — Green "LSK 2026 Verified", Yellow "Pending", Red "Rejected"
- [ ] Blacklist model — rejected LSK numbers, auto-block on re-registration
- [ ] `Lead` model — links Query to Lawyer, records consent, contact status
- [ ] "Unganisha na Wakili" button at bottom of every answer — shows 3 verified lawyers by county
- [ ] User consent flow before sharing their phone number with a lawyer
- [ ] Lawyer dashboard — leads list, case summaries, WhatsApp connect button
- [ ] Lawyer subscription billing — M-Pesa STK push, auto-deactivate if not paid
- [ ] Lawyer public answer feature — one answer per week, shown on their profile
- [ ] Fee guide from LSK Remuneration Order — shown to user to prevent overcharging

### Done when:
3 verified lawyers in Kitale/Eldoret are listed. A user asking about employment can click "Connect" and the lawyer receives the case summary on WhatsApp. Lawyer renews subscription monthly via M-Pesa.

---

## CHUNK 5 — Growth, Learning, and Scale

**Goal:** The AI gets smarter over time. More case types added. Auto-learning from new judgments.

### What to build:
- [ ] Add Tier 2 case types: fraud (victim side), land/succession, GBV, cyber/defamation
- [ ] Auto-scraper — runs nightly, pulls new Kenya Law judgments, adds to database
- [ ] Learning loop — "Hapana" answers reviewed weekly, AI search improved with corrections
- [ ] User accounts (optional login via phone number + OTP)
- [ ] Voice + language improvement — Sheng detection, dialect handling
- [ ] USSD version — for feature phones with no internet (future)
- [ ] Uganda and Tanzania expansion — ULII and TanzLII data (same architecture)
- [ ] County government chatbot integration (API)
- [ ] Testimonials system — voice notes from users who won their cases

---

## What We Are NOT Building (Boundaries We Keep)

- We do not write court pleadings or submit documents to court on behalf of users
- We do not give advice on murder, defilement, terrorism, or serious criminal strategy — information only + immediate lawyer referral
- We do not take a percentage of any case outcome (LSK rules)
- We do not generate fake M-Pesa statements, fake court orders, or fake LSK certificates
- We do not store anyone's story with their real name or phone number without consent
- We do not claim to be a lawyer, represent anyone in court, or use the word "advocate" to describe ourselves

---

## First 3 Steps This Week

1. **Download 3 documents** from kenyalaw.org: Constitution 2010, Employment Act 2007, Criminal Procedure Code — these are your first training data
2. **Set up Django project** — `django-admin startproject sheria_ai`, create `cases` app, install dependencies
3. **Start with 20 manual law rows** in the database — Constitution Articles 19, 22, 25, 40, 47, 49, 50 + Employment Act Sections 35, 40, 41, 44, 45 — these 15–20 rows will answer 60% of Tier 1 questions

We are in **Chunk 1**. The AI brain comes first. Everything else is built on top of it.
