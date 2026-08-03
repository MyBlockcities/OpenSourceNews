# Atom schema (atom.v1)

See also: [HERMES_CONTRACT.md](HERMES_CONTRACT.md)

## Identity

```
atom_id = uuid5(namespace, parent_signal_id + "|" + atom_type + "|" + text_hash)
text_hash = sha256(normalized_text)[:16]
```

Namespace URL: `https://github.com/MyBlockcities/OpenSourceNews/atoms`

## Types

`claim`, `data_point`, `tool`, `framework`, `entity`, `prediction`, `counterexample`, `reasoning`

## Line shape (JSONL)

```json
{
  "atom_id": "...",
  "parent_signal_id": "...",
  "atom_type": "tool",
  "text": "langchain",
  "evidence_urls": ["https://..."],
  "extracted_at": "2026-08-03T12:00:00Z",
  "schema_version": "atom.v1",
  "public_topics": ["ai_agents"]
}
```

## Extraction

1. Deterministic heuristics on Actions (always).
2. Optional `ATOM_LLM=1` + `OPENROUTER_API_KEY` for claim/reasoning/counterexample (fail-soft).

Paths: `outputs/atoms/{date}.jsonl`, `outputs/atoms/latest.jsonl`
