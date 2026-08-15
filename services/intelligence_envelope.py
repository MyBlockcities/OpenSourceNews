"""Build IntelligenceEnvelope.v1 for Agency pull/push consumers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from services.news_schema import add_item_ids, utc_now_iso
from services.source_registry import config_hash, load_sources, registry_hash

ROOT_DIR = Path(__file__).resolve().parents[1]
ENVELOPE_DIR = ROOT_DIR / "outputs" / "envelopes"


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_ref(path: Path) -> Optional[Dict[str, str]]:
    if not path.exists():
        return None
    rel = str(path.relative_to(ROOT_DIR)) if path.is_relative_to(ROOT_DIR) else str(path)
    return {"path": rel, "sha256": _sha256_file(path)}


def producer_version() -> str:
    env = os.environ.get("GITHUB_SHA") or os.environ.get("COMMIT_SHA")
    if env:
        return env.strip()
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT_DIR,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _iter_report_items(report: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for topic, items in (report or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                enriched = add_item_ids(dict(item))
                enriched["_topic"] = topic
                yield enriched


def compact_item(item: Dict[str, Any]) -> Dict[str, Any]:
    topics = item.get("public_topics")
    if not isinstance(topics, list) or not topics:
        topics = [item["_topic"]] if item.get("_topic") else []
    return {
        "signal_id": item.get("signal_id") or "",
        "content_hash": item.get("content_hash") or "",
        "source_id": item.get("source_id") or "unmatched",
        "source_tier": item.get("source_tier") or "T3",
        "permitted_use": item.get("permitted_use") or "discovery_only",
        "canonical_url": item.get("canonical_url") or item.get("url") or "",
        "published_at": item.get("published_at"),
        "fetched_at": item.get("fetched_at") or "",
        "title": item.get("title") or "",
        "excerpt": item.get("excerpt") or item.get("summary") or "",
        "language": item.get("language") or "en",
        "topics": topics,
        "raw_archive_ref": item.get("raw_archive_ref"),
        "primary_record_link_count": int(item.get("primary_record_link_count") or 0),
    }


def build_envelope(
    *,
    report: Dict[str, Any],
    report_path: Path,
    report_date: str,
    started_at: str,
    completed_at: Optional[str] = None,
    run_id: Optional[str] = None,
    health: Optional[Dict[str, Any]] = None,
    extra_artifacts: Optional[Dict[str, Path]] = None,
) -> Dict[str, Any]:
    sources = load_sources()
    items = [compact_item(item) for item in _iter_report_items(report)]
    artifacts: Dict[str, Any] = {
        "daily_report": _artifact_ref(report_path),
        "atoms": _artifact_ref(ROOT_DIR / "outputs" / "atoms" / f"{report_date}.jsonl"),
        "entities": _artifact_ref(ROOT_DIR / "outputs" / "entities" / f"{report_date}.json"),
        "consensus": _artifact_ref(ROOT_DIR / "outputs" / "consensus" / f"{report_date}.json"),
        "embedding_ready": _artifact_ref(
            ROOT_DIR / "outputs" / "embedding_ready" / f"{report_date}.jsonl"
        ),
        "document_leads": _artifact_ref(
            ROOT_DIR / "outputs" / "document_leads" / f"{report_date}.jsonl"
        ),
        "source_trust": _artifact_ref(
            ROOT_DIR / "outputs" / "source_trust" / f"{report_date}.json"
        ),
    }
    if extra_artifacts:
        for name, path in extra_artifacts.items():
            artifacts[name] = _artifact_ref(path)
    artifacts = {k: v for k, v in artifacts.items() if v}

    enabled = [s for s in sources if s.get("enabled")]
    envelope = {
        "schema": "intelligence_envelope.v1",
        "producer": "opensourcenews",
        "producer_version": producer_version(),
        "run_id": run_id or str(uuid.uuid4()),
        "report_date": report_date,
        "started_at": started_at,
        "completed_at": completed_at or utc_now_iso(),
        "source_registry_hash": registry_hash(sources),
        "config_hash": config_hash(),
        "report_hash": _sha256_file(report_path),
        "item_count": len(items),
        "items": items,
        "artifacts": artifacts,
        "health": health
        or {
            "expected_sources": len(enabled),
            "successful_sources": len(enabled),
            "degraded_sources": 0,
            "failed_sources": 0,
            "stale_sources": [],
        },
        "signature": None,
        "collect_only": True,
    }
    return envelope


def write_envelope(envelope: Dict[str, Any], *, report_date: str) -> Path:
    ENVELOPE_DIR.mkdir(parents=True, exist_ok=True)
    final = ENVELOPE_DIR / f"{report_date}.json"
    tmp = ENVELOPE_DIR / f"{report_date}.json.tmp"
    tmp.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(final)
    latest = ENVELOPE_DIR / "latest.json"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(final.read_bytes())
    return final
