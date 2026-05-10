#!/usr/bin/env python3
"""Generate deterministic mission briefs from daily reports and watchlists."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.news_schema import item_search_text, normalize_item, slugify_name


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
BRIEFS_DIR = ROOT_DIR / "outputs" / "briefs"
WATCHLISTS_PATH = ROOT_DIR / "config" / "watchlists.yaml"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_watchlists(path: Path = WATCHLISTS_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    watchlists = data.get("watchlists") or []
    return [w for w in watchlists if isinstance(w, dict) and w.get("name")]


def latest_report_path() -> Path | None:
    reports = sorted(DAILY_DIR.glob("*.json"), reverse=True)
    return reports[0] if reports else None


def report_path_for_date(date_str: str | None) -> Path | None:
    if date_str:
        candidate = DAILY_DIR / f"{date_str}.json"
        return candidate if candidate.exists() else None
    return latest_report_path()


def watchlist_terms(watchlist: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for key in ("entities", "topics"):
        values = watchlist.get(key) or []
        if isinstance(values, list):
            terms.extend(str(value).strip().lower() for value in values if str(value).strip())
    return sorted(set(terms), key=len, reverse=True)


def watchlist_exclude_terms(watchlist: Dict[str, Any]) -> List[str]:
    values = watchlist.get("exclude_terms") or []
    if not isinstance(values, list):
        return []
    return sorted(
        {str(value).strip().lower() for value in values if str(value).strip()},
        key=len,
        reverse=True,
    )


def _term_variants(term: str) -> List[str]:
    variants = {term, term.replace("_", " "), term.replace("-", " ")}
    if term.endswith("s") and len(term) > 3:
        variants.add(term[:-1])
    return [variant for variant in variants if variant]


def _contains_term(haystack: str, term: str) -> bool:
    if len(term) <= 3 and re.fullmatch(r"[a-z0-9+]+", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) is not None
    return term in haystack


def find_matches(
    report_data: Dict[str, Any],
    watchlist: Dict[str, Any],
    limit: int,
) -> List[Dict[str, Any]]:
    terms = watchlist_terms(watchlist)
    exclude_terms = watchlist_exclude_terms(watchlist)
    matches: List[Dict[str, Any]] = []

    for topic_name, topic_items in report_data.items():
        if not isinstance(topic_items, list):
            continue
        for item in topic_items:
            if not isinstance(item, dict):
                continue
            item_for_match = {**item, "bucket": ""}
            haystack = item_search_text("", item_for_match)
            if exclude_terms and any(
                _contains_term(haystack, variant)
                for term in exclude_terms
                for variant in _term_variants(term)
            ):
                continue
            matched_terms = [
                term
                for term in terms
                if any(_contains_term(haystack, variant) for variant in _term_variants(term))
            ]
            if not matched_terms:
                continue

            normalized = normalize_item(topic_name, item)
            quality = normalized.get("quality_score")
            confidence = normalized.get("classification_confidence")
            score = len(matched_terms) * 10
            if isinstance(quality, (int, float)):
                score += float(quality)
            if isinstance(confidence, (int, float)):
                score += float(confidence)
            normalized["matched_terms"] = matched_terms
            normalized["match_score"] = score
            matches.append(normalized)

    matches.sort(
        key=lambda item: (
            item.get("match_score") or 0,
            item.get("quality_score") or 0,
            item.get("classification_confidence") or 0,
        ),
        reverse=True,
    )
    return matches[:limit]


def compact_title(item: Dict[str, Any]) -> str:
    title = item.get("title") or "Untitled signal"
    source = item.get("source") or "Unknown"
    return f"{title} ({source})"


def source_links(items: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    seen = set()
    for item in items:
        for url in item.get("source_urls") or []:
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({"title": item.get("title") or url, "url": url})
    return links


def build_sections(watchlist: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    persona = watchlist.get("persona") or "operator"
    if not items:
        return {
            "what_changed": ["No matching signals were found in this report."],
            "why_it_matters": [f"No immediate action is required for the {persona} watchlist."],
            "who_should_care": [persona],
            "recommended_actions": ["Review the watchlist terms if this brief stays empty for several days."],
            "build_ideas": [],
            "content_ideas": [],
            "investment_partnership_angles": [],
        }

    top = items[:5]
    what_changed = [compact_title(item) for item in top]
    why_it_matters = [
        f"{item.get('title')} maps to {', '.join(item.get('matched_terms') or [])}."
        for item in top[:3]
    ]
    recommended_actions = [
        f"Review {item.get('source') or 'the source'} signal: {item.get('title')}"
        for item in top[:3]
    ]
    build_ideas = [
        f"Prototype an internal brief or automation around: {top[0].get('title')}"
    ]
    content_ideas = [
        f"Publish a short explainer on: {item.get('title')}"
        for item in top[:2]
    ]
    investment_angles = [
        f"Track the cluster `{item.get('cluster_id')}` for repeat mentions over the next week."
        for item in top[:2]
    ]

    return {
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "who_should_care": [persona],
        "recommended_actions": recommended_actions,
        "build_ideas": build_ideas,
        "content_ideas": content_ideas,
        "investment_partnership_angles": investment_angles,
    }


def build_brief(
    report_date: str,
    report_data: Dict[str, Any],
    watchlist: Dict[str, Any],
    limit: int,
) -> Dict[str, Any]:
    items = find_matches(report_data, watchlist, limit=limit)
    sections = build_sections(watchlist, items)
    return {
        "schema": "open_source_news_mission_brief.v1",
        "generated_at": utc_now_iso(),
        "report_date": report_date,
        "watchlist": {
            "name": watchlist.get("name"),
            "persona": watchlist.get("persona"),
            "entities": watchlist.get("entities") or [],
            "topics": watchlist.get("topics") or [],
            "alert_rules": watchlist.get("alert_rules") or [],
        },
        "counts": {
            "matched_items": len(items),
            "source_links": len(source_links(items)),
        },
        "sections": sections,
        "items": items,
        "source_links": source_links(items),
    }


def section_lines(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}", ""]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("_No items._")
    lines.append("")
    return lines


def brief_to_markdown(brief: Dict[str, Any]) -> str:
    watchlist = brief["watchlist"]
    title_name = str(watchlist.get("name") or "mission").replace("_", " ").title()
    sections = brief["sections"]
    lines = [
        f"# Mission Brief - {title_name} - {brief['report_date']}",
        "",
        f"- Persona: {watchlist.get('persona') or 'n/a'}",
        f"- Matched items: {brief['counts']['matched_items']}",
        "",
    ]
    lines.extend(section_lines("What changed?", sections["what_changed"]))
    lines.extend(section_lines("Why it matters", sections["why_it_matters"]))
    lines.extend(section_lines("Who should care?", sections["who_should_care"]))
    lines.extend(section_lines("What action should Brian take?", sections["recommended_actions"]))
    lines.extend(section_lines("Build idea", sections["build_ideas"]))
    lines.extend(section_lines("Content idea", sections["content_ideas"]))
    lines.extend(
        section_lines(
            "Investment / partnership angle",
            sections["investment_partnership_angles"],
        )
    )
    lines.append("## Source links")
    lines.append("")
    if brief["source_links"]:
        for link in brief["source_links"]:
            lines.append(f"- [{link['title']}]({link['url']})")
    else:
        lines.append("_No links._")
    lines.append("")
    return "\n".join(lines)


def write_brief(brief: Dict[str, Any]) -> Tuple[Path, Path]:
    name = slugify_name(brief["watchlist"]["name"])
    out_dir = BRIEFS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = brief["report_date"]
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(brief_to_markdown(brief), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mission briefs from daily reports.")
    parser.add_argument("--date", help="Report date to brief, YYYY-MM-DD. Defaults to latest.")
    parser.add_argument("--watchlist", help="Only generate one watchlist by name.")
    parser.add_argument("--limit", type=int, default=12, help="Max matched items per brief.")
    args = parser.parse_args()

    report_path = report_path_for_date(args.date)
    if not report_path:
        raise SystemExit("No daily report found for mission brief generation.")

    report_date = report_path.stem
    report_data = load_json(report_path)
    watchlists = load_watchlists()
    if args.watchlist:
        wanted = slugify_name(args.watchlist)
        watchlists = [w for w in watchlists if slugify_name(w.get("name", "")) == wanted]
    if not watchlists:
        raise SystemExit("No matching watchlists found.")

    for watchlist in watchlists:
        brief = build_brief(report_date, report_data, watchlist, limit=max(1, args.limit))
        json_path, md_path = write_brief(brief)
        print(
            f"Mission brief written: {json_path.relative_to(ROOT_DIR)} "
            f"({brief['counts']['matched_items']} matches)"
        )
        print(f"Markdown brief written: {md_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
