# OpenSourceNews → Hermes Pipeline Audit

**Date:** 2026-08-31
**Auditor:** Claude (Opus 5)
**Scope:** Nightly GitHub Actions, generated artifacts, storage locations, Hermes Agency handoff
**Verdict:** **The pipeline is working. Content is flowing into Hermes every night.** But it is degrading silently in several places, and roughly a third of what it produces is never consumed.

**Overall grade: B−**

---

## 1. Executive summary

Answering your three questions directly:

**Are the nightly actions working correctly?**
Yes, mechanically. The last 60 workflow runs are all `success`, and the daily collection has produced a report every single night for 28 consecutive days (2026-08-03 → 2026-08-30), averaging ~518 items/night. But "success" is not the same as "correct" — **13 sources fail silently every night** and the run still exits 0.

**Where is it being saved?**
Committed straight back into this repo under `outputs/`, on `main`. That's the whole delivery mechanism — no S3, no database, no API. Git *is* the transport.

**Is Hermes picking it up?**
Yes. Verified end-to-end. Last night (2026-08-31T07:40:42Z) Hermes pulled report `2026-08-30`, ranked 510 signals, and upserted **510 signals + 2,906 atoms into Qdrant `news_signals`**. The ledger shows 28 consecutive nights with no gaps or double-ingests. The core loop you built this for is genuinely working.

**The three things that actually need attention:**

1. **The health telemetry is lying.** The IntelligenceEnvelope reports `123/123 sources successful, 0 failed` every night — hardcoded, never computed. On a night where 13 sources demonstrably failed, it still reported perfect health.
2. **Nothing alerts.** `MAILAROO_API_KEY` was never set, so the failure-notification step is a no-op. Neo4j silently failed last night and the run still reported SUCCESS.
3. **Five artifact families are produced daily and never read** — including `outputs/envelopes/`, which `HERMES_INTEGRATION.md` calls "the compact Agency ingest contract."

---

## 2. What runs, and when

12 workflows: 6 scheduled, 2 chained, 3 manual, 1 CI guard.

| Workflow | Trigger | Status | Notes |
|---|---|---|---|
| `daily.yml` | `17 7 * * *` | ✅ Working | The main event. ~510 items/night |
| `github-traction.yml` | `47 7 * * *` | ✅ Working | 36/38 repos snapshotted |
| `knowledge-base.yml` | `30 9 * * *` | ⚠️ Orphaned | Output unreachable — see §6 |
| `influencer-discovery.yml` | `20 10 * * *` | ✅ Working | Commits nightly |
| `api-smoke.yml` | `25 12 * * *` | ⚠️ Vacuous | Secrets unset — see §5 |
| `status-summary.yml` | `45 12 * * *` | ✅ Working | |
| `report-manifest.yml` | `workflow_run` | ✅ Working | Chains off daily |
| `qdrant-export.yml` | `workflow_run` | ✅ Working | Chains off daily |
| `security-guard.yml` | push / PR | ✅ Working | |
| `prune-outputs.yml` | manual | 🔴 **Never run** | Retention never applied — see §7 |
| `video-script.yml` | manual | ℹ️ By design | Moved to Hermes (needs local Ollama) |
| `dispatch.yml` | manual | ℹ️ Never run | |

### 2.1 Schedule drift is real and getting worse

`daily.yml` is scheduled for 07:17 UTC. Actual start times:

| Date | Started (UTC) | Drift |
|---|---|---|
| 08-18 → 08-26 | ~07:45–08:03 | +0.5h to +0.8h |
| 08-27 | 18:16 | **+11.0h** |
| 08-28 | 19:25 | **+12.1h** |
| 08-29 | 13:09 | +5.9h |
| 08-30 | 12:51 | +5.6h |
| 08-31 | 15:04 | +7.8h |

This is standard GitHub free-tier scheduler queueing, not a bug in your code — but it has a **real consequence**. Hermes pulls at a fixed 01:40 Mountain (07:40 UTC). Since 08-27, the OSN run finishes *hours after* Hermes has already pulled. So **Hermes is always ingesting yesterday's report**, and the effective content latency is now 24–30 hours rather than the ~20 minutes the architecture diagram implies.

**Grade — scheduling reliability: C+**

---

## 3. What gets generated, and where

