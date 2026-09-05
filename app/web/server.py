"""Web dashboard: a live, read/act-on view of the Notion job log,
replacing (well, supplementing) the Telegram alerts with a browsable
site. Runs alongside the bot as its own process (see run_web.bat).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.models import JobStatus
from app.notion.client import get_all_jobs, get_job_by_page_id, update_status_by_page_id

app = FastAPI(title="Vetted")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

ACTION_TO_STATUS = {
    "approve": JobStatus.APPROVED,
    "review": JobStatus.REVIEWED,
    "skip": JobStatus.REJECTED,
}

EMPTY_STATS = {"found": 0, "sent": 0, "auto_rejected": 0, "applied": 0}


def _status_class(status: str | None) -> str:
    if status in ("Approved", "Applied", "Interview", "Offer"):
        return "verify"
    if status == "Rejected":
        return "alert"
    if status == "Reviewed":
        return "fit"
    return "muted"


def _compute_stats(all_jobs: list[dict]) -> dict:
    """Derive the same counts as get_weekly_stats(), but from a list
    already fetched for this request instead of a second full Notion
    scan - list_view already has everything it needs in hand.
    """
    since = datetime.now(timezone.utc) - timedelta(days=7)
    found = hard_failed = applied = 0
    for job in all_jobs:
        date_found = job.get("date_found")
        if not date_found:
            continue
        try:
            found_dt = datetime.fromisoformat(date_found.replace("Z", "+00:00"))
        except ValueError:
            continue
        if found_dt < since:
            continue
        found += 1
        if "Hard fail" in " ".join(job.get("legitimacy_reasons") or []):
            hard_failed += 1
        if job.get("status") == "Applied":
            applied += 1
    return {"found": found, "sent": found - hard_failed, "auto_rejected": hard_failed, "applied": applied}


SORT_OPTIONS = [("date", "Newest"), ("fit", "Highest fit"), ("legit", "Highest legitimacy")]
VERIFIED_OPTIONS = ["All", "Verified", "Not verified"]


# Hard floor for "Needs your review" - not a query param, not
# adjustable via the URL. Jobs below this never appear on the main
# feed, full stop; there is no "show them anyway" escape hatch.
MIN_FIT_TO_SHOW = 65


@app.get("/")
def list_view(
    request: Request,
    status: str = "",
    source: str = "",
    verified: str = "",
    sort: str = "date",
    q: str = "",
):
    # "All" means no filter, but it can arrive literally as the string
    # "All" (e.g. from the search form's hidden fields), not just as an
    # empty query param - normalize both to the same "no filter" state.
    status = "" if status == "All" else status
    source = "" if source == "All" else source
    verified = "" if verified == "All" else verified

    all_jobs = get_all_jobs(limit=500)

    available_sources = ["All"] + sorted({j["source"] for j in all_jobs if j["source"]})
    available_statuses = ["All"] + sorted({j["status"] for j in all_jobs if j["status"]})

    jobs = all_jobs
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    if source:
        jobs = [j for j in jobs if j["source"] == source]
    if verified == "Verified":
        jobs = [j for j in jobs if j["legitimacy_score"] is not None]
    elif verified == "Not verified":
        jobs = [j for j in jobs if j["legitimacy_score"] is None]
    if q:
        q_lower = q.lower()
        jobs = [
            j
            for j in jobs
            if q_lower in (j["title"] or "").lower() or q_lower in (j["description"] or "").lower()
        ]

    if sort == "fit":
        jobs.sort(key=lambda j: j["fit_score"] or 0, reverse=True)
    elif sort == "legit":
        jobs.sort(key=lambda j: j["legitimacy_score"] if j["legitimacy_score"] is not None else -1, reverse=True)
    # "date" needs no re-sort - get_all_jobs already returns newest first

    review_jobs_all = [j for j in jobs if j["status"] == "New"]
    hidden_count = len([j for j in review_jobs_all if (j["fit_score"] or 0) < MIN_FIT_TO_SHOW])
    review_jobs = [j for j in review_jobs_all if (j["fit_score"] or 0) >= MIN_FIT_TO_SHOW]
    pipeline_jobs = [j for j in jobs if j["status"] not in ("New", "Rejected")]

    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "review_jobs": review_jobs,
            "pipeline_jobs": pipeline_jobs,
            "available_sources": available_sources,
            "available_statuses": available_statuses,
            "sort_options": SORT_OPTIONS,
            "verified_options": VERIFIED_OPTIONS,
            "current_status": status or "All",
            "current_source": source or "All",
            "current_verified": verified or "All",
            "current_sort": sort,
            "current_q": q,
            "hidden_count": hidden_count,
            "stats": _compute_stats(all_jobs),
        },
    )


@app.get("/job/{page_id}")
def detail_view(request: Request, page_id: str):
    job = get_job_by_page_id(page_id)
    if job is None:
        return templates.TemplateResponse(
            request,
            "list.html",
            {
                "review_jobs": [],
                "pipeline_jobs": [],
                "available_sources": ["All"],
                "available_statuses": ["All"],
                "sort_options": SORT_OPTIONS,
                "verified_options": VERIFIED_OPTIONS,
                "current_status": "All",
                "current_source": "All",
                "current_verified": "All",
                "current_sort": "date",
                "current_q": "",
                "hidden_count": 0,
                "stats": EMPTY_STATS,
            },
            status_code=404,
        )

    related = [j for j in get_all_jobs(limit=20) if j["page_id"] != page_id][:3]
    matched_keywords = []  # no fit criteria defined right now - see app/grading/matching.py

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "job": job,
            "status_class": _status_class(job["status"]),
            "related": related,
            "matched_keywords": matched_keywords,
        },
    )


@app.post("/job/{page_id}/action")
def job_action(page_id: str, action: str = Form(...)):
    status = ACTION_TO_STATUS.get(action)
    if status is None:
        return JSONResponse({"error": "unknown action"}, status_code=400)

    update_status_by_page_id(page_id, status)
    job = get_job_by_page_id(page_id)
    apply_url = job["apply_url"] if job else None

    return JSONResponse(
        {
            "status": status.value.capitalize(),
            "status_class": _status_class(status.value.capitalize()),
            "apply_url": apply_url,
        }
    )
