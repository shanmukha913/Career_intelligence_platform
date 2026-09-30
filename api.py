"""HTTP processing API for meeting transcription and intelligence extraction."""

import logging
import hmac
import os
import tempfile
from functools import lru_cache

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile

import auth_service
from knowledge_repository import answer_question, semantic_search, upsert_meeting_embeddings
from llm_service import process_transcript
from meeting_db import get_meeting, init_db, recent_meetings, save_meeting
from provider_integrations import sync_google_meet_recordings, sync_zoom_recordings

logger = logging.getLogger("meeting_api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Meeting Intelligence API", version="1.0.0")
init_db()
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


@lru_cache(maxsize=3)
def load_whisper_model(model_name: str):
    """Reuse loaded Whisper models across API requests in this process."""
    import whisper
    return whisper.load_model(model_name)


def get_current_user_id(request: Request) -> int | None:
    """Resolve a user session or accept the configured administrative API key."""
    configured_key = os.getenv("MEETING_API_KEY") or os.getenv("API_KEY")
    auth_value = request.headers.get("authorization", "")
    token = auth_value.split(" ", 1)[1].strip() if auth_value.lower().startswith("bearer ") else auth_value.strip()
    if token:
        if configured_key and hmac.compare_digest(token, configured_key):
            return None
        user_id = auth_service.resolve_session(token)
        if user_id is not None:
            return user_id
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    if configured_key:
        raise HTTPException(status_code=401, detail="Bearer token or API key required")
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise HTTPException(status_code=401, detail="Login is required")
    return None


@app.get("/health")
def health() -> dict[str, str]:
    logger.info("Health check requested")
    return {"status": "ok"}


