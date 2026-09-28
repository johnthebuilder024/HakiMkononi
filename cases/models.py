import json
from django.db import models


class Law(models.Model):
    """
    One row = one section of a Kenyan law.
    e.g. Employment Act 2007, Section 35
    """
    CATEGORY_CHOICES = [
        ('constitution', 'Constitution of Kenya 2010'),
        ('employment', 'Employment'),
        ('landlord_tenant', 'Landlord & Tenant'),
        ('criminal_procedure', 'Criminal Procedure'),
        ('children', 'Children & Family'),
        ('consumer', 'Consumer Protection'),
        ('fraud', 'Fraud & Cybercrime'),
        ('land', 'Land & Succession'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=300)        # e.g. "Employment Act 2007"
    section = models.CharField(max_length=500)       # e.g. "Section 35" or "Article 49"
    content = models.TextField()                     # full text of that section
    simple_swahili = models.TextField(blank=True)    # plain Swahili meaning (you write this)
    related_to = models.CharField(max_length=300, blank=True)  # e.g. "Article 47, Section 40"
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    source_url = models.URLField(max_length=500)     # always kenyalaw.org link
    # Embedding stored as JSON list of floats
    embedding_json = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title', 'section']
        verbose_name = 'Law Section'
        verbose_name_plural = 'Law Sections'

    def __str__(self):
        return f"{self.title} — {self.section}"

    def get_embedding(self):
        """Return embedding as a Python list, or None if not set."""
        if self.embedding_json:
            return json.loads(self.embedding_json)
        return None

    def set_embedding(self, vector):
        """Store embedding vector (list of floats) as JSON."""
        self.embedding_json = json.dumps(vector)


class Query(models.Model):
    """
    Every question Wanjiku asks, plus the answer and her feedback.
    This is our learning database.
    """
    HELPFUL_CHOICES = [
        (True, 'Ndio — Ilisaidia'),
        (False, 'Hapana — Haikuwa Sahihi'),
    ]

    # Anonymised identifier — phone number hashed or session ID
    user_identifier = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100, blank=True)
    story = models.TextField()                    # what the user typed
    answer_law = models.TextField(blank=True)      # Box 1: Sheria Inasema
    answer_simple = models.TextField(blank=True)   # Box 2: Tafsiri Rahisi
    answer_loophole = models.TextField(blank=True) # Box 3: Haki Yako / Loophole
    answer_letter = models.TextField(blank=True)   # Box 4: Andika Hivi
    raw_answer = models.TextField(blank=True)      # full GPT response (for debugging)

    # Which law sections were used
    laws_used = models.ManyToManyField(Law, blank=True)

    # Feedback from user
    was_helpful = models.BooleanField(null=True, blank=True, choices=HELPFUL_CHOICES)
    what_actually_happened = models.TextField(blank=True)  # "Court said..."
    correct_section = models.CharField(max_length=200, blank=True)  # admin correction

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Query'
        verbose_name_plural = 'User Queries'

    def __str__(self):
        return f"Query #{self.pk} — {self.story[:60]}..."


class WhatsAppUser(models.Model):
    """
    Stores each WhatsApp user's phone number and their preferred language.
    Created on first contact, updated when they choose a language.
    """
    LANG_CHOICES = [
        ('sw',   'Kiswahili'),
        ('en',   'English'),
        ('any',  'Any language'),
    ]
    STATE_NEW      = 'new'        # just joined, not yet chosen language
    STATE_ACTIVE   = 'active'     # language chosen, ready to answer questions
    STATE_CHOICES  = [
        ('new',    'New — awaiting language choice'),
        ('active', 'Active'),
    ]

    phone    = models.CharField(max_length=30, unique=True)  # e.g. whatsapp:+254712345678
    lang     = models.CharField(max_length=10, choices=LANG_CHOICES, default='sw')
    state    = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_NEW)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'WhatsApp User'
        verbose_name_plural = 'WhatsApp Users'

    def __str__(self):
        return f"{self.phone} [{self.lang}]"


