"""
Views for the trafficking app — Chunk 2 + Chunk 4 complete.

Public:
  submit_report       — report form (GET/POST)
  report_submitted    — confirmation page

Partner dashboard:
  dashboard_login     — access key login
  dashboard_logout    — clear session
  dashboard           — main list (Police sees all, NGO sees all, Researcher redirect)
  report_detail       — single report with full content
  update_status       — POST: change status / add note
  report_pdf          — generate + download PDF of formal report
  researcher_stats    — anonymised aggregate charts (Researcher tier only)

API:
  report_status_api   — poll AI processing status (public, no login needed)
"""

import hashlib
import io
import json
import logging
import threading
from collections import Counter
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    TraffickingReport, TraffickingSuspect,
    TraffickingAccessKey, TraffickingAliasAlert,
)

logger = logging.getLogger(__name__)

COUNTIES = [
    "Baringo","Bomet","Bungoma","Busia","Elgeyo Marakwet","Embu","Garissa",
    "Homa Bay","Isiolo","Kajiado","Kakamega","Kericho","Kiambu","Kilifi",
    "Kirinyaga","Kisii","Kisumu","Kitui","Kwale","Laikipia","Lamu",
    "Machakos","Makueni","Mandera","Marsabit","Meru","Migori","Mombasa",
    "Muranga","Nairobi","Nakuru","Nandi","Narok","Nyandarua","Nyamira",
    "Nyeri","Samburu","Siaya","Taita Taveta","Tana River","Tharaka Nithi",
    "Trans Nzoia","Turkana","Uasin Gishu","Vihiga","Wajir","West Pokot",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_ip_hash(request) -> str:
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '127.0.0.1')
    )
    return hashlib.sha256(ip.encode()).hexdigest()


def _check_rate_limit(ip_hash: str) -> bool:
    key   = f"tip_submit_{ip_hash}"
    count = cache.get(key, 0)
    if count >= 3:
        return False
    cache.set(key, count + 1, timeout=3600)
    return True


def _parse_aliases(alias_text: str) -> list:
    import re
    if not alias_text:
        return []
    parts = re.split(r'[,;\n]+', alias_text)
    return [p.strip() for p in parts if p.strip()]


def _fire_ai_processing(report_id: int):
    def _run():
        try:
            from .ai import process_report
            process_report(report_id)
        except Exception as e:
            logger.error(f"[TIP] AI processing failed for report {report_id}: {e}", exc_info=True)
            TraffickingReport.objects.filter(pk=report_id).update(
                status=TraffickingReport.STATUS_READY
            )
    threading.Thread(target=_run, daemon=True).start()


def _get_partner(request):
    """Return TraffickingAccessKey from session, or None."""
    key_id = request.session.get('trafficking_partner_id')
    if not key_id:
        return None
    try:
        return TraffickingAccessKey.objects.get(pk=key_id, active=True)
    except TraffickingAccessKey.DoesNotExist:
        return None


def _require_partner(request, min_tier=None):
    """
    Check partner login. Returns (partner, None) or (None, redirect_response).
    min_tier: if set, only allow that tier or higher
              hierarchy: police > ngo > researcher
    """
    partner = _get_partner(request)
    if not partner:
        return None, redirect('trafficking:dashboard_login')

    tier_rank = {'police': 3, 'ngo': 2, 'researcher': 1}
    if min_tier and tier_rank.get(partner.tier, 0) < tier_rank.get(min_tier, 0):
        return None, HttpResponse('Access denied.', status=403)

    return partner, None


def _filter_reports_for_partner(partner):
    """Return queryset filtered by partner's county_filter if set."""
    qs = TraffickingReport.objects.prefetch_related('suspects', 'alias_alerts_new')
    if partner.county_filter:
        qs = qs.filter(county_of_origin__iexact=partner.county_filter)
    return qs


# ─────────────────────────────────────────────────────────────────────────────
# Public: Report form
# ─────────────────────────────────────────────────────────────────────────────

