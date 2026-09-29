import os
import tempfile
from django.apps import AppConfig


class CasesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cases'

    def ready(self):
        # Skip during dev server child process
        if os.environ.get('RUN_MAIN') == 'true':
            return

        # Skip if no token configured
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        if not token:
            print("[TelegramBot] No TELEGRAM_BOT_TOKEN — skipping bot startup.")
            return

        # OS-level lock file — only the first process that creates it
        # starts the bot. Works across gunicorn master+worker forks.
        lock_file = os.path.join(tempfile.gettempdir(), 'hakimkononi_bot.lock')
        try:
            # Exclusive creation — fails if file already exists
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
        except FileExistsError:
            # Another process already started the bot
            print(f"[TelegramBot] Lock exists — bot already running in another process.")
            return

        try:
            from telegram_bot import run_bot_in_thread
            run_bot_in_thread()
        except Exception as e:
            # Remove lock on failure so next restart can try again
            try:
                os.remove(lock_file)
            except OSError:
                pass
            print(f"[TelegramBot] Failed to start: {e}")
