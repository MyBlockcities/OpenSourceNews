#!/usr/bin/env python3
"""
Simple test of youtube-transcript-api with different approaches
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
import sys

# Test videos
test_videos = [
    ("dQw4w9WgXcQ", "Rick Astley - Never Gonna Give You Up"),
    ("jNQXAC9IVRw", "Me at the zoo (first YouTube video)"),
    ("9bZkp7q19f0", "PSY - GANGNAM STYLE"),
]

print("=" * 80)
print("YOUTUBE TRANSCRIPT API - SIMPLE TEST")
print("=" * 80)

for video_id, title in test_videos:
    print(f"\n📹 Testing: {title}")
    print(f"   ID: {video_id}")
    print("-" * 80)

    try:
        # Create API instance
        api = YouTubeTranscriptApi()

        # Method 1: Fetch transcript directly
        fetched_transcript = api.fetch(video_id, languages=['en'])

        print(f"   ✅ Fetched transcript successfully")
        print(f"   📝 Language: {fetched_transcript.language_code}")
        print(f"   📝 Is generated: {fetched_transcript.is_generated}")

        # Get the transcript data
        transcript_data = fetched_transcript.snippets

        # Show preview
        full_text = " ".join([snippet.text for snippet in transcript_data])
        word_count = len(full_text.split())

        print(f"   📝 Word count: {word_count}")
        print(f"   📄 Preview: {full_text[:200]}...")
        print(f"   ✅ SUCCESS!")

    except TranscriptsDisabled:
        print(f"   ❌ Transcripts disabled for this video")
    except NoTranscriptFound:
        print(f"   ❌ No transcript found")
    except VideoUnavailable:
        print(f"   ❌ Video unavailable")
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {str(e)}")

print("\n" + "=" * 80)
