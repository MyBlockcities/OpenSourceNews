"""Local data tools used by the OpenSourceNews MCP server."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.news_schema import normalize_item, normalize_report, search_score, slugify_name


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
MANIFEST_PATH = ROOT_DIR / "outputs" / "manifests" / "latest.json"
BRIEFS_DIR = ROOT_DIR / "outputs" / "briefs"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _report_files(limit: int = 365) -> List[Path]:
    return sorted(DAILY_DIR.glob("*.json"), reverse=True)[:limit]


def _report_date(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.stem, "%Y-%m-%d")
    except ValueError:
        return None


def get_latest_report() -> Dict[str, Any]:
    files = _report_files(limit=1)
    if not files:
        return {"error": "No reports found"}
    return {"date": files[0].stem, "report": _json(files[0])}


def get_latest_normalized_report() -> Dict[str, Any]:
    latest = get_latest_report()
    if "error" in latest:
        return latest
    return normalize_report(latest["date"], latest["report"])


def get_report_by_date(date: str) -> Dict[str, Any]:
    path = DAILY_DIR / f"{date}.json"
    if not path.exists():
        return {"error": f"No report found for {date}"}
    return {"date": date, "report": _json(path)}


def search_news(
    q: str = "",
    days: int = 30,
    topic: str = "",
    bucket: str = "",
    source: str = "",
    limit: int = 25,
) -> Dict[str, Any]:
    query = (q or "").strip()
    topic_filter = (topic or "").strip().lower()
    bucket_filter = (bucket or "").strip().lower()
    source_filter = (source or "").strip().lower()
    if not query and not topic_filter and not bucket_filter and not source_filter:
        return {"error": "Provide q, topic, bucket, or source"}

    safe_days = max(1, min(int(days or 30), 365))
    safe_limit = max(1, min(int(limit or 25), 100))
    cutoff = datetime.utcnow() - timedelta(days=safe_days)
    query_terms = [term for term in query.lower().split() if term]
    results: List[Dict[str, Any]] = []

    for path in _report_files(limit=365):
        report_dt = _report_date(path)
        if report_dt and report_dt < cutoff:
            continue
        report = _json(path)
        for topic_name, items in report.items():
            if topic_filter and topic_filter not in topic_name.lower():
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                if bucket_filter and bucket_filter != str(item.get("bucket") or "").lower():
                    continue
                if source_filter and source_filter not in str(item.get("source") or "").lower():
                    continue
                score = search_score(query_terms, topic_name, item) if query_terms else 1
                if query_terms and score <= 0:
                    continue
                normalized = normalize_item(topic_name, item)
                normalized["report_date"] = path.stem
                normalized["score"] = score
                results.append(normalized)

    results.sort(
        key=lambda it: (
            it.get("score", 0),
            it.get("quality_score") or 0,
            it.get("classification_confidence") or 0,
            it.get("report_date", ""),
        ),
        reverse=True,
    )
    return {
        "query": query,
        "days": safe_days,
        "limit": safe_limit,
        "count": min(len(results), safe_limit),
        "total_matches": len(results),
        "items": results[:safe_limit],
    }


def get_signal(signal_id: str, days: int = 365) -> Dict[str, Any]:
    safe_id = (signal_id or "").strip()
    if not safe_id:
        return {"error": "signal_id is required"}
    result = search_news(days=days, topic=".", limit=100)
    if "error" in result:
        result = {"items": []}
    for item in result.get("items", []):
        if item.get("signal_id") == safe_id:
            return item

    for path in _report_files(limit=365):
        report = _json(path)
        for topic_name, items in report.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = normalize_item(topic_name, item)
                if normalized.get("signal_id") == safe_id:
                    normalized["report_date"] = path.stem
                    return normalized
    return {"error": f"No signal found for {safe_id}"}


def get_topic_digest(topic: str, days: int = 7, limit: int = 25) -> Dict[str, Any]:
    result = search_news(topic=topic, days=days, limit=limit)
    if "error" in result:
        return result
    items = result.get("items", [])
    return {
        "topic": topic,
        "days": result["days"],
        "count": len(items),
        "top_titles": [item.get("title") for item in items[:10]],
        "items": items,
    }


def get_manifest() -> Dict[str, Any]:
    if MANIFEST_PATH.exists():
        return _json(MANIFEST_PATH)
    latest = get_latest_report()
    if "error" in latest:
        return latest
    report = latest["report"]
    return {
        "latest_report_date": latest["date"],
        "item_count": sum(len(items) for items in report.values() if isinstance(items, list)),
        "topics": list(report.keys()),
    }


def get_latest_brief(watchlist: str) -> Dict[str, Any]:
    slug = slugify_name(watchlist)
    files = sorted((BRIEFS_DIR / slug).glob("*.json"), reverse=True)
    if not files:
        return {"error": f"No mission brief found for {watchlist}"}
    return _json(files[0])


def hermes_status() -> Dict[str, Any]:
    """Hermes-facing status: manifest + artifact presence."""
    manifest = get_manifest()
    if "error" in manifest and "latest_report_date" not in manifest:
        return manifest
    date = str(manifest.get("latest_report_date") or "")
    artifacts = manifest.get("artifacts") or {}
    return {
        "ok": True,
        "latest_report_date": date,
        "item_count": manifest.get("item_count"),
        "report_sha256": manifest.get("report_sha256"),
        "generated_at": manifest.get("generated_at"),
        "artifacts": artifacts,
        "contract": "HERMES_CONTRACT.md",
    }


def hermes_schedule() -> Dict[str, Any]:
    return {
        "daily_cron_utc": "17 7 * * *",
        "daily_local_hint": "~01:17 MDT / ~00:17 MST",
        "github_traction_cron_utc": "47 8 * * *",
        "collect_only": True,
        "atom_llm": "optional when OPENROUTER_API_KEY set",
        "hermes_pull_hint": "~01:40 Mountain (com.hermes.osn-nightly)",
    }


def hermes_topics() -> Dict[str, Any]:
    topics_latest = ROOT_DIR / "outputs" / "topics" / "latest.json"
    ontology = ROOT_DIR / "config" / "topics.yaml"
    out: Dict[str, Any] = {"ontology_path": "config/topics.yaml"}
    if topics_latest.exists():
        out["latest"] = _json(topics_latest)
    else:
        out["latest"] = None
        out["note"] = "No topics export yet — run pipelines/public_intelligence.py"
    if ontology.exists():
        try:
            import yaml

            data = yaml.safe_load(ontology.read_text(encoding="utf-8")) or {}
            out["topic_ids"] = [t.get("id") for t in (data.get("topics") or []) if t.get("id")]
        except Exception as exc:  # noqa: BLE001
            out["ontology_error"] = str(exc)
    return out


def hermes_health() -> Dict[str, Any]:
    status = hermes_status()
    date = status.get("latest_report_date") or ""
    checks = {
        "manifest": MANIFEST_PATH.exists(),
        "daily_report": bool(date) and (DAILY_DIR / f"{date}.json").exists(),
        "atoms": (ROOT_DIR / "outputs" / "atoms" / "latest.jsonl").exists(),
        "embedding_ready": (ROOT_DIR / "outputs" / "embedding_ready" / "latest.jsonl").exists(),
        "topics": (ROOT_DIR / "outputs" / "topics" / "latest.json").exists(),
        "entities": (ROOT_DIR / "outputs" / "entities" / "latest.json").exists(),
        "consensus": (ROOT_DIR / "outputs" / "consensus" / "latest.json").exists(),
        "source_trust": (ROOT_DIR / "outputs" / "source_trust" / "latest.json").exists(),
        "github_traction": (ROOT_DIR / "outputs" / "github_traction" / "latest.json").exists(),
        "contract": (ROOT_DIR / "HERMES_CONTRACT.md").exists(),
    }
    missing = [k for k, ok in checks.items() if not ok]
    return {
        "healthy": len(missing) == 0 or (checks["manifest"] and checks["daily_report"]),
        "checks": checks,
        "missing": missing,
        "status": status,
    }
