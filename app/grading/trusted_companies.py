"""Trusted company list, kept in Notion. Once a company is manually
confirmed as real, future postings from that exact domain skip to a
lighter legitimacy check. New, unverified companies always get the
full process.
"""

import logging

logger = logging.getLogger(__name__)

_cache: set[str] | None = None


def _load_trusted_domains() -> set[str]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        from app.notion.client import get_trusted_domains

        _cache = {d.lower() for d in get_trusted_domains()}
    except NotImplementedError:
        logger.warning("Notion client not implemented yet; treating no companies as trusted.")
        _cache = set()
    return _cache


def is_trusted(domain: str) -> bool:
    """Check whether the given apply/company domain is on the trusted
    company list in Notion.
    """
    return domain.lower() in _load_trusted_domains()
