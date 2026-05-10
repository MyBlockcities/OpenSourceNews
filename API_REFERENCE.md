# OpenSourceNews API Reference

**Base URL:** `http://localhost:5000` (local) or your Railway/deployed URL
**Start command:** `python3 api/script_generator.py`

---

## Authentication

`GET /api/health` never requires authentication.

Read-only `GET` endpoints are public unless `OPEN_SOURCE_NEWS_API_KEY` is set. When it is set, read endpoints require a Bearer token matching either `OPEN_SOURCE_NEWS_API_KEY` or `OPEN_SOURCE_NEWS_ADMIN_KEY`.

POST/PUT/PATCH/DELETE endpoints are admin routes. In production, set `OPEN_SOURCE_NEWS_ADMIN_KEY`; if it is not set, the server falls back to `OPEN_SOURCE_NEWS_API_KEY` for backward compatibility. These routes can edit config or spend LLM/transcript quota and should not be exposed without an admin key.

```
Authorization: Bearer <your-api-key>
```

If neither API key is set, read-only routes remain public and admin routes return `401`.

**Error responses:**

| Status | Body | Meaning |
|--------|------|---------|
| 401 | `{"error": "Missing or invalid Authorization header"}` | No `Authorization: Bearer ...` header sent |
| 401 | `{"error": "Invalid API key"}` | Token does not match the configured key |
| 403 | `{"error": "Admin API key required"}` | Token is valid for reads but not admin routes |

---

## Feed Endpoints

These endpoints serve daily report data for the frontend and external consumers.

### GET /api/health

Health check. **No authentication required.**

**Response:**
```json
{
  "status": "ok",
  "service": "OpenSourceNews API",
  "latest_report_date": "2026-04-04"
}
```

`latest_report_date` is `null` if no reports exist yet.

---

### GET /api/reports/latest

Returns the most recent daily report as raw JSON.

**Response:**
```json
{
  "date": "2026-04-04",
  "report": {
    "AI / AI Tools / AI Agents": [
      {
        "title": "New LLM Framework Released",
        "url": "https://example.com/article",
        "source": "RSS",
        "category": "New Framework Release",
        "summary": "A new framework for building AI agents...",
        "bucket": "ai",
        "content_type": "product_release",
        "processing_mode": "standard_summary",
        "classification_confidence": 0.85
      }
    ],
    "Blockchain / Crypto / Web3": [...],
    "General News & Research": [...],
    "Sense-Making & Narrative Analysis": [...]
  }
}
```

**Errors:**

| Status | Meaning |
|--------|---------|
| 404 | No reports exist |

---

### GET /api/reports

Returns metadata for recent reports. Does not include full item data.

**Query parameters:**

| Param | Type | Default | Max | Description |
|-------|------|---------|-----|-------------|
| `limit` | int | 7 | 90 | Number of recent reports to return |

**Example:** `GET /api/reports?limit=14`

**Response:**
```json
{
  "reports": [
    {
      "date": "2026-04-04",
      "topics": ["AI / AI Tools / AI Agents", "Blockchain / Crypto / Web3", ...],
      "item_count": 87
    },
    {
      "date": "2026-04-03",
      "topics": [...],
      "item_count": 62
    }
  ]
}
```

Reports are sorted most recent first.

---

### GET /api/reports/by-date/{YYYY-MM-DD}

Returns a specific day's full report.

**Example:** `GET /api/reports/by-date/2026-04-04`

**Response:**
```json
{
  "date": "2026-04-04",
  "report": {
    "AI / AI Tools / AI Agents": [...],
    "Blockchain / Crypto / Web3": [...]
  }
}
```

**Errors:**

| Status | Meaning |
|--------|---------|
| 404 | No report for that date |

---

### GET /api/reports/latest/normalized

Returns the latest report transformed into a **stable normalized schema** designed for external consumers (e.g., Agency by Blockcities). Every item gets a deterministic `signal_id` (SHA-256 of `url` + newline + `title`, first 16 hex chars) for item-level deduplication and a deterministic `cluster_id` (SHA-256 of bucket + normalized title, first 16 hex chars) for story-level grouping.

**Top-level keys (always present):** `report_date`, `items`, `sources`, `counts`, `digest`.

**`counts`** includes `total`, `by_topic`, `by_source`, `by_bucket` (slug bucket ids such as `ai`, `general`, `blockchain`, `sense_making`, `alternative_news`, `unknown`), and `by_cluster`.

