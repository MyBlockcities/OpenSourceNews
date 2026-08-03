"""Composite GitHub traction scoring with a hard quality gate.

Sub-scores (0–100): momentum, quality, community, adoption.
Composite = weighted sum (default 0.25 / 0.25 / 0.20 / 0.20).
Snapshots with quality_score < QUALITY_GATE are excluded from top lists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = ROOT_DIR / "config" / "scoring_weights.yaml"

DEFAULT_WEIGHTS = {
    "momentum": 0.25,
    "quality": 0.25,
    "community": 0.20,
    "adoption": 0.20,
}
QUALITY_GATE = 60.0


def load_weights(path: Path = WEIGHTS_PATH) -> Dict[str, Any]:
    global QUALITY_GATE
    if not path.exists():
        return {"weights": dict(DEFAULT_WEIGHTS), "quality_gate": QUALITY_GATE}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(data.get("weights") or {})
    gate = float(data.get("quality_gate") or QUALITY_GATE)
    QUALITY_GATE = gate
    return {"weights": weights, "quality_gate": gate}


def _clamp(n: float, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        return max(lo, min(hi, float(n)))
    except (TypeError, ValueError):
        return lo


def _f(snap: Dict[str, Any], key: str, default: float = 0.0) -> float:
    v = snap.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def score_momentum(snap: Dict[str, Any]) -> float:
    v7 = _f(snap, "star_velocity_7d")
    v30 = _f(snap, "star_velocity_30d")
    fv = _f(snap, "fork_velocity_7d")
    accel = snap.get("acceleration")
    accel_n = float(accel) if isinstance(accel, (int, float)) else 0.0
    return _clamp(min(40.0, v7 * 4.0) + min(30.0, v30 * 2.0) + min(20.0, fv * 5.0) + min(10.0, max(0.0, accel_n) * 20.0))


def score_quality(snap: Dict[str, Any]) -> float:
    score = 40.0
    days = _f(snap, "days_since_last_commit", 999)
    if days <= 14:
        score += 30.0
    elif days <= 45:
        score += 20.0
    elif days <= 90:
        score += 10.0
    elif days > 180:
        score -= 35.0
    if snap.get("is_archived"):
        score -= 50.0
    close_rate = _f(snap, "issue_close_rate_30d", 0.5)
    score += close_rate * 20.0
    bus = _f(snap, "bus_factor", 0.5)
    # Lower bus factor (more distributed) is better
    score += (1.0 - min(1.0, bus)) * 15.0
    releases = _f(snap, "release_count_90d")
    score += min(15.0, releases * 3.0)
    return _clamp(score)


def score_community(snap: Dict[str, Any]) -> float:
    contributors = _f(snap, "contributor_count_30d")
    resp = _f(snap, "median_first_response_hours", 48.0)
    hn = _f(snap, "hn_mentions_30d")
    reddit = _f(snap, "reddit_mentions_30d")
    resp_score = 25.0 if resp <= 12 else (15.0 if resp <= 48 else 5.0)
    return _clamp(
        min(40.0, contributors * 3.0)
        + resp_score
        + min(20.0, hn * 2.0)
        + min(15.0, reddit * 1.5)
    )


def score_adoption(snap: Dict[str, Any]) -> float:
    import math

    stars = _f(snap, "stars_total")
    forks = _f(snap, "forks_total")
    deps = _f(snap, "dependents_count")
    forks_back = _f(snap, "forks_with_prs_back")
    cross = _f(snap, "cross_platform_count")
    return _clamp(
        min(40.0, math.log10(stars + 1) * 10.0)
        + min(20.0, math.log10(forks + 1) * 7.0)
        + min(20.0, math.log10(deps + 1) * 8.0)
        + min(10.0, forks_back)
        + min(10.0, cross * 2.0)
    )


def compute_composite_score(
    snap: Dict[str, Any],
    *,
    weights_cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = weights_cfg or load_weights()
    weights = cfg.get("weights") or DEFAULT_WEIGHTS
    gate = float(cfg.get("quality_gate") or QUALITY_GATE)

    momentum = score_momentum(snap)
    quality = score_quality(snap)
    community = score_community(snap)
    adoption = score_adoption(snap)
    composite = _clamp(
        momentum * float(weights.get("momentum", 0.25))
        + quality * float(weights.get("quality", 0.25))
        + community * float(weights.get("community", 0.20))
        + adoption * float(weights.get("adoption", 0.20))
    )
    return {
        "momentum_score": round(momentum, 2),
        "quality_score": round(quality, 2),
        "community_score": round(community, 2),
        "adoption_score": round(adoption, 2),
        "composite_score": round(composite, 2),
        "passes_quality_gate": quality >= gate,
        "quality_gate": gate,
        "weights": weights,
    }


def attach_score(snapshot: Dict[str, Any], *, weights_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = dict(snapshot)
    out["score"] = compute_composite_score(snapshot, weights_cfg=weights_cfg)
    return out


def rank_snapshots(
    snapshots: List[Dict[str, Any]],
    *,
    limit: int = 50,
    require_gate: bool = True,
    weights_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    scored = []
    for snap in snapshots:
        if "score" in snap and isinstance(snap["score"], dict):
            row = snap
        else:
            row = attach_score(snap, weights_cfg=weights_cfg)
        if require_gate and not (row.get("score") or {}).get("passes_quality_gate"):
            continue
        scored.append(row)
    scored.sort(key=lambda s: float((s.get("score") or {}).get("composite_score") or 0), reverse=True)
    return scored[: max(1, int(limit or 50))]


def apply_quality_gate(scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Back-compat helper for older callers that used flat score dicts."""
    out = []
    for s in scores:
        if "score" in s and isinstance(s["score"], dict):
            if s["score"].get("passes_quality_gate"):
                out.append(s)
        elif s.get("passes_quality_gate"):
            out.append(s)
    return out


