# Hermes Consumer Contract — v1

This document is the **stable API surface** Hermes consumes. Field
additions are backward-compatible; field removals require a major
version bump with a 30-day deprecation window. New files are added
under `outputs/` and announced here.

The repo produces these artifacts. Hermes treats them as inputs.

---

## 1. Daily report (the source of truth)

`outputs/daily/{YYYY-MM-DD}.json`

The raw daily report produced by `pipelines/daily_run.py`. Unchanged
contract — see `services/news_schema.py`. The normalized item shape
remains the public digest v1.

`outputs/manifests/latest.json`

The integration manifest. Now extends v2 with:

```json
{
  "schema": "open_source_news_manifest.v2",
  "report_date": "YYYY-MM-DD",
  "report_sha256": "...",
  "report_bytes": 12345,
  "item_count": 200,
  "unique_signal_count": 187,
  "source_counts": { "RSS": 80, "Hacker News": 40, "...": "..." },
  "atom_count": 814,
  "topic_count": 18,
  "entity_count": 142,
  "consensus_cluster_count": 6,
  "tracked_repo_count": 28,
  "schema_version": "open_source_news_manifest.v2"
}
```

---

## 2. Atoms (the primary Hermes input)

`outputs/atoms/{YYYY-MM-DD}.jsonl` — one atom per line, append-only.
`outputs/atoms/latest.jsonl` — symlink to most recent.

Every record carries `schema_version: "atom.v1"`:

```json
{
  "atom_id":        "uuid5(atom_namespace, parent_signal_id|type|text_hash)",
  "atom_type":      "claim | data_point | tool | framework | entity | prediction | counterexample | reasoning | url",
  "text":           "Atomic statement, one sentence.",
  "polarity":       "supports | neutral | contradicts",
  "evidence_urls":  ["https://...", "..."],
  "extracted_by":   "deterministic | llm",
  "extracted_at":   "2026-08-03T07:18:00Z",
  "parent_signal_id":"16-char sha256 prefix",
  "parent_canonical_url": "https://...",
  "parent_source_domain":  "blog.example.com",
  "parent_bucket":         "ai | peptides | real_estate_tech | ...",
  "parent_topics":         ["AI / AI Tools / AI Agents"],
  "public_topics":         ["ai_agents", "voice_agents"],
  "report_date":           "YYYY-MM-DD",
  "schema_version":        "atom.v1"
}
```

**Guarantees**

- `atom_id` is stable across reruns and machines.
- `parent_signal_id` references the same id used in the daily report.
- `extracted_by` is `deterministic` for the regex-only pass (always runs)
  and `llm` when the optional LLM pass ran. Mixed sets are normal.
- `public_topics` is a sorted list, parents before children.

---

## 3. Embedding-ready (the text Hermes embeds)

`outputs/embedding_ready/{YYYY-MM-DD}.jsonl` — one record per line.
`outputs/embedding_ready/latest.jsonl` — symlink to most recent.

The repo does **not** embed. It produces clean text + provenance so
Hermes can stream-embed in a single pass with the local MiniLM model.

```json
{
  "external_id":    "opensourcenews:atom:{atom_id}",
  "record_type":    "atom | signal",
  "embedding_text": "<clean, clipped text — typically 200-1500 chars>",
  "payload": {
    "schema_version":    "embed_ready.v1",
    "source":            "OpenSourceNews",
    "report_date":       "YYYY-MM-DD",
    "public_topics":     ["ai_agents"],
    "parent_signal_id":  "...",
    "atom_id":           "..." | null,
    "atom_type":         "claim | null",
    "source_domain":     "blog.example.com",
    "url":               "https://...",
    "title":             "..."
  }
}
```

**Embedding model contract (Hermes-side)**

- Vector size: 384
- Distance: cosine
- Embedding model: all-MiniLM (or compatible sentence-transformer)
- Embedding version is recorded by Hermes in its own ledger.

**Storage rule (Hermes-side)**

- `external_id` is Hermes' unique key in Qdrant / SQLite. Re-ingest
  with the same `external_id` is an upsert, not a duplicate.

---

## 4. Topics (the public ontology)

`outputs/topics/{YYYY-MM-DD}.json`
`outputs/topics/latest.json`

```json
{
  "frequency":   {"ai_agents": 47, "real_estate_tech": 12, "...": "..."},
  "cooccurrence":[{"topics": ["ai_agents", "voice_agents"], "count": 9}, "..."],
  "rising":      [{"topic": "voice_agents", "current": 9, "previous": 2, "delta": 7}, "..."],
  "cooling":     [{"topic": "...", "current": 1, "previous": 8, "delta": -7}, "..."],
  "topic_count": 18,
  "schema_version": "topics.v1"
}
```

The ontology itself is `config/topics.yaml`. Additions are PR-reviewable.

---

## 5. Entities (the public registry)

`outputs/entities/{YYYY-MM-DD}.json`
`outputs/entities/latest.json`
`outputs/entity_pages/{slug}.json` — one per entity.

