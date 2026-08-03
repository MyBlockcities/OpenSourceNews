"""Per-source per-topic trust scoring with exponential moving average.

The trust score is public-learnable. Anyone can rebuild it from the
consensus + atom data. It updates daily from the consensus pipeline:

- consensus.support(source, topic)  → +0.05  (EMA weight 0.10)
- consensus.contradict(source, topic)→ -0.15
- retraction or human-flag          → -0.25

Initial score is 0.5 (neutral). Scores are bounded to [0.0, 1.0].
The model is intentionally simple — it's a starting point, not a
Bayesian oracle. Hermes may apply its own private multipliers on top.

Output
------
- outputs/source_trust/{date}.json : per-source per-topic snapshot
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from services.news_schema import utc_now_iso

DEFAULT_TRUST_DIR = Path(__file__).resolve().parents[1] / "outputs" / "source_trust"

# Initial score for a never-seen (source, topic) pair.
INITIAL_SCORE = 0.5

# EMA smoothing factor applied to each positive/negative signal.
ALPHA = 0.10

# Per-signal weights.
W_CORROBORATION = 0.05
W_CONTRADICTION = 0.15
W_RETRACTION = 0.25

# Bounded range.
_SCORE_MIN, _SCORE_MAX = 0.0, 1.0


def _key(source: str, topic: str) -> Tuple[str, str]:
    return ((source or "").strip().lower(), (topic or "").strip().lower())


def empty_state() -> Dict[str, Any]:
    """Return a fresh, in-memory trust state."""
    return {
        "scores": {},        # (source, topic) -> float
        "evidence": defaultdict(list),
        "version": 1,
    }


def load_state(path: Path) -> Dict[str, Any]:
    """Load existing trust state from a snapshot. Best-effort."""
    if not path.exists():
        return empty_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()
    scores = data.get("scores") or {}
    out_scores: Dict[Tuple[str, str], float] = {}
    for k, v in scores.items():
        if isinstance(k, str) and "::" in k:
            source, topic = k.split("::", 1)
            try:
                out_scores[(source, topic)] = float(v)
            except (TypeError, ValueError):
                continue
    return {"scores": out_scores, "evidence": defaultdict(list), "version": 1}


def _bump(state: Dict[str, Any], source: str, topic: str, delta: float, evidence_type: str) -> float:
    key = _key(source, topic)
    cur = state["scores"].get(key, INITIAL_SCORE)
    # EMA: new = cur + alpha * delta (delta already encodes the signal weight).
    new = max(_SCORE_MIN, min(_SCORE_MAX, cur + ALPHA * delta))
    state["scores"][key] = round(new, 4)
    state["evidence"][key].append(
        {"type": evidence_type, "delta": delta, "at": utc_now_iso()}
    )
    return new


def record_corroboration(state: Dict[str, Any], source: str, topic: str) -> float:
    """Source said something that other sources confirmed. Small positive bump."""
    return _bump(state, source, topic, W_CORROBORATION, "corroboration")


def record_contradiction(state: Dict[str, Any], source: str, topic: str) -> float:
    """Source said something that other sources contradicted. Negative bump."""
    return _bump(state, source, topic, -W_CONTRADICTION, "contradiction")


def record_retraction(state: Dict[str, Any], source: str, topic: str) -> float:
    """Source retracted a claim. Strongest negative signal."""
    return _bump(state, source, topic, -W_RETRACTION, "retraction")


def get_trust(state: Dict[str, Any], source: str, topic: str) -> float:
    return state["scores"].get(_key(source, topic), INITIAL_SCORE)


# -- Updating from consensus clusters ----------------------------------------

def update_from_consensus(
    state: Dict[str, Any],
    clusters: List[Dict[str, Any]],
    *,
    topics_for_atom: Optional[Dict[str, List[str]]] = None,
) -> int:
    """Apply today's consensus clusters to the trust state.

    For each cluster:
    - If `agreement_score >= 0.6` AND the cluster has 2+ source domains,
      all contributing sources get a corroboration signal.
    - If `agreement_score <= 0.2`, contributing sources with the *minority*
      polarity get a contradiction signal.

    Parameters
    ----------
    state : dict
        The current trust state (mutated in place).
    clusters : list
        Output of services.consensus.cluster_claims.
    topics_for_atom : optional dict
        atom_id -> list of public_topics. When provided, source/topic
        updates are applied per-topic (more granular). When None, we
        use the wildcard topic "*" so trust is at least source-level.

    Returns
    -------
    int : number of (source, topic) updates applied.
    """
    updates = 0
    for c in clusters:
        domains = c.get("source_domains") or []
        if len(domains) < 2:
            continue
        agreement = float(c.get("agreement_score") or 0.0)
        polarity_counts = c.get("polarity_counts") or {}
        # Determine minority polarity for low-agreement clusters.
        minority = None
        if agreement <= 0.2 and polarity_counts:
            minority = min(polarity_counts, key=polarity_counts.get)
        atom_ids = c.get("atom_ids") or []
        topics = ["*"]
        if topics_for_atom:
            for aid in atom_ids:
                t = topics_for_atom.get(aid)
                if t:
                    topics = list(set(topics + t))
        for source in domains:
            for topic in topics:
                if minority and minority == "contradicts":
                    record_contradiction(state, source, topic)
                elif agreement >= 0.6:
                    record_corroboration(state, source, topic)
                updates += 1
    return updates


def export_trust_snapshot(
    state: Dict[str, Any],
    *,
    report_date: str,
    out_dir: Path = DEFAULT_TRUST_DIR,
) -> Path:
    """Write the per-day trust snapshot. Atomic write."""
    out_dir.mkdir(parents=True, exist_ok=True)
    flat: Dict[str, Dict[str, Any]] = {}
    for (source, topic), score in state["scores"].items():
        flat[f"{source}::{topic}"] = {
            "source": source,
            "topic": topic,
            "score": score,
            "evidence_count": len(state["evidence"].get((source, topic), [])),
        }
    payload = {
        "report_date": report_date,
        "initial_score": INITIAL_SCORE,
        "alpha": ALPHA,
        "weights": {
            "corroboration": W_CORROBORATION,
            "contradiction": W_CONTRADICTION,
            "retraction": W_RETRACTION,
        },
        "source_topic_count": len(flat),
        "scores": flat,
        "schema_version": "source_trust.v1",
    }
    final = out_dir / f"{report_date}.json"
    tmp = out_dir / f"{report_date}.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp.replace(final)
    latest = out_dir / "latest.json"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(final.read_bytes())
    return final
