"""
AI Engine — HakiMkononi

Uses requests directly (not the openai library) so we get proper
per-chunk timeouts.  Supports a model fallback chain: if NVIDIA returns
404/410/429/503 for a model, the next model is tried immediately instead
of hanging for 20 minutes.

Provider priority (configured in .env):
  1. NVIDIA NIM  — free, slow cold-start but good quality
  2. OpenAI      — paid, fast  (set AI_PROVIDER=openai)

NVIDIA model chain (tried in order — add new models at the top):
  nvidia/nemotron-3-nano-30b-a3b     28 tok/s, first token ~6s  — fastest
  nvidia/nemotron-3-super-120b-a12b  13 tok/s, first token ~8s  — fallback
  nvidia/llama-3.3-70b-instruct      good quality, widely available

Timeout strategy:
  connect_timeout = 30s  (bail if NVIDIA doesn't acknowledge the request)
  read_timeout    = 60s  (bail if no token arrives for 60s mid-stream)
  These match the working AdaKanisa app.
"""

import json
import logging
import os

import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AI_PROVIDER = os.getenv("AI_PROVIDER", "nvidia").lower()

# ─── NVIDIA model fallback chain ─────────────────────────────────────────────
# Tried in order. If a model returns a skip-code (404/410/429/503)
# the next model is tried immediately — no hang.
# AI_MODEL in .env overrides this list with a single model.
# Current live models verified September 2026 from docs.api.nvidia.com/nim/reference/llm-apis
_NVIDIA_MODEL_CHAIN = [
    "meta/llama-3.1-8b-instruct",           # fast, free, widely available — primary
    "meta/llama-3.3-70b-instruct",           # better quality — fallback
    "deepseek-ai/deepseek-v4-flash",         # fast DeepSeek — second fallback
    "nvidia/llama-3.1-nemotron-nano-8b-v1",  # NVIDIA's own small model — last resort
]

# HTTP codes that mean "skip this model, try the next one immediately"
_SKIP_CODES = {402, 404, 410, 413, 429, 503}

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

# Per-request timeouts: (connect_seconds, read_seconds)
_TIMEOUT = (30, 60)

# Groq model — fast, free tier available at console.groq.com
# Current Groq production models (verified September 2026 from console.groq.com/docs/models)
# openai/gpt-oss-20b  — 1000 tok/s, $0.075/1M tokens (fast, very cheap)
# openai/gpt-oss-120b — 500  tok/s, $0.15/1M tokens  (higher quality)
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def _get_nvidia_models() -> list:
    override = os.getenv("AI_MODEL", "").strip()
    if override:
        return [override]
    return list(_NVIDIA_MODEL_CHAIN)


def _nvidia_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY', '')}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _openai_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _groq_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


