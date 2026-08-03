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


# ──────────────────────────────────────────────────────────────────────
# Hermes consumer tools — added for the v1 contract.
#
# These read the new public outputs (atoms, embedding-ready, topics,
# entities, consensus, source_trust, github_traction). Keep them
# dependency-light so the MCP server stays cheap to spawn.
# ──────────────────────────────────────────────────────────────────────

ATOMS_DIR = ROOT_DIR / "outputs" / "atoms"
EMBED_DIR = ROOT_DIR / "outputs" / "embedding_ready"
TOPICS_DIR = ROOT_DIR / "outputs" / "topics"
ENTITIES_DIR = ROOT_DIR / "outputs" / "entities"
CONSENSUS_DIR = ROOT_DIR / "outputs" / "consensus"
SOURCE_TRUST_DIR = ROOT_DIR / "outputs" / "source_trust"
GH_TRACTION_DIR = ROOT_DIR / "outputs" / "github_traction"


def _read_jsonl(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[:limit]


def get_latest_atoms(limit: int = 200) -> Dict[str, Any]:
    """Return the latest atoms JSONL (Hermes' primary input)."""
    safe = max(1, min(int(limit or 200), 5000))
    path = ATOMS_DIR / "latest.jsonl"
    atoms = _read_jsonl(path, limit=safe)
    return {
        "source": str(path),
        "count": len(atoms),
        "atoms": atoms,
    }


def get_atom_by_id(atom_id: str) -> Dict[str, Any]:
    """Find a single atom across the latest + previous days."""
    safe = (atom_id or "").strip()
    if not safe:
        return {"error": "atom_id is required"}
    for path in sorted(ATOMS_DIR.glob("*.jsonl"), reverse=True)[:7]:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("atom_id") == safe:
                return rec
    return {"error": f"No atom found for {safe}"}


def get_latest_embedding_ready(limit: int = 500) -> Dict[str, Any]:
    path = EMBED_DIR / "latest.jsonl"
    recs = _read_jsonl(path, limit=max(1, min(int(limit or 500), 5000)))
    return {
        "source": str(path),
        "count": len(recs),
        "records": recs,
    }


def get_latest_topics() -> Dict[str, Any]:
    path = TOPICS_DIR / "latest.json"
    if not path.exists():
        return {"error": "no topics snapshot yet"}
    return _json(path)


def get_latest_entities(limit: int = 100, trajectory: str = "") -> Dict[str, Any]:
    path = ENTITIES_DIR / "latest.json"
    if not path.exists():
        return {"error": "no entities snapshot yet"}
    data = _json(path)
    entities = data.get("entities") or []
    if trajectory:
        entities = [e for e in entities if (e.get("trajectory") or "").lower() == trajectory.lower()]
    return {
        "report_date": data.get("report_date"),
        "count": len(entities[:limit]),
        "entities": entities[:limit],
    }


def get_entity_page(slug: str) -> Dict[str, Any]:
    pages_dir = ENTITIES_DIR.parent / "entity_pages"
    safe = (slug or "").strip()
    if not safe:
        return {"error": "slug is required"}
    path = pages_dir / f"{safe}.json"
    if not path.exists():
        return {"error": f"No entity page for {safe}"}
    return _json(path)


def get_latest_consensus(min_members: int = 2) -> Dict[str, Any]:
    path = CONSENSUS_DIR / "latest.json"
    if not path.exists():
        return {"error": "no consensus snapshot yet"}
    data = _json(path)
    clusters = [c for c in (data.get("clusters") or []) if c.get("member_count", 0) >= max(1, int(min_members or 2))]
    return {
        "report_date": data.get("report_date"),
        "cluster_count": len(clusters),
        "clusters": clusters,
    }


def get_source_trust(source: str = "", topic: str = "") -> Dict[str, Any]:
    path = SOURCE_TRUST_DIR / "latest.json"
    if not path.exists():
        return {"error": "no source_trust snapshot yet"}
    data = _json(path)
    scores = data.get("scores") or {}
    if source and topic:
        key = f"{source.strip().lower()}::{topic.strip().lower()}"
        if key not in scores:
            return {"error": f"no entry for {source} / {topic}", "default": 0.5}
        return scores[key]
    if source:
        prefix = f"{source.strip().lower()}::"
        filtered = {k: v for k, v in scores.items() if k.startswith(prefix)}
        return {"source": source, "count": len(filtered), "scores": filtered}
    return {"count": len(scores), "scores": list(scores.values())[:100]}


def get_github_traction(limit: int = 50, full_name: str = "") -> Dict[str, Any]:
    path = GH_TRACTION_DIR / "latest.json"
    if not path.exists():
        return {"error": "no github_traction snapshot yet"}
    data = _json(path)
    snapshots = data.get("snapshots") or []
    if full_name:
        for s in snapshots:
            if (s.get("full_name") or "").lower() == full_name.strip().lower():
                return s
        return {"error": f"no snapshot for {full_name}"}
    safe = max(1, min(int(limit or 50), 500))
    scored = sorted(
        snapshots,
        key=lambda s: (s.get("score") or {}).get("composite_score", 0),
        reverse=True,
    )
    return {
        "report_date": data.get("report_date"),
        "count": min(len(scored), safe),
        "snapshots": scored[:safe],
    }


def get_github_top_this_week(limit: int = 25) -> Dict[str, Any]:
    path = GH_TRACTION_DIR / "top_this_week.json"
    if not path.exists():
        return {"error": "no top_this_week snapshot yet"}
    data = _json(path)
    return {
        "report_date": data.get("report_date"),
        "count": min(len(data.get("repos") or []), max(1, int(limit or 25))),
        "repos": (data.get("repos") or [])[: max(1, int(limit or 25))],
    }


def get_github_fastest_30d(limit: int = 25) -> Dict[str, Any]:
    path = GH_TRACTION_DIR / "fastest_30d.json"
    if not path.exists():
        return {"error": "no fastest_30d snapshot yet"}
    data = _json(path)
    return {
        "report_date": data.get("report_date"),
        "count": min(len(data.get("repos") or []), max(1, int(limit or 25))),
        "repos": (data.get("repos") or [])[: max(1, int(limit or 25))],
    }


def hermes_status() -> Dict[str, Any]:
    """Operational metadata for Hermes: what's there, what's missing, when last run."""
    out: Dict[str, Any] = {"outputs": {}, "schema_version": "hermes_status.v1"}
    for label, path in (
        ("daily_report", DAILY_DIR / "latest.json"),
        ("manifest", MANIFEST_PATH),
        ("atoms", ATOMS_DIR / "latest.jsonl"),
        ("embedding_ready", EMBED_DIR / "latest.jsonl"),
        ("topics", TOPICS_DIR / "latest.json"),
        ("entities", ENTITIES_DIR / "latest.json"),
        ("consensus", CONSENSUS_DIR / "latest.json"),
        ("source_trust", SOURCE_TRUST_DIR / "latest.json"),
        ("github_traction", GH_TRACTION_DIR / "latest.json"),
        ("github_top_week", GH_TRACTION_DIR / "top_this_week.json"),
        ("github_fastest_30d", GH_TRACTION_DIR / "fastest_30d.json"),
    ):
        entry: Dict[str, Any] = {"present": path.exists()}
        if entry["present"]:
            try:
                stat = path.stat()
                entry["size_bytes"] = stat.st_size
                entry["mtime"] = datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z"
            except OSError:
                pass
        out["outputs"][label] = entry
    return out


def hermes_schedule() -> Dict[str, Any]:
    return {
        "daily_cron_utc": "17 7 * * *",
        "daily_local_hint": "~01:17 MDT / ~00:17 MST",
        "github_traction_cron_utc": "47 8 * * *",
        "collect_only": True,
        "atoms_llm": "optional via vars.ATOMS_LLM=1 + OPENROUTER_API_KEY",
        "hermes_pull_hint": "~01:40 Mountain (com.hermes.osn-nightly)",
        "news_factory_hint": "~05:50 local (com.hermes.news-factory-nightly)",
    }


def hermes_topics() -> Dict[str, Any]:
    path = TOPICS_DIR / "latest.json"
    ontology = ROOT_DIR / "config" / "topics.yaml"
    out: Dict[str, Any] = {"ontology_path": "config/topics.yaml"}
    if path.exists():
        out["latest"] = _json(path)
    else:
        out["latest"] = None
        out["note"] = "No topics export yet — run scripts/export_atoms.py"
    if ontology.exists():
        try:
            import yaml
            data = yaml.safe_load(ontology.read_text(encoding="utf-8")) or {}
            topics = data.get("topics") or {}
            if isinstance(topics, dict):
                out["topic_ids"] = sorted(topics.keys())
            elif isinstance(topics, list):
                out["topic_ids"] = [t.get("id") for t in topics if isinstance(t, dict) and t.get("id")]
        except Exception as exc:  # noqa: BLE001
            out["ontology_error"] = str(exc)
    return out


def hermes_health() -> Dict[str, Any]:
    status = hermes_status()
    checks = {
        "manifest": MANIFEST_PATH.exists(),
        "atoms": (ATOMS_DIR / "latest.jsonl").exists(),
        "embedding_ready": (EMBED_DIR / "latest.jsonl").exists(),
        "topics": (TOPICS_DIR / "latest.json").exists(),
        "entities": (ENTITIES_DIR / "latest.json").exists(),
        "consensus": (CONSENSUS_DIR / "latest.json").exists(),
        "source_trust": (SOURCE_TRUST_DIR / "latest.json").exists(),
        "github_traction": (GH_TRACTION_DIR / "latest.json").exists(),
        "contract": (ROOT_DIR / "HERMES_CONTRACT.md").exists(),
    }
    missing = [k for k, ok in checks.items() if not ok]
    return {
        "healthy": checks["manifest"] and checks.get("atoms", False),
        "checks": checks,
        "missing": missing,
        "status": status,
    }
