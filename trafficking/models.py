"""
Trafficking app — models.

Completely separate from the cases app.
No imports from cases — zero coupling.

Four models:
  TraffickingReport    — one per submitted report
  TraffickingSuspect   — one per alias/name extracted from a report
  TraffickingAccessKey — controls partner dashboard access (Police/NGO/Researcher)
  TraffickingAliasAlert — records when two reports share the same alias
"""

import hashlib
import json

from django.db import models
from django.utils import timezone


# ─── Indicator codes ──────────────────────────────────────────────────────────
# These are saved as a JSON list in TraffickingReport.indicators

INDICATOR_CHOICES = [
    ('passport_confiscation',      'Passport / ID confiscated'),
    ('document_confiscation',      'Documents confiscated (other)'),
    ('debt_bondage',               'Debt bondage'),
    ('movement_restriction',       'Movement restricted'),
    ('unpaid_wages',               'Wages withheld / unpaid'),
    ('threats_violence',           'Threats or violence'),
    ('physical_abuse',             'Physical abuse'),
    ('sexual_abuse',               'Sexual abuse'),
    ('confinement',                'Confined / locked in'),
    ('deceptive_job_offer',        'Deceived with fake job offer'),
    ('false_promises',             'False promises (money, education, marriage)'),
    ('recruited_for_domestic_work','Recruited specifically for domestic work'),
    ('transported_across_border',  'Transported across county or country border'),
    ('phone_confiscated',          'Phone confiscated'),
    ('monitored_communications',   'Communications monitored'),
    ('underfed_or_starved',        'Underfed or starved'),
    ('multiple_victims_together',  'Multiple victims held together'),
]


