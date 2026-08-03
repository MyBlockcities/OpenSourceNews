# Hermes Contract v1
#
# Stable public API for Hermes Agency (and other pull consumers).
# Ops / setup details live in HERMES_INTEGRATION.md — this file is the schema contract.

## Guarantees

1. **Daily report** — `outputs/daily/{YYYY-MM-DD}.json`  
   Topic → list of items. Additive sensor fields only. Digest push schema remains `open_source_news_daily_digest.v1`.

2. **Manifest** — `outputs/manifests/latest.json` (`open_source_news_manifest.v2`)  
   Always includes `report_sha256`, `latest_report_path`, `latest_report_date`, `item_count`.  
   May include `artifacts` listing sibling public intelligence paths for the same date.

3. **Atoms** — `outputs/atoms/{YYYY-MM-DD}.jsonl` + `outputs/atoms/latest.jsonl`  
   Schema: `atom.v1`. One JSON object per line. Stable `atom_id` = uuid5(parent_signal_id + atom_type + text_hash).

4. **Embedding-ready** — `outputs/embedding_ready/{YYYY-MM-DD}.jsonl` + `latest.jsonl`  
   Schema: `embedding_ready.v1`. Field `embedding_text` is present; **no vectors**. Hermes embeds locally (e.g. all-MiniLM 384-d).

5. **Topics** — `outputs/topics/{YYYY-MM-DD}.json`  
   Public ontology tags only (`config/topics.yaml`). No private venture mapping.

6. **Entities** — `outputs/entities/{YYYY-MM-DD}.json`  
   Optional pages under `outputs/entity_pages/{entity_id}.json`.

7. **Consensus** — `outputs/consensus/{YYYY-MM-DD}.json`  
   Cross-source confirmation / contradiction counts for claim-like atoms.

8. **Source trust** — `outputs/source_trust/{YYYY-MM-DD}.json`  
   Public-learnable per-source per-topic scores.

9. **GitHub traction** — `outputs/github_traction/` (parallel workflow)  
   Composite scores; quality gate ≥ 60 for “top” lists.

## Atomic writes

All JSON/JSONL artifacts are written via temp file + rename. Consumers should treat partial files as corrupt and retry on next pull.

## Versioning

| Artifact | schema field / name |
|----------|---------------------|
| Manifest | `open_source_news_manifest.v2` |
| Atom line | `schema_version: atom.v1` |
| Embedding-ready line | `schema_version: embedding_ready.v1` |
| This contract | Hermes Contract **v1** |

Breaking changes require a new contract version and dual-publish window.

## Explicit non-goals (Hermes-only)

- Private venture / project relevance mapping  
- Persona content, Telegram / Academy delivery  
- Heavy LLM tutorial forging  
- Private relevance multiplier on GitHub scores  

## Env (Actions)

| Var | Meaning |
|-----|---------|
| `COLLECT_ONLY=1` | Skip full triage LLM on daily collect |
| `ATOM_LLM=1` | Optional cheap atom LLM (requires `OPENROUTER_API_KEY`); fail-soft to deterministic |
