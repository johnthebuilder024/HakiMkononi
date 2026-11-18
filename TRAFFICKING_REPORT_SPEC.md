# HakiMkononi — Anti-Trafficking Reporting System
## Full Build Specification (Chunk by Chunk)

> Build this after the main HakiMkononi platform is stable.
> Approach HAART Kenya with the working demo from Chunk 4.

---

## What We Are Building

A digital reporting system for human trafficking in Kenya that:

1. Lets anyone (victim, witness, boda boda driver, hotel worker) submit a report **anonymously** in Swahili, English or Sheng
2. Uses AI to read the raw story and produce a **structured formal report** suitable for DCI submission
3. Extracts every name, nickname, alias and phone number from the story and saves them to an **alias database**
4. **Flags when the same alias appears in multiple reports** — connecting dots that humans would miss
5. Gives different access levels to **Police/DCI, NGOs (HAART), and Researchers**
6. Sends **instant alerts** to DCI when an urgent report (victim currently held) comes in

---

## Chunk 1 — Database Models + Basic Admin

### What gets built
- 4 new Django models in `cases/models.py`
- Django admin registration with filters
- Database migration
- No frontend yet — just the data layer

### Models

#### 1. TraffickingReport
One row per submitted report.

```
id                  — auto
story_raw           — TextField — original story in any language
story_lang          — CharField(5) — 'sw' / 'en' / 'sheng' / 'unknown'
report_type         — CharField(20) — labour / sexual / domestic / child / unknown
recruitment_method  — CharField(30) — social_media / job_offer / romance /
                                       family_member / broker / unknown
indicators          — JSONField(list) — list of indicator codes (see below)
victim_profile      — CharField(20) — adult_female / adult_male /
                                       minor_female / minor_male / unknown
destination         — CharField(200) — "Dubai" or "Mombasa" or "Unknown"
county_of_origin    — CharField(100) — where it happened / where victim is from
is_urgent           — BooleanField — victim currently being held right now
formal_report_en    — TextField — AI-generated formal report in English
formal_report_sw    — TextField — AI-generated formal report in Swahili
reporter_contact    — TextField(encrypted) — phone/email (optional, may be blank)
is_anonymous        — BooleanField(default=True)
status              — CharField(15) — new / under_review / actioned / closed / false_report
status_note         — TextField — internal note from DCI/NGO on what was done
reviewed_by         — CharField(100) — which partner reviewed it
reviewed_at         — DateTimeField(null=True)
has_linked_reports  — BooleanField(default=False) — True if alias match found
ip_hash             — CharField(64) — SHA256 of submitter IP (rate limiting only, not identifiable)
created_at          — DateTimeField(auto_now_add=True)
```

**Indicator codes (save as JSON list):**
```
passport_confiscation
document_confiscation
debt_bondage
movement_restriction
unpaid_wages
threats_violence
physical_abuse
sexual_abuse
confinement
deceptive_job_offer
false_promises
recruited_for_domestic_work
transported_across_border
phone_confiscated
monitored_communications
underfed_or_starved
multiple_victims_together
```

---

#### 2. TraffickingSuspect
One row per name/alias/phone extracted from a report. Many suspects per report.

```
id                  — auto
report              — ForeignKey(TraffickingReport, related_name='suspects')
alias               — CharField(200) — the actual name: "Mkubwa", "Uncle James", "+254712345678"
alias_type          — CharField(20) — nickname / phone / facebook_name /
                                       real_name / vehicle_plate / organisation / unknown
alias_normalized    — CharField(200) — lowercase, stripped: "mkubwa" — used for matching
county_context      — CharField(100) — county where this person was operating
confidence          — CharField(10) — high / medium / low — AI confidence this is real
linked_to           — ManyToManyField('self', blank=True) — links to same alias in other reports
created_at          — DateTimeField(auto_now_add=True)
```

---

#### 3. TraffickingAccessKey
Controls who can log into the partner dashboard.

