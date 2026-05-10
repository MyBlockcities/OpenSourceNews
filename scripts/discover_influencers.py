#!/usr/bin/env python3
"""Discover daily micro-influencer candidates for OpenSourceNews topics.

The pipeline is designed for scheduled GitHub Actions runs with free data
sources. YouTube Data API is used when a free quota key is available; RSS author
signals are used as a zero-cost fallback and supplement. X/Twitter is never
queried directly; handles are only extracted from public descriptions/content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "influencers"
FEEDS_CONFIG_PATH = ROOT_DIR / "config" / "feeds.yaml"

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

HTTP_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": "OpenSourceNews influencer discovery (+https://github.com/MyBlockcities/OpenSourceNews)"
}

SCHEMA_VERSION = "opensourcenews.influencers.v1"
DEFAULT_MIN_SUBSCRIBERS = int(os.getenv("INFLUENCER_MIN_SUBSCRIBERS", "2000"))
DEFAULT_MAX_SUBSCRIBERS = int(os.getenv("INFLUENCER_MAX_SUBSCRIBERS", "100000"))
DEFAULT_MAX_PER_TOPIC = int(os.getenv("INFLUENCERS_PER_TOPIC", "20"))
DEFAULT_SEARCH_DAYS = int(os.getenv("INFLUENCER_SEARCH_DAYS", "7"))
DEFAULT_YOUTUBE_MAX_RESULTS = int(os.getenv("INFLUENCER_YOUTUBE_MAX_RESULTS", "25"))
DEFAULT_RSS_LIMIT_PER_FEED = int(os.getenv("INFLUENCER_RSS_LIMIT_PER_FEED", "20"))


TOPICS: Dict[str, Dict[str, Any]] = {
    "real_estate_tokenization": {
        "label": "Real Estate Tokenization",
        "feed_topic_terms": ["blockchain", "crypto", "web3"],
        "youtube_queries": [
            "real estate tokenization",
            "tokenized real estate",
            "real estate RWA",
            "property tokenization",
        ],
    },
    "alternative_news": {
        "label": "Alternative News",
        "feed_topic_terms": ["alternative news", "independent commentary"],
        "youtube_queries": [
            "independent news",
            "alternative media",
            "independent journalism",
            "censorship news",
        ],
    },
    "blockchain_crypto": {
        "label": "Blockchain and Crypto",
        "feed_topic_terms": ["blockchain", "crypto", "web3"],
        "youtube_queries": [
            "real world assets crypto",
            "RWA tokenization",
            "onchain analysis",
            "crypto regulation",
        ],
    },
    "peptides": {
        "label": "Peptides",
        "feed_topic_terms": ["peptides", "wellness", "longevity"],
        "youtube_queries": [
            "peptide therapy",
            "BPC-157",
            "TB-500 peptide",
            "GLP-1 peptides",
            "semaglutide alternatives",
        ],
        "sensitive_topic": True,
    },
    "fitness_wellness": {
        "label": "Fitness and Wellness",
        "feed_topic_terms": ["peptides", "wellness", "longevity", "sense-making"],
        "youtube_queries": [
            "functional fitness",
            "longevity protocol",
            "biohacking routine",
            "wellness peptides",
        ],
    },
}


SOCIAL_LINK_PATTERNS = {
    "x": re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/[A-Za-z0-9_]{1,15}", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|channel/)[A-Za-z0-9_.@-]+", re.I),
}


@dataclass(frozen=True)
class YoutubeConfig:
    api_key: str
    min_subscribers: int
    max_subscribers: int
    search_days: int
    max_results: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def iso_today() -> str:
    return utc_now().date().isoformat()


def load_environment() -> None:
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(ROOT_DIR / ".env.local")


def stable_id(parts: Iterable[str]) -> str:
    joined = "|".join(part.strip().lower() for part in parts if part)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    parsed = safe_int(value)
    return parsed if parsed is not None else default


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def domain_for(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host.removeprefix("www.")


def clean_url(value: str) -> str:
    return value.strip().rstrip(".,);]}>\"'")


def extract_social_links(text: str) -> Dict[str, str]:
    links: Dict[str, str] = {}
    if not text:
        return links
    for platform, pattern in SOCIAL_LINK_PATTERNS.items():
        match = pattern.search(text)
        if match:
            links[platform] = clean_url(match.group(0))
    return links


def request_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def youtube_published_after(days: int) -> str:
    dt = utc_now() - timedelta(days=max(1, days))
    return dt.isoformat().replace("+00:00", "Z")


def youtube_search(topic_key: str, queries: Sequence[str], config: YoutubeConfig) -> Dict[str, Dict[str, Any]]:
    """Return channel samples keyed by YouTube channel ID."""
    channel_samples: Dict[str, Dict[str, Any]] = {}
    published_after = youtube_published_after(config.search_days)

    for query in queries:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "publishedAfter": published_after,
            "maxResults": max(1, min(config.max_results, 50)),
            "key": config.api_key,
        }
        data = request_json(YOUTUBE_SEARCH_URL, params)
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet") or {}
            channel_id = snippet.get("channelId")
            if not channel_id:
                continue
            video_id = (item.get("id") or {}).get("videoId")
            sample = {
                "query": query,
                "video_id": video_id,
                "title": snippet.get("title") or "",
                "description": snippet.get("description") or "",
                "published_at": snippet.get("publishedAt") or "",
                "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            }
            entry = channel_samples.setdefault(
                channel_id,
                {
                    "topic_key": topic_key,
                    "matched_queries": set(),
                    "videos": [],
                    "description_text": "",
                },
            )
            entry["matched_queries"].add(query)
            entry["videos"].append(sample)
            entry["description_text"] = f"{entry.get('description_text', '')}\n{sample['description']}"
        time.sleep(0.15)

    for entry in channel_samples.values():
        entry["matched_queries"] = sorted(entry["matched_queries"])
        entry["videos"] = sorted(
            entry["videos"],
            key=lambda video: video.get("published_at") or "",
            reverse=True,
        )[:5]
    return channel_samples


def youtube_channel_stats(channel_ids: Sequence[str], api_key: str) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    ids = list(dict.fromkeys(channel_ids))
    for index in range(0, len(ids), 50):
        chunk = ids[index:index + 50]
        data = request_json(
            YOUTUBE_CHANNELS_URL,
            {
                "part": "snippet,statistics",
                "id": ",".join(chunk),
                "key": api_key,
            },
        )
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("id"):
                results[item["id"]] = item
        time.sleep(0.15)
    return results


def youtube_score(
    subscribers: int,
    total_views: int | None,
    video_count: int | None,
    matched_query_count: int,
    sample_video_count: int,
    latest_video_at: str | None,
    has_social_links: bool,
) -> float:
    avg_views = (total_views or 0) / max(video_count or 1, 1)
    subs_score = min(35.0, math.log10(subscribers + 1) * 7.0)
    avg_views_score = min(25.0, math.log10(avg_views + 1) * 5.0)
    match_score = min(25.0, matched_query_count * 4.0 + sample_video_count * 3.0)
    social_score = 5.0 if has_social_links else 0.0
    recency_score = 0.0
    latest_dt = parse_datetime(latest_video_at)
    if latest_dt:
        age_days = max(0, (utc_now() - latest_dt).days)
        recency_score = max(0.0, 10.0 - age_days)
    return round(subs_score + avg_views_score + match_score + social_score + recency_score, 2)


def discover_youtube_candidates(
    topic_key: str,
    topic_cfg: Dict[str, Any],
    config: YoutubeConfig,
) -> List[Dict[str, Any]]:
    samples_by_channel = youtube_search(topic_key, topic_cfg.get("youtube_queries", []), config)
    if not samples_by_channel:
        return []

    stats_by_channel = youtube_channel_stats(list(samples_by_channel), config.api_key)
    candidates: List[Dict[str, Any]] = []
    today = iso_today()

    for channel_id, channel in stats_by_channel.items():
        stats = channel.get("statistics") or {}
        snippet = channel.get("snippet") or {}
        subscribers = safe_int(stats.get("subscriberCount"))
        if subscribers is None:
            continue
        if subscribers < config.min_subscribers or subscribers > config.max_subscribers:
            continue

        sample_info = samples_by_channel.get(channel_id, {})
        videos = sample_info.get("videos") or []
        latest_video_at = videos[0].get("published_at") if videos else None
        description = snippet.get("description") or ""
        social_links = extract_social_links(f"{description}\n{sample_info.get('description_text', '')}")
        total_views = safe_int(stats.get("viewCount"))
        video_count = safe_int(stats.get("videoCount"))
        score = youtube_score(
            subscribers=subscribers,
            total_views=total_views,
            video_count=video_count,
            matched_query_count=len(sample_info.get("matched_queries") or []),
            sample_video_count=len(videos),
            latest_video_at=latest_video_at,
            has_social_links=bool(social_links),
        )

        notes = []
        if topic_cfg.get("sensitive_topic"):
            notes.append(
                "Peptide/wellness creator signal only; verify all medical claims against truth-layer sources."
            )

        candidates.append(
            {
                "id": f"youtube:{channel_id}",
                "external_id": channel_id,
                "name": snippet.get("title") or "Unknown YouTube channel",
                "platform": "youtube",
                "topic_key": topic_key,
                "topic_label": topic_cfg.get("label", topic_key),
                "primary_url": f"https://www.youtube.com/channel/{channel_id}",
                "discovered_on": today,
                "score": score,
                "metrics": {
                    "subscribers": subscribers,
                    "total_views": total_views,
                    "video_count": video_count,
                    "avg_views_per_video": round((total_views or 0) / max(video_count or 1, 1), 2),
                    "matched_queries": len(sample_info.get("matched_queries") or []),
                    "sample_videos": len(videos),
                },
                "social_links": social_links,
                "source_metadata": {
                    "matched_queries": sample_info.get("matched_queries") or [],
                    "recent_video_samples": videos,
                    "channel_description": description[:2000],
                    "latest_video_at": latest_video_at,
                    "micro_band": {
                        "min_subscribers": config.min_subscribers,
                        "max_subscribers": config.max_subscribers,
                    },
                    "discovery_source": "youtube_data_api",
                    "notes": notes,
                },
            }
        )

    return candidates


def load_feeds_config() -> Dict[str, Any]:
    if not FEEDS_CONFIG_PATH.exists():
        return {}
    with FEEDS_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def rss_sources_for_topic(topic_cfg: Dict[str, Any], feeds_config: Dict[str, Any]) -> List[str]:
    terms = [term.lower() for term in topic_cfg.get("feed_topic_terms", [])]
    sources: List[str] = []
    for topic in feeds_config.get("topics", []) or []:
        if not isinstance(topic, dict):
            continue
        topic_name = str(topic.get("topic_name") or "").lower()
        if terms and not any(term in topic_name for term in terms):
            continue
        for url in topic.get("rss_sources", []) or []:
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                sources.append(url)
    return sorted(dict.fromkeys(sources))


def text_or_attr(tag: Any, attr: str | None = None) -> str:
    if not tag:
        return ""
    if attr:
        return str(tag.get(attr) or "").strip()
    return tag.get_text(" ", strip=True) if hasattr(tag, "get_text") else str(tag).strip()


def first_text(item: Any, selectors: Sequence[str]) -> str:
    for selector in selectors:
        found = item.find(selector)
        value = text_or_attr(found)
        if value:
            return value
    return ""


def first_link(item: Any) -> str:
    link = item.find("link")
    if link:
        href = text_or_attr(link, "href")
        if href:
            return href
        value = text_or_attr(link)
        if value:
            return value
    return ""


def discover_rss_author_candidates(
    topic_key: str,
    topic_cfg: Dict[str, Any],
    feeds_config: Dict[str, Any],
    rss_limit_per_feed: int,
) -> List[Dict[str, Any]]:
    rss_urls = rss_sources_for_topic(topic_cfg, feeds_config)
    if not rss_urls:
        return []

    authors: Dict[str, Dict[str, Any]] = {}
    today = iso_today()

    for feed_url in rss_urls:
        try:
            response = requests.get(feed_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
        except Exception as exc:
            print(f"RSS fetch failed for {feed_url}: {exc}")
            continue

        soup = BeautifulSoup(response.content, "xml")
        entries = soup.find_all(["item", "entry"])[:max(1, rss_limit_per_feed)]
        for entry in entries:
            title = first_text(entry, ["title"])
            link = first_link(entry) or feed_url
            author = first_text(entry, ["author", "creator", "dc:creator", "name"])
            if not author:
                continue
            summary = first_text(entry, ["description", "summary", "content", "content:encoded"])
            key = stable_id(["rss_author", topic_key, domain_for(link) or domain_for(feed_url), author])
            info = authors.setdefault(
                key,
                {
                    "name": author,
                    "domain": domain_for(link) or domain_for(feed_url),
                    "sample_url": link,
                    "titles": [],
                    "feed_urls": set(),
                    "social_text": "",
                },
            )
            info["titles"].append(title)
            info["feed_urls"].add(feed_url)
            info["social_text"] = f"{info.get('social_text', '')}\n{summary}\n{link}"

    candidates: List[Dict[str, Any]] = []
    for key, info in authors.items():
        titles = [title for title in info.get("titles", []) if title]
        feed_urls = sorted(info.get("feed_urls") or [])
        social_links = extract_social_links(info.get("social_text", ""))
        score = round(min(70.0, 12.0 + len(titles) * 8.0 + len(feed_urls) * 4.0 + (5.0 if social_links else 0.0)), 2)
        candidates.append(
            {
                "id": f"rss_author:{key}",
                "external_id": key,
                "name": info["name"],
                "platform": "rss_author",
                "topic_key": topic_key,
                "topic_label": topic_cfg.get("label", topic_key),
                "primary_url": info.get("sample_url") or "",
                "discovered_on": today,
                "score": score,
                "metrics": {
                    "posts_seen_in_fetch": len(titles),
                    "feeds_seen": len(feed_urls),
                    "subscriber_count": None,
                },
                "social_links": social_links,
                "source_metadata": {
                    "domain": info.get("domain"),
                    "feed_urls": feed_urls,
                    "sample_titles": titles[:5],
                    "discovery_source": "rss_author_frequency",
                    "micro_band": "unknown; RSS author signal has no free follower metric",
                },
            }
        )

    return candidates


def dedupe_candidates(candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        candidate_id = candidate.get("id")
        if not candidate_id:
            continue
        existing = by_id.get(candidate_id)
        if existing is None or float(candidate.get("score") or 0) > float(existing.get("score") or 0):
            by_id[candidate_id] = dict(candidate)
    return sorted(by_id.values(), key=lambda item: (float(item.get("score") or 0), item.get("name", "")), reverse=True)


def topic_file_path(data_dir: Path, topic_key: str) -> Path:
    return data_dir / f"{topic_key}.json"


def load_existing(data_dir: Path, topic_key: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    path = topic_file_path(data_dir, topic_key)
    if not path.exists():
        return {}, []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, list):
        return {}, [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        items = raw.get("influencers") or []
        return raw, [item for item in items if isinstance(item, dict)]
    return {}, []


def write_topic_file(
    data_dir: Path,
    topic_key: str,
    topic_cfg: Dict[str, Any],
    influencers: Sequence[Dict[str, Any]],
    new_items: Sequence[Dict[str, Any]],
    run_summary: Dict[str, Any],
) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA_VERSION,
        "topic_key": topic_key,
        "topic_label": topic_cfg.get("label", topic_key),
        "updated_at": iso_now(),
        "new_this_run": len(new_items),
        "total_influencers": len(influencers),
        "run_summary": run_summary,
        "influencers": list(influencers),
    }
    path = topic_file_path(data_dir, topic_key)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def select_new_items(existing: Sequence[Dict[str, Any]], candidates: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    existing_ids = {item.get("id") for item in existing if item.get("id")}
    new_items = [item for item in dedupe_candidates(candidates) if item.get("id") not in existing_ids]
    return new_items[:max(1, limit)]


def merge_influencers(existing: Sequence[Dict[str, Any]], new_items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {item["id"]: dict(item) for item in existing if item.get("id")}
    for item in new_items:
        by_id[item["id"]] = dict(item)
    merged = list(by_id.values())
    merged.sort(
        key=lambda item: (
            item.get("discovered_on") or "",
            float(item.get("score") or 0),
            item.get("name") or "",
        ),
        reverse=True,
    )
    return merged


def topic_keys_from_args(values: Sequence[str] | None) -> List[str]:
    if not values:
        return list(TOPICS)
    keys: List[str] = []
    for value in values:
        for part in value.split(","):
            key = part.strip()
            if key:
                if key not in TOPICS:
                    raise SystemExit(f"Unknown topic '{key}'. Valid topics: {', '.join(TOPICS)}")
                keys.append(key)
    return list(dict.fromkeys(keys))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover free-source micro-influencer candidates.")
    parser.add_argument("--topic", action="append", help="Topic key to run. May be repeated or comma-separated.")
    parser.add_argument("--out-dir", default=str(DEFAULT_DATA_DIR), help="Directory for influencer JSON files.")
    parser.add_argument("--max-per-topic", type=int, default=env_int("INFLUENCERS_PER_TOPIC", DEFAULT_MAX_PER_TOPIC))
    parser.add_argument("--search-days", type=int, default=env_int("INFLUENCER_SEARCH_DAYS", DEFAULT_SEARCH_DAYS))
    parser.add_argument("--youtube-max-results", type=int, default=env_int("INFLUENCER_YOUTUBE_MAX_RESULTS", DEFAULT_YOUTUBE_MAX_RESULTS))
    parser.add_argument("--min-subscribers", type=int, default=env_int("INFLUENCER_MIN_SUBSCRIBERS", DEFAULT_MIN_SUBSCRIBERS))
    parser.add_argument("--max-subscribers", type=int, default=env_int("INFLUENCER_MAX_SUBSCRIBERS", DEFAULT_MAX_SUBSCRIBERS))
    parser.add_argument("--rss-limit-per-feed", type=int, default=env_int("INFLUENCER_RSS_LIMIT_PER_FEED", DEFAULT_RSS_LIMIT_PER_FEED))
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and rank without writing files.")
    return parser.parse_args()


def main() -> None:
    load_environment()
    args = parse_args()
    data_dir = Path(args.out_dir)
    topic_keys = topic_keys_from_args(args.topic)
    youtube_api_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("YT_API_KEY") or ""
    feeds_config = load_feeds_config() if not args.skip_rss else {}

    youtube_config = None
    if not args.skip_youtube:
        if youtube_api_key:
            youtube_config = YoutubeConfig(
                api_key=youtube_api_key,
                min_subscribers=args.min_subscribers,
                max_subscribers=args.max_subscribers,
                search_days=args.search_days,
                max_results=args.youtube_max_results,
            )
        else:
            print("YOUTUBE_API_KEY/YT_API_KEY is not set; skipping YouTube discovery and using RSS only.")

    run_started = iso_now()
    print("=== OpenSourceNews Daily Influencer Discovery ===")
    print(f"Topics: {', '.join(topic_keys)}")
    print(f"Output directory: {data_dir}")
    print(f"Dry run: {args.dry_run}")

    total_new = 0
    manifest_topics: Dict[str, Any] = {}

    for topic_key in topic_keys:
        topic_cfg = TOPICS[topic_key]
        print(f"\n--- {topic_cfg.get('label', topic_key)} ({topic_key}) ---")
        candidates: List[Dict[str, Any]] = []

        if youtube_config:
            try:
                youtube_candidates = discover_youtube_candidates(topic_key, topic_cfg, youtube_config)
                candidates.extend(youtube_candidates)
                print(f"YouTube candidates: {len(youtube_candidates)}")
            except Exception as exc:
                print(f"YouTube discovery failed for {topic_key}: {exc}")

        if not args.skip_rss:
            try:
                rss_candidates = discover_rss_author_candidates(
                    topic_key,
                    topic_cfg,
                    feeds_config,
                    rss_limit_per_feed=args.rss_limit_per_feed,
                )
                candidates.extend(rss_candidates)
                print(f"RSS author candidates: {len(rss_candidates)}")
            except Exception as exc:
                print(f"RSS discovery failed for {topic_key}: {exc}")

        candidates = dedupe_candidates(candidates)
        _, existing = load_existing(data_dir, topic_key)
        selected = select_new_items(existing, candidates, args.max_per_topic)
        merged = merge_influencers(existing, selected)
        total_new += len(selected)

        run_summary = {
            "run_started_at": run_started,
            "candidate_count": len(candidates),
            "existing_count": len(existing),
            "selected_new_count": len(selected),
            "max_per_topic": args.max_per_topic,
            "youtube_enabled": bool(youtube_config),
            "rss_enabled": not args.skip_rss,
        }
        manifest_topics[topic_key] = run_summary

        print(f"Existing: {len(existing)}")
        print(f"Selected new: {len(selected)}")
        for item in selected[:5]:
            print(f"  - {item.get('platform')}: {item.get('name')} ({item.get('score')})")

        if args.dry_run:
            continue
        if selected or not topic_file_path(data_dir, topic_key).exists():
            write_topic_file(data_dir, topic_key, topic_cfg, merged, selected, run_summary)

    if not args.dry_run and total_new:
        manifest = {
            "schema": SCHEMA_VERSION,
            "generated_at": iso_now(),
            "total_new": total_new,
            "topics": manifest_topics,
        }
        (data_dir / "latest_run.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(f"\nDone. New influencers selected: {total_new}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
