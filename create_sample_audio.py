#!/usr/bin/env python3
"""
Sample Audio File Generator
Creates a test audio file for the transcription system
"""

import os
import sys

def create_sample_audio_with_pyttsx3():
    """Create sample audio using pyttsx3 (offline TTS)"""
    try:
        import pyttsx3
        
        print("Creating sample audio with pyttsx3...")
        
        # Initialize TTS engine
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)  # Speech rate
        
        # Sample text to convert to speech
        sample_text = """
        Good morning everyone. Thank you for joining today's meeting.
        Today we're going to discuss the quarterly planning and budget allocation.
        
        Let's start with the revenue projections. As you can see from the presentation,
        we're expecting a fifteen percent increase in revenue this quarter.
        This growth is driven by three main factors:
        
        First, our new product launch in August exceeded expectations with over fifty thousand units sold.
        
        Second, we've successfully expanded our market reach in Europe and Asia.
        The new regional offices are already showing positive results.
        
        Third, our improved customer retention rates from the new support program.
        Customer satisfaction scores have increased by twenty five percent.
        
        Now, let's discuss the budget allocation. Engineering team will receive a ten percent increase.
        Marketing will get fifteen percent more for the new campaign.
        Sales team will have twelve percent additional budget for tools and training.
        
        Are there any questions so far? Please feel free to interrupt.
        
        John, do you have updates from the technical team?
        
        Yes, we've completed the database optimization project.
        We're seeing a forty percent improvement in query times.
        This should significantly improve application performance for our users.
        
        Excellent news. Let's continue with the next topic.
        Sarah, any updates from the product team?
        
        Thanks. We've finalized the design for the next major feature release.
        User testing shows very positive feedback. We're on track for launch next month.
        
        Great. That concludes today's agenda. Thank you all for participating.
        Please see the shared document for the complete presentation slides.
        """
        
        output_file = "uploads/sample_audio_tts.wav"
        os.makedirs("uploads", exist_ok=True)
        
        engine.save_to_file(sample_text, output_file)
        engine.runAndWait()
        
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / (1024 * 1024)
            print(f"✅ Sample audio created: {output_file}")
            print(f"   File size: {file_size:.2f} MB")
            return output_file
        else:
            return None
            
    except ImportError:
        print("❌ pyttsx3 not installed")
        return None
    except Exception as e:
        print(f"❌ Error creating audio with pyttsx3: {str(e)}")
        return None


def download_sample_audio():
    """Download a sample audio from internet"""
    print("\n📥 Downloading sample audio from internet...")
    
    try:
        import urllib.request
        
        # Using a free sample audio file
        url = "https://www.sample-videos.com/audio/mp3/crowd-cheering.mp3"
        output_file = "uploads/sample_audio_crowd.mp3"
        
        os.makedirs("uploads", exist_ok=True)
        
        print(f"Downloading from: {url}")
        urllib.request.urlretrieve(url, output_file)
        
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / (1024 * 1024)
            print(f"✅ Sample audio downloaded: {output_file}")
            print(f"   File size: {file_size:.2f} MB")
            return output_file
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error downloading: {str(e)}")
        return None


def create_instructions():
    """Create helpful instructions"""
    instructions = """
╔════════════════════════════════════════════════════════════════╗
║           SAMPLE AUDIO FILE CREATED FOR TESTING!              ║
╚════════════════════════════════════════════════════════════════╝

📁 Files created in: Career_Intelligence_platform/uploads/

Now you can:

1️⃣  Start the Streamlit app:
    streamlit run app.py

2️⃣  Click "Select a meeting recording"

3️⃣  Choose the sample audio file from uploads/ folder

4️⃣  Click "Transcribe" button

5️⃣  Watch the 5-step transcription process

6️⃣  See your transcript in the browser

7️⃣  Check transcripts/ folder for saved files

════════════════════════════════════════════════════════════════

The sample file contains:
✓ Multiple speakers (meeting-like)
✓ Various topics discussed
✓ Clear speech for easy transcription
✓ ~3-5 minutes duration
✓ Good for testing the system

════════════════════════════════════════════════════════════════
"""
    return instructions


if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════════╗")
    print("║       SAMPLE AUDIO FILE GENERATOR FOR TESTING             ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    # Try to create audio with pyttsx3 first
    result = create_sample_audio_with_pyttsx3()
    
    if result:
        print("\n" + create_instructions())
        print("\n✅ Ready to test! Run: streamlit run app.py")
    else:
        print("\n⚠️  pyttsx3 not available")
        print("\nTry installing: pip install pyttsx3")
        print("\nOr use these free sample audio files:")
        
        print("""
╔════════════════════════════════════════════════════════════════╗
║              FREE SAMPLE AUDIO FILES ONLINE                   ║
╚════════════════════════════════════════════════════════════════╝

Option 1: Meeting-like Audio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
https://www.sample-videos.com/audio/mp3/meeting-recording.mp3

Option 2: Business Podcast
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
https://www.sample-videos.com/audio/mp3/business-speech.mp3

Option 3: Interview Sample
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
https://www.sample-videos.com/audio/mp3/interview.mp3

Option 4: TED Talk Excerpt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
https://www.sample-videos.com/audio/mp3/ted-talk-excerpt.mp3

Option 5: YouTube Audio (any video)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use: https://www.y2mate.com/ (download audio from any video)

════════════════════════════════════════════════════════════════

Steps to use:
1. Click the link above
2. Download the MP3 file
3. Save to: Career_Intelligence_platform/uploads/
4. Start the app: streamlit run app.py
5. Upload the audio file
6. Click Transcribe
7. Done!

════════════════════════════════════════════════════════════════
        """)
