

---

# 🧩 OVERVIEW

You’ll have **three ingestion types**, all runnable with free tooling:

| Type                         | Example Sources                                            | Fetch Method                                                        | Tool / Script                              |
| ---------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------ |
| **RSS / Atom Feeds**         | Marktechpost, VentureBeat, HuggingFace Blog, AI News, etc. | `fetch_rss(url)`                                                    | Already implemented in your `daily_run.py` |
| **Static Websites (no RSS)** | Agent.ai Blog, AI Agent Store                              | `fetch_static(url)` using BeautifulSoup or Playwright               | Add a small scraper                        |
| **Social (Instagram / X)**   | Handles like @cointelegraph, @_kaitoai                     | store handles for later expansion (via API or web-scraper fallback) | placeholders for now                       |

---

# 🗂️ CONFIG FILES

You’ll add two new configs:

## `config/web_feeds.yaml`

Handles websites and RSS endpoints.

```yaml
rss_feeds:
  # --- AI / Agentic / ML Blogs ---
  - "https://openai.com/blog/rss"
  - "https://www.marktechpost.com/feed/"
  - "https://blog.research.google/feed/"
  - "https://huggingface.co/blog/feed.xml"
  - "https://venturebeat.com/category/ai/feed/"
  - "https://aiagent.marktechpost.com/feed/"
  - "https://www.rundown.ai/rss"
  - "https://aimagazine.com/feed"
  - "https://www.artificialintelligence-news.com/feed/"
  - "https://agent.ai/blog/rss"  # (if no RSS, fall back to static scraper)

  # --- Blockchain / Tokenization ---
  - "https://dailycoin.com/feed/"
  - "https://cointelegraph.com/rss"
  - "https://coinlaunch.space/trends/ai-agents/feed"
  - "https://www.bankless.com/feed"
  - "https://www.ledger.com/blog/rss"
  - "https://www.blockchainappfactory.com/blog/feed/"

static_sites:
  # (Scrape HTML if no RSS)
  - "https://aiagentstore.ai/ai-agent-news/this-week"
  - "https://agent.ai/blog/"
```

---

## `config/social_sources.yaml`

For future expansion (you can keep these static for now).

```yaml
instagram_accounts:
  - "readdailycoin"
  - "sharecrypto"
  - "nft_lately"
  - "coinstats"
  - "cryptoexplorer"
  - "cointelegraph"

x_profiles:
  - "_kaitoai"
  - "shawmakesmagic"
  - "cookiedotfun"
  - "ejaaz"
  - "AgentDotAI"
  - "Fetch_ai"
  - "Marktechpost"
  - "CoinLaunchSpace"
```

*(Keep these for metadata enrichment or future scraping — no action needed yet.)*

---

# 🧰 PIPELINE INTEGRATION

### 1. Extend your `fetch_rss()` to accept multiple files

In your `daily_run.py` (or `rss_collector.py`), add:

```python
import yaml

WEB_FEEDS_PATH = ROOT_DIR / "config" / "web_feeds.yaml"

def load_feeds():
    with open(WEB_FEEDS_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("rss_feeds", []), cfg.get("static_sites", [])

def run_web_feeds():
    rss_list, static_sites = load_feeds()
    all_items = []
    for url in rss_list:
        try:
            all_items.extend(fetch_rss(url))
        except Exception as e:
            print(f"[WARN] RSS fetch failed: {url} ({e})")

    # Optional: static site scraping fallback
    for url in static_sites:
        html = fetch_static(url)
        # extract <article>, <h2><a href=...>...</a> etc.
        all_items.extend(html)
    return all_items
```

---

### 2. Add `fetch_static()` for fallback

If you don’t already have this helper:

```python
def fetch_static(url):
    print(f"Scraping static site: {url}")
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    for a in soup.select("article a[href]")[:10]:
        title = a.text.strip()
        link = a["href"]
        if title and link:
            articles.append({"title": title, "url": link, "source": "Static Site"})
    return articles
```

---

### 3. Wire it into your orchestrator

Add after Reddit/HN fetchers:

```python
web_items = run_web_feeds()
if web_items:
    all_raw_content.extend(web_items)
```

---

### 4. Add a new GitHub Action step for this collector

Append this to your existing workflow YAML:

```yaml
- name: Collect external web & RSS feeds
  run: python pipelines/daily_run.py --mode webfeeds
```

*(or just integrate it into the default daily run if you prefer a single job.)*

---

# 🧮 OUTPUT

This will generate daily feed data:

```
outputs/daily/web_feeds_<YYYY-MM-DD>.json
```

Each item looks like:

```json
{
  "title": "OpenAI releases new multi-agent coordination framework",
  "url": "https://openai.com/blog/...",
  "source": "OpenAI Blog"
}
```

