"""Common observation contract for collectors."""

from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict


class RawObservation(TypedDict, total=False):
    schema: str
    source_id: str
    canonical_url: str
    original_url: str
    published_at: Optional[str]
    fetched_at: str
    http_status: Optional[int]
    etag: Optional[str]
    last_modified: Optional[str]
    content_type: Optional[str]
    language: Optional[str]
    raw_content_hash: Optional[str]
    archive_path: Optional[str]
    title: str
    author: str
    excerpt: str
    rights: Optional[str]
    adapter: str
    adapter_version: str
    error_class: Optional[str]


def observation(**kwargs: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"schema": "raw_observation.v1"}
    payload.update(kwargs)
    payload.setdefault("error_class", None)
    return payload
