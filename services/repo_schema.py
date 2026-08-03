"""Repo score record schema for GitHub traction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


SCHEMA_VERSION = "github_traction.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_repo_score(
    *,
    full_name: str,
    momentum: float,
    quality: float,
    community: float,
    adoption: float,
    composite: float,
    passes_quality_gate: bool,
    metrics: Optional[Dict[str, Any]] = None,
    topics: Optional[list] = None,
    scored_at: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "full_name": full_name,
        "momentum_score": round(float(momentum), 2),
        "quality_score": round(float(quality), 2),
        "community_score": round(float(community), 2),
        "adoption_score": round(float(adoption), 2),
        "composite_score": round(float(composite), 2),
        "passes_quality_gate": bool(passes_quality_gate),
        "topics": list(topics or []),
        "metrics": dict(metrics or {}),
        "scored_at": scored_at or utc_now_iso(),
    }
