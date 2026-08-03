"""Cross-source consensus for claim-like atoms."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
CONSENSUS_OUT = ROOT_DIR / "outputs" / "consensus"

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def claim_key(text: str) -> str:
    cleaned = _NORMALIZE_RE.sub(" ", (text or "").lower()).strip()
    tokens = cleaned.split()
    return " ".join(tokens[:12])


def build_consensus(
    atoms: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
    *,
    report_date: str,
) -> Dict[str, Any]:
    signal_source = {
        str(i.get("signal_id") or ""): str(i.get("source") or i.get("source_domain") or "unknown")
        for i in items
    }
    by_key: Dict[str, Dict[str, Any]] = {}

    claim_atoms = [a for a in atoms if a.get("atom_type") in {"claim", "prediction", "counterexample"}]
    for atom in claim_atoms:
        text = str(atom.get("text") or "")
        key = claim_key(text)
        if len(key) < 8:
            continue
        parent = str(atom.get("parent_signal_id") or "")
        source = signal_source.get(parent, "unknown")
        entry = by_key.setdefault(
            key,
            {
                "claim_key": key,
                "sample_text": text[:400],
                "atom_ids": [],
                "sources": set(),
                "confirming_sources": set(),
                "contradicting_sources": set(),
                "atom_types": set(),
            },
        )
        entry["atom_ids"].append(atom.get("atom_id"))
        entry["sources"].add(source)
        entry["atom_types"].add(atom.get("atom_type"))
        if atom.get("atom_type") == "counterexample":
            entry["contradicting_sources"].add(source)
        else:
            entry["confirming_sources"].add(source)

    rows = []
    for entry in by_key.values():
        confirming = sorted(entry["confirming_sources"])
        contradicting = sorted(entry["contradicting_sources"])
        sources = sorted(entry["sources"])
        rows.append(
            {
                "claim_key": entry["claim_key"],
                "sample_text": entry["sample_text"],
                "atom_ids": entry["atom_ids"][:20],
                "source_count": len(sources),
                "sources": sources,
                "confirmation_count": len(confirming),
                "contradiction_count": len(contradicting),
                "confirming_sources": confirming,
                "contradicting_sources": contradicting,
                "atom_types": sorted(entry["atom_types"]),
            }
        )

    rows.sort(key=lambda r: (-r["confirmation_count"], -r["source_count"], r["claim_key"]))
    return {
        "schema": "open_source_news_consensus.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "claim_cluster_count": len(rows),
        "claims": rows[:200],
    }


def write_consensus(payload: Dict[str, Any], report_date: str) -> Path:
    CONSENSUS_OUT.mkdir(parents=True, exist_ok=True)
    path = CONSENSUS_OUT / f"{report_date}.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(CONSENSUS_OUT / "latest.json", payload)
    return path
