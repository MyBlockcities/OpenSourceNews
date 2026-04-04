#!/usr/bin/env python3
"""
Quick test of AssemblyAI transcription on a single short video
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load environment variables
load_dotenv('.env')
load_dotenv('.env.local')

from pipelines.transcript_fetcher import TranscriptFetcher


# Test with a very short video (Me at the zoo - 19 seconds)
test_video = "https://youtu.be/jNQXAC9IVRw"

print("Testing AssemblyAI transcription on short video...")
print(f"Video: {test_video}")
print("-" * 80)

fetcher = TranscriptFetcher()
result = fetcher.fetch_transcript(test_video)

print("-" * 80)

if "error" in result:
    print(f"❌ FAILED: {result['error']}")
    sys.exit(1)
else:
    print(f"✅ SUCCESS!")
    print(f"Source: {result.get('source')}")
    print(f"Word count: {result.get('word_count')}")
    print(f"Duration: {result.get('duration_seconds')}s")
    print(f"\nTranscript:\n{result.get('transcript')}")
    sys.exit(0)
