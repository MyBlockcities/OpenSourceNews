# OpenSourceNews Audit and Optimization Plan

Date: 2026-05-09

## Executive Summary

OpenSourceNews is already close to the intended shape: a scheduled, mostly free news aggregation pipeline that runs on GitHub Actions, writes daily reports, exposes a Flask API, and serves a Vite/React dashboard. The biggest gaps are not in basic collection. They are operational hardening, public-secret safety, clearer public/private API boundaries, and long-term storage/search strategy.

No committed `.env` file was found. `.gitignore` ignores `.env*` while preserving `.env.example`, and a regex scan did not find obvious real API keys in source files. The main key-exposure risk is configuration-driven: the frontend currently supports `VITE_API_BEARER_TOKEN`, which would embed a token in the public JavaScript bundle if set. That should not be used for production.

## Current Architecture

- `pipelines/daily_run.py` fetches RSS, Hacker News, GitHub Trending, and YouTube metadata from `config/feeds.yaml`.
- `pipelines/mission_briefs.py` turns generated reports plus `config/watchlists.yaml` into strategic briefs under `outputs/briefs`.
- `pipelines/llm_provider.py` supports local Ollama, Gemini, OpenRouter, and rotating OpenRouter/Ollama.
- `.github/workflows/daily.yml` runs the daily pipeline at 07:00 UTC and commits `outputs/daily/*.json`, `outputs/transcripts/*.json`, and generated mission briefs.
- `.github/workflows/video-script.yml` generates daily script outputs.
- `.github/workflows/report-manifest.yml` builds `outputs/manifests/latest.json`.
- `.github/workflows/knowledge-base.yml` builds a knowledge-base artifact.
- `api/script_generator.py` exposes report, manifest, feed config, research, transcript, and generation endpoints.
- `mcp/server.py` exposes the generated archive to agent clients over stdio MCP tools and resources.
- `components/DailyFeedViewer.tsx` now discovers reports via `/api/reports?limit=14`, with static-file fallback.

## Secret and API-Key Findings

### What Looks Good

- Real environment files are ignored by `.gitignore`.
- GitHub Actions read keys from `secrets.*`, not from committed files.
- The backend reads server-side credentials from environment variables.
- The frontend no longer directly imports Gemini or other vendor SDK secrets; calls are routed through the backend API.
- `services/external_ingest.py` sends outbound Bearer auth only server-side.

### Critical Risk

- `VITE_API_BEARER_TOKEN` is unsafe for production because every `VITE_*` variable is compiled into the public browser bundle. If set to the same value as `OPEN_SOURCE_NEWS_API_KEY`, anyone viewing the app can reuse the token.

### Medium Risks

- The API currently uses a single `OPEN_SOURCE_NEWS_API_KEY` for all non-health routes. This makes it hard to expose public read endpoints while locking down expensive/write endpoints.
- `PUT /api/config/feeds` modifies repo-local configuration and should require a stronger admin token than read-only report access.
- POST endpoints can trigger paid or quota-consuming work through LLM, transcript, search, or TTS paths. These should be admin-protected when the service is exposed.
- CORS was open to all origins. Bearer tokens in browsers are still unsafe even with CORS, but a restrictive origin list lowers accidental exposure and abuse from browser contexts.
- GitHub Actions workflows use broad `contents: write` where commits are needed. This is acceptable for report-writing jobs, but non-committing jobs should stay read-only.

## Reliability Findings

- Daily and script workflows commit generated output back to the repository. This keeps the project free and easy to consume through raw GitHub URLs, but it will bloat the repo over time.
- The daily workflow has `concurrency` protection, which is good.
- The video script workflow does `git pull` before generation. That helps pick up daily reports, but concurrent pushes from multiple workflows can still occasionally race.
- The knowledge-base workflow uploads artifacts but does not commit them, keeping larger derived data out of git.
- The API has a health endpoint and a scheduled smoke test, but the smoke test is optional because it skips when `API_BASE_URL` is absent.

## Improvement Plan

### Phase 1: Immediate Hardening

- [x] Remove automatic browser injection of `VITE_API_BEARER_TOKEN`.
- [x] Add an explicit `VITE_ALLOW_BROWSER_BEARER_TOKEN=1` escape hatch only for private/dev deployments.
- [x] Add `OPEN_SOURCE_NEWS_ADMIN_KEY` for POST/PUT/admin endpoints.
- [x] Allow public read-only report endpoints while protecting expensive/admin endpoints.
- [x] Use constant-time token comparison with `hmac.compare_digest`.
- [x] Add `OPEN_SOURCE_NEWS_CORS_ORIGINS` so production origins are explicit.
- [x] Document secret rules clearly in `.env.example`, README, and API reference.
- [x] Add a GitHub Actions workflow/job that checks for accidental use of browser bearer tokens in production config.

### Phase 2: Continuous Free Operation

- [x] Keep daily generated JSON in `outputs/daily` for now because raw GitHub access is the cheapest public distribution mechanism.
- [x] Add retention tooling to prune older generated outputs or move them to GitHub Releases/artifacts later.
- [x] Keep `outputs/manifests/latest.json` as the stable discovery file for static consumers.
- [x] Add `workflow_dispatch` inputs for dry-run and no-commit modes so Actions can be tested without pushing output.
- [x] Improve commit/push robustness by rebasing before push or using a retry loop.
- [x] Add a scheduled workflow status summary that reports last successful daily run and latest report date.

### Phase 3: Better News Product