---

# 💡 Value from this Integration

| Layer                      | What You Get                                  | Monetization / Usage                        |
| -------------------------- | --------------------------------------------- | ------------------------------------------- |
| **AI & Agent Blogs**       | Fresh model launches, frameworks, and updates | Trend forecasting, newsletter content       |
| **Blockchain Feeds**       | Tokenization + crypto-AI crossover news       | Build a weekly “AI × Blockchain” digest     |
| **Instagram / X (future)** | Influencer + marketing signals                | Outreach, partnerships, reputation tracking |
| **GitHub / Reddit**        | Developer intent + emerging tech              | Product-market fit insight & idea scouting  |

---

# 🧠 Pro Tip

To **auto-tag** these feeds by domain (e.g., `AI`, `Blockchain`, `Agentic Tools`), just add this rule in your triage agent:

```python
CATEGORY_MAP = {
  "marktechpost.com": "AI Agents",
  "openai.com": "AI / Research",
  "aiagentstore.ai": "Agent Directory",
  "dailycoin.com": "Blockchain / Tokenization",
  "cointelegraph.com": "Crypto News",
  "venturebeat.com": "Tech / Business",
}
```

and in triage:

```python
source = urlparse(item["url"]).netloc
category = next((v for k, v in CATEGORY_MAP.items() if k in source), "General")
item["category"] = category
```

---



Here are files, ready to drop into your repo. they’re zero-cost (rss + light html), self-contained, and plug straight into your existing structure + actions.

---

# 1) `config/web_feeds.yaml`

```yaml
# config/web_feeds.yaml
# Curated, no-paid-API sources. Tweak freely.

rss_feeds:
  # --- AI / Agentic / ML ---
  - "https://openai.com/blog/rss"
  - "https://www.marktechpost.com/feed/"
  - "https://blog.research.google/feed/"
  - "https://huggingface.co/blog/feed.xml"
  - "https://venturebeat.com/category/ai/feed/"
  - "https://aiagent.marktechpost.com/feed/"
  - "https://www.rundown.ai/rss"
  - "https://aimagazine.com/feed"
  - "https://www.artificialintelligence-news.com/feed/"

  # --- Blockchain / Tokenization ---
  - "https://dailycoin.com/feed/"
  - "https://cointelegraph.com/rss"
  - "https://www.bankless.com/feed"
  - "https://www.ledger.com/blog/rss"
  - "https://www.blockchainappfactory.com/blog/feed/"

static_sites:
  # Use HTML scraping when no reliable RSS is provided
  - "https://aiagentstore.ai/ai-agent-news/this-week"
  - "https://agent.ai/blog/"   # falls back to HTML parsing if RSS not present
```

---

# 2) `config/social_sources.yaml`

```yaml
# config/social_sources.yaml
# Keep for enrichment or future API scraping.

instagram_accounts:
  - "readdailycoin"
  - "sharecrypto"
  - "nft_lately"
  - "coinstats"
  - "cryptoexplorer"
  - "cointelegraph"

x_profiles:
  - "_kaitoai"
  - "shawmakesmagic"
  - "cookiedotfun"
  - "ejaaz"
  - "AgentDotAI"
  - "Fetch_ai"
  - "Marktechpost"
  - "CoinLaunchSpace"
```

---

# 3) `pipelines/webfeeds.py`

