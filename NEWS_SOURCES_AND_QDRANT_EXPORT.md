# OpenSourceNews Source Inventory and Qdrant Export Contract

Date: 2026-05-10

This document summarizes the news and information inputs currently configured in `config/feeds.yaml`, plus the local export shape downstream apps can use to embed and upsert OpenSourceNews records into Qdrant.

## Key Safety Notes

- `services/geminiService.ts` does not read or expose `GEMINI_API_KEY`; it only calls the backend through `apiFetch`.
- `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `YOUTUBE_API_KEY`, `ASSEMBLYAI_API_KEY`, and Qdrant credentials must stay in server-side environment variables or GitHub Actions secrets.
- Do not set `VITE_API_BEARER_TOKEN` in a public frontend build unless `VITE_ALLOW_BROWSER_BEARER_TOKEN=1` is intentionally used for a private/dev deployment. Vite variables are visible in browser JavaScript.
- Public abuse risk comes from exposed admin credentials, not from `geminiService.ts`. Keep `OPEN_SOURCE_NEWS_ADMIN_KEY` server-side and separate from any public read token.
- The scheduled GitHub Actions workflows do not require `GEMINI_API_KEY`. With no cloud LLM configured, daily collection still runs and uses fallback summaries/classification.

## Collection Behavior

The daily pipeline in `pipelines/daily_run.py` currently pulls up to five items per configured source/query:

- RSS feeds via direct HTTP fetch and XML parsing.
- Hacker News search via `https://hn.algolia.com/api/v1/search`.
- GitHub Trending via `https://github.com/trending/{language}`.
- YouTube metadata via the YouTube Data API using `YT_API_KEY` or `YOUTUBE_API_KEY`.
- PubMed metadata through NCBI E-utilities for configured `pubmed_sources`.
- ClinicalTrials.gov study records through the modern v2 API for configured `clinical_trials_sources`.
- X and Instagram entries are configured placeholders only; the current fetchers intentionally skip them.
- `Alternative News & Independent Commentary` is intentionally separated into `bucket = "alternative_news"` and should be treated as commentary/opinion-heavy, not as high-confidence institutional reporting.
- `Peptides / Wellness / Longevity` is intentionally separated into `bucket = "peptides"` with truth-layer metadata so trend signals are not treated as clinical evidence.

The backend research endpoints can also do on-demand DuckDuckGo HTML search through `POST /api/research/search`. That is separate from the scheduled daily feed configuration.

## Topic: General News & Research

Purpose: broad tech, open source, startup/product releases, and platform shifts.

GitHub Trending languages:

- `typescript`
- `python`
- `rust`

Hacker News search queries:

- `open source`
- `startup funding`
- `developer tools`
- `tech industry`

RSS feeds:

- Hacker News front page: `https://hnrss.org/frontpage`
- The Verge: `https://www.theverge.com/rss/index.xml`
- TechCrunch: `https://techcrunch.com/feed/`
- Wired: `https://www.wired.com/feed/rss`
- Ars Technica: `https://arstechnica.com/feed/`

YouTube sources:

- Fireship: `@Fireship`
- ThePrimeTime: `@ThePrimeTimeagen`

## Topic: AI / AI Tools / AI Agents

Purpose: AI tools, agents, model releases, frameworks, evals, inference, and training.

GitHub Trending languages:

- `python`

Hacker News search queries:

- `AI agent`
- `LLM`
- `GPT`
- `machine learning`

RSS feeds:

- Google AI Blog: `https://blog.google/technology/ai/rss/`
- MarkTechPost: `https://www.marktechpost.com/feed/`
- Hugging Face Blog: `https://huggingface.co/blog/feed.xml`
- AI News: `https://www.artificialintelligence-news.com/feed/`
- The Rundown AI: `https://www.rundown.ai/rss`
- AI Agent News: `https://aiagent.marktechpost.com/feed/`

YouTube sources:

- Two Minute Papers: `@TwoMinutePapers`
- IndyDevDan: `indydevdan`
- Arseny Shatokhin: `UC_x36zCEGilGpB1m-V4gmjg`
- Matthew Berman: `UCSv4qL8vmoSH7GaPjuqRiCQ`
- WorldofAI: `UCawZsQWqfGSbCI5yjkdVkTA`
- Matt Wolfe: `UC2WmuBuFq6gL08QYG-JjXKw`
- Additional AI channel: `UCAl9Ld79qaZxp9JzEOwd3aA`

