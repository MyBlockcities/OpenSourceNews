"""
Standalone YouTube Transcript Fetcher
Inspired by YouTubeAgency/fetch_video_transcript.py but fully self-contained
"""

import os
import re
import json
import requests
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class TranscriptFetcher:
    """
    Fetch YouTube transcripts with caching and multiple fallback methods.
    Based on proven YouTubeAgency logic but standalone.
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Path(__file__).parents[1] / "outputs" / "transcripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)',
            r'(?:youtube\.com\/embed\/)([\w-]+)',
            r'(?:youtube\.com\/v\/)([\w-]+)',
            r'(?:youtube\.com\/watch\?.*v=)([\w-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def fetch_transcript(self, video_url: str, force_refresh: bool = False) -> Dict:
        """
        Fetch full transcript for a YouTube video.

        Args:
            video_url: YouTube video URL (e.g., https://youtu.be/abc123)
            force_refresh: Skip cache and fetch fresh

        Returns:
            {
                "video_id": "abc123",
                "transcript": "Full text...",
                "segments": [{"time": 0, "text": "..."}],
                "word_count": 5000,
                "duration_seconds": 600,
                "cached": False
            }
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return {"error": f"Invalid YouTube URL: {video_url}"}

        # Check cache first (unless force refresh)
        cache_path = self.output_dir / f"{video_id}.json"
        if not force_refresh and cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                cached_data['cached'] = True
                return cached_data
            except Exception as e:
                print(f"Warning: Cache read failed for {video_id}: {e}")

        # Try to fetch fresh transcript
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            # Get transcript from YouTube
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            if not transcript_list:
                return {
                    "error": "No transcript available for this video",
                    "video_id": video_id
                }

            # Extract segments and build full text
            segments = []
            full_text_parts = []

            for item in transcript_list:
                segments.append({
                    "time": round(item['start'], 2),
                    "text": item['text'].strip()
                })
                full_text_parts.append(item['text'])

            full_text = " ".join(full_text_parts).strip()
            duration = transcript_list[-1]['start'] if transcript_list else 0

            result = {
                "video_id": video_id,
                "video_url": video_url,
                "transcript": full_text,
                "segments": segments,
                "word_count": len(full_text.split()),
                "duration_seconds": round(duration, 2),
                "fetched_at": datetime.utcnow().isoformat(),
                "cached": False
            }

            # Cache the result
            with open(cache_path, 'w') as f:
                json.dump(result, f, indent=2)

            return result

        except ModuleNotFoundError:
            return {
                "error": "youtube-transcript-api not installed. Run: pip install youtube-transcript-api",
                "video_id": video_id
            }
        except Exception as e:
            error_msg = str(e)
            if "TranscriptsDisabled" in error_msg or "No transcript" in error_msg:
                return {
                    "error": "Transcripts disabled or unavailable for this video",
                    "video_id": video_id
                }
            return {
                "error": f"Failed to fetch transcript: {error_msg}",
                "video_id": video_id
            }

    def batch_fetch(self, video_urls: list, max_videos: int = 5) -> Dict[str, Dict]:
        """
        Fetch transcripts for multiple videos (with quota limits).

        Args:
            video_urls: List of YouTube URLs
            max_videos: Maximum number to fetch (default 5 for quota management)

        Returns:
            {"video_id1": {...}, "video_id2": {...}}
        """
        results = {}
        processed = 0

        for url in video_urls:
            if processed >= max_videos:
                print(f"Reached max limit of {max_videos} transcripts")
                break

            video_id = self.extract_video_id(url)
            if not video_id:
                results[url] = {"error": "Invalid URL"}
                continue

            print(f"Fetching transcript for {video_id} ({processed + 1}/{max_videos})...")
            result = self.fetch_transcript(url)
            results[video_id] = result

            if "error" not in result:
                processed += 1

        return results
