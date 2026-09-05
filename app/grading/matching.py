"""Fit scoring, kept separate from the legitimacy score so the two
numbers never get blended into one confusing figure.

Built directly around profile/candidate_profile.md's "What counts as a
good fit" section, which is explicit that this is a strict filter, not
a set of loose preferences:

- Level must be explicitly stated as internship/entry/junior/graduate/
  fresher (or freelance/contract, per "Preferred working format") -
  "only", per the profile's own wording. No explicit label means
  disqualified, not a neutral/50 guess.
- A fixed exclude list (specialist/lead/manager/principal/senior titles,
  "operations specialist", and "software engineer" postings without an
  explicit junior/entry label) is disqualifying regardless of keyword
  overlap.
- Only postings matching one of the profile's named role types count as
  a good fit at all; everything else is disqualified too.
"""

import re
from functools import lru_cache

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

# Profile: "Level, hard filter: internship, entry level, junior, or
# explicitly labelled graduate or fresher roles only." Plus "Preferred
# working format" treats freelance/contract as equally acceptable.
LEVEL_KEYWORDS = [
    "intern",
    "internship",
    "entry level",
    "entry-level",
    "junior",
    "jr.",
    "new grad",
    "graduate",
    "fresher",
    "freelance",
    "contract",
    "contractor",
    "hourly",
]

# Profile: "Role types to exclude outright, regardless of keyword
# match" - senior/lead/manager/principal/specialist titles.
EXCLUDE_TITLE_KEYWORDS = [
    "senior",
    "sr.",
    "staff",
    "principal",
    "lead",
    "director",
    "head of",
    "vp",
    "manager",
    "specialist",
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


@lru_cache(maxsize=None)
def _word_pattern(phrase: str) -> re.Pattern:
    """Whole-word/whole-phrase match, so short keywords like "git" don't
    fire on unrelated words like "digital", or "react" on "reactive".

    Uses lookaround instead of \\b: phrases ending in punctuation (e.g.
    "sr.", "jr.") break \\b, since \\b only fires on a word<->non-word
    transition, and non-word ("." then " ") to non-word is not one.
    """
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)


def _contains(text: str, phrase: str) -> bool:
    return bool(_word_pattern(phrase).search(text))


def _text_blob(job: Job) -> str:
    return " ".join(filter(None, [job.title, job.description])).lower()


def _all_keywords() -> list[str]:
    """Default plan keywords plus anything listed under the Skills/
    Keywords section of the candidate profile."""
    return list(dict.fromkeys([*DEFAULT_KEYWORDS, *_extract_profile_keywords()]))


def _is_excluded(text: str) -> bool:
    """Profile's explicit exclude list, checked before anything else."""
    if any(_contains(text, kw) for kw in EXCLUDE_TITLE_KEYWORDS):
        return True
    if _contains(text, "operations specialist"):
        return True
    if _contains(text, "software engineer") and not any(_contains(text, kw) for kw in LEVEL_KEYWORDS):
        return True
    return False


def _match_role_category(text: str) -> int:
    """Profile's "Role types to include, in rough order of interest".
    Returns 0 if the posting matches none of them at all.
    """
    if _contains(text, "data analyst") and any(_contains(text, kw) for kw in ("intern", "internship")):
        return 100
    if _contains(text, "data analyst") or _contains(text, "data engineer"):
        return 95
    if _contains(text, "business analyst") and any(_contains(text, kw) for kw in ("intern", "internship")):
        return 90
    if _contains(text, "data entry"):
        return 85
    if any(_contains(text, phrase) for phrase in ["ai evaluation", "data annotation", "research assistant"]):
        return 80
    if _contains(text, "web development") or _contains(text, "frontend") or _contains(text, "front-end"):
        return 75
    if _contains(text, "data analysis") or _contains(text, "python"):
        return 65
    return 0


def _keyword_score(text: str) -> float:
    matches = sum(1 for kw in _all_keywords() if _contains(text, kw))
    return min(matches, 3) / 3 * 100


def _location_score(job: Job, text: str) -> float:
    location = (job.location or "").lower()
    if any(_contains(location, kw) for kw in REMOTE_KEYWORDS) or any(
        _contains(text, kw) for kw in REMOTE_KEYWORDS
    ):
        if any(_contains(text, pattern) for pattern in VISA_BLOCKER_PATTERNS):
            return 40
        return 100
    if location:
        return 20  # tied to a specific in-office location, not flagged remote
    return 50  # location unknown, can't tell either way


def _check_india_flag(job: Job, text: str) -> str | None:
    """The profile's standing filter says not to auto-apply to
    India-based companies until verified beyond reasonable doubt, but to
    still surface them (flagged) rather than silently discard them.
    """
    if not wants_india_flagged():
        return None
    location = (job.location or "").lower()
    if any(_contains(location, marker) for marker in INDIA_LOCATION_MARKERS) or _contains(text, "india"):
        return "Standing filter: company appears to be India-based — review case by case rather than auto-apply."
    return None


def matched_keywords_in_text(text: str) -> list[str]:
    """Which profile/plan keywords a piece of text actually matched, for
    display on the web dashboard. Not stored in Notion — recomputed from
    the job's title+description each time the page is rendered.
    """
    lowered = (text or "").lower()
    return [kw for kw in _all_keywords() if _contains(lowered, kw)]


def grade_fit(job: Job) -> Job:
    """Score how well the job matches the profile's role types, level,
    keywords, and location - all treated as a strict filter per the
    profile's own wording, not loose preferences. A posting fails
    outright (capped low) if it's on the exclude list, doesn't match
    any of the named role types, or has no explicit qualifying level
    label at all.
    """
    text = _text_blob(job)
    has_level_signal = any(_contains(text, kw) for kw in LEVEL_KEYWORDS)
    role_score = _match_role_category(text)

    if _is_excluded(text):
        job.fit_score = 10
    elif role_score == 0:
        job.fit_score = 15
    elif not has_level_signal:
        job.fit_score = 20
    else:
        keyword_score = _keyword_score(text)
        location_score = _location_score(job, text)
        job.fit_score = round(role_score * 0.55 + keyword_score * 0.25 + location_score * 0.20)

    india_flag = _check_india_flag(job, text)
    if india_flag:
        job.notes = india_flag if not job.notes else f"{job.notes}; {india_flag}"

    return job
