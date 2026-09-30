# Project Data Flow - Visual Guide

## 🔄 **COMPLETE DATA FLOW**

```
╔════════════════════════════════════════════════════════════════════════╗
║              CAREER INTELLIGENCE PLATFORM - DATA FLOW                  ║
╚════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────┐
│ INPUT: Audio/Video File                                              │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Example: meeting.mp3                                                │
│    • Format: MP3                                                     │
│    • Size: 42.5 MB                                                   │
│    • Duration: 30 minutes                                            │
│    • Speaker: Multiple (Manager, Dev 1, Dev 2, etc.)               │
│                                                                       │
│  Supported Formats:                                                  │
│    ✓ MP3  ✓ WAV  ✓ M4A  ✓ MP4  ✓ WEBM  ✓ M4B  ✓ OGG                │
│                                                                       │
│  Max Size: 500 MB                                                    │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER UPLOADS FILE                                            │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  File: meeting.mp3                                                   │
│  ↓                                                                    │
│  Loaded into memory                                                  │
│  ↓                                                                    │
│  File info extracted                                                 │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2: VALIDATION                                                   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Check 1: File Format?                                               │
│    Input: meeting.mp3                                                │
│    Expected: [mp3, wav, m4a, mp4, webm, m4b, ogg]                  │
│    Result: ✅ PASS                                                   │
│                                                                       │
│  Check 2: File Size?                                                 │
│    Input: 42.5 MB                                                    │
│    Expected: ≤ 500 MB                                                │
│    Result: ✅ PASS                                                   │
│                                                                       │
│  Check 3: File Not Empty?                                            │
│    Input: 42.5 MB                                                    │
│    Expected: > 0 KB                                                  │
│    Result: ✅ PASS                                                   │
│                                                                       │
│  Final Result: ✅ ALL CHECKS PASSED → CONTINUE                       │
│  (If any fail: ❌ Show error message & stop)                         │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3: LOAD WHISPER AI MODEL                                        │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Available Models:                                                   │
│  ┌──────────┬────────┬─────────────┬──────────────┐                 │
│  │ Model    │ Size   │ Speed       │ Accuracy     │                 │
│  ├──────────┼────────┼─────────────┼──────────────┤                 │
│  │ tiny     │ 39 MB  │ ⚡⚡⚡⚡⚡ Fast  │ ✦✦ Low     │                 │
│  │ base     │ 72 MB  │ ⚡⚡⚡ Normal │ ✦✦✦ Medium  │ ← DEFAULT       │
│  │ small    │ 244 MB │ ⚡⚡ Slower  │ ✦✦✦✦ Good   │                 │
│  │ medium   │ 769 MB │ ⚡ Slowest  │ ✦✦✦✦✦ Great │                 │
│  │ large    │ 2.9 GB │ 🐢 Very Slow│ ✦✦✦✦✦ Best  │                 │
│  └──────────┴────────┴─────────────┴──────────────┘                 │
│                                                                       │
│  Selected: base model                                                │
│    ↓                                                                  │
│  First time?                                                         │
│    → Download from OpenAI (~72 MB, takes 2-5 min)                   │
│    → Save to: C:\Users\[username]\.cache\whisper\                   │
│                                                                       │
│  After first time?                                                   │
│    → Load from cache (takes 10-30 seconds)                           │
│                                                                       │
│  Status: ✅ MODEL READY                                              │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 4: TRANSCRIBE AUDIO WITH WHISPER                               │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Input Audio File                                                    │
│  ├─ File: meeting.mp3                                                │
│  ├─ Duration: 30 minutes (1,800 seconds)                             │
│  ├─ Sample Rate: 44.1 kHz                                            │
│  ├─ Channels: Stereo                                                 │
│  └─ Content: Multiple speakers discussing Q4 planning                │
│                                                                       │
│  Processing Inside Whisper:                                          │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Raw Audio Bytes (1,800 sec × 44,100 Hz × 2 channels)     │    │
│  │           ↓                                               │    │
│  │ Convert to 16 kHz mono (Whisper standard)                │    │
│  │           ↓                                               │    │
│  │ Extract Audio Features (Mel-spectrograms)                │    │
│  │           ↓                                               │    │
│  │ AI Encoder: "What are these audio features?"             │    │
│  │           ↓                                               │    │
│  │ AI Decoder: "These features mean: word1 word2 word3..."  │    │
│  │           ↓                                               │    │
│  │ Output: Text Tokens → Convert to Words                   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Result: Complete Transcript Text                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  "Good morning everyone. Thank you for joining. Today we're          │
│   going to discuss Q4 planning and budget allocation. Let's start    │
│   with the revenue projections. As you can see from the slide,       │
│   we're expecting a 15% increase in revenue. That's driven by        │
│   three main factors: first, our new product launch in August;       │
│   second, expanded market reach in Europe; and third, improved       │
│   customer retention rates from our new support program.             │
│   [continues for ~5,500+ words]"                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│                                                                       │
│  Statistics:                                                         │
│  • Total Words: 5,523                                                │
│  • Total Characters: 31,452                                          │
│  • Processing Time: ~5 minutes (30 min audio ÷ 6 = 5 min)           │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 5: VALIDATE TRANSCRIPT                                          │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Validation Check 1: Has Text?                                       │
│    Input: Transcript text                                            │
│    Check: Is it not None/null?                                       │
│    Result: ✅ YES (5,523 words)                                      │
│                                                                       │
│  Validation Check 2: Not Empty?                                      │
│    Input: Stripped text                                              │
│    Check: Does it have length > 0?                                   │
│    Result: ✅ YES (31,452 characters)                                │
│                                                                       │
│  Validation Check 3: Minimum Length?                                 │
│    Input: Text length                                                │
│    Check: Is length ≥ 10 characters?                                 │
│    Result: ✅ YES (31,452 ≥ 10)                                      │
│                                                                       │
│  Final Result: ✅ TRANSCRIPT VALID → SAVE                            │
│  (If any check fails: ❌ Show error & stop)                          │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 6: SAVE FILES                                                   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Timestamp Generated: 20260829_143025                                │
│                      (Date_Time: Aug 29, 2026 at 14:30:25)           │
│                                                                       │
│  FILE 1: Transcript Text (.txt)                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Location:                                                     │  │
│  │   transcripts/meeting_20260829_143025.txt                    │  │
│  │                                                               │  │
│  │ Contents:                                                     │  │
│  │   Good morning everyone. Thank you for joining...            │  │
│  │   [5,523 words of complete meeting transcript]               │  │
│  │                                                               │  │
│  │ Properties:                                                   │  │
│  │   • Format: Plain Text                                        │  │
│  │   • Encoding: UTF-8                                           │  │
│  │   • Size: ~31 KB                                              │  │
│  │   • Lines: 127                                                │  │
│  │   • Words: 5,523                                              │  │
│  │   • Characters: 31,452                                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  FILE 2: Metadata (JSON)                                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Location:                                                     │  │
│  │   transcripts/meeting_20260829_143025_metadata.json          │  │
│  │                                                               │  │
│  │ Contents (JSON Format):                                       │  │
│  │ {                                                             │  │
│  │   "original_file": "meeting.mp3",                            │  │
│  │   "timestamp": "20260829_143025",                            │  │
│  │   "transcription_date": "2026-08-29T14:30:25.123456",        │  │
│  │   "transcript_length": 31452,                                │  │
│  │   "word_count": 5523                                         │  │
│  │ }                                                             │  │
│  │                                                               │  │
│  │ Size: ~1.2 KB                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Status: ✅ FILES SAVED SUCCESSFULLY                                 │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 7: DISPLAY IN STREAMLIT UI                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  Browser Display (http://localhost:8501):                            │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ 🎙️ Meeting Transcription System                           │    │
│  │                                                            │    │
│  │ 📤 Upload Audio File          ⚙️ Settings                 │    │
│  │ [File Uploader]               Model: base                 │    │
│  │ File uploaded: meeting.mp3                                │    │
│  │ (42.5 MB)                                                 │    │
│  │                                                            │    │
│  │ [Transcribe] | [View Transcripts]                         │    │
│  │                                                            │    │
│  │ ✅ TRANSCRIPTION COMPLETE                                 │    │
│  │                                                            │    │
│  │ 📄 Transcript Result                                       │    │
│  │ ┌──────────────────────────────────────────────────────┐  │    │
│  │ │ Good morning everyone. Thank you for joining        │  │    │
│  │ │ today's meeting. We're going to discuss Q4          │  │    │
│  │ │ planning and budget allocation. Let's start...      │  │    │
│  │ │                                                      │  │    │
│  │ │ [scrollable - 5,523 words total]                    │  │    │
│  │ └──────────────────────────────────────────────────────┘  │    │
│  │                                                            │    │
│  │ 📊 Transcript Details                                      │    │
│  │   Word Count: 5,523                                        │    │
│  │   Character Count: 31,452                                  │    │
│  │   Saved At: 20260829_143025                                │    │
│  │                                                            │    │
│  │ [📥 Download Transcript (TXT)]                            │    │
│  │                                                            │    │
│  │ ────────────────────────────────────────────────────────  │    │
│  │ 📋 Saved Transcripts                                       │    │
│  │ 📄 meeting.mp3 | Words: 5,523 [📥 Download]               │    │
│  │ 📄 other.wav | Words: 8,234 [📥 Download]                 │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Status: ✅ DISPLAYED IN BROWSER                                     │
└─────────────────────────────────────────────┬────────────────────────┘
                                              │
                                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ OUTPUT: Generated Files & Display                                    │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                                       │
│  ✅ OUTPUT 1: Transcript Text File                                   │
│     Location: transcripts/meeting_20260829_143025.txt               │
│     Size: 31 KB                                                     │
│     Content: 5,523 words of full meeting transcript                 │
│                                                                       │
│  ✅ OUTPUT 2: Metadata JSON File                                     │
│     Location: transcripts/meeting_20260829_143025_metadata.json     │
│     Size: 1.2 KB                                                    │
│     Content: File info, timestamps, statistics                      │
│                                                                       │
│  ✅ OUTPUT 3: Browser Display                                        │
│     Platform: Streamlit Web UI                                      │
│     URL: http://localhost:8501                                      │
│     Content: Full transcript + metadata + download                  │
│                                                                       │
│  ✅ OUTPUT 4: Optional Download                                      │
│     Format: .txt file                                               │
│     Location: User's Downloads folder                               │
│     Content: Same as OUTPUT 1                                       │
│                                                                       │
│  ✅ OPTIONAL: Accuracy Test Report                                   │
│     Location: accuracy_reports/report_20260829_143025.json         │
│     Content: WER, CER, Accuracy, Similarity metrics                │
└──────────────────────────────────────────────────────────────────────┘

╔════════════════════════════════════════════════════════════════════════╗
║                           TOTAL PROCESSING TIME                        ║
║                                                                        ║
║  30-minute meeting audio:                                              ║
║   • Upload: ~30 seconds                                                ║
║   • Validation: ~5 seconds                                             ║
║   • Model Load: ~10-30 seconds (first time: 2-5 minutes)              ║
║   • Transcription: ~5 minutes (30 min audio ÷ 6 = ~5 min)             ║
║   • Validation: ~5 seconds                                             ║
║   • Save Files: ~3 seconds                                             ║
║   ────────────────────────────────────────────────                    ║
║   TOTAL: ~6 minutes (after model cached: ~5.5 minutes)               ║
╚════════════════════════════════════════════════════════════════════════╝
```

