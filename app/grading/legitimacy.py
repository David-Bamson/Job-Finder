"""Legitimacy verification. The most important layer, run in full for
every non-trusted job: pull the facts, run several searches, check
domain consistency, check for real company presence, scan for red flag
language, and produce a 0-100 score with specific reasons attached.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from serpapi import GoogleSearch

from app.config import SERPAPI_API_KEY
from app.grading.trusted_companies import is_trusted
from app.models import Job

HEADERS = {"User-Agent": "Mozilla/5.0 (job-search-automation)"}

HARD_FAIL_PATTERNS = [
    r"\bregistration fee\b",
    r"\bprocessing fee\b",
    r"\bapplication fee\b",
    r"\btraining fee\b",
    r"\btraining charge\b",
    r"\brefundable deposit\b",
    r"\bsecurity deposit\b",
    r"\bconfirmation payment\b",
    r"\bpurchase (?:your own|a) (?:starter kit|equipment)\b",
    r"\bsend (?:us )?(?:a )?(?:payment|money)\b",
]

RED_FLAG_PRESSURE_PATTERNS = [
    r"\bact fast\b",
    r"\bact now\b",
    r"\bwithin \d+\s*(?:hours|hrs|minutes)\b",
    r"\blimited time\b",
    r"\bconfirm (?:immediately|asap|now)\b",
]

SCREENSHOT_PATTERN = r"\b(?:confirmation )?screenshot\b"
SELECTED_NO_INTERVIEW_PATTERN = r"\byou (?:have been|are|were) selected\b"
INTERVIEW_MENTION_PATTERN = r"\b(?:interview|assessment|test|screening)\b"
CONFIDENTIALITY_PATTERN = r"\bconfidential(?:ity)?\b"
UNPAID_ENTRY_PATTERN = r"\b(?:unpaid|no pay|volunteer|entry level|entry-level|intern(?:ship)?)\b"

GENERIC_FORM_HOSTS = {
    "forms.gle",
    "docs.google.com",
    "typeform.com",
    "jotform.com",
    "linktr.ee",
    "bit.ly",
    "tinyurl.com",
    "forms.office.com",
    "surveymonkey.com",
}

GENERIC_SITE_BUILDER_HOSTS = {
    "wixsite.com",
    "weebly.com",
    "sites.google.com",
    "carrd.co",
    "wordpress.com",
    "blogspot.com",
}

NEGATIVE_SIGNAL_WORDS = ["scam", "fraud", "fake", "warning", "avoid", "scheme", "rip off", "ripoff"]
IMPERSONATION_MARKERS = [
    "impersonat",
    "posing as",
    "pretending to be",
    "claiming to be from",
    "claiming to be",
    "using our name",
    "using the company name",
    "fraud alert",
    "scams claiming",
    "beware of scams",
    "scam warning",
    "scam alert",
]
REVIEW_SITE_DOMAINS = ["glassdoor.com", "trustpilot.com", "indeed.com", "bbb.org"]
ACCOUNTABILITY_PAGE_MARKERS = ["contact us", "about us", "privacy policy", "terms of service", "terms & conditions"]


@dataclass
class _CheckResult:
    score_delta: int
    reasons: list[str]


def _extract_domain(value: str | None) -> str | None:
    if not value:
        return None
    if "@" in value and "://" not in value:
        domain = value.split("@")[-1]
    else:
        parsed = urlparse(value if "://" in value else f"//{value}")
        domain = parsed.netloc or parsed.path
    domain = domain.lower().split(":")[0].strip("/")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def check_hard_fail(job: Job) -> bool:
    """Return True if the listing mentions any fee, confirmation payment,
    refundable deposit, or training charge. A hard fail is never sent as
    a Telegram alert, only logged to Notion.
    """
    text = " ".join(filter(None, [job.title, job.description])).lower()
    return any(re.search(pattern, text) for pattern in HARD_FAIL_PATTERNS)


def _serpapi_search(query: str, num: int = 5) -> list[dict]:
    if not SERPAPI_API_KEY:
        return []
    try:
        search = GoogleSearch({"q": query, "api_key": SERPAPI_API_KEY, "num": num})
        return search.get_dict().get("organic_results", [])
    except Exception:
        return []


def _check_company_presence(company: str, apply_domain: str | None) -> _CheckResult:
    """Search the company name alone: confirms a real presence beyond the
    listing, and checks whether the apply domain shows up as associated
    with the company.
    """
    results = _serpapi_search(f'"{company}"')
    if not results:
        return _CheckResult(-10, [f'No search results found for the company name "{company}" alone.'])
    if apply_domain and any(apply_domain in (r.get("link") or "") for r in results):
        return _CheckResult(
            10,
            [f"Apply domain {apply_domain} appears in general search results for \"{company}\"."],
        )
    return _CheckResult(0, [])


def _check_reputation(company: str) -> _CheckResult:
    """Search "<company> scam" and "<company> reviews". Results warning
    that scammers impersonate the company are a protective signal, not a
    red flag against the company itself, so those are filtered out
    before counting genuine negative hits.
    """
    scam_results = _serpapi_search(f'"{company}" scam')
    flagged = [
        r
        for r in scam_results
        if any(w in (r.get("title", "") + r.get("snippet", "")).lower() for w in NEGATIVE_SIGNAL_WORDS)
    ]
    impersonation_hits = [
        r
        for r in flagged
        if any(m in (r.get("title", "") + r.get("snippet", "")).lower() for m in IMPERSONATION_MARKERS)
    ]
    genuine_hits = [r for r in flagged if r not in impersonation_hits]

    if impersonation_hits and not genuine_hits:
        return _CheckResult(
            5,
            [f'Search results warn that scammers impersonate "{company}", which is a sign the company itself is a known, established target rather than the scam.'],
        )
    if len(genuine_hits) >= 2:
        return _CheckResult(
            -30,
            [f'Search for "{company} scam" surfaced {len(genuine_hits)} result(s) describing the company itself as fraudulent.'],
        )

    review_results = _serpapi_search(f'"{company}" reviews')
    review_hits = [r for r in review_results if any(d in (r.get("link") or "") for d in REVIEW_SITE_DOMAINS)]
    if review_hits:
        return _CheckResult(10, [f"Found independent reviews for {company} on established review sites."])
    return _CheckResult(-5, [f"No independent reviews found for {company} on established review sites."])


def _check_duplicate_listing(title: str, company: str) -> _CheckResult:
    """Does the same posting appear on other independent platforms with
    matching details?
    """
    results = _serpapi_search(f'"{title}" "{company}"')
    domains = {_extract_domain(r.get("link")) for r in results if r.get("link")}
    domains.discard(None)
    if len(domains) >= 2:
        return _CheckResult(
            10,
            [f'The listing for "{title}" at {company} appears on {len(domains)} independent sites with matching details.'],
        )
    return _CheckResult(0, [])


def _check_website_accountability(apply_domain: str | None) -> _CheckResult:
    """Fetch the apply domain's homepage and look for basic accountability
    pages (contact, about, privacy policy, terms).
    """
    if not apply_domain:
        return _CheckResult(0, [])
    try:
        response = requests.get(f"https://{apply_domain}", headers=HEADERS, timeout=10)
        page_text = response.text.lower()
    except requests.RequestException:
        return _CheckResult(0, [f"Could not reach {apply_domain} to check for accountability pages."])

    hits = sum(1 for marker in ACCOUNTABILITY_PAGE_MARKERS if marker in page_text)
    if hits >= 2:
        return _CheckResult(5, [f"{apply_domain} shows standard accountability pages (contact/about/policies)."])
    return _CheckResult(-5, [f"{apply_domain} shows little sign of contact info or accountability pages."])


def grade_legitimacy(job: Job, full_check: bool = True) -> Job:
    """Run the verification process and set job.legitimacy_score and
    job.legitimacy_reasons in place. Trusted-company jobs skip to a
    lighter check via app.grading.trusted_companies, and hard fails are
    caught before any search runs.

    full_check controls whether the SerpApi-backed searches run at all.
    They're the expensive part of this layer, so the grading pipeline
    only sets full_check=True for jobs whose fit score already clears
    FIT_SCORE_THRESHOLD_FOR_FULL_CHECK — everything else (hard-fail and
    trusted-company checks) is free and always runs regardless.
    """
    if check_hard_fail(job):
        job.hard_failed = True
        job.legitimacy_score = 0
        job.legitimacy_reasons = [
            "Hard fail: listing mentions a fee, payment, deposit, or training charge."
        ]
        return job

    apply_domain = _extract_domain(job.apply_url)

    if apply_domain and is_trusted(apply_domain):
        job.legitimacy_score = 85
        job.legitimacy_reasons = [
            f"{apply_domain} is on the trusted company list; full verification skipped."
        ]
        return job

    if not full_check:
        job.legitimacy_score = None
        job.legitimacy_reasons = [
            "Fit score too low to warrant the full search-based legitimacy check; not verified."
        ]
        return job

    score = 50
    reasons: list[str] = []
    text = " ".join(filter(None, [job.title, job.description])).lower()

    if job.contact_email:
        email_domain = _extract_domain(job.contact_email)
        if email_domain and apply_domain and email_domain != apply_domain:
            score -= 15
            reasons.append(
                f"Contact email domain ({email_domain}) does not match the apply link domain ({apply_domain})."
            )

    if apply_domain and any(apply_domain == h or apply_domain.endswith(f".{h}") for h in GENERIC_FORM_HOSTS):
        score -= 10
        reasons.append(f"Apply link uses a generic third-party form host ({apply_domain}), not the company's own domain.")
    elif apply_domain and any(apply_domain == h or apply_domain.endswith(f".{h}") for h in GENERIC_SITE_BUILDER_HOSTS):
        score -= 15
        reasons.append(f"Company site is hosted on a generic site builder ({apply_domain}), not a dedicated company domain.")
    elif apply_domain:
        score += 10
        reasons.append(f"Apply link sits on the company's own domain ({apply_domain}).")

    if re.search(SELECTED_NO_INTERVIEW_PATTERN, text) and not re.search(INTERVIEW_MENTION_PATTERN, text):
        score -= 15
        reasons.append("Listing claims you are selected with no mention of an interview or assessment.")

    if any(re.search(pattern, text) for pattern in RED_FLAG_PRESSURE_PATTERNS):
        score -= 10
        reasons.append("Listing uses pressure language to act or confirm quickly.")

    if re.search(SCREENSHOT_PATTERN, text):
        score -= 10
        reasons.append("Listing asks for a confirmation screenshot.")

    if re.search(CONFIDENTIALITY_PATTERN, text) and re.search(UNPAID_ENTRY_PATTERN, text):
        score -= 10
        reasons.append("Confidentiality clause attached to an unpaid or entry-level role.")

    if job.company:
        for check in (
            _check_company_presence(job.company, apply_domain),
            _check_reputation(job.company),
            _check_duplicate_listing(job.title, job.company),
        ):
            score += check.score_delta
            reasons.extend(check.reasons)

    website_check = _check_website_accountability(apply_domain)
    score += website_check.score_delta
    reasons.extend(website_check.reasons)

    job.legitimacy_score = max(0, min(100, round(score)))
    job.legitimacy_reasons = reasons
    return job
