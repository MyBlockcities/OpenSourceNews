import os
import sys
import yaml
import json
import datetime
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Add parent directory to path to enable imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / '.env')
load_dotenv(ROOT_DIR / '.env.local')

from pipelines.youtube import fetch_latest_videos
from pipelines.transcript_fetcher import TranscriptFetcher
from pipelines.transcript_analysis import analyze_transcript_auto
from services.mailaroo_emailer import send_text_email

# --- CONFIGURATION ---
CONFIG_PATH = ROOT_DIR / 'config' / 'feeds.yaml'
OUTPUT_DIR = ROOT_DIR / 'outputs' / 'daily'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DAILY_DIR = ROOT_DIR / 'docs' / 'generated' / 'daily'
DOCS_DAILY_DIR.mkdir(parents=True, exist_ok=True)

# --- HTTP DEFAULTS ---
HTTP_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (research-bot; +https://github.com/user/repo)"
}

# --- GEMINI SETUP ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
else:
    print("WARNING: GEMINI_API_KEY not found. Triage agent will be skipped.")

# --- TRANSCRIPT FETCHER SETUP ---
transcript_fetcher = TranscriptFetcher()

# --- HELPERS ---
def _get(url: str):
    r = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r

# --- DATA FETCHERS ---
def fetch_rss(url: str, limit: int = 5):
    if not url: return []
    try:
        resp = _get(url)
        soup = BeautifulSoup(resp.content, "xml")
        items = []
        for item in soup.find_all("item")[:limit]:
            title = (item.title.text if item.title else "").strip()
            link = (item.link.text if item.link else "").strip()
            if title and link:
                items.append({"title": title, "url": link, "source": "RSS"})
        return items
    except Exception as e:
        print(f"ERROR: RSS fetch failed for {url}: {e}")
        return []

def fetch_youtube(identifier: str):
    # Accepts channelId, @handle, or plain name
    if not identifier: return []
    try:
        return fetch_latest_videos(identifier, max_results=5)
    except Exception as e:
        print(f"ERROR: YouTube fetch failed for '{identifier}': {e}")
        return []

def fetch_github_trending(language: str):
    if not language: return []
    url = f"https://github.com/trending/{language}"
    try:
        resp = _get(url)
        soup = BeautifulSoup(resp.content, "html.parser")
        items = []
        for repo in soup.select("article.Box-row")[:5]:
            a_tag = repo.select_one("h2 > a")
            if not a_tag: continue
            title = " ".join(a_tag.text.split())
            href = a_tag.get("href", "")
            if href:
                items.append({"title": title, "url": f"https://github.com{href}", "source": "GitHub Trending"})
        return items
    except Exception as e:
        print(f"ERROR: GitHub trending fetch for '{language}' failed: {e}")
        return []

def fetch_hackernews(keyword: str):
    if not keyword: return []
    url = f"https://hn.algolia.com/api/v1/search?query={keyword}&tags=story"
    try:
        hits = _get(url).json().get("hits", [])
        items = []
        for hit in hits[:5]:
            title, link = hit.get("title"), hit.get("url")
            if title and link:
                items.append({"title": title, "url": link, "source": "Hacker News"})
        return items
    except Exception as e:
        print(f"ERROR: Hacker News fetch for '{keyword}' failed: {e}")
        return []

def fetch_x_profile_posts(username: str):
    if not username: return []
    print(f"INFO: Skipping X placeholder for @{username}. Implement with official X API.")
    return []

def fetch_instagram_profile_posts(username: str):
    if not username: return []
    print(f"INFO: Skipping Instagram placeholder for @{username}.")
    return []