```
id                  — auto
organisation        — CharField(200) — "HAART Kenya" / "DCI Unit" / "IOM Kenya" / "Researcher X"
tier                — CharField(15) — police / ngo / researcher
access_key          — CharField(128) — hashed key (never stored plain)
county_filter       — CharField(100, blank=True) — if set, only shows reports from this county
can_update_status   — BooleanField — can mark reports as actioned/closed
active              — BooleanField(default=True)
last_used_at        — DateTimeField(null=True)
created_at          — DateTimeField(auto_now_add=True)
```

---

#### 4. TraffickingAliasAlert
One row per alias match detected. Tracks the alert so we don't send it twice.

```
id                  — auto
alias               — CharField(200) — the alias that matched
report_new          — ForeignKey(TraffickingReport) — the new report that triggered it
report_previous     — ForeignKey(TraffickingReport) — the earlier report it matched
alert_sent          — BooleanField(default=False) — email/SMS sent to DCI
created_at          — DateTimeField(auto_now_add=True)
```

---

### Django Admin setup
- `TraffickingReportAdmin` — list display: county, type, urgent flag, status, created_at. Filter by: type, county, is_urgent, status. Search: story_raw, suspects__alias
- `TraffickingSuspectAdmin` — list display: alias, alias_type, county_context, report link. Filter by: alias_type, confidence
- `TraffickingAliasAlertAdmin` — list display: alias, both reports, alert_sent

### Migration
`python manage.py makemigrations cases`
`python manage.py migrate`

### Files to create/edit
- `cases/models.py` — add 4 models
- `cases/admin.py` — register all 4 with filters
- New migration file auto-generated

---

## Chunk 2 — Report Submission Form (Web)

### What gets built
- New page `/report-trafficking/`
- New URL in `sheria_ai/urls.py`
- New view in `cases/web_views.py`
- New template `templates/report_trafficking.html`
- Linked from main navbar

### The page

**Header:**
```
🚨 Report Human Trafficking
Your report is anonymous. You do not need to give your name.
If someone is in danger RIGHT NOW — call DCI: 0800 722 203 (free)
```

**PANIC BUTTON** — top right corner, always visible:
```
[⚡ Close this page quickly]
— navigates to kra.go.ke immediately, no history
```

**Form fields:**

```
1. What happened?
   Textarea — "Tell us in your own words. Any language. 
               Even a short description helps."
   Placeholder: "Mfano: Mtu aliniambia kuna kazi Dubai. 
                Alinichukua passport yangu nikifika airport..."

2. Any names or nicknames you remember? (optional)
   Text input — "Even a nickname like 'Mkubwa' or a 
                  phone number helps us connect reports"
   Placeholder: "e.g. Uncle James, Mkubwa, 0712345678, 
                  'Mama wa Salon'"

3. Where did this happen?
   County dropdown (all 47 counties + "Outside Kenya")

4. When? (approximate)
   Month + Year dropdowns — "Approximate is fine"

5. Is someone being held RIGHT NOW?
   Big checkbox — "⚠️ Yes, a victim is currently being 
                    held — this is urgent"
   (If checked, red warning shows: "We will alert DCI 
    immediately. If you know the location, include it 
    in your story above.")

6. Can we contact you? (completely optional)
   Text input — "Phone or email — only if you want 
                  us to follow up with you"
   Small text: "You can leave this blank. Your report 
                 is just as useful anonymous."

[Submit Report] button
```

**After submission:**
```
✅ Thank you. Your report has been received.

Reference number: TIP-2026-0042
Keep this number — you can use it to check if your 
report has been actioned.

If you are in danger now:
📞 DCI: 0800 722 203 (free, 24hrs)
📞 HAART Kenya: +254 738 506 264
📞 NLAS (free lawyers): 0800 720 120
```

### Security
- No login required
- CSRF protection (Django default)
- Rate limit: 3 submissions per IP per hour (using cache)
- IP stored only as SHA256 hash — not reversible
- Reporter contact field encrypted at rest (django-cryptography)

### Files to create/edit
- `cases/web_views.py` — add `report_trafficking` view
- `sheria_ai/urls.py` — add path
- `templates/report_trafficking.html` — new template
- `templates/base.html` — add navbar link

---

## Chunk 3 — AI Processing Pipeline

### What gets built
- Background processing (same threading pattern as AnswerJob)
- Groq prompt that reads raw story → structured JSON + formal report
- Alias extraction and normalization
- Alias matching against existing suspects
- Alert creation when match found

