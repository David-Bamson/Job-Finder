"""LinkedIn job alert emails, read over IMAP. LinkedIn itself is not
scraped directly since that violates their terms of service.
"""

import email
import imaplib

from bs4 import BeautifulSoup

from app.config import EMAIL_ADDRESS, EMAIL_APP_PASSWORD, IMAP_SERVER
from app.models import Job, TrustTier

SENDER = "jobalerts-noreply@linkedin.com"


def _extract_jobs_from_html(html: str) -> list[Job]:
    """LinkedIn's job alert digest lists several job cards per email, each
    wrapping a /comm/jobs/view/<id> link. The link itself has no text (it
    wraps a logo image), so the title/company/location/pay live in the
    surrounding text of a parent element.
    """
    soup = BeautifulSoup(html, "lxml")
    links = soup.find_all("a", href=lambda h: h and "/comm/jobs/view/" in h)

    jobs = []
    seen_urls = set()
    for link in links:
        apply_url = link["href"].split("?")[0]
        if apply_url in seen_urls:
            continue
        seen_urls.add(apply_url)

        card_text = None
        node = link
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            text = node.get_text(separator=" | ", strip=True)
            if text:
                card_text = text
                break
        if not card_text:
            continue

        parts = [p.strip() for p in card_text.split("|") if p.strip()]
        if not parts:
            continue

        title = parts[0]
        company, location = "", None
        if len(parts) > 1:
            company_location = parts[1]
            if "·" in company_location:
                company, location = (s.strip() for s in company_location.split("·", 1))
            else:
                company = company_location

        pay = next((p for p in parts[2:] if any(c in p for c in "$£€₦")), None)

        jobs.append(
            Job(
                title=title,
                company=company,
                apply_url=apply_url,
                source="linkedin_alerts",
                trust_tier=TrustTier.TIER_ONE,
                location=location,
                pay=pay,
                description=card_text,
            )
        )
    return jobs


def fetch_jobs() -> list[Job]:
    """Read unread LinkedIn job alert emails from the configured inbox and
    return the listings they contain as Job objects.
    """
    mailbox = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=20)
    mailbox.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
    mailbox.select("inbox")

    status, data = mailbox.search(None, "UNSEEN", "FROM", f'"{SENDER}"')
    message_ids = data[0].split()

    jobs = []
    for message_id in message_ids:
        status, msg_data = mailbox.fetch(message_id, "(RFC822)")
        message = email.message_from_bytes(msg_data[0][1])

        html = None
        for part in message.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="replace")
                break

        if html:
            jobs.extend(_extract_jobs_from_html(html))

    mailbox.logout()
    return jobs
