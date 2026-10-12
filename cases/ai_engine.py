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

SHERIA ZA KUFUATA:
- Tumia tu vifungu vya sheria vilivyotolewa. Usibunie.
- Jibu LOTE kwa KISWAHILI rahisi (darasa la 8).
- Kila sehemu iwe fupi na wazi.
- Katika barua: USITUMIE ** (asterisks). Maneno ya kawaida tu.

MUUNDO — tumia vichwa hivi:

## SHERIA INASEMA
Kwa kila kifungu (max 5): **[Jina] – [Kifungu] ([Kichwa])** — sentensi 1-2 inayoelezea hali hii.

## TAFSIRI RAHISI
Sentensi 4-5 kwa lugha rahisi. Hatua za kufanya SASA:
1. [hatua ya kwanza]
2. [hatua ya pili]
3. [ya tatu ikiwa inahitajika]

## HAKI YAKO NA LOOPHOLE
- Haki: [haki 1], [haki 2]
- Kosa: [nini kilipaswa kufanywa]

## ANDIKA HIVI
Barua fupi ya kudai haki. Jumuisha: tarehe, jina, mada, tatizo, haki husika, ombi mahususi na muda (siku 14 au haraka zaidi), onyo la hatua za kisheria, saini. Maneno ya kawaida, si formal sana.

---
VIFUNGU VYA SHERIA:
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