# Back-compat aliases used by earlier leverage-pipeline tests / offline runner.
def score_repo(full_name: str, metrics: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    """Map legacy metric keys into a snapshot-shaped dict and score it."""
    snap = {
        "full_name": full_name,
        "stars_total": metrics.get("stars_total") or metrics.get("stargazers_count"),
        "forks_total": metrics.get("forks_total") or metrics.get("forks_count"),
        "star_velocity_7d": metrics.get("stars_delta_7d"),
        "star_velocity_30d": metrics.get("stars_delta_7d"),
        "fork_velocity_7d": metrics.get("forks_delta_7d"),
        "contributor_count_30d": metrics.get("contributors_active") or metrics.get("contributors"),
        "days_since_last_commit": 5 if not metrics.get("archived") else 400,
        "is_archived": bool(metrics.get("archived")),
        "issue_close_rate_30d": metrics.get("pr_merge_rate") or 0.5,
        "bus_factor": 0.4,
        "release_count_90d": 2 if metrics.get("has_ci") else 0,
        "dependents_count": metrics.get("dependents_proxy") or 0,
        "hn_mentions_30d": metrics.get("discussion_activity") or 0,
        "reddit_mentions_30d": 0,
        "cross_platform_count": 1,
        "forks_with_prs_back": 0,
        "median_first_response_hours": 12,
        "topics": kwargs.get("topics") or [],
    }
    score = compute_composite_score(snap, weights_cfg=kwargs.get("weights_cfg"))
    return {
        "full_name": full_name,
        "momentum_score": score["momentum_score"],
        "quality_score": score["quality_score"],
        "community_score": score["community_score"],
        "adoption_score": score["adoption_score"],
        "composite_score": score["composite_score"],
        "passes_quality_gate": score["passes_quality_gate"],
        "metrics": metrics,
        "topics": list(kwargs.get("topics") or []),
        "score": score,
    }
