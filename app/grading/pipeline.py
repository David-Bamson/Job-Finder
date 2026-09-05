"""Runs the legitimacy and fit checks over a batch of freshly discovered
jobs before they reach the Telegram layer.

Fit scoring is free (local keyword/location/level matching), so it
always runs first. The legitimacy layer's SerpApi searches cost real
API quota, so they only run for jobs whose fit score clears
FIT_SCORE_THRESHOLD_FOR_FULL_CHECK — trusted companies still get their
lightweight check regardless of fit, since that path never touches
SerpApi.
"""

from app.config import FIT_SCORE_THRESHOLD_FOR_FULL_CHECK
from app.grading.legitimacy import check_hard_fail, grade_legitimacy
from app.grading.matching import grade_fit
from app.models import Job


def grade_all(jobs: list[Job]) -> list[Job]:
    """Apply hard-fail checks, fit grading, and (for promising jobs)
    full legitimacy grading to every job in the list.
    """
    graded = []
    for job in jobs:
        if check_hard_fail(job):
            job.hard_failed = True
            job.legitimacy_score = 0
            job.legitimacy_reasons = [
                "Hard fail: listing mentions a fee, payment, deposit, or training charge."
            ]
            graded.append(job)
            continue

        grade_fit(job)
        full_check = (job.fit_score or 0) >= FIT_SCORE_THRESHOLD_FOR_FULL_CHECK
        grade_legitimacy(job, full_check=full_check)
        graded.append(job)
    return graded
