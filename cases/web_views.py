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
        "nav_lawyers":      "Mawakili",

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
        "nav_lawyers":      "Lawyers",

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


@require_http_methods(["GET"])
def lawyers_landing(request):
    """
    GET /lawyers/
    Shows verified lawyers for clients to find + join section for lawyers.
    """
    from cases.models import Lawyer

    lang = _get_lang(request)

    # All verified lawyers — show to clients
    lawyers = Lawyer.objects.filter(
        kyc_status=Lawyer.KYC_VERIFIED, is_active=True
    ).order_by('-verified_at')

    verified_count = lawyers.count()

    # Optional county filter from query param
    f_county = request.GET.get('county', '').strip()
    f_specialty = request.GET.get('specialty', '').strip()

    if f_county:
        lawyers = lawyers.filter(county__iexact=f_county) | lawyers.filter(county_secondary__iexact=f_county)
    if f_specialty:
        lawyers = [l for l in lawyers if f_specialty in (l.specialties or [])]
    else:
        lawyers = list(lawyers[:50])

    return _render_with_lang(
        request, "lawyers/landing.html",
        {
            "verified_count": verified_count,
            "lawyers":        lawyers,
            "counties":       COUNTIES,
            "spec_choices":   Lawyer.SPEC_CHOICES,
            "f_county":       f_county,
            "f_specialty":    f_specialty,
        }, lang
    )


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


# ─── /dashboard/login/ and /dashboard/logout/ ────────────────────────────────

@require_http_methods(["GET", "POST"])
def dashboard_login(request):
    """
    GET  /dashboard/login/  — show the branded login page
    POST /dashboard/login/  — authenticate and redirect to dashboard
    """
    from django.contrib.auth import authenticate, login as auth_login
    from django.shortcuts import redirect

    # Already logged in as staff? Go straight to dashboard
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/dashboard/')

    error    = None
    username = ''
    next_url = request.GET.get('next', request.POST.get('next', '/dashboard/'))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff and user.is_active:
            auth_login(request, user)
            return redirect(next_url or '/dashboard/')
        elif user is not None and not user.is_staff:
            error = "Your account does not have platform access."
        else:
            error = "Username or password is incorrect."

    from django.middleware.csrf import get_token
    get_token(request)  # ensure CSRF cookie is set
    return render(request, 'dashboard_login.html', {
        'error':    error,
        'username': username,
        'next':     next_url,
    })


@require_http_methods(["GET", "POST"])
def dashboard_logout(request):
    """GET /dashboard/logout/ — log out and return to the login page."""
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    from django.shortcuts import redirect
    return redirect('/dashboard/login/')


# ─── /dashboard/ — Admin Learning Dashboard ──────────────────────────────────

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


