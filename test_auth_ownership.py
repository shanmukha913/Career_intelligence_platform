import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import auth_service
import knowledge_repository
import meeting_db


class AuthenticationOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "meetings.db"
        self.db_patch = patch.object(meeting_db, "DB_PATH", self.db_path)
        self.repo_patch = patch.object(knowledge_repository, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.repo_patch.start()
        meeting_db.init_db()
        knowledge_repository.init_knowledge_db()

    def tearDown(self):
        self.repo_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_users_can_register_login_and_revoke_sessions(self):
        user_id = auth_service.register_user("Ravi@example.com", "a-long-test-password")
        token = auth_service.authenticate_user("ravi@example.com", "a-long-test-password")
        self.assertEqual(auth_service.resolve_session(token), user_id)
        auth_service.revoke_session(token)
        self.assertIsNone(auth_service.resolve_session(token))

    def test_meeting_reads_are_scoped_to_owner(self):
        first_owner = auth_service.register_user("first@example.com", "first-long-password")
        second_owner = auth_service.register_user("second@example.com", "second-long-password")
        intelligence = {"summary": "Private notes", "participants": [], "action_items": [], "deadlines": []}
        meeting_id = meeting_db.save_meeting("private.txt", "private transcript", intelligence, owner_id=first_owner)

        self.assertEqual(len(meeting_db.recent_meetings(owner_id=first_owner)), 1)
        self.assertEqual(meeting_db.recent_meetings(owner_id=second_owner), [])
        self.assertIsNone(meeting_db.get_meeting(meeting_id, owner_id=second_owner))

    def test_meeting_analytics_are_scoped_to_owner(self):
        first_owner = auth_service.register_user("first@example.com", "first-long-password")
        second_owner = auth_service.register_user("second@example.com", "second-long-password")
        intelligence = {
            "summary": "Planning sync",
            "action_items": [{
                "task": "Prepare report",
                "assignee": "Ravi",
                "deadline": "Friday",
                "priority": "High",
                "status": "Pending",
            }],
            "deadlines": [{"item": "Report", "due_date": "Friday"}],
            "participants": [
                {"name": "Ravi", "responsibilities": "Prepare report"},
                {"name": "Ravi", "responsibilities": "Prepare report"},
            ],
        }
        meeting_db.save_meeting("first.wav", "Ravi will prepare the report.", intelligence, owner_id=first_owner)
        meeting_db.save_meeting("second.wav", "Private meeting transcript.", {"summary": "Private"}, owner_id=second_owner)

        first_analytics = meeting_db.meeting_analytics(first_owner)
        second_analytics = meeting_db.meeting_analytics(second_owner)

        self.assertEqual(first_analytics["meetings"], 1)
        self.assertEqual(first_analytics["action_items"], 1)
        self.assertEqual(first_analytics["deadlines"], 1)
        self.assertEqual(first_analytics["participants"], 1)
        self.assertEqual(second_analytics["meetings"], 1)
        self.assertEqual(second_analytics["action_items"], 0)
        self.assertEqual(len(first_analytics["weekly_activity"]), 8)

    def test_registration_rejects_short_password(self):
        with self.assertRaises(ValueError):
            auth_service.register_user("weak@example.com", "short")

    def test_private_meeting_data_is_not_visible_to_other_users(self):
        first_owner = auth_service.register_user("first@example.com", "first-long-password")
        second_owner = auth_service.register_user("second@example.com", "second-long-password")
        transcript = "The private release plan is due Friday. Ravi owns the API integration."
        intelligence = {
            "summary": "Private release plan",
            "key_points": ["Release plan due Friday"],
            "decisions": [],
            "action_items": [{"task": "API integration", "assignee": "Ravi", "deadline": "Friday", "priority": "High", "status": "Pending"}],
            "participants": [{"name": "Ravi", "responsibilities": "API integration"}],
            "deadlines": [{"item": "API integration", "due_date": "Friday"}],
            "priorities": ["High"],
            "meeting_points": [],
        }
        meeting_id = meeting_db.save_meeting("private.mp3", transcript, intelligence, owner_id=first_owner)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)

        self.assertEqual(len(meeting_db.recent_meetings(owner_id=first_owner)), 1)
        self.assertEqual(meeting_db.recent_meetings(owner_id=second_owner), [])
        self.assertIsNone(meeting_db.get_meeting(meeting_id, owner_id=second_owner))
        self.assertEqual(knowledge_repository.semantic_search("private release plan", owner_id=second_owner), [])
        self.assertEqual(knowledge_repository.answer_question("What is the private release plan?", owner_id=second_owner)["sources"], [])

    def test_existing_meeting_database_is_migrated_in_place(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            "CREATE TABLE meetings (id INTEGER PRIMARY KEY, filename TEXT NOT NULL, transcript TEXT NOT NULL, "
            "intelligence_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.commit()
        connection.close()
        with patch.object(meeting_db, "DB_PATH", legacy_path):
            meeting_db.init_db()
            connection = sqlite3.connect(legacy_path)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(meetings)")}
            connection.close()
        self.assertTrue({"owner_id", "source", "external_id"}.issubset(columns))


if __name__ == "__main__":
    unittest.main()
