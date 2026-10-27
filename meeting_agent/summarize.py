"""Turns a raw Attendee transcript into structured English meeting notes with Claude."""

import re

import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-5-5"

SYSTEM_PROMPT = """You write meeting notes for {owner}, who may not have attended the meeting.

The transcript comes from automatic speech recognition. Speakers use English, Egyptian Arabic, \
or switch between them mid-sentence, and Arabic may appear in Arabic script or as English-letter \
transliteration. Expect recognition errors: infer the intended meaning from context, but do not \
invent facts, names, numbers, or commitments that the transcript does not support.

Write everything in clear English, regardless of the language spoken. Keep people's names as \
they appear in the speaker labels. For action items, name an owner only when the transcript makes \
it clear who took the task, and give a due date only when one was stated. When something was \
discussed but left unresolved, list it as an open question rather than a decision."""


class ActionItem(BaseModel):
    task: str
    owner: str | None
    due: str | None


class MeetingNotes(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    decisions: list[str]
    action_items: list[ActionItem]
    open_questions: list[str]
    languages_spoken: list[str]


def format_transcript(utterances: list[dict]) -> str:
    # Attendee timestamps are wall-clock epoch ms; show them relative to the first utterance.
    start_ms = min((u.get("timestamp_ms", 0) for u in utterances), default=0)
    lines = []
    for u in utterances:
        text = ((u.get("transcription") or {}).get("transcript") or "").strip()
        # Skip empty segments and ones that are only an audio tag like "[background noise]".
        if not text or re.fullmatch(r"(\[[^\]]*\]\s*)+", text):
            continue
        seconds = (u.get("timestamp_ms", 0) - start_ms) // 1000
        lines.append(f"[{seconds // 60:02d}:{seconds % 60:02d}] {u.get('speaker_name', 'Unknown')}: {text}")
    return "\n".join(lines)


def summarize(transcript_text: str, owner_name: str) -> MeetingNotes:
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=MODEL,
        # If Sonnet declines, the API reruns the request on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        max_tokens=16000,
        system=SYSTEM_PROMPT.format(owner=owner_name),
        output_config={"effort": "high"},
        messages=[
            {
                "role": "user",
                "content": f"<transcript>\n{transcript_text}\n</transcript>\n\nWrite the meeting notes.",
            }
        ],
        output_format=MeetingNotes,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined to summarize: {response.stop_details}")
    return response.parsed_output