# ─── Language-aware system prompts ───────────────────────────────────────────
SYSTEM_PROMPTS = {
    "sw": """You are HakiMkononi, msaidizi wa kisheria wa Kenya.
Kazi yako: soma hali ya mtumiaji na vifungu vya sheria vilivyotolewa, kisha andika jibu lililoundwa.

SHERIA ZA KUFUATA (lazima):
- Tumia tu vifungu vya sheria vilivyotolewa hapa chini. Usibunie au kukumbuka.
- Jibu LOTE kwa KISWAHILI rahisi (kiwango cha darasa la 8).
- USIANDIKE mawazo yako. Toa jibu la mwisho tu.
- Kila sehemu LAZIMA iwe fupi na wazi — maneno mengi hayafai.
- Katika barua: USITUMIE ** (asterisks). Andika kwa maneno ya kawaida tu.

MUUNDO WA MATOKEO — tumia vichwa hivi VIU HASWA:

## SHERIA INASEMA
Kwa kila kifungu kinachohusika (max 6):
**[Jina la Sheria] – [Kifungu] ([Kichwa])**

Sema kwa sentensi 1-2 sheria inasema nini haswa kuhusu hali hii.

(acha mstari tupu kati ya kila kifungu)

## TAFSIRI RAHISI
Maelezo ya kawaida kwa sentensi 4-5. Hali hii inamaanisha nini kwa mtu huyu haswa. Eleza kwa lugha rahisi sana.

Hatua za kufanya SASA HIVI:
1. [hatua ya kwanza — ya vitendo, ya haraka]
2. [hatua ya pili]
3. [hatua ya tatu ikiwa inahitajika]

## HAKI YAKO NA LOOPHOLE
Haki zako:
- [haki 1]
- [haki 2]

Kosa lililofanywa:
- [nini kilipaswa kufanywa lakini hakufanywa]

## ANDIKA HIVI
(BARUA YA KUDAI HAKI)

[DATE]

[JINA LAKO]
[ANWANI]

Kwa:
[Jina la Mwajiri/Polisi/Landlord]
[Anwani yao]

Ndugu/Dada,

Mada: [Andika mada husika]

Mimi [JINA LAKO], ninaandika barua hii kudai haki zangu. [Eleza tatizo haswa kwa sentensi 2-3.]

Chini ya [Jina la Sheria, Kifungu], [eleza haki haswa].

Naitaka [ombi haswa] ndani ya [muda unaofaa — tumia "mara moja" kwa kesi za kukamatwa, "masaa 24" kwa kesi za dharura, "siku 14" kwa kesi za ajira/nyumba/walaji] tangu kupokea barua hii. Kama ombi hili halitafanyika, nitachukua hatua za kisheria ikiwemo kuwasiliana na [mahali husika].

Wako katika heshima,
[JINA LAKO]
[NAMBARI YA SIMU]

---
TAARIFA: Hii ni taarifa ya kisheria tu — si ushauri wa wakili. Thibitisha: kenyalaw.org

VIFUNGU VYA SHERIA (tumia hivi tu):
{context}""",

    "en": """You are HakiMkononi, a Kenyan legal information assistant.
Your job: read the user's situation and the law sections provided, then write a structured answer.

RULES (follow exactly):
- Only use the law sections given below. Never invent sections from memory.
- Respond ENTIRELY IN ENGLISH. Clear, simple language (secondary school level).
- Be specific to Kenya — cite actual section numbers, actual Kenyan acts.
- Keep each section SHORT and punchy. No waffle.
- In the letter: NO asterisks (**), NO markdown bold. Plain text only.

OUTPUT FORMAT — use these exact headers:

## WHAT THE LAW SAYS
For each relevant section (max 6):
**[Act Name] – Section [Number] ([Title])**

State in 1-2 sentences exactly what this section says about this situation.

(leave a blank line between each section)

## PLAIN EXPLANATION
4-5 sentences. What this means for this specific person, in plain English.

Steps to take RIGHT NOW:
1. [first action — concrete and immediate]
2. [second action]
3. [third action if needed]

## YOUR RIGHTS & WHAT WENT WRONG
Your rights:
- [right 1]
- [right 2]

What went wrong:
- [what the employer/police/landlord was required to do but didn't]

## WRITE THIS
(DEMAND LETTER)

[DATE]

[YOUR NAME]
[YOUR ADDRESS]

To:
[Name of Employer/Police Station/Landlord]
[Their Address]

Dear Sir/Madam,

Subject: [Write relevant subject line]

I, [YOUR NAME], write to formally demand compliance with my legal rights. [State the problem clearly in 2-3 sentences.]

Under [Act Name, Section Number], [state exactly what the law requires].

I demand that [specific demand] within [appropriate timeframe — use "immediately" for arrest/detention cases, "24 hours" for urgent safety cases, "14 days" for employment/landlord/consumer cases] of receiving this letter. Failure to comply will compel me to seek legal redress through the [Labour Court/Magistrate/High Court/relevant authority].

Yours faithfully,
[YOUR NAME]
[PHONE NUMBER]

---
NOTE: Legal information only — not legal advice. Verify at kenyalaw.org

LAW SECTIONS TO USE (only these):
{context}""",

    "sheng": """You are HakiMkononi, msaidizi wa kisheria wa Kenya.
Kazi yako: soma situation ya mtu na sheria zilizotolewa, kisha andika jibu kwa Kiswahili rahisi na wazi.
Mtu huyu anaandika kwa Sheng — jibu kwa Kiswahili safi, fupi, rahisi kuelewa.

RULES (lazima):
- Tumia tu sheria zilizotolewa hapa chini. Usibunie.
- Jibu kwa KISWAHILI RAHISI — safi, fupi, wazi. Kiwango cha darasa 8.
- Cite section numbers za actual Kenyan laws.
- Kila sehemu iwe fupi. Maneno mengi hayafai.
- Katika barua: USITUMIE ** (asterisks). Andika plain text tu.

MUUNDO — tumia vichwa hivi HASA:

## SHERIA INASEMA
Kwa kila sheria inayohusika (max 4):
[Jina la Sheria] – Kifungu [Nambari] ([Kichwa])
Sema kwa sentensi 1-2 sheria inasema nini haswa.

## TAFSIRI RAHISI
Sentensi 3-4. Hali yake inamaanisha nini kwa maneno ya kawaida.

## HAKI YAKO NA LOOPHOLE
Haki zako:
- [haki 1]
- [haki 2]

Kosa lililofanywa:
- [nini kilipaswa kufanywa lakini hakufanywa]

## ANDIKA HIVI
(BARUA YA KUDAI HAKI)

[DATE]

[JINA LAKO]
[ANWANI YAKO]

Kwa:
[Jina la Mwajiri/Polisi/Landlord]
[Anwani yao]

Ndugu/Dada,

Mada: [Andika mada husika]

Mimi [JINA LAKO], ninaandika barua hii kudai haki zangu. [Eleza tatizo haswa kwa sentensi 2-3.]

Chini ya [Jina la Sheria, Kifungu], [eleza haki haswa].

Naitaka [ombi haswa] ndani ya [muda unaofaa — "mara moja" kwa kukamatwa, "masaa 24" kwa dharura, "siku 14" kwa ajira/nyumba] tangu kupokea barua hii. Kama ombi hili halitafanyika, nitachukua hatua za kisheria.

Wako katika heshima,
[JINA LAKO]
[NAMBARI YA SIMU]

---
TAARIFA: Hii ni taarifa ya kisheria tu. Thibitisha: kenyalaw.org

VIFUNGU VYA SHERIA (tumia hivi tu):
{context}""",
}

