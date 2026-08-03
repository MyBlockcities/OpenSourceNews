"""Multi-dimensional GitHub repo scoring."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from services.repo_schema import build_repo_score

ROOT_DIR = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = ROOT_DIR / "config" / "scoring_weights.yaml"


def load_weights(path: Path = WEIGHTS_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {
            "weights": {"momentum": 0.25, "quality": 0.25, "community": 0.20, "adoption": 0.20},
            "quality_gate": 60,
        }
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        if n is None or (isinstance(n, float) and math.isnan(n)):
            return lo
        return max(lo, min(hi, float(n)))
    except (TypeError, ValueError):
        return lo


def score_momentum(metrics: Dict[str, Any]) -> float:
    stars_d = float(metrics.get("stars_delta_7d") or 0)
    forks_d = float(metrics.get("forks_delta_7d") or 0)
    commits_d = float(metrics.get("commits_delta_7d") or 0)
    return _clamp(min(40.0, stars_d * 2.0) + min(30.0, forks_d * 3.0) + min(30.0, commits_d * 1.5))


def score_quality(metrics: Dict[str, Any]) -> float:
    score = 20.0
    if metrics.get("has_license"):
        score += 20.0
    if metrics.get("has_ci"):
        score += 15.0
    if metrics.get("docs_present"):
        score += 15.0
    open_issues = float(metrics.get("open_issues") or 0)
    if 5 <= open_issues <= 500:
        score += 20.0
    elif open_issues < 5:
        score += 10.0
    if metrics.get("archived"):
        score -= 40.0
    return _clamp(score)


def score_community(metrics: Dict[str, Any]) -> float:
    contributors = float(metrics.get("contributors_active") or metrics.get("contributors") or 0)
    pr_rate = float(metrics.get("pr_merge_rate") or 0)
    discussions = float(metrics.get("discussion_activity") or 0)
    return _clamp(min(40.0, contributors * 2.0) + pr_rate * 35.0 + min(25.0, discussions * 2.0))


def score_adoption(metrics: Dict[str, Any]) -> float:
    stars = float(metrics.get("stars_total") or metrics.get("stargazers_count") or 0)
    forks = float(metrics.get("forks_total") or metrics.get("forks_count") or 0)
    dependents = float(metrics.get("dependents_proxy") or 0)
    star_part = min(50.0, math.log10(stars + 1) * 12.0)
    fork_part = min(25.0, math.log10(forks + 1) * 8.0)
    dep_part = min(25.0, math.log10(dependents + 1) * 10.0)
    return _clamp(star_part + fork_part + dep_part)


def score_repo(
    full_name: str,
    metrics: Dict[str, Any],
    *,
    topics: Optional[List[str]] = None,
    weights_cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = weights_cfg or load_weights()
    weights = cfg.get("weights") or {}
    gate = float(cfg.get("quality_gate") or 60)

    momentum = score_momentum(metrics)
    quality = score_quality(metrics)
    community = score_community(metrics)
    adoption = score_adoption(metrics)

    composite = (
        momentum * float(weights.get("momentum", 0.25))
        + quality * float(weights.get("quality", 0.25))
        + community * float(weights.get("community", 0.20))
        + adoption * float(weights.get("adoption", 0.20))
    )
    composite = _clamp(composite)

    low_confidence = bool(metrics.get("offline") or metrics.get("fetch_error"))
    if low_confidence and float(metrics.get("stars_total") or 0) < 100:
        quality = min(quality, gate - 1)

    result = build_repo_score(
        full_name=full_name,
        momentum=momentum,
        quality=quality,
        community=community,
        adoption=adoption,
        composite=composite,
        passes_quality_gate=quality >= gate,
        metrics=metrics,
        topics=topics,
    )
    if low_confidence:
        result["low_confidence_score"] = True
    return result


def apply_quality_gate(scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [s for s in scores if s.get("passes_quality_gate")]
