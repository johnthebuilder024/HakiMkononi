"""
Views for the trafficking app — Chunk 2.

Public views:
  submit_report    — GET: show form / POST: save report + fire AI
  report_submitted — confirmation page with reference number

Partner dashboard views (stubs for Chunk 4):
  dashboard_login, dashboard_logout, dashboard, report_detail

API:
  report_status_api — polls AI processing status
"""

import hashlib
import json
import threading
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.utils import timezone

from .models import TraffickingReport, TraffickingAccessKey

logger = logging.getLogger(__name__)

# ── Kenyan counties ────────────────────────────────────────────────────────────
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
    """Return SHA256 of the request IP — not reversible, safe to store."""
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '127.0.0.1')
    )
    return hashlib.sha256(ip.encode()).hexdigest()


def _check_rate_limit(ip_hash: str) -> bool:
    """
    Allow max 3 report submissions per IP hash per hour.
    Returns True if allowed, False if rate-limited.
    """
    key   = f"tip_submit_{ip_hash}"
    count = cache.get(key, 0)
    if count >= 3:
        return False
    cache.set(key, count + 1, timeout=3600)
    return True


def _parse_aliases(alias_text: str) -> list:
    """
    Parse the aliases field — comma or newline separated.
    Returns list of non-empty stripped strings.
    """
    if not alias_text:
        return []
    # Split on comma, semicolon or newline
    import re
    parts = re.split(r'[,;\n]+', alias_text)
    return [p.strip() for p in parts if p.strip()]


def _fire_ai_processing(report_id: int):
    """
    Fire the AI processing in a background thread.
    Chunk 3 will replace the stub inside trafficking/ai.py with the real Groq call.
    """
    def _run():
        try:
            from .ai import process_report
            process_report(report_id)
        except ImportError:
            # ai.py not yet built (Chunk 3) — mark as ready without AI processing
            TraffickingReport.objects.filter(pk=report_id).update(
                status=TraffickingReport.STATUS_READY
            )
        except Exception as e:
            logger.error(f"[TIP] AI processing failed for report {report_id}: {e}", exc_info=True)
            TraffickingReport.objects.filter(pk=report_id).update(
                status=TraffickingReport.STATUS_READY  # still usable, just not AI-structured
            )

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ─────────────────────────────────────────────────────────────────────────────
# Public: Report submission form
# ─────────────────────────────────────────────────────────────────────────────