class SlangKeyword(models.Model):
    """
    Slang and vernacular keywords that map to legal topics.
    Managed from Django admin — no code changes needed to add new words.

    Examples:
      karao   → criminal  (Sheng for police)
      sanse   → criminal  (Sheng for police)
      boss    → employment
      landlord → land
    """
    TOPIC_CHOICES = [
        ('employment',         'Employment / Job'),
        ('criminal',           'Criminal / Police / Arrest'),
        ('land',               'Land / Landlord / Tenant'),
        ('family',             'Family / Marriage / Divorce'),
    ]
    LANG_CHOICES = [
        ('sheng',    'Sheng'),
        ('sw',       'Kiswahili'),
        ('en',       'English'),
        ('any',      'Any language'),
    ]

    word     = models.CharField(max_length=100, unique=True,
                                help_text="The slang/vernacular word or phrase (lowercase)")
    topic    = models.CharField(max_length=30, choices=TOPIC_CHOICES,
                                help_text="Which legal topic this word signals")
    language = models.CharField(max_length=10, choices=LANG_CHOICES, default='any',
                                help_text="Which language this word belongs to")
    notes    = models.CharField(max_length=200, blank=True,
                                help_text="Optional note e.g. 'Swahili for police officer'")
    active   = models.BooleanField(default=True,
                                   help_text="Uncheck to disable without deleting")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['topic', 'word']
        verbose_name = 'Slang Keyword'
        verbose_name_plural = 'Slang Keywords'

    def save(self, *args, **kwargs):
        self.word = self.word.lower().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.word} → {self.get_topic_display()} ({self.get_language_display()})"


class AnswerJob(models.Model):
    """
    Tracks a background AI job so the client can poll for results
    without keeping a long HTTP connection open.

    Lifecycle:  pending → done | error
    """
    STATUS_PENDING = "pending"
    STATUS_DONE    = "done"
    STATUS_ERROR   = "error"

    story   = models.TextField()
    county  = models.CharField(max_length=100, blank=True)
    lang    = models.CharField(max_length=10, default="sw")
    status  = models.CharField(max_length=10, default=STATUS_PENDING)

    # Filled in when status = done
    answer_law      = models.TextField(blank=True)
    answer_simple   = models.TextField(blank=True)
    answer_loophole = models.TextField(blank=True)
    answer_letter   = models.TextField(blank=True)
    is_serious      = models.BooleanField(default=False)
    sources_json    = models.TextField(blank=True)   # JSON list

    # Filled in when status = error
    error_message = models.TextField(blank=True)

    # Link to the full Query record once created
    query = models.ForeignKey(
        Query, null=True, blank=True, on_delete=models.SET_NULL
    )

    created_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Answer Job"
        verbose_name_plural = "Answer Jobs"

    def __str__(self):
        return f"Job #{self.pk} [{self.status}] — {self.story[:50]}"


