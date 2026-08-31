# OpenSourceNews → Hermes Agency Brief

**Date:** 2026-08-31 · **Repo:** https://github.com/MyBlockcities/OpenSourceNews (`main`)
**Audience:** Hermes Agency (the consumer)

Everything below is live on `main`. Nothing about the pull mechanism changed —
**existing Hermes code keeps working without modification.** Two things you
should change, one bug you should know about, and 18 new sources.

---

## 1. What changed

| # | Change | Why it matters to you |
|---|---|---|
| 1 | **New artifact `outputs/source_health/{date}.json`** | Tells you which sources actually worked. Previously unavailable |
| 2 | **Envelope `health` is now measured, not assumed** | It used to report `123/123 successful, 0 failed` *unconditionally* — on nights when 13 sources were failing. It was never a real signal. Now it is |
| 3 | **Health gate on the nightly run** | Above 10% / 25 failed sources the workflow now fails loudly instead of reporting green |
| 4 | **YouTube channels pinned to `UC…` IDs** | Fixes silent wrong-channel collection — see §3 |
| 5 | **18 sources added, 4 duplicates removed, 6 broken sources fixed or disabled** | See §4 |
| 6 | **Politeness throttle + honest User-Agent** | Recovered 3 previously-dead feeds; should end nightly PubMed 429s |

---

## 2. How to pull (unchanged)

```bash
export OSN_GIT_PATH=/Users/brian/Documents/opensourcenews
cd "$OSN_GIT_PATH" && git checkout main && git pull --ff-only origin main
cat outputs/manifests/latest.json
```

Ledger rule is unchanged: skip if `report_sha256` is already in
`~/.hermes/news/ingest_ledger.json`; process on a new hash; reconcile if the
same date returns a different hash.

### New: check health before you trust a run

```python
import json, pathlib

root = pathlib.Path(OSN_GIT_PATH)
health = json.loads((root / "outputs/source_health/latest.json").read_text())

failed   = health["failed_sources"]
expected = health["expected_sources"]

if expected and failed / expected > 0.10:
    # Still ingest — just don't treat a missing topic as signal today.
    mark_run_degraded(health["failures"])
```

The same numbers appear in `outputs/envelopes/{date}.json` under `health`, with
a `health_source` field:

- `"source_health.v1"` → real measured health.
- `"unavailable"` → snapshot missing; `successful_sources`, `degraded_sources`
  and `failed_sources` are **`null`**.

> **`null` means unknown, not zero.** Do not coerce it into a clean run. This is
> exactly the bug we just fixed on our side — don't reintroduce it on yours.

---

## 3. ⚠️ Attribution bug — action required on your side

`pipelines/youtube.py:resolve_channel_id()` resolved bare `@handles` through the
YouTube **search** API and took the first result. Search ranking drifts, so
several sources quietly collected the wrong channel:

| Config said | Actually collected |
|---|---|
| Wes Roth | **Matt Wolfe** |
| Matt Wolfe | **WorldofAI** |
| WorldofAI | **Matthew Berman** |
| Matthew Berman | **VRSEN** |
| AI Explained | an unrelated channel |
| Bloomberg Television | a personal vlog |

All are now pinned to `UC…` IDs and fixed going forward. But:

### Rule: `author` is authoritative, not `publisher`

For YouTube items, `publisher` is a **static label from our source registry**,
while `author` comes from the **fetched feed**. When they disagree, `author` is
correct.

```python
# Correct attribution
creator = item.get("author") or item.get("publisher")
```

**Use `author` for anything that reaches published content.** Attributing a
quote to the wrong creator is a credibility problem, not a cosmetic one.

### Historical data needs repair

Every `outputs/daily/*.json` **before 2026-08-31** carries mis-attributed
`publisher` values for the channels above — and those records are already in
Qdrant `news_signals`. The `author` field in the same records is correct, so
this is repairable in place; no re-collection needed.

Suggested: re-derive `publisher` from `author` for `source == "YouTube"` and
re-upsert the affected points. Roughly 8 channels × ~28 days × 5 items/day.

---

## 4. Sources added

**Registry: 191 total, 128 enabled** (was 123 enabled).
**Enabled YouTube: 45** (was 35).

### AI — recommended additions

| Channel | `source_id` | Tier | Why |
|---|---|---|---|
| Cole Medin | `yt_cole_medin` | T4 | Production agent engineering, RAG, MCP, local models |
| AI Engineer | `yt_ai_engineer` | T3 | Conference talks — dense, citable, best KB material of the set |
| Sam Witteveen | `yt_sam_witteveen` | T4 | Code-first, early on new model/agent releases |
| Greg Isenberg | `yt_greg_isenberg` | T4 | AI business models, productized services |
| bycloud | `yt_bycloud` | T4 | Research-to-practice; catches capability shifts early |

### AI — from the priority list

| Channel | `source_id` | Note |
|---|---|---|
| Wes Roth | `yt_wes_roth` | **Now actually collected** — the slot previously fetched Matt Wolfe |
| AI LABS | `yt_ai_labs` | New |
| Riley Brown | `yt_riley_brown` | New |
| echohive | `yt_echohive` | New — ⚠️ last upload 46 days ago, expect low volume |

Already collecting (no change needed): IndyDevDan, WorldofAI, VRSEN, Matt Wolfe,
Matthew Berman, All-In, Nate Herk, AI Explained, Two Minute Papers.

### Strategy

