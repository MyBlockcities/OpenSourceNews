Here is the clean split.

## Inside **Agency by Blockcities**

### 1. Add a dedicated provider config for OpenSourceNews

Create these env vars in Agency:

```env
OPEN_SOURCE_NEWS_ENABLED=true
OPEN_SOURCE_NEWS_MODE=report_polling
OPEN_SOURCE_NEWS_BASE_URL=https://opensourcenews-api-production.up.railway.app
OPEN_SOURCE_NEWS_API_KEY=replace-with-shared-secret
OPEN_SOURCE_NEWS_TIMEOUT_MS=30000
OPEN_SOURCE_NEWS_QDRANT_ENABLED=false
OPEN_SOURCE_NEWS_QDRANT_COLLECTION=open_source_news
OPEN_SOURCE_NEWS_POLL_CRON=*/30 * * * *
OPEN_SOURCE_NEWS_MAX_ITEMS_PER_RUN=50
OPEN_SOURCE_NEWS_MIN_RELEVANCE=0.65
```

Why: the repo is built around daily outputs, an API service in `api/script_generator.py`, and optional Qdrant sync, so Agency should treat it as an external intelligence provider with explicit base URL, auth, timeout, and ingestion controls. ([GitHub][1])

### 2. Add one new integration/tool in Agency

Create a tool or service module called something like:

`openSourceNewsService`

Give it these methods:

* `getLatestReport()`
* `listRecentReports(limit)`
* `searchResearch(objective)`
* `synthesizeResearch(objective, queries)`
* `generateVideoScript(items, topic)`

The repo already exposes research and generation endpoints including `/api/research/search`, `/api/research/synthesize`, `/api/research/pathfinder`, `/api/generate-script`, `/api/transcribe-video`, and `/api/analyze-video`. ([GitHub][2])

### 3. Use **report polling** as your first integration mode

For Agency, start by ingesting the machine-readable outputs from `outputs/daily/*.json`, because the repo explicitly produces those as daily structured outputs. This is the least fragile way to get a reliable news stream into Blockcities before you depend on more interactive endpoints. ([GitHub][1])

Your Agency ingest job should do this:

1. Fetch latest report metadata.
2. Pull the latest daily JSON.
3. Normalize every item into your internal signal schema.
4. Score each item for relevance to your watchlists.
5. Create events, tasks, digests, or memory records.

Suggested internal schema:

```json
{
  "source_system": "OpenSourceNews",
  "signal_id": "stable-hash-or-upstream-id",
  "published_at": "2026-04-04T07:00:00Z",
  "title": "Signal title",
  "summary": "1-2 sentence why it matters",
  "source_urls": ["https://..."],
  "topics": ["ai-infra", "open-source", "media", "research"],
  "relevance_score": 0.84,
  "actionability_score": 0.72,
  "recommended_action": "route_to_research"
}
```

### 4. Create an Agency cron job

Add a cron job in Agency that runs every 30 minutes or hourly.

Job name:
`opensourcenews_ingest_latest`

Job steps:

1. call `getLatestReport()`
2. skip if already ingested
3. normalize items
4. store raw payload
5. store normalized signals
6. create one digest deliverable
7. create tasks only for items above a threshold

This is the right fit because your repo already has a separate cron-like production model through GitHub Actions; Agency should be the consumer, not the place where raw crawling happens. ([GitHub][1])

### 5. Add a relevance router in Agency

Create topic routes like:

* `bc_news_ai_infra`
* `bc_news_tokenization`
* `bc_news_compliance`
* `bc_news_open_source_tools`
* `bc_news_creator_media`

Then map ingested items by keyword/tag/embedding match into those queues.

This matters because the repo gathers from RSS, Hacker News, GitHub Trending, and YouTube metadata, which is broad by design. You do not want everything to hit one generic inbox. ([GitHub][1])

### 6. Add two Agency-facing user actions

Add these commands to your chat/orchestration layer:

* “Get the latest open source news digest”
* “Research this topic using OpenSourceNews”

The second command should call:

1. `/api/research/plan`
2. `/api/research/search`
3. `/api/research/synthesize`
4. optional `/api/research/pathfinder`

Those research endpoints are already present in the API file. ([GitHub][2])

### 7. Add auth handling in Agency

Every request from Agency to OpenSourceNews should send:

```http
Authorization: Bearer <OPEN_SOURCE_NEWS_API_KEY>
```

Do this now on the Agency side even before you finish adding auth in the repo, so your integration contract is set from day one. That is especially important because the API file currently shows CORS enabled and does not show auth hooks like `Authorization`, `before_request`, or a dedicated `OPEN_SOURCE_NEWS_API_KEY` check. ([GitHub][2])

