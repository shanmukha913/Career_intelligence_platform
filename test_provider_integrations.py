import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import knowledge_repository
import meeting_db
import provider_integrations


class FakeResponse:
    def __init__(self, payload=None, content=b"meeting audio bytes"):
        self.payload = payload or {}
        self.content = content
        self.headers = {"Content-Length": str(len(content))}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload

    def iter_content(self, chunk_size):
        yield self.content


class ProviderIntegrationTests(unittest.TestCase):
    def setUp(self):
        provider_integrations.load_whisper_model.cache_clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "meetings.db"
        self.db_patch = patch.object(meeting_db, "DB_PATH", self.db_path)
        self.repo_patch = patch.object(knowledge_repository, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.repo_patch.start()
        meeting_db.init_db()
        knowledge_repository.init_knowledge_db()

    def tearDown(self):
        provider_integrations.load_whisper_model.cache_clear()
        self.repo_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_zoom_sync_transcribes_persists_and_skips_duplicate_recording(self):
        credentials = {
            "ZOOM_ACCOUNT_ID": "account",
            "ZOOM_CLIENT_ID": "client",
            "ZOOM_CLIENT_SECRET": "secret",
            "ZOOM_USER_ID": "me",
        }
        recording_page = FakeResponse({
            "meetings": [{
                "uuid": "zoom-meeting",
                "id": 123,
                "recording_files": [{"id": "file-1", "file_type": "MP4", "file_name": "launch.mp4", "download_url": "https://us06web.zoom.us/rec/download/file-1"}],
            }]
        })
        media_response = FakeResponse()
        with patch.dict("os.environ", credentials):
            with patch.object(provider_integrations.requests, "post", return_value=FakeResponse({"access_token": "zoom-token"})) as post_request:
                with patch.object(provider_integrations.requests, "get", side_effect=[recording_page, media_response, recording_page]) as get_request:
                    with patch("whisper.load_model") as load_model:
                        load_model.return_value.transcribe.return_value = {"text": "Ravi will finish the mobile launch report by Friday."}
                        first = provider_integrations.sync_zoom_recordings(owner_id=9)
                        second = provider_integrations.sync_zoom_recordings(owner_id=9)

        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(len(meeting_db.recent_meetings(owner_id=9)), 1)
        self.assertEqual(post_request.call_count, 2)
        self.assertEqual(get_request.call_count, 3)

    def test_google_drive_meet_sync_imports_recording(self):
        credentials = {
            "GOOGLE_CLIENT_ID": "client",
            "GOOGLE_CLIENT_SECRET": "secret",
            "GOOGLE_REFRESH_TOKEN": "refresh",
            "GOOGLE_MEET_RECORDINGS_FOLDER_ID": "meet-recordings-folder",
        }
        list_response = FakeResponse({"files": [{"id": "drive-file-1", "name": "Team meeting.mp4", "mimeType": "video/mp4"}]})
        media_response = FakeResponse()
        with patch.dict("os.environ", credentials):
            with patch.object(provider_integrations.requests, "post", return_value=FakeResponse({"access_token": "google-token"})):
                with patch.object(provider_integrations.requests, "get", side_effect=[list_response, media_response]):
                    with patch("whisper.load_model") as load_model:
                        load_model.return_value.transcribe.return_value = {"text": "Priya will prepare the UI testing report by Friday."}
                        result = provider_integrations.sync_google_meet_recordings(owner_id=11)

        self.assertEqual(result["imported"], 1)
        self.assertEqual(len(meeting_db.recent_meetings(owner_id=11)), 1)
        self.assertEqual(meeting_db.recent_meetings(owner_id=11)[0]["filename"], "Team meeting.mp4")

    def test_untrusted_download_hosts_are_rejected(self):
        with self.assertRaises(ValueError):
            provider_integrations._download_recording("https://example.com/audio.mp4", {}, ("zoom.us",))

    def test_duplicate_import_repairs_missing_embeddings_without_redownload(self):
        transcript = "The database migration deadline is Friday."
        intelligence = {"summary": transcript, "decisions": [], "action_items": [], "participants": [], "deadlines": []}
        meeting_id = meeting_db.save_meeting(
            "migration.mp4", transcript, intelligence, owner_id=13, source="zoom", external_id="zoom-13"
        )
        with patch.object(provider_integrations.requests, "get") as get_request:
            result = provider_integrations._import_one(
                "zoom", "zoom-13", "migration.mp4", "https://example.zoom.us/file", {}, 13, "base", ("zoom.us",)
            )

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["meeting_id"], meeting_id)
        self.assertTrue(knowledge_repository.semantic_search("database migration", owner_id=13))
        get_request.assert_not_called()

    def test_transcription_failure_is_reported_without_persisting_record(self):
        with patch.object(provider_integrations.requests, "get", return_value=FakeResponse()):
            with patch("whisper.load_model", side_effect=RuntimeError("model unavailable")):
                result = provider_integrations._import_one(
                    "google_meet", "file-failed", "failed.mp4", "https://drive.googleapis.com/file", {}, 15, "base", ("googleapis.com",)
                )

        self.assertEqual(result["status"], "failed")
        self.assertIn("model unavailable", result["error"])
        self.assertEqual(meeting_db.recent_meetings(owner_id=15), [])


if __name__ == "__main__":
    unittest.main()