```json
{
  "report_date": "YYYY-MM-DD",
  "entities": [
    {
      "entity_id":     "uuid5 prefix",
      "name":          "Anthropic",
      "slug":          "anthropic",
      "first_seen":    "2026-05-12",
      "last_seen":     "2026-08-03",
      "mention_count_total": 47,
      "mentions_7d_rate": 1.4,
      "mentions_30d_rate": 0.9,
      "trajectory":    "rising | stable | cooling | emerging",
      "source_domains":["blog.anthropic.com", "news.ycombinator.com", "..."],
      "recent_signal_ids": ["...", "..."],
      "schema_version":"entity.v1"
    }
  ],
  "schema_version": "entities.v1"
}
```

**Notes**

- `trajectory = emerging` means < 7 days of history but rising mentions.
- Free-text entity candidates are capped at 15 per signal to bound noise.
- Trajectory is computed from EMA-smoothed 7-day rates.

---

## 6. Consensus (the public truth)

`outputs/consensus/{YYYY-MM-DD}.json`
`outputs/consensus/latest.json`

Clusters of similar claims across sources, with cross-source agreement
scored 0-1.

```json
{
  "report_date": "YYYY-MM-DD",
  "cluster_count": 6,
  "clusters": [
    {
      "cluster_id":     "uuid5 prefix",
      "canonical_text": "MCP is becoming the de facto standard for agent interop",
      "member_count":   4,
      "atom_ids":       ["...", "..."],
      "parent_signal_ids":["...", "..."],
      "source_domains": ["blog.anthropic.com", "github.com", "..."],
      "source_count":   3,
      "polarity_counts": {"supports": 3, "neutral": 1, "contradicts": 0},
      "agreement_score": 0.84,
      "evidence_urls":  ["https://...", "..."],
      "schema_version": "consensus.v1"
    }
  ],
  "schema_version": "consensus.v1"
}
```

**Notes**

- Clustering is text-based (Jaccard on normalized tokens, threshold 0.78).
- Qdrant-side semantic clustering is done by Hermes and may yield finer
  clusters. This file is the deterministic public baseline.
- `agreement_score` is `support_rate - contradict_rate`, scaled by
  source diversity (more distinct sources → stronger).

---

## 7. Source trust (the public reputation ledger)

`outputs/source_trust/{YYYY-MM-DD}.json`
`outputs/source_trust/latest.json`

```json
{
  "report_date": "YYYY-MM-DD",
  "initial_score": 0.5,
  "alpha":        0.10,
  "weights": {
    "corroboration": 0.05,
    "contradiction": 0.15,
    "retraction":    0.25
  },
  "source_topic_count": 84,
  "scores": {
    "anthropic.com::ai_agents": {
      "source": "anthropic.com", "topic": "ai_agents",
      "score": 0.62, "evidence_count": 14
    }
  },
  "schema_version": "source_trust.v1"
}
```

**Algorithm**

- Initial score 0.5 (neutral). Bounded [0.0, 1.0].
- Each corroboration event: `+alpha * 0.05` (small positive)
- Each contradiction event: `-alpha * 0.15`
- Each retraction event:    `-alpha * 0.25`

**Topic**

- The topic `"*"` is the wildcard (source-only trust).
- Per-topic entries are kept for granular sources (e.g. Hacker News
  is high-trust for AI infra, lower for medical content).

---

## 8. GitHub traction (the trending signal)

`outputs/github_traction/{YYYY-MM-DD}.json`        — full snapshot
`outputs/github_traction/latest.json`
`outputs/github_traction/top_this_week.json`       — top 50, quality-gated
`outputs/github_traction/fastest_30d.json`         — 30-90d repos by momentum
`outputs/github_traction/repo_pages/{slug}.json`   — per-repo detail

**Per-repo snapshot**

```json
{
  "snapshot_id":        "uuid5 prefix",
  "repo_id":            "uuid5 prefix",
  "full_name":          "owner/name",
  "report_date":        "YYYY-MM-DD",
  "stars_total":        1234,
  "forks_total":        56,
  "star_velocity_7d":   8.4,
  "star_velocity_30d":  4.2,
  "acceleration":       1.0,
  "fork_velocity_7d":   0.5,
  "contributor_count_30d": 7,
  "release_count_90d":  4,
  "days_since_last_commit": 3,
  "bus_factor":         0.42,
  "issue_close_rate_30d": 0.78,
  "median_first_response_hours": 6.5,
  "dependents_count":   12,
  "forks_with_prs_back": 3,
  "cross_platform_count": 4,
  "primary_language":   "Python",
  "license":            "MIT",
  "topics":             ["mcp", "agent"],
  "public_topics":      ["ai_agents", "open_source"],
  "is_archived":        false,
  "is_fork":            false,
  "score": {
    "momentum_score": 72.3,
    "quality_score":  85.1,
    "community_score": 64.2,
    "adoption_score": 41.0,
    "composite_score": 67.4,
    "passes_quality_gate": true,
    "weights": {"momentum": 0.25, "quality": 0.25, "community": 0.20, "adoption": 0.20},
    "scored_at": "2026-08-03T07:18:00Z",
    "schema_version": "repo_score.v1"
  },
  "schema_version": "repo_snapshot.v1"
}
```

