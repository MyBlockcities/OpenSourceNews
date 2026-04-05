# OpenSourceNews Audit & Gap Analysis

**Date:** 2026-04-04
**Scope:** Full system audit against operational checklist

---

## Audit Summary

| Area | Items Checked | Done | Gaps Remaining |
|------|:---:|:---:|:---:|
| Workflow Scheduling | 5 | 5 | 0 |
| Failure Notifications | 5 | 5 | 0 |
| Report Manifest | 1 | 1 | 0 |
| Artifact Uploads | 3 | 1 | 2 |
| Source Configuration | 4 | 4 | 0 |
| Content Classification | 3 | 3 | 0 |
| Transcript Processing | 2 | 2 | 0 |
| Output Normalization | 6 | 6 | 0 |
| Knowledge Base Enrichment | 6 | 6 | 0 |
| Qdrant Sync | 4 | 4 | 0 |
| New Workflows | 3 | 0 | 3 |
| Per-Source Metadata | 1 | 0 | 1 |
| X/Twitter Implementation | 1 | 0 | 1 |

**FIXED THIS SESSION:** KB enrichment (bucket/claims/lessons/entities/embedding_text), Qdrant enrichment, failure notifications on all workflows.

---

## Detailed Checklist

### 1. Workflow Scheduling

| Item | Status | Details |
|------|--------|---------|
| daily.yml cron changed to actual daily | DONE | `0 7 * * *` (every day 07:00 UTC) |
| knowledge-base.yml schedule decision | DONE | Weekly Monday 09:30 UTC + on-push trigger. Adequate since KB rebuilds whenever outputs/ changes are pushed. |
| video-script.yml stays weekly | DONE | Weekly Monday 08:00 UTC. Intentional — weekly editorial cadence. |

### 2. Failure Notifications

| Workflow | Status | Details |
|----------|--------|---------|
| daily.yml | DONE | Sends Mailaroo email with run link on failure |
| video-script.yml | DONE (this session) | Added failure notification step |
| knowledge-base.yml | DONE (this session) | Added failure notification step |
| dispatch.yml | N/A | Triggered externally — caller handles errors |
| report-manifest.yml | N/A | Non-critical, runs after daily |

### 3. Artifact Uploads

| Artifact | Status | Details |
|----------|--------|---------|
| outputs/knowledge_base/ | DONE | Uploaded in knowledge-base.yml with 14-day retention |
| outputs/daily/ | NOT UPLOADED | Currently committed to git instead. See Remaining Gap #1. |
| docs/generated/knowledge_base/SUMMARY.md | DONE | Included in knowledge-base.yml artifact |

### 4. Report Manifest

| Item | Status | Details |
|------|--------|---------|
| report-manifest.yml exists | DONE | Writes `outputs/manifests/latest.json` after daily pipeline succeeds |
| Manifest includes date, path, item_count, topics | DONE | Plus generated_at timestamp |

### 5. Source Configuration (feeds.yaml)

| Bucket | Status | RSS | YouTube | HN | GitHub | X |
|--------|--------|:---:|:---:|:---:|:---:|:---:|
| General News & Research | DONE | 5 | 2 | 4 | 3 | 0 |
| AI / AI Tools / AI Agents | DONE | 6 | 7 | 4 | 1 | 5 |
| Blockchain / Crypto / Web3 | DONE | 5 | 3 | 4 | 1 | 6 |
| Sense-Making & Narrative Analysis | DONE | 2 | 1 | 4 | 0 | 0 |
| **Totals** | | **18** | **13** | **16** | **5** | **11** |

### 6. Content Classification Pipeline

| Feature | Status | Location |
|---------|--------|----------|
| `classify_item()` — assigns bucket, content_type, processing_mode | DONE | daily_run.py:272-338 |
| Applied after triage in main() | DONE | daily_run.py:701-706 |
| Fallback when Gemini unavailable | DONE | Defaults to topic-based bucket, "news", "standard_summary" |

### 7. Processing Modes

