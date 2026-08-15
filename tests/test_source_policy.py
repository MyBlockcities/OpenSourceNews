"""T0–T5 permitted-use enforcement on collected items."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.source_policy import (
    annotate_item,
    can_establish_facts,
    content_eligible,
    reset_cache,
)


def setup_function():
    reset_cache()


def test_official_feed_stamps_t0_factual_support():
    item = {
        "title": "FOMC statement",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260815a.htm",
    }
    annotate_item(item, endpoint="https://www.federalreserve.gov/feeds/press_all.xml")
    assert item["source_id"] == "federal_reserve_press"
    assert item["source_tier"] == "T0"
    assert item["permitted_use"] == "factual_support"
    assert can_establish_facts(item) is True
    assert content_eligible(item) is True


def test_investigative_feed_requires_corroboration():
    item = {
        "title": "Investigation",
        "url": "https://unlimitedhangout.com/2026/08/example/",
    }
    annotate_item(item, endpoint="https://unlimitedhangout.com/feed/")
    assert item["source_id"] == "unlimited_hangout_site"
    assert item["source_tier"] == "T2"
    assert item["permitted_use"] == "discovery_and_interpretation"
    assert item["corroboration_required"] is True
    assert can_establish_facts(item) is False
    assert content_eligible(item) is False


def test_unknown_source_fails_closed_to_discovery():
    item = {"title": "Random", "url": "https://not-in-registry.example/post"}
    annotate_item(item, endpoint="https://not-in-registry.example/feed")
    assert item["source_id"] == "unmatched"
    assert item["source_tier"] == "T3"
    assert item["permitted_use"] == "discovery_only"
    assert item["automatic_content_eligible"] is False
    assert can_establish_facts(item) is False


def test_t4_aggregator_cannot_establish_facts():
    item = {
        "title": "AI roundup",
        "url": "https://www.marktechpost.com/2026/08/01/example/",
    }
    annotate_item(item, endpoint="https://www.marktechpost.com/feed/")
    assert item["source_tier"] == "T4"
    assert can_establish_facts(item) is False
    assert content_eligible(item) is False
