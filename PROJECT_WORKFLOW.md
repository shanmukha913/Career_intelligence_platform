# Career Intelligence Platform - Project Workflow & Output Guide

## 🎯 **PROJECT PURPOSE**

This is a **Meeting Transcription System** that:
- Converts meeting recordings (audio/video) into text
- Uses AI (Whisper) to transcribe automatically
- Saves transcripts for later reference
- Tests accuracy of transcriptions

---

## 📊 **HIGH-LEVEL WORKFLOW**

```
┌─────────────────┐
│  User Uploads   │
│  Audio File     │
│ (mp3, wav, etc) │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Validation    │  ← Checks if file is valid
│  - Format       │     (format, size, content)
│  - Size         │
│  - Content      │
└────────┬────────┘
         │
         ├─→ ❌ Invalid? → Show Error Message
         │
         ├─→ ✅ Valid? → Continue
         │
         ↓
┌─────────────────┐
│  Load Whisper   │  ← AI model loads
│  AI Model       │     (cached for speed)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Transcribe     │  ← AI listens to audio
│  Audio          │     and converts to text
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Validate       │  ← Check if transcription
│  Transcript     │     is valid/complete
└────────┬────────┘
         │
         ├─→ ❌ Invalid? → Show Error
         │
         ├─→ ✅ Valid? → Continue
         │
         ↓
┌─────────────────┐
│  Save Files     │  ← Store results
│  - Transcript   │
│  - Metadata     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Display to     │  ← Show to user
│  User in UI     │     in Streamlit app
└─────────────────┘
```

---

## 🔄 **DETAILED WORKFLOW**

### **Step 1: Upload Audio File**

**What happens:**
```
User selects file from computer
        ↓
File loads into memory
        ↓
System reads file info:
  - File name: meeting.mp3
  - File size: 45.3 MB
  - File type: .mp3
```

**Example:**
- Upload: `meeting_001.mp3` (45.3 MB)

---

### **Step 2: Validation**

**What gets checked:**

| Check | Details | Result |
|-------|---------|--------|
| **Format** | Is it .mp3, .wav, .m4a, .mp4, .webm, .m4b, or .ogg? | ✅ YES → Continue |
| **Size** | Is file ≤ 500MB? | ✅ YES → Continue |
| **Empty** | Is file > 0 KB? | ✅ YES → Continue |

**If any check fails:**
```
❌ Error Message:
   "Format '.pdf' not supported. Allowed: mp3, wav, m4a..."
   "File size (567.89MB) exceeds 500MB limit"
   "File is empty"
```

---

### **Step 3: Load Whisper Model**

**What is Whisper?**
- OpenAI's speech-to-text AI model
- Trained on 680,000 hours of audio
- Supports 99+ languages
- Runs locally (no internet needed after download)

**Models Available:**
```
tiny    → 39M   (fastest, least accurate)
base    → 72M   (good balance)     ← DEFAULT
small   → 244M  (better accuracy)
medium  → 769M  (good accuracy)
large   → 2.9GB (best accuracy)
```

**First time:**
- Model downloads (~72MB for base)
- Stored in: `C:\Users\[username]\.cache\whisper\`
- Takes ~2-5 minutes first run

**After first time:**
- Model is cached
- Loads in ~10-30 seconds

---

### **Step 4: Transcription**

**What happens:**

```
Audio file (meeting.mp3)
  ↓ [AI listens]
  ↓ [Processes audio]
  ↓ [Converts to text]
  ↓
Output: Full transcript text
```

**Example Input:** Audio file 45 minutes long
**Example Output:** 5,200+ words of transcript text

---

### **Step 5: Validation**

**Transcript checked for:**

| Check | Details |
|-------|---------|
| **Not Empty** | Does transcript have text? |
| **Length** | Is it ≥ 10 characters? |
| **Success** | Did transcription complete without errors? |

---

### **Step 6: Saving**

**Files Created:**

1. **Transcript Text File**
   ```
   Location: transcripts/
   Filename: meeting_001_20260829_143025.txt
   Contains: Full transcription text
   Size: ~10-50 KB
   ```

2. **Metadata JSON File**
   ```
   Location: transcripts/
   Filename: meeting_001_20260829_143025_metadata.json
   Contains: File info, timestamps, word count
   Size: ~1-2 KB
   ```

---

## 📤 **OUTPUTS EXPLAINED**

### **Output 1: Transcript Text File** 📄

**File Location:**
```
C:\Users\Windows\Downloads\Career_Intelligence_platform\
    └── transcripts\
        └── meeting_001_20260829_143025.txt
