"""
Optional outbound POST after a daily digest is produced.

Set AGENCY_INGEST_URL or EXTERNAL_INGEST_URL to push JSON to another system
(e.g. agents / Agency backend). Disabled when unset — safe for public clones.

Payload schema: open_source_news_daily_digest.v1
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

DEFAULT_TIMEOUT = int(os.environ.get("EXTERNAL_INGEST_TIMEOUT", "90"))
MAX_MARKDOWN_CHARS = int(os.environ.get("EXTERNAL_INGEST_MAX_MARKDOWN_CHARS", "200000"))


def _truthy(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _resolve_url() -> str:
    return (
        os.environ.get("AGENCY_INGEST_URL", "").strip()
        or os.environ.get("EXTERNAL_INGEST_URL", "").strip()
    )


def _resolve_bearer() -> str:
    return (
        os.environ.get("AGENCY_INGEST_BEARER_TOKEN", "").strip()
        or os.environ.get("EXTERNAL_INGEST_BEARER_TOKEN", "").strip()
    )


def _resolve_headers() -> Dict[str, str]:
    """Optional JSON in EXTERNAL_INGEST_HEADERS='{"X-Custom":"v"}'"""
    raw = os.environ.get("EXTERNAL_INGEST_HEADERS", "").strip()
    if not raw:
        return {}
    return json.loads(raw)


def post_daily_digest(
    *,
    report_date: str,
    report: Dict[str, Any],
    markdown_path: Optional[Path] = None,
) -> tuple[bool, str]:
    """
    POST JSON to configured URL. Returns (ok, message).

    Environment (any of):
      AGENCY_INGEST_URL or EXTERNAL_INGEST_URL — full https URL (required to enable)
      AGENCY_INGEST_BEARER_TOKEN or EXTERNAL_INGEST_BEARER_TOKEN — optional Bearer auth
      EXTERNAL_INGEST_HEADERS — optional JSON object of extra headers
      EXTERNAL_INGEST_ENABLED — set to 0/false to disable even if URL is set
      EXTERNAL_INGEST_INCLUDE_MARKDOWN — default 1; include markdown body in payload
    """
    if not _truthy("EXTERNAL_INGEST_ENABLED", default=True):
        return True, "disabled (EXTERNAL_INGEST_ENABLED=0)"

    url = _resolve_url()
    if not url:
        return True, "skipped (no ingest URL)"

    lowered_url = url.lower()
    local_http = lowered_url.startswith("http://localhost") or lowered_url.startswith("http://127.0.0.1")
    if not lowered_url.startswith("https://") and not local_http:
        return False, "ingest URL must be https:// unless it targets localhost"

    markdown_text: Optional[str] = None
    if markdown_path and _truthy("EXTERNAL_INGEST_INCLUDE_MARKDOWN", default=True):
        try:
            raw_md = markdown_path.read_text(encoding="utf-8")
            if len(raw_md) > MAX_MARKDOWN_CHARS:
                raw_md = raw_md[:MAX_MARKDOWN_CHARS] + "\n\n[truncated by EXTERNAL_INGEST_MAX_MARKDOWN_CHARS]"
            markdown_text = raw_md
        except OSError as e:
            markdown_text = f"[could not read markdown: {e}]"

    payload: Dict[str, Any] = {
        "schema": "open_source_news_daily_digest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report_date": report_date,
        "report": report,
        "meta": {
            "source": "open_source_news",
            "pipeline": "pipelines/daily_run.py",
        },
    }
    if markdown_text is not None:
        payload["markdown"] = markdown_text

    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "OpenSourceNews-daily-ingest/1.0",
    }
    token = _resolve_bearer()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers.update(_resolve_headers())

    r = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code}: {r.text[:500]}"
    return True, f"ok ({r.status_code})"


def maybe_push_daily_digest(
    *,
    report_date: str,
    report: Dict[str, Any],
    markdown_path: Optional[Path] = None,
) -> None:
    """Call post_daily_digest; log only — never raises."""
    try:
        ok, msg = post_daily_digest(
            report_date=report_date, report=report, markdown_path=markdown_path
        )
        if "skipped" in msg or "disabled" in msg:
            return
        if ok:
            print(f"  ✓ External ingest: {msg}")
        else:
            print(f"  WARNING: External ingest failed: {msg}")
    except json.JSONDecodeError as e:
        print(f"  WARNING: EXTERNAL_INGEST_HEADERS must be valid JSON: {e}")
    except requests.RequestException as e:
        print(f"  WARNING: External ingest request error: {e}")
