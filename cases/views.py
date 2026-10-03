"""
API views for HakiMkononi.

Endpoints:
  POST /api/submit/             — kick off a background AI job, return job_id immediately
  GET  /api/status/<job_id>/    — poll for job result
  POST /api/ask/                — legacy synchronous endpoint (kept for direct API use)
  POST /api/feedback/           — save user feedback on an answer
  GET  /api/health/             — server health check
  GET  /api/letter-pdf/<id>/    — download demand letter as PDF
  GET  /api/answer-pdf/<id>/    — download full answer as PDF
  POST /api/whatsapp/           — Twilio WhatsApp webhook (sandbox bot)
"""

import json
import re
import threading
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from cases.models import Law, Query, AnswerJob
from cases.rag import find_relevant_laws
from cases.ai_engine import get_answer, is_serious_criminal


# ── Conversation memory helpers (mirrors telegram_bot.py) ────────────────────

_CORRECTION_SIGNALS = {
    # English
    'actually', 'wait', 'no wait', 'sorry', 'i meant', 'i mean',
    'correction', 'not that', 'let me correct', 'i made a mistake',
    'ignore that', 'forget that', 'scratch that', 'not exactly',
    'to clarify', 'let me clarify', 'what i meant', 'actually no',
    # Swahili
    'siyo', 'hapana', 'nilimaanisha', 'nilikuwa nasema', 'acha',
    'samahani', 'sahihisha', 'kwa kweli', 'kweli ni', 'badala yake',
    'nilikosea', 'si hivyo', 'namaanisha', 'ukweli ni',
}

_FOLLOWUP_SIGNALS = {
    # English
    'what about', 'and', 'also', 'but', 'how about', 'what if',
    'can i', 'do i', 'is it', 'so', 'then', 'okay so', 'ok so',
    'what happens', 'and if', 'does that mean', 'so i can',
    'what else', 'anything else', 'more', 'tell me more', 'elaborate',
    # Swahili
    'na', 'lakini', 'vipi', 'je', 'sawa basi', 'na kama',
    'pia', 'zaidi', 'eleza zaidi', 'endelea', 'basi', 'sasa',
    'kisha', 'halafu', 'je niaweza', 'ninaweza',
}

_THANKS = {
    'thanks', 'thank you', 'thank you so much', 'thanks a lot',
    'asante', 'asante sana', 'nashukuru', 'shukrani', 'sawa asante',
    'nimeshukuru', 'appreciated', 'helpful', 'that helped', 'you helped me',
    'umesaidia', 'great', 'wonderful', 'excellent', 'perfect', 'amazing',
}

_GREETINGS = {
    'hello', 'hi', 'hey', 'habari', 'habari yako', 'sasa', 'mambo',
    'niaje', 'vipi', 'sup', 'hola', 'salamu', 'good morning',
    'good afternoon', 'good evening', 'ok', 'okay', 'sawa',
}


def _detect_correction(message: str) -> bool:
    msg = message.lower().strip()
    for signal in _CORRECTION_SIGNALS:
        if msg.startswith(signal + ' ') or msg.startswith(signal + ',') or msg == signal:
            return True
    return False


def _detect_followup(message: str, has_history: bool) -> bool:
    if not has_history:
        return False
    msg = message.lower().strip()
    if len(message.strip()) < 40:
        return True
    for signal in _FOLLOWUP_SIGNALS:
        if msg.startswith(signal + ' ') or msg.startswith(signal + ','):
            return True
    return False


def _build_rag_query(message: str, history: list, is_correction: bool) -> str:
    """Enrich short/follow-up messages with prior context for better RAG results."""
    if not history:
        return message
    last_user = ''
    for turn in reversed(history):
        if turn.get('role') == 'user':
            last_user = turn['content']
            break
    if not last_user:
        return message
    if is_correction:
        return f"{last_user} — correction: {message}"
    return f"{last_user}. {message}"


def _summarise_answer(answer: dict) -> str:
    """Store a concise summary in history — not the full formatted answer."""
    parts = []
    if answer.get('law'):
        parts.append(answer['law'][:300].strip())
    if answer.get('simple'):
        parts.append(answer['simple'][:300].strip())
    return '\n\n'.join(parts) if parts else 'Answered.'


# ─── Background worker ───────────────────────────────────────────────────────

def _run_job(job_id: int, history: list = None, rag_query: str = None):
    """
    Runs in a background thread.
    Calls the AI with conversation history, fills in the AnswerJob row.
    Never raises — all errors go into the job record.
    """
    try:
        job = AnswerJob.objects.get(pk=job_id)
        # Use enriched RAG query when available (for follow-ups/corrections)
        search_story = rag_query or job.story
        top_laws = find_relevant_laws(
            user_story=search_story, top_n=8, category_boost=["constitution"]
        )
        answer = get_answer(
            user_story=job.story,
            laws=top_laws,
            lang=job.lang,
            history=history or [],
        )

        query = Query.objects.create(
            user_identifier="web-anonymous",
            county=job.county,
            story=job.story,
            answer_law=answer.get("law", ""),
            answer_simple=answer.get("simple", ""),
            answer_loophole=answer.get("loophole", ""),
            answer_letter=answer.get("letter", ""),
            raw_answer=answer.get("raw", ""),
        )
        query.laws_used.set(top_laws)

        # Build summary to return to client so it can update localStorage history
        summary = _summarise_answer(answer)

        AnswerJob.objects.filter(pk=job_id).update(
            status=AnswerJob.STATUS_DONE,
            answer_law=answer.get("law", ""),
            answer_simple=answer.get("simple", ""),
            answer_loophole=answer.get("loophole", ""),
            answer_letter=answer.get("letter", ""),
            is_serious=answer.get("is_serious", False),
            sources_json=json.dumps([
                {"title": l.title, "section": l.section, "url": l.source_url}
                for l in top_laws
            ]),
            query=query,
            finished_at=timezone.now(),
        )
        # Store summary for the client to add to its history
        # We piggyback it in a separate field using the raw_answer slot isn't ideal
        # so we store it in the job's error_message field only when status=done (it's blank then)
        # Actually: we return it in the status response extra field — store in sources_json extra key
        # Cleanest: store in a temp cache dict keyed by job_id
        _job_summaries[job_id] = summary

    except Exception as exc:
        AnswerJob.objects.filter(pk=job_id).update(
            status=AnswerJob.STATUS_ERROR,
            error_message=str(exc)[:500],
            finished_at=timezone.now(),
        )


# Small in-process cache: job_id → assistant summary text
# Used to send the summary back to the browser so it can update localStorage history
_job_summaries: dict = {}


