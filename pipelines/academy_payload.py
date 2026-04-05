"""
Format normalized daily items into Academy-oriented draft payloads (optional helper for Agency).
"""

from __future__ import annotations

from typing import Any, Dict, List


def academy_draft_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a compact draft from a single report item (e.g. wisdom_extraction output).
    Safe to call on any item; missing fields become empty lists or null.
    """
    return {
        "signal_id": item.get("signal_id"),
        "title": item.get("title"),
        "source_urls": item.get("source_urls") or [],
        "bucket": item.get("bucket"),
        "processing_mode": item.get("processing_mode"),
        "difficulty": item.get("difficulty") or None,
        "key_lessons": item.get("key_lessons") or [],
        "actionable_steps": item.get("actionable_steps") or [],
        "tools_mentioned": item.get("tools_mentioned") or [],
        "frameworks_mentioned": item.get("frameworks_mentioned") or [],
        "implementation_notes": item.get("implementation_notes") or None,
        "neutral_synthesis": item.get("neutral_synthesis") or None,
    }


def academy_drafts_from_normalized(normalized: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Given a /api/reports/latest/normalized JSON body, return draft objects for rich items."""
    out: List[Dict[str, Any]] = []
    for it in normalized.get("items") or []:
        mode = (it.get("processing_mode") or "").strip()
        if mode != "wisdom_extraction":
            continue
        out.append(academy_draft_from_item(it))
    return out
