"""Watches the bot's Google Calendar and sends the bot to every meeting it is invited to.

The calendar is read through its "Secret address in iCal format", so no Google
Cloud project or OAuth is needed. Each meeting runs in its own thread, so
overlapping meetings are handled.
"""

import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import recurring_ical_events
import requests
from icalendar import Calendar

from .attendee_client import AttendeeClient
from .config import Settings
from .pipeline import log, run_meeting

CHECK_SECONDS = 60
JOIN_BEFORE = timedelta(minutes=1)
# Still join if the watcher notices a meeting this long after it started
# (for example, the Mac just woke up or the invite arrived late).
JOIN_LATE_UP_TO = timedelta(minutes=15)

MEET_URL = re.compile(r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}")


@dataclass(frozen=True)
class Meeting:
    key: str
    title: str
    start: datetime
    url: str
    invitees: tuple[str, ...]


def _attendees(event) -> list:
    attendees = event.get("ATTENDEE", [])
    return attendees if isinstance(attendees, list) else [attendees]


def _invitee_emails(event) -> tuple[str, ...]:
    emails = [str(a).removeprefix("mailto:").removeprefix("MAILTO:").lower() for a in _attendees(event)]
    organizer = event.get("ORGANIZER")
    if organizer:
        emails.append(str(organizer).removeprefix("mailto:").removeprefix("MAILTO:").lower())
    return tuple(dict.fromkeys(e for e in emails if "@" in e))


def _meet_url(event) -> str | None:
    for field in ("X-GOOGLE-CONFERENCE", "LOCATION", "DESCRIPTION"):
        match = MEET_URL.search(str(event.get(field, "")))
        if match:
            return match.group(0)
    return None


def _declined_by_bot(event, bot_address: str) -> bool:
    for a in _attendees(event):
        if str(a).lower() == f"mailto:{bot_address.lower()}":
            return str(a.params.get("PARTSTAT", "")).upper() == "DECLINED"
    return False


def upcoming_meetings(ics_url: str, bot_address: str, now: datetime) -> list[Meeting]:
    resp = requests.get(ics_url, timeout=30)
    resp.raise_for_status()
    calendar = Calendar.from_ical(resp.content)
    window = recurring_ical_events.of(calendar).between(now - JOIN_LATE_UP_TO, now + JOIN_BEFORE)

    meetings = []
    for event in window:
        start = event.get("DTSTART").dt
        if not isinstance(start, datetime):
            continue  # all-day events have no start time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if str(event.get("STATUS", "")).upper() == "CANCELLED" or _declined_by_bot(event, bot_address):
            continue
        url = _meet_url(event)
        if not url:
            continue
        meetings.append(
            Meeting(
                key=f"{event.get('UID')}@{start.isoformat()}",
                title=str(event.get("SUMMARY", "Meeting")),
                start=start,
                url=url,
                invitees=_invitee_emails(event),
            )
        )
    return meetings


class Watcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AttendeeClient(settings.attendee_url, settings.attendee_api_key)
        self.state_file = settings.data_dir / "joined_events.json"
        self.joined: dict[str, str] = (
            json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        )

    def _remember(self, meeting: Meeting) -> None:
        self.joined[meeting.key] = datetime.now(timezone.utc).isoformat()
        # Forget entries older than a week so the file stays small.
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self.joined = {k: v for k, v in self.joined.items() if datetime.fromisoformat(v) > cutoff}
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.joined, indent=2))

    def _run(self, meeting: Meeting) -> None:
        try:
            run_meeting(self.client, self.settings, meeting.url, meeting.title, meeting.invitees)
        except Exception as e:  # keep the watcher alive whatever one meeting does
            log(f"meeting '{meeting.title}' failed: {e!r}")

    def check_once(self) -> None:
        now = datetime.now(timezone.utc)
        for meeting in upcoming_meetings(self.settings.calendar_ics_url, self.settings.bot_calendar_email, now):
            if meeting.key in self.joined:
                continue
            log(f"joining '{meeting.title}' (starts {meeting.start.astimezone():%H:%M}) at {meeting.url}")
            self._remember(meeting)
            threading.Thread(target=self._run, args=(meeting,), daemon=True).start()

    def run_forever(self) -> None:
        log(f"watching the bot's calendar every {CHECK_SECONDS}s")
        while True:
            try:
                self.check_once()
            except Exception as e:  # network blips, Attendee restarting, etc.
                log(f"calendar check failed: {e!r}")
            time.sleep(CHECK_SECONDS)
