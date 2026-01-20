import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.integrations.google_calendar import _build_event_payload, _normalize_datetime  # noqa: E402


class GoogleCalendarPayloadTests(unittest.TestCase):
    def test_meeting_url_included(self) -> None:
        payload = {
            "attendee": "hiroshi.inoue@is-tech.co.jp",
            "title": "Nemawashi sync",
            "start_at": "2026-01-21T10:00:00",
            "end_at": "2026-01-21T11:00:00",
            "timezone": "Asia/Tokyo",
            "description": "Agenda: review",
            "meeting_url": "https://meet.example.com/abc",
        }
        event = _build_event_payload(payload, include_conference=False)
        self.assertEqual(event.get("location"), "https://meet.example.com/abc")
        self.assertIn("Meeting URL: https://meet.example.com/abc", event.get("description", ""))

    def test_timezone_normalization(self) -> None:
        dt = _normalize_datetime("2026-01-21T10:00:00", "Asia/Tokyo")
        self.assertTrue(dt.isoformat().endswith("+09:00"))

    def test_conference_data_added_when_requested(self) -> None:
        payload = {
            "attendee": "hiroshi.inoue@is-tech.co.jp",
            "title": "Nemawashi sync",
            "start_at": "2026-01-21T10:00:00+09:00",
            "end_at": "2026-01-21T11:00:00+09:00",
            "timezone": "Asia/Tokyo",
            "description": "Agenda: review",
        }
        event = _build_event_payload(payload, include_conference=True)
        self.assertIn("conferenceData", event)


if __name__ == "__main__":
    unittest.main()
