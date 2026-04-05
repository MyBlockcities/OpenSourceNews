# OpenSourceNews API Reference

**Base URL:** `http://localhost:5000` (local) or your Railway/deployed URL
**Start command:** `python3 api/script_generator.py`

---

## Authentication

All endpoints (except `/api/health`) require a Bearer token when `OPEN_SOURCE_NEWS_API_KEY` is set.

```
Authorization: Bearer <your-api-key>
```

If `OPEN_SOURCE_NEWS_API_KEY` is not set in the environment, auth is disabled (dev mode) and all requests are allowed.

**Error responses:**

| Status | Body | Meaning |
|--------|------|---------|
| 401 | `{"error": "Missing or invalid Authorization header"}` | No `Authorization: Bearer ...` header sent |
| 401 | `{"error": "Invalid API key"}` | Token does not match the configured key |

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

Returns the latest report transformed into a **stable normalized schema** designed for external consumers (e.g., Agency by Blockcities). Every item gets a deterministic `signal_id` for deduplication.

**Response:**
```json
{
  "report_date": "2026-04-04",
  "items": [
    {
      "source_system": "OpenSourceNews",
      "signal_id": "a1b2c3d4e5f67890",
      "title": "New LLM Framework Released",
      "summary": "A new framework for building AI agents...",
      "source_urls": ["https://example.com/article"],
      "topics": ["AI / AI Tools / AI Agents"],
      "source": "RSS",
      "category": "New Framework Release",
      "content_type": "product_release",
      "quality_score": null,
      "bucket": "ai",
      "processing_mode": "standard_summary"
    }
  ],
  "sources": ["GitHub Trending", "Hacker News", "RSS", "YouTube"],
  "counts": {
    "total": 87,
    "by_topic": {
      "AI / AI Tools / AI Agents": 35,
      "Blockchain / Crypto / Web3": 22,
      "General News & Research": 20,
      "Sense-Making & Narrative Analysis": 10
    },
    "by_source": {
      "RSS": 40,
      "YouTube": 25,
      "Hacker News": 15,
      "GitHub Trending": 7
    }
  },
  "digest": "87 items across 4 topics from 4 source types."
}
```

---

## Research Endpoints

These endpoints power the "Research" tab in the frontend. They use Gemini AI and DuckDuckGo for live research.

**Requires:** `GEMINI_API_KEY` set in environment.

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
| 500 | `{"error": "Gemini API key not configured"}` | No `GEMINI_API_KEY` |

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

Generate a video script from selected daily feed items using Gemini AI.

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

On-demand deep analysis of a YouTube video. Fetches the transcript, then analyzes with Gemini AI.

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
- `topics` key is required
- Each topic must have a `topic_name`

**Response:**
```json
{
  "status": "ok",
  "topics": 1
}
```

**Errors:**

| Status | Body |
|--------|------|
| 400 | `{"error": "Invalid config: 'topics' key required"}` |
| 400 | `{"error": "Each topic must have a 'topic_name'"}` |

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key for triage, classification, analysis, and script generation |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key for fetching video metadata |

### Optional

| Variable | Description |
|----------|-------------|
| `OPEN_SOURCE_NEWS_API_KEY` | API auth key. When set, all endpoints (except `/api/health`) require `Authorization: Bearer <key>` |
| `ASSEMBLYAI_API_KEY` | AssemblyAI key for fallback video transcription |
| `YT_API_KEY` | Alias for `YOUTUBE_API_KEY` |
| `PORT` | Server port (default: `5000`) |
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
| 404 | Resource not found |
| 500 | Server error (API key not configured, Gemini failure, etc.) |

---

## Quick Start

```bash
# 1. Set environment variables
export GEMINI_API_KEY=your-key
export YOUTUBE_API_KEY=your-key

# 2. Install dependencies
pip install -r requirements-api.txt

# 3. Start the API
python3 api/script_generator.py

# 4. Test health
curl http://localhost:5000/api/health

# 5. Get latest report
curl http://localhost:5000/api/reports/latest

# 6. With auth enabled
export OPEN_SOURCE_NEWS_API_KEY=your-secret
python3 api/script_generator.py
curl -H "Authorization: Bearer your-secret" http://localhost:5000/api/reports/latest
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

  "bucket": "general | ai | blockchain | sense_making",
  "content_type": "news | tutorial | product_release | opinion | speculative_claim | research | market_narrative",
  "processing_mode": "standard_summary | wisdom_extraction | claim_mapping",
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
