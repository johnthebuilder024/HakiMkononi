from django.contrib import admin
from django.utils.html import format_html
from cases.models import Law, Query, SlangKeyword, WhatsAppUser, AnswerJob


@admin.register(Law)
class LawAdmin(admin.ModelAdmin):
    list_display = ['title', 'section', 'category', 'has_swahili', 'has_embedding', 'source_link']
    list_filter = ['category']
    search_fields = ['title', 'section', 'content', 'simple_swahili']
    readonly_fields = ['created_at', 'updated_at', 'has_embedding']
    list_per_page = 50

    fieldsets = (
        ('Section Identity', {
            'fields': ('title', 'section', 'category', 'source_url')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Swahili Translation', {
            'fields': ('simple_swahili',),
            'description': 'Write the plain Swahili meaning here. This is what Wanjiku will read.'
        }),
        ('Connections', {
            'fields': ('related_to',),
            'description': 'Other sections that relate to this one (e.g. Article 47, Section 40)'
        }),
        ('System', {
            'fields': ('has_embedding', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_swahili(self, obj):
        if obj.simple_swahili:
            return format_html('<span style="color:green;">✓ Ipo</span>')
        return format_html('<span style="color:red;">✗ Haipo</span>')
    has_swahili.short_description = 'Swahili'

    def has_embedding(self, obj):
        if obj.embedding_json:
            return format_html('<span style="color:green;">✓ Ready</span>')
        return format_html('<span style="color:orange;">⚠ Run build_embeddings</span>')
    has_embedding.short_description = 'AI Embedding'

    def source_link(self, obj):
        if obj.source_url:
            return format_html('<a href="{}" target="_blank">kenyalaw.org ↗</a>', obj.source_url)
        return '—'
    source_link.short_description = 'Source'

    actions = ['build_embeddings_for_selected']

    def build_embeddings_for_selected(self, request, queryset):
        from cases.rag import embed_text
        count = 0
        for law in queryset:
            if not law.embedding_json:
                text = f"{law.title} {law.section}: {law.content}"
                vector = embed_text(text)
                law.set_embedding(vector)
                law.save(update_fields=['embedding_json'])
                count += 1
        self.message_user(request, f"Built embeddings for {count} law sections.")
    build_embeddings_for_selected.short_description = "Build AI embeddings for selected laws"


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ['pk', 'story_preview', 'county', 'feedback_badge', 'created_at']
    list_filter = ['was_helpful', 'county', 'created_at']
    search_fields = ['story', 'answer_law', 'correct_section']
    readonly_fields = [
        'story', 'county', 'user_identifier', 'answer_law', 'answer_simple',
        'answer_loophole', 'answer_letter', 'raw_answer', 'laws_used', 'created_at'
    ]
    list_per_page = 30

    fieldsets = (
        ('User Story', {
            'fields': ('user_identifier', 'county', 'story', 'created_at')
        }),
        ('AI Answer (Read Only)', {
            'fields': ('answer_law', 'answer_simple', 'answer_loophole', 'answer_letter'),
            'classes': ('collapse',)
        }),
        ('Laws Used', {
            'fields': ('laws_used',)
        }),
        ('Feedback & Correction', {
            'fields': ('was_helpful', 'what_actually_happened', 'correct_section'),
            'description': (
                'When was_helpful is False, review the answer and fill in '
                'correct_section so the AI learns from this mistake.'
            )
        }),
    )

    def story_preview(self, obj):
        return obj.story[:80] + ('...' if len(obj.story) > 80 else '')
    story_preview.short_description = 'Story'

    def feedback_badge(self, obj):
        if obj.was_helpful is True:
            return format_html('<span style="color:green;font-weight:bold;">✓ Ndio</span>')
        elif obj.was_helpful is False:
            return format_html('<span style="color:red;font-weight:bold;">✗ Hapana</span>')
        return format_html('<span style="color:gray;">— Pending</span>')
    feedback_badge.short_description = 'Feedback'


@admin.register(SlangKeyword)
class SlangKeywordAdmin(admin.ModelAdmin):
    list_display  = ['word', 'topic_badge', 'language', 'notes', 'active']
    list_filter   = ['topic', 'language', 'active']
    search_fields = ['word', 'notes']
    list_editable = ['active']
    list_per_page = 100
    ordering      = ['topic', 'word']

    fieldsets = (
        ('Keyword', {
            'fields': ('word', 'topic', 'language', 'active'),
            'description': (
                'Add any slang, vernacular, or street word that signals a legal topic. '
                'Examples: <b>karao</b> → Criminal, <b>sanse</b> → Criminal, '
                '<b>landlord</b> → Land. Words are matched case-insensitively.'
            ),
        }),
        ('Notes', {
            'fields': ('notes',),
        }),
    )

    def topic_badge(self, obj):
        colors = {
            'employment': '#1a7a3c',
            'criminal':   '#9b2226',
            'land':       '#0077b6',
            'family':     '#e07c00',
        }
        color = colors.get(obj.topic, '#666')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:.8em;">{}</span>',
            color, obj.get_topic_display()
        )
    topic_badge.short_description = 'Topic'

    actions = ['activate_keywords', 'deactivate_keywords']

    def activate_keywords(self, request, queryset):
        count = queryset.update(active=True)
        self.message_user(request, f"Activated {count} keywords.")
    activate_keywords.short_description = "Activate selected keywords"

    def deactivate_keywords(self, request, queryset):
        count = queryset.update(active=False)
        self.message_user(request, f"Deactivated {count} keywords.")
    deactivate_keywords.short_description = "Deactivate selected keywords"


# Import SlangKeyword at the top — already imported above


@admin.register(WhatsAppUser)
class WhatsAppUserAdmin(admin.ModelAdmin):
    list_display  = ['phone', 'lang', 'state', 'joined_at']
    list_filter   = ['lang', 'state']
    search_fields = ['phone']
    readonly_fields = ['joined_at', 'updated_at']
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-joined_at')


@admin.register(AnswerJob)
class AnswerJobAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'story_preview', 'lang', 'status_badge', 'created_at']
    list_filter   = ['status', 'lang', 'created_at']
    search_fields = ['story']
    readonly_fields = [
        'story', 'county', 'lang', 'status', 'answer_law', 'answer_simple',
        'answer_loophole', 'answer_letter', 'sources_json', 'error_message',
        'query', 'created_at', 'finished_at',
    ]
    list_per_page = 30

    def story_preview(self, obj):
        return obj.story[:80] + ('...' if len(obj.story) > 80 else '')
    story_preview.short_description = 'Story'

    def status_badge(self, obj):
        colors = {'pending': 'orange', 'done': 'green', 'error': 'red'}
        color  = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'


from cases.models import Lawyer, Lead
from django.utils import timezone


@admin.register(Lawyer)
class LawyerAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'lsk_number', 'county', 'specialties_display',
                     'kyc_badge', 'is_active', 'created_at']
    list_filter   = ['kyc_status', 'is_active', 'county']
    search_fields = ['full_name', 'email', 'lsk_number', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'verified_at', 'verified_by']
    list_per_page = 30
    list_editable = ['is_active']

    fieldsets = (
        ('👤 Identity', {
            'fields': ('full_name', 'email', 'phone', 'whatsapp', 'telegram_username', 'national_id_number'),
        }),
        ('⚖️ LSK Credentials', {
            'fields': ('lsk_number', 'lsk_name'),
            'description': (
                'Verify LSK number at: '
                '<a href="https://kenyalaw.org/kl/index.php?id=7066" target="_blank">'
                'kenyalaw.org LSK Register ↗</a>'
            ),
        }),
        ('📍 Practice Details', {
            'fields': ('county', 'county_secondary', 'specialties',
                       'years_experience', 'firm_name', 'bio'),
        }),
        ('📄 KYC Documents', {
            'fields': ('doc_practicing_cert', 'doc_national_id',
                       'doc_selfie_with_id', 'doc_kra_pin', 'doc_video',
                       'profile_photo'),
            'description': (
                '<strong>Checklist before verifying:</strong><br>'
                '✅ Practicing cert shows current year (2026) + LSK stamp<br>'
                '✅ Name on cert matches name in application<br>'
                '✅ National ID photo is clear and readable<br>'
                '✅ Selfie clearly shows person holding the same ID<br>'
                '✅ LSK number on cert matches lsk_number field<br>'
                '✅ KRA PIN confirms same name/firm'
            ),
        }),
        ('🔍 Verification', {
            'fields': ('kyc_status', 'kyc_rejection_reason', 'kyc_notes',
                       'verified_by', 'verified_at', 'is_active'),
        }),
        ('🕒 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def kyc_badge(self, obj):
        colors = {
            'pending':       '#888',
            'level1_pass':   '#0077b6',
            'docs_submitted':'#e07c00',
            'verified':      '#1a7a3c',
            'rejected':      '#dc3545',
            'suspended':     '#6c757d',
        }
        labels = {
            'pending':       '⏳ Pending',
            'level1_pass':   '📋 Awaiting Docs',
            'docs_submitted':'📄 Under Review',
            'verified':      '✅ Verified',
            'rejected':      '❌ Rejected',
            'suspended':     '⚠️ Suspended',
        }
        color = colors.get(obj.kyc_status, '#888')
        label = labels.get(obj.kyc_status, obj.kyc_status)
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:10px;font-size:.8em;font-weight:600;">{}</span>',
            color, label
        )
    kyc_badge.short_description = 'KYC Status'

    def specialties_display(self, obj):
        specs = obj.specialties or []
        return ', '.join(specs[:3]) + ('…' if len(specs) > 3 else '')
    specialties_display.short_description = 'Specialties'

    actions = ['verify_lawyers', 'reject_lawyers', 'suspend_lawyers', 'activate_lawyers']

    def verify_lawyers(self, request, queryset):
        count = 0
        for lawyer in queryset.filter(kyc_status='docs_submitted'):
            lawyer.kyc_status  = 'verified'
            lawyer.verified_by = request.user
            lawyer.verified_at = timezone.now()
            lawyer.save(update_fields=['kyc_status', 'verified_by', 'verified_at'])
            # Send password setup email so lawyer can access their dashboard
            try:
                from cases.web_views import _send_password_setup_link
                _send_password_setup_link(lawyer)
            except Exception as e:
                print(f"[LAWYER] Could not send setup email: {e}")
            count += 1
        self.message_user(request, f"✅ Verified {count} lawyers. Password setup emails sent.")
    verify_lawyers.short_description = "✅ Mark selected as VERIFIED"

    def reject_lawyers(self, request, queryset):
        count = 0
        for lawyer in queryset.exclude(kyc_status='verified'):
            lawyer.kyc_status = 'rejected'
            lawyer.save(update_fields=['kyc_status'])
            # Notify the lawyer of rejection
            try:
                from cases.web_views import _send_rejection_notification
                _send_rejection_notification(lawyer)
            except Exception as e:
                print(f"[LAWYER] Could not send rejection email: {e}")
            count += 1
        self.message_user(request, f"❌ Rejected {count} lawyers. Notification emails sent.")
    reject_lawyers.short_description = "❌ Mark selected as REJECTED"

    def suspend_lawyers(self, request, queryset):
        count = queryset.filter(kyc_status='verified').update(kyc_status='suspended')
        self.message_user(request, f"⚠️ Suspended {count} lawyers.")
    suspend_lawyers.short_description = "⚠️ Suspend selected lawyers"

    def activate_lawyers(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} lawyers.")
    activate_lawyers.short_description = "Activate selected lawyers"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'lawyer_name', 'query_preview', 'status', 'user_consented', 'created_at']
    list_filter   = ['status', 'user_consented', 'created_at']
    search_fields = ['lawyer__full_name', 'query__story', 'user_phone']
    readonly_fields = ['query', 'lawyer', 'user_phone', 'user_consented', 'created_at']
    list_per_page = 30

    def lawyer_name(self, obj):
        return obj.lawyer.full_name
    lawyer_name.short_description = 'Lawyer'

    def query_preview(self, obj):
        return obj.query.story[:60] + '...' if len(obj.query.story) > 60 else obj.query.story
    query_preview.short_description = 'Question'


from cases.models import CaseAudio, Testimonial, LawyerPublicAnswer


@admin.register(CaseAudio)
class CaseAudioAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'court_station', 'lang', 'status', 'created_at']
    list_filter   = ['status', 'lang']
    readonly_fields = ['transcript', 'summary', 'status', 'error_message', 'created_at', 'finished_at']
    list_per_page = 30


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display  = ['name', 'county', 'case_type', 'approved', 'created_at']
    list_filter   = ['approved', 'case_type', 'lang']
    search_fields = ['name', 'story', 'county']
    list_editable = ['approved']
    readonly_fields = ['created_at']
    list_per_page = 30