### 8. Add observability in Agency

Track these metrics:

* `opensourcenews_fetch_success`
* `opensourcenews_fetch_latency_ms`
* `opensourcenews_items_ingested`
* `opensourcenews_items_deduped`
* `opensourcenews_tasks_created`
* `opensourcenews_digest_created`
* `opensourcenews_last_success_at`

Without this, you will not know whether the feed is failing upstream or your Agency parser is failing downstream.

### 9. Optional: wire Qdrant later

Do not start with Qdrant as the primary path. Add it after polling works.

When ready, use OpenSourceNews as a separate collection namespace such as:

* `open_source_news`
  or
* `bc_external_news`

The repo already supports building a consolidated knowledge base and syncing it to Qdrant after KB creation. ([GitHub][1])

---

## Inside the **OpenSourceNews repo**

### 1. Split frontend and backend deployment

Right now your Railway files show the app is built with Nixpacks using Node only, runs `npm install`, `npm run build`, and starts `caddy file-server --root /app/dist`. That means the current Railway deployment is serving the frontend build, not the Python API. ([GitHub][3])

So do this:

#### Keep current service

Use current Railway service as:

* `opensourcenews-web`

#### Create a second Railway service

Create:

* `opensourcenews-api`

Set its start command to:

```bash
python3 api/script_generator.py
```

The README explicitly says the backend API is started with `python3 api/script_generator.py`, and local dev proxies `/api/*` to `http://localhost:5000`. ([GitHub][1])

### 2. Add API authentication

In the repo, add a shared-secret auth layer to the Flask app.

You need:

* env var: `OPEN_SOURCE_NEWS_API_KEY`
* a `before_request` hook
* exemption for `/health` only

Because the current API file shows CORS enabled but no `Authorization` handling, no `before_request`, and no `OPEN_SOURCE_NEWS_API_KEY` reference. ([GitHub][2])

Implement logic like:

* check `Authorization: Bearer ...`
* compare to env var
* return `401` if missing or invalid

### 3. Add three feed-oriented endpoints

Your API is currently research-oriented. Add these endpoints:

```http
GET /api/health
GET /api/reports/latest
GET /api/reports?limit=7
GET /api/reports/by-date/<YYYY-MM-DD>
```

Why: Agency should not have to guess files or scrape the frontend. The repo already produces daily JSON outputs, so add explicit endpoints that surface them cleanly. ([GitHub][1])

### 4. Add a lightweight `/api/knowledge-base/search`

Later, add:

```http
GET /api/knowledge-base/search?q=<query>&limit=10
```

Back it by:

* local JSONL search first
* Qdrant later if enabled

That gives Agency a simple retrieval endpoint before full vector integration.

### 5. Add a `/api/reports/latest/normalized`

Make this endpoint return a stable schema specifically for Agency:

```json
{
  "report_date": "2026-04-04",
  "items": [...],
  "sources": [...],
  "counts": {...},
  "digest": "..."
}
```

This will save you repeated parsing logic inside Blockcities.

---

## Inside **GitHub Actions**

### 1. Fix the “daily” workflow schedule

Your current `daily.yml` cron is:

```yaml
0 7 * * 1
```

which is every Monday at 07:00 UTC, not daily. ([GitHub][4])

Change it to:

```yaml
0 7 * * *
```

if you want daily at 07:00 UTC.

### 2. Keep the video script workflow if you want weekly

Your `video-script.yml` currently runs Mondays at 08:00 UTC, one hour after the weekly report. That is fine if you want a weekly editorial script instead of daily. ([GitHub][5])

### 3. Decide whether knowledge-base workflow should stay weekly

Your `knowledge-base.yml` is currently weekly, runs Python 3.11, builds the KB with `python3 scripts/build_knowledge_base.py`, and uploads `outputs/knowledge_base/` plus `docs/generated/knowledge_base/SUMMARY.md` as an artifact retained for 14 days. ([GitHub][6])

That is fine if Agency is not depending on near-real-time semantic search. If you want Agency retrieval from a fresher corpus, run it daily.

### 4. Add one new GitHub Action for API-ready manifests

Create a new workflow:

* `report-manifest.yml`

What it should do:

1. run after daily report generation
2. build a simple `outputs/manifests/latest.json`
3. optionally publish a stable artifact or commit it

This makes Agency polling easier because it can fetch one “latest” manifest instead of scanning the repo.

### 5. Add failure notifications

Add email/Slack/webhook notification on Action failure for:

