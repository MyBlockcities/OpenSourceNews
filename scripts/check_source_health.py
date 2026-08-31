#!/usr/bin/env python3
"""Fail the nightly run when too many sources are failing.

Collectors deliberately swallow per-source errors so one dead feed cannot
abort the whole run. The cost of that design is silence: before this gate the
pipeline reported success with 13 sources failing every night.

This runs *after* the commit step so a degraded run still publishes whatever
it managed to collect, and still leaves a health snapshot behind — it just
stops reporting a clean bill of health.

Thresholds are env-tunable:
  SOURCE_HEALTH_MAX_FAILED_PCT   default 10   (percent of expected sources)
  SOURCE_HEALTH_MAX_FAILED_ABS   default 25   (absolute count)

Exit codes: 0 ok/warn, 1 threshold breached, 2 snapshot missing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
HEALTH_DIR = ROOT_DIR / "outputs" / "source_health"


def main() -> int:
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    path = HEALTH_DIR / (f"{date_arg}.json" if date_arg else "latest.json")
    if not path.exists():
        print(f"ERROR: no source-health snapshot at {path}")
        print("The collection step did not complete; treating as failure.")
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    expected = int(data.get("expected_sources") or 0)
    failed = int(data.get("failed_sources") or 0)
    empty = int(data.get("degraded_sources") or 0)
    ok = int(data.get("successful_sources") or 0)

    max_pct = float(os.getenv("SOURCE_HEALTH_MAX_FAILED_PCT", "10"))
    max_abs = int(os.getenv("SOURCE_HEALTH_MAX_FAILED_ABS", "25"))
    pct = (failed / expected * 100.0) if expected else 0.0

    print(f"Source health for {data.get('report_date', '?')}")
    print(f"  expected : {expected}")
    print(f"  ok       : {ok}")
    print(f"  empty    : {empty}")
    print(f"  failed   : {failed} ({pct:.1f}%)")

    failures = data.get("failures") or []
    if failures:
        print("\nFailing sources:")
        for f in failures:
            print(f"  - {f.get('endpoint')}: {str(f.get('error'))[:160]}")

    if failed > max_abs or pct > max_pct:
        print(
            f"\n::error::Source health below threshold — {failed} failed "
            f"({pct:.1f}%); limits are {max_abs} absolute / {max_pct}%."
        )
        return 1

    if failures:
        print(
            f"\n::warning::{failed} source(s) failing but within threshold "
            f"({max_abs} absolute / {max_pct}%)."
        )
    print("\nSource health OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