def submit_report(request):
    """
    GET  — display the report form
    POST — validate, save report, fire AI processing, redirect to confirmation
    """
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

        # ── Validation ──────────────────────────────────────────────────────
        story_words = len(form_data['story'].split()) if form_data['story'] else 0
        if not form_data['story']:
            errors.append(
                "Tafadhali eleza kilichotokea." if lang == 'sw'
                else "Please describe what happened."
            )
        elif story_words < 5:
            errors.append(
                "Tafadhali andika zaidi — angalau maneno 5." if lang == 'sw'
                else "Please write more — at least 5 words."
            )

        # ── Rate limiting ────────────────────────────────────────────────────
        ip_hash = _get_ip_hash(request)
        if not errors and not _check_rate_limit(ip_hash):
            errors.append(
                "Umeshatuma ripoti nyingi. Tafadhali jaribu tena baada ya saa moja." if lang == 'sw'
                else "You have submitted too many reports. Please try again in one hour."
            )

        if not errors:
            # ── Save the report ──────────────────────────────────────────────
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

            # ── Save raw aliases as suspects (Chunk 3 will run AI on them too) ──
            from .models import TraffickingSuspect
            for alias_text in _parse_aliases(form_data['aliases']):
                TraffickingSuspect.objects.create(
                    report      = report,
                    alias       = alias_text,
                    alias_type  = TraffickingSuspect.ALIAS_UNKNOWN,
                    confidence  = TraffickingSuspect.CONF_MEDIUM,
                )

            # ── Fire AI processing in background ────────────────────────────
            _fire_ai_processing(report.pk)

            # ── Store reference in session so confirmation page can show it ─
            request.session['tip_submitted'] = {
                'report_id':        report.pk,
                'reference_number': report.reference_number,
                'is_urgent':        report.is_urgent,
                'lang':             lang,
            }

            return redirect('trafficking:report_submitted')

    return render(request, 'trafficking/report.html', {
        'lang':      lang,
        'counties':  COUNTIES,
        'errors':    errors,
        'form_data': form_data,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Public: Confirmation page
# ─────────────────────────────────────────────────────────────────────────────

def report_submitted(request):
    """
    Shown after a successful submission.
    Reads reference number from session — prevents refresh re-submission.
    """
    data = request.session.pop('tip_submitted', None)

    if not data:
        # Direct access without submission — redirect to form
        return redirect('trafficking:submit_report')

    return render(request, 'trafficking/submitted.html', {
        'reference_number': data.get('reference_number', 'TIP-????'),
        'report_id':        data.get('report_id'),
        'is_urgent':        data.get('is_urgent', False),
        'lang':             data.get('lang', 'en'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# API: Poll AI processing status
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def report_status_api(request, pk):
    """
    GET /report-trafficking/api/status/<pk>/

    Returns processing status — used by the confirmation page to show
    when AI has finished structuring the report.
    Only returns non-sensitive fields (no story text, no contact).
    """
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
# Partner dashboard (Chunk 4 stubs)
# ─────────────────────────────────────────────────────────────────────────────

def _get_partner(request):
    """
    Check session for a valid partner login.
    Returns TraffickingAccessKey or None.
    """
    key_id = request.session.get('trafficking_partner_id')
    if not key_id:
        return None
    try:
        partner = TraffickingAccessKey.objects.get(pk=key_id, active=True)
        return partner
    except TraffickingAccessKey.DoesNotExist:
        return None


def dashboard_login(request):
    """Partner login with access key. Full implementation in Chunk 4."""
    lang = request.GET.get('lang', 'en')
    error = None

    if request.method == 'POST':
        raw_key = request.POST.get('access_key', '').strip()
        if raw_key:
            key_hash = TraffickingAccessKey.hash_key(raw_key)
            try:
                partner = TraffickingAccessKey.objects.get(
                    access_key_hash=key_hash, active=True
                )
                # Valid — save to session
                request.session['trafficking_partner_id'] = partner.pk
                partner.last_used_at = timezone.now()
                partner.save(update_fields=['last_used_at'])
                return redirect('trafficking:dashboard')
            except TraffickingAccessKey.DoesNotExist:
                error = (
                    "Ufunguo batili. Jaribu tena." if lang == 'sw'
                    else "Invalid access key. Please try again."
                )
        else:
            error = (
                "Ingiza ufunguo wa ufikiaji." if lang == 'sw'
                else "Please enter your access key."
            )

    return render(request, 'trafficking/login.html', {
        'lang': lang,
        'error': error,
    })


def dashboard_logout(request):
    """Clear partner session."""
    request.session.pop('trafficking_partner_id', None)
    return redirect('trafficking:dashboard_login')


def dashboard(request):
    """Main partner dashboard. Full implementation in Chunk 4."""
    partner = _get_partner(request)
    if not partner:
        return redirect('trafficking:dashboard_login')

    return render(request, 'trafficking/dashboard.html', {
        'partner': partner,
        'lang': 'en',
        'coming_soon': True,
    })


def report_detail(request, pk):
    """Single report detail. Full implementation in Chunk 4."""
    partner = _get_partner(request)
    if not partner:
        return redirect('trafficking:dashboard_login')

    report = get_object_or_404(TraffickingReport, pk=pk)
    return render(request, 'trafficking/report_detail.html', {
        'report': report,
        'partner': partner,
        'lang': 'en',
        'coming_soon': True,
    })