* `daily.yml`
* `knowledge-base.yml`

If the upstream report generation breaks, Agency should not silently keep showing stale news.

---

## Inside **GitHub Secrets / env**

### Repo secrets you should have

The README documents these as the main variables:

* `GEMINI_API_KEY`
* `YT_API_KEY` or `YOUTUBE_API_KEY`
* `ASSEMBLYAI_API_KEY`
* `QDRANT_URL`
* `QDRANT_API_KEY` ([GitHub][1])

From the daily workflow, I also see:

* `MAILAROO_API_KEY`
* `MAILAROO_TO_EMAIL` ([GitHub][4])

### Add these new secrets

For the repo/API deployment, add:

* `OPEN_SOURCE_NEWS_API_KEY`
* `BLOCKCITIES_WEBHOOK_SECRET` if you want push delivery into Agency
* `BLOCKCITIES_INGEST_URL` if OpenSourceNews should POST digests into Agency instead of waiting for Agency to poll

### Railway env for `opensourcenews-api`

Set:

```env
PORT=5000
GEMINI_API_KEY=...
YT_API_KEY=...
YOUTUBE_API_KEY=...
ASSEMBLYAI_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
OPEN_SOURCE_NEWS_API_KEY=...
```

The API script runs Flask and ends with `app.run(host='0.0.0.0', port=port, debug=False)`, so the Railway API service must expose the correct `PORT`. ([GitHub][2])

---

## The exact rollout order I recommend

### First, in OpenSourceNews

1. Create `opensourcenews-api` Railway service.
2. Start it with `python3 api/script_generator.py`.
3. Add `OPEN_SOURCE_NEWS_API_KEY`.
4. Add `/api/health`.
5. Add `/api/reports/latest`.
6. Change `daily.yml` cron to true daily. ([GitHub][1])

### Second, in Agency by Blockcities

1. add env vars
2. create `openSourceNewsService`
3. create scheduled ingest job
4. create digest writer
5. create topic routing
6. create chat command for on-demand research

### Third, after that works

1. add KB search endpoint
2. run KB build daily
3. optionally sync to Qdrant
4. wire semantic retrieval into Agency memory/search. ([GitHub][1])

---

## The shortest possible version

Inside **Agency by Blockcities**, you need to:

* add OpenSourceNews env vars
* add one integration service/tool
* poll the latest daily JSON report
* normalize items into signals/tasks/digests
* add auth header support
* add a cron job
* add observability

Inside **OpenSourceNews**, you need to:

* deploy the Python API separately from the frontend
* add API auth
* add feed endpoints like `/api/reports/latest`
* fix the “daily” GitHub Action so it is actually daily
* optionally add KB/Qdrant endpoints later

The main thing to avoid is pointing Agency at the current static Railway frontend and expecting it to behave like the backend API, because the current Railway and Nixpacks configs show a static `dist` deployment via Caddy, not the Python API service. ([GitHub][3])






Let’s break it down step-by-step:

1. Create a new endpoint for your API that returns the latest daily report in a machine-readable format—something like `/api/reports/latest`. This should read the latest JSON report from your `outputs/daily/` folder.

2. Add a route for listing recent reports, such as `/api/reports?limit=7`, which returns metadata for the last week’s reports.

3. Implement API authentication. Introduce an environment variable like `OPEN_SOURCE_NEWS_API_KEY`. In the API code, add a check for the `Authorization` header (e.g., `Bearer <API_KEY>`) and return a 401 response if it’s missing or invalid.

4. Change your GitHub Action for daily report generation (`daily.yml`) so it runs every day, not just once a week. Adjust the cron schedule accordingly (e.g., `0 7 * * *` for every day at 07:00 UTC).

5. Ensure that after generating each report, you output a manifest or summary file (e.g., `outputs/manifests/latest.json`) that your Agency can easily poll.

6. Optionally, if you plan to sync the knowledge base to Qdrant, make sure the Qdrant sync script is properly tied to your GitHub Action (e.g., run daily or weekly depending on your preference).

7. Update your `config/feeds.yaml` (if needed) to ensure the sources you are pulling from are aligned with what you want your Agency to consume.

Once these updates are done, Agency by Blockcities will be able to securely fetch the latest news reports and integrate them into your workflows.



Your repo already supports **topic-based ingestion from config**, writes a **per-topic daily report**, includes YouTube transcript handling, builds a **knowledge base JSON/JSONL**, and has optional **Qdrant sync**. The important catch is that some source types are only partially implemented right now, transcript analysis is currently truncated for efficiency, and the daily pipeline still sends **all triaged items into the report without quality filtering**. ([GitHub][1])

