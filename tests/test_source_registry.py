"""Typed source registry validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.source_registry import (
    SourceRegistryError,
    enabled_sources,
    load_policy,
    load_sources,
    lookup_by_endpoint,
    registry_hash,
    validate_source,
)


def test_registry_loads_and_ids_are_unique():
    sources = load_sources()
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    assert len(sources) >= 50
    enabled = enabled_sources(sources)
    assert enabled
    assert all(s["enabled"] is True for s in enabled)


def test_registry_hash_is_stable():
    sources = load_sources()
    assert registry_hash(sources) == registry_hash(sources)
    assert registry_hash(sources).startswith("sha256:")


def test_unlimited_hangout_and_wave_a_are_enabled():
    by_id = {s["id"]: s for s in load_sources()}
    assert by_id["unlimited_hangout_site"]["enabled"] is True
    assert by_id["unlimited_hangout_site"]["tier"] == "T2"
    assert by_id["federal_reserve_press"]["enabled"] is True
    assert by_id["federal_reserve_press"]["tier"] == "T0"
    assert by_id["david_icke_manual_watch"]["enabled"] is False
    assert by_id["david_icke_manual_watch"]["tier"] == "T5"
    assert by_id["ddosecrets_catalog"]["enabled"] is False
    assert by_id["national_security_archive"]["enabled"] is False


def test_lookup_by_feed_endpoint():
    found = lookup_by_endpoint("https://unlimitedhangout.com/feed/")
    assert found is not None
    assert found["id"] == "unlimited_hangout_site"


def test_disabled_site_change_cannot_be_enabled_without_adapter(tmp_path):
    policy = load_policy()
    source = {
        "schema": "source_definition.v1",
        "id": "example_archive",
        "name": "Example",
        "publisher": "Example",
        "homepage": "https://example.com/",
        "adapter": "site_change",
        "endpoints": ["https://example.com/"],
        "tier": "T1",
        "source_kind": "document_archive",
        "permitted_use": "documentary_lead",
        "corroboration_required": False,
        "license_or_terms_url": "https://example.com/terms",
        "robots_policy": "obey",
        "rate_limit": {"requests_per_second": 0.2},
        "enabled": True,
        "owner": "intelligence",
        "reviewed_at": "2026-08-15",
    }
    errors = validate_source(source, policy)
    assert any("not wired for collection" in err for err in errors)


def test_t4_cannot_use_factual_support():
    policy = load_policy()
    source = {
        "schema": "source_definition.v1",
        "id": "promo_feed",
        "name": "Promo",
        "publisher": "Promo",
        "homepage": "https://example.com/",
        "adapter": "rss",
        "endpoints": ["https://example.com/feed/"],
        "tier": "T4",
        "source_kind": "promotional",
        "permitted_use": "factual_support",
        "corroboration_required": True,
        "rate_limit": {"requests_per_second": 0.2},
        "enabled": True,
        "owner": "intelligence",
        "reviewed_at": "2026-08-15",
    }
    errors = validate_source(source, policy)
    assert any("not allowed for T4" in err for err in errors)


def test_t5_cannot_be_enabled():
    policy = load_policy()
    source = {
        "schema": "source_definition.v1",
        "id": "quarantine_feed",
        "name": "Quarantine",
        "publisher": "Quarantine",
        "homepage": "https://example.com/",
        "adapter": "rss",
        "endpoints": ["https://example.com/feed/"],
        "tier": "T5",
        "source_kind": "commentary",
        "permitted_use": "quarantined_discovery",
        "corroboration_required": True,
        "automatic_content_eligible": False,
        "automatic_evidence_promotion": False,
        "rate_limit": {"requests_per_second": 0.1},
        "enabled": True,
        "owner": "intelligence",
        "reviewed_at": "2026-08-15",
    }
    errors = validate_source(source, policy)
    assert any("T5 sources must remain disabled" in err for err in errors)


def test_http_credentials_rejected():
    policy = load_policy()
    source = {
        "schema": "source_definition.v1",
        "id": "bad_secret_url",
        "name": "Bad",
        "publisher": "Bad",
        "homepage": "https://example.com/",
        "adapter": "rss",
        "endpoints": ["https://example.com/feed?api_key=secret"],
        "tier": "T3",
        "source_kind": "newsroom",
        "permitted_use": "discovery_only",
        "corroboration_required": True,
        "rate_limit": {"requests_per_second": 0.2},
        "enabled": True,
        "owner": "intelligence",
        "reviewed_at": "2026-08-15",
    }
    errors = validate_source(source, policy)
    assert any("secret query key" in err for err in errors)


def test_empty_registry_file_raises(tmp_path):
    bogus = tmp_path / "empty.yaml"
    bogus.write_text("not_sources: true\n", encoding="utf-8")
    with pytest.raises(SourceRegistryError):
        load_sources(tmp_path)
