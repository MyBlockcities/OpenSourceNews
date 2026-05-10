"""
Unified LLM access:
  - Ollama (local, no cloud LLM fees)
  - OpenRouter (many models; use :free slugs or provider.sort=price for cheap tiers)
  - Gemini (premium, direct Google API)
  - rotating: alternate OpenRouter + Ollama per request to spread load / reduce rate-limit hits

Docs: https://openrouter.ai/docs/guides/routing/provider-selection

Environment (high level):
  LLM_PROVIDER=ollama|openrouter|gemini|rotating
    rotating = OpenRouter + Ollama alternating (see OPENROUTER_* and OLLAMA_*)

  OPENROUTER_API_KEY=sk-or-...
  OPENROUTER_MODEL=google/gemma-2-9b-it:free   (example free-tier slug; pick from OpenRouter model list)
  OPENROUTER_PROVIDER_SORT=price               optional: maps to provider.sort (price|throughput|latency)
  OPENROUTER_PROVIDER_JSON={"sort":"price"}   optional: full provider object override (JSON)
  OPENROUTER_MAX_REQUESTS_PER_RUN=0            optional hard cap per Python process; 0 = unlimited
  OPENROUTER_MIN_INTERVAL_SECONDS=0            optional spacing between OpenRouter calls

  LLM_ROTATION_FAILOVER=1                     on error from chosen backend, try the other once (default on)
"""

from __future__ import annotations

import itertools
import json
import os
import re
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import google.generativeai as genai
import requests

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENROUTER_MODEL = "google/gemma-2-9b-it:free"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = int(os.environ.get("LLM_HTTP_TIMEOUT", os.environ.get("OLLAMA_TIMEOUT", "600")))


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def parse_json_text(text: str) -> Any:
    return json.loads(_strip_json_fences(text))


def _extract_gemini_text(response: Any) -> str:
    text_response = getattr(response, "text", None)
    if not text_response and getattr(response, "candidates", None):
        try:
            text_response = response.candidates[0].content.parts[0].text
        except (IndexError, AttributeError):
            pass
    if not text_response:
        raise ValueError("No text returned from Gemini")
    return _strip_json_fences(text_response)


class LLMClient(ABC):
    name: str = "unknown"

    @abstractmethod
    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        """Return model text (JSON string if json_mode)."""


class GeminiLLM(LLMClient):
    name = "gemini"

    def __init__(self, model_name: Optional[str] = None) -> None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (required for LLM_PROVIDER=gemini)")
        genai.configure(api_key=key)
        self._model_name = model_name or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self._model = genai.GenerativeModel(self._model_name)

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["generation_config"] = {"response_mime_type": "application/json"}
        response = self._model.generate_content(prompt, **kwargs)
        return _extract_gemini_text(response)


class OllamaLLM(LLMClient):
    name = "ollama"

    def __init__(self, base_url: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.base = (base_url or os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)).rstrip("/")
        self.model_name = model_name or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        p = prompt
        if json_mode:
            p = (
                f"{prompt}\n\n"
                "Respond with ONLY valid JSON. No markdown code fences, no commentary."
            )
        url = f"{self.base}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": p}],
            "stream": False,
        }
        try:
            r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(
                f"Ollama request failed ({self.base}). Is Ollama running? "
                f"Install from https://ollama.com and run: ollama pull {self.model_name}. "
                f"Or set LLM_PROVIDER=openrouter with OPENROUTER_API_KEY. ({e})"
            ) from e
        data = r.json()
        msg = data.get("message") or {}
        content = msg.get("content")
        if not content:
            raise ValueError(f"Unexpected Ollama response: {data!r}")
        return content.strip()


def _openrouter_provider_payload() -> Optional[dict[str, Any]]:
    raw = os.environ.get("OPENROUTER_PROVIDER_JSON", "").strip()
    if raw:
        return json.loads(raw)
    sort = os.environ.get("OPENROUTER_PROVIDER_SORT", "").strip().lower()
    if sort in ("price", "throughput", "latency"):
        return {"sort": sort}
    return None