# --- DEEP CONTENT ANALYSIS ---
def analyze_with_transcript(item: dict) -> dict:
    """
    Deep analysis of content using full transcript (for YouTube videos only).
    Adds quality scoring, key insights, and enhanced metadata.
    """
    # Only process YouTube videos
    if item.get("source") != "YouTube":
        return item

    url = item.get("url", "")
    if not url:
        return item

    print(f"  → Fetching transcript for: {item.get('title', 'Unknown')[:50]}...")

    # Fetch transcript with detailed error handling
    try:
        transcript_data = transcript_fetcher.fetch_transcript(url)

        # If transcript fetch failed, return original item with error details
        if "error" in transcript_data:
            error_msg = transcript_data['error']
            print(f"    ✗ Transcript unavailable: {error_msg}")
            return {
                **item,
                "has_transcript": False,
                "transcript_error": error_msg
            }

    except Exception as e:
        error_msg = f"Exception during transcript fetch: {str(e)}"
        print(f"    ✗ {error_msg}")
        return {
            **item,
            "has_transcript": False,
            "transcript_error": error_msg
        }

    transcript_text = transcript_data.get("transcript", "")
    word_count = transcript_data.get("word_count", 0)

    print(f"    ✓ Transcript fetched ({word_count} words)")

    # Don't analyze if no Gemini model
    if not model:
        return {
            **item,
            "has_transcript": True,
            "transcript_word_count": word_count,
        }

    print(
        f"    Transcript analysis ({word_count} words) — "
        f"{'chunked_full' if word_count > 4000 else 'truncated'}"
    )
    try:
        return analyze_transcript_auto(model, item, transcript_text, word_count)
    except Exception as e:
        print(f"    ✗ Analysis failed: {type(e).__name__} - {str(e)[:100]}")
        return {
            **item,
            "has_transcript": True,
            "transcript_word_count": word_count,
            "transcript_mode": "truncated",
        }

# --- SECOND-STAGE CONTENT CLASSIFIER ---
BUCKET_MAP = {
    "General News & Research": "general",
    "AI / AI Tools / AI Agents": "ai",
    "Blockchain / Crypto / Web3": "blockchain",
    "Sense-Making & Narrative Analysis": "sense_making",
}


def classify_item(item: dict, topic_name: str) -> dict:
    """
    Second-stage classifier: assigns bucket, content_type, and processing_mode
    to each item using Gemini. Falls back to topic-based defaults if Gemini unavailable.
    """
    default_bucket = BUCKET_MAP.get(topic_name, "general")

    if not model:
        return {
            **item,
            "bucket": default_bucket,
            "content_type": "news",
            "processing_mode": "standard_summary",
            "classification_confidence": 0.5,
        }

    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")

    prompt = f"""Classify this news item. Return ONLY valid JSON, no markdown.

Title: {title}
Source type: {source}
Summary: {summary}
Topic group: {topic_name}

Return:
{{
  "bucket": "<general|ai|blockchain|sense_making>",
  "content_type": "<news|tutorial|product_release|opinion|speculative_claim|research|market_narrative>",
  "processing_mode": "<standard_summary|wisdom_extraction|claim_mapping>",
  "confidence": <0.0-1.0>
}}

Rules:
- wisdom_extraction: for tutorials, educational explainers, technical walkthroughs
- claim_mapping: for contested narratives, geopolitical analysis, institutional critique, speculative claims
- standard_summary: for everything else (news, product releases, funding announcements)"""

    try:
        response = model.generate_content(prompt)
        text = getattr(response, 'text', None)
        if not text and hasattr(response, 'candidates') and response.candidates:
            text = getattr(response.candidates[0].content.parts[0], 'text', None)
        if text:
            text = text.strip()
            if text.startswith('```'):
                text = text.replace('```json', '').replace('```', '').strip()
            classification = json.loads(text)
            return {
                **item,
                "bucket": classification.get("bucket", default_bucket),
                "content_type": classification.get("content_type", "news"),
                "processing_mode": classification.get("processing_mode", "standard_summary"),
                "classification_confidence": classification.get("confidence", 0.5),
            }
    except Exception as e:
        print(f"    Classification failed for '{title[:40]}': {e}")

    return {
        **item,
        "bucket": default_bucket,
        "content_type": "news",
        "processing_mode": "standard_summary",
        "classification_confidence": 0.5,
    }


# --- DUAL PROCESSING MODES ---