| Mode | Status | Location |
|------|--------|----------|
| `extract_wisdom()` — lessons, steps, tools, frameworks | DONE | daily_run.py:343-393 |
| `map_claims()` — claims table, entities, uncertainty markers | DONE | daily_run.py:396-454 |
| `apply_processing_mode()` — routes based on classification | DONE | daily_run.py:457-464 |
| Applied in main() after classification | DONE | daily_run.py:709-717 |

### 8. Transcript Processing

| Feature | Status | Location |
|---------|--------|----------|
| Chunked analysis for >4000 word transcripts | DONE | daily_run.py:469-578 |
| 3000-word chunks with 300-word overlap | DONE | Configurable constants |
| Synthesis pass merging chunk results | DONE | Deduplicates insights, runs final Gemini synthesis |
| `transcript_mode` field (truncated/chunked_full) | DONE | Added to item records |

### 9. Output Normalization (per item)

| Field | Status |
|-------|--------|
| summary | DONE (from triage) |
| claims | DONE (from map_claims) |
| key_lessons | DONE (from extract_wisdom) |
| entities | DONE (from map_claims) |
| tools_mentioned / frameworks_mentioned | DONE (from extract_wisdom) |
| source metadata (source, url, category) | DONE (from fetchers + triage) |

### 10. Knowledge Base Enrichment

| Field in KB Record | Status | Details |
|--------------------|--------|---------|
| bucket | DONE (this session) | Added to build_knowledge_base.py |
| content_type | DONE (already existed) | |
| claims | DONE (this session) | Full claims array persisted |
| key_lessons | DONE (this session) | Array of lesson strings |
| entities | DONE (this session) | Array of entity strings |
| embedding_text | DONE (this session) | Pre-built from title, summary, insights, claims, lessons, entities, synthesis |
| actionable_steps | DONE (this session) | |
| tools_mentioned / frameworks_mentioned | DONE (this session) | |
| difficulty | DONE (this session) | |
| processing_mode | DONE (this session) | |
| classification_confidence | DONE (this session) | |
| uncertainty_markers | DONE (this session) | |
| neutral_synthesis | DONE (this session) | |
| implementation_notes | DONE (this session) | |

### 11. Qdrant Sync Enrichment

| Feature | Status | Details |
|---------|--------|---------|
| Collection name configurable | DONE | Default: `scheduler_knowledge_base`, via env or CLI arg |
| Embedding text includes claims, lessons, entities | DONE (this session) | Uses `embedding_text` field or builds from enriched record |
| Tags include bucket, processing_mode, content_type | DONE (this session) | Also includes entity tags as `entity:name` |
| Full record stored as payload | DONE | All fields available for filtering |

---

## Remaining Gaps

These items require external resources, architectural decisions, or future implementation:

### Gap 1: Artifact Upload for Daily Reports

**Current state:** `outputs/daily/*.json` is committed to git, not uploaded as a GitHub Actions artifact.

**Why it matters:** Git repos grow over time with daily JSON files. Artifacts are auto-cleaned after retention.

**Steps to fix:**
1. Add an `upload-artifact` step to `daily.yml` after the commit step:
```yaml
- name: Upload daily report artifact
  uses: actions/upload-artifact@v4
  with:
    name: daily-report-${{ github.run_id }}
    path: outputs/daily/*.json
    retention-days: 30
```
2. Optionally add the same to `dispatch.yml`
3. Consider whether old daily JSONs should eventually be purged from git (a separate cleanup workflow)

**Decision needed:** Keep git commit (current) for availability, add artifact for backup? Or switch to artifact-only?

---

### Gap 2: API Smoke Test Workflow

**Current state:** No automated test that the deployed API is reachable and responding.

**Steps to create `api-smoke-test.yml`:**
1. Create `.github/workflows/api-smoke-test.yml`
2. Trigger: after deployment succeeds, or on schedule (e.g., every 6 hours)
3. Steps:
   - `curl` the deployed `/api/health` endpoint
   - Verify `status: "ok"` in response
   - Check `/api/reports/latest` returns 200
   - Optional: check `/api/reports/latest/normalized` returns valid schema
4. Fail the workflow if any check returns non-200
5. Add failure notification