_USER_MESSAGES = {
    "sw":    "Hali yangu: {story}\n\nNiambie haki zangu na niandikia barua ya kudai haki zangu.",
    "en":    "My situation: {story}\n\nTell me my rights and write me a demand letter.",
    "sheng": "Hali yangu: {story}\n\nNiambie haki zangu uniandike barua ya kudai rights zangu.",
}

# ─── Self-representation extra sections ──────────────────────────────────────
# Appended to the base system prompt when self_rep=True.
# These sections guide the model to add 3 practical self-rep boxes.
SELF_REP_EXTRA = {
    "en": """

ADDITIONAL SECTIONS — include these ONLY when the user wants to self-represent:

## COURT DOCUMENT
Write the appropriate court document for this case. Choose ONE from:
- Statement of Claim (Employment & Labour Court or Magistrate Court)
- Notice of Motion (for urgent injunctions)
- Memorandum of Appearance (if responding to a claim)

Format it as a real Kenyan court document — include:
- The correct court name and location (e.g. "Employment and Labour Relations Court at Nairobi")
- Case number placeholder: [CASE NO.]
- Plaintiff/Claimant: [YOUR NAME], ID: [YOUR ID]
- Defendant/Respondent: [Name of Other Party]
- Date filed: [DATE]
- The specific relief/orders sought — numbered, one per line
- A brief statement of facts (3-5 sentences)
- Signed: [YOUR NAME], [PHONE NUMBER]

NO asterisks (**). Plain text. Real Kenyan legal language.

## EVIDENCE CHECKLIST
List every document and piece of evidence Wanjiku needs to WIN this case. For each item:
- [Document name] — why it's important / what it proves

Organise in order of importance. Include:
- Documents she already has (payslips, contracts, messages, photos, etc.)
- Documents she must request or obtain (medical reports, bank statements, etc.)
- Witness considerations (who can testify and what they would say)

## PROCEDURE TIMELINE
Exact step-by-step guide for filing and arguing this case. Be specific to Kenya:

**Before Filing (Day 1–3):**
- [specific action — where to go, what to bring, what to say]

**Filing Day:**
- [where to go, which court, which registry, what forms, what fees]
- [what to expect at the counter]

**After Filing (Day 7–14):**
- [what happens next, service of process, hearing date]

**At the Hearing:**
- [how to present yourself, what to say, how to respond to the other side]
- Counter-argument: the other side will likely argue "[X]" — respond with "[Y based on the law]"

**If You Win / If You Lose:**
- [next steps in either scenario]""",

    "sw": """

SEHEMU ZA ZIADA — jumuisha hizi TU wakati mtumiaji anataka kujitetea mahakamani:

## HATI YA MAHAKAMA
Andika hati sahihi ya mahakama kwa kesi hii. Chagua MOJA kati ya:
- Madai ya Kudai (Mahakama ya Kazi au Mahakama ya Wilaya)
- Notisi ya Hukumu ya Haraka (kwa amri za dharura)
- Kumbukumbu ya Kuonekana (kama unajibu madai)

Fomati kama hati halisi ya mahakama ya Kenya — jumuisha:
- Jina sahihi la mahakama na mahali (mfano: "Mahakama ya Kazi na Mahusiano ya Wafanyakazi Nairobi")
- Nambari ya kesi: [NAMBARI YA KESI]
- Mdai: [JINA LAKO], Kitambulisho: [NAMBARI YA ID]
- Mshitakiwa: [Jina la Upande Mwingine]
- Tarehe ya kuwasilisha: [DATE]
- Msaada/Amri zinazoombwa — kila moja mstari wake
- Muhtasari mfupi wa ukweli (sentensi 3-5)
- Imesainiwa: [JINA LAKO], [NAMBARI YA SIMU]

USITUMIE ** (asterisks). Maneno ya kawaida. Lugha halisi ya mahakama ya Kenya.

## ORODHA YA USHAHIDI
Orodhesha kila hati na ushahidi ambao Wanjiku anahitaji ili KUSHINDA kesi hii. Kwa kila kitu:
- [Jina la hati] — kwa nini ni muhimu / inathibitisha nini

Panga kwa mpangilio wa umuhimu. Jumuisha:
- Hati anazokwisha nazo (vipande vya mshahara, mikataba, ujumbe, picha, n.k.)
- Hati anazohitaji kuomba au kupata (ripoti za daktari, maelezo ya benki, n.k.)
- Mashahidi (ni nani anaweza kushuhudia na wangesema nini)

## RATIBA YA HATUA
Mwongozo wa hatua kwa hatua wa kufungua na kupigana kesi hii. Kuwa mahususi kwa Kenya:

**Kabla ya Kufungua Kesi (Siku 1-3):**
- [hatua mahususi — kwenda wapi, kuleta nini, kusema nini]

**Siku ya Kufungua Kesi:**
- [kwenda wapi, mahakama gani, ofisi gani, fomu gani, ada ngapi]
- [unatarajia nini pale]

**Baada ya Kufungua Kesi (Siku 7-14):**
- [kinachofuata, kuwasilisha hati, tarehe ya kusikilizwa]

**Wakati wa Kusikilizwa:**
- [jinsi ya kujionyesha, kusema nini, kujibu upande mwingine vipi]
- Hoja ya upande mwingine: watadai "[X]" — jibu kwa "[Y kulingana na sheria]"

**Ukishinda / Ukipoteza:**
- [hatua za mwisho katika hali zote mbili]""",
}