# ─── LSK Fee Guide (Remuneration Order 2014 + 2023 gazette) ──────────────────
# Approximate ranges for common case types so Wanjiku knows if she's
# being overcharged. These are GUIDANCE, not fixed prices.
# Source: LSK Advocates Remuneration Order 2014 + common market rates.
LSK_FEE_GUIDE = {
    "employment": {
        "en": {
            "range": "KES 20,000 – 150,000",
            "note": "Unfair dismissal / unpaid wages at Employment & Labour Court. "
                    "Many advocates take 20–30% of the award (no win, no fee). "
                    "Consultation fee: KES 2,000–5,000.",
        },
        "sw": {
            "range": "KES 20,000 – 150,000",
            "note": "Kesi ya kufukuzwa kazi / mshahara ambao haujalipiwa katika Mahakama ya Kazi. "
                    "Mawakili wengi wanachukua 20–30% ya malipo (hakuna ushindi, hakuna ada). "
                    "Ada ya ushauri: KES 2,000–5,000.",
        },
    },
    "landlord_tenant": {
        "en": {
            "range": "KES 10,000 – 80,000",
            "note": "Eviction disputes or deposit recovery at the Rent Tribunal or Magistrate Court. "
                    "Simple cases can be filed yourself (no lawyer needed). "
                    "Consultation fee: KES 1,500–3,000.",
        },
        "sw": {
            "range": "KES 10,000 – 80,000",
            "note": "Migogoro ya kukimbia nyumba au kurejesha amana kwenye Baraza la Kodi au Mahakama ya Wilaya. "
                    "Kesi rahisi zinaweza kufunguliwa wewe mwenyewe (hakuna haja ya wakili). "
                    "Ada ya ushauri: KES 1,500–3,000.",
        },
    },
    "criminal_procedure": {
        "en": {
            "range": "KES 30,000 – 300,000",
            "note": "Criminal defence depends heavily on the charge. Bail hearings: KES 5,000–30,000. "
                    "Full trial: KES 50,000–300,000+. Legal Aid (free) available via NLAS: 0800 720 120.",
        },
        "sw": {
            "range": "KES 30,000 – 300,000",
            "note": "Utetezi wa jinai unategemea sana shtaka. Kusikilizana kwa dhamana: KES 5,000–30,000. "
                    "Kesi kamili: KES 50,000–300,000+. Msaada wa kisheria (bure) unapatikana kupitia NLAS: 0800 720 120.",
        },
    },
    "land": {
        "en": {
            "range": "KES 25,000 – 250,000",
            "note": "Land disputes at the Environment & Land Court. "
                    "Succession matters at the High Court: KES 15,000–80,000. "
                    "Title deed transfers: KES 10,000–50,000.",
        },
        "sw": {
            "range": "KES 25,000 – 250,000",
            "note": "Migogoro ya ardhi katika Mahakama ya Mazingira na Ardhi. "
                    "Masuala ya urithi katika Mahakama Kuu: KES 15,000–80,000. "
                    "Uhamishaji wa hati ya ardhi: KES 10,000–50,000.",
        },
    },
    "children": {
        "en": {
            "range": "KES 8,000 – 60,000",
            "note": "Child support / custody at the Children's Court. "
                    "Maintenance orders are often handled without a lawyer. "
                    "FIDA Kenya offers free legal aid for women: 020 271 4911.",
        },
        "sw": {
            "range": "KES 8,000 – 60,000",
            "note": "Msaada wa mtoto / ulezi katika Mahakama ya Watoto. "
                    "Amri za matunzo mara nyingi hushughulikiwa bila wakili. "
                    "FIDA Kenya inatoa msaada wa kisheria bure kwa wanawake: 020 271 4911.",
        },
    },
    "consumer": {
        "en": {
            "range": "KES 5,000 – 40,000",
            "note": "Consumer disputes at the Consumer Protection Tribunal or Magistrate Court. "
                    "Small claims (under KES 200,000) can be filed at the Small Claims Court with no lawyer needed.",
        },
        "sw": {
            "range": "KES 5,000 – 40,000",
            "note": "Migogoro ya walaji kwenye Baraza la Ulinzi wa Walaji au Mahakama ya Wilaya. "
                    "Madai madogo (chini ya KES 200,000) yanaweza kufunguliwa kwenye Mahakama ya Madai Madogo bila haja ya wakili.",
        },
    },
    "constitution": {
        "en": {
            "range": "KES 30,000 – 200,000",
            "note": "Constitutional petitions at the High Court. "
                    "Many human rights NGOs (KHRC, ICJ Kenya, Kituo cha Sheria) take constitutional cases pro bono.",
        },
        "sw": {
            "range": "KES 30,000 – 200,000",
            "note": "Malalamiko ya kikatiba katika Mahakama Kuu. "
                    "Mashirika mengi ya haki za binadamu (KHRC, ICJ Kenya, Kituo cha Sheria) yanachukua kesi za kikatiba bila malipo.",
        },
    },
    "fraud": {
        "en": {
            "range": "KES 15,000 – 100,000",
            "note": "Online fraud, M-Pesa fraud, hacking or cybercrime offences — report to DCI Cybercrime Unit: "
                    "📞 0800 722 203 (toll-free) or visit dci.go.ke. "
                    "Civil recovery through Magistrate Court. "
                    "Hire Purchase disputes at the Magistrate Court: KES 5,000–30,000.",
        },
        "sw": {
            "range": "KES 15,000 – 100,000",
            "note": "Ulaghai wa mtandaoni, ulaghai wa M-Pesa, udukuzi — ripoti kwa DCI Cybercrime Unit: "
                    "📞 0800 722 203 (simu ya bure) au tembelea dci.go.ke. "
                    "Kudai fidia kupitia Mahakama ya Wilaya. "
                    "Migogoro ya Hire Purchase katika Mahakama ya Wilaya: KES 5,000–30,000.",
        },
    },
    "family": {
        "en": {
            "range": "KES 10,000 – 80,000",
            "note": "Divorce, matrimonial property and domestic violence matters at the High Court / Family Division. "
                    "FIDA Kenya offers free legal aid for women: 020 271 4911. "
                    "Domestic violence protection orders can be obtained at a Magistrate Court same-day, no lawyer needed.",
        },
        "sw": {
            "range": "KES 10,000 – 80,000",
            "note": "Talaka, mali ya ndoa na ukatili wa nyumbani katika Mahakama Kuu / Kitengo cha Familia. "
                    "FIDA Kenya inatoa msaada wa kisheria bure kwa wanawake: 020 271 4911. "
                    "Amri ya ulinzi dhidi ya ukatili inaweza kupatikana siku hiyo hiyo katika Mahakama ya Wilaya, bila haja ya wakili.",
        },
    },
    "county": {
        "en": {
            "range": "KES 0 – 30,000",
            "note": "County enforcement disputes (kanjo, business permits, hawker confiscations). "
                    "File an appeal at the County Government offices or the County Appeal Tribunal within 30 days. "
                    "Small claims under KES 200,000 can go to the Small Claims Court — no lawyer needed. "
                    "Contact the County Ombudsman or Kenya Citizens & Foreign Nationals Management Service for complaints.",
        },
        "sw": {
            "range": "KES 0 – 30,000",
            "note": "Migogoro ya askari wa kaunti (kanjo, leseni za biashara, kukamata mali ya wafanyabiashara). "
                    "Kata rufaa ofisini kwa Serikali ya Kaunti au Baraza la Rufaa la Kaunti ndani ya siku 30. "
                    "Madai madogo chini ya KES 200,000 yanaweza kwenda Mahakama ya Madai Madogo — bila haja ya wakili. "
                    "Wasiliana na Mkurugenzi wa Malalamiko wa Kaunti kwa malalamiko.",
        },
    },
    "banking": {
        "en": {
            "range": "KES 5,000 – 80,000",
            "note": "Banking disputes — file complaint with Central Bank of Kenya (CBK): 📞 020 286 0000 or cbuonline@centralbank.go.ke. "
                    "CRB disputes — write to the bank first, then escalate to CBK or Kenya Credit Reference Bureau. "
                    "Mobile money disputes — report to Safaricom/Airtel, then Communications Authority: 📞 020 429 0000. "
                    "Court action in Magistrate Court for amounts under KES 20M.",
        },
        "sw": {
            "range": "KES 5,000 – 80,000",
            "note": "Migogoro ya benki — wasiliana na Benki Kuu ya Kenya (CBK): 📞 020 286 0000. "
                    "Migogoro ya CRB — andika benki kwanza, kisha CBK. "
                    "Migogoro ya pesa za simu — ripoti Safaricom/Airtel, kisha Mamlaka ya Mawasiliano: 📞 020 429 0000.",
        },
    },
    "insurance": {
        "en": {
            "range": "KES 10,000 – 100,000",
            "note": "Insurance disputes — file complaint with Insurance Regulatory Authority (IRA): 📞 020 496 5000 or info@ira.go.ke. "
                    "IRA mediation is free. Court action through Magistrate Court or IRA Tribunal. "
                    "NHIF disputes — visit any NHIF office or call 📞 0800 720 601 (toll-free).",
        },
        "sw": {
            "range": "KES 10,000 – 100,000",
            "note": "Migogoro ya bima — wasiliana na Mamlaka ya Udhibiti wa Bima (IRA): 📞 020 496 5000. "
                    "Upatanisho wa IRA ni bila malipo. "
                    "Migogoro ya NHIF — tembelea ofisi yoyote ya NHIF au piga 📞 0800 720 601 (bure).",
        },
    },
    "copyright": {
        "en": {
            "range": "KES 10,000 – 150,000",
            "note": "Copyright disputes — Kenya Copyright Board (KECOBO): 📞 020 238 6091 or info@copyright.go.ke. "
                    "Trademark disputes — Kenya Industrial Property Institute (KIPI): 📞 020 604 2000. "
                    "Court action through High Court (Intellectual Property division). "
                    "KECOBO complaints are free. Litigation: KES 30,000–150,000.",
        },
        "sw": {
            "range": "KES 10,000 – 150,000",
            "note": "Migogoro ya haki miliki — Kenya Copyright Board (KECOBO): 📞 020 238 6091. "
                    "Migogoro ya alama za biashara — KIPI: 📞 020 604 2000. "
                    "Malalamiko ya KECOBO ni bila malipo.",
        },
    },
    "environment": {
        "en": {
            "range": "KES 5,000 – 60,000",
            "note": "Environmental complaints — National Environment Management Authority (NEMA): 📞 020 603 6000 or info@nema.go.ke. "
                    "NEMA complaints are free. Court action through Environment & Land Court. "
                    "For urgent pollution — also contact county environment office.",
        },
        "sw": {
            "range": "KES 5,000 – 60,000",
            "note": "Malalamiko ya mazingira — Mamlaka ya Usimamizi wa Mazingira (NEMA): 📞 020 603 6000. "
                    "Malalamiko ya NEMA ni bila malipo. "
                    "Mahakama ya Mazingira na Ardhi kwa kesi ngumu.",
        },
    },
    "procurement": {
        "en": {
            "range": "KES 10,000 – 200,000",
            "note": "Procurement disputes — Public Procurement Regulatory Authority (PPRA): 📞 020 312 7100. "
                    "Review Board complaints are free and must be filed within 14 days of the decision. "
                    "For unpaid government contracts — also file with the relevant Ministry Accounting Officer. "
                    "Court action through High Court (Commercial Division).",
        },
        "sw": {
            "range": "KES 10,000 – 200,000",
            "note": "Migogoro ya zabuni — Mamlaka ya Udhibiti wa Manunuzi ya Umma (PPRA): 📞 020 312 7100. "
                    "Malalamiko ya Bodi ya Mapitio ni bila malipo — lazima yafunguliwe ndani ya siku 14. "
                    "Kwa malipo yanayodaiwa na serikali — pia wasiliana na Afisa Uhasibu wa Wizara husika.",
        },
    },
    "health": {
        "en": {
            "range": "KES 5,000 – 80,000",
            "note": "Health rights complaints — Kenya Health Professionals Oversight Authority or county health department. "
                    "Emergency treatment refusal — Constitution Article 43 guarantees right to emergency care. "
                    "Medical negligence — sue in High Court; initial consultation KES 5,000–10,000. "
                    "NHIF disputes: 📞 0800 720 601 (toll-free).",
        },
        "sw": {
            "range": "KES 5,000 – 80,000",
            "note": "Malalamiko ya haki za afya — Mamlaka ya Usimamizi wa Wataalamu wa Afya au idara ya afya ya kaunti. "
                    "Kukataliwa matibabu ya dharura — Katiba Ibara 43 inahakikisha haki hiyo. "
                    "Uzembe wa daktari — Mahakama Kuu; ushauri wa kwanza KES 5,000–10,000.",
        },
    },
    "data": {
        "en": {
            "range": "KES 5,000 – 60,000",
            "note": "Data protection complaints — file with the Office of the Data Protection Commissioner (ODPC): 📞 0800 723 253 or odpc.go.ke. "
                    "CRB disputes — file with Central Bank of Kenya or the specific bank. "
                    "Court action under Data Protection Act 2019: KES 5,000–60,000 for an advocate. "
                    "Free options: ODPC complaints are free. Kenya Human Rights Commission also takes cases.",
        },
        "sw": {
            "range": "KES 5,000 – 60,000",
            "note": "Malalamiko ya ulinzi wa data — wasiliana na Ofisi ya Msimamizi wa Ulinzi wa Data (ODPC): 📞 0800 723 253 au odpc.go.ke. "
                    "Migogoro ya CRB — wasiliana na Benki Kuu ya Kenya au benki husika. "
                    "Malalamiko ya ODPC ni bila malipo. "
                    "Wakili kwa kesi mahakamani: KES 5,000–60,000.",
        },
    },
    "other": {
        "en": {
            "range": "KES 5,000 – 50,000",
            "note": "Rates vary by case complexity. Initial consultation: KES 1,000–5,000. "
                    "Always ask for a written fee agreement before retaining any lawyer. "
                    "Free legal aid: NLAS 0800 720 120 (toll-free).",
        },
        "sw": {
            "range": "KES 5,000 – 50,000",
            "note": "Ada zinatofautiana kulingana na ugumu wa kesi. Ushauri wa kwanza: KES 1,000–5,000. "
                    "Daima omba makubaliano ya ada kwa maandishi kabla ya kumtunza wakili wowote. "
                    "Msaada wa kisheria bure: NLAS 0800 720 120 (simu ya bure).",
        },
    },
}