class OpenRouterLLM(LLMClient):
    """OpenAI-compatible chat at OpenRouter; supports provider routing in request body."""

    name = "openrouter"
    _usage_lock = threading.Lock()
    _requests_made = 0
    _last_request_at = 0.0

    def __init__(self, model_name: Optional[str] = None) -> None:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set (required for LLM_PROVIDER=openrouter or rotating)"
            )
        self._api_key = key
        self.model_name = model_name or os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        self._url = os.environ.get("OPENROUTER_CHAT_URL", OPENROUTER_CHAT_URL).strip()
        self._max_requests_per_run = max(
            0, int(os.environ.get("OPENROUTER_MAX_REQUESTS_PER_RUN", "0") or "0")
        )
        self._min_interval_seconds = max(
            0.0,
            float(os.environ.get("OPENROUTER_MIN_INTERVAL_SECONDS", "0") or "0"),
        )

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        referer = os.environ.get("OPENROUTER_HTTP_REFERER", "").strip()
        if referer:
            h["HTTP-Referer"] = referer
        title = os.environ.get("OPENROUTER_TITLE", "OpenSourceNews").strip()
        h["X-OpenRouter-Title"] = title
        return h

    def _before_request(self) -> None:
        with OpenRouterLLM._usage_lock:
            if (
                self._max_requests_per_run
                and OpenRouterLLM._requests_made >= self._max_requests_per_run
            ):
                raise RuntimeError(
                    "OpenRouter request cap reached for this run "
                    f"({self._max_requests_per_run}). Increase "
                    "OPENROUTER_MAX_REQUESTS_PER_RUN or use no-LLM/local mode."
                )

            if self._min_interval_seconds and OpenRouterLLM._last_request_at:
                elapsed = time.monotonic() - OpenRouterLLM._last_request_at
                delay = self._min_interval_seconds - elapsed
                if delay > 0:
                    time.sleep(delay)

            OpenRouterLLM._requests_made += 1
            OpenRouterLLM._last_request_at = time.monotonic()

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        messages = [{"role": "user", "content": prompt}]
        if json_mode:
            messages[0]["content"] = (
                f"{prompt}\n\nRespond with ONLY valid JSON. No markdown code fences, no commentary."
            )

        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        prov = _openrouter_provider_payload()
        if prov:
            body["provider"] = prov

        self._before_request()
        r = requests.post(self._url, headers=self._headers(), json=body, timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            raise RuntimeError(
                f"OpenRouter rate limited (429). Use LLM_PROVIDER=rotating to alternate with Ollama, "
                f"or wait / upgrade limits. Body: {r.text[:500]}"
            )
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"OpenRouter: no choices in response: {data!r}")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if not content:
            raise ValueError(f"OpenRouter: empty content: {data!r}")
        return content.strip()


class RotatingOpenRouterOllama(LLMClient):
    """
    Alternate between OpenRouter and Ollama on each generate() call (thread-safe).
    Optionally failover to the other backend on error (LLM_ROTATION_FAILOVER, default on).
    """

    name = "rotating_openrouter_ollama"

    def __init__(self) -> None:
        self._or = OpenRouterLLM()
        self._ollama = OllamaLLM()
        self._lock = threading.Lock()
        self._counter = itertools.count()
        self._failover = os.environ.get("LLM_ROTATION_FAILOVER", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        with self._lock:
            idx = next(self._counter) % 2
        primary: LLMClient = self._or if idx == 0 else self._ollama
        secondary: LLMClient = self._ollama if idx == 0 else self._or

        try:
            return primary.generate(prompt, json_mode=json_mode)
        except Exception as first:
            if not self._failover:
                raise
            try:
                print(
                    f"WARNING: LLM primary ({primary.name}) failed: {first!s}; "
                    f"failover to {secondary.name}."
                )
                return secondary.generate(prompt, json_mode=json_mode)
            except Exception as second:
                raise RuntimeError(
                    f"Both LLM backends failed. Primary ({primary.name}): {first!s}. "
                    f"Secondary ({secondary.name}): {second!s}."
                ) from first


def ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def get_llm_client() -> LLMClient:
    """
    Resolve LLM backend from env.
    Defaults: ollama (local). Use openrouter, gemini, or rotating (OpenRouter + Ollama).
    """
    provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()

    if provider in ("google", "gemini", "premium"):
        return GeminiLLM()

    if provider in ("openrouter", "or"):
        return OpenRouterLLM()

    if provider in ("rotating", "openrouter_ollama", "or_ollama", "hybrid"):
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise RuntimeError("LLM_PROVIDER=rotating requires OPENROUTER_API_KEY")
        base = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
        if not ollama_reachable(base):
            print(
                f"WARNING: Ollama not reachable at {base} — using OpenRouter only (no alternation)."
            )
            return OpenRouterLLM()
        return RotatingOpenRouterOllama()

    if provider != "ollama":
        raise RuntimeError(
            f"Unknown LLM_PROVIDER={provider!r}; use 'ollama', 'openrouter', 'gemini', or 'rotating'"
        )

    base = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    if not ollama_reachable(base):
        fallback = os.environ.get("LLM_FALLBACK_TO_GEMINI", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if fallback and os.environ.get("GEMINI_API_KEY"):
            print("WARNING: Ollama not reachable; LLM_FALLBACK_TO_GEMINI=1 — using Gemini.")
            return GeminiLLM()
        or_fb = os.environ.get("LLM_FALLBACK_TO_OPENROUTER", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if or_fb and os.environ.get("OPENROUTER_API_KEY"):
            print("WARNING: Ollama not reachable; LLM_FALLBACK_TO_OPENROUTER=1 — using OpenRouter.")
            return OpenRouterLLM()
        raise RuntimeError(
            f"Ollama not reachable at {base}. Start Ollama, pull a model "
            f"(e.g. ollama pull {os.environ.get('OLLAMA_MODEL', DEFAULT_OLLAMA_MODEL)}), "
            "or set LLM_PROVIDER=openrouter / rotating, or enable fallbacks."
        )

    return OllamaLLM()


def try_get_llm_client() -> Optional[LLMClient]:
    """Like get_llm_client but returns None if configuration/connection fails."""
    try:
        return get_llm_client()
    except RuntimeError as e:
        print(f"WARNING: LLM unavailable: {e}")
        return None
