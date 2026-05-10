## TLDR

This repo is already more than a simple news scraper. It is a **news intelligence pipeline + API + frontend dashboard + optional knowledge base sync layer**.

It currently:

1. Pulls signals from RSS, Hacker News, GitHub Trending, YouTube metadata, and configured feeds.
2. Uses an LLM layer for triage, categorization, summaries, research planning, transcript analysis, and scripts.
3. Writes daily JSON reports into `outputs/daily`.
4. Exposes those reports through Flask API endpoints.
5. Builds a normalized knowledge base in JSON/JSONL.
6. Can optionally sync that corpus into Qdrant.
7. Can optionally push the daily digest into another backend via outbound POST.

The easiest way for you to “tap into the news” is through the API endpoint:

```bash
curl https://YOUR_API_DOMAIN/api/reports/latest
```

Or, better for another app/agent/backend:

```bash
curl https://YOUR_API_DOMAIN/api/reports/latest/normalized
```

The normalized endpoint is the one I would use for AlltheAI, BlockCities, Agency, OpenClaw, or any agent memory system because it gives you stable fields, deterministic IDs, counts, topics, source URLs, and metadata. ([GitHub][1])

---

## What the repo is architecturally

The repo is organized around a clean pipeline pattern:

**Ingestion → triage → report generation → script generation → knowledge base → API/frontend access.**

The README says the system collects from RSS, Hacker News, GitHub Trending, and YouTube metadata; uses configurable LLMs including Ollama, OpenRouter, Gemini, or rotating OpenRouter/Ollama; writes daily reports; generates scripts; builds a knowledge base; optionally syncs Qdrant; and runs scheduled automation through GitHub Actions. ([GitHub][2])

Core files:

| Area              | File                                       | Purpose                                                           |
| ----------------- | ------------------------------------------ | ----------------------------------------------------------------- |
| Main ingestion    | `pipelines/daily_run.py`                   | Fetches configured sources and writes daily reports               |
| Script generation | `pipelines/generate_video_script.py`       | Creates scripts from latest report                                |
| Weekly analysis   | `pipelines/weekly_analyzer.py`             | Weekly summary/script generation                                  |
| API               | `api/script_generator.py`                  | Flask API for reports, config, research, transcripts, and scripts |
| Feed config       | `config/feeds.yaml`                        | Source/topic definitions                                          |
| Knowledge base    | `scripts/build_knowledge_base.py`          | Aggregates generated outputs                                      |
| Qdrant sync       | `scripts/sync_knowledge_base_to_qdrant.py` | Pushes normalized corpus into vector search                       |
| Frontend          | `App.tsx`, `components/*`                  | Vite/React dashboard                                              |

The public `outputs/daily` folder already contains many generated JSON reports, including reports through `2026-05-09.json`, which means the repo is not just a code template; it is storing an active archive of generated news outputs. ([GitHub][3])

---

## How to tap into the news it aggregates

### Option 1: API pull — best for dashboards and agents

Run the API:

```bash
python3 api/script_generator.py
```

Then call:

```bash
curl http://localhost:5000/api/reports/latest
```

That returns:

```json
{
  "date": "2026-05-09",
  "report": {
    "Topic Name": [
      {
        "title": "...",
        "url": "...",
        "source": "RSS",
        "category": "...",
        "summary": "..."
      }
    ]
  }
}
```

The repo exposes `GET /api/reports/latest`, `GET /api/reports`, `GET /api/reports/by-date/{YYYY-MM-DD}`, and `GET /api/reports/latest/normalized`. ([GitHub][1])

For your systems, I would mostly use:

```bash
curl http://localhost:5000/api/reports/latest/normalized
```

That gives you a stable schema with:

```json
{
  "report_date": "2026-05-09",
  "items": [],
  "sources": [],
  "counts": {},
  "digest": "..."
}
```

Each item includes fields like `signal_id`, `title`, `summary`, `source_urls`, `topics`, `source`, `category`, `bucket`, `content_type`, `quality_score`, `claims`, `entities`, `key_lessons`, `actionable_steps`, and transcript metadata when available. ([GitHub][1])

### Option 2: Direct file pull from GitHub

Because daily reports are committed into `outputs/daily`, you can directly fetch a specific date’s JSON from GitHub raw content:

```bash
curl https://raw.githubusercontent.com/MyBlockcities/OpenSourceNews/main/outputs/daily/2026-05-09.json
```

This is the fastest zero-backend integration. The downside is that you have to know the date or use the GitHub file listing/manifest to discover the latest report.

### Option 3: Outbound push into your own system

This is probably the most powerful option for your broader agent architecture.

The repo supports an outbound daily digest POST after `daily_run.py` finishes. You configure:

```bash
AGENCY_INGEST_URL=https://your-backend.com/api/news/ingest
AGENCY_INGEST_BEARER_TOKEN=your-secret
```

Then the pipeline sends a JSON payload with:

```json
{
  "schema": "open_source_news_daily_digest.v1",
  "generated_at": "...",
  "report_date": "...",
  "report": {},
  "markdown": "...",
  "meta": {
    "source": "open_source_news",
    "pipeline": "pipelines/daily_run.py"
  }
}
```

The repo’s `services/external_ingest.py` handles this push and logs failures without breaking the daily run. ([GitHub][4])

This is the version I would wire into **AlltheAI / BlockCities / Agency**:

```txt
OpenSourceNews daily_run.py
        ↓
AGENCY_INGEST_URL
        ↓
Your Django/FastAPI ingest endpoint
        ↓
Normalize + tag + dedupe
        ↓
Postgres + Qdrant
        ↓
Agent memory / content engine / dashboards
```

### Option 4: Qdrant/vector search layer

The repo already has a knowledge base build step and Qdrant sync path. The README says the KB builder writes `outputs/knowledge_base/knowledge_base.json` and `knowledge_base.jsonl`; the Qdrant sync embeds records and upserts them into a Qdrant collection. ([GitHub][2])

That means you can turn the news into a queryable intelligence layer:

```txt
“What happened this week in AI agents?”
“What open-source repos are trending?”
“What should I build based on the last 30 days of signals?”
“What funding/partnership/product-release patterns are emerging?”
```

---

## Biggest improvement opportunities

### 1. Separate “news archive” from repo commits

Right now, the generated daily outputs are committed back into GitHub Actions. The workflow commits `outputs/daily/*.json` and `outputs/transcripts/*.json` after each run. ([GitHub][5])

That is convenient, but long-term it will bloat the repo and mix source code with production data.

Better:

```txt
GitHub repo = code
S3/R2/Supabase Storage = daily JSON + markdown archives
Postgres = normalized metadata
Qdrant = semantic retrieval
```

Keep maybe the latest 7–14 reports in the repo for demo purposes, but move the real archive to storage.

### 2. Add a real `/api/search` over reports

The repo exposes latest, by-date, list, and normalized endpoints. That is good. But the missing killer endpoint is:

```http
GET /api/news/search?q=agent frameworks&topic=AI&days=30
```

Return ranked items across all reports.

Implementation path:

```python
@app.get("/api/news/search")
def search_news():
    q = request.args.get("q", "").lower()
    days = int(request.args.get("days", 30))
    # load recent output files
    # flatten items
    # keyword filter first
    # optional vector search if Qdrant enabled
```

This would turn the system from a daily report viewer into a reusable intelligence API.

### 3. Add source reliability scoring

Right now, the schema has `source`, `category`, `quality_score`, `classification_confidence`, and optional claim fields. ([GitHub][1])

I would add:

```json
{
  "source_reputation": "high | medium | low | unknown",
  "source_type": "primary | trade_press | social | aggregator | opinion",
  "verification_status": "unverified | single_source | multi_source | primary_confirmed",
  "duplicate_cluster_id": "...",
  "first_seen_at": "...",
  "last_seen_at": "..."
}
```

This matters because for news intelligence, the big problem is not collection. It is **trust, de-duplication, and ranking**.

### 4. Improve dedupe from URL-only to semantic/event clustering

The pipeline dedupes by URL in `daily_run.py`, which is useful but not enough. ([GitHub][6])

Many sources cover the same story with different URLs. Add clustering by:

```txt
normalized title
canonical domain
named entities
event date
embedding similarity
```

A better output would be:

