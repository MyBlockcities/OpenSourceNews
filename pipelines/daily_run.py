import os
import sys
import yaml
import json
import datetime
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import google.generativeai as genai

# Add parent directory to path to enable imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelines.youtube import fetch_latest_videos

# --- CONFIGURATION ---
ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / 'config' / 'feeds.yaml'
OUTPUT_DIR = ROOT_DIR / 'outputs' / 'daily'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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

    prompt = f"""
    You are a Triage Analyst. Review the following items for the topic '{topic_name}'.
    Return ONLY a JSON array of objects. Each object must have:
    - "title": string
    - "url": string
    - "source": string
    - "category": string (one of: "Funding Announcement", "New Framework Release", "Major Partnership", "Technical Analysis", "General News")
    - "summary": string (a concise, 1-2 sentence summary)

    Raw items:
    {json.dumps(items, ensure_ascii=False)}
    """

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        # Handle potential variations in Gemini SDK response structure
        text_response = getattr(response, 'text', None)
        if not text_response and response.candidates:
             text_response = response.candidates[0].content.parts[0].text

        if text_response:
             parsed_json = json.loads(text_response)
             if isinstance(parsed_json, list):
                 return parsed_json
    except Exception as e:
        print(f"ERROR: Gemini triage API call failed: {e}. Using fallback.")

    return fallback_triage(items)


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

        triaged_content = triage_and_categorize_content(topic_name, all_raw_content)
        final_report[topic_name] = triaged_content

    # --- SAVE REPORT ---
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    report_path = OUTPUT_DIR / f"{timestamp}.json"
    with open(report_path, 'w', encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    # --- OPTIONAL: Markdown export for humans ---
    md_lines = [f"# Daily Research — {timestamp}", ""]
    for topic, items in final_report.items():
        md_lines.append(f"## {topic}")
        if not items:
            md_lines.append("_No items today._\n")
            continue
        for it in items:
            title = it.get("title","").strip()
            url = it.get("url","").strip()
            src = it.get("source","")
            cat = it.get("category","")
            summ = it.get("summary","").strip()
            md_lines.append(f"- **[{title}]({url})** — *{src} · {cat}*")
            if summ:
                md_lines.append(f"  - {summ}")
        md_lines.append("")
    (OUTPUT_DIR / f"{timestamp}.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nSUCCESS: Daily intelligence report saved to {report_path}")
    print(f"Markdown report saved to {OUTPUT_DIR / f'{timestamp}.md'}")

if __name__ == "__main__":
    main()