Here is the exact planning breakdown.

## 1. What you already have

The daily pipeline loads `config/feeds.yaml`, reads `topics`, and maps source types including `rss_sources`, `youtube_sources`, `github_sources`, `hackernews_sources`, `x_sources`, and `instagram_sources`. It then stores the final report **by topic name**. That means the core abstraction you want — multiple source lists flowing into named buckets — already exists. ([GitHub][2])

Your current sample config already shows one topic bucket, `"AI Agents & Frameworks"`, with GitHub, Hacker News, RSS, and YouTube sources. So the right next move is not redesigning the pipeline, but expanding the config model into the four buckets you want. ([GitHub][3])

The pipeline also has transcript support for YouTube. It fetches full transcript text and returns structured fields like `transcript`, `segments`, `word_count`, and `duration_seconds`. But in the daily analysis path it only passes the **first 4,000 words** into Gemini for token efficiency. ([GitHub][4])

The knowledge-base builder already consolidates outputs into `knowledge_base.json` and `knowledge_base.jsonl`, and includes `daily_topic_counts`, `daily_source_counts`, `daily_reports`, `video_scripts`, `transcripts`, and `records`. That is a very good foundation for Qdrant, Neo4j, and graph-style downstream systems. ([GitHub][5])

## 2. What is not sufficient yet

The biggest limitation is source maturity. Although `x_sources` and `instagram_sources` are present in the pipeline map, the X and Instagram fetchers are still placeholders that return empty arrays and explicitly log that X is skipped until the official API is implemented. So today, your scalable multi-source design is real for RSS, Hacker News, GitHub, and YouTube, but **not yet real for X/Twitter and Instagram**. ([GitHub][2])

The second limitation is classification depth. Right now the pipeline groups by configured topic, but it does not yet appear to add a second-stage semantic classifier that says, “this belongs in general news vs AI vs blockchain vs sense-making,” nor does it show a strong “instructional wisdom extraction” path versus a separate “claim validation” path. The current daily flow also says there is **no quality filtering yet**, and all items are saved for user review. ([GitHub][2])

The third limitation is scheduling and deployment topology. Your “daily” workflow is still configured to run **every Monday at 07:00 UTC**, and the video script workflow is also weekly on Monday at 08:00 UTC. So for a high-volume multi-channel news system, your current automation is still more weekly than truly continuous. ([GitHub][6])

## 3. The four buckets you should create

You should expand `config/feeds.yaml` into these four top-level topic groups:

1. **General News / Research**
2. **AI / AI Tools / AI Agents**
3. **Blockchain / Crypto / DAOs / Tokenization / Web3**
4. **Sense-Making / Alternative Analysis / Geopolitical Narratives / Institutional Skepticism**

This fits your current topic-driven architecture because the pipeline already loops through `config['topics']` and emits `final_report[topic_name]`. ([GitHub][2])

I would not call the fourth bucket “conspiracy” in the config. Use something like:

* `Sense-Making & Narrative Analysis`
* `Open Questions & Competing Explanations`
* `Alternative Analysis`

That will make the system easier to maintain and much safer to reason about, because the workflow should focus on **evidence organization and claim validation**, not on pre-judging truth or falsity.

## 4. The pipeline architecture you actually want

You should think of each item going through **five stages**.

### Stage A — Source ingestion

This already exists for RSS, GitHub Trending, Hacker News, YouTube metadata, and partially for X/Instagram placeholders. For your long-term design, you should keep the source layer broad and dumb. It just fetches items and basic metadata. ([GitHub][1])

### Stage B — Bucket classification

After fetch, every item should be classified into one or more of your four buckets:

* general
* ai
* blockchain
* sense_making

This should be a **second-stage classifier**, not just source-based routing. A YouTube channel can post blockchain one day and AI another day. So the classifier should use title, description, transcript, source identity, and detected entities.

### Stage C — Content-type routing

Once bucketed, route by content type:

* **news item**
* **instructional/tutorial**
* **opinion/analysis**
* **speculative claim**
* **product/tool release**
* **research paper / technical explainer**
* **market narrative / tokenization / finance**
* **geopolitical / institutional claim**

This step is what lets you treat an instructional video differently from a speculative claim video.

### Stage D — Deep extraction workflow

This is where you split behavior:

For **instructional / educational videos**:

* extract core lessons
* extract actionable steps
* extract tools/frameworks mentioned
* extract “what to apply and how”
* generate structured implementation notes

For **speculative / sense-making / contested-claim videos**:

