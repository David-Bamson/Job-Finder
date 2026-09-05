"""Indeed and Prosple. Tier three source, scraped, held to a higher bar
in grading rather than discarded outright.
"""

from app.models import Job


def fetch_jobs() -> list[Job]:
    """Scrape Indeed and Prosple search results and return listings as Job objects."""
    raise NotImplementedError
