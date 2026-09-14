import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import llm_service
import meeting_db


class Milestone2Tests(unittest.TestCase):
    def test_schema_and_extraction(self):
        result = llm_service.process_transcript(
            "The team agreed to launch the app. Ravi will complete API integration by Friday. "
            "Priya is responsible for UI testing."
        )
        self.assertEqual(
            set(result),
            {"summary", "key_points", "decisions", "action_items", "participants", "deadlines", "priorities", "meeting_points"},
        )
        self.assertTrue(any(item["assignee"] == "Ravi" for item in result["action_items"]))
        self.assertTrue(any(item["name"] == "Priya" for item in result["participants"]))

    def test_unknown_and_duplicate_participants_are_safe(self):
        result = llm_service.validate_structured_output({
            "participants": [
                {"name": "Ravi", "responsibilities": "API"},
                {"name": "Ravi", "responsibilities": "API"},
                {"responsibilities": "Testing"},
            ]
        })
        self.assertEqual(len(result["participants"]), 2)
        self.assertEqual(result["participants"][1]["name"], "Unknown")

    def test_long_transcript_local_fallback(self):
        result = llm_service.process_transcript("Ravi will complete testing by Friday. " * 500)
        self.assertIn("action_items", result)
        self.assertTrue(result["action_items"])

    def test_database_persists_linked_records(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "meetings.db"
            with patch.object(meeting_db, "DB_PATH", database_path):
                intelligence = llm_service.process_transcript("Ravi will complete testing by Friday.")
                meeting_id = meeting_db.save_meeting("test.mp3", "Ravi will complete testing by Friday.", intelligence)
                connection = sqlite3.connect(database_path)
                try:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM meetings").fetchone()[0], 1)
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM action_items WHERE meeting_id = ?", (meeting_id,)).fetchone()[0], 1)
                finally:
                    connection.close()


if __name__ == "__main__":
    unittest.main()
