"""
HakiMkononi — Telegram Bot (python-telegram-bot v21)
Run with: python telegram_bot.py

Uses polling — no webhook, no ngrok, no public URL needed.
The bot connects directly to Telegram's servers.

Flow:
  /start or first message → language selection (1/2/3)
  Reply 1/2/3             → saves language, sends welcome
  Any other message       → RAG + Groq answer in chosen language
  /language               → change language at any time
  /help                   → show instructions
"""

import os
import re
import logging
import threading

from dotenv import load_dotenv
load_dotenv(override=True)

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler,
)

from cases.models import WhatsAppUser
from asgiref.sync import sync_to_async
from cases.rag import find_relevant_laws
from cases.ai_engine import (
    _call_groq, SYSTEM_PROMPTS, _USER_MESSAGES,
    format_law_context, parse_answer_sections, is_serious_criminal,
)

# ── Logging ───────────────────────────────────────────────────────────────────
# Use the root logger config — gunicorn inherits it so all bot logs
# appear in the same Render log stream as the web server.
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("hakimkononi_bot")

# ── Conversation states ───────────────────────────────────────────────────────
CHOOSING_LANG  = 1
ANSWERING      = 2
FILLING_LETTER = 3
FILLING_PHONE  = 4


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user(tg_id: int) -> WhatsAppUser:
    """Get or create a WhatsAppUser record — wrapped for async Django."""
    @sync_to_async
    def _db():
        user, _ = WhatsAppUser.objects.get_or_create(phone=f"tg:{tg_id}")
        return user
    return await _db()


async def _save_user_lang(user: WhatsAppUser, lang: str, state: str):
    """Save language + state — wrapped for async Django."""
    @sync_to_async
    def _db():
        user.lang  = lang
        user.state = state
        user.save()
    await _db()


async def _set_user_state(user: WhatsAppUser, state: str):
    """Save state only — wrapped for async Django."""
    @sync_to_async
    def _db():
        user.state = state
        user.save(update_fields=['state'])
    await _db()


def _get_matched_lawyers(query_id: int, county: str = '', top_laws=None) -> list:
    """
    Find verified lawyers matching the case type and county.
    Returns a list of dicts with name, county, specialties, wa_link.
    """
    try:
        from cases.models import Lawyer
        # Map law categories to lawyer specialties
        spec_map = {
            'employment':         ['employment'],
            'criminal_procedure': ['criminal'],
            'land':               ['land'],
            'landlord_tenant':    ['land'],
            'consumer':           ['consumer'],
            'other':              ['family', 'consumer', 'data'],
        }
        needed = set()
        if top_laws:
            for law in top_laws:
                needed.update(spec_map.get(law.category, []))

        verified = Lawyer.objects.filter(kyc_status=Lawyer.KYC_VERIFIED, is_active=True)

        # County match first
        if county:
            county_match = list(verified.filter(county__iexact=county))
        else:
            county_match = []

        pool = county_match if len(county_match) >= 2 else list(verified)

        # Filter by specialty
        if needed:
            spec_match = [l for l in pool if any(s in (l.specialties or []) for s in needed)]
            lawyers = spec_match[:3] if spec_match else pool[:3]
        else:
            lawyers = pool[:3]

        result = []
        for l in lawyers:
            wa_msg = (
                f"Habari {l.full_name}, ninahitaji msaada wa kisheria. "
                f"Nilikupata kwenye HakiMkononi."
            )
            result.append({
                'name':        l.full_name,
                'county':      l.county,
                'specialties': l.specialty_labels[:2],
                'firm':        l.firm_name,
                'years':       l.years_experience,
                'wa_link':     l.get_whatsapp_link(wa_msg),
                'tg_link':     l.get_telegram_link(),
            })
        return result
    except Exception:
        return []