class Lawyer(models.Model):
    """
    Verified lawyer profile.
    KYC has 3 levels — only verified lawyers appear to Wanjiku.
    """

    # ── KYC Status ───────────────────────────────────────────────────────────
    KYC_PENDING    = 'pending'        # just registered, Level 1 not yet passed
    KYC_L1_PASS    = 'level1_pass'   # LSK format check passed, awaiting docs
    KYC_DOCS       = 'docs_submitted' # documents uploaded, awaiting admin review
    KYC_VERIFIED   = 'verified'       # admin approved — shows on platform
    KYC_REJECTED   = 'rejected'       # admin rejected
    KYC_SUSPENDED  = 'suspended'      # was verified, then suspended
    KYC_CHOICES = [
        (KYC_PENDING,   'Pending — Level 1'),
        (KYC_L1_PASS,   'Level 1 Passed — Awaiting Documents'),
        (KYC_DOCS,      'Documents Submitted — Under Review'),
        (KYC_VERIFIED,  '✅ Verified'),
        (KYC_REJECTED,  '❌ Rejected'),
        (KYC_SUSPENDED, '⚠️ Suspended'),
    ]

    # ── Specialties ───────────────────────────────────────────────────────────
    SPEC_CHOICES = [
        ('employment', 'Employment & Labour'),
        ('criminal',   'Criminal Law'),
        ('land',       'Land & Property'),
        ('family',     'Family & Matrimonial'),
        ('consumer',   'Consumer Protection'),
        ('data',       'Data Protection & Cyber'),
        ('commercial', 'Commercial & Business'),
        ('other',      'Other'),
    ]

    # ── Identity ─────────────────────────────────────────────────────────────
    full_name          = models.CharField(max_length=200)
    email              = models.EmailField(unique=True)
    phone              = models.CharField(max_length=20,
                             help_text="Format: +254XXXXXXXXX")
    whatsapp           = models.CharField(max_length=20, blank=True,
                             help_text="WhatsApp number — clients will be connected here. Format: +254XXXXXXXXX")
    national_id_number = models.CharField(max_length=30, blank=True)

    # ── LSK Credentials ───────────────────────────────────────────────────────
    lsk_number         = models.CharField(max_length=50, unique=True,
                             help_text="Format: P.XXX/XXXX/YYYY e.g. P.105/1234/2024")
    lsk_name           = models.CharField(max_length=200, blank=True,
                             help_text="Full name exactly as it appears on kenyalaw.org LSK register")

    # ── Practice ─────────────────────────────────────────────────────────────
    county             = models.CharField(max_length=100,
                             help_text="Primary county of practice")
    county_secondary   = models.CharField(max_length=100, blank=True,
                             help_text="Second county (optional)")
    specialties        = models.JSONField(default=list,
                             help_text="List of specialty codes e.g. ['employment','land']")
    years_experience   = models.PositiveSmallIntegerField(default=0)
    firm_name          = models.CharField(max_length=200, blank=True)
    bio                = models.TextField(max_length=500, blank=True,
                             help_text="Brief professional bio (max 500 chars)")

    # ── KYC Documents ─────────────────────────────────────────────────────────
    doc_practicing_cert = models.FileField(upload_to='kyc/certs/', blank=True, null=True,
                              help_text="2026 LSK Practicing Certificate (PDF or image)")
    doc_national_id     = models.FileField(upload_to='kyc/ids/', blank=True, null=True,
                              help_text="National ID or Passport (front photo)")
    doc_selfie_with_id  = models.FileField(upload_to='kyc/selfies/', blank=True, null=True,
                              help_text="Selfie holding National ID")
    doc_kra_pin         = models.FileField(upload_to='kyc/kra/', blank=True, null=True,
                              help_text="KRA PIN Certificate")
    doc_video           = models.FileField(upload_to='kyc/videos/', blank=True, null=True,
                              help_text="Optional: short video stating name, LSK number, today's date while holding certificate")
    profile_photo       = models.FileField(upload_to='lawyers/photos/', blank=True, null=True)

    # ── Verification ─────────────────────────────────────────────────────────
    kyc_status          = models.CharField(max_length=20, choices=KYC_CHOICES, default=KYC_PENDING)
    kyc_rejection_reason = models.TextField(blank=True,
                               help_text="Reason sent to lawyer when rejected")
    kyc_notes           = models.TextField(blank=True,
                               help_text="Internal admin notes — not shown to lawyer")
    verified_by         = models.ForeignKey(
                               'auth.User', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='verified_lawyers')
    verified_at         = models.DateTimeField(null=True, blank=True)

    # ── Status ────────────────────────────────────────────────────────────────
    is_active           = models.BooleanField(default=True,
                              help_text="Uncheck to hide from platform without deleting")

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-verified_at', '-created_at']
        verbose_name = 'Lawyer'
        verbose_name_plural = 'Lawyers'

    def __str__(self):
        return f"{self.full_name} ({self.lsk_number}) [{self.kyc_status}]"

    @property
    def is_verified(self):
        return self.kyc_status == self.KYC_VERIFIED and self.is_active

    @property
    def display_phone(self):
        return self.whatsapp or self.phone

    @property
    def specialty_labels(self):
        label_map = dict(self.SPEC_CHOICES)
        return [label_map.get(s, s) for s in (self.specialties or [])]

    def get_whatsapp_link(self, message: str = "") -> str:
        """Generate a wa.me link for connecting to this lawyer."""
        import urllib.parse
        num = self.display_phone.replace('+', '').replace(' ', '')
        if message:
            return f"https://wa.me/{num}?text={urllib.parse.quote(message)}"
        return f"https://wa.me/{num}"


class Lead(models.Model):
    """
    Records when Wanjiku clicks "Connect" to reach a lawyer.
    Links a Query (the legal question) to a Lawyer.
    """
    STATUS_NEW       = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_CLOSED    = 'closed'
    STATUS_CHOICES = [
        ('new',       'New — not yet contacted'),
        ('contacted', 'Lawyer contacted client'),
        ('closed',    'Closed'),
    ]

    query        = models.ForeignKey(Query,  on_delete=models.CASCADE, related_name='leads')
    lawyer       = models.ForeignKey(Lawyer, on_delete=models.CASCADE, related_name='leads')
    user_phone   = models.CharField(max_length=20, blank=True,
                       help_text="Wanjiku's phone — only stored if she consented")
    user_consented = models.BooleanField(default=False)
    status       = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_NEW)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'

    def __str__(self):
        return f"Lead #{self.pk} → {self.lawyer.full_name} | {self.status}"