class TraffickingReport(models.Model):
    """
    One row per submitted trafficking report.

    A report starts with a raw story in any language.
    The AI processes it and fills the structured fields.
    """

    # ── Type choices ──────────────────────────────────────────────────────────
    TYPE_LABOUR    = 'labour'
    TYPE_SEXUAL    = 'sexual'
    TYPE_DOMESTIC  = 'domestic'
    TYPE_CHILD     = 'child'
    TYPE_UNKNOWN   = 'unknown'
    TYPE_CHOICES = [
        (TYPE_LABOUR,   'Labour Trafficking'),
        (TYPE_SEXUAL,   'Sexual Exploitation'),
        (TYPE_DOMESTIC, 'Domestic Servitude'),
        (TYPE_CHILD,    'Child Trafficking'),
        (TYPE_UNKNOWN,  'Unknown / Other'),
    ]

    # ── Recruitment method choices ────────────────────────────────────────────
    RECRUIT_SOCIAL   = 'social_media'
    RECRUIT_JOB      = 'job_offer'
    RECRUIT_ROMANCE  = 'romance'
    RECRUIT_FAMILY   = 'family_member'
    RECRUIT_BROKER   = 'broker'
    RECRUIT_UNKNOWN  = 'unknown'
    RECRUIT_CHOICES = [
        (RECRUIT_SOCIAL,  'Social Media (Facebook, WhatsApp, TikTok)'),
        (RECRUIT_JOB,     'Fake Job Offer'),
        (RECRUIT_ROMANCE, 'Romance / Relationship'),
        (RECRUIT_FAMILY,  'Family Member Involved'),
        (RECRUIT_BROKER,  'Agent / Broker'),
        (RECRUIT_UNKNOWN, 'Unknown'),
    ]

    # ── Victim profile choices ────────────────────────────────────────────────
    PROFILE_ADULT_F  = 'adult_female'
    PROFILE_ADULT_M  = 'adult_male'
    PROFILE_MINOR_F  = 'minor_female'
    PROFILE_MINOR_M  = 'minor_male'
    PROFILE_UNKNOWN  = 'unknown'
    PROFILE_CHOICES = [
        (PROFILE_ADULT_F, 'Adult Female'),
        (PROFILE_ADULT_M, 'Adult Male'),
        (PROFILE_MINOR_F, 'Minor (Female, under 18)'),
        (PROFILE_MINOR_M, 'Minor (Male, under 18)'),
        (PROFILE_UNKNOWN, 'Unknown'),
    ]

    # ── Status choices ────────────────────────────────────────────────────────
    STATUS_NEW      = 'new'
    STATUS_PROCESS  = 'processing'
    STATUS_READY    = 'ready'          # AI processed, awaiting partner review
    STATUS_REVIEW   = 'under_review'
    STATUS_ACTIONED = 'actioned'       # partner took action
    STATUS_CLOSED   = 'closed'
    STATUS_FALSE    = 'false_report'
    STATUS_CHOICES = [
        (STATUS_NEW,      '🆕 New — awaiting AI processing'),
        (STATUS_PROCESS,  '⏳ Processing'),
        (STATUS_READY,    '✅ Ready for review'),
        (STATUS_REVIEW,   '👁️ Under review'),
        (STATUS_ACTIONED, '⚡ Actioned'),
        (STATUS_CLOSED,   '🔒 Closed'),
        (STATUS_FALSE,    '❌ False / Spam'),
    ]

    # ── Raw submission fields ─────────────────────────────────────────────────
    story_raw           = models.TextField(
                              help_text="Original story as submitted — any language")
    story_lang          = models.CharField(
                              max_length=10, default='unknown',
                              help_text="Detected language: sw / en / sheng / unknown")
    county_of_origin    = models.CharField(
                              max_length=100, blank=True,
                              help_text="County where trafficking occurred / victim is from")
    approximate_date    = models.CharField(
                              max_length=50, blank=True,
                              help_text="Approximate date as entered e.g. 'October 2026'")
    is_urgent           = models.BooleanField(
                              default=False,
                              help_text="Victim currently being held — requires immediate action")

    # ── Contact (optional, stored as hash+encrypted value) ───────────────────
    # We store the contact as plain text but flag it as sensitive.
    # Full encryption (django-cryptography) added in Chunk 5.
    reporter_contact    = models.TextField(
                              blank=True,
                              help_text="Phone or email — optional, may be blank if anonymous")
    is_anonymous        = models.BooleanField(
                              default=True,
                              help_text="True if reporter chose not to provide contact")

    # ── AI-extracted structured fields ────────────────────────────────────────
    report_type         = models.CharField(
                              max_length=20, choices=TYPE_CHOICES, default=TYPE_UNKNOWN)
    recruitment_method  = models.CharField(
                              max_length=30, choices=RECRUIT_CHOICES, default=RECRUIT_UNKNOWN)
    indicators          = models.JSONField(
                              default=list, blank=True,
                              help_text="List of indicator codes extracted by AI")
    victim_profile      = models.CharField(
                              max_length=20, choices=PROFILE_CHOICES, default=PROFILE_UNKNOWN)
    destination         = models.CharField(
                              max_length=200, blank=True,
                              help_text="Destination country or county e.g. 'Dubai' or 'Nairobi'")

    # ── AI-generated formal reports ───────────────────────────────────────────
    formal_report_en    = models.TextField(
                              blank=True,
                              help_text="AI-generated formal report in English for DCI submission")
    formal_report_sw    = models.TextField(
                              blank=True,
                              help_text="AI-generated formal report in Swahili")

    # ── Status and partner workflow ───────────────────────────────────────────
    status              = models.CharField(
                              max_length=15, choices=STATUS_CHOICES, default=STATUS_NEW)
    status_note         = models.TextField(
                              blank=True,
                              help_text="Internal note from reviewing partner")
    reviewed_by         = models.CharField(
                              max_length=200, blank=True,
                              help_text="Organisation that reviewed this report")
    reviewed_at         = models.DateTimeField(null=True, blank=True)

    # ── Alias cross-referencing ───────────────────────────────────────────────
    has_linked_reports  = models.BooleanField(
                              default=False,
                              help_text="True if a suspect alias in this report also appears in another")

    # ── Rate limiting (not personal data) ────────────────────────────────────
    ip_hash             = models.CharField(
                              max_length=64, blank=True,
                              help_text="SHA256 of submitter IP — for rate limiting only, not identifiable")

    # ── Reference number ─────────────────────────────────────────────────────
    reference_number    = models.CharField(
                              max_length=20, unique=True, blank=True,
                              help_text="e.g. TIP-2026-0042 — shown to reporter after submission")

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_urgent', '-created_at']
        verbose_name = 'Trafficking Report'
        verbose_name_plural = 'Trafficking Reports'

    def __str__(self):
        urgent = '🚨 URGENT — ' if self.is_urgent else ''
        return f"{urgent}{self.reference_number} [{self.get_report_type_display()}] {self.county_of_origin}"

    def save(self, *args, **kwargs):
        # Auto-generate reference number on first save
        if not self.reference_number:
            super().save(*args, **kwargs)  # need pk first
            year = self.created_at.year if self.created_at else timezone.now().year
            self.reference_number = f"TIP-{year}-{self.pk:04d}"
            kwargs['update_fields'] = ['reference_number'] if 'update_fields' not in kwargs else kwargs['update_fields']
        super().save(*args, **kwargs)

    def get_indicators_display_list(self):
        """Return human-readable list of indicator labels."""
        label_map = dict(INDICATOR_CHOICES)
        return [label_map.get(i, i) for i in (self.indicators or [])]


