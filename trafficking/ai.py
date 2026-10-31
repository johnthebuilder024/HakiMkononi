"""
trafficking/ai.py — Chunk 3

AI processing pipeline for trafficking reports.

Flow for each report:
  1. Call Groq with TRAFFICKING_SYSTEM_PROMPT + raw story
  2. Parse JSON response → extract structured fields + suspects + formal reports
  3. Update TraffickingReport with structured data
  4. Save each AI-extracted suspect as TraffickingSuspect
  5. Run alias matching against all existing suspects
  6. Create TraffickingAliasAlert for any matches found
  7. Send email alert if urgent or alias match found
  8. Mark report status = 'ready'

Alias matching strategy (3 levels):
  Level 1 — Exact normalized match        → HIGH confidence
  Level 2 — Fuzzy match (edit distance≤2) → MEDIUM confidence
  Level 3 — Phone number match            → HIGH confidence
"""

import json
import logging
import os
import re

import requests as _requests

from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Valid indicator codes (must match model choices) ──────────────────────────
VALID_INDICATORS = {
    'passport_confiscation', 'document_confiscation', 'debt_bondage',
    'movement_restriction', 'unpaid_wages', 'threats_violence',
    'physical_abuse', 'sexual_abuse', 'confinement', 'deceptive_job_offer',
    'false_promises', 'recruited_for_domestic_work', 'transported_across_border',
    'phone_confiscated', 'monitored_communications', 'underfed_or_starved',
    'multiple_victims_together',
}

VALID_TYPES = {'labour', 'sexual', 'domestic', 'child', 'unknown'}
VALID_RECRUIT = {
    'social_media', 'job_offer', 'romance', 'family_member', 'broker', 'unknown'
}
VALID_PROFILES = {
    'adult_female', 'adult_male', 'minor_female', 'minor_male', 'unknown'
}
VALID_ALIAS_TYPES = {
    'nickname', 'phone', 'facebook_name', 'real_name',
    'vehicle_plate', 'organisation', 'unknown'
}
VALID_CONFIDENCE = {'high', 'medium', 'low'}

# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

TRAFFICKING_SYSTEM_PROMPT = """You are a specialist anti-trafficking analyst for Kenya.
Read the report below and extract structured information.

KENYA CONTEXT — common patterns to recognise:
- Recruitment: Facebook/WhatsApp fake job offers, domestic work agencies, romance scams, family members selling relatives
- Common destinations: Dubai, Saudi Arabia, Qatar, Kuwait, Oman (Gulf), South Sudan, Uganda, Tanzania, and internal routes (Nairobi, Mombasa, Malindi)
- Common indicators: passport taken at airport, unpaid, locked in house, phone confiscated, debt bondage ("you owe us for transport"), threats, multiple victims together
- Language: story may be in Swahili, English or Sheng — understand all three

EXTRACT as valid JSON with exactly these keys:

{
  "report_type": "labour|sexual|domestic|child|unknown",
  "recruitment_method": "social_media|job_offer|romance|family_member|broker|unknown",
  "indicators": ["indicator_code1", "indicator_code2"],
  "suspects": [
    {
      "alias": "exact name or number as mentioned in the story",
      "alias_type": "nickname|phone|facebook_name|real_name|vehicle_plate|organisation|unknown",
      "county_context": "county or country where this person operates, or empty string",
      "confidence": "high|medium|low"
    }
  ],
  "victim_profile": "adult_female|adult_male|minor_female|minor_male|unknown",
  "destination": "destination country or Kenyan county, or Unknown",
  "story_lang": "en|sw|sheng|unknown",
  "is_urgent_indicators": true or false,
  "formal_report_en": "Full formal report in English. Structure: SUMMARY (2 sentences), TRAFFICKING TYPE, RECRUITMENT METHOD, INDICATORS PRESENT (bulleted), SUSPECT INFORMATION (names/aliases/phones), VICTIM PROFILE, RECOMMENDED ACTIONS (numbered). Professional law enforcement language.",
  "formal_report_sw": "Same formal report in Swahili. Same structure, same content, translated."
}

VALID indicator codes (use only these exact strings):
passport_confiscation, document_confiscation, debt_bondage, movement_restriction,
unpaid_wages, threats_violence, physical_abuse, sexual_abuse, confinement,
deceptive_job_offer, false_promises, recruited_for_domestic_work,
transported_across_border, phone_confiscated, monitored_communications,
underfed_or_starved, multiple_victims_together

RULES:
- Return ONLY valid JSON. No text before or after.
- Extract ALL names, nicknames, phone numbers, Facebook names, vehicle plates mentioned.
- If the story mentions no suspects at all, return "suspects": []
- For phones: include the number exactly as written (e.g. "0712345678" or "+254712345678")
- Confidence: high = clearly a real identifier, medium = probable, low = uncertain
- is_urgent_indicators: true if the story suggests victim is CURRENTLY being held
- formal_report_en must be professional enough to hand directly to DCI
"""