* extract claims
* extract supporting evidence cited by the speaker
* extract named entities, dates, places, institutions
* mark confidence and ambiguity
* run a validation workflow against external sources
* preserve multiple competing interpretations

This is the key design improvement you are really asking for.

### Stage E — storage and retrieval

Store every processed item in:

* daily reports
* a normalized record set for Qdrant
* optionally a graph-ready entity/relationship export for Neo4j

Your KB builder already gives you a strong base for this because it consolidates transcripts, reports, scripts, and records into JSON/JSONL. ([GitHub][5])

## 5. What you need to add for YouTube at scale

If you want to process **tons of YouTube channels daily**, you need three upgrades.

### First: channel/watchlist management

Right now your source config is static YAML. That is fine for a first version, but not for managing 100+ channels. You should move source definitions into a structured registry with fields like:

* source_id
* platform
* handle/channel_id
* default_bucket
* subtopics
* priority
* transcript_required
* validation_mode
* active/inactive
* poll_frequency

Then generate `feeds.yaml` from that registry or replace `feeds.yaml` entirely.

### Second: transcript mode control

Your current transcript path is good, but the daily pipeline only uses the first 4,000 words for analysis. For short videos this may be enough; for long interviews and lectures it will lose material. You need:

* `summary_mode` for short videos
* `chunked_full_analysis_mode` for long videos
* `on_demand_full_deep_dive_mode` for videos above a threshold or from priority channels

The current code path makes it clear that transcript-based analysis already exists, but is truncated. ([GitHub][2])

### Third: per-video record normalization

Every processed video should become a normalized record with:

* bucket
* content_type
* source metadata
* transcript metadata
* extracted claims
* extracted lessons
* extracted entities
* validation results
* graph nodes/edges
* embeddings text

Without this, Qdrant and Neo4j become much less useful.

## 6. What you need to add for X/Twitter

You asked about Twitter sources. The repo architecture expects them, but the actual implementation is still placeholder-only. So to make your system real for X, you need to implement `fetch_x_profile_posts()` properly. The current code explicitly says X is skipped and should be implemented with the official API. ([GitHub][2])

That means you need:

* X API credentials
* profile/user lookup logic
* recent posts fetch
* optional thread expansion
* rate limit handling
* record normalization

And you should treat X differently from YouTube:

* lower trust by default
* higher need for claim extraction
* more emphasis on linking to corroborating sources

## 7. The two processing modes you specifically want

You described two very different desired behaviors, and they should become two explicit modes.

### Mode 1 — Wisdom Extraction

Use for:

* tutorials
* educational explainers
* technical walkthroughs
* product demos
* frameworks and methods

Outputs:

* summary
* key lessons
* step-by-step application ideas
* tools/frameworks mentioned
* “how to apply this in Agency by Blockcities”
* confidence score
* implementation checklist

### Mode 2 — Neutral Claim Mapping + Validation

Use for:

* sense-making
* competing narratives
* controversial institutional claims
* blockchain macro claims
* geopolitical analysis
* “alternative explanation” content

Outputs:

* claims table
* evidence cited by speaker
* external corroboration sources
* contradictions / gaps
* unresolved questions
* confidence per claim
* neutral synthesis memo
* “what appears supported / unsupported / unresolved”

That second mode is the correct way to avoid dismissiveness without becoming credulous.

## 8. The exact output formats you should produce

You mentioned tables and PDFs. I would produce **three output layers** for every high-value item.

### Layer 1 — normalized machine record

For Qdrant / Agency / graphing

### Layer 2 — human-readable markdown

For internal review

### Layer 3 — generated PDF

Only for selected high-value deep dives, not for every item

Why not PDF for everything? Because your machine-readable JSON/JSONL is much better for pipelines, and your KB builder is already centered on structured outputs. PDFs should be downstream artifacts, not the primary storage layer. ([GitHub][1])

For “sense-making” content, I recommend a table like:

* Claim
* Speaker wording/paraphrase
* Evidence cited in source
* External corroboration
* Counter-evidence
* Status: supported / mixed / unresolved / contradicted
* Analyst note

For instructional content, I recommend:

* Concept
* Why it matters
* How to apply it
* Tools required
* Estimated difficulty
* Suggested Blockcities use case

## 9. How Qdrant and Neo4j should fit together

Your repo already supports a KB build and optional Qdrant sync, and `package.json` includes scripts for `build:kb` and `sync:qdrant`. ([GitHub][1])

Use them like this:

### Qdrant

Store:

* chunked transcript passages
* summaries
* extracted claims
* extracted lessons
* entity-rich snippets
* daily report items