Configured but inactive X placeholders:

- `Sauain`
- `levelsio`
- `SwiftOnSecurity`
- `_kaitoai`
- `Marktechpost`

## Topic: Blockchain / Crypto / Web3

Purpose: crypto, tokenization, DAOs, wallets, custody, stablecoins, and regulation.

GitHub Trending languages:

- `solana`

Hacker News search queries:

- `crypto funding`
- `blockchain funding`
- `web3`
- `tokenization`

RSS feeds:

- CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml`
- Cointelegraph: `https://cointelegraph.com/rss`
- DailyCoin: `https://dailycoin.com/feed/`
- Bankless: `https://www.bankless.com/feed`
- Blockchain App Factory: `https://www.blockchainappfactory.com/blog/feed/`

YouTube sources:

- BitBoy X: `UChpleBmo18P08aKCIgti38g`
- Coin Bureau: `UCuV9EB4I9L-xmRoaXd8tmuA`
- Bankless: `UCqK_GSMbpiV8spgD3ZGloSw`

Configured but inactive X placeholders:

- `a16zcrypto`
- `paradigm`
- `multicoincap`
- `cointelegraph`
- `CoinLaunchSpace`
- `TimBeiko`

## Topic: Sense-Making & Narrative Analysis

Purpose: contested narratives, geopolitics, institutional critique, alternative interpretations, and media framing analysis.

Hacker News search queries:

- `geopolitics`
- `misinformation`
- `media analysis`
- `institutional`

RSS feeds:

- BBC Technology: `https://www.bbc.co.uk/news/technology/rss.xml`
- Reuters all news RSS: `https://www.reuters.com/arc/outboundfeeds/v3/all/rss.xml`
- LessWrong: `https://www.lesswrong.com/feed.xml`
- Astral Codex Ten: `https://www.astralcodexten.com/feed`
- Foreign Affairs: `https://www.foreignaffairs.com/rss.xml`

YouTube sources:

- All-In Podcast: `@AllInPodcast`
- Lex Fridman: `@LexFridman`
- Johnny Harris: `@JohnnyHarris`

## Topic: Alternative News & Independent Commentary

Purpose: personality-led, independent, non-institutional, and opinion-heavy channels. This bucket is useful for monitoring narratives and claims, but downstream apps should label it clearly and avoid mixing it into mainstream/research confidence scoring.

Default metadata applied to this bucket:

- `bucket`: `alternative_news`
- `mode`: `commentary`
- `stance`: `commentary`
- `affiliation`: `independent`
- `risk_level`: `mixed`
- `verification_mode`: `needs_review`
- `content_warning`: `Opinion-heavy or contested claims may be present; verify before reuse.`

YouTube sources:

- Ian Carroll: `Ian Carroll`
- Joe Rogan Experience: `@joerogan`
- Dr. David Martin: `Dr David Martin`
- Danny Jones: `Danny Jones podcast`
- Dr. Jack Kruse: `Dr Jack Kruse`
- The Align Podcast / Aaron Alexander: `The Align Podcast Aaron Alexander`
- The Diary of a CEO: `@TheDiaryOfACEO`
- Candace Owens: `@realCandaceOwens`
- Tucker Carlson: `@TuckerCarlson`
- Alex Jones: `Alex Jones`
- Dave Smith: `Dave Smith podcast`
- Breaking Points: `@breakingpoints`
- Coffeezilla: `@Coffeezilla`
- Nick Shirley: `@NickShirley`
- Johnny Harris: `@johnnyharris`
- TLDR Podcasts: `@tldrpodcasts`
- The Independent: `theindependent`

## Topic: Peptides / Wellness / Longevity

Purpose: peptide research, clinical trial monitoring, GLP-1/metabolic-health signals, safety/regulatory watch items, and cautious wellness trend monitoring.

Default metadata applied to this bucket:

- `bucket`: `peptides`
- `trust_layer`: `truth` for PubMed and ClinicalTrials.gov; `demand_signal` for YouTube/Hacker News trend inputs
- `verification_mode`: `truth_layer` for PubMed and ClinicalTrials.gov; `needs_review` for trend inputs
- `regulatory_sensitivity`: `high`
- `medical_claim_policy`: no medical, dosing, disease, or treatment claims without qualified review and primary-source support
- `content_warning`: peptide and wellness content is medically sensitive; trend claims require verification before reuse

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