@admin.register(LawyerPublicAnswer)
class LawyerPublicAnswerAdmin(admin.ModelAdmin):
    list_display  = ['lawyer_name', 'question_preview', 'approved', 'created_at']
    list_filter   = ['approved', 'lang']
    search_fields = ['lawyer__full_name', 'question', 'answer']
    list_editable = ['approved']
    readonly_fields = ['lawyer', 'created_at', 'updated_at']
    list_per_page = 30

    def lawyer_name(self, obj):
        return obj.lawyer.full_name
    lawyer_name.short_description = 'Lawyer'

    def question_preview(self, obj):
        return obj.question[:70] + ('...' if len(obj.question) > 70 else '')
    question_preview.short_description = 'Question'


from cases.models import LawyerReport


@admin.register(LawyerReport)
class LawyerReportAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'lawyer_name', 'reason_preview', 'reviewed', 'created_at']
    list_filter   = ['reviewed', 'created_at']
    search_fields = ['lawyer__full_name', 'reason']
    list_editable = ['reviewed']
    readonly_fields = ['lawyer', 'lead', 'reason', 'contact_info', 'created_at']
    list_per_page = 30

    def lawyer_name(self, obj):
        return format_html(
            '<a href="/admin/cases/lawyer/{}/change/">{}</a>',
            obj.lawyer.pk, obj.lawyer.full_name
        )
    lawyer_name.short_description = 'Lawyer'

    def reason_preview(self, obj):
        return obj.reason[:80] + ('…' if len(obj.reason) > 80 else '')
    reason_preview.short_description = 'Reason'


# Extend the existing LeadAdmin to show rating and report info
# (Re-register with extra fields)
admin.site.unregister(Lead)

@admin.register(Lead)
class LeadAdminV2(admin.ModelAdmin):
    list_display  = ['pk', 'lawyer_name', 'query_preview', 'status', 'rating', 'reported', 'user_consented', 'created_at']
    list_filter   = ['status', 'user_consented', 'reported', 'created_at']
    search_fields = ['lawyer__full_name', 'query__story', 'user_phone']
    readonly_fields = ['query', 'lawyer', 'user_phone', 'user_consented', 'rating', 'rating_text', 'rating_at', 'reported', 'report_reason', 'report_at', 'created_at']
    list_per_page = 30

    def lawyer_name(self, obj):
        return obj.lawyer.full_name
    lawyer_name.short_description = 'Lawyer'

    def query_preview(self, obj):
        return obj.query.story[:60] + '...' if len(obj.query.story) > 60 else obj.query.story
    query_preview.short_description = 'Question'