```json
{
  "cluster_id": "openai-agent-sdk-update-2026-05-09",
  "canonical_title": "OpenAI updates Agents SDK",
  "items": [
    {"source": "Official Blog", "url": "..."},
    {"source": "Hacker News", "url": "..."},
    {"source": "YouTube", "url": "..."}
  ],
  "confidence": 0.92
}
```

### 5. Make the frontend consume the API dynamically

The README still notes that the `DailyFeedViewer` has had limitations around loading a fixed set of known report dates instead of auto-indexing all generated reports. ([GitHub][2])

The API already has:

```http
GET /api/reports?limit=90
```

So the frontend should always load report metadata from that endpoint, not from hardcoded date assumptions.

### 6. Harden auth before exposing this publicly

The repo supports `OPEN_SOURCE_NEWS_API_KEY`; when set, all endpoints except `/api/health` require a Bearer token. ([GitHub][7])

That is good, but for production I would add:

```txt
- rate limiting
- CORS allowlist instead of open CORS
- separate read token vs write/admin token
- protect PUT /api/config/feeds behind admin-only auth
- do not expose VITE_API_BEARER_TOKEN in a public browser bundle
```

The repo’s `apiClient.ts` even warns that Vite bearer tokens are visible in the browser bundle and recommends a server-side proxy for production. ([GitHub][8])

### 7. Add a proper ingestion receiver template

Since the outbound push is one of the best features, I would add a ready-to-copy receiver:

```python
@app.post("/api/news/ingest")
def ingest_news():
    verify_bearer()
    validate_schema("open_source_news_daily_digest.v1")
    store_raw_payload()
    normalize_items()
    upsert_by_signal_id()
    enqueue_embedding_jobs()
    return {"ok": True}
```

This would make it plug-and-play with AlltheAI, Django, Supabase, FastAPI, or n8n.

### 8. Add “watchlists” and “mission briefs”

Right now the repo is topic/feed driven. I would add a higher-value layer:

```yaml
watchlists:
  - name: "AI Agent Infrastructure"
    entities:
      - OpenAI Agents SDK
      - Claude Code
      - LangGraph
      - CrewAI
      - MCP
      - OpenRouter
    alert_rules:
      - "new release"
      - "funding"
      - "security issue"
      - "repo trending"
```

Then output:

```txt
Daily Mission Brief:
- What changed?
- Why it matters
- Who should care
- What action should Brian take?
- Build idea / content idea / investment angle
```

This fits your style much more than generic news aggregation.

---

## How I would wire this into your ecosystem

For your use case, I would treat this repo as a **sidecar intelligence service**.

```txt
OpenSourceNews
  - Collects raw signals
  - Summarizes and classifies
  - Outputs daily/normalized JSON
  - Pushes digest to your backend

AlltheAI / BlockCities / Agency
  - Receives digest
  - Stores normalized records
  - Adds project/persona/entity tags
  - Runs deeper agents
  - Turns signals into briefs, scripts, product ideas, alerts, dashboards
```

The integration path I’d choose:

1. Deploy the API separately from the frontend, as the README recommends for two Railway services. ([GitHub][2])
2. Set `OPEN_SOURCE_NEWS_API_KEY`.
3. Add a receiver endpoint in your main backend.
4. Set `AGENCY_INGEST_URL` in the news repo.
5. Store each item by `signal_id`.
6. Add project/entity tagging.
7. Sync important items into Qdrant.
8. Let your agents query the normalized corpus.

---

## The best “tap into the news” implementation

Use both **pull** and **push**:

### Pull for dashboards

```ts
const res = await fetch(`${API_BASE}/api/reports/latest/normalized`, {
  headers: {
    Authorization: `Bearer ${OPEN_SOURCE_NEWS_API_KEY}`,
  },
});

const data = await res.json();
```

### Push for automation

```env
AGENCY_INGEST_URL=https://your-backend.com/api/intel/opensourcenews/ingest
AGENCY_INGEST_BEARER_TOKEN=super-secret-token
EXTERNAL_INGEST_INCLUDE_MARKDOWN=1
```

Then every daily run sends the digest directly into your system. ([GitHub][4])

---

## My recommended next upgrade sequence

**Phase 1 — Make it reliable**

* Move generated archives out of git into object storage.
* Add `/api/news/search`.
* Add admin/read token separation.
* Make frontend dynamically load report dates.
* Add a proper receiver template.

