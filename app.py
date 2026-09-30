import streamlit as st
import whisper
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import csv
import io
from llm_service import process_transcript
from meeting_db import get_meeting, init_db, save_meeting, recent_meetings
from knowledge_repository import answer_question, index_existing_meetings, init_knowledge_db, semantic_search, upsert_meeting_embeddings
from meeting_reports import build_meeting_csv, build_meeting_pdf
import auth_service
from provider_integrations import sync_google_meet_recordings, sync_zoom_recordings

# Page Configuration
st.set_page_config(
    page_title="Meeting Transcriber",
    page_icon="🎙️",
    layout="wide"
)


def enforce_dashboard_access():
    """Require an individual account and retain a revocable Streamlit session."""
    auth_service.init_auth_db()
    token = st.session_state.get("auth_token")
    if token and (user_id := auth_service.resolve_session(token)) is not None:
        with st.sidebar:
            st.caption(auth_service.user_email(user_id))
            if st.button("Log out"):
                auth_service.revoke_session(token)
                st.session_state.pop("auth_token", None)
                st.session_state.pop("authenticated_user_id", None)
                st.rerun()
        return user_id
    st.session_state.pop("auth_token", None)
    st.session_state.pop("authenticated_user_id", None)

    st.title("Meeting Intelligence Login")
    login_tab, register_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        with st.form("dashboard_login"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            login_submitted = st.form_submit_button("Log in")
        if login_submitted:
            try:
                session_token = auth_service.authenticate_user(email, password)
                st.session_state["auth_token"] = session_token
                st.session_state["authenticated_user_id"] = auth_service.resolve_session(session_token)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    if os.getenv("ALLOW_USER_REGISTRATION", "true").lower() == "true":
        with register_tab:
            with st.form("dashboard_registration"):
                new_email = st.text_input("Email", key="register_email")
                new_password = st.text_input("Password (12+ characters)", type="password", key="register_password")
                register_submitted = st.form_submit_button("Create account")
            if register_submitted:
                try:
                    auth_service.register_user(new_email, new_password)
                    session_token = auth_service.authenticate_user(new_email, new_password)
                    st.session_state["auth_token"] = session_token
                    st.session_state["authenticated_user_id"] = auth_service.resolve_session(session_token)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    st.stop()


current_user_id = enforce_dashboard_access()

st.markdown(
    """
    <style>
        :root {
            --bg: #0f172a;
            --panel: rgba(15, 23, 42, 0.88);
            --panel-soft: rgba(15, 23, 42, 0.72);
            --surface: #111827;
            --surface-alt: #1f2937;
            --border: rgba(148, 163, 184, 0.2);
            --text: #e5eefb;
            --muted: #a6b5c8;
            --primary: #7dd3fc;
            --primary-strong: #38bdf8;
            --success: #34d399;
            --warning: #fbbf24;
        }

        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #111827 30%, #172554 100%);
            color: var(--text);
        }

        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .resume-hero {
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.25);
        }

        .resume-kicker {
            color: var(--primary);
            font-size: 0.78rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }

        .resume-title {
            font-size: clamp(2.1rem, 4vw, 3.1rem);
            font-weight: 800;
            line-height: 1.1;
            margin: 0;
        }

        .resume-subtitle {
            color: var(--muted);
            font-size: 1.02rem;
            margin-top: 0.5rem;
            margin-bottom: 0;
        }

        .mini-badge {
            display: inline-block;
            padding: 0.38rem 0.7rem;
            border-radius: 999px;
            background: rgba(125, 211, 252, 0.12);
            border: 1px solid rgba(125, 211, 252, 0.35);
            color: var(--primary);
            font-size: 0.76rem;
            font-weight: 700;
            margin-right: 0.5rem;
            margin-top: 0.6rem;
        }

        .section-card {
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            margin: 0.6rem 0 1rem 0;
        }

        .section-label {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: var(--text);
        }

        .metric-box {
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.9), rgba(17, 24, 39, 0.75));
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 0.9rem 0.8rem;
            min-height: 110px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .stButton > button {
            border-radius: 12px;
            background: linear-gradient(135deg, #7dd3fc 0%, #38bdf8 100%);
            color: #082f49;
            border: none;
            font-weight: 700;
            padding: 0.65rem 1rem;
            transition: transform 0.15s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 18px rgba(56, 189, 248, 0.25);
        }

        .stTabs [role="tablist"] {
            gap: 0.5rem;
        }

        .stTabs [role="tab"] {
            border-radius: 10px 10px 0 0;
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid var(--border);
            color: var(--muted);
            padding: 0.5rem 1rem;
        }

        .stTabs [role="tab"][aria-selected="true"] {
            background: rgba(56, 189, 248, 0.12);
            border-color: rgba(56, 189, 248, 0.5);
            color: var(--primary);
        }

        .stDataFrame {
            background: rgba(15, 23, 42, 0.65);
            border-radius: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="resume-hero">
        <div class="resume-kicker">AI-powered meeting intelligence</div>
        <h1 class="resume-title">🎙️ Meeting Transcription System</h1>
        <p class="resume-subtitle">Upload a meeting recording, extract actionable insights, validate transcript accuracy, and search across saved meetings using natural language.</p>
        <div>
            <span class="mini-badge">Whisper</span>
            <span class="mini-badge">Semantic Search</span>
            <span class="mini-badge">Meeting Insights</span>
            <span class="mini-badge">SQLite Storage</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("transcripts", exist_ok=True)
os.makedirs("cache", exist_ok=True)
init_db()
init_knowledge_db()
index_existing_meetings()

# ==================== CACHING SYSTEM (Avoid Re-transcription) ====================
def get_file_hash(file_bytes):
    """Generate hash of file for caching"""
    return hashlib.md5(file_bytes).hexdigest()

def get_cached_transcript(file_hash):
    """Check if transcript already exists"""
    cache_file = os.path.join("cache", f"{file_hash}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_to_cache(file_hash, result):
    """Save transcription result to cache"""
    cache_file = os.path.join("cache", f"{file_hash}.json")
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(result, f)

# ==================== TASK 2: FILE UPLOAD VALIDATION ====================
def validate_file(uploaded_file):
    """
    Validate uploaded file
    - Check file size (max 500MB)
    - Check file format
    - Check if file is not empty
    """
    allowed_formats = ["mp3", "wav", "m4a", "mp4", "webm", "m4b", "ogg"]
    
    if uploaded_file is None:
        return False, "No file selected"
    
    # Check file size (500MB limit)
    file_size = uploaded_file.size / (1024 * 1024)  # Convert to MB
    if file_size > 500:
        return False, f"File size ({file_size:.2f}MB) exceeds 500MB limit"
    
    # Check file format
    file_extension = uploaded_file.name.split('.')[-1].lower()
    if file_extension not in allowed_formats:
        return False, f"Format '.{file_extension}' not supported. Allowed: {', '.join(allowed_formats)}"
    
    # Check if file is empty
    if file_size == 0:
        return False, "File is empty"
    
    return True, "File validation passed"


# ==================== TASK 1 & 3: WHISPER TRANSCRIPTION & SAVING ====================
@st.cache_resource
def load_whisper_model(model_name="base"):
    """Load Whisper model (cached to avoid reloading)"""
    return whisper.load_model(model_name)


def transcribe_audio(file_path, model):
    """
    Transcribe audio using Whisper and always return a dictionary-like result.
    """
    try:
        result = model.transcribe(file_path)
        if isinstance(result, dict):
            return result
        return {"text": ""}
    except Exception as e:
        return {"text": "", "error": f"Transcription error: {str(e)}"}


def save_transcript(transcript_text, filename, owner_id=None):
    """
    Save transcript to file
    Returns: (success, filepath)
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(filename).stem
        transcript_filename = f"{base_name}_{timestamp}.txt"
        transcript_directory = os.path.join("transcripts", f"user_{owner_id}") if owner_id is not None else "transcripts"
        os.makedirs(transcript_directory, exist_ok=True)
        transcript_path = os.path.join(transcript_directory, transcript_filename)
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        
        # Also save metadata
        metadata = {
            "original_file": filename,
            "timestamp": timestamp,
            "transcription_date": datetime.now().isoformat(),
            "transcript_length": len(transcript_text),
            "word_count": len(transcript_text.split())
        }
        
        metadata_path = transcript_path.replace('.txt', '_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return True, transcript_path, metadata
    except Exception as e:
        return False, None, str(e)


def validate_transcript(transcript_result):
    """
    Validate transcript
    - Check if not empty
    - Check if transcription was successful
    """
    validation_result = {
        "is_valid": True,
        "issues": []
    }
    
    if not transcript_result or "text" not in transcript_result:
        validation_result["is_valid"] = False
        validation_result["issues"].append("No text in transcript")
        return validation_result
    
    text = transcript_result["text"].strip()
    
    if not text:
        validation_result["is_valid"] = False
        validation_result["issues"].append("Transcript is empty")
    
    if len(text) < 10:
        validation_result["is_valid"] = False
        validation_result["issues"].append("Transcript is too short (less than 10 characters)")
    
    return validation_result


def build_csv_export(transcript_text, intelligence):
    """Build one CSV report from the structured meeting intelligence."""

    rows = [
        ["Section", "Content"],
        ["Transcript", transcript_text],
        ["Summary", intelligence["summary"]],
        ["Key Points", "; ".join(intelligence["key_points"])],
        ["Decisions", "; ".join(intelligence["decisions"])],
        ["Action Items", json.dumps(intelligence["action_items"])],
        ["Participants", json.dumps(intelligence["participants"])],
        ["Deadlines", json.dumps(intelligence["deadlines"])],
        ["Priorities", "; ".join(intelligence["priorities"])],
        ["Meeting Points", "; ".join(intelligence["meeting_points"])],
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)
    return output.getvalue()


# ==================== TASK 4: STREAMLIT INTERFACE ====================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
col1, col2 = st.columns([2.3, 1])

with col1:
    st.markdown('<div class="section-label">📤 Upload Audio File</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Select a meeting recording",
        type=["mp3", "wav", "m4a", "mp4", "webm", "m4b", "ogg"],
        help="Maximum file size: 500MB. No need to manually save - upload directly!",
        label_visibility="collapsed",
    )

with col2:
    st.markdown('<div class="section-label">⚙️ Settings</div>', unsafe_allow_html=True)
    model_name = st.selectbox(
        "Whisper Model",
        ["tiny", "base", "small"],
        index=0,
        help="tiny: fastest preview | base: balanced accuracy | small: slower, better accuracy"
    )
    model_info = {
        "tiny": "⚡ Fastest | best for quick demos and short recordings",
        "base": "🚀 Fast | ~85-90% accuracy | ~5-10 sec/min",
        "small": "⚡ Medium | ~90-95% accuracy | ~15-20 sec/min"
    }
    st.caption(model_info[model_name])

st.markdown('</div>', unsafe_allow_html=True)

# Main Processing Section
if "transcript_result" not in st.session_state:
    st.session_state["transcript_result"] = None

transcript_result = st.session_state.get("transcript_result")

if uploaded_file is not None:
    # Validate file
    is_valid, validation_message = validate_file(uploaded_file)
    
    if not is_valid:
        st.error(f"❌ {validation_message}")
    else:
        st.success(f"✅ File uploaded: {uploaded_file.name} ({uploaded_file.size / (1024*1024):.2f}MB)")
        
        # Get file hash for caching
        file_bytes = uploaded_file.getbuffer()
        file_hash = get_file_hash(str(current_user_id).encode("utf-8") + bytes(file_bytes))
        
        # Check if already transcribed
        cached_result = get_cached_transcript(file_hash)
        
        if cached_result:
            st.info("💾 This file was already transcribed! Using cached result (instant).")
        
        # Create two tabs for transcription and results
        tab1, tab2, tab3, tab4 = st.tabs(["Transcribe", "View Transcripts", "Verify Accuracy", "AI Search"])
        
        with tab1:
            col1, col2 = st.columns([3, 1])
            with col2:
                transcribe_button = st.button("🎙️ Transcribe", use_container_width=True)
            
            if transcribe_button:
                # Check cache first
                if cached_result:
                    transcript_result = cached_result
                    if isinstance(transcript_result, dict) and "text" in transcript_result:
                        st.session_state["transcript_result"] = transcript_result
                        try:
                            meeting_intelligence = process_transcript(transcript_result["text"])
                            st.session_state["meeting_intelligence"] = meeting_intelligence
                            st.session_state["meeting_id"] = save_meeting(
                                uploaded_file.name,
                                transcript_result["text"],
                                meeting_intelligence,
                                owner_id=current_user_id,
                            )
                            upsert_meeting_embeddings(
                                st.session_state["meeting_id"],
                                transcript_result["text"],
                                meeting_intelligence,
                            )
                        except Exception as intelligence_error:
                            st.warning(f"⚠️ Meeting intelligence was not saved: {intelligence_error}")
                        status_text = st.empty()
                        status_text.success("✅ Used cached transcription (instant)!")
                    else:
                        st.warning("⚠️ Cached result was invalid. Re-transcribing the file...")
                        cached_result = None
                else:
                    # Create progress bar and status area
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    transcript_display = st.empty()
                    
                    try:
                        # Step 1: Save uploaded file
                        status_text.info("📝 Step 1/5: Saving audio file...")
                        progress_bar.progress(20)
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                            tmp_file.write(file_bytes)
                            temp_path = tmp_file.name
                        
                        # Step 2: Load Whisper model
                        status_text.info(f"🤖 Step 2/5: Loading {model_name} Whisper model...")
                        progress_bar.progress(40)
                        model = load_whisper_model(model_name)
                        
                        # Step 3: Transcribe audio
                        status_text.info("🔄 Step 3/5: Processing audio and generating transcript...")
                        progress_bar.progress(60)
                        transcript_result = transcribe_audio(temp_path, model)

                        if isinstance(transcript_result, dict) and "error" in transcript_result:
                            st.error(f"❌ {transcript_result['error']}")
                            os.unlink(temp_path)
                            raise RuntimeError(transcript_result["error"])

                        if not isinstance(transcript_result, dict) or "text" not in transcript_result:
                            st.error("❌ Transcription returned an invalid result format. Please try a different audio/video file.")
                            os.unlink(temp_path)
                            raise TypeError("Invalid transcription result format")
                        
                        # Save to cache
                        save_to_cache(file_hash, transcript_result)
                        
                        # Step 4: Validate transcript
                        status_text.info("✔️ Step 4/5: Validating transcript...")
                        progress_bar.progress(80)
                        validation = validate_transcript(transcript_result)
                        
                        if not validation["is_valid"]:
                            st.error(f"❌ Transcript validation failed: {', '.join(validation['issues'])}")
                        else:
                            # Step 5: Save transcript
                            status_text.info("💾 Step 5/5: Saving transcript...")
                            progress_bar.progress(95)
                            
                            transcript_text = transcript_result["text"]
                            success, filepath, metadata = save_transcript(transcript_text, uploaded_file.name, current_user_id)
                            
                            if success:
                                progress_bar.progress(100)
                                status_text.success("✅ Transcription completed successfully!")
                                try:
                                    meeting_intelligence = process_transcript(transcript_text)
                                    meeting_id = save_meeting(
                                        uploaded_file.name,
                                        transcript_text,
                                        meeting_intelligence,
                                        owner_id=current_user_id,
                                    )
                                    st.session_state["meeting_intelligence"] = meeting_intelligence
                                    st.session_state["meeting_id"] = meeting_id
                                    upsert_meeting_embeddings(meeting_id, transcript_text, meeting_intelligence)
                                except Exception as intelligence_error:
                                    st.warning(f"⚠️ Meeting intelligence was not saved: {intelligence_error}")
                                st.session_state["transcript_result"] = transcript_result
                            else:
                                st.error(f"❌ Failed to save transcript: {metadata}")
                        
                        # Cleanup temp file
                        os.unlink(temp_path)
                        
                    except Exception as e:
                        st.error(f"❌ Error during transcription: {str(e)}")
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                
                # Display results
                if transcript_result:
                    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
                    st.subheader("📄 Transcript Result")
                    transcript_text = transcript_result["text"]

                    st.text_area(
                        "Transcript:",
                        value=transcript_text,
                        height=300,
                        disabled=True,
                    )

                    col1, col2, col3, col4 = st.columns(4)
                    word_count = len(transcript_text.split())
                    char_count = len(transcript_text)

                    with col1:
                        st.markdown("<div class='metric-box'><div style='color: #94a3b8; font-size: 0.77rem;'>Word Count</div><div style='font-size: 2rem; font-weight: 800; margin-top: 0.3rem;'>%s</div></div>" % word_count, unsafe_allow_html=True)
                    with col2:
                        st.markdown("<div class='metric-box'><div style='color: #94a3b8; font-size: 0.77rem;'>Characters</div><div style='font-size: 2rem; font-weight: 800; margin-top: 0.3rem;'>%s</div></div>" % char_count, unsafe_allow_html=True)
                    with col3:
                        st.markdown("<div class='metric-box'><div style='color: #94a3b8; font-size: 0.77rem;'>Model</div><div style='font-size: 1.3rem; font-weight: 800; margin-top: 0.3rem;'>%s</div></div>" % model_name, unsafe_allow_html=True)
                    with col4:
                        if model_name == "base":
                            accuracy = "85-90%"
                        else:
                            accuracy = "90-95%"
                        st.markdown("<div class='metric-box'><div style='color: #94a3b8; font-size: 0.77rem;'>Est. Accuracy</div><div style='font-size: 1.8rem; font-weight: 800; margin-top: 0.3rem;'>%s</div></div>" % accuracy, unsafe_allow_html=True)

                    intelligence = st.session_state.get("meeting_intelligence") or process_transcript(transcript_text)
                    st.session_state["meeting_intelligence"] = intelligence
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                    col_download1, col_download2 = st.columns(2)
                    with col_download1:
                        st.download_button(
                            label="📥 Download Transcript (TXT)",
                            data=transcript_text,
                            file_name=f"transcript_{timestamp}.txt",
                            mime="text/plain",
                            use_container_width=True,
                        )
                    with col_download2:
                        st.download_button(
                            label="📊 Download Summary (CSV)",
                            data=build_csv_export(transcript_text, intelligence),
                            file_name=f"meeting_summary_{timestamp}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown("---")
                    st.markdown("## 🧠 Structured Meeting Intelligence")
                    st.caption("LLM-powered when OPENAI_API_KEY is configured; otherwise the app uses a deterministic local fallback.")
                    st.markdown(f"### Summary\n{intelligence['summary']}")

                    insight_col1, insight_col2 = st.columns(2)
                    with insight_col1:
                        st.markdown("#### Key Points")
                        for item in intelligence["key_points"] or ["No key points extracted."]:
                            st.markdown(f"- {item}")
                        st.markdown("#### Decisions")
                        for item in intelligence["decisions"] or ["No decisions extracted."]:
                            st.markdown(f"- {item}")
                        st.markdown("#### Priorities")
                        for item in intelligence["priorities"] or ["No priorities extracted."]:
                            st.markdown(f"- {item}")
                        st.markdown("#### Meeting Points")
                        for item in intelligence["meeting_points"] or ["No meeting point extracted."]:
                            st.markdown(f"- {item}")

                        if intelligence["action_items"]:
                            st.dataframe(intelligence["action_items"], use_container_width=True, hide_index=True)
                        else:
                            st.info("No action items extracted.")
                        st.markdown("#### Participants & Responsibilities")
                        if intelligence["participants"]:
                            st.dataframe(intelligence["participants"], use_container_width=True, hide_index=True)
                        else:
                            st.info("No participants identified.")

                        st.markdown("#### Deadlines")
                        if intelligence["deadlines"]:
                            st.dataframe(intelligence["deadlines"], use_container_width=True, hide_index=True)
                        else:
                            st.info("No deadlines extracted.")

        
        with tab2:
            st.subheader("📋 Saved Transcripts")

            stored_meetings = recent_meetings(owner_id=current_user_id)
            if stored_meetings:
                st.caption("Structured records saved in the local database")
                for meeting in stored_meetings:
                    intelligence = meeting["intelligence"]
                    with st.expander(f"{meeting['filename']} · {meeting['created_at']}"):
                        st.markdown(f"**Summary**  \n{intelligence['summary']}")
                        if intelligence["action_items"]:
                            st.markdown("**Action items**")
                            st.dataframe(intelligence["action_items"], use_container_width=True, hide_index=True)
            else:
                st.info("No structured meeting records saved yet.")

            transcript_directory = Path("transcripts") / f"user_{current_user_id}" if current_user_id is not None else Path("transcripts")
            transcript_files = list(transcript_directory.glob("*_metadata.json"))
            st.markdown("### Transcript files")
            if transcript_files:
                for metadata_file in sorted(transcript_files, reverse=True):
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"📄 {metadata['original_file']}")
                    with col2:
                        st.write(f"Words: {metadata['word_count']}")
                    with col3:
                        transcript_file = str(metadata_file).replace('_metadata.json', '.txt')
                        if os.path.exists(transcript_file):
                            with open(transcript_file, 'r') as f:
                                transcript_text = f.read()
                            st.download_button(
                                "📥 Download",
                                data=transcript_text,
                                file_name=os.path.basename(transcript_file),
                                key=str(metadata_file)
                            )
            else:
                st.info("No transcript files saved yet.")
        
        with tab3:
            st.subheader("✔️ Verify Accuracy")
            st.write("""
            How to use this feature:
            1. First transcribe a file.
            2. Go to this tab.
            3. Paste the real/reference text spoken in the audio.
            4. Click 'Compare & Calculate Accuracy'.
            5. The app shows Accuracy %, Word Error Rate, and a side-by-side comparison.
            """)
            
            reference_text = st.text_area(
                "Paste the reference/expected transcript text:",
                height=200,
                placeholder="Paste what the audio actually says..."
            )
            
            transcript_result = st.session_state.get("transcript_result")

            if reference_text and st.button("🔍 Compare & Calculate Accuracy"):
                if transcript_result is not None:
                    transcript_text = transcript_result.get("text", "")
                    
                    # Calculate metrics
                    ref_words = reference_text.lower().split()
                    hyp_words = transcript_text.lower().split()
                    
                    from difflib import SequenceMatcher
                    matcher = SequenceMatcher(None, ref_words, hyp_words)
                    matches = sum(block.size for block in matcher.get_matching_blocks())
                    errors = len(ref_words) - matches
                    
                    if len(ref_words) == 0:
                        wer = 0 if len(hyp_words) == 0 else 100
                    else:
                        wer = (errors / len(ref_words)) * 100
                    
                    accuracy = 100 - wer
                    
                    # Display results
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Accuracy", f"{accuracy:.1f}%", 
                                 delta="✅ Good" if accuracy >= 90 else "⚠️ Fair" if accuracy >= 75 else "❌ Poor")
                    with col2:
                        st.metric("Word Error Rate", f"{wer:.1f}%")
                    with col3:
                        st.metric("Reference Words", len(ref_words))
                    with col4:
                        st.metric("Transcribed Words", len(hyp_words))
                    
                    # Show comparison
                    st.write("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Reference Text:**")
                        st.text(reference_text[:500])
                    with col2:
                        st.write("**Transcribed Text:**")
                        st.text(transcript_text[:500])
                else:
                    st.warning("Please transcribe audio first!")

        with tab4:
            st.subheader("🔎 Search Historical Meetings")
            st.caption("Search saved meeting information using natural-language queries.")
            search_query = st.text_input(
                "Search query",
                placeholder="Which meeting discussed the database migration?",
            )
            if search_query:
                results = semantic_search(search_query, owner_id=current_user_id)
                if results:
                    for result in results:
                        st.markdown(f"**{result['filename']}** · {result['section_type']} · {result['score']:.2f}")
                        st.write(result["content"])
                else:
                    st.info("No matching meeting information found.")

            question = st.text_input(
                "Ask about your meetings",
                placeholder="What deadline was decided for the mobile application?",
                key="rag_question",
            )
            if question and st.button("💬 Answer from meetings"):
                rag_result = answer_question(question, owner_id=current_user_id)
                st.markdown("### Grounded answer")
                st.write(rag_result["answer"])
                st.caption("Sources used")
                for source in rag_result["sources"]:
                    st.write(f"- {source['filename']} ({source['section_type']})")


st.divider()
st.header("Meeting Library")
st.caption("Browse stored meetings, inspect the full record, and export a report for the selected meeting.")

library_meetings = recent_meetings(limit=100, owner_id=current_user_id)
if not library_meetings:
    st.info("No meetings have been saved yet.")
else:
    filter_col, participant_col, period_col = st.columns([2, 1, 1])
    with filter_col:
        library_query = st.text_input("Filter meetings", placeholder="Filename or meeting topic")
    participant_names = sorted({
        participant.get("name", "Unknown")
        for meeting in library_meetings
        for participant in meeting["intelligence"].get("participants", [])
        if participant.get("name")
    })
    with participant_col:
        participant_filter = st.selectbox("Participant", ["All participants", *participant_names])
    with period_col:
        period_filter = st.selectbox("Date range", ["Any time", "Last 7 days", "Last 30 days"])

    cutoff = None
    if period_filter == "Last 7 days":
        cutoff = datetime.now() - timedelta(days=7)
    elif period_filter == "Last 30 days":
        cutoff = datetime.now() - timedelta(days=30)

    filtered_meetings = []
    for item in library_meetings:
        intelligence = item["intelligence"]
        searchable = f"{item['filename']} {intelligence.get('summary', '')}".lower()
        if library_query and library_query.lower() not in searchable:
            continue
        if participant_filter != "All participants" and participant_filter not in {
            person.get("name") for person in intelligence.get("participants", [])
        }:
            continue
        if cutoff:
            try:
                meeting_date = datetime.fromisoformat(item["created_at"])
            except (TypeError, ValueError):
                continue
            if meeting_date < cutoff:
                continue
        filtered_meetings.append(item)

    if not filtered_meetings:
        st.info("No meetings match these filters.")
    else:
        meeting_options = {
            f"#{item['id']} · {item['filename']} · {item['created_at']}": item["id"]
            for item in filtered_meetings
        }
        selected_label = st.selectbox("Select a meeting", list(meeting_options))
        selected_meeting = get_meeting(meeting_options[selected_label], owner_id=current_user_id)
        if selected_meeting:
            intelligence = selected_meeting["intelligence"]
            metric_cols = st.columns(4)
            metric_cols[0].metric("Transcript words", len(selected_meeting["transcript"].split()))
            metric_cols[1].metric("Action items", len(intelligence.get("action_items", [])))
            metric_cols[2].metric("Participants", len(intelligence.get("participants", [])))
            metric_cols[3].metric("Deadlines", len(intelligence.get("deadlines", [])))

            st.subheader(selected_meeting["filename"])
            st.caption(f"Meeting #{selected_meeting['id']} · {selected_meeting['created_at']}")
            st.markdown("#### Summary")
            st.write(intelligence.get("summary", "No summary available."))
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown("#### Key Decisions")
                st.write("\n".join(f"- {item}" for item in intelligence.get("decisions", [])) or "No decisions recorded.")
                st.markdown("#### Action Items")
                actions = intelligence.get("action_items", [])
                if actions:
                    st.dataframe(actions, use_container_width=True, hide_index=True)
                else:
                    st.write("No action items recorded.")
                st.markdown("#### Deadlines")
                deadlines = intelligence.get("deadlines", [])
                if deadlines:
                    st.dataframe(deadlines, use_container_width=True, hide_index=True)
                else:
                    st.write("No deadlines recorded.")
            with detail_col2:
                st.markdown("#### Participants & Responsibilities")
                participants = intelligence.get("participants", [])
                if participants:
                    st.dataframe(participants, use_container_width=True, hide_index=True)
                else:
                    st.write("No participants recorded.")
                st.markdown("#### Transcript")
                st.text_area(
                    "Selected meeting transcript",
                    value=selected_meeting["transcript"],
                    height=260,
                    disabled=True,
                    key=f"meeting_transcript_{selected_meeting['id']}",
                )

            export_col1, export_col2 = st.columns(2)
            with export_col1:
                st.download_button(
                    "Download selected meeting CSV",
                    data=build_meeting_csv(selected_meeting),
                    file_name=f"meeting_{selected_meeting['id']}_report.csv",
                    mime="text/csv",
                    key=f"meeting_csv_{selected_meeting['id']}",
                )
            with export_col2:
                st.download_button(
                    "Download selected meeting PDF",
                    data=build_meeting_pdf(selected_meeting),
                    file_name=f"meeting_{selected_meeting['id']}_report.pdf",
                    mime="application/pdf",
                    key=f"meeting_pdf_{selected_meeting['id']}",
                )

st.divider()
st.header("AI Meeting Assistant")
assistant_question = st.text_input(
    "Ask a question across your saved meetings",
    placeholder="What deadline was decided for the mobile application?",
    key="library_rag_question",
)
if assistant_question and st.button("Search and answer", key="library_rag_submit"):
    assistant_result = answer_question(assistant_question, owner_id=current_user_id)
    st.markdown("#### Answer")
    st.write(assistant_result["answer"])
    if assistant_result["sources"]:
        st.markdown("#### Retrieved sources and context")
        for source in assistant_result["sources"]:
            st.markdown(
                f"**{source['filename']}** · {source['created_at']} · {source['section_type']} · "
                f"meeting #{source['meeting_id']} · score {source['score']:.2f}"
            )
            st.write(source["content"])
    else:
        st.info("No stored meeting context matched that question.")

assistant_search = st.text_input(
    "Search meeting records",
    placeholder="Which meeting discussed the database migration?",
    key="library_search_query",
)
if assistant_search:
    search_results = semantic_search(assistant_search, owner_id=current_user_id)
    if search_results:
        for result in search_results:
            st.markdown(
                f"**{result['filename']}** · {result['created_at']} · {result['section_type']} · "
                f"meeting #{result['meeting_id']} · score {result['score']:.2f}"
            )
            st.write(result["content"])
    else:
        st.info("No matching meeting context was found.")

st.divider()
st.header("Recording Integrations")
if current_user_id is None:
    st.info("Sign in with an account to import recordings into a private meeting library.")
else:
    zoom_col, meet_col = st.columns(2)
    with zoom_col:
        if st.button("Sync Zoom recordings", use_container_width=True):
            try:
                sync_result = sync_zoom_recordings(current_user_id, model_name=model_name)
                st.success(f"Zoom sync: {sync_result['imported']} imported, {sync_result['duplicates']} already present, {sync_result['failed']} failed.")
                for item in sync_result["results"]:
                    if item["status"] == "failed":
                        st.error(f"{item['filename']}: {item['error']}")
            except Exception as error:
                st.error(f"Zoom sync could not run: {error}")
    with meet_col:
        if st.button("Sync Google Meet recordings", use_container_width=True):
            try:
                sync_result = sync_google_meet_recordings(current_user_id, model_name=model_name)
                st.success(f"Google Meet sync: {sync_result['imported']} imported, {sync_result['duplicates']} already present, {sync_result['failed']} failed.")
                for item in sync_result["results"]:
                    if item["status"] == "failed":
                        st.error(f"{item['filename']}: {item['error']}")
            except Exception as error:
                st.error(f"Google Meet sync could not run: {error}")