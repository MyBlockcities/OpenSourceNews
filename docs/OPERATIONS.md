# Operations Guide

Day-to-day running of the OpenSourceNews collector. Companion to
[`HERMES_CONTRACT.md`](../HERMES_CONTRACT.md) (what we publish) and
[`HERMES_INTEGRATION.md`](../HERMES_INTEGRATION.md) (how Hermes consumes it).

---

## Nightly schedule

| Workflow | Cron (UTC) | Purpose |
|---|---|---|
| `daily.yml` | `17 7 * * *` | Collect → atoms → envelope → manifest → commit → health gate |
| `github-traction.yml` | `47 7 * * *` | Repo star/fork snapshots |
| `knowledge-base.yml` | `30 9 * * *` | KB build (artifact only — see *Known gaps*) |
| `influencer-discovery.yml` | `20 10 * * *` | Influencer discovery |
| `api-smoke.yml` | `25 12 * * *` | API smoke test |
| `status-summary.yml` | `45 12 * * *` | Output status summary |
| `report-manifest.yml` / `qdrant-export.yml` | `workflow_run` | Chained off `daily.yml` |
| `prune-outputs.yml` / `video-script.yml` / `dispatch.yml` | manual | Not scheduled |

### Expect schedule drift

GitHub's free-tier scheduler queues cron jobs under load. Observed drift on
`daily.yml` ranged from **+0.5 h to +12.1 h** in August 2026. This is normal and
not a bug in this repo.

It matters because the Hermes consumer runs on a fixed local timer
(`com.hermes.osn-nightly` at 01:40 Mountain / 07:40 UTC). When drift exceeds
~20 minutes, Hermes ingests the **previous** day's report. Under heavy drift the
effective content latency is 24–30 h.

If latency matters more than clock alignment, move Hermes to trigger on "new
commit on `main`" rather than a fixed time.

---

## Source health

The nightly run writes `outputs/source_health/{date}.json` and `latest.json`:

```bash
python3 -c "import json;print(json.load(open('outputs/source_health/latest.json'))['failed_sources'])"
```

Collectors deliberately swallow per-source errors so one dead feed cannot abort
the run. The gate makes that visible instead of silent:

```bash
python scripts/check_source_health.py           # exit 1 if over threshold
SOURCE_HEALTH_MAX_FAILED_PCT=5 python scripts/check_source_health.py
```

Defaults: fail above **10%** failed sources or **25** absolute. Tune via repo
variables `SOURCE_HEALTH_MAX_FAILED_PCT` / `SOURCE_HEALTH_MAX_FAILED_ABS`.

The gate runs **after** the commit step on purpose: a degraded run still
publishes what it collected, it just stops reporting a clean bill of health.

---

## Adding a source

1. Add a `source_definition.v1` block to the right file in `config/sources/`.
2. **Use a stable ID, not a handle.** For YouTube this means the `UC…` channel
   ID. `resolve_channel_id()` resolves handles through the YouTube *search* API
   and takes the first hit, which drifts — this silently collected the wrong
   channel for months. Resolve once:
   ```bash
   curl -s -A "Mozilla/5.0" https://www.youtube.com/@HANDLE \
     | grep -o '"externalId":"UC[^"]*"' | head -1
   ```
3. Pick the tier honestly — see `config/source_policy.yaml`. T0/T1 can
   auto-promote to evidence; T4 is discovery-only; **T5 must stay
   `enabled: false`** (the validator enforces this).
4. Validate and recompile:
   ```bash
   python scripts/validate_sources.py
   python scripts/compile_feeds_compat.py --write
   python scripts/compile_feeds_compat.py --check
   ```
5. After three nights, confirm it is actually producing:
   ```bash
   python3 - <<'EOF'
   import json,glob,collections
   c=collections.Counter()
   for f in sorted(glob.glob('outputs/daily/*.json'))[-3:]:
       for _,items in json.load(open(f)).items():
           for it in items: c[it.get('source_id')]+=1
   print(c.get('YOUR_SOURCE_ID', 0), 'items in last 3 reports')
   EOF
   ```
   Zero items means broken, not quiet.

### Per-source cap

Every collector is capped at **5 items per source per run** (`limit=5` / `[:5]`
in `pipelines/daily_run.py`). A channel posting three times a day and one
posting weekly contribute identically. Adding sources is currently the only way
to increase volume — raising the cap for T0–T2 sources is the alternative if you
want depth instead of breadth.

---

## Rate limiting

`HOST_MIN_INTERVAL_SECONDS` (default `0.7`) sets a per-host minimum spacing via
`_throttle()`. Before it existed the run fired every request back to back, which
is what produced nightly NCBI 429s across all eight PubMed queries.

For PubMed specifically, set the `NCBI_API_KEY` and `NCBI_EMAIL` secrets — this
raises NCBI's limit from 3 to 10 req/sec. `_ncbi_params()` picks them up
automatically.

