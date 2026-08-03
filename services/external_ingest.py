"""
Optional outbound POST after a daily digest is produced.

Set AGENCY_INGEST_URL or EXTERNAL_INGEST_URL to push JSON to another system
(e.g. agents / Agency backend). Disabled when unset — safe for public clones.

Payload schema: open_source_news_daily_digest.v1

Delivery receipts (optional): when a push is attempted, a local receipt is written
under outputs/ingest_receipts/ (gitignored). Set EXTERNAL_INGEST_RECEIPTS=0 to disable.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from services.news_schema import normalize_report
from pipelines.route_destinations import filter_for_destination, route_normalized

DEFAULT_TIMEOUT = int(os.environ.get("EXTERNAL_INGEST_TIMEOUT", "90"))
MAX_MARKDOWN_CHARS = int(os.environ.get("EXTERNAL_INGEST_MAX_MARKDOWN_CHARS", "200000"))
MAX_RETRIES = max(1, int(os.environ.get("EXTERNAL_INGEST_RETRIES", "3")))
ROOT_DIR = Path(__file__).resolve().parents[1]
RECEIPTS_DIR = ROOT_DIR / "outputs" / "ingest_receipts"


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_delivery_receipt(
    *,
    destination: str,
    report_date: str,
    ok: bool,
    message: str,
    url: str = "",
    status_code: Optional[int] = None,
    attempt: int = 1,
    item_count: Optional[int] = None,
    response_body: str = "",
) -> Optional[Path]:
    """Persist a local delivery receipt (never raises). Returns path or None."""
    if not _truthy("EXTERNAL_INGEST_RECEIPTS", default=True):
        return None
    try:
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "open_source_news_ingest_receipt.v1",
            "destination": destination,
            "report_date": report_date,
            "ok": ok,
            "message": message[:1000],
            "url_host": "",
            "status_code": status_code,
            "attempt": attempt,
            "item_count": item_count,
            "response_sha256": hashlib.sha256(response_body.encode("utf-8")).hexdigest()
            if response_body
            else "",
            "response_preview": (response_body or "")[:300],
            "recorded_at": _utc_now(),
        }
        if url:
            try:
                from urllib.parse import urlparse

                receipt["url_host"] = urlparse(url).netloc
            except Exception:  # noqa: BLE001
                receipt["url_host"] = ""
        path = RECEIPTS_DIR / f"{report_date}-{destination}.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not write ingest receipt: {exc}")
        return None


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
      EXTERNAL_INGEST_RECEIPTS — default 1; write local delivery receipts
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

    normalized = normalize_report(report_date, report)
    payload: Dict[str, Any] = {
        "schema": "open_source_news_daily_digest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report_date": report_date,
        "report": report,
        "normalized": normalized,
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

    last_message = "not attempted"
    last_status: Optional[int] = None
    last_body = ""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
            last_status = r.status_code
            last_body = r.text or ""
            if 200 <= r.status_code < 300:
                write_delivery_receipt(
                    destination="agency",
                    report_date=report_date,
                    ok=True,
                    message=f"ok ({r.status_code})",
                    url=url,
                    status_code=r.status_code,
                    attempt=attempt + 1,
                    item_count=(normalized.get("counts") or {}).get("total"),
                    response_body=last_body,
                )
                return True, f"ok ({r.status_code})"
            last_message = f"HTTP {r.status_code}: {r.text[:500]}"
            if r.status_code < 500:
                break
        except requests.RequestException as e:
            last_message = f"request error: {e}"

        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)

    write_delivery_receipt(
        destination="agency",
        report_date=report_date,
        ok=False,
        message=last_message,
        url=url,
        status_code=last_status,
        attempt=MAX_RETRIES,
        item_count=(normalized.get("counts") or {}).get("total"),
        response_body=last_body,
    )
    return False, last_message


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


# ---------------------------------------------------------------------------
# Per-destination ingest (closed-loop: academy / godseye)
# ---------------------------------------------------------------------------

_DESTINATION_ENV = {
    "academy": ("ACADEMY_INGEST_URL", "ACADEMY_INGEST_BEARER_TOKEN"),
    "godseye": ("GODSEYE_INGEST_URL", "GODSEYE_INGEST_BEARER_TOKEN"),
}


def post_destination_digest(
    destination: str,
    *,
    report_date: str,
    routed_normalized: Dict[str, Any],
) -> tuple[bool, str]:
    """
    POST the destination-filtered normalized payload to that destination's
    ingest endpoint. Returns (ok, message). Skips cleanly when the env URL is
    unset (safe for public clones).

    Environment:
      ACADEMY_INGEST_URL / ACADEMY_INGEST_BEARER_TOKEN
      GODSEYE_INGEST_URL / GODSEYE_INGEST_BEARER_TOKEN
    """
    if destination not in _DESTINATION_ENV:
        return False, f"unknown destination: {destination}"

    url_var, token_var = _DESTINATION_ENV[destination]
    url = os.environ.get(url_var, "").strip()
    if not url:
        return True, f"skipped (no {url_var})"

    lowered_url = url.lower()
    local_http = lowered_url.startswith("http://localhost") or lowered_url.startswith("http://127.0.0.1")
    if not lowered_url.startswith("https://") and not local_http:
        return False, f"{url_var} must be https:// unless it targets localhost"

    filtered = filter_for_destination(routed_normalized, destination)
    if not filtered.get("items"):
        return True, f"skipped (0 items routed to {destination})"

    payload: Dict[str, Any] = {
        "schema": "open_source_news_daily_digest.v1",
        "destination": destination,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report_date": report_date,
        "normalized": filtered,
        "meta": {
            "source": "open_source_news",
            "pipeline": "pipelines/daily_run.py",
            "router_version": "1",
        },
    }

    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "OpenSourceNews-daily-ingest/1.0",
    }
    token = os.environ.get(token_var, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_message = "not attempted"
    last_status: Optional[int] = None
    last_body = ""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
            last_status = r.status_code
            last_body = r.text or ""
            if 200 <= r.status_code < 300:
                msg = f"ok ({r.status_code}, {len(filtered['items'])} items)"
                write_delivery_receipt(
                    destination=destination,
                    report_date=report_date,
                    ok=True,
                    message=msg,
                    url=url,
                    status_code=r.status_code,
                    attempt=attempt + 1,
                    item_count=len(filtered["items"]),
                    response_body=last_body,
                )
                return True, msg
            last_message = f"HTTP {r.status_code}: {r.text[:500]}"
            if r.status_code < 500:
                break
        except requests.RequestException as e:
            last_message = f"request error: {e}"

        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)

    write_delivery_receipt(
        destination=destination,
        report_date=report_date,
        ok=False,
        message=last_message,
        url=url,
        status_code=last_status,
        attempt=MAX_RETRIES,
        item_count=len(filtered.get("items") or []),
        response_body=last_body,
    )
    return False, last_message


def maybe_push_destination_digests(
    *,
    report_date: str,
    report: Dict[str, Any],
) -> None:
    """
    Route the normalized report and POST one filtered payload per destination
    (academy, godseye). Log only — never raises, never fails the run.
    """
    try:
        normalized = normalize_report(report_date, report)
        routed = route_normalized(normalized)
        by_dest = (routed.get("counts") or {}).get("by_destination") or {}
        print(
            f"  Destination routing: academy={by_dest.get('academy', 0)} "
            f"godseye={by_dest.get('godseye', 0)} both={by_dest.get('both', 0)}"
        )
        for destination in ("academy", "godseye"):
            ok, msg = post_destination_digest(
                destination, report_date=report_date, routed_normalized=routed
            )
            if "skipped" in msg:
                continue
            if ok:
                print(f"  \u2713 {destination} ingest: {msg}")
            else:
                print(f"  WARNING: {destination} ingest failed: {msg}")
    except Exception as e:  # noqa: BLE001 — ingest must never break the daily run
        print(f"  WARNING: destination ingest error: {e}")
