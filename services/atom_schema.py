"""Atomic decomposition schema and hybrid extraction for OpenSourceNews.

Atoms are the smallest meaningful, reusable units derived from a signal.
They power Hermes' retrieval, scoring, and content generation. Public-domain
extraction only — no private project mapping belongs here.

Atom types
----------
- claim         : A specific assertion the source makes
- data_point    : A number, date, statistic, or measurable fact
- tool          : A named tool, library, framework, or product
- framework     : A named methodology or conceptual framework
- entity        : A person, company, project, or organization
- prediction    : A forward-looking statement about what will happen
- counterexample: Evidence that contradicts a related claim
- reasoning     : The "why" behind a claim (the underlying argument)
- url           : A meaningful URL beyond the canonical source

Atom ID
-------
Stable: uuid5 over (parent_signal_id, atom_type, normalized_text).
Reproducible across runs and machines.

Collection-only / COLLECT_ONLY behavior
---------------------------------------
Deterministic extraction (entities, tools, urls, frameworks) ALWAYS runs.
LLM extraction (claim, prediction, counterexample, reasoning) ONLY runs when
ATOMS_LLM=1 AND an LLM client is available. Fails soft to deterministic-only.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.news_schema import (
    canonicalize_url,
    content_hash_for_item,
    make_signal_id,
    normalize_title,
    utc_now_iso,
)

# Stable namespace for atom IDs. Unique to OpenSourceNews.
_ATOM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews#atom")

# Atom type vocabulary. Strings, not enums (matches existing schema style).
ATOM_TYPES = (
    "claim",
    "data_point",
    "tool",
    "framework",
    "entity",
    "prediction",
    "counterexample",
    "reasoning",
    "url",
)

# Deterministic types run without an LLM (cheap, always-available).
DETERMINISTIC_ATOM_TYPES = {"tool", "framework", "entity", "url"}

# LLM-dependent types need reasoning that regex can't do well.
LLM_ATOM_TYPES = {"claim", "data_point", "prediction", "counterexample", "reasoning"}

# Regex patterns for cheap deterministic extraction.
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
# Match a tool/framework-shaped token: CamelCase, snake_case, or dotted names.
_TOOLISH_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+(?:\.[a-zA-Z][A-Za-z0-9]+)+)\b")
_TOOLISH_VENDOR_RE = re.compile(r"\b([A-Z][A-Za-z0-9]{2,})\b")
# Common version-like patterns for data points (years, percentages, $ amounts).
_DATA_RE = re.compile(
    r"(\$\s?\d[\d,\.]*\s?(?:k|m|b|bn|mn|million|billion|thousand)?\b"
    r"|\d{1,3}(?:,\d{3})+\b"
    r"|\d{1,2}(?:\.\d+)?\s?%"
    r"|\b(?:19|20)\d{2}\b"
    r"|\bv?\d+\.\d+(?:\.\d+)?\b)"
)
# Title-cased multi-word entity hint (crude, but useful as a seed).
_ENTITY_PHRASE_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")


def _atom_text_hash(atom_type: str, text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(f"{atom_type}\n{normalized}".encode("utf-8")).hexdigest()[:16]


def make_atom_id(parent_signal_id: str, atom_type: str, text: str) -> str:
    """Stable atom ID derived from parent signal, type, and normalized text.

    Same input on any machine produces the same ID. Reproduces across reruns.
    """
    return uuid.uuid5(
        _ATOM_NAMESPACE,
        f"{parent_signal_id}|{atom_type}|{_atom_text_hash(atom_type, text)}",
    ).hex[:24]


def _split_text_blob(item: Dict[str, Any]) -> str:
    """Concatenate the text fields most likely to contain atoms."""
    parts: List[str] = [
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("excerpt") or ""),
        str(item.get("neutral_synthesis") or ""),
        str(item.get("implementation_notes") or ""),
        str(item.get("unique_value") or ""),
    ]
    for key in (
        "key_insights",
        "key_lessons",
        "actionable_steps",
        "tools_mentioned",
        "frameworks_mentioned",
        "entities",
        "uncertainty_markers",
    ):
        v = item.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v if str(x).strip())
    claims = item.get("claims") or []
    if isinstance(claims, list):
        for c in claims:
            if isinstance(c, dict):
                parts.append(str(c.get("claim") or ""))
                parts.append(str(c.get("evidence_cited") or ""))
            else:
                parts.append(str(c))
    return "\n".join(p for p in parts if p.strip())


# -- Deterministic extractors (no LLM) ----------------------------------------

def _dedupe_preserving_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for v in values:
        v = v.strip()
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _extract_urls(text: str, source_url: str) -> List[str]:
    found = _URL_RE.findall(text or "")
    cleaned: List[str] = []
    for raw in found:
        # Drop the canonical source URL itself — already represented by signal.
        canon = canonicalize_url(raw)
        if canon and canon == source_url:
            continue
        if canon:
            cleaned.append(canon)
    return _dedupe_preserving_order(cleaned)


def _extract_tools_and_frameworks(item: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Heuristic tool/framework extraction from declared + free-text fields.

    Declared lists (tools_mentioned, frameworks_mentioned) are authoritative.
    Free-text only adds candidates when we see tool-shaped tokens.
    """
    text = _split_text_blob(item)
    declared_tools = [str(x) for x in (item.get("tools_mentioned") or []) if str(x).strip()]
    declared_frameworks = [str(x) for x in (item.get("frameworks_mentioned") or []) if str(x).strip()]

    # Dotted names (npm packages, model identifiers) — high signal for tools.
    dotted = [m.group(1) for m in _TOOLISH_RE.finditer(text)]
    # TitleCase single words — only kept if they appear with a tool-ish neighborhood.
    cap_words = [m.group(1) for m in _TOOLISH_VENDOR_RE.finditer(text)]

    # Heuristic: dotted → tools, TitleCase alone is too noisy for tools.
    tools = _dedupe_preserving_order(declared_tools + dotted)
    frameworks = _dedupe_preserving_order(declared_frameworks)
    return tools, frameworks


