#!/usr/bin/env python3
"""Extract public document leads from a daily report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.outbound_evidence import extract_outbound_evidence  # noqa: E402
from services.news_schema import add_item_ids  # noqa: E402

DAILY_DIR = ROOT_DIR / "outputs" / "daily"
OUT_DIR = ROOT_DIR / "outputs" / "document_leads"


def run(date_str: str | None = None) -> Dict[str, Any]:
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = DAILY_DIR / f"{date_str}.json"
    if not report_path.exists():
        return {"ok": False, "error": f"missing {report_path}", "date": date_str}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    leads: List[Dict[str, Any]] = []
    updated = {}
    for topic, items in (report or {}).items():
        if not isinstance(items, list):
            updated[topic] = items
            continue
        new_items = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = add_item_ids(dict(raw))
            evidence = extract_outbound_evidence(item)
            item["outbound_evidence"] = evidence
            item["primary_record_link_count"] = sum(
                1 for rec in evidence if rec.get("corroboration")
            )
            leads.extend(evidence)
            new_items.append(item)
        updated[topic] = new_items
    tmp = report_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(report_path)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{date_str}.jsonl"
    with open(out_path, "w", encoding="utf-8") as handle:
        for rec in leads:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    latest = OUT_DIR / "latest.jsonl"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(out_path.read_bytes())
    return {
        "ok": True,
        "date": date_str,
        "lead_count": len(leads),
        "out_path": str(out_path),
        "schema_version": "document_leads_run.v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    summary = run(args.date)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
