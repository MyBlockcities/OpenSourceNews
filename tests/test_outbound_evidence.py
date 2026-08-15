"""Outbound document-link extraction."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.outbound_evidence import (
    attach_outbound_evidence,
    classify_url,
    extract_outbound_evidence,
)


def test_classifies_sec_and_federal_register():
    assert classify_url("https://www.sec.gov/Archives/edgar/data/1/0001/a.htm") == "agency_filing"
    assert classify_url("https://www.federalregister.gov/documents/2026/08/01/2026-1") == "agency_filing"
    assert classify_url("https://arxiv.org/abs/2608.12345") == "research_repository"
    assert classify_url("https://www.courtlistener.com/docket/123/") == "court_record"
    assert classify_url("https://patents.google.com/patent/US123") == "patent_record"
    assert classify_url("https://example.com/file.pdf") == "document_file"
    assert classify_url("https://www.youtube.com/watch?v=abc") == "secondary_commentary"


def test_extracts_primary_links_from_excerpt_not_self_url():
    item = {
        "signal_id": "abc123def456",
        "title": "FOIA dump",
        "url": "https://unlimitedhangout.com/2026/08/story",
        "canonical_url": "https://unlimitedhangout.com/2026/08/story",
        "excerpt": "See the filing at https://www.sec.gov/Archives/edgar/data/1/0001/filing.htm and https://www.federalregister.gov/d/2026-1",
    }
    recs = extract_outbound_evidence(item)
    urls = {r["canonical_url"] for r in recs}
    assert "https://unlimitedhangout.com/2026/08/story" not in urls
    assert any("sec.gov" in u for u in urls)
    assert any("federalregister.gov" in u for u in urls)
    assert all(r["schema"] == "document_evidence.v1" for r in recs)
    assert any(r["corroboration"] for r in recs)


def test_evidence_ids_are_stable():
    item = {
        "signal_id": "sig1",
        "url": "https://example.com/a",
        "excerpt": "https://www.sec.gov/files/example.pdf",
    }
    a = extract_outbound_evidence(item)
    b = extract_outbound_evidence(item)
    assert a and a[0]["evidence_id"] == b[0]["evidence_id"]


def test_attach_counts_primary_links():
    item = {
        "signal_id": "sig2",
        "url": "https://usrtk.org/story",
        "excerpt": "Document: https://www.sec.gov/files/x.pdf",
    }
    attach_outbound_evidence(item)
    assert item["primary_record_link_count"] >= 1
    assert item["outbound_evidence"]