| Channel | `source_id` |
|---|---|
| Alex Hormozi | `yt_alex_hormozi` |
| Peter Diamandis | `yt_peter_diamandis` |

### Crypto

| Channel | `source_id` | Tier |
|---|---|---|
| Altcoin Daily | `yt_altcoin_daily` | T4 |
| Solana (official) | `yt_solana_official` | **T2** — official channel, `discovery_and_interpretation` |

Already collecting: Coin Bureau, Bankless, Ivan on Tech, BitBoy X.

### Independent journalism

| Channel | `source_id` | Tier |
|---|---|---|
| Shawn Ryan Show | `yt_shawn_ryan_show` | T4 |
| Ian Carroll | `yt_ian_carroll` | T4 |

### Staged but **NOT** collecting — T5 quarantine

`yt_london_real`, `yt_robert_edward_grant`, `yt_only_the_savvy`,
`yt_newsupdates4real`.

These are configured but `enabled: false`. `scripts/validate_sources.py`
**refuses to let a T5 source run enabled** — that guardrail is deliberate and
predates this work. Activating them is a conscious decision: flip `enabled: true`
and re-tier them, or relax the validator rule.

**If they are ever activated:** `permitted_use: quarantined_discovery` means
discovery only. They must never auto-promote to evidence and must never be cited
as factual support in generated content.

### Removed (were duplicates — silently double-counting)

`yt_coinbureau_id`, `yt_ai_channel_extra`, `yt_bankless_id`,
`yt_johnny_harris_alt` — each was a second copy of a channel already collected,
costing ~25 duplicate items/day.

### Fixed / disabled

| Source | Action |
|---|---|
| `rundown_ai` | URL fixed → `therundown.ai/feed` (was 404). **Recovered** |
| `eric_topol_ground_truths` | Recovered by the User-Agent fix (was 403) |
| `reliefweb_updates` | Recovered by the User-Agent fix |
| `reuters_rss` | Disabled — Reuters retired public RSS |
| `marktechpost`, `ai_news_ainews` | Disabled — 403 to non-browser agents; `robots_policy: obey`, so we don't spoof |
| `marktechpost_agents`, `bis_all` | Disabled — endpoints 404 |

Expect nightly volume to rise from ~510 to roughly **~570–600 items**.

---

## 5. Rules to follow

1. **`author` beats `publisher`** for YouTube attribution. Always.
2. **Check `health` before trusting a run.** `health_source: "unavailable"` and
   `null` counts mean *unknown*, never *clean*.
3. **Respect `permitted_use`.** `discovery_only` and `quarantined_discovery`
   sources cannot establish facts or be cited as evidence, regardless of how
   good the content is. `factual_support` (T0/T1) can.
4. **Respect `corroboration_required: true`.** Most new sources are T4 — they
   need a second, higher-tier source before a claim goes into content.
5. **Unique ingest key stays `(producer, report_hash)`.** Validate artifact
   hashes before embedding.
6. **Never send private keys to this repo.** It is a public, collect-only
   sensor. `QDRANT_API_KEY`, `SUPABASE_SECRET_KEY` and
   `SUPABASE_SERVICE_ROLE_KEY` must never appear in Actions.
7. **Expect the report to be a day old.** Free-tier Actions scheduling drifted
   +0.5 h to +12.1 h in August. Hermes pulls at a fixed 01:40 MT, so it usually
   ingests the *previous* day's report. If latency matters, trigger on "new
   commit on `main`" instead of a fixed clock.
8. **A source at zero items for 3 days is broken, not quiet.** Check
   `source_health` `failures[]` before assuming a topic went silent.

---

## 6. Open items on the Hermes side

Not blocking, but each is unrealized value we're already producing nightly:

| Item | Status |
|---|---|
| `outputs/envelopes/` | **Never read.** `HERMES_INTEGRATION.md` calls it "the compact Agency ingest contract", but no consumer implements it. 475 KB/night |
| `outputs/briefs/` | **Never read.** Mission briefs across all four topics, generated nightly, 13 MB accumulated. Most content-ready artifact we produce |
| `outputs/document_leads/` | **Never read.** 105 KB/night of public-document links for the investigative bucket |
| `outputs/entity_pages/` | **Never read.** Top-50 entities, refreshed nightly |
| `kb_bridge` | Bridges **2 of ~510** items/night against a cap of 20. Narrowest point between collection and content generation |
| Neo4j | Failed on the 2026-08-31 run (`Connection refused`, `localhost:7687`); the graph for 2026-08-30 was never written. The run still reported SUCCESS |
| Sidecars | `topics`, `entities`, `consensus`, `source_trust`, `github_traction` are hashed into the ledger but never ingested |

Also note: `consensus` and `source_trust` have been **empty since day one** —
deterministic atom extraction produces no `claim` atoms, so both artifacts are
structurally empty until `ATOMS_LLM=1` is set. Don't build logic expecting data
there yet.

---

## 7. References

| Doc | Contents |
|---|---|
| `HERMES_CONTRACT.md` | Artifact schemas — now includes §8b source health |
| `HERMES_INTEGRATION.md` | Pull mechanics + the attribution rule |
| `docs/OPERATIONS.md` | Schedules, adding sources, secrets, repo size |
| `PIPELINE_AUDIT_2026-08-31.md` | Full audit with grades (overall B−) |
| `YOUTUBE_SOURCE_AUDIT_AND_ADDITIONS_2026-08-31.md` | Channel-by-channel verification |