# ─── /api/submit/ ─────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def submit_job(request):
    """
    POST /api/submit/
    Body: {
      "story":   "...",
      "county":  "...",
      "lang":    "sw|en",
      "history": [{"role":"user","content":"..."},{"role":"assistant","content":"..."},...],
      "is_correction": false,
      "is_followup":   false
    }

    Creates an AnswerJob, fires the AI in a background thread,
    and returns the job_id immediately (< 1 second).
    For greetings/thanks detected on the client, no job is created —
    the client handles them locally. But if they reach here, we treat
    them as normal questions.
    """
    try:
        body   = json.loads(request.body)
        story  = body.get("story",  "").strip()
        county = body.get("county", "").strip()
        lang   = body.get("lang",   "sw").strip()
        history       = body.get("history", [])
        is_correction = bool(body.get("is_correction", False))
        is_followup   = bool(body.get("is_followup", False))
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if not story or len(story) < 5:
        return JsonResponse({"error": "Story too short."}, status=400)

    if not Law.objects.filter(embedding_json__isnull=False).exclude(embedding_json="").exists():
        return JsonResponse({"error": "Law data not loaded yet."}, status=503)

    # Validate lang
    if lang not in ("sw", "en"):
        lang = "sw"

    # Validate history — must be a list of role/content dicts, max 8 entries
    if not isinstance(history, list):
        history = []
    history = [
        h for h in history
        if isinstance(h, dict) and h.get('role') in ('user', 'assistant')
           and isinstance(h.get('content'), str)
    ][-8:]  # trim to last 4 turns

    # Build enriched RAG query for follow-ups and corrections
    rag_query = _build_rag_query(story, history, is_correction) if (is_correction or is_followup) else story

    job = AnswerJob.objects.create(story=story, county=county, lang=lang)

    # Fire and forget — Django response returns while thread works
    t = threading.Thread(
        target=_run_job,
        args=(job.pk, history, rag_query),
        daemon=True,
    )
    t.start()

    return JsonResponse({
        "job_id": job.pk,
        "status": "pending",
        "is_correction": is_correction,
    })


# ─── /api/status/<job_id>/ ────────────────────────────────────────────────────

@require_http_methods(["GET"])
def job_status(request, job_id):
    """
    GET /api/status/<job_id>/

    Returns current job state.

    While pending:
      {"status": "pending", "elapsed_seconds": 42}

    When done:
      {"status": "done", "answer": {...}, "sources": [...],
       "query_id": 5, "is_serious": false}

    On error:
      {"status": "error", "message": "..."}
    """
    try:
        job = AnswerJob.objects.get(pk=job_id)
    except AnswerJob.DoesNotExist:
        return JsonResponse({"error": "Job not found."}, status=404)

    elapsed = int((timezone.now() - job.created_at).total_seconds())

    if job.status == AnswerJob.STATUS_PENDING:
        return JsonResponse({"status": "pending", "elapsed_seconds": elapsed})

    if job.status == AnswerJob.STATUS_ERROR:
        return JsonResponse({"status": "error", "message": job.error_message})

    # Done — return full answer
    try:
        sources = json.loads(job.sources_json) if job.sources_json else []
    except (json.JSONDecodeError, ValueError):
        sources = []

    # Include assistant summary so the browser can update its localStorage history
    summary = _job_summaries.pop(job.pk, "")

    return JsonResponse({
        "status":    "done",
        "query_id":  job.query_id,
        "is_serious": job.is_serious,
        "answer": {
            "sheria_inasema": job.answer_law,
            "tafsiri_rahisi": job.answer_simple,
            "haki_yako":      job.answer_loophole,
            "andika_hivi":    job.answer_letter,
        },
        "sources":    sources,
        "elapsed_seconds": elapsed,
        "assistant_summary": summary,  # used by browser to update conversation history
    })


# ─── /api/ask/ — legacy synchronous endpoint ─────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
def ask_sheria(request):
    """
    Kept for direct API use / testing.
    Synchronous — waits for the full AI response before returning.

    GET  /api/ask/?q=your+question
    POST /api/ask/  body: {"story": "...", "county": "..."}
    """
    if request.method == "POST":
        try:
            body    = json.loads(request.body)
            story   = body.get("story", "").strip()
            county  = body.get("county", "").strip()
            user_id = body.get("user_identifier", "").strip()
            lang    = body.get("lang", "sw").strip()
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)
    else:
        story   = request.GET.get("q", "").strip()
        county  = request.GET.get("county", "").strip()
        user_id = request.GET.get("uid", "").strip()
        lang    = request.GET.get("lang", "sw").strip()

    if not story or len(story) < 5:
        return JsonResponse({"error": "Please provide your story (min 5 chars)."}, status=400)

    top_laws = find_relevant_laws(user_story=story, top_n=8,
                                  category_boost=["constitution"])
    if not top_laws:
        return JsonResponse({"error": "Law data not loaded."}, status=503)

    answer = get_answer(user_story=story, laws=top_laws, lang=lang)

    query = Query.objects.create(
        user_identifier=user_id or "anonymous",
        county=county, story=story,
        answer_law=answer.get("law", ""),
        answer_simple=answer.get("simple", ""),
        answer_loophole=answer.get("loophole", ""),
        answer_letter=answer.get("letter", ""),
        raw_answer=answer.get("raw", ""),
    )
    query.laws_used.set(top_laws)

    return JsonResponse({
        "query_id": query.pk,
        "answer": {
            "sheria_inasema": answer.get("law", ""),
            "tafsiri_rahisi": answer.get("simple", ""),
            "haki_yako":      answer.get("loophole", ""),
            "andika_hivi":    answer.get("letter", ""),
        },
        "is_serious_case": answer.get("is_serious", False),
        "sources": [
            {"title": l.title, "section": l.section, "url": l.source_url}
            for l in top_laws
        ],
        "disclaimer": (
            "This is legal information only, not legal advice. "
            "Verify at https://kenyalaw.org"
        ),
    })


# ─── /api/feedback/ ───────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def submit_feedback(request):
    """POST /api/feedback/  body: {"query_id": 1, "helpful": true}"""
    try:
        body        = json.loads(request.body)
        query_id    = body.get("query_id")
        was_helpful = body.get("helpful") or body.get("was_helpful")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    try:
        query = Query.objects.get(pk=query_id)
    except Query.DoesNotExist:
        return JsonResponse({"error": "Query not found."}, status=404)

    query.was_helpful = was_helpful
    query.save(update_fields=["was_helpful"])

    return JsonResponse({
        "message": "Asante! 🙏" if was_helpful else "Asante kwa maoni.",
        "query_id": query_id,
    })


# ─── /api/letter-pdf/<job_id>/ ───────────────────────────────────────────────