@app.post("/auth/register")
def register_endpoint(payload: dict) -> dict:
    if os.getenv("APP_ENV", "development").lower() == "production" and os.getenv("ALLOW_USER_REGISTRATION", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Account registration is disabled")
    try:
        email = payload.get("email", "")
        password = payload.get("password", "")
        if not isinstance(email, str) or not isinstance(password, str):
            raise ValueError("Email and password must be text")
        user_id = auth_service.register_user(email, password)
        logger.info("Account registered: user_id=%s", user_id)
        return {"user_id": user_id, "email": email.strip().lower()}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/auth/token")
def login_endpoint(payload: dict) -> dict:
    try:
        email = payload.get("email", "")
        password = payload.get("password", "")
        if not isinstance(email, str) or not isinstance(password, str):
            raise ValueError("Email and password must be text")
        token = auth_service.authenticate_user(email, password)
        user_id = auth_service.resolve_session(token)
        return {"access_token": token, "token_type": "bearer", "user_id": user_id}
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/auth/me")
def current_user_endpoint(user_id: int | None = Depends(get_current_user_id)) -> dict:
    if user_id is None:
        return {"role": "administrator"}
    return {"user_id": user_id, "email": auth_service.user_email(user_id)}


@app.post("/auth/logout")
def logout_endpoint(request: Request, user_id: int | None = Depends(get_current_user_id)) -> dict[str, str]:
    if user_id is None:
        raise HTTPException(status_code=400, detail="Logout requires a user session token")
    auth_value = request.headers.get("authorization", "")
    token = auth_value.split(" ", 1)[1].strip() if auth_value.lower().startswith("bearer ") else auth_value.strip()
    auth_service.revoke_session(token)
    return {"status": "logged out"}


@app.post("/integrations/zoom/sync")
def zoom_sync_endpoint(model_name: str = "base", user_id: int | None = Depends(get_current_user_id)) -> dict:
    if user_id is None:
        raise HTTPException(status_code=403, detail="Provider imports require an authenticated user account")
    try:
        return sync_zoom_recordings(user_id, model_name=model_name)
    except Exception as error:
        logger.exception("Zoom recording sync failed for user_id=%s", user_id)
        raise HTTPException(status_code=502, detail=f"Zoom recording sync failed: {error}") from error


@app.post("/integrations/google-meet/sync")
def google_meet_sync_endpoint(model_name: str = "base", user_id: int | None = Depends(get_current_user_id)) -> dict:
    if user_id is None:
        raise HTTPException(status_code=403, detail="Provider imports require an authenticated user account")
    try:
        return sync_google_meet_recordings(user_id, model_name=model_name)
    except Exception as error:
        logger.exception("Google Meet recording sync failed for user_id=%s", user_id)
        raise HTTPException(status_code=502, detail=f"Google Meet recording sync failed: {error}") from error


@app.post("/process-transcript")
def process_transcript_endpoint(payload: dict, user_id: int | None = Depends(get_current_user_id)) -> dict:
    transcript = payload.get("transcript", "")
    logger.info("Transcript processing request received for filename=%s", payload.get("filename", "api-transcript.txt"))
    try:
        intelligence = process_transcript(transcript)
        meeting_id = save_meeting(payload.get("filename", "api-transcript.txt"), transcript, intelligence, owner_id=user_id)
        upsert_meeting_embeddings(meeting_id, transcript, intelligence)
        logger.info("Transcript processed and saved: meeting_id=%s", meeting_id)
        return {"meeting_id": meeting_id, "intelligence": intelligence}
    except (ValueError, RuntimeError) as error:
        logger.exception("Transcript processing failed")
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/process-meeting")
def process_meeting_endpoint(
    file: UploadFile = File(...),
    model_name: str = "base",
    user_id: int | None = Depends(get_current_user_id),
) -> dict:
    """Upload audio/video, transcribe with Whisper, process, and persist."""
    allowed_formats = {"mp3", "wav", "m4a", "mp4", "webm", "m4b", "ogg"}
    extension = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    logger.info("Meeting upload request received: filename=%s format=%s", file.filename, extension)
    if extension not in allowed_formats:
        raise HTTPException(status_code=415, detail="Unsupported audio/video format")

    try:
        import whisper  # noqa: F401
    except ImportError as error:
        logger.exception("Whisper dependency missing")
        raise HTTPException(status_code=500, detail="Whisper is not installed") from error

    temp_path = None
    try:
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Uploaded recording exceeds 500MB limit")
        if not content:
            raise HTTPException(status_code=422, detail="Uploaded file is empty")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as temporary_file:
            temporary_file.write(content)
            temp_path = temporary_file.name

        model = load_whisper_model(model_name)
        transcription = model.transcribe(temp_path)
        transcript = transcription.get("text", "").strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="Whisper produced an empty transcript")
        intelligence = process_transcript(transcript)
        meeting_id = save_meeting(file.filename or "uploaded-meeting", transcript, intelligence, owner_id=user_id)
        upsert_meeting_embeddings(meeting_id, transcript, intelligence)
        logger.info("Audio meeting processed and saved: meeting_id=%s", meeting_id)
        return {"meeting_id": meeting_id, "transcript": transcript, "intelligence": intelligence}
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Meeting processing failed")
        raise HTTPException(status_code=500, detail=f"Meeting processing failed: {error}") from error
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@app.get("/meetings")
def meetings_endpoint(limit: int = 10, user_id: int | None = Depends(get_current_user_id)) -> dict:
    safe_limit = max(1, min(int(limit), 100))
    meetings = recent_meetings(safe_limit, owner_id=user_id)
    logger.info("Meeting list requested: count=%s limit=%s", len(meetings), safe_limit)
    return {"count": len(meetings), "meetings": meetings}


@app.get("/meetings/{meeting_id}")
def meeting_detail_endpoint(meeting_id: int, user_id: int | None = Depends(get_current_user_id)) -> dict:
    meeting = get_meeting(meeting_id, owner_id=user_id)
    if meeting is None:
        logger.warning("Meeting detail not found: meeting_id=%s", meeting_id)
        raise HTTPException(status_code=404, detail="Meeting not found")
    logger.info("Meeting detail retrieved: meeting_id=%s", meeting_id)
    return {"meeting": meeting}


@app.get("/search")
def search_endpoint(query: str, limit: int = 5, user_id: int | None = Depends(get_current_user_id)) -> dict:
    if not query or not query.strip():
        logger.warning("Search requested with empty query")
        raise HTTPException(status_code=422, detail="Query cannot be empty")
    safe_limit = max(1, min(int(limit), 20))
    results = semantic_search(query, limit=safe_limit, owner_id=user_id)
    logger.info("Semantic search completed: query=%s results=%s", query, len(results))
    return {"query": query, "results": results}


@app.post("/ask")
def ask_endpoint(payload: dict, user_id: int | None = Depends(get_current_user_id)) -> dict:
    question = payload.get("question", "")
    if not question or not str(question).strip():
        logger.warning("RAG ask request rejected: empty question")
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    answer = answer_question(str(question).strip(), owner_id=user_id)
    logger.info("RAG answer generated for question=%s", question)
    return answer