### The AI prompt (Groq)

```python
TRAFFICKING_SYSTEM_PROMPT = """
You are an anti-trafficking analyst for Kenya.
Read the report below and extract information.

KENYA TRAFFICKING CONTEXT:
- Common recruitment: Facebook/WhatsApp job offers, 
  fake domestic work agencies, romance scams
- Common destinations: Gulf states (Dubai, Saudi, Qatar), 
  South Sudan, Tanzania, internal (Nairobi, Mombasa)
- Common indicators: passport taken, unpaid, not allowed 
  to leave, phone taken, threats, debt bondage

EXTRACT as JSON with these exact keys:
{
  "report_type": "labour|sexual|domestic|child|unknown",
  "recruitment_method": "social_media|job_offer|romance|family_member|broker|unknown",
  "indicators": ["list", "of", "indicator", "codes"],
  "suspects": [
    {
      "alias": "exact name/number as mentioned",
      "alias_type": "nickname|phone|facebook_name|real_name|vehicle_plate|unknown",
      "county_context": "where this person was operating or blank",
      "confidence": "high|medium|low"
    }
  ],
  "victim_profile": "adult_female|adult_male|minor_female|minor_male|unknown",
  "destination": "country or county or Unknown",
  "is_urgent_indicators": true/false,
  "formal_report_en": "Full formal report in English suitable for DCI submission. 
                        Include: Summary, Recruitment Method, Trafficking Indicators, 
                        Suspect Information, Victim Profile, Recommended Action.",
  "formal_report_sw": "Same report in Swahili."
}

Only return valid JSON. No explanation outside the JSON.
"""
```

### The alias matching logic

```python
def find_alias_matches(new_suspect):
    """
    After saving a new TraffickingSuspect, check if the normalized
    alias appears in any previous report.
    
    Matching strategy (3 levels):
    
    Level 1 — Exact match: 
      alias_normalized == existing alias_normalized
      → HIGH confidence match, create alert immediately
    
    Level 2 — Fuzzy match (Levenshtein distance ≤ 2):
      "mkubwa" matches "mukubwa" or "mkubwa wa"
      → MEDIUM confidence, flag for human review
    
    Level 3 — Phone number match:
      Strip spaces/dashes, compare last 9 digits
      "+254 712 345 678" matches "0712345678"
      → HIGH confidence match
    
    When match found:
    - Link both TraffickingSuspect records (M2M)
    - Set has_linked_reports=True on both TraffickingReports
    - Create TraffickingAliasAlert record
    - If either report is_urgent → send email to DCI immediately
    """
```

### Background processing flow

```
User submits form
       ↓
TraffickingReport saved (status='new', formal_report_en='')
       ↓
Background thread starts (daemon=True)
       ↓
Call Groq with TRAFFICKING_SYSTEM_PROMPT + story
       ↓
Parse JSON response
       ↓
Update TraffickingReport with extracted fields + formal reports
       ↓
Save each suspect as TraffickingSuspect
       ↓
Run alias matching for each new suspect
       ↓
If match found → create TraffickingAliasAlert
       ↓
If is_urgent → send email alert to DCI (via Django email)
       ↓
Status → 'processed' (ready for partner dashboard)
```

### Files to create/edit
- `cases/trafficking_ai.py` — new file: prompt, processing function, alias matching
- `cases/web_views.py` — update submit view to fire background thread
- `requirements.txt` — add `python-Levenshtein` for fuzzy matching

---

## Chunk 4 — Partner Dashboard

### What gets built
- Login page at `/trafficking/login/`
- Dashboard at `/trafficking/dashboard/`
- Report detail at `/trafficking/report/<id>/`
- Researcher stats at `/trafficking/stats/`
- PDF download per report
- Email alert system

### Access control

```python
def trafficking_tier_required(tier):
    """
    Decorator for trafficking dashboard views.
    Checks session for valid TraffickingAccessKey.
    tier = 'police' | 'ngo' | 'researcher'
    police can access ngo views, ngo can access researcher views.
    """
```

### Dashboard views by tier

