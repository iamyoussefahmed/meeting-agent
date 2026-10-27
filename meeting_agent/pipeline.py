"""One meeting end to end: send the bot, wait for the meeting to end, email the notes."""

import json
import time
from datetime import datetime

from .attendee_client import FINAL_STATES, IN_CALL_STATES, AttendeeClient
from .config import Settings
from .emailer import send_no_speech, send_notes
from .summarize import format_transcript, summarize

POLL_SECONDS = 15


def notes_recipients(settings: Settings, invitees: tuple[str, ...] = ()) -> list[str]:
    """The owner, plus invitees on a company domain. External addresses never get notes."""
    skip = {settings.bot_calendar_email.lower(), settings.smtp_user.lower()}
    recipients = [settings.email_to.lower()]
    for email in invitees:
        email = email.lower()
        # Exact domain match: "acme.com" must not match "x@notacme.com" or "x@acme.com.evil.io".
        if email.rsplit("@", 1)[-1] in settings.company_domains and email not in skip:
            recipients.append(email)
    return list(dict.fromkeys(recipients))


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def wait_for_meeting(client: AttendeeClient, bot_id: str, settings: Settings) -> str:
    """Polls until the bot finishes. Returns the final state."""
    last_state, announced = None, False
    while True:
        state = client.get_bot(bot_id)["state"]
        if state != last_state:
            log(f"{bot_id} state: {state}")
            last_state = state
        if state in IN_CALL_STATES and not announced:
            try:
                client.send_chat_message(
                    bot_id,
                    f"Hi, I'm {settings.owner_name}'s notetaker. I'm transcribing this meeting "
                    f"so {settings.owner_name} gets a summary afterwards.",
                )
            except RuntimeError as e:
                log(f"{bot_id} could not post chat notice: {e}")
            announced = True
        if state in FINAL_STATES:
            return state
        time.sleep(POLL_SECONDS)


def build_and_send_notes(
    client: AttendeeClient,
    bot_id: str,
    meeting_url: str,
    settings: Settings,
    title: str | None = None,
    invitees: tuple[str, ...] = (),
) -> None:
    recipients = notes_recipients(settings, invitees)
    utterances = client.get_transcript(bot_id)
    transcript_text = format_transcript(utterances)

    out_dir = settings.data_dir / bot_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "transcript.json").write_text(json.dumps(utterances, ensure_ascii=False, indent=2))
    (out_dir / "transcript.txt").write_text(transcript_text)

    if not transcript_text:
        state = client.get_bot(bot_id)["state"]
        reason = (
            "The bot hit an error. Check the Attendee dashboard."
            if state == "fatal_error"
            else "No speech was captured. The bot may not have been admitted, or nobody spoke while it was there."
        )
        log(f"{bot_id} empty transcript; sending notice")
        # Only the owner hears about failed meetings.
        send_no_speech(
            smtp_user=settings.smtp_user,
            app_password=settings.smtp_app_password,
            to=settings.email_to,
            meeting_url=meeting_url,
            title=title or meeting_url,
            reason=reason,
        )
        return

    log(f"{bot_id} summarizing {len(utterances)} utterances with Claude")
    notes = summarize(transcript_text, settings.owner_name)
    (out_dir / "notes.json").write_text(notes.model_dump_json(indent=2))

    send_notes(
        smtp_user=settings.smtp_user,
        app_password=settings.smtp_app_password,
        to=recipients,
        notes=notes,
        meeting_url=meeting_url,
        started=datetime.now().strftime("%a %d %b %Y"),
        transcript_text=transcript_text,
    )
    log(f"{bot_id} notes emailed to {', '.join(recipients)} (saved in {out_dir})")


def run_meeting(
    client: AttendeeClient,
    settings: Settings,
    meeting_url: str,
    title: str | None = None,
    invitees: tuple[str, ...] = (),
) -> None:
    bot = client.create_bot(meeting_url, settings.bot_name)
    log(f"{bot['id']} created for {title or meeting_url}; waiting to be admitted")
    state = wait_for_meeting(client, bot["id"], settings)
    if state == "fatal_error":
        log(f"{bot['id']} hit a fatal error; check the Attendee dashboard at {settings.attendee_url}")
    build_and_send_notes(client, bot["id"], meeting_url, settings, title, invitees)
