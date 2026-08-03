# Hermes ↔ OpenSourceNews integration

**Canonical public repo:** https://github.com/MyBlockcities/OpenSourceNews (`main`)

OpenSourceNews is the public **sensor**. Hermes Agency is the private **brain**.

| System | Owns |
|--------|------|
| **OpenSourceNews** (`main`) | Discover sources, fetch free metadata, normalize records, stable IDs, manifests, raw git history |
| **Hermes Agency** | Pull reports, rank signals, embed into Qdrant, deeper enrichment, insights, tutorials, QC, delivery |

---

## Live status

| Item | Status |
|------|--------|
| Collection-first code on **`main`** | **Shipped** — https://github.com/MyBlockcities/OpenSourceNews/commit/6630835 |
| Daily Actions `COLLECT_ONLY=1` | Active on `main` (`.github/workflows/daily.yml`) |
| Schedule | `17 7 * * *` UTC (~01:17 MDT / ~00:17 MST) |
| `YT_API_KEY` | GitHub Actions **secret** only (not in git). Confirmed present. |
| Manifest contract | `outputs/manifests/latest.json` includes `report_sha256` |
| Hermes pull path | Git clone/pull + ledger (no public Hermes webhook required) |
| Hermes Qdrant collection | `news_signals` (Hermes-owned embeddings; not Gemini sync from this repo) |
| Academy / God's Eye push | Optional via Actions secrets; digest schema stays `open_source_news_daily_digest.v1` |

---

## Nightly architecture (pull-first)

```text
GitHub Actions @ 07:17 UTC
  COLLECT_ONLY=1
  → fetch RSS / HN / GitHub / YouTube / PubMed / ClinicalTrials
  → normalize + signal_id / cluster_id
  → commit outputs/daily/{YYYY-MM-DD}.json
  → mission briefs
        ↓
  report-manifest.yml → outputs/manifests/latest.json (+ report_sha256)
  qdrant-export.yml   → v1 + v2 JSONL (no embeddings)
        ↓
Hermes (local) ~01:40 Mountain — com.hermes.osn-nightly
  → git pull https://github.com/MyBlockcities/OpenSourceNews
  → read latest.json
  → if report_sha256 already in ~/.hermes/news/ingest_ledger.json → exit
  → cheap-rank signals → upsert Qdrant news_signals
  → (later) deep enrich / tutorials / Telegram·Buzz·Academy queue
```

This avoids a publicly reachable Hermes webhook, Railway API, or tunnel for v1.

---

## What Hermes should do every night

### 1. Clone / pull the public repo

Recommended stable path:

```bash
export OSN_GIT_PATH=/Users/brian/Documents/opensourcenews
# or: ~/Projects/OpenSourceNews
cd "$OSN_GIT_PATH" && git checkout main && git pull --ff-only origin main
```

### 2. Discover via manifest (idempotent)

```bash
cat outputs/manifests/latest.json
```

| Field | Hermes use |
|-------|------------|
| `report_sha256` | Skip if already in ledger |
| `latest_report_path` | Load that JSON |
| `latest_report_date` | Dating / labeling |
| `item_count` / `source_counts` / `enrichment_pending_count` | Health checks |
| `bucket_counts` | Routing hints |

**Ledger rule**

- Same `report_sha256` → do nothing  
- New hash → process  
- Same date, different hash → reconcile / reprocess  

Ledger file (Hermes-private): `~/.hermes/news/ingest_ledger.json`

### 3. Run the Hermes nightly CLI

From the Hermes Agency checkout (after its OSN nightly PR is on `main`, or from the feature branch already verified locally):

```bash
export OSN_GIT_PATH=/Users/brian/Documents/opensourcenews
export OSN_GIT_PULL=1

python3 hermes/news/nightly_pull.py --dry-run
python3 hermes/news/nightly_pull.py --collection news_signals
# Optional smoke:
python3 hermes/news/nightly_pull.py --force --limit 20 --collection news_signals
```

Schedule (already installable):

```bash
bash ops/launchd/install_osn_nightly.sh   # ~01:40 local
# Logs: ~/Library/Logs/Hermes/osn_nightly*.log
```

### 4. Rank before deep spend

Hermes should prefer free metadata already in each signal:

- HN: `points`, `num_comments`, `author`, `created_at` / `published_at`
- GitHub: `stars_today`, `stargazers_count`, `primary_language`, `license`, `updated_at`, `readme_excerpt`
- Peptides: `trust_layer`, `evidence_level`, PubMed / ClinicalTrials fields
- All: `excerpt`, `canonical_url`, `content_hash`, `enrichment_status`

Built-in helper: `hermes/news/rank.py` → `select_top_signals(...)`.

---

## Public contracts Hermes can trust

### Manifest (`open_source_news_manifest.v2`)

Legacy keys (keep working for Academy / dashboards):

- `latest_report_date`, `latest_report_path`, `item_count`, `topics`, `bucket_counts`, `generated_at`

Additive:

