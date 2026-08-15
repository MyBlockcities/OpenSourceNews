#!/usr/bin/env python3
"""Build outputs/manifests/latest.json for Hermes / Agency pull consumers.

Preserves the original discovery keys (latest_report_date, item_count, …)
and adds v2 fields including report_sha256 for idempotent nightly processing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT_DIR / "outputs" / "daily"
MANIFEST_PATH = ROOT_DIR / "outputs" / "manifests" / "latest.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_report_path() -> Path | None:
    paths = sorted(DAILY_DIR.glob("*.json"), reverse=True)
    return paths[0] if paths else None


def build_manifest(
    report_path: Path,
    *,
    workflow_run_id: str = "",
    commit_sha: str = "",
) -> Dict[str, Any]:
    raw_bytes = report_path.read_bytes()
    data = json.loads(raw_bytes.decode("utf-8"))

    item_count = 0
    topics = list(data.keys()) if isinstance(data, dict) else []
    bucket_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    signal_ids = set()
    cluster_ids = set()
    enrichment_pending = 0

    if isinstance(data, dict):
        for _topic, items in data.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_count += 1
                bucket_counts[item.get("bucket") or "unknown"] += 1
                source_counts[item.get("source") or "unknown"] += 1
                if item.get("signal_id"):
                    signal_ids.add(item["signal_id"])
                if item.get("cluster_id"):
                    cluster_ids.add(item["cluster_id"])
                status = str(item.get("enrichment_status") or "pending").lower()
                if status in {"", "pending"}:
                    enrichment_pending += 1

    date = report_path.stem
    relative_path = f"outputs/daily/{report_path.name}"

    def _artifact(rel: str) -> Optional[str]:
        path = ROOT_DIR / rel
        return rel if path.exists() else None

    artifacts = {
        "atoms_jsonl": _artifact(f"outputs/atoms/{date}.jsonl"),
        "atoms_latest": _artifact("outputs/atoms/latest.jsonl"),
        "embedding_ready_jsonl": _artifact(f"outputs/embedding_ready/{date}.jsonl"),
        "embedding_ready_latest": _artifact("outputs/embedding_ready/latest.jsonl"),
        "topics": _artifact(f"outputs/topics/{date}.json"),
        "entities": _artifact(f"outputs/entities/{date}.json"),
        "consensus": _artifact(f"outputs/consensus/{date}.json"),
        "source_trust": _artifact(f"outputs/source_trust/{date}.json"),
        "github_traction": _artifact("outputs/github_traction/latest.json"),
        "github_traction_top": _artifact("outputs/github_traction/top_this_week.json"),
        "document_leads": _artifact(f"outputs/document_leads/{date}.jsonl"),
        "intelligence_envelope": _artifact(f"outputs/envelopes/{date}.json"),
        "hermes_contract": "HERMES_CONTRACT.md",
    }
    artifacts = {k: v for k, v in artifacts.items() if v}

    # Keep legacy keys stable for existing Academy / dashboard consumers.
    return {
        "schema": "open_source_news_manifest.v2",
        "report_schema": "open_source_news_daily_report.v2",
        "latest_report_date": date,
        "latest_report_path": relative_path,
        "item_count": item_count,
        "topics": topics,
        "bucket_counts": dict(bucket_counts),
        "generated_at": utc_now_iso(),
        "report_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "report_bytes": len(raw_bytes),
        "unique_signal_count": len(signal_ids),
        "unique_cluster_count": len(cluster_ids),
        "source_counts": dict(source_counts),
        "enrichment_pending_count": enrichment_pending,
        "artifacts": artifacts,
        "workflow_run_id": workflow_run_id or os.environ.get("GITHUB_RUN_ID", ""),
        "commit_sha": commit_sha
        or os.environ.get("GITHUB_SHA", "")
        or os.environ.get("COMMIT_SHA", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the latest report manifest.")
    parser.add_argument("--report", default="", help="Optional path to a daily report JSON.")
    parser.add_argument("--out", default=str(MANIFEST_PATH), help="Manifest output path.")
    parser.add_argument("--workflow-run-id", default="", help="Optional GitHub run id.")
    parser.add_argument("--commit-sha", default="", help="Optional commit sha.")
    args = parser.parse_args()

    report_path = Path(args.report) if args.report else latest_report_path()
    if report_path is None or not report_path.exists():
        print("No daily reports found")
        return

    manifest = build_manifest(
        report_path,
        workflow_run_id=args.workflow_run_id,
        commit_sha=args.commit_sha,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Manifest: {manifest['latest_report_date']} "
        f"({manifest['item_count']} items, sha256={manifest['report_sha256'][:12]}…)"
    )


if __name__ == "__main__":
    main()