**Scoring**

- Composite = `momentum * 0.25 + quality * 0.25 + community * 0.20 + adoption * 0.20`
- Hard gate: `quality_score < 60` excludes from `top_this_week`.
- Default weights live in `config/scoring_weights.yaml`.

**Velocity caveat**

- True historical star velocity needs GitHub Archive backfill. The
  pipeline exposes the fields; Hermes can recompute against richer
  history when available. The current proxy is `stars / days_since_creation`.

---

## 8b. Source health (the honest run report)

`outputs/source_health/{YYYY-MM-DD}.json` + `outputs/source_health/latest.json`

**Added 2026-08-31.** Records the real per-source outcome of the nightly
collection run. Before this artifact existed the IntelligenceEnvelope
reported `successful_sources == expected_sources` unconditionally, so a run
with a third of its feeds failing was indistinguishable from a clean one.

```json
{
  "schema_version": "source_health.v1",
  "report_date": "YYYY-MM-DD",
  "generated_at": "2026-08-31T07:20:00Z",
  "expected_sources": 128,
  "successful_sources": 120,
  "degraded_sources": 3,
  "failed_sources": 5,
  "stale_sources": ["https://example.com/feed"],
  "failures": [
    {"endpoint": "https://dead.example/rss", "error": "404 Client Error"}
  ],
  "sources": {"https://example.com/feed": "ok"}
}
```

Status values: `ok` (items returned), `empty` (reached, nothing usable),
`failed` (fetch raised).

**Consumer rules**

- Treat `failed_sources / expected_sources > 0.10` as a degraded run.
  Ingest it, but do not treat that day's absence of a topic as signal.
- `outputs/envelopes/{date}.json` now carries the same numbers under
  `health`, plus `health_source`:
  - `"source_health.v1"` — real measured health.
  - `"unavailable"` — snapshot missing; `successful_sources`,
    `degraded_sources` and `failed_sources` are `null`.
    **`null` means unknown, never zero.** Do not coerce it to a clean run.

---

## 9. Atomic-write rule

Every artifact under `outputs/` is written atomically: the file is
written to a `.tmp` path, then renamed. Consumers can read the file
once the rename completes. Symlinks (`latest.json`, `latest.jsonl`)
point at the most recent date-stamped file. Filesystems without
symlink support fall back to a copy of the contents.

---

## 10. Versioning

- Each artifact carries a `schema_version` field. Consumers should
  read this and refuse to ingest unsupported versions.
- Adding a field is **backward-compatible**. Removing a field or
  changing semantics is a **breaking change** and requires a major
  version bump on the artifact (e.g. `atom.v1` → `atom.v2`).
- 30-day deprecation window. Both versions are written during
  transitions.

---

## 11. Failure modes (consumer expectations)

| Failure                     | What Hermes sees                              |
|-----------------------------|-----------------------------------------------|
| LLM call timeout            | Atoms present, all `extracted_by: deterministic` |
| GitHub API rate limit       | `github_traction/latest.json` missing or stale |
| Topic yaml missing          | `topics/latest.json` empty or absent          |
| Empty daily report          | All `outputs/{date}.jsonl` empty, symlink intact |
| LLM returns malformed JSON  | Atom count lower than deterministic baseline  |
| Repo deleted                | That `repo_id` simply absent from snapshot    |
| Feed 404 / 403 / rate-limit | Listed in `source_health` `failures[]`; run still commits |
| Collection step crashed     | `source_health` absent; envelope `health_source: unavailable` |

Hermes treats a missing artifact as "I have no data for this dimension,"
not as a fatal error. Each pipeline is independently resettable.

---

## 12. Operational metadata

MCP tool: `hermes_status` — returns which outputs exist, sizes, mtimes.
This is the first thing Hermes calls on startup to plan its work.

---

## 13. Cross-reference table

| Hermes need                            | Repo output                                |
|----------------------------------------|--------------------------------------------|
| What changed today?                    | `outputs/atoms/latest.jsonl`               |
| Embed these                            | `outputs/embedding_ready/latest.jsonl`     |
| Map to my projects                     | `outputs/topics/latest.json` + private map |
| Track who's active                     | `outputs/entities/latest.json`             |
| Find cross-source claims               | `outputs/consensus/latest.json`            |
| Trust a source on a topic              | `outputs/source_trust/latest.json`         |
| Find new repos to evaluate             | `outputs/github_traction/fastest_30d.json` |
| Top trending                            | `outputs/github_traction/top_this_week.json`|
| Which sources failed tonight?          | `outputs/source_health/latest.json`        |
| Is this run trustworthy?               | `envelopes/latest.json` → `health`         |
| Pipeline health                        | MCP `hermes_status`                        |
