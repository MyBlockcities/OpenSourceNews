"""Fail-closed policy for sensitive public-document leads.

The sensor may record that a lead exists. It must not copy or expose
credentials, private-person data, medical records, financial accounts,
exploit code, or datasets with uncertain redistribution rights.
"""

from __future__ import annotations

import re
from typing import Any, Dict
from urllib.parse import urlparse

BLOCKED_HOST_MARKERS = (
    "pastebin.com/raw",
    "ghostbin",
    "anonfiles",
)
BLOCKED_PATH_RE = re.compile(
    r"(password|passwd|secret|credential|doxx|ssn|social-security|medical-record|bank-account|exploit|0day)",
    re.I,
)
RESTRICTED_ARCHIVE_HOSTS = frozenset(
    {
        "ddosecrets.org",
        "www.ddosecrets.org",
        "ddosecrets.com",
    }
)
PERSONAL_DATA_HINTS = re.compile(
    r"\b(ssn|social security|passport|home address|phone number|medical record|patient|doxx)\b",
    re.I,
)


def evaluate_url(url: str, *, classification: str = "", context_text: str = "") -> Dict[str, Any]:
    parsed = urlparse(url or "")
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "") + ("?" + parsed.query if parsed.query else "")
    notes = []
    blocked = False

    if host in RESTRICTED_ARCHIVE_HOSTS:
        blocked = True
        notes.append("Restricted leak-archive host: metadata-only, no download.")
    if any(marker in (host + path).lower() for marker in BLOCKED_HOST_MARKERS):
        blocked = True
        notes.append("Paste/dump host is blocked.")
    if BLOCKED_PATH_RE.search(path):
        blocked = True
        notes.append("URL path looks like credentials, private data, or exploit material.")
    if PERSONAL_DATA_HINTS.search(context_text or ""):
        blocked = True
        notes.append("Surrounding text suggests personal or medical data.")
    if classification == "document_file" and host in RESTRICTED_ARCHIVE_HOSTS:
        blocked = True

    if blocked:
        return {
            "policy_status": "blocked_sensitive",
            "download_allowed": False,
            "extract_personal_data": False,
            "notes": " ".join(notes),
        }
    if classification in {"unknown", "secondary_commentary"}:
        return {
            "policy_status": "needs_review",
            "download_allowed": False,
            "extract_personal_data": False,
            "notes": "Not a recognized primary-record host.",
        }
    return {
        "policy_status": "allowed_metadata",
        "download_allowed": False,  # collect-only: never auto-download
        "extract_personal_data": False,
        "notes": "Metadata capture only; Agency decides whether to retrieve the document.",
    }


def allow_download(policy: Dict[str, Any]) -> bool:
    return bool(policy.get("download_allowed"))
