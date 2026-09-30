# Deployment

## Current deployment shape

The supplied Compose configuration runs the FastAPI service and Streamlit dashboard in separate containers. Both use the existing SQLite database on a persistent Docker volume. The API and dashboard ports bind to localhost; place a TLS reverse proxy and network controls in front of them before exposing the application remotely.

This is a single-instance demonstration deployment. SQLite is not configured for multi-host or horizontally scaled writes. Back up the Docker volume regularly and use a managed database before scaling beyond one instance.

## Configure and run

1. Copy `.env.example` to `.env`.
2. Set a unique, strong `MEETING_API_KEY` for administrative API access. Set `ALLOW_USER_REGISTRATION=true` to allow individual account creation; set it to `false` after creating the intended users. Do not commit `.env`.
3. Optionally configure `OPENAI_API_KEY` and `MEETING_LLM_MODEL` for hosted LLM processing. Without an API key, the application uses its local extraction fallback.
4. Run `docker compose up --build`.
5. Open the dashboard at `http://localhost:8501`; the API health check is at `http://localhost:8000/health`.

The dashboard and API support individual email/password accounts with salted PBKDF2 password hashes, expiring revocable bearer sessions, and owner-scoped meeting, transcript, semantic-search, and RAG access. The configured API key is administrative and can access all records; keep it private. Legacy meetings without an owner are not shown to regular accounts. SQLite remains a single-instance datastore; use a managed database for scaled deployments.

## Provider integrations

The dashboard and API can sync Zoom recordings using Server-to-Server OAuth and Google Meet recording files stored in Drive using an OAuth refresh token. Imports run the normal Whisper, intelligence extraction, persistence, and vector indexing pipeline; provider IDs are deduplicated per account. A repeated sync repairs missing vectors for already-persisted recordings. Downloads are restricted to provider hosts and the 500 MB upload limit.

Create and authorize the provider applications before syncing. Configure `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, and optionally `ZOOM_USER_ID`. Grant the Zoom app recording read/download scopes. For Google, configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, and `GOOGLE_MEET_RECORDINGS_FOLDER_ID` with Drive file read access. The folder ID is required to prevent importing unrelated media. Meet recordings must be accessible to the Google account that authorized Drive access.

The automated provider tests mock external APIs; they do not prove the supplied credentials, tenant permissions, or live recording availability. Before public deployment, run provider sync against the intended accounts, verify backup/restore, and perform load and security testing. Docker Compose YAML is included, but a container build must be verified in an environment with Docker installed.

## Configuration

- `APP_ENV`: use `production` for deployed services; protected API routes fail closed when `MEETING_API_KEY` is unset.
- `MEETING_API_KEY`: shared API credential for protected API routes.
- `ALLOW_USER_REGISTRATION`: controls public account creation; disable after creating the intended users.
- `MEETING_DB_PATH`: SQLite file location; Compose uses `/data/meetings.db` on the persistent volume.
- `OPENAI_API_KEY`: optional hosted LLM credential.
- `MEETING_LLM_MODEL`: optional model name, default `gpt-4o-mini`.
- `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_USER_ID`: Zoom Server-to-Server OAuth configuration.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_MEET_RECORDINGS_FOLDER_ID`: Google Drive OAuth and optional recordings-folder configuration.

The process reads environment variables directly. Compose loads a `.env` file automatically; local PowerShell runs must set the variables in the process environment before starting the API/dashboard.
