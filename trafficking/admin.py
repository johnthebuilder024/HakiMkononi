"""
Django admin for the trafficking app.

Gives the platform owner (you) full visibility into all reports,
suspects, partner keys and alias alerts — before NGO/DCI partners
have their own dashboard (built in Chunk 4).
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    TraffickingReport,
    TraffickingSuspect,
    TraffickingAccessKey,
    TraffickingAliasAlert,
)


# ─────────────────────────────────────────────────────────────────────────────
# Inline: Suspects inside a Report
# ─────────────────────────────────────────────────────────────────────────────

class TraffickingSuspectInline(admin.TabularInline):
    model       = TraffickingSuspect
    extra       = 0
    fields      = ('alias', 'alias_type', 'alias_normalized',
                   'county_context', 'confidence')
    readonly_fields = ('alias_normalized',)
    show_change_link = True


class TraffickingAliasAlertInlineNew(admin.TabularInline):
    """Alias alerts where this report is the NEW one."""
    model           = TraffickingAliasAlert
    fk_name         = 'report_new'
    extra           = 0
    readonly_fields = ('alias', 'match_type', 'report_previous', 'alert_sent')
    fields          = ('alias', 'match_type', 'report_previous', 'alert_sent')
    verbose_name    = 'Alias Match (this is the newer report)'
    verbose_name_plural = 'Alias Matches (this is the newer report)'
    can_delete      = False


# ─────────────────────────────────────────────────────────────────────────────
# TraffickingReport admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(TraffickingReport)
class TraffickingReportAdmin(admin.ModelAdmin):
    list_display  = (
        'reference_number', 'urgent_badge', 'report_type',
        'county_of_origin', 'status_badge', 'alias_match_badge',
        'created_at',
    )
    list_filter   = (
        'is_urgent', 'report_type', 'status',
        'county_of_origin', 'has_linked_reports',
        'recruitment_method', 'victim_profile',
    )
    search_fields = (
        'story_raw', 'reference_number',
        'suspects__alias', 'county_of_origin', 'destination',
    )
    readonly_fields = (
        'reference_number', 'ip_hash', 'created_at', 'updated_at',
        'formal_report_en', 'formal_report_sw', 'has_linked_reports',
    )
    ordering      = ('-is_urgent', '-created_at')
    date_hierarchy = 'created_at'
    inlines       = [TraffickingSuspectInline, TraffickingAliasAlertInlineNew]

    fieldsets = (
        ('🚨 Urgency & Status', {
            'fields': (
                'reference_number', 'is_urgent', 'status',
                'status_note', 'reviewed_by', 'reviewed_at',
            ),
        }),
        ('📝 Raw Submission', {
            'fields': (
                'story_raw', 'story_lang', 'county_of_origin',
                'approximate_date', 'is_anonymous', 'reporter_contact',
            ),
        }),
        ('🤖 AI Analysis', {
            'fields': (
                'report_type', 'recruitment_method', 'indicators',
                'victim_profile', 'destination',
            ),
        }),
        ('📄 Formal Reports (AI-generated)', {
            'fields': ('formal_report_en', 'formal_report_sw'),
            'classes': ('collapse',),
        }),
        ('🔗 Cross-report Links', {
            'fields': ('has_linked_reports',),
        }),
        ('⚙️ System', {
            'fields': ('ip_hash', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def urgent_badge(self, obj):
        if obj.is_urgent:
            return format_html(
                '<span style="background:#dc3545;color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:.8rem;font-weight:700;">🚨 URGENT</span>'
            )
        return format_html(
            '<span style="color:#aaa;font-size:.8rem;">—</span>'
        )
    urgent_badge.short_description = 'Urgency'

    def status_badge(self, obj):
        colours = {
            'new':          ('#0077b6', '🆕 New'),
            'processing':   ('#f77f00', '⏳ Processing'),
            'ready':        ('#2a9d8f', '✅ Ready'),
            'under_review': ('#6d6875', '👁️ Reviewing'),
            'actioned':     ('#1a7a3c', '⚡ Actioned'),
            'closed':       ('#555',    '🔒 Closed'),
            'false_report': ('#999',    '❌ False'),
        }
        colour, label = colours.get(obj.status, ('#999', obj.status))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:.8rem;">{}</span>',
            colour, label
        )
    status_badge.short_description = 'Status'

    def alias_match_badge(self, obj):
        if obj.has_linked_reports:
            return format_html(
                '<span style="background:#ffc107;color:#000;padding:2px 8px;'
                'border-radius:10px;font-size:.8rem;font-weight:700;">⚠️ ALIAS MATCH</span>'
            )
        return '—'
    alias_match_badge.short_description = 'Alias Links'

    actions = ['mark_urgent', 'mark_actioned', 'mark_false_report']

    def mark_urgent(self, request, queryset):
        queryset.update(is_urgent=True)
        self.message_user(request, f"{queryset.count()} report(s) marked as URGENT.")
    mark_urgent.short_description = '🚨 Mark selected as URGENT'

    def mark_actioned(self, request, queryset):
        queryset.update(
            status=TraffickingReport.STATUS_ACTIONED,
            reviewed_by='Admin',
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{queryset.count()} report(s) marked as actioned.")
    mark_actioned.short_description = '⚡ Mark selected as Actioned'

    def mark_false_report(self, request, queryset):
        queryset.update(status=TraffickingReport.STATUS_FALSE)
        self.message_user(request, f"{queryset.count()} report(s) marked as false/spam.")
    mark_false_report.short_description = '❌ Mark selected as False/Spam'


# ─────────────────────────────────────────────────────────────────────────────
# TraffickingSuspect admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(TraffickingSuspect)
class TraffickingSuspectAdmin(admin.ModelAdmin):
    list_display  = (
        'alias', 'alias_type', 'alias_normalized',
        'county_context', 'confidence', 'report_link', 'created_at',
    )
    list_filter   = ('alias_type', 'confidence', 'county_context')
    search_fields = ('alias', 'alias_normalized', 'county_context',
                     'report__reference_number')
    readonly_fields = ('alias_normalized', 'created_at', 'report_link')
    ordering      = ('-created_at',)

    def report_link(self, obj):
        return format_html(
            '<a href="/admin/trafficking/traffickingreport/{}/change/">{}</a>',
            obj.report_id, obj.report.reference_number
        )
    report_link.short_description = 'Report'


# ─────────────────────────────────────────────────────────────────────────────
# TraffickingAccessKey admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(TraffickingAccessKey)
class TraffickingAccessKeyAdmin(admin.ModelAdmin):
    list_display  = (
        'organisation', 'tier', 'county_filter',
        'can_update_status', 'active', 'last_used_at',
    )
    list_filter   = ('tier', 'active')
    search_fields = ('organisation', 'email_alerts')
    readonly_fields = ('access_key_hash', 'last_used_at', 'created_at', 'generated_key_display')
    ordering      = ('tier', 'organisation')

    fieldsets = (
        ('Organisation', {
            'fields': ('organisation', 'tier', 'county_filter'),
        }),
        ('Permissions', {
            'fields': ('can_update_status', 'active', 'email_alerts'),
        }),
        ('Access Key', {
            'fields': ('access_key_hash', 'generated_key_display'),
            'description': (
                'To create a new access key: save the record first, '
                'then use the Django shell: '
                'key = TraffickingAccessKey.generate_key(); '
                'obj.access_key_hash = TraffickingAccessKey.hash_key(key); '
                'obj.save() — then give the key to the partner.'
            ),
        }),
        ('Activity', {
            'fields': ('last_used_at', 'created_at'),
        }),
    )

    def generated_key_display(self, obj):
        return format_html(
            '<em style="color:#888;">Generate in Django shell: '
            'TraffickingAccessKey.generate_key()</em>'
        )
    generated_key_display.short_description = 'Generate key'


# ─────────────────────────────────────────────────────────────────────────────
# TraffickingAliasAlert admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(TraffickingAliasAlert)
class TraffickingAliasAlertAdmin(admin.ModelAdmin):
    list_display  = (
        'alias', 'match_type', 'report_new_link',
        'report_previous_link', 'alert_sent', 'created_at',
    )
    list_filter   = ('match_type', 'alert_sent')
    search_fields = ('alias', 'report_new__reference_number',
                     'report_previous__reference_number')
    readonly_fields = (
        'alias', 'match_type', 'report_new', 'report_previous',
        'suspect_new', 'suspect_previous', 'alert_sent_at', 'created_at',
    )
    ordering      = ('-created_at',)

    def report_new_link(self, obj):
        return format_html(
            '<a href="/admin/trafficking/traffickingreport/{}/change/">{}</a>',
            obj.report_new_id, obj.report_new.reference_number
        )
    report_new_link.short_description = 'New report'

    def report_previous_link(self, obj):
        return format_html(
            '<a href="/admin/trafficking/traffickingreport/{}/change/">{}</a>',
            obj.report_previous_id, obj.report_previous.reference_number
        )
    report_previous_link.short_description = 'Previous report'
