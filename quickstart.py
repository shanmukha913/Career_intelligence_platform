#!/usr/bin/env python3
"""
Quick Start Script for Career Intelligence Platform - Milestone 1
This script sets up and runs the complete transcription workflow
"""

import os
import subprocess
import sys
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    dirs = ["uploads", "transcripts", "accuracy_reports", "test_recordings"]
    for dir_name in dirs:
        os.makedirs(dir_name, exist_ok=True)
        print(f"✓ Created/verified: {dir_name}/")

def check_dependencies():
    """Check if all required packages are installed"""
    print_header("Checking Dependencies")
    
    required = ["streamlit", "openai-whisper", "numpy", "torch"]
    missing = []
    
    for package in required:
        try:
            __import__(package.replace("-", "_"))
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is NOT installed")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("\nRun: pip install -r requirements.txt")
        return False
    
    return True

def run_tests():
    """Run quick tests"""
    print_header("Running Quick Diagnostics")
    
    # Test Whisper model loading
    print("Testing Whisper model loading...")
    try:
        import whisper
        print("✓ Whisper import successful")
        
        # Try to load base model (small, fast for testing)
        print("  Loading base model (this may take a moment)...")
        model = whisper.load_model("base")
        print("✓ Base model loaded successfully")
        print("  Note: Models are cached in ~/.cache/whisper/")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False
    
    return True

def start_streamlit():
    """Start Streamlit application"""
    print_header("Starting Streamlit Application")
    
    print("🚀 Launching app.py...")
    print("   The app will open at: http://localhost:8501")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
    except KeyboardInterrupt:
        print("\n\nStreamlit server stopped.")

def main():
    """Main execution flow"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "Career Intelligence Platform" + " "*13 + "║")
    print("║" + " "*16 + "Milestone 1: Audio Processing & Transcription" + " "*0 + "║")
    print("╚" + "="*58 + "╝")
    
    # Step 1: Create directories
    create_directories()
    
    # Step 2: Check dependencies
    if not check_dependencies():
        print("\n⚠️  Please install missing dependencies:")
        print("   pip install -r requirements.txt")
        return
    
    # Step 3: Run quick tests
    if not run_tests():
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return
    
    # Step 4: Start application
    input("\n✓ All checks passed! Press Enter to start the application...\n")
    start_streamlit()

if __name__ == "__main__":
    main()