def get_fee_guide(categories: list, lang: str = "sw") -> dict | None:
    """
    Given a list of Law.category values from the RAG results, return the most
    relevant fee guide entry so Wanjiku can check if a lawyer is overcharging.
    Returns None if no match found.
    """
    # Priority order — pick the most specific match
    priority = ["criminal_procedure", "fraud", "data", "employment", "landlord_tenant", "land",
                "children", "family", "consumer", "county", "banking", "insurance",
                "copyright", "environment", "procurement", "health", "constitution", "other"]
    cats = set(categories)
    for cat in priority:
        if cat in cats:
            guide = LSK_FEE_GUIDE.get(cat, {})
            lang_key = lang if lang in guide else "sw"
            return {
                "category": cat,
                "range":    guide.get(lang_key, {}).get("range", ""),
                "note":     guide.get(lang_key, {}).get("note", ""),
            }
    # fallback to 'other'
    guide = LSK_FEE_GUIDE["other"]
    lang_key = lang if lang in guide else "sw"
    return {
        "category": "other",
        "range":    guide[lang_key]["range"],
        "note":     guide[lang_key]["note"],
    }


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
        f"[{l.title} — {l.section}]\nText: {l.content[:500]}\nSource: {l.source_url}\n"
        for l in laws
    )


# ─── Intent classification ────────────────────────────────────────────────────
# Two-stage: fast keyword scan first, AI classifier for uncertain cases.
# Used by both the web chat (/api/converse/ + /api/submit/) and the Telegram bot.

