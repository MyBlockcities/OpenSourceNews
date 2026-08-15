"""Load and validate the typed OpenSourceNews source registry.

The YAML files under ``config/sources/`` are authoritative. ``config/feeds.yaml``
is a compatibility export consumed by ``pipelines/daily_run.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT_DIR / "config" / "sources"
POLICY_PATH = ROOT_DIR / "config" / "source_policy.yaml"
SCHEMA_PATH = ROOT_DIR / "schemas" / "source_definition.v1.json"

ADAPTERS = frozenset(
    {
        "rss",
        "youtube",
        "github",
        "github_trending",
        "hackernews",
        "pubmed",
        "clinical_trials",
        "json_api",
        "site_change",
        "document_index",
        "foia_archive",
        "sec_edgar",
        "federal_register",
        "fred",
        "gdelt",
        "geoevent",
        "ocds",
        "x",
        "twitch",
        "manual_link_watch",
    }
)
IMPLEMENTED_COLLECTORS = frozenset(
    {
        "rss",
        "youtube",
        "github_trending",
        "hackernews",
        "pubmed",
        "clinical_trials",
        "x",  # no-op placeholder; kept so existing feeds.yaml does not fail validation
    }
)
QUERY_ADAPTERS = frozenset(
    {
        "youtube",
        "github_trending",
        "hackernews",
        "pubmed",
        "clinical_trials",
        "x",
        "twitch",
        "manual_link_watch",
    }
)
SCRAPER_ADAPTERS = frozenset({"site_change", "document_index", "foia_archive"})
TIERS = ("T0", "T1", "T2", "T3", "T4", "T5")
PERMITTED_USES = frozenset(
    {
        "factual_support",
        "documentary_lead",
        "discovery_and_interpretation",
        "discovery_only",
        "metadata_discovery_only",
        "quarantined_discovery",
    }
)
SECRET_QUERY_KEYS = frozenset(
    {"api_key", "apikey", "token", "access_token", "password", "secret", "key"}
)
_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,80}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SourceRegistryError(ValueError):
    """Raised when the source registry fails validation."""


def _read_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_policy(path: Path = POLICY_PATH) -> Dict[str, Any]:
    data = _read_yaml(path)
    if not isinstance(data, dict) or data.get("schema") != "source_policy.v1":
        raise SourceRegistryError(f"Invalid source policy at {path}")
    return data


def iter_source_files(sources_dir: Path = SOURCES_DIR) -> List[Path]:
    if not sources_dir.exists():
        return []
    return sorted(p for p in sources_dir.glob("*.yaml") if not p.name.startswith("."))


def _as_sources(payload: Any, path: Path) -> List[Dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("sources"), list):
        return [item for item in payload["sources"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise SourceRegistryError(f"{path} must contain a top-level sources list")


def _endpoint_is_url(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    return bool(parsed.scheme and parsed.netloc)


def _credential_issues(endpoint: str) -> List[str]:
    issues: List[str] = []
    parsed = urlparse(endpoint)
    if parsed.username or parsed.password:
        issues.append("contains userinfo credentials")
    query = (parsed.query or "").lower()
    for key in SECRET_QUERY_KEYS:
        if re.search(rf"(?:^|&){re.escape(key)}=", query):
            issues.append(f"contains secret query key {key}")
    return issues


def validate_source(source: Dict[str, Any], policy: Dict[str, Any]) -> List[str]:
    """Return human-readable validation errors for one source definition."""
    errors: List[str] = []
    source_id = str(source.get("id") or "")
    prefix = source_id or "<missing-id>"

    if source.get("schema") != "source_definition.v1":
        errors.append(f"{prefix}: schema must be source_definition.v1")
    if not _ID_RE.match(source_id):
        errors.append(f"{prefix}: id must be snake_case [a-z][a-z0-9_]{{1,80}}")
    for field in ("name", "publisher", "homepage", "source_kind", "owner"):
        if not str(source.get(field) or "").strip():
            errors.append(f"{prefix}: missing {field}")
    if not _DATE_RE.match(str(source.get("reviewed_at") or "")):
        errors.append(f"{prefix}: reviewed_at must be YYYY-MM-DD")

    adapter = str(source.get("adapter") or "")
    if adapter not in ADAPTERS:
        errors.append(f"{prefix}: unknown adapter {adapter!r}")

    endpoints = source.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        errors.append(f"{prefix}: endpoints must be a non-empty list")
        endpoints = []
    allow_http = bool(source.get("allow_http"))
    for endpoint in endpoints:
        if not isinstance(endpoint, str) or not endpoint.strip():
            errors.append(f"{prefix}: empty endpoint")
            continue
        if _endpoint_is_url(endpoint):
            scheme = urlparse(endpoint).scheme.lower()
            if scheme != "https" and not (allow_http and scheme == "http"):
                errors.append(f"{prefix}: non-HTTPS endpoint {endpoint}")
            for issue in _credential_issues(endpoint):
                errors.append(f"{prefix}: {issue} in {endpoint}")
        elif adapter not in QUERY_ADAPTERS:
            errors.append(f"{prefix}: non-URL endpoint requires a query adapter: {endpoint}")

    tier = str(source.get("tier") or "")
    if tier not in TIERS:
        errors.append(f"{prefix}: invalid tier {tier!r}")
    permitted_use = str(source.get("permitted_use") or "")
    if permitted_use not in PERMITTED_USES:
        errors.append(f"{prefix}: invalid permitted_use {permitted_use!r}")
    allowed = (policy.get("allowed_permitted_use_by_tier") or {}).get(tier) or []
    if tier in TIERS and permitted_use in PERMITTED_USES and permitted_use not in allowed:
        errors.append(f"{prefix}: {permitted_use} is not allowed for {tier}")

    if "corroboration_required" not in source:
        errors.append(f"{prefix}: corroboration_required is required")
    rate = source.get("rate_limit")
    if not isinstance(rate, dict) or not isinstance(rate.get("requests_per_second"), (int, float)):
        errors.append(f"{prefix}: rate_limit.requests_per_second is required")
    elif float(rate["requests_per_second"]) <= 0:
        errors.append(f"{prefix}: rate_limit.requests_per_second must be > 0")

    enabled = source.get("enabled")
    if not isinstance(enabled, bool):
        errors.append(f"{prefix}: enabled must be a boolean")
    elif enabled is False and not str(source.get("disabled_reason") or "").strip():
        errors.append(f"{prefix}: disabled source requires disabled_reason")

    if enabled is True and adapter not in IMPLEMENTED_COLLECTORS:
        errors.append(
            f"{prefix}: adapter {adapter} is not wired for collection; keep enabled=false"
        )
    if enabled is True and adapter == "x":
        errors.append(f"{prefix}: X collection is not automated; use enabled=false")

    if adapter in SCRAPER_ADAPTERS:
        if not source.get("license_or_terms_url"):
            errors.append(f"{prefix}: scraper adapters require license_or_terms_url")
        if source.get("robots_policy") not in {"obey", "none", "unknown"}:
            errors.append(f"{prefix}: scraper adapters require robots_policy")

    if tier == "T5":
        if source.get("automatic_content_eligible") is True:
            errors.append(f"{prefix}: T5 cannot be automatic_content_eligible")
        if source.get("automatic_evidence_promotion") is True:
            errors.append(f"{prefix}: T5 cannot auto-promote evidence")
        if enabled is True:
            errors.append(f"{prefix}: T5 sources must remain disabled until explicit activation")

    homepage = str(source.get("homepage") or "")
    if _endpoint_is_url(homepage) and urlparse(homepage).scheme.lower() != "https":
        errors.append(f"{prefix}: homepage must be HTTPS")

    return errors


def load_sources(
    sources_dir: Path = SOURCES_DIR,
    *,
    policy: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    policy = policy or load_policy()
    sources: List[Dict[str, Any]] = []
    errors: List[str] = []
    seen: Dict[str, str] = {}
    for path in iter_source_files(sources_dir):
        payload = _read_yaml(path)
        for source in _as_sources(payload, path):
            source = dict(source)
            source["_registry_file"] = str(path.relative_to(ROOT_DIR)) if path.is_relative_to(ROOT_DIR) else str(path)
            source_id = str(source.get("id") or "")
            if source_id in seen:
                errors.append(f"{source_id}: duplicate id in {path.name} and {seen[source_id]}")
            else:
                seen[source_id] = path.name
            errors.extend(validate_source(source, policy))
            sources.append(source)
    if errors:
        raise SourceRegistryError("Source registry validation failed:\n- " + "\n- ".join(errors))
    return sources


def registry_hash(sources: Iterable[Dict[str, Any]]) -> str:
    """Deterministic hash of public source definitions (ignores loader metadata)."""
    payload = []
    for source in sources:
        clean = {k: v for k, v in source.items() if not str(k).startswith("_")}
        payload.append(clean)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def config_hash(paths: Optional[Iterable[Path]] = None) -> str:
    files = list(paths) if paths is not None else [
        ROOT_DIR / "config" / "feeds.yaml",
        ROOT_DIR / "config" / "source_policy.yaml",
        ROOT_DIR / "config" / "channels_catalog.yaml",
        ROOT_DIR / "config" / "watchlists.yaml",
        *iter_source_files(),
    ]
    h = hashlib.sha256()
    for path in sorted(files, key=lambda p: str(p)):
        if not path.exists():
            continue
        h.update(str(path.relative_to(ROOT_DIR) if path.is_relative_to(ROOT_DIR) else path).encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\n")
    return "sha256:" + h.hexdigest()


def enabled_sources(sources: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    sources = sources if sources is not None else load_sources()
    return [s for s in sources if s.get("enabled") is True]


def index_by_id(sources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    sources = sources if sources is not None else load_sources()
    return {str(s["id"]): s for s in sources}


def index_by_endpoint(sources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    sources = sources if sources is not None else load_sources()
    out: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        for endpoint in source.get("endpoints") or []:
            key = str(endpoint).strip()
            if key:
                out[key] = source
                out[key.rstrip("/")] = source
    return out


def lookup_by_endpoint(
    endpoint: str,
    *,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    table = index_by_endpoint(sources)
    raw = (endpoint or "").strip()
    return table.get(raw) or table.get(raw.rstrip("/"))


def lookup_by_item_url(
    url: str,
    *,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Best-effort publisher match when the originating feed endpoint is unknown."""
    parsed = urlparse(url or "")
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if not host:
        return None
    sources = sources if sources is not None else load_sources()
    ranked: List[Tuple[int, Dict[str, Any]]] = []
    for source in sources:
        candidates = [str(source.get("homepage") or "")] + list(source.get("endpoints") or [])
        for candidate in candidates:
            cand = urlparse(candidate)
            cand_host = (cand.netloc or "").lower().removeprefix("www.")
            if cand_host and cand_host == host:
                path_score = len(cand.path.rstrip("/"))
                ranked.append((path_score, source))
    if not ranked:
        return None
    ranked.sort(key=lambda row: row[0], reverse=True)
    return ranked[0][1]
