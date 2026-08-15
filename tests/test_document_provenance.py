"""Document provenance labels."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.document_provenance import provenance_record, sha256_bytes


def test_official_host_is_official_hosted():
    rec = provenance_record(
        "https://www.sec.gov/files/example.pdf",
        parent_signal_id="sig1",
    )
    assert rec["provenance_status"] == "official_hosted"
    assert rec["authenticity"] == "official"
    assert rec["interpretation_bound"] is False
    assert rec["content_hash"] is None


def test_archive_host_is_not_automatic_proof():
    rec = provenance_record("https://nsarchive.gwu.edu/briefing-book/example")
    assert rec["provenance_status"] == "archive_hosted"
    assert rec["authenticity"] == "archive_attributed"
    assert rec["interpretation_bound"] is False


def test_hash_when_bytes_present():
    rec = provenance_record(
        "https://www.sec.gov/files/example.pdf",
        content=b"%PDF-fake",
    )
    assert rec["content_hash"] == sha256_bytes(b"%PDF-fake")
