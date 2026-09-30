"""Meeting intelligence service with structured LLM output and local fallback."""

import json
import os
import re
import time
from typing import Any


SCHEMA_KEYS = (
    "summary",
    "key_points",
    "decisions",
    "action_items",
    "participants",
    "deadlines",
    "priorities",
    "meeting_points",
)

SYSTEM_PROMPT = """You are a meeting intelligence assistant. Analyze the transcript faithfully.
Return only valid JSON with exactly these top-level keys:
summary (string), key_points (array of strings), decisions (array of strings),
action_items (array of objects), participants (array of objects), deadlines (array of objects),
priorities (array of strings).
meeting_points (array of strings).
Action object fields: task, assignee, deadline, priority, status.
Participant object fields: name, responsibilities.
Deadline object fields: item, due_date.
Use 'Unknown' when a person, date, priority, or status is not stated. Never invent facts.
"""


def build_prompt(transcript: str) -> str:
    """Create the reusable user prompt sent to the approved LLM."""
    return (
        "Analyze this meeting transcript and produce the required JSON structure. "
        "Preserve names and dates exactly when they are stated.\n\nTRANSCRIPT:\n"
        + transcript
    )


def _empty_result() -> dict[str, Any]:
    return {
        "summary": "No meeting summary could be generated.",
        "key_points": [],
        "decisions": [],
        "action_items": [],
        "participants": [],
        "deadlines": [],
        "priorities": [],
        "meeting_points": [],
    }


def validate_structured_output(value: Any) -> dict[str, Any]:
    """Validate and normalize the predefined meeting intelligence schema."""
    if not isinstance(value, dict):
        raise ValueError("LLM output must be a JSON object")

    result = _empty_result()
    result["summary"] = str(value.get("summary", "")).strip() or result["summary"]

    for key in ("key_points", "decisions", "priorities", "meeting_points"):
        raw_items = value.get(key, [])
        if not isinstance(raw_items, list):
            raise ValueError(f"'{key}' must be an array")
        result[key] = [str(item).strip() for item in raw_items if str(item).strip()]

    for key, fields in (
        ("action_items", ("task", "assignee", "deadline", "priority", "status")),
        ("participants", ("name", "responsibilities")),
        ("deadlines", ("item", "due_date")),
    ):
        raw_items = value.get(key, [])
        if not isinstance(raw_items, list):
            raise ValueError(f"'{key}' must be an array")
        normalized = []
        seen = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            normalized_item = {field: str(item.get(field, "Unknown")).strip() or "Unknown" for field in fields}
            identity = tuple(normalized_item[field].lower() for field in fields)
            if identity not in seen:
                normalized.append(normalized_item)
                seen.add(identity)
        result[key] = normalized

    return result


def _local_fallback(transcript: str) -> dict[str, Any]:
    """Provide deterministic meeting intelligence when no LLM key is available."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", transcript) if part.strip()]
    action_keywords = ("need to", "will", "assigned", "responsible", "task", "must", "prepare", "complete")
    date_pattern = re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|next week|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", re.I)
    actions = []
    participants = []
    deadlines = []
    participant_pattern = re.compile(
        r"\b([A-Z][a-z]{2,})(?:\s+(?:will|is|has|should|must|can)|\s*[-:])",
    )
    meeting_keywords = ("room", "office", "hall", "venue", "location", "zoom", "google meet", "meeting point")
    for sentence in sentences:
        lowered = sentence.lower()
        participant_match = participant_pattern.search(sentence)
        participant_name = participant_match.group(1) if participant_match else "Unknown"
        if participant_name != "Unknown":
            responsibility = sentence
            participant = {"name": participant_name, "responsibilities": responsibility}
            if participant not in participants:
                participants.append(participant)
        if any(keyword in lowered for keyword in action_keywords):
            due_match = date_pattern.search(sentence)
            actions.append({
                "task": sentence,
                "assignee": participant_name,
                "deadline": due_match.group(0) if due_match else "Unknown",
                "priority": "Unknown",
                "status": "Pending",
            })
            if due_match:
                deadlines.append({"item": sentence, "due_date": due_match.group(0)})

    return validate_structured_output({
        "summary": " ".join(sentences[:2])[:500] or "No transcript content available.",
        "key_points": sentences[:5],
        "decisions": [sentence for sentence in sentences if "decided" in sentence.lower() or "agreed" in sentence.lower()][:5],
        "action_items": actions[:10],
        "participants": participants[:20],
        "deadlines": deadlines[:10],
        "priorities": [],
        "meeting_points": [sentence for sentence in sentences if any(keyword in sentence.lower() for keyword in meeting_keywords)][:10],
    })


def _process_llm_chunk(client: Any, transcript: str, model: str, retries: int) -> dict[str, Any]:
    """Process one transcript chunk with retries and schema validation."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_prompt(transcript)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            return validate_structured_output(json.loads(content))
        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(1)
    raise RuntimeError(f"LLM processing failed after retries: {last_error}")


def _merge_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge chunk results while removing duplicate structured records."""
    if not results:
        return _empty_result()
    merged = {
        "summary": " ".join(result["summary"] for result in results if result["summary"]),
        "key_points": [],
        "decisions": [],
        "action_items": [],
        "participants": [],
        "deadlines": [],
        "priorities": [],
        "meeting_points": [],
    }
    for key in ("key_points", "decisions", "priorities"):
        merged[key] = list(dict.fromkeys(item for result in results for item in result[key]))
    for key in ("action_items", "participants", "deadlines"):
        seen = set()
        for result in results:
            for item in result[key]:
                identity = json.dumps(item, sort_keys=True).lower()
                if identity not in seen:
                    merged[key].append(item)
                    seen.add(identity)
    return validate_structured_output(merged)


def process_transcript(transcript: str, max_chars: int = 12000, retries: int = 2) -> dict[str, Any]:
    """Process a transcript with an optional LLM, chunking long input safely."""
    transcript = (transcript or "").strip()
    if not transcript:
        raise ValueError("Transcript cannot be empty")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _local_fallback(transcript)

    try:
        from openai import OpenAI
    except ImportError:
        return _local_fallback(transcript)

    client = OpenAI(api_key=api_key, timeout=30.0, max_retries=0)
    model = os.getenv("MEETING_LLM_MODEL", "gpt-4o-mini")
    chunks = [transcript[index:index + max_chars] for index in range(0, len(transcript), max_chars)]
    return _merge_results([_process_llm_chunk(client, chunk, model, retries) for chunk in chunks])
