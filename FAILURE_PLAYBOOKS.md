# Failure-mode playbooks

Concrete procedures for OpenSourceNews + Hermes News Factory pipelines.

## atom_extraction (Actions)

| Failure | Action | Recovery |
|---------|--------|----------|
| LLM timeout (>30s/signal) | Log to `outputs/atoms/_partial/{date}.jsonl` with `status=llm_timeout`; continue deterministic-only for that signal; alert if >20% timeouts | Reduce batch, cheaper model, or accept deterministic-only |
| Malformed LLM JSON | Retry once with shorter prompt; else `llm_parse_error` skip; alert if >5% | Fix prompt / schema reminder |
| 0 deterministic atoms | Write empty entry `status=no_extractable_atoms`; do **not** retry (normal ~5–10%) | — |
| Run >5h (Actions limit) | Split AM/PM batches or sample signals; alert | Quota / channel rotation |
| Hosted LLM rate limit | Exp backoff (max 60s); after 3 hits abort LLM, commit deterministic-only with `status=llm_rate_limited` | Wait / lower concurrency |

## github_traction

| Failure | Action | Recovery |
|---------|--------|----------|
| API rate limit | Cache; conditional ETag when available; prioritize top 100 by prior composite; defer rest | Authenticated token, stagger runs |
| Repo deleted/private | Mark `archived` in registry; keep last score; remove from active tracked | Manual restore if renamed |
| NaN / divide-by-zero | Sub-score → 0; flag `low_confidence_score`; exclude from tops until 7d history | Backtest weights |
| Offline / no token | Placeholder metrics with `offline: true` (CI smoke) | Set `GITHUB_TOKEN` |

## nightly_ingest (Hermes)

| Failure | Action | Recovery |
|---------|--------|----------|
| Qdrant unreachable | Stage all rows in SQLite; retry drain; never drop | Next run drains staging |
| Embedding model missing | Leave `embedding_status=pending`; alert if 2+ nights | Install sentence-transformers / model |
| Disk full | Archive briefs/tutorials >90d to tarball; **never** delete SQLite ledger; alert | Free disk |

## nightly_brief (Hermes)

| Failure | Action | Recovery |
|---------|--------|----------|
| LLM unusable | Retry stricter prompt; else degraded brief (titles+URLs); alert | Check Ollama/Gemma |
| <5 atoms | Still write short brief + low-signal note; still Telegram | — |
| Telegram down | Save file; retry; optional email backup if configured | Fix bot token/chat |

## weekly_tutorial_forge

| Failure | Action | Recovery |
|---------|--------|----------|
| Code fails verification | Retry simpler example; else `code unverified, human review required`; **do not** Academy-publish | Human runs code |
| Critic >3 high severity | Hold under `_held/`; no publish | Human approve/revise |

## Ownership

- Public sensor failures → OpenSourceNews Actions logs + Mailaroo failure step
- Private factory failures → `~/Library/Logs/Hermes/news_factory_*.log` + Telegram alert text when send enabled