Best for:

* semantic search
* retrieval augmentation
* “show me related videos/articles across all buckets”

### Neo4j / graph

Store:

* entities
* claims
* relationships
* source-to-claim edges
* entity co-occurrence
* contradiction/support edges
* bucket membership
* topic lineage

Best for:

* knowledge graphs
* narrative tracing
* “what people/sources keep pointing at the same institutions or technologies?”

The right design is:

* **Qdrant for semantic retrieval**
* **Neo4j for explicit relationships**

Do not force one to do the other’s job.

## 10. The biggest changes I would make to the repo

Here is the order I would do them in.

### Phase 1 — strengthen bucketing

Update `feeds.yaml` into your four major buckets. Since the pipeline already iterates over `topic_name`, this is the lowest-friction upgrade. ([GitHub][2])

### Phase 2 — implement source registry

Replace static source sprawl with a structured registry and import/export to YAML.

### Phase 3 — add second-stage classifier

After ingestion, classify by:

* bucket
* content_type
* processing_mode

### Phase 4 — implement X properly

Replace the placeholder fetcher. Right now X and Instagram are effectively nonfunctional in the pipeline. ([GitHub][2])

### Phase 5 — add full long-video chunking

Replace one-shot 4,000-word truncation with chunked transcript analysis for long videos. The current truncation is useful, but not enough for deep extraction. ([GitHub][2])

### Phase 6 — add claim tables and lesson tables

This is where your output becomes truly valuable.

### Phase 7 — add PDF generation

Only for selected deep dives.

### Phase 8 — improve automation cadence

Your “daily” report is currently weekly Monday 07:00 UTC, and the video script is weekly Monday 08:00 UTC. Change those to actual daily schedules if you want continuous coverage. ([GitHub][6])

## 11. What I think the missing conceptual piece is

The missing piece is not just “more sources.”
It is a **policy engine** that decides how each item should be treated.

Right now the repo is good at:

* collecting
* grouping by topic
* transcript fetching
* summarization
* building a knowledge base

What you want next is:

* **bucket-aware analysis**
* **content-type-aware analysis**
* **epistemic-mode-aware analysis**

That is the real upgrade.

## 12. My recommendation for your four buckets

I would define them like this:

**General News**

* broad tech
* open source
* startup/product releases
* macro platform shifts
* important industry developments

**AI**

* AI tools
* agents
* model releases
* frameworks
* evals
* robotics if AI-led
* inference/training/open-source LLM infrastructure

**Blockchain**

* crypto
* tokenization
* DAOs
* Web3
* wallets
* custody
* stablecoins
* rails
* onchain identity
* regulatory developments

**Sense-Making**

* contested narratives
* geopolitics
* institutional critique
* alternative interpretations
* “open questions”
* media framing analysis
* anomaly clusters

That fourth bucket should require the strongest claim-mapping workflow.

## 13. What I would do first, concretely

First, expand `config/feeds.yaml` into the four buckets and populate them heavily for YouTube and RSS. Your pipeline already supports topic buckets and YouTube sources. ([GitHub][2])

Second, add a post-ingestion classifier that assigns:

* `bucket`
* `content_type`
* `processing_mode`

Third, implement chunked full-transcript analysis for long YouTube videos instead of relying only on the current 4,000-word truncation path. ([GitHub][2])

Fourth, implement X for real, because today the placeholder means your “tons of Twitter sources” vision is not yet operational. ([GitHub][2])

Fifth, enrich your KB records so that Qdrant stores not just summaries, but also claims, lessons, entities, and relationships. The KB builder already gives you one place to unify all of that. ([GitHub][5])


**OpenSourceNews should be the producer and organizer of external signals.**
**Agency by Blockcities should be the interpreter, validator, action engine, and memory/orchestration layer.**

That split fits how the repo already works: it ingests curated sources, groups them by topics from `config/feeds.yaml`, generates daily outputs, exposes research/script endpoints in `api/script_generator.py`, and builds a consolidated knowledge base JSON/JSONL. ([GitHub][1])

## 1. OpenSourceNews: what belongs here

This app should own everything related to **collecting, normalizing, classifying, and packaging external content**.

### Put these steps in OpenSourceNews

**A. Source registry and source ingestion**

* YouTube channels
* RSS feeds
* GitHub Trending topics
* Hacker News queries
* later: X/Twitter accounts
* later: other source types

