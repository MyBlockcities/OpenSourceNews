"""Extract and classify outbound primary-document links from public items.

This does not download attachments. It preserves the claim→link relationship
and labels each URL as a primary-record candidate, archive index, or commentary.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from services.news_schema import canonicalize_url
from services.sensitive_document_policy import evaluate_url

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)

PRIMARY_HOST_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".mil",
)
PRIMARY_HOSTS = frozenset(
    {
        "sec.gov",
        "www.sec.gov",
        "data.sec.gov",
        "federalregister.gov",
        "www.federalregister.gov",
        "regulations.gov",
        "www.regulations.gov",
        "congress.gov",
        "www.congress.gov",
        "govinfo.gov",
        "www.govinfo.gov",
        "courtlistener.com",
        "www.courtlistener.com",
        "pacer.gov",
        "ecf.uscourts.gov",
        "www.uspto.gov",
        "patents.google.com",
        "patentscope.wipo.int",
        "clinicaltrials.gov",
        "earthquake.usgs.gov",
        "eonet.gsfc.nasa.gov",
        "reliefweb.int",
        "gdacs.org",
        "www.gdacs.org",
        "federalreserve.gov",
        "www.federalreserve.gov",
        "bls.gov",
        "www.bls.gov",
        "bea.gov",
        "www.bea.gov",
        "treasury.gov",
        "home.treasury.gov",
        "bis.org",
        "www.bis.org",
        "ecb.europa.eu",
        "www.ecb.europa.eu",
        "imf.org",
        "www.imf.org",
        "eia.gov",
        "www.eia.gov",
        "nrel.gov",
        "www.nrel.gov",
        "osti.gov",
        "www.osti.gov",
    }
)
ARCHIVE_HOSTS = frozenset(
    {
        "nsarchive.gwu.edu",
        "nsarchive2.gwu.edu",
        "www.theblackvault.com",
        "theblackvault.com",
        "www.muckrock.com",
        "muckrock.com",
        "ddosecrets.org",
        "www.ddosecrets.org",
        "archive.org",
        "web.archive.org",
        "usrtk.org",
        "www.usrtk.org",
    }
)
COMMENTARY_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "x.com",
        "twitter.com",
        "substack.com",
        "medium.com",
        "reddit.com",
        "www.reddit.com",
        "news.ycombinator.com",
    }
)
DOCUMENT_SUFFIXES = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".zip")


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def _path(url: str) -> str:
    return (urlparse(url).path or "").lower()


def classify_url(url: str) -> str:
    host = _host(url)
    path = _path(url)
    if path.endswith(DOCUMENT_SUFFIXES):
        if host in PRIMARY_HOSTS or host.endswith(PRIMARY_HOST_SUFFIXES):
            return "primary_record_candidate"
        if host in ARCHIVE_HOSTS:
            return "document_file"
        return "document_file"
    if "patent" in host or "/patent" in path:
        return "patent_record"
    if any(token in host for token in ("courtlistener", "uscourts", "pacer", "supremecourt")):
        return "court_record"
    if host in {"sec.gov", "www.sec.gov", "data.sec.gov"} or "/edgar" in path:
        return "agency_filing"
    if "federalregister" in host or "regulations.gov" in host:
        return "agency_filing"
    if host in {
        "arxiv.org",
        "export.arxiv.org",
        "rss.arxiv.org",
        "pubmed.ncbi.nlm.nih.gov",
        "doi.org",
        "dx.doi.org",
    }:
        return "research_repository"
    if host in PRIMARY_HOSTS or host.endswith(PRIMARY_HOST_SUFFIXES):
        return "agency_filing"
    if host in ARCHIVE_HOSTS:
        return "archive_index"
    if host in COMMENTARY_HOSTS:
        return "secondary_commentary"
    return "unknown"


def provenance_status_for_url(url: str) -> str:
    host = _host(url)
    if host in PRIMARY_HOSTS or host.endswith(PRIMARY_HOST_SUFFIXES):
        return "official_hosted"
    if host in ARCHIVE_HOSTS or host.endswith("archive.org"):
        return "archive_hosted"
    return "unverified"


def _iter_text_urls(item: Dict[str, Any]) -> List[str]:
    blobs = [
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("excerpt") or ""),
        str(item.get("url") or ""),
        str(item.get("canonical_url") or ""),
    ]
    for key in ("source_urls", "key_insights", "key_lessons"):
        value = item.get(key)
        if isinstance(value, list):
            blobs.extend(str(entry) for entry in value)
    text = " ".join(blobs)
    found = [canonicalize_url(match.rstrip(").,;")) for match in _URL_RE.findall(text)]
    return [url for url in found if url]


def make_evidence_id(parent_signal_id: str, url: str) -> str:
    value = f"{parent_signal_id}|{canonicalize_url(url)}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def extract_outbound_evidence(
    item: Dict[str, Any],
    *,
    include_self: bool = False,
) -> List[Dict[str, Any]]:
    """Return document_evidence.v1 records for outbound URLs on an item."""
    parent = str(item.get("signal_id") or "")
    self_urls = {
        canonicalize_url(str(item.get("canonical_url") or "")),
        canonicalize_url(str(item.get("url") or "")),
    }
    self_urls.discard("")
    records: List[Dict[str, Any]] = []
    seen = set()
    for url in _iter_text_urls(item):
        canonical = canonicalize_url(url)
        if not canonical or canonical in seen:
            continue
        if not include_self and canonical in self_urls:
            continue
        seen.add(canonical)
        classification = classify_url(canonical)
        policy = evaluate_url(canonical, classification=classification)
        records.append(
            {
                "schema": "document_evidence.v1",
                "evidence_id": make_evidence_id(parent, canonical),
                "parent_signal_id": parent,
                "url": url,
                "canonical_url": canonical,
                "classification": classification,
                "originating_institution": None,
                "jurisdiction": None,
                "document_identifier": None,
                "mime_hint": "application/pdf" if _path(canonical).endswith(".pdf") else None,
                "provenance_status": provenance_status_for_url(canonical),
                "authenticity": "official"
                if provenance_status_for_url(canonical) == "official_hosted"
                else "unknown",
                "policy_status": policy["policy_status"],
                "download_allowed": policy["download_allowed"],
                "corroboration": classification
                in {
                    "primary_record_candidate",
                    "agency_filing",
                    "court_record",
                    "patent_record",
                    "research_repository",
                },
                "notes": policy.get("notes") or "",
            }
        )
    return records


def attach_outbound_evidence(item: Dict[str, Any]) -> Dict[str, Any]:
    evidence = extract_outbound_evidence(item)
    item["outbound_evidence"] = evidence
    item["primary_record_link_count"] = sum(
        1
        for rec in evidence
        if rec.get("corroboration") and rec.get("policy_status") != "blocked_sensitive"
    )
    return item


def extract_from_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.extend(extract_outbound_evidence(item))
    return out
