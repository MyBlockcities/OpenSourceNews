"""Schema and helpers for the GitHub traction pipeline.

A `Repo` is a snapshot of one tracked repository on one day. A `RepoScore`
is the composite score computed from that snapshot. Repos are tracked
deterministically from `config/tracked_repos.yaml`. New ones are
discovered via GitHub Trending + explicit add.

All IDs are uuid5-derived for stability across runs.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.news_schema import utc_now_iso

# Stable namespace for repo IDs (uuid5 over owner/name).
_REPO_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews#repo"
)

# Snapshot namespace (one per day per repo).
_SNAPSHOT_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews#repo_snapshot"
)

DEFAULT_REPO_DIR = Path(__file__).resolve().parents[1] / "outputs" / "github_traction"


def make_repo_id(owner: str, name: str) -> str:
    return uuid.uuid5(_REPO_NAMESPACE, f"{(owner or '').strip().lower()}/{(name or '').strip().lower()}").hex[:24]


def make_snapshot_id(repo_id: str, report_date: str) -> str:
    return uuid.uuid5(_SNAPSHOT_NAMESPACE, f"{repo_id}|{report_date}").hex[:24]


def _coerce_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _coerce_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_owner_name(repo_url: str) -> tuple[str, str]:
    """Parse a github.com URL (or owner/name) into (owner, name)."""
    s = (repo_url or "").strip().rstrip("/")
    s = re.sub(r"^https?://github\.com/", "", s)
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ""
    return "", ""


def repo_from_github_api(api_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a GitHub API repo payload into our internal Repo dict.

    Only stable, public fields. No secrets.
    """
    owner = ""
    name = ""
    if isinstance(api_payload.get("owner"), dict):
        owner = (api_payload["owner"].get("login") or "").strip()
    full_name = (api_payload.get("full_name") or "").strip()
    if not owner and full_name and "/" in full_name:
        owner, name = full_name.split("/", 1)
    if not name:
        name = (api_payload.get("name") or "").strip()
    license_info = api_payload.get("license") or {}
    license_id = (
        (license_info.get("spdx_id") if isinstance(license_info, dict) else None)
        or (license_info.get("key") if isinstance(license_info, dict) else None)
        or ""
    )
    return {
        "repo_id": make_repo_id(owner, name),
        "full_name": full_name or f"{owner}/{name}",
        "owner": owner,
        "name": name,
        "canonical_url": (api_payload.get("html_url") or f"https://github.com/{owner}/{name}").strip(),
        "description": (api_payload.get("description") or "").strip(),
        "primary_language": (api_payload.get("language") or "").strip(),
        "topics": list(api_payload.get("topics") or []),
        "license": license_id,
        "stars_total": _coerce_int(api_payload.get("stargazers_count")),
        "forks_total": _coerce_int(api_payload.get("forks_count")),
        "open_issues": _coerce_int(api_payload.get("open_issues_count")),
        "watchers_total": _coerce_int(api_payload.get("subscribers_count")),
        "created_at": (api_payload.get("created_at") or "").strip() or None,
        "pushed_at": (api_payload.get("pushed_at") or "").strip() or None,
        "updated_at": (api_payload.get("updated_at") or "").strip() or None,
        "default_branch": (api_payload.get("default_branch") or "").strip(),
        "is_archived": bool(api_payload.get("archived")),
        "is_fork": bool(api_payload.get("fork")),
        "schema_version": "repo.v1",
    }


def snapshot_from_repo(
    repo: Dict[str, Any],
    *,
    report_date: str,
    star_velocity_7d: Optional[float] = None,
    star_velocity_30d: Optional[float] = None,
    fork_velocity_7d: Optional[float] = None,
    contributor_count_30d: Optional[int] = None,
    release_count_90d: Optional[int] = None,
    days_since_last_commit: Optional[int] = None,
    bus_factor: Optional[float] = None,
    issue_close_rate_30d: Optional[float] = None,
    median_first_response_hours: Optional[float] = None,
    dependents_count: Optional[int] = None,
    forks_with_prs_back: Optional[int] = None,
    cross_platform_count: Optional[int] = None,
    hn_mentions_30d: Optional[int] = None,
    reddit_mentions_30d: Optional[int] = None,
    public_topics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a per-day snapshot of a repo with all the metrics we track."""
    return {
        "snapshot_id": make_snapshot_id(repo["repo_id"], report_date),
        "repo_id": repo["repo_id"],
        "full_name": repo.get("full_name", ""),
        "report_date": report_date,
        "stars_total": repo.get("stars_total"),
        "forks_total": repo.get("forks_total"),
        "open_issues": repo.get("open_issues"),
        "star_velocity_7d": star_velocity_7d,
        "star_velocity_30d": star_velocity_30d,
        "acceleration": (
            round((star_velocity_7d - star_velocity_30d) / star_velocity_30d, 3)
            if star_velocity_7d is not None
            and star_velocity_30d
            and star_velocity_30d > 0
            else None
        ),
        "fork_velocity_7d": fork_velocity_7d,
        "contributor_count_30d": contributor_count_30d,
        "release_count_90d": release_count_90d,
        "days_since_last_commit": days_since_last_commit,
        "bus_factor": bus_factor,
        "issue_close_rate_30d": issue_close_rate_30d,
        "median_first_response_hours": median_first_response_hours,
        "dependents_count": dependents_count,
        "forks_with_prs_back": forks_with_prs_back,
        "cross_platform_count": cross_platform_count,
        "hn_mentions_30d": hn_mentions_30d,
        "reddit_mentions_30d": reddit_mentions_30d,
        "primary_language": repo.get("primary_language", ""),
        "license": repo.get("license", ""),
        "topics": list(repo.get("topics") or []),
        "public_topics": list(public_topics or []),
        "is_archived": bool(repo.get("is_archived", False)),
        "is_fork": bool(repo.get("is_fork", False)),
        "schema_version": "repo_snapshot.v1",
    }