Why this belongs here: the daily pipeline already uses a `fetcher_map` keyed by source types and iterates over `config['topics']`, so this repo is already designed as the ingestion layer. It explicitly supports `rss_sources`, `youtube_sources`, `github_sources`, `hackernews_sources`, plus placeholders for `x_sources` and `instagram_sources`. ([GitHub][2])

**B. First-pass bucketing**
Your 4 buckets should live here:

* General News
* AI / AI Tools / AI Agents
* Blockchain / Crypto / DAOs / Tokenization / Web3
* Sense-Making / Competing Narratives / Alternative Analysis

Why this belongs here: the repo already groups outputs by topic name from `feeds.yaml`, and the current sample config already has topic-based organization. ([GitHub][3])

**C. Content-type classification**
Also do this here:

* news
* tutorial / instructional
* product/tool release
* opinion / analysis
* speculative claim
* research / technical explainer
* market / blockchain narrative

This should happen before Agency sees the data, because it is part of content normalization.

**D. Transcript fetching and core extraction**
For YouTube:

* transcript fetch
* transcript chunking
* summary
* entities
* claims
* lessons
* tools/frameworks mentioned

This belongs here because transcript handling is already in the repo, and the pipeline already analyzes transcript text, though today it truncates to the first 4,000 words for efficiency. ([GitHub][2])

**E. Structured output creation**
Generate:

* normalized JSON records
* daily reports
* extracted claims table
* extracted lessons table
* optional deep-dive markdown
* knowledge-base JSON and JSONL

This clearly belongs here because the repo already writes daily structured outputs and builds `knowledge_base.json` and `knowledge_base.jsonl`. ([GitHub][1])

**F. Feed/API surface for consumers**
OpenSourceNews should expose:

* latest report
* recent reports
* normalized record search
* bucket-filtered report access
* later: KB search

This belongs here because the repo already has an API app with research endpoints, and this is where feed-oriented endpoints should live too. ([GitHub][4])

---

## 2. Agency by Blockcities: what belongs here

Agency should own everything related to **meaning, action, validation, escalation, decision-making, and long-term orchestration**.

### Put these steps in Agency

**A. Pulling from OpenSourceNews**
Agency should consume:

* latest normalized reports
* recent records
* deep-dive items
* later: KB / vector retrieval

Agency should not be your main web crawler.

**B. Second-pass interpretation**
Agency should answer:

* Why does this matter to us?
* Does this affect Blockcities, tokenization, AI products, Academy, or portfolio strategy?
* Should this become a task, memo, or watchlist item?

That is an orchestration and decision layer problem, not an ingestion problem.

**C. Validation workflows**
Especially for your fourth bucket, Agency should do:

* corroboration
* contradiction checks
* deeper web research
* internal relevance scoring
* memo generation
* escalation to specific agents

This is where your multi-agent system becomes valuable.

**D. Action routing**
Agency should turn items into:

* tasks
* approvals
* operator alerts
* project notes
* opportunity memos
* research assignments
* deliverables

**E. Memory / cross-linking**
Agency should connect incoming signals to:

* existing projects
* existing tasks
* investor narratives
* regulatory topics
* product opportunities
* knowledge graph entities

**F. Human-facing synthesis**
Agency should produce:

* executive brief
* “top 5 things that matter”
* blockchain-specific watchlist
* AI tool opportunity list
* unresolved-claims digest

---

## 3. The exact split by application

Here is the practical division.

### OpenSourceNews owns:

* source lists
* source polling
* transcript collection
* bucket assignment
* content-type classification
* first-pass summarization
* claim extraction
* lesson extraction
* normalized records
* daily reports
* knowledge-base build
* Qdrant publishing interface or export staging

### Agency by Blockcities owns:

* ingesting those outputs
* validating high-risk/high-interest items
* deciding what matters
* routing to specialized agents
* converting signals to tasks and deliverables
* connecting results to projects and memory
* cross-source synthesis
* graph intelligence and action loops

---

## 4. What you should add to OpenSourceNews now

These are the parts that make sense to implement in that repo itself.

### Highest priority additions in OpenSourceNews

**1. Expand `feeds.yaml` into your 4 buckets**
Right now the config already uses `topics:` and includes at least one sample topic, `"AI Agents & Frameworks"`. You should add your four real buckets there first. ([GitHub][3])

**2. Add second-stage classification fields to each record**
Each normalized item should include:

* `bucket`
* `content_type`
* `processing_mode`
* `source_type`
* `confidence`
* `entities`
* `claims`
* `lessons`
* `recommended_next_step`

**3. Replace transcript truncation with chunked deep extraction**
Right now the transcript analysis path says it uses Gemini on the transcript but limits analysis to the first 4,000 words for token efficiency. That is okay for a first pass, but not for the “extract all knowledge” workflow you described. ([GitHub][2])

