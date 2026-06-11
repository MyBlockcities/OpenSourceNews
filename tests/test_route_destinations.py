"""Unit tests for destination routing (pipelines/route_destinations.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.route_destinations import (
    filter_for_destination,
    route_item,
    route_normalized,
)


def _item(**kw):
    base = {"title": "", "summary": "", "bucket": "general", "category": ""}
    base.update(kw)
    return base


def test_ai_bucket_routes_academy():
    assert route_item(_item(bucket="ai", title="New LLM framework released")) == "academy"


def test_godseye_keywords_route_godseye():
    item = _item(
        bucket="general",
        title="OPEC announces oil production cuts amid sanctions",
        summary="Energy markets react to new tariff policy and supply chain risk.",
    )
    assert route_item(item) == "godseye"


def test_overlap_routes_both():
    item = _item(
        bucket="ai",
        title="AI agents deployed for military conflict analysis",
        summary="LLM tooling used by defense and national security analysts in wartime intelligence.",
    )
    assert route_item(item) == "both"


def test_no_signal_falls_back_to_default():
    item = _item(bucket="peptides", title="BPC-157 dosage overview", summary="")
    assert route_item(item) == "academy"


def test_route_normalized_tags_every_item_and_counts():
    normalized = {
        "report_date": "2026-06-10",
        "items": [
            _item(bucket="ai", title="Open source MCP server"),
            _item(bucket="sense_making", title="Central bank interest rate shift"),
        ],
        "counts": {"total": 2},
    }
    routed = route_normalized(normalized)
    assert all("destination" in i for i in routed["items"])
    bd = routed["counts"]["by_destination"]
    assert bd["academy"] >= 1 and bd["godseye"] >= 1
    # original untouched
    assert "destination" not in normalized["items"][0]


def test_filter_for_destination_includes_both():
    normalized = route_normalized({
        "items": [
            _item(bucket="ai", title="agentic coding sdk"),
            _item(
                bucket="ai",
                title="AI in military conflict and national security",
                summary="defense llm warfare sanction analysis with open source agents",
            ),
            _item(bucket="alternative_news", title="tariff war escalates trade conflict"),
        ],
    })
    academy = filter_for_destination(normalized, "academy")
    godseye = filter_for_destination(normalized, "godseye")
    academy_titles = [i["title"] for i in academy["items"]]
    godseye_titles = [i["title"] for i in godseye["items"]]
    assert "agentic coding sdk" in academy_titles
    assert "tariff war escalates trade conflict" in godseye_titles
    # "both" item should appear in each
    assert any("military" in t for t in academy_titles) or any("military" in t for t in godseye_titles)


def test_filter_rejects_bad_destination():
    try:
        filter_for_destination({"items": []}, "nope")
        assert False, "expected ValueError"
    except ValueError:
        pass
