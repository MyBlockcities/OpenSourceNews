"""Public entity registry derived from signals + atoms."""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
ENTITIES_OUT = ROOT_DIR / "outputs" / "entities"
ENTITY_PAGES = ROOT_DIR / "outputs" / "entity_pages"

ENTITY_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews/entities")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def entity_id(name: str) -> str:
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    return str(uuid.uuid5(ENTITY_NAMESPACE, key))


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def extract_entity_names(item: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for ent in item.get("entities") or []:
        if isinstance(ent, str) and ent.strip():
            names.append(ent.strip())
        elif isinstance(ent, dict) and ent.get("name"):
            names.append(str(ent["name"]).strip())
    blob = f"{item.get('title') or ''} {item.get('summary') or ''}"
    for match in re.finditer(
        r"\b(OpenAI|Anthropic|Google|Meta|Microsoft|NVIDIA|BlackRock|Ethereum|Solana|Bitcoin|"
        r"LangChain|HuggingFace|Qdrant|FDA|SEC)\b",
        blob,
        re.I,
    ):
        names.append(match.group(0))
    seen = set()
    out = []
    for n in names:
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out


def build_entity_registry(
    items: List[Dict[str, Any]],
    *,
    report_date: str,
    atoms: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    by_id: Dict[str, Dict[str, Any]] = {}

    for item in items:
        signal_id = str(item.get("signal_id") or "")
        for name in extract_entity_names(item):
            eid = entity_id(name)
            entry = by_id.setdefault(
                eid,
                {
                    "entity_id": eid,
                    "name": name,
                    "aliases": [],
                    "mention_count": 0,
                    "signal_ids": [],
                    "atom_ids": [],
                    "public_topics": [],
                },
            )
            entry["mention_count"] += 1
            if signal_id and signal_id not in entry["signal_ids"]:
                entry["signal_ids"].append(signal_id)
            for t in item.get("public_topics") or []:
                if t not in entry["public_topics"]:
                    entry["public_topics"].append(t)

    for atom in atoms or []:
        if atom.get("atom_type") != "entity":
            continue
        name = str(atom.get("text") or "").removeprefix("url:").strip()
        if not name or name.lower().startswith("http"):
            continue
        eid = entity_id(name)
        entry = by_id.setdefault(
            eid,
            {
                "entity_id": eid,
                "name": name,
                "aliases": [],
                "mention_count": 0,
                "signal_ids": [],
                "atom_ids": [],
                "public_topics": [],
            },
        )
        entry["mention_count"] += 1
        aid = atom.get("atom_id")
        if aid and aid not in entry["atom_ids"]:
            entry["atom_ids"].append(aid)
        parent = atom.get("parent_signal_id")
        if parent and parent not in entry["signal_ids"]:
            entry["signal_ids"].append(parent)

    entities = sorted(by_id.values(), key=lambda e: (-e["mention_count"], e["name"].lower()))
    return {
        "schema": "open_source_news_entities.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "entity_count": len(entities),
        "entities": entities[:500],
    }


def write_entity_exports(
    payload: Dict[str, Any],
    report_date: str,
    *,
    write_pages: bool = True,
    page_limit: int = 50,
) -> Path:
    ENTITIES_OUT.mkdir(parents=True, exist_ok=True)
    path = ENTITIES_OUT / f"{report_date}.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(ENTITIES_OUT / "latest.json", payload)
    if write_pages:
        ENTITY_PAGES.mkdir(parents=True, exist_ok=True)
        for ent in (payload.get("entities") or [])[: max(0, page_limit)]:
            eid = ent.get("entity_id")
            if not eid:
                continue
            page = {
                "schema": "open_source_news_entity_page.v1",
                "report_date": report_date,
                "generated_at": utc_now_iso(),
                **ent,
            }
            _atomic_write_json(ENTITY_PAGES / f"{eid}.json", page)
    return path
