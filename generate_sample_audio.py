#!/usr/bin/env python3
"""
Simple Sample Audio Generator
Creates a WAV audio file for testing transcription
"""

import numpy as np
from scipy.io import wavfile
import os

def create_sample_wav_file():
    """Create a sample audio WAV file with spoken text simulation"""
    
    print("Creating sample audio file...")
    
    # Audio parameters
    sample_rate = 22050  # Hz
    duration = 30  # seconds
    frequency = 440  # Hz (A4 note - base frequency for speech simulation)
    
    # Create time array
    t = np.linspace(0, duration, sample_rate * duration, False)
    
    # Create a more complex sound that mimics speech patterns
    # Mix multiple frequencies to simulate speech
    
    # Base frequencies for different phonemes
    frequencies = [
        200, 300, 400,  # Lower frequencies
        500, 600, 700,  # Mid frequencies
        800, 900, 1000, # Higher frequencies
    ]
    
    # Build waveform by mixing multiple sine waves with varying amplitudes
    waveform = np.zeros_like(t)
    
    for i, freq in enumerate(frequencies):
        # Varying amplitude for naturalness
        amplitude = 0.1 / (i + 1)
        # Add sine wave
        waveform += amplitude * np.sin(2 * np.pi * freq * t)
    
    # Add some amplitude modulation (envelope) to simulate speaking
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 0.2 * t))  # Slow modulation
    waveform = waveform * envelope
    
    # Normalize to prevent clipping
    waveform = (waveform / np.max(np.abs(waveform))) * 0.8
    
    # Convert to 16-bit audio
    waveform_int16 = np.int16(waveform * 32767)
    
    # Create uploads directory
    os.makedirs("uploads", exist_ok=True)
    
    # Save WAV file
    output_file = os.path.join("uploads", "sample_audio_generated.wav")
    wavfile.write(output_file, sample_rate, waveform_int16)
    
    file_size = os.path.getsize(output_file) / 1024
    print(f"✅ Sample audio file created!")
    print(f"   File: {output_file}")
    print(f"   Duration: {duration} seconds")
    print(f"   Sample Rate: {sample_rate} Hz")
    print(f"   File Size: {file_size:.1f} KB")
    print(f"   Format: WAV (44.1 kHz, 16-bit)")
    
    return output_file


if __name__ == "__main__":
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║      SAMPLE AUDIO FILE GENERATOR                          ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    try:
        audio_file = create_sample_wav_file()
        
        print("\n" + "="*60)
        print("✅ SUCCESS! Sample audio file created")
        print("="*60)
        print("\n📍 File Location:")
        print(f"   {os.path.abspath(audio_file)}\n")
        
        print("🚀 NEXT STEPS:")
        print("─" * 60)
        print("1. Start the Streamlit app:")
        print("   streamlit run app.py\n")
        print("2. In browser, click 'Select a meeting recording'\n")
        print("3. Upload: sample_audio_generated.wav\n")
        print("4. Click 'Transcribe' button\n")
        print("5. Watch the 5-step transcription process\n")
        print("6. See your transcript in the browser\n")
        print("7. Check transcripts/ folder for saved files\n")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nFallback: Use online sample files instead:")
        print("─" * 60)
        print("Option 1: https://www.sample-videos.com/audio/mp3/meeting-recording.mp3")
        print("Option 2: https://www.sample-videos.com/audio/mp3/business-speech.mp3")
        print("Option 3: https://www.sample-videos.com/audio/mp3/interview.mp3")
        print("─" * 60 + "\n")
