"""Document-index collector: list public document links from an index page.

Does not bulk-download archives. Restricted catalogs (e.g. DDoSecrets) must
set ``download_attachments: false`` and stay disabled until legal review.
"""

from __future__ import annotations

from typing import Any, Dict, List

from collectors.site_change import collect_site_change


def collect_document_index(source: Dict[str, Any], **kwargs: Any) -> List[Dict[str, Any]]:
    if source.get("download_attachments") is True:
        raise ValueError(
            f"{source.get('id')}: document_index collector refuses download_attachments=true"
        )
    observations = collect_site_change(source, **kwargs)
    for item in observations:
        item["adapter"] = "document_index"
        item["adapter_version"] = "document_index.v1"
    return observations