Everything lands in `outputs/` and is committed to `main`. Current state:

| Path | Latest | Size | Consumed by Hermes? |
|---|---|---|---|
| `outputs/daily/{date}.json` | 08-30 | 1.25 MB | ✅ **Yes** — primary input |
| `outputs/atoms/{date}.jsonl` | 08-30 | 1.6 MB | ✅ **Yes** — 2,906 → Qdrant |
| `outputs/embedding_ready/{date}.jsonl` | 08-30 | 1.97 MB | ✅ Yes |
| `outputs/manifests/latest.json` | 08-30 | — | ✅ Yes — discovery + idempotency |
| `outputs/topics/{date}.json` | 08-30 | 4.9 KB | ⚠️ Hash only, not ingested |
| `outputs/entities/{date}.json` | 08-30 | 627 KB | ⚠️ Hash only, not ingested |
| `outputs/consensus/{date}.json` | 08-30 | **109 B** | ⚠️ Hash only — **and empty** |
| `outputs/source_trust/{date}.json` | 08-30 | **252 B** | ⚠️ Hash only — **and empty** |
| `outputs/github_traction/latest.json` | 08-30 | — | ⚠️ Hash only |
| `outputs/envelopes/{date}.json` | 08-30 | 475 KB | 🔴 **Never read** |
| `outputs/document_leads/{date}.jsonl` | 08-30 | 105 KB | 🔴 **Never read** |
| `outputs/entity_pages/` | 08-30 | 196 files | 🔴 **Never read** |
| `outputs/briefs/` (4 topics) | 08-30 | 13 MB | 🔴 **Never read** |
| `outputs/knowledge_base/` | — | — | 🔴 **Unreachable** (gitignored) |
| `outputs/transcripts/` | **2026-08-03** | — | 🔴 **Stale 28 days** |

### 3.1 Content volume is healthy and stable

Last 10 nights: 531, 509, 524, 507, 523, 527, 511, 521, 529, 510. No decay.

Collector mix over the last 7 days (3,628 items):

| Collector | Items | Share |
|---|---|---|
| RSS | 1,283 | 35% |
| YouTube | 1,146 | 32% |
| Hacker News | 693 | 19% |
| ClinicalTrials.gov | 271 | 7% |
| GitHub Trending | 140 | 4% |
| PubMed | 95 | 3% |

**Grade — collection volume & stability: A−**

---

## 4. The silent failures

This is the core problem. Every collector wraps its fetch in `except Exception` → `print("ERROR: ...")` → continue. Nothing propagates. The workflow exits 0 and reports green no matter how many sources die.

### 4.1 Thirteen sources failed on last night's run

Pulled directly from the run log for `33406295050` (2026-08-31):

| Source | Failure | Fix |
|---|---|---|
| 8× PubMed queries (BPC-157, GLP-1, KPV, GHK-Cu, NAD+, collagen, thymosin α-1…) | **429 Too Many Requests** | Set `NCBI_API_KEY` + add throttling |
| `erictopol.substack.com` | 403 from runner IP | Fix User-Agent |
| `reuters.com/arc/outboundfeeds/...` | 404 — Reuters killed this feed | Replace source |
| `aiagent.marktechpost.com` | 404 | Remove |
| `rundown.ai/rss` | 404 (redirects to `therundown.ai`) | Fix URL |
| `bis.org/doclist/rss_all_categories.rss` | 404 | Fix URL |
| `unlimitedhangout.com/feed/` | Network unreachable from runner | Investigate/replace |

**The PubMed 429s are the most damaging and the easiest to fix.** Peptides is your single largest bucket (93 items on 08-30), and PubMed is its primary-source backbone — currently contributing only 3% of volume because most queries get rate-limited away.

**Root cause:** `pipelines/daily_run.py` has **zero `time.sleep()` calls anywhere**. It fires 8 PubMed queries × 2 requests each back-to-back. NCBI allows 3 req/sec unauthenticated, 10 req/sec with a key. `_ncbi_params()` (line 364) already supports `NCBI_API_KEY` and `NCBI_EMAIL` — **neither is set as a repo secret.** This is a one-line fix for a meaningful volume gain.

**Secondary cause:** the User-Agent is a placeholder:

```python
# pipelines/daily_run.py:50
"User-Agent": "Mozilla/5.0 (research-bot; +https://github.com/user/repo)"
```

