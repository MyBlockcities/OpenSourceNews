"""
Shared transcript analysis (truncated vs chunked) for daily_run and api/script_generator.
Uses LLMClient (Ollama or Gemini) from llm_provider.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from pipelines.llm_provider import LLMClient, parse_json_text


def analyze_transcript_truncated(
    llm: LLMClient,
    item: Dict[str, Any],
    transcript_text: str,
    word_count: int,
    max_words: int = 4000,
) -> Dict[str, Any]:
    """Standard analysis using up to max_words words of transcript."""
    truncated_transcript = " ".join(transcript_text.split()[:max_words])
    analysis_prompt = f"""Analyze this YouTube video transcript and provide detailed insights.

Video Title: {item.get('title', 'Unknown')}
Transcript ({word_count} words):
{truncated_transcript}

Return ONLY valid JSON with these exact fields (no markdown, no code blocks):
{{
    "quality_score": <number 0-10>,
    "main_topic": "<single sentence>",
    "key_insights": ["<insight 1>", "<insight 2>", "<insight 3>"],
    "content_type": "<Tutorial|News|Opinion|Research|Case Study>",
    "target_audience": "<Beginner|Intermediate|Advanced>",
    "unique_value": "<what makes this content special>"
}}

Quality Score Criteria:
- 8-10: Groundbreaking, highly actionable, expert-level
- 6-7: Solid content, good insights, well-produced
- 4-5: Average, basic information
- 0-3: Low value, clickbait, or superficial"""

    text = llm.generate(analysis_prompt, json_mode=True)
    analysis = parse_json_text(text)
    return {
        **item,
        "has_transcript": True,
        "transcript_word_count": word_count,
        "transcript_mode": "truncated",
        "quality_score": analysis.get("quality_score", 5),
        "main_topic": analysis.get("main_topic", ""),
        "key_insights": analysis.get("key_insights", []),
        "content_type": analysis.get("content_type", "General"),
        "target_audience": analysis.get("target_audience", "General"),
        "unique_value": analysis.get("unique_value", ""),
    }


def analyze_transcript_chunked(
    llm: LLMClient,
    item: Dict[str, Any],
    transcript_text: str,
    word_count: int,
) -> Dict[str, Any]:
    """Chunked analysis for long transcripts (e.g. >4000 words)."""
    words = transcript_text.split()
    chunk_size = 3000
    overlap = 300
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap

    all_insights: List[str] = []
    all_key_topics: List[str] = []

    for i, chunk in enumerate(chunks):
        prompt = f"""Analyze chunk {i+1}/{len(chunks)} of a YouTube video transcript.

Video Title: {item.get('title', 'Unknown')}
Chunk {i+1} of {len(chunks)} ({len(chunk.split())} words):
{chunk}

Return ONLY valid JSON:
{{
    "key_insights": ["insight 1", "insight 2"],
    "main_topics": ["topic 1", "topic 2"],
    "content_type": "<Tutorial|News|Opinion|Research|Case Study>",
    "notable_claims": ["claim if any"]
}}"""
        try:
            chunk_result = parse_json_text(llm.generate(prompt, json_mode=True))
            all_insights.extend(chunk_result.get("key_insights", []))
            all_key_topics.extend(chunk_result.get("main_topics", []))
        except Exception as e:
            print(f"    Chunk {i+1} analysis failed: {e}")

    unique_insights = list(dict.fromkeys(all_insights))[:10]
    unique_topics = list(dict.fromkeys(all_key_topics))[:5]

    synthesis_prompt = f"""Synthesize these insights from a full video transcript analysis.

Video Title: {item.get('title', 'Unknown')}
Total words: {word_count}
Key insights from all chunks:
{json.dumps(unique_insights, ensure_ascii=False)}

Topics covered:
{json.dumps(unique_topics, ensure_ascii=False)}

Return ONLY valid JSON:
{{
    "quality_score": <0-10>,
    "main_topic": "single sentence",
    "key_insights": ["top 5 insights"],
    "content_type": "<Tutorial|News|Opinion|Research|Case Study>",
    "target_audience": "<Beginner|Intermediate|Advanced>",
    "unique_value": "what makes this special"
}}"""

    try:
        synthesis = parse_json_text(llm.generate(synthesis_prompt, json_mode=True))
        return {
            **item,
            "has_transcript": True,
            "transcript_word_count": word_count,
            "transcript_mode": "chunked_full",
            "quality_score": synthesis.get("quality_score", 5),
            "main_topic": synthesis.get("main_topic", ""),
            "key_insights": synthesis.get("key_insights", unique_insights[:5]),
            "content_type": synthesis.get("content_type", "General"),
            "target_audience": synthesis.get("target_audience", "General"),
            "unique_value": synthesis.get("unique_value", ""),
        }
    except Exception as e:
        print(f"    Synthesis failed: {e}")

    return {
        **item,
        "has_transcript": True,
        "transcript_word_count": word_count,
        "transcript_mode": "chunked_full",
        "key_insights": unique_insights[:5],
    }


def analyze_transcript_auto(
    llm: LLMClient,
    item: Dict[str, Any],
    transcript_text: str,
    word_count: int,
    long_threshold: int = 4000,
) -> Dict[str, Any]:
    """Choose truncated vs chunked_full based on length."""
    if word_count > long_threshold:
        return analyze_transcript_chunked(llm, item, transcript_text, word_count)
    return analyze_transcript_truncated(llm, item, transcript_text, word_count)