import re
import io
from django.http import HttpResponse, Http404
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _strip_markdown(text: str) -> str:
    """
    Remove markdown formatting and non-ASCII symbols so the letter renders
    as clean plain text with no black squares in the PDF.
    """
    # Remove bold/italic markers (**text** / __text__ / *text* / _text_)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__',     r'\1', text)
    text = re.sub(r'\*(.+?)\*',     r'\1', text)
    text = re.sub(r'_(.+?)_',       r'\1', text)
    # Remove heading markers (# ## ###)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove markdown links — keep display text
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    # Remove backtick code spans
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Replace common unicode bullets/arrows with ASCII equivalents
    replacements = {
        '\u2022': '-',   # • bullet
        '\u2023': '-',   # ‣ triangle bullet
        '\u25cf': '-',   # ● black circle
        '\u25aa': '-',   # ▪ small black square
        '\u25a0': '-',   # ■ black square
        '\u2013': '-',   # – en dash
        '\u2014': '-',   # — em dash
        '\u2018': "'",   # ' left single quote
        '\u2019': "'",   # ' right single quote
        '\u201c': '"',   # " left double quote
        '\u201d': '"',   # " right double quote
        '\u2026': '...',  # … ellipsis
        '\u2192': '->',  # → right arrow
        '\u2190': '<-',  # ← left arrow
        '\u00a0': ' ',   # non-breaking space
    }
    for uni, asc in replacements.items():
        text = text.replace(uni, asc)
    # Strip any remaining non-ASCII characters that Courier can't render
    text = text.encode('ascii', errors='replace').decode('ascii')
    # Strip trailing whitespace from each line (markdown uses "  " for line breaks)
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    # Collapse 3+ blank lines down to 1 blank line (saves vertical space)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@require_http_methods(["GET"])
def letter_pdf(request, job_id):
    """
    GET /api/letter-pdf/<job_id>/
    Generates a clean A4 PDF of the demand letter and returns it
    as an attachment (direct download, no new tab).
    """
    try:
        job = AnswerJob.objects.get(pk=job_id)
    except AnswerJob.DoesNotExist:
        raise Http404("Job not found.")

    if job.status != AnswerJob.STATUS_DONE or not job.answer_letter:
        return HttpResponse("Letter not ready yet.", status=404)

    letter_text = _strip_markdown(job.answer_letter)

    # ── Build PDF in memory ───────────────────────────────────────────
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Demand Letter",
        author="HakiMkononi",
    )

    # Courier (built-in) — professional letter look, no font files needed
    letter_style = ParagraphStyle(
        name="LetterBody",
        fontName="Courier",
        fontSize=10,
        leading=14,       # line spacing — tight enough to fit one page
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
    )

    story = []
    for line in letter_text.split("\n"):
        # Escape XML special chars that reportlab's Paragraph parser chokes on
        safe = (line
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
        if safe.strip() == "":
            story.append(Spacer(1, 3 * mm))   # 3 mm between paragraphs — was 5 mm
        else:
            story.append(Paragraph(safe, letter_style))

    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # ── Return as download (Content-Disposition: attachment) ─────────
    from datetime import date
    filename = f"Letter-{date.today().isoformat()}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = len(pdf_bytes)
    return response


# ─── /api/answer-pdf/<job_id>/ ───────────────────────────────────────────────

@require_http_methods(["GET"])
def answer_pdf(request, job_id):
    """
    GET /api/answer-pdf/<job_id>/
    Generates a full A4 PDF of all 4 answer boxes + sources.
    Returns as attachment — direct download, no print dialog, no new tab.
    """
    try:
        job = AnswerJob.objects.get(pk=job_id)
    except AnswerJob.DoesNotExist:
        raise Http404("Job not found.")

    if job.status != AnswerJob.STATUS_DONE:
        return HttpResponse("Answer not ready yet.", status=404)

    lang = job.lang or "sw"

    # Section labels per language
    labels = {
        "en":    {"law": "What The Law Says", "simple": "Plain Explanation",
                  "rights": "Your Rights & Next Steps", "letter": "Demand Letter"},
        "sw":    {"law": "Sheria Inasema", "simple": "Tafsiri Rahisi",
                  "rights": "Haki Yako", "letter": "Andika Hivi"},
    }
    L = labels.get(lang, labels["sw"])

    try:
        sources = json.loads(job.sources_json) if job.sources_json else []
    except (json.JSONDecodeError, ValueError):
        sources = []

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="HakiMkononi — Legal Answer",
        author="HakiMkononi",
    )

    # ── Styles ────────────────────────────────────────────────────────
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import HRFlowable

    heading_style = ParagraphStyle(
        name="Heading",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=10,
        spaceAfter=4,
        textColor=HexColor("#0f3d1f"),
    )
    body_style = ParagraphStyle(
        name="Body",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=3,
        spaceBefore=0,
    )
    letter_style = ParagraphStyle(
        name="Letter",
        fontName="Courier",
        fontSize=9.5,
        leading=13,
        spaceAfter=2,
        spaceBefore=0,
    )
    source_style = ParagraphStyle(
        name="Source",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        spaceAfter=2,
        spaceBefore=0,
        textColor=HexColor("#333333"),
    )

    def safe(text):
        return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def add_section(story, icon, title, text, style):
        if not text or not text.strip():
            return
        story.append(Paragraph(icon + " " + title, heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=HexColor("#cccccc"), spaceAfter=4))
        cleaned = _strip_markdown(text)
        for line in cleaned.split("\n"):
            s = safe(line)
            if s.strip() == "":
                story.append(Spacer(1, 2 * mm))
            else:
                story.append(Paragraph(s, style))

    story = []

    # Question at top (if available)
    if job.story:
        story.append(Paragraph(
            safe(job.story[:300] + ("..." if len(job.story) > 300 else "")),
            ParagraphStyle(name="Q", fontName="Helvetica-Oblique",
                           fontSize=9, leading=13, textColor=HexColor("#555555"),
                           spaceAfter=6)
        ))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=HexColor("#1a7a3c"), spaceAfter=8))

    add_section(story, "1.", L["law"],    job.answer_law,      body_style)
    add_section(story, "2.", L["simple"], job.answer_simple,   body_style)
    add_section(story, "3.", L["rights"], job.answer_loophole, body_style)
    add_section(story, "4.", L["letter"], job.answer_letter,   letter_style)

    # Sources
    if sources:
        story.append(Paragraph("Sources", heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=HexColor("#cccccc"), spaceAfter=4))
        for i, s in enumerate(sources, 1):
            title_text = f"{i}. {s.get('title','')} — {s.get('section','')}"
            url_text = f"  {s.get('url','')}" if s.get("url") else ""
            story.append(Paragraph(safe(title_text) + safe(url_text), source_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    from datetime import date
    filename = f"HakiMkononi-Answer-{date.today().isoformat()}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = len(pdf_bytes)
    return response


# ─── /api/health/ ─────────────────────────────────────────────────────────────

def health_check(request):
    """GET /api/health/"""
    count     = Law.objects.count()
    with_embs = Law.objects.exclude(embedding_json="").count()
    return JsonResponse({
        "status": "ok",
        "law_sections_loaded": count,
        "law_sections_with_embeddings": with_embs,
        "ready": with_embs > 0,
    })


def _wa_answer_job(sender: str, message: str, lang: str):
    """
    Background thread for WhatsApp: runs RAG + Groq directly, sends reply
    via raw HTTP POST to Twilio (avoids SDK ContentSid issue).
    """
    import os, re as _re, requests as _req

    try:
        from cases.ai_engine import (
            _call_groq, SYSTEM_PROMPTS, _USER_MESSAGES,
            format_law_context, parse_answer_sections, is_serious_criminal
        )

        top_laws = find_relevant_laws(message, top_n=8, category_boost=['constitution'])

        if is_serious_criminal(message):
            _wa_send(sender, {
                'sw': '🚨 Kesi hii ni nyeti sana. Wasiliana na wakili au NLAS: www.nlas.go.ke',
                'en': '🚨 This is a serious case. Contact a lawyer or NLAS: www.nlas.go.ke',
            }.get(lang, '🚨 Please contact a lawyer urgently.'))
            return

        context  = format_law_context(top_laws)
        system   = SYSTEM_PROMPTS[lang].format(context=context)
        user_msg = _USER_MESSAGES[lang].format(story=message)
        raw      = _call_groq([
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ])
        answer = parse_answer_sections(raw, lang=lang)

        def to_wa(text):
            if not text: return ''
            text = _re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
            text = _re.sub(r'__(.+?)__',      r'*\1*', text)
            text = _re.sub(r'^#+\s+',         '',      text, flags=_re.MULTILINE)
            text = _re.sub(r'^>\s?',          '',      text, flags=_re.MULTILINE)
            return text.strip()

        L = {
            'sw':    {'law': '📜 *Sheria Inasema*',    'simple': '💬 *Tafsiri Rahisi*', 'rights': '💪 *Haki Yako*'},
            'en':    {'law': '📜 *What The Law Says*', 'simple': '💬 *Plain Explanation*', 'rights': '💪 *Your Rights*'},
        }.get(lang, {'law': '📜 *Law*', 'simple': '💬 *Explanation*', 'rights': '💪 *Rights*'})

        parts = []
        if answer.get('law'):     parts.append(f"{L['law']}\n{to_wa(answer['law'])}")
        if answer.get('simple'):  parts.append(f"{L['simple']}\n{to_wa(answer['simple'])}")
        if answer.get('loophole'):parts.append(f"{L['rights']}\n{to_wa(answer['loophole'])}")
        if top_laws:
            src = '\n'.join(f"  {i+1}. {l.title} — {l.section}" for i, l in enumerate(top_laws[:3]))
            parts.append(f"📚 *Sources*\n{src}")
        parts.append({'sw':'⚠️ Taarifa ya kisheria tu.','en':'⚠️ Legal info only — not legal advice.'}.get(lang,''))

        full = '\n\n'.join(p for p in parts if p)
        _wa_send(sender, full)

    except Exception as e:
        print(f"[WhatsApp] Answer job error: {e}")
        _wa_send(sender, {
            'sw':    '❌ Samahani, kuna tatizo. Jaribu tena.',
            'en':    '❌ Sorry, a technical error occurred. Please try again.',
        }.get(lang, '❌ Sorry, please try again.'))


def _wa_send(to: str, body: str):
    """Send WhatsApp message via raw HTTP — avoids Twilio SDK ContentSid bug."""
    import os, requests as _req

    sid   = os.getenv('TWILIO_ACCOUNT_SID', '').strip()
    token = os.getenv('TWILIO_AUTH_TOKEN', '').strip()
    from_ = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886').strip()
    if not sid or not token:
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    MAX = 1500

    # Split at paragraph boundaries
    chunks, current = [], ''
    for para in body.split('\n\n'):
        if len(current) + len(para) + 2 <= MAX:
            current = (current + '\n\n' + para).strip()
        else:
            if current: chunks.append(current)
            current = para[:MAX]
    if current: chunks.append(current)
    if not chunks: chunks = [body[:MAX]]

    for chunk in chunks:
        try:
            r = _req.post(url, auth=(sid, token),
                         data={'From': from_, 'To': to, 'Body': chunk},
                         timeout=15)
            if r.status_code == 201:
                print(f"[WhatsApp] Sent {r.json().get('sid')} ({len(chunk)} chars)")
            else:
                print(f"[WhatsApp] Send failed {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"[WhatsApp] Send error: {e}")


# ─── /api/whatsapp/ — Twilio WhatsApp Sandbox webhook ────────────────────────

def _detect_lang_from_text(text: str) -> str:
    """
    Guess language from message keywords.
    Returns 'sw' or 'en'.
    Defaults to 'sw' (most Kenyans).
    Mixed/Sheng → 'sw' (Kiswahili reply is more appropriate).
    """
    t = text.lower()

    # English markers
    en_words = ['my employer', 'my landlord', 'i was', 'i have', 'i need',
                'police', 'arrested', 'fired', 'dismissed', 'salary',
                'what are', 'what is', 'how do', 'can i', 'help me']
    # Swahili markers
    sw_words = ['mwajiri', 'mfanyakazi', 'kazi', 'landlord', 'mpangaji',
                'sheria', 'haki', 'tafadhali', 'nisaidie', 'nifanye',
                'alinifukuza', 'walinishika', 'bila', 'notisi', 'ardhi']

    en_score = sum(1 for w in en_words if w in t)
    sw_score = sum(1 for w in sw_words if w in t)

    if en_score > sw_score:
        return 'en'
    return 'sw'


def _send_whatsapp(to: str, body: str):
    """
    Send a WhatsApp message via Twilio REST API.
    Splits messages longer than 1500 chars into chunks.
    Uses the sandbox number directly with body text.
    """
    import os
    from twilio.rest import Client

    sid   = os.getenv('TWILIO_ACCOUNT_SID', '').strip()
    token = os.getenv('TWILIO_AUTH_TOKEN', '').strip()
    from_ = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886').strip()

    if not sid or not token:
        print("[WhatsApp] ERROR: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set in .env")
        return

    client = Client(sid, token)

    # Split into ≤1500-char chunks at paragraph boundaries
    MAX = 1500
    chunks = []
    if len(body) <= MAX:
        chunks = [body]
    else:
        paragraphs = body.split('\n\n')
        current = ''
        for para in paragraphs:
            if len(current) + len(para) + 2 <= MAX:
                current = (current + '\n\n' + para).strip()
            else:
                if current:
                    chunks.append(current)
                while len(para) > MAX:
                    chunks.append(para[:MAX])
                    para = para[MAX:]
                current = para
        if current:
            chunks.append(current)

    for chunk in chunks:
        try:
            # Use the low-level messages.create with explicit body parameter.
            # persistent_action is not set — this keeps it as a plain text reply
            # which is allowed within the 24-hour user-initiated session window.
            msg = client.messages.create(
                from_=from_,
                to=to,
                body=chunk,
            )
            print(f"[WhatsApp] Sent SID={msg.sid} to={to} len={len(chunk)}")
        except Exception as e:
            error_str = str(e)
            # Error 21654: ContentSid Required — happens when Twilio sandbox
            # requires a template for outbound. Retry without from_ using
            # messaging_service_sid if available, otherwise log and skip.
            if '21654' in error_str or 'ContentSid' in error_str:
                print(f"[WhatsApp] ContentSid error — trying fallback without from_")
                try:
                    # Fallback: some sandbox accounts accept body without from_
                    # when using the account's default messaging service
                    msg = client.messages.create(
                        messaging_service_sid=None,
                        to=to,
                        body=chunk,
                        from_=from_,
                    )
                    print(f"[WhatsApp] Fallback sent SID={msg.sid}")
                except Exception as e2:
                    print(f"[WhatsApp] Fallback also failed: {e2}")
                    # Last resort: try with just the number, no whatsapp: prefix
                    try:
                        plain_to = to.replace('whatsapp:', '')
                        plain_from = from_.replace('whatsapp:', '')
                        msg = client.messages.create(
                            from_=f'whatsapp:{plain_from}',
                            to=f'whatsapp:{plain_to}',
                            body=chunk,
                        )
                        print(f"[WhatsApp] Plain retry SID={msg.sid}")
                    except Exception as e3:
                        print(f"[WhatsApp] All attempts failed: {e3}")
            else:
                print(f"[WhatsApp] Send error: {e}")


def _run_whatsapp_job(sender: str, message: str, lang: str):
    """
    Background thread: runs RAG + AI, then sends reply via Twilio.
    """
    try:
        top_laws = find_relevant_laws(
            user_story=message, top_n=8, category_boost=['constitution']
        )
        answer = get_answer(user_story=message, laws=top_laws, lang=lang)

        # ── Format reply ─────────────────────────────────────────────
        labels = {
            'sw':    {'law': '📜 *Sheria Inasema*', 'simple': '💬 *Tafsiri Rahisi*',
                      'rights': '💪 *Haki Yako*', 'letter': '✉️ *Andika Hivi*'},
            'en':    {'law': '📜 *What The Law Says*', 'simple': '💬 *Plain Explanation*',
                      'rights': '💪 *Your Rights*', 'letter': '✉️ *Write This*'},
        }
        L = labels.get(lang, labels['sw'])

        # Strip markdown bold (**text**) — WhatsApp uses *text* for bold
        def to_wa(text):
            if not text:
                return ''
            import re
            text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)   # **x** → *x*
            text = re.sub(r'__(.+?)__',      r'*\1*', text)   # __x__ → *x*
            text = re.sub(r'^#+\s+',         '',      text, flags=re.MULTILINE)  # headings
            text = re.sub(r'^>\s?',          '',      text, flags=re.MULTILINE)  # blockquotes
            return text.strip()

        parts = []
        if answer.get('law'):
            parts.append(f"{L['law']}\n{to_wa(answer['law'])}")
        if answer.get('simple'):
            parts.append(f"{L['simple']}\n{to_wa(answer['simple'])}")
        if answer.get('loophole'):
            parts.append(f"{L['rights']}\n{to_wa(answer['loophole'])}")

        # Sources — compact list
        if top_laws:
            src_lines = [f"  {i+1}. {l.title} — {l.section}"
                         for i, l in enumerate(top_laws[:4])]
            parts.append("📚 *Sources*\n" + '\n'.join(src_lines))

        # Letter — separate message so it's easy to copy
        if answer.get('letter'):
            parts.append(f"{L['letter']}\n{to_wa(answer['letter'])}")

        # Footer
        disclaimer = {
            'sw': '⚠️ Taarifa ya kisheria tu — si ushauri wa kisheria.',
            'en': '⚠️ Legal information only — not legal advice.',
        }.get(lang, '⚠️ Legal information only — not legal advice.')
        parts.append(disclaimer + '\nwww.hakimkononi.co.ke')

        full_reply = '\n\n'.join(parts)
        _send_whatsapp(sender, full_reply)

    except Exception as e:
        print(f"[WhatsApp] Job error: {e}")
        err = {
            'sw':    '❌ Samahani, kuna tatizo la kiufundi. Tafadhali jaribu tena.',
            'en':    '❌ Sorry, a technical error occurred. Please try again.',
        }.get(lang, '❌ Sorry, please try again.')
        _send_whatsapp(sender, err)


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_webhook(request):
    """
    POST /api/whatsapp/

    Flow:
      1st message ever  → ask language preference (1/2/3)
      Reply "1","2","3" → save language, send confirmation + instructions
      Any other message → run RAG+AI in chosen language, reply
    """
    from twilio.twiml.messaging_response import MessagingResponse
    from cases.models import WhatsAppUser

    body   = request.POST.get('Body', '').strip()
    sender = request.POST.get('From', '').strip()

    resp = MessagingResponse()

    if not body or not sender:
        return HttpResponse(str(resp), content_type='text/xml')

    # ── Get or create user record ─────────────────────────────────────
    user, created = WhatsAppUser.objects.get_or_create(phone=sender)

    msg_lower = body.lower().strip()

    # ── "stop" command — leave sandbox ────────────────────────────────
    if msg_lower == 'stop':
        resp.message("Umesimamishwa. Tuma *start* kurudi. / You have been unsubscribed. Send *start* to rejoin.")
        return HttpResponse(str(resp), content_type='text/xml')

    # ── Language selection reply (1, 2, or 3) — check BEFORE reset words ──
    # This must come before the reset/greeting check so "1","2","3" are
    # caught while the user is in the NEW state, not re-triggered as greetings.
    if user.state == WhatsAppUser.STATE_NEW and msg_lower in ['1', '2']:
        lang_map   = {'1': 'sw', '2': 'en'}
        lang_names = {'1': 'Kiswahili 🇰🇪', '2': 'English 🇬🇧'}
        chosen = lang_map[msg_lower]
        user.lang  = chosen
        user.state = WhatsAppUser.STATE_ACTIVE
        user.save()   # save both fields at once — do NOT use update_fields here

        confirm = {
            'sw': (
                f"✅ Vizuri! Utapata majibu kwa *{lang_names[msg_lower]}*.\n\n"
                "Sasa niambie tatizo lako la kisheria.\n\n"
                "Mfano: _Mwajiri wangu alinifukuza kazi bila notisi._\n\n"
                "_(Andika *lugha* kubadilisha lugha wakati wowote)_"
            ),
            'en': (
                f"✅ Great! You'll get answers in *{lang_names[msg_lower]}*.\n\n"
                "Now tell me your legal problem.\n\n"
                "Example: _My employer fired me without notice._\n\n"
                "_(Type *language* to change language at any time)_"
            ),
        }[chosen]
        resp.message(confirm)
        return HttpResponse(str(resp), content_type='text/xml')

    # ── NEW user or reset words → ask language ────────────────────────
    reset_words = ['start', 'hi', 'hello', 'habari', 'hujambo', 'help',
                   'language', 'lugha', 'change language', 'badilisha lugha']
    if created or user.state == WhatsAppUser.STATE_NEW or msg_lower in reset_words:
        user.state = WhatsAppUser.STATE_NEW
        user.save(update_fields=['state'])
        resp.message(
            "👋 *Karibu HakiMkononi!*\n\n"
            "Chagua lugha yako / Choose your language / Chagua lingo yako:\n\n"
            "1️⃣  *Kiswahili*\n"
            "2️⃣  *English*\n\n"
            "Jibu na namba / Reply with number: *1* or *2*"
        )
        return HttpResponse(str(resp), content_type='text/xml')

    # ── If still new and didn't pick 1/2/3 → remind them ─────────────
    if user.state == WhatsAppUser.STATE_NEW:
        resp.message(
            "Tafadhali chagua namba / Please choose a number:\n\n"
            "1️⃣  Kiswahili\n"
            "2️⃣  English"
        )
        return HttpResponse(str(resp), content_type='text/xml')

    # ── ACTIVE user — answer their legal question ──────────────────────
    lang = user.lang

    # Step 1: Send instant ack via TwiML (< 1s, no timeout risk)
    ack = {
        'sw':    '⏳ Inasoma sheria yako… jibu litakuja sekunde 15-20.',
        'en':    '⏳ Reading the law for you… reply coming in 15-20 seconds.',
    }.get(lang, '⏳ Processing…')
    resp.message(ack)

    # Step 2: Fire the real answer in a background thread using REST API.
    # This is a reply within an active user-initiated session so Twilio
    # allows free-form body text (no ContentSid required).
    threading.Thread(
        target=_wa_answer_job,
        args=(sender, body, lang),
        daemon=True,
    ).start()

    return HttpResponse(str(resp), content_type='text/xml')


# ─── /api/sms/ — Africa's Talking SMS webhook ────────────────────────────────

def _sms_send(to: str, message: str):
    """
    Send SMS reply via Africa's Talking API.
    Splits long messages into numbered parts of 155 chars each.
    Uses raw HTTP so no SDK initialisation needed at import time.
    """
    import os, requests as _req

    username = os.getenv('AT_USERNAME', '').strip()
    api_key  = os.getenv('AT_API_KEY',  '').strip()
    sender   = os.getenv('AT_SENDER_ID', '').strip() or None  # optional short code

    if not username or not api_key:
        print("[SMS] ERROR: AT_USERNAME or AT_API_KEY not set in .env")
        return

    # Use sandbox URL if username is 'sandbox', else live
    if username == 'sandbox':
        url = "https://api.sandbox.africastalking.com/version1/messaging"
    else:
        url = "https://api.africastalking.com/version1/messaging"

    # Split into 155-char chunks (leaves room for "1/3 " prefix)
    MAX  = 155
    words = message.split()
    parts, current = [], ''
    for word in words:
        if len(current) + len(word) + 1 <= MAX:
            current = (current + ' ' + word).strip()
        else:
            if current:
                parts.append(current)
            current = word
    if current:
        parts.append(current)

    if not parts:
        parts = [message[:MAX]]

    total = len(parts)
    for i, part in enumerate(parts, 1):
        text = f"{i}/{total} {part}" if total > 1 else part
        data = {
            'username': username,
            'to':       to,
            'message':  text,
        }
        if sender:
            data['from'] = sender
        try:
            r = _req.post(
                url,
                headers={'apiKey': api_key, 'Accept': 'application/json'},
                data=data,
                timeout=15,
            )
            resp_data = r.json()
            recipients = resp_data.get('SMSMessageData', {}).get('Recipients', [])
            if recipients:
                status = recipients[0].get('status', '?')
                print(f"[SMS] Sent part {i}/{total} to {to} — status: {status}")
            else:
                print(f"[SMS] Send response {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[SMS] Send error: {e}")


def _sms_answer_job(phone: str, message: str, lang: str):
    """
    Background thread: runs RAG + Groq, sends answer via AT SMS.
    Formats answer into concise SMS-friendly text.
    """
    import re as _re

    try:
        from cases.ai_engine import (
            _call_groq, SYSTEM_PROMPTS, _USER_MESSAGES,
            format_law_context, parse_answer_sections, is_serious_criminal
        )

        top_laws = find_relevant_laws(message, top_n=5, category_boost=['constitution'])

        if is_serious_criminal(message):
            _sms_send(phone, {
                'sw': 'HAKIMKONONI: Kesi hii ni nyeti. Wasiliana na wakili au NLAS: 0800 720 120 (bure)',
                'en': 'HAKIMKONONI: This is serious. Contact a lawyer or NLAS free line: 0800 720 120',
            }.get(lang, 'HAKIMKONONI: Please contact a lawyer urgently. NLAS: 0800 720 120'))
            return

        context  = format_law_context(top_laws)
        system   = SYSTEM_PROMPTS[lang].format(context=context)
        user_msg = _USER_MESSAGES[lang].format(story=message)
        raw      = _call_groq([
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ])
        answer = parse_answer_sections(raw, lang=lang)

        # Strip markdown — SMS has no formatting
        def plain(text):
            if not text: return ''
            text = _re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = _re.sub(r'\*(.+?)\*',     r'\1', text)
            text = _re.sub(r'__(.+?)__',     r'\1', text)
            text = _re.sub(r'^#+\s+',        '',    text, flags=_re.MULTILINE)
            text = _re.sub(r'^>\s?',         '',    text, flags=_re.MULTILINE)
            text = _re.sub(r'\n{2,}',        ' ',   text)
            text = _re.sub(r'\s{2,}',        ' ',   text)
            return text.strip()

        # Build a concise SMS answer — law + rights only (letter too long for SMS)
        L = {
            'sw':    {'law': 'SHERIA', 'rights': 'HAKI YAKO'},
            'en':    {'law': 'LAW',    'rights': 'YOUR RIGHTS'},
        }.get(lang, {'law': 'LAW', 'rights': 'RIGHTS'})

        parts = ['HAKIMKONONI:']

        law_text = plain(answer.get('law', ''))
        if law_text:
            parts.append(f"{L['law']}: {law_text[:300]}")

        rights_text = plain(answer.get('loophole', '') or answer.get('simple', ''))
        if rights_text:
            parts.append(f"{L['rights']}: {rights_text[:300]}")

        # Top 2 sources
        if top_laws:
            src = ', '.join(f"{l.section}" for l in top_laws[:2])
            parts.append(f"Ref: {src}")

        disclaimer = {
            'sw': 'Taarifa ya kisheria tu.',
            'en': 'Legal info only, not advice.',
        }.get(lang, '')
        parts.append(disclaimer)

        full = ' | '.join(p for p in parts if p)
        _sms_send(phone, full)

    except Exception as e:
        print(f"[SMS] Answer job error: {e}")
        _sms_send(phone, {
            'sw':    'HAKIMKONONI: Samahani, kuna tatizo. Jaribu tena.',
            'en':    'HAKIMKONONI: Sorry, technical error. Please try again.',
        }.get(lang, 'HAKIMKONONI: Sorry, please try again.'))


@csrf_exempt
@require_http_methods(["POST"])
def sms_webhook(request):
    """
    POST /api/sms/
    Africa's Talking sends an HTTP POST here for every inbound SMS.

    AT form fields:
      from     — sender phone number e.g. +254712345678
      text     — message body
      to       — our short code / number
      date     — timestamp
      id       — message ID

    Flow:
      New number       → ask language (reply 1/2/3)
      Reply 1/2/3      → save language, send confirmation
      Any other text   → run RAG+Groq, send SMS answer
    """
    from cases.models import WhatsAppUser  # reuse same model — phone is phone

    phone = request.POST.get('from', '').strip()
    text  = request.POST.get('text', '').strip()

    print(f"[SMS] Received from={phone} text={text[:80]}")

    if not phone or not text:
        return HttpResponse("", status=200)  # AT expects 200

    # Normalise phone — AT sends +254..., store as-is
    # Reuse WhatsAppUser model with a "sms:" prefix to distinguish from WA
    sms_phone = f"sms:{phone}"
    user, created = WhatsAppUser.objects.get_or_create(phone=sms_phone)

    msg_lower = text.lower().strip()

    # ── STOP ──────────────────────────────────────────────────────────
    if msg_lower == 'stop':
        threading.Thread(
            target=_sms_send,
            args=(phone, 'HAKIMKONONI: Umesimamishwa. Tuma START kurudi.'),
            daemon=True
        ).start()
        return HttpResponse("", status=200)

    # ── Language choice (1/2/3) — check BEFORE reset words ────────────
    if user.state == WhatsAppUser.STATE_NEW and msg_lower in ['1', '2']:
        lang_map   = {'1': 'sw', '2': 'en'}
        lang_names = {'1': 'Kiswahili', '2': 'English'}
        chosen = lang_map[msg_lower]
        user.lang  = chosen
        user.state = WhatsAppUser.STATE_ACTIVE
        user.save()
        confirm = {
            'sw':    f"HAKIMKONONI: Sawa! Lugha: Kiswahili. Sasa niandikia tatizo lako la kisheria.",
            'en':    f"HAKIMKONONI: Great! Language: English. Now text me your legal problem.",
        }[chosen]
        threading.Thread(target=_sms_send, args=(phone, confirm), daemon=True).start()
        return HttpResponse("", status=200)

    # ── New user or reset → ask language ──────────────────────────────
    reset_words = ['start', 'hi', 'hello', 'habari', 'help', 'language', 'lugha']
    if created or user.state == WhatsAppUser.STATE_NEW or msg_lower in reset_words:
        user.state = WhatsAppUser.STATE_NEW
        user.save(update_fields=['state'])
        welcome = (
            "HAKIMKONONI: Karibu! Chagua lugha / Choose language:\n"
            "1=Kiswahili 2=English\n"
            "Jibu na namba / Reply with 1 or 2"
        )
        threading.Thread(target=_sms_send, args=(phone, welcome), daemon=True).start()
        return HttpResponse("", status=200)

    # ── Still new, didn't pick 1/2/3 ──────────────────────────────────
    if user.state == WhatsAppUser.STATE_NEW:
        threading.Thread(
            target=_sms_send,
            args=(phone, 'HAKIMKONONI: Tafadhali chagua: 1=Kiswahili 2=English'),
            daemon=True
        ).start()
        return HttpResponse("", status=200)

    # ── Active user — answer question ─────────────────────────────────
    lang = user.lang

    # Send instant ack
    ack = {
        'sw':    'HAKIMKONONI: Inaangalia sheria... jibu linakuja dakika moja.',
        'en':    'HAKIMKONONI: Reading the law... answer coming in ~1 minute.',
    }.get(lang, 'HAKIMKONONI: Processing... please wait.')
    threading.Thread(target=_sms_send, args=(phone, ack), daemon=True).start()

    # Fire answer in background
    threading.Thread(
        target=_sms_answer_job,
        args=(phone, text, lang),
        daemon=True,
    ).start()

    return HttpResponse("", status=200)  # AT needs a 200 response


# ─── /api/meta-whatsapp/ — Meta WhatsApp Cloud API webhook ───────────────────

def _meta_send(to: str, body: str):
    """
    Send a WhatsApp message via Meta Cloud API.
    No ContentSid, no templates needed for replies within 24h session.
    Splits messages longer than 4000 chars into chunks.
    """
    import os, requests as _req

    token    = os.getenv('META_WHATSAPP_TOKEN', '').strip()
    phone_id = os.getenv('META_PHONE_NUMBER_ID', '').strip()

    if not token or not phone_id or phone_id == 'your-phone-number-id-here':
        print("[Meta WA] ERROR: META_PHONE_NUMBER_ID not set in .env")
        return

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    MAX = 4000
    chunks = []
    if len(body) <= MAX:
        chunks = [body]
    else:
        paragraphs = body.split('\n\n')
        current = ''
        for para in paragraphs:
            if len(current) + len(para) + 2 <= MAX:
                current = (current + '\n\n' + para).strip()
            else:
                if current: chunks.append(current)
                current = para[:MAX]
        if current: chunks.append(current)

    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": chunk},
        }
        try:
            r = _req.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code == 200:
                print(f"[Meta WA] Sent to={to} ({len(chunk)} chars)")
            else:
                print(f"[Meta WA] Send failed {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[Meta WA] Send error: {e}")


def _meta_answer_job(phone: str, message: str, lang: str):
    """Background thread: RAG + Groq → reply via Meta API."""
    import re as _re

    try:
        from cases.ai_engine import (
            _call_groq, SYSTEM_PROMPTS, _USER_MESSAGES,
            format_law_context, parse_answer_sections, is_serious_criminal,
        )

        top_laws = find_relevant_laws(message, top_n=8, category_boost=['constitution'])

        if is_serious_criminal(message):
            _meta_send(phone, {
                'sw':    '🚨 Kesi nyeti. Wasiliana na NLAS (bure): 0800 720 120 | www.nlas.go.ke',
                'en':    '🚨 Serious case. Contact NLAS (free): 0800 720 120 | www.nlas.go.ke',
            }.get(lang, '🚨 Serious case — contact a lawyer urgently.'))
            return

        context  = format_law_context(top_laws)
        system   = SYSTEM_PROMPTS[lang].format(context=context)
        user_msg = _USER_MESSAGES[lang].format(story=message)
        raw      = _call_groq([
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ])
        answer = parse_answer_sections(raw, lang=lang)

        def to_wa(text):
            if not text: return ''
            text = _re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
            text = _re.sub(r'__(.+?)__',      r'*\1*', text)
            text = _re.sub(r'^#+\s+',         '',      text, flags=_re.MULTILINE)
            text = _re.sub(r'^>\s?',          '',      text, flags=_re.MULTILINE)
            return text.strip()

        L = {
            'sw':    {'law': '📜 *Sheria Inasema*',    'simple': '💬 *Tafsiri Rahisi*', 'rights': '💪 *Haki Yako*'},
            'en':    {'law': '📜 *What The Law Says*', 'simple': '💬 *Plain Explanation*', 'rights': '💪 *Your Rights*'},
        }.get(lang, {'law': '📜 Law', 'simple': '💬 Explanation', 'rights': '💪 Rights'})

        parts = []
        if answer.get('law'):     parts.append(f"{L['law']}\n{to_wa(answer['law'])}")
        if answer.get('simple'):  parts.append(f"{L['simple']}\n{to_wa(answer['simple'])}")
        if answer.get('loophole'):parts.append(f"{L['rights']}\n{to_wa(answer['loophole'])}")
        if answer.get('letter'):  parts.append(f"✉️ *Write This*\n{answer['letter'][:800]}")
        if top_laws:
            src = '\n'.join(f"  {i+1}. {l.title} — {l.section}" for i, l in enumerate(top_laws[:4]))
            parts.append(f"📚 *Sources*\n{src}")
        parts.append({
            'sw': '⚠️ Taarifa ya kisheria tu — si ushauri wa kisheria.',
            'en': '⚠️ Legal information only — not legal advice.',
        }.get(lang, ''))

        _meta_send(phone, '\n\n'.join(p for p in parts if p))

    except Exception as e:
        print(f"[Meta WA] Answer job error: {e}")
        _meta_send(phone, {
            'sw':    '❌ Samahani, kuna tatizo. Jaribu tena.',
            'en':    '❌ Sorry, a technical error occurred. Please try again.',
        }.get(lang, '❌ Sorry, please try again.'))


@csrf_exempt
def meta_whatsapp_webhook(request):
    """
    GET  /api/meta-whatsapp/ — Meta verification challenge
    POST /api/meta-whatsapp/ — Incoming messages
    """
    import json as _json
    import os

    # ── GET: Meta verifies the webhook URL ────────────────────────────
    if request.method == 'GET':
        mode      = request.GET.get('hub.mode', '')
        token     = request.GET.get('hub.verify_token', '')
        challenge = request.GET.get('hub.challenge', '')
        verify    = os.getenv('META_VERIFY_TOKEN', 'hakimkononi2026')

        if mode == 'subscribe' and token == verify:
            print(f"[Meta WA] Webhook verified ✅")
            return HttpResponse(challenge, status=200)
        return HttpResponse("Verification failed", status=403)

    # ── POST: Incoming message ─────────────────────────────────────────
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    try:
        data = _json.loads(request.body)
    except Exception:
        return HttpResponse("Bad JSON", status=400)

    # Extract message from Meta's webhook payload
    try:
        entry   = data['entry'][0]
        changes = entry['changes'][0]
        value   = changes['value']

        # Ignore status updates (delivered, read, etc.)
        if 'messages' not in value:
            return HttpResponse("OK", status=200)

        msg     = value['messages'][0]
        phone   = msg['from']          # e.g. "254712345678"
        msg_type = msg.get('type', '')

        # Only handle text messages
        if msg_type != 'text':
            return HttpResponse("OK", status=200)

        text = msg['text']['body'].strip()
        print(f"[Meta WA] Received from={phone} text={text[:80]}")

    except (KeyError, IndexError) as e:
        print(f"[Meta WA] Payload parse error: {e}")
        return HttpResponse("OK", status=200)

    # Reuse WhatsAppUser model with "meta:" prefix
    from cases.models import WhatsAppUser
    meta_phone = f"meta:{phone}"
    user, created = WhatsAppUser.objects.get_or_create(phone=meta_phone)
    msg_lower = text.lower().strip()

    # ── STOP ──────────────────────────────────────────────────────────
    if msg_lower == 'stop':
        threading.Thread(
            target=_meta_send,
            args=(phone, 'Umesimamishwa. Text START kurudi. / Unsubscribed. Text START to rejoin.'),
            daemon=True,
        ).start()
        return HttpResponse("OK", status=200)

    # ── Language choice (1/2/3) — check BEFORE reset words ────────────
    if user.state == WhatsAppUser.STATE_NEW and msg_lower in ['1', '2']:
        lang_map   = {'1': 'sw', '2': 'en'}
        lang_names = {'1': 'Kiswahili 🇰🇪', '2': 'English 🇬🇧'}
        chosen = lang_map[msg_lower]
        user.lang  = chosen
        user.state = WhatsAppUser.STATE_ACTIVE
        user.save()
        confirm = {
            'sw':    f"✅ Vizuri! Lugha: *{lang_names[msg_lower]}*\n\nNiambie tatizo lako la kisheria.\n\nMfano: _Nilifukuzwa kazi bila notisi._\n\n_(Andika *language* kubadilisha lugha)_",
            'en':    f"✅ Great! Language: *{lang_names[msg_lower]}*\n\nTell me your legal problem.\n\nExample: _My employer fired me without notice._\n\n_(Type *language* to change language)_",
        }[chosen]
        threading.Thread(target=_meta_send, args=(phone, confirm), daemon=True).start()
        return HttpResponse("OK", status=200)

    # ── New user or reset ──────────────────────────────────────────────
    reset_words = ['start', 'hi', 'hello', 'habari', 'help', 'language', 'lugha']
    if created or user.state == WhatsAppUser.STATE_NEW or msg_lower in reset_words:
        user.state = WhatsAppUser.STATE_NEW
        user.save(update_fields=['state'])
        welcome = (
            "👋 *Karibu HakiMkononi!*\n\n"
            "Mimi ni AI inayokusaidia kuelewa sheria ya Kenya *bila malipo*.\n\n"
            "Chagua lugha yako / Choose your language:\n\n"
            "1️⃣ Kiswahili\n"
            "2️⃣ English\n\n"
            "Jibu na namba / Reply with: *1* or *2*"
        )
        threading.Thread(target=_meta_send, args=(phone, welcome), daemon=True).start()
        return HttpResponse("OK", status=200)

    # ── Still new, invalid choice ──────────────────────────────────────
    if user.state == WhatsAppUser.STATE_NEW:
        threading.Thread(
            target=_meta_send,
            args=(phone, 'Tafadhali chagua / Please choose:\n1️⃣ Kiswahili  2️⃣ English'),
            daemon=True,
        ).start()
        return HttpResponse("OK", status=200)

    # ── Active user — send ack then answer ────────────────────────────
    lang = user.lang
    ack = {
        'sw':    '⏳ Inasoma sheria yako… jibu linakuja sekunde 15-20.',
        'en':    '⏳ Reading the law for you… reply coming in 15-20 seconds.',
    }.get(lang, '⏳ Processing…')

    threading.Thread(target=_meta_send, args=(phone, ack), daemon=True).start()
    threading.Thread(
        target=_meta_answer_job,
        args=(phone, text, lang),
        daemon=True,
    ).start()

    return HttpResponse("OK", status=200)


# ─── /api/transcribe/ — Voice to text via Groq Whisper ───────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def transcribe_audio(request):
    """
    POST /api/transcribe/
    Accepts an audio file upload, sends to Groq Whisper, returns transcript.

    Form data:
      audio — audio file (webm, mp3, wav, m4a, ogg — anything Whisper supports)
      lang  — optional hint: 'sw' or 'en' (default: auto-detect)

    Returns:
      {"transcript": "Mwajiri wangu alinifukuza...", "detected_language": "sw"}
    """
    import requests as _req
    import os

    if 'audio' not in request.FILES:
        return JsonResponse({"error": "No audio file provided."}, status=400)

    audio_file = request.FILES['audio']
    lang_hint  = request.POST.get('lang', '').strip()

    groq_key = os.getenv('GROQ_API_KEY', '').strip()
    if not groq_key:
        return JsonResponse({"error": "Transcription not configured."}, status=503)

    # Map lang hint to Whisper language code
    lang_map = {'sw': 'sw', 'en': 'en', 'swahili': 'sw', 'english': 'en'}
    whisper_lang = lang_map.get(lang_hint.lower(), None)  # None = auto-detect

    try:
        files = {
            'file': (audio_file.name or 'audio.webm', audio_file.read(), audio_file.content_type or 'audio/webm'),
        }
        data = {
            'model': 'whisper-large-v3',
            'response_format': 'verbose_json',  # gives us detected_language
            'temperature': '0',
        }
        if whisper_lang:
            data['language'] = whisper_lang

        r = _req.post(
            'https://api.groq.com/openai/v1/audio/transcriptions',
            headers={'Authorization': f'Bearer {groq_key}'},
            files=files,
            data=data,
            timeout=30,
        )

        if r.status_code != 200:
            print(f"[Whisper] Error {r.status_code}: {r.text[:200]}")
            return JsonResponse({"error": "Transcription failed. Please try again."}, status=500)

        result = r.json()
        transcript = result.get('text', '').strip()
        detected   = result.get('language', 'unknown')

        print(f"[Whisper] Transcribed ({detected}): {transcript[:80]}")

        return JsonResponse({
            "transcript":         transcript,
            "detected_language":  detected,
        })

    except Exception as e:
        print(f"[Whisper] Exception: {e}")
        return JsonResponse({"error": "Transcription service error."}, status=500)
