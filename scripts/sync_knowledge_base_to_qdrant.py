#!/usr/bin/env python3
"""Embed and sync knowledge-base records into Qdrant."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import google.generativeai as genai
import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from build_knowledge_base import KNOWLEDGE_BASE_DIR, main as build_knowledge_base  # noqa: E402


DEFAULT_COLLECTION = "scheduler_knowledge_base"
DEFAULT_DISTANCE = "Cosine"
DEFAULT_EMBEDDING_MODEL = "models/text-embedding-004"
DEFAULT_BATCH_SIZE = 50
DEFAULT_EMBED_MAX_CHARS = 12000
DEFAULT_EMBED_BATCH_SIZE = 10


def load_environment() -> None:
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(ROOT_DIR / ".env.local")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def strip_none(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def read_records(rebuild: bool = False) -> List[Dict[str, Any]]:
    if rebuild or not (KNOWLEDGE_BASE_DIR / "knowledge_base.jsonl").exists():
        build_knowledge_base()

    records_path = KNOWLEDGE_BASE_DIR / "knowledge_base.jsonl"
    records: List[Dict[str, Any]] = []
    with records_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def iter_batches(items: Sequence[Dict[str, Any]], size: int) -> Iterable[Sequence[Dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def build_embedding_text(record: Dict[str, Any], max_chars: int) -> str:
    # Use pre-built embedding_text if available (from enriched KB builder)
    if record.get("embedding_text"):
        return record["embedding_text"][:max_chars]

    parts = [
        f"Record type: {record.get('record_type', 'unknown')}",
        f"Title: {record.get('title', '')}",
        f"Topic: {record.get('topic', '')}",
        f"Bucket: {record.get('bucket', '')}",
        f"Date: {record.get('date', '')}",
        f"Source: {record.get('source', '')}",
        f"Category: {record.get('category', '')}",
        f"URL: {record.get('url', record.get('video_url', ''))}",
        "",
        record.get("content", ""),
    ]

    # Include enriched fields for richer embeddings
    for claim in (record.get("claims") or []):
        if isinstance(claim, dict):
            parts.append(f"Claim: {claim.get('claim', '')}")
    for lesson in (record.get("key_lessons") or []):
        parts.append(f"Lesson: {lesson}")
    for entity in (record.get("entities") or []):
        parts.append(f"Entity: {entity}")
    if record.get("neutral_synthesis"):
        parts.append(f"Synthesis: {record['neutral_synthesis']}")
    if record.get("implementation_notes"):
        parts.append(f"Implementation: {record['implementation_notes']}")

    text = "\n".join(part for part in parts if part and part.strip())
    return text[:max_chars]


def coerce_embedding(item: Any) -> List[float]:
    if isinstance(item, dict):
        if "values" in item:
            return item["values"]
        if "embedding" in item:
            return coerce_embedding(item["embedding"])
    if isinstance(item, list) and item and isinstance(item[0], (float, int)):
        return [float(value) for value in item]
    raise ValueError(f"Unsupported embedding shape: {type(item)}")


def parse_embeddings(result: Dict[str, Any]) -> List[List[float]]:
    if "embeddings" in result:
        return [coerce_embedding(item) for item in result["embeddings"]]

    if "embedding" in result:
        embedding = result["embedding"]
        if isinstance(embedding, list) and embedding and isinstance(embedding[0], dict):
            return [coerce_embedding(item) for item in embedding]
        return [coerce_embedding(embedding)]

    raise ValueError(f"Embedding response missing expected keys: {result.keys()}")


def embed_texts(texts: Sequence[str], model_name: str) -> List[List[float]]:
    try:
        result = genai.embed_content(
            model=model_name,
            content=list(texts),
            task_type="retrieval_document",
        )
        embeddings = parse_embeddings(result)
        if len(embeddings) == len(texts):
            return embeddings
    except Exception:
        pass

    embeddings: List[List[float]] = []
    for text in texts:
        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type="retrieval_document",
        )
        embeddings.extend(parse_embeddings(result))
    return embeddings


def qdrant_headers(api_key: str | None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def qdrant_request(method: str, url: str, api_key: str | None, **kwargs: Any) -> requests.Response:
    response = requests.request(method, url, headers=qdrant_headers(api_key), timeout=60, **kwargs)
    return response


def ensure_collection(base_url: str, api_key: str | None, collection: str, vector_size: int, distance: str, recreate: bool) -> None:
    collection_url = f"{base_url}/collections/{collection}"
    existing = qdrant_request("GET", collection_url, api_key)

    if existing.status_code == 200 and recreate:
        delete_response = qdrant_request("DELETE", collection_url, api_key)
        delete_response.raise_for_status()
        existing = requests.Response()
        existing.status_code = 404

    if existing.status_code == 200:
        existing_payload = existing.json()
        existing_vectors = (
            existing_payload.get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
        )
        if isinstance(existing_vectors, dict):
            existing_size = existing_vectors.get("size")
            if existing_size and existing_size != vector_size:
                raise RuntimeError(
                    f"Qdrant collection '{collection}' already exists with vector size {existing_size}, "
                    f"but current embeddings use size {vector_size}. Re-run with --recreate-collection."
                )
        return

    if existing.status_code not in {404, 400}:
        existing.raise_for_status()

    create_response = qdrant_request(
        "PUT",
        collection_url,
        api_key,
        json={
            "vectors": {
                "size": vector_size,
                "distance": distance,
            },
            "on_disk_payload": True,
        },
    )
    create_response.raise_for_status()


def record_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    tags = [
        record.get("record_type"),
        record.get("topic"),
        record.get("source"),
        record.get("category"),
        record.get("bucket"),
        record.get("processing_mode"),
        record.get("content_type"),
        record.get("difficulty"),
    ]
    # Add entity tags for graph-style filtering
    for entity in (record.get("entities") or []):
        tags.append(f"entity:{entity}")
    payload = dict(record)
    payload["tags"] = [tag for tag in tags if tag]
    return strip_none(payload)


def upsert_points(base_url: str, api_key: str | None, collection: str, points: List[Dict[str, Any]]) -> None:
    upsert_url = f"{base_url}/collections/{collection}/points?wait=true"
    response = qdrant_request("PUT", upsert_url, api_key, json={"points": points})
    response.raise_for_status()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the generated knowledge base into Qdrant.")
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("QDRANT_BATCH_SIZE", DEFAULT_BATCH_SIZE)))
    parser.add_argument("--embed-batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    parser.add_argument("--embed-model", default=os.getenv("QDRANT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    parser.add_argument("--embed-max-chars", type=int, default=int(os.getenv("QDRANT_EMBED_MAX_CHARS", DEFAULT_EMBED_MAX_CHARS)))
    parser.add_argument("--bucket-filter", action="append", default=None, help="Only sync records with this bucket. May be passed multiple times.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rebuild-knowledge-base", action="store_true")
    parser.add_argument("--recreate-collection", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_environment()
    args = parse_args()

    records = read_records(rebuild=args.rebuild_knowledge_base)
    if args.bucket_filter:
        allowed = {bucket.strip() for bucket in args.bucket_filter if bucket.strip()}
        records = [record for record in records if record.get("bucket") in allowed]
    if args.limit is not None:
        records = records[:args.limit]

    print(f"Loaded {len(records)} knowledge-base records")
    if not records:
        print("No records found. Nothing to sync.")
        return

    if args.dry_run:
        print("Dry run enabled; skipping embedding and Qdrant upsert.")
        return

    qdrant_url = os.getenv("QDRANT_URL")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        raise RuntimeError("QDRANT_URL is required")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for embedding")

    genai.configure(api_key=gemini_api_key)

    recreate_collection = args.recreate_collection or env_bool("QDRANT_RECREATE_COLLECTION", False)
    distance = os.getenv("QDRANT_DISTANCE", DEFAULT_DISTANCE)
    base_url = qdrant_url.rstrip("/")

    first_text = build_embedding_text(records[0], args.embed_max_chars)
    first_vector = embed_texts([first_text], args.embed_model)[0]
    ensure_collection(base_url, qdrant_api_key, args.collection, len(first_vector), distance, recreate_collection)

    synced = 0
    for batch in iter_batches(records, args.batch_size):
        texts = [build_embedding_text(record, args.embed_max_chars) for record in batch]
        vectors: List[List[float]] = []
        for embed_batch in range(0, len(texts), args.embed_batch_size):
            chunk = texts[embed_batch:embed_batch + args.embed_batch_size]
            vectors.extend(embed_texts(chunk, args.embed_model))

        points = []
        for record, vector in zip(batch, vectors):
            points.append(
                {
                    "id": record["id"],
                    "vector": vector,
                    "payload": record_payload(record),
                }
            )

        upsert_points(base_url, qdrant_api_key, args.collection, points)
        synced += len(points)
        print(f"Upserted {synced}/{len(records)} records into '{args.collection}'")

    print("Qdrant sync complete.")


if __name__ == "__main__":
    main()
