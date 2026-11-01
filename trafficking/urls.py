"""
URL configuration for the trafficking app.

All URLs are prefixed with /report-trafficking/
in sheria_ai/urls.py — nothing linked from main site yet.
"""

from django.urls import path
from . import views

app_name = 'trafficking'

urlpatterns = [
    # ── Public (no login) ────────────────────────────────────────────────────
    path('report/',           views.submit_report,     name='submit_report'),
    path('report/submitted/', views.report_submitted,  name='report_submitted'),
    path('',                  views.resource_page,     name='resource_page'),

    # ── Partner dashboard ────────────────────────────────────────────────────
    path('dashboard/login/',               views.dashboard_login,   name='dashboard_login'),
    path('dashboard/logout/',              views.dashboard_logout,  name='dashboard_logout'),
    path('dashboard/',                     views.dashboard,         name='dashboard'),
    path('dashboard/report/<int:pk>/',     views.report_detail,     name='report_detail'),
    path('dashboard/report/<int:pk>/update-status/', views.update_status, name='update_status'),
    path('dashboard/report/<int:pk>/pdf/', views.report_pdf,        name='report_pdf'),
    path('dashboard/stats/',               views.researcher_stats,  name='researcher_stats'),

    # ── Internal API ─────────────────────────────────────────────────────────
    path('api/status/<int:pk>/',           views.report_status_api, name='report_status_api'),
]
