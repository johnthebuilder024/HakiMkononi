import os
from django.apps import AppConfig

_bot_started = False   # module-level guard — only ever start once per process


class CasesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cases'

    def ready(self):
        global _bot_started

        # Guard: only start once per process
        if _bot_started:
            return
        _bot_started = True

        # Skip during migrations, management commands, or dev-server child fork
        if os.environ.get('RUN_MAIN') == 'true':
            _bot_started = False   # reset so the parent process can start it
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
