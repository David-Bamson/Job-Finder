"""RemoteOK public API. Tier one source, free and reliable."""

import requests
from bs4 import BeautifulSoup

from app.config import REMOTEOK_API_URL
from app.models import Job, TrustTier

HEADERS = {"User-Agent": "Mozilla/5.0 (job-search-automation)"}


def _format_pay(entry: dict) -> str | None:
    # RemoteOK doesn't return a currency or period field, but its salary
    # figures are USD, stated annually, by platform convention
    salary_min = entry.get("salary_min") or 0
    salary_max = entry.get("salary_max") or 0
    if not salary_min and not salary_max:
        return None
    if salary_min and salary_max:
        return f"${salary_min:,} to ${salary_max:,} /year"
    return f"${salary_min or salary_max:,} /year"


def fetch_jobs() -> list[Job]:
    """Pull current listings from the RemoteOK API and return them as Job objects."""
    response = requests.get(REMOTEOK_API_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    listings = response.json()

    jobs = []
    for entry in listings:
        if "id" not in entry:
            # the first element of the response is a legal notice, not a job
            continue
        jobs.append(
            Job(
                title=entry.get("position", ""),
                company=entry.get("company", ""),
                apply_url=entry.get("apply_url") or entry.get("url", ""),
                source="remoteok",
                trust_tier=TrustTier.TIER_ONE,
                location=entry.get("location") or "Remote",
                pay=_format_pay(entry),
                description=BeautifulSoup(entry.get("description") or "", "lxml").get_text(
                    separator=" ", strip=True
                ),
            )
        )
    return jobs
