"""Import Zoom and Google Meet Drive recordings into the normal meeting pipeline."""

import logging
import os
import re
import tempfile
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests

from knowledge_repository import upsert_meeting_embeddings
from llm_service import process_transcript
from meeting_db import get_external_meeting, get_meeting, save_meeting

ALLOWED_RECORDING_EXTENSIONS = {"mp3", "wav", "m4a", "mp4", "webm", "ogg"}
MAX_RECORDING_BYTES = 500 * 1024 * 1024
REQUEST_TIMEOUT = (10, 60)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=3)
def load_whisper_model(model_name: str):
    """Reuse Whisper models across provider recordings in one process."""
    import whisper
    return whisper.load_model(model_name)


def sync_zoom_recordings(owner_id: int, model_name: str = "base", from_date: str | None = None) -> dict[str, Any]:
    """Retrieve and process recordings visible to a Zoom Server-to-Server OAuth app."""
    account_id = _required_environment("ZOOM_ACCOUNT_ID")
    client_id = _required_environment("ZOOM_CLIENT_ID")
    client_secret = _required_environment("ZOOM_CLIENT_SECRET")
    user_id = os.getenv("ZOOM_USER_ID", "me")
    start_date = from_date or (date.today() - timedelta(days=30)).isoformat()
    token_response = requests.post(
        "https://zoom.us/oauth/token",
        params={"grant_type": "account_credentials", "account_id": account_id},
        auth=(client_id, client_secret),
        timeout=REQUEST_TIMEOUT,
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    results = []
    next_page_token = None

    while True:
        parameters = {"from": start_date, "to": date.today().isoformat(), "page_size": 100}
        if next_page_token:
            parameters["next_page_token"] = next_page_token
        response = requests.get(
            f"https://api.zoom.us/v2/users/{quote(user_id, safe='')}/recordings",
            headers=headers,
            params=parameters,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        for recording in payload.get("meetings", []):
            meeting_uuid = str(recording.get("uuid", recording.get("id", "")))
            for recording_file in recording.get("recording_files", []):
                extension = _recording_extension(recording_file.get("file_type", ""), recording_file.get("download_url", ""))
                if extension not in ALLOWED_RECORDING_EXTENSIONS:
                    continue
                recording_id = f"{meeting_uuid}:{recording_file.get('id', recording_file.get('recording_type', 'recording'))}"
                filename = _safe_filename(recording_file.get("file_name") or f"zoom_{recording.get('id')}.{extension}")
                results.append(_import_one(
                    source="zoom",
                    external_id=recording_id,
                    filename=filename,
                    url=recording_file["download_url"],
                    headers=headers,
                    owner_id=owner_id,
                    model_name=model_name,
                    allowed_hosts=("zoom.us",),
                ))
        next_page_token = payload.get("next_page_token")
        if not next_page_token:
            break
    return _summarize_results("zoom", results)


def sync_google_meet_recordings(owner_id: int, model_name: str = "base") -> dict[str, Any]:
    """Import Meet recordings stored in Drive using an OAuth refresh token."""
    client_id = _required_environment("GOOGLE_CLIENT_ID")
    client_secret = _required_environment("GOOGLE_CLIENT_SECRET")
    refresh_token = _required_environment("GOOGLE_REFRESH_TOKEN")
    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=REQUEST_TIMEOUT,
    )
    try:
        token_response.raise_for_status()
    except requests.HTTPError as error:
        try:
            error_payload = token_response.json()
        except ValueError:
            error_payload = {}
        if not isinstance(error_payload, dict):
            error_payload = {}
        error_code = error_payload.get("error")
        error_description = error_payload.get("error_description")
        details = ": ".join(str(value) for value in (error_code, error_description) if value)
        if not details:
            details = f"HTTP {token_response.status_code}"
        raise RuntimeError(f"Google OAuth token exchange failed: {details}") from error
    headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
    folder_id = _required_environment("GOOGLE_MEET_RECORDINGS_FOLDER_ID")
    query = "trashed = false and (mimeType contains 'audio/' or mimeType contains 'video/')"
    query += f" and '{folder_id}' in parents"
    results = []
    page_token = None

    while True:
        parameters = {
            "q": query,
            "pageSize": 100,
            "orderBy": "modifiedTime desc",
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime)",
        }
        if page_token:
            parameters["pageToken"] = page_token
        response = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params=parameters,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        for recording in payload.get("files", []):
            name = _safe_filename(recording.get("name", ""))
            extension = Path(name).suffix.lower().lstrip(".")
            if extension not in ALLOWED_RECORDING_EXTENSIONS:
                extension = _extension_for_mime(recording.get("mimeType", ""))
                name = f"{Path(name).stem or recording['id']}.{extension}"
            if extension not in ALLOWED_RECORDING_EXTENSIONS:
                continue
            results.append(_import_one(
                source="google_meet",
                external_id=str(recording["id"]),
                filename=name,
                url=f"https://www.googleapis.com/drive/v3/files/{quote(recording['id'], safe='')}?alt=media",
                headers=headers,
                owner_id=owner_id,
                model_name=model_name,
                allowed_hosts=("googleapis.com",),
            ))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return _summarize_results("google_meet", results)