def _extract_entities(item: Dict[str, Any]) -> List[str]:
    """Entity extraction. Declared entities win; free-text gives phrase candidates."""
    declared = [str(x) for x in (item.get("entities") or []) if str(x).strip()]
    text = _split_text_blob(item)
    # Crude TitleCase-phrase candidate set; lower-cased to dedupe.
    candidates = []
    seen_lower = {x.lower() for x in declared}
    for m in _ENTITY_PHRASE_RE.finditer(text):
        phrase = m.group(1)
        if len(phrase) < 5:
            continue
        if phrase.lower() in seen_lower:
            continue
        # Drop phrases starting with a stopword-ish first word.
        first = phrase.split()[0].lower()
        if first in {"the", "a", "an", "this", "that", "these", "those", "it"}:
            continue
        candidates.append(phrase)
        seen_lower.add(phrase.lower())
    # Cap the free-text candidates to keep noise bounded.
    return _dedupe_preserving_order(declared + candidates[:15])


def _extract_data_points(item: Dict[str, Any]) -> List[str]:
    text = _split_text_blob(item)
    matches = _DATA_RE.findall(text)
    # Drop very short matches that are usually noise.
    return _dedupe_preserving_order(m for m in matches if len(m.strip()) >= 3)[:25]


# -- LLM extractors (optional, fail-soft) -------------------------------------

