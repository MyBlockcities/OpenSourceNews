#!/usr/bin/env python3
"""Atom extraction pipeline + public intelligence sidecars.

Writes:
  outputs/atoms/{date}.jsonl + latest.jsonl
  outputs/topics/{date}.json
  outputs/entities/{date}.json (+ entity pages)
  outputs/consensus/{date}.json
  outputs/source_trust/{date}.json (+ ema_state.json)

LLM atoms only when ATOMS_LLM=1 (or ATOM_LLM=1) and OPENROUTER_API_KEY is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.atom_schema import atom_to_record, extract_atoms
from services.consensus import export_consensus_snapshot, find_consensus
from services.entity_registry import export_entity_pages, export_entity_snapshot, update_registry
from services.news_schema import add_item_ids, canonicalize_url, source_domain, utc_now_iso
from services.source_trust import (
    empty_state,
    export_trust_snapshot,
    load_state,
    update_from_consensus,
)
from services.topics import add_public_topics, export_topic_snapshot, load_topics, tag_item


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
ATOMS_DIR = ROOT_DIR / "outputs" / "atoms"
TOPICS_DIR = ROOT_DIR / "outputs" / "topics"
TRUST_DIR = ROOT_DIR / "outputs" / "source_trust"
TRUST_STATE = TRUST_DIR / "ema_state.json"


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _mirror_latest(dated: Path) -> None:
    """Publish latest.* as a real file copy (portable; no git symlink churn)."""
    latest = dated.parent / ("latest" + dated.suffix)
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(dated.read_bytes())


def _llm_allowed(explicit: Optional[bool]) -> bool:
    if explicit is False:
        return False
    if explicit is True:
        return True
    return os.getenv("ATOMS_LLM", os.getenv("ATOM_LLM", "0")).strip() in {"1", "true", "yes"}


def _try_llm_client():
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        return None
    try:
        os.environ.setdefault("LLM_PROVIDER", "openrouter")
        from pipelines.llm_provider import try_get_llm_client

        return try_get_llm_client()
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: LLM client unavailable: {exc}")
        return None


def _iter_items(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for topic, rows in (report or {}).items():
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            item = add_item_ids(dict(raw))
            item.setdefault("topics", [topic])
            items.append(item)
    return items


def _write_atoms_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    _atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _save_trust_state(state: Dict[str, Any], path: Path = TRUST_STATE) -> None:
    flat = {
        f"{src}::{topic}": score
        for (src, topic), score in (state.get("scores") or {}).items()
    }
    _atomic_write_json(path, {"schema": "source_trust_ema_state.v1", "scores": flat, "version": 1})


def run(date_str: Optional[str] = None, *, allow_llm: Optional[bool] = None) -> Dict[str, Any]:
    files = sorted(DAILY_DIR.glob("*.json"), reverse=True)
    if date_str:
        report_path = DAILY_DIR / f"{date_str}.json"
        if not report_path.exists():
            return {"ok": False, "error": f"no report for {date_str}"}
    else:
        if not files:
            return {"ok": False, "error": "no daily reports"}
        report_path = files[0]
        date_str = report_path.stem

    report = json.loads(report_path.read_text(encoding="utf-8"))
    items = _iter_items(report)
    topics_ontology = load_topics()
    enriched_items = [add_public_topics(item, topics_ontology) for item in items]

    use_llm = _llm_allowed(allow_llm)
    llm = _try_llm_client() if use_llm else None
    atom_records: List[Dict[str, Any]] = []
    raw_atoms: List[Dict[str, Any]] = []
    skipped = 0

    for item in enriched_items:
        signal_id = str(item.get("signal_id") or "")
        if not signal_id:
            skipped += 1
            continue
        atoms = extract_atoms(item, llm_client=llm, allow_llm=bool(llm))
        canon = item.get("canonical_url") or canonicalize_url(str(item.get("url") or ""))
        domain = item.get("source_domain") or source_domain(str(canon or item.get("url") or ""))
        public_topics = list(item.get("public_topics") or tag_item(item, topics_ontology))
        for atom in atoms:
            raw_atoms.append(
                {
                    **atom,
                    "parent_signal_id": signal_id,
                    "parent_source_domain": domain,
                    "public_topics": public_topics,
                }
            )
            atom_records.append(
                atom_to_record(
                    atom,
                    parent_signal_id=signal_id,
                    parent_canonical_url=str(canon or ""),
                    parent_source_domain=str(domain or ""),
                    parent_bucket=str(item.get("bucket") or ""),
                    parent_topics=list(item.get("topics") or []),
                    public_topics=public_topics,
                    report_date=date_str,
                )
            )

    ATOMS_DIR.mkdir(parents=True, exist_ok=True)
    dated = ATOMS_DIR / f"{date_str}.jsonl"
    _write_atoms_jsonl(dated, atom_records)
    _mirror_latest(dated)

    # Topics snapshot
    prev_freq = None
    prev_topics = TOPICS_DIR / "latest.json"
    if prev_topics.exists():
        try:
            prev = json.loads(prev_topics.read_text(encoding="utf-8"))
            if prev.get("report_date") != date_str:
                prev_freq = prev.get("frequency")
        except Exception:  # noqa: BLE001
            prev_freq = None
    topics_payload = export_topic_snapshot(
        enriched_items, previous_frequency=prev_freq, topics=topics_ontology
    )
    topics_payload["report_date"] = date_str
    topics_payload["generated_at"] = utc_now_iso()
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    topics_path = TOPICS_DIR / f"{date_str}.json"
    _atomic_write_json(topics_path, topics_payload)
    _mirror_latest(topics_path)

    # Entities
    prior = None
    ent_latest = ROOT_DIR / "outputs" / "entities" / "latest.json"
    if ent_latest.exists():
        try:
            prior_data = json.loads(ent_latest.read_text(encoding="utf-8"))
            prior = {
                e["name"]: e
                for e in (prior_data.get("entities") or [])
                if e.get("name") and prior_data.get("report_date") != date_str
            }
        except Exception:  # noqa: BLE001
            prior = None
    entity_snap = update_registry(enriched_items, report_date=date_str, prior_snapshot=prior)
    export_entity_snapshot(entity_snap)
    # Cap entity pages to top 50 by mentions
    capped = dict(entity_snap)
    capped["entities"] = list(entity_snap.get("entities") or [])[:50]
    export_entity_pages(capped)

    # Consensus
    clusters = find_consensus(raw_atoms, report_date=date_str)
    export_consensus_snapshot(clusters, report_date=date_str)

    # Source trust EMA
    state = load_state(TRUST_STATE) if TRUST_STATE.exists() else empty_state()
    update_from_consensus(state, clusters)
    export_trust_snapshot(state, report_date=date_str)
    _save_trust_state(state)

    summary = {
        "ok": True,
        "report_date": date_str,
        "signal_count": len(enriched_items),
        "atom_count": len(atom_records),
        "skipped_no_signal_id": skipped,
        "llm_enabled": bool(llm),
        "generated_at": utc_now_iso(),
        "atoms_path": f"outputs/atoms/{date_str}.jsonl",
        "topics": topics_payload.get("topic_count"),
        "entities": len(entity_snap.get("entities") or []),
        "consensus_clusters": len(clusters),
    }
    _atomic_write_text(ATOMS_DIR / f"{date_str}.manifest.json", json.dumps(summary, indent=2) + "\n")
    return summary


def extract_report_atoms(report: Dict[str, Any], *, use_llm: bool = False) -> List[Dict[str, Any]]:
    items = _iter_items(report)
    llm = _try_llm_client() if use_llm else None
    out: List[Dict[str, Any]] = []
    for item in items:
        if not item.get("signal_id"):
            continue
        out.extend(extract_atoms(item, llm_client=llm, allow_llm=bool(llm)))
    return out


def write_atoms_jsonl(path: Path, atoms: List[Dict[str, Any]]) -> int:
    _write_atoms_jsonl(path, atoms)
    return len(atoms)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract atoms + public intelligence sidecars")
    parser.add_argument("--date", default=None)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()
    summary = run(args.date, allow_llm=False if args.no_llm else None)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    raise SystemExit(0 if summary.get("ok") else 1)


if __name__ == "__main__":
    main()
