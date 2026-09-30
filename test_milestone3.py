import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import knowledge_repository
import llm_service
import meeting_db


class Milestone3Tests(unittest.TestCase):
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

    def test_index_and_linked_semantic_search(self):
        transcript = "The database migration will be reviewed by Ravi on Friday."
        intelligence = llm_service.process_transcript(transcript)
        meeting_id = meeting_db.save_meeting("migration.mp3", transcript, intelligence)
        count = knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)
        started = time.perf_counter()
        results = knowledge_repository.semantic_search("Which meeting discussed database migration?")
        elapsed = time.perf_counter() - started
        self.assertGreater(count, 0)
        self.assertTrue(results)
        self.assertEqual(results[0]["meeting_id"], meeting_id)
        self.assertLess(elapsed, 3)

    def test_update_and_delete_vectors(self):
        intelligence = llm_service.process_transcript("The API launch is planned for Friday.")
        meeting_id = meeting_db.save_meeting("api.mp3", "The API launch is planned for Friday.", intelligence)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, "The API launch is planned for Friday.", intelligence)
        updated = llm_service.process_transcript("The database migration is planned for Monday.")
        knowledge_repository.upsert_meeting_embeddings(meeting_id, "The database migration is planned for Monday.", updated)
        self.assertTrue(knowledge_repository.semantic_search("database migration", meeting_id=meeting_id))
        self.assertGreater(knowledge_repository.delete_meeting_embeddings(meeting_id), 0)
        self.assertFalse(knowledge_repository.semantic_search("database migration", meeting_id=meeting_id))

    def test_rag_answer_is_retrieved_and_grounded(self):
        transcript = "The mobile application deadline is Friday."
        intelligence = llm_service.process_transcript(transcript)
        meeting_id = meeting_db.save_meeting("mobile.mp3", transcript, intelligence)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)
        result = knowledge_repository.answer_question("What is the mobile application deadline?")
        self.assertIn("Friday", result["answer"])
        self.assertTrue(result["sources"])
        self.assertEqual(result["sources"][0]["meeting_id"], meeting_id)

    def test_unrelated_search_and_question_return_no_meeting_context(self):
        transcript = "The mobile application deadline is Friday."
        intelligence = llm_service.process_transcript(transcript)
        meeting_id = meeting_db.save_meeting("mobile.mp3", transcript, intelligence)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)

        self.assertEqual(knowledge_repository.semantic_search("What is the orbital telescope budget?"), [])
        answer = knowledge_repository.answer_question("What is the orbital telescope budget?")
        self.assertEqual(answer["sources"], [])

    def test_rag_fallback_returns_relevant_points_not_full_transcript(self):
        transcript = (
            "The team reviewed the mobile application launch. "
            "Ravi will complete API integration by Friday. "
            "Priya will prepare the UI testing report next week. "
            "The team also discussed the office seating plan and lunch schedule."
        )
        intelligence = llm_service.process_transcript(transcript)
        meeting_id = meeting_db.save_meeting("planning.mp3", transcript, intelligence)
        knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)

        answer = knowledge_repository.answer_question("What is Ravi responsible for and when is it due?")

        self.assertIn("Ravi", answer["answer"])
        self.assertIn("Friday", answer["answer"])
        self.assertLess(len(answer["answer"]), len(transcript))
        self.assertNotIn("office seating plan", answer["answer"])
        transcript_sources = [source for source in answer["sources"] if source["section_type"] == "transcript"]
        self.assertTrue(transcript_sources)
        self.assertTrue(all(source["is_excerpt"] for source in transcript_sources))
        self.assertTrue(all("office seating plan" not in source["content"] for source in transcript_sources))

    def test_search_ranks_correct_meeting_across_multiple_historical_records(self):
        target_id = None
        for index in range(40):
            if index == 23:
                transcript = "The database migration will be completed by Ravi on Friday."
                filename = "database-migration.mp3"
            else:
                transcript = f"The design review discussed customer interviews and prototype feedback number {index}."
                filename = f"design-review-{index}.mp3"
            intelligence = llm_service.process_transcript(transcript)
            meeting_id = meeting_db.save_meeting(filename, transcript, intelligence)
            knowledge_repository.upsert_meeting_embeddings(meeting_id, transcript, intelligence)
            if index == 23:
                target_id = meeting_id

        started = time.perf_counter()
        results = knowledge_repository.semantic_search("Which meeting discussed the database migration?")
        elapsed = time.perf_counter() - started

        self.assertTrue(results)
        self.assertEqual(results[0]["meeting_id"], target_id)
        self.assertLess(elapsed, 3)


if __name__ == "__main__":
    unittest.main()