**4. Add feed-oriented API endpoints**
Your API already exposes research endpoints and enables CORS, but it should also expose:

* `/api/reports/latest`
* `/api/reports?limit=...`
* `/api/reports/by-bucket/...`
* `/api/records/search?...`

The API app exists, but it is more research-oriented today than feed-oriented. ([GitHub][4])

**5. Add auth to the API**
The current API file shows `CORS(app)` and environment loading, but no visible request auth layer in the sections we inspected. So this repo should own its own API authentication. ([GitHub][4])

**6. Implement X/Twitter for real**
The architecture expects `x_sources`, but today that is just part of the fetcher map. So if X is important, OpenSourceNews should own the fetcher implementation. ([GitHub][2])

**7. Produce graph/Qdrant-ready records**
The KB builder already creates `knowledge_base.json`, `knowledge_base.jsonl`, `daily_topic_counts`, `daily_source_counts`, `daily_reports`, `transcripts`, and `records`. That means OpenSourceNews is already the correct place to emit graph-ready normalized records. ([GitHub][5])

---

## 5. What you should not force into OpenSourceNews

These things are better left to Agency.

### Do not overload OpenSourceNews with:

* full decision-making
* project prioritization
* multi-agent debate
* internal task routing
* approval flows
* strategic memo selection
* project-specific interpretation
* cross-linking to your internal Blockcities project graph

Why: that turns a clean ingestion/knowledge producer into a bloated orchestration app.

OpenSourceNews should answer:
**“What’s out there, how is it organized, and what does it say?”**

Agency should answer:
**“What matters to us, what do we believe, what do we do next?”**

---

## 6. The workflow, by application

### In OpenSourceNews

**Step 1:** ingest source items
**Step 2:** assign bucket
**Step 3:** assign content type
**Step 4:** fetch transcript/full text where possible
**Step 5:** extract summary, claims, lessons, entities
**Step 6:** build normalized records
**Step 7:** write daily bucketed reports
**Step 8:** build/update KB JSON/JSONL
**Step 9:** optionally push embeddings / Qdrant export
**Step 10:** expose API endpoints for Agency to consume

### In Agency by Blockcities

**Step 11:** ingest latest report/records from OpenSourceNews
**Step 12:** re-score for Blockcities relevance
**Step 13:** send high-value items to specialized agents
**Step 14:** run validation workflows when needed
**Step 15:** generate memos / action recommendations
**Step 16:** create tasks, deliverables, alerts, and project links
**Step 17:** store selected outputs in your internal memory / graph systems

---

## 7. The two especially important mode splits

These should be designed across both apps, but mostly start in OpenSourceNews.

### For instructional videos

**OpenSourceNews should extract:**

* key lessons
* step-by-step takeaways
* tools mentioned
* frameworks mentioned
* practical application notes

**Agency should add:**

* how this applies to Blockcities
* which team/agent should use it
* whether to turn it into a task or internal playbook

### For sense-making / contested-claim content

**OpenSourceNews should extract:**

* claims
* entities
* cited evidence
* timeline
* uncertainty markers

**Agency should add:**

* external validation
* contradiction analysis
* significance assessment
* final neutral memo
* action/no-action recommendation

---

## 8. The best long-term storage model

### OpenSourceNews should publish:

* raw-ish normalized records
* chunked transcript excerpts
* lessons
* claims
* entities
* metadata
* bucket labels

### Agency should consume and choose what to preserve as:

* operational memory
* project-linked notes
* graph relationships
* tasks and deliverables

### Qdrant

OpenSourceNews is the right place to produce the embedding-ready records because it already builds the KB. ([GitHub][5])

### Neo4j / graph

Agency is the better place to turn selected items into meaningful relationships, because graph usefulness depends on internal context and not just external content.

---

## 9. One important deployment implication

Because your current Railway deployment is configured to serve `dist` via Caddy with `startCommand = "caddy file-server --listen :$PORT --root /app/dist"`, the live deployment is acting like a static frontend. That means feed/API production should either be added as a second API deployment or explicitly separated. ([GitHub][6])

Also, your “daily” workflow is currently scheduled for Mondays at 07:00 UTC, and the video-script workflow is Mondays at 08:00 UTC, so your automation cadence is still weekly for those jobs. ([GitHub][7])

---

## 10. My recommendation in one sentence

**Build OpenSourceNews into the external signal refinery. Build Agency by Blockcities into the intelligence command center.**

That is the cleanest architecture