# ─────────────────────────────────────────────────────────────────────────────
# Groq call
# ─────────────────────────────────────────────────────────────────────────────

def _call_groq(story: str) -> dict:
    """
    Call Groq with the trafficking prompt.
    Returns the parsed JSON dict, or raises on failure.
    """
    groq_key = os.getenv('GROQ_API_KEY', '').strip()
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY not set")

    groq_model = os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')

    payload = {
        "model": groq_model,
        "messages": [
            {"role": "system", "content": TRAFFICKING_SYSTEM_PROMPT},
            {"role": "user",   "content": f"REPORT:\n{story}"},
        ],
        "temperature": 0.1,   # low temperature for consistent structured output
        "max_tokens":  2000,
        "response_format": {"type": "json_object"},  # force JSON output
    }

    resp = _requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=(15, 60),
    )
    resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Parse JSON — strip markdown fences if model added them
    if content.startswith("```"):
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

    return json.loads(content)


# ─────────────────────────────────────────────────────────────────────────────
# Alias normalization & matching
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_alias(alias: str) -> str:
    """
    Normalize an alias for cross-report matching.

    Phone numbers → last 9 digits (strips prefix)
    Names         → lowercase, strip titles (uncle/mama/mr/bw), collapse spaces
    """
    s = alias.lower().strip()

    # Phone: strip all non-digits except leading +
    phone_digits = re.sub(r'[\s\-\(\)\+\.]', '', s)
    if re.match(r'^(254|0)\d{9}$', phone_digits) or re.match(r'^\d{9,12}$', phone_digits):
        return phone_digits[-9:]   # last 9 digits = unique Kenyan number

    # Name normalization
    s = re.sub(r'^(uncle|aunt|mama|baba|mr|mrs|miss|ms|dr|dkt|prof|mzee|bibi|bw|bi)\s+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _levenshtein(a: str, b: str) -> int:
    """
    Compute Levenshtein edit distance between two strings.
    Pure Python — no external library needed.
    """
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)
    # Use dynamic programming
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def _find_alias_matches(new_suspect):
    """
    Given a newly saved TraffickingSuspect, find matching suspects
    from previous reports.

    Returns list of (existing_suspect, match_type) tuples.
    match_type: 'exact' | 'fuzzy' | 'phone'
    """
    from .models import TraffickingSuspect

    new_norm  = new_suspect.alias_normalized
    matches   = []

    # Don't match against suspects in the SAME report
    existing  = TraffickingSuspect.objects.exclude(
        report=new_suspect.report
    ).only('id', 'alias', 'alias_normalized', 'alias_type', 'report_id')

    for existing_s in existing:
        ex_norm = existing_s.alias_normalized

        # Skip very short normalised values — too likely to be false positives
        if len(new_norm) < 3 or len(ex_norm) < 3:
            continue

        # Level 3: Phone match (both look like 9-digit phone numbers)
        if (re.match(r'^\d{9}$', new_norm) and re.match(r'^\d{9}$', ex_norm)
                and new_norm == ex_norm):
            matches.append((existing_s, 'phone'))
            continue

        # Level 1: Exact normalized match
        if new_norm == ex_norm:
            matches.append((existing_s, 'exact'))
            continue

        # Level 2: Fuzzy match — only for strings ≥ 5 chars to avoid noise
        if len(new_norm) >= 5 and len(ex_norm) >= 5:
            dist = _levenshtein(new_norm, ex_norm)
            if dist <= 2:
                matches.append((existing_s, 'fuzzy'))

    return matches


