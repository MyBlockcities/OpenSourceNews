Github actions for youtube channels: 
UCSv4qL8vmoSH7GaPjuqRiCQ, 
UCawZsQWqfGSbCI5yjkdVkTA, 
UC2WmuBuFq6gL08QYG-JjXKw, 
UChpleBmo18P08aKCIgti38g, 
UCuV9EB4I9L-xmRoaXd8tmuA, 
UCqK_GSMbpiV8spgD3ZGloSw, 
UCAl9Ld79qaZxp9JzEOwd3aA 



.github/workflows/daily.yml Copy name: Daily Research Briefing on: schedule: - cron: "0 7 * * *" # Runs at 0 7 * * * UTC workflow_dispatch: {} # Allows manual runs permissions: contents: write # Needed to commit the report back to the repo concurrency: group: daily-research cancel-in-progress: false jobs: run-research: runs-on: ubuntu-latest timeout-minutes: 30 steps: - name: Checkout repository uses: actions/checkout@v4 - name: Set up Python uses: actions/setup-python@v5 with: python-version: '3.11' - name: Cache pip dependencies uses: actions/cache@v4 with: path: ~/.cache/pip key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }} restore-keys: | ${{ runner.os }}-pip- - name: Install dependencies run: pip install -r requirements.txt - name: Run research pipeline env: GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }} # X_CONSUMER_KEY: ${{ secrets.X_CONSUMER_KEY }} # X_CONSUMER_SECRET: ${{ secrets.X_CONSUMER_SECRET }} # Add other secrets for social media APIs here run: python pipelines/daily_run.py - name: Commit and push report run: | git config --global user.name "GitHub Actions Bot" git config --global user.email "actions-bot@users.noreply.github.com" git add outputs/daily/*.json || true git commit -m "Daily intelligence report for $(date -u +'%Y-%m-%d')" || echo "No changes to commit" git push pipelines/daily_run.py Copy import os import yaml import json import datetime import requests from bs4 import BeautifulSoup from pathlib import Path import google.generativeai as genai # --- CONFIGURATION --- ROOT_DIR = Path(__file__).resolve().parents[1] CONFIG_PATH = ROOT_DIR / 'config' / 'feeds.yaml' OUTPUT_DIR = ROOT_DIR / 'outputs' / 'daily' OUTPUT_DIR.mkdir(parents=True, exist_ok=True) # --- HTTP DEFAULTS --- HTTP_TIMEOUT = 20 HTTP_HEADERS = { "User-Agent": "Mozilla/5.0 (research-bot; +https://github.com/user/repo)" } # --- GEMINI SETUP --- GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") model = None if GEMINI_API_KEY: genai.configure(api_key=GEMINI_API_KEY) model = genai.GenerativeModel("gemini-2.5-flash") else: print("WARNING: GEMINI_API_KEY not found. Triage agent will be skipped.") # --- HELPERS --- def _get(url: str): r = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT) r.raise_for_status() return r # --- DATA FETCHERS --- def fetch_rss(url: str, limit: int = 5): if not url: return [] try: resp = _get(url) soup = BeautifulSoup(resp.content, "xml") items = [] for item in soup.find_all("item")[:limit]: title = (item.title.text if item.title else "").strip() link = (item.link.text if item.link else "").strip() if title and link: items.append({"title": title, "url": link, "source": "RSS"}) return items except Exception as e: print(f"ERROR: RSS fetch failed for {url}: {e}") return [] def fetch_youtube_channel(channel_id: str): if not channel_id: return [] print(f"INFO: Skipping YouTube placeholder for Channel ID '{channel_id}'. Implement with YouTube Data API.") # To implement: Use googleapiclient to search for recent videos by channelId. # This requires a YouTube Data API key. return [] def fetch_github_trending(language: str): if not language: return [] url = f"https://github.com/trending/{language}" try: resp = _get(url) soup = BeautifulSoup(resp.content, "html.parser") items = [] for repo in soup.select("article.Box-row")[:5]: a_tag = repo.select_one("h2 > a") if not a_tag: continue title = " ".join(a_tag.text.split()) href = a_tag.get("href", "") if href: items.append({"title": title, "url": f"https://github.com{href}", "source": "GitHub Trending"}) return items except Exception as e: print(f"ERROR: GitHub trending fetch for '{language}' failed: {e}") return [] def fetch_hackernews(keyword: str): if not keyword: return [] url = f"https://hn.algolia.com/api/v1/search?query={keyword}&tags=story" try: hits = _get(url).json().get("hits", []) items = [] for hit in hits[:5]: title, link = hit.get("title"), hit.get("url") if title and link: items.append({"title": title, "url": link, "source": "Hacker News"}) return items except Exception as e: print(f"ERROR: Hacker News fetch for '{keyword}' failed: {e}") return [] def fetch_x_profile_posts(username: str): if not username: return [] print(f"INFO: Skipping X placeholder for @{username}. Implement with official X API.") return [] def fetch_instagram_profile_posts(username: str): if not username: return [] print(f"INFO: Skipping Instagram placeholder for @{username}.") return [] # --- AI TRIAGE AGENT --- def triage_and_categorize_content(topic_name: str, items: list) -> list: if not items: return [] print(f"Running Triage Agent for topic: '{topic_name}' ({len(items)} items)") # Fallback if Gemini is not configured def fallback_triage(item_list): return [ {**item, "category": "General News", "summary": ""} for item in item_list ] if not model: return fallback_triage(items) prompt = f""" You are a Triage Analyst. Review the following items for the topic '{topic_name}'. Return ONLY a JSON array of objects. Each object must have: - "title": string - "url": string - "source": string - "category": string (one of: "Funding Announcement", "New Framework Release", "Major Partnership", "Technical Analysis", "General News") - "summary": string (a concise, 1-2 sentence summary) Raw items: {json.dumps(items, ensure_ascii=False)} """ try: response = model.generate_content( prompt, generation_config={"response_mime_type": "application/json"} ) # Handle potential variations in Gemini SDK response structure text_response = getattr(response, 'text', None) if not text_response and response.candidates: text_response = response.candidates[0].content.parts[0].text if text_response: parsed_json = json.loads(text_response) if isinstance(parsed_json, list): return parsed_json except Exception as e: print(f"ERROR: Gemini triage API call failed: {e}. Using fallback.") return fallback_triage(items) # --- MAIN ORCHESTRATOR --- def main(): with open(CONFIG_PATH, 'r', encoding="utf-8") as f: config = yaml.safe_load(f) final_report = {} fetcher_map = { 'rss_sources': fetch_rss, 'youtube_sources': fetch_youtube_channel, 'github_sources': fetch_github_trending, 'hackernews_sources': fetch_hackernews, 'x_sources': fetch_x_profile_posts, 'instagram_sources': fetch_instagram_profile_posts, } for topic in config.get('topics', []): topic_name = topic.get('topic_name', 'Unnamed Topic') print(f"\n--- Processing Topic: {topic_name} ---") all_raw_content = [] for source_type, fetcher_func in fetcher_map.items(): for source_value in topic.get(source_type, []) or []: try: fetched_items = fetcher_func(source_value) if fetched_items: all_raw_content.extend(fetched_items) except Exception as e: print(f"ERROR: Failed during fetch for {source_type} '{source_value}': {e}") triaged_content = triage_and_categorize_content(topic_name, all_raw_content) final_report[topic_name] = triaged_content # --- SAVE REPORT --- timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d") report_path = OUTPUT_DIR / f"{timestamp}.json" with open(report_path, 'w', encoding="utf-8") as f: json.dump(final_report, f, indent=2, ensure_ascii=False) print(f"\nSUCCESS: Daily intelligence report saved to {report_path}") if __name__ == "__main__": main() config/feeds.yaml Copy # config/feeds.yaml topics: - topic_name: "AI Agents & Frameworks" github_sources: - "typescript" hackernews_sources: - "AI Agent" youtube_sources: - "UC_x36zCEGilGpB1m-V4gmjg" x_sources: - "Sauain" - "levelsio" - "TimBeiko" - "SwiftOnSecurity" - topic_name: "Blockchain VC Funding" rss_sources: - "https://www.coindesk.com/arc/outboundfeeds/rss/" x_sources: - "a16zcrypto" requirements.txt Copy requests beautifulsoup4 PyYAML python-dotenv google-generativeai # --- OPTIONAL: For X/Twitter Integration (implement fetcher in daily_run.py) --- # tweepy # --- OPTIONAL: For Instagram Integration (use with caution, may be unstable) --- # instaloader Step 3: Deploy to GitHub Create a new, private GitHub repository. Create the folder structure inside: pipelines/, config/, .github/workflows/. Copy the generated code above into the corresponding files in your repository. Go to your repository's **Settings > Secrets and variables > Actions**. Click **New repository secret** and add your GEMINI_API_KEY. If using X or Instagram, add their API keys as secrets (e.g., X_CONSUMER_KEY) and implement the logic in pipelines/daily_run.py. Commit and push the files. The action will run on your defined schedule, or you can trigger it manually from the "Actions" tab.


