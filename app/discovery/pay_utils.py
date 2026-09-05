"""Shared helper for pulling a stated salary figure, with whatever pay
period it's expressed in (hourly/weekly/monthly/yearly), out of free
text job postings. Used by sources whose raw data doesn't separate
salary into its own field (e.g. the HN hiring thread's free-text
comments).
"""

import re

SALARY_PATTERN = re.compile(
    r"[$€£₦]\s?\d[\d,.]*\s?[kK]?"
    r"(?:\s?[-–to]{1,4}\s?[$€£₦]?\s?\d[\d,.]*\s?[kK]?)?"
    r"(?:\s?/\s?(?:hour|hr|week|wk|month|mo|year|yr)"
    r"|\s?per\s+(?:hour|week|month|year)"
    r"|\s?(?:hourly|weekly|monthly|yearly|annually))?",
    re.IGNORECASE,
)


def extract_salary(text: str) -> str | None:
    """Pull the first salary-looking figure out of free text, e.g.
    "$35-$50/hour" or "75k-110k EUR/year". The pay period is included in
    the match when the source text states one; if it doesn't, the
    period is genuinely unknown and left out rather than guessed.
    """
    if not text:
        return None
    match = SALARY_PATTERN.search(text)
    return match.group(0).strip() if match else None
