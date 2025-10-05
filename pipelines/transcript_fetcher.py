"""
Enhanced YouTube Transcript Fetcher
Multi-source fallback: YouTube Captions → YouTube Audio + AssemblyAI
"""

import os
import re
import json
import requests
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class TranscriptFetcher:
    """
    Fetch YouTube transcripts with caching and multiple fallback methods.

    Fallback chain:
    1. YouTube native captions (youtube-transcript-api)
    2. YouTube audio → AssemblyAI transcription (if API key available)
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Path(__file__).parents[1] / "outputs" / "transcripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("YT_API_KEY")
        self.assemblyai_key = os.getenv("ASSEMBLYAI_API_KEY")

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

        # METHOD 1: Try YouTube native captions first
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            print(f"    [Method 1/2] Trying YouTube captions...")
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            if transcript_list:
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
                    "source": "youtube_captions",
                    "cached": False
                }

                # Cache the result
                with open(cache_path, 'w') as f:
                    json.dump(result, f, indent=2)

                print(f"    ✓ Success via YouTube captions")
                return result

        except Exception as e:
            print(f"    ✗ YouTube captions failed: {type(e).__name__}")

        # METHOD 2: Fallback to AssemblyAI (if API key available)
        if self.assemblyai_key:
            try:
                print(f"    [Method 2/2] Trying AssemblyAI transcription...")
                result = self._transcribe_with_assemblyai(video_id, video_url)

                if result and "error" not in result:
                    # Cache the result
                    with open(cache_path, 'w') as f:
                        json.dump(result, f, indent=2)

                    print(f"    ✓ Success via AssemblyAI")
                    return result
                else:
                    print(f"    ✗ AssemblyAI failed: {result.get('error', 'Unknown')}")

            except Exception as e:
                print(f"    ✗ AssemblyAI exception: {str(e)}")

        # All methods failed
        return {
            "error": "All transcript methods failed (YouTube captions + AssemblyAI)",
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

    def _get_youtube_audio_url(self, video_id: str) -> Optional[str]:
        """
        Extract direct audio URL from YouTube video using yt-dlp.
        """
        try:
            import yt_dlp

            video_url = f"https://www.youtube.com/watch?v={video_id}"

            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'no_check_certificates': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)

                # Get the best audio URL
                if 'url' in info:
                    return info['url']
                elif 'formats' in info:
                    # Find best audio format
                    audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                    if audio_formats:
                        # Sort by quality and get URL
                        best_audio = max(audio_formats, key=lambda x: x.get('abr', 0))
                        return best_audio.get('url')

            return None

        except ImportError:
            print(f"      ✗ yt-dlp not installed. Run: pip install yt-dlp")
            return None
        except Exception as e:
            print(f"      ✗ Error extracting audio URL: {e}")
            return None

    def _transcribe_with_assemblyai(self, video_id: str, video_url: str) -> Dict:
        """
        Transcribe YouTube video using AssemblyAI.
        Downloads audio to temp file, uploads to AssemblyAI, then deletes temp file.
        """
        import tempfile
        import os

        temp_audio_path = None

        try:
            import assemblyai as aai
            import yt_dlp

            # Configure AssemblyAI
            aai.settings.api_key = self.assemblyai_key

            # Download audio to temporary file
            print(f"      Downloading audio with yt-dlp...")

            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_audio_path = os.path.join(temp_dir, f"{video_id}.m4a")

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_audio_path.replace('.m4a', ''),
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            if not os.path.exists(temp_audio_path):
                return {
                    "error": "Failed to download audio file",
                    "video_id": video_id
                }

            print(f"      Audio downloaded ({os.path.getsize(temp_audio_path) / 1024 / 1024:.1f} MB), uploading to AssemblyAI...")

            # Create transcriber and upload file
            transcriber = aai.Transcriber()

            # Upload and transcribe the local file
            transcript_obj = transcriber.transcribe(temp_audio_path)

            # Wait for transcription to complete
            if transcript_obj.status == aai.TranscriptStatus.error:
                return {
                    "error": f"AssemblyAI transcription failed: {transcript_obj.error}",
                    "video_id": video_id
                }

            # Extract text and segments
            full_text = transcript_obj.text

            segments = []
            if transcript_obj.words:
                # Group words into sentence-like segments (every ~10 seconds)
                current_segment = {"time": 0, "text": ""}
                last_time = 0

                for word in transcript_obj.words:
                    word_time = word.start / 1000.0  # Convert ms to seconds

                    # Start new segment every 10 seconds
                    if word_time - last_time > 10000 and current_segment["text"]:
                        segments.append(current_segment)
                        current_segment = {"time": round(word_time, 2), "text": word.text}
                        last_time = word_time
                    else:
                        current_segment["text"] += " " + word.text

                # Add final segment
                if current_segment["text"]:
                    segments.append(current_segment)

            result = {
                "video_id": video_id,
                "video_url": video_url,
                "transcript": full_text,
                "segments": segments,
                "word_count": len(full_text.split()),
                "duration_seconds": transcript_obj.audio_duration if hasattr(transcript_obj, 'audio_duration') else 0,
                "fetched_at": datetime.utcnow().isoformat(),
                "source": "assemblyai",
                "cached": False
            }

            # Cleanup temp file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    print(f"      Cleaned up temp audio file")
                except:
                    pass

            return result

        except ImportError:
            return {
                "error": "assemblyai library not installed. Run: pip install assemblyai",
                "video_id": video_id
            }
        except Exception as e:
            # Cleanup temp file on error
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except:
                    pass

            return {
                "error": f"AssemblyAI transcription failed: {str(e)}",
                "video_id": video_id
            }