def extract_wisdom(
    item: dict,
    transcript_text: str | None = None,
    transcript_word_count: int | None = None,
    transcript_source: str | None = None,
) -> dict:
    """
    Wisdom Extraction mode for tutorials, educational content, technical walkthroughs.
    Extracts key lessons, actionable steps, tools mentioned, implementation notes.
    """
    if not model:
        return item

    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")

    transcript_block = ""
    if transcript_text:
        wc = transcript_word_count
        src = transcript_source or "unknown"
        transcript_block = f"""
Transcript excerpt (up to ~8000 words, {wc} words total, source={src}):
{transcript_text}
"""

    prompt = f"""You are an expert knowledge extractor. Analyze this educational/instructional content.

Title: {title}
Source: {source}
Summary: {summary}
{transcript_block}
Return ONLY valid JSON:
{{
  "key_lessons": ["lesson 1", "lesson 2", "lesson 3"],
  "actionable_steps": ["step 1", "step 2"],
  "tools_mentioned": ["tool 1", "tool 2"],
  "frameworks_mentioned": ["framework 1"],
  "implementation_notes": "How to apply this practically",
  "difficulty": "<beginner|intermediate|advanced>",
  "confidence": <0.0-1.0>
}}"""

    try:
        response = model.generate_content(prompt)
        text = getattr(response, 'text', None)
        if not text and hasattr(response, 'candidates') and response.candidates:
            text = getattr(response.candidates[0].content.parts[0], 'text', None)
        if text:
            text = text.strip()
            if text.startswith('```'):
                text = text.replace('```json', '').replace('```', '').strip()
            wisdom = json.loads(text)
            return {
                **item,
                "key_lessons": wisdom.get("key_lessons", []),
                "actionable_steps": wisdom.get("actionable_steps", []),
                "tools_mentioned": wisdom.get("tools_mentioned", []),
                "frameworks_mentioned": wisdom.get("frameworks_mentioned", []),
                "implementation_notes": wisdom.get("implementation_notes", ""),
                "difficulty": wisdom.get("difficulty", ""),
                "wisdom_extraction_confidence": wisdom.get("confidence"),
                "transcript_metadata": {
                    "word_count": transcript_word_count,
                    "source": transcript_source,
                    "used_in_prompt": bool(transcript_text),
                },
            }
    except Exception as e:
        print(f"    Wisdom extraction failed for '{title[:40]}': {e}")
    return item


def map_claims(
    item: dict,
    transcript_text: str | None = None,
    transcript_word_count: int | None = None,
    transcript_source: str | None = None,
) -> dict:
    """
    Neutral Claim Mapping mode for sense-making, contested narratives, speculative claims.
    Extracts claims table, entities, evidence, uncertainty markers.
    """
    if not model:
        return item

    title = item.get("title", "")
    summary = item.get("summary", "")
    source = item.get("source", "")

    transcript_block = ""
    if transcript_text:
        wc = transcript_word_count
        src = transcript_source or "unknown"
        transcript_block = f"""
Transcript excerpt (up to ~8000 words, {wc} words total, source={src}):
{transcript_text}
"""

    prompt = f"""You are a neutral claim analyst. Map the claims in this content WITHOUT judging truth.

Title: {title}
Source: {source}
Summary: {summary}
{transcript_block}
Return ONLY valid JSON:
{{
  "claims": [
    {{
      "claim": "The specific claim being made",
      "evidence_cited": "Evidence the source cites",
      "status": "<supported|mixed|unresolved|contradicted>",
      "confidence": <0.0-1.0>,
      "analyst_note": "Brief neutral note"
    }}
  ],
  "entities": ["entity 1", "entity 2"],
  "uncertainty_markers": ["what remains unclear"],
  "neutral_synthesis": "A balanced 2-3 sentence summary of the claims landscape"
}}

Rules:
- Be neutral. Do not pre-judge truth.
- Distinguish between what is claimed and what is established.
- Mark confidence honestly. Most claims should be 'unresolved' or 'mixed'."""

    try:
        response = model.generate_content(prompt)
        text = getattr(response, 'text', None)
        if not text and hasattr(response, 'candidates') and response.candidates:
            text = getattr(response.candidates[0].content.parts[0], 'text', None)
        if text:
            text = text.strip()
            if text.startswith('```'):
                text = text.replace('```json', '').replace('```', '').strip()
            claims_data = json.loads(text)
            return {
                **item,
                "claims": claims_data.get("claims", []),
                "entities": claims_data.get("entities", []),
                "uncertainty_markers": claims_data.get("uncertainty_markers", []),
                "neutral_synthesis": claims_data.get("neutral_synthesis", ""),
                "transcript_metadata": {
                    "word_count": transcript_word_count,
                    "source": transcript_source,
                    "used_in_prompt": bool(transcript_text),
                },
            }
    except Exception as e:
        print(f"    Claim mapping failed for '{title[:40]}': {e}")
    return item