def submit_report(request):
    lang = request.GET.get('lang') or request.POST.get('lang') or 'en'
    if lang not in ('sw', 'en'):
        lang = 'en'

    errors    = []
    form_data = {}

    if request.method == 'POST':
        form_data = {
            'story':            request.POST.get('story', '').strip(),
            'aliases':          request.POST.get('aliases', '').strip(),
            'county':           request.POST.get('county', '').strip(),
            'approximate_date': request.POST.get('approximate_date', '').strip(),
            'is_urgent':        bool(request.POST.get('is_urgent')),
            'reporter_contact': request.POST.get('reporter_contact', '').strip(),
        }

        story_words = len(form_data['story'].split()) if form_data['story'] else 0
        if not form_data['story']:
            errors.append("Tafadhali eleza kilichotokea." if lang == 'sw'
                          else "Please describe what happened.")
        elif story_words < 5:
            errors.append("Tafadhali andika zaidi — angalau maneno 5." if lang == 'sw'
                          else "Please write more — at least 5 words.")

        ip_hash = _get_ip_hash(request)
        if not errors and not _check_rate_limit(ip_hash):
            errors.append("Umeshatuma ripoti nyingi. Jaribu tena baada ya saa moja." if lang == 'sw'
                          else "Too many submissions. Please try again in one hour.")

        if not errors:
            is_anonymous = not bool(form_data['reporter_contact'])
            report = TraffickingReport.objects.create(
                story_raw        = form_data['story'],
                story_lang       = lang,
                county_of_origin = form_data['county'],
                approximate_date = form_data['approximate_date'],
                is_urgent        = form_data['is_urgent'],
                reporter_contact = form_data['reporter_contact'],
                is_anonymous     = is_anonymous,
                status           = TraffickingReport.STATUS_PROCESS,
                ip_hash          = ip_hash,
            )
            for alias_text in _parse_aliases(form_data['aliases']):
                TraffickingSuspect.objects.create(
                    report=report, alias=alias_text,
                    alias_type=TraffickingSuspect.ALIAS_UNKNOWN,
                    confidence=TraffickingSuspect.CONF_MEDIUM,
                )
            _fire_ai_processing(report.pk)
            request.session['tip_submitted'] = {
                'report_id':        report.pk,
                'reference_number': report.reference_number,
                'is_urgent':        report.is_urgent,
                'lang':             lang,
            }
            return redirect('trafficking:report_submitted')

    return render(request, 'trafficking/report.html', {
        'lang': lang, 'counties': COUNTIES,
        'errors': errors, 'form_data': form_data,
    })


