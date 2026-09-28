from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from cases.web_views import home, about, ask_web, dashboard
from cases.web_views import lawyer_register, lawyer_documents, lawyer_status
from cases.web_views import lawyers_connect, lawyers_for_query

admin.site.site_header = "HakiMkononi Admin"
admin.site.site_title  = "HakiMkononi"
admin.site.index_title = "Karibu — Manage Laws, Queries & Lawyers"


def api_root(request):
    return JsonResponse({
        "name": "HakiMkononi API",
        "status": "running",
        "endpoints": {
            "ask":      "/api/ask/?q=your+question",
            "feedback": "/api/feedback/",
            "health":   "/api/health/",
        },
    })


urlpatterns = [
    path("",                           home,               name="home"),
    path("ask/",                       ask_web,            name="ask_web"),
    path("about/",                     about,              name="about"),
    path("dashboard/",                 dashboard,          name="dashboard"),
    # Lawyers
    path("lawyers/register/",                       lawyer_register,    name="lawyer_register"),
    path("lawyers/documents/<int:lawyer_id>/",      lawyer_documents,   name="lawyer_documents"),
    path("lawyers/status/<int:lawyer_id>/",         lawyer_status,      name="lawyer_status"),
    path("lawyers/connect/",                        lawyers_connect,    name="lawyers_connect"),
    path("lawyers/for-query/<int:query_id>/",       lawyers_for_query,  name="lawyers_for_query"),
    path("admin/",     admin.site.urls),
    path("api/",   include("cases.urls")),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