The only real “missing piece” is a working YouTube fetcher (handles → channelId and recent videos), plus a couple tiny hardening tweaks. Drop the snippets below into your repo and you’ll have an end-to-end, scheduled, quota-safe pipeline.

---

# 1) Add YouTube support (handles or channel IDs)

### `.github/workflows/daily.yml` (add `YT_API_KEY`)

```yaml
      - name: Run research pipeline
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          YT_API_KEY: ${{ secrets.YT_API_KEY }}   # ⬅️ add this
        run: python pipelines/daily_run.py
```

Add the secret in **Settings → Secrets and variables → Actions → New repository secret** as `YT_API_KEY`.

---

### `pipelines/youtube.py` (new)

```python
import os
import time
import json
import httpx
from typing import List, Dict, Tuple

YT_API_KEY = os.getenv("YT_API_KEY", "")
BASE = "https://www.googleapis.com/youtube/v3"

# Basic rate limiter (very light)
_last_call = 0.0
def _throttle(min_interval=0.2):
    global _last_call
    dt = time.time() - _last_call
    if dt < min_interval:
        time.sleep(min_interval - dt)
    _last_call = time.time()

def _get(endpoint: str, params: Dict) -> Dict:
    if not YT_API_KEY:
        raise RuntimeError("YT_API_KEY not set")
    _throttle()
    params = dict(params or {})
    params["key"] = YT_API_KEY
    url = f"{BASE}/{endpoint}"
    with httpx.Client(timeout=30.0) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()

def resolve_channel_id(identifier: str) -> str:
    """
    Accepts:
      - a channel ID (starts with 'UC...')
      - a handle like '@TwoMinutePapers' or '@vrsen'
      - a plain query like 'indydevdan'
    Returns a channelId (UCxxxx...) or '' if not found.
    """
    if not identifier:
        return ""
    ident = identifier.strip()
    if ident.startswith("UC") and len(ident) >= 20:
        return ident  # already a channel ID
    # Search for a channel matching the handle or query
    data = _get("search", {
        "part": "snippet",
        "q": ident,
        "type": "channel",
        "maxResults": 1
    })
    items = data.get("items", [])
    if not items:
        return ""
    return items[0]["id"]["channelId"]

def fetch_latest_videos(identifier: str, max_results: int = 5) -> List[Dict]:
    """
    Returns a list of {title, url, publishedAt, channelTitle, source}
    """
    ch_id = resolve_channel_id(identifier)
    if not ch_id:
        return []
    # Search latest videos by channelId
    data = _get("search", {
        "part": "snippet",
        "channelId": ch_id,
        "order": "date",
        "type": "video",
        "maxResults": max(1, min(max_results, 10))
    })
    out = []
    for it in data.get("items", []):
        sn = it["snippet"]
        out.append({
            "title": sn["title"],
            "url": f"https://youtu.be/{it['id']['videoId']}",
            "publishedAt": sn["publishedAt"],
            "channelTitle": sn["channelTitle"],
            "source": "YouTube"
        })
    return out
```

