"""Public-learnable per-source per-topic trust scores (EMA + class priors)."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
TRUST_OUT = ROOT_DIR / "outputs" / "source_trust"
STATE_PATH = TRUST_OUT / "ema_state.json"

_SOURCE_PRIORS = {
    "pubmed": 0.85,
    "clinicaltrials": 0.8,
    "rss": 0.65,
    "hackernews": 0.6,
    "github": 0.7,
    "youtube": 0.55,
    "x": 0.45,
    "unknown": 0.5,
}

DEFAULT_ALPHA = 0.1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _source_key(item: Dict[str, Any]) -> str:
    return str(item.get("source") or item.get("source_domain") or "unknown").strip() or "unknown"


def _source_class(item: Dict[str, Any]) -> str:
    source = _source_key(item).lower()
    if "pubmed" in source:
        return "pubmed"
    if "clinical" in source:
        return "clinicaltrials"
    if "github" in source:
        return "github"
    if "youtube" in source or source.startswith("@"):
        return "youtube"
    if "hacker" in source or source == "hn":
        return "hackernews"
    if source in {"x", "twitter"}:
        return "x"
    return "rss" if source != "unknown" else "unknown"


class SourceTrustModel:
    """EMA trust per (source, topic). Neutral prior 0.5, clamped 0–1."""

    def __init__(self, alpha: float = DEFAULT_ALPHA, state: Optional[Dict[str, Any]] = None):
        self.alpha = alpha
        self.scores: Dict[str, float] = {}
        self.evidence_counts: Dict[str, int] = {}
        if state:
            self.scores = {k: float(v.get("score", 0.5)) for k, v in (state.get("scores") or {}).items()}
            self.evidence_counts = {
                k: int(v.get("evidence_count") or 0) for k, v in (state.get("scores") or {}).items()
            }

    @staticmethod
    def key(source: str, topic: str) -> str:
        return f"{source}::{topic}"

    def get_trust(self, source: str, topic: str) -> float:
        return float(self.scores.get(self.key(source, topic), 0.5))

    def _bump(self, source: str, topic: str, delta: float) -> None:
        k = self.key(source, topic)
        old = float(self.scores.get(k, 0.5))
        new = max(0.0, min(1.0, old + self.alpha * delta))
        self.scores[k] = new
        self.evidence_counts[k] = int(self.evidence_counts.get(k, 0)) + 1

    def record_corroboration(self, source: str, topic: str) -> None:
        self._bump(source, topic, 0.05)

    def record_contradiction(self, source: str, topic: str) -> None:
        self._bump(source, topic, -0.15)

    def record_retraction(self, source: str, topic: str) -> None:
        self._bump(source, topic, -0.25)

    def export_state(self) -> Dict[str, Any]:
        scores = {}
        for k, v in self.scores.items():
            scores[k] = {
                "score": round(v, 4),
                "evidence_count": int(self.evidence_counts.get(k, 0)),
                "last_updated": utc_now_iso(),
            }
        return {"schema": "source_trust_ema_state.v1", "alpha": self.alpha, "scores": scores}


def load_ema_state(path: Path = STATE_PATH) -> SourceTrustModel:
    if path.exists():
        try:
            return SourceTrustModel(state=json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            pass
    return SourceTrustModel()


def build_source_trust(
    items: List[Dict[str, Any]],
    consensus: Optional[Dict[str, Any]] = None,
    *,
    report_date: str,
    model: Optional[SourceTrustModel] = None,
) -> Dict[str, Any]:
    model = model or load_ema_state()
    by_source_topic: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"count": 0.0, "confirm": 0.0, "contradict": 0.0})
    )
    source_class: Dict[str, str] = {}

    for item in items:
        src = _source_key(item)
        source_class[src] = _source_class(item)
        topics = item.get("public_topics") or ["untagged"]
        for topic in topics:
            by_source_topic[src][topic]["count"] += 1.0

    if consensus:
        for claim in consensus.get("claims") or []:
            topic = "untagged"
            for src in claim.get("confirming_sources") or []:
                model.record_corroboration(src, topic)
                by_source_topic[src]["__global__"]["confirm"] += 1.0
                source_class.setdefault(src, "unknown")
            for src in claim.get("contradicting_sources") or []:
                model.record_contradiction(src, topic)
                by_source_topic[src]["__global__"]["contradict"] += 1.0
                source_class.setdefault(src, "unknown")

    rows = []
    for src, topic_map in by_source_topic.items():
        prior = _SOURCE_PRIORS.get(source_class.get(src, "unknown"), 0.5)
        for topic, stats in topic_map.items():
            count = stats["count"]
            confirm = stats["confirm"]
            contradict = stats["contradict"]
            ema = model.get_trust(src, topic if topic != "__global__" else "untagged")
            volume = min(1.0, count / 10.0) if count else 0.0
            confirm_boost = min(0.2, confirm * 0.05)
            contradict_pen = min(0.25, contradict * 0.08)
            # Blend class prior + volume signal + EMA learned trust
            score = max(
                0.0,
                min(
                    1.0,
                    prior * 0.35 + volume * 0.2 + confirm_boost - contradict_pen + ema * 0.45,
                ),
            )
            rows.append(
                {
                    "source": src,
                    "source_class": source_class.get(src, "unknown"),
                    "topic": topic,
                    "item_count": int(count),
                    "confirmation_events": int(confirm),
                    "contradiction_events": int(contradict),
                    "ema_trust": round(ema, 4),
                    "trust_score": round(score, 4),
                }
            )

    rows.sort(key=lambda r: (-r["trust_score"], r["source"], r["topic"]))
    state = model.export_state()
    _atomic_write_json(STATE_PATH, state)

    return {
        "schema": "open_source_news_source_trust.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "methodology": "prior*0.35 + volume*0.2 + confirm - contradict + ema*0.45",
        "alpha": model.alpha,
        "scores": rows[:500],
    }


def write_source_trust(payload: Dict[str, Any], report_date: str) -> Path:
    TRUST_OUT.mkdir(parents=True, exist_ok=True)
    path = TRUST_OUT / f"{report_date}.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(TRUST_OUT / "latest.json", payload)
    return path
