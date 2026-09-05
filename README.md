# Job Search Automation

Finds job postings, checks them for legitimacy and fit, alerts you on
Telegram, and logs everything to Notion. You always approve before
anything gets applied to — see [job_search_automation_plan.md](job_search_automation_plan.md)
for the full architecture.

**Status:** discovery and grading are implemented and tested against
live data. Telegram and Notion are still skeleton (`NotImplementedError`
stubs) — `main.py` isn't wired up end to end yet.

| Layer | Status |
|---|---|
| Discovery: RemoteOK, Arbeitnow, WeWorkRemotely, HN hiring thread, LinkedIn alert emails | Done |
| Discovery: Indeed/Prosple (aggregators) | Blocked — both block simple scraping (Cloudflare/403); needs a headless browser or proxy service |
| Discovery: company career pages | Blocked — depends on the trusted company list, which lives in Notion (not built yet) |
| Grading: fit scoring, legitimacy scoring | Done |
| Telegram bot | Not started |
| Notion logging | Not started |

## Project structure

```
app/
  config.py              # loads settings from .env
  models.py               # shared Job dataclass, TrustTier, JobStatus
  profile.py               # loads profile/candidate_profile.md, extracts skills as keywords
  discovery/
    pipeline.py            # runs every source, merges + de-dupes results
    sources/
      remoteok.py           # RemoteOK API (tier one)
      arbeitnow.py           # Arbeitnow API (tier one)
      weworkremotely.py      # WeWorkRemotely RSS (tier one)
      hn_hiring.py           # HN "who is hiring" thread, monthly (tier one)
      career_pages.py        # manually verified company career pages (tier two) — blocked, see above
      aggregators.py         # Indeed / Prosple scrapes (tier three) — blocked, see above
      linkedin_alerts.py     # reads LinkedIn job alert emails over IMAP
  grading/
    legitimacy.py           # hard-fail + 0-100 legitimacy scoring (SerpApi-backed)
    matching.py              # fit scoring (keywords, location, level)
    trusted_companies.py    # trusted-domain lookup, backed by Notion
    pipeline.py              # fit scoring first (free), then legitimacy only for jobs that clear the bar
  telegram/
    bot.py                   # sends alerts, weekly summary, /stats command — not implemented
    messages.py               # formats Job objects into message text — not implemented
  notion/
    client.py                # logs jobs, updates status, trusted company list — not implemented
profile/
  README.md                # profile format notes
  candidate_profile.example.md  # template — copy to candidate_profile.md and fill in your own background
main.py                     # wires the pipeline together, runs on a schedule — not implemented
requirements.txt
.env.example
```

Note: the `telegram/` and `notion/` folders live under `app/` (not at the
project root) so they don't shadow the `python-telegram-bot` and
`notion-client` packages when imported.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your Telegram bot token,
   Notion integration token and database IDs, SerpApi key, and email
   app password (see comments in that file for where to get each one).
3. Copy `profile/candidate_profile.example.md` to `profile/candidate_profile.md`
   and fill in your own skills, target roles, and background — the
   `Skills` section is merged into the fit-matching keyword list.
   `candidate_profile.md` is gitignored since it's personal.
4. In Notion, create the two databases referenced in `.env` (jobs log,
   trusted companies) with the fields listed in the plan file, once you
   get to the Notion layer.

## Running

Individual layers can already be tested in isolation:

```
python -c "from app.discovery.sources.remoteok import fetch_jobs; print(len(fetch_jobs()))"

python -c "
from app.discovery.sources.remoteok import fetch_jobs
from app.grading.pipeline import grade_all
jobs = grade_all(fetch_jobs())
for j in sorted(jobs, key=lambda j: j.fit_score or 0, reverse=True)[:10]:
    print(j.fit_score, j.legitimacy_score, j.title, '|', j.company)
"
```

Full `python main.py` won't run yet — it needs the Telegram and Notion
layers wired in first.

## Cost note

Legitimacy grading calls SerpApi (company presence, scam search,
reviews search, duplicate-listing search — up to 4 calls per job). To
avoid burning through the free tier, `grade_all()` only runs the full
SerpApi-backed check on jobs whose fit score clears
`FIT_SCORE_THRESHOLD_FOR_FULL_CHECK` (default 50, set in `.env`).
Trusted companies (once the Notion list exists) always get a free,
lightweight check regardless of fit score.

## Next steps

1. Notion `client.py` — unblocks the trusted-company skip-list (cheaper
   legitimacy checks) and the career-pages discovery source
2. Telegram `bot.py` / `messages.py` — send alerts for graded jobs
3. Wire discovery → grading → telegram → notion together in `main.py`
   on a schedule
4. Indeed/Prosple — revisit with a headless browser if still wanted