**Each item** includes these keys (use `null` or empty string/array where data is missing — field names are stable):

| Field | Type | Notes |
|-------|------|--------|
| `source_system` | string | Always `OpenSourceNews` |
| `signal_id` | string | Deterministic id |
| `cluster_id` | string | Deterministic story-level id |
| `title`, `summary` | string | |
| `source_urls` | string[] | Usually one URL |
| `topics` | string[] | Topic bucket name(s) |
| `source`, `category` | string | |
| `content_type`, `bucket`, `processing_mode` | string | `bucket`: `general` \| `ai` \| `blockchain` \| `sense_making` \| `alternative_news`; `processing_mode`: `standard_summary` \| `wisdom_extraction` \| `claim_mapping` |
| `mode`, `stance`, `affiliation`, `risk_level`, `verification_mode`, `content_warning` | string | Populated for `alternative_news` so downstream systems can keep commentary/opinion-heavy sources separate |
| `classification_confidence` | number \| null | |
| `quality_score` | number \| null | |
| `has_transcript` | boolean | |
| `transcript_metadata` | object | `word_count`, `mode`, `source`, `used_in_prompt` (may be null) |
| `key_lessons`, `actionable_steps`, `tools_mentioned`, `frameworks_mentioned` | string[] | Wisdom mode |
| `claims` | object[] | Claim mapping mode |
| `entities`, `uncertainty_markers` | string[] | |
| `neutral_synthesis`, `implementation_notes`, `difficulty` | string | |
| `main_topic`, `key_insights`, `target_audience`, `unique_value` | | Often from transcript-backed analysis |
| `transcript_error` | string \| null | |

**Example (abbreviated):**
```json
{
  "report_date": "2026-04-04",
  "items": [
    {
      "source_system": "OpenSourceNews",
      "signal_id": "a1b2c3d4e5f67890",
      "cluster_id": "b2c3d4e5f67890a1",
      "title": "New LLM Framework Released",
      "summary": "A new framework for building AI agents...",
      "source_urls": ["https://example.com/article"],
      "topics": ["AI / AI Tools / AI Agents"],
      "source": "RSS",
      "category": "New Framework Release",
      "content_type": "product_release",
      "bucket": "ai",
      "processing_mode": "standard_summary",
      "mode": "",
      "stance": "",
      "affiliation": "",
      "risk_level": "",
      "verification_mode": "",
      "content_warning": "",
      "classification_confidence": 0.85,
      "quality_score": null,
      "has_transcript": false,
      "transcript_metadata": {
        "word_count": null,
        "mode": null,
        "source": null,
        "used_in_prompt": null
      },
      "key_lessons": [],
      "actionable_steps": [],
      "tools_mentioned": [],
      "frameworks_mentioned": [],
      "claims": [],
      "entities": [],
      "uncertainty_markers": [],
      "neutral_synthesis": "",
      "implementation_notes": "",
      "difficulty": "",
      "main_topic": "",
      "key_insights": [],
      "target_audience": "",
      "unique_value": "",
      "transcript_error": null
    }
  ],
  "sources": ["GitHub Trending", "Hacker News", "RSS", "YouTube"],
  "counts": {
    "total": 100,
    "by_topic": {
      "AI / AI Tools / AI Agents": 35,
      "Blockchain / Crypto / Web3": 22,
      "General News & Research": 20,
      "Sense-Making & Narrative Analysis": 10,
      "Alternative News & Independent Commentary": 13
    },
    "by_source": {
      "RSS": 40,
      "YouTube": 38,
      "Hacker News": 15,
      "GitHub Trending": 7
    },
    "by_bucket": {
      "ai": 35,
      "blockchain": 22,
      "general": 20,
      "sense_making": 10,
      "alternative_news": 13
    },
    "by_cluster": {
      "b2c3d4e5f67890a1": 2
    }
  },
  "digest": "100 items across 5 topics from 4 source types."
}
```

---

### GET /api/news/search

Search recent generated reports with a lightweight keyword ranker. This does not require Qdrant or an LLM.

**Query parameters:**

| Param | Type | Default | Max | Description |
|-------|------|---------|-----|-------------|
| `q` | string | | | Keyword query. Optional when `topic`, `source`, or `bucket` is provided |
| `days` | int | 30 | 365 | Search reports dated within this many days |
| `limit` | int | 25 | 100 | Maximum result count |
| `topic` | string | | | Optional topic-name substring filter |
| `source` | string | | | Optional source substring filter, e.g. `RSS` |
| `bucket` | string | | | Optional exact bucket filter, e.g. `ai` or `alternative_news` |