**Police/DCI view** — sees everything:
```
- All reports, newest first
- URGENT flag prominent (red, top of list)
- Full story text
- Formal report in English
- Reporter contact (if provided)
- All aliases + linked reports
- Alias alert badges: "⚠️ Alias 'Mkubwa' in 3 reports"
- Status update dropdown
- Download as PDF button
- County filter
- Date range filter
- Search by alias
```

**NGO view** (HAART, IOM) — same as police except:
```
- Reporter contact hidden if is_anonymous=True
- Can update status to 'under_review' or 'referred'
- Can add internal notes
```

**Researcher view** — anonymised aggregate only:
```
- Charts: trafficking type by county (bar chart)
- Charts: recruitment method trends by month
- Charts: top indicators frequency
- Charts: destinations frequency
- NO individual report stories
- NO names, aliases or contact info
- Export as CSV (anonymised)
```

### The alias alert banner (Police/NGO)

When opening a report with linked suspects:
```
┌─────────────────────────────────────────────────────┐
│ ⚠️  ALIAS MATCH DETECTED                             │
│                                                       │
│ The alias "Mkubwa" in this report also appears in:   │
│  • Report TIP-2026-0031 (Kisumu, 3 weeks ago)        │
│  • Report TIP-2026-0018 (Nakuru, 2 months ago)       │
│                                                       │
│ [View linked reports]                                 │
└─────────────────────────────────────────────────────┘
```

### Email alerts

When `is_urgent=True` on a new report:
```
Subject: 🚨 URGENT — Trafficking Report Requires Immediate Action
To: dci-trafficking@dci.go.ke (configurable in .env)

A new urgent trafficking report has been submitted.

Report ID: TIP-2026-0042
County: Mombasa
Submitted: 31 October 2026, 22:34

The reporter indicates a victim is currently being held.

Login to view full report: https://hakimkononi.onrender.com/trafficking/dashboard/
Access key required.

— HakiMkononi Anti-Trafficking System
```

When alias match is found (even non-urgent):
```
Subject: ⚠️ Alias Match — "Mkubwa" appears in 2 reports
...
```

### Files to create/edit
- `cases/trafficking_views.py` — new file: all dashboard views
- `templates/trafficking/` — new folder: login, dashboard, report_detail, stats
- `sheria_ai/urls.py` — add /trafficking/ routes
- `cases/models.py` — add send_alert() method to TraffickingAliasAlert

---

## Chunk 5 — Security Hardening + Panic Button

### What gets built
- Panic button (JavaScript redirect, no history)
- Encryption for reporter_contact field
- Rate limiting on submission
- Content Security Policy headers
- No-index meta tag (report pages should not appear in Google)

### Panic button (JavaScript)
```javascript
// Replaces current page in history so Back button doesn't 
// return to the report form
function panicClose() {
    window.location.replace('https://www.kra.go.ke');
}
```

### reporter_contact encryption
```python
# requirements.txt
django-cryptography==1.1

# models.py
from django_cryptography.fields import encrypt

class TraffickingReport(models.Model):
    reporter_contact = encrypt(models.TextField(blank=True))
```

### Rate limiting (using Django cache)
```python
def check_rate_limit(ip_hash):
    """Max 3 submissions per IP hash per hour."""
    key = f"trafficking_submit_{ip_hash}"
    count = cache.get(key, 0)
    if count >= 3:
        return False  # rate limited
    cache.set(key, count + 1, timeout=3600)
    return True
```

### Meta tags on report page
```html
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
```

### Files to create/edit
- `templates/report_trafficking.html` — panic button, meta tags
- `requirements.txt` — add django-cryptography
- `cases/web_views.py` — rate limiting logic
- `sheria_ai/settings.py` — add encryption keys to env

---

## Chunk 6 — Navbar Link + Resource Page

### What gets built
- `/trafficking/` — public resource page (no login)
  - What is trafficking?
  - Signs to watch for
  - Who to call (HAART, DCI, NLAS)
  - [Report anonymously] button → goes to /report-trafficking/
- Navbar link on main site

