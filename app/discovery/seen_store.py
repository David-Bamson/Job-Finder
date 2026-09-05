"""Tracks which job postings have already been discovered, so repeated
discovery cycles only surface genuinely new listings instead of
re-alerting the same postings every run.

Backed by a local JSON file rather than a Notion query so a cycle
covering 500+ candidate jobs doesn't need 500+ round trips just to
check what's new.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.models import Job

SEEN_JOBS_PATH = Path("data/seen_jobs.json")
RETENTION_DAYS = 90


def _dedup_key(job: Job) -> str:
    return f"{job.source}:{job.apply_url}".lower()


def _load_seen() -> dict[str, str]:
    if not SEEN_JOBS_PATH.exists():
        return {}
    return json.loads(SEEN_JOBS_PATH.read_text(encoding="utf-8"))


def _save_seen(seen: dict[str, str]) -> None:
    SEEN_JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_JOBS_PATH.write_text(json.dumps(seen), encoding="utf-8")


def filter_new(jobs: list[Job]) -> list[Job]:
    """Return only the jobs not seen in a previous discovery cycle, and
    record them as seen so they aren't alerted again next cycle.
    """
    seen = _load_seen()
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    seen = {key: seen_at for key, seen_at in seen.items() if seen_at >= cutoff}

    new_jobs = []
    now = datetime.utcnow().isoformat()
    for job in jobs:
        key = _dedup_key(job)
        if key not in seen:
            new_jobs.append(job)
            seen[key] = now

    _save_seen(seen)
    return new_jobs
