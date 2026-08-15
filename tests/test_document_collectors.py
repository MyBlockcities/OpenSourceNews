"""Site-change / document-index collector guards."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.document_index import collect_document_index
from collectors.foia_archive import collect_foia_archive
from collectors.site_change import extract_document_hrefs


def test_extracts_pdf_and_gov_links():
    html = """
    <html><body>
      <a href="/files/doc.pdf">PDF</a>
      <a href="https://www.sec.gov/Archives/edgar/data/1/a.htm">EDGAR</a>
      <a href="https://example.com/about">About</a>
    </body></html>
    """
    urls = extract_document_hrefs(html, "https://archive.example/")
    assert any(u.endswith(".pdf") for u in urls)
    assert any("sec.gov" in u for u in urls)
    assert not any(u.endswith("/about") for u in urls)


def test_document_index_refuses_downloads():
    with pytest.raises(ValueError, match="download_attachments"):
        collect_document_index(
            {
                "id": "restricted",
                "download_attachments": True,
                "endpoints": ["https://example.com/"],
            }
        )


def test_foia_archive_refuses_personal_data_extraction():
    with pytest.raises(ValueError, match="personal data"):
        collect_foia_archive(
            {
                "id": "muckrock",
                "extract_personal_data": True,
                "endpoints": ["https://www.muckrock.com/"],
            }
        )
