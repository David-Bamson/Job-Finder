"""Hacker News "Who is hiring" monthly thread. Scraped once a month."""

import requests
from bs4 import BeautifulSoup

from app.discovery.pay_utils import extract_salary
from app.models import Job, TrustTier

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{item_id}"


def _find_latest_thread_id() -> str | None:
    params = {"tags": "story,author_whoishiring", "query": "Who is Hiring"}
    response = requests.get(ALGOLIA_SEARCH_URL, params=params, timeout=15)
    response.raise_for_status()
    for hit in response.json().get("hits", []):
        if hit.get("title", "").startswith("Ask HN: Who is hiring?"):
            return hit["objectID"]
    return None


def _parse_comment(comment: dict) -> Job | None:
    text = comment.get("text") or ""
    if not text:
        return None

    soup = BeautifulSoup(text, "lxml")
    full_text = soup.get_text(separator="\n")
    first_line = full_text.split("\n")[0]
    parts = [p.strip() for p in first_line.split("|")]
    if len(parts) < 2:
        return None

    company, title = parts[0], parts[1]
    location = parts[2] if len(parts) > 2 else None

    link_tag = soup.find("a")
    apply_url = (
        link_tag["href"] if link_tag else f"https://news.ycombinator.com/item?id={comment['id']}"
    )

    return Job(
        title=title,
        company=company,
        apply_url=apply_url,
        source="hn_hiring",
        trust_tier=TrustTier.TIER_ONE,
        location=location,
        pay=extract_salary(first_line) or extract_salary(full_text),
        description=full_text,
    )


def fetch_jobs() -> list[Job]:
    """Scrape the current month's HN hiring thread and return listings as Job objects."""
    thread_id = _find_latest_thread_id()
    if not thread_id:
        return []

    response = requests.get(ALGOLIA_ITEM_URL.format(item_id=thread_id), timeout=30)
    response.raise_for_status()
    thread = response.json()

    jobs = []
    for comment in thread.get("children", []):
        job = _parse_comment(comment)
        if job:
            jobs.append(job)
    return jobs