`github.com/user/repo` is not a real URL. Several 403s (Substack, MarkTechPost, artificialintelligence-news) are likely bot-filters reacting to this.

### 4.2 The health block is hardcoded to "everything is fine"

This is the most serious finding in the audit.

`outputs/envelopes/latest.json` — for the same run that logged 13 failures — reports:

```json
"health": {
  "expected_sources": 123,
  "successful_sources": 123,
  "degraded_sources": 0,
  "failed_sources": 0,
  "stale_sources": []
}
```

Cause, in `services/intelligence_envelope.py:128-135`:

```python
"health": health or {
    "expected_sources": len(enabled),
    "successful_sources": len(enabled),   # ← assumes total success
    "degraded_sources": 0,
    "failed_sources": 0,
    "stale_sources": [],
},
```

`scripts/export_intelligence_envelope.py:31` calls `build_envelope()` **without a `health=` argument**, so the optimistic fallback fires unconditionally, every night. The one field designed to let Hermes detect source degradation is a rubber stamp. If half your sources died tomorrow, this would still report 123/123.

**Grade — observability & alerting: D**

### 4.3 Nothing would tell you if it broke

- `MAILAROO_API_KEY` / `MAILAROO_TO_EMAIL` are **not set**. The `Notify on failure` step in `daily.yml` checks `if [ -n "$MAILAROO_API_KEY" ]` and silently skips. **There is currently no failure alerting on any workflow.**
- Neo4j **failed on last night's Hermes run** (`Connection refused` on `localhost:7687`) — the graph for 2026-08-30 was never written. The run still logged `SUCCESS · produced 510` and exited 0. Prior 10 nights wrote 507–531 nodes fine, so this is fresh breakage you'd otherwise not have noticed.

---

## 5. Secrets audit

Referenced in workflows vs. actually configured:

| Secret | Status | Impact |
|---|---|---|
| `YT_API_KEY` | ✅ Set | YouTube working (32% of volume) |
| `ACADEMY_INGEST_URL` / `_TOKEN` | ✅ Set | Academy push working |
| `OPENROUTER_API_KEYS` | ⚠️ **Name mismatch** | Workflows reference `OPENROUTER_API_KEY` (singular). **The key is never passed.** Latent — LLM paths are off under `COLLECT_ONLY=1`, but this will bite the moment you enable `ATOMS_LLM=1` |
| `MAILAROO_API_KEY` / `_TO_EMAIL` | 🔴 Missing | **No failure alerting anywhere** |
| `ASSEMBLYAI_API_KEY` | 🔴 Missing | Transcription disabled — `outputs/transcripts/` frozen since 08-03 |
| `NCBI_API_KEY` / `NCBI_EMAIL` | 🔴 Missing | Supported in code, unset → PubMed 429s |
| `API_BASE_URL`, `OPEN_SOURCE_NEWS_API_KEY` | 🔴 Missing | `api-smoke.yml` passes vacuously — it isn't testing anything |
| `GODSEYE_INGEST_URL` / `_TOKEN` | 🔴 Missing | God's Eye push inert |
| `AGENCY_INGEST_URL` / `_BEARER_TOKEN` | ⬜ Missing | Fine — pull-based path is preferred |

Also: **no Actions `vars` are configured at all**, so `LLM_PROVIDER` defaults to `ollama` — which does not exist on GitHub runners — and `ATOMS_LLM` defaults to `0`. Consistent with the collect-only design, but see §6.1 for the downstream consequence.

**Grade — configuration hygiene: C**

---

## 6. Dead derived artifacts

### 6.1 `consensus` and `source_trust` have produced nothing since day one

`outputs/consensus/*.json` is **109 bytes every single day** — `cluster_count: 0`. `outputs/source_trust/*.json` is 252 bytes with `scores: {}`. `ema_state.json` has been `{}` since 2026-08-03.

Traced the full chain:

1. `ATOMS_LLM` var is unset → defaults to `'0'` → atoms extracted deterministically only
2. Deterministic extraction produces **only** `entity` (2,470), `data_point` (253), `url` (183) — verified against `outputs/atoms/latest.jsonl`. **Zero `claim` atoms.**
3. `services/consensus.py:collect_claim_atoms()` filters `atom_type == "claim"` → returns empty
4. `find_consensus()` → 0 clusters
5. `update_from_consensus(state, clusters)` → nothing to update → `source_trust` stays `{}` forever

