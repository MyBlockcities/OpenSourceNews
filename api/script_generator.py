#!/usr/bin/env python3
"""Backend API for research orchestration and on-demand generation."""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / '.env')
load_dotenv(ROOT_DIR / '.env.local')

from pipelines.video_script_generator import VideoScriptGenerator
from pipelines.transcript_fetcher import TranscriptFetcher

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# --- API Authentication ---
OPEN_SOURCE_NEWS_API_KEY = os.environ.get("OPEN_SOURCE_NEWS_API_KEY")

# Endpoints that don't require authentication
AUTH_EXEMPT_PATHS = {"/api/health"}


@app.before_request
def check_api_auth():
    """Validate Bearer token on all endpoints except exempt ones."""
    if request.path in AUTH_EXEMPT_PATHS:
        return None
    if not OPEN_SOURCE_NEWS_API_KEY:
        # Auth not configured — allow all requests (dev mode)
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401
    token = auth_header[len("Bearer "):]
    if token != OPEN_SOURCE_NEWS_API_KEY:
        return jsonify({"error": "Invalid API key"}), 401
    return None


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
HTTP_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (scheduler-api; +https://example.com)"
}


def require_model():
    if not model:
        raise RuntimeError("Gemini API key not configured")
    return model


def extract_response_text(response: Any) -> str:
    text_response = getattr(response, "text", None)
    if not text_response and getattr(response, "candidates", None):
        candidate = response.candidates[0]
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None)
        if parts:
            text_response = getattr(parts[0], "text", None)

    if not text_response:
        raise ValueError("No text returned from Gemini")

    text_response = text_response.strip()
    if text_response.startswith("```"):
        text_response = text_response.replace("```json", "").replace("```", "").strip()
    return text_response


def parse_json_response(response: Any) -> Any:
    return json.loads(extract_response_text(response))


def search_duckduckgo(query: str, limit: int = 5) -> List[Dict[str, str]]:
    if not query.strip():
        return []

    response = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=HTTP_HEADERS,
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    results: List[Dict[str, str]] = []
    seen_urls = set()

    for link in soup.select("a.result__a"):
        title = " ".join(link.get_text(" ", strip=True).split())
        url = link.get("href", "").strip()
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"title": title, "url": url, "snippet": ""})
        if len(results) >= limit:
            break

    return results


def plan_research(objective: str) -> Dict[str, Any]:
    planner = require_model()
    prompt = f"""
As a professional AI research planner, create a concise research plan.

User Objective: "{objective}"

Return ONLY valid JSON with these exact keys:
{{
  "planRationale": "short rationale",
  "queries": ["query 1", "query 2", "query 3"],
  "claimsToVerify": ["claim 1", "claim 2"]
}}
"""
    response = planner.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    return parse_json_response(response)


def synthesize_research(objective: str, search_results: List[Dict[str, str]]) -> Dict[str, Any]:
    synthesizer = require_model()
    sources_text = "\n\n".join(
        f"URL: {item.get('url', '')}\nTitle: {item.get('title', '')}\nSnippet: {item.get('snippet', '')}"
        for item in search_results
    )
    prompt = f"""
As a professional AI research synthesizer, write a useful markdown brief from the provided sources.

User Objective: "{objective}"

Sources:
{sources_text}

Return ONLY valid JSON with these exact keys:
{{
  "summary": "markdown summary",
  "sources": [
    {{"title": "source title", "url": "https://example.com"}}
  ]
}}
"""
    response = synthesizer.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    return parse_json_response(response)


def generate_pathfinder_suggestions(objective: str, report_summary: str) -> Dict[str, List[str]]:
    pathfinder = require_model()
    prompt = f"""
You are a strategic AI pathfinder.

Initial objective:
{objective}

Report summary:
{report_summary}

Return ONLY valid JSON with this exact structure:
{{
  "suggestions": ["next step 1", "next step 2", "next step 3"]
}}
"""
    response = pathfinder.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    return parse_json_response(response)