**Requires:** The Railway API service URL as a GitHub secret (e.g., `API_BASE_URL`)

---

### Gap 3: Academy Sync Workflow

**Current state:** No `academy-sync.yml` workflow exists. This is only needed if you want GitHub Actions to auto-create draft Academy content from daily reports.

**Steps to create (if needed):**
1. Create `.github/workflows/academy-sync.yml`
2. Trigger: after daily pipeline or on schedule
3. Steps:
   - Read latest report
   - Transform selected high-quality items into Academy draft format
   - POST to Academy API or commit to an Academy content repo
4. Requires: Academy API credentials or target repo access

**Decision needed:** Is Academy auto-content a priority? If not, skip this entirely.

---

### Gap 4: Academy Smoke Test Workflow

**Current state:** No `academy-smoke-test.yml` exists.

**Steps to create (if needed):**
1. Create `.github/workflows/academy-smoke-test.yml`
2. Trigger: on schedule (e.g., daily)
3. Steps:
   - Authenticate against Academy API
   - Read a known resource to verify access
   - Fail if auth or read fails

**Decision needed:** Only relevant if Academy integration is active.

---

### Gap 5: X/Twitter Real Implementation

**Current state:** `fetch_x_profile_posts()` in `daily_run.py` is a placeholder that returns `[]` and logs a skip message. 11 X accounts are configured across 2 topics.

**Steps to implement:**
1. Obtain X API credentials (Essential or Basic tier)
2. Install `tweepy` (already in requirements.txt as optional)
3. Implement `fetch_x_profile_posts()` in `daily_run.py`:
   - Authenticate with OAuth 2.0 Bearer token
   - Fetch recent tweets from user timeline
   - Handle rate limits (300 requests/15 min on Basic)
   - Normalize into `{title, url, source: "X"}` format
4. Add `X_BEARER_TOKEN` to GitHub Secrets and `.env.example`
5. Uncomment X secrets in `daily.yml` and `dispatch.yml`

**Cost:** X Basic API is $100/month. Essential is free but very limited.

---

### Gap 6: Per-Source Metadata

**Current state:** Sources in `feeds.yaml` are plain strings (URLs, channel IDs, keywords). No metadata per source.

**Eventual target schema:**
```yaml
youtube_sources:
  - id: "@Fireship"
    default_bucket: general
    priority: high
    transcript_required: true
    content_type_hint: tutorial
  - id: "@AllInPodcast"
    default_bucket: sense_making
    priority: high
    transcript_required: true
    content_type_hint: opinion
```

**Steps to implement:**
1. Define the enhanced source schema in `feeds.yaml`
2. Update all fetcher functions in `daily_run.py` to accept dict sources (not just strings)
3. Pass source metadata through to `classify_item()` as hints
4. Use `transcript_required` to decide whether to auto-fetch transcripts
5. Use `priority` to order processing (high-priority first)

**When:** After current system is stable and running daily. This is an optimization, not a blocker.

---

### Gap 7: Knowledge Base Workflow Cadence

**Current state:** Weekly Monday 09:30 UTC + on-push to `outputs/**`.

**Decision:** The on-push trigger means the KB rebuilds automatically whenever daily reports are pushed. This effectively makes it daily already. No change needed unless you want a guaranteed daily schedule regardless of push activity.

**Optional:** Change cron to `0 10 * * *` (daily 10:00 UTC) if you want guaranteed daily rebuilds.

---

## What Was Fixed This Session

1. **build_knowledge_base.py** — Added 14 new fields to daily_item records: bucket, processing_mode, classification_confidence, key_lessons, actionable_steps, tools_mentioned, frameworks_mentioned, implementation_notes, difficulty, claims, entities, uncertainty_markers, neutral_synthesis, embedding_text
2. **sync_knowledge_base_to_qdrant.py** — Updated `build_embedding_text()` to use pre-built `embedding_text` or include claims/lessons/entities. Updated `record_payload()` tags to include bucket, processing_mode, content_type, difficulty, entity tags.
3. **video-script.yml** — Added failure notification step
4. **knowledge-base.yml** — Added failure notification step