So cross-source corroboration and source-trust scoring — two of the more valuable features in the design — have **never produced a single data point**. The code is fine; it's starved of input because claim extraction requires an LLM that is switched off.

Compounding this: your `source_trust_methodology.md` and the Hermes contract both treat trust scores as live inputs. They are not.

### 6.2 Five artifact families are produced and never consumed

`hermes/news/artifacts.py:130` defines the sidecar list Hermes reads:

```python
for key in ("topics", "entities", "consensus", "source_trust", "github_traction"):
```

…and `summarize_sidecar_json()` only records **path + sha256** into the ledger. Its own docstring says *"not upserted here."* So even the five sidecars it "reads" contribute nothing to Qdrant, Neo4j, or content generation — they're checksums in a log file.

Never referenced by Hermes at all:

- **`outputs/envelopes/`** — 475 KB/night. `HERMES_INTEGRATION.md` §2b calls this "the compact Agency ingest contract" and states "Agency must validate hashes before embedding or writing Qdrant." **The consumer side was never implemented.** The documented contract and the running code have diverged.
- **`outputs/document_leads/`** — 105 KB/night of extracted public-document links. This is exactly the investigative-research raw material the system was built to surface.
- **`outputs/entity_pages/`** — 196 files, top-50 entities refreshed nightly.
- **`outputs/briefs/`** — mission briefs for `ai_agent_infra`, `health_wellness_peptides`, `investigative_documents`, `real_estate_tokenization`. Generated fresh every night (confirmed 08-30), 13 MB accumulated. **This is the most content-ready artifact in the entire repo and nothing reads it.**
- **`outputs/knowledge_base/`** — `knowledge-base.yml` runs nightly and uploads to an Actions artifact with `retention-days: 14`. But `outputs/knowledge_base/` is in `.gitignore`, and Hermes pulls **via git**. The output is structurally unreachable by the consumer and expires after two weeks. This workflow has been running nightly for weeks producing nothing anyone can use.

### 6.3 The knowledge-base bridge is a pinhole

Every night: `"kb_bridge": {"bridged": 2, "cap": 20}`. Exactly **2 items out of ~510** reach `hermes_knowledge_v2` — 0.4%, against a cap of 20 that is itself only 4%. Whatever filter governs this is far too narrow. This is the narrowest point in the entire pipe between collection and your content systems.

**Grade — derived artifact utilization: D+**

---

## 7. Repo hygiene

The repo is **764 MB** — 251 MB `.git`, 236 MB working `outputs/`.

| Directory | Size |
|---|---|
| `outputs/qdrant_export` | 68 MB |
| `outputs/embedding_ready` | 47 MB |
| `outputs/daily` | 43 MB |
| `outputs/atoms` | 39 MB |
| `outputs/briefs` | 13 MB |

Two compounding problems:

1. **`outputs/qdrant_export/` is in `.gitignore` but the files are still tracked.** `git ls-files` confirms `news_signals_v2_occurrences.jsonl` (27 MB) is under version control. Gitignore does not apply retroactively to tracked files — so a 27 MB binary-ish blob is **rewritten and recommitted every single night**, and every version is permanent in history. This alone accounts for much of the 251 MB `.git`.

2. **`prune-outputs.yml` has never run.** It's `workflow_dispatch`-only with sensible defaults (`keep_days: 120`, `keep_daily_min: 60`), but nobody has ever triggered it. There are 210 daily reports going back to 2025-10-04.

At the current rate the repo grows ~30–50 MB/night in history. Clone times and Actions checkout times will keep climbing. Worth noting this is a public repo — the growth is on GitHub's free tier, which does have soft limits.

Also: **121 missing days** between 2025-10-28 and 2026-07-09, in a distinctive every-other-day pattern through Nov 2025–Apr 2026. That predates the current architecture and the Hermes ledger (which starts 2026-08-03 and is complete), so it's historical rather than active — but the daily archive is not the continuous series it appears to be.

**Grade — repo hygiene: D+**

---

## 8. What's genuinely working well

Worth stating plainly, because the list above is all problems:

- **Idempotency is solid.** The `report_sha256` ledger at `~/.hermes/news/ingest_ledger.json` has 29 entries across 28 distinct dates with zero double-ingests and zero gaps since 08-03. The manifest → hash → ledger design works exactly as specified.
- **The collect-first security boundary is correctly enforced.** No `QDRANT_API_KEY`, `SUPABASE_SECRET_KEY`, or service-role key is present in Actions. The public repo genuinely cannot write to private stores. This was the right call and it holds.
- **Item schema is rich and stable.** Every item carries `signal_id`, `cluster_id`, `content_hash`, `source_tier`, `permitted_use`, `corroboration_required`, `automatic_content_eligible`. That's a well-designed contract for downstream routing.
- **Volume is stable.** ~518 items/night ±12 over 10 days, no decay.
- **Git-as-transport was a good architectural choice.** No webhook, no tunnel, no public Hermes endpoint, no Railway dependency. It's auditable, replayable, and free.
- **The Hermes consumer runs reliably.** launchd `com.hermes.osn-nightly` fires at 01:40 MT and has completed successfully 28 nights running.

**Grade — architecture & contract design: A−**
**Grade — core Hermes handoff (signals + atoms → Qdrant): B+**

---

## 9. Grades

| Area | Grade | One-line rationale |
|---|---|---|
| Architecture & contract design | **A−** | Clean separation, idempotent, correct security boundary |
| Collection volume & stability | **A−** | 28/28 nights, ~518 items, no decay |
| Core Hermes handoff | **B+** | Signals + atoms reach Qdrant nightly, verified |
| Schedule reliability | **C+** | Up to +12h drift → consumer always a day behind |
| Configuration hygiene | **C** | 9 missing secrets, 1 name mismatch, 0 vars set |
| Source health | **C−** | 13/123 enabled sources failing silently every night |
| Derived artifact utilization | **D+** | 5 families produced and never consumed |
| Observability & alerting | **D** | Health block hardcoded to success; no alerting at all |
| Repo hygiene | **D+** | 764 MB, gitignored-but-tracked blobs, prune never run |
| **Overall** | **B−** | **Working pipeline, silently degrading, half-consumed** |

---

## 10. Recommended fixes, in priority order

### P0 — do before adding any new sources

1. **Fix the health block.** Thread real per-source fetch results into `build_envelope(health=...)` in `services/intelligence_envelope.py`. Until this is honest, you cannot tell whether a new source is working, and you will be adding sources blind.
2. **Add failure alerting.** Set `MAILAROO_API_KEY` + `MAILAROO_TO_EMAIL`. The code path already exists and is tested — it's purely a missing secret.
3. **Fail the run on source-failure thresholds.** Have `daily_run.py` collect failures and exit non-zero above, say, 10% failed sources. Silent green is what let 13 dead sources persist unnoticed.

### P1 — recover lost volume (cheap, high yield)

4. **Set `NCBI_API_KEY` + `NCBI_EMAIL`.** Already supported at `daily_run.py:364`. Raises 3→10 req/sec and should recover most of the 8 failing PubMed queries in your largest bucket.
5. **Add throttling.** There is no `time.sleep()` anywhere in `daily_run.py`. Add a per-host rate limiter.
6. **Fix the User-Agent.** Replace `https://github.com/user/repo` with the real repo URL. Likely clears several 403s.
7. **Fix or retire the 5 dead URLs** (Reuters, `aiagent.marktechpost`, `rundown.ai`, `bis.org`, `unlimitedhangout`).
8. **Rename the OpenRouter secret** to `OPENROUTER_API_KEY` (or update the workflow refs). This is a landmine for the moment you enable LLM atoms.

### P2 — connect what's already being produced

9. **Wire `outputs/briefs/` into Hermes.** This is the highest-leverage single change in the document — daily mission briefs across your four core topics, fully generated, currently going nowhere.
10. **Implement envelope consumption** in `hermes/news/artifacts.py`, or amend `HERMES_INTEGRATION.md` to stop describing it as the active contract. Right now the doc and the code disagree.
11. **Wire `outputs/document_leads/`** — 105 KB/night of public-document links feeding your investigative bucket.
12. **Raise the `kb_bridge` cap and widen its filter.** 2 of 510 is not a bridge.
13. **Un-gitignore `outputs/knowledge_base/`** or switch Hermes to fetch the Actions artifact. As built, that workflow's output is unreachable.

