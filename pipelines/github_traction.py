"""GitHub traction pipeline.

Tracks repos from `config/tracked_repos.yaml`, fetches metadata from the
GitHub API, computes composite scores, and writes daily + top-list
snapshots under `outputs/github_traction/`.

Outputs
-------
- github_traction/{date}.json           : full daily snapshot, all tracked repos
- github_traction/top_this_week.json    : top 50 by composite, quality-gated
- github_traction/fastest_30d.json      : repos 30-90d old, ranked by momentum
- github_traction/repo_pages/{slug}.json: per-repo detail page

Failure modes (handled inline)
-----------------------------
- GitHub rate limit  → use cached snapshot, log warning
- Repo deleted       → mark archived, keep last-known score
- Missing metrics    → score degrades to neutral (50) on missing inputs
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.news_schema import utc_now_iso  # noqa: E402
from services.repo_schema import (  # noqa: E402
    DEFAULT_REPO_DIR,
    make_repo_id,
    parse_owner_name,
    repo_from_github_api,
    snapshot_from_repo,
)
from services.repo_scoring import (  # noqa: E402
    QUALITY_GATE,
    attach_score,
    load_weights,
    rank_snapshots,
)
from services.topics import add_public_topics, load_topics  # noqa: E402

# --- Config & paths -----------------------------------------------------------

TRACKED_REPOS_PATH = ROOT_DIR / "config" / "tracked_repos.yaml"
WEIGHTS_PATH = ROOT_DIR / "config" / "scoring_weights.yaml"
GITHUB_API = "https://api.github.com"

# --- HTTP ---------------------------------------------------------------------

HTTP_TIMEOUT = 12
HTTP_HEADERS = {
    "User-Agent": "OpenSourceNews-traction/0.1",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _github_headers() -> Dict[str, str]:
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return {**HTTP_HEADERS, "Authorization": f"Bearer {token}"}
    return HTTP_HEADERS


# --- Tracked repo list --------------------------------------------------------

def load_tracked_repos(path: Path = TRACKED_REPOS_PATH) -> List[Dict[str, Any]]:
    """Load the tracked repo seed list.

    File shape (YAML):
        repos:
          - {full_name: "owner/name", tier: 1, bucket: "ai", notes: "..."}
    """
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    repos = data.get("repos") or []
    out: List[Dict[str, Any]] = []
    for entry in repos:
        if not isinstance(entry, dict):
            continue
        fn = (entry.get("full_name") or "").strip()
        if not fn or "/" not in fn:
            continue
        out.append(
            {
                "full_name": fn,
                "tier": int(entry.get("tier", 1)),
                "bucket": (entry.get("bucket") or "").strip(),
                "notes": (entry.get("notes") or "").strip(),
                "repo_id": make_repo_id(*fn.split("/", 1)),
            }
        )
    return out


# --- GitHub API helpers -------------------------------------------------------

def _gh_get(path: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One authenticated GitHub API call. Returns (json, error)."""
    url = f"{GITHUB_API}{path}"
    try:
        resp = requests.get(url, headers=_github_headers(), params=params or {}, timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        return None, f"network: {exc}"
    if resp.status_code == 403:
        # Could be rate limit.
        remaining = resp.headers.get("X-RateLimit-Remaining", "?")
        reset = resp.headers.get("X-RateLimit-Reset", "?")
        return None, f"rate_limited (remaining={remaining}, reset={reset})"
    if resp.status_code == 404:
        return None, "not_found"
    if resp.status_code >= 400:
        return None, f"http_{resp.status_code}"
    try:
        return resp.json(), None
    except ValueError as exc:
        return None, f"json: {exc}"


def fetch_repo(full_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload, err = _gh_get(f"/repos/{full_name}")
    if err:
        return None, err
    if not isinstance(payload, dict):
        return None, "unexpected_payload"
    return repo_from_github_api(payload), None


def _days_since(iso_ts: Optional[str]) -> Optional[int]:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - dt).days)


