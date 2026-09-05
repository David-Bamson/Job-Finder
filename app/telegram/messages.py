"""Formats Job objects into the plain-language Telegram alert text and
the weekly auto-rejected summary described in the plan.
"""

from app.models import Job

# Exact substrings used by app.grading.legitimacy's reason strings that
# indicate a positive signal, used to split reasons into "why it scored
# well" vs "something to note" for the alert message.
POSITIVE_MARKERS = [
    "sits on the company's own domain",
    "appears in general search results",
    "found independent reviews",
    "independent sites with matching details",
    "shows standard accountability pages",
    "is on the trusted company list",
    "warn that scammers impersonate",
]


def _split_reasons(reasons: list[str]) -> tuple[list[str], list[str]]:
    positives, negatives = [], []
    for reason in reasons:
        lower = reason.lower()
        (positives if any(marker in lower for marker in POSITIVE_MARKERS) else negatives).append(reason)
    return positives, negatives


def format_job_alert(job: Job) -> str:
    """Build the message text for a single job alert (title, company,
    legitimacy score, fit score, pay, location, source, why it scored
    well, and anything to note).
    """
    legitimacy_line = (
        f"{job.legitimacy_score} out of 100"
        if job.legitimacy_score is not None
        else "not verified (fit score too low, full check skipped)"
    )
    fit_line = f"{job.fit_score} out of 100" if job.fit_score is not None else "not scored"

    positives, negatives = _split_reasons(job.legitimacy_reasons)
    if job.notes:
        negatives.append(job.notes)

    lines = [
        "🆕 New job found!",
        "",
        f"📌 Title: {job.title}",
        "",
        f"🏢 Company: {job.company}",
        "",
        f"✅ Legitimacy score: {legitimacy_line}",
        "",
        f"🎯 Fit score: {fit_line}",
        "",
        f"💰 Pay: {job.pay or 'Not stated'}",
        "",
        f"📍 Location: {job.location or 'Not stated'}",
        "",
        f"🌐 Source: {job.source} ({job.trust_tier.value.replace('_', ' ')})",
    ]
    if positives:
        lines += ["", f"👍 Why it scored well: {'; '.join(positives)}"]
    if negatives:
        lines += ["", f"⚠️ Something to note: {'; '.join(negatives)}"]
    lines += ["", f"🔗 Apply link: {job.apply_url}"]
    return "\n".join(lines)


def format_weekly_summary(rejected_jobs: list[Job]) -> str:
    """Build the weekly digest of everything auto rejected, so the user
    can spot check that the system isn't over filtering.
    """
    if not rejected_jobs:
        return "📋 Weekly summary\n\nNo jobs were auto rejected this week. 🎉"

    lines = [f"📋 Weekly summary: {len(rejected_jobs)} job(s) auto rejected this week.", ""]
    for job in rejected_jobs:
        reason = job.legitimacy_reasons[0] if job.legitimacy_reasons else "No reason recorded."
        lines += [f"🚫 {job.title} at {job.company}: {reason}", ""]
    return "\n".join(lines).rstrip()


def format_stats(stats: dict) -> str:
    """Build the response for the /stats command: jobs found, sent,
    auto rejected, and applied to for the current week.
    """
    return (
        "📊 Stats for the last 7 days\n\n"
        f"🔎 Jobs found: {stats.get('found', 0)}\n\n"
        f"📨 Sent to you: {stats.get('sent', 0)}\n\n"
        f"🚫 Auto rejected: {stats.get('auto_rejected', 0)}\n\n"
        f"✅ Applied to: {stats.get('applied', 0)}"
    )
