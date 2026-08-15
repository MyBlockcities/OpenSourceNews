"""Base collector helpers: polite rate limits and degraded receipts."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from collectors import observation
from services.news_schema import utc_now_iso

DEFAULT_HEADERS = {
    "User-Agent": "OpenSourceNews/1.0 (+https://github.com/MyBlockcities/OpenSourceNews)"
}


class CollectorError(Exception):
    def __init__(self, message: str, error_class: str = "collector_error"):
        super().__init__(message)
        self.error_class = error_class


def polite_get(
    url: str,
    *,
    timeout: int = 20,
    headers: Optional[Dict[str, str]] = None,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
    min_interval: float = 0.0,
) -> requests.Response:
    if min_interval > 0:
        time.sleep(min_interval)
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    if etag:
        req_headers["If-None-Match"] = etag
    if last_modified:
        req_headers["If-Modified-Since"] = last_modified
    return requests.get(url, headers=req_headers, timeout=timeout)


def degraded_observation(source_id: str, url: str, error_class: str, message: str) -> Dict[str, Any]:
    return observation(
        source_id=source_id,
        canonical_url=url,
        original_url=url,
        fetched_at=utc_now_iso(),
        title="",
        author="",
        excerpt="",
        adapter="unknown",
        adapter_version="1",
        error_class=error_class,
        error_message=message,
    )
