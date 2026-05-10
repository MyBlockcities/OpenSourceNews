
Help me plan and then execute, setting up new capabilities to extend OpenSourceNews to auto‑discover ~20 new micro‑influencers per day per niche with nothing but scheduled GitHub Actions plus free‑tier APIs (mainly YouTube + RSS + generic web), but you cannot reliably *analyze* X accounts for free anymore; you’d treat X handles as metadata discovered from other sources. 

Below is a practical, repo‑level way to do it.

***

## Key constraints and free‑tier realities

Because you want this to run “for free” inside a public GitHub repo:

| Component | Free reality (2026) | Implication |
| --- | --- | --- |
| GitHub Actions | Standard runners are free and effectively unlimited for **public** repos (minutes and storage), with a max ~6 hours per job. [github](https://github.com/orgs/community/discussions/70492) | You can run a daily scheduled workflow that fetches data, runs ranking logic, and commits a JSON/CSV file of 20 new influencers per niche back into the repo. |
| YouTube Data API | Default free quota: **10,000 units/day** per project; search.list costs 100 units per call, other read calls are cheaper. [getphyllo](https://www.getphyllo.com/post/is-the-youtube-api-free-costs-limits-iv) | Plenty for a few keyword searches per niche + channel lookups; very viable for discovering micro‑influencers from your topical queries. |
| X (Twitter) API | Free tier for meaningful reads is gone; new devs are on pay‑per‑use: reads start at **$0.005 per post**, followers at around **$0.01 per resource**, and free tier is effectively discontinued. [postproxy](https://postproxy.dev/blog/x-api-pricing-2026/) | You can’t cheaply do large‑scale search, follower‑count checks, or engagement stats for X purely via official API. Treat X as a channel you *link to* (when you see handles in bios/descriptions), not one you exhaustively scan for free. |
| RSS / HTML news pages | No direct cost; only thing to watch is each site’s robots.txt/ToS around scraping frequency. | Perfect for pulling author names, bylines, and social links around your target topics. |

Because I can’t read the repo contents directly (GitHub’s HTML is blocked to tools), I’ll treat OpenSourceNews as a typical Python/TS news+YouTube+RSS aggregator and show how to bolt an “influencer discovery” layer on top of what you already do. [github](https://github.com/orgs/community/discussions/156389)

***

## High‑level pipeline: daily influencer discovery

You can think of this as a daily, fully automated ETL job, implemented as a GitHub Actions workflow that runs a Python/Node script in the repo.

**Daily job steps:**

1. **Ingest fresh content (reuse what you already have):**  
   - Pull new articles via your existing RSS/HTML scrapers.  
   - Pull new YouTube videos & transcripts for your focus topics.  
   - Optionally, ingest newsletters or other feeds if you already do that.

2. **Extract creator identities from that content:**  
   - YouTube: channel ID, channel title, link, description, tags.  
   - Articles/blogs: byline name, site domain, author page, any “follow me on X/IG” links.  
   - Embedded social links: regex for `x.com/handle`, `twitter.com/handle`, `instagram.com/...`, `tiktok.com/@...` in descriptions and author bios.

3. **Enrich each candidate with free‑tier stats:**
   - For YouTube: call YouTube Data API `channels.list` for subscriber count, view count, and recent upload activity; this is cheap in quota terms vs `search.list`. [elfsight](https://elfsight.com/blog/youtube-data-api-v3-limits-operations-resources-methods-etc/)
   - For blogs/RSS: basic signals like posting frequency (how many posts in last N days) and whether they cover your target tags.  
   - For social handles: don’t hit X API; just store the handle as metadata associated with the channel/author.

4. **Score and filter as “micro‑influencers”:**
   - Define micro‑influencer bands per platform (e.g., 2k–50k subs for YouTube; you can adjust).  
   - Score based on: niche match, recency, activity, and engagement proxies (views per recent video, comments, likes if accessible via YouTube API or HTML).

5. **Select 20 new ones per day per niche:**
   - Maintain a JSON/CSV store (in the repo) of all previously discovered influencer IDs per niche.  
   - From today’s candidates, filter out any already in the store, sort by score, and take the top N (e.g., 20 per topic or 20 overall).  

6. **Persist & expose:**
   - Update `data/influencers/<topic>.json` and commit/push from GitHub Actions back to `main`.  
   - Downstream: other scripts or marketing pipelines can read those files and auto‑generate outreach lists, asset ideas, or co‑marketing content.

All of this can run inside a **daily cron‑triggered GitHub Action** for a public repo, which is free on standard runners. [github](https://github.com/orgs/community/discussions/26054)

***

## Platform‑specific strategy (per focus area)

### 1) Real estate tokenization

**Primary sources:**

- YouTube search for “real estate tokenization”, “RWA real estate”, “property tokenization”, etc., restricted to last 7–30 days. [getphyllo](https://www.getphyllo.com/post/is-the-youtube-api-free-costs-limits-iv)
- RSS/news: crypto/fintech blogs and verticals (Bankless, CoinDesk RWA pieces, etc.) where authors repeatedly cover tokenized real estate.

**Detection logic:**

- YouTube:  
  - Use `search.list` with topic keywords + date filter.  
  - For each result, call `channels.list` and mark channels with subscriber count in your micro‑band (e.g., 1k–50k subs) and at least 1–2 videos about tokenization in the last month. [developers.google](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits)
- RSS/blogs:  
  - Extract author names & URLs; track frequency of posts containing tokenization/RWA keywords.  
  - Treat frequently appearing authors as “micro‑influencers” even if they primarily write versus post video.

***

### 2) Alternative news

**Primary sources:**

- YouTube channels focused on “alternative media”, “independent news”, “censorship”, etc.  
- RSS from independent-journalism platforms, Substack tags, and alt‑news blogs that you’re already aggregating.

**Detection logic:**

- YouTube: same pattern as above but with alt‑news keywords + view/subscriber thresholds.  
- RSS: authors and Substack writers whose bylines show up consistently on relevant stories.

You don’t need to label them as “alt” programmatically; use your existing topic classification on content to propagate a topic label to the creator.

***

### 3) Blockchain and crypto

This is the easiest to mine because YouTube crypto channels are plentiful and well‑indexed.

**Primary sources:**

- YouTube: “onchain analysis”, “real world assets”, “DeFi RWA”, “crypto regulation”, “tokenization” keywords.  
- RSS/news: crypto news sites, RWA newsletters, etc.

**Detection logic:**

- YouTube search → channel stats → micro‑band filter, exactly as with real estate tokenization.  
- Since big channels dominate crypto, you may want multiple tiers: true micro (2–20k), mid (20–200k) and exclude >500k as “macro” for other purposes.

***

### 4) Peptides

**Primary sources:**

- YouTube search for “BPC‑157”, “TB‑500”, “peptide therapy”, “GLP‑1 peptides”, “semaglutide alternatives”, etc. [wyclinicfoundation](https://wyclinicfoundation.com/top-5-clinical-research-peptides)
- Blogs/RSS from peptide therapy clinics, peptide education hubs, and MD blogs you already found; they often include bylines and social handles. [mypeptidematch](https://www.mypeptidematch.com/blog)

**Detection logic:**

- YouTube: filter channels where 2+ recent videos are about peptides or peptide‑adjacent wellness and channel subs within your micro range.  
- Blogs: treat recurring peptide authors+their clinics as micro‑influencers, and store their YouTube channel or Insta/X handles if present in bios.

Because the peptide niche can drift into non‑compliant gray‑market material, you can also flag channels as “clinical/MD” vs “bro‑science” based on key phrases and disclaimers, which is useful for XoPure’s brand safety.

***

### 5) Fitness & wellness

**Primary sources:**

- YouTube: “functional fitness”, “longevity”, “biohacking”, “peptide stack”, “wellness routine”, etc.  
- RSS: fitness blogs, wellness newsletters, and podcasts with transcripts.

**Detection logic:**

- YouTube: micro‑band channels where recent videos also include your peptide/crypto/alt‑news/real‑estate tokens in titles/descriptions get boosted scores (because they overlap multiple focus areas).  
- RSS/podcasts: host + guest name extraction from transcripts and show notes.

***

## How to wire this into OpenSourceNews via GitHub Actions

Even without seeing your code, you can add the following pattern on top of your existing repo.

### 1) Workflow skeleton

Create `.github/workflows/influencer-discovery.yml`:

```yaml
name: Daily Influencer Discovery

on:
  schedule:
    - cron: "0 5 * * *"  # 5:00 UTC daily
  workflow_dispatch: {}

jobs:
  discover:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          pip install -r requirements.txt

      - name: Run discovery script
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: |
          python scripts/discover_influencers.py

      - name: Commit updated influencer data
        if: success()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/influencers/*.json
          git commit -m "chore: daily influencer update" || exit 0
          git push
```

This stays entirely within free GitHub Actions limits for a public repo. [docs.github](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

### 2) `discover_influencers.py` outline

In that script, you’d:

- Load existing influencer registry files, e.g.  
  - `data/influencers/real_estate_tokenization.json`  
  - `data/influencers/alt_news.json`  
  - `data/influencers/crypto.json`  
  - `data/influencers/peptides.json`  
  - `data/influencers/fitness_wellness.json`

- For each topic:  
  - Run YouTube search queries (minimal number of `search.list` calls to conserve quota). [dev](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h)
  - Call `channels.list` for the channels returned to fetch stats. [elfsight](https://elfsight.com/blog/youtube-data-api-v3-limits-operations-resources-methods-etc/)
  - Scrape any new RSS items you’ve already downloaded that match the same topic label and extract authors & social handles.

- Compute a topic‑specific score function, e.g.:

\[
\text{score} = w_1 \cdot \text{normalized_subs} + w_2 \cdot \text{recent_views} + w_3 \cdot \text{topic_match} + w_4 \cdot \text{posting_recency}
\]

(using plain math in code, no external service).

- Deduplicate against existing influencers (by channel ID / canonical URL / author identifier).

- Sort by score and pick top N that are **new**.

- Append them to the relevant JSON file with a structure like:

```json
{
  "id": "UCxxxx",
  "name": "Example Creator",
  "platform": "youtube",
  "topic": "peptides",
  "primary_url": "https://www.youtube.com/@example",
  "discovered_on": "2026-05-10",
  "metrics": {
    "subscribers": 8450,
    "avg_recent_views": 3200,
    "posts_per_month": 6
  },
  "social_links": {
    "x": "https://x.com/example",
    "instagram": "https://www.instagram.com/example"
  }
}
```

***

## Handling X.com “for free”

Because there is no real free read tier for X anymore, and new devs are on pay‑per‑use pricing for reads and followers: [postproxy](https://postproxy.dev/blog/x-api-pricing-2026/)

- **Do not** plan on:  
  - Searching X for influencers,  
  - Pulling follower counts, or  
  - Streaming engagement metrics via official API, if your goal is strictly zero spend.

- What you *can* safely do for free:

  - **Extraction only:** when you see `x.com/username` links in YouTube descriptions, author bios, or RSS content, extract and store them as part of the influencer profile.  
  - **Outbound use:** later, if you or a separate (paid) system wants to query X, it can start from that curated list of handles.

That keeps OpenSourceNews + GitHub Actions firmly in the “free infra” world while still tying creators to their X presence by URL.

***

## Why this is realistic to run daily, for free

- A single daily job doing a few dozen YouTube searches and channel lookups will stay far under **10,000 YouTube quota units/day**. [dev](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h)
- GitHub Actions on public repos with standard runners are **free and effectively unlimited**, so your daily cron workflows cost you nothing, aside from occasional timeouts if you push them beyond ~6 hours. [github](https://github.com/orgs/community/discussions/70492)
- RSS and HTML parsing are just plain HTTP GETs from Actions and don’t incur platform fees; you just need to keep an eye on rate limits and robots.txt.





Below is concrete, drop‑in code to add a **daily, free, YouTube‑first micro‑influencer discovery pipeline** to OpenSourceNews, wired via GitHub Actions. It uses only your existing stack (requests, PyYAML, lxml, etc.) and free YouTube quota plus free GitHub Actions minutes for public repos. [getphyllo](https://www.getphyllo.com/post/is-the-youtube-api-free-costs-limits-iv)

You can extend it later to RSS authors, but this gets you a working baseline that finds **up to 20 new YouTube micro‑influencers per topic per day** in your five focus areas.

***

## 1) GitHub Actions workflow

Create `.github/workflows/influencer-discovery.yml` in the repo:

```yaml
name: Daily Influencer Discovery

on:
  schedule:
    - cron: "0 5 * * *"  # 05:00 UTC daily
  workflow_dispatch: {}

jobs:
  discover:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run influencer discovery
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: |
          python scripts/discover_influencers.py

      - name: Commit and push updated influencer data
        if: success()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/influencers/*.json || echo "No influencer files changed"
          git commit -m "chore: daily influencer update" || echo "No changes to commit"
          git push || echo "No changes pushed"
```

- Set `YOUTUBE_API_KEY` in repo secrets; YouTube Data API v3 free quota is 10k units/day, enough for modest search+channel lookups. [dev](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h)
- Actions minutes are free for public repos on GitHub standard runners. [docs.github](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

***

## 2) Directory structure

Ensure these directories exist:

```bash
mkdir -p scripts
mkdir -p data/influencers
mkdir -p config
```

You already have `config/feeds.yaml`; we’ll read it but not modify it.

***

## 3) Python: `scripts/discover_influencers.py`

Save this as `scripts/discover_influencers.py`:

```python
import os
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

import requests
import yaml  # PyYAML
from lxml import etree  # For optional RSS parsing

# ------------- Configuration -------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "influencers"
CONFIG_FEEDS_PATH = BASE_DIR / "config" / "feeds.yaml"

DATA_DIR.mkdir(parents=True, exist_ok=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") or os.getenv("YT_API_KEY")

# How many new influencers per topic per run
NEW_INFLUENCERS_PER_TOPIC = 20

# Define micro-influencer bands for YouTube
MIN_SUBSCRIBERS = 2_000
MAX_SUBSCRIBERS = 100_000

# Look back this many days when searching for new videos
SEARCH_DAYS = 7

# Topics and their YouTube search queries
INFLUENCER_TOPICS: Dict[str, Dict[str, Any]] = {
    "real_estate_tokenization": {
        "label": "Real Estate Tokenization",
        "youtube_queries": [
            "real estate tokenization",
            "tokenized real estate",
            "real estate RWA",
            "property tokenization"
        ],
    },
    "alternative_news": {
        "label": "Alternative News",
        "youtube_queries": [
            "independent news",
            "alternative media",
            "censored news",
            "independent journalism"
        ],
    },
    "blockchain_crypto": {
        "label": "Blockchain & Crypto",
        "youtube_queries": [
            "real world assets crypto",
            "RWA tokenization",
            "onchain analysis",
            "crypto regulation 2026",
        ],
    },
    "peptides": {
        "label": "Peptides",
        "youtube_queries": [
            "peptide therapy",
            "BPC-157",
            "TB-500 peptide",
            "GLP-1 peptides",
            "semaglutide alternatives",
        ],
    },
    "fitness_wellness": {
        "label": "Fitness & Wellness",
        "youtube_queries": [
            "functional fitness",
            "longevity protocol",
            "biohacking routine",
            "wellness peptides",
        ],
    },
}


# ------------- Data Model -------------

@dataclass
class InfluencerMetrics:
    subscribers: Optional[int] = None
    total_views: Optional[int] = None
    videos_last_30d: Optional[int] = None
    avg_recent_views: Optional[float] = None


@dataclass
class Influencer:
    id: str
    name: str
    platform: str
    topic_key: str
    topic_label: str
    primary_url: str
    discovered_on: str
    metrics: InfluencerMetrics
    social_links: Dict[str, str]
    source_metadata: Dict[str, Any]


# ------------- Utility Functions -------------

def load_existing_influencers(topic_key: str) -> List[Influencer]:
    path = DATA_DIR / f"{topic_key}.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    influencers: List[Influencer] = []
    for item in raw:
        metrics = InfluencerMetrics(**item.get("metrics", {}))
        influencers.append(
            Influencer(
                id=item["id"],
                name=item["name"],
                platform=item["platform"],
                topic_key=item["topic_key"],
                topic_label=item.get("topic_label", topic_key),
                primary_url=item["primary_url"],
                discovered_on=item["discovered_on"],
                metrics=metrics,
                social_links=item.get("social_links", {}),
                source_metadata=item.get("source_metadata", {}),
            )
        )
    return influencers


def save_influencers(topic_key: str, influencers: List[Influencer]) -> None:
    path = DATA_DIR / f"{topic_key}.json"
    serializable = []
    for inf in influencers:
        data = asdict(inf)
        # Flatten metrics dataclass
        data["metrics"] = asdict(inf.metrics)
        serializable.append(data)
    with path.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)


def iso_today() -> str:
    return datetime.utcnow().date().isoformat()


def get_published_after_iso(days: int) -> str:
    dt = datetime.utcnow() - timedelta(days=days)
    return dt.isoformat("T") + "Z"


# ------------- YouTube API Helpers -------------

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def youtube_search_channels_for_topic(
    topic_key: str, queries: List[str]
) -> Set[str]:
    """
    Returns a set of channel IDs that recently posted videos relevant to the topic.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not set")

    channel_ids: Set[str] = set()
    published_after = get_published_after_iso(SEARCH_DAYS)

    for query in queries:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 25,
            "order": "date",
            "publishedAfter": published_after,
            "key": YOUTUBE_API_KEY,
        }
        resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId")
            if channel_id:
                channel_ids.add(channel_id)

    return channel_ids


def youtube_fetch_channel_stats(channel_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch snippet and statistics for a list of channel IDs.
    """
    if not channel_ids:
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    # YouTube channels.list supports up to 50 IDs per call
    for i in range(0, len(channel_ids), 50):
        chunk = channel_ids[i : i + 50]
        params = {
            "part": "snippet,statistics",
            "id": ",".join(chunk),
            "key": YOUTUBE_API_KEY,
            "maxResults": 50,
        }
        resp = requests.get(YOUTUBE_CHANNELS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            cid = item.get("id")
            if not cid:
                continue
            results[cid] = item
    return results


def parse_int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def score_channel(stats: Dict[str, Any]) -> float:
    """
    Simple scoring function: log-like scale for subs and views.
    """
    s = stats.get("statistics", {})
    subs = parse_int_or_none(s.get("subscriberCount")) or 0
    views = parse_int_or_none(s.get("viewCount")) or 0

    # Basic heuristic: favor micro-range with decent views
    # Use square root-like scaling by raising to 0.5
    # Avoid math module log/exp to keep it simple.
    subs_score = subs ** 0.5
    views_score = views ** 0.3
    return subs_score + views_score


def extract_social_links_from_description(description: str) -> Dict[str, str]:
    """
    Very simple heuristic extraction for X and Instagram links from channel description.
    """
    links: Dict[str, str] = {}
    if not description:
        return links
    lower = description.lower()

    for token in ["https://x.com/", "https://twitter.com/"]:
        idx = lower.find(token)
        if idx != -1:
            end = description.find(" ", idx)
            if end == -1:
                end = len(description)
            links["x"] = description[idx:end].strip().rstrip(".,);")
            break

    for token in ["https://www.instagram.com/", "https://instagram.com/"]:
        idx = lower.find(token)
        if idx != -1:
            end = description.find(" ", idx)
            if end == -1:
                end = len(description)
            links["instagram"] = description[idx:end].strip().rstrip(".,);")
            break

    return links


# ------------- Optional RSS Author Extraction (simple) -------------

def load_feeds_config() -> Dict[str, Any]:
    if not CONFIG_FEEDS_PATH.exists():
        return {}
    with CONFIG_FEEDS_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch_rss_authors(rss_urls: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Very generic RSS author extraction.
    Returns mapping: author_name -> { 'count': int, 'sample_url': str }
    """
    authors: Dict[str, Dict[str, Any]] = {}
    for url in rss_urls:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            root = etree.fromstring(resp.content)
        except Exception:
            continue

        # Handle both RSS 2.0 (<item>) and Atom (<entry>)
        for item in root.findall(".//item") + root.findall(".//{*}entry"):
            author_name = None
            # RSS author
            author_elem = item.find("author")
            if author_elem is not None and author_elem.text:
                author_name = author_elem.text.strip()
            # Dublin Core creator
            if not author_name:
                dc_creator = item.find(".//{*}creator")
                if dc_creator is not None and dc_creator.text:
                    author_name = dc_creator.text.strip()
            # Atom author
            if not author_name:
                atom_author = item.find(".//{*}author/{*}name")
                if atom_author is not None and atom_author.text:
                    author_name = atom_author.text.strip()

            if not author_name:
                continue

            link_elem = item.find("link")
            link = None
            if link_elem is not None and link_elem.text:
                link = link_elem.text.strip()
            # Atom link with href
            if not link:
                link_elem = item.find(".//{*}link[@rel='alternate']")
                if link_elem is not None:
                    link = link_elem.get("href")

            info = authors.setdefault(
                author_name,
                {"count": 0, "sample_url": link or url},
            )
            info["count"] += 1

    return authors


# ------------- Discovery Logic -------------

def discover_youtube_influencers_for_topic(
    topic_key: str, topic_cfg: Dict[str, Any], existing_ids: Set[str]
) -> List[Influencer]:
    label = topic_cfg.get("label", topic_key)
    queries = topic_cfg.get("youtube_queries", [])
    channel_ids = youtube_search_channels_for_topic(topic_key, queries)
    if not channel_ids:
        return []

    channel_data = youtube_fetch_channel_stats(list(channel_ids))
    candidates: List[Influencer] = []

    today = iso_today()

    for cid, item in channel_data.items():
        if cid in existing_ids:
            continue

        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        subs = parse_int_or_none(stats.get("subscriberCount"))
        if subs is None:
            continue
        if subs < MIN_SUBSCRIBERS or subs > MAX_SUBSCRIBERS:
            continue

        title = snippet.get("title") or "Unknown Channel"
        description = snippet.get("description") or ""
        channel_url = f"https://www.youtube.com/channel/{cid}"

        social_links = extract_social_links_from_description(description)

        metrics = InfluencerMetrics(
            subscribers=subs,
            total_views=parse_int_or_none(stats.get("viewCount")),
            videos_last_30d=None,  # Could be computed with extra API calls
            avg_recent_views=None,
        )

        influencer = Influencer(
            id=cid,
            name=title,
            platform="youtube",
            topic_key=topic_key,
            topic_label=label,
            primary_url=channel_url,
            discovered_on=today,
            metrics=metrics,
            social_links=social_links,
            source_metadata={
                "snippet": {"description": description},
                "statistics": stats,
            },
        )

        candidates.append(influencer)

    # Score and select top N
    scored = []
    for inf in candidates:
        raw_stats = channel_data[inf.id]
        s = score_channel(raw_stats)
        scored.append((s, inf))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_influencers = [inf for _, inf in scored[:NEW_INFLUENCERS_PER_TOPIC]]
    return top_influencers


def merge_influencers(
    existing: List[Influencer], new: List[Influencer]
) -> List[Influencer]:
    by_id: Dict[str, Influencer] = {inf.id: inf for inf in existing}
    for inf in new:
        if inf.id not in by_id:
            by_id[inf.id] = inf
    # Preserve deterministic order (by discovered_on then id)
    merged = list(by_id.values())
    merged.sort(key=lambda i: (i.discovered_on, i.id))
    return merged


# ------------- Main Entrypoint -------------

def main() -> None:
    if not YOUTUBE_API_KEY:
        raise SystemExit("YOUTUBE_API_KEY (or YT_API_KEY) must be set")

    print("=== OpenSourceNews: Daily Influencer Discovery ===")
    print(f"Data directory: {DATA_DIR}")

    feeds_cfg = load_feeds_config()
    if feeds_cfg:
        print("Loaded config/feeds.yaml")
    else:
        print("No config/feeds.yaml found or empty; continuing with default topic queries.")

    for topic_key, topic_cfg in INFLUENCER_TOPICS.items():
        print(f"\n--- Topic: {topic_cfg.get('label', topic_key)} ({topic_key}) ---")

        existing_influencers = load_existing_influencers(topic_key)
        existing_ids = {inf.id for inf in existing_influencers}
        print(f"Existing influencers: {len(existing_influencers)}")

        try:
            new_influencers = discover_youtube_influencers_for_topic(
                topic_key, topic_cfg, existing_ids
            )
        except Exception as e:
            print(f"Error discovering influencers for {topic_key}: {e}")
            continue

        print(f"Discovered {len(new_influencers)} new YouTube micro-influencers")

        if not new_influencers:
            continue

        merged = merge_influencers(existing_influencers, new_influencers)
        save_influencers(topic_key, merged)
        print(f"Saved {len(merged)} total influencers for topic {topic_key}")

    print("\nDone.")


if __name__ == "__main__":
    main()
```

This script:

- Uses **YouTube search + channels.list** to find channels active in your topic in the last `SEARCH_DAYS` days. [developers.google](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits)
- Treats channels with **2k–100k subscribers** as micro‑influencers and scores them by subs+views.  
- Writes per‑topic JSON files under `data/influencers/` (`real_estate_tokenization.json`, `alternative_news.json`, etc.) that you can consume from the API or other scripts.  

***

## 4) Optional: tie feeds.yaml topics to influencer topics

If you want to align this with your existing `config/feeds.yaml`, you can augment `INFLUENCER_TOPICS` at runtime using that file (for example, to pull topic‑specific RSS lists and feed them into `fetch_rss_authors`). The scaffolding is already in place: `load_feeds_config()` and `fetch_rss_authors()`.

A simple extension would be:

- For each OpenSourceNews topic whose `topic_name` mentions “Blockchain / Crypto / Web3”, map that to `blockchain_crypto` and pass its `rss_sources` into `fetch_rss_authors`, then treat recurring authors as text‑based micro‑influencers for that topic.
