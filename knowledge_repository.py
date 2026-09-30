"""Meeting knowledge repository, embeddings, vector search, and grounded RAG."""

import json
import hashlib
import math
import re
import sqlite3
from datetime import datetime
from typing import Any

from llm_service import process_transcript
from meeting_db import DB_PATH, init_db

EMBEDDING_DIMENSIONS = 256
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SEARCH_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "for", "from", "how",
    "i", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "we",
    "what", "when", "where", "which", "who", "why", "will", "with",
}


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


def generate_embedding(text: str) -> list[float]:
    """Generate a deterministic normalized embedding without external services."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = _tokens(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def init_knowledge_db() -> None:
    init_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS knowledge_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                section_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(meeting_id, section_type, content),
                FOREIGN KEY(meeting_id) REFERENCES meetings(id)
            )"""
        )
        connection.commit()
    finally:
        connection.close()


def _meeting_sections(meeting_id: int, transcript: str, intelligence: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    sections = [("transcript", transcript, {})]
    sections.append(("summary", intelligence.get("summary", ""), {}))
    for key in ("decisions", "priorities", "meeting_points", "key_points"):
        for item in intelligence.get(key, []):
            sections.append((key[:-1] if key.endswith("s") else key, str(item), {}))
    for item in intelligence.get("action_items", []):
        sections.append(("action_item", item.get("task", ""), item))
    for item in intelligence.get("deadlines", []):
        sections.append(("deadline", item.get("item", ""), item))
    return [(kind, content.strip(), metadata) for kind, content, metadata in sections if content and content.strip()]


def upsert_meeting_embeddings(meeting_id: int, transcript: str, intelligence: dict[str, Any]) -> int:
    """Create or update vectors for every searchable section of a meeting."""
    init_knowledge_db()
    sections = _meeting_sections(meeting_id, transcript, intelligence)
    connection = sqlite3.connect(DB_PATH)
    try:
        for section_type, content, metadata in sections:
            connection.execute(
                """INSERT INTO knowledge_vectors
                (meeting_id, section_type, content, embedding_json, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(meeting_id, section_type, content) DO UPDATE SET
                    embedding_json=excluded.embedding_json,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at""",
                (meeting_id, section_type, content, json.dumps(generate_embedding(content)), json.dumps(metadata), datetime.now().isoformat(timespec="seconds")),
            )
        connection.commit()
        return len(sections)
    finally:
        connection.close()


def index_existing_meetings() -> int:
    """Backfill vectors for meetings already stored before Milestone 3."""
    init_knowledge_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        rows = connection.execute("SELECT id, transcript, intelligence_json FROM meetings").fetchall()
    finally:
        connection.close()
    total = 0
    for meeting_id, transcript, intelligence_json in rows:
        total += upsert_meeting_embeddings(meeting_id, transcript, json.loads(intelligence_json))
    return total


def delete_meeting_embeddings(meeting_id: int) -> int:
    init_knowledge_db()
    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.execute("DELETE FROM knowledge_vectors WHERE meeting_id = ?", (meeting_id,))
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def semantic_search(
    query: str,
    limit: int = 5,
    meeting_id: int | None = None,
    owner_id: int | None = None,
) -> list[dict[str, Any]]:
    """Search vectors and optionally filter results to one meeting."""
    if not (query or "").strip():
        return []
    init_knowledge_db()
    query_vector = generate_embedding(query)
    query_terms = set(_tokens(query)) - SEARCH_STOP_WORDS
    if not query_terms:
        return []
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        sql = """SELECT v.*, m.filename, m.created_at FROM knowledge_vectors v
                 JOIN meetings m ON m.id = v.meeting_id"""
        parameters: list[Any] = []
        filters = []
        if meeting_id is not None:
            filters.append("v.meeting_id = ?")
            parameters.append(meeting_id)
        if owner_id is not None:
            filters.append("m.owner_id = ?")
            parameters.append(owner_id)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        rows = connection.execute(sql, parameters).fetchall()
        matches = []
        for row in rows:
            content_terms = set(_tokens(row["content"])) - SEARCH_STOP_WORDS
            shared_terms = query_terms.intersection(content_terms)
            if not shared_terms:
                continue
            vector_score = cosine_similarity(query_vector, json.loads(row["embedding_json"]))
            lexical_coverage = len(shared_terms) / len(query_terms)
            score = 0.75 * vector_score + 0.25 * lexical_coverage
            metadata = json.loads(row["metadata_json"])
            matches.append({"vector_id": row["id"], "meeting_id": row["meeting_id"], "filename": row["filename"], "created_at": row["created_at"], "section_type": row["section_type"], "content": row["content"], "metadata": metadata, "score": score})
        return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]
    finally:
        connection.close()


def answer_question(question: str, limit: int = 5, owner_id: int | None = None) -> dict[str, Any]:
    """Retrieve relevant sections and answer only from that retrieved context."""
    results = semantic_search(question, limit=limit, owner_id=owner_id)
    if not results:
        return {"answer": "I could not find relevant information in the stored meetings.", "sources": []}
    context = "\n".join(
        f"[{item['filename']} | {item['section_type']}] "
        f"{_focused_content(question, item['content']) if item['section_type'] == 'transcript' else item['content']}"
        for item in results
    )
    api_key = __import__("os").getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            response = OpenAI(api_key=api_key, timeout=30.0, max_retries=0).chat.completions.create(
                model=__import__("os").getenv("MEETING_LLM_MODEL", "gpt-4o-mini"),
                temperature=0,
                messages=[
                    {"role": "system", "content": "Answer only from the supplied meeting context. If the answer is not present, say so. Give only the key points in at most 3 short bullets and 80 words. Do not reproduce the transcript. Include relevant owner and deadline, and cite the source filename."},
                    {"role": "user", "content": f"QUESTION: {question}\n\nCONTEXT:\n{context}"},
                ],
            )
            answer = response.choices[0].message.content.strip()
        except Exception:
            answer = _grounded_fallback(question, results)
    else:
        answer = _grounded_fallback(question, results)
    sources = []
    for item in results:
        source = dict(item)
        if source["section_type"] == "transcript":
            source["content"] = _focused_content(question, source["content"])
            source["is_excerpt"] = True
        sources.append(source)
    return {"answer": answer, "sources": sources}


def _grounded_fallback(question: str, results: list[dict[str, Any]]) -> str:
    """Return a few relevant evidence sentences when no LLM is configured."""
    question_tokens = set(_tokens(question)) - SEARCH_STOP_WORDS
    best = max(
        results,
        key=lambda item: len(question_tokens.intersection(set(_tokens(item["content"])) - SEARCH_STOP_WORDS)),
    )
    content = best["content"]
    if best["section_type"] == "transcript":
        content = _focused_content(question, content)
    return f"Based on {best['filename']}: {content}"


def _focused_content(question: str, content: str, max_sentences: int = 3) -> str:
    """Extract only query-relevant sentences from a retrieved transcript section."""
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", content) if sentence.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    query_terms = set(_tokens(question)) - SEARCH_STOP_WORDS
    ranked = []
    for index, sentence in enumerate(sentences):
        sentence_terms = set(_tokens(sentence)) - SEARCH_STOP_WORDS
        overlap = len(query_terms.intersection(sentence_terms))
        if overlap:
            ranked.append((overlap, index, sentence))
    if not ranked:
        return " ".join(sentences[:max_sentences])

    selected = sorted(ranked, key=lambda item: (-item[0], item[1]))[:max_sentences]
    return " ".join(sentence for _, _, sentence in sorted(selected, key=lambda item: item[1]))
