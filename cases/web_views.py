"""
Web views for the Wanjiku-facing HTML interface.
Separate from cases/views.py which handles the JSON API.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from cases.models import Law, Query
from cases.rag import find_relevant_laws
from cases.ai_engine import get_answer  # kept for potential direct use

# ─── Supported languages ─────────────────────────────────────────────────────
SUPPORTED_LANGS = ("sw", "en")
DEFAULT_LANG = "sw"

# ─── All UI strings in 3 languages ───────────────────────────────────────────
# Rule: app name "HakiMkononi" is NEVER translated.
UI = {
    "sw": {
        "lang_code":        "sw",
        "lang_name":        "Kiswahili",
        "html_lang":        "sw",

        # Nav
        "nav_home":         "Nyumbani",
        "nav_about":        "Kuhusu",

        # Hero
        "hero_title":       "Sheria Yako, Mkononi Mwako",
        "hero_sub":         "Eleza hali yako. AI itakusaidia kuelewa haki zako bila malipo.",
        "hero_note":        "Inategemea Katiba ya Kenya 2010, Sheria ya Ajira 2007 na zaidi.",

        # Form
        "form_heading":     "Eleza Hali Yako",
        "field_story":      "Tatizo lako la kisheria",
        "story_help":       "Andika kwa lugha yoyote. Kiswahili, Kingereza, au mchanganyiko. Sentensi 1 au 2 zinatosha.",
        "field_county":     "Kaunti yako (si lazima)",
        "county_default":   "-- Chagua kaunti --",
        "county_help":      "Husaidia kupata msaada wa mahali ulipo.",
        "field_lang":       "Unataka jibu kwa lugha gani?",
        "btn_submit":       "Tafuta Jibu la Kisheria",
        "btn_loading":      "Inashughulikia…",
        "story_placeholder":"Mfano: Boss wangu alinifukuza kazi bila notisi wala malipo. Nilifanya kazi miaka 3. Nifanye nini?",

        # Chips
        "chips_label":      "Mifano ya maswali:",
        "chips": [
            "Nilifukuzwa kazi bila notisi",
            "Landlord ananizuia nyumba bila notisi",
            "Polisi walinishika bila warrant",
            "Mke wangu ananidanganya mali",
            "Mwajiri hakulipia mshahara wangu",
            "Nilipigwa na jirani. Nifanye nini?",
        ],

        # How it works
        "how_title":        "Inafanya Kazi Vipi?",
        "how_1_title":      "1. Eleza Tatizo",
        "how_1_body":       "Andika hali yako kwa lugha yoyote. Sentensi moja au mbili zinatosha.",
        "how_2_title":      "2. AI Inasoma Sheria",
        "how_2_body":       "Mfumo wetu unasoma Katiba, Sheria ya Ajira na sheria nyingine za Kenya.",
        "how_3_title":      "3. Pata Jibu Lako",
        "how_3_body":       "Unapata maelezo ya kisheria, haki zako, na barua ya kudai haki.",

        # Errors / validation
        "error_short":      "Tafadhali eleza hali yako zaidi. Andika sentensi moja au mbili.",
        "error_heading":    "Kuna tatizo:",
        "error_retry_hint": "Jaribu tena, au andika swali fupi zaidi.",
        "error_no_laws":    "Sheria bado hazijapakiwa. Tafadhali subiri.",

        # Disclaimer
        "disclaimer":       "HakiMkononi inatoa taarifa za kisheria tu. Si ushauri wa kisheria. Kwa kesi ngumu, wasiliana na wakili.",

        # Answer page
        "answer_heading":   "Jibu la Kisheria",
        "back_home":        "← Rudi Nyumbani",
        "box_law":          "Sheria Inasema",
        "box_law_sub":      "What the law says",
        "box_simple":       "Tafsiri Rahisi",
        "box_simple_sub":   "Plain language",
        "box_rights":       "Haki Yako",
        "box_rights_sub":   "Your rights and next steps",
        "box_letter":       "Andika Hivi",
        "box_letter_sub":   "Draft letter / complaint",
        "sources_heading":  "Vyanzo vya Sheria",
        "sources_read":     "Soma zaidi",
        "feedback_prompt":  "Je, jibu hili lilikusaidia?",
        "feedback_yes":     "👍 Ndiyo, ilisaidia",
        "feedback_no":      "👎 Hapana",
        "feedback_thanks":  "Asante kwa maoni yako!",
        "btn_ask_another":  "Uliza Swali Jingine",
        "btn_print":        "Pakua PDF",
        "btn_share":        "Shiriki",
        "btn_copy":         "Nakili",
        "btn_copied":       "Imenakiliwa",
        "serious_warning":  "Kesi hii ni nyeti. Tafadhali wasiliana na wakili.",
        "serious_nlas":     "Unaweza kupata msaada bila malipo kupitia",
        "answer_disclaimer":"Taarifa hii ni ya kisheria tu. Si ushauri wa kisheria. Thibitisha vifungu kwenye",
        "answer_nlas":      "Kwa kesi ngumu, wasiliana na wakili au",

        # About
        "about_title":      "Kuhusu HakiMkononi",
        "about_hero_sub":   "Tunaamini kila Mkenya anastahili kuelewa haki zake. Bila malipo. Bila wasiwasi.",
        "about_mission_h":  "Dhamira Yetu",
        "about_mission_1":  "HakiMkononi iliundwa kwa ajili ya Wanjiku. Mtu wa kawaida Kenya ambaye ana tatizo la kisheria lakini hawezi kumudu wakili, au hajui hata pa kuanza.",
        "about_mission_2":  "Watu wengi wanafukuzwa kazi bila haki, wanabaguliwa, au wananyanyaswa. Hawajui haki zao. Sheria ya Kenya ipo, lakini imeandikwa kwa lugha ngumu sana.",
        "about_mission_3":  "Sisi tunabadilisha hilo. Unauliza swali kwa lugha yoyote. Sisi tunakuambia sheria inasema nini, haki zako ni zipi, na tunakuandikia barua ya kudai haki yako.",
        "about_tech_h":     "Teknolojia Yetu",
        "about_laws_h":     "Sheria Tulizopakia",
        "about_limits_h":   "Mambo Muhimu ya Kujua",
        "about_cta":        "Uliza Swali la Kisheria",

        # Footer
        "footer_tagline":   "Sheria yako, mkononi mwako 🇰🇪",
        "footer_legal":     "Taarifa ya kisheria tu. Si ushauri wa kisheria.",

        # Loading overlay
        "loading_title":    "Inashughulikia ombi lako…",
        "loading_sub":      "Inasoma sheria. Majibu yataonekana mara mara.",
    },

    "en": {
        "lang_code":        "en",
        "lang_name":        "English",
        "html_lang":        "en",

        "nav_home":         "Home",
        "nav_about":        "About",

        "hero_title":       "Your Rights, In Your Hands",
        "hero_sub":         "Describe your situation. AI will help you understand your legal rights for free.",
        "hero_note":        "Powered by the Kenya Constitution 2010, Employment Act 2007 and more.",

        "form_heading":     "Describe Your Situation",
        "field_story":      "Your legal problem",
        "story_help":       "Type in any language. English, Swahili, or a mix. One or two sentences is enough.",
        "field_county":     "Your county (optional)",
        "county_default":   "-- Select county --",
        "county_help":      "Helps us find local resources near you.",
        "field_lang":       "What language do you want your answer in?",
        "btn_submit":       "Find Legal Answer",
        "btn_loading":      "Processing…",
        "story_placeholder":"Example: My boss fired me without notice or pay. I worked there 3 years. What do I do?",

        "chips_label":      "Example questions:",
        "chips": [
            "I was fired without notice",
            "Landlord locked me out without notice",
            "Police arrested me without a warrant",
            "Spouse is hiding our shared property",
            "My employer hasn't paid my salary",
            "My neighbour assaulted me. What do I do?",
        ],

        "how_title":        "How It Works",
        "how_1_title":      "1. Describe the Problem",
        "how_1_body":       "Type your situation in any language. One or two sentences is enough.",
        "how_2_title":      "2. AI Reads the Law",
        "how_2_body":       "Our system searches the Constitution, Employment Act and other Kenyan laws.",
        "how_3_title":      "3. Get Your Answer",
        "how_3_body":       "You get a legal explanation, your rights, and a ready-to-use demand letter.",

        "error_short":      "Please describe your situation more. Write at least one sentence.",
        "error_heading":    "There's a problem:",
        "error_retry_hint": "Please try again, or write a shorter question.",
        "error_no_laws":    "Law data not loaded yet. Please wait.",

        "disclaimer":       "HakiMkononi provides legal information only. Not legal advice. For complex cases, consult a lawyer.",

        "answer_heading":   "Legal Answer",
        "back_home":        "← Back Home",
        "box_law":          "What The Law Says",
        "box_law_sub":      "Sheria inasema",
        "box_simple":       "Plain Explanation",
        "box_simple_sub":   "Tafsiri rahisi",
        "box_rights":       "Your Rights",
        "box_rights_sub":   "what went wrong",
        "box_letter":       "Write This",
        "box_letter_sub":   "Demand letter / complaint",
        "sources_heading":  "Legal Sources",
        "sources_read":     "Read more",
        "feedback_prompt":  "Did this answer help you?",
        "feedback_yes":     "👍 Yes, it helped",
        "feedback_no":      "👎 No",
        "feedback_thanks":  "Thank you for your feedback!",
        "btn_ask_another":  "Ask Another Question",
        "btn_print":        "Download PDF",        "btn_share":        "Share",
        "btn_copy":         "Copy",
        "btn_copied":       "Copied!",
        "serious_warning":  "This is a serious case. Please contact a lawyer urgently.",
        "serious_nlas":     "You can get free help through",
        "answer_disclaimer":"This is legal information only. Not legal advice. Verify sections at",
        "answer_nlas":      "For serious cases, contact a lawyer or",

        "about_title":      "About HakiMkononi",
        "about_hero_sub":   "We believe every Kenyan deserves to understand their rights. Free of charge. Free of fear.",
        "about_mission_h":  "Our Mission",
        "about_mission_1":  "HakiMkononi was built for the ordinary Kenyan who has a legal problem but cannot afford a lawyer or does not even know where to start.",
        "about_mission_2":  "People get fired unfairly, locked out of their homes, or arrested without being told their rights. The law is there to protect them but it is written in language most people cannot read.",
        "about_mission_3":  "We are changing that. You ask a question in any language. We tell you what the law says, what your rights are, and we write you a demand letter you can actually use.",
        "about_tech_h":     "How We Built It",
        "about_laws_h":     "Laws We Have Loaded",
        "about_limits_h":   "Important Things to Know",
        "about_cta":        "Ask a Legal Question",

        "footer_tagline":   "Your rights, in your hands 🇰🇪",
        "footer_legal":     "Legal information only. Not legal advice.",

        "loading_title":    "Processing your request…",
        "loading_sub":      "Reading the law for you. Results will appear shortly.",
    },

}

COUNTIES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo Marakwet",
    "Embu", "Garissa", "Homa Bay", "Isiolo", "Kajiado",
    "Kakamega", "Kericho", "Kiambu", "Kilifi", "Kirinyaga",
    "Kisii", "Kisumu", "Kitui", "Kwale", "Laikipia",
    "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
    "Meru", "Migori", "Mombasa", "Muranga", "Nairobi",
    "Nakuru", "Nandi", "Narok", "Nyandarua", "Nyamira",
    "Nyeri", "Samburu", "Siaya", "Taita Taveta", "Tana River",
    "Tharaka Nithi", "Trans Nzoia", "Turkana", "Uasin Gishu",
    "Vihiga", "Wajir", "West Pokot",
]


def _get_lang(request) -> str:
    """
    Resolve active language. Priority:
      1. POST/GET param 'lang'
      2. Cookie 'haki_lang'
      3. DEFAULT_LANG
    """
    lang = (
        request.POST.get("lang")
        or request.GET.get("lang")
        or request.COOKIES.get("haki_lang")
        or DEFAULT_LANG
    )
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def _render_with_lang(request, template, context, lang):
    """Render a template and set the haki_lang cookie on the response."""
    context["ui"] = UI[lang]
    context["lang"] = lang
    context["supported_langs"] = [UI[l] for l in SUPPORTED_LANGS]
    response = render(request, template, context)
    response.set_cookie(
        "haki_lang", lang,
        max_age=60 * 60 * 24 * 365,   # 1 year
        httponly=False,                 # JS needs to read it for chips
        samesite="Lax",
    )
    return response


@require_http_methods(["GET", "HEAD"])
def home(request):
    lang = _get_lang(request)
    resp = _render_with_lang(request, "chat.html", {"counties": COUNTIES}, lang)
    resp.set_cookie("haki_lang", lang, max_age=60*60*24*365, samesite="Lax")
    return resp


@require_http_methods(["GET"])
def about(request):
    lang = _get_lang(request)
    return _render_with_lang(request, "about.html", {}, lang)


@csrf_protect
@require_http_methods(["GET", "POST"])
def ask_web(request):
    """
    GET  /ask/?job=ID  — renders the answer shell so JS restores from localStorage
    POST /ask/         — renders the answer shell, JS submits to /api/submit/
    """
    lang = _get_lang(request)
    ui   = UI[lang]

    # ── GET with ?job= param — just render the shell, JS restores from localStorage
    if request.method == "GET":
        job_id = request.GET.get("job", "").strip()
        if job_id:
            # Render a minimal shell — JS will restore from localStorage
            return _render_with_lang(request, "answer.html", {
                "story":     "",
                "county":    "",
                "streaming": True,   # tells template to activate restore JS
                "job_id":    job_id,
            }, lang)
        # GET without job param — redirect home
        from django.shortcuts import redirect
        return redirect(f"/?lang={lang}")

    # ── POST — normal form submission
    story  = request.POST.get("story",  "").strip()
    county = request.POST.get("county", "").strip()

    # Validate before rendering — catch empty/short inputs server-side too
    if not story or len(story) < 5:
        return _render_with_lang(request, "home.html", {
            "error":    ui["error_short"],
            "counties": COUNTIES,
            "story":    story,
            "county":   county,
        }, lang)

    if not Law.objects.filter(embedding_json__isnull=False).exclude(embedding_json="").exists():
        return _render_with_lang(request, "answer.html", {
            "story":      story,
            "county":     county,
            "error":      ui["error_no_laws"],
            "streaming":  False,
        }, lang)

    # Render the shell — answer.html JS will call /api/stream/ with these values
    return _render_with_lang(request, "answer.html", {
        "story":     story,
        "county":    county,
        "streaming": True,   # tells the template to activate the stream JS
    }, lang)


# ─── /dashboard/ — Admin Learning Dashboard ──────────────────────────────────

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


@staff_member_required(login_url='/admin/login/')
def dashboard(request):
    """
    Staff-only learning dashboard.
    Shows stats, 👎 answers to review, and allows adding corrections.
    """
    from cases.models import Query, Law, AnswerJob, WhatsAppUser

    now = timezone.now()
    day30 = now - timedelta(days=30)
    day7  = now - timedelta(days=7)
    day1  = now - timedelta(days=1)

    # ── Stats ────────────────────────────────────────────────────────────────
    total_queries  = Query.objects.count()
    queries_30d    = Query.objects.filter(created_at__gte=day30).count()
    queries_7d     = Query.objects.filter(created_at__gte=day7).count()
    queries_today  = Query.objects.filter(created_at__gte=day1).count()

    helpful        = Query.objects.filter(was_helpful=True).count()
    not_helpful    = Query.objects.filter(was_helpful=False).count()
    no_feedback    = Query.objects.filter(was_helpful__isnull=True).count()

    # Satisfaction rate
    rated = helpful + not_helpful
    satisfaction = round((helpful / rated * 100)) if rated > 0 else 0

    # ── 👎 Queries needing review ─────────────────────────────────────────────
    unhelpful_queries = (
        Query.objects
        .filter(was_helpful=False)
        .order_by('-created_at')
        .prefetch_related('laws_used')[:50]
    )

    # ── Top questions (counties) ──────────────────────────────────────────────
    top_counties = (
        Query.objects
        .filter(county__isnull=False)
        .exclude(county='')
        .values('county')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )

    # ── Most cited laws ───────────────────────────────────────────────────────
    # Count how many queries used each law
    top_laws = (
        Law.objects
        .annotate(query_count=Count('query'))
        .filter(query_count__gt=0)
        .order_by('-query_count')[:10]
    )

    # ── Recent activity (last 7 days by day) ─────────────────────────────────
    daily_counts = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        day_start = d.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        count = Query.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count()
        daily_counts.append({'date': d.strftime('%b %d'), 'count': count})

    # ── WhatsApp/Telegram users ───────────────────────────────────────────────
    total_bot_users = WhatsAppUser.objects.count()
    wa_users   = WhatsAppUser.objects.filter(phone__startswith='whatsapp:').count()
    tg_users   = WhatsAppUser.objects.filter(phone__startswith='tg:').count()
    meta_users = WhatsAppUser.objects.filter(phone__startswith='meta:').count()
    sms_users  = WhatsAppUser.objects.filter(phone__startswith='sms:').count()

    # ── Total laws ────────────────────────────────────────────────────────────
    total_law_sections = Law.objects.count()
    total_acts = Law.objects.values('title').distinct().count()

    # ── Handle POST — save correction ────────────────────────────────────────
    fix_message = None
    if request.method == 'POST':
        query_id       = request.POST.get('query_id')
        correct_section = request.POST.get('correct_section', '').strip()
        what_happened  = request.POST.get('what_actually_happened', '').strip()
        try:
            q = Query.objects.get(pk=query_id)
            q.correct_section        = correct_section
            q.what_actually_happened = what_happened
            q.save(update_fields=['correct_section', 'what_actually_happened'])
            fix_message = f"✅ Query #{query_id} updated."
        except Query.DoesNotExist:
            fix_message = f"❌ Query #{query_id} not found."

    context = {
        # Stats
        'total_queries':  total_queries,
        'queries_30d':    queries_30d,
        'queries_7d':     queries_7d,
        'queries_today':  queries_today,
        'helpful':        helpful,
        'not_helpful':    not_helpful,
        'no_feedback':    no_feedback,
        'satisfaction':   satisfaction,
        # Data
        'unhelpful_queries': unhelpful_queries,
        'top_counties':   top_counties,
        'top_laws':       top_laws,
        'daily_counts':   daily_counts,
        # Bot users
        'total_bot_users': total_bot_users,
        'wa_users':        wa_users,
        'tg_users':        tg_users,
        'meta_users':      meta_users,
        'sms_users':       sms_users,
        # Laws
        'total_law_sections': total_law_sections,
        'total_acts':         total_acts,
        # Misc
        'fix_message': fix_message,
    }
    return render(request, 'dashboard.html', context)


# ─── Lawyer Registration ──────────────────────────────────────────────────────

import re as _re

LSK_PATTERN = _re.compile(r'^P\.\d{1,4}/\d{1,4}/\d{4}$', _re.IGNORECASE)
KENYAN_PHONE = _re.compile(r'^\+254[17]\d{8}$')


def _validate_lsk(lsk: str) -> str | None:
    """Return error message or None if valid."""
    lsk = lsk.strip().upper()
    if not LSK_PATTERN.match(lsk):
        return "Invalid LSK format. Must be like P.105/1234/2024"
    return None


def _validate_phone(phone: str) -> str | None:
    phone = phone.strip()
    if not KENYAN_PHONE.match(phone):
        return "Phone must be a valid Kenyan number: +254XXXXXXXXX"
    return None


def lawyer_register(request):
    """
    GET  /lawyers/register/  — Step 1 registration form
    POST /lawyers/register/  — submit Step 1
    """
    from cases.models import Lawyer

    errors = {}
    data   = {}

    if request.method == 'POST':
        data = {
            'full_name':        request.POST.get('full_name', '').strip(),
            'email':            request.POST.get('email', '').strip().lower(),
            'phone':            request.POST.get('phone', '').strip(),
            'whatsapp':         request.POST.get('whatsapp', '').strip(),
            'lsk_number':       request.POST.get('lsk_number', '').strip().upper(),
            'lsk_name':         request.POST.get('lsk_name', '').strip(),
            'county':           request.POST.get('county', '').strip(),
            'county_secondary': request.POST.get('county_secondary', '').strip(),
            'specialties':      request.POST.getlist('specialties'),
            'years_experience': request.POST.get('years_experience', '0').strip(),
            'firm_name':        request.POST.get('firm_name', '').strip(),
            'bio':              request.POST.get('bio', '').strip(),
        }

        # Validate
        if not data['full_name']:
            errors['full_name'] = "Full name is required."
        if not data['email']:
            errors['email'] = "Email is required."
        if not data['county']:
            errors['county'] = "County is required."
        if not data['specialties']:
            errors['specialties'] = "Select at least one specialty."
        if not data['bio']:
            errors['bio'] = "Bio is required."

        phone_err = _validate_phone(data['phone'])
        if phone_err:
            errors['phone'] = phone_err

        lsk_err = _validate_lsk(data['lsk_number'])
        if lsk_err:
            errors['lsk_number'] = lsk_err

        if not errors:
            # Check uniqueness
            if Lawyer.objects.filter(email=data['email']).exists():
                errors['email'] = "An application with this email already exists."
            if Lawyer.objects.filter(lsk_number=data['lsk_number']).exists():
                errors['lsk_number'] = "This LSK number is already registered."

        if not errors:
            try:
                years = int(data['years_experience'])
            except ValueError:
                years = 0

            lawyer = Lawyer.objects.create(
                full_name        = data['full_name'],
                email            = data['email'],
                phone            = data['phone'],
                whatsapp         = data['whatsapp'] or data['phone'],
                telegram_username = data.get('telegram_username', '').strip().lstrip('@'),
                lsk_number       = data['lsk_number'],
                lsk_name         = data['lsk_name'],
                county           = data['county'],
                county_secondary = data['county_secondary'],
                specialties      = data['specialties'],
                years_experience = years,
                firm_name        = data['firm_name'],
                bio              = data['bio'],
                kyc_status       = Lawyer.KYC_L1_PASS,
            )
            # Redirect to document upload
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(f'/lawyers/documents/{lawyer.pk}/')

    context = {
        'errors': errors,
        'data':   data,
        'counties': COUNTIES,
        'specialty_choices': Lawyer.SPEC_CHOICES,
    }
    return render(request, 'lawyers/register.html', context)


def lawyer_documents(request, lawyer_id):
    """
    GET  /lawyers/documents/<id>/  — document upload form
    POST /lawyers/documents/<id>/  — save uploaded documents
    """
    from cases.models import Lawyer

    try:
        lawyer = Lawyer.objects.get(pk=lawyer_id)
    except Lawyer.DoesNotExist:
        from django.http import Http404
        raise Http404("Application not found.")

    # Only allow access if still in the upload phase
    if lawyer.kyc_status not in (Lawyer.KYC_L1_PASS, Lawyer.KYC_DOCS):
        return render(request, 'lawyers/status.html', {'lawyer': lawyer})

    errors  = {}
    success = False

    if request.method == 'POST':
        files = request.FILES

        # Require at least cert + ID + selfie
        if 'doc_practicing_cert' not in files:
            errors['doc_practicing_cert'] = "Practicing Certificate is required."
        if 'doc_national_id' not in files:
            errors['doc_national_id'] = "National ID photo is required."
        if 'doc_selfie_with_id' not in files:
            errors['doc_selfie_with_id'] = "Selfie with ID is required."
        if 'doc_kra_pin' not in files:
            errors['doc_kra_pin'] = "KRA PIN Certificate is required."

        if not errors:
            if 'doc_practicing_cert' in files:
                lawyer.doc_practicing_cert = files['doc_practicing_cert']
            if 'doc_national_id' in files:
                lawyer.doc_national_id = files['doc_national_id']
            if 'doc_selfie_with_id' in files:
                lawyer.doc_selfie_with_id = files['doc_selfie_with_id']
            if 'doc_kra_pin' in files:
                lawyer.doc_kra_pin = files['doc_kra_pin']
            if 'doc_video' in files:
                lawyer.doc_video = files['doc_video']
            if 'profile_photo' in files:
                lawyer.profile_photo = files['profile_photo']

            lawyer.kyc_status = Lawyer.KYC_DOCS
            lawyer.save()
            success = True

    context = {'lawyer': lawyer, 'errors': errors, 'success': success}
    return render(request, 'lawyers/documents.html', context)


def lawyer_status(request, lawyer_id):
    """GET /lawyers/status/<id>/ — check application status."""
    from cases.models import Lawyer
    try:
        lawyer = Lawyer.objects.get(pk=lawyer_id)
    except Lawyer.DoesNotExist:
        from django.http import Http404
        raise Http404()
    return render(request, 'lawyers/status.html', {'lawyer': lawyer})


def lawyers_connect(request):
    """
    POST /lawyers/connect/
    body: {query_id, lawyer_id, user_phone, consent}
    Creates a Lead and returns WhatsApp link for lawyer.
    """
    from cases.models import Lawyer, Lead, Query
    import json as _json

    if request.method != 'POST':
        from django.http import JsonResponse
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body      = _json.loads(request.body)
        query_id  = body.get('query_id')
        lawyer_id = body.get('lawyer_id')
        user_phone = body.get('user_phone', '').strip()
        consent   = bool(body.get('consent', False))
    except Exception:
        from django.http import JsonResponse
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    from django.http import JsonResponse
    try:
        lawyer = Lawyer.objects.get(pk=lawyer_id, kyc_status=Lawyer.KYC_VERIFIED, is_active=True)
        query  = Query.objects.get(pk=query_id)
    except (Lawyer.DoesNotExist, Query.DoesNotExist):
        return JsonResponse({'error': 'Not found'}, status=404)

    # Create lead (avoid duplicates)
    lead, created = Lead.objects.get_or_create(
        query=query,
        lawyer=lawyer,
        defaults={
            'user_phone':    user_phone if consent else '',
            'user_consented': consent,
        }
    )

    # Build WhatsApp message for lawyer
    story_short = query.story[:200]
    wa_message = (
        f"Habari {lawyer.full_name},\n\n"
        f"Mteja mpya kutoka HakiMkononi anahitaji msaada wako.\n\n"
        f"Swali lake: {story_short}\n\n"
        f"Wasiliana nao haraka. Asante!"
        if query.story else
        f"New client from HakiMkononi needs your help. Lead #{lead.pk}"
    )

    wa_link = lawyer.get_whatsapp_link(wa_message)

    return JsonResponse({
        'success':  True,
        'wa_link':  wa_link,
        'lead_id':  lead.pk,
        'lawyer':   lawyer.full_name,
        'created':  created,
    })


def lawyers_for_query(request, query_id):
    """
    GET /lawyers/for-query/<query_id>/
    Returns matched lawyers for a given query.
    Used by the answer page to show the connect card.
    """
    from cases.models import Lawyer, Query
    from django.http import JsonResponse

    try:
        query = Query.objects.get(pk=query_id)
    except Query.DoesNotExist:
        return JsonResponse({'lawyers': []})

    # Detect topic from laws used
    cats = set(query.laws_used.values_list('category', flat=True))
    topic_to_spec = {
        'employment':        ['employment'],
        'criminal_procedure': ['criminal'],
        'land':              ['land'],
        'landlord_tenant':   ['land'],
        'other':             ['family', 'consumer', 'data'],
        'consumer':          ['consumer'],
    }
    needed_specs = set()
    for cat in cats:
        needed_specs.update(topic_to_spec.get(cat, []))

    # Find verified lawyers — match county first, then specialty
    verified = Lawyer.objects.filter(
        kyc_status=Lawyer.KYC_VERIFIED,
        is_active=True,
    )

    # Try county match first
    county_match = verified.filter(county__iexact=query.county) if query.county else verified.none()

    # Fallback: any verified lawyer with matching specialty
    if county_match.count() < 2:
        all_lawyers = verified
    else:
        all_lawyers = county_match

    # Filter by specialty if we know the topic
    if needed_specs:
        spec_match = [
            l for l in all_lawyers
            if any(s in (l.specialties or []) for s in needed_specs)
        ]
        if len(spec_match) >= 1:
            lawyers = spec_match[:3]
        else:
            lawyers = list(all_lawyers[:3])
    else:
        lawyers = list(all_lawyers[:3])

    data = []
    for l in lawyers:
        data.append({
            'id':               l.pk,
            'name':             l.full_name,
            'county':           l.county,
            'specialties':      l.specialty_labels[:3],
            'firm':             l.firm_name,
            'years':            l.years_experience,
            'bio':              l.bio[:150] + ('…' if len(l.bio) > 150 else ''),
            'has_photo':        bool(l.profile_photo),
            'telegram':         l.telegram_username.lstrip('@') if l.telegram_username else '',
        })

    return JsonResponse({'lawyers': data, 'query_county': query.county or ''})
