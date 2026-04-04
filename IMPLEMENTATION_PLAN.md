# OpenSourceNews Implementation Plan

**Date:** 2026-04-04
**Status:** ALL 8 PHASES COMPLETE
**Scope:** All improvements within the OpenSourceNews repo only (excludes Agency by Blockcities)

---

## Overview

This plan addresses the full set of improvements identified in `updates_to_make.md`, filtered to only what belongs inside this repository. The changes span 8 phases, ordered by dependency and priority.

---

## Phase 1: Fix GitHub Actions Scheduling [COMPLETE]

**Problem:** `daily.yml` cron is `0 7 * * 1` (Mondays only), not daily.

**Changes:**
- [x] Change `daily.yml` cron from `0 7 * * 1` to `0 7 * * *` (every day at 07:00 UTC)
- [x] Keep `video-script.yml` at weekly Monday 08:00 UTC (intentional weekly editorial)
- [x] Keep `knowledge-base.yml` at weekly + on-push (sufficient for now)
- [x] Updated email subjects from "Weekly" to "Daily" in `daily_run.py`

**Files:** `.github/workflows/daily.yml`, `pipelines/daily_run.py`

---

## Phase 2: API Authentication [COMPLETE]

**Problem:** Flask API has CORS enabled but zero auth. All endpoints publicly accessible.

**Changes:**
- [x] Add `OPEN_SOURCE_NEWS_API_KEY` env var support
- [x] Add `before_request` hook to validate `Authorization: Bearer <key>` header
- [x] Exempt `/api/health` from auth
- [x] Return 401 JSON response for missing/invalid auth
- [x] Dev mode: when env var is unset, auth is disabled
- [x] Update `.env.example` with new var

**Files:** `api/script_generator.py`, `.env.example`

---

## Phase 3: Feed-Oriented API Endpoints [COMPLETE]

**Problem:** API is research-oriented only. No way for external consumers to fetch daily reports.

**New endpoints:**
- [x] `GET /api/health` �� simple healthcheck (no auth required)
- [x] `GET /api/reports/latest` — returns the most recent daily report JSON
- [x] `GET /api/reports?limit=7` — returns metadata for N most recent reports
- [x] `GET /api/reports/by-date/<YYYY-MM-DD>` — returns a specific day's report
- [x] `GET /api/reports/latest/normalized` — returns stable normalized schema with signal_id, topics, counts, digest

**Normalized schema:**
```json
{
  "report_date": "2026-04-04",
  "items": [
    {
      "source_system": "OpenSourceNews",
      "signal_id": "hash",
      "published_at": "ISO8601",
      "title": "...",
      "summary": "...",
      "source_urls": ["..."],
      "topics": ["ai", "open-source"],
      "relevance_score": 0.84,
      "source": "RSS|YouTube|GitHub|HackerNews",
      "category": "...",
      "content_type": "...",
      "bucket": "..."
    }
  ],
  "sources": ["RSS", "YouTube", ...],
  "counts": {"total": N, "by_topic": {}, "by_source": {}},
  "digest": "One-paragraph summary"
}
```

**Files:** `api/script_generator.py`

---

## Phase 4: Expand feeds.yaml into 4 Topic Buckets [COMPLETE]

**Problem:** Only 2 topics exist ("AI Agents & Frameworks", "Blockchain VC Funding"). Need 4 comprehensive buckets.

**New bucket structure:**

### Bucket 1: General News & Research
- [x] Broad tech, open source, startup/product releases, macro platform shifts
- [x] Sources: HN frontpage, TechCrunch, The Verge, Wired, Ars Technica, Fireship, ThePrimeTime

### Bucket 2: AI / AI Tools / AI Agents
- [x] AI tools, agents, model releases, frameworks, evals, inference/training infra
- [x] Sources: All existing AI RSS feeds + YouTube channels preserved, expanded HN queries

### Bucket 3: Blockchain / Crypto / DAOs / Tokenization / Web3
- [x] Crypto, tokenization, DAOs, wallets, custody, stablecoins, regulatory
- [x] Sources: All existing blockchain sources preserved + tokenization queries

### Bucket 4: Sense-Making & Narrative Analysis
- [x] Contested narratives, geopolitics, institutional critique, alternative analysis
- [x] Sources: BBC Tech, Reuters (mainstream baselines), All-In Podcast, HN geopolitics/media queries

**Files:** `config/feeds.yaml`

---

## Phase 5: Second-Stage Content Classifier [COMPLETE]

