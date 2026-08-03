# Source trust methodology (public)

Export: `outputs/source_trust/{date}.json`  
Schema: `open_source_news_source_trust.v1`

## Formula (v2 — EMA + priors)

For each `(source, topic)`:

```
prior = class_prior(source_class)
volume = min(1.0, item_count / 10)
confirm_boost = min(0.2, confirmation_events * 0.05)
contradict_pen = min(0.25, contradiction_events * 0.08)
ema = SourceTrustModel EMA (α=0.1), starts at 0.5
  corroboration → +α*0.05
  contradiction → −α*0.15
  retraction    → −α*0.25

trust_score = clamp01(prior*0.35 + volume*0.2 + confirm_boost - contradict_pen + ema*0.45)
```

EMA state persisted at `outputs/source_trust/ema_state.json`.
Daily `outputs/consensus/{date}.json` feeds corroboration/contradiction events.

## Notes

- Scores are **public-learnable heuristics**, not editorial judgments.
- Hermes may reweight with private feedback / delivery outcomes.
- Class priors favor primary literature (PubMed / ClinicalTrials) over social.
