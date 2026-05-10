"""Resource definitions for the OpenSourceNews MCP server."""

from __future__ import annotations

from typing import Any, Dict, List

from . import tools


def list_resources() -> List[Dict[str, str]]:
    return [
        {
            "uri": "news://latest",
            "name": "Latest raw report",
            "description": "Most recent OpenSourceNews daily report.",
            "mimeType": "application/json",
        },
        {
            "uri": "news://latest/normalized",
            "name": "Latest normalized report",
            "description": "Most recent report in agent-friendly normalized form.",
            "mimeType": "application/json",
        },
        {
            "uri": "news://manifest/latest",
            "name": "Latest manifest",
            "description": "Integration manifest for latest generated outputs.",
            "mimeType": "application/json",
        },
    ]


def read_resource(uri: str) -> Dict[str, Any]:
    if uri == "news://latest":
        return tools.get_latest_report()
    if uri == "news://latest/normalized":
        return tools.get_latest_normalized_report()
    if uri == "news://manifest/latest":
        return tools.get_manifest()
    return {"error": f"Unknown resource URI: {uri}"}