def _llm_extract_atoms(
    item: Dict[str, Any],
    llm_client: Any,
    parent_signal_id: str,
    source_url: str,
) -> List[Dict[str, Any]]:
    """Use the LLM to extract claim / prediction / counterexample / reasoning atoms.

    Prompt asks for strict JSON. Output is a list of atom dicts; each gets a
    stable atom_id at the end. Fails soft — returns [] on any error.
    """
    if not llm_client:
        return []
    text = _split_text_blob(item)
    if not text.strip():
        return []

    # Truncate so the prompt fits small local models.
    text_for_prompt = text[:6000]
    title = (item.get("title") or "").strip()
    source = (item.get("source") or "").strip()

    prompt = f"""Extract atomic claims from this news item. Return ONLY valid JSON.

Title: {title}
Source: {source}

Text:
{text_for_prompt}

Return a JSON array of objects. Each object must have:
- "atom_type": one of "claim", "data_point", "prediction", "counterexample", "reasoning"
- "text": the atomic statement (one sentence, no preamble)
- "evidence_urls": array of supporting URLs (may be empty)
- "polarity": "supports" | "neutral" | "contradicts" (relative to the dominant claim of the source)

Rules:
- Maximum 8 atoms per item.
- Each atom must stand alone — no pronouns referring to the source.
- Be specific. Numbers, names, and dates preserved verbatim.
- If the source is opinion/commentary, mark claims as "polarity": "neutral".
- If the text contains a clear forecast, capture it as a "prediction".
- If the text refutes a prior claim, capture it as a "counterexample".
- Capture the underlying "why" of a claim as "reasoning" — the mechanism, not the claim.
- Do NOT include the source URL itself in evidence_urls.
"""

    raw_text: Optional[str] = None
    try:
        raw_text = llm_client.generate(prompt, json_mode=True)
    except Exception:
        return []

    # Parse. Tolerate code fences and trailing commas.
    from pipelines.llm_provider import parse_json_text  # local import — keep module optional
    parsed = parse_json_text(raw_text or "")
    if not isinstance(parsed, list):
        return []

    atoms: List[Dict[str, Any]] = []
    for entry in parsed[:8]:
        if not isinstance(entry, dict):
            continue
        atom_type = str(entry.get("atom_type") or "").strip().lower()
        text_v = str(entry.get("text") or "").strip()
        if atom_type not in LLM_ATOM_TYPES or not text_v:
            continue
        polarity = str(entry.get("polarity") or "neutral").strip().lower()
        if polarity not in {"supports", "neutral", "contradicts"}:
            polarity = "neutral"
        evidence = entry.get("evidence_urls") or []
        if not isinstance(evidence, list):
            evidence = []
        evidence = [canonicalize_url(str(u)) for u in evidence if str(u).strip()]
        evidence = [u for u in evidence if u and u != source_url]
        atoms.append(
            {
                "atom_id": make_atom_id(parent_signal_id, atom_type, text_v),
                "atom_type": atom_type,
                "text": text_v,
                "polarity": polarity,
                "evidence_urls": evidence[:5],
                "extracted_by": "llm",
                "extracted_at": utc_now_iso(),
            }
        )
    return atoms


