"""Sends the meeting notes from the bot's Gmail account over SMTP."""

import smtplib
from email.message import EmailMessage
from html import escape

from .summarize import MeetingNotes


def _list(items: list[str]) -> str:
    if not items:
        return "<p><em>None</em></p>"
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def render_html(notes: MeetingNotes, meeting_url: str, started: str) -> str:
    if notes.action_items:
        rows = "".join(
            f"<tr><td>{escape(a.task)}</td><td>{escape(a.owner or '-')}</td><td>{escape(a.due or '-')}</td></tr>"
            for a in notes.action_items
        )
        actions = (
            '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">'
            "<tr><th align=left>Task</th><th align=left>Owner</th><th align=left>Due</th></tr>"
            f"{rows}</table>"
        )
    else:
        actions = "<p><em>None</em></p>"
    return f"""<div style="font-family:Arial,sans-serif;max-width:720px">
<h2>{escape(notes.title)}</h2>
<p style="color:#666">{escape(started)} &middot; <a href="{escape(meeting_url)}">{escape(meeting_url)}</a>
&middot; Languages: {escape(", ".join(notes.languages_spoken) or "-")}</p>
<h3>Summary</h3><p>{escape(notes.summary)}</p>
<h3>Action items</h3>{actions}
<h3>Decisions</h3>{_list(notes.decisions)}
<h3>Key points</h3>{_list(notes.key_points)}
<h3>Open questions</h3>{_list(notes.open_questions)}
<p style="color:#999;font-size:12px">Full transcript attached.</p>
</div>"""


def _send(smtp_user: str, app_password: str, msg: EmailMessage) -> None:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(smtp_user, app_password)
        smtp.send_message(msg)


def send_no_speech(*, smtp_user: str, app_password: str, to: str, meeting_url: str, title: str, reason: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"No notes: {title}"
    msg["From"] = smtp_user
    msg["To"] = to
    msg.set_content(f"The notetaker could not produce notes for {meeting_url}.\n\nReason: {reason}\n")
    _send(smtp_user, app_password, msg)


def send_notes(
    *,
    smtp_user: str,
    app_password: str,
    to: list[str],
    notes: MeetingNotes,
    meeting_url: str,
    started: str,
    transcript_text: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"Meeting notes: {notes.title}"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(to)
    msg.set_content(notes.summary)
    msg.add_alternative(render_html(notes, meeting_url, started), subtype="html")
    msg.add_attachment(
        transcript_text.encode("utf-8"), maintype="text", subtype="plain", filename="transcript.txt"
    )
    _send(smtp_user, app_password, msg)
