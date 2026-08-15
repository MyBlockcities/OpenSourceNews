"""FOIA / archive catalog collector. Metadata only; no bulk file retrieval."""

from __future__ import annotations

from typing import Any, Dict, List

from collectors.document_index import collect_document_index


def collect_foia_archive(source: Dict[str, Any], **kwargs: Any) -> List[Dict[str, Any]]:
    if source.get("extract_personal_data") is True:
        raise ValueError(f"{source.get('id')}: FOIA collector will not extract personal data")
    observations = collect_document_index(source, **kwargs)
    for item in observations:
        item["adapter"] = "foia_archive"
        item["adapter_version"] = "foia_archive.v1"
    return observations
