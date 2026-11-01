# HakiMkononi — Anti-Trafficking Reporting System
## Demo Handout for HAART Kenya & DCI Anti-HT Unit

---

### What Is This?

HakiMkononi has built a **digital reporting platform** for human trafficking
in Kenya. It is the first platform of its kind in the country with:

- Anonymous reporting in **Swahili, English and Sheng**
- **AI-powered analysis** — converts raw survivor stories into structured
  formal reports suitable for DCI submission
- **Alias cross-referencing** — automatically flags when the same suspect
  name appears in multiple reports from different counties
- **Three-tier partner access** — Police/DCI, NGOs, Researchers each see
  appropriate data

---

### The Problem We Are Solving

Right now, if a survivor or witness wants to report trafficking:
- They must go to a police station in person
- Give a formal statement in formal language they may not know
- Hope the officer takes it seriously
- There is **no digital system** connecting reports from different areas

A trafficker called "Uncle James" can be reported in Nairobi, Kisumu and
Mombasa by different people — and no one connects the dots.

**HakiMkononi connects the dots automatically.**

---

### How It Works — In 3 Steps

**Step 1 — Anyone reports (anonymous, any language)**

A victim, witness, hotel worker, boda boda driver — anyone — goes to:
`hakimkononi.onrender.com/report-trafficking/report/`

They type their story in plain language. No login. No name needed.

**Step 2 — AI structures the report**

Within 30 seconds, Groq AI reads the story and:
- Identifies trafficking type (labour, sexual, domestic, child)
- Extracts all names, nicknames, phone numbers, Facebook names
- Generates a formal English report ready for DCI
- Flags urgency if victim is currently held

**Step 3 — Partners see it on their dashboard**

DCI logs in with their access key and sees:
- All reports filtered by county, type, urgency
- ⚠️ ALIAS MATCH alerts when the same name appears twice
- Full formal report downloadable as a file
- Status tracking (new → under review → actioned)

---

### The Alias Matching — Why It Matters

**Example from demo data:**

Report TIP-2026-0001 (Nairobi): "A man called Uncle James contacted me
on Facebook and promised a job in Dubai..."

Report TIP-2026-0002 (Kisumu): "...my cousin was recruited by a man
also known as Uncle James, his number is 0701234567..."

**The system automatically links these two reports** and sends an alert:
*"⚠️ Alias 'Uncle James' appears in 2 reports from Nairobi and Kisumu"*

Without technology, these would be two unconnected files in two different
police stations. With HakiMkononi, they are immediately linked.

---

### Access Tiers

| Tier | Who | What they see |
|---|---|---|
| 🚔 Police / DCI | DCI Anti-HT Unit | Everything — full story, contact, aliases, PDF |
| 🤝 NGO | HAART Kenya, IOM | Full reports, anonymous contact hidden |
| 📊 Researcher | IOM Research, academics | Aggregated stats only — no personal data |

---

### Demo Instructions

**To try the system right now:**

1. Go to: `hakimkononi.onrender.com/report-trafficking/report/`
2. Submit a test report (any story, any language)
3. Note your reference number
4. Login to the dashboard: `hakimkononi.onrender.com/report-trafficking/dashboard/login/`
5. Use the access key we provide

**Demo access keys** (generated fresh for this meeting):

| Role | Access Key |
|---|---|
| DCI (Police tier) | *(printed separately — ask presenter)* |
| HAART (NGO tier) | *(printed separately — ask presenter)* |
| Researcher | *(printed separately — ask presenter)* |

---

### What We Need From You

**From HAART Kenya:**
- Agree to monitor the NGO dashboard and respond within 24 hours to urgent reports
- Sign a simple MOU (one page) confirming the data sharing arrangement
- Help introduce us to the CTiP Secretariat and DCI

**From DCI Anti-HT Unit:**
- Designate one officer to receive the dashboard access key and alert emails
- Provide an email address for urgent report alerts
- Sign the MOU

**That's it.** We do all the technical work. You just check the dashboard.

---

### Data Protection & Security

- Reporter contact details are **encrypted** using AES-128 (Fernet)
- The system is **registered under the Data Protection Act 2019**
- Reports are only shared with MOU partners — no third parties
- All pages have no-index meta tags (don't appear in Google)
- Panic button on the report form closes the page instantly with no history

---

### Contact

**HakiMkononi**
hakimkononi.onrender.com
info@hakimkononi.co.ke

*Sheria Yako, Mkononi Mwako 🇰🇪*

---

*This handout is confidential — for HAART Kenya and DCI Anti-HT Unit only.*
*Demo data only — no real reports are in the system at this stage.*