```

**File Contents:**
```
Good morning everyone. Thank you for joining today's meeting.
We're going to discuss Q4 planning and budget allocation.

Let's start with the revenue projections. As you can see
in the presentation, we're expecting a 15% increase...

[continues with full transcript]
```

**Properties:**
- Format: Plain text (.txt)
- Encoding: UTF-8
- Size: Depends on audio length
  - 30-min audio → ~3,000-5,000 words
  - 1-hour audio → ~6,000-10,000 words
  - 2-hour audio → ~12,000-20,000 words

**Downloadable:** Yes! Click "Download Transcript" button in UI

---

### **Output 2: Metadata JSON File** 📊

**File Location:**
```
C:\Users\Windows\Downloads\Career_Intelligence_platform\
    └── transcripts\
        └── meeting_001_20260829_143025_metadata.json
```

**File Contents:**
```json
{
  "original_file": "meeting_001.mp3",
  "timestamp": "20260829_143025",
  "transcription_date": "2026-08-29T14:30:25.123456",
  "transcript_length": 5432,
  "word_count": 823
}
```

**What Each Field Means:**
| Field | Meaning | Example |
|-------|---------|---------|
| `original_file` | Original audio file name | meeting_001.mp3 |
| `timestamp` | When transcribed (Date_Time) | 20260829_143025 |
| `transcription_date` | Full timestamp (ISO format) | 2026-08-29T14:30:25 |
| `transcript_length` | Character count (with spaces) | 5432 |
| `word_count` | Number of words | 823 |

---

### **Output 3: Streamlit UI Display** 💻

**What User Sees:**

```
🎙️ Meeting Transcription System

📤 Upload Audio File        ⚙️ Settings
[File Uploader]             Model: base ▼
Choose file...
✅ File uploaded: meeting_001.mp3 (45.3MB)

┌─────────────────────────────────────┐
│ Transcribe | View Transcripts        │
├─────────────────────────────────────┤
│                                     │
│ Progress: ████████░░░░░░░░░░ 60%   │
│ Status: 🔄 Step 3/5: Processing    │
│ audio and generating transcript...  │
│                                     │
│ Transcript:                         │
│ ┌───────────────────────────────┐   │
│ │ Good morning everyone. Thank  │   │
│ │ you for joining today's       │   │
│ │ meeting. We're going to       │   │
│ │ discuss Q4 planning and...    │   │
│ │                               │   │
│ │ [scrollable text area]        │   │
│ └───────────────────────────────┘   │
│                                     │
│ 📊 Transcript Details               │
│   Word Count: 823                   │
│   Character Count: 5432             │
│   Saved At: 20260829_143025         │
│                                     │
│ [📥 Download Transcript (TXT)]      │
└─────────────────────────────────────┘

📋 Saved Transcripts
┌─────────────────────────────────────┐
│ 📄 meeting_001.mp3 | Words: 823     │
│ [📥 Download]                       │
│                                     │
│ 📄 meeting_002.wav | Words: 1247    │
│ [📥 Download]                       │
└─────────────────────────────────────┘
```

---

## 🧪 **OUTPUT FROM ACCURACY TESTING**

### **Accuracy Test Report** 📈

**File Location:**
```
C:\Users\Windows\Downloads\Career_Intelligence_platform\
    └── accuracy_reports\
        └── report_20260829_143025.json
```

**Report Contents:**
```json
{
  "summary": {
    "total_tests": 3,
    "average_accuracy": 92.45,
    "average_wer": 7.55,
    "average_cer": 3.21,
    "average_similarity": 95.67,
    "passed_tests": 3,
    "target_met": true
  },
  "detailed_results": [
    {
      "file": "meeting1.mp3",
      "reference_length": 850,
      "hypothesis_length": 823,
      "word_error_rate": 6.5,
      "character_error_rate": 2.8,
      "similarity_ratio": 96.2,
      "accuracy": 93.5,
      "timestamp": "2026-08-29T14:30:25"
    },
    {
      "file": "meeting2.wav",
      "word_error_rate": 8.2,
      "accuracy": 91.8,
      ...
    },
    ...
  ]
}
```

**What These Metrics Mean:**

| Metric | Meaning | Example | Target |
|--------|---------|---------|--------|
| **Accuracy** | % of words transcribed correctly | 93.5% | ≥ 90% |
| **Word Error Rate (WER)** | % of words that had errors | 6.5% | ≤ 10% |
| **Character Error Rate (CER)** | % of characters that had errors | 2.8% | ≤ 5% |
| **Similarity Ratio** | Overall text similarity (0-100) | 96.2% | ≥ 90% |

---

## 📁 **COMPLETE FILE STRUCTURE AFTER RUNNING**

```
Career_Intelligence_platform/
│
├── app.py                           ← Main application
├── accuracy_testing.py              ← Testing framework
├── requirements.txt                 ← Dependencies
│
├── uploads/                         ← User uploaded files (temporary)
│   ├── meeting_001.mp3
│   └── meeting_002.wav
│
├── transcripts/                     ← ⭐ OUTPUT FILES HERE ⭐
│   ├── meeting_001_20260829_143025.txt
│   ├── meeting_001_20260829_143025_metadata.json
│   ├── meeting_002_20260829_143526.txt
│   └── meeting_002_20260829_143526_metadata.json
│
├── accuracy_reports/                ← ⭐ TEST REPORTS HERE ⭐
│   └── report_20260829_143025.json
│
└── test_recordings/                 ← Test audio files (for accuracy testing)
    ├── test_1.mp3
    └── test_2.wav
