"""Site-change collector: hash a public page and extract document links.

Sources using this adapter stay ``enabled: false`` until a nightly dry-run
proves the endpoint is stable. This collector never logs in, never bypasses
paywalls, and never downloads attachments.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from collectors import observation
from collectors.base import polite_get
from services.news_schema import canonicalize_url, truncate_excerpt, utc_now_iso
from services.outbound_evidence import classify_url
from services.sensitive_document_policy import evaluate_url

ADAPTER_VERSION = "site_change.v1"
STATE_DIR = Path(__file__).resolve().parents[1] / "outputs" / "site_change_state"
_HREF_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
_DOC_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip")


def _page_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _load_state(source_id: str) -> Dict[str, Any]:
    path = STATE_DIR / f"{source_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(source_id: str, state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{source_id}.json"
    tmp = STATE_DIR / f"{source_id}.json.tmp"
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def extract_document_hrefs(html: str, base_url: str) -> List[str]:
    urls: List[str] = []
    seen = set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', html or "", flags=re.I):
        canonical = canonicalize_url(urljoin(base_url, href))
        if not canonical or canonical in seen:
            continue
        path = canonical.lower()
        classification = classify_url(canonical)
        if path.endswith(_DOC_SUFFIXES) or classification in {
            "primary_record_candidate",
            "agency_filing",
            "court_record",
            "patent_record",
            "document_file",
            "archive_index",
        }:
            seen.add(canonical)
            urls.append(canonical)
    return urls[:50]


def collect_site_change(
    source: Dict[str, Any],
    *,
    persist_state: bool = True,
) -> List[Dict[str, Any]]:
    """Return observations when the page hash changes, plus document-link leads.

    A first fetch records baseline state and does not emit a fake 'new documents'
    burst beyond the current link list labelled as baseline.
    """
    source_id = str(source.get("id") or "unknown")
    endpoints = list(source.get("endpoints") or [])
    rps = float((source.get("rate_limit") or {}).get("requests_per_second") or 0.2)
    min_interval = 1.0 / rps if rps > 0 else 5.0
    out: List[Dict[str, Any]] = []
    state = _load_state(source_id) if persist_state else {}

    for url in endpoints:
        try:
            resp = polite_get(url, min_interval=min_interval)
            resp.raise_for_status()
        except Exception as exc:
            out.append(
                observation(
                    source_id=source_id,
                    canonical_url=url,
                    original_url=url,
                    fetched_at=utc_now_iso(),
                    adapter="site_change",
                    adapter_version=ADAPTER_VERSION,
                    error_class="fetch_failed",
                    error_message=str(exc)[:300],
                    title="",
                    author="",
                    excerpt="",
                )
            )
            continue

        digest = _page_hash(resp.content)
        previous = (state.get("pages") or {}).get(url) or {}
        changed = previous.get("hash") != digest
        html = resp.text if "html" in (resp.headers.get("content-type") or "") else ""
        title = ""
        links: List[str] = []
        if html:
            match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
            title = re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
            links = extract_document_hrefs(html, url)

        if persist_state:
            pages = dict(state.get("pages") or {})
            pages[url] = {"hash": digest, "fetched_at": utc_now_iso(), "link_count": len(links)}
            state["pages"] = pages
            _save_state(source_id, state)

        excerpt = truncate_excerpt(
            f"site_change {'changed' if changed else 'unchanged'}; {len(links)} document leads"
        )
        out.append(
            observation(
                source_id=source_id,
                canonical_url=canonicalize_url(url),
                original_url=url,
                fetched_at=utc_now_iso(),
                http_status=resp.status_code,
                etag=resp.headers.get("ETag"),
                last_modified=resp.headers.get("Last-Modified"),
                content_type=resp.headers.get("Content-Type"),
                raw_content_hash=digest,
                title=title or source.get("name") or source_id,
                author=source.get("publisher") or "",
                excerpt=excerpt,
                adapter="site_change",
                adapter_version=ADAPTER_VERSION,
                changed=changed,
                baseline=not previous,
                document_links=links[:50],
            )
        )
        for link in links:
            policy = evaluate_url(link)
            if policy["policy_status"] == "blocked_sensitive":
                continue
            out.append(
                observation(
                    source_id=source_id,
                    canonical_url=link,
                    original_url=link,
                    fetched_at=utc_now_iso(),
                    title=f"Document lead from {source.get('name') or source_id}",
                    author=source.get("publisher") or "",
                    excerpt=truncate_excerpt(link),
                    adapter="site_change",
                    adapter_version=ADAPTER_VERSION,
                    classification=classify_url(link),
                    parent_page=url,
                )
            )
    return out