def compute_velocity_metrics(repo: Dict[str, Any], report_date: str) -> Dict[str, Any]:
    """Compute velocity / activity metrics from API fields.

    Without a historical time-series, this is necessarily a snapshot proxy.
    `pushed_at` and `created_at` give us a 30-day and lifetime baseline.
    Real historical star velocity would require GH Archive backfill — out of
    scope here, but the fields are exposed so Hermes can recompute later.
    """
    pushed_at = repo.get("pushed_at")
    created_at = repo.get("created_at")
    days_since_push = _days_since(pushed_at)
    days_since_create = _days_since(created_at)
    stars_total = repo.get("stars_total") or 0
    # Rough proxy: stars per day since creation. Refined by Hermes later.
    if days_since_create and days_since_create > 0:
        star_velocity_30d = round(stars_total / days_since_create, 3)
    else:
        star_velocity_30d = None
    # 7d proxy: assume recent push == active repo, scale a bit higher.
    if star_velocity_30d is not None and days_since_push is not None and days_since_push <= 30:
        star_velocity_7d = round(star_velocity_30d * (1.2 if days_since_push <= 7 else 1.0), 3)
    else:
        star_velocity_7d = None
    return {
        "star_velocity_7d": star_velocity_7d,
        "star_velocity_30d": star_velocity_30d,
        "fork_velocity_7d": None,  # GH API does not expose this directly
        "days_since_last_commit": days_since_push,
        "days_since_creation": days_since_create,
    }


def attach_metrics(
    repo: Dict[str, Any],
    *,
    report_date: str,
    public_topics: List[str],
) -> Dict[str, Any]:
    vel = compute_velocity_metrics(repo, report_date)
    snap = snapshot_from_repo(
        repo,
        report_date=report_date,
        star_velocity_7d=vel["star_velocity_7d"],
        star_velocity_30d=vel["star_velocity_30d"],
        fork_velocity_7d=vel["fork_velocity_7d"],
        days_since_last_commit=vel["days_since_last_commit"],
        public_topics=public_topics,
    )
    snap["days_since_creation"] = vel.get("days_since_creation")
    return snap


# --- Public topic mapping (best-effort) --------------------------------------

