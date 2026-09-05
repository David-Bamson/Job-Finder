"""WeWorkRemotely RSS feed. Tier one source, no scraping needed."""

import feedparser
from bs4 import BeautifulSoup

from app.config import WEWORKREMOTELY_RSS_URL
from app.models import Job, TrustTier


def fetch_jobs() -> list[Job]:
    """Parse the WeWorkRemotely RSS feed and return listings as Job objects."""
    feed = feedparser.parse(WEWORKREMOTELY_RSS_URL)

    jobs = []
    for entry in feed.entries:
        # titles are formatted "Company: Position"
        if ":" in entry.title:
            company, title = entry.title.split(":", 1)
            company, title = company.strip(), title.strip()
        else:
            company, title = "", entry.title.strip()

        jobs.append(
            Job(
                title=title,
                company=company,
                apply_url=entry.link,
                source="weworkremotely",
                trust_tier=TrustTier.TIER_ONE,
                location=entry.get("region") or "Remote",
                description=BeautifulSoup(
                    entry.get("summary") or entry.get("description") or "", "lxml"
                ).get_text(separator=" ", strip=True),
            )
        )
    return jobs