# Stage 1 keywords — expanded to catch edge cases keywords usually miss
_INTENT_KW_EN = {
    # Employment
    'fired', 'dismissed', 'terminated', 'redundant', 'laid off', 'salary',
    'wages', 'pay', 'unpaid', 'employer', 'employee', 'boss', 'work', 'job',
    'overtime', 'nssf', 'nhif', 'payslip', 'labour', 'unfair', 'discriminat',
    'harass', 'workplace', 'resign', 'resigned', 'notice', 'contract',
    # Land / tenancy
    'landlord', 'tenant', 'rent', 'evict', 'evicted', 'house', 'land',
    'title deed', 'property', 'lease', 'deposit', 'locked out', 'caretaker',
    'estate', 'inherit', 'succession', 'shamba', 'plot', 'acre',
    # Succession / wills (deeper keywords)
    'will', 'probate', 'letters of administration', 'intestate', 'deceased',
    'next of kin', 'beneficiary', 'executor', 'administrator',
    'died without a will', 'challenge a will', 'disinherited',
    'surviving spouse', 'estate of', 'administer the estate',
    # Police / criminal
    'arrested', 'arrest', 'police', 'detain', 'bail', 'charged', 'charge',
    'court', 'magistrate', 'judge', 'prison', 'jail', 'warrant', 'stolen',
    'theft', 'rob', 'assault', 'beat', 'beaten', 'threaten', 'bribe',
    # Family
    'divorce', 'separat', 'child support', 'maintenance', 'custody',
    'children', 'wife', 'husband', 'marriage', 'dowry', 'domestic',
    # Consumer / debt
    'scam', 'fraud', 'conned', 'cheat', 'debt', 'loan', 'tala', 'mshwari',
    'crb', 'blacklist', 'refund', 'breach', 'goods', 'defect',
    # Cybercrime / fraud
    'hacked', 'hack', 'mpesa fraud', 'online fraud', 'cyber', 'phishing',
    'identity theft', 'stolen phone', 'sim swap', 'account hacked',
    'blackmail', 'extort', 'sextortion', 'online scam', 'defraud',
    'unauthorised access', 'unauthorized access', 'accessed my computer',
    'accessed my account', 'wire transfer', 'internet fraud', 'cyber fraud',
    'someone logged into', 'password stolen', 'phone cloned', 'computer misuse',
    'facebook hacked', 'instagram hacked', 'social media', 'fake profile',
    'impersonating me', 'account takeover', 'till number fraud', 'paybill fraud',
    'posed as a seller', 'fake seller', 'paid and received nothing',
    'never delivered', 'sent money never', 'paid online',
    # Data protection / privacy
    'personal data', 'privacy', 'data breach', 'cctv', 'consent',
    'data protection', 'my data', 'surveillance', 'leaked my data',
    'crb', 'credit reference', 'blacklisted credit', 'credit bureau',
    'shared my data', 'sharing my data', 'hidden camera', 'spy camera',
    'recorded without', 'filmed without', 'tracked my location',
    # Elections
    'election', 'voter', 'bribery', 'vote buying', 'ballot', 'candidate',
    'campaign', 'electoral', 'iebc', 'polling station', 'constituency',
    # Traffic / road
    'traffic', 'driving licence', 'ntsa', 'impound', 'road accident',
    'drunk driving', 'road carnage', 'motor vehicle', 'driving without',
    # Work injury / OSHA / hire purchase
    'work injury', 'wiba', 'occupational safety', 'osha', 'workplace injury',
    'hire purchase', 'hire-purchase',
    # County enforcement / kanjo
    'kanjo', 'county enforcement', 'county officer', 'county askari',
    'business permit', 'trade license', 'hawker', 'street vendor', 'confiscated',
    # Banking & mobile money
    'bank account', 'bank froze', 'frozen account', 'bank refused',
    'loan interest', 'mobile money agent', 'mpesa agent', 'reverse transaction',
    'account frozen', 'bank error', 'banking', 'overdraft', 'bank charges',
    # Insurance
    'insurance claim', 'insurer refused', 'insurance policy', 'claim denied',
    'accident claim', 'medical insurance', 'insurance company', 'premium',
    'third party', 'car insurance', 'nhif claim',
    # Copyright / intellectual property
    'copyright', 'intellectual property', 'trademark', 'trade mark',
    'brand name', 'logo', 'music rights', 'piracy', 'plagiarism', 'patent',
    'my song', 'my design', 'my artwork', 'copied my work',
    # Disability rights
    'disability', 'disabled', 'wheelchair', 'persons with disability',
    'discrimination disability', 'special needs', 'accessibility',
    # Environment / pollution
    'pollution', 'environmental', 'factory waste', 'contaminated water',
    'noise pollution', 'air pollution', 'nema', 'emca', 'dumping waste',
    # Public procurement
    'tender', 'procurement', 'government contract', 'bid rigging',
    'contractor unpaid', 'government unpaid', 'ppra', 'tendering',
    # Health rights
    'hospital refused', 'denied treatment', 'emergency treatment',
    'medical negligence', 'health rights', 'maternal health',
    # Legal process
    'sue', 'lawsuit', 'claim', 'demand letter', 'compensat', 'rights',
    'illegal', 'violat', 'constitution', 'human rights', 'tribunal',
    'appeal', 'affidavit', 'evidence', 'witness', 'lawyer', 'advocate',
    'legal', 'case', 'hearing', 'file a', 'my rights',
    # Common complaint patterns
    'they did not pay', 'did not pay me', 'has not paid', 'refused to pay',
    'locked me', 'kicked me out', 'threw out', 'not paid', 'owes me',
    'owe me', 'threatening me', 'threatened', 'abuse', 'forced me',
}
_INTENT_KW_SW = {
    # Employment
    'kufukuzwa', 'kufukuzwa kazi', 'mwajiri', 'mfanyakazi', 'mshahara',
    'kulipwa', 'hakulipwa', 'hajalipa', 'hajalipwa', 'malipo', 'kazi',
    'likizo', 'unyanyasaji', 'ubaguzi', 'notisi', 'mkataba',
    # Tenancy / land
    'landlord', 'mpangaji', 'kodi', 'kukimbiwa', 'kufukuzwa nyumba',
    'nyumba', 'amana', 'ardhi', 'shamba', 'hati', 'urithi', 'mali',
    # Police / criminal
    'polisi', 'kukamatwa', 'kukamatwa bila', 'dhamana', 'mahakama',
    'jaji', 'wizi', 'kuibiwa', 'kupigwa', 'taarifa', 'shtaka', 'jela',
    'korti', 'riswa', 'rushwa',
    # Family
    'talaka', 'matunzo', 'ulezi', 'watoto', 'mtoto', 'mke', 'mume',
    'ndoa', 'mahari', 'unyanyasaji wa nyumbani',
    # Consumer / debt
    'kudanganywa', 'kuibiwa', 'ulaghai', 'deni', 'mkopo', 'kurudisha',
    'bidhaa', 'kasoro', 'kulazimishwa',
    # Cybercrime / fraud (sw)
    'kudanganywa mtandaoni', 'ulaghai wa mpesa', 'akaunti yangu', 'simu iliibwa',
    'sim kubadilishwa', 'udukuzi', 'mtandaoni', 'waliiba pesa zangu',
    'blackmail', 'kunidhuru', 'picha zangu', 'vitisho vya mtandao',
    'sim swap', 'pesa zilienda', 'waliingia akaunti', 'simu yangu ilidukuliwa',
    'facebook yangu', 'instagram yangu', 'whatsapp iliibwa', 'akaunti ya mtandaoni',
    'wanajifanya mimi', 'wanatumia picha zangu', 'till number bandia',
    # Data protection / privacy (sw)
    'data yangu', 'wanashare data', 'bila ruhusa yangu', 'taarifa zangu',
    'walichukua picha', 'kampuni imeshare', 'faragha yangu', 'cctv yangu',
    'crb', 'orodha mbaya ya benki', 'wameniweka crb', 'mkopo ulikataliwa',
    'camera iliyofichwa', 'wananikuatilia',
    # Elections (sw)
    'uchaguzi', 'kura', 'mgombea', 'rushwa ya uchaguzi', 'kununua kura',
    'karatasi ya kura', 'iebc', 'jimbo', 'msimamizi wa uchaguzi', 'chaguzi',
    # County enforcement / kanjo (sw)
    'kanjo', 'county askari', 'kaounti', 'kibanda changu',
    'wamechukua mali', 'wamefunga duka', 'leseni ya biashara',
    'ruhusa ya biashara', 'hawkers', 'wafanyabiashara',
    # Traffic / WIBA / hire purchase (sw)
    'hire purchase', 'nilijeruhiwa kazini', 'mwajiri hana bima',
    'ajali ya kazi', 'gari lilichukuliwa', 'leseni ya udereva',
    # Succession / wills (sw)
    'wosia', 'mirathi', 'marehemu', 'msimamizi wa mali', 'probate',
    'barua ya usimamizi', 'kupinga wosia', 'mrithi', 'tangazo la wosia',
    # Banking & mobile money (sw)
    'benki imefunga akaunti', 'akaunti imezuiwa', 'benki ilikataa',
    'wakala wa mpesa', 'wakala akadanganya', 'mkopo wa benki', 'benki haijalipi',
    # Insurance (sw)
    'bima ilikataa', 'madai ya bima', 'kampuni ya bima', 'bima ya gari',
    'bima ya afya', 'nhif ilikataa', 'fidia ya ajali',
    # Copyright / IP (sw)
    'haki ya kunakili', 'nyimbo zangu', 'kazi yangu imeibiwa', 'nembo yangu',
    'jina la biashara langu', 'wanapiga nakala', 'uvumbuzi wangu',
    # Disability (sw)
    'ulemavu', 'mlemavu', 'kiti cha magurudumu', 'unyanyasaji wa ulemavu',
    # Environment (sw)
    'uchafuzi wa mazingira', 'kiwanda kinachochafua', 'maji machafu',
    'kelele za kiwanda', 'nema', 'kutupa taka',
    # Procurement (sw)
    'zabuni', 'manunuzi ya serikali', 'mkataba wa serikali',
    'serikali haijalipi', 'mchujo wa zabuni',
    # Health (sw)
    'hospitali ilikataa', 'dawa zilikataliwa', 'huduma ya dharura ilikataliwa',
    'uzembe wa daktari', 'haki ya afya',
    # Legal
    'haki zangu', 'haki zake', 'haki yake', 'haki yangu', 'kisheria',
    'madai', 'barua ya kudai', 'fidia', 'ushahidi', 'katiba', 'haramu',
    'ukiukwaji', 'rufaa', 'kesi', 'wakili', 'mahakamani', 'madai',
    'alinifukuza', 'hakulipa', 'alinishambulia', 'ananisumbua',
    'wameniambia', 'wananitaka', 'wananilazimisha', 'wananidhulumu',
}

