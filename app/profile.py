"""Loads the candidate profile markdown file (skills, target roles,
background) used to steer fit matching. The real file is personal and
lives outside version control — see profile/README.md for the expected
format and profile/candidate_profile.example.md for a template.
"""

import re
from pathlib import Path

from app.config import PROFILE_PATH

SKILLS_HEADING_NAMES = {"skills", "keywords", "tech stack", "technologies"}

EXPLICIT_KEYWORDS_PATTERN = re.compile(r"keywords?\s+that\s+signal\s+fit\s*:\s*(.+)", re.IGNORECASE)

# Broader vocabulary scanned across the whole profile text, so specific
# tools mentioned in prose (e.g. "deployed through FastAPI") are picked
# up as fit keywords even outside a dedicated "Skills" list.
KNOWN_TECH_VOCABULARY = [
    "sql",
    "python",
    "etl",
    "data pipeline",
    "backend",
    "data analyst",
    "data engineer",
    "dashboards",
    "data cleaning",
    "automation",
    "power bi",
    "excel",
    "git",
    "github",
    "html",
    "css",
    "javascript",
    "pandas",
    "scikit-learn",
    "fastapi",
    "react",
    "airflow",
    "dbt",
    "bigquery",
    "snowflake",
    "machine learning",
    "data annotation",
    "ai evaluation",
    "research assistant",
]

INDIA_LOCATION_MARKERS = [
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "mumbai",
    "delhi",
    "gurgaon",
    "gurugram",
    "noida",
    "chennai",
]

_text_cache: str | None = None


def load_profile_text() -> str:
    """Return the raw contents of the candidate profile file, or an
    empty string if it hasn't been created yet.
    """
    global _text_cache
    if _text_cache is not None:
        return _text_cache
    path = Path(PROFILE_PATH)
    _text_cache = path.read_text(encoding="utf-8") if path.exists() else ""
    return _text_cache


def _bullet_list_keywords(text: str) -> list[str]:
    """Bullet items under a heading literally named Skills/Keywords/Tech
    Stack/Technologies — the format used by the example template.
    """
    keywords = []
    in_skills_section = False
    for line in text.splitlines():
        heading_match = re.match(r"#{1,6}\s*(.+)", line)
        if heading_match:
            in_skills_section = heading_match.group(1).strip().lower() in SKILLS_HEADING_NAMES
            continue
        if not in_skills_section:
            continue
        item_match = re.match(r"[-*]\s*(.+)", line.strip())
        if item_match:
            for keyword in item_match.group(1).split(","):
                keyword = keyword.strip().lower()
                if keyword:
                    keywords.append(keyword)
    return keywords


def extract_keywords() -> list[str]:
    """Pull fit-matching keywords out of the profile: an explicit
    "Keywords that signal fit: ..." line if present, bullet lists under
    a Skills/Keywords heading (template format), and a scan for known
    tech terms mentioned anywhere in the file. Returns an empty list if
    no profile file exists yet.
    """
    text = load_profile_text()
    if not text:
        return []

    keywords: list[str] = []

    for line in text.splitlines():
        match = EXPLICIT_KEYWORDS_PATTERN.search(line)
        if match:
            for keyword in match.group(1).split(","):
                keyword = keyword.strip().rstrip(".").lower()
                if keyword:
                    keywords.append(keyword)

    keywords.extend(_bullet_list_keywords(text))

    lower_text = text.lower()
    for term in KNOWN_TECH_VOCABULARY:
        if term in lower_text:
            keywords.append(term)

    return list(dict.fromkeys(keywords))


def wants_india_flagged() -> bool:
    """Whether the profile's standing filter section calls out India
    specifically for case-by-case review rather than auto-surfacing.
    """
    text = load_profile_text().lower()
    return "india" in text and ("standing filter" in text or "review case by case" in text)