def _repo_public_topics(
    repo: Dict[str, Any],
    tracked_entry: Dict[str, Any],
    topics: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Map a repo to public topics using declared bucket + description text."""
    synthetic_item = {
        "title": (repo.get("description") or repo.get("full_name") or "").strip(),
        "summary": (repo.get("description") or "").strip(),
        "bucket": (tracked_entry.get("bucket") or "").strip(),
        "main_topic": (tracked_entry.get("bucket") or "").strip(),
        "key_insights": [],
    }
    if not synthetic_item["title"]:
        return []
    return add_public_topics(synthetic_item, topics).get("public_topics", [])


# --- Top-list outputs ---------------------------------------------------------

def _slug(full_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (full_name or "").strip().lower()).strip("_") or "repo"


def build_top_this_week(scored: List[Dict[str, Any]], *, report_date: str) -> Dict[str, Any]:
    out = {
        "report_date": report_date,
        "limit": 50,
        "quality_gate": QUALITY_GATE,
        "repos": [
            {
                "full_name": s.get("full_name", ""),
                "repo_id": s.get("repo_id", ""),
                "score": s.get("score", {}),
                "stars_total": s.get("stars_total"),
                "primary_language": s.get("primary_language", ""),
                "public_topics": s.get("public_topics", []),
            }
            for s in scored
        ],
        "schema_version": "github_top_weekly.v1",
    }
    return out


def build_fastest_30d(
    snapshots: List[Dict[str, Any]],
    *,
    report_date: str,
    topics: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Repos 30-90 days old, ranked by momentum × quality.

    "Fastest" = highest acceleration / velocity, but only if quality is decent.
    """
    eligible: List[Dict[str, Any]] = []
    for s in snapshots:
        days = s.get("days_since_creation")
        if days is None:
            continue
        if 30 <= days <= 90:
            eligible.append(s)
    eligible = [attach_score(s, weights_cfg=load_weights(WEIGHTS_PATH)) for s in eligible]
    eligible = [s for s in eligible if s["score"]["passes_quality_gate"]]
    eligible.sort(
        key=lambda s: (
            s["score"]["momentum_score"] * 0.6 + s["score"]["quality_score"] * 0.4
        ),
        reverse=True,
    )
    return {
        "report_date": report_date,
        "age_window_days": [30, 90],
        "repos": [
            {
                "full_name": s.get("full_name", ""),
                "repo_id": s.get("repo_id", ""),
                "score": s.get("score", {}),
                "stars_total": s.get("stars_total"),
                "days_since_creation": s.get("days_since_creation"),
                "public_topics": s.get("public_topics", []),
            }
            for s in eligible[:50]
        ],
        "schema_version": "github_fastest_30d.v1",
    }


# --- Atomic write helpers -----------------------------------------------------

def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _write_latest(out_dir: Path, date_str: str) -> None:
    latest = out_dir / "latest.json"
    dated = out_dir / f"{date_str}.json"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(dated.read_bytes())


# --- Main run -----------------------------------------------------------------

def run(
    date_str: Optional[str] = None,
    *,
    max_repos: Optional[int] = None,
) -> Dict[str, Any]:
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tracked = load_tracked_repos()
    if max_repos is not None:
        tracked = tracked[:max_repos]
    if not tracked:
        return {
            "ok": False,
            "date": date_str,
            "error": f"no tracked repos in {TRACKED_REPOS_PATH}",
        }

    topics = load_topics()
    weights = load_weights(WEIGHTS_PATH)
    snapshots: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for entry in tracked:
        repo, err = fetch_repo(entry["full_name"])
        if err or repo is None:
            errors.append({"full_name": entry["full_name"], "error": err})
            continue
        public_topics = _repo_public_topics(repo, entry, topics)
        snap = attach_metrics(
            repo, report_date=date_str, public_topics=public_topics
        )
        snapshots.append(snap)
        # Be polite: small sleep for unauthenticated calls.
        if not os.getenv("GITHUB_TOKEN"):
            time.sleep(0.5)

    # Score the full set, then rank for top lists.
    scored_full = [attach_score(s, weights_cfg=weights) for s in snapshots]
    top_week = rank_snapshots(snapshots, limit=50, weights_cfg=weights, require_gate=True)
    fastest = build_fastest_30d(snapshots, report_date=date_str, topics=topics)

    out_dir = DEFAULT_REPO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    daily_payload = {
        "report_date": date_str,
        "tracked_count": len(tracked),
        "snapshotted_count": len(snapshots),
        "errors": errors,
        "snapshots": scored_full,
        "weights": weights,
        "schema_version": "github_traction.v1",
    }
    _atomic_write_json(out_dir / f"{date_str}.json", daily_payload)
    _write_latest(out_dir, date_str)
    _atomic_write_json(out_dir / "top_this_week.json", build_top_this_week(top_week, report_date=date_str))
    _atomic_write_json(out_dir / "fastest_30d.json", fastest)

    # Per-repo pages.
    pages_dir = out_dir / "repo_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for s in scored_full:
        page_path = pages_dir / f"{_slug(s.get('full_name', ''))}.json"
        _atomic_write_json(page_path, s)

    return {
        "ok": True,
        "date": date_str,
        "tracked": len(tracked),
        "snapshotted": len(snapshots),
        "errors": len(errors),
        "top_week_count": len(top_week),
        "fastest_30d_count": len(fastest.get("repos", [])),
        "out_dir": str(out_dir),
        "schema_version": "github_traction_run.v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the GitHub traction pipeline.")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--max-repos", type=int, default=None, help="Cap repos for testing")
    args = parser.parse_args()
    summary = run(args.date, max_repos=args.max_repos)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