---

## Required secrets

| Secret | Status | Without it |
|---|---|---|
| `YT_API_KEY` | ✅ set | No YouTube collection (~32% of volume) |
| `ACADEMY_INGEST_URL` / `_TOKEN` | ✅ set | Academy push disabled |
| `OPENROUTER_API_KEYS` | ✅ set | LLM paths disabled (fine under `COLLECT_ONLY=1`) |
| `MAILAROO_API_KEY` / `MAILAROO_TO_EMAIL` | ❌ **missing** | **No failure alerting at all** |
| `NCBI_API_KEY` / `NCBI_EMAIL` | ❌ missing | PubMed 429s; ~8 queries lost per night |
| `ASSEMBLYAI_API_KEY` | ❌ missing | Transcription disabled |
| `API_BASE_URL` / `OPEN_SOURCE_NEWS_API_KEY` | ❌ missing | `api-smoke.yml` passes without testing anything |

> The workflow references `secrets.OPENROUTER_API_KEYS` (plural) to match the
> configured secret name. Keep them in sync — a mismatch fails silently because
> the expression falls through to `''`.

**Never add** `QDRANT_API_KEY`, `SUPABASE_SECRET_KEY`, or
`SUPABASE_SERVICE_ROLE_KEY` here. This is a public repo running a collect-only
sensor; private stores are written by Hermes, not by Actions.

---

## Repo size

The repo is ~764 MB (251 MB `.git`, 236 MB working `outputs/`).

The dominant cost is `outputs/qdrant_export/` — **~68 MB rewritten every
night**. It is listed in `.gitignore`, but `qdrant-export.yml` force-adds it:

```yaml
git add -f outputs/qdrant_export/*.jsonl outputs/qdrant_export/*.manifest.json
```

**Nothing in Hermes reads it** (`hermes/news/` has zero references), and it is
fully regenerable from `outputs/embedding_ready/`. If no external consumer
depends on it, dropping the force-add is the single largest size win available:

```bash
# stop committing it going forward
git rm --cached outputs/qdrant_export/*.jsonl outputs/qdrant_export/*.manifest.json
# then delete the `git add -f` line from .github/workflows/qdrant-export.yml
```

This is an outward-facing change on a public repo — confirm nobody consumes
those files first. Past commits keep the blobs either way; only a history
rewrite reclaims that space.

**Retention** — `prune-outputs.yml` exists but has never run. Dry-run first:

```
Actions → Prune Generated Outputs → Run workflow
  apply: false   keep_days: 120   keep_daily_min: 60
```

---

## Known gaps

| Gap | Effect | Fix |
|---|---|---|
| `consensus` / `source_trust` always empty | No cross-source corroboration or trust scores, ever | Deterministic extraction emits no `claim` atoms. Set repo variable `ATOMS_LLM=1` |
| `outputs/knowledge_base/` unreachable | KB built nightly, expires in 14 days, no consumer can read it | It is gitignored but only uploaded as an Actions artifact. Either un-ignore it or have Hermes fetch the artifact |
| `briefs`, `envelopes`, `document_leads`, `entity_pages` uncommitted upstream of any reader | Produced daily, read by nothing | Wire them into `hermes/news/artifacts.py` |
| `kb_bridge` bridges 2 of ~510 items | Narrowest point in the pipe to content generation | Widen the filter / raise the cap in Hermes |
| No failure alerting | A broken night is invisible | Set `MAILAROO_*` secrets |

See [`../PIPELINE_AUDIT_2026-08-31.md`](../PIPELINE_AUDIT_2026-08-31.md) for the
full analysis and grades.

---

## Verification one-liners

```bash
# Did Hermes ingest last night?
python3 -c "import json;d=json.load(open('$HOME/.hermes/news/ingest_ledger.json'));\
r=sorted(d['by_sha256'].values(),key=lambda x:x.get('processed_at',''));\
print(r[-1]['report_date'], r[-1]['item_count'], r[-1]['processed_at'])"

# How many sources failed in the latest Actions run?
gh run list --workflow=daily.yml --limit 1 --json databaseId -q '.[0].databaseId' \
  | xargs -I{} gh run view {} --log | grep -c "ERROR:"

# Is the envelope health real or unavailable?
python3 -c "import json;print(json.load(open('outputs/envelopes/latest.json'))['health'])"

# Which registered sources produced nothing in 14 days?
python3 -c "
import yaml,glob,json,collections
reg={s['id'] for f in glob.glob('config/sources/*.yaml')
     for s in (yaml.safe_load(open(f)).get('sources') or []) if s.get('enabled')}
act=collections.Counter()
for f in sorted(glob.glob('outputs/daily/*.json'))[-14:]:
    for _,items in json.load(open(f)).items():
        for it in items: act[it.get('source_id')]+=1
print(sorted(reg-set(act)))"
```