- [x] Add `/api/news/search?q=...&days=...&topic=...` over recent reports.
- [x] Add stable event clustering beyond URL-only dedupe using normalized title + bucket `cluster_id`.
- [ ] Add source reputation, source type, and verification status to normalized items.
- [x] Add watchlists for strategic topics such as AI agents, RWA/tokenization, and health/wellness peptides.
- [x] Add mission briefs that turn daily signals into "what changed, why it matters, what to do next."

### Phase 4: Agent-Native Interfaces

- [x] Add an MCP server wrapper exposing latest report, normalized report, search, by-date, signal, topic digest, manifest, and brief tools.
- [ ] Add webhook dispatch per topic/watchlist.
- [x] Keep Qdrant sync optional because it requires paid/credentialed services.
- [ ] Add a receiver template for downstream systems that validates the outbound digest schema and Bearer token.

## Recommended Production Secret Setup

Use these GitHub Secrets for the scheduled pipeline:

- `GEMINI_API_KEY` only if scheduled Actions use Gemini.
- `OPENROUTER_API_KEY` only if scheduled Actions use OpenRouter.
- `YT_API_KEY` for YouTube metadata.
- `ASSEMBLYAI_API_KEY` only if transcript fallback is needed.
- `MAILAROO_API_KEY` and `MAILAROO_TO_EMAIL` only for notifications.

Use these API deployment variables:

- `OPEN_SOURCE_NEWS_ADMIN_KEY`: required for feed edits and expensive POST endpoints.
- `OPEN_SOURCE_NEWS_API_KEY`: optional read token if read endpoints should not be public.
- `OPEN_SOURCE_NEWS_CORS_ORIGINS`: comma-separated list of frontend origins.

Do not set `VITE_API_BEARER_TOKEN` on a public static frontend. Prefer one of:

- Same-origin reverse proxy that injects Authorization server-side.
- Public read-only API with only admin/expensive endpoints protected.
- Private frontend deployment only, with `VITE_ALLOW_BROWSER_BEARER_TOKEN=1` set intentionally.

## First Implementation Pass

Completed in this audit pass:

- [x] Harden `services/apiClient.ts`.
- [x] Harden `api/script_generator.py`.
- [x] Update `.env.example`, README, and API reference.
- [x] Tighten Actions permissions where possible.
- [x] Run frontend build and lightweight Python checks.
- [x] Remove the unused frontend `@google/genai` dependency.
- [x] Require explicit opt-in before a Vite browser build injects a Bearer token.
- [x] Add admin/read API-key separation and constant-time token comparison.
- [x] Restrict CORS to configured/local origins instead of allowing every origin by default.
- [x] Stop scheduled Actions from forcing Gemini as the default LLM provider.
- [x] Require HTTPS for outbound ingest except localhost development URLs.

## Second Implementation Pass

Started after the first hardening pass:

- [x] Add `/api/news/search` for keyword search over recent generated reports.
- [x] Add retention tooling for `outputs/daily`, `outputs/scripts`, and `outputs/transcripts`.
- [x] Add dry-run/no-commit controls for scheduled workflows.
- [x] Add commit push retry/rebase logic for generated-output workflows.
- [x] Add a CI guard for unsafe public browser token configuration.

Verification completed:

- [x] `npm run build`
- [x] `python3 -m py_compile api/script_generator.py services/external_ingest.py pipelines/daily_run.py pipelines/llm_provider.py scripts/prune_outputs.py`
- [x] `python3 scripts/prune_outputs.py --keep-days 120 --keep-daily-min 60 --keep-script-min 30 --keep-transcript-min 25`
- [x] Workflow YAML parse check.
- [x] `/api/news/search?q=ai&days=365&limit=3` test-client smoke check.
- [x] Browser-token committed-assignment guard check.

## Third Implementation Pass

Completed for the OpenSwarm/news-intelligence integration layer:

- [x] Reuse shared deterministic schema helpers for `signal_id`, `cluster_id`, normalized items, normalized reports, and search scoring.
- [x] Add `cluster_id` to normalized items and future daily report items.
- [x] Allow `/api/news/search` to work with `q`, `topic`, `source`, or `bucket` filters so external consumers can search without a keyword when they already know the topic lane.
- [x] Include both raw `report` and normalized `items`/`sources`/`counts`/`digest` in outbound webhook payloads.
- [x] Add outbound webhook retry/backoff while preserving "do not fail the daily pipeline" behavior.
- [x] Add `config/watchlists.yaml` with initial strategic watchlists.
- [x] Add `pipelines/mission_briefs.py` and wire it into the daily GitHub Actions workflow.
- [x] Add read endpoints for watchlists and generated mission briefs.
- [x] Add an MCP stdio server with tools for latest reports, normalized reports, search, by-date reports, signals, topic digests, manifests, and mission briefs.
- [x] Remove scheduled GitHub Actions dependency on `GEMINI_API_KEY`; daily collection and video script generation now have no-Gemini fallback paths.
- [x] Add a downstream-friendly Qdrant JSONL export contract that does not require embedding or Qdrant credentials in this repo.

## Open Follow-Ups

- Decide whether public report reads should stay open by default in production.
- Decide how long generated `outputs/daily` should remain committed to git.
- Decide whether to add object storage later for long-term history.
- Decide whether Actions should use Gemini, OpenRouter free models, or only Ollama/local runs.
- Decide whether feed edits should be available from the public dashboard or only from local/admin contexts.
- Optional later: add source reputation, source type, and verification status fields.
- Optional later: add per-topic/per-watchlist outbound webhook fanout and a downstream receiver template.
