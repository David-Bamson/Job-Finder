"""Entry point. Starts the Telegram bot, which schedules the
discover -> grade -> log -> alert cycle and the weekly summary via its
own job queue, and listens for /stats and the approve/skip/review
buttons. Blocks until interrupted (Ctrl+C).
"""

from app.telegram.bot import run

if __name__ == "__main__":
    run()
