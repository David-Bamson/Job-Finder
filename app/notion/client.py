"""Wrapper around the official Notion client for logging jobs and
reading/writing the trusted company list.

Uses Notion's data-source API (a database can have multiple data
sources; the database id from .env is resolved to its data source id
once and cached).
"""

from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from notion_client import Client

from app.config import (
    NOTION_API_KEY,
    NOTION_JOBS_DATABASE_ID,
    NOTION_TRUSTED_COMPANIES_DATABASE_ID,
)
from app.models import Job, JobStatus, TrustTier

_client: Client | None = None
_data_source_id_cache: dict[str, str] = {}


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(auth=NOTION_API_KEY)
    return _client


def _get_data_source_id(database_id: str) -> str:
    if database_id not in _data_source_id_cache:
        db = _get_client().databases.retrieve(database_id=database_id)
        _data_source_id_cache[database_id] = db["data_sources"][0]["id"]
    return _data_source_id_cache[database_id]


def _title_prop(text: str | None) -> dict:
    return {"title": [{"text": {"content": (text or "")[:2000]}}]}


def _rich_text_prop(text: str | None) -> dict:
    return {"rich_text": [{"text": {"content": (text or "")[:2000]}}] if text else []}


def _select_prop(value: str | None) -> dict:
    return {"select": {"name": value} if value else None}


def _number_prop(value: float | None) -> dict:
    return {"number": value}


def _url_prop(value: str | None) -> dict:
    return {"url": value or None}


def _date_prop(iso_date: str | None) -> dict:
    return {"date": {"start": iso_date} if iso_date else None}


def _extract_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"//{url}")
    domain = (parsed.netloc or parsed.path).lower().split(":")[0]
    return domain[4:] if domain.startswith("www.") else domain


def log_job(job: Job) -> str:
    """Create a row in the jobs database with the fields from the plan:
    title, company, source/trust tier, date found, legitimacy score and
    reasons, fit score, status, apply link, pay, notes, and follow up
    date. Returns the created page id, also stored on job.notion_page_id.
    """
    properties = {
        "Title": _title_prop(job.title),
        "Company": _rich_text_prop(job.company),
        "Source": _select_prop(job.source),
        "Trust Tier": _select_prop(job.trust_tier.value.replace("_", " ").capitalize()),
        "Date Found": _date_prop(job.date_found.isoformat()),
        "Status": _select_prop(job.status.value.capitalize()),
        "Apply Link": _url_prop(job.apply_url),
        "Pay": _rich_text_prop(job.pay),
        "Notes": _rich_text_prop(job.notes),
        "Location": _rich_text_prop(job.location),
        "Description": _rich_text_prop(job.description),
        "Follow-up Date": _date_prop(job.follow_up_date.isoformat() if job.follow_up_date else None),
    }
    if job.legitimacy_score is not None:
        properties["Legitimacy Score"] = _number_prop(job.legitimacy_score)
    if job.legitimacy_reasons:
        properties["Legitimacy Reasons"] = _rich_text_prop(
            "\n".join(f"- {reason}" for reason in job.legitimacy_reasons)
        )
    if job.fit_score is not None:
        properties["Fit Score"] = _number_prop(job.fit_score)

    page = _get_client().pages.create(
        parent={"type": "data_source_id", "data_source_id": _get_data_source_id(NOTION_JOBS_DATABASE_ID)},
        properties=properties,
    )
    job.notion_page_id = page["id"]
    return page["id"]


def update_status_by_page_id(page_id: str, status: JobStatus) -> None:
    """Update the Status field of a job row by its Notion page id. Used
    by the Telegram callback handlers, which only have the page id from
    a button's callback_data, not a full Job object.
    """
    _get_client().pages.update(
        page_id=page_id,
        properties={"Status": _select_prop(status.value.capitalize())},
    )


def update_job_status(job: Job) -> None:
    """Update the status field (new/reviewed/approved/applied/interview/
    offer/rejected) for an existing job row.
    """
    if not job.notion_page_id:
        raise ValueError("Job has no notion_page_id; call log_job() first.")
    update_status_by_page_id(job.notion_page_id, job.status)


def get_weekly_stats() -> dict:
    """Return counts of jobs found, sent to you, auto rejected, and
    applied to over the last 7 days, for the Telegram /stats command.
    """
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    data_source_id = _get_data_source_id(NOTION_JOBS_DATABASE_ID)

    found = 0
    hard_failed = 0
    applied = 0
    cursor = None
    while True:
        response = _get_client().data_sources.query(
            data_source_id=data_source_id,
            filter={"property": "Date Found", "date": {"on_or_after": since}},
            start_cursor=cursor,
        )
        for page in response["results"]:
            found += 1
            reasons_prop = page["properties"].get("Legitimacy Reasons", {}).get("rich_text", [])
            reasons_text = "".join(part.get("plain_text", "") for part in reasons_prop)
            if "Hard fail" in reasons_text:
                hard_failed += 1
            status_prop = page["properties"].get("Status", {}).get("select")
            if status_prop and status_prop.get("name") == JobStatus.APPLIED.value.capitalize():
                applied += 1
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return {
        "found": found,
        "sent": found - hard_failed,
        "auto_rejected": hard_failed,
        "applied": applied,
    }