def text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def build_atom(
    *,
    parent_signal_id: str,
    atom_type: str,
    text: str,
    evidence_urls: Optional[List[str]] = None,
    extracted_at: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body = (text or "").strip()
    if not body:
        raise ValueError("atom text required")
    if atom_type not in ATOM_TYPES:
        raise ValueError(f"invalid atom_type: {atom_type}")
    atom: Dict[str, Any] = {
        "atom_id": make_atom_id(parent_signal_id, atom_type, body),
        "parent_signal_id": parent_signal_id,
        "atom_type": atom_type,
        "text": body[:2000],
        "evidence_urls": list(evidence_urls or []),
        "extracted_at": extracted_at or utc_now_iso(),
        "schema_version": "atom.v1",
        "extracted_by": "deterministic",
        "polarity": "neutral",
    }
    if extra:
        atom.update(extra)
    return atom


def extract_atoms_deterministic(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic atom extraction. Cheap, always-available, no LLM."""
    # Make sure the item has an id we can reference.
    if not item.get("signal_id"):
        item = {**item, "signal_id": make_signal_id(item)}
    parent_signal_id = item["signal_id"]
    source_url = item.get("canonical_url") or canonicalize_url(str(item.get("url") or ""))
    text = _split_text_blob(item)

    atoms: List[Dict[str, Any]] = []

    # Tools
    for tool, _ in zip(*_extract_tools_and_frameworks(item)):
        atoms.append(
            {
                "atom_id": make_atom_id(parent_signal_id, "tool", tool),
                "atom_type": "tool",
                "text": tool,
                "polarity": "neutral",
                "evidence_urls": [],
                "extracted_by": "deterministic",
                "extracted_at": utc_now_iso(),
            }
        )

    # Frameworks
    _, frameworks = _extract_tools_and_frameworks(item)
    for fw in frameworks:
        atoms.append(
            {
                "atom_id": make_atom_id(parent_signal_id, "framework", fw),
                "atom_type": "framework",
                "text": fw,
                "polarity": "neutral",
                "evidence_urls": [],
                "extracted_by": "deterministic",
                "extracted_at": utc_now_iso(),
            }
        )

    # Entities
    for entity in _extract_entities(item):
        atoms.append(
            {
                "atom_id": make_atom_id(parent_signal_id, "entity", entity),
                "atom_type": "entity",
                "text": entity,
                "polarity": "neutral",
                "evidence_urls": [],
                "extracted_by": "deterministic",
                "extracted_at": utc_now_iso(),
            }
        )

    # URLs
    for url in _extract_urls(text, source_url):
        atoms.append(
            {
                "atom_id": make_atom_id(parent_signal_id, "url", url),
                "atom_type": "url",
                "text": url,
                "polarity": "neutral",
                "evidence_urls": [],
                "extracted_by": "deterministic",
                "extracted_at": utc_now_iso(),
            }
        )

    # Data points (deterministic regex — no LLM needed for the obvious ones)
    for dp in _extract_data_points(item):
        atoms.append(
            {
                "atom_id": make_atom_id(parent_signal_id, "data_point", dp),
                "atom_type": "data_point",
                "text": dp,
                "polarity": "neutral",
                "evidence_urls": [],
                "extracted_by": "deterministic",
                "extracted_at": utc_now_iso(),
            }
        )

    return atoms


def extract_atoms(
    item: Dict[str, Any],
    llm_client: Any = None,
    *,
    allow_llm: bool = True,
) -> List[Dict[str, Any]]:
    """Hybrid atom extraction. Deterministic always runs; LLM only if allowed.

    Parameters
    ----------
    item : dict
        A normalized signal item.
    llm_client : optional
        An LLM client with a `.generate(prompt, json_mode=True)` method.
        If None, only deterministic extraction runs.
    allow_llm : bool
        Master switch. Set False to force deterministic-only.

    Returns
    -------
    list of atom dicts (deterministic order; stable IDs).
    """
    atoms = extract_atoms_deterministic(item)
    if not allow_llm or llm_client is None:
        return atoms

    # Dedupe against the deterministic pass by (atom_type, text lower).
    seen: set[Tuple[str, str]] = {(a["atom_type"], a["text"].lower()) for a in atoms}

    parent_signal_id = item.get("signal_id") or make_signal_id(item)
    source_url = item.get("canonical_url") or canonicalize_url(str(item.get("url") or ""))
    llm_atoms = _llm_extract_atoms(item, llm_client, parent_signal_id, source_url)
    for a in llm_atoms:
        key = (a["atom_type"], a["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        atoms.append(a)

    return atoms


def atom_to_record(
    atom: Dict[str, Any],
    parent_signal_id: str,
    parent_canonical_url: str,
    parent_source_domain: str,
    parent_bucket: str,
    parent_topics: List[str],
    public_topics: List[str],
    report_date: str,
) -> Dict[str, Any]:
    """Wrap an atom in a stable envelope for downstream JSONL / Qdrant use.

    The envelope carries everything Hermes needs to consume an atom without
    re-fetching the parent signal.
    """
    return {
        "atom_id": atom["atom_id"],
        "atom_type": atom["atom_type"],
        "text": atom["text"],
        "polarity": atom.get("polarity", "neutral"),
        "evidence_urls": atom.get("evidence_urls", []),
        "extracted_by": atom.get("extracted_by", "deterministic"),
        "extracted_at": atom.get("extracted_at", utc_now_iso()),
        "parent_signal_id": parent_signal_id,
        "parent_canonical_url": parent_canonical_url,
        "parent_source_domain": parent_source_domain,
        "parent_bucket": parent_bucket,
        "parent_topics": list(parent_topics or []),
        "public_topics": list(public_topics or []),
        "report_date": report_date,
        "schema_version": "atom.v1",
    }


# Back-compat aliases for earlier leverage-pipeline callers / tests.
extract_deterministic_atoms = extract_atoms_deterministic