def _lang_keyboard():
    return ReplyKeyboardMarkup(
        [["1️⃣ Kiswahili", "2️⃣ English"]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )


def _main_keyboard(lang: str):
    """
    Persistent keyboard shown after language selection.
    Always visible at the bottom — includes voice prompt button.
    """
    if lang == 'sw':
        return ReplyKeyboardMarkup(
            [["🎤 Tuma Sauti", "❓ Swali Jipya"],
             ["📞 Pata Wakili", "⚖️ /help"]],
            resize_keyboard=True,
            one_time_keyboard=False,   # persistent — stays visible
        )
    return ReplyKeyboardMarkup(
        [["🎤 Send Voice", "❓ New Question"],
         ["📞 Find a Lawyer", "⚖️ /help"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def _main_keyboard(lang: str):
    """Quick reply keyboard shown after an answer."""
    if lang == 'sw':
        return ReplyKeyboardMarkup(
            [["❓ Swali jingine", "📞 Pata Wakili"],
             ["🗑️ Anza upya", "⚖️ /help"]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        [["❓ Ask another question", "📞 Find a Lawyer"],
         ["🗑️ Start fresh", "⚖️ /help"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _fill_letter(template: str, name: str, phone: str = "") -> str:
    """Replace [YOUR NAME], [DATE], [PHONE NUMBER] placeholders with real values."""
    # Windows-safe date formatting
    try:
        from datetime import date as _date
        today = _date.today().strftime("%d %B %Y").lstrip("0")
    except Exception:
        from datetime import date as _date
        today = _date.today().isoformat()

    result = template
    result = result.replace("[YOUR NAME]", name)
    result = result.replace("[JINA LAKO]", name)
    result = result.replace("[DATE]", today)
    result = result.replace("[TAREHE]", today)
    result = result.replace("[YOUR ADDRESS]", "[Your address — add this]")
    result = result.replace("[ANWANI YAKO]", "[Anwani yako — ongeza hapa]")
    result = result.replace("[ANWANI]", "[Anwani yako — ongeza hapa]")
    if phone:
        result = result.replace("[PHONE NUMBER]", phone)
        result = result.replace("[NAMBARI YA SIMU]", phone)
    return result


def _letter_is_complete(letter: str) -> bool:
    """Check the letter ends with a proper closing — not cut off mid-sentence."""
    closings = [
        "yours faithfully", "yours sincerely", "yours truly",
        "wako katika heshima", "wako kwa heshima",
        "[phone number]", "[nambari ya simu]",
        "kenyalaw.org", "legal advice",
    ]
    letter_lower = letter.lower().strip()
    return any(letter_lower.endswith(c) or c in letter_lower[-200:] for c in closings)


def _repair_letter(letter: str, lang: str = "en") -> str:
    """If letter was cut off, append a proper closing so it's usable."""
    if _letter_is_complete(letter):
        return letter
    # Trim any broken last sentence (ends without punctuation)
    lines = letter.rstrip().split('\n')
    # Remove last line if it looks incomplete (no punctuation at end)
    while lines and lines[-1].strip() and not lines[-1].strip()[-1] in '.!?,':
        lines.pop()
    letter = '\n'.join(lines)
    if lang == 'sw':
        letter += (
            "\n\nNitachukua hatua za kisheria kama ombi hili halitafanyika ndani ya siku 14.\n\n"
            "Wako kwa heshima,\n[JINA LAKO]\n[NAMBARI YA SIMU]"
        )
    else:
        letter += (
            "\n\nFailure to comply within 14 days will compel me to seek legal redress.\n\n"
            "Yours faithfully,\n[YOUR NAME]\n[PHONE NUMBER]"
        )
    return letter
    return ReplyKeyboardMarkup(
        [["1️⃣ Kiswahili", "2️⃣ English"]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )



def _format_answer(answer: dict, top_laws: list, lang: str) -> str:
    """Build a clean Telegram message from the 4-box answer."""
    L = {
        'sw':    {'law': '📜 *Sheria Inasema*',    'simple': '💬 *Tafsiri Rahisi*',  'rights': '💪 *Haki Yako*',     'letter': '✉️ *Andika Hivi*'},
        'en':    {'law': '📜 *What The Law Says*', 'simple': '💬 *Plain Explanation*','rights': '💪 *Your Rights*',   'letter': '✉️ *Write This*'},
    }.get(lang, {'law': '📜 *Law*', 'simple': '💬 *Explanation*', 'rights': '💪 *Rights*', 'letter': '✉️ *Letter*'})

    DIV = '─────────────────────'

    def clean(text):
        if not text: return ''
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        text = re.sub(r'__(.+?)__',      r'*\1*', text)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^>\s?',  '', text, flags=re.MULTILINE)
        return text.strip()

    parts = []
    if answer.get('law'):
        parts.append(f"{DIV}\n{L['law']}\n{clean(answer['law'])}")
    if answer.get('simple'):
        parts.append(f"{DIV}\n{L['simple']}\n{clean(answer['simple'])}")
    if answer.get('loophole'):
        parts.append(f"{DIV}\n{L['rights']}\n{clean(answer['loophole'])}")
    if answer.get('letter'):
        # Plain text — not code block — easier to read and copy on mobile
        letter = clean(answer['letter'])[:1500]
        parts.append(f"{DIV}\n{L['letter']}\n{letter}")
    if top_laws:
        src = '\n'.join(f"  {i+1}. {l.title} — {l.section}" for i, l in enumerate(top_laws[:4]))
        parts.append(f"{DIV}\n📚 *Sources*\n{src}")

    disclaimer = {
        'sw':    '⚠️ _Taarifa ya kisheria tu — si ushauri wa kisheria._',
        'en':    '⚠️ _Legal information only — not legal advice._',
    }.get(lang, '')
    parts.append(disclaimer)

    return '\n\n'.join(p for p in parts if p)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _get_user(update.effective_user.id)
    tg_user = update.effective_user
    first_name = tg_user.first_name or ''
    logger.info(f"[TelegramBot] /start — user {tg_user.id} (@{tg_user.username})")

    # Returning user with language already set — skip picker, go straight to answering
    if user.state == WhatsAppUser.STATE_ACTIVE:
        lang = user.lang
        name_greeting = f", {first_name}" if first_name else ""
        msg = {
            'sw': (
                f"👋 *Karibu tena{name_greeting}!*\n\n"
                "Niko hapa. Niambie tatizo lako la kisheria.\n\n"
                "_Andika /language kubadilisha lugha._"
            ),
            'en': (
                f"👋 *Welcome back{name_greeting}!*\n\n"
                "I'm here. Tell me your legal problem.\n\n"
                "_Type /language to change language._"
            ),
        }.get(lang, f"👋 Welcome back{name_greeting}! Tell me your legal problem.")
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ANSWERING

    # New user — show language picker
    await _set_user_state(user, WhatsAppUser.STATE_NEW)
    name_greeting = f", {first_name}" if first_name else ""
    await update.message.reply_text(
        f"👋 *Karibu HakiMkononi{name_greeting}!*\n\n"
        "Mimi ni AI inayokusaidia kuelewa haki zako za kisheria Kenya *bila malipo*.\n\n"
        "Unaweza andika au *tuma sauti* — ninaelewa Kiswahili na Kingereza.\n\n"
        "Chagua lugha yako / Choose your language:\n\n"
        "1️⃣  Kiswahili\n"
        "2️⃣  English",
        parse_mode="Markdown",
        reply_markup=_lang_keyboard(),
    )
    return CHOOSING_LANG


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _get_user(update.effective_user.id)
    await _set_user_state(user, WhatsAppUser.STATE_NEW)
    await update.message.reply_text(
        "🌍 *Chagua lugha yako / Choose your language:*\n\n"
        "1️⃣  Kiswahili\n"
        "2️⃣  English\n\n"
        "Jibu na *1* au *2* / Reply with *1* or *2*:",
        parse_mode="Markdown",
        reply_markup=_lang_keyboard(),
    )
    return CHOOSING_LANG


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _get_user(update.effective_user.id)
    lang = user.lang
    msgs = {
        'sw': (
            "⚖️ *HakiMkononi — Msaada*\n\n"
            "Niambie tatizo lako la kisheria kwa sentensi 1-2.\n"
            "Unaweza *andika* au *tuma sauti* 🎤\n\n"
            "*Mifano:*\n"
            "• Nilifukuzwa kazi bila notisi\n"
            "• Landlord alinifunga nje bila notisi\n"
            "• Polisi walinishika bila warrant\n"
            "• Mke wangu anaficha mali yetu\n\n"
            "*Utapata:*\n"
            "📜 Sheria inasema nini\n"
            "💬 Maelezo rahisi\n"
            "💪 Haki zako\n"
            "✉️ Barua ya kudai haki (iliyojazwa na jina lako)\n\n"
            "📌 *Amri:*\n"
            "/language — Badilisha lugha\n"
            "/clear — Anza mazungumzo mapya\n"
            "/stop — Maliza\n"
            "/help — Msaada huu"
        ),
        'en': (
            "⚖️ *HakiMkononi — Help*\n\n"
            "Tell me your legal problem in 1-2 sentences.\n"
            "You can *type* or *send a voice message* 🎤\n\n"
            "*Examples:*\n"
            "• My employer fired me without notice\n"
            "• My landlord locked me out without notice\n"
            "• Police arrested me without a warrant\n"
            "• My spouse is hiding our shared property\n\n"
            "*You get:*\n"
            "📜 What the law says\n"
            "💬 Plain explanation\n"
            "💪 Your rights\n"
            "✉️ A demand letter filled with your name\n\n"
            "📌 *Commands:*\n"
            "/language — Change language\n"
            "/clear — Start a new conversation\n"
            "/stop — End conversation\n"
            "/help — This help message"
        ),
    }
    if user.state == WhatsAppUser.STATE_NEW:
        await update.message.reply_text(
            "⚖️ *HakiMkononi — Help*\n\n"
            "Niambie tatizo lako la kisheria / Tell me your legal problem.\n\n"
            "*Mifano / Examples:*\n"
            "• Nilifukuzwa kazi bila notisi\n"
            "• My employer fired me without notice\n"
            "• Boss wangu alinifukuza bila notice\n\n"
            "📌 *Commands:*\n"
            "/start — Chagua lugha / Choose language\n"
            "/language — Badilisha lugha / Change language",
            parse_mode="Markdown",
        )
        return CHOOSING_LANG
    await update.message.reply_text(msgs.get(lang, msgs['en']), parse_mode="Markdown")
    return ANSWERING


# ── Conversation handlers ─────────────────────────────────────────────────────



async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle voice messages — transcribe with Groq Whisper then answer."""
    user = await _get_user(update.effective_user.id)

    # Language not chosen yet — ask first
    if user.state == WhatsAppUser.STATE_NEW:
        await update.message.reply_text(
            "👋 *Karibu HakiMkononi!*\n\n"
            "Chagua lugha kwanza / Choose language first:\n\n"
            "1️⃣  Kiswahili\n2️⃣  English\n\n"
            "Jibu na *1* au *2*:",
            parse_mode="Markdown",
            reply_markup=_lang_keyboard(),
        )
        return CHOOSING_LANG

    lang    = user.lang
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    ack_msg = await update.message.reply_text(
        '🎤 ' + ('Inatafsiri sauti yako…' if lang == 'sw' else 'Transcribing your voice…')
    )

    try:
        # Download audio
        voice   = update.message.voice or update.message.audio
        tg_file = await context.bot.get_file(voice.file_id)
        import io
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        file_bytes = buf.getvalue()

        # Transcribe in thread (blocking HTTP call)
        @sync_to_async(thread_sensitive=False)
        def do_transcribe():
            import requests as _req, os
            groq_key     = os.environ.get('GROQ_API_KEY', '').strip()
            lang_map     = {'sw': 'sw', 'en': 'en'}
            whisper_lang = lang_map.get(lang)
            data = {'model': 'whisper-large-v3', 'response_format': 'verbose_json', 'temperature': '0'}
            if whisper_lang:
                data['language'] = whisper_lang
            r = _req.post(
                'https://api.groq.com/openai/v1/audio/transcriptions',
                headers={'Authorization': f'Bearer {groq_key}'},
                files={'file': ('voice.ogg', file_bytes, 'audio/ogg')},
                data=data,
                timeout=30,
            )
            if r.status_code != 200:
                return '', ''
            result = r.json()
            return result.get('text', '').strip(), result.get('language', '')

        transcript, detected_lang = await do_transcribe()

        if not transcript:
            await ack_msg.edit_text(
                '❌ ' + ('Sikuweza kuelewa sauti yako. Jaribu tena au andika.' if lang == 'sw'
                          else 'Could not understand the audio. Please try again or type.')
            )
            return ANSWERING

        # Show what was heard so user can verify accuracy
        heard = '🎤 Nilisikia: ' if lang == 'sw' else '🎤 I heard: '
        await ack_msg.edit_text(
            f"{heard}_\"{transcript[:100]}\"_\n\n"
            f"⏳ {'Inasoma sheria…' if lang == 'sw' else 'Reading the law…'}",
            parse_mode="Markdown"
        )

        # Run AI in thread
        @sync_to_async(thread_sensitive=False)
        def run_ai():
            from cases.ai_engine import (
                _call_groq, SYSTEM_PROMPTS, _USER_MESSAGES,
                format_law_context, parse_answer_sections, is_serious_criminal,
            )
            if is_serious_criminal(transcript):
                return None, None, True
            top_laws   = find_relevant_laws(transcript, top_n=8, category_boost=['constitution'])
            reply_lang = 'sw' if lang == 'sheng' else lang
            ctx        = format_law_context(top_laws)
            system     = SYSTEM_PROMPTS[reply_lang].format(context=ctx)
            user_msg   = _USER_MESSAGES[reply_lang].format(story=transcript)
            raw        = _call_groq([{"role": "system", "content": system},
                                     {"role": "user",   "content": user_msg}])
            answer     = parse_answer_sections(raw, lang=reply_lang)
            return answer, top_laws, False

        answer, top_laws, is_serious = await run_ai()

        if is_serious:
            await ack_msg.edit_text(
                "🚨 *Kesi Nyeti*\n\nKesi hii inahitaji wakili haraka.\n\n*NLAS (Bure):* 0800 720 120\nwww.nlas.go.ke"
                if lang == 'sw' else
                "🚨 *Serious Case*\n\nThis needs a lawyer urgently.\n\n*NLAS (Free):* 0800 720 120\nwww.nlas.go.ke",
                parse_mode="Markdown"
            )
            return ANSWERING

        reply_lang = 'sw' if lang == 'sheng' else lang
        reply      = _format_answer(answer, top_laws, reply_lang)
        await ack_msg.delete()

        MAX = 4000
        if len(reply) <= MAX:
            await update.message.reply_text(reply, parse_mode="Markdown")
        else:
            chunks, current = [], ''
            for block in reply.split('\n\n'):
                if len(current) + len(block) + 2 <= MAX:
                    current = (current + '\n\n' + block).strip()
                else:
                    if current: chunks.append(current)
                    current = block
            if current: chunks.append(current)
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode="Markdown")

        # ── Letter personalisation — same flow as typed questions ────────
        if answer.get('letter') and (
            '[YOUR NAME]' in answer['letter'] or '[JINA LAKO]' in answer['letter']
        ):
            from cases.rag import _repair_letter
            repaired = _repair_letter(answer['letter'], reply_lang)
            context.user_data['pending_letter'] = repaired
            context.user_data['letter_lang']    = reply_lang
            name_prompt = {
                'sw': (
                    "✍️ *Barua ipo tayari!*\n\n"
                    "Niambie *jina lako kamili* ili niijaze barua yako:\n"
                    "_(au andika /skip kuruka hatua hii)_"
                ),
                'en': (
                    "✍️ *Your letter is ready!*\n\n"
                    "Type your *full name* and I'll fill it in for you:\n"
                    "_(or type /skip to skip this step)_"
                ),
            }.get(reply_lang, "✍️ Type your full name to complete the letter:")
            await update.message.reply_text(name_prompt, parse_mode="Markdown")
            return FILLING_LETTER

        await update.message.reply_text(
            '❓ Una swali lingine? Andika au tuma sauti.' if lang == 'sw'
            else '❓ Another question? Type or send a voice message.',
            reply_markup=_main_keyboard(reply_lang)
        )

    except Exception as e:
        logger.error(f"Voice handler error: {e}", exc_info=True)
        try:
            await ack_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(
            '❌ Samahani, kuna tatizo. Jaribu tena au andika swali lako.' if lang == 'sw'
            else '❌ Sorry, something went wrong. Try again or type your question instead.'
        )

    return ANSWERING


async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    user = await _get_user(update.effective_user.id)

    if text.startswith("1") or "kiswahili" in text:
        chosen, name = 'sw', 'Kiswahili 🇰🇪'
    elif text.startswith("2") or "english" in text:
        chosen, name = 'en', 'English 🇬🇧'
    else:
        # Any other text — show the full friendly welcome
        await update.message.reply_text(
            "👋 *Karibu HakiMkononi!*\n\n"
            "Mimi ni AI inayokusaidia kuelewa sheria ya Kenya *bila malipo*.\n\n"
            "Chagua lugha yako / Choose your language:\n\n"
            "1️⃣  Kiswahili\n"
            "2️⃣  English\n\n"
            "Jibu na *1* au *2* / Reply with *1* or *2*:",
            parse_mode="Markdown",
            reply_markup=_lang_keyboard(),
        )
        return CHOOSING_LANG

    await _save_user_lang(user, chosen, WhatsAppUser.STATE_ACTIVE)

    confirm = {
        'sw': (
            f"✅ Vizuri! Lugha: *{name}*\n\n"
            "Sasa niambie tatizo lako la kisheria.\n\n"
            "_Mfano: Nilifukuzwa kazi bila notisi na mwajiri wangu._\n\n"
            "💡 Unaweza *andika* au *tuma sauti* — ninaelewa vyote.\n"
            "Nitakupa maelezo ya sheria, haki zako, na barua ya kudai haki.\n\n"
            "_Andika /help kwa mifano zaidi._"
        ),
        'en': (
            f"✅ Great! Language: *{name}*\n\n"
            "Now tell me your legal problem.\n\n"
            "_Example: My employer fired me without notice._\n\n"
            "💡 You can *type* or *send a voice message* — I understand both.\n"
            "I'll explain your rights and write you a demand letter.\n\n"
            "_Type /help for more examples._"
        ),
    }[chosen]

    await update.message.reply_text(
        confirm,
        parse_mode="Markdown",
        reply_markup=_main_keyboard(chosen),
    )
    return ANSWERING


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user    = await _get_user(update.effective_user.id)
    lang    = user.lang
    message = update.message.text.strip()
    logger.info(f"[TelegramBot] Question from {update.effective_user.id} [{lang}]: {message[:80]}")

    # If still in NEW state, show full welcome
    if user.state == WhatsAppUser.STATE_NEW:
        await update.message.reply_text(
            "👋 *Karibu HakiMkononi!*\n\n"
            "Mimi ni AI inayokusaidia kuelewa sheria ya Kenya *bila malipo*.\n\n"
            "Chagua lugha yako / Choose your language:\n\n"
            "1️⃣  Kiswahili\n"
            "2️⃣  English\n\n"
            "Jibu na *1* au *2* / Reply with *1* or *2*:",
            parse_mode="Markdown",
            reply_markup=_lang_keyboard(),
        )
        return CHOOSING_LANG

    # ── Handle quick-reply keyboard button taps ─────────────────────────
    _CLEAR_BUTTONS    = {'🗑️ anza upya', '🗑️ start fresh', 'start fresh', 'anza upya'}
    _LAWYER_BUTTONS   = {'📞 pata wakili', '📞 find a lawyer', 'find a lawyer', 'pata wakili'}
    _QUESTION_BUTTONS = {'❓ swali jingine', '❓ ask another question', 'ask another question',
                         'swali jingine', '❓ new question', '❓ swali jipya', 'new question', 'swali jipya'}
    _VOICE_BUTTONS    = {'🎤 send voice', '🎤 tuma sauti', 'send voice', 'tuma sauti'}

    msg_clean = message.lower().strip().rstrip('!?.')

    # Voice prompt button
    if msg_clean in _VOICE_BUTTONS:
        voice_tip = {
            'sw': (
                "🎤 *Jinsi ya kutuma sauti:*\n\n"
                "1. Bonyeza na ushikilie ikoni ya 🎤 kwenye kibodi yako\n"
                "2. Sema swali lako la kisheria\n"
                "3. Acha kidole. Ujumbe wa sauti utatumwa moja kwa moja\n\n"
                "_Mfano: 'Mwajiri wangu alinifukuza bila notisi...'_"
            ),
            'en': (
                "🎤 *How to send a voice message:*\n\n"
                "1. Press and hold the 🎤 microphone icon on your keyboard\n"
                "2. Speak your legal question clearly\n"
                "3. Release. Your voice note will be sent automatically\n\n"
                "_Example: 'My employer fired me without notice...'_"
            ),
        }.get(lang, "🎤 Press and hold the mic icon on your keyboard to record.")
        await update.message.reply_text(voice_tip, parse_mode="Markdown",
                                        reply_markup=_main_keyboard(lang))
        return ANSWERING
    if msg_clean in _CLEAR_BUTTONS:
        context.user_data.clear()
        reply = {
            'sw': "━━━━━━━━━━━━━━━━━━━━━━\n🗑️ *Anza upya*\n━━━━━━━━━━━━━━━━━━━━━━\n\nNiambie tatizo lako jipya la kisheria.",
            'en': "━━━━━━━━━━━━━━━━━━━━━━\n🗑️ *Starting fresh*\n━━━━━━━━━━━━━━━━━━━━━━\n\nTell me your new legal problem.",
        }.get(lang, "Starting fresh. Tell me your new legal problem.")
        await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ANSWERING

    if msg_clean in _LAWYER_BUTTONS:
        # Try to show verified platform lawyers first
        @sync_to_async(thread_sensitive=False)
        def fetch_any_lawyers():
            return _get_matched_lawyers(0)

        any_lawyers = await fetch_any_lawyers()
        if any_lawyers:
            intro = {
                'sw': "💼 *Mawakili Walioidhinishwa wa HakiMkononi:*",
                'en': "💼 *HakiMkononi Verified Lawyers:*",
            }.get(lang, "💼 *Verified Lawyers:*")
            await update.message.reply_text(intro, parse_mode="Markdown")
            for l in any_lawyers:
                specs = ', '.join(l['specialties']) if l['specialties'] else ''
                firm = f"\n_{l['firm']}_" if l['firm'] else ''
                contacts = f"[💬 WhatsApp]({l['wa_link']})"
                if l.get('tg_link'):
                    contacts += f"  |  [✈️ Telegram]({l['tg_link']})"
                card = (
                    f"👤 *{l['name']}*{firm}\n"
                    f"📍 {l['county']}\n"
                    f"⚖️ {specs}\n\n"
                    f"{contacts}"
                )
                await update.message.reply_text(card, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            # No verified lawyers yet — fall back to free resources
            reply = {
                'sw': "📞 *Msaada wa Kisheria Bila Malipo Kenya*\n\n*NLAS:* 0800 720 120\n_National Legal Aid Service — bure kabisa_\n\n*Kituo Cha Sheria:* 0800 720 372\n\n*LSK Pro Bono:* lsk.or.ke",
                'en': "📞 *Free Legal Help in Kenya*\n\n*NLAS:* 0800 720 120\n_National Legal Aid Service — completely free_\n\n*Kituo Cha Sheria:* 0800 720 372\n\n*LSK Pro Bono:* lsk.or.ke",
            }.get(lang, "📞 NLAS: 0800 720 120 (free lawyers)")
            await update.message.reply_text(reply, parse_mode="Markdown")
        return ANSWERING

    if msg_clean in _QUESTION_BUTTONS:
        nudge = {
            'sw': "👍 Niko tayari! Niambie tatizo lako jipya la kisheria.",
            'en': "👍 Ready! Tell me your new legal problem.",
        }.get(lang, "Ready! Tell me your legal problem.")
        await update.message.reply_text(nudge, reply_markup=ReplyKeyboardRemove())
        return ANSWERING

    # ── Greeting / too-short message detection ───────────────────────────

    # Thank you messages — separate from greetings, need a warm response
    _THANKS = {
        'thanks', 'thank you', 'thank you so much', 'thank you very much',
        'thanks a lot', 'asante', 'asante sana', 'nashukuru', 'shukrani',
        'sawa asante', 'nimeshukuru', 'appreciated', 'it helped',
        'ilisaidia', 'helpful', 'that helped', 'you helped me',
        'umesaidia', 'umenihelp', 'great', 'wonderful', 'excellent',
        'perfect', 'amazing', 'awesome',
    }
    msg_stripped_for_thanks = message.lower().strip().rstrip('!?.,:')
    if msg_stripped_for_thanks in _THANKS:
        import random
        responses_sw = [
            "😊 Karibu sana!\n\nNimefurahi kukusaidia. Haki zako ni muhimu na unastahili kuzijua.\n\nUkiwa na swali jingine la kisheria, niko hapa wakati wowote.",
            "😊 Karibu!\n\nNimefurahi sana. Kazi yangu ni kuhakikisha Wakenya wote wanajua haki zao.\n\nUkihitaji msaada tena, niambie tu.",
            "🙏 Karibu sana!\n\nNimefurahi kukusaidia leo. Kumbuka kushiriki HakiMkononi na wengine wanaohitaji msaada wa kisheria.",
        ]
        responses_en = [
            "😊 You're welcome!\n\nI'm really glad I could help. Your rights matter and you deserve to know them.\n\nIf you ever have another legal question, I'm here anytime.",
            "😊 Happy to help!\n\nThat's exactly what I'm here for. No one should face a legal problem alone.\n\nFeel free to ask anything else whenever you need.",
            "🙏 You're welcome!\n\nI'm glad the answer was useful. Share HakiMkononi with others who might need legal help too.",
        ]
        responses = responses_sw if lang == 'sw' else responses_en
        reply = random.choice(responses)
        await update.message.reply_text(reply, parse_mode="Markdown",
                                        reply_markup=_main_keyboard(lang))
        return ANSWERING

    _GREETINGS = {
        'hello', 'hi', 'hey', 'hii', 'habari', 'habari yako', 'sasa',
        'mambo', 'niaje', 'vipi', 'sup', 'hola', 'salamu', 'karibu',
        'good morning', 'good afternoon', 'good evening', 'good day',
        'asubuhi njema', 'ok', 'okay', 'sawa', 'fine',
        'yes', 'no', 'ndiyo', 'hapana', '👋', '😊',
    }
    msg_lower_stripped = message.lower().strip().rstrip('!?.,:')
    is_greeting = msg_lower_stripped in _GREETINGS or len(message.strip()) < 8

    if is_greeting:
        nudge = {
            'sw': (
                "👋 Habari!\n\n"
                "Niambie tatizo lako la kisheria ili nikusaidie.\n\n"
                "*Mfano:*\n"
                "_Nilifukuzwa kazi bila notisi na mwajiri wangu._\n\n"
                "Andika tatizo lako na nitakusaidia kuelewa haki zako."
            ),
            'en': (
                "👋 Hello!\n\n"
                "Tell me your legal problem and I'll help you.\n\n"
                "*Example:*\n"
                "_My employer fired me without notice._\n\n"
                "Describe your situation and I'll explain your rights."
            ),
        }.get(lang, "👋 Hello! Tell me your legal problem and I'll help.")
        await update.message.reply_text(nudge, parse_mode="Markdown",
                                        reply_markup=_main_keyboard(lang))
        return ANSWERING

    # Serious case
    if is_serious_criminal(message):
        serious = {
            'sw': (
                "🚨 *Kesi Nyeti — Tafuta Wakili Haraka*\n\n"
                "Kesi hii inahitaji wakili wa kweli, si AI.\n\n"
                "📞 *NLAS (Bure):* 0800 720 120\n"
                "_NLAS = National Legal Aid Service — mawakili wa serikali bila malipo_\n\n"
                "🌐 www.nlas.go.ke"
            ),
            'en': (
                "🚨 *Serious Case — Get a Lawyer Urgently*\n\n"
                "This situation needs a real lawyer, not an AI.\n\n"
                "📞 *NLAS (Free):* 0800 720 120\n"
                "_NLAS = National Legal Aid Service — free government lawyers_\n\n"
                "🌐 www.nlas.go.ke"
            ),
        }.get(lang, "🚨 *Serious Case* — Contact NLAS: 0800 720 120 (free lawyers)")
        await update.message.reply_text(serious, parse_mode="Markdown")
        return ANSWERING

    # Send instant "thinking" message + typing indicator
    ack = {
        'sw': '⏳ Inasoma sheria yako... jibu linakuja sekunde 15-20.',
        'en': '⏳ Reading the law for you... reply in 15-20 seconds.',
    }.get(lang, '⏳ Processing...')

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    thinking = await update.message.reply_text(ack)

    try:
        @sync_to_async(thread_sensitive=False)
        def run_ai():
            top_laws = find_relevant_laws(message, top_n=8, category_boost=['constitution'])
            ctx_text = format_law_context(top_laws)
            # Map any old sheng sessions to sw
            reply_lang = 'sw' if lang == 'sheng' else lang
            system   = SYSTEM_PROMPTS[reply_lang].format(context=ctx_text)
            user_msg = _USER_MESSAGES[reply_lang].format(story=message)
            raw      = _call_groq([
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ])
            answer = parse_answer_sections(raw, lang=reply_lang)
            return answer, top_laws, reply_lang

        answer, top_laws, reply_lang = await run_ai()
        reply = _format_answer(answer, top_laws, reply_lang)

        await thinking.delete()

        MAX = 4000
        if len(reply) <= MAX:
            await update.message.reply_text(reply, parse_mode="Markdown")
        else:
            chunks, current = [], ''
            for block in reply.split('\n\n'):
                if len(current) + len(block) + 2 <= MAX:
                    current = (current + '\n\n' + block).strip()
                else:
                    if current: chunks.append(current)
                    current = block
            if current: chunks.append(current)
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode="Markdown")

        # ── Show matched lawyers if any are available ─────────────────────
        @sync_to_async(thread_sensitive=False)
        def fetch_lawyers():
            return _get_matched_lawyers(0, top_laws=top_laws)

        lawyers = await fetch_lawyers()
        if lawyers:
            lawyer_intro = {
                'sw': "💼 *Mawakili Walioidhinishwa Wanaoweza Kukusaidia:*\n_(Wote wamepita ukaguzi wa HakiMkononi)_",
                'en': "💼 *Verified Lawyers Who Can Help You:*\n_(All verified by HakiMkononi)_",
            }.get(reply_lang, "💼 *Verified Lawyers:*")
            await update.message.reply_text(lawyer_intro, parse_mode="Markdown")

            for l in lawyers:
                specs = ', '.join(l['specialties']) if l['specialties'] else ''
                firm = f"\n_{l['firm']}_" if l['firm'] else ''
                years = f"  •  {l['years']} yrs exp" if l['years'] else ''
                # Build contact links
                contacts = f"[💬 WhatsApp]({l['wa_link']})"
                if l.get('tg_link'):
                    contacts += f"  |  [✈️ Telegram]({l['tg_link']})"
                card = (
                    f"👤 *{l['name']}*{firm}\n"
                    f"📍 {l['county']}{years}\n"
                    f"⚖️ {specs}\n\n"
                    f"{contacts}"
                )
                await update.message.reply_text(card, parse_mode="Markdown", disable_web_page_preview=True)

        # ── If letter was generated, ask for name to personalise it ──────────
        if answer.get('letter') and '[YOUR NAME]' in answer['letter'] or \
           answer.get('letter') and '[JINA LAKO]' in answer['letter']:
            # Repair letter before storing so it's always complete
            repaired = _repair_letter(answer['letter'], reply_lang)
            context.user_data['pending_letter'] = repaired
            context.user_data['letter_lang']    = reply_lang
            name_prompt = {
                'sw': (
                    "✍️ *Barua ipo tayari!*\n\n"
                    "Niambie *jina lako kamili* ili niijaze barua yako:\n"
                    "_(au andika /skip kuruka hatua hii)_"
                ),
                'en': (
                    "✍️ *Your letter is ready!*\n\n"
                    "Type your *full name* and I'll fill it in for you:\n"
                    "_(or type /skip to skip this step)_"
                ),
            }.get(reply_lang, "✍️ Type your full name to complete the letter:")
            await update.message.reply_text(name_prompt, parse_mode="Markdown")
            return FILLING_LETTER

        followup = {
            'sw': '❓ Una swali lingine? Andika au bonyeza chini.',
            'en': '❓ Have another question? Type it or tap below.',
        }.get(reply_lang, '❓ Any other question?')
        await update.message.reply_text(followup, reply_markup=_main_keyboard(reply_lang))

    except Exception as e:
        logger.error(f"Answer error: {e}", exc_info=True)
        try:
            await thinking.delete()
        except Exception:
            pass
        err = {
            'sw': (
                '❌ *Kuna tatizo la kiufundi.*\n\n'
                'Jaribu tena kwa kutuma swali lako upya.\n'
                '_Kama tatizo linaendelea, andika /help._'
            ),
            'en': (
                '❌ *A technical error occurred.*\n\n'
                'Please try sending your question again.\n'
                '_If it keeps happening, type /help._'
            ),
        }.get(lang, '❌ Error. Please try again or type /help.')
        await update.message.reply_text(err, parse_mode="Markdown")

    return ANSWERING


async def handle_letter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User replied with their name — save it and ask for phone number."""
    name = update.message.text.strip()
    lang = context.user_data.get('letter_lang', 'en')

    if not name or len(name) < 2:
        await update.message.reply_text(
            '⚠️ Tafadhali andika jina lako kamili.' if lang == 'sw'
            else '⚠️ Please type your full name.'
        )
        return FILLING_LETTER

    context.user_data['letter_name'] = name

    phone_prompt = {
        'sw': (
            f"✅ Asante, *{name}*!\n\n"
            "Sasa niambie *nambari yako ya simu*:\n"
            "_(au andika /skip kuruka)_"
        ),
        'en': (
            f"✅ Got it, *{name}*!\n\n"
            "Now type your *phone number*:\n"
            "_(or type /skip to skip)_"
        ),
    }.get(lang, f"✅ {name}. Type your phone number (or /skip):")
    await update.message.reply_text(phone_prompt, parse_mode="Markdown")
    return FILLING_PHONE


async def handle_letter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User replied with phone — validate, fill and send the complete letter."""
    phone = update.message.text.strip()
    lang  = context.user_data.get('letter_lang', 'en')
    name  = context.user_data.get('letter_name', '')

    # Basic phone validation — must look like a number
    phone_digits = re.sub(r'[\s\-\(\)]', '', phone)
    is_valid_phone = (
        phone_digits.lstrip('+').isdigit() and
        len(phone_digits) >= 9
    )
    if not is_valid_phone:
        warn = {
            'sw': "⚠️ Hiyo haionekani kama nambari ya simu. Jaribu tena (mfano: 0712345678)\n_(au andika /skip kuruka)_",
            'en': "⚠️ That doesn't look like a phone number. Try again (e.g. 0712345678)\n_(or type /skip to skip)_",
        }.get(lang, "⚠️ Invalid phone number. Try again or type /skip.")
        await update.message.reply_text(warn, parse_mode="Markdown")
        return FILLING_PHONE
    letter_template = context.user_data.get('pending_letter', '')

    # Clean up stored data
    for k in ('pending_letter', 'letter_lang', 'letter_name'):
        context.user_data.pop(k, None)

    if not letter_template:
        await update.message.reply_text(
            '❓ Una swali lingine? Andika hapa.' if lang == 'sw'
            else '❓ Have another question? Just type it.'
        )
        return ANSWERING

    filled = _fill_letter(letter_template, name, phone)

    intro = {
        'sw': f"✅ *Barua yako iliyokamilika, {name}:*",
        'en': f"✅ *Your completed letter, {name}:*",
    }.get(lang, f"✅ *Your completed letter:*")

    await update.message.reply_text(intro, parse_mode="Markdown")

    # Send letter in chunks to avoid Telegram 4096 char limit
    MAX_CHUNK = 3800
    for i in range(0, len(filled), MAX_CHUNK):
        await update.message.reply_text(
            f"```\n{filled[i:i+MAX_CHUNK]}\n```",
            parse_mode="Markdown"
        )

    tip = {
        'sw': (
            "💡 *Vidokezo:*\n"
            "• Badilisha \[Anwani yako\] na anwani yako halisi\n"
            "• Tuma kwa barua pepe, WhatsApp, au mkono\n"
            "• Hifadhi nakala moja kwako\n\n"
            "❓ Una swali lingine?"
        ),
        'en': (
            "💡 *Tips:*\n"
            "• Replace \[Your address\] with your actual address\n"
            "• Send by email, WhatsApp, or hand-deliver with a witness\n"
            "• Keep a copy for yourself\n\n"
            "❓ Have another question?"
        ),
    }.get(lang, "❓ Have another question?")
    await update.message.reply_text(tip, parse_mode="Markdown", reply_markup=_main_keyboard(lang))
    return ANSWERING


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User wants to end the conversation."""
    user = await _get_user(update.effective_user.id)
    lang = user.lang

    # Clear any pending letter data
    context.user_data.clear()

    msg = {
        'sw': (
            "👋 *Kwaheri!*\n\n"
            "Natumai nimekusaidia. Ukihitaji msaada wa kisheria tena, "
            "andika /start wakati wowote.\n\n"
            "HakiMkononi iko hapa kila wakati. 🇰🇪"
        ),
        'en': (
            "👋 *Goodbye!*\n\n"
            "Hope I was useful. Whenever you need legal help again, "
            "just type /start.\n\n"
            "HakiMkononi is here whenever you need it. 🇰🇪"
        ),
    }.get(lang, "👋 Goodbye! Type /start to chat again anytime.")

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clear conversation history and start fresh — user keeps their language preference."""
    user = await _get_user(update.effective_user.id)
    lang = user.lang

    # Clear all pending data (letter, phone, name)
    context.user_data.clear()

    # Reset conversation state to active but keep language preference
    await _set_user_state(user, WhatsAppUser.STATE_ACTIVE)

    msg = {
        'sw': (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🗑️ *Mazungumzo yamefutwa*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Anza upya. Niambie tatizo lako jipya la kisheria.\n\n"
            "_Lugha yako bado ni Kiswahili._\n"
            "_Andika /language kubadilisha._"
        ),
        'en': (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🗑️ *Chat cleared*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Starting fresh. Tell me your new legal problem.\n\n"
            "_Your language is still English._\n"
            "_Type /language to change it._"
        ),
    }.get(lang, (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🗑️ *Chat cleared*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Starting fresh. Tell me your new legal problem."
    ))

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ANSWERING


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User skipped name or phone step — send letter with remaining placeholders."""
    lang         = context.user_data.get('letter_lang', 'en')
    name         = context.user_data.get('letter_name', '')
    template     = context.user_data.get('pending_letter', '')

    for k in ('pending_letter', 'letter_lang', 'letter_name'):
        context.user_data.pop(k, None)

    if template:
        # Fill what we have, leave the rest as placeholders
        filled = _fill_letter(template, name or '[YOUR NAME]', '')
        await update.message.reply_text(
            '📄 ' + ('Barua yenye nafasi zilizobaki:' if lang == 'sw' else 'Letter with remaining placeholders:'),
            parse_mode="Markdown"
        )
        for i in range(0, len(filled), 3800):
            await update.message.reply_text(f"```\n{filled[i:i+3800]}\n```", parse_mode="Markdown")

    msg = {
        'sw': '👍 Badilisha nafasi zilizobaki mwenyewe.\n\n❓ Una swali lingine?',
        'en': '👍 Fill in the remaining placeholders yourself.\n\n❓ Have another question?',
    }.get(lang, '❓ Have another question?')
    await update.message.reply_text(msg, parse_mode="Markdown")
    return ANSWERING


# ── Main ──────────────────────────────────────────────────────────────────────

def _build_app(token: str):
    """
    Build the Application with ConversationHandler.
    Entry points always route to cmd_start so new users always get
    language selection — regardless of their DB state.
    """
    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CommandHandler("clear", cmd_clear),   # works even after /stop ends the conversation
            # Any first message without /start → handle_question checks STATE_NEW
            # and shows the welcome/language picker itself
            MessageHandler(filters.VOICE | filters.AUDIO, handle_voice),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question),
        ],
        states={
            CHOOSING_LANG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_language_choice),
            ],
            ANSWERING: [
                CommandHandler("language", cmd_language),
                CommandHandler("help",     cmd_help),
                CommandHandler("stop",     cmd_stop),
                CommandHandler("clear",    cmd_clear),
                MessageHandler(filters.VOICE | filters.AUDIO, handle_voice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question),
            ],
            FILLING_LETTER: [
                CommandHandler("skip",     cmd_skip),
                CommandHandler("stop",     cmd_stop),
                CommandHandler("clear",    cmd_clear),
                CommandHandler("language", cmd_language),
                CommandHandler("start",    cmd_start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_letter_name),
            ],
            FILLING_PHONE: [
                CommandHandler("skip",     cmd_skip),
                CommandHandler("stop",     cmd_stop),
                CommandHandler("clear",    cmd_clear),
                CommandHandler("language", cmd_language),
                CommandHandler("start",    cmd_start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_letter_phone),
            ],
        },
        fallbacks=[
            CommandHandler("start",    cmd_start),
            CommandHandler("language", cmd_language),
            CommandHandler("help",     cmd_help),
            CommandHandler("skip",     cmd_skip),
            CommandHandler("stop",     cmd_stop),
            CommandHandler("clear",    cmd_clear),
        ],
        per_user=True,
        per_chat=True,
    )
    app.add_handler(conv)
    return app


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "your-token-here":
        print("ERROR: Set TELEGRAM_BOT_TOKEN in .env")
        return

    app = _build_app(token)

    print("[TelegramBot] ✅ Bot is ONLINE — polling Telegram servers...")
    logger.info("[TelegramBot] ✅ Bot is ONLINE — polling Telegram servers...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    logger.info("[TelegramBot] ⛔ Bot polling stopped.")


async def _run_polling_async(token: str):
    """
    Runs the bot without signal handlers — safe to call from a background thread.
    run_polling() registers OS signals which only works in the main thread.
    """
    import asyncio

    app = _build_app(token)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,   # drop stale updates from previous session on restart
    )

    logger.info("[TelegramBot] ✅ Bot is ONLINE — polling Telegram servers...")
    print("[TelegramBot] ✅ Bot is ONLINE — polling Telegram servers...")

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("[TelegramBot] ⛔ Bot stopped.")


def run_bot_in_thread():
    """
    Start the Telegram bot in a background daemon thread.
    Uses _run_polling_async() instead of run_polling() to avoid the
    'set_wakeup_fd only works in main thread' error.
    """
    import threading
    import asyncio

    def _run():
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token or token == "your-token-here":
            print("[TelegramBot] TELEGRAM_BOT_TOKEN not set — bot disabled.")
            return
        retry = 0
        while True:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                logger.info(f"[TelegramBot] Starting polling (attempt {retry + 1})...")
                loop.run_until_complete(_run_polling_async(token))
                break  # clean exit
            except Exception as e:
                err = str(e)
                if "Conflict" in err:
                    retry += 1
                    wait = min(30 * retry, 120)  # 30s, 60s, 90s, then cap at 120s
                    logger.warning(f"[TelegramBot] Conflict — waiting {wait}s before retry...")
                    import time; time.sleep(wait)
                else:
                    logger.error(f"[TelegramBot] Crashed: {e}", exc_info=True)
                    break

    t = threading.Thread(target=_run, daemon=True, name="telegram-bot")
    t.start()
    print("[TelegramBot] Background thread launched.")


if __name__ == "__main__":
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sheria_ai.settings")
    django.setup()
    main()