---

# 2) Wire it into your main pipeline

### `pipelines/daily_run.py` (replace your YouTube placeholders)

1. **Add the import** near the top:

```python
from pipelines.youtube import fetch_latest_videos
```

2. **Replace** your current `fetch_youtube_channel` + mapping with this:

```python
def fetch_youtube(identifier: str):
    # Accepts channelId, @handle, or plain name
    try:
        return fetch_latest_videos(identifier, max_results=5)
    except Exception as e:
        print(f"ERROR: YouTube fetch failed for '{identifier}': {e}")
        return []
```

…and update the `fetcher_map`:

```python
fetcher_map = {
    'rss_sources': fetch_rss,
    'youtube_sources': fetch_youtube,          # ⬅️ updated
    'github_sources': fetch_github_trending,
    'hackernews_sources': fetch_hackernews,
    'x_sources': fetch_x_profile_posts,
    'instagram_sources': fetch_instagram_profile_posts,
}
```

That’s it. Your topics can now list either a `UC…` channelId, an `@handle`, or a plain name, and it’ll just work.

---

# 3) Clean config example (handles or IDs)

### `config/feeds.yaml`

```yaml
topics:
  - topic_name: "AI Agents & Frameworks"
    github_sources:
      - "typescript"
    hackernews_sources:
      - "AI agent"
    rss_sources:
      - "https://ai.googleblog.com/atom.xml"
    youtube_sources:
      - "@TwoMinutePapers"     # handle works
      - "indydevdan"           # plain name works
      - "UC_x36zCEGilGpB1m-V4gmjg"  # channelId works

  - topic_name: "Blockchain VC Funding"
    rss_sources:
      - "https://www.coindesk.com/arc/outboundfeeds/rss/"
```

---

# 4) Requirements update

### `requirements.txt`

```text
requests
beautifulsoup4
PyYAML
python-dotenv
google-generativeai
httpx
```

*(We use `httpx` for the YouTube API calls.)*

---

# 5) Optional: markdown export (nice for quick reading)

Add this near the end of `main()` in `pipelines/daily_run.py` (after writing the JSON):

```python
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
```

…and in the workflow’s commit step, also add `*.md`:

```bash
git add outputs/daily/*.json outputs/daily/*.md || true
```

---

# 6) Optional: precise local-time trigger

If you ever want exact **America/Denver** timing independent of UTC/DST drift, add this extra workflow to receive external triggers:

### `.github/workflows/dispatch.yml`

```yaml
name: Dispatch Receiver
on:
  repository_dispatch:
    types: [run-deep-research]
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python pipelines/daily_run.py
```

Then have any precise scheduler (Railway cron, Cloud Scheduler, etc.) POST:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GH_PAT" \
  https://api.github.com/repos/<owner>/<repo>/dispatches \
  -d '{"event_type":"run-deep-research"}'
```

---

## Sanity checklist

* [ ] `YT_API_KEY` added as a repo secret
* [ ] `youtube.py` file created and imported
* [ ] `requirements.txt` includes `httpx`
* [ ] `feeds.yaml` has no empty strings
* [ ] Workflow `permissions: contents: write` present