def apply_processing_mode(item: dict) -> dict:
    """Route an item to the correct processing mode based on its classification."""
    mode = item.get("processing_mode", "standard_summary")
    if item.get("source") == "YouTube" and mode in ("wisdom_extraction", "claim_mapping"):
        url = item.get("url", "")
        if url and model:
            try:
                td = transcript_fetcher.fetch_transcript(url)
                if "error" not in td:
                    ttext = td.get("transcript", "")
                    wc = td.get("word_count", 0)
                    excerpt = (
                        ttext
                        if len(ttext.split()) <= 8000
                        else " ".join(ttext.split()[:8000])
                    )
                    tsrc = td.get("source")
                    if mode == "wisdom_extraction":
                        return extract_wisdom(
                            item,
                            transcript_text=excerpt,
                            transcript_word_count=wc,
                            transcript_source=tsrc,
                        )
                    return map_claims(
                        item,
                        transcript_text=excerpt,
                        transcript_word_count=wc,
                        transcript_source=tsrc,
                    )
            except Exception as e:
                print(f"    Transcript fetch for mode '{mode}' failed: {e}")

    if mode == "wisdom_extraction":
        return extract_wisdom(item)
    if mode == "claim_mapping":
        return map_claims(item)
    return item


# --- AI TRIAGE AGENT ---
def triage_and_categorize_content(topic_name: str, items: list) -> list:
    if not items:
        return []

    print(f"Running Triage Agent for topic: '{topic_name}' ({len(items)} items)")

    # Fallback if Gemini is not configured
    def fallback_triage(item_list):
        return [
            {**item, "category": "General News", "summary": ""}
            for item in item_list
        ]

    if not model:
        return fallback_triage(items)

    prompt = f"""You are a Triage Analyst. Review the following items for the topic '{topic_name}'.
Return ONLY a JSON array of objects (no markdown, no code blocks). Each object must have:
- "title": string
- "url": string
- "source": string
- "category": string (one of: "Funding Announcement", "New Framework Release", "Major Partnership", "Technical Analysis", "General News")
- "summary": string (a concise, 1-2 sentence summary)

Raw items:
{json.dumps(items, ensure_ascii=False)}"""

    try:
        response = model.generate_content(prompt)
        
        # Enhanced response extraction
        text_response = None
        if hasattr(response, 'text'):
            text_response = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            if hasattr(response.candidates[0], 'content'):
                if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
                    text_response = response.candidates[0].content.parts[0].text

        if text_response:
            # Clean markdown code blocks if present
            text_response = text_response.strip()
            if text_response.startswith('```'):
                text_response = text_response.replace('```json', '').replace('```', '').strip()
            
            parsed_json = json.loads(text_response)
            if isinstance(parsed_json, list):
                print(f"  ✓ Triage successful: {len(parsed_json)} items categorized")
                return parsed_json
            else:
                print(f"  ✗ Triage returned non-list: {type(parsed_json)}")
    except json.JSONDecodeError as je:
        print(f"ERROR: Gemini triage JSON parse failed: {je}")
        print(f"  Raw response (first 200 chars): {text_response[:200] if text_response else 'None'}")
    except Exception as e:
        print(f"ERROR: Gemini triage API call failed: {type(e).__name__} - {str(e)[:100]}")

    print(f"  → Using fallback triage")
    return fallback_triage(items)