At least one of `q`, `topic`, `source`, or `bucket` is required.

**Example:** `GET /api/news/search?q=agent%20framework&days=30&bucket=ai`
**Filter-only example:** `GET /api/news/search?topic=AI&bucket=ai&days=30`
**Alternative bucket example:** `GET /api/news/search?bucket=alternative_news&days=30`

**Response:**
```json
{
  "query": "agent framework",
  "days": 30,
  "limit": 25,
  "count": 2,
  "total_matches": 2,
  "items": [
    {
      "source_system": "OpenSourceNews",
      "signal_id": "a1b2c3d4e5f67890",
      "cluster_id": "b2c3d4e5f67890a1",
      "report_date": "2026-04-04",
      "score": 23,
      "title": "New Agent Framework Released",
      "summary": "A new framework for building AI agents...",
      "source_urls": ["https://example.com/article"],
      "topics": ["AI / AI Tools / AI Agents"],
      "source": "RSS",
      "bucket": "ai"
    }
  ]
}
```

For compatibility with earlier consumers, the response includes both `items` and `results` with the same list.

---

### GET /api/watchlists

Returns configured strategic watchlists from `config/watchlists.yaml`.

**Response:**
```json
{
  "watchlists": [
    {
      "name": "ai_agent_infra",
      "persona": "AI automation agency operator",
      "entities": ["OpenAI Agents SDK", "Claude Code", "MCP"],
      "topics": ["AI", "agents"],
      "alert_rules": ["new_release", "funding", "security_issue", "repo_trending"]
    }
  ]
}
```

---

### GET /api/briefs/{watchlist}/latest

Returns the latest generated mission brief for a watchlist. Watchlist names are slug-normalized, so `ai_agent_infra` maps to `outputs/briefs/ai_agent_infra/*.json`.

**Errors:**

| Status | Meaning |
|--------|---------|
| 404 | No generated brief exists for that watchlist |

---

### GET /api/briefs/{watchlist}/by-date/{YYYY-MM-DD}

Returns one generated mission brief for a watchlist and date.

**Errors:**

| Status | Meaning |
|--------|---------|
| 404 | No generated brief exists for that watchlist/date |

---

## MCP Server

OpenSourceNews also includes a local stdio MCP server for agent clients:

```bash
python3 -m mcp.server
```

Tools exposed:

- `get_latest_report`
- `get_latest_normalized_report`
- `search_news`
- `get_report_by_date`
- `get_signal`
- `get_topic_digest`
- `get_manifest`
- `get_latest_brief`

Resources exposed:

- `news://latest`
- `news://latest/normalized`
- `news://manifest/latest`

---

### GET /api/manifest/latest

Returns a small **integration manifest**: merges `outputs/manifests/latest.json` (when present) with live filesystem metadata such as `knowledge_base_last_built` from `outputs/knowledge_base/knowledge_base.json` mtime.

**Authentication:** Same as other non-health routes (Bearer when `OPEN_SOURCE_NEWS_API_KEY` is set).

---

## Research Endpoints

These endpoints power the "Research" tab in the frontend. LLM-powered steps use the backend configured in `pipelines/llm_provider.py` (`LLM_PROVIDER`: Ollama, OpenRouter, Gemini, or `rotating`). Web search uses DuckDuckGo.