```

---

## 🔁 **COMPLETE EXAMPLE WORKFLOW**

### **Scenario: Transcribe a 30-minute meeting**

**Input:**
```
File: team_meeting.mp3
Size: 42.5 MB
Duration: 30 minutes
```

**Process (Timeline):**
```
00:00 → User uploads file
00:05 → Validation complete (✅ valid)
00:10 → Whisper model loads
01:30 → Transcription starts
05:45 → Transcription complete (30 min audio ≈ 5 min processing)
05:50 → Validation check (✅ valid)
05:52 → Files saved
05:53 → Displayed to user
```

**Output Files Created:**

1. **Transcript:**
   ```
   File: team_meeting_20260829_145353.txt
   Content: ~5,500 words of meeting text
   Size: ~32 KB
   ```

2. **Metadata:**
   ```
   File: team_meeting_20260829_145353_metadata.json
   Content: {
     "original_file": "team_meeting.mp3",
     "timestamp": "20260829_145353",
     "word_count": 5523,
     "transcript_length": 31452
   }
   ```

**UI Shows:**
- ✅ Full transcript text (scrollable)
- 📊 Word count: 5,523
- 💾 Timestamp: 20260829_145353
- 📥 Download button (ready to save locally)

---

## 📝 **KEY POINTS TO UNDERSTAND**

1. **Input:** Audio/Video file (mp3, wav, m4a, mp4, webm, m4b, ogg)
2. **Processing:** Whisper AI converts speech → text
3. **Validation:** Checks if file and transcript are valid
4. **Output:** 
   - Transcript text file (.txt)
   - Metadata file (.json)
   - Display in Streamlit UI
   - Downloadable results

5. **Storage:** All files saved in `transcripts/` folder with timestamp

6. **Accuracy:** Tested with WER, CER, and similarity metrics
   - Target: ≥90% accuracy
   - If met: System is production-ready

---

## ⚡ **QUICK START TO SEE IT IN ACTION**

```bash
# 1. Start the app
streamlit run app.py

# 2. Upload any MP3 or WAV file (30 seconds - 10 minutes recommended)

# 3. Click "Transcribe"

# 4. Watch the 5-step progress

# 5. See output in UI

# 6. Check transcripts/ folder for saved files
```

---

## ❓ **COMMON QUESTIONS**

**Q: Where do transcripts get saved?**
A: `Career_Intelligence_platform\transcripts\` folder on your computer

**Q: Can I download the transcript?**
A: Yes! Click "Download Transcript (TXT)" button in the UI

**Q: How long does it take?**
A: ~1-2 min per 10 min of audio (depends on computer speed and model)

**Q: What if transcription is wrong?**
A: That's where accuracy testing comes in. Bigger Whisper models are more accurate.

**Q: Can I use recorded meetings/podcasts?**
A: Yes! Any audio format supported (mp3, wav, m4a, mp4, webm, m4b, ogg)

**Q: Is internet required?**
A: Only first download of model. After that, everything runs offline.

---

## 🎯 **SUMMARY**

| Aspect | Details |
|--------|---------|
| **Purpose** | Convert meeting recordings to text automatically |
| **Input** | Audio/Video files (8 formats) |
| **Processing** | Whisper AI transcribes speech → text |
| **Validation** | Checks file validity and transcript quality |
| **Output** | Text transcript + metadata + UI display |
| **Storage** | Files saved in `transcripts/` folder |
| **Testing** | Accuracy testing with WER/CER metrics |
| **Target Accuracy** | ≥ 90% word accuracy |

---
