"""Command line entry point.

    python -m meeting_agent watch              join every meeting the bot's calendar is invited to
    python -m meeting_agent upcoming           list the invited meetings the watcher can see right now
    python -m meeting_agent join <meet-url>    send the bot to one meeting now
    python -m meeting_agent notes <bot-id>     (re)build and email notes for a finished bot
"""

import argparse
from datetime import datetime, timedelta, timezone

from .attendee_client import AttendeeClient
from .config import load_settings
from .pipeline import build_and_send_notes, run_meeting


def main() -> None:
    parser = argparse.ArgumentParser(prog="meeting_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("watch", help="auto-join meetings the bot is invited to")
    sub.add_parser("upcoming", help="show invited meetings in the next 7 days")
    join = sub.add_parser("join", help="send the bot to a Google Meet and email notes afterwards")
    join.add_argument("meeting_url")
    notes = sub.add_parser("notes", help="build and email notes for a bot that already finished")
    notes.add_argument("bot_id")
    args = parser.parse_args()

    settings = load_settings()
    client = AttendeeClient(settings.attendee_url, settings.attendee_api_key)

    if args.command == "watch":
        from .calendar_watch import Watcher

        Watcher(settings).run_forever()
    elif args.command == "upcoming":
        from . import calendar_watch

        # Widen the window to preview the week ahead.
        calendar_watch.JOIN_BEFORE = timedelta(days=7)
        meetings = calendar_watch.upcoming_meetings(
            settings.calendar_ics_url, settings.bot_calendar_email, datetime.now(timezone.utc)
        )
        for m in sorted(meetings, key=lambda m: m.start):
            print(f"{m.start.astimezone():%a %d %b %H:%M}  {m.title}  {m.url}")
        if not meetings:
            print("No invited meetings with a Meet link in the next 7 days.")
    elif args.command == "join":
        run_meeting(client, settings, args.meeting_url)
    else:
        bot = client.get_bot(args.bot_id)
        build_and_send_notes(client, args.bot_id, bot.get("meeting_url", ""), settings)


if __name__ == "__main__":
    main()