@app.route('/api/research/plan', methods=['POST'])
def research_plan():
    try:
        data = request.json or {}
        objective = (data.get('objective') or '').strip()
        if not objective:
            return jsonify({"error": "No objective provided"}), 400
        return jsonify(plan_research(objective))
    except Exception as e:
        print(f"ERROR: Research planning failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/search', methods=['POST'])
def research_search():
    try:
        data = request.json or {}
        queries = data.get('queries') or []
        if not isinstance(queries, list) or not queries:
            return jsonify({"error": "No queries provided"}), 400

        results: List[Dict[str, str]] = []
        seen_urls = set()
        for query in queries:
            for result in search_duckduckgo(str(query), limit=5):
                url = result.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    results.append(result)

        return jsonify({"results": results[:10]})
    except Exception as e:
        print(f"ERROR: Search failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/synthesize', methods=['POST'])
def research_synthesize():
    try:
        data = request.json or {}
        objective = (data.get('objective') or '').strip()
        search_results = data.get('searchResults') or []
        if not objective:
            return jsonify({"error": "No objective provided"}), 400
        if not isinstance(search_results, list) or not search_results:
            return jsonify({"error": "No search results provided"}), 400
        return jsonify(synthesize_research(objective, search_results))
    except Exception as e:
        print(f"ERROR: Research synthesis failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/research/pathfinder', methods=['POST'])
def research_pathfinder():
    try:
        data = request.json or {}
        objective = (data.get('objective') or '').strip()
        report_summary = (data.get('reportSummary') or '').strip()
        if not objective or not report_summary:
            return jsonify({"error": "Objective and reportSummary are required"}), 400
        return jsonify(generate_pathfinder_suggestions(objective, report_summary))
    except Exception as e:
        print(f"ERROR: Pathfinder failed: {e}")
        return jsonify({"error": str(e)}), 500


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
        analysis = parse_json_response(response)

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


# ---------------------------------------------------------------------------
# Feed-oriented endpoints (for external consumers like Agency by Blockcities)
# ---------------------------------------------------------------------------

DAILY_OUTPUT_DIR = ROOT_DIR / 'outputs' / 'daily'


def _list_report_files(limit: int = 30):
    """Return sorted list of daily report paths, most recent first."""
    files = sorted(DAILY_OUTPUT_DIR.glob("*.json"), reverse=True)
    return files[:limit]


def _load_report(path: Path) -> dict:
    """Load and return a daily report JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _normalize_report(report_date: str, report_data: dict) -> dict:
    """Transform a raw daily report into a stable normalized schema."""
    items = []
    sources_seen = set()
    topic_counts = {}
    source_counts = {}

    for topic_name, topic_items in report_data.items():
        topic_counts[topic_name] = len(topic_items)
        for item in topic_items:
            src = item.get("source", "Unknown")
            sources_seen.add(src)
            source_counts[src] = source_counts.get(src, 0) + 1

            import hashlib
            signal_id = hashlib.sha256(
                (item.get("url", "") + item.get("title", "")).encode()
            ).hexdigest()[:16]

            items.append({
                "source_system": "OpenSourceNews",
                "signal_id": signal_id,
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "source_urls": [item.get("url", "")],
                "topics": [topic_name],
                "source": src,
                "category": item.get("category", ""),
                "content_type": item.get("content_type", ""),
                "quality_score": item.get("quality_score"),
                "bucket": item.get("bucket", ""),
                "processing_mode": item.get("processing_mode", ""),
            })

    total = len(items)
    digest = f"{total} items across {len(topic_counts)} topics from {len(sources_seen)} source types."

    return {
        "report_date": report_date,
        "items": items,
        "sources": sorted(sources_seen),
        "counts": {
            "total": total,
            "by_topic": topic_counts,
            "by_source": source_counts,
        },
        "digest": digest,
    }


@app.route('/api/health', methods=['GET'])
def health():
    """Health check — no auth required."""
    report_files = _list_report_files(limit=1)
    latest_date = report_files[0].stem if report_files else None
    return jsonify({
        "status": "ok",
        "service": "OpenSourceNews API",
        "latest_report_date": latest_date,
    })


@app.route('/api/reports/latest', methods=['GET'])
def reports_latest():
    """Return the most recent daily report as raw JSON."""
    files = _list_report_files(limit=1)
    if not files:
        return jsonify({"error": "No reports found"}), 404
    report = _load_report(files[0])
    return jsonify({"date": files[0].stem, "report": report})


@app.route('/api/reports', methods=['GET'])
def reports_list():
    """Return metadata for recent reports. ?limit=7 (default 7, max 90)."""
    limit = min(int(request.args.get('limit', 7)), 90)
    files = _list_report_files(limit=limit)
    result = []
    for f in files:
        report = _load_report(f)
        item_count = sum(len(v) for v in report.values())
        result.append({
            "date": f.stem,
            "topics": list(report.keys()),
            "item_count": item_count,
        })
    return jsonify({"reports": result})


@app.route('/api/reports/by-date/<date_str>', methods=['GET'])
def reports_by_date(date_str: str):
    """Return a specific day's report by date (YYYY-MM-DD)."""
    report_path = DAILY_OUTPUT_DIR / f"{date_str}.json"
    if not report_path.exists():
        return jsonify({"error": f"No report found for {date_str}"}), 404
    report = _load_report(report_path)
    return jsonify({"date": date_str, "report": report})


@app.route('/api/reports/latest/normalized', methods=['GET'])
def reports_latest_normalized():
    """Return the latest report in a stable normalized schema for external consumers."""
    files = _list_report_files(limit=1)
    if not files:
        return jsonify({"error": "No reports found"}), 404
    report_date = files[0].stem
    report_data = _load_report(files[0])
    return jsonify(_normalize_report(report_date, report_data))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", "5000"))
    print("=" * 60)
    print("OpenSourceNews Backend API")
    print("=" * 60)
    print("\nFeed Endpoints:")
    print("  GET  /api/health - Health check (no auth)")
    print("  GET  /api/reports/latest - Latest daily report")
    print("  GET  /api/reports?limit=7 - Recent report metadata")
    print("  GET  /api/reports/by-date/<YYYY-MM-DD> - Report by date")
    print("  GET  /api/reports/latest/normalized - Normalized schema")
    print("\nResearch Endpoints:")
    print("  POST /api/research/plan - Create mission plan")
    print("  POST /api/research/search - Run web search queries")
    print("  POST /api/research/synthesize - Build final research brief")
    print("  POST /api/research/pathfinder - Suggest follow-up missions")
    print("\nGeneration Endpoints:")
    print("  POST /api/generate-script - Generate video script from items")
    print("  POST /api/generate-audio - Generate audio from script")
    print("  POST /api/transcribe-video - On-demand video transcription")
    print("  POST /api/analyze-video - On-demand video analysis")
    print(f"\nAuth: {'ENABLED' if OPEN_SOURCE_NEWS_API_KEY else 'DISABLED (dev mode)'}")
    print(f"Starting server on http://localhost:{port}")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=False)