- `schema`, `report_schema`, `report_sha256`, `report_bytes`
- `unique_signal_count`, `unique_cluster_count`, `source_counts`
- `enrichment_pending_count`, `workflow_run_id`, `commit_sha`

### Daily items (additive; Academy digest still v1)

Always present for consumers: `title`, `url`, `summary`, `signal_id`, `cluster_id`, `source`, `bucket`, …

Sensor fields for Hermes ranking:

| Field | Meaning |
|-------|---------|
| `url` | Original source URL |
| `canonical_url` | Tracking-stripped URL used for IDs |
| `source_domain` | Host without `www.` |
| `published_at` | Publisher time when known |
| `fetched_at` | Collection time (UTC) |
| `excerpt` | Short free text (~500–1500 chars), **not** full articles |
| `author` | Author / channel / owner when known |
| `content_hash` | Fingerprint of canonical URL + title + excerpt |
| `enrichment_status` | `pending` from Actions; Hermes updates privately |

`signal_id` = SHA256(`canonical_url` + `"\n"` + `title`)[:16].  
Clean URLs keep historical IDs; UTM/gclid/fbclid variants collapse.

### Qdrant exports (optional; Hermes may ignore)

- **v1** (unchanged): `npm run export:qdrant` — occurrence IDs per day  
- **v2**: `npm run export:qdrant:v2` — canonical + occurrence IDs; `embedding_text` left empty for Hermes models  

Do **not** run `npm run sync:qdrant` against Hermes memory (Gemini / foreign dimensions).

### MCP / raw GitHub

```bash
# Raw report
curl -sL https://raw.githubusercontent.com/MyBlockcities/OpenSourceNews/main/outputs/manifests/latest.json

# Local MCP over the clone
cd /Users/brian/Documents/opensourcenews && python3 -m mcp.server
```

---

## Secrets & privacy

| Secret | Where | In public git? |
|--------|--------|----------------|
| `YT_API_KEY` | GitHub Actions secrets (+ optional local `.env`) | **Never** |
| `ACADEMY_INGEST_*` / `GODSEYE_INGEST_*` | Actions secrets | **Never** |
| Hermes `QDRANT_URL` / `QDRANT_API_KEY` | `~/.hermes/.env` only | **Never on this repo** |
| Private prompts, XO Pure deals, buyer names | Hermes only | **Never** |

Watchlists in this repo stay **generalized** (AI agents, RWA, peptides). Private strategy stays in Hermes.

---

## OpenSourceNews checklist (shipped on `main`)

- [x] `COLLECT_ONLY=1` on Actions
- [x] Richer free metadata + excerpts
- [x] Canonical URLs before `signal_id`
- [x] Manifest `report_sha256`
- [x] Cron `17 7 * * *`
- [x] Qdrant-export: no duplicate scheduled cron
- [x] Video-script: manual only
- [x] No scheduled Gemini Qdrant sync
- [x] Qdrant export v2
- [x] Delivery receipts for optional push (gitignored)
- [x] This integration document
- [x] Schema / ID / manifest / dedupe tests
- [x] `YT_API_KEY` as Actions secret
- [x] Merged to `main`

---

## Remaining steps (Hermes ops / product)

1. **[ ] Keep local clone on `main`**
   ```bash
   cd /Users/brian/Documents/opensourcenews && git pull origin main
   ```

2. **[ ] Merge Hermes Agency PR** (if not already):  
   https://github.com/MyBlockcities/hermes-agency/pull/1  
   Local Hermes already has the puller/ledger/ranker verified; merging publishes it for the rest of the team.

3. **[ ] Confirm first post-merge daily run**  
   After 07:17 UTC (or Actions → *Daily Research Briefing* → *Run workflow*):  
   - YouTube / Alternative News should populate (uses `YT_API_KEY`)  
   - New `outputs/daily/{date}.json` + refreshed `latest.json` with `report_sha256`

4. **[ ] Hermes consume that report**
   ```bash
   python3 hermes/news/nightly_pull.py --dry-run
   python3 hermes/news/nightly_pull.py --collection news_signals
   ```

5. **[ ] Later (content factory)**  
   Deep LLM enrichment, critic pass, Telegram / Buzz / Academy review queue.  
   Optional `AGENCY_INGEST_URL` webhook only when Hermes has stable public HTTPS — pull + hash remain the reliability baseline.

---

## Quick health commands

```bash
# Public sensor
curl -sL https://raw.githubusercontent.com/MyBlockcities/OpenSourceNews/main/outputs/manifests/latest.json | python3 -m json.tool | head -40

# Local tests
cd /Users/brian/Documents/opensourcenews
python3 -m pytest tests/test_news_schema.py tests/test_collection_first.py -q

# Hermes dry-run
OSN_GIT_PATH=/Users/brian/Documents/opensourcenews OSN_GIT_PULL=0 \
  python3 /Users/brian/Documents/hermes_agency/hermes/news/nightly_pull.py --dry-run
```