def report_submitted(request):
    data = request.session.pop('tip_submitted', None)
    if not data:
        return redirect('trafficking:submit_report')
    return render(request, 'trafficking/submitted.html', {
        'reference_number': data.get('reference_number', 'TIP-????'),
        'report_id':        data.get('report_id'),
        'is_urgent':        data.get('is_urgent', False),
        'lang':             data.get('lang', 'en'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def report_status_api(request, pk):
    try:
        report = TraffickingReport.objects.only(
            'status', 'reference_number', 'has_linked_reports'
        ).get(pk=pk)
    except TraffickingReport.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({
        'status':             report.status,
        'reference_number':   report.reference_number,
        'has_linked_reports': report.has_linked_reports,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Partner: Login / Logout
# ─────────────────────────────────────────────────────────────────────────────

def dashboard_login(request):
    error = None
    if request.method == 'POST':
        raw_key = request.POST.get('access_key', '').strip()
        if raw_key:
            key_hash = TraffickingAccessKey.hash_key(raw_key)
            try:
                partner = TraffickingAccessKey.objects.get(
                    access_key_hash=key_hash, active=True
                )
                request.session['trafficking_partner_id'] = partner.pk
                partner.last_used_at = timezone.now()
                partner.save(update_fields=['last_used_at'])
                # Researchers go straight to stats
                if partner.tier == TraffickingAccessKey.TIER_RESEARCHER:
                    return redirect('trafficking:researcher_stats')
                return redirect('trafficking:dashboard')
            except TraffickingAccessKey.DoesNotExist:
                error = "Invalid access key. Please try again."
        else:
            error = "Please enter your access key."

    return render(request, 'trafficking/login.html', {'error': error})


def dashboard_logout(request):
    request.session.pop('trafficking_partner_id', None)
    return redirect('trafficking:dashboard_login')


# ─────────────────────────────────────────────────────────────────────────────
# Partner: Main dashboard
# ─────────────────────────────────────────────────────────────────────────────

def dashboard(request):
    partner, err = _require_partner(request, min_tier='ngo')
    if err:
        return err

    # Researchers can't access the report list
    if partner.tier == TraffickingAccessKey.TIER_RESEARCHER:
        return redirect('trafficking:researcher_stats')

    qs = _filter_reports_for_partner(partner)

    # ── Filters from GET params ──────────────────────────────────────────────
    status_filter  = request.GET.get('status', '')
    county_filter  = request.GET.get('county', '')
    urgent_filter  = request.GET.get('urgent', '')
    type_filter    = request.GET.get('type', '')
    search_query   = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if county_filter:
        qs = qs.filter(county_of_origin__iexact=county_filter)
    if urgent_filter == '1':
        qs = qs.filter(is_urgent=True)
    if type_filter:
        qs = qs.filter(report_type=type_filter)
    if search_query:
        qs = qs.filter(
            Q(story_raw__icontains=search_query) |
            Q(reference_number__icontains=search_query) |
            Q(suspects__alias__icontains=search_query) |
            Q(county_of_origin__icontains=search_query)
        ).distinct()

    reports = qs.order_by('-is_urgent', '-created_at')

    # ── Summary counts ────────────────────────────────────────────────────────
    all_reports = _filter_reports_for_partner(partner)
    counts = {
        'total':        all_reports.count(),
        'urgent':       all_reports.filter(is_urgent=True).count(),
        'new':          all_reports.filter(status='new').count(),
        'ready':        all_reports.filter(status='ready').count(),
        'alias_alerts': TraffickingAliasAlert.objects.filter(
                            report_new__in=all_reports
                        ).count(),
    }

    return render(request, 'trafficking/dashboard.html', {
        'partner':       partner,
        'reports':       reports[:100],
        'counts':        counts,
        'counties':      COUNTIES,
        'status_choices': TraffickingReport.STATUS_CHOICES,
        'type_choices':  TraffickingReport.TYPE_CHOICES,
        # Active filters (to keep dropdowns selected)
        'f_status':  status_filter,
        'f_county':  county_filter,
        'f_urgent':  urgent_filter,
        'f_type':    type_filter,
        'f_q':       search_query,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Partner: Report detail
# ─────────────────────────────────────────────────────────────────────────────

def report_detail(request, pk):
    partner, err = _require_partner(request, min_tier='ngo')
    if err:
        return err

    qs = _filter_reports_for_partner(partner)
    report = get_object_or_404(qs, pk=pk)

    suspects     = report.suspects.all().order_by('-confidence', 'alias_type')
    alias_alerts = TraffickingAliasAlert.objects.filter(
        Q(report_new=report) | Q(report_previous=report)
    ).select_related('report_new', 'report_previous').order_by('-created_at')

    # Police can see reporter contact; NGO only if not anonymous
    show_contact = (
        partner.tier == TraffickingAccessKey.TIER_POLICE
        or (partner.tier == TraffickingAccessKey.TIER_NGO and not report.is_anonymous)
    )

    return render(request, 'trafficking/report_detail.html', {
        'partner':      partner,
        'report':       report,
        'suspects':     suspects,
        'alias_alerts': alias_alerts,
        'show_contact': show_contact,
        'indicators':   report.get_indicators_display_list(),
        'can_update':   partner.can_update_status,
        'status_choices': TraffickingReport.STATUS_CHOICES,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Partner: Update status
# ─────────────────────────────────────────────────────────────────────────────

@require_POST
def update_status(request, pk):
    partner, err = _require_partner(request, min_tier='ngo')
    if err:
        return err

    if not partner.can_update_status:
        return HttpResponse('Not authorised to update status.', status=403)

    qs     = _filter_reports_for_partner(partner)
    report = get_object_or_404(qs, pk=pk)

    new_status = request.POST.get('status', '').strip()
    note       = request.POST.get('status_note', '').strip()

    valid_statuses = [s[0] for s in TraffickingReport.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return HttpResponse('Invalid status.', status=400)

    report.status      = new_status
    report.reviewed_by = partner.organisation
    report.reviewed_at = timezone.now()
    if note:
        report.status_note = note
    report.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'status_note'])

    logger.info(
        f"[TIP] Report {report.reference_number} status → {new_status} "
        f"by {partner.organisation}"
    )
    return redirect('trafficking:report_detail', pk=pk)


# ─────────────────────────────────────────────────────────────────────────────
# Partner: PDF download
# ─────────────────────────────────────────────────────────────────────────────

def report_pdf(request, pk):
    partner, err = _require_partner(request, min_tier='ngo')
    if err:
        return err

    qs     = _filter_reports_for_partner(partner)
    report = get_object_or_404(qs, pk=pk)

    # Build plain-text report — universal, no PDF library needed
    # Partners can print-to-PDF from the browser if they need actual PDF
    show_contact = (
        partner.tier == TraffickingAccessKey.TIER_POLICE
        or (partner.tier == TraffickingAccessKey.TIER_NGO and not report.is_anonymous)
    )

    suspects_text = '\n'.join(
        f"  • {s.alias} ({s.get_alias_type_display()}, confidence: {s.confidence})"
        + (f" — {s.county_context}" if s.county_context else '')
        for s in report.suspects.all()
    ) or '  None extracted'

    indicators_text = '\n'.join(
        f"  • {label}" for label in report.get_indicators_display_list()
    ) or '  None identified'

    contact_text = (
        report.reporter_contact if (show_contact and report.reporter_contact)
        else '[Anonymous — contact not available]'
    )

    lines = [
        "=" * 65,
        "HakiMkononi Anti-Trafficking Report",
        "CONFIDENTIAL — For authorised partners only",
        "=" * 65,
        "",
        f"Reference Number : {report.reference_number}",
        f"Status           : {report.get_status_display()}",
        f"Submitted        : {report.created_at.strftime('%d %B %Y, %H:%M UTC')}",
        f"County           : {report.county_of_origin or 'Not specified'}",
        f"Approximate Date : {report.approximate_date or 'Not specified'}",
        f"Urgent           : {'YES — IMMEDIATE ACTION REQUIRED' if report.is_urgent else 'No'}",
        f"Reporter Contact : {contact_text}",
        "",
        "-" * 65,
        "AI ANALYSIS",
        "-" * 65,
        f"Trafficking Type     : {report.get_report_type_display()}",
        f"Recruitment Method   : {report.get_recruitment_method_display()}",
        f"Victim Profile       : {report.get_victim_profile_display()}",
        f"Destination          : {report.destination or 'Unknown'}",
        "",
        "Indicators Present:",
        indicators_text,
        "",
        "Suspects / Aliases:",
        suspects_text,
        "",
        "-" * 65,
        "RAW REPORT (as submitted)",
        "-" * 65,
        report.story_raw,
        "",
        "-" * 65,
        "FORMAL REPORT (AI-generated, English)",
        "-" * 65,
        report.formal_report_en or '(AI processing not yet complete)',
        "",
        "-" * 65,
        "FORMAL REPORT (AI-generated, Swahili)",
        "-" * 65,
        report.formal_report_sw or '(AI processing not yet complete)',
        "",
        "=" * 65,
        f"Reviewed by      : {report.reviewed_by or 'Not yet reviewed'}",
        f"Reviewed at      : {report.reviewed_at.strftime('%d %B %Y, %H:%M UTC') if report.reviewed_at else '—'}",
        f"Review notes     : {report.status_note or '—'}",
        "=" * 65,
        "",
        "Generated by HakiMkononi Anti-Trafficking System",
        "hakimkononi.onrender.com",
        f"Downloaded by: {partner.organisation} ({partner.get_tier_display()})",
        f"Download time: {timezone.now().strftime('%d %B %Y, %H:%M UTC')}",
    ]

    content  = '\n'.join(lines)
    filename = f"{report.reference_number}.txt"

    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Partner: Researcher stats (anonymised)
# ─────────────────────────────────────────────────────────────────────────────

def researcher_stats(request):
    partner, err = _require_partner(request)
    if err:
        return err

    qs = _filter_reports_for_partner(partner)

    # All counts — no personal data exposed
    total = qs.count()
    urgent_count = qs.filter(is_urgent=True).count()

    # By type
    by_type = dict(
        qs.values('report_type')
          .annotate(n=Count('id'))
          .values_list('report_type', 'n')
    )

    # By recruitment method
    by_recruit = dict(
        qs.values('recruitment_method')
          .annotate(n=Count('id'))
          .values_list('recruitment_method', 'n')
    )

    # By county (top 10)
    by_county = list(
        qs.exclude(county_of_origin='')
          .values('county_of_origin')
          .annotate(n=Count('id'))
          .order_by('-n')[:10]
    )

    # By month (last 12 months)
    twelve_months_ago = timezone.now() - timedelta(days=365)
    by_month = list(
        qs.filter(created_at__gte=twelve_months_ago)
          .extra(select={'month': "date_trunc('month', created_at)"})
          .values('month')
          .annotate(n=Count('id'))
          .order_by('month')
    )

    # Top indicators
    all_indicators = []
    for r in qs.values_list('indicators', flat=True):
        if r:
            all_indicators.extend(r)
    indicator_counts = Counter(all_indicators).most_common(10)

    # Alias alert count
    alert_count = TraffickingAliasAlert.objects.filter(
        report_new__in=qs
    ).count()

    # Pre-process for template bar charts (Django can't do dict lookups with variables)
    max_n = max(by_type.values(), default=1) or 1
    by_type_list = [
        {'code': code, 'label': label, 'n': by_type.get(code, 0),
         'pct': round(by_type.get(code, 0) / max_n * 100)}
        for code, label in TraffickingReport.TYPE_CHOICES
    ]
    max_r = max(by_recruit.values(), default=1) or 1
    by_recruit_list = [
        {'code': code, 'label': label, 'n': by_recruit.get(code, 0),
         'pct': round(by_recruit.get(code, 0) / max_r * 100)}
        for code, label in TraffickingReport.RECRUIT_CHOICES
    ]

    return render(request, 'trafficking/stats.html', {
        'partner':          partner,
        'total':            total,
        'urgent_count':     urgent_count,
        'alert_count':      alert_count,
        'by_type_list':     by_type_list,
        'by_recruit_list':  by_recruit_list,
        'by_county':        by_county,
        'by_month':         by_month,
        'indicator_counts': indicator_counts,
    })
