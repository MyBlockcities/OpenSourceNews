"""Additional tests for collection-first schema, v2 export, and receipts."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.external_ingest import write_delivery_receipt
from services.news_schema import add_item_ids


def test_dedupe_canonical_collapses_tracking_variants():
    a = add_item_ids(
        {"title": "Same Story", "url": "https://news.example/a", "bucket": "ai"}
    )
    b = add_item_ids(
        {
            "title": "Same Story",
            "url": "https://news.example/a?utm_source=rss&fbclid=xyz",
            "bucket": "ai",
        }
    )
    assert a["signal_id"] == b["signal_id"]
    assert a["canonical_url"] == b["canonical_url"] == "https://news.example/a"


def test_enrichment_pending_and_content_hash():
    item = add_item_ids(
        {
            "title": "Collected",
            "url": "https://example.com/c",
            "bucket": "general",
            "enrichment_status": "pending",
            "excerpt": "short",
        }
    )
    assert item["enrichment_status"] == "pending"
    assert item["content_hash"]


def test_v2_canonical_and_occurrence_ids_differ(tmp_path, monkeypatch):
    daily = tmp_path / "daily"
    daily.mkdir()
    report = {
        "AI": [
            {
                "title": "Signal One",
                "url": "https://example.com/one",
                "source": "RSS",
                "bucket": "ai",
                "summary": "hello",
                "signal_id": "sig001",
                "cluster_id": "clu001",
            }
        ]
    }
    (daily / "2026-08-01.json").write_text(json.dumps(report), encoding="utf-8")
    (daily / "2026-08-02.json").write_text(json.dumps(report), encoding="utf-8")

    import scripts.export_qdrant_payload_v2 as v2

    monkeypatch.setattr(v2, "DAILY_DIR", daily)
    occurrences, canonicals = v2.collect_occurrences(days=30)
    assert len(canonicals) == 1
    assert len(occurrences) == 2
    canon_id = list(canonicals.values())[0]["id"]
    occ_ids = {o["id"] for o in occurrences}
    assert canon_id not in occ_ids
    payload = list(canonicals.values())[0]["payload"]
    assert payload["occurrence_count"] == 2
    assert payload["first_seen"] == "2026-08-01"
    assert payload["last_seen"] == "2026-08-02"
    assert list(canonicals.values())[0]["embedding_text"] == ""


def test_delivery_receipt_written(tmp_path, monkeypatch):
    import services.external_ingest as ingest

    monkeypatch.setattr(ingest, "RECEIPTS_DIR", tmp_path)
    path = write_delivery_receipt(
        destination="academy",
        report_date="2026-08-03",
        ok=True,
        message="ok (200)",
        url="https://example.com/ingest",
        status_code=200,
        item_count=3,
        response_body='{"ack":true}',
    )
    assert path is not None and path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "open_source_news_ingest_receipt.v1"
    assert data["ok"] is True
    assert data["response_sha256"] == hashlib.sha256(b'{"ack":true}').hexdigest()