def _import_one(
    source: str,
    external_id: str,
    filename: str,
    url: str,
    headers: dict[str, str],
    owner_id: int,
    model_name: str,
    allowed_hosts: tuple[str, ...],
) -> dict[str, Any]:
    temporary_path = None
    try:
        existing_id = get_external_meeting(owner_id, source, external_id)
        if existing_id is not None:
            meeting = get_meeting(existing_id, owner_id=owner_id)
            if meeting:
                upsert_meeting_embeddings(existing_id, meeting["transcript"], meeting["intelligence"])
            return {"status": "duplicate", "meeting_id": existing_id, "filename": filename}

        content = _download_recording(url, headers, allowed_hosts)
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in ALLOWED_RECORDING_EXTENSIONS:
            raise ValueError("Unsupported recording file format")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as temporary_file:
            temporary_file.write(content)
            temporary_path = temporary_file.name

        transcription = load_whisper_model(model_name).transcribe(temporary_path)
        transcript = str(transcription.get("text", "")).strip()
        if len(transcript) < 10:
            raise ValueError("Recording produced an empty or too-short transcript")
        intelligence = process_transcript(transcript)
        meeting_id = save_meeting(
            filename,
            transcript,
            intelligence,
            owner_id=owner_id,
            source=source,
            external_id=external_id,
        )
        upsert_meeting_embeddings(meeting_id, transcript, intelligence)
        return {"status": "imported", "meeting_id": meeting_id, "filename": filename}
    except Exception as error:
        logger.exception("Provider recording import failed: source=%s filename=%s", source, filename)
        return {
            "status": "failed",
            "filename": filename,
            "error": f"{type(error).__name__}: {error}",
        }
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _download_recording(url: str, headers: dict[str, str], allowed_hosts: tuple[str, ...]) -> bytes:
    hostname = (urlparse(url).hostname or "").lower()
    if not any(hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts):
        raise ValueError("Provider returned a download URL on an untrusted host")
    response = requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_RECORDING_BYTES:
        raise ValueError("Recording exceeds 500MB limit")
    chunks = []
    total_bytes = 0
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if not chunk:
            continue
        total_bytes += len(chunk)
        if total_bytes > MAX_RECORDING_BYTES:
            raise ValueError("Recording exceeds 500MB limit")
        chunks.append(chunk)
    if not total_bytes:
        raise ValueError("Provider returned an empty recording")
    return b"".join(chunks)


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Provider integration is not configured: set {name}")
    return value


def _recording_extension(file_type: str, download_url: str) -> str:
    extension = Path(urlparse(download_url).path).suffix.lower().lstrip(".")
    if extension in ALLOWED_RECORDING_EXTENSIONS:
        return extension
    normalized = file_type.lower()
    return normalized if normalized in ALLOWED_RECORDING_EXTENSIONS else ""


def _extension_for_mime(mime_type: str) -> str:
    return {"video/mp4": "mp4", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/wav": "wav", "audio/ogg": "ogg"}.get(mime_type, "")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:200] or "recording"


def _summarize_results(provider: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "provider": provider,
        "total": len(results),
        "imported": sum(result["status"] == "imported" for result in results),
        "duplicates": sum(result["status"] == "duplicate" for result in results),
        "failed": sum(result["status"] == "failed" for result in results),
        "results": results,
    }
