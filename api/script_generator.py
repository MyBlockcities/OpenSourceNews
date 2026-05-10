#!/usr/bin/env python3
"""Backend API for research orchestration and on-demand generation."""

import hmac
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / '.env')
load_dotenv(ROOT_DIR / '.env.local')

from pipelines.video_script_generator import VideoScriptGenerator
from pipelines.transcript_fetcher import TranscriptFetcher
from pipelines.transcript_analysis import analyze_transcript_auto
from pipelines.llm_provider import parse_json_text, try_get_llm_client
from services.news_schema import (
    normalize_item,
    normalize_report,
    search_score,
    slugify_name,
)

app = Flask(__name__)


def _cors_origins():
    raw = os.environ.get("OPEN_SOURCE_NEWS_CORS_ORIGINS", "").strip()
    if raw:
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        return origins or []
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]


CORS(app, origins=_cors_origins())

# --- API Authentication ---
OPEN_SOURCE_NEWS_API_KEY = os.environ.get("OPEN_SOURCE_NEWS_API_KEY")
OPEN_SOURCE_NEWS_ADMIN_KEY = os.environ.get("OPEN_SOURCE_NEWS_ADMIN_KEY")

# Endpoints that don't require authentication
AUTH_EXEMPT_PATHS = {"/api/health"}
WRITE_OR_EXPENSIVE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _extract_bearer() -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    return auth_header[len("Bearer "):].strip()


def _token_matches(token: str, expected: str | None) -> bool:
    return bool(token and expected and hmac.compare_digest(token, expected))


def _valid_read_token(token: str) -> bool:
    return _token_matches(token, OPEN_SOURCE_NEWS_API_KEY) or _token_matches(
        token, OPEN_SOURCE_NEWS_ADMIN_KEY
    )


def _valid_admin_token(token: str) -> bool:
    admin_key = OPEN_SOURCE_NEWS_ADMIN_KEY or OPEN_SOURCE_NEWS_API_KEY
    return _token_matches(token, admin_key)


@app.before_request
def check_api_auth():
    """Validate Bearer tokens.

    GET routes can be public when OPEN_SOURCE_NEWS_API_KEY is unset.
    Write/POST routes are admin-only when OPEN_SOURCE_NEWS_ADMIN_KEY or
    OPEN_SOURCE_NEWS_API_KEY is configured.
    """
    if request.method == "OPTIONS":
        return None
    if request.path in AUTH_EXEMPT_PATHS:
        return None

    token = _extract_bearer()
    is_admin_route = request.method in WRITE_OR_EXPENSIVE_METHODS

    if is_admin_route and (OPEN_SOURCE_NEWS_ADMIN_KEY or OPEN_SOURCE_NEWS_API_KEY):
        if not token:
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        if not _valid_admin_token(token):
            return jsonify({"error": "Admin API key required"}), 403
        return None

    if OPEN_SOURCE_NEWS_API_KEY:
        if not token:
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        if not _valid_read_token(token):
            return jsonify({"error": "Invalid API key"}), 401
        return None

    if is_admin_route:
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    return None


# Setup
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")

_llm_cache = None


