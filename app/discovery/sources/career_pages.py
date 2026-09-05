"""Manually added company career pages. Tier two source, added once a
company has been verified.
"""

from app.models import Job


def fetch_jobs() -> list[Job]:
    """Check the configured list of verified company career pages for new listings."""
    raise NotImplementedError
