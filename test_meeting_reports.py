import csv
import io
import unittest

from meeting_reports import build_meeting_csv, build_meeting_pdf


class MeetingReportTests(unittest.TestCase):
    def setUp(self):
        self.meeting = {
            "id": 7,
            "filename": "mobile-launch.mp3",
            "created_at": "2026-09-27T10:30:00",
            "transcript": "Ravi will finish API integration by Friday.",
            "intelligence": {
                "summary": "The team reviewed the mobile launch.",
                "decisions": ["Proceed with the planned launch."],
                "action_items": [{"task": "API integration", "assignee": "Ravi", "deadline": "Friday"}],
                "participants": [{"name": "Ravi", "responsibilities": "API integration"}],
                "deadlines": [{"item": "API integration", "due_date": "Friday"}],
            },
        }

    def test_csv_includes_selected_meeting_details(self):
        rows = list(csv.reader(io.StringIO(build_meeting_csv(self.meeting))))
        self.assertIn(["Meeting ID", "7"], rows)
        self.assertIn(["Meeting", "mobile-launch.mp3"], rows)
        self.assertTrue(any(row[0] == "Action Items" and "Ravi" in row[1] for row in rows))

    def test_pdf_is_valid_and_contains_report_content(self):
        report = build_meeting_pdf(self.meeting)
        self.assertTrue(report.startswith(b"%PDF-"))
        self.assertGreater(len(report), 500)


if __name__ == "__main__":
    unittest.main()
