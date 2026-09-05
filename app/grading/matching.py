"""Fit scoring, rebuilt exactly per direct instruction (2026-09-05):

Only these role types count as a fit at all:
- Data Analyst
- Data Entry
- Business Analyst
- Data Engineer
- Web Developer

Only these employment types count as a fit at all:
- Internship
- Contract
- Part time

A job must match at least one role AND at least one employment type
to be considered a fit at all - otherwise it's capped low, no matter
what else it contains. Volume doesn't matter; precision does.

Stack keywords are pulled only from the profile's "Current technical
stack" section (current level: Power BI, Git/GitHub, Python, SQL,
HTML/CSS/JS, Excel, Pandas/Scikit-learn, FastAPI, React) - explicitly
not the "Stack likely to grow into soon" section (Airflow, dbt,
BigQuery, Snowflake, deeper SQL), since scoring is meant to reflect
current level, not aspirational skills.
"""

import re
from functools import lru_cache

from app.models import Job

ROLE_KEYWORDS = [
    "data analyst",
    "data entry",
    "business analyst",
    "data engineer",
    "web developer",
]

EMPLOYMENT_TYPE_KEYWORDS = [
    "intern",
    "internship",
    "contract",
    "part time",
    "part-time",
]

# Current technical stack only, from profile/candidate_profile.md's
# "Current technical stack" section - not the growth-stack section.
STACK_KEYWORDS = [
    "power bi",
    "git",
    "github",
    "python",
    "sql",
    "html",
    "css",
    "javascript",
    "excel",
    "pandas",
    "scikit-learn",
    "fastapi",
    "react",
]


@lru_cache(maxsize=None)
def _word_pattern(phrase: str) -> re.Pattern:
    """Whole-word/whole-phrase match, so short keywords like "git" don't
    fire on unrelated words like "digital".

    Uses lookaround instead of \\b: phrases ending in punctuation break
    \\b, since \\b only fires on a word<->non-word transition.
    """
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)


def _contains(text: str, phrase: str) -> bool:
    return bool(_word_pattern(phrase).search(text))


def _text_blob(job: Job) -> str:
    return " ".join(filter(None, [job.title, job.description])).lower()


def grade_fit(job: Job) -> Job:
    """A job counts as a fit only if it matches one of the five named
    role types AND one of the three named employment types. Everything
    else is capped low regardless of any other keyword overlap. Among
    qualifying jobs, the score scales with how many current-level stack
    keywords it mentions.

    Role match is checked against the title only, not the description.
    Some sources (the HN hiring thread especially) pack multiple unrelated
    job openings into one comment/description, so scanning the full text
    can match a role keyword that belongs to a completely different
    posting than the one actually being scored.
    """
    title_text = (job.title or "").lower()
    text = _text_blob(job)

    role_match = any(_contains(title_text, kw) for kw in ROLE_KEYWORDS)
    employment_match = any(_contains(text, kw) for kw in EMPLOYMENT_TYPE_KEYWORDS)

    if not (role_match and employment_match):
        job.fit_score = 10
        return job

    stack_matches = sum(1 for kw in STACK_KEYWORDS if _contains(text, kw))
    job.fit_score = min(100, 70 + stack_matches * 10)
    return job
