"""Telegram bot: sends job alerts with Approve / Skip / Needs manual
review buttons, the weekly summary, and the /stats command. Hard failed
jobs are never sent here, only logged to Notion.
"""

import asyncio

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.config import POLL_INTERVAL_HOURS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.discovery.pipeline import discover_all
from app.grading.pipeline import grade_all
from app.models import Job, JobStatus
from app.notion.client import (
    get_recent_hard_failed_jobs,
    get_weekly_stats,
    log_job,
    update_status_by_page_id,
)
from app.telegram.messages import format_job_alert, format_stats, format_weekly_summary

CALLBACK_ACTIONS = {
    "approve": JobStatus.APPROVED,
    "skip": JobStatus.REJECTED,
    "review": JobStatus.REVIEWED,
}


def _build_keyboard(page_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve and apply", callback_data=f"approve:{page_id}"),
                InlineKeyboardButton("Skip", callback_data=f"skip:{page_id}"),
            ],
            [InlineKeyboardButton("Needs manual review", callback_data=f"review:{page_id}")],
        ]
    )


def send_job_alert(job: Job) -> None:
    """Send a single job alert with inline Approve/Skip/Manual review
    buttons. job must already be logged to Notion (job.notion_page_id
    set) since the buttons update that row by page id.
    """
    if not job.notion_page_id:
        raise ValueError("Job must be logged to Notion before alerting (job.notion_page_id is not set).")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    asyncio.run(
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=format_job_alert(job),
            reply_markup=_build_keyboard(job.notion_page_id),
        )
    )


def send_weekly_summary(rejected_jobs: list[Job]) -> None:
    """Send the weekly digest of auto-rejected jobs."""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    asyncio.run(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=format_weekly_summary(rejected_jobs)))


def handle_stats_command() -> str:
    """Build the response text for the /stats command: jobs found, sent,
    auto rejected, and applied to for the current week.
    """
    return format_stats(get_weekly_stats())


async def _stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(handle_stats_command())


async def _button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, _, page_id = query.data.partition(":")
    status = CALLBACK_ACTIONS.get(action)
    if status is None or not page_id:
        return

    update_status_by_page_id(page_id, status)
    await query.edit_message_text(text=f"{query.message.text}\n\n-> Marked: {status.value}")


async def _discover_and_alert(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job: discover -> grade -> log -> alert.

    Every non-duplicate job gets logged to Notion regardless of fit, so
    the full record stays intact. Only jobs that passed the full
    legitimacy check (i.e. cleared the fit threshold, or were already
    trusted) actually get pushed to Telegram — jobs whose fit score was
    too low to warrant a check have legitimacy_score=None and stay
    logged-but-quiet, same as hard fails, to keep alert volume relevant.
    """
    jobs = discover_all()
    graded = grade_all(jobs)
    for job in graded:
        log_job(job)
        if not job.hard_failed and job.legitimacy_score is not None:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=format_job_alert(job),
                reply_markup=_build_keyboard(job.notion_page_id),
            )


async def _weekly_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    rejected_jobs = get_recent_hard_failed_jobs(days=7)
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=format_weekly_summary(rejected_jobs))


def run() -> None:
    """Start the bot: registers /stats and the approve/skip/review button
    handler, schedules the discover -> grade -> alert -> log cycle every
    POLL_INTERVAL_HOURS and the weekly summary every 7 days, then starts
    polling for updates. Blocks until interrupted.
    """
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("stats", _stats_command))
    application.add_handler(CallbackQueryHandler(_button_callback))
    application.job_queue.run_repeating(_discover_and_alert, interval=POLL_INTERVAL_HOURS * 3600, first=0)
    application.job_queue.run_repeating(_weekly_summary_job, interval=7 * 24 * 3600, first=7 * 24 * 3600)
    application.run_polling()