# ─────────────────────────────────────────────────────────────────────────────
# Email alerts
# ─────────────────────────────────────────────────────────────────────────────

def _send_alert_email(subject: str, body: str):
    """
    Send email alert to DCI/NGO partners.
    Uses Django's email backend (configured via EMAIL_* settings).
    Silently fails if email not configured — doesn't break report processing.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings

        recipient = os.getenv('DCI_ALERT_EMAIL', '').strip()
        if not recipient:
            logger.info("[TIP] No DCI_ALERT_EMAIL configured — skipping email alert")
            return

        send_mail(
            subject=subject,
            message=body,
            from_email=os.getenv('EMAIL_HOST_USER', 'alerts@hakimkononi.co.ke'),
            recipient_list=[recipient],
            fail_silently=True,
        )
        logger.info(f"[TIP] Alert email sent to {recipient}: {subject}")
    except Exception as e:
        logger.warning(f"[TIP] Email alert failed: {e}")


def _send_urgent_alert(report):
    """Send immediate DCI alert for an urgent report."""
    subject = f"🚨 URGENT — Trafficking Report {report.reference_number} Requires Immediate Action"
    body = (
        f"A new URGENT trafficking report has been submitted.\n\n"
        f"Reference: {report.reference_number}\n"
        f"County: {report.county_of_origin or 'Not specified'}\n"
        f"Submitted: {report.created_at.strftime('%d %B %Y, %H:%M UTC')}\n"
        f"Type: {report.get_report_type_display()}\n\n"
        f"The reporter indicates a victim is currently being held.\n\n"
        f"Login to view full report:\n"
        f"https://hakimkononi.onrender.com/report-trafficking/dashboard/\n\n"
        f"Access key required. Contact admin if you need your key.\n\n"
        f"— HakiMkononi Anti-Trafficking System"
    )
    _send_alert_email(subject, body)


def _send_alias_match_alert(alert):
    """Send alert when an alias match is found between two reports."""
    subject = (
        f"⚠️ Alias Match Detected — \"{alert.alias}\" in "
        f"{alert.report_new.reference_number} matches {alert.report_previous.reference_number}"
    )
    body = (
        f"An alias match has been detected across two trafficking reports.\n\n"
        f"Alias: \"{alert.alias}\" ({alert.get_match_type_display()})\n\n"
        f"New report:      {alert.report_new.reference_number} "
        f"({alert.report_new.county_of_origin}, "
        f"{alert.report_new.created_at.strftime('%d %b %Y')})\n"
        f"Previous report: {alert.report_previous.reference_number} "
        f"({alert.report_previous.county_of_origin}, "
        f"{alert.report_previous.created_at.strftime('%d %b %Y')})\n\n"
        f"This may indicate the same trafficker operating in multiple areas.\n\n"
        f"Login to review:\n"
        f"https://hakimkononi.onrender.com/report-trafficking/dashboard/\n\n"
        f"— HakiMkononi Anti-Trafficking System"
    )
    _send_alert_email(subject, body)


# ─────────────────────────────────────────────────────────────────────────────
# Main processing function
# ─────────────────────────────────────────────────────────────────────────────

def process_report(report_id: int):
    """
    Main entry point — called in a background thread by views.py.

    1. Load report
    2. Call Groq → structured JSON
    3. Save structured fields to report
    4. Save AI-extracted suspects
    5. Run alias matching on each suspect
    6. Create alias alerts
    7. Send email alerts (urgent + alias matches)
    8. Mark status = 'ready'
    """
    from .models import TraffickingReport, TraffickingSuspect, TraffickingAliasAlert

    logger.info(f"[TIP] Starting AI processing for report {report_id}")

    try:
        report = TraffickingReport.objects.get(pk=report_id)
    except TraffickingReport.DoesNotExist:
        logger.error(f"[TIP] Report {report_id} not found")
        return

    # Already processed — skip
    if report.status not in (
        TraffickingReport.STATUS_NEW,
        TraffickingReport.STATUS_PROCESS,
    ):
        logger.info(f"[TIP] Report {report_id} already processed ({report.status}), skipping")
        return

    # ── Step 1: Call Groq ─────────────────────────────────────────────────────
    try:
        data = _call_groq(report.story_raw)
        logger.info(f"[TIP] Groq response received for report {report_id}")
    except Exception as e:
        logger.error(f"[TIP] Groq call failed for report {report_id}: {e}", exc_info=True)
        # Mark ready anyway — partners can read raw story
        TraffickingReport.objects.filter(pk=report_id).update(
            status=TraffickingReport.STATUS_READY
        )
        return

    # ── Step 2: Parse and validate fields ────────────────────────────────────
    report_type = data.get('report_type', 'unknown')
    if report_type not in VALID_TYPES:
        report_type = 'unknown'

    recruitment_method = data.get('recruitment_method', 'unknown')
    if recruitment_method not in VALID_RECRUIT:
        recruitment_method = 'unknown'

    victim_profile = data.get('victim_profile', 'unknown')
    if victim_profile not in VALID_PROFILES:
        victim_profile = 'unknown'

    # Validate indicator codes — keep only known ones
    raw_indicators = data.get('indicators', [])
    indicators = [i for i in raw_indicators if i in VALID_INDICATORS]

    destination      = str(data.get('destination', ''))[:200]
    story_lang       = data.get('story_lang', 'unknown')
    if story_lang not in ('en', 'sw', 'sheng', 'unknown'):
        story_lang = 'unknown'

    formal_en = str(data.get('formal_report_en', ''))
    formal_sw = str(data.get('formal_report_sw', ''))

    # ai_urgent: whether AI detected ongoing urgency signals
    ai_urgent = bool(data.get('is_urgent_indicators', False))

    # ── Step 3: Update report ─────────────────────────────────────────────────
    TraffickingReport.objects.filter(pk=report_id).update(
        report_type         = report_type,
        recruitment_method  = recruitment_method,
        indicators          = indicators,
        victim_profile      = victim_profile,
        destination         = destination,
        story_lang          = story_lang,
        formal_report_en    = formal_en,
        formal_report_sw    = formal_sw,
        # If either reporter marked urgent OR AI detected urgency signals, mark urgent
        is_urgent           = report.is_urgent or ai_urgent,
    )
    # Refresh from DB
    report.refresh_from_db()
    logger.info(f"[TIP] Report {report_id} updated: type={report_type}, indicators={indicators}")

    # ── Step 4: Save AI-extracted suspects ────────────────────────────────────
    suspects_data = data.get('suspects', [])
    new_suspects  = []

    for s in suspects_data:
        alias_text = str(s.get('alias', '')).strip()
        if not alias_text or len(alias_text) < 2:
            continue

        alias_type = s.get('alias_type', 'unknown')
        if alias_type not in VALID_ALIAS_TYPES:
            alias_type = 'unknown'

        confidence = s.get('confidence', 'medium')
        if confidence not in VALID_CONFIDENCE:
            confidence = 'medium'

        county_ctx = str(s.get('county_context', ''))[:100]

        # Check if this exact alias was already saved by the form submission
        # (reporter typed it manually in the aliases field)
        already_exists = TraffickingSuspect.objects.filter(
            report=report,
            alias__iexact=alias_text,
        ).exists()

        if already_exists:
            # Update the existing record with AI-enriched fields
            TraffickingSuspect.objects.filter(
                report=report,
                alias__iexact=alias_text,
            ).update(
                alias_type     = alias_type,
                confidence     = confidence,
                county_context = county_ctx,
                alias_normalized = _normalize_alias(alias_text),
            )
            suspect = TraffickingSuspect.objects.get(
                report=report,
                alias__iexact=alias_text,
            )
        else:
            suspect = TraffickingSuspect.objects.create(
                report           = report,
                alias            = alias_text,
                alias_type       = alias_type,
                alias_normalized = _normalize_alias(alias_text),
                county_context   = county_ctx,
                confidence       = confidence,
            )

        new_suspects.append(suspect)
        logger.info(f"[TIP] Suspect saved: \"{alias_text}\" [{alias_type}] for report {report_id}")

    # Also normalize any existing suspects from the form submission
    for existing_s in TraffickingSuspect.objects.filter(report=report):
        if not existing_s.alias_normalized:
            existing_s.alias_normalized = _normalize_alias(existing_s.alias)
            existing_s.save(update_fields=['alias_normalized'])
        if existing_s not in new_suspects:
            new_suspects.append(existing_s)

    # ── Step 5: Alias matching ────────────────────────────────────────────────
    alias_alerts_created  = []
    has_linked            = False

    for suspect in new_suspects:
        matches = _find_alias_matches(suspect)
        for matched_suspect, match_type in matches:
            has_linked = True

            # Link suspects M2M
            suspect.linked_to.add(matched_suspect)
            matched_suspect.linked_to.add(suspect)

            # Mark both reports as having linked reports
            TraffickingReport.objects.filter(
                pk__in=[report.pk, matched_suspect.report_id]
            ).update(has_linked_reports=True)

            # Create alert record (avoid duplicates)
            alert_exists = TraffickingAliasAlert.objects.filter(
                alias=suspect.alias,
                report_new=report,
                report_previous=matched_suspect.report,
            ).exists()

            if not alert_exists:
                alert = TraffickingAliasAlert.objects.create(
                    alias            = suspect.alias,
                    match_type       = match_type,
                    report_new       = report,
                    report_previous  = matched_suspect.report,
                    suspect_new      = suspect,
                    suspect_previous = matched_suspect,
                )
                alias_alerts_created.append(alert)
                logger.warning(
                    f"[TIP] ALIAS MATCH: \"{suspect.alias}\" ({match_type}) — "
                    f"report {report.reference_number} ↔ "
                    f"{matched_suspect.report.reference_number}"
                )

    if has_linked:
        TraffickingReport.objects.filter(pk=report_id).update(has_linked_reports=True)

    # ── Step 6: Email alerts ──────────────────────────────────────────────────
    # Refresh to get latest is_urgent after AI update
    report.refresh_from_db()

    if report.is_urgent:
        _send_urgent_alert(report)

    for alert in alias_alerts_created:
        alert.alert_sent    = True
        alert.alert_sent_at = timezone.now()
        alert.save(update_fields=['alert_sent', 'alert_sent_at'])
        _send_alias_match_alert(alert)

    # ── Step 7: Mark ready ────────────────────────────────────────────────────
    TraffickingReport.objects.filter(pk=report_id).update(
        status=TraffickingReport.STATUS_READY
    )

    logger.info(
        f"[TIP] ✅ Report {report.reference_number} processed — "
        f"type={report_type}, suspects={len(new_suspects)}, "
        f"alias_alerts={len(alias_alerts_created)}, urgent={report.is_urgent}"
    )
