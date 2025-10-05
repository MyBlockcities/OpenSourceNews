#!/usr/bin/env python3
"""
Test script for transcript fetching with YouTube Captions + AssemblyAI fallback
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load environment variables
load_dotenv('.env.local')

from pipelines.transcript_fetcher import TranscriptFetcher


def test_transcript_fetching():
    """Test transcript fetching with multiple YouTube videos"""

    print("=" * 80)
    print("TRANSCRIPT FETCHER TEST")
    print("=" * 80)

    # Verify API keys are loaded
    print("\n📋 API Keys Status:")
    youtube_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("YT_API_KEY")
    assemblyai_key = os.getenv("ASSEMBLYAI_API_KEY")

    print(f"  YouTube API Key: {'✓ Loaded' if youtube_key else '✗ Missing'}")
    print(f"  AssemblyAI API Key: {'✓ Loaded' if assemblyai_key else '✗ Missing'}")

    if not youtube_key and not assemblyai_key:
        print("\n❌ ERROR: No API keys found. Please check .env.local")
        return

    # Initialize fetcher
    fetcher = TranscriptFetcher()

    # Test videos (mix of likely captioned and non-captioned)
    test_videos = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - likely has captions
        "https://youtu.be/jNQXAC9IVRw",  # Me at the zoo - first YouTube video
        "https://www.youtube.com/watch?v=9bZkp7q19f0",  # Gangnam Style - definitely has captions
    ]

    print(f"\n🎬 Testing {len(test_videos)} videos...")
    print("-" * 80)

    results = []
    for i, video_url in enumerate(test_videos, 1):
        print(f"\n[{i}/{len(test_videos)}] Testing: {video_url}")

        result = fetcher.fetch_transcript(video_url)
        results.append(result)

        if "error" in result:
            print(f"  ✗ FAILED: {result['error']}")
        else:
            source = result.get('source', 'unknown')
            word_count = result.get('word_count', 0)
            duration = result.get('duration_seconds', 0)
            cached = result.get('cached', False)

            print(f"  ✓ SUCCESS via {source}")
            print(f"    - Word count: {word_count:,}")
            print(f"    - Duration: {duration:.1f}s")
            print(f"    - Cached: {cached}")

            # Show first 200 characters of transcript
            transcript = result.get('transcript', '')
            if transcript:
                preview = transcript[:200] + "..." if len(transcript) > 200 else transcript
                print(f"    - Preview: {preview}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = len(results)
    successful = sum(1 for r in results if "error" not in r)
    failed = total - successful

    print(f"\n  Total tested: {total}")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")

    # Method breakdown
    if successful > 0:
        youtube_count = sum(1 for r in results if r.get('source') == 'youtube_captions')
        assemblyai_count = sum(1 for r in results if r.get('source') == 'assemblyai')

        print(f"\n  Methods used:")
        if youtube_count > 0:
            print(f"    - YouTube Captions: {youtube_count}")
        if assemblyai_count > 0:
            print(f"    - AssemblyAI: {assemblyai_count}")

    print("\n" + "=" * 80)

    # Return success/failure for CI
    return successful > 0


if __name__ == "__main__":
    success = test_transcript_fetching()
    sys.exit(0 if success else 1)
