#!/usr/bin/env python3
"""Extract public-domain atoms from the latest daily report.

Hybrid extraction:
  1. Deterministic regex/heuristics (always)
  2. Optional cheap LLM when ATOM_LLM=1 and OPENROUTER_API_KEY is set

Writes:
  outputs/atoms/{date}.jsonl
  outputs/atoms/latest.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.atom_schema import extract_deterministic_atoms, utc_now_iso
from services.news_schema import add_item_ids


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
ATOMS_DIR = ROOT_DIR / "outputs" / "atoms"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def latest_report_path(explicit: str = "") -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
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
            items.append(item)
    return items


def maybe_llm_atoms(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Optional OpenRouter extraction for hard atom types. Fail-soft playbook."""
    if os.getenv("ATOM_LLM", "0") != "1":
        return []
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return []
    partial_dir = ATOMS_DIR / "_partial"
    signal_id = str(item.get("signal_id") or "")
    try:
        from pipelines.llm_provider import try_get_llm_client, parse_json_text
        from services.atom_schema import build_atom

        os.environ.setdefault("LLM_PROVIDER", "openrouter")
        llm = try_get_llm_client()
        if not llm:
            return []
        title = item.get("title") or ""
        summary = item.get("summary") or item.get("excerpt") or ""
        url = item.get("canonical_url") or item.get("url") or ""
        prompt = f"""Extract up to 5 hard atoms as a JSON array. Types allowed: claim, reasoning, counterexample, prediction.
Each object: {{"atom_type":"...","text":"...","polarity":"supports|contradicts"}}
Title: {title}
Summary: {summary}
Return ONLY JSON array."""

        def _parse(raw: str) -> List[Dict[str, Any]]:
            parsed = parse_json_text(raw)
            if not isinstance(parsed, list):
                raise ValueError("not a list")
            out = []
            for row in parsed[:5]:
                if not isinstance(row, dict):
                    continue
                try:
                    atom = build_atom(
                        parent_signal_id=signal_id,
                        atom_type=str(row.get("atom_type") or "claim"),
                        text=str(row.get("text") or ""),
                        evidence_urls=[url] if url else [],
                        extra={"polarity": str(row.get("polarity") or "supports")},
                    )
                    out.append(atom)
                except ValueError:
                    continue
            return out

        try:
            text = llm.generate(prompt, json_mode=True)
            return _parse(text)
        except Exception as first:  # noqa: BLE001
            # Retry once with shorter prompt (malformed JSON playbook)
            try:
                short = f"JSON array of atoms with atom_type+text only.\nTitle: {title}\nSummary: {str(summary)[:400]}"
                text = llm.generate(short, json_mode=True)
                return _parse(text)
            except Exception as second:  # noqa: BLE001
                partial_dir.mkdir(parents=True, exist_ok=True)
                status = "llm_timeout" if "timeout" in str(second).lower() or "timeout" in str(first).lower() else "llm_parse_error"
                if "rate" in str(second).lower() or "429" in str(second):
                    status = "llm_rate_limited"
                line = {
                    "signal_id": signal_id,
                    "status": status,
                    "error": str(second)[:300],
                }
                with (partial_dir / "latest.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(line) + "\n")
                print(f"  WARNING: atom LLM {status} for {signal_id[:12]}")
                return []
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: atom LLM pass skipped: {exc}")
        return []


def extract_report_atoms(report: Dict[str, Any], *, use_llm: bool = False) -> List[Dict[str, Any]]:
    atoms: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in iter_items(report):
        batch = extract_deterministic_atoms(item)
        if use_llm:
            batch.extend(maybe_llm_atoms(item))
        for atom in batch:
            aid = atom["atom_id"]
            if aid in seen:
                continue
            seen.add(aid)
            atoms.append(atom)
    return atoms


def write_atoms_jsonl(path: Path, atoms: List[Dict[str, Any]]) -> int:
    lines = [json.dumps(atom, ensure_ascii=False) for atom in atoms]
    _atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))
    return len(atoms)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract atoms from a daily report")
    parser.add_argument("--report", default="", help="Path to daily report JSON")
    parser.add_argument("--date", default="", help="Override output date stem")
    parser.add_argument("--llm", action="store_true", help="Enable optional ATOM_LLM pass")
    args = parser.parse_args()

    report_path = latest_report_path(args.report)
    if report_path is None:
        print("No daily report found")
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))
    date = args.date or report_path.stem
    use_llm = args.llm or os.getenv("ATOM_LLM", "0") == "1"
    atoms = extract_report_atoms(report, use_llm=use_llm)

    ATOMS_DIR.mkdir(parents=True, exist_ok=True)
    dated = ATOMS_DIR / f"{date}.jsonl"
    latest = ATOMS_DIR / "latest.jsonl"
    count = write_atoms_jsonl(dated, atoms)
    # Copy for stable Hermes path.
    latest.write_bytes(dated.read_bytes())

    meta = {
        "schema": "open_source_news_atoms_manifest.v1",
        "report_date": date,
        "atom_count": count,
        "generated_at": utc_now_iso(),
        "llm_enabled": use_llm,
        "jsonl_path": f"outputs/atoms/{date}.jsonl",
    }
    _atomic_write_text(
        ATOMS_DIR / f"{date}.manifest.json",
        json.dumps(meta, indent=2) + "\n",
    )
    print(f"Atoms written: {dated} ({count})")
    print(f"Latest mirror: {latest}")


if __name__ == "__main__":
    main()
