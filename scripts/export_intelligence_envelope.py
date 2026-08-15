#!/usr/bin/env python3
"""Build outputs/envelopes/{date}.json for Agency pull consumers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.intelligence_envelope import build_envelope, write_envelope  # noqa: E402
from services.news_schema import utc_now_iso  # noqa: E402

DAILY_DIR = ROOT_DIR / "outputs" / "daily"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = DAILY_DIR / f"{date_str}.json"
    if not report_path.exists():
        print(json.dumps({"ok": False, "error": f"missing {report_path}"}))
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    envelope = build_envelope(
        report=report,
        report_path=report_path,
        report_date=date_str,
        started_at=utc_now_iso(),
    )
    path = write_envelope(envelope, report_date=date_str)
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(path),
                "item_count": envelope["item_count"],
                "report_hash": envelope["report_hash"],
                "run_id": envelope["run_id"],
                "schema": envelope["schema"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