def require_llm():
    """LLM from LLM_PROVIDER (ollama / openrouter / gemini / rotating)."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = try_get_llm_client()
    if _llm_cache is None:
        raise RuntimeError(
            "LLM not available. Configure Ollama, or set OPENROUTER_API_KEY, "
            "or GEMINI_API_KEY with LLM_PROVIDER=gemini — see .env.example"
        )
    return _llm_cache


transcript_fetcher = TranscriptFetcher()
OUTPUT_DIR = ROOT_DIR / 'outputs'
HTTP_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (scheduler-api; +https://example.com)"
}


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
    planner = require_llm()
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
    text = planner.generate(prompt, json_mode=True)
    return parse_json_text(text)


def synthesize_research(objective: str, search_results: List[Dict[str, str]]) -> Dict[str, Any]:
    synthesizer = require_llm()
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
    text = synthesizer.generate(prompt, json_mode=True)
    return parse_json_text(text)


def generate_pathfinder_suggestions(objective: str, report_summary: str) -> Dict[str, List[str]]:
    pathfinder = require_llm()
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
    text = pathfinder.generate(prompt, json_mode=True)
    return parse_json_text(text)


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

        try:
            llm = require_llm()
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 500

        print(f"Generating script for {len(items)} items...")

        # Use video script generator
        generator = VideoScriptGenerator(llm)
        
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

        wc = result.get("word_count") or 0
        return jsonify({
            "video_id": result.get("video_id"),
            "transcript": result.get("transcript"),
            "word_count": wc,
            "duration_seconds": result.get("duration_seconds"),
            "source": result.get("source"),
            "transcript_mode": "full",
            "segment_count": len(result.get("segments") or []),
            "is_generated_caption": result.get("is_generated"),
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
        try:
            llm = require_llm()
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 500

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

        # Use chunked_full for long transcripts; truncated path for shorter (shared with daily_run).
        pseudo_item = {"title": title}
        analyzed = analyze_transcript_auto(
            llm, pseudo_item, transcript_text, word_count, long_threshold=4000
        )
        tm = analyzed.get("transcript_mode", "truncated")

        return jsonify({
            "quality_score": analyzed.get("quality_score", 5),
            "main_topic": analyzed.get("main_topic", ""),
            "key_insights": analyzed.get("key_insights", []),
            "content_type": analyzed.get("content_type", "General"),
            "target_audience": analyzed.get("target_audience", "General"),
            "unique_value": analyzed.get("unique_value", ""),
            "transcript_word_count": word_count,
            "transcript_mode": tm,
            "transcript_source": transcript_data.get("source"),
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


def _parse_positive_int(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _report_date(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.stem, "%Y-%m-%d")
    except ValueError:
        return None


def _item_search_text(topic_name: str, item: dict) -> str:
    from services.news_schema import item_search_text

    return item_search_text(topic_name, item)


def _search_score(query_terms: List[str], topic_name: str, item: dict) -> int:
    return search_score(query_terms, topic_name, item)


def _transcript_metadata_block(item: dict) -> dict:
    """Stable transcript sub-object for normalized items (explicit nulls)."""
    from services.news_schema import transcript_metadata_block

    return transcript_metadata_block(item)


def _normalize_item(topic_name: str, item: dict) -> dict:
    """Single normalized item with a fixed key set for external consumers (Agency)."""
    return normalize_item(topic_name, item)


def _normalize_report(report_date: str, report_data: dict) -> dict:
    """Transform a raw daily report into a stable normalized schema."""
    return normalize_report(report_date, report_data)


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


@app.route('/api/news/search', methods=['GET'])
def news_search():
    """Keyword search across recent daily reports."""
    query = (request.args.get("q") or "").strip()
    days = _parse_positive_int(request.args.get("days"), default=30, maximum=365)
    limit = _parse_positive_int(request.args.get("limit"), default=25, maximum=100)
    topic_filter = (request.args.get("topic") or "").strip().lower()
    source_filter = (request.args.get("source") or "").strip().lower()
    bucket_filter = (request.args.get("bucket") or "").strip().lower()

    if not query and not topic_filter and not source_filter and not bucket_filter:
        return jsonify({"error": "Provide q, topic, source, or bucket"}), 400

    query_terms = [term for term in query.lower().split() if term]
    cutoff = datetime.utcnow() - timedelta(days=days)
    results: List[Dict[str, Any]] = []

    for report_path in _list_report_files(limit=365):
        report_dt = _report_date(report_path)
        if report_dt and report_dt < cutoff:
            continue

        try:
            report = _load_report(report_path)
        except Exception as e:
            print(f"WARNING: Could not load report {report_path}: {e}")
            continue

        for topic_name, topic_items in report.items():
            if topic_filter and topic_filter not in topic_name.lower():
                continue
            if not isinstance(topic_items, list):
                continue
            for item in topic_items:
                if not isinstance(item, dict):
                    continue
                if source_filter and source_filter not in (item.get("source") or "").lower():
                    continue
                if bucket_filter and bucket_filter != (item.get("bucket") or "").lower():
                    continue

                score = _search_score(query_terms, topic_name, item) if query_terms else 1
                if query_terms and score <= 0:
                    continue

                normalized = _normalize_item(topic_name, item)
                normalized["report_date"] = report_path.stem
                normalized["score"] = score
                results.append(normalized)

    results.sort(key=lambda it: (it.get("score", 0), it.get("quality_score") or 0, it.get("report_date", "")), reverse=True)
    return jsonify({
        "query": query,
        "days": days,
        "limit": limit,
        "count": min(len(results), limit),
        "total_matches": len(results),
        "items": results[:limit],
        "results": results[:limit],
    })


# ---------------------------------------------------------------------------
# Configuration endpoints (for Settings UI)
# ---------------------------------------------------------------------------

import yaml

CONFIG_PATH = ROOT_DIR / 'config' / 'feeds.yaml'
WATCHLISTS_CONFIG_PATH = ROOT_DIR / 'config' / 'watchlists.yaml'
MANIFEST_JSON_PATH = ROOT_DIR / 'outputs' / 'manifests' / 'latest.json'
KNOWLEDGE_BASE_JSON = ROOT_DIR / 'outputs' / 'knowledge_base' / 'knowledge_base.json'
BRIEFS_OUTPUT_DIR = ROOT_DIR / 'outputs' / 'briefs'

FEEDS_ALLOWED_TOPIC_KEYS = frozenset({
    "topic_name",
    "github_sources",
    "hackernews_sources",
    "rss_sources",
    "youtube_sources",
    "x_sources",
    "instagram_sources",
})


def _validate_feeds_payload(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("Body must be a JSON object")
    topics = data.get("topics")
    if not isinstance(topics, list) or len(topics) < 1:
        raise ValueError("Invalid config: 'topics' must be a non-empty list")
    for topic in topics:
        if not isinstance(topic, dict):
            raise ValueError("Each topic must be an object")
        if "topic_name" not in topic:
            raise ValueError("Each topic must have a 'topic_name'")
        name = topic.get("topic_name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each topic_name must be a non-empty string")
        for key in topic:
            if key not in FEEDS_ALLOWED_TOPIC_KEYS:
                raise ValueError(f"Unknown key in topic: {key}")
        for key, val in topic.items():
            if key == "topic_name":
                continue
            if not isinstance(val, list):
                raise ValueError(f"{key} must be a list of strings")
            for entry in val:
                if not isinstance(entry, str):
                    raise ValueError(f"Invalid entry in {key}: must be string")


@app.route('/api/config/feeds', methods=['GET'])
def get_feeds_config():
    """Return the current feeds.yaml configuration."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/watchlists', methods=['GET'])