def get_recent_hard_failed_jobs(days: int = 7) -> list[Job]:
    """Return minimal Job objects for postings hard-failed (auto
    rejected) within the last N days, for the weekly Telegram summary.
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    data_source_id = _get_data_source_id(NOTION_JOBS_DATABASE_ID)

    jobs = []
    cursor = None
    while True:
        response = _get_client().data_sources.query(
            data_source_id=data_source_id,
            filter={
                "and": [
                    {"property": "Date Found", "date": {"on_or_after": since}},
                    {"property": "Legitimacy Reasons", "rich_text": {"contains": "Hard fail"}},
                ]
            },
            start_cursor=cursor,
        )
        for page in response["results"]:
            props = page["properties"]
            title_parts = props.get("Title", {}).get("title", [])
            title = title_parts[0]["plain_text"] if title_parts else ""
            company = "".join(part.get("plain_text", "") for part in props.get("Company", {}).get("rich_text", []))
            reasons_text = "".join(
                part.get("plain_text", "") for part in props.get("Legitimacy Reasons", {}).get("rich_text", [])
            )
            jobs.append(
                Job(
                    title=title,
                    company=company,
                    apply_url=props.get("Apply Link", {}).get("url") or "",
                    source="notion",
                    trust_tier=TrustTier.TIER_THREE,
                    legitimacy_reasons=[reasons_text] if reasons_text else [],
                    hard_failed=True,
                )
            )
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return jobs


def _plain_text(rich_text_list) -> str:
    return "".join(part.get("plain_text", "") for part in (rich_text_list or []))


def _parse_job_page(page: dict) -> dict:
    """Flatten a Notion page object into a plain dict for the web
    dashboard (list and detail views).
    """
    props = page["properties"]
    title_parts = props.get("Title", {}).get("title", [])
    reasons_text = _plain_text(props.get("Legitimacy Reasons", {}).get("rich_text"))
    reasons = [
        line[2:].strip() if line.startswith("- ") else line.strip()
        for line in reasons_text.split("\n")
        if line.strip()
    ]
    status_prop = props.get("Status", {}).get("select")
    source_prop = props.get("Source", {}).get("select")
    tier_prop = props.get("Trust Tier", {}).get("select")
    date_found = props.get("Date Found", {}).get("date")
    follow_up = props.get("Follow-up Date", {}).get("date")

    return {
        "page_id": page["id"],
        "title": title_parts[0]["plain_text"] if title_parts else "",
        "company": _plain_text(props.get("Company", {}).get("rich_text")),
        "source": source_prop.get("name") if source_prop else None,
        "trust_tier": tier_prop.get("name") if tier_prop else None,
        "date_found": date_found.get("start") if date_found else None,
        "legitimacy_score": props.get("Legitimacy Score", {}).get("number"),
        "legitimacy_reasons": reasons,
        "fit_score": props.get("Fit Score", {}).get("number"),
        "status": status_prop.get("name") if status_prop else None,
        "apply_url": props.get("Apply Link", {}).get("url"),
        "pay": _plain_text(props.get("Pay", {}).get("rich_text")),
        "notes": _plain_text(props.get("Notes", {}).get("rich_text")),
        "location": _plain_text(props.get("Location", {}).get("rich_text")),
        "description": _plain_text(props.get("Description", {}).get("rich_text")),
        "follow_up_date": follow_up.get("start") if follow_up else None,
    }


def get_all_jobs(status: str | None = None, source: str | None = None, limit: int = 200) -> list[dict]:
    """Return jobs from the log as plain dicts, newest first, for the
    web dashboard. Optionally filter by Status and/or Source.
    """
    data_source_id = _get_data_source_id(NOTION_JOBS_DATABASE_ID)
    filters = []
    if status:
        filters.append({"property": "Status", "select": {"equals": status}})
    if source:
        filters.append({"property": "Source", "select": {"equals": source}})

    query: dict = {
        "data_source_id": data_source_id,
        "sorts": [{"property": "Date Found", "direction": "descending"}],
    }
    if len(filters) == 1:
        query["filter"] = filters[0]
    elif len(filters) > 1:
        query["filter"] = {"and": filters}

    jobs = []
    cursor = None
    while len(jobs) < limit:
        if cursor:
            query["start_cursor"] = cursor
        response = _get_client().data_sources.query(**query)
        jobs.extend(_parse_job_page(page) for page in response["results"])
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return jobs[:limit]


def get_job_by_page_id(page_id: str) -> dict | None:
    """Return a single job as a plain dict, for the web dashboard's
    detail page. Returns None if the page doesn't exist or is archived.
    """
    try:
        page = _get_client().pages.retrieve(page_id=page_id)
    except Exception:
        return None
    if page.get("archived"):
        return None
    return _parse_job_page(page)


def get_trusted_domains() -> list[str]:
    """Return every domain currently on the trusted company list."""
    data_source_id = _get_data_source_id(NOTION_TRUSTED_COMPANIES_DATABASE_ID)
    domains = []
    cursor = None
    while True:
        response = _get_client().data_sources.query(data_source_id=data_source_id, start_cursor=cursor)
        for page in response["results"]:
            url_value = page["properties"].get("Domain", {}).get("url")
            if url_value:
                domains.append(_extract_domain(url_value))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return domains


def add_trusted_company(domain: str, company_name: str) -> None:
    """Add a manually verified company to the trusted company list."""
    _get_client().pages.create(
        parent={
            "type": "data_source_id",
            "data_source_id": _get_data_source_id(NOTION_TRUSTED_COMPANIES_DATABASE_ID),
        },
        properties={
            "Company Name": _title_prop(company_name),
            "Domain": _url_prop(f"https://{domain}" if "://" not in domain else domain),
            "Date Verified": _date_prop(date.today().isoformat()),
        },
    )