_SELF_REP_USER_MESSAGES = {
    "sw": "Hali yangu: {story}\n\nNiambie haki zangu, niandikia barua ya kudai haki zangu, NA nionyeshe jinsi ya kujitetea mahakamani ikiwa hawataitikia.",
    "en": "My situation: {story}\n\nTell me my rights, write me a demand letter, AND show me how to represent myself in court if they don't comply.",
}

SERIOUS_CRIMINAL_KEYWORDS = [
    "murder", "mauaji", "rape", "ubakaji", "defilement", "udhalilishaji",
    "terrorism", "ugaidi", "robbery with violence", "wizi wa kutumia nguvu",
    "manslaughter", "kuua bila kukusudia",
]

_SERIOUS_MESSAGES = {
    "sw": (
        "⚠️ TAFUTA WAKILI HARAKA — Hii kesi ni nzito sana.\n\n"
        "Haki zako (Katiba, Ibara 49 & 50):\n"
        "- Una haki ya kukaa kimya\n"
        "- Una haki ya wakili bure\n"
        "- Lazima upelekwe mahakamani ndani ya masaa 24\n\n"
        "Msaada wa bure:\n"
        "📞 Kituo Cha Sheria: 0800 720 372\n"
        "📞 LSK Pro-Bono: lsk.or.ke"
    ),
    "en": (
        "⚠️ GET A LAWYER URGENTLY — This is a very serious case.\n\n"
        "Your rights (Constitution, Articles 49 & 50):\n"
        "- You have the right to remain silent\n"
        "- You have the right to a free lawyer\n"
        "- You must be taken to court within 24 hours\n\n"
        "Free legal help:\n"
        "📞 Kituo Cha Sheria: 0800 720 372\n"
        "📞 LSK Pro-Bono: lsk.or.ke"
    ),
    "sheng": (
        "⚠️ TAFUTA WAKILI HARAKA — Kesi hii ni serious sana, usiicheze.\n\n"
        "Haki zako (Katiba, Articles 49 & 50):\n"
        "- Una haki ya kukaa kimya — usiseme chochote\n"
        "- Una haki ya lawyer bure kabisa\n"
        "- Lazima wakupeleke kortini ndani ya masaa 24\n\n"
        "Free help iko hapa:\n"
        "📞 Kituo Cha Sheria: 0800 720 372\n"
        "📞 LSK Pro-Bono: lsk.or.ke"
    ),
}


