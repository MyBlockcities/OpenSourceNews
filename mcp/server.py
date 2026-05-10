#!/usr/bin/env python3
"""Minimal stdio MCP server for OpenSourceNews.

Run with:
    python3 -m mcp.server

The local package is intentionally named `mcp/` to keep the repo layout simple,
so this server implements the small JSON-RPC surface we need instead of
depending on the external Python package with the same import name.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict

try:
    from . import resources, tools
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mcp import resources, tools


ToolFunc = Callable[..., Dict[str, Any]]


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_latest_report": {
        "description": "Return the latest raw daily report.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tools.get_latest_report,
    },
    "get_latest_normalized_report": {
        "description": "Return the latest daily report in normalized item form.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tools.get_latest_normalized_report,
    },
    "search_news": {
        "description": "Search historical reports by query, topic, bucket, or source.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "days": {"type": "integer", "default": 30},
                "topic": {"type": "string"},
                "bucket": {"type": "string"},
                "source": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": tools.search_news,
    },
    "get_report_by_date": {
        "description": "Return one raw daily report by YYYY-MM-DD date.",
        "inputSchema": {
            "type": "object",
            "properties": {"date": {"type": "string"}},
            "required": ["date"],
        },
        "handler": tools.get_report_by_date,
    },
    "get_signal": {
        "description": "Find a normalized signal by signal_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "signal_id": {"type": "string"},
                "days": {"type": "integer", "default": 365},
            },
            "required": ["signal_id"],
        },
        "handler": tools.get_signal,
    },
    "get_topic_digest": {
        "description": "Return a compact digest for a topic over recent reports.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "days": {"type": "integer", "default": 7},
                "limit": {"type": "integer", "default": 25},
            },
            "required": ["topic"],
        },
        "handler": tools.get_topic_digest,
    },
    "get_manifest": {
        "description": "Return the latest integration manifest.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tools.get_manifest,
    },
    "get_latest_brief": {
        "description": "Return the latest generated mission brief for a watchlist.",
        "inputSchema": {
            "type": "object",
            "properties": {"watchlist": {"type": "string"}},
            "required": ["watchlist"],
        },
        "handler": tools.get_latest_brief,
    },
}


def _tool_specs() -> list[dict[str, Any]]:
    specs = []
    for name, entry in TOOL_REGISTRY.items():
        specs.append(
            {
                "name": name,
                "description": entry["description"],
                "inputSchema": entry["inputSchema"],
            }
        )
    return specs


def _response(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_content(payload: Dict[str, Any], is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2, ensure_ascii=False),
            }
        ],
        "isError": is_error,
    }


def handle(message: Dict[str, Any]) -> Dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        protocol_version = params.get("protocolVersion") or "2024-11-05"
        return _response(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "opensourcenews", "version": "0.1.0"},
            },
        )
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": _tool_specs()})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        entry = TOOL_REGISTRY.get(name)
        if not entry:
            return _response(request_id, _tool_content({"error": f"Unknown tool: {name}"}, True))
        try:
            payload = entry["handler"](**args)
            return _response(request_id, _tool_content(payload, bool(payload.get("error"))))
        except Exception as exc:
            return _response(request_id, _tool_content({"error": str(exc)}, True))
    if method == "resources/list":
        return _response(request_id, {"resources": resources.list_resources()})
    if method == "resources/read":
        uri = params.get("uri")
        payload = resources.read_resource(uri)
        return _response(
            request_id,
            {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, ensure_ascii=False),
                    }
                ]
            },
        )

    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except Exception as exc:
            response = _error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
