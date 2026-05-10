# Peptides Source and Qdrant Workflow

Date: 2026-05-10

This document defines the `peptides` bucket for peptide, wellness, longevity, GLP-1, safety, regulatory, clinical-trial, and trend-monitoring intelligence.

## Design Principle

Peptide content is medically sensitive. OpenSourceNews should collect it, label it, and export it cleanly, but downstream systems must not treat influencer, forum, or commentary signals as clinical evidence.

The bucket is intentionally separate:

- `bucket = "peptides"`
- Qdrant collection: `peptides`
- Truth-layer sources: PubMed and ClinicalTrials.gov
- Demand-signal sources: YouTube and Hacker News
- Medical claim policy: no disease, treatment, dosing, efficacy, or safety claims without qualified review and primary-source support

## Source Layers

| Layer | Sources | Trust Use | Content Use |
|---|---|---|---|
| Truth Layer | PubMed, ClinicalTrials.gov | High-confidence source discovery | Evidence checkpoint, study status, endpoint direction, evidence gaps |
| Medical Interpretation | Ground Truths / Eric Topol RSS | Strong expert framing, still verify primary claims | Narrative intelligence and public-health framing |
| Demand Signal | YouTube, Hacker News | Not evidence | Questions, hooks, objections, market language, content ideas |

## Configured Inputs

Configured in `config/feeds.yaml` under `Peptides / Wellness / Longevity`.

PubMed queries:

- `(peptides[Title/Abstract] OR peptide therapeutics[Title/Abstract]) AND wellness`
- `BPC-157 peptide`
- `GHK-Cu peptide`
- `KPV peptide`
- `NAD+ peptide`
- `GLP-1 peptide`
- `collagen peptides`
- `thymosin alpha-1 peptide`

ClinicalTrials.gov queries:

- `peptide therapy`
- `BPC-157`
- `GHK-Cu`
- `NAD+`
- `GLP-1`
- `collagen peptides`
- `semaglutide peptide`
- `tirzepatide`
- `retatrutide`

Trend/listening queries:

- Hacker News: `peptides`, `GLP-1`, `longevity`, `FDA peptide`
- YouTube: `Ben Greenfield peptides`, `Dave Asprey peptides`, `peptides physician lecture`, `GLP-1 peptide science`
- RSS: `https://erictopol.substack.com/feed`

## Metadata Contract

Every peptide item should carry these fields into normalized reports and Qdrant payloads:

```json
{
  "bucket": "peptides",
  "source_category": "research_database | clinical_trial_registry | trend_signal | medical_information",
  "trust_layer": "truth | demand_signal",
  "trust_level": "very_high | low_for_evidence",
  "evidence_level": "peer_reviewed_or_indexed | human_clinical_registry | anecdotal_or_commentary",
  "verification_mode": "truth_layer | needs_review",
  "regulatory_sensitivity": "high",
  "content_use": "evidence_checkpoint | science_monitoring | hook_and_question_mining",
  "safe_framing": "Conservative wellness education framing only.",
  "medical_claim_policy": "No medical, dosing, disease, treatment, safety, or efficacy claims without review."
}
```

## Daily Workflow

The normal daily pipeline now includes the peptide bucket:

```bash
python3 pipelines/daily_run.py
```

The scheduled GitHub Actions workflow can run without `GEMINI_API_KEY`; collection, IDs, and exports still work with fallback summaries and classification.

## Peptide-Only Qdrant Export

OpenSourceNews prepares a downstream-friendly JSONL file without embedding or requiring Qdrant credentials:

```bash
python3 scripts/export_qdrant_payload.py --days 30 --bucket peptides --out outputs/qdrant_export/peptides_signals.jsonl
npm run export:qdrant:peptides
```

Outputs:

- `outputs/qdrant_export/peptides_signals.jsonl`
- `outputs/qdrant_export/peptides_signals.manifest.json`

## OpenSwarm Import

OpenSwarm imports the peptide JSONL into a dedicated Qdrant collection named `peptides` using local sentence-transformer embeddings:

```bash
cd /Users/brians/Documents/openswarm2026/OpenSwarm

.venv/bin/python - <<'PY'
from news_workflow.knowledge_graph_agent.tools.LoadQdrantExport import LoadQdrantExport

print(LoadQdrantExport(
    action="import",
    export_path="/Users/brians/Documents/openswarm2026/OpenSourceNews/outputs/qdrant_export/peptides_signals.jsonl",
    collection="peptides",
    bucket_filter=["peptides"],
).run())
PY
```

Search the dedicated collection:

```bash
.venv/bin/python - <<'PY'
from news_workflow.knowledge_graph_agent.tools.QdrantStore import QdrantStore

print(QdrantStore(
    action="search",
    collection="peptides",
    query="BPC-157 clinical trial safety evidence",
    k=5,
).run())
PY
```

## Recommended Qdrant Indexes

- `report_date`
- `signal_id`
- `cluster_id`
- `bucket`
- `source`
- `source_category`
- `trust_layer`
- `trust_level`
- `evidence_level`
- `verification_mode`
- `regulatory_sensitivity`
- `content_type`
- `topics`

## Safe Content Use

Use peptide records for:

- Evidence-level tagging
- FAQ planning
- Content hooks
- Consumer education outlines
- Regulatory/safety alerts
- Source-backed "what is being studied" summaries

Do not use peptide records for:

- Disease treatment claims
- Dosing protocols
- Safety guarantees
- Efficacy claims
- Product claims that imply FDA approval
- Repeating influencer or forum claims as facts

## Source API Notes

ClinicalTrials.gov v2 exposes `/api/v2/studies` and supports `query.term`, `pageSize`, and JSON responses. PubMed records are fetched through NCBI E-utilities using ESearch and ESummary. Both are metadata/discovery feeds; they do not replace expert medical review.
