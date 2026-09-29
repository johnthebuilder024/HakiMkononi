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
CHOOSING_LANG = 1
ANSWERING     = 2


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
                MessageHandler(filters.VOICE | filters.AUDIO, handle_voice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question),
            ],
        },
        fallbacks=[
            CommandHandler("start",    cmd_start),
            CommandHandler("language", cmd_language),
            CommandHandler("help",     cmd_help),
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
    app.run_polling(allowed_updates=Update.ALL_TYPES)
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
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

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
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger.info("[TelegramBot] Starting polling thread...")
            loop.run_until_complete(_run_polling_async(token))
        except Exception as e:
            logger.error(f"[TelegramBot] Crashed: {e}", exc_info=True)

    t = threading.Thread(target=_run, daemon=True, name="telegram-bot")
    t.start()
    print("[TelegramBot] Background thread launched.")

    t = threading.Thread(target=_run, daemon=True, name="telegram-bot")
    t.start()
    print("[TelegramBot] Background thread launched.")


if __name__ == "__main__":
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sheria_ai.settings")
    django.setup()
    main()