class TraffickingSuspect(models.Model):
    """
    One row per name, nickname, alias, phone number, or vehicle plate
    extracted from a TraffickingReport.

    The alias_normalized field is used for matching across reports.
    """

    ALIAS_NICKNAME   = 'nickname'
    ALIAS_PHONE      = 'phone'
    ALIAS_FACEBOOK   = 'facebook_name'
    ALIAS_REAL       = 'real_name'
    ALIAS_PLATE      = 'vehicle_plate'
    ALIAS_ORG        = 'organisation'
    ALIAS_UNKNOWN    = 'unknown'
    ALIAS_CHOICES = [
        (ALIAS_NICKNAME, 'Nickname / Street name'),
        (ALIAS_PHONE,    'Phone number'),
        (ALIAS_FACEBOOK, 'Facebook / WhatsApp name'),
        (ALIAS_REAL,     'Real name'),
        (ALIAS_PLATE,    'Vehicle plate'),
        (ALIAS_ORG,      'Organisation / Agency'),
        (ALIAS_UNKNOWN,  'Unknown type'),
    ]

    CONF_HIGH   = 'high'
    CONF_MEDIUM = 'medium'
    CONF_LOW    = 'low'
    CONF_CHOICES = [
        (CONF_HIGH,   'High — AI is confident this is a real identifier'),
        (CONF_MEDIUM, 'Medium — possible, needs review'),
        (CONF_LOW,    'Low — uncertain'),
    ]

    report          = models.ForeignKey(
                          TraffickingReport,
                          on_delete=models.CASCADE,
                          related_name='suspects')
    alias           = models.CharField(
                          max_length=300,
                          help_text="Exact alias as mentioned in the report")
    alias_type      = models.CharField(
                          max_length=20, choices=ALIAS_CHOICES, default=ALIAS_UNKNOWN)
    alias_normalized = models.CharField(
                          max_length=300, blank=True,
                          help_text="Lowercase, stripped — used for cross-report matching")
    county_context  = models.CharField(
                          max_length=100, blank=True,
                          help_text="County where this person was operating, if known")
    confidence      = models.CharField(
                          max_length=10, choices=CONF_CHOICES, default=CONF_MEDIUM)

    # Links to matching suspects in other reports
    linked_to       = models.ManyToManyField(
                          'self', blank=True,
                          help_text="Suspects from other reports with the same alias")

    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Suspect / Alias'
        verbose_name_plural = 'Suspects / Aliases'

    def __str__(self):
        return f'"{self.alias}" [{self.get_alias_type_display()}] — {self.report.reference_number}'

    def save(self, *args, **kwargs):
        # Auto-normalize alias for matching
        if self.alias and not self.alias_normalized:
            self.alias_normalized = self._normalize(self.alias)
        super().save(*args, **kwargs)

    @staticmethod
    def _normalize(alias: str) -> str:
        """
        Normalize an alias for fuzzy matching.
        Strips whitespace, lowercases, removes common prefixes like
        'uncle', 'mama', 'mr', 'mrs', 'bw', 'bi'.
        Phone numbers: strip +254 prefix, spaces, dashes.
        """
        import re
        s = alias.lower().strip()
        # Phone normalization — strip +254 or 254 prefix, keep last 9 digits
        phone_clean = re.sub(r'[\s\-\(\)\+]', '', s)
        if re.match(r'^(254|0)\d{9}$', phone_clean):
            # Normalize to 9-digit suffix
            return phone_clean[-9:]
        # Name normalization
        s = re.sub(r'^(uncle|mama|mr|mrs|miss|bw|bi|dkt|prof)\s+', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s


class TraffickingAccessKey(models.Model):
    """
    Controls who can log into the partner dashboard.

    Tier hierarchy:
      police     — sees everything including reporter contact
      ngo        — sees reports but hides anonymous reporter contact
      researcher — sees only anonymised aggregate statistics
    """

    TIER_POLICE     = 'police'
    TIER_NGO        = 'ngo'
    TIER_RESEARCHER = 'researcher'
    TIER_CHOICES = [
        (TIER_POLICE,     '🚔 Police / DCI — full access'),
        (TIER_NGO,        '🤝 NGO Partner — full reports, no anonymous contact'),
        (TIER_RESEARCHER, '📊 Researcher — anonymised stats only'),
    ]

    organisation    = models.CharField(
                          max_length=200,
                          help_text="e.g. 'HAART Kenya', 'DCI Anti-HT Unit', 'IOM Kenya'")
    tier            = models.CharField(
                          max_length=15, choices=TIER_CHOICES)
    # Store only the hash of the access key — never the key itself
    access_key_hash = models.CharField(
                          max_length=128,
                          help_text="SHA256 of the access key — never store plain text")
    county_filter   = models.CharField(
                          max_length=100, blank=True,
                          help_text="If set, this partner only sees reports from this county")
    can_update_status = models.BooleanField(
                          default=True,
                          help_text="Can this partner update report status?")
    email_alerts    = models.EmailField(
                          blank=True,
                          help_text="Send urgent alerts and alias match alerts to this email")
    active          = models.BooleanField(default=True)
    last_used_at    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tier', 'organisation']
        verbose_name = 'Partner Access Key'
        verbose_name_plural = 'Partner Access Keys'

    def __str__(self):
        status = '✅' if self.active else '❌'
        return f"{status} {self.organisation} [{self.get_tier_display()}]"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hash a raw access key for storage and comparison."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def check_key(self, raw_key: str) -> bool:
        """Verify a raw access key against the stored hash."""
        return self.access_key_hash == self.hash_key(raw_key)

    @classmethod
    def generate_key(cls) -> str:
        """Generate a secure random access key to give to a partner."""
        import secrets
        return secrets.token_urlsafe(32)


class TraffickingAliasAlert(models.Model):
    """
    Created whenever a new suspect alias matches an alias from a previous report.

    This is how the system surfaces connections between reports that
    would otherwise be invisible — the same trafficker using the same
    nickname in Kisumu and Mombasa.
    """

    MATCH_EXACT  = 'exact'
    MATCH_FUZZY  = 'fuzzy'
    MATCH_PHONE  = 'phone'
    MATCH_CHOICES = [
        (MATCH_EXACT, 'Exact match — same normalized alias'),
        (MATCH_FUZZY, 'Fuzzy match — similar alias (edit distance ≤ 2)'),
        (MATCH_PHONE, 'Phone match — same number, different format'),
    ]

    alias           = models.CharField(
                          max_length=300,
                          help_text="The alias that matched")
    match_type      = models.CharField(
                          max_length=10, choices=MATCH_CHOICES, default=MATCH_EXACT)
    report_new      = models.ForeignKey(
                          TraffickingReport,
                          on_delete=models.CASCADE,
                          related_name='alias_alerts_new',
                          help_text="The newer report that triggered the match")
    report_previous = models.ForeignKey(
                          TraffickingReport,
                          on_delete=models.CASCADE,
                          related_name='alias_alerts_previous',
                          help_text="The earlier report the alias was found in")
    suspect_new     = models.ForeignKey(
                          TraffickingSuspect,
                          on_delete=models.CASCADE,
                          related_name='alerts_as_new',
                          null=True, blank=True)
    suspect_previous = models.ForeignKey(
                          TraffickingSuspect,
                          on_delete=models.CASCADE,
                          related_name='alerts_as_previous',
                          null=True, blank=True)
    alert_sent      = models.BooleanField(
                          default=False,
                          help_text="Email alert sent to DCI/NGO")
    alert_sent_at   = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Alias Match Alert'
        verbose_name_plural = 'Alias Match Alerts'

    def __str__(self):
        sent = '📧 Sent' if self.alert_sent else '⏳ Pending'
        return (
            f'{sent} — "{self.alias}" in '
            f'{self.report_new.reference_number} matches '
            f'{self.report_previous.reference_number}'
        )
