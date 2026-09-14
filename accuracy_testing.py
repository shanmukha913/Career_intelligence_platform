"""
Task 5: Accuracy Testing Framework
Tests transcription accuracy against known recordings
"""

import os
import json
import whisper
from pathlib import Path
from difflib import SequenceMatcher
from datetime import datetime


class AccuracyTester:
    def __init__(self, model_name="base"):
        """Initialize the accuracy tester"""
        self.model = whisper.load_model(model_name)
        self.results = []
        self.test_dir = "test_recordings"  # Directory with test audio files
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs("accuracy_reports", exist_ok=True)
    
    def word_error_rate(self, reference, hypothesis):
        """
        Calculate Word Error Rate (WER)
        WER = (S + D + I) / N
        S = substitutions, D = deletions, I = insertions, N = reference length
        """
        ref_words = reference.lower().split()
        hyp_words = hypothesis.lower().split()
        
        # Use SequenceMatcher to find differences
        matcher = SequenceMatcher(None, ref_words, hyp_words)
        
        matches = sum(block.size for block in matcher.get_matching_blocks())
        errors = len(ref_words) - matches
        
        if len(ref_words) == 0:
            return 0 if len(hyp_words) == 0 else 100
        
        wer = (errors / len(ref_words)) * 100
        return wer
    
    def character_error_rate(self, reference, hypothesis):
        """
        Calculate Character Error Rate (CER)
        """
        ref_chars = reference.lower().replace(" ", "")
        hyp_chars = hypothesis.lower().replace(" ", "")
        
        matcher = SequenceMatcher(None, ref_chars, hyp_chars)
        matches = sum(block.size for block in matcher.get_matching_blocks())
        errors = len(ref_chars) - matches
        
        if len(ref_chars) == 0:
            return 0 if len(hyp_chars) == 0 else 100
        
        cer = (errors / len(ref_chars)) * 100
        return cer
    
    def similarity_ratio(self, reference, hypothesis):
        """
        Calculate overall similarity ratio (0-100%)
        """
        matcher = SequenceMatcher(None, reference.lower(), hypothesis.lower())
        ratio = matcher.ratio() * 100
        return ratio
    
    def transcribe_test_file(self, audio_path):
        """Transcribe a test audio file"""
        try:
            result = self.model.transcribe(audio_path)
            return result["text"]
        except Exception as e:
            return f"Error: {str(e)}"
    
    def test_single_file(self, audio_path, reference_text):
        """
        Test a single audio file against reference text
        """
        print(f"\nTesting: {os.path.basename(audio_path)}")
        print("-" * 50)
        
        # Transcribe
        hypothesis = self.transcribe_test_file(audio_path)
        
        # Calculate metrics
        wer = self.word_error_rate(reference_text, hypothesis)
        cer = self.character_error_rate(reference_text, hypothesis)
        similarity = self.similarity_ratio(reference_text, hypothesis)
        accuracy = 100 - wer  # Accuracy is inverse of WER
        
        result = {
            "file": os.path.basename(audio_path),
            "reference_length": len(reference_text.split()),
            "hypothesis_length": len(hypothesis.split()),
            "word_error_rate": round(wer, 2),
            "character_error_rate": round(cer, 2),
            "similarity_ratio": round(similarity, 2),
            "accuracy": round(accuracy, 2),
            "reference_text": reference_text[:100] + "...",
            "hypothesis_text": hypothesis[:100] + "...",
            "timestamp": datetime.now().isoformat()
        }
        
        self.results.append(result)
        
        # Print results
        print(f"✓ Accuracy: {result['accuracy']:.2f}%")
        print(f"✓ Word Error Rate: {result['word_error_rate']:.2f}%")
        print(f"✓ Character Error Rate: {result['character_error_rate']:.2f}%")
        print(f"✓ Similarity: {result['similarity_ratio']:.2f}%")
        
        return result
    
    def run_batch_test(self, test_cases):
        """
        Run multiple test cases
        test_cases: list of tuples (audio_path, reference_text)
        """
        print("\n" + "="*50)
        print("ACCURACY TESTING - BATCH TEST")
        print("="*50)
        
        for audio_path, reference_text in test_cases:
            if os.path.exists(audio_path):
                self.test_single_file(audio_path, reference_text)
            else:
                print(f"❌ File not found: {audio_path}")
        
        # Generate report
        report = self.generate_report()
        return report
    
    def generate_report(self):
        """Generate accuracy testing report"""
        if not self.results:
            return {"error": "No test results"}
        
        accuracies = [r["accuracy"] for r in self.results]
        wers = [r["word_error_rate"] for r in self.results]
        cers = [r["character_error_rate"] for r in self.results]
        similarities = [r["similarity_ratio"] for r in self.results]
        
        report = {
            "summary": {
                "total_tests": len(self.results),
                "average_accuracy": round(sum(accuracies) / len(accuracies), 2),
                "average_wer": round(sum(wers) / len(wers), 2),
                "average_cer": round(sum(cers) / len(cers), 2),
                "average_similarity": round(sum(similarities) / len(similarities), 2),
                "passed_tests": len([r for r in self.results if r["accuracy"] >= 90]),
                "target_met": sum(accuracies) / len(accuracies) >= 90
            },
            "detailed_results": self.results,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save report
        report_filename = f"accuracy_reports/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print("\n" + "="*50)
        print("TEST REPORT SUMMARY")
        print("="*50)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Average Accuracy: {report['summary']['average_accuracy']:.2f}%")
        print(f"Average WER: {report['summary']['average_wer']:.2f}%")
        print(f"Passed Tests (≥90%): {report['summary']['passed_tests']}")
        print(f"Target Met (≥90%): {'✓ YES' if report['summary']['target_met'] else '✗ NO'}")
        print(f"Report saved: {report_filename}")
        
        return report


# Example usage and test data setup
if __name__ == "__main__":
    # Initialize tester
    tester = AccuracyTester(model_name="base")
    
    # Create sample test cases
    # In real scenario, you would have actual audio files and reference texts
    test_cases = [
        # ("path/to/test1.mp3", "This is the reference transcript for test one"),
        # ("path/to/test2.wav", "Another test recording with reference text"),
    ]
    
    # Run batch test
    if test_cases:
        report = tester.run_batch_test(test_cases)
    else:
        print("No test cases defined. Add test audio files and reference texts to test_cases list.")
        print("\nExample:")
        print('test_cases = [')
        print('    ("uploads/meeting1.mp3", "Reference transcript text here"),')
        print('    ("uploads/meeting2.wav", "Another reference transcript"),')
        print(']')
        print('report = tester.run_batch_test(test_cases)')