---

## **DATA SIZE REFERENCE**

```
Typical Audio Durations and Output Sizes:

Duration → Processing Time → Transcript Words → File Size (KB)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5 min   → 1 min            → 600-750 words   → 4-5 KB
10 min  → 2 min            → 1,200-1,500     → 8-10 KB
30 min  → 5 min            → 3,600-4,500     → 25-32 KB
60 min  → 10 min           → 7,200-9,000     → 50-64 KB
90 min  → 15 min           → 10,800-13,500   → 75-96 KB
```

---

## **QUALITY OF TRANSCRIPTION**

```
Accuracy Depends On:

1. Audio Quality
   ┌─ Clear speech, low background noise → 95%+ accuracy
   ├─ Moderate noise, clear speakers → 90-95% accuracy
   ├─ Some echo, multiple speakers → 85-90% accuracy
   └─ Heavy noise, unclear speech → <85% accuracy

2. Model Size
   ┌─ tiny/base → 80-90% on clear audio
   ├─ small → 85-93% on clear audio
   ├─ medium → 90-96% on clear audio
   └─ large → 93-98% on clear audio

3. Language
   ┌─ English → Best performance
   ├─ European languages → Very good
   ├─ Asian languages → Good
   └─ Rare languages → Fair to good

Combined Effect:
   Clear English + Large Model = 95-98% Accuracy ✅
   Noisy Audio + Tiny Model = 70-80% Accuracy ⚠️
```

---

## **WHERE FILES LIVE**

```
Your Computer Folder Structure:

C:\Users\Windows\Downloads\Career_Intelligence_platform\
│
├── 📄 app.py                              ← Main application
├── 📄 accuracy_testing.py                 ← Testing tool
├── 📄 requirements.txt                    ← Dependencies
│
├── 📁 uploads/                            ← User uploads
│   └── meeting.mp3 (temporary)
│
├── 📁 transcripts/                        ⭐ YOUR OUTPUTS GO HERE ⭐
│   ├── meeting_20260829_143025.txt               ← Transcript
│   ├── meeting_20260829_143025_metadata.json     ← Metadata
│   ├── other_20260829_145530.txt
│   └── other_20260829_145530_metadata.json
│
├── 📁 accuracy_reports/                   ⭐ TEST RESULTS HERE ⭐
│   └── report_20260829_143025.json              ← Accuracy report
│
└── 📁 test_recordings/                    ← Test audio files
    └── test_*.mp3

Cache Folder (Auto-created):
C:\Users\Windows\.cache\whisper\
├── base.pt          ← Downloaded model
├── small.pt         ← (if downloaded)
└── medium.pt        ← (if downloaded)
```

---
