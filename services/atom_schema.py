"""Atom schema (atom.v1) for OpenSourceNews → Hermes.

Atoms are public-domain, append-only extraction units produced on GitHub Actions
so Hermes does not need to re-run expensive extraction locally.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ATOM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews/atoms")
SCHEMA_VERSION = "atom.v1"
ATOM_TYPES = (
    "claim",
    "data_point",
    "tool",
    "framework",
    "entity",
    "prediction",
    "counterexample",
    "reasoning",
)

_URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.I)
_TOOL_RE = re.compile(
    r"\b(langchain|langgraph|autogen|crewai|ollama|openai|anthropic|claude|"
    r"gemini|qdrant|neo4j|fastapi|next\.?js|typescript|pytorch|tensorflow|"
    r"huggingface|vllm|llama\.?cpp|mcp|n8n|cursor|docker|kubernetes)\b",
    re.I,
)
_FRAMEWORK_RE = re.compile(
    r"\b(react|vue|svelte|django|flask|express|spring|rails|"
    r"transformer|diffusion|rag|agentic|mcp protocol)\b",
    re.I,
)
_ENTITY_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|OpenAI|Anthropic|Google|Meta|Microsoft|"
    r"BlackRock|Ethereum|Solana|Bitcoin|FDA|SEC|NVIDIA)\b"
)
_CLAIM_HINT_RE = re.compile(
    r"\b(is|are|will|claims?|shows?|found|reports?|announces?|launches?)\b",
    re.I,
)
_PREDICTION_RE = re.compile(
    r"\b(will|by 20\d{2}|next year|in the future|expected to|forecast)\b",
    re.I,
)
_COUNTER_RE = re.compile(
    r"\b(however|but|contrary|despite|unlike|not actually|debunk|myth)\b",
    re.I,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text_hash(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


def make_atom_id(parent_signal_id: str, atom_type: str, text: str) -> str:
    key = f"{parent_signal_id}|{atom_type}|{text_hash(text)}"
    return str(uuid.uuid5(ATOM_NAMESPACE, key))


def build_atom(
    *,
    parent_signal_id: str,
    atom_type: str,
    text: str,
    evidence_urls: Optional[List[str]] = None,
    extracted_at: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if atom_type not in ATOM_TYPES:
        raise ValueError(f"invalid atom_type: {atom_type}")
    body = (text or "").strip()
    if not body:
        raise ValueError("atom text required")
    atom: Dict[str, Any] = {
        "atom_id": make_atom_id(parent_signal_id, atom_type, body),
        "parent_signal_id": parent_signal_id,
        "atom_type": atom_type,
        "text": body[:2000],
        "evidence_urls": list(evidence_urls or []),
        "extracted_at": extracted_at or utc_now_iso(),
        "schema_version": SCHEMA_VERSION,
    }
    if extra:
        atom.update(extra)
    return atom


def extract_deterministic_atoms(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Regex/heuristic atoms — free on Actions, no LLM required."""
    signal_id = str(item.get("signal_id") or "")
    if not signal_id:
        return []
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or item.get("excerpt") or "")
    blob = f"{title}\n{summary}".strip()
    url = str(item.get("canonical_url") or item.get("url") or "")
    evidence = [url] if url else []
    atoms: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _add(atom_type: str, text: str) -> None:
        text = text.strip(" .,;:-")
        if len(text) < 3:
            return
        try:
            atom = build_atom(
                parent_signal_id=signal_id,
                atom_type=atom_type,
                text=text,
                evidence_urls=evidence,
            )
        except ValueError:
            return
        if atom["atom_id"] in seen:
            return
        seen.add(atom["atom_id"])
        atoms.append(atom)

    for match in _URL_RE.findall(blob):
        clean = match.rstrip(".,);]")
        if clean and clean != url:
            _add("entity", f"url:{clean}")

    for match in _TOOL_RE.finditer(blob):
        _add("tool", match.group(0))

    for match in _FRAMEWORK_RE.finditer(blob):
        _add("framework", match.group(0))

    for match in _ENTITY_RE.finditer(blob):
        name = match.group(0).strip()
        if len(name) >= 3 and name.lower() not in {"the", "and", "for", "with"}:
            _add("entity", name)

    # Title as weak claim seed when it looks declarative.
    if title and _CLAIM_HINT_RE.search(title) and len(title) > 20:
        _add("claim", title)

    if summary and _PREDICTION_RE.search(summary):
        # First sentence-ish of summary as prediction candidate.
        snippet = re.split(r"(?<=[.!?])\s+", summary)[0][:400]
        if snippet:
            _add("prediction", snippet)

    if summary and _COUNTER_RE.search(summary):
        snippet = re.split(r"(?<=[.!?])\s+", summary)[0][:400]
        if snippet:
            _add("counterexample", snippet)

    # Numeric data points
    for match in re.finditer(
        r"\b(\$?\d[\d,]*(?:\.\d+)?\s*(?:%|percent|stars?|downloads?|billion|million|B|M|K)?)\b",
        blob,
        re.I,
    ):
        _add("data_point", match.group(0))

    return atoms
