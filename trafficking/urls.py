"""
URL configuration for the trafficking app.

All URLs are prefixed with /trafficking/ or /report-trafficking/
in sheria_ai/urls.py — nothing here is linked from the main site yet.
"""

from django.urls import path
from . import views

app_name = 'trafficking'

urlpatterns = [
    # ── Public (no login) ────────────────────────────────────────────────────
    # Report submission form — the main entry point
    path('report/',           views.submit_report,    name='submit_report'),
    # Confirmation page after submission (shows reference number)
    path('report/submitted/', views.report_submitted, name='report_submitted'),

    # ── Partner dashboard (requires access key) ───────────────────────────────
    # Login with access key
    path('dashboard/login/',  views.dashboard_login,  name='dashboard_login'),
    path('dashboard/logout/', views.dashboard_logout, name='dashboard_logout'),
    # Main dashboard
    path('dashboard/',        views.dashboard,        name='dashboard'),
    # Single report detail
    path('dashboard/report/<int:pk>/', views.report_detail, name='report_detail'),

    # ── API (internal, called by JS polling) ─────────────────────────────────
    # Poll for AI processing status
    path('api/status/<int:pk>/', views.report_status_api, name='report_status_api'),
]
