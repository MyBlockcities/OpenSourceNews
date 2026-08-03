# Hermes / Agency integration (pull-first)

OpenSourceNews is the public **sensor**. Hermes Agency is the private **brain**.

## Current status (2026-08-03)

| Item | Status |
|------|--------|
| OpenSourceNews code on branch `hermes/collection-first-sensor` | Done + pushed |
| OpenSourceNews **merged to `main`** | **Not yet** — PR open: https://github.com/MyBlockcities/OpenSourceNews/pull/1 |
| Hermes Agency branch `feature/osn-git-manifest-nightly` | Done + pushed |
| Hermes Agency **merged to `main`** | **Not yet** — PR open: https://github.com/MyBlockcities/hermes-agency/pull/1 |
| `YT_API_KEY` as GitHub Actions **secret** (not in git) | Done (ops) |
| Local Hermes e2e (pull → rank → `news_signals` → ledger) | Verified |
| `com.hermes.osn-nightly` launchd | Installed on this Mac |

**Production GitHub Actions still run the old `main` contract until PR #1 is merged.**

## Division of responsibility

| System | Owns |
|--------|------|
| OpenSourceNews | Discover sources, fetch free metadata, normalize records, stable IDs, manifests, raw history |
| Hermes Agency | Pull reports, deeper fetch, semantic dedupe, local Qdrant embeddings, insights, tutorials, QC, delivery |

## Zero-hosting nightly flow

```text
GitHub Actions (COLLECT_ONLY=1)  @ 07:17 UTC
  → commit outputs/daily/{YYYY-MM-DD}.json
  → commit outputs/manifests/latest.json (includes report_sha256)
        ↓
Local Hermes (~01:40 Mountain / com.hermes.osn-nightly)
  → git pull OpenSourceNews
  → compare report_sha256 to ~/.hermes/news/ingest_ledger.json
  → rank → upsert news_signals → (later) enrich / tutorials
```

No public Hermes webhook is required for this path.  
`YT_API_KEY` lives only in GitHub Actions secrets + optional local `.env` (gitignored) — never in the public tree.

## Implementation checklist

### OpenSourceNews (public sensor)

- [x] `COLLECT_ONLY=1` in daily Actions (`daily.yml` + `pipelines/daily_run.py`)
- [x] Richer free metadata (`published_at`, `fetched_at`, `excerpt`, `author`, …)
- [x] Canonical URL normalization before `signal_id`
- [x] `content_hash` + `enrichment_status: pending`
- [x] Manifest v2 with `report_sha256` (legacy keys preserved)
- [x] Daily cron `17 7 * * *`
- [x] Qdrant-export schedule removed (workflow_run + manual only)
- [x] Video-script workflow manual only
- [x] Gemini Qdrant sync not scheduled
- [x] Canonical/occurrence Qdrant export v2
- [x] Delivery receipts for optional push (`outputs/ingest_receipts/`, gitignored)
- [x] Public integration contract (this document)
- [x] Schema / ID / manifest / dedupe tests
- [x] GitHub trending: description, language, stars today, owner, README excerpt, license, updated_at
- [x] `YT_API_KEY` stored as GitHub Actions secret (not committed)

### Hermes Agency (private brain)

- [x] Git/manifest pull (`hermes/news/git_source.py`)
- [x] Idempotent ledger on `report_sha256` (`hermes/news/ledger.py`)
- [x] `source=git|auto|rest|local` in pull/pipeline/tools
- [x] Nightly CLI (`hermes/news/nightly_pull.py`)
- [x] launchd unit + installer (`ops/launchd/*osn*`)
- [x] Cheap ranking before deep enrich (`hermes/news/rank.py`)
- [x] E2E verified into Qdrant collection `news_signals`

### Remaining steps (do these next)

1. **[ ] Merge OpenSourceNews PR → `main`**  
   https://github.com/MyBlockcities/OpenSourceNews/pull/1  
   Until this lands, scheduled Actions will not use `COLLECT_ONLY`, richer metadata, or the new cron.

2. **[ ] Merge Hermes Agency PR → `main`**  
   https://github.com/MyBlockcities/hermes-agency/pull/1  

