import streamlit as st
import whisper
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import tempfile
import csv
import io
from llm_service import process_transcript
from meeting_db import init_db, save_meeting, recent_meetings

# Page Configuration
st.set_page_config(
    page_title="Meeting Transcriber",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ Meeting Transcription System")
st.write("Upload a meeting recording and generate a transcript using Whisper.")

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("transcripts", exist_ok=True)
os.makedirs("cache", exist_ok=True)
init_db()

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


def save_transcript(transcript_text, filename):
    """
    Save transcript to file
    Returns: (success, filepath)
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(filename).stem
        transcript_filename = f"{base_name}_{timestamp}.txt"
        transcript_path = os.path.join("transcripts", transcript_filename)
        
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
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="section-label">📤 Upload Audio File</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Select a meeting recording",
        type=["mp3", "wav", "m4a", "mp4", "webm", "m4b", "ogg"],
        help="Maximum file size: 500MB. No need to manually save - upload directly!"
    )

with col2:
    st.markdown('<div class="section-label">⚙️ Settings</div>', unsafe_allow_html=True)
    model_name = st.selectbox(
        "Whisper Model",
        ["base", "small"],
        index=0,
        help="base: Fast + Good accuracy | small: Better accuracy but slower"
    )

    # Show model info
    model_info = {
        "base": "🚀 Fast | ~85-90% accuracy | ~5-10 sec/min",
        "small": "⚡ Medium | ~90-95% accuracy | ~15-20 sec/min"
    }
    st.caption(model_info[model_name])

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
        file_hash = get_file_hash(file_bytes)
        
        # Check if already transcribed
        cached_result = get_cached_transcript(file_hash)
        
        if cached_result:
            st.info("💾 This file was already transcribed! Using cached result (instant).")
        
        # Create two tabs for transcription and results
        tab1, tab2, tab3 = st.tabs(["Transcribe", "View Transcripts", "Verify Accuracy"])
        
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
                            success, filepath, metadata = save_transcript(transcript_text, uploaded_file.name)
                            
                            if success:
                                progress_bar.progress(100)
                                status_text.success("✅ Transcription completed successfully!")
                                try:
                                    meeting_intelligence = process_transcript(transcript_text)
                                    meeting_id = save_meeting(
                                        uploaded_file.name,
                                        transcript_text,
                                        meeting_intelligence,
                                    )
                                    st.session_state["meeting_intelligence"] = meeting_intelligence
                                    st.session_state["meeting_id"] = meeting_id
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
                    st.subheader("📄 Transcript Result")
                    transcript_text = transcript_result["text"]
                    
                    st.text_area(
                        "Transcript:",
                        value=transcript_text,
                        height=300,
                        disabled=True
                    )
                    
                    # Display metadata with accuracy info
                    col1, col2, col3, col4 = st.columns(4)
                    word_count = len(transcript_text.split())
                    char_count = len(transcript_text)
                    
                    with col1:
                        st.metric("Word Count", word_count)
                    with col2:
                        st.metric("Character Count", char_count)
                    with col3:
                        st.metric("Model Used", model_name)
                    with col4:
                        if model_name == "base":
                            accuracy = "85-90%"
                        else:
                            accuracy = "90-95%"
                        st.metric("Est. Accuracy", accuracy)
                    
                    intelligence = st.session_state.get("meeting_intelligence") or process_transcript(transcript_text)
                    st.session_state["meeting_intelligence"] = intelligence

                    # Download option
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    col_download1, col_download2 = st.columns(2)
                    with col_download1:
                        st.download_button(
                            label="📥 Download Transcript (TXT)",
                            data=transcript_text,
                            file_name=f"transcript_{timestamp}.txt",
                            mime="text/plain"
                        )
                    with col_download2:
                        st.download_button(
                            label="📊 Download Summary (CSV)",
                            data=build_csv_export(transcript_text, intelligence),
                            file_name=f"meeting_summary_{timestamp}.csv",
                            mime="text/csv"
                        )

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

                    with insight_col2:
                        st.markdown("#### Action Items")
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

            stored_meetings = recent_meetings()
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

            transcript_files = list(Path("transcripts").glob("*_metadata.json"))
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