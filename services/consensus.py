"""Cross-source consensus: cluster similar claims and score agreement.

This module is purely deterministic. It uses the atom_id hash and
parent_signal_id fields to build a stable cluster_id per claim group.
No LLM. No embeddings. The clustering is text-similarity over
normalized claim text — good enough for short, declarative claims.

Output
------
- outputs/consensus/{date}.json : per-cluster consensus + divergence
- Embedding-quality clustering (Qdrant-side) is done by Hermes; this
  module produces a text-based fallback that runs on free Actions compute.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from services.news_schema import utc_now_iso

# Cluster ID namespace (separate from atom namespace).
_CLUSTER_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews#claim_cluster"
)

# How similar two claim texts must be to land in the same cluster.
# Higher = stricter (fewer merges, more clusters).
_SIMILARITY_THRESHOLD = 0.78

# A few stopwords that don't carry meaning for clustering.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "and", "or", "but", "so", "as", "at",
    "by", "with", "this", "that", "these", "those", "it", "its", "from",
    "has", "have", "had", "will", "would", "can", "could", "should", "may",
    "might", "do", "does", "did", "i", "you", "we", "they", "he", "she",
    "his", "her", "their", "our", "your", "my",
}

DEFAULT_CONSENSUS_DIR = Path(__file__).resolve().parents[1] / "outputs" / "consensus"

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> List[str]:
    """Lowercase, strip punctuation, drop stopwords and short tokens."""
    tokens = _WORD_RE.findall((text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _jaccard(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = sa & sb
    union = sa | sb
    if not union:
        return 0.0
    return len(inter) / len(union)


def _cluster_id(canonical_text: str) -> str:
    norm = re.sub(r"\s+", " ", (canonical_text or "").strip().lower())
    return uuid.uuid5(_CLUSTER_NAMESPACE, norm).hex[:24]


def collect_claim_atoms(atoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter atoms to claim-type only. Defensive about shape."""
    out: List[Dict[str, Any]] = []
    for a in atoms:
        if not isinstance(a, dict):
            continue
        if a.get("atom_type") != "claim":
            continue
        text = (a.get("text") or "").strip()
        if not text:
            continue
        out.append(a)
    return out


def cluster_claims(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cluster similar claims. Single-link clustering by Jaccard over word sets.

    Cheap and good enough for short claim text. Returns a list of cluster
    dicts (see _build_cluster_record for shape).
    """
    # Pre-compute normalized token lists.
    norm_tokens: List[List[str]] = [_normalize(c.get("text", "")) for c in claims]
    n = len(claims)
    parent_idx: List[int] = list(range(n))

    def find(i: int) -> int:
        while parent_idx[i] != i:
            parent_idx[i] = parent_idx[parent_idx[i]]
            i = parent_idx[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent_idx[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            sim = _jaccard(norm_tokens[i], norm_tokens[j])
            if sim >= _SIMILARITY_THRESHOLD:
                union(i, j)

    # Group by root.
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    clusters: List[Dict[str, Any]] = []
    for indices in groups.values():
        # Canonical text = longest member (most information).
        canonical_idx = max(indices, key=lambda k: len(claims[k].get("text", "")))
        clusters.append(_build_cluster_record(claims, indices, canonical_idx))
    return clusters


def _build_cluster_record(
    claims: List[Dict[str, Any]],
    indices: List[int],
    canonical_idx: int,
) -> Dict[str, Any]:
    canonical = claims[canonical_idx]
    canonical_text = (canonical.get("text") or "").strip()

    # Source distribution.
    source_doms: Set[str] = set()
    polarity_counts: Dict[str, int] = defaultdict(int)
    atom_ids: List[str] = []
    parent_signal_ids: List[str] = []
    evidence: Set[str] = set()
    for i in indices:
        c = claims[i]
        dom = (c.get("parent_source_domain") or "").strip()
        if dom:
            source_doms.add(dom)
        pol = (c.get("polarity") or "neutral").strip().lower()
        if pol not in {"supports", "neutral", "contradicts"}:
            pol = "neutral"
        polarity_counts[pol] += 1
        if c.get("atom_id"):
            atom_ids.append(c["atom_id"])
        if c.get("parent_signal_id"):
            parent_signal_ids.append(c["parent_signal_id"])
        for u in c.get("evidence_urls") or []:
            if u:
                evidence.add(u)

    # Agreement score: balance of support / contradict + source diversity.
    total = sum(polarity_counts.values()) or 1
    support_rate = polarity_counts["supports"] / total
    contradict_rate = polarity_counts["contradicts"] / total
    # Diversity bonus: more distinct sources = stronger evidence.
    diversity = min(len(source_doms) / 5.0, 1.0)
    # 0-1: how much the cluster "agrees" overall.
    agreement = round(
        max(0.0, min(1.0, support_rate - contradict_rate)) * (0.5 + 0.5 * diversity),
        3,
    )

    return {
        "cluster_id": _cluster_id(canonical_text),
        "canonical_text": canonical_text,
        "member_count": len(indices),
        "atom_ids": atom_ids,
        "parent_signal_ids": parent_signal_ids,
        "source_domains": sorted(source_doms),
        "source_count": len(source_doms),
        "polarity_counts": dict(polarity_counts),
        "agreement_score": agreement,
        "evidence_urls": sorted(evidence)[:10],
        "schema_version": "consensus.v1",
    }


def export_consensus_snapshot(
    clusters: List[Dict[str, Any]],
    *,
    report_date: str,
    out_dir: Path = DEFAULT_CONSENSUS_DIR,
) -> Path:
    """Write the per-day consensus snapshot. Atomic write."""
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{report_date}.json"
    tmp = out_dir / f"{report_date}.json.tmp"
    payload = {
        "report_date": report_date,
        "cluster_count": len(clusters),
        "clusters": clusters,
        "schema_version": "consensus.v1",
    }
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp.replace(final)
    latest = out_dir / "latest.json"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(final.read_bytes())
    return final


def find_consensus(
    atoms: List[Dict[str, Any]],
    *,
    report_date: str,
) -> List[Dict[str, Any]]:
    """Convenience: collect claims, cluster them, return the cluster list."""
    claims = collect_claim_atoms(atoms)
    return cluster_claims(claims)
