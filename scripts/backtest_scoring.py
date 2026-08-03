#!/usr/bin/env python3
"""Backtest scaffold for GitHub composite scoring weights.

Uses historical snapshots when available; otherwise evaluates weight configs
against the current offline/API traction scores as a smoke harness.

Full GH Archive / BigQuery reconstruction is documented in comments — wire
credentials and expand reconstruct_snapshot() for production calibration.

  python3 scripts/backtest_scoring.py
  python3 scripts/backtest_scoring.py --write outputs/github_traction/backtest_latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.repo_scoring import apply_quality_gate, load_weights, score_repo

CONFIGS = [
    {"momentum": 0.25, "quality": 0.25, "community": 0.20, "adoption": 0.20},
    {"momentum": 0.30, "quality": 0.30, "community": 0.20, "adoption": 0.20},
    {"momentum": 0.20, "quality": 0.30, "community": 0.25, "adoption": 0.25},
    {"momentum": 0.15, "quality": 0.35, "community": 0.25, "adoption": 0.25},
]


def _metrics_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return dict(row.get("metrics") or {})


def evaluate_config(
    weights: Dict[str, float],
    rows: List[Dict[str, Any]],
    gate: float = 60.0,
) -> Dict[str, Any]:
    cfg = {"weights": weights, "quality_gate": gate}
    scored = []
    for row in rows:
        name = row.get("full_name") or "unknown/unknown"
        topics = list(row.get("topics") or [])
        metrics = _metrics_from_row(row)
        if not metrics:
            continue
        scored.append(score_repo(name, metrics, topics=topics, weights_cfg=cfg))
    scored.sort(key=lambda s: -float(s.get("composite_score") or 0))
    gated = apply_quality_gate(scored)
    top10 = gated[:10]
    # Proxy outcome labels from current metrics (stand-in until GH Archive outcomes exist)
    foundational = [
        s for s in gated
        if float((s.get("metrics") or {}).get("stars_total") or 0) >= 5000
        and float(s.get("quality_score") or 0) >= 70
    ]
    top10_ids = {s["full_name"] for s in top10}
    found_ids = {s["full_name"] for s in foundational}
    precision_at_10 = len(top10_ids & found_ids) / max(1, len(top10))
    return {
        "weights": weights,
        "scored": len(scored),
        "passed_gate": len(gated),
        "precision_at_10_proxy": round(precision_at_10, 4),
        "top10": [s["full_name"] for s in top10],
        "foundational_proxy_count": len(foundational),
        "note": "precision uses stars/quality proxy until GH Archive outcomes are wired",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT_DIR / "outputs" / "github_traction" / "latest.json"))
    parser.add_argument("--write", default="")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        # Generate offline scores first
        from pipelines.github_traction import run

        run(offline=True)

    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"scores": []}
    rows = list(data.get("scores") or [])
    results = [evaluate_config(cfg, rows) for cfg in CONFIGS]
    results.sort(key=lambda r: -r["precision_at_10_proxy"])
    baseline = load_weights()
    payload = {
        "schema": "github_traction_backtest.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline_weights": baseline.get("weights"),
        "recommended": results[0]["weights"] if results else baseline.get("weights"),
        "results": results,
        "methodology": (
            "Smoke backtest on current snapshots. For production: reconstruct day-D "
            "metrics from GH Archive (BigQuery githubarchive), classify outcomes "
            "6–24 months later (foundational/stable/fading/abandoned/vapor), then "
            "maximize precision@10 for foundational."
        ),
    }
    text = json.dumps(payload, indent=2) + "\n"
    print(text)
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
