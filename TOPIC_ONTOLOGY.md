# Public topic ontology

Config: [`config/topics.yaml`](config/topics.yaml)  
Export: `outputs/topics/{date}.json`

## Rules

- Tags are **`public_topics[]` only** — never private venture names (All the AI, Blockcities, XO Pure, …).
- Tagging is keyword-based and deterministic on GitHub Actions.
- Export includes frequency, rising/cooling vs previous day, and co-occurrence pairs.

## Current topic ids

- `ai_agents`
- `ai_models`
- `real_estate_tech`
- `wellness_research`
- `creator_economy`
- `blockchain_rwa`
- `open_source_dev`
- `sense_making_macro`
- `alternative_media`
- `quantum_compute`

Hermes maps these to private projects locally.