### Emergency contacts on the page
```
🚨 If someone is in danger NOW:
📞 DCI Anti-Human Trafficking Unit: 0800 722 203 (toll-free, 24hrs)

📞 HAART Kenya: +254 738 506 264
   haartkenya.org — Nairobi-based NGO, victim support

📞 IOM Kenya: +254 20 434 6000
   International Organization for Migration

📞 NLAS: 0800 720 120 (toll-free)
   Free legal aid — if you need a lawyer

📞 FIDA Kenya: 020 271 4911
   Women and children specifically

Under the Counter-Trafficking in Persons Act 2010 (Cap 61),
trafficking carries a maximum sentence of 30 years or life 
imprisonment if the victim is a child.
```

---

## Chunk 7 — Demo Package for HAART + DCI

### What gets built
- 5 pre-loaded test reports (realistic Kenyan scenarios)
- Demo access keys for HAART (NGO tier) and DCI (police tier)
- Management command: `python manage.py load_demo_trafficking`
- One-page summary PDF to hand to HAART/DCI at the meeting

### Demo scenarios
```
1. Labour trafficking — Nairobi woman recruited for Dubai domestic work,
   passport taken, not paid, alias "Uncle James" extracted
   
2. Labour trafficking — Same alias "Uncle James" from Kisumu 
   → triggers alias match alert ✅

3. Child trafficking — 15-year-old girl, family member involved,
   URGENT flag set → triggers email alert ✅

4. Sexual exploitation — Mombasa, social media recruitment,
   phone number extracted as alias

5. Internal trafficking — Kisumu to Nairobi, broker involved,
   cross-referenced to report 1 by county pattern
```

### Files to create
- `cases/management/commands/load_demo_trafficking.py`
- `TRAFFICKING_DEMO.pdf` — one-page handout

---

## Environment Variables Needed

Add these to Render env and local .env:

```
# Email alerts to DCI/NGO
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=alerts@hakimkononi.co.ke
EMAIL_HOST_PASSWORD=...

# DCI alert recipient (configure once partner agrees)
DCI_ALERT_EMAIL=dci-trafficking@dci.go.ke
HAART_ALERT_EMAIL=info@haartkenya.org

# Encryption key for reporter_contact field
FIELD_ENCRYPTION_KEY=...   # generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## New Dependencies

Add to `requirements.txt`:
```
django-cryptography==1.1     # field-level encryption for reporter contact
python-Levenshtein==0.25.1   # fuzzy alias matching
```

---

## New Files Summary

```
cases/
  trafficking_ai.py          — AI prompt + processing + alias matching
  trafficking_views.py       — partner dashboard views
  management/commands/
    load_demo_trafficking.py — demo data loader

templates/
  report_trafficking.html    — public submission form
  trafficking/
    login.html               — partner login
    dashboard.html           — main dashboard
    report_detail.html       — single report view
    stats.html               — researcher stats
    resource_page.html       — public info page

sheria_ai/
  urls.py                    — add /trafficking/ + /report-trafficking/ routes
```

---

## Render.yaml additions (after building)

```yaml
# No new services needed — runs inside existing web dyno
# Just add the email env vars to existing web service
```

---

## Build Order

Do these chunks in order — each one is usable without the next:

| Chunk | What it unlocks |
|---|---|
| 1 — Models | Can start saving reports in admin |
| 2 — Form | Anyone can submit a report |
| 3 — AI processing | Reports become structured, aliases extracted |
| 4 — Dashboard | Partners can log in and see reports |
| 5 — Security | Safe to go live |
| 6 — Resource page | Public finds the system |
| 7 — Demo package | Ready to show HAART and DCI |

**Start Chunk 1 when ready.**

---

## Partners to Contact (after Chunk 4)

| Organisation | Contact | What to ask |
|---|---|---|
| HAART Kenya | +254 738 506 264 / info@haartkenya.org | NGO tier login, review reports, MOU |
| CTiP Secretariat | Via Ministry of Interior | Formal endorsement, police referral protocol |
| DCI Anti-HT Unit | Via HAART introduction | Police tier login, alert email, MOU |
| IOM Kenya | +254 20 434 6000 | Researcher tier access, data sharing |
| ODPC | odpc.go.ke | Register as data processor (Data Protection Act 2019) |

---

*HakiMkononi — Sheria Yako, Mkononi Mwako 🇰🇪*
*Anti-Trafficking Module — Spec v1.0 — October 2026*
