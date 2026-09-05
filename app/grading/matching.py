"""Fit scoring, kept separate from the legitimacy score so the two
numbers never get blended into one confusing figure.

Filters: keyword match (SQL, Python, ETL, data pipeline, backend, data
analyst, data engineer), location (remote or open to applicants
outside the company's country, excluding roles that require work
authorization the applicant does not have), and level (internship,
entry level, junior).
"""

from app.models import Job
from app.profile import INDIA_LOCATION_MARKERS
from app.profile import extract_keywords as _extract_profile_keywords
from app.profile import wants_india_flagged

DEFAULT_KEYWORDS = [
    "sql",
    "python",
    "etl",
    "data pipeline",
    "backend",
    "data analyst",
    "data engineer",
]

LEVEL_KEYWORDS = [
    "intern",
    "internship",
    "entry level",
    "entry-level",
    "junior",
    "jr.",
    "new grad",
    "graduate",
    "freelance",
    "contract",
    "contractor",
    "hourly",
]

SENIOR_KEYWORDS = [
    "senior",
    "sr.",
    "staff",
    "principal",
    "lead ",
    "director",
    "head of",
    "vp ",
    "manager",
]

REMOTE_KEYWORDS = ["remote", "anywhere", "worldwide", "distributed"]

VISA_BLOCKER_PATTERNS = [
    "must be authorized to work",
    "no visa sponsorship",
    "not able to sponsor",
    "us citizens only",
    "must be a us citizen",
    "security clearance required",
]


def _text_blob(job: Job) -> str:
    return " ".join(filter(None, [job.title, job.description])).lower()


def _all_keywords() -> list[str]:
    """Default plan keywords plus anything listed under the Skills
    section of the candidate profile, if one has been added.
    """
    return list(dict.fromkeys([*DEFAULT_KEYWORDS, *_extract_profile_keywords()]))


def _keyword_score(text: str) -> float:
    matches = sum(1 for kw in _all_keywords() if kw in text)
    return min(matches, 3) / 3 * 100


def _location_score(job: Job, text: str) -> float:
    location = (job.location or "").lower()
    if any(kw in location for kw in REMOTE_KEYWORDS) or any(kw in text for kw in REMOTE_KEYWORDS):
        if any(pattern in text for pattern in VISA_BLOCKER_PATTERNS):
            return 40
        return 100
    if location:
        return 20  # tied to a specific in-office location, not flagged remote
    return 50  # location unknown, can't tell either way


def _level_score(text: str) -> float:
    if any(kw in text for kw in SENIOR_KEYWORDS):
        return 0
    if any(kw in text for kw in LEVEL_KEYWORDS):
        return 100
    return 50  # no explicit level signal either way


def _check_india_flag(job: Job, text: str) -> str | None:
    """The profile's standing filter says not to auto-apply to
    India-based companies until verified beyond reasonable doubt, but to
    still surface them (flagged) rather than silently discard them.
    """
    if not wants_india_flagged():
        return None
    location = (job.location or "").lower()
    if any(marker in location for marker in INDIA_LOCATION_MARKERS) or "india" in text:
        return "Standing filter: company appears to be India-based — review case by case rather than auto-apply."
    return None


def grade_fit(job: Job) -> Job:
    """Score how well the job matches the target keywords, location, and
    level, and set job.fit_score in place.
    """
    text = _text_blob(job)
    keyword_score = _keyword_score(text)
    location_score = _location_score(job, text)
    level_score = _level_score(text)

    job.fit_score = round(keyword_score * 0.4 + location_score * 0.3 + level_score * 0.3)

    india_flag = _check_india_flag(job, text)
    if india_flag:
        job.notes = india_flag if not job.notes else f"{job.notes}; {india_flag}"

    return job
