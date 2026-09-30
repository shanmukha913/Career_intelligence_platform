import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
import knowledge_repository
import llm_service
import meeting_db


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "meetings.db"
        self.db_patch = patch.object(meeting_db, "DB_PATH", self.db_path)
        self.repo_patch = patch.object(knowledge_repository, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.repo_patch.start()
        meeting_db.init_db()
        knowledge_repository.init_knowledge_db()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.repo_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_meeting_listing_and_detail_endpoints(self):
        transcript = "The mobile application deadline is Friday and Ravi will complete API integration."
        intelligence = llm_service.process_transcript(transcript)
        meeting_id = meeting_db.save_meeting("mobile.mp3", transcript, intelligence)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)

        list_response = self.client.get("/meetings")
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(list_response.json()["meetings"])

        detail_response = self.client.get(f"/meetings/{meeting_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["meeting"]["id"], meeting_id)
        self.assertIn("mobile.mp3", detail_response.json()["meeting"]["filename"])

    def test_search_and_ask_are_integrated_with_existing_backend(self):
        transcript = "The database migration will be reviewed by Ravi on Friday."
        intelligence = llm_service.process_transcript(transcript)
        meeting_id = meeting_db.save_meeting("migration.mp3", transcript, intelligence)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)

        search_response = self.client.get("/search", params={"query": "Which meeting discussed database migration?", "limit": 5})
        self.assertEqual(search_response.status_code, 200)
        self.assertTrue(search_response.json()["results"])

        ask_response = self.client.post("/ask", json={"question": "Which meeting discussed database migration?"})
        self.assertEqual(ask_response.status_code, 200)
        self.assertIn("migration", ask_response.json()["answer"].lower())

    def test_empty_question_is_rejected_cleanly(self):
        response = self.client.post("/ask", json={"question": "   "})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Question cannot be empty", response.json()["detail"])

    def test_production_api_fails_closed_without_authentication_config(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            response = self.client.get("/meetings")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Login is required", response.json()["detail"])

    def test_authenticated_users_cannot_read_other_meetings_or_rag_context(self):
        first_registration = self.client.post("/auth/register", json={
            "email": "first@example.com",
            "password": "first-long-test-password",
        })
        second_registration = self.client.post("/auth/register", json={
            "email": "second@example.com",
            "password": "second-long-test-password",
        })
        self.assertEqual(first_registration.status_code, 200)
        self.assertEqual(second_registration.status_code, 200)
        first_token = self.client.post("/auth/token", json={
            "email": "first@example.com",
            "password": "first-long-test-password",
        }).json()["access_token"]
        second_token = self.client.post("/auth/token", json={
            "email": "second@example.com",
            "password": "second-long-test-password",
        }).json()["access_token"]

        created = self.client.post(
            "/process-transcript",
            headers={"Authorization": f"Bearer {first_token}"},
            json={"filename": "private-migration.txt", "transcript": "The private database migration deadline is Friday."},
        )
        meeting_id = created.json()["meeting_id"]
        second_headers = {"Authorization": f"Bearer {second_token}"}

        self.assertEqual(self.client.get("/meetings", headers=second_headers).json()["meetings"], [])
        self.assertEqual(self.client.get(f"/meetings/{meeting_id}", headers=second_headers).status_code, 404)
        search = self.client.get("/search", params={"query": "private database migration"}, headers=second_headers)
        self.assertEqual(search.json()["results"], [])
        answer = self.client.post("/ask", json={"question": "What is the private database migration deadline?"}, headers=second_headers)
        self.assertEqual(answer.json()["sources"], [])

    def test_logout_revokes_bearer_session_and_admin_cannot_import_for_a_user(self):
        registered = self.client.post("/auth/register", json={
            "email": "logout@example.com",
            "password": "a-long-logout-password",
        })
        self.assertEqual(registered.status_code, 200)
        token = self.client.post("/auth/token", json={
            "email": "logout@example.com",
            "password": "a-long-logout-password",
        }).json()["access_token"]
        user_headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.post("/auth/logout", headers=user_headers).status_code, 200)
        self.assertEqual(self.client.get("/auth/me", headers=user_headers).status_code, 401)

        with patch.dict(os.environ, {"APP_ENV": "production", "MEETING_API_KEY": "admin-secret"}):
            response = self.client.post(
                "/integrations/zoom/sync",
                headers={"Authorization": "Bearer admin-secret"},
            )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
