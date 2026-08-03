"""Cross-source consensus for claim-like atoms.

Algorithm (deterministic, Actions-safe):
  1. Filter claim / prediction / counterexample atoms
  2. Token Jaccard cluster (threshold ~0.55) as cosine proxy without vectors
  3. Canonical text = longest member (centroid proxy)
  4. Support vs contradiction by atom_type + polarity
  5. Agreement weighted by source diversity (+ optional trust lookup)
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT_DIR = Path(__file__).resolve().parents[1]
CONSENSUS_OUT = ROOT_DIR / "outputs" / "consensus"

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
CLAIM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews/claims")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def tokenize(text: str) -> Set[str]:
    cleaned = _NORMALIZE_RE.sub(" ", (text or "").lower()).strip()
    return {t for t in cleaned.split() if len(t) > 2}


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def claim_key(text: str) -> str:
    tokens = sorted(tokenize(text))
    return " ".join(tokens[:12])


def compute_agreement(
    *,
    confirmation_count: int,
    contradiction_count: int,
    source_count: int,
    mean_trust: float = 0.5,
) -> float:
    total = max(1, confirmation_count + contradiction_count)
    positive_rate = confirmation_count / total
    if source_count < 2:
        base = 0.5
    else:
        diversity = min(source_count / 5.0, 1.0)
        base = positive_rate * (0.5 + 0.5 * diversity)
    return round(max(0.0, min(1.0, base * (0.5 + 0.5 * mean_trust))), 4)


def _cluster_claims(atoms: List[Dict[str, Any]], threshold: float = 0.55) -> List[List[Dict[str, Any]]]:
    """Greedy clustering by token Jaccard (stand-in for cosine 0.82 without embeddings)."""
    prepared = []
    for atom in atoms:
        text = str(atom.get("text") or "")
        toks = tokenize(text)
        if len(toks) < 4:
            continue
        prepared.append({**atom, "_tokens": toks, "_text": text})

    clusters: List[List[Dict[str, Any]]] = []
    used = [False] * len(prepared)
    for i, atom in enumerate(prepared):
        if used[i]:
            continue
        cluster = [atom]
        used[i] = True
        for j in range(i + 1, len(prepared)):
            if used[j]:
                continue
            if jaccard(atom["_tokens"], prepared[j]["_tokens"]) >= threshold:
                cluster.append(prepared[j])
                used[j] = True
        if len(cluster) >= 2:
            clusters.append(cluster)
        elif atom.get("atom_type") == "claim" and len(atom["_tokens"]) >= 6:
            # singleton claims still exported with weak agreement
            clusters.append(cluster)
    return clusters


def build_consensus(
    atoms: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
    *,
    report_date: str,
    trust_lookup: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    signal_source = {
        str(i.get("signal_id") or ""): str(i.get("source") or i.get("source_domain") or "unknown")
        for i in items
    }
    claim_atoms = [a for a in atoms if a.get("atom_type") in {"claim", "prediction", "counterexample"}]
    clusters = _cluster_claims(claim_atoms, threshold=0.55)

    rows = []
    for cluster in clusters:
        canonical = max(cluster, key=lambda a: len(str(a.get("_text") or a.get("text") or "")))
        canonical_text = str(canonical.get("_text") or canonical.get("text") or "")
        confirming: Set[str] = set()
        contradicting: Set[str] = set()
        sources: Set[str] = set()
        atom_ids = []
        polarities = []
        for atom in cluster:
            parent = str(atom.get("parent_signal_id") or "")
            source = signal_source.get(parent, "unknown")
            sources.add(source)
            atom_ids.append(atom.get("atom_id"))
            polarity = str(atom.get("polarity") or "").lower()
            if not polarity:
                polarity = "contradicts" if atom.get("atom_type") == "counterexample" else "supports"
            polarities.append(polarity)
            if polarity == "contradicts":
                contradicting.add(source)
            else:
                confirming.add(source)

        trusts = []
        for src in sources:
            if trust_lookup and src in trust_lookup:
                trusts.append(trust_lookup[src])
        mean_trust = sum(trusts) / len(trusts) if trusts else 0.5

        strength = compute_agreement(
            confirmation_count=len(confirming),
            contradiction_count=len(contradicting),
            source_count=len(sources),
            mean_trust=mean_trust,
        )
        claim_id = str(uuid.uuid5(CLAIM_NAMESPACE, claim_key(canonical_text) or canonical_text[:64]))
        rows.append(
            {
                "claim_id": claim_id,
                "claim_key": claim_key(canonical_text),
                "canonical_text": canonical_text[:400],
                "sample_text": canonical_text[:400],
                "member_atom_ids": atom_ids[:30],
                "atom_ids": atom_ids[:20],
                "source_count": len(sources),
                "sources": sorted(sources),
                "confirmation_count": len(confirming),
                "contradiction_count": len(contradicting),
                "confirming_sources": sorted(confirming),
                "contradicting_sources": sorted(contradicting),
                "consensus_strength": strength,
                "atom_types": sorted({str(a.get("atom_type")) for a in cluster}),
                "schema_version": "consensus.v1",
            }
        )

    rows.sort(
        key=lambda r: (
            -float(r.get("consensus_strength") or 0),
            -r["confirmation_count"],
            -r["source_count"],
        )
    )
    return {
        "schema": "open_source_news_consensus.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "algorithm": "token_jaccard_cluster_v1",
        "cluster_threshold": 0.55,
        "claim_cluster_count": len(rows),
        "claims": rows[:200],
    }


def write_consensus(payload: Dict[str, Any], report_date: str) -> Path:
    CONSENSUS_OUT.mkdir(parents=True, exist_ok=True)
    path = CONSENSUS_OUT / f"{report_date}.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(CONSENSUS_OUT / "latest.json", payload)
    return path
