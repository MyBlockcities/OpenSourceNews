"""Enforce T0–T5 source policy on collected items."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.source_registry import (
    load_policy,
    load_sources,
    lookup_by_endpoint,
    lookup_by_item_url,
)

_POLICY: Optional[Dict[str, Any]] = None
_SOURCES: Optional[list] = None


def _policy() -> Dict[str, Any]:
    global _POLICY
    if _POLICY is None:
        _POLICY = load_policy()
    return _POLICY


def _sources() -> list:
    global _SOURCES
    if _SOURCES is None:
        _SOURCES = load_sources()
    return _SOURCES


def reset_cache() -> None:
    """Test helper."""
    global _POLICY, _SOURCES
    _POLICY = None
    _SOURCES = None


def defaults_for_unknown() -> Dict[str, Any]:
    unknown = _policy().get("unknown_source_defaults") or {}
    return {
        "source_id": unknown.get("source_id") or "unmatched",
        "source_tier": unknown.get("tier") or "T3",
        "permitted_use": unknown.get("permitted_use") or "discovery_only",
        "corroboration_required": bool(unknown.get("corroboration_required", True)),
        "automatic_content_eligible": bool(unknown.get("automatic_content_eligible", False)),
        "automatic_evidence_promotion": bool(unknown.get("automatic_evidence_promotion", False)),
    }


def policy_fields_for_source(source: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(source.get("tier") or "T3")
    tier_meta = (_policy().get("tiers") or {}).get(tier) or {}
    automatic_content = source.get("automatic_content_eligible")
    if automatic_content is None:
        automatic_content = bool(tier_meta.get("automatic_content_eligible", False))
    automatic_evidence = source.get("automatic_evidence_promotion")
    if automatic_evidence is None:
        automatic_evidence = bool(tier_meta.get("automatic_evidence_promotion", False))
    if tier in {"T4", "T5"}:
        automatic_content = False
        automatic_evidence = False
    return {
        "source_id": source.get("id") or "unmatched",
        "source_tier": tier,
        "permitted_use": source.get("permitted_use") or "discovery_only",
        "corroboration_required": bool(source.get("corroboration_required", True)),
        "automatic_content_eligible": bool(automatic_content),
        "automatic_evidence_promotion": bool(automatic_evidence),
        "source_kind": source.get("source_kind") or "",
        "publisher": source.get("publisher") or "",
        "extract_outbound_evidence_links": bool(
            source.get("extract_outbound_evidence_links", True)
        ),
    }


def resolve_source(
    *,
    endpoint: str = "",
    url: str = "",
    sources: Optional[list] = None,
) -> Optional[Dict[str, Any]]:
    pool = sources if sources is not None else _sources()
    if endpoint:
        found = lookup_by_endpoint(endpoint, sources=pool)
        if found:
            return found
    if url:
        return lookup_by_item_url(url, sources=pool)
    return None


def annotate_item(
    item: Dict[str, Any],
    *,
    endpoint: str = "",
    sources: Optional[list] = None,
) -> Dict[str, Any]:
    """Stamp source policy onto a collected item. Unknown sources fail closed to T3 discovery."""
    found = resolve_source(
        endpoint=endpoint,
        url=str(item.get("canonical_url") or item.get("url") or ""),
        sources=sources,
    )
    fields = policy_fields_for_source(found) if found else defaults_for_unknown()
    item.update(fields)
    if found:
        item.setdefault("source_registry_id", found.get("id"))
    return item


def can_establish_facts(item_or_source: Dict[str, Any]) -> bool:
    tier = str(item_or_source.get("source_tier") or item_or_source.get("tier") or "")
    permitted = str(item_or_source.get("permitted_use") or "")
    return tier in {"T0", "T1"} and permitted == "factual_support"


def content_eligible(item: Dict[str, Any]) -> bool:
    if item.get("automatic_content_eligible") is not True:
        return False
    if str(item.get("source_tier") or "") in {"T4", "T5"}:
        return False
    return True
