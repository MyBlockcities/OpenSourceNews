#!/usr/bin/env python3
"""GitHub traction pipeline — multi-dimensional scoring with quality gate.

Parallel to daily collect (does not block COLLECT_ONLY). Uses GitHub API when
GITHUB_TOKEN is set; otherwise writes placeholder scores from local metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.repo_scoring import apply_quality_gate, load_weights, score_repo
from services.repo_schema import utc_now_iso


TRACKED_PATH = ROOT_DIR / "config" / "tracked_repos.yaml"
OUT_DIR = ROOT_DIR / "outputs" / "github_traction"


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_tracked() -> List[Dict[str, Any]]:
    data = yaml.safe_load(TRACKED_PATH.read_text(encoding="utf-8")) or {}
    return list(data.get("repos") or [])


def fetch_repo(full_name: str, token: str = "") -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{full_name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenSourceNews-traction",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def metrics_from_api(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "stars_total": data.get("stargazers_count") or 0,
        "forks_total": data.get("forks_count") or 0,
        "open_issues": data.get("open_issues_count") or 0,
        "has_license": bool(data.get("license")),
        "has_ci": True,  # unknown without Actions lookup; optimistic default for tracked set
        "docs_present": bool(data.get("has_pages") or data.get("homepage")),
        "archived": bool(data.get("archived")),
        "contributors": 0,
        "contributors_active": 0,
        "pr_merge_rate": 0.5,
        "discussion_activity": 0,
        "stars_delta_7d": 0,
        "forks_delta_7d": 0,
        "commits_delta_7d": 0,
        "dependents_proxy": int((data.get("stargazers_count") or 0) / 50),
        "pushed_at": data.get("pushed_at") or "",
        "html_url": data.get("html_url") or "",
        "description": data.get("description") or "",
    }


def placeholder_metrics(full_name: str) -> Dict[str, Any]:
    # Deterministic placeholders so offline CI still produces artifacts.
    seed = sum(ord(c) for c in full_name) % 100
    return {
        "stars_total": 1000 + seed * 50,
        "forks_total": 100 + seed,
        "open_issues": 20 + (seed % 40),
        "has_license": True,
        "has_ci": True,
        "docs_present": seed % 2 == 0,
        "archived": False,
        "contributors": 10 + seed % 30,
        "contributors_active": 5 + seed % 15,
        "pr_merge_rate": 0.4 + (seed % 50) / 100.0,
        "discussion_activity": seed % 20,
        "stars_delta_7d": seed % 25,
        "forks_delta_7d": seed % 8,
        "commits_delta_7d": seed % 15,
        "dependents_proxy": seed,
        "offline": True,
    }


def run(*, offline: bool = False, date: str = "") -> Dict[str, Any]:
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    weights = load_weights()
    gate = float(weights.get("quality_gate") or 60)
    report_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scores: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for repo in load_tracked():
        full_name = str(repo.get("full_name") or "").strip()
        if not full_name:
            continue
        topics = list(repo.get("topics") or [])
        try:
            if offline or not token:
                metrics = placeholder_metrics(full_name)
            else:
                data = fetch_repo(full_name, token=token)
                metrics = metrics_from_api(data)
            scores.append(score_repo(full_name, metrics, topics=topics, weights_cfg=weights))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append({"full_name": full_name, "error": str(exc)[:300]})
            metrics = placeholder_metrics(full_name)
            metrics["fetch_error"] = True
            scores.append(score_repo(full_name, metrics, topics=topics, weights_cfg=weights))

    scores.sort(key=lambda s: (-float(s.get("composite_score") or 0), s.get("full_name") or ""))
    gated = apply_quality_gate(scores)
    top = gated[:25]

    payload = {
        "schema": "open_source_news_github_traction.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "quality_gate": gate,
        "repo_count": len(scores),
        "passed_gate_count": len(gated),
        "weights": weights.get("weights") or {},
        "errors": errors,
        "scores": scores,
        "top": top,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(OUT_DIR / f"{report_date}.json", payload)
    _atomic_write_json(OUT_DIR / "latest.json", payload)
    _atomic_write_json(
        OUT_DIR / f"top_{report_date}.json",
        {
            "schema": "open_source_news_github_traction_top.v1",
            "report_date": report_date,
            "quality_gate": gate,
            "count": len(top),
            "repos": top,
        },
    )
    # Monday-friendly alias
    _atomic_write_json(OUT_DIR / "top_this_week.json", {"report_date": report_date, "repos": top})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Score tracked GitHub repos")
    parser.add_argument("--offline", action="store_true", help="Skip GitHub API")
    parser.add_argument("--date", default="")
    args = parser.parse_args()
    payload = run(offline=args.offline, date=args.date)
    print(
        f"GitHub traction: {payload['repo_count']} repos, "
        f"{payload['passed_gate_count']} passed gate>={payload['quality_gate']}"
    )


if __name__ == "__main__":
    main()