def is_serious_criminal(story: str) -> bool:
    s = story.lower()
    return any(kw in s for kw in SERIOUS_CRIMINAL_KEYWORDS)


def format_law_context(laws) -> str:
    if not laws:
        return "Hakuna sheria iliyopatikana."
    return "\n".join(
        f"[{l.title} — {l.section}]\nText: {l.content[:800]}\nSource: {l.source_url}\n"
        for l in laws
    )


def parse_answer_sections(raw: str, lang: str = "sw") -> dict:
    """Split the model response into the 4 standard boxes + 3 optional self-rep boxes."""
    sections = {"law": "", "simple": "", "loophole": "", "letter": "",
                "court_doc": "", "evidence": "", "procedure": ""}
    marker_sets = [
        # Standard markdown headers (## prefix)
        ["## SHERIA INASEMA",      "## TAFSIRI RAHISI",              "## HAKI YAKO NA LOOPHOLE",          "## ANDIKA HIVI"],
        ["## WHAT THE LAW SAYS",   "## PLAIN EXPLANATION",           "## YOUR RIGHTS & WHAT WENT WRONG",  "## WRITE THIS"],
        ["## SHERIA INASEMA NINI", "## STORY Yake KWA MANENO RAHISI","## HAKI ZAKO NA WAPI WALIMESS",      "## ANDIKA HIVI (BARUA YA KUDAI)"],
        # Bold markdown (**text**) — AI sometimes uses this instead of ##
        ["**SHERIA INASEMA**",     "**TAFSIRI RAHISI**",             "**HAKI YAKO NA LOOPHOLE**",         "**ANDIKA HIVI**"],
        ["**WHAT THE LAW SAYS**",  "**PLAIN EXPLANATION**",          "**YOUR RIGHTS & WHAT WENT WRONG**", "**WRITE THIS**"],
        # Bold without asterisks — plain text headers AI occasionally uses
        ["SHERIA INASEMA\n",       "TAFSIRI RAHISI\n",               "HAKI YAKO NA LOOPHOLE\n",           "ANDIKA HIVI\n"],
        ["WHAT THE LAW SAYS\n",    "PLAIN EXPLANATION\n",            "YOUR RIGHTS & WHAT WENT WRONG\n",   "WRITE THIS\n"],
    ]
    order = ["law", "simple", "loophole", "letter"]
    # Use uppercase for case-insensitive matching
    raw_upper = raw.upper()
    for marker_set in marker_sets:
        markers_upper = [m.upper() for m in marker_set]
        if not any(m in raw_upper for m in markers_upper):
            continue
        for i, key in enumerate(order):
            start = raw_upper.find(markers_upper[i])
            if start == -1:
                continue
            start += len(markers_upper[i])
            end = raw_upper.find(markers_upper[i + 1]) if i + 1 < len(order) else len(raw)
            if end == -1:
                end = len(raw)
            sections[key] = raw[start:end].strip()
        break
    if not any(v for k, v in sections.items() if k in ("law", "simple", "loophole", "letter")):
        # Fallback: put the whole response in the law box so something shows
        sections["law"] = raw.strip()

    # ── Self-rep sections (optional — only present in self-rep mode) ──────────
    self_rep_marker_sets = [
        # English
        {"court_doc": "## COURT DOCUMENT",     "evidence": "## EVIDENCE CHECKLIST",  "procedure": "## PROCEDURE TIMELINE"},
        # Swahili
        {"court_doc": "## HATI YA MAHAKAMA",   "evidence": "## ORODHA YA USHAHIDI",  "procedure": "## RATIBA YA HATUA"},
    ]
    for sr_markers in self_rep_marker_sets:
        sr_upper = {k: v.upper() for k, v in sr_markers.items()}
        if not any(m in raw_upper for m in sr_upper.values()):
            continue
        sr_order = ["court_doc", "evidence", "procedure"]
        for i, key in enumerate(sr_order):
            start = raw_upper.find(sr_upper[key])
            if start == -1:
                continue
            start += len(sr_upper[key])
            # End at the next self-rep marker, or end of string
            next_markers = [sr_upper[sr_order[j]] for j in range(i+1, len(sr_order))]
            end = len(raw)
            for nm in next_markers:
                pos = raw_upper.find(nm, start)
                if pos != -1 and pos < end:
                    end = pos
            sections[key] = raw[start:end].strip()
        break

    return sections


