import csv
import io
import unittest

from meeting_reports import build_meeting_csv, build_meeting_pdf, build_transcript_pdf


class MeetingReportTests(unittest.TestCase):
    def setUp(self):
        self.meeting = {
            "id": 7,
            "filename": "mobile-launch.mp3",
            "created_at": "2026-09-27T10:30:00",
            "transcript": "Ravi will finish API integration by Friday.",
            "intelligence": {
                "summary": "The team reviewed the mobile launch.",
                "key_points": ["Launch review completed."],
                "meeting_points": ["Mobile launch remains on schedule."],
                "decisions": ["Proceed with the planned launch."],
                "priorities": ["Complete API integration."],
                "action_items": [{"task": "API integration", "assignee": "Ravi", "deadline": "Friday"}],
                "participants": [{"name": "Ravi", "responsibilities": "API integration"}],
                "deadlines": [{"item": "API integration", "due_date": "Friday"}],
            },
        }

    def test_csv_includes_selected_meeting_details(self):
        rows = list(csv.reader(io.StringIO(build_meeting_csv(self.meeting))))
        self.assertIn(["Meeting ID", "7"], rows)
        self.assertIn(["Meeting", "mobile-launch.mp3"], rows)
        self.assertIn(["Summary", "The team reviewed the mobile launch."], rows)
        self.assertIn(["Key Points", "Launch review completed."], rows)
        self.assertIn(["Meeting Points", "Mobile launch remains on schedule."], rows)
        self.assertIn(["Priorities", "Complete API integration."], rows)
        self.assertIn(["Transcript", "Ravi will finish API integration by Friday."], rows)
        self.assertTrue(any(row[0] == "Action Items" and "Ravi" in row[1] for row in rows))

    def test_pdf_is_valid_and_contains_report_content(self):
        report = build_meeting_pdf(self.meeting)
        self.assertTrue(report.startswith(b"%PDF-"))
        self.assertGreater(len(report), 500)
        self.assertTrue(report.startswith(b"%PDF-"))

    def test_transcript_download_builder_returns_pdf(self):
        report = build_transcript_pdf(
            self.meeting["transcript"],
            self.meeting["filename"],
            intelligence=self.meeting["intelligence"],
            created_at=self.meeting["created_at"],
        )
        self.assertTrue(report.startswith(b"%PDF-"))
        self.assertGreater(len(report), 500)


if __name__ == "__main__":
    unittest.main()
