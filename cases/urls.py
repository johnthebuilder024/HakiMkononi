from django.urls import path
from cases import views

urlpatterns = [
    path("submit/",                  views.submit_job,       name="submit_job"),
    path("status/<int:job_id>/",     views.job_status,       name="job_status"),
    path("ask/",                     views.ask_sheria,        name="ask_sheria"),
    path("feedback/",                views.submit_feedback,   name="submit_feedback"),
    path("health/",                  views.health_check,      name="health_check"),
    path("letter-pdf/<int:job_id>/", views.letter_pdf,        name="letter_pdf"),
    path("answer-pdf/<int:job_id>/", views.answer_pdf,        name="answer_pdf"),
    path("whatsapp/",                views.whatsapp_webhook,  name="whatsapp_webhook"),
    path("sms/",                     views.sms_webhook,           name="sms_webhook"),
    path("meta-whatsapp/",           views.meta_whatsapp_webhook, name="meta_whatsapp_webhook"),
    path("transcribe/",              views.transcribe_audio,      name="transcribe_audio"),
    path("court-audio/",             views.court_audio_submit,    name="court_audio_submit"),
    path("court-audio/<int:pk>/",    views.court_audio_status,    name="court_audio_status"),
]
