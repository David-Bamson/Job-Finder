"""Runs all discovery sources on a schedule and hands the combined,
de-duplicated list of jobs to the grading layer.
"""

import logging

from app.discovery.seen_store import filter_new
from app.discovery.sources import arbeitnow, hn_hiring, linkedin_alerts, remoteok, weworkremotely
from app.models import Job

logger = logging.getLogger(__name__)

# Career pages and Indeed/Prosple aggregators aren't wired in yet (see
# README) so they're left out here rather than run and fail every cycle.
# HN hiring thread used to be gated to the first few days of the month
# (it only refreshes monthly) but is on every cycle now for maximum
# source coverage - dedup already prevents re-alerting the same posts.
ALWAYS_ON_SOURCES = [remoteok, arbeitnow, weworkremotely, linkedin_alerts, hn_hiring]


def discover_all() -> list[Job]:
    """Call every enabled source, merge the results, and return only
    jobs not seen in a previous cycle.
    """
    sources = list(ALWAYS_ON_SOURCES)

    all_jobs: list[Job] = []
    for source in sources:
        try:
            all_jobs.extend(source.fetch_jobs())
        except Exception:
            logger.exception("Discovery source %s failed", source.__name__)

    return filter_new(all_jobs)
