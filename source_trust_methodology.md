# Source trust methodology (public)

Export: `outputs/source_trust/{date}.json`  
Schema: `open_source_news_source_trust.v1`

## Formula

For each `(source, topic)`:

```
prior = class_prior(source_class)   # pubmed 0.85 … youtube 0.55 … x 0.45
volume = min(1.0, item_count / 10)
confirm_boost = min(0.2, confirmation_events * 0.05)
contradict_pen = min(0.25, contradiction_events * 0.08)

trust_score = clamp01(prior * 0.6 + volume * 0.3 + confirm_boost - contradict_pen)
```

Confirmation / contradiction events come from claim clusters in `outputs/consensus/`.

## Notes

- Scores are **public-learnable heuristics**, not editorial judgments.
- Hermes may reweight with private feedback / delivery outcomes.
- Class priors favor primary literature (PubMed / ClinicalTrials) over social.
