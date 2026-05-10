# Customizable News Aggregation System

This repository is a configurable news and research pipeline for collecting signals from curated sources, producing daily intelligence reports, generating short-form video scripts, and consolidating the generated corpus into a searchable knowledge base.

The public repo is intended to contain the runnable system, sample configuration, and automation workflows. Internal notes, audit docs, and generated markdown archives are kept under a local `docs/` folder that is ignored by git.

## What it does

- Collects content from RSS feeds, Hacker News, GitHub Trending, and YouTube metadata
- Keeps independent/personality-led commentary in a separate `alternative_news` bucket with review metadata
- Uses a configurable LLM (local Ollama, OpenRouter, or optional Gemini) for richer triage, summarization, planning, and follow-up suggestions; scheduled collection still runs without one
- Produces daily structured outputs in `outputs/daily`
- Produces script and storyboard outputs in `outputs/scripts`
- Builds a consolidated JSON/JSONL knowledge base from generated outputs
- Optionally syncs normalized records into Qdrant
- Generates strategic mission briefs from configurable watchlists
- Exposes an agent-facing MCP stdio server over the generated archive
- Runs scheduled automation through GitHub Actions

## Architecture

- `pipelines/daily_run.py`: main ingestion and report generation pipeline
- `pipelines/generate_video_script.py`: daily script generation from the latest report
- `pipelines/weekly_analyzer.py`: weekly summary and script generation
- `pipelines/mission_briefs.py`: watchlist-driven mission briefs from daily reports
- `pipelines/transcript_analysis.py`: shared LLM transcript analysis (truncated vs `chunked_full`)
- `pipelines/academy_payload.py`: optional helpers to shape Academy-oriented drafts from normalized items
- `api/script_generator.py`: Flask API for research endpoints, reports, feeds config, transcription, and analysis (`python3 api/script_generator.py`)
- `mcp/server.py`: stdio MCP server exposing latest reports, search, signals, topic digests, manifests, and briefs
- `scripts/build_knowledge_base.py`: knowledge-base builder
- `scripts/sync_knowledge_base_to_qdrant.py`: optional Qdrant sync
- `config/feeds.yaml`: source configuration
- `config/watchlists.yaml`: strategic watchlists for mission briefs

## Deployment (two targets)

Production is easiest as **two separate services** (e.g. two Railway services from the same repo):

| Target | Build | Start |
|--------|--------|--------|
| **Frontend** | Node: `npm install` && `npm run build` | Static server on `dist/` (e.g. Caddy) — see `nixpacks.toml` |
| **API** | `pip install -r requirements.txt && pip install -r requirements-api.txt` | `python3 api/script_generator.py` — see `nixpacks.api.toml` |

Details: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Railway API vs static UI: [docs/RAILWAY_API_DEPLOYMENT_CHECKLIST.md](docs/RAILWAY_API_DEPLOYMENT_CHECKLIST.md).

## Requirements

- Node.js 18+
- Python 3.11+

## Environment

Copy the example environment file:

```bash
cp .env.example .env
```

