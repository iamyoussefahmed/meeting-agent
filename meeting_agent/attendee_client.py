"""Thin wrapper around the self-hosted Attendee REST API."""

import requests

# States after which the bot will not produce more transcript.
FINAL_STATES = {"ended", "fatal_error", "data_deleted"}
IN_CALL_STATES = {"joined_recording", "joined_not_recording", "joined_recording_paused"}


class AttendeeClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
        )

    def _request(self, method: str, path: str, **kwargs):
        resp = self.session.request(method, f"{self.base_url}/api/v1{path}", timeout=30, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"Attendee {method} {path} failed ({resp.status_code}): {resp.text}")
        return resp.json() if resp.content else None

    def create_bot(self, meeting_url: str, bot_name: str) -> dict:
        return self._request(
            "POST",
            "/bots",
            json={
                "meeting_url": meeting_url,
                "bot_name": bot_name,
                # No language_code: Scribe auto-detects per segment, which handles
                # English, Egyptian Arabic, and speakers switching between them.
                "transcription_settings": {
                    "elevenlabs": {"model_id": "scribe_v1", "tag_audio_events": False}
                },
                "automatic_leave_settings": {
                    "waiting_room_timeout_seconds": 900,
                    "only_participant_in_meeting_timeout_seconds": 60,
                },
            },
        )

    def get_bot(self, bot_id: str) -> dict:
        return self._request("GET", f"/bots/{bot_id}")

    def get_transcript(self, bot_id: str) -> list[dict]:
        return self._request("GET", f"/bots/{bot_id}/transcript")

    def send_chat_message(self, bot_id: str, message: str) -> None:
        self._request("POST", f"/bots/{bot_id}/send_chat_message", json={"message": message})
