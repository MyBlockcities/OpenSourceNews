#!/usr/bin/env python3
"""Prune generated outputs while keeping recent history.

Defaults are conservative and dry-run. Use --apply to delete files.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List

ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_date_from_name(path: Path) -> datetime | None:
    stem = path.stem
    date_part = stem[:10]
    try:
        return datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        return None


def candidates(directory: Path, patterns: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        files.extend(p for p in directory.glob(pattern) if p.is_file())
    return sorted(set(files), key=lambda p: (parse_date_from_name(p) or datetime.min, p.name), reverse=True)


def select_prunable(files: List[Path], *, keep_days: int, keep_min: int) -> List[Path]:
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    prunable: List[Path] = []

    for index, path in enumerate(files):
        file_date = parse_date_from_name(path)
        keep_by_count = index < keep_min
        keep_by_date = file_date is None or file_date >= cutoff
        if not keep_by_count and not keep_by_date:
            prunable.append(path)

    return prunable


def prune_group(label: str, directory: Path, patterns: List[str], keep_days: int, keep_min: int, apply: bool) -> int:
    files = candidates(directory, patterns)
    prunable = select_prunable(files, keep_days=keep_days, keep_min=keep_min)

    print(f"{label}: {len(files)} files, {len(prunable)} prunable")
    for path in prunable:
        rel = path.relative_to(ROOT_DIR)
        print(f"  {'delete' if apply else 'would delete'} {rel}")
        if apply:
            path.unlink()

    return len(prunable)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune generated OpenSourceNews output files.")
    parser.add_argument("--keep-days", type=int, default=120, help="Keep files dated within this many days.")
    parser.add_argument("--keep-daily-min", type=int, default=60, help="Always keep at least this many daily reports.")
    parser.add_argument("--keep-script-min", type=int, default=30, help="Always keep at least this many script/storyboard files.")
    parser.add_argument("--keep-transcript-min", type=int, default=25, help="Always keep at least this many transcript files.")
    parser.add_argument("--apply", action="store_true", help="Delete selected files. Omit for dry-run.")
    args = parser.parse_args()

    if args.keep_days < 1:
        raise SystemExit("--keep-days must be >= 1")

    total = 0
    total += prune_group(
        "daily reports",
        ROOT_DIR / "outputs" / "daily",
        ["*.json"],
        args.keep_days,
        args.keep_daily_min,
        args.apply,
    )
    total += prune_group(
        "scripts",
        ROOT_DIR / "outputs" / "scripts",
        ["*.txt", "*.json"],
        args.keep_days,
        args.keep_script_min,
        args.apply,
    )
    total += prune_group(
        "transcripts",
        ROOT_DIR / "outputs" / "transcripts",
        ["*.json"],
        args.keep_days,
        args.keep_transcript_min,
        args.apply,
    )

    mode = "applied" if args.apply else "dry-run"
    print(f"Prune {mode} complete: {total} files selected.")


if __name__ == "__main__":
    main()