# ─── Core HTTP caller (non-streaming) ────────────────────────────────────────

def _call_nvidia(messages: list, model: str) -> str:
    """
    Call NVIDIA NIM synchronously.
    Returns the content string.
    Raises requests.HTTPError on bad status, requests.Timeout on timeout.
    """
    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": 0.2,
        "max_tokens":  4000,   # enough for 4-section answer + full demand letter
        "stream":      False,
    }
    resp = http_requests.post(
        NVIDIA_URL,
        headers=_nvidia_headers(),
        json=payload,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_openai(messages: list) -> str:
    model = os.getenv("AI_MODEL", "gpt-4o-mini")
    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": 0.2,
        "max_tokens":  4000,   # enough for 4-section answer + full demand letter
    }
    resp = http_requests.post(
        OPENAI_URL,
        headers=_openai_headers(),
        json=payload,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_groq(messages: list) -> str:
    payload = {
        "model":       GROQ_MODEL,
        "messages":    messages,
        "temperature": 0.2,
        "max_tokens":  4000,   # enough for 4-section answer + full demand letter
    }
    resp = http_requests.post(
        GROQ_URL,
        headers=_groq_headers(),
        json=payload,
        timeout=(30, 90),  # connect 30s, read 90s — more context needs more time
    )
    resp.raise_for_status()
    result = resp.json()["choices"][0]["message"]["content"]
    if result is None:
        result = ""
    result = result.strip()
    if not result:
        logger.warning("[AI] Groq returned empty response — retrying once...")
        resp2 = http_requests.post(
            GROQ_URL, headers=_groq_headers(), json=payload, timeout=_TIMEOUT
        )
        resp2.raise_for_status()
        result = (resp2.json()["choices"][0]["message"]["content"] or "").strip()
    return result


def _call_with_fallback(messages: list, lang: str = "sw") -> str:
    """
    Try NVIDIA model chain first, then OpenAI.
    Skips a model immediately on _SKIP_CODES instead of waiting.
    Returns the raw content string.
    Raises RuntimeError with a user-facing message if everything fails.
    """
    timeout_msgs = {
        "sw":    "⏱️ Samahani — imechukua muda mrefu sana. Tafadhali jaribu tena.",
        "en":    "⏱️ Sorry — this took too long to respond. Please try again.",
        "sheng": "⏱️ Pole buda — ilichukua muda mrefu. Jaribu tena.",
    }
    error_msgs = {
        "sw":    "❌ Kuna tatizo la kiufundi. Tafadhali jaribu tena.",
        "en":    "❌ A technical error occurred. Please try again.",
        "sheng": "❌ Kuna technical issue. Jaribu tena.",
    }
    last_error = error_msgs.get(lang, error_msgs["sw"])

    # ── NVIDIA chain ──────────────────────────────────────────────────────
    nvidia_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if nvidia_key:
        for model in _get_nvidia_models():
            try:
                logger.info("[AI] Trying NVIDIA model: %s", model)
                content = _call_nvidia(messages, model)
                logger.info("[AI] Success: %s", model)
                return content
            except http_requests.exceptions.Timeout:
                logger.warning("[AI] %s timed out — trying next", model)
                last_error = timeout_msgs.get(lang, timeout_msgs["sw"])
                continue
            except http_requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                logger.warning("[AI] %s returned HTTP %d — trying next", model, code)
                if code in _SKIP_CODES:
                    continue   # try next model immediately
                if code == 401:
                    logger.error("[AI] NVIDIA 401 — API key invalid")
                    break      # no point trying other NVIDIA models
                last_error = error_msgs.get(lang, error_msgs["sw"])
                continue
            except Exception as exc:
                logger.error("[AI] %s unexpected error: %s", model, exc)
                continue

    # ── Groq fallback (free tier, fast) ─────────────────────────────────
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            logger.info("[AI] Trying Groq: %s", GROQ_MODEL)
            content = _call_groq(messages)
            logger.info("[AI] Groq success")
            return content
        except http_requests.exceptions.Timeout:
            last_error = timeout_msgs.get(lang, timeout_msgs["sw"])
        except http_requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            logger.warning("[AI] Groq HTTP %d", code)
        except Exception as exc:
            logger.error("[AI] Groq error: %s", exc)

    # ── OpenAI fallback ───────────────────────────────────────────────────
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key and not openai_key.startswith("your-"):
        try:
            logger.info("[AI] Trying OpenAI fallback")
            content = _call_openai(messages)
            logger.info("[AI] OpenAI success")
            return content
        except http_requests.exceptions.Timeout:
            last_error = timeout_msgs.get(lang, timeout_msgs["sw"])
        except Exception as exc:
            logger.error("[AI] OpenAI error: %s", exc)

    raise RuntimeError(last_error)


# ─── Core HTTP caller (streaming) ────────────────────────────────────────────

def _stream_nvidia(messages: list, model: str):
    """
    Generator — yields raw text chunks from NVIDIA streaming.
    Raises requests.HTTPError / requests.Timeout so the caller can skip models.
    Sends a keep-alive ': ping' comment every 15s of silence (keeps Nginx alive).
    """
    import time as _time
    HEARTBEAT = 15

    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": 0.2,
        "max_tokens":  4000,   # enough for 4-section answer + full demand letter
        "stream":      True,
    }
    headers = {**_nvidia_headers(), "Accept": "text/event-stream"}

    with http_requests.post(
        NVIDIA_URL,
        headers=headers,
        json=payload,
        stream=True,
        timeout=_TIMEOUT,
    ) as resp:
        if resp.status_code in _SKIP_CODES:
            resp.raise_for_status()       # triggers HTTPError with the status code
        resp.raise_for_status()

        last_ping = _time.monotonic()
        for raw_line in resp.iter_lines():
            # Keep-alive ping during pauses between tokens
            now = _time.monotonic()
            if now - last_ping >= HEARTBEAT:
                yield ": ping\n\n"
                last_ping = now

            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                raw_line = raw_line.decode("utf-8")
            if not raw_line.startswith("data: "):
                continue
            chunk = raw_line[6:]
            if chunk.strip() == "[DONE]":
                return
            try:
                delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                if delta:
                    last_ping = _time.monotonic()
                    yield delta
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