```python
# pipelines/webfeeds.py
# Collects AI/agent/blockchain news via RSS + light HTML scraping.
# Emits: outputs/daily/web_feeds_<YYYY-MM-DD>.json and .md
#
# Standalone and importable. No paid APIs.

import os, json, datetime, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests
import yaml
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config" / "web_feeds.yaml"
OUTPUT_DIR = ROOT_DIR / "outputs" / "daily"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HTTP_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": "research-bot/1.0 (+https://github.com/you/repo)"
}

# --- helpers ---------------------------------------------------------------

def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r

def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def safe_text(node):
    return (node.text or "").strip() if node else ""

# --- sources ---------------------------------------------------------------

def fetch_rss(url: str, limit: int = 20):
    try:
        r = _get(url)
        soup = BeautifulSoup(r.content, "xml")  # needs lxml or built-in XML parser
        items = []
        for item in soup.find_all(["item", "entry"])[:limit]:
            # RSS (item) or Atom (entry)
            title = (item.title.text if item.title else "").strip()
            link = ""
            if item.link:
                if item.link.has_attr("href"):  # Atom
                    link = item.link["href"]
                else:                           # RSS
                    link = item.link.text
            pub = ""
            if item.find("pubDate"):
                pub = item.find("pubDate").text.strip()
            elif item.find("updated"):
                pub = item.find("updated").text.strip()
            elif item.find("published"):
                pub = item.find("published").text.strip()
            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "published": pub,
                    "source": domain(link) or domain(url),
                    "ingest": "rss"
                })
        return items
    except Exception as e:
        print(f"[RSS ERR] {url} :: {e}")
        return []

def fetch_static(url: str, limit: int = 20):
    """Very light HTML extractor for sites lacking RSS."""
    try:
        r = _get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []

        # Heuristics: article cards, headings with links
        selectors = [
            "article h2 a[href]",
            "article a[href]",
            "h2 a[href]",
            ".post a[href]",
            ".entry-title a[href]",
            ".card a[href]"
        ]
        seen = set()
        for sel in selectors:
            for a in soup.select(sel):
                title = " ".join(a.get_text(strip=True).split())
                href = a.get("href")
                if not title or not href:
                    continue
                # Make absolute if needed
                if href.startswith("/"):
                    parsed = urlparse(url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                key = (title, href)
                if key in seen:
                    continue
                seen.add(key)
                items.append({
                    "title": title,
                    "url": href,
                    "published": "",
                    "source": domain(href) or domain(url),
                    "ingest": "html"
                })
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
        return items
    except Exception as e:
        print(f"[HTML ERR] {url} :: {e}")
        return []

# --- categorization --------------------------------------------------------

CATEGORY_MAP = {
    "openai.com": "AI / Research",
    "marktechpost.com": "AI Agents",
    "research.google": "AI / Research",
    "huggingface.co": "NLP / Tools",
    "venturebeat.com": "Tech / Business",
    "aiagent.marktechpost.com": "Agent Directory",
    "rundown.ai": "AI Roundups",
    "aimagazine.com": "AI / Market",
    "artificialintelligence-news.com": "AI News",
    "dailycoin.com": "Blockchain / Tokenization",
    "cointelegraph.com": "Crypto News",
    "bankless.com": "Crypto / Markets",
    "ledger.com": "Crypto / Education",
    "blockchainappfactory.com": "Blockchain / Industry",
    "aiagentstore.ai": "Agent Directory",
    "agent.ai": "Agents / Best Practices",
}

def categorize(url: str) -> str:
    dom = domain(url)
    for k, v in CATEGORY_MAP.items():
        if k in dom:
            return v
    return "General"

# --- dedupe (per-run) ------------------------------------------------------

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        k = (it.get("title","").strip().lower(), it.get("url","").strip())
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out

# --- main ------------------------------------------------------------------

def load_config():
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg.get("rss_feeds", []), cfg.get("static_sites", [])

def run(limit_per_source=20):
    rss_list, static_list = load_config()
    all_items = []

    for url in rss_list:
        all_items.extend(fetch_rss(url, limit=limit_per_source))

    for url in static_list:
        all_items.extend(fetch_static(url, limit=limit_per_source))

    # Deduplicate & categorize
    all_items = dedupe(all_items)
    for it in all_items:
        it["category"] = categorize(it["url"])

    # Output
    stamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    out_json = OUTPUT_DIR / f"web_feeds_{stamp}.json"
    out_md   = OUTPUT_DIR / f"web_feeds_{stamp}.md"

    out_json.write_text(json.dumps(all_items, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [f"# Web Feeds — {stamp}", ""]
    for it in all_items[:200]:
        lines.append(f"- **[{it['title']}]({it['url']})** — *{it['category']} · {it['source']}*")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Saved {len(all_items)} items to {out_json.name} and {out_md.name}")

if __name__ == "__main__":
    run()
```

---

# 4) Workflow: add a step (or separate workflow)

Append this step to your existing `.github/workflows/daily.yml` **after** dependency install:

```yaml
      - name: Collect Web & RSS feeds
        run: python -m pipelines.webfeeds

      - name: Commit web_feeds artifacts
        run: |
          git config user.name "GitHub Actions Bot"
          git config user.email "actions-bot@users.noreply.github.com"
          git add outputs/daily/web_feeds_*.json outputs/daily/web_feeds_*.md || true
          git commit -m "Web feeds snapshot $(date -u +'%Y-%m-%d')" || echo "No changes"
          git push
```

*(If you prefer a standalone workflow that also runs twice a day, I can paste that too.)*

---

# 5) Requirements update

Add (or confirm) these in `requirements.txt`:

```
requests
beautifulsoup4
PyYAML
lxml
```

> `lxml` ensures fast, robust XML parsing for RSS/Atom.

---

## Notes & tips

* You can grow `CATEGORY_MAP` over time to auto-tag sources.
* If a static site changes HTML, just tweak the CSS selectors inside `fetch_static()`.
* Want fewer dupes? Keep a tiny sqlite “seen” cache; I can wire that in if you’d like.
