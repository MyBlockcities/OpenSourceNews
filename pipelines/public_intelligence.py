#!/usr/bin/env python3
"""Post-daily public intelligence pass for Hermes consumers.

Runs after COLLECT_ONLY daily report:
  atoms → topics → entities → consensus → source_trust → tutorial flags → embedding_ready

Does not re-enable full triage LLM under COLLECT_ONLY.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from pipelines.atom_extraction import extract_report_atoms, write_atoms_jsonl
from scripts.export_embedding_ready import atom_records, signal_records, write_jsonl
from services.consensus import build_consensus, write_consensus
from services.entity_registry import build_entity_registry, write_entity_exports
from services.news_schema import add_item_ids
from services.source_trust import build_source_trust, write_source_trust
from services.topics import build_topics_export, tag_item, write_topics_export
from services.tutorial_flags import apply_tutorial_flags


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
ATOMS_DIR = ROOT_DIR / "outputs" / "atoms"
EMBED_DIR = ROOT_DIR / "outputs" / "embedding_ready"
TOPICS_OUT = ROOT_DIR / "outputs" / "topics"


def latest_report_path(explicit: str = "") -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    files = sorted(DAILY_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def iter_items(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for topic, rows in (report or {}).items():
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            item = add_item_ids(dict(raw))
            item.setdefault("topics", [topic])
            item["public_topics"] = tag_item(item)
            items.append(item)
    return apply_tutorial_flags(items)


def load_atoms_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Public intelligence post-pass")
    parser.add_argument("--report", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--skip-pages", action="store_true", help="Skip entity page files")
    args = parser.parse_args()

    report_path = latest_report_path(args.report)
    if report_path is None:
        print("No daily report found")
        return

    report_date = args.date or report_path.stem
    report = json.loads(report_path.read_text(encoding="utf-8"))
    items = iter_items(report)

    # 1. Atoms
    atoms = extract_report_atoms(report, use_llm=False)
    # Attach public_topics onto claim atoms from parent when possible
    by_sig = {i.get("signal_id"): i for i in items}
    for atom in atoms:
        parent = by_sig.get(atom.get("parent_signal_id"))
        if parent:
            atom["public_topics"] = parent.get("public_topics") or []

    ATOMS_DIR.mkdir(parents=True, exist_ok=True)
    dated_atoms = ATOMS_DIR / f"{report_date}.jsonl"
    write_atoms_jsonl(dated_atoms, atoms)
    (ATOMS_DIR / "latest.jsonl").write_bytes(dated_atoms.read_bytes())
    print(f"atoms={len(atoms)}")

    # 2. Topics
    previous = None
    prev_path = TOPICS_OUT / "latest.json"
    if prev_path.exists():
        try:
            previous = json.loads(prev_path.read_text(encoding="utf-8"))
            if previous.get("report_date") == report_date:
                # Prefer day-before if same date re-run
                prev_files = sorted(TOPICS_OUT.glob("????-??-??.json"), reverse=True)
                for cand in prev_files:
                    if cand.stem != report_date:
                        previous = json.loads(cand.read_text(encoding="utf-8"))
                        break
        except Exception:  # noqa: BLE001
            previous = None
    topics_payload = build_topics_export(items, report_date=report_date, previous=previous)
    write_topics_export(topics_payload, report_date)
    print(f"topics={len(topics_payload.get('frequency') or {})}")

    # 3. Entities
    entities_payload = build_entity_registry(items, report_date=report_date, atoms=atoms)
    write_entity_exports(entities_payload, report_date, write_pages=not args.skip_pages)
    print(f"entities={entities_payload.get('entity_count')}")

    # 4. Consensus
    consensus_payload = build_consensus(atoms, items, report_date=report_date)
    write_consensus(consensus_payload, report_date)
    print(f"consensus_clusters={consensus_payload.get('claim_cluster_count')}")

    # 5. Source trust
    trust_payload = build_source_trust(items, consensus_payload, report_date=report_date)
    write_source_trust(trust_payload, report_date)
    print(f"source_trust_rows={len(trust_payload.get('scores') or [])}")

    # 6. Embedding-ready (signals + atoms; include tutorial fields on signals)
    # Rebuild a lightweight report-shaped map is unnecessary — use signal_records helpers
    # with a synthetic report that preserves tutorial fields via items.
    synthetic: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        topic = (item.get("topics") or ["General"])[0]
        synthetic.setdefault(topic, []).append(item)
    records = signal_records(synthetic, report_date)
    records.extend(atom_records(dated_atoms, report_date))
    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    embed_path = EMBED_DIR / f"{report_date}.jsonl"
    count = write_jsonl(embed_path, records)
    (EMBED_DIR / "latest.jsonl").write_bytes(embed_path.read_bytes())
    print(f"embedding_ready={count}")
    print(f"Public intelligence complete for {report_date}")


if __name__ == "__main__":
    main()
