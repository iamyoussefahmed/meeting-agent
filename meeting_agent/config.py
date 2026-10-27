"""Settings loaded from the project's .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name} in .env (see .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    attendee_url: str
    attendee_api_key: str
    bot_name: str
    smtp_user: str
    smtp_app_password: str
    email_to: str
    owner_name: str
    calendar_ics_url: str
    bot_calendar_email: str
    company_domains: tuple[str, ...]
    data_dir: Path


def load_settings() -> Settings:
    return Settings(
        attendee_url=os.getenv("ATTENDEE_URL", "http://localhost:8000").rstrip("/"),
        attendee_api_key=_require("ATTENDEE_API_KEY"),
        bot_name=os.getenv("BOT_NAME", "Notetaker"),
        smtp_user=_require("GMAIL_BOT_ADDRESS"),
        smtp_app_password=_require("GMAIL_APP_PASSWORD").replace(" ", ""),
        email_to=_require("EMAIL_TO"),
        owner_name=os.getenv("OWNER_NAME", "the organizer"),
        calendar_ics_url=os.getenv("BOT_CALENDAR_ICS_URL", "").strip(),
        # The address people invite. Can differ from the sending address.
        bot_calendar_email=(os.getenv("BOT_CALENDAR_EMAIL") or os.getenv("GMAIL_BOT_ADDRESS", "")).strip(),
        # Invitees on these comma-separated domains also get the notes. Empty means only EMAIL_TO does.
        company_domains=tuple(
            d.strip().lower().lstrip("@") for d in os.getenv("COMPANY_DOMAINS", "").split(",") if d.strip()
        ),
        data_dir=PROJECT_ROOT / "data",
    )