**Problem:** Pipeline groups items by configured topic only. No per-item classification of content type or processing mode.

**Changes:**
- [x] Add `classify_item()` function using Gemini to assign:
  - `bucket`: general / ai / blockchain / sense_making
  - `content_type`: news / tutorial / product_release / opinion / speculative_claim / research / market_narrative
  - `processing_mode`: wisdom_extraction / claim_mapping / standard_summary
  - `classification_confidence`: 0.0-1.0
- [x] Call classifier after triage in the daily pipeline
- [x] Store classification fields in each item record
- [x] Fallback to topic-based defaults when Gemini is unavailable

**Files:** `pipelines/daily_run.py`

---

## Phase 6: Dual Processing Modes (Wisdom Extraction + Claim Mapping) [COMPLETE]

**Problem:** All items get the same summarization treatment. No distinction between tutorials and contested claims.

### Mode 1: Wisdom Extraction (for tutorials, educational, technical content)
- [x] `extract_wisdom()` — extracts key_lessons, actionable_steps, tools_mentioned, frameworks_mentioned, implementation_notes, difficulty

### Mode 2: Neutral Claim Mapping (for sense-making, contested narratives)
- [x] `map_claims()` — extracts claims table (claim, evidence_cited, status, confidence, analyst_note), entities, uncertainty_markers, neutral_synthesis

**Changes:**
- [x] Add `extract_wisdom()` function with Gemini prompt for instructional content
- [x] Add `map_claims()` function with Gemini prompt for sense-making content
- [x] Add `apply_processing_mode()` router based on `processing_mode` from Phase 5
- [x] Store enriched outputs in daily report items

**Files:** `pipelines/daily_run.py`

---

## Phase 7: Chunked Transcript Analysis for Long Videos [COMPLETE]

**Problem:** Current pipeline truncates transcripts to first 4,000 words. Loses material from long interviews/lectures.

**Changes:**
- [x] Add `analyze_transcript_chunked()` function that:
  - Splits transcript into ~3,000-word chunks with 300-word overlap
  - Analyzes each chunk with Gemini independently
  - Runs a final synthesis pass to merge results
- [x] Automatic routing: videos >4,000 words go to chunked mode
- [x] Standard truncated mode preserved for shorter videos (cost efficiency)
- [x] Add `transcript_mode` field: `truncated` | `chunked_full`

**Files:** `pipelines/daily_run.py`

---

## Phase 8: Report Manifest Workflow + Failure Notifications [COMPLETE]

**Problem:** No easy "latest" pointer for consumers. No failure notifications.

**Changes:**
- [x] Create `report-manifest.yml` workflow triggered after Daily Research Briefing completes
  - Builds `outputs/manifests/latest.json` with date, path, item_count, topics, generated_at
  - Commits manifest to repo
- [x] Add failure notification step to `daily.yml`
  - Sends email via Mailaroo on pipeline failure with link to failed run

**Files:** `.github/workflows/report-manifest.yml`, `.github/workflows/daily.yml`

---

## Execution Order

1. **Phase 1** ��� Fix daily cron [COMPLETE]
2. **Phase 2** — API auth [COMPLETE]
3. **Phase 3** — Feed endpoints [COMPLETE]
4. **Phase 4** — Expand feeds.yaml [COMPLETE]
5. **Phase 5** — Content classifier [COMPLETE]
6. **Phase 6** — Dual processing modes [COMPLETE]
7. **Phase 7** — Chunked transcripts [COMPLETE]
8. **Phase 8** — Manifest workflow + notifications [COMPLETE]

---

## Out of Scope (Agency by Blockcities)

The following items from `updates_to_make.md` are for the separate Agency application and are NOT implemented here:
- Agency env vars / provider config
- `openSourceNewsService` integration module
- Agency cron jobs / ingest jobs
- Agency relevance router / topic routes
- Agency chat commands
- Agency observability metrics
- Agency Qdrant collection setup
- Agency second-pass interpretation, validation workflows, action routing
- Neo4j graph (Agency-side concern)

## Out of Scope (Future Phases)

- X/Twitter API implementation (requires API credentials + separate development)
- Instagram implementation (requires API credentials)
- PDF generation for deep dives
- Source registry database (replace YAML with structured DB)
- Qdrant sync improvements
- `/api/knowledge-base/search` endpoint (after KB improvements land)
- Separate Railway `opensourcenews-api` service (deployment decision, not code change)