# --- DEDUPLICATION ---
def deduplicate_items(items: list) -> list:
    """Remove duplicate items based on URL."""
    seen_urls = set()
    unique_items = []
    duplicates = 0
    
    for item in items:
        url = item.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_items.append(item)
        elif url:
            duplicates += 1
    
    if duplicates > 0:
        print(f"  ℹ Removed {duplicates} duplicate items")
    
    return unique_items


# --- MAIN ORCHESTRATOR ---
def main():
    with open(CONFIG_PATH, 'r', encoding="utf-8") as f:
        config = yaml.safe_load(f)

    final_report = {}

    fetcher_map = {
        'rss_sources': fetch_rss,
        'youtube_sources': fetch_youtube,
        'github_sources': fetch_github_trending,
        'hackernews_sources': fetch_hackernews,
        'x_sources': fetch_x_profile_posts,
        'instagram_sources': fetch_instagram_profile_posts,
    }

    for topic in config.get('topics', []):
        topic_name = topic.get('topic_name', 'Unnamed Topic')
        print(f"\n--- Processing Topic: {topic_name} ---")
        all_raw_content = []
        for source_type, fetcher_func in fetcher_map.items():
            for source_value in topic.get(source_type, []) or []:
                try:
                    fetched_items = fetcher_func(source_value)
                    if fetched_items:
                        all_raw_content.extend(fetched_items)
                except Exception as e:
                    print(f"ERROR: Failed during fetch for {source_type} '{source_value}': {e}")

        # Deduplicate before triage
        print(f"  Total items fetched: {len(all_raw_content)}")
        all_raw_content = deduplicate_items(all_raw_content)
        print(f"  Unique items: {len(all_raw_content)}")

        # First, do basic triage
        triaged_content = triage_and_categorize_content(topic_name, all_raw_content)

        # Second-stage classification: bucket, content_type, processing_mode
        print(f"\n  --- Classifying items ---")
        classified_content = []
        for item in triaged_content:
            classified_content.append(classify_item(item, topic_name))
        print(f"  ✓ Classified {len(classified_content)} items")

        # Apply processing modes (wisdom extraction or claim mapping)
        print(f"  --- Applying processing modes ---")
        processed_content = []
        mode_counts = {"standard_summary": 0, "wisdom_extraction": 0, "claim_mapping": 0}
        for item in classified_content:
            processed = apply_processing_mode(item)
            mode = item.get("processing_mode", "standard_summary")
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            processed_content.append(processed)
        print(f"  ✓ Modes: {mode_counts}")

        # NOTE: Automatic transcription DISABLED to save costs ($30/month)
        # Transcription is now ON-DEMAND via frontend UI
        yt_count = len([item for item in processed_content if item.get('source') == 'YouTube'])
        if yt_count:
            print(f"  ℹ  {yt_count} YouTube videos (transcripts on-demand via UI)")

        final_report[topic_name] = processed_content
        print(f"  Total items saved: {len(processed_content)}")

    # --- SAVE REPORT ---
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    report_path = OUTPUT_DIR / f"{timestamp}.json"
    with open(report_path, 'w', encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    # --- OPTIONAL: Markdown export for humans ---
    md_lines = [f"# Daily Research — {timestamp}", ""]

    # Sort items by quality score (highest first) for better readability
    for topic, items in final_report.items():
        md_lines.append(f"## {topic}")
        if not items:
            md_lines.append("_No items today._\n")
            continue

        # Sort by quality score if available
        sorted_items = sorted(items, key=lambda x: x.get("quality_score", 0), reverse=True)

        for it in sorted_items:
            title = it.get("title","").strip()
            url = it.get("url","").strip()
            src = it.get("source","")
            cat = it.get("category","")
            summ = it.get("summary","").strip()
            quality = it.get("quality_score")
            target_aud = it.get("target_audience", "")
            content_type = it.get("content_type", "")
            key_insights = it.get("key_insights", [])

            # Build main line
            quality_badge = f" **[{quality}/10]**" if quality else ""
            type_badge = f" `{content_type}`" if content_type and content_type != "General" else ""
            audience_badge = f" `{target_aud}`" if target_aud and target_aud != "General" else ""

            md_lines.append(f"- **[{title}]({url})**{quality_badge} — *{src} · {cat}*{type_badge}{audience_badge}")

            # Add summary
            if summ:
                md_lines.append(f"  - {summ}")

            # Add key insights for high-quality items
            if key_insights:
                md_lines.append(f"  - **Key Insights:**")
                for insight in key_insights[:3]:  # Limit to top 3
                    md_lines.append(f"    - {insight}")

        md_lines.append("")

    md_path = DOCS_DAILY_DIR / f"{timestamp}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nSUCCESS: Daily intelligence report saved to {report_path}")
    print(f"Markdown report saved to {md_path}")

    # --- OPTIONAL: Email report + scripts + transcripts via Mailaroo ---
    # We send up to three separate, smaller emails to avoid 413 errors.
    try:
        scripts_dir = ROOT_DIR / "outputs" / "scripts"
        transcripts_dir = ROOT_DIR / "outputs" / "transcripts"

        # 1) Email: main research report
        if md_path.exists():
            report_body = md_path.read_text(encoding="utf-8")
            report_subject = f"Daily Research — {timestamp}"
            # Trim extremely large reports
            MAX_REPORT_CHARS = 15000
            if len(report_body) > MAX_REPORT_CHARS:
                report_body = report_body[:MAX_REPORT_CHARS] + "\n\n[Truncated due to size]"
            send_text_email(body=report_body, subject=report_subject)

        # 2) Email: scripts summary
        if scripts_dir.exists():
            script_parts = ["Daily video scripts summary.\n"]
            MAX_EMAIL_CHARS = 15000
            for script_file in sorted(scripts_dir.glob("*.txt")):
                header = f"\n=== Script: {script_file.name} ===\n"
                try:
                    content = script_file.read_text(encoding="utf-8")
                except Exception as e:
                    content = f"[Error reading {script_file.name}: {type(e).__name__}]\n"

                MAX_SNIPPET_CHARS = 2000
                if len(content) > MAX_SNIPPET_CHARS:
                    content = content[:MAX_SNIPPET_CHARS] + "\n[Truncated script snippet]"

                candidate = header + content + "\n"
                if len("".join(script_parts)) + len(candidate) > MAX_EMAIL_CHARS:
                    break
                script_parts.append(candidate)

            script_body = "".join(script_parts)
            script_subject = f"Daily Video Scripts Summary — {timestamp}"
            if len(script_body.strip()) > 0:
                send_text_email(body=script_body, subject=script_subject)

        # 3) Email: transcripts summary
        if transcripts_dir.exists():
            transcript_parts = ["Daily transcripts summary.\n"]
            MAX_EMAIL_CHARS = 15000
            for transcript_file in sorted(transcripts_dir.glob("*.json")):
                try:
                    data = json.loads(transcript_file.read_text(encoding="utf-8"))
                    title = data.get("video_url") or data.get("video_id") or transcript_file.name
                    transcript_text = data.get("transcript", "")
                except Exception as e:
                    title = transcript_file.name
                    transcript_text = f"[Error reading transcript JSON: {type(e).__name__}]\n"

                MAX_SNIPPET_CHARS = 2000
                if len(transcript_text) > MAX_SNIPPET_CHARS:
                    transcript_text = transcript_text[:MAX_SNIPPET_CHARS] + "\n[Truncated transcript snippet]"

                header = f"\n=== Transcript: {title} ===\n"
                candidate = header + transcript_text + "\n"
                if len("".join(transcript_parts)) + len(candidate) > MAX_EMAIL_CHARS:
                    break
                transcript_parts.append(candidate)

            transcripts_body = "".join(transcript_parts)
            transcripts_subject = f"Daily Transcripts Summary — {timestamp}"
            if len(transcripts_body.strip()) > 0:
                send_text_email(body=transcripts_body, subject=transcripts_subject)

    except Exception as e:
        print(f"WARNING: Failed to build or send Mailaroo digest emails: {type(e).__name__}: {str(e)[:200]}")

if __name__ == "__main__":
    main()