**Phase 2 — Make it intelligent**

* Add entity extraction.
* Add duplicate/event clustering.
* Add source reliability and verification status.
* Add watchlists.
* Add “why this matters” scoring.

**Phase 3 — Make it agent-native**

* Add webhook dispatch per topic.
* Add MCP server wrapper.
* Add Qdrant-powered semantic search endpoint.
* Add daily “mission briefs” per persona/project.
* Add one-click “turn this into script / post / build idea / client opportunity.”

The core is solid. The biggest leap is turning it from a **news aggregation app** into a **signal intelligence sidecar** that feeds your agents, dashboards, content systems, and business-development workflows.



An MCP server **can help you create a continuous, mostly-free news stream**, but MCP is not the thing that “runs continuously” by itself.

The clean way to think about it:

```txt
News collectors / cron jobs / RSS polling
        ↓
Database or JSON archive
        ↓
MCP server exposes tools + resources
        ↓
Claude / Cursor / OpenAI / your agents query and act on it
```

MCP is the **interface layer**. It lets agents ask questions like:

```txt
get_latest_news(topic="AI agents")
search_news(query="MCP security", days=14)
get_trending_repos(category="developer tools")
summarize_signal(signal_id="...")
create_brief_for_persona(persona="Brian / AlltheAI")
```

But MCP does **not** replace the crawler, scheduler, database, or news source APIs.

## What MCP gives you

MCP standardizes how an AI client connects to your tools and context. The official MCP spec defines servers exposing things like tools and resources, with transports including `stdio` and Streamable HTTP. Resources are meant to expose contextual data such as files, schemas, or app-specific information to models. ([Model Context Protocol][1])

For your OpenSourceNews repo, an MCP server would be excellent because it could expose the repo’s news archive as agent tools:

```ts
tools = [
  "get_latest_digest",
  "search_news",
  "get_news_by_date",
  "get_topic_feed",
  "get_source_links",
  "generate_daily_brief",
  "find_build_opportunities",
  "find_content_angles",
  "send_signal_to_alltheai"
]
```

So instead of your agents manually reading JSON files or hitting Flask endpoints, they call a standardized tool.

## What MCP does not give you

MCP does **not** automatically make the stream free, live, or persistent.

You still need:

```txt
1. Sources: RSS, HN, GitHub Trending, YouTube, APIs, webpages
2. Scheduler: GitHub Actions, Cloudflare Cron, Supabase Cron, local cron, etc.
3. Storage: JSON files, SQLite, Postgres, Supabase, R2/S3, Qdrant
4. Processing: dedupe, summarize, classify, embed, score
5. Interface: MCP server, REST API, dashboard, webhook
```

MCP is best used as the **agent access port** into the system.

## Can it be free?

Yes, mostly — depending on how “continuous” you mean.

There are three levels:

### 1. Free-ish daily or hourly stream

This is very doable.

Use:

```txt
GitHub Actions cron
+ RSS feeds
+ HN API
+ GitHub Trending scraping or API alternatives
+ local/Ollama or free-tier LLMs
+ JSON files or SQLite
+ MCP server
```

This costs little to nothing if volume is modest. GitHub Actions, Cloudflare Workers, Supabase, and similar tools all have free-tier paths, though each has usage limits. Cloudflare Workers Free includes 100,000 requests per day, for example. ([Cloudflare Docs][2])

### 2. Near-real-time stream every 5–15 minutes

Still possible mostly free, but you need to be more careful.

Architecture:

```txt
Cloudflare Worker Cron / GitHub Action
        ↓ every 5–15 minutes
Fetch RSS + APIs
        ↓
Deduplicate by URL/title/hash
        ↓
Store new items only
        ↓
MCP exposes latest stream
```

This can remain free if you avoid expensive full-page scraping and avoid LLM-summarizing every item. Instead, summarize only high-value items.

### 3. True continuous firehose

This gets harder to keep free.

A true live stream means:

```txt
constant polling
websocket updates
many sources
deduplication
embedding
LLM summarization
historical search
alerts
```

That becomes compute/storage/API heavy. Free tiers may still support a prototype, but not a serious production firehose.

## Best architecture for your repo

I would not replace your existing Flask API. I would add MCP beside it.