Hacker News trend queries:

- `peptides`
- `GLP-1`
- `longevity`
- `FDA peptide`

RSS feeds:

- Ground Truths / Eric Topol: `https://erictopol.substack.com/feed`

YouTube trend/listening sources:

- Ben Greenfield peptides: `Ben Greenfield peptides`
- Dave Asprey peptides: `Dave Asprey peptides`
- Peptides physician lecture: `peptides physician lecture`
- GLP-1 peptide science: `GLP-1 peptide science`

## Additional Information Assets

Generated files become part of the local knowledge base:

- `outputs/daily/*.json`: structured daily reports.
- `outputs/scripts/*.txt` and `outputs/scripts/*.json`: generated scripts and storyboard metadata.
- `outputs/transcripts/*.json`: cached transcripts fetched on demand.
- `outputs/briefs/{watchlist}/*.json` and `.md`: mission briefs generated from watchlists.
- `outputs/manifests/latest.json`: latest report discovery manifest.

## Qdrant Export Contract

The repo now includes a downstream-friendly exporter:

```bash
python3 scripts/export_qdrant_payload.py --days 30
npm run export:qdrant
npm run export:qdrant:peptides
```

Default output:

- `outputs/qdrant_export/news_signals.jsonl`
- `outputs/qdrant_export/news_signals.manifest.json`
- `outputs/qdrant_export/peptides_signals.jsonl`
- `outputs/qdrant_export/peptides_signals.manifest.json`

Each JSONL row has this shape:

```json
{
  "id": "deterministic-uuid-for-qdrant-point-id",
  "external_id": "opensourcenews:2026-05-09:a1b2c3d4e5f67890",
  "record_type": "news_signal",
  "embedding_text": "Title, summary, insights, claims, lessons, and entities...",
  "payload": {
    "source_system": "OpenSourceNews",
    "report_date": "2026-05-09",
    "signal_id": "a1b2c3d4e5f67890",
    "cluster_id": "b2c3d4e5f67890a1",
    "title": "Example headline",
    "summary": "Example summary",
    "source_urls": ["https://example.com/article"],
    "topics": ["AI / AI Tools / AI Agents"],
    "source": "RSS",
    "category": "General News",
    "content_type": "news",
    "bucket": "ai",
    "processing_mode": "standard_summary",
    "mode": "",
    "stance": "",
    "affiliation": "",
    "risk_level": "",
    "verification_mode": "",
    "content_warning": "",
    "source_category": "",
    "trust_layer": "",
    "trust_level": "",
    "evidence_level": "",
    "regulatory_sensitivity": "",
    "content_use": "",
    "safe_framing": "",
    "medical_claim_policy": "",
    "classification_confidence": 0.5,
    "quality_score": null,
    "has_transcript": false
  }
}
```

Recommended downstream ingestion flow:

1. Fetch `outputs/manifests/latest.json` from GitHub raw content or the API `GET /api/manifest/latest`.
2. Detect new `outputs/daily/{date}.json` files or run the exporter after pulling the repo.
3. Embed `embedding_text` in the downstream app.
4. Upsert to Qdrant using `id` as the point id and `payload` as the point payload.
5. Use `signal_id` for item-level dedupe and `cluster_id` for story-level grouping.

Recommended Qdrant payload indexes:

- `report_date`
- `signal_id`
- `cluster_id`
- `bucket`
- `source`
- `content_type`
- `topics`
- `has_transcript`
- `verification_mode`
- `risk_level`
- `affiliation`
- `trust_layer`
- `trust_level`
- `evidence_level`
- `regulatory_sensitivity`
- `source_category`

Peptide-only export and OpenSwarm import:

```bash
python3 scripts/export_qdrant_payload.py --days 30 --bucket peptides --out outputs/qdrant_export/peptides_signals.jsonl
```

From OpenSwarm, import that JSONL into a dedicated Qdrant collection named `peptides`:

```bash
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

The exporter intentionally does not require `GEMINI_API_KEY`, `QDRANT_URL`, or `QDRANT_API_KEY`; those belong to the downstream embedding/upsert service.