**Requires:** A working LLM configuration (see [Environment Variables](#environment-variables) — not necessarily `GEMINI_API_KEY` if you use OpenRouter or local Ollama).

### POST /api/research/plan

Generate a research plan from a user objective.

**Request:**
```json
{
  "objective": "What are the latest developments in AI agent frameworks?"
}
```

**Response:**
```json
{
  "planRationale": "Focus on recent releases and comparisons...",
  "queries": [
    "latest AI agent frameworks 2026",
    "LangChain vs CrewAI comparison",
    "autonomous AI agents new releases"
  ],
  "claimsToVerify": [
    "CrewAI has surpassed LangChain in adoption",
    "OpenAI released a new agent SDK"
  ]
}
```

**Errors:**

| Status | Body | Meaning |
|--------|------|---------|
| 400 | `{"error": "No objective provided"}` | Missing or empty `objective` |
| 500 | `{"error": "LLM not available. ..."}` | No usable LLM (configure `LLM_PROVIDER` and keys — see `.env.example`) |

---

### POST /api/research/search

Run web search queries via DuckDuckGo. Returns deduplicated results.

**Request:**
```json
{
  "queries": [
    "latest AI agent frameworks 2026",
    "LangChain vs CrewAI comparison"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "title": "Top AI Agent Frameworks in 2026",
      "url": "https://example.com/top-frameworks",
      "snippet": ""
    }
  ]
}
```

Returns up to 10 deduplicated results across all queries (5 per query max).

---

### POST /api/research/synthesize

Synthesize search results into a markdown research brief.

**Request:**
```json
{
  "objective": "What are the latest developments in AI agent frameworks?",
  "searchResults": [
    {
      "title": "Top AI Agent Frameworks",
      "url": "https://example.com/top-frameworks",
      "snippet": "A comparison of the leading frameworks..."
    }
  ]
}
```

**Response:**
```json
{
  "summary": "## AI Agent Frameworks in 2026\n\nThe landscape has shifted...",
  "sources": [
    {
      "title": "Top AI Agent Frameworks",
      "url": "https://example.com/top-frameworks"
    }
  ]
}
```

---

### POST /api/research/pathfinder

Generate follow-up research suggestions based on completed research.

**Request:**
```json
{
  "objective": "What are the latest developments in AI agent frameworks?",
  "reportSummary": "The research found that CrewAI and LangGraph are leading..."
}
```

**Response:**
```json
{
  "suggestions": [
    "Compare CrewAI performance benchmarks against LangGraph",
    "Investigate enterprise adoption patterns for AI agent frameworks",
    "Research the role of tool-use in modern agent architectures"
  ]
}
```

---

## Generation Endpoints

### POST /api/generate-script

Generate a video script from selected daily feed items using the configured LLM backend.

**Request:**
```json
{
  "items": [
    {
      "title": "New LLM Framework Released",
      "url": "https://example.com/article",
      "source": "RSS",
      "category": "New Framework Release",
      "summary": "A new framework..."
    }
  ],
  "topic": "AI / AI Tools / AI Agents"
}
```

**Response:**
```json
{
  "script": "Welcome back to Open Source News. Today we're covering...",
  "sources": [...],
  "metadata": {
    "num_sources": 5,
    "avg_quality_score": 7.2,
    "generated_at": "2026-04-04T12:00:00Z"
  }
}
```

---

### POST /api/generate-audio

Generate audio from a script. **Currently a placeholder** — returns a "coming soon" message.

**Request:**
```json
{
  "script": "Welcome back to Open Source News...",
  "date": "2026-04-04"
}
```

**Response:**
```json
{
  "message": "Audio generation coming soon",
  "audioUrl": "/outputs/audio/2026-04-04-script.mp3",
  "note": "Implement with Google Cloud TTS, ElevenLabs, or OpenAI TTS"
}
```

---

### POST /api/transcribe-video

On-demand YouTube video transcription. Uses YouTube native captions first, falls back to AssemblyAI.

**Request:**
```json
{
  "video_url": "https://youtu.be/vd14EElCRvs"
}
```

**Response:**
```json
{
  "video_id": "vd14EElCRvs",
  "transcript": "Earlier this week, the world may have changed forever...",
  "word_count": 1217,
  "duration_seconds": 337.76,
  "source": "youtube_captions"
}
```

The `source` field indicates which method succeeded:
- `youtube_captions` — free YouTube native captions
- `assemblyai` — paid AssemblyAI transcription (fallback)

---

### POST /api/analyze-video

On-demand deep analysis of a YouTube video. Fetches the transcript, then analyzes it with the configured LLM backend.

**Request:**
```json
{
  "video_url": "https://youtu.be/vd14EElCRvs",
  "title": "He just crawled through hell to fix the browser"
}
```

**Response:**
```json
{
  "quality_score": 8,
  "main_topic": "A developer's journey to fix a critical browser rendering bug",
  "key_insights": [
    "The fix required understanding the full browser rendering pipeline",
    "Open source contributors often work without compensation on critical infra",
    "Browser engine diversity is declining, increasing systemic risk"
  ],
  "content_type": "News",
  "target_audience": "Intermediate",
  "unique_value": "Rare inside look at browser engine debugging process",
  "transcript_word_count": 1217
}
```

**Quality score criteria:**
- 8-10: Groundbreaking, highly actionable, expert-level
- 6-7: Solid content, good insights, well-produced
- 4-5: Average, basic information
- 0-3: Low value, clickbait, or superficial

---

## Configuration Endpoints

These endpoints power the Settings UI and allow reading/writing the pipeline configuration.

### GET /api/config/feeds

Returns the current `config/feeds.yaml` as JSON.

**Response:**
```json
{
  "topics": [
    {
      "topic_name": "General News & Research",
      "github_sources": ["typescript", "python", "rust"],
      "hackernews_sources": ["open source", "startup funding"],
      "rss_sources": [
        "https://hnrss.org/frontpage",
        "https://techcrunch.com/feed/"
      ],
      "youtube_sources": ["@Fireship", "@ThePrimeTimeagen"]
    },
    {
      "topic_name": "AI / AI Tools / AI Agents",
      "rss_sources": [...],
      "youtube_sources": [...],
      "hackernews_sources": [...],
      "x_sources": [...]
    }
  ]
}
```

---

### PUT /api/config/feeds

Update the feeds configuration. Overwrites `config/feeds.yaml`.

**Request:**
```json
{
  "topics": [
    {
      "topic_name": "My Custom Topic",
      "rss_sources": ["https://example.com/feed/"],
      "youtube_sources": ["@SomeChannel"],
      "hackernews_sources": ["my keyword"],
      "github_sources": ["python"],
      "x_sources": ["someuser"]
    }
  ]
}
```

**Validation:**
- `topics` key is required (non-empty list)
- Each topic must have a non-empty `topic_name`
- Only known keys per topic are allowed: `topic_name`, `github_sources`, `hackernews_sources`, `rss_sources`, `youtube_sources`, `x_sources`, `instagram_sources`
- List fields must contain strings only

**Behavior:**
- Before overwrite, a timestamped backup is written next to `config/feeds.yaml` (e.g. `config/feeds.backup.<UTC>.yaml`)

**Response:**
```json
{
  "status": "ok",
  "topics": 1,
  "backup_path": "config/feeds.backup.20260404T120000Z.yaml"
}
```

**Errors:**

| Status | Body |
|--------|------|
| 400 | Validation message describing invalid structure |

---

## Outbound daily digest (optional)

This is **not** an HTTP route on the OpenSourceNews API. When `pipelines/daily_run.py` finishes writing the daily JSON and markdown, it can **POST** a single JSON document to a URL you control (for example an Agency or agent backend).

**Enable:** Set `AGENCY_INGEST_URL` or `EXTERNAL_INGEST_URL` to a full URL including path (e.g. `https://your-service.up.railway.app/api/your-ingest-path`). If unset, nothing is sent.

**Auth (optional):** `AGENCY_INGEST_BEARER_TOKEN` or `EXTERNAL_INGEST_BEARER_TOKEN` → sent as `Authorization: Bearer …`.

**Other:** `EXTERNAL_INGEST_ENABLED=0` disables; `EXTERNAL_INGEST_INCLUDE_MARKDOWN=0` omits markdown; `EXTERNAL_INGEST_RETRIES=3` controls retry attempts for transient request/5xx failures; `EXTERNAL_INGEST_HEADERS` optional JSON object for extra headers. See `.env.example`.

**Payload** (`Content-Type: application/json`), schema id `open_source_news_daily_digest.v1`:

```json
{
  "schema": "open_source_news_daily_digest.v1",
  "generated_at": "2026-04-04T12:00:00Z",
  "report_date": "2026-04-04",
  "report": { "Topic Name": [ { "title": "...", "url": "...", "summary": "..." } ] },
  "normalized": {
    "report_date": "2026-04-04",
    "items": [
      {
        "signal_id": "a1b2c3d4e5f67890",
        "cluster_id": "b2c3d4e5f67890a1",
        "title": "...",
        "source_urls": ["https://example.com/article"]
      }
    ],
    "sources": ["RSS"],
    "counts": { "total": 1, "by_topic": {}, "by_source": {}, "by_bucket": {}, "by_cluster": {} },
    "digest": "1 items across 1 topics from 1 source types."
  },
  "markdown": "# Daily Research — 2026-04-04\n...",
  "meta": {
    "source": "open_source_news",
    "pipeline": "pipelines/daily_run.py"
  }
}
```

Your receiving service should validate the Bearer token (if you use one), accept JSON, and return `2xx` on success. Transient request errors and `5xx` responses are retried with exponential backoff. Failures are logged as warnings; they do **not** fail the daily pipeline.

For Agency / OpenClaw configuration, security, troubleshooting, and a minimal receiver contract, see **[docs/AGENCY_DAILY_INGEST.md](docs/AGENCY_DAILY_INGEST.md)**.

---

## Environment Variables

### LLM (text generation for research, scripts, transcript analysis)

Set `LLM_PROVIDER` and the matching credentials. The API and pipelines share `pipelines/llm_provider.py`.

| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | `ollama` (default if Ollama is reachable), `openrouter`, `gemini`, or `rotating` (OpenRouter + Ollama alternating). |
| `OPENROUTER_API_KEY` | Required when `LLM_PROVIDER` is `openrouter` or `rotating`. Defaults to the `openrouter/free` router; you can also use a specific `:free` model slug. See [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-models-router). |
| `OPENROUTER_MODEL` | OpenRouter model id (optional; defaults in code). |
| `OPENROUTER_PROVIDER_SORT` | Optional: `price`, `throughput`, or `latency` (maps to `provider.sort`). |
| `OPENROUTER_MAX_REQUESTS_PER_RUN` | Optional local hard cap for OpenRouter calls in one Python process. `0` or unset means no local cap. |
| `OPENROUTER_MIN_INTERVAL_SECONDS` | Optional local spacing between OpenRouter calls to avoid exhausting free/limited tiers too quickly. |
| `OLLAMA_HOST` | Default `http://127.0.0.1:11434` when using Ollama. |
| `OLLAMA_MODEL` | Default `llama3.2` when using Ollama. |
| `GEMINI_API_KEY` | Optional. Required only when you intentionally set `LLM_PROVIDER=gemini` or use the legacy direct Qdrant sync script. Scheduled collection does not require it. |
| `LLM_FALLBACK_TO_GEMINI` | If `1` and Ollama is down, fall back to Gemini when `GEMINI_API_KEY` is set. Leave `0` to prevent Gemini usage. |
| `LLM_FALLBACK_TO_OPENROUTER` | If `1` and Ollama is down, fall back to OpenRouter when `OPENROUTER_API_KEY` is set. |
| `AGENCY_INGEST_URL` / `EXTERNAL_INGEST_URL` | Optional. After `daily_run.py`, POST the daily digest JSON to this URL (see [Outbound daily digest](#outbound-daily-digest-optional)). |
| `AGENCY_INGEST_BEARER_TOKEN` / `EXTERNAL_INGEST_BEARER_TOKEN` | Optional Bearer for that POST. |
| `EXTERNAL_INGEST_RETRIES` | Optional retry count for outbound daily digest POST attempts. Defaults to `3`. |

Full list and examples: `.env.example`.

### Required for YouTube metadata

| Variable | Description |
|----------|-------------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key for fetching video metadata |

### Optional

| Variable | Description |
|----------|-------------|
| `OPEN_SOURCE_NEWS_ADMIN_KEY` | Admin auth key for POST/PUT/PATCH/DELETE routes. Recommended for any deployed API. |
| `OPEN_SOURCE_NEWS_API_KEY` | Optional read auth key. When set, read-only endpoints except `/api/health` require `Authorization: Bearer <key>`. |
| `OPEN_SOURCE_NEWS_CORS_ORIGINS` | Comma-separated browser origins allowed by CORS. Defaults to local Vite origins. |
| `ASSEMBLYAI_API_KEY` | AssemblyAI key for fallback video transcription |
| `YT_API_KEY` | Alias for `YOUTUBE_API_KEY` |
| `PORT` | Server port (default: `5000`) |

### Frontend (Vite build)

Set at **build time** for the static UI (not read by the Flask process):

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | API origin when UI and API are split (e.g. `https://your-api.up.railway.app`). Empty = same-origin `/api` (dev proxy or reverse proxy). |
| `VITE_API_BEARER_TOKEN` | Private/dev escape hatch only. Vite exposes this in the public JS bundle. Ignored unless `VITE_ALLOW_BROWSER_BEARER_TOKEN=1`. |
| `VITE_ALLOW_BROWSER_BEARER_TOKEN` | Set to `1` only for private/dev deployments where exposing the token in browser code is acceptable. |
| `MAILAROO_API_KEY` | Mailaroo email API key for pipeline notifications |
| `MAILAROO_TO_EMAIL` | Recipient email for pipeline notifications |
| `QDRANT_URL` | Qdrant cluster URL for knowledge base sync |
| `QDRANT_API_KEY` | Qdrant API key |

---

## Error Format

All errors return JSON with an `error` key:

```json
{
  "error": "Description of what went wrong"
}
```

Common HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (missing/invalid parameters) |
| 401 | Unauthorized (missing or invalid API key) |
| 403 | Forbidden (read token used on an admin route) |
| 404 | Resource not found |
| 500 | Server error (LLM not configured, upstream LLM failure, etc.) |

---

## Quick Start

```bash
# 1. Set environment variables (pick an LLM path)
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=your-openrouter-key
export OPENROUTER_MODEL=openrouter/free
# Or: LLM_PROVIDER=gemini and GEMINI_API_KEY=... only if you intentionally use Gemini
# Or: run Ollama locally and LLM_PROVIDER=ollama

export YOUTUBE_API_KEY=your-youtube-key

# 2. Install dependencies
pip install -r requirements-api.txt

# 3. Start the API
python3 api/script_generator.py

# 4. Test health
curl http://localhost:5000/api/health

# 5. Get latest report
curl http://localhost:5000/api/reports/latest

# 6. With read auth enabled
export OPEN_SOURCE_NEWS_API_KEY=your-secret
python3 api/script_generator.py
curl -H "Authorization: Bearer your-secret" http://localhost:5000/api/reports/latest

# 7. For deployed admin/expensive routes
export OPEN_SOURCE_NEWS_ADMIN_KEY=your-admin-secret
curl -H "Authorization: Bearer your-admin-secret" \
  -H "Content-Type: application/json" \
  -X PUT http://localhost:5000/api/config/feeds \
  -d '{"topics":[{"topic_name":"AI","rss_sources":[]}]}'
```

---

## Daily Pipeline Item Schema

Each item in a daily report can contain these fields after processing:

```json
{
  "title": "string",
  "url": "string",
  "source": "RSS | YouTube | GitHub Trending | Hacker News",
  "category": "Funding Announcement | New Framework Release | Major Partnership | Technical Analysis | General News",
  "summary": "string (1-2 sentences)",

  "bucket": "general | ai | blockchain | sense_making | alternative_news",
  "content_type": "news | tutorial | product_release | opinion | commentary | interview | investigation | speculative_claim | research | market_narrative",
  "processing_mode": "standard_summary | wisdom_extraction | claim_mapping",
  "mode": "commentary",
  "stance": "commentary",
  "affiliation": "independent",
  "risk_level": "mixed",
  "verification_mode": "needs_review",
  "content_warning": "Opinion-heavy or contested claims may be present; verify before reuse.",
  "classification_confidence": 0.85,

  "quality_score": 8,
  "main_topic": "string",
  "key_insights": ["insight 1", "insight 2"],
  "content_type": "Tutorial | News | Opinion | Research | Case Study",
  "target_audience": "Beginner | Intermediate | Advanced",
  "unique_value": "string",

  "has_transcript": true,
  "transcript_word_count": 5000,
  "transcript_mode": "truncated | chunked_full",

  "key_lessons": ["lesson 1", "lesson 2"],
  "actionable_steps": ["step 1", "step 2"],
  "tools_mentioned": ["tool 1"],
  "frameworks_mentioned": ["framework 1"],
  "implementation_notes": "string",
  "difficulty": "beginner | intermediate | advanced",

  "claims": [
    {
      "claim": "string",
      "evidence_cited": "string",
      "status": "supported | mixed | unresolved | contradicted",
      "confidence": 0.7,
      "analyst_note": "string"
    }
  ],
  "entities": ["entity 1", "entity 2"],
  "uncertainty_markers": ["what remains unclear"],
  "neutral_synthesis": "string"
}
```

Not all fields are present on every item. Fields are populated based on the item's `processing_mode`:

- **standard_summary**: basic fields only (title, url, source, category, summary, bucket, content_type)
- **wisdom_extraction**: adds key_lessons, actionable_steps, tools_mentioned, frameworks_mentioned, implementation_notes, difficulty
- **claim_mapping**: adds claims, entities, uncertainty_markers, neutral_synthesis

`alternative_news` items also carry commentary metadata (`mode`, `stance`, `affiliation`, `risk_level`, `verification_mode`, `content_warning`) so downstream apps can label and rank them separately from mainstream/research sources.