def get_watchlists():
    """Return configured strategic watchlists."""
    if not WATCHLISTS_CONFIG_PATH.exists():
        return jsonify({"watchlists": []})
    try:
        with open(WATCHLISTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/config/feeds', methods=['PUT'])
def update_feeds_config():
    """Update the feeds.yaml configuration."""
    try:
        data = request.json
        _validate_feeds_payload(data)

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        backup_name = f"feeds.backup.{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.yaml"
        backup_path = CONFIG_PATH.parent / backup_name
        if CONFIG_PATH.exists():
            shutil.copy2(CONFIG_PATH, backup_path)

        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=1000,
            )

        return jsonify({
            "status": "ok",
            "topics": len(data["topics"]),
            "backup_path": str(backup_path.relative_to(ROOT_DIR)) if backup_path.exists() else None,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _brief_path(watchlist: str, date_str: str | None = None) -> Path | None:
    slug = slugify_name(watchlist)
    brief_dir = BRIEFS_OUTPUT_DIR / slug
    if date_str:
        path = brief_dir / f"{date_str}.json"
        return path if path.exists() else None
    files = sorted(brief_dir.glob("*.json"), reverse=True)
    return files[0] if files else None


@app.route('/api/briefs/<watchlist>/latest', methods=['GET'])
def brief_latest(watchlist: str):
    """Return the latest generated mission brief for a watchlist."""
    path = _brief_path(watchlist)
    if not path:
        return jsonify({"error": f"No mission brief found for {watchlist}"}), 404
    try:
        return jsonify(json.loads(path.read_text(encoding='utf-8')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/briefs/<watchlist>/by-date/<date_str>', methods=['GET'])
def brief_by_date(watchlist: str, date_str: str):
    """Return a generated mission brief for a watchlist and date."""
    path = _brief_path(watchlist, date_str)
    if not path:
        return jsonify({"error": f"No mission brief found for {watchlist} on {date_str}"}), 404
    try:
        return jsonify(json.loads(path.read_text(encoding='utf-8')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/manifest/latest', methods=['GET'])
def manifest_latest():
    """Stable integration manifest: latest report info + optional KB timestamp."""
    if MANIFEST_JSON_PATH.exists():
        try:
            with open(MANIFEST_JSON_PATH, 'r', encoding='utf-8') as f:
                base = json.load(f)
        except Exception:
            base = {}
    else:
        base = {}

    files = _list_report_files(limit=1)
    latest_date = files[0].stem if files else None
    kb_ts = None
    if KNOWLEDGE_BASE_JSON.exists():
        kb_ts = datetime.utcfromtimestamp(
            KNOWLEDGE_BASE_JSON.stat().st_mtime
        ).isoformat() + "Z"

    out = {
        "latest_report_date": base.get("latest_report_date") or latest_date,
        "latest_report_path": base.get("latest_report_path"),
        "item_count": base.get("item_count"),
        "topics": base.get("topics"),
        "bucket_counts": base.get("bucket_counts"),
        "generated_at": base.get("generated_at"),
        "knowledge_base_last_built": kb_ts,
    }
    return jsonify(out)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", "5000"))
    print("=" * 60)
    print("OpenSourceNews Backend API")
    print("=" * 60)
    read_auth = "ENABLED" if OPEN_SOURCE_NEWS_API_KEY else "PUBLIC"
    admin_auth = "ENABLED" if (OPEN_SOURCE_NEWS_ADMIN_KEY or OPEN_SOURCE_NEWS_API_KEY) else "BLOCKED (no admin key)"
    print(f"\nRead auth: {read_auth}")
    print(f"Admin route auth: {admin_auth}")
    print(f"Starting server on http://localhost:{port}")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=False)
