"""HTTP processing API for meeting transcription and intelligence extraction."""

import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile

from llm_service import process_transcript
from meeting_db import init_db, save_meeting

app = FastAPI(title="Meeting Intelligence API", version="1.0.0")
init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process-transcript")
def process_transcript_endpoint(payload: dict) -> dict:
    transcript = payload.get("transcript", "")
    try:
        intelligence = process_transcript(transcript)
        meeting_id = save_meeting(payload.get("filename", "api-transcript.txt"), transcript, intelligence)
        return {"meeting_id": meeting_id, "intelligence": intelligence}
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/process-meeting")
def process_meeting_endpoint(file: UploadFile = File(...), model_name: str = "base") -> dict:
    """Upload audio/video, transcribe with Whisper, process, and persist."""
    allowed_formats = {"mp3", "wav", "m4a", "mp4", "webm", "m4b", "ogg"}
    extension = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if extension not in allowed_formats:
        raise HTTPException(status_code=415, detail="Unsupported audio/video format")

    try:
        import whisper
    except ImportError as error:
        raise HTTPException(status_code=500, detail="Whisper is not installed") from error

    temp_path = None
    try:
        content = file.file.read()
        if not content:
            raise HTTPException(status_code=422, detail="Uploaded file is empty")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as temporary_file:
            temporary_file.write(content)
            temp_path = temporary_file.name

        model = whisper.load_model(model_name)
        transcription = model.transcribe(temp_path)
        transcript = transcription.get("text", "").strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="Whisper produced an empty transcript")
        intelligence = process_transcript(transcript)
        meeting_id = save_meeting(file.filename or "uploaded-meeting", transcript, intelligence)
        return {"meeting_id": meeting_id, "transcript": transcript, "intelligence": intelligence}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Meeting processing failed: {error}") from error
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
