"""Document provenance labels for public-record candidates.

Collect-only runs typically have a URL, not the file bytes. Hashing happens
when a lawful local archive copy exists. This module never treats an archive
host as proof of the commentator's interpretation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from services.news_schema import canonicalize_url, utc_now_iso
from services.outbound_evidence import classify_url, provenance_status_for_url


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def asserted_origin(url: str) -> Dict[str, Optional[str]]:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    return {
        "host": host,
        "scheme": parsed.scheme.lower() if parsed.scheme else "",
        "path": parsed.path or "",
    }


def provenance_record(
    url: str,
    *,
    parent_signal_id: str = "",
    archive_path: Optional[Path] = None,
    content: Optional[bytes] = None,
) -> Dict[str, Any]:
    canonical = canonicalize_url(url)
    status = provenance_status_for_url(canonical)
    content_hash = None
    if content is not None:
        content_hash = sha256_bytes(content)
    elif archive_path is not None and archive_path.exists():
        content_hash = sha256_file(archive_path)
    authenticity = {
        "official_hosted": "official",
        "archive_hosted": "archive_attributed",
        "mirrored": "unknown",
        "unverified": "unknown",
    }.get(status, "unknown")
    return {
        "schema": "document_provenance.v1",
        "parent_signal_id": parent_signal_id,
        "canonical_url": canonical,
        "classification": classify_url(canonical),
        "provenance_status": status,
        "authenticity": authenticity,
        "asserted_origin": asserted_origin(canonical),
        "content_hash": content_hash,
        "archive_path": str(archive_path) if archive_path else None,
        "recorded_at": utc_now_iso(),
        "interpretation_bound": False,
        "notes": "Archive or leak hosting does not prove the surrounding interpretation.",
    }
