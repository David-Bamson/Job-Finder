"""Central place for loading settings from environment variables (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()


# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Notion ---
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_JOBS_DATABASE_ID = os.getenv("NOTION_JOBS_DATABASE_ID")
NOTION_TRUSTED_COMPANIES_DATABASE_ID = os.getenv("NOTION_TRUSTED_COMPANIES_DATABASE_ID")

# --- Web search, used by the grading layer for reviews / scam checks ---
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# --- Email, used to read LinkedIn job alert emails via IMAP ---
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")

# --- Discovery source endpoints ---
REMOTEOK_API_URL = os.getenv("REMOTEOK_API_URL", "https://remoteok.com/api")
ARBEITNOW_API_URL = os.getenv(
    "ARBEITNOW_API_URL", "https://www.arbeitnow.com/api/job-board-api"
)
WEWORKREMOTELY_RSS_URL = os.getenv(
    "WEWORKREMOTELY_RSS_URL", "https://weworkremotely.com/remote-jobs.rss"
)

# --- Scheduler / general ---
POLL_INTERVAL_HOURS = int(os.getenv("POLL_INTERVAL_HOURS", "4"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Candidate profile, used to steer fit matching ---
PROFILE_PATH = os.getenv("PROFILE_PATH", "profile/candidate_profile.md")

# --- Cost control: only run the SerpApi-heavy legitimacy check on jobs
# whose fit score already clears this bar (or on trusted companies,
# which skip SerpApi entirely regardless of fit) ---
FIT_SCORE_THRESHOLD_FOR_FULL_CHECK = int(os.getenv("FIT_SCORE_THRESHOLD_FOR_FULL_CHECK", "50"))
