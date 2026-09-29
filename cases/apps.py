import os
from django.apps import AppConfig


class CasesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cases'

    def ready(self):
        # Only start the Telegram bot in the main process (not during
        # migrations, management commands, or Django's auto-reloader fork).
        # RUN_MAIN is set by the dev server reloader — skip the child process.
        # On Render/gunicorn, RUN_MAIN is not set so the bot always starts.
        run_main = os.environ.get('RUN_MAIN')
        if run_main == 'true':
            # Dev server child process — skip (bot already running in parent)
            return

        token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        if not token:
            print("[TelegramBot] No TELEGRAM_BOT_TOKEN — skipping bot startup.")
            return

        try:
            from telegram_bot import run_bot_in_thread
            run_bot_in_thread()
        except Exception as e:
            print(f"[TelegramBot] Failed to start: {e}")