3. **[ ] After OSN merge — smoke the Action**  
   Actions → *Daily Research Briefing* → *Run workflow* (or wait for 07:17 UTC).  
   Confirm Alternative News / YouTube items appear (needs the secret you added).  
   Confirm `outputs/manifests/latest.json` has `report_sha256`.

4. **[ ] After both merges — one Hermes pull against `main`**  
   ```bash
   cd /Users/brian/Documents/opensourcenews && git checkout main && git pull
   export OSN_GIT_PATH=/Users/brian/Documents/opensourcenews
   python3 /Users/brian/Documents/hermes_agency/hermes/news/nightly_pull.py --dry-run
   ```

5. **[ ] Later product (not blocking sensor → memory)**  
   Deep LLM enrichment, tutorial critic, Telegram / Buzz / Academy review queue.  
   Optional public webhook only when Hermes has stable HTTPS.

## Discovery contract

1. Read [`outputs/manifests/latest.json`](outputs/manifests/latest.json).
2. If `report_sha256` matches your ledger → **do nothing**.
3. Else fetch `latest_report_path` (or the raw GitHub URL for that file).
4. Rank signals cheaply; upsert / enrich under Hermes-owned embeddings.

### Manifest keys

Legacy keys remain for existing consumers:

- `latest_report_date`
- `latest_report_path`
- `item_count`
- `topics`
- `bucket_counts`
- `generated_at`

Additive v2 keys:

- `schema` = `open_source_news_manifest.v2`
- `report_schema` = `open_source_news_daily_report.v2`
- `report_sha256`
- `report_bytes`
- `unique_signal_count`
- `unique_cluster_count`
- `source_counts`
- `enrichment_pending_count`
- `workflow_run_id`
- `commit_sha`

## Item contract (additive)

Existing daily-report / digest fields stay (`title`, `url`, `summary`, `signal_id`, `cluster_id`, bucket/trust metadata, …).

New collection fields Hermes can use for ranking before deep fetch:

- `published_at`
- `fetched_at`
- `canonical_url`
- `source_domain`
- `excerpt` (short; not full articles)
- `author`
- `content_hash`
- `enrichment_status` (`pending` from Actions)

`signal_id` is derived from **canonical URL + title**. Clean URLs without tracking params keep the same IDs as before. Tracked URL variants collapse onto one ID.

## Existing Academy / God's Eye push

`ACADEMY_INGEST_*` and `GODSEYE_INGEST_*` remain optional in `daily.yml`.  
Digest schema stays `open_source_news_daily_digest.v1` with the same required normalized fields; new sensor fields are additive.

## Hermes Agency nightly puller

```bash
export OSN_GIT_PATH=/Users/brian/Documents/opensourcenews
python3 hermes/news/nightly_pull.py --dry-run
python3 hermes/news/nightly_pull.py --limit 50   # upsert into Hermes Qdrant
bash ops/launchd/install_osn_nightly.sh          # schedule ~01:40 local
```

Ledger: `~/.hermes/news/ingest_ledger.json` keyed by `report_sha256`.  
Default Qdrant collection for news ingest: `news_signals` (override with `--collection`).

## Secrets (public repo)

| Secret | Where | Committed? |
|--------|--------|------------|
| `YT_API_KEY` | GitHub Actions secrets (+ optional local `.env`) | **Never** |
| Academy / God's Eye ingest URLs & tokens | GitHub Actions secrets | **Never** |
| Hermes `QDRANT_*` | `~/.hermes/.env` / Hermes only | **Never** on OpenSourceNews |

## Delivery receipts (optional push)

When `AGENCY_INGEST_URL` / Academy / God's Eye push is configured, local receipts are written to `outputs/ingest_receipts/` (gitignored). Disable with `EXTERNAL_INGEST_RECEIPTS=0`.

## What not to wire on the public repo

Do **not** configure live Hermes secrets here:

- `QDRANT_URL` / `QDRANT_API_KEY` for the private knowledge base
- `GEMINI_API_KEY` for scheduled embedding sync

Keep `npm run export:qdrant` / `npm run export:qdrant:v2` as portable examples. Do not schedule `npm run sync:qdrant` against Hermes.