@staff_member_required(login_url='/dashboard/login/')
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

    # ── 👎 Queries needing review — full feedback learning loop ──────────────
    # Pending review (most urgent — sorted by newest first)
    pending_review = (
        Query.objects
        .filter(was_helpful=False, review_status='pending')
        .order_by('-created_at')
        .prefetch_related('laws_used')[:30]
    )
    # Already fixed ones (last 10 for reference)
    fixed_this_week = (
        Query.objects
        .filter(was_helpful=False, review_status='fixed', created_at__gte=day7)
        .order_by('-created_at')[:10]
    )
    pending_count  = Query.objects.filter(was_helpful=False, review_status='pending').count()
    fixed_count    = Query.objects.filter(was_helpful=False, review_status='fixed').count()
    wontfix_count  = Query.objects.filter(was_helpful=False, review_status='wontfix').count()

    # ── Pattern analysis: which law categories have the most failures? ────────
    from django.db.models import FloatField, ExpressionWrapper
    failure_by_category = []
    for cat_code, cat_label in Law.CATEGORY_CHOICES:
        total_using_cat = (
            Query.objects
            .filter(laws_used__category=cat_code)
            .distinct().count()
        )
        unhelpful_using_cat = (
            Query.objects
            .filter(laws_used__category=cat_code, was_helpful=False)
            .distinct().count()
        )
        if total_using_cat > 0:
            rate = round(unhelpful_using_cat / total_using_cat * 100)
            failure_by_category.append({
                'category': cat_label,
                'code': cat_code,
                'total': total_using_cat,
                'failed': unhelpful_using_cat,
                'rate': rate,
            })
    failure_by_category.sort(key=lambda x: x['rate'], reverse=True)

    # ── Most common failing question patterns (top repeated stories) ──────────
    # Questions that got 👎 and whose first 60 chars appear more than once
    # (a proxy for "this type of question keeps failing")
    # Keep it simple — just show the raw 👎 queries with their category context
    unhelpful_queries = pending_review  # alias for template backward compat

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

    # ── Lawyer KYC pipeline ───────────────────────────────────────────────────
    from cases.models import Lawyer, LawyerPublicAnswer, LawyerReport
    lawyers_pending_review = Lawyer.objects.filter(kyc_status='docs_submitted').count()
    lawyers_verified       = Lawyer.objects.filter(kyc_status='verified', is_active=True).count()
    lawyers_total          = Lawyer.objects.count()

    # Full lawyer lists for dashboard management
    lawyers_awaiting = Lawyer.objects.filter(kyc_status='docs_submitted').order_by('created_at')
    lawyers_all      = Lawyer.objects.order_by('-created_at')[:50]

    # Pending public answers waiting for approval
    pending_public_answers = LawyerPublicAnswer.objects.filter(
        approved=False
    ).select_related('lawyer').order_by('-created_at')[:20]

    # Unreviewed reports
    unreviewed_reports = LawyerReport.objects.filter(
        reviewed=False
    ).select_related('lawyer').order_by('-created_at')[:20]

    # Current staff team members
    from django.contrib.auth import get_user_model
    User = get_user_model()
    team_members = User.objects.filter(is_staff=True).order_by('username')

    # Slang keywords list for dashboard management
    from cases.models import SlangKeyword
    slang_keywords = SlangKeyword.objects.order_by('topic', 'word')[:100]

    # Law sections — recent additions and unembedded ones
    unembedded_laws = Law.objects.filter(embedding_json='').exclude(content='')[:20]
    recent_laws     = Law.objects.order_by('-created_at')[:10]

    # Testimonials pending approval
    from cases.models import Testimonial
    pending_testimonials = Testimonial.objects.filter(approved=False).order_by('-created_at')[:20]
    approved_testimonial_count = Testimonial.objects.filter(approved=True).count()

    # Lead summary per lawyer (for platform owner visibility)
    from cases.models import Lead
    lead_summary = (
        Lead.objects
        .select_related('lawyer')
        .values('lawyer__full_name', 'lawyer__pk', 'lawyer__kyc_status')
        .annotate(
            total=Count('id'),
            new=Count('id', filter=Q(status='new')),
            contacted=Count('id', filter=Q(status='contacted')),
        )
        .filter(lawyer__kyc_status='verified')
        .order_by('-total')[:15]
    )

    # ── Handle POST — save correction or update review status ────────────────
    fix_message = None
    if request.method == 'POST':
        action = request.POST.get('action', 'save_fix')

        # ── Lawyer KYC actions ────────────────────────────────────────────────
        if action in ('verify_lawyer', 'reject_lawyer', 'suspend_lawyer', 'activate_lawyer'):
            lawyer_id = request.POST.get('lawyer_id', '').strip()
            try:
                lawyer = Lawyer.objects.get(pk=lawyer_id)
                if action == 'verify_lawyer':
                    lawyer.kyc_status  = 'verified'
                    lawyer.verified_by = request.user
                    lawyer.verified_at = timezone.now()
                    lawyer.is_active   = True
                    lawyer.save(update_fields=['kyc_status','verified_by','verified_at','is_active'])
                    # Send notification email
                    try:
                        from cases.web_views import _send_password_setup_link
                        _send_password_setup_link(lawyer)
                    except Exception:
                        pass
                    fix_message = f"✅ {lawyer.full_name} verified and notified."
                elif action == 'reject_lawyer':
                    reason = request.POST.get('rejection_reason', '').strip()
                    lawyer.kyc_status            = 'rejected'
                    lawyer.kyc_rejection_reason  = reason
                    lawyer.save(update_fields=['kyc_status','kyc_rejection_reason'])
                    try:
                        from cases.web_views import _send_rejection_notification
                        _send_rejection_notification(lawyer)
                    except Exception:
                        pass
                    fix_message = f"❌ {lawyer.full_name} rejected."
                elif action == 'suspend_lawyer':
                    lawyer.kyc_status = 'suspended'
                    lawyer.save(update_fields=['kyc_status'])
                    fix_message = f"⚠️ {lawyer.full_name} suspended."
                elif action == 'activate_lawyer':
                    lawyer.kyc_status = 'verified'
                    lawyer.is_active  = True
                    lawyer.save(update_fields=['kyc_status','is_active'])
                    fix_message = f"✅ {lawyer.full_name} reactivated."
            except Lawyer.DoesNotExist:
                fix_message = "❌ Lawyer not found."

        # ── Public answer moderation ──────────────────────────────────────────
        elif action in ('approve_public_answer', 'reject_public_answer'):
            pa_id = request.POST.get('pa_id', '').strip()
            try:
                pa = LawyerPublicAnswer.objects.get(pk=pa_id)
                if action == 'approve_public_answer':
                    pa.approved = True
                    pa.save(update_fields=['approved'])
                    # Notify the lawyer their answer is now live
                    try:
                        import os, threading
                        from django.core.mail import send_mail
                        login_url = "https://hakimkononi.onrender.com/lawyers/dashboard/"
                        subject = "✅ Your public answer is now live on HakiMkononi"
                        body = (
                            f"Hi {pa.lawyer.full_name},\n\n"
                            f"Your public answer has been reviewed and approved.\n\n"
                            f"Question: {pa.question[:200]}\n\n"
                            f"It is now visible on your public profile at:\n"
                            f"https://hakimkononi.onrender.com/lawyers/{pa.lawyer.pk}/\n\n"
                            f"Log in to your dashboard to post another:\n{login_url}\n\n"
                            f"HakiMkononi Team\n"
                        )
                        def _send_approval():
                            try:
                                from_email = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@hakimkononi.co.ke')
                                send_mail(subject, body, from_email, [pa.lawyer.email], fail_silently=True)
                            except Exception: pass
                        threading.Thread(target=_send_approval, daemon=True).start()
                    except Exception: pass
                    fix_message = f"✅ Public answer by {pa.lawyer.full_name} approved and they have been notified."
                else:
                    lawyer_email = pa.lawyer.email
                    lawyer_name  = pa.lawyer.full_name
                    pa.delete()
                    # Notify lawyer of rejection
                    try:
                        import os, threading
                        from django.core.mail import send_mail
                        subject = "Your public answer was not approved — HakiMkononi"
                        body = (
                            f"Hi {lawyer_name},\n\n"
                            f"Your public answer was reviewed but could not be approved at this time.\n\n"
                            f"Please log in to your dashboard and try submitting another:\n"
                            f"https://hakimkononi.onrender.com/lawyers/dashboard/\n\n"
                            f"HakiMkononi Team\n"
                        )
                        def _send_rejection():
                            try:
                                from_email = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@hakimkononi.co.ke')
                                send_mail(subject, body, from_email, [lawyer_email], fail_silently=True)
                            except Exception: pass
                        threading.Thread(target=_send_rejection, daemon=True).start()
                    except Exception: pass
                    fix_message = "🗑️ Public answer rejected, deleted, and lawyer notified."
            except LawyerPublicAnswer.DoesNotExist:
                fix_message = "❌ Answer not found."

        # ── Lawyer report review ──────────────────────────────────────────────
        elif action == 'review_report':
            from cases.models import LawyerReport
            report_id   = request.POST.get('report_id', '').strip()
            action_note = request.POST.get('action_taken', '').strip()
            try:
                report = LawyerReport.objects.get(pk=report_id)
                report.reviewed     = True
                report.action_taken = action_note
                report.save(update_fields=['reviewed', 'action_taken'])
                fix_message = f"✅ Report #{report_id} marked as reviewed."
            except LawyerReport.DoesNotExist:
                fix_message = "❌ Report not found."

        # ── Testimonial moderation ────────────────────────────────────────────
        elif action in ('approve_testimonial', 'reject_testimonial'):
            from cases.models import Testimonial
            t_id = request.POST.get('testimonial_id', '').strip()
            try:
                t = Testimonial.objects.get(pk=t_id)
                if action == 'approve_testimonial':
                    t.approved = True
                    t.save(update_fields=['approved'])
                    fix_message = f"✅ Testimonial from {t.name} approved — now shows publicly."
                else:
                    name = t.name
                    t.delete()
                    fix_message = f"🗑️ Testimonial from {name} rejected and deleted."
            except Testimonial.DoesNotExist:
                fix_message = "❌ Testimonial not found."

        # ── Slang keyword toggle/delete ───────────────────────────────────────
        elif action in ('toggle_slang', 'delete_slang'):
            from cases.models import SlangKeyword
            from cases.rag import invalidate_law_cache
            slang_id = request.POST.get('slang_id', '').strip()
            try:
                kw = SlangKeyword.objects.get(pk=slang_id)
                if action == 'toggle_slang':
                    kw.active = not kw.active
                    kw.save(update_fields=['active'])
                    try: invalidate_law_cache()
                    except Exception: pass
                    fix_message = f"{'✅ Activated' if kw.active else '⏸️ Deactivated'} keyword '{kw.word}'."
                else:
                    word = kw.word
                    kw.delete()
                    try: invalidate_law_cache()
                    except Exception: pass
                    fix_message = f"🗑️ Keyword '{word}' deleted."
            except SlangKeyword.DoesNotExist:
                fix_message = "❌ Keyword not found."

        # ── Build embeddings for new law sections ─────────────────────────────
        elif action == 'build_embeddings':
            try:
                from cases.rag import embed_text, invalidate_law_cache
                import time as _time
                unembedded = Law.objects.filter(embedding_json='').exclude(content='')
                total = unembedded.count()
                if total == 0:
                    fix_message = "ℹ️ All law sections already have embeddings — AI is fully up to date."
                else:
                    count = 0
                    failed = 0
                    for law in unembedded[:50]:  # cap at 50 per request to avoid timeout
                        try:
                            text = f"{law.title} {law.section}: {law.content}"
                            vec  = embed_text(text)
                            if vec:
                                law.set_embedding(vec)
                                law.save(update_fields=['embedding_json'])
                                count += 1
                                _time.sleep(0.15)  # stay within Gemini rate limits
                        except Exception:
                            failed += 1
                    try: invalidate_law_cache()
                    except Exception: pass
                    remaining = total - count - failed
                    fix_message = (
                        f"✅ Built embeddings for {count} law sections."
                        + (f" {failed} failed." if failed else "")
                        + (f" {remaining} still pending — click again to continue." if remaining > 0 else " All done!")
                    )
            except Exception as exc:
                fix_message = f"❌ Embedding error: {str(exc)[:200]}"

        # ── Add slang keyword ─────────────────────────────────────────────────
        elif action == 'add_slang':
            from cases.models import SlangKeyword
            word  = request.POST.get('slang_word', '').strip().lower()
            topic = request.POST.get('slang_topic', '').strip()
            lang  = request.POST.get('slang_lang', 'sw').strip()
            if word and topic:
                _, created = SlangKeyword.objects.get_or_create(
                    word=word, topic=topic,
                    defaults={'language': lang, 'active': True}
                )
                if created:
                    from cases.rag import invalidate_law_cache
                    try: invalidate_law_cache()
                    except Exception: pass
                    fix_message = f"✅ Slang keyword '{word}' added for topic '{topic}'."
                else:
                    fix_message = f"ℹ️ '{word}' already exists for that topic."
            else:
                fix_message = "❌ Word and topic are required."

        # ── Add law section ───────────────────────────────────────────────────
        elif action == 'add_law_section':
            from cases.models import Law
            title    = request.POST.get('law_title', '').strip()
            section  = request.POST.get('law_section', '').strip()
            category = request.POST.get('law_category', '').strip()
            content  = request.POST.get('law_content', '').strip()
            source   = request.POST.get('law_source', '').strip()
            if title and section and category and content:
                law = Law.objects.create(
                    title=title, section=section,
                    category=category, content=content,
                    source_url=source,
                )
                fix_message = (
                    f"✅ Law section '{section}' added under '{title}'. "
                    f"Run 'Build Embeddings' in admin to make it searchable."
                )
            else:
                fix_message = "❌ Title, section, category, and content are all required."

        # ── Team member management ────────────────────────────────────────────
        elif action == 'add_team_member':
            username = request.POST.get('tm_username', '').strip()
            password = request.POST.get('tm_password', '').strip()
            email    = request.POST.get('tm_email', '').strip()
            if username and len(password) >= 8:
                if User.objects.filter(username=username).exists():
                    fix_message = f"❌ Username '{username}' already taken."
                else:
                    u = User.objects.create_user(
                        username=username, password=password,
                        email=email, is_staff=True
                    )
                    fix_message = f"✅ Team member '{username}' added with dashboard access."
            else:
                fix_message = "❌ Username and password (min 8 chars) are required."

        elif action == 'remove_team_member':
            tm_id = request.POST.get('tm_id', '').strip()
            # Never allow removing yourself
            if str(request.user.pk) == tm_id:
                fix_message = "❌ You cannot remove your own account."
            else:
                try:
                    u = User.objects.get(pk=tm_id, is_staff=True)
                    uname = u.username
                    u.is_staff = False
                    u.save(update_fields=['is_staff'])
                    fix_message = f"✅ '{uname}' removed from dashboard access (account kept)."
                except User.DoesNotExist:
                    fix_message = "❌ User not found."

        # ── Existing query review actions ─────────────────────────────────────
        else:
            query_id        = request.POST.get('query_id')
            correct_section = request.POST.get('correct_section', '').strip()
            what_happened   = request.POST.get('what_actually_happened', '').strip()
            review_note     = request.POST.get('review_note', '').strip()
            try:
                q = Query.objects.get(pk=query_id)
                if action == 'mark_fixed':
                    q.correct_section        = correct_section
                    q.what_actually_happened = what_happened
                    q.review_status          = 'fixed'
                    q.review_note            = review_note
                    q.save(update_fields=['correct_section','what_actually_happened',
                                          'review_status','review_note'])
                    fix_message = f"✅ Query #{query_id} marked as fixed."
                elif action == 'mark_wontfix':
                    q.review_status = 'wontfix'
                    q.review_note   = review_note
                    q.save(update_fields=['review_status','review_note'])
                    fix_message = f"🔕 Query #{query_id} marked as won't fix."
                elif action == 'reopen':
                    q.review_status = 'pending'
                    q.save(update_fields=['review_status'])
                    fix_message = f"🔄 Query #{query_id} reopened for review."
                else:
                    q.correct_section        = correct_section
                    q.what_actually_happened = what_happened
                    q.save(update_fields=['correct_section', 'what_actually_happened'])
                    fix_message = f"✅ Query #{query_id} updated."
            except (Query.DoesNotExist, TypeError):
                fix_message = f"❌ Query not found."

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
        # Review workflow
        'unhelpful_queries':    unhelpful_queries,
        'pending_review':       pending_review,
        'fixed_this_week':      fixed_this_week,
        'pending_count':        pending_count,
        'fixed_count':          fixed_count,
        'wontfix_count':        wontfix_count,
        'failure_by_category':  failure_by_category,
        # Other data
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
        # Lawyers
        'lawyers_pending_review': lawyers_pending_review,
        'lawyers_verified':       lawyers_verified,
        'lawyers_total':          lawyers_total,
        'lawyers_awaiting':       lawyers_awaiting,
        'lawyers_all':            lawyers_all,
        'pending_public_answers': pending_public_answers,
        'unreviewed_reports':     unreviewed_reports,
        'team_members':           team_members,
        'current_user_id':        request.user.pk,
        # New management data
        'slang_keywords':         slang_keywords,
        'unembedded_laws':        unembedded_laws,
        'recent_laws':            recent_laws,
        'pending_testimonials':   pending_testimonials,
        'approved_testimonial_count': approved_testimonial_count,
        'lead_summary':           lead_summary,
        # Misc
        'fix_message': fix_message,
        # Form choices for inline forms
        'law_category_choices':   Law.CATEGORY_CHOICES,
        'slang_topic_choices':    [('employment','Employment / Job'),('criminal','Criminal / Police / Arrest'),('land','Land / Landlord / Tenant'),('family','Family / Marriage / Divorce'),('fraud','Fraud / Cybercrime'),('data','Data Protection / Privacy')],
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
            # Password — set now, used to log in after verification
            'password':         request.POST.get('password', ''),
            'confirm_password': request.POST.get('confirm_password', ''),
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

        # Password validation
        if len(data['password']) < 8:
            errors['password'] = "Password must be at least 8 characters."
        elif data['password'] != data['confirm_password']:
            errors['confirm_password'] = "Passwords do not match."

        if not errors:
            # Check uniqueness
            if Lawyer.objects.filter(email=data['email']).exists():
                errors['email'] = "An application with this email already exists."
            if Lawyer.objects.filter(lsk_number=data['lsk_number']).exists():
                errors['lsk_number'] = "This LSK number is already registered."

        if not errors:
            from django.contrib.auth.hashers import make_password as _make_password
            try:
                years = int(data['years_experience'])
            except ValueError:
                years = 0

            lawyer = Lawyer.objects.create(
                full_name         = data['full_name'],
                email             = data['email'],
                phone             = data['phone'],
                whatsapp          = data['whatsapp'] or data['phone'],
                telegram_username = data.get('telegram_username', '').strip().lstrip('@'),
                lsk_number        = data['lsk_number'],
                lsk_name          = data['lsk_name'],
                county            = data['county'],
                county_secondary  = data['county_secondary'],
                specialties       = data['specialties'],
                years_experience  = years,
                firm_name         = data['firm_name'],
                bio               = data['bio'],
                kyc_status        = Lawyer.KYC_L1_PASS,
                # Hash and store password immediately so the lawyer can log in
                # as soon as they are verified — no email link needed
                password_hash     = _make_password(data['password']),
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

            # ── Notify admin of new documents submission ───────────────
            _notify_admin_new_submission(lawyer)

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
    Optional: ?county=Nairobi  — override county filter
    Returns matched lawyers for a given query.
    """
    from cases.models import Lawyer, Query
    from django.http import JsonResponse

    try:
        query = Query.objects.get(pk=query_id)
    except Query.DoesNotExist:
        return JsonResponse({'lawyers': []})

    # County: explicit override from JS picker, then query county, then all
    county_override = request.GET.get('county', '').strip()
    effective_county = county_override or query.county or ''

    # Detect topic from laws used — for specialty matching
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

    # Try county match first — use effective_county (explicit picker > query county > none)
    county_match = verified.filter(
        county__iexact=effective_county
    ) if effective_county else verified.none()

    # Also check secondary county
    if county_match.count() == 0 and effective_county:
        county_match = verified.filter(county_secondary__iexact=effective_county)

    # Fallback: if there's no county to match on at all, show any verified lawyer.
    # If the user (or the query) specified a county with no coverage, do NOT silently
    # show lawyers from other counties — that would misleadingly suggest local coverage.
    if not effective_county:
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
            'photo_url':        l.profile_photo_url if hasattr(l, 'profile_photo_url') and l.profile_photo_url else '',
            'telegram':         l.telegram_username.lstrip('@') if l.telegram_username else '',
            'wa_num':           l.display_phone.replace('+', '').replace(' ', ''),
        })

    return JsonResponse({'lawyers': data, 'query_county': effective_county or query.county or ''})


# ═══════════════════════════════════════════════════════════════════════════
# ─── ADMIN NOTIFICATION ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

def _notify_admin_new_submission(lawyer):
    """
    Send an email to all staff when a lawyer submits documents.
    Uses Django's send_mail — falls back gracefully if email not configured.
    Always logs to console (visible in Render logs).
    """
    import os, threading
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail

    review_url = f"https://hakimkononi.onrender.com/admin/cases/lawyer/{lawyer.pk}/change/"
    subject = f"[HakiMkononi] New lawyer submission: {lawyer.full_name}"
    body = (
        f"A new lawyer has submitted documents for KYC review.\n\n"
        f"Name:       {lawyer.full_name}\n"
        f"LSK Number: {lawyer.lsk_number}\n"
        f"County:     {lawyer.county}\n"
        f"Email:      {lawyer.email}\n"
        f"Phone:      {lawyer.phone}\n"
        f"Submitted:  {lawyer.updated_at.strftime('%d %b %Y %H:%M') if lawyer.updated_at else 'now'}\n\n"
        f"Review at: {review_url}\n\n"
        "Use the admin panel to Verify or Reject this application.\n"
    )

    # Always log — visible in Render logs even without email configured
    print(f"\n[LAWYER KYC] 📋 New submission: {lawyer.full_name} ({lawyer.lsk_number})")
    print(f"[LAWYER KYC] Review at: {review_url}\n")

    # Send email in background thread — don't block the HTTP response
    def _send():
        try:
            User = get_user_model()
            staff_emails = list(
                User.objects.filter(is_staff=True, is_active=True)
                .exclude(email='')
                .values_list('email', flat=True)
            )
            admin_email = os.getenv('ADMIN_EMAIL', '').strip()
            if admin_email and admin_email not in staff_emails:
                staff_emails.append(admin_email)

            if not staff_emails:
                print("[LAWYER KYC] No staff emails found — email not sent.")
                return

            from_email = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@hakimkononi.co.ke')
            send_mail(subject, body, from_email, staff_emails, fail_silently=True)
            print(f"[LAWYER KYC] Email notification sent to: {', '.join(staff_emails)}")
        except Exception as e:
            print(f"[LAWYER KYC] Email error (non-fatal): {e}")

    threading.Thread(target=_send, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════
# ─── PUBLIC LAWYER PROFILE PAGE ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def lawyer_profile(request, lawyer_id):
    """
    GET /lawyers/<id>/
    Public profile page for a verified lawyer.
    Only shows verified, active lawyers.
    """
    from cases.models import Lawyer, Lead
    from django.http import Http404

    try:
        lawyer = Lawyer.objects.get(pk=lawyer_id, kyc_status=Lawyer.KYC_VERIFIED, is_active=True)
    except Lawyer.DoesNotExist:
        raise Http404("Lawyer profile not found.")

    lang = _get_lang(request)

    # Build a pre-filled WhatsApp message
    wa_msg = (
        f"Habari {lawyer.full_name}, ninahitaji msaada wa kisheria. "
        f"Nilikupata kwenye HakiMkononi."
        if lang == 'sw' else
        f"Hello {lawyer.full_name}, I need legal help. I found you on HakiMkononi."
    )
    wa_link = lawyer.get_whatsapp_link(wa_msg)
    tg_link = lawyer.get_telegram_link()

    # Count leads as a rough popularity indicator (no sensitive data exposed)
    lead_count = Lead.objects.filter(lawyer=lawyer).count()

    # Approved public answers for this lawyer
    from cases.models import LawyerPublicAnswer
    public_answers = LawyerPublicAnswer.objects.filter(
        lawyer=lawyer, approved=True
    ).order_by('-created_at')[:5]

    return _render_with_lang(request, 'lawyers/profile.html', {
        'lawyer':         lawyer,
        'wa_link':        wa_link,
        'tg_link':        tg_link,
        'lead_count':     lead_count,
        'public_answers': public_answers,
        # True when the logged-in lawyer is viewing their own profile
        'is_own_profile': request.session.get('lawyer_id') == lawyer.pk,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER DASHBOARD — AUTH HELPERS ─────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

def _get_logged_in_lawyer(request):
    """Return the Lawyer object from session, or None if not logged in."""
    from cases.models import Lawyer
    lawyer_id = request.session.get('lawyer_id')
    if not lawyer_id:
        return None
    try:
        return Lawyer.objects.get(pk=lawyer_id, is_active=True)
    except Lawyer.DoesNotExist:
        del request.session['lawyer_id']
        return None


def _lawyer_login_required(fn):
    """Decorator — redirects to lawyer login page if not authenticated."""
    from functools import wraps
    from django.shortcuts import redirect

    @wraps(fn)
    def wrapper(request, *args, **kwargs):
        lawyer = _get_logged_in_lawyer(request)
        if not lawyer:
            return redirect(f'/lawyers/login/?next={request.path}')
        return fn(request, *args, lawyer=lawyer, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER LOGIN / LOGOUT ───────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def lawyer_login(request):
    """GET /lawyers/login/   POST /lawyers/login/"""
    from django.utils import timezone

    # Already logged in?
    if _get_logged_in_lawyer(request):
        return _redirect_dashboard()

    lang = _get_lang(request)
    error = None

    if request.method == 'POST':
        from cases.models import Lawyer
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        try:
            lawyer = Lawyer.objects.get(email=email, is_active=True)
        except Lawyer.DoesNotExist:
            lawyer = None

        if lawyer and lawyer.check_password(password):
            # Successful login
            request.session['lawyer_id'] = lawyer.pk
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
            lawyer.last_login_at = timezone.now()
            lawyer.save(update_fields=['last_login_at'])
            next_url = request.GET.get('next', '/lawyers/dashboard/')
            from django.shortcuts import redirect
            return redirect(next_url)
        elif lawyer and not lawyer.password_hash:
            error = (
                "Your account is verified but you haven't set a password yet. "
                "Check your email for a setup link, or contact admin@hakimkononi.co.ke"
                if lang == 'en' else
                "Akaunti yako imethibitishwa lakini bado hujaweka nenosiri. "
                "Angalia barua pepe yako kwa kiungo cha usanidi."
            )
        else:
            error = (
                "Email or password is incorrect." if lang == 'en'
                else "Barua pepe au nenosiri si sahihi."
            )

    return _render_with_lang(request, 'lawyers/login.html', {'error': error}, lang)


def lawyer_logout(request):
    """GET /lawyers/logout/"""
    if 'lawyer_id' in request.session:
        del request.session['lawyer_id']
    from django.shortcuts import redirect
    return redirect('/lawyers/')


def _redirect_dashboard():
    from django.shortcuts import redirect
    return redirect('/lawyers/dashboard/')


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER SET PASSWORD ─────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def lawyer_set_password(request):
    """
    GET  /lawyers/set-password/?token=<email_b64>
    POST /lawyers/set-password/?token=<email_b64>

    Lets a lawyer set their dashboard password for the first time
    (or reset it). Token = base64(email) — simple, no DB needed.
    Admin can also manually trigger this by sending the link.
    """
    import base64
    from cases.models import Lawyer

    lang = _get_lang(request)
    token = request.GET.get('token', '').strip()
    error = None
    success = False
    lawyer = None

    if token:
        try:
            email = base64.urlsafe_b64decode(token.encode()).decode('utf-8')
            lawyer = Lawyer.objects.get(email=email, is_active=True)
        except Exception:
            error = "Invalid or expired link." if lang == 'en' else "Kiungo si sahihi au kimeisha muda."

    if request.method == 'POST' and lawyer:
        pw1 = request.POST.get('password', '')
        pw2 = request.POST.get('confirm', '')
        if len(pw1) < 8:
            error = "Password must be at least 8 characters." if lang == 'en' else "Nenosiri lazima liwe na herufi angalau 8."
        elif pw1 != pw2:
            error = "Passwords do not match." if lang == 'en' else "Manenosiri hayafanani."
        else:
            lawyer.set_password(pw1)
            lawyer.save(update_fields=['password_hash'])
            success = True
            # Auto-login
            request.session['lawyer_id'] = lawyer.pk

    return _render_with_lang(request, 'lawyers/set_password.html', {
        'token':   token,
        'lawyer':  lawyer,
        'error':   error,
        'success': success,
    }, lang)


def _send_rejection_notification(lawyer):
    """
    Notify a lawyer when their KYC application is rejected.
    Always logs to console, sends email if configured.
    """
    import os, threading
    from django.core.mail import send_mail

    rejection_reason = lawyer.kyc_rejection_reason or "Your application did not meet our verification requirements."
    reapply_url = f"https://hakimkononi.onrender.com/lawyers/register/"

    subject = "HakiMkononi — Update on your lawyer application"
    body = (
        f"Dear {lawyer.full_name},\n\n"
        f"Thank you for applying to join HakiMkononi.\n\n"
        f"After reviewing your application, we were unable to verify your credentials at this time.\n\n"
        f"Reason: {rejection_reason}\n\n"
        f"You are welcome to reapply once you have addressed the above:\n"
        f"{reapply_url}\n\n"
        f"If you believe this decision is incorrect or have questions, "
        f"please contact us at admin@hakimkononi.co.ke\n\n"
        f"HakiMkononi Team\n"
    )

    print(f"[LAWYER KYC] ❌ Rejected: {lawyer.full_name} ({lawyer.email})")

    def _send():
        try:
            from_email = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@hakimkononi.co.ke')
            send_mail(subject, body, from_email, [lawyer.email], fail_silently=True)
            print(f"[LAWYER KYC] Rejection email sent to {lawyer.email}")
        except Exception as e:
            print(f"[LAWYER KYC] Rejection email error: {e}")

    threading.Thread(target=_send, daemon=True).start()


def _send_password_setup_link(lawyer):
    """
    Notify a newly verified lawyer that their KYC passed and they can now log in.
    Called from the Django admin `verify_lawyers` action.
    If the lawyer already set a password at registration, we just tell them to log in.
    If not (legacy lawyers), we include the password setup link as well.
    """
    import os, base64, threading
    from django.core.mail import send_mail

    login_url = "https://hakimkononi.onrender.com/lawyers/login/"
    token = base64.urlsafe_b64encode(lawyer.email.encode()).decode()
    setup_url = f"https://hakimkononi.onrender.com/lawyers/set-password/?token={token}"

    has_password = bool(lawyer.password_hash)

    subject = "🎉 Congratulations — You are now verified on HakiMkononi!"
    body = (
        f"Dear {lawyer.full_name},\n\n"
        f"Great news! Your application to join HakiMkononi has been reviewed and verified.\n\n"
        f"Your profile is now live on the platform. Clients in {lawyer.county} asking about "
        f"{', '.join(lawyer.specialty_labels[:2]) or 'your specialties'} will see you and can "
        f"connect with you directly via WhatsApp or Telegram.\n\n"
    )

    if has_password:
        body += (
            f"You already set your password during registration.\n"
            f"Log in to your lawyer dashboard here:\n"
            f"{login_url}\n\n"
            f"Use your registered email: {lawyer.email}\n\n"
        )
    else:
        body += (
            f"To access your lawyer dashboard, set your password here:\n"
            f"{setup_url}\n\n"
            f"This link is tied to your email address ({lawyer.email}).\n\n"
        )

    body += (
        f"Your dashboard lets you:\n"
        f"  • See clients who connected with you (leads)\n"
        f"  • Track lead status (new, contacted, closed)\n"
        f"  • Update your bio, WhatsApp, and contact details\n\n"
        f"Welcome to the team!\n"
        f"HakiMkononi\n"
    )

    print(f"[LAWYER] Verification notification for {lawyer.full_name}: {login_url if has_password else setup_url}")

    def _send():
        try:
            from_email = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@hakimkononi.co.ke')
            send_mail(subject, body, from_email, [lawyer.email], fail_silently=True)
            print(f"[LAWYER] Password setup email sent to {lawyer.email}")
        except Exception as e:
            print(f"[LAWYER] Email error: {e}")

    threading.Thread(target=_send, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER DASHBOARD ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@_lawyer_login_required
def lawyer_dashboard(request, lawyer=None):
    """
    GET  /lawyers/dashboard/
    POST /lawyers/dashboard/   — update bio/contact details
    """
    from cases.models import Lead
    from django.utils import timezone
    from datetime import timedelta

    lang = _get_lang(request)
    save_msg = None

    # Handle profile update
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'update_profile':
            bio   = request.POST.get('bio', '').strip()[:500]
            wa    = request.POST.get('whatsapp', '').strip()
            tg    = request.POST.get('telegram_username', '').strip().lstrip('@')
            county2 = request.POST.get('county_secondary', '').strip()
            photo_url = request.POST.get('profile_photo_url', '').strip()
            if bio:
                lawyer.bio = bio
            if wa:
                lawyer.whatsapp = wa
            if tg is not None:
                lawyer.telegram_username = tg
            lawyer.county_secondary = county2

            # Handle direct photo upload — goes to Cloudinary when configured
            photo_file = request.FILES.get('profile_photo_file')
            if photo_file:
                if photo_file.size > 5 * 1024 * 1024:
                    save_msg = "❌ Photo too large. Max 5 MB." if lang == 'en' else "❌ Picha ni kubwa sana. Hadi 5 MB."
                else:
                    lawyer.profile_photo = photo_file
                    if hasattr(lawyer, 'profile_photo_url'):
                        lawyer.profile_photo_url = ''  # clear URL since we have a real file
            elif hasattr(lawyer, 'profile_photo_url'):
                lawyer.profile_photo_url = photo_url

            update_fields = ['bio', 'whatsapp', 'telegram_username', 'county_secondary', 'updated_at']
            if photo_file and photo_file.size <= 5 * 1024 * 1024:
                update_fields += ['profile_photo']
                if hasattr(lawyer, 'profile_photo_url'):
                    update_fields.append('profile_photo_url')
            elif hasattr(lawyer, 'profile_photo_url'):
                update_fields.append('profile_photo_url')

            if not save_msg:
                lawyer.save(update_fields=update_fields)
                save_msg = "✅ Profile updated." if lang == 'en' else "✅ Wasifu umesasishwa."
        elif action == 'update_lead_status':
            lead_id = request.POST.get('lead_id', '')
            new_status = request.POST.get('status', '')
            valid_statuses = dict(Lead.STATUS_CHOICES)
            if lead_id and new_status in valid_statuses:
                Lead.objects.filter(pk=lead_id, lawyer=lawyer).update(status=new_status)
                save_msg = "Lead updated." if lang == 'en' else "Mteja amesasishwa."
        elif action == 'post_public_answer':
            from cases.models import LawyerPublicAnswer
            from datetime import timedelta as _td
            question = request.POST.get('pa_question', '').strip()[:500]
            answer_text = request.POST.get('pa_answer', '').strip()[:800]
            if question and answer_text:
                # Block if one is already pending review
                pending = LawyerPublicAnswer.objects.filter(
                    lawyer=lawyer, approved=False
                ).count()
                # Also enforce one per 7 days (whether approved or not)
                week_ago = timezone.now() - _td(days=7)
                recent   = LawyerPublicAnswer.objects.filter(
                    lawyer=lawyer, created_at__gte=week_ago
                ).count()
                if pending >= 1:
                    save_msg = (
                        "You already have a public answer pending review. "
                        "Wait for it to be approved before posting another."
                        if lang == 'en' else
                        "Una jibu moja linalongojea ukaguzi. "
                        "Subiri lipitishwe kabla ya kutuma lingine."
                    )
                elif recent >= 1:
                    save_msg = (
                        "You can submit one public answer per week. "
                        "Please wait 7 days before posting another."
                        if lang == 'en' else
                        "Unaweza kutuma jibu moja la umma kwa wiki. "
                        "Tafadhali subiri siku 7 kabla ya kutuma lingine."
                    )
                else:
                    LawyerPublicAnswer.objects.create(
                        lawyer=lawyer,
                        question=question,
                        answer=answer_text,
                        lang=lang,
                        approved=False,
                    )
                    save_msg = (
                        "Public answer submitted for review. It will appear on your profile once approved."
                        if lang == 'en' else
                        "Jibu la umma limetumwa kwa ukaguzi. Litaonekana kwenye wasifu wako baada ya kupitishwa."
                    )
            else:
                save_msg = "Please fill in both the question and answer." if lang == 'en' else "Tafadhali jaza swali na jibu vyote."

    # Stats
    now   = timezone.now()
    day30 = now - timedelta(days=30)
    day7  = now - timedelta(days=7)

    all_leads   = Lead.objects.filter(lawyer=lawyer).order_by('-created_at')
    leads_30d   = all_leads.filter(created_at__gte=day30)
    leads_7d    = all_leads.filter(created_at__gte=day7)
    recent_leads = all_leads.select_related('query')[:10]

    # Lead status breakdown — how many are still unactioned vs contacted vs closed
    new_count       = all_leads.filter(status=Lead.STATUS_NEW).count()
    contacted_count = all_leads.filter(status=Lead.STATUS_CONTACTED).count()
    closed_count    = all_leads.filter(status=Lead.STATUS_CLOSED).count()

    # Top counties driving leads (which county the user's question came from)
    county_counts = (
        all_leads.exclude(query__county='')
        .values('query__county')
        .annotate(n=Count('id'))
        .order_by('-n')[:5]
    )
    top_counties = [{'county': c['query__county'], 'count': c['n']} for c in county_counts]

    # Fetch this lawyer's approved public answers (for profile display) and pending (for dashboard)
    from cases.models import LawyerPublicAnswer
    public_answers_approved = LawyerPublicAnswer.objects.filter(
        lawyer=lawyer, approved=True
    ).order_by('-created_at')[:5]
    public_answers_pending  = LawyerPublicAnswer.objects.filter(
        lawyer=lawyer, approved=False
    ).order_by('-created_at')[:3]

    # Build password setup link (show if no password set yet)
    import base64
    setup_token = base64.urlsafe_b64encode(lawyer.email.encode()).decode()

    return _render_with_lang(request, 'lawyers/dashboard.html', {
        'lawyer':          lawyer,
        'all_leads':       all_leads.count(),
        'leads_30d':       leads_30d.count(),
        'leads_7d':        leads_7d.count(),
        'recent_leads':    recent_leads,
        'new_count':       new_count,
        'contacted_count': contacted_count,
        'closed_count':    closed_count,
        'top_counties':    top_counties,
        'save_msg':        save_msg,
        'setup_token':     setup_token,
        'has_password':    bool(lawyer.password_hash),
        'counties':        COUNTIES,
        'public_answers_approved': public_answers_approved,
        'public_answers_pending':  public_answers_pending,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER STATUS CHECK (by email) ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def lawyer_check_status(request):
    """
    GET  /lawyers/check-status/
    POST /lawyers/check-status/  — enter email → see KYC status

    Lets a lawyer look up their application by email without logging in.
    """
    from cases.models import Lawyer

    lang = _get_lang(request)
    lawyer = None
    error = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            error = "Please enter your email." if lang == 'en' else "Tafadhali ingiza barua pepe yako."
        else:
            try:
                lawyer = Lawyer.objects.get(email=email)
            except Lawyer.DoesNotExist:
                error = (
                    "No application found with that email address. "
                    "Please check the email you used to register."
                    if lang == 'en' else
                    "Hakuna maombi yaliyopatikana kwa barua pepe hiyo. "
                    "Tafadhali angalia barua pepe uliyotumia kusajili."
                )

    return _render_with_lang(request, 'lawyers/check_status.html', {
        'lawyer': lawyer,
        'error':  error,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── COURT AUDIO PAGE ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def court_audio_page(request):
    """
    GET /court-audio/
    Page where Wanjiku can upload a recording of her court hearing
    and get a plain-language Swahili summary of what the judge said.
    """
    lang = _get_lang(request)
    return _render_with_lang(request, 'court_audio.html', {}, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── TESTIMONIALS ────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def submit_testimonial(request):
    """
    GET  /testimonials/submit/  — show submission form
    POST /testimonials/submit/  — save a new testimonial (pending admin approval)
    """
    from cases.models import Testimonial

    lang = _get_lang(request)
    success = False
    error   = None

    if request.method == 'POST':
        name      = request.POST.get('name', '').strip()[:100]
        county    = request.POST.get('county', '').strip()[:100]
        case_type = request.POST.get('case_type', '').strip()[:100]
        story     = request.POST.get('story', '').strip()
        outcome   = request.POST.get('outcome', '').strip()[:200]

        if not name or not story or len(story) < 20:
            error = (
                "Please fill in your name and your story (at least 20 characters)."
                if lang == 'en' else
                "Tafadhali jaza jina lako na hadithi yako (angalau maneno 20)."
            )
        else:
            Testimonial.objects.create(
                name=name,
                county=county,
                case_type=case_type,
                story=story,
                outcome=outcome,
                lang=lang,
                approved=False,
            )
            success = True

    return _render_with_lang(request, 'testimonials/submit.html', {
        'success': success,
        'error':   error,
        'counties': COUNTIES,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER DIRECTORY ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def lawyers_directory(request):
    """
    GET /lawyers/directory/
    Browsable, filterable public directory of all verified lawyers.
    Filters: county, specialty, pro_bono, min_years, q (name/firm search), sort
    """
    from cases.models import Lawyer, Lead
    from django.db.models import Count, Avg

    lang = _get_lang(request)

    # Read filter params
    f_county    = request.GET.get('county', '').strip()
    f_specialty = request.GET.get('specialty', '').strip()
    f_pro_bono  = request.GET.get('pro_bono', '').strip()
    f_min_years = request.GET.get('min_years', '').strip()
    f_search    = request.GET.get('q', '').strip()
    f_sort      = request.GET.get('sort', 'recent').strip()

    # Base queryset — only verified, active lawyers
    qs = Lawyer.objects.filter(
        kyc_status=Lawyer.KYC_VERIFIED, is_active=True
    )

    # Apply filters
    if f_county:
        from django.db.models import Q as _Q
        qs = qs.filter(_Q(county__iexact=f_county) | _Q(county_secondary__iexact=f_county))
    if f_specialty:
        qs = qs.filter(specialties__contains=[f_specialty])
    if f_pro_bono == '1':
        qs = qs.filter(pro_bono=True)
    if f_min_years.isdigit():
        qs = qs.filter(years_experience__gte=int(f_min_years))
    if f_search:
        from django.db.models import Q as _Q2
        qs = qs.filter(
            _Q2(full_name__icontains=f_search) |
            _Q2(firm_name__icontains=f_search) |
            _Q2(bio__icontains=f_search)
        )

    # Annotate with lead count and avg rating for display
    qs = qs.annotate(
        lead_count=Count('leads', distinct=True),
        avg_rating=Avg('leads__rating'),
    )

    # Sort
    sort_map = {
        'recent':     '-verified_at',
        'experience': '-years_experience',
        'name':       'full_name',
        'leads':      '-lead_count',
    }
    qs = qs.order_by(sort_map.get(f_sort, '-verified_at'))

    total   = qs.count()
    lawyers = list(qs[:50])

    spec_choices = Lawyer.SPEC_CHOICES

    return _render_with_lang(request, 'lawyers/directory.html', {
        'lawyers':      lawyers,
        'total':        total,
        'counties':     COUNTIES,
        'spec_choices': spec_choices,
        'f_county':    f_county,
        'f_specialty': f_specialty,
        'f_pro_bono':  f_pro_bono,
        'f_min_years': f_min_years,
        'f_search':    f_search,
        'f_sort':      f_sort,
        'has_filters': bool(f_county or f_specialty or f_pro_bono or f_min_years or f_search),
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── LSK FEE SCHEDULE ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def fee_schedule(request):
    """
    GET /fees/
    Standalone LSK fee schedule page so Wanjiku knows what to expect
    before hiring a lawyer, independent of asking a legal question.
    """
    from cases.ai_engine import LSK_FEE_GUIDE

    lang = _get_lang(request)

    # Build a display-friendly list ordered by how common each case type is
    display_order = [
        ('employment',       '👔' if lang == 'en' else '👔', 'Employment & Labour', 'Ajira na Kazi'),
        ('landlord_tenant',  '🏠', 'Landlord & Tenant', 'Landlord na Mpangaji'),
        ('criminal_procedure','🚔', 'Criminal / Police', 'Jinai / Polisi'),
        ('land',             '🌍', 'Land & Succession', 'Ardhi na Urithi'),
        ('children',         '👶', 'Children & Family', 'Watoto na Familia'),
        ('consumer',         '🛒', 'Consumer Rights', 'Haki za Mlaji'),
        ('constitution',     '📜', 'Constitutional', 'Kikatiba'),
        ('other',            '⚖️', 'Other Matters', 'Mambo Mengine'),
    ]

    fees = []
    for key, icon, label_en, label_sw in display_order:
        entry = LSK_FEE_GUIDE.get(key, {})
        label = label_en if lang == 'en' else label_sw
        data  = entry.get(lang, entry.get('sw', {}))
        fees.append({
            'key':    key,
            'icon':   icon,
            'label':  label,
            'range':  data.get('range', ''),
            'note':   data.get('note', ''),
        })

    return _render_with_lang(request, 'fees.html', {
        'fees': fees,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER RATING (post-contact feedback) ───────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def lawyer_rate(request, lead_id):
    """
    GET  /lawyers/rate/<lead_id>/  — show rating form
    POST /lawyers/rate/<lead_id>/  — save rating

    Uses a token-in-URL approach so Wanjiku doesn't need an account.
    The token is base64(lead_id + salt) — not cryptographically strong but
    sufficient to prevent casual manipulation of other people's ratings.
    """
    import base64, hmac, hashlib, os
    from cases.models import Lead
    from django.utils import timezone

    lang  = _get_lang(request)
    token = request.GET.get('t', request.POST.get('t', ''))

    # Validate token
    secret = os.getenv('SECRET_KEY', 'insecure')
    expected = hmac.new(secret.encode(), str(lead_id).encode(), hashlib.sha256).hexdigest()[:16]
    if token != expected:
        return _render_with_lang(request, 'lawyers/rate.html', {
            'error': True,
        }, lang)

    try:
        lead = Lead.objects.select_related('lawyer').get(pk=lead_id)
    except Lead.DoesNotExist:
        return _render_with_lang(request, 'lawyers/rate.html', {
            'error': True,
        }, lang)

    success = False
    error_msg = None

    if request.method == 'POST':
        try:
            rating_val = int(request.POST.get('rating', '0'))
            rating_text = request.POST.get('rating_text', '').strip()[:1000]
        except (ValueError, TypeError):
            rating_val = 0

        if rating_val < 1 or rating_val > 5:
            error_msg = "Please choose a rating between 1 and 5." if lang == 'en' else "Tafadhali chagua alama kati ya 1 na 5."
        elif lead.rating is not None:
            error_msg = "You have already rated this lawyer." if lang == 'en' else "Tayari umempa alama wakili huyu."
        else:
            lead.rating     = rating_val
            lead.rating_text = rating_text
            lead.rating_at   = timezone.now()
            lead.save(update_fields=['rating', 'rating_text', 'rating_at'])
            success = True

    return _render_with_lang(request, 'lawyers/rate.html', {
        'lead':    lead,
        'lawyer':  lead.lawyer,
        'success': success,
        'error_msg': error_msg,
        'token':   token,
        'already_rated': lead.rating is not None,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── LAWYER REPORT ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def lawyer_report(request, lawyer_id):
    """
    GET  /lawyers/<id>/report/  — show report form
    POST /lawyers/<id>/report/  — save report

    Any user can report a lawyer. No account needed.
    """
    from cases.models import Lawyer, LawyerReport
    from django.http import Http404

    try:
        lawyer = Lawyer.objects.get(pk=lawyer_id, kyc_status=Lawyer.KYC_VERIFIED, is_active=True)
    except Lawyer.DoesNotExist:
        raise Http404("Lawyer not found.")

    lang    = _get_lang(request)
    success = False
    error   = None

    if request.method == 'POST':
        reason       = request.POST.get('reason', '').strip()
        contact_info = request.POST.get('contact_info', '').strip()[:100]

        if not reason or len(reason) < 20:
            error = (
                "Please describe what happened (at least 20 characters)."
                if lang == 'en' else
                "Tafadhali eleza kilichotokea (angalau herufi 20)."
            )
        else:
            LawyerReport.objects.create(
                lawyer=lawyer,
                reason=reason[:2000],
                contact_info=contact_info,
            )
            # Notify admin by email/log
            print(f"[LAWYER REPORT] Lawyer #{lawyer.pk} ({lawyer.full_name}) reported. "
                  f"Reason: {reason[:100]}")
            success = True

    return _render_with_lang(request, 'lawyers/report.html', {
        'lawyer':  lawyer,
        'success': success,
        'error':   error,
    }, lang)


# ═══════════════════════════════════════════════════════════════════════════
# ─── PRE-CONTACT BRIEFING (JSON endpoint) ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def lawyer_briefing(request, lawyer_id):
    """
    GET /lawyers/<id>/briefing/?query_id=N
    Returns the fee guide and tips for this lawyer/query combination.
    Used by the modal that shows before Wanjiku contacts the lawyer.
    """
    from cases.models import Lawyer, Query, Lead
    from cases.ai_engine import LSK_FEE_GUIDE
    from django.http import JsonResponse

    lang = _get_lang(request)

    try:
        lawyer = Lawyer.objects.get(pk=lawyer_id, kyc_status=Lawyer.KYC_VERIFIED, is_active=True)
    except Lawyer.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    # Try to get fee context from the query's laws
    query_id = request.GET.get('query_id', '').strip()
    fee_range = ''
    fee_note  = ''
    if query_id and query_id.isdigit():
        try:
            query = Query.objects.get(pk=int(query_id))
            cats  = list({l.category for l in query.laws_used.all() if l.category})
            from cases.ai_engine import get_fee_guide
            fg = get_fee_guide(cats, lang=lang)
            if fg:
                fee_range = fg['range']
                fee_note  = fg['note']
        except Query.DoesNotExist:
            pass

    # Fallback: pick based on lawyer's primary specialty
    if not fee_range and lawyer.specialties:
        spec_to_cat = {
            'employment': 'employment',
            'criminal':   'criminal_procedure',
            'land':       'land',
            'family':     'children',
            'consumer':   'consumer',
            'data':       'other',
            'commercial': 'other',
        }
        cat = spec_to_cat.get(lawyer.specialties[0], 'other')
        entry = LSK_FEE_GUIDE.get(cat, LSK_FEE_GUIDE['other'])
        d = entry.get(lang, entry.get('sw', {}))
        fee_range = d.get('range', '')
        fee_note  = d.get('note', '')

    # Lead count for social proof (how many people contacted this lawyer)
    lead_count = Lead.objects.filter(lawyer=lawyer).count()

    # Average rating
    rated_leads = Lead.objects.filter(lawyer=lawyer, rating__isnull=False)
    avg_rating  = None
    if rated_leads.exists():
        total = sum(l.rating for l in rated_leads)
        avg_rating = round(total / rated_leads.count(), 1)

    return JsonResponse({
        'lawyer_name': lawyer.full_name,
        'fee_range':   fee_range,
        'fee_note':    fee_note,
        'lead_count':  lead_count,
        'avg_rating':  avg_rating,
        'rated_count': rated_leads.count(),
        'pro_bono':    lawyer.pro_bono,
    })
