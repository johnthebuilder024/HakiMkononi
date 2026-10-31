"""
Views for the trafficking app.

Chunk 1: stub views only — return simple responses.
Real implementation in Chunks 2, 3, 4.
"""

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import TraffickingReport, TraffickingAccessKey


# ─────────────────────────────────────────────────────────────────────────────
# Public views (Chunk 2 will flesh these out fully)
# ─────────────────────────────────────────────────────────────────────────────

def submit_report(request):
    """
    GET  — show the report submission form
    POST — save the report and redirect to confirmation page

    Full implementation in Chunk 2.
    """
    if request.method == 'POST':
        # Stub: will be replaced with full form processing in Chunk 2
        return redirect('trafficking:report_submitted')
    # Stub: will be replaced with full template in Chunk 2
    return HttpResponse(
        '<h2>Anti-Trafficking Report Form</h2>'
        '<p>Coming in Chunk 2. Models and admin are ready.</p>'
        '<p>You can already see reports at <a href="/admin/trafficking/">/admin/trafficking/</a></p>',
        content_type='text/html'
    )


def report_submitted(request):
    """
    Confirmation page shown after a report is submitted.
    Full implementation in Chunk 2.
    """
    return HttpResponse(
        '<h2>Report Received</h2>'
        '<p>Thank you. Coming in Chunk 2.</p>',
        content_type='text/html'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Partner dashboard views (Chunk 4 will flesh these out fully)
# ─────────────────────────────────────────────────────────────────────────────

def dashboard_login(request):
    """Partner login with access key. Full implementation in Chunk 4."""
    return HttpResponse(
        '<h2>Partner Dashboard Login</h2>'
        '<p>Coming in Chunk 4.</p>',
        content_type='text/html'
    )


def dashboard_logout(request):
    """Clear partner session. Full implementation in Chunk 4."""
    request.session.pop('trafficking_partner', None)
    return redirect('trafficking:dashboard_login')


def dashboard(request):
    """Main partner dashboard. Full implementation in Chunk 4."""
    return HttpResponse(
        '<h2>Partner Dashboard</h2>'
        '<p>Coming in Chunk 4.</p>',
        content_type='text/html'
    )


def report_detail(request, pk):
    """Single report detail view. Full implementation in Chunk 4."""
    report = get_object_or_404(TraffickingReport, pk=pk)
    return HttpResponse(
        f'<h2>Report {report.reference_number}</h2>'
        f'<p>Status: {report.status}</p>'
        f'<p>Coming in Chunk 4.</p>',
        content_type='text/html'
    )


# ─────────────────────────────────────────────────────────────────────────────
# API view (Chunk 3 will flesh this out)
# ─────────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def report_status_api(request, pk):
    """
    GET /trafficking/api/status/<pk>/
    Returns current processing status of a report.
    Used by the confirmation page to poll for AI processing completion.
    Full implementation in Chunk 3.
    """
    try:
        report = TraffickingReport.objects.get(pk=pk)
        return JsonResponse({
            'status': report.status,
            'reference_number': report.reference_number,
            'has_linked_reports': report.has_linked_reports,
        })
    except TraffickingReport.DoesNotExist:
        return JsonResponse({'error': 'Report not found'}, status=404)