```txt
OpenSourceNews Repo
├── pipelines/daily_run.py
├── outputs/daily/*.json
├── api/script_generator.py      ← REST API
└── mcp/news_server.py           ← Agent tool interface
```

The MCP server would read from the same normalized report files or call your existing API internally.

Best version:

```txt
Collectors write to storage
REST API serves dashboards
MCP server serves agents
Webhook pushes to AlltheAI / BlockCities / Agency
Qdrant enables semantic search
```

So you get all three:

```txt
Human dashboard → REST API
Agent access → MCP
Automation → webhook
```

## Pros of using MCP for the news stream

**1. Agent-native access**
Your agents can call `search_news`, `get_latest_digest`, or `generate_brief` directly instead of scraping files or guessing API paths.

**2. Reusable across clients**
Cursor, Claude Desktop, Claude Code, custom agent harnesses, LangChain, OpenAI-compatible systems, and your own dashboards can connect through a standard pattern.

**3. Clean separation**
The collector gathers news. The MCP server exposes capabilities. Your agents reason over the results.

**4. Works well with your sidecar harness idea**
This becomes a perfect “news intelligence sidecar” that any of your apps can plug into.

**5. Good for persona-specific intelligence**
You can add tools like:

```txt
get_news_for_persona("real estate tokenization strategist")
get_news_for_persona("AI automation agency operator")
get_news_for_persona("health/wellness peptide brand")
```

That is much more valuable than generic news.

## Cons / risks

**1. MCP does not solve scheduling**
You still need cron jobs or always-on infrastructure.

**2. MCP does not solve storage**
You still need JSON, SQLite, Postgres, Supabase, R2, or Qdrant.

**3. MCP can become a security risk**
An MCP server can expose powerful tools. If you let it fetch arbitrary URLs, run shell commands, edit files, or call private APIs, you need strict allowlists and auth. This is especially important with `stdio`-based local servers, because MCP tooling often bridges model output into real tool execution.

**4. Free tiers are not infinite**
The free architecture works best when it is pull-based, scheduled, deduped, and selective. It breaks down if you try to summarize hundreds or thousands of articles with paid LLM calls every hour.

**5. News scraping can be legally and technically messy**
RSS and public APIs are safer. Full webpage scraping triggers rate limits, copyright issues, bot detection, and inconsistent extraction.

## My recommended free/cheap setup

Use this:

```txt
1. GitHub Actions or Cloudflare Cron
   Runs every 1–6 hours

2. Collectors
   RSS, Hacker News, GitHub Trending, YouTube metadata, selected APIs

3. Storage
   SQLite or Supabase Postgres
   plus JSON archive for portability

4. Dedupe layer
   URL hash + normalized title + source domain

5. Selective LLM processing
   Only summarize top-ranked items

6. MCP server
   Exposes query/search/brief tools

7. Optional Qdrant
   Semantic memory for “what has been happening lately?”
```

Cloudflare Workers are attractive for cheap scheduled fetching because the Free plan includes 100,000 requests per day, while Supabase Cron can schedule recurring jobs from Postgres and trigger functions/webhooks. ([Cloudflare Docs][2])

## The best practical design

I would build the MCP server with these tools first:

```ts
get_latest_report()
search_reports(query, days, topic)
get_topic_digest(topic, days)
get_signal(signal_id)
get_sources_for_signal(signal_id)
create_persona_brief(persona, topic, days)
get_trending_repos(days)
get_actionable_opportunities(topic)
```

Then add resources like:

```txt
news://latest
news://daily/2026-05-09
news://topic/ai-agents
news://topic/real-estate-tokenization
news://watchlist/mcp
news://watchlist/open-source-ai
```

That gives agents a clean, readable information surface.

## My honest answer

An MCP server is absolutely worth adding, but it should be the **agent-facing layer**, not the whole news system.

The cheapest durable architecture is:

```txt
Scheduled free collectors
→ normalized local/Supabase storage
→ REST API for apps
→ MCP server for agents
→ Qdrant only for higher-value semantic search
```

For your world, I’d call this:

```txt
OpenSourceNews Intelligence Sidecar
```

It would let every system you’re building — AlltheAI, AgentOS, BlockCities, XO Pure, scholarship agents, real estate agents — ask:

```txt
“What changed today that matters to this project?”
```