def keyword_suggests_legal(message: str) -> bool:
    """
    Stage 1: Fast keyword scan. Returns True if any legal keyword found.
    No API call. Handles ~70% of cases instantly.
    """
    text = message.lower()
    for kw in _INTENT_KW_EN:
        if kw in text:
            return True
    for kw in _INTENT_KW_SW:
        if kw in text:
            return True
    return False


def classify_intent(message: str, lang: str = 'sw', history: list = None) -> str:
    """
    Two-stage intent classifier. Returns 'LEGAL' or 'CHAT'.

    Stage 1: keyword scan (instant, free)
    Stage 2: AI classifier via Groq (only when keywords are inconclusive)

    'LEGAL' → route to the RAG + law pipeline
    'CHAT'  → route to the conversational persona
    """
    # Very short messages with no context → conversational
    if len(message.strip()) < 4:
        return 'CHAT'

    msg_lower = message.lower().strip()
    msg_clean = msg_lower.rstrip('?!.,')

    # ── Check pure-chat and frustration FIRST — before keyword scan ──────
    # These must win even if the message accidentally contains a legal word
    # e.g. "that is wrong about my rights" has 'rights' but is frustration
    _pure_chat = {
        'hello', 'hi', 'hey', 'habari', 'sasa', 'mambo', 'niaje', 'ok',
        'okay', 'sawa', 'thanks', 'thank you', 'asante', 'nashukuru',
        'good morning', 'good afternoon', 'good evening',
        'who are you', 'what is your name', 'wewe ni nani', 'jina lako ni nani',
        'are you a bot', 'are you human', 'are you real', 'wewe ni roboti',
        'what do you do', 'can you help me', 'tell me about yourself',
        'what can you do', 'how does this work', 'are you intelligent',
        'do you think you are intelligent', 'do you think youre intelligent',
        'are you smart', 'what are you', 'how are you', 'how is life',
        'how is life as an ai', 'what is your purpose', 'who made you',
        'who created you', 'who built you', 'do you have feelings',
        'can you write code', 'can you code', 'write code', 'write me code',
        'write python', 'write a program', 'do you do coding',
        'what do you know', 'what else can you do',
        # Frustration / meta-complaints about the bot
        'are you stupid', 'you are stupid', 'wewe ni mjinga', 'hujui chochote',
        'why are you not answering', 'you did not answer', 'hukujibu',
        'you did not understand', 'hukuelewa', 'unaelewa nini',
        'that is not what i asked', 'hiyo si swali langu', 'hiyo sio nilichouliza',
        'you are useless', 'wewe hufai', 'this is not helpful',
        'wrong answer', 'jibu baya', 'that is wrong', 'hiyo ni makosa',
        'you misunderstood', 'you misunderstood me', 'hukuelewa swali langu',
        'i did not ask that', 'sikuuliza hivyo', 'answer my question',
        'jibu swali langu', 'read my question', 'soma swali langu',
    }
    # Frustration prefix patterns — catch variants like "why are you not answering my case"
    _frustration_prefixes = (
        'are you stupid', 'you are stupid', 'wewe ni mjinga',
        'why are you not', 'you did not answer', 'you did not understand',
        'hukuelewa', 'hukujibu', 'that is not what i asked',
        'you misunderstood', 'i did not ask that', 'sikuuliza',
        'this is not helpful', 'you are useless', 'wewe hufai',
        'wrong answer', 'jibu baya', 'answer my question', 'jibu swali',
        'read my question', 'soma swali',
    )
    if msg_clean in _pure_chat or msg_lower.startswith(_frustration_prefixes):
        logger.debug("[Intent] Stage1=CHAT (pure chat / frustration): %s", message[:60])
        return 'CHAT'

    # Short messages with no legal context → conversational
    if len(message.strip()) < 12:
        return 'CHAT'

    # ── Stage 1: keyword scan ─────────────────────────────────────────────
    if keyword_suggests_legal(message):
        logger.debug("[Intent] Stage1=LEGAL (keyword): %s", message[:60])
        return 'LEGAL'

    # ── Stage 2: AI classifier ────────────────────────────────────────────
    groq_key = os.getenv('GROQ_API_KEY', '').strip()
    if not groq_key:
        # No Groq key — default to LEGAL for longer messages (safer)
        return 'LEGAL' if len(message.strip()) > 20 else 'CHAT'

    # Build context from history (last user message, if any)
    context_hint = ''
    if history:
        for turn in reversed(history):
            if turn.get('role') == 'user' and turn.get('content'):
                context_hint = f"\nPrior message: {turn['content'][:100]}"
                break

    classifier_prompt = (
        "You are an intent classifier for HakiMkononi, a Kenyan legal AI.\n"
        "Classify the following message as either LEGAL or CHAT.\n\n"
        "LEGAL = the person has a legal problem, dispute, complaint, or is asking about their rights under Kenyan law.\n"
        "CHAT  = the person is making conversation, asking about you, expressing feelings, or anything not related to a legal problem.\n\n"
        "When in doubt, choose LEGAL — it is better to give legal help than to miss a real problem.\n"
        "Reply with exactly one word: LEGAL or CHAT. Nothing else."
        f"{context_hint}"
    )

    try:
        r = http_requests.post(
            GROQ_URL,
            headers=_groq_headers(),
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': classifier_prompt},
                    {'role': 'user', 'content': message},
                ],
                'temperature': 0.0,   # deterministic
                'max_tokens': 5,       # one word only
            },
            timeout=(5, 15),
        )
        r.raise_for_status()
        result = r.json()['choices'][0]['message']['content'].strip().upper()
        intent = 'LEGAL' if 'LEGAL' in result else 'CHAT'
        logger.debug("[Intent] Stage2=AI result=%s for: %s", intent, message[:60])
        return intent
    except Exception as exc:
        logger.warning("[Intent] AI classifier failed (%s) — defaulting to LEGAL", exc)
        # When the classifier fails, default to LEGAL (give legal answer rather than miss a real problem)
        return 'LEGAL' if len(message.strip()) > 20 else 'CHAT'


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

    # Trim the letter at the first self-rep section header so it doesn't bleed into them
    self_rep_boundaries = [
        "## COURT DOCUMENT", "## HATI YA MAHAKAMA",
        "## EVIDENCE CHECKLIST", "## ORODHA YA USHAHIDI",
        "## PROCEDURE TIMELINE", "## RATIBA YA HATUA",
    ]
    if sections["letter"]:
        letter_upper = sections["letter"].upper()
        earliest = len(sections["letter"])
        for boundary in self_rep_boundaries:
            pos = letter_upper.find(boundary.upper())
            if pos != -1 and pos < earliest:
                earliest = pos
        sections["letter"] = sections["letter"][:earliest].strip()

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
        "max_tokens":  3000,   # reduced from 4000 — stays within Groq free-tier token/min limit
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