### P3 — hygiene

14. **`git rm --cached outputs/qdrant_export/`** to stop recommitting 27 MB nightly. (History rewrite is a separate, larger decision.)
15. **Run `prune-outputs.yml`** — dry-run first, then apply.
16. **Enable `ATOMS_LLM=1`** if you want consensus and source-trust to ever produce data. Without claim atoms they will stay empty permanently.
17. **Consider moving the schedule earlier** (e.g. `17 3 * * *`) or having Hermes pull on a "new commit detected" trigger rather than a fixed clock, to close the 24–30h latency gap.
18. **Restart Neo4j** and add a liveness check — last night's graph write was lost.

---

## 11. Notes for source expansion

You mentioned wanting to plan new ingestion sources. Three things from this audit that should shape that plan:

**First — fix health reporting before you add anything.** With the health block hardcoded to success and no alerting, a newly added source that silently 403s is indistinguishable from one that's working. You'd be adding sources into a system that cannot tell you whether they took.

**Second — there is a hard cap of 5 items per source per run.** Every collector (`fetch_rss`, `fetch_pubmed_query`, `fetch_clinical_trials_query`, GitHub trending, HN) uses `limit=5` or `[:5]`. That's why so many sources land on exactly 35 items over 7 days. Consequence: **adding sources is currently the only way to increase volume** — you cannot get more from existing high-quality feeds without raising that cap. Worth deciding deliberately whether you want breadth (more sources) or depth (higher cap on good ones). Right now the architecture only offers breadth.

**Third — you already have 54 sources staged and disabled**, plus 13 enabled-but-broken. Before adding new ones, there's meaningful latent capacity sitting in the registry:

| File | Disabled | Notable |
|---|---|---|
| `social_watch.yaml` | 18 | All `x_*` — X killed free RSS; these need a paid API or Nitter and will not work as-is |
| `investigative_documents.yaml` | 11 | Corbett Report, MuckRock, National Security Archive, DDoSecrets |
| `panama_latam.yaml` | 6 | Gaceta Oficial, PanamaCompra OCDS, INEC, SMV |
| `regulation_companies.yaml` | 5 | **SEC EDGAR, OFAC, FinCEN, FINRA, CFTC** — T0 primary regulator records |
| `macro_markets.yaml` | 4 | BLS, BEA, ECB, IMF |
| `ai_agents.yaml` | 3 | **Anthropic, Meta AI, Mistral** — T1 official lab sources |
| `ai_experts.yaml` | 3 | Simon Willison, Import AI, Chip Huyen |

The regulator group (SEC EDGAR, OFAC, FinCEN, FINRA, CFTC) and the AI-lab group (Anthropic, Meta AI, Mistral) are the highest-value quick wins — T0/T1 tier, `automatic_evidence_promotion: true`, and mostly just marked `enabled: false` pending a yield review that never happened. Simon Willison's feed in particular is a `rss` adapter against a working Atom endpoint and would likely light up immediately.

Note that 20 of the disabled entries use the `site_change` adapter and 17 use `manual_link_watch` — those need collector work, not just an `enabled: true` flip. `collectors/site_change.py` exists; `manual_link_watch` appears to have no collector at all.

**Suggested sequence:** fix health reporting → flip on the ~11 regulator + AI-lab sources → confirm they land via honest health metrics → then plan genuinely new sources against a system that can actually tell you what's working.

---

## Appendix — verification commands

```bash
# Confirm Hermes ingested last night
python3 -c "import json; d=json.load(open('$HOME/.hermes/news/ingest_ledger.json')); \
  r=sorted(d['by_sha256'].values(), key=lambda x: x.get('processed_at','')); \
  print(r[-1]['report_date'], r[-1]['item_count'], r[-1]['processed_at'])"

# Count silent source failures in the latest run
gh run list --workflow=daily.yml --limit 1 --json databaseId -q '.[0].databaseId' \
  | xargs -I{} gh run view {} --log | grep -c "ERROR:"

# Verify the health block against reality
python3 -c "import json; print(json.load(open('outputs/envelopes/latest.json'))['health'])"

# Confirm consensus is still empty
cat outputs/consensus/latest.json

# List gitignored-but-tracked blobs
git ls-files outputs/qdrant_export/
```
