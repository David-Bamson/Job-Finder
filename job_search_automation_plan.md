# Job Search Automation System, Architecture Plan

## Core loop

Discover jobs, verify and grade them, check fit, notify you on Telegram, wait for your decision, log to Notion, track status.

Apply stays human approved. The system prepares, you confirm. Speed is not the goal, catching bad listings before you act on them is.

---

## 1. Discovery layer

What it does: pulls job postings from multiple sources on a schedule.

Sources used:
- RemoteOK, public API, free and reliable
- Arbeitnow, public API, remote focused
- WeWorkRemotely, RSS feed, no scraping needed
- Hacker News monthly hiring thread, scraped once a month
- Company career pages, added once a company is manually verified
- Indeed and Prosple, scraped, treated as lower trust and graded harder as a result
- LinkedIn, not scraped directly since that violates their terms, their own job alert emails are used instead

Trust tiers assigned by source:
- Tier one: official APIs and RSS feeds
- Tier two: verified company career pages
- Tier three: aggregator scrapes, held to a higher bar in grading, not discarded

---

## 2. Verification and grading layer

What it does: runs every non obvious job through a full check before deciding anything. This is the most important layer, so it is done in full every time, not shortcut.

Step by step:
- Pull the facts: company name, apply link domain, contact email domain, stated pay, stated location, and any claims about how you were selected
- Run several searches, not one: the company name alone, the company name with the word reviews, the company name with the word scam, and the apply domain by itself
- Check domain consistency: does the apply link match the company's real website, does the contact email match that same domain
- Check for real presence: does the company have a verifiable product or service beyond the listing, does the same posting appear on other independent platforms with matching details
- Check the website itself: built on a generic site builder with hidden ownership, or does it show a real address and accountability
- Scan for red flag language

Automatic hard fail, no matter how good anything else looks:
- Any mention of a fee, confirmation payment, refundable deposit, or training charge

Red flags that lower the score but do not auto fail:
- Being told you are selected with no interview or assessment at all
- Pressure language telling you to act fast or confirm within a short window
- Being asked to reply with a confirmation screenshot
- Confidentiality clauses attached to an unpaid or entry level role

Green flags that raise the score:
- The listing matches near identically across two or more independent sources
- A verifiable product or track record beyond the listing itself
- The apply link sits on the company's own domain, not a third party form

Output: a score from zero to one hundred with specific reasons attached, for example naming exactly which domain mismatch or missing evidence lowered the score.

Efficiency without cutting corners:
- A trusted company list is kept in Notion
- Once a company is manually confirmed as real, future postings from that exact domain skip to a lighter check
- New, unverified companies always get the full process

---

## 3. Matching layer

What it does: scores fit separately from legitimacy, so the two numbers never get blended into one confusing figure.

Filters applied:
- Keywords: SQL, Python, ETL, data pipeline, backend, data analyst, data engineer
- Location: remote roles, or roles open to applicants outside the company's country, excluding ones that require work authorization you do not have
- Level: internship, entry level, and junior roles for now

Result: every job carries two separate numbers, a legitimacy score and a fit score, so you can see something like highly legitimate but a weak fit, or a strong fit but a score that needs your own attention.

---

## 4. Telegram bot layer

What it does: sends you each job that is not an automatic hard fail, in plain, simple language.

Message format example:

New job found.
Title: Data Analyst Intern
Company: example company name
Legitimacy score: 82 out of 100
Fit score: 75 out of 100
Pay: 35000 to 100000 naira per month
Location: remote
Source: company careers page, high trust
Why it scored well: the same listing appears on two other independent job boards with matching details, and the apply link matches the company's own website
Something to note: this is a young company with limited independent reviews

Buttons offered: Approve and apply. Skip. Needs manual review.

Additional behaviour:
- Hard failed jobs, meaning any payment request, are never sent as alerts, they are logged quietly to Notion instead
- A weekly summary of everything auto rejected is sent, so you can spot check the system isn't over filtering
- A stats command is available any time, showing how many jobs were found, sent to you, auto rejected, and applied to that week

---

## 5. Application layer

What it does: prepares your application, never submits it for you.

- On approve and apply, the bot drafts your resume attachment plus a short note tailored to that listing
- It sends the draft back to you for a final look
- You do the actual submitting yourself, especially on any form asking for personal details beyond name, email, and resume

---

## 6. Notion logging layer

What it does: keeps a running record of every job and its status.

Fields tracked:
- Job title
- Company name
- Source and trust tier
- Date found
- Legitimacy score and reasons
- Fit score
- Status: new, reviewed, approved, applied, interview, offer or rejected
- Apply link
- Pay
- Your own notes
- Follow up date, so nothing goes silent without a reminder

Bonus view: a filter showing only applied jobs sorted by follow up date, turning the same table into an interview pipeline tracker.

---

## Suggested build stack

- Scheduler: a cron job or lightweight always on script, running every few hours
- Language: Python, with requests and BeautifulSoup for scraping, python telegram bot for Telegram, and the official Notion client for logging
- Faster alternative: n8n or Make, no code tools with built in Notion and Telegram integrations, useful if you want this running in days rather than weeks

---

## Open decisions for you

- Which sources to start with, a reasonable first set is RemoteOK, WeWorkRemotely, Arbeitnow, and any company career pages you add manually over time
- Whether hard failed jobs stay completely silent or you want a visible running log of them too at first, to confirm the system is catching the right things
- Which company becomes the first entry in your trusted company list
