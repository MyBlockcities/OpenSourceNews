# Customizable News Aggregation System

This repository is a configurable news and research pipeline for collecting signals from curated sources, producing daily intelligence reports, generating short-form video scripts, and consolidating the generated corpus into a searchable knowledge base.

The public repo is intended to contain the runnable system, sample configuration, and automation workflows. Internal notes, audit docs, and generated markdown archives are kept under a local `docs/` folder that is ignored by git.

## What it does

- Collects content from RSS feeds, Hacker News, GitHub Trending, and YouTube metadata
- Uses Gemini for triage, summarization, planning, and follow-up suggestions
- Produces daily structured outputs in `outputs/daily`
- Produces script and storyboard outputs in `outputs/scripts`
- Builds a consolidated JSON/JSONL knowledge base from generated outputs
- Optionally syncs normalized records into Qdrant
- Runs scheduled automation through GitHub Actions

## Architecture

- `pipelines/daily_run.py`: main ingestion and report generation pipeline
- `pipelines/generate_video_script.py`: daily script generation from the latest report
- `pipelines/weekly_analyzer.py`: weekly summary and script generation
- `pipelines/transcript_analysis.py`: shared Gemini transcript analysis (truncated vs `chunked_full`)
- `pipelines/academy_payload.py`: optional helpers to shape Academy-oriented drafts from normalized items
- `api/script_generator.py`: Flask API for research endpoints, reports, feeds config, transcription, and analysis (`python3 api/script_generator.py`)
- `scripts/build_knowledge_base.py`: knowledge-base builder
- `scripts/sync_knowledge_base_to_qdrant.py`: optional Qdrant sync
- `config/feeds.yaml`: source configuration

## Deployment (two targets)

Production is easiest as **two separate services** (e.g. two Railway services from the same repo):

| Target | Build | Start |
|--------|--------|--------|
| **Frontend** | Node: `npm install` && `npm run build` | Static server on `dist/` (e.g. Caddy) — see `nixpacks.toml` |
| **API** | `pip install -r requirements.txt && pip install -r requirements-api.txt` | `python3 api/script_generator.py` — see `nixpacks.api.toml` |

Details: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Requirements

- Node.js 18+
- Python 3.11+

## Environment

Copy the example environment file:

```bash
cp .env.example .env
```

The backend and Python pipelines read `GEMINI_API_KEY` from `.env` or `.env.local`. A browser-exposed Gemini key is no longer required.

Common variables:

- `GEMINI_API_KEY`: required for AI-assisted planning, summarization, scripts, and Qdrant embeddings
- `YT_API_KEY` or `YOUTUBE_API_KEY`: required for YouTube metadata collection
- `ASSEMBLYAI_API_KEY`: optional transcript fallback
- `OPEN_SOURCE_NEWS_API_KEY`: optional on the API; when set, all routes except `GET /api/health` require a Bearer token
- `VITE_API_BASE_URL`: optional at **frontend build time**; set to the API origin when the UI and API are on different hosts (see `docs/DEPLOYMENT.md`)
- `VITE_API_BEARER_TOKEN`: optional; only if the API enforces auth and you accept embedding a token in the static bundle (prefer same-origin proxy in production)
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

Generate a daily report:

```bash
python3 pipelines/daily_run.py
```

Generate a script from the latest daily report:

```bash
python3 pipelines/generate_video_script.py
```

Generate a weekly summary:

```bash
python3 pipelines/weekly_analyzer.py
```

## Outputs

- `outputs/daily/*.json`: daily machine-readable reports
- `outputs/scripts/*.txt`: generated scripts
- `outputs/scripts/*.json`: storyboard metadata
- `outputs/transcripts/*.json`: cached transcripts
- `outputs/knowledge_base/knowledge_base.json`: aggregate corpus export
- `outputs/knowledge_base/knowledge_base.jsonl`: normalized line-delimited records

Generated markdown reports and archived notes are written under local `docs/`, which is ignored by git.

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

After the knowledge base exists, you can sync it into Qdrant:

```bash
python3 scripts/sync_knowledge_base_to_qdrant.py --dry-run
python3 scripts/sync_knowledge_base_to_qdrant.py --rebuild-knowledge-base
```

The sync script:

- reads records from the generated knowledge base
- embeds them with Gemini using `GEMINI_API_KEY`
- creates or validates the target Qdrant collection
- upserts records in batches

## GitHub Actions

- `.github/workflows/daily.yml`: scheduled daily report generation (07:00 UTC)
- `.github/workflows/video-script.yml`: scheduled video script generation (08:00 UTC daily)
- `.github/workflows/knowledge-base.yml`: rebuilds the aggregate KB and uploads it as an artifact (09:30 UTC daily)
- `.github/workflows/report-manifest.yml`: writes `outputs/manifests/latest.json` after a successful daily run
- `.github/workflows/api-smoke.yml`: optional smoke test against a deployed API (`API_BASE_URL` + optional `OPEN_SOURCE_NEWS_API_KEY` secrets)

## Public-release notes

- Keep real credentials only in `.env`, `.env.local`, or GitHub Secrets
- The ignored `docs/` tree is intended for private notes, audits, and generated markdown artifacts
- Review `config/feeds.yaml` before publishing if the source list contains anything you do not want to ship by default

## Current limitations

- Transcript availability still depends on YouTube and fallback service behavior
- The `DailyFeedViewer` currently loads a small fixed set of known report dates rather than auto-indexing all generated reports
- Search results for the mission UI are fetched server-side and depend on the external search provider remaining reachable
