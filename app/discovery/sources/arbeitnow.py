"""Arbeitnow public API. Tier one source, remote focused."""

import requests
from bs4 import BeautifulSoup

from app.config import ARBEITNOW_API_URL
from app.models import Job, TrustTier

HEADERS = {"User-Agent": "Mozilla/5.0 (job-search-automation)"}


def fetch_jobs() -> list[Job]:
    """Pull current listings from the Arbeitnow API and return them as Job objects."""
    response = requests.get(ARBEITNOW_API_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    listings = response.json().get("data", [])

    jobs = []
    for entry in listings:
        jobs.append(
            Job(
                title=entry.get("title", ""),
                company=entry.get("company_name", ""),
                apply_url=entry.get("url", ""),
                source="arbeitnow",
                trust_tier=TrustTier.TIER_ONE,
                location="Remote" if entry.get("remote") else entry.get("location") or None,
                description=BeautifulSoup(entry.get("description") or "", "lxml").get_text(
                    separator=" ", strip=True
                ),
            )
        )
    return jobs