def stream_answer(user_story: str, laws: list, lang: str = "sw"):
    """
    Public generator — yields raw AI text chunks.
    On error yields:  __ERROR__<message>
    Used by stream_answer_view (kept for compatibility) but not the main path
    any more — the background-thread polling approach is the primary path.
    """
    lang = lang if lang in SYSTEM_PROMPTS else "sw"
    # Sheng is understood as input but we reply in Kiswahili
    if lang == "sheng":
        lang = "sw"

    if is_serious_criminal(user_story):
        yield _SERIOUS_MESSAGES[lang]
        return

    context  = format_law_context(laws)
    system   = SYSTEM_PROMPTS[lang].format(context=context)
    user_msg = _USER_MESSAGES[lang].format(story=user_story)
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_msg},
    ]

    timeout_msgs = {
        "sw":    "⏱️ Samahani — imechukua muda mrefu sana. Tafadhali jaribu tena.",
        "en":    "⏱️ Sorry — this took too long. Please try again.",
        "sheng": "⏱️ Pole buda — ilichukua muda mrefu. Jaribu tena.",
    }
    error_msgs = {
        "sw":    "❌ Kuna tatizo la kiufundi. Tafadhali jaribu tena.",
        "en":    "❌ A technical error occurred. Please try again.",
        "sheng": "❌ Kuna technical issue. Jaribu tena.",
    }

    nvidia_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if nvidia_key:
        for model in _get_nvidia_models():
            try:
                logger.info("[AI stream] Trying NVIDIA model: %s", model)
                for chunk in _stream_nvidia(messages, model):
                    yield chunk
                logger.info("[AI stream] Done: %s", model)
                return
            except http_requests.exceptions.Timeout:
                logger.warning("[AI stream] %s timed out — trying next", model)
                continue
            except http_requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                logger.warning("[AI stream] %s HTTP %d — trying next", model, code)
                if code == 401:
                    break
                continue
            except Exception as exc:
                logger.error("[AI stream] %s error: %s", model, exc)
                continue

    yield "__ERROR__" + error_msgs.get(lang, error_msgs["sw"])


