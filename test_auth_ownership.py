import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import auth_service
import meeting_db


class AuthenticationOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "meetings.db"
        self.db_patch = patch.object(meeting_db, "DB_PATH", self.db_path)
        self.db_patch.start()
        meeting_db.init_db()

    def tearDown(self):
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

    def test_registration_rejects_short_password(self):
        with self.assertRaises(ValueError):
            auth_service.register_user("weak@example.com", "short")

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
