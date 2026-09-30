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


def _lang_keyboard():
    return ReplyKeyboardMarkup(
        [["1️⃣ Kiswahili", "2️⃣ English"]],
        one_time_keyboard=True,
        resize_keyboard=True,
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

    def clean(text):
        if not text: return ''
        # Convert **bold** → *bold* for Telegram
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        text = re.sub(r'__(.+?)__',      r'*\1*', text)
        # Remove markdown headings and blockquotes
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^>\s?',  '', text, flags=re.MULTILINE)
        return text.strip()

    parts = []
    if answer.get('law'):
        parts.append(f"{L['law']}\n{clean(answer['law'])}")
    if answer.get('simple'):
        parts.append(f"{L['simple']}\n{clean(answer['simple'])}")
    if answer.get('loophole'):
        parts.append(f"{L['rights']}\n{clean(answer['loophole'])}")
    if answer.get('letter'):
        letter = answer['letter'][:1500]
        parts.append(f"{L['letter']}\n```\n{letter}\n```")
    if top_laws:
        src = '\n'.join(f"  {i+1}. {l.title} — {l.section}" for i, l in enumerate(top_laws[:4]))
        parts.append(f"📚 *Sources*\n{src}")

    disclaimer = {
        'sw':    '⚠️ _Taarifa ya kisheria tu — si ushauri wa kisheria._',
        'en':    '⚠️ _Legal information only — not legal advice._',
    }.get(lang, '')
    parts.append(disclaimer)

    return '\n\n'.join(p for p in parts if p)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _get_user(update.effective_user.id)
    await _set_user_state(user, WhatsAppUser.STATE_NEW)
    tg_user = update.effective_user
    logger.info(f"[TelegramBot] /start — user {tg_user.id} (@{tg_user.username})")

    await update.message.reply_text(
        "👋 *Karibu HakiMkononi!*\n\n"
        "Mimi ni AI inayokusaidia kuelewa sheria ya Kenya *bila malipo*.\n\n"
        "Chagua lugha yako / Choose your language:\n\n"
        "1️⃣  Kiswahili\n"
        "2️⃣  English\n\n"
        "Bonyeza chaguo lako / Tap your choice below:",
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
            "Niambie tatizo lako la kisheria kwa sentensi 1-2.\n\n"
            "*Mifano:*\n"
            "• Nilifukuzwa kazi bila notisi\n"
            "• Landlord alinifunga nje bila notisi\n"
            "• Polisi walinishika bila warrant\n"
            "• Mke wangu anaficha mali yetu\n\n"
            "📌 *Amri:*\n"
            "/language — Badilisha lugha\n"
            "/start — Anza upya\n"
            "/stop — Maliza mazungumzo\n"
            "/help — Msaada huu"
        ),
        'en': (
            "⚖️ *HakiMkononi — Help*\n\n"
            "Tell me your legal problem in 1-2 sentences.\n\n"
            "*Examples:*\n"
            "• My employer fired me without notice\n"
            "• My landlord locked me out without notice\n"
            "• Police arrested me without a warrant\n"
            "• My spouse is hiding our shared property\n\n"
            "📌 *Commands:*\n"
            "/language — Change language\n"
            "/start — Start over\n"
            "/stop — End this conversation\n"
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
            data = {'model': 'whisper-large-v3', 'response_format': 'json', 'temperature': '0'}
            if whisper_lang:
                data['language'] = whisper_lang
            r = _req.post(
                'https://api.groq.com/openai/v1/audio/transcriptions',
                headers={'Authorization': f'Bearer {groq_key}'},
                files={'file': ('voice.ogg', file_bytes, 'audio/ogg')},
                data=data,
                timeout=30,
            )
            return r.json().get('text', '').strip() if r.status_code == 200 else ''

        transcript = await do_transcribe()

        if not transcript:
            await ack_msg.edit_text(
                '❌ ' + ('Sikuweza kuelewa sauti yako. Jaribu tena au andika.' if lang == 'sw'
                          else 'Could not understand the audio. Please try again or type.')
            )
            return ANSWERING

        # Show what was heard then process
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
            top_laws   = find_relevant_laws(transcript, top_n=6, category_boost=['constitution'])
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

        await update.message.reply_text(
            '❓ Una swali lingine? Andika au tuma sauti.' if lang == 'sw'
            else '❓ Another question? Type or send a voice message.'
        )

    except Exception as e:
        logger.error(f"Voice handler error: {e}", exc_info=True)
        try:
            await ack_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(
            '❌ Samahani, kuna tatizo. Jaribu tena.' if lang == 'sw'
            else '❌ Sorry, an error occurred. Please try again.'
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
            "_Mfano: Nilifukuzwa kazi bila notisi._\n\n"
            "Unaweza andika kwa Kiswahili, Kingereza, au mchanganyiko — ninaelewa vyote.\n"
            "Andika /language kubadilisha lugha wakati wowote."
        ),
        'en': (
            f"✅ Great! Language: *{name}*\n\n"
            "Now tell me your legal problem.\n\n"
            "_Example: My employer fired me without notice._\n\n"
            "You can write in English, Swahili, or a mix — I understand all.\n"
            "Type /language to change language at any time."
        ),
    }[chosen]

    await update.message.reply_text(
        confirm,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
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

    # Serious case
    if is_serious_criminal(message):
        serious = {
            'sw': "🚨 *Kesi Nyeti*\n\nKesi hii inahitaji wakili haraka.\n\n*NLAS (Bure):* 0800 720 120\nwww.nlas.go.ke",
            'en': "🚨 *Serious Case*\n\nThis needs a lawyer urgently.\n\n*NLAS (Free):* 0800 720 120\nwww.nlas.go.ke",
        }.get(lang, "🚨 *Serious Case*\n\nContact NLAS: 0800 720 120")
        await update.message.reply_text(serious, parse_mode="Markdown")
        return ANSWERING

    # Send instant "thinking" message
    ack = {
        'sw': '⏳ Inasoma sheria yako... jibu linakuja sekunde 15-20.',
        'en': '⏳ Reading the law for you... reply in 15-20 seconds.',
    }.get(lang, '⏳ Processing...')

    thinking = await update.message.reply_text(ack)

    try:
        @sync_to_async(thread_sensitive=False)
        def run_ai():
            top_laws = find_relevant_laws(message, top_n=6, category_boost=['constitution'])
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
            'sw': '❓ Una swali lingine? Andika hapa.',
            'en': '❓ Have another question? Just type it.',
        }.get(reply_lang, '❓ Any other question? Just type it.')
        await update.message.reply_text(followup)

    except Exception as e:
        logger.error(f"Answer error: {e}", exc_info=True)
        try:
            await thinking.delete()
        except Exception:
            pass
        err = {
            'sw': '❌ Samahani, kuna tatizo la kiufundi. Tafadhali jaribu tena.',
            'en': '❌ Sorry, a technical error occurred. Please try again.',
        }.get(lang, '❌ Sorry, please try again.')
        await update.message.reply_text(err)

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
    """User replied with phone — fill and send the complete letter."""
    phone = update.message.text.strip()
    lang  = context.user_data.get('letter_lang', 'en')
    name  = context.user_data.get('letter_name', '')
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
            "❓ Una swali lingine? Andika hapa."
        ),
        'en': (
            "💡 *Tips:*\n"
            "• Replace \[Your address\] with your actual address\n"
            "• Send by email, WhatsApp, or hand-deliver with a witness\n"
            "• Keep a copy for yourself\n\n"
            "❓ Have another question? Just type it."
        ),
    }.get(lang, "❓ Have another question? Just type it.")
    await update.message.reply_text(tip, parse_mode="Markdown")
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
            "Nimefurahi kukusaidia leo. Ukihitaji msaada wa kisheria tena, "
            "andika /start wakati wowote.\n\n"
            "HakiMkononi iko hapa kila wakati. 🇰🇪"
        ),
        'en': (
            "👋 *Goodbye!*\n\n"
            "Happy to have helped you today. Whenever you need legal help again, "
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
                MessageHandler(filters.VOICE | filters.AUDIO, handle_voice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question),
            ],
            FILLING_LETTER: [
                CommandHandler("skip",     cmd_skip),
                CommandHandler("stop",     cmd_stop),
                CommandHandler("language", cmd_language),
                CommandHandler("start",    cmd_start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_letter_name),
            ],
            FILLING_PHONE: [
                CommandHandler("skip",     cmd_skip),
                CommandHandler("stop",     cmd_stop),
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
