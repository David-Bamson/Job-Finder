"""Shared data structures passed between the discovery, grading, telegram,
and notion layers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TrustTier(str, Enum):
    TIER_ONE = "tier_one"  # official APIs, RSS feeds
    TIER_TWO = "tier_two"  # verified company career pages
    TIER_THREE = "tier_three"  # aggregator scrapes


class JobStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


@dataclass
class Job:
    """A single job posting as it moves through the pipeline."""

    title: str
    company: str
    apply_url: str
    source: str
    trust_tier: TrustTier
    date_found: datetime = field(default_factory=datetime.utcnow)

    contact_email: str | None = None
    pay: str | None = None
    location: str | None = None
    description: str | None = None

    legitimacy_score: int | None = None
    legitimacy_reasons: list[str] = field(default_factory=list)
    hard_failed: bool = False

    fit_score: int | None = None

    status: JobStatus = JobStatus.NEW
    notes: str | None = None
    follow_up_date: datetime | None = None
    notion_page_id: str | None = None
