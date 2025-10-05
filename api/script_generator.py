#!/usr/bin/env python3
"""
On-Demand Script & Audio Generation API
Provides endpoints for frontend to trigger script and audio generation
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / '.env.local')

from pipelines.video_script_generator import VideoScriptGenerator
from pipelines.transcript_fetcher import TranscriptFetcher

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
else:
    model = None

transcript_fetcher = TranscriptFetcher()
OUTPUT_DIR = ROOT_DIR / 'outputs'


@app.route('/api/generate-script', methods=['POST'])
def generate_script():
    """
    Generate video script from selected items.
    
    Request body:
    {
        "items": [...DailyFeedItems],
        "topic": "Topic Name"
    }
    """
    try:
        data = request.json
        items = data.get('items', [])
        topic = data.get('topic', 'Research')

        if not items:
            return jsonify({"error": "No items provided"}), 400

        if not model:
            return jsonify({"error": "Gemini API key not configured"}), 500

        print(f"Generating script for {len(items)} items...")

        # Use video script generator
        generator = VideoScriptGenerator(model)
        
        # Prepare report data in expected format
        report_data = {topic: items}
        
        result = generator.generate_daily_script(report_data)

        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        if not result.get("success"):
            return jsonify({"error": "Script generation failed"}), 500

        # Return script data
        return jsonify({
            "script": result["script"],
            "sources": result["sources"],
            "metadata": result["metadata"]
        })

    except Exception as e:
        print(f"ERROR: Script generation failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate-audio', methods=['POST'])
def generate_audio():
    """
    Generate audio from script text using AssemblyAI.
    
    Request body:
    {
        "script": "Script text...",
        "date": "2025-10-05"
    }
    """
    try:
        if not ASSEMBLYAI_API_KEY:
            return jsonify({"error": "AssemblyAI API key not configured"}), 500

        data = request.json
        script_text = data.get('script', '')
        date = data.get('date', datetime.utcnow().strftime("%Y-%m-%d"))

        if not script_text:
            return jsonify({"error": "No script text provided"}), 400

        print(f"Generating audio for script ({len(script_text)} chars)...")

        # Use AssemblyAI text-to-speech
        import assemblyai as aai
        aai.settings.api_key = ASSEMBLYAI_API_KEY

        # Generate audio
        audio_path = OUTPUT_DIR / 'audio' / f"{date}-script.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)

        # Simple TTS (you can enhance this with better voice options)
        # Note: AssemblyAI may not have direct TTS - this is a placeholder
        # You might want to use Google Cloud TTS, ElevenLabs, or OpenAI TTS instead
        
        # For now, return a message about implementation
        return jsonify({
            "message": "Audio generation coming soon",
            "audioUrl": f"/outputs/audio/{date}-script.mp3",
            "note": "Implement with Google Cloud TTS, ElevenLabs, or OpenAI TTS"
        })

    except Exception as e:
        print(f"ERROR: Audio generation failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/transcribe-video', methods=['POST'])
def transcribe_video():
    """
    On-demand transcription for a single video.
    
    Request body:
    {
        "video_url": "https://youtu.be/..."
    }
    """
    try:
        data = request.json
        video_url = data.get('video_url', '')

        if not video_url:
            return jsonify({"error": "No video URL provided"}), 400

        print(f"Transcribing video: {video_url}")

        # Fetch transcript
        result = transcript_fetcher.fetch_transcript(video_url)

        if "error" in result:
            return jsonify({"error": result["error"]}), 500

        return jsonify({
            "video_id": result.get("video_id"),
            "transcript": result.get("transcript"),
            "word_count": result.get("word_count"),
            "duration_seconds": result.get("duration_seconds"),
            "source": result.get("source")
        })

    except Exception as e:
        print(f"ERROR: Video transcription failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/analyze-video', methods=['POST'])
def analyze_video():
    """
    On-demand deep analysis for a single video (requires transcript).
    
    Request body:
    {
        "video_url": "https://youtu.be/...",
        "title": "Video Title"
    }
    """
    try:
        if not model:
            return jsonify({"error": "Gemini API key not configured"}), 500

        data = request.json
        video_url = data.get('video_url', '')
        title = data.get('title', 'Unknown')

        if not video_url:
            return jsonify({"error": "No video URL provided"}), 400

        print(f"Analyzing video: {title}")

        # First, get transcript
        transcript_data = transcript_fetcher.fetch_transcript(video_url)
        
        if "error" in transcript_data:
            return jsonify({"error": transcript_data["error"]}), 500

        transcript_text = transcript_data.get("transcript", "")
        word_count = transcript_data.get("word_count", 0)

        # Analyze with Gemini
        truncated_transcript = " ".join(transcript_text.split()[:4000])

        analysis_prompt = f"""Analyze this YouTube video transcript and provide detailed insights.

Video Title: {title}
Transcript ({word_count} words):
{truncated_transcript}

Return ONLY valid JSON with these exact fields (no markdown, no code blocks):
{{
    "quality_score": <number 0-10>,
    "main_topic": "<single sentence>",
    "key_insights": ["<insight 1>", "<insight 2>", "<insight 3>"],
    "content_type": "<Tutorial|News|Opinion|Research|Case Study>",
    "target_audience": "<Beginner|Intermediate|Advanced>",
    "unique_value": "<what makes this content special>"
}}

Quality Score Criteria:
- 8-10: Groundbreaking, highly actionable, expert-level
- 6-7: Solid content, good insights, well-produced
- 4-5: Average, basic information
- 0-3: Low value, clickbait, or superficial"""

        response = model.generate_content(analysis_prompt)
        
        # Extract response
        text_response = None
        if hasattr(response, 'text'):
            text_response = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            if hasattr(response.candidates[0], 'content'):
                if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
                    text_response = response.candidates[0].content.parts[0].text

        if not text_response:
            return jsonify({"error": "No response from Gemini"}), 500

        # Clean and parse JSON
        text_response = text_response.strip()
        if text_response.startswith('```'):
            text_response = text_response.replace('```json', '').replace('```', '').strip()

        analysis = json.loads(text_response)

        return jsonify({
            "quality_score": analysis.get("quality_score", 5),
            "main_topic": analysis.get("main_topic", ""),
            "key_insights": analysis.get("key_insights", []),
            "content_type": analysis.get("content_type", "General"),
            "target_audience": analysis.get("target_audience", "General"),
            "unique_value": analysis.get("unique_value", ""),
            "transcript_word_count": word_count
        })

    except Exception as e:
        print(f"ERROR: Video analysis failed: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("On-Demand Script & Audio Generation API")
    print("=" * 60)
    print("\nEndpoints:")
    print("  POST /api/generate-script - Generate video script from items")
    print("  POST /api/generate-audio - Generate audio from script")
    print("  POST /api/transcribe-video - On-demand video transcription")
    print("  POST /api/analyze-video - On-demand video analysis")
    print("\nStarting server on http://localhost:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)