The backend and Python pipelines read LLM settings from `.env` or `.env.local` (`LLM_PROVIDER`, `OPENROUTER_*`, `OLLAMA_*`, optional `GEMINI_API_KEY`, etc.). See `.env.example` and [API_REFERENCE.md](API_REFERENCE.md#environment-variables).

Common variables:

- `LLM_PROVIDER` and matching keys (`OPENROUTER_API_KEY` for OpenRouter, optional `GEMINI_API_KEY` for Gemini-only, or local Ollama): required only for AI-assisted planning, summarization, premium script generation, and on-demand analysis. OpenRouter defaults to `openrouter/free`.
- `GEMINI_API_KEY`: optional. Scheduled GitHub Actions do not require it. Keep it out of public/frontend environments.
- `YT_API_KEY` or `YOUTUBE_API_KEY`: required for YouTube metadata collection
- `ASSEMBLYAI_API_KEY`: optional transcript fallback
- `OPEN_SOURCE_NEWS_ADMIN_KEY`: recommended for any deployed API; protects POST/PUT/PATCH/DELETE routes that can edit config or spend LLM/transcript quota
- `OPEN_SOURCE_NEWS_API_KEY`: optional read token; when set, read-only routes except `GET /api/health` require a Bearer token too
- `OPEN_SOURCE_NEWS_CORS_ORIGINS`: comma-separated browser origins allowed to call the API; defaults to local Vite origins
- `VITE_API_BASE_URL`: optional at **frontend build time**; set to the API origin when the UI and API are on different hosts (see `docs/DEPLOYMENT.md`)
- `VITE_API_BEARER_TOKEN`: private/dev escape hatch only; Vite embeds it in the public browser bundle and the app ignores it unless `VITE_ALLOW_BROWSER_BEARER_TOKEN=1`
- `OPENROUTER_MAX_REQUESTS_PER_RUN` and `OPENROUTER_MIN_INTERVAL_SECONDS`: optional local guardrails if you use OpenRouter free/limited models
- `QDRANT_URL`: required only if syncing the knowledge base into Qdrant
- `QDRANT_API_KEY`: optional, depending on your Qdrant deployment

## Local setup

### 1. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### 2. Install frontend dependencies

```bash
npm install
```

### 3. Run the backend API

```bash
python3 api/script_generator.py
```

This enables:

- mission planning and synthesis endpoints used by the frontend
- on-demand script generation
- on-demand transcript and video analysis endpoints

### 4. Run the frontend

```bash
npm run dev
```

Vite proxies `/api/*` requests to the backend at `http://localhost:5000`.

## Running the pipeline

Current source inventory and downstream export guidance: [NEWS_SOURCES_AND_QDRANT_EXPORT.md](NEWS_SOURCES_AND_QDRANT_EXPORT.md).

Generate a daily report:

```bash
python3 pipelines/daily_run.py
```

Optional: after the report is written, the same run can **POST** the digest JSON (and markdown) to another HTTPS endpoint you configure — for example an agent or Agency backend. Set `AGENCY_INGEST_URL` or `EXTERNAL_INGEST_URL` (and optional Bearer token) in `.env`. See **[docs/AGENCY_DAILY_INGEST.md](docs/AGENCY_DAILY_INGEST.md)** for receiver setup, payload schema, and security; also `API_REFERENCE.md` (*Outbound daily digest*) and `services/external_ingest.py`.

Generate mission briefs from the latest daily report and `config/watchlists.yaml`:

```bash
python3 pipelines/mission_briefs.py
```

Generate a script from the latest daily report:

```bash
python3 pipelines/generate_video_script.py
```

Generate a weekly summary:

```bash
python3 pipelines/weekly_analyzer.py
```

Search generated reports through the API:

```bash
curl "http://localhost:5000/api/news/search?q=agent%20framework&days=30"
curl "http://localhost:5000/api/news/search?topic=AI&bucket=ai&days=30"
curl "http://localhost:5000/api/news/search?bucket=alternative_news&days=30"
```

Run the local MCP server for agent clients:

```bash
python3 -m mcp.server
```

## Outputs

- `outputs/daily/*.json`: daily machine-readable reports
- `outputs/scripts/*.txt`: generated scripts
- `outputs/scripts/*.json`: storyboard metadata
- `outputs/transcripts/*.json`: cached transcripts
- `outputs/briefs/{watchlist}/*.json`: mission brief payloads
- `outputs/briefs/{watchlist}/*.md`: human-readable mission briefs
- `outputs/knowledge_base/knowledge_base.json`: aggregate corpus export
- `outputs/knowledge_base/knowledge_base.jsonl`: normalized line-delimited records

Generated markdown reports and archived notes are written under local `docs/`, which is ignored by git.

Preview output pruning without deleting files:

```bash
python3 scripts/prune_outputs.py
```

Apply pruning when the retention window looks right:

```bash
python3 scripts/prune_outputs.py --keep-days 120 --apply
```

## Knowledge base

Build the consolidated knowledge base:

```bash
npm run build:kb
```

This reads generated outputs and produces:

- `outputs/knowledge_base/knowledge_base.json`
- `outputs/knowledge_base/knowledge_base.jsonl`

It also writes a local human-readable summary to:

- `docs/generated/knowledge_base/SUMMARY.md`

## Qdrant sync

After the knowledge base exists, you can preview the legacy direct Qdrant sync:

```bash
python3 scripts/sync_knowledge_base_to_qdrant.py --dry-run
python3 scripts/sync_knowledge_base_to_qdrant.py --rebuild-knowledge-base
npm run sync:qdrant:peptides
```

Prepare Qdrant-ready JSONL for another application to embed/upsert:

```bash
npm run export:qdrant
npm run export:qdrant:peptides
```

The legacy direct sync script:

- reads records from the generated knowledge base
- embeds them with Gemini using `GEMINI_API_KEY`
- creates or validates the target Qdrant collection
- upserts records in batches

For your current setup, prefer `npm run export:qdrant` and let the downstream app handle embeddings/upsert with its own credentials. Use `npm run export:qdrant:peptides` for the medically sensitive peptide-only export intended for a separate Qdrant collection named `peptides`.

See [NEWS_SOURCES_AND_QDRANT_EXPORT.md](NEWS_SOURCES_AND_QDRANT_EXPORT.md) for the current source inventory and downstream Qdrant payload contract.
See [PEPTIDES_SOURCE_AND_QDRANT_WORKFLOW.md](PEPTIDES_SOURCE_AND_QDRANT_WORKFLOW.md) for peptide source layering, safety metadata, and the OpenSwarm import command.

## Influencer discovery

Discover up to 20 new micro-influencer candidates per topic from free sources:

```bash
npm run discover:influencers
python3 scripts/discover_influencers.py --dry-run --topic peptides
```

The discovery runner writes topic registries under `data/influencers/`. It uses
YouTube Data API free quota when `YOUTUBE_API_KEY` or `YT_API_KEY` is set, reads
RSS authors from `config/feeds.yaml`, and only extracts X/Instagram/TikTok links
from public descriptions or feed content. It does not query paid social APIs.

## GitHub Actions

- `.github/workflows/daily.yml`: scheduled daily report generation (07:00 UTC)
- `.github/workflows/video-script.yml`: scheduled video script generation (08:00 UTC daily)
- `.github/workflows/knowledge-base.yml`: rebuilds the aggregate KB and uploads it as an artifact (09:30 UTC daily)
- `.github/workflows/qdrant-export.yml`: rebuilds default and peptide Qdrant JSONL exports after daily reports
- `.github/workflows/influencer-discovery.yml`: discovers up to 20 new micro-influencers per topic daily
- `.github/workflows/report-manifest.yml`: writes `outputs/manifests/latest.json` after a successful daily run
- `.github/workflows/api-smoke.yml`: optional smoke test against a deployed API (`API_BASE_URL` + optional `OPEN_SOURCE_NEWS_API_KEY` secrets)
- `.github/workflows/prune-outputs.yml`: manual dry-run/apply pruning for generated output retention
- `.github/workflows/security-guard.yml`: checks committed config for unsafe browser token settings
- `.github/workflows/status-summary.yml`: scheduled/manual summary of latest generated output health

## Public-release notes

- Keep real credentials only in `.env`, `.env.local`, or GitHub Secrets
- Do not put `OPEN_SOURCE_NEWS_ADMIN_KEY`, `OPEN_SOURCE_NEWS_API_KEY`, vendor API keys, or ingest Bearer tokens into `VITE_*` variables for a public frontend
- For public deployments, prefer public read-only report endpoints plus `OPEN_SOURCE_NEWS_ADMIN_KEY` for expensive/admin API routes
- The ignored `docs/` tree is intended for private notes, audits, and generated markdown artifacts
- Review `config/feeds.yaml` before publishing if the source list contains anything you do not want to ship by default

## Current limitations

- Transcript availability still depends on YouTube and fallback service behavior
- The `DailyFeedViewer` currently loads a small fixed set of known report dates rather than auto-indexing all generated reports
- Search results for the mission UI are fetched server-side and depend on the external search provider remaining reachable