# ─── Public synchronous entry point ──────────────────────────────────────────

def get_answer(user_story: str, laws: list, lang: str = "sw",
               history: list = None, self_rep: bool = False) -> dict:
    """
    Main entry point for the background job thread.
    Returns a dict with the 4-box answer (+ 3 self-rep boxes when self_rep=True).

    history  — optional list of prior {role, content} turns from the web chat.
    self_rep — when True, extends the prompt with court document, evidence
               checklist, and procedure timeline sections.
    """
    lang = lang if lang in SYSTEM_PROMPTS else "sw"
    # Sheng is understood as input but we reply in Kiswahili
    if lang == "sheng":
        lang = "sw"

    if is_serious_criminal(user_story):
        msg = _SERIOUS_MESSAGES[lang]
        return {"law": msg, "simple": "", "loophole": "", "letter": "",
                "court_doc": "", "evidence": "", "procedure": "",
                "raw": msg, "is_serious": True}

    context = format_law_context(laws)

    # Build system prompt — extend with self-rep sections when requested
    base_system = SYSTEM_PROMPTS[lang].format(context=context)
    if self_rep:
        sr_extra = SELF_REP_EXTRA.get(lang, SELF_REP_EXTRA["en"])
        system = base_system.replace(
            "LAW SECTIONS TO USE (only these):\n{context}".format(context=context),
            sr_extra + "\n\nLAW SECTIONS TO USE (only these):\n" + context
        ).replace(
            "VIFUNGU VYA SHERIA (tumia hivi tu):\n{context}".format(context=context),
            sr_extra + "\n\nVIFUNGU VYA SHERIA (tumia hivi tu):\n" + context
        )
        # Fallback: if the replace didn't match (prompt wording varies), just append
        if system == base_system:
            system = base_system.rstrip() + "\n\n" + sr_extra.strip() + "\n"
    else:
        system = base_system

    # Use richer user message for self-rep mode
    if self_rep:
        user_msg = _SELF_REP_USER_MESSAGES.get(lang, _SELF_REP_USER_MESSAGES["en"]).format(story=user_story)
    else:
        user_msg = _USER_MESSAGES[lang].format(story=user_story)

    # Build multi-turn message array — same logic as the Telegram bot
    messages = [{"role": "system", "content": system}]
    if history:
        # Trim to last 4 turns (8 messages) to keep prompt size sane
        trimmed = history[-(8):]
        messages.extend(trimmed)
    messages.append({"role": "user", "content": user_msg})

    try:
        raw = _call_with_fallback(messages, lang=lang)
    except RuntimeError as exc:
        # Return the user-facing error in the law box so it shows on screen
        return {"law": str(exc), "simple": "", "loophole": "", "letter": "",
                "court_doc": "", "evidence": "", "procedure": "",
                "raw": str(exc), "is_serious": False, "api_error": True}

    sections = parse_answer_sections(raw, lang=lang)
    sections["raw"]        = raw
    sections["is_serious"] = False
    return sections
