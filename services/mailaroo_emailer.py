import os
from pathlib import Path
from typing import Optional

import requests


MAILAROO_DEFAULT_API_URL = "https://api.mailaroo.com/send"


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is not None:
        value = value.strip()
    return value or default


def send_markdown_report(md_path: Path, subject: str) -> None:
    """Send the given markdown report via Mailaroo, if configured.

    This is a best-effort helper: if required configuration is missing,
    it will log a warning and return without raising.
    """
    api_key = _get_env("MAILAROO_API_KEY")
    to_email = _get_env("MAILAROO_TO_EMAIL")
    from_email = _get_env("MAILAROO_FROM_EMAIL", to_email)
    api_url = _get_env("MAILAROO_API_URL", MAILAROO_DEFAULT_API_URL)

    if not api_key or not to_email or not api_url:
        print("INFO: Mailaroo not configured (missing MAILAROO_API_KEY, MAILAROO_TO_EMAIL, or MAILAROO_API_URL). Skipping email.")
        return

    if not md_path.exists():
        print(f"INFO: Markdown report not found at {md_path}. Skipping email.")
        return

    body = md_path.read_text(encoding="utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "text": body,
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if resp.status_code >= 400:
            print(f"WARNING: Mailaroo email failed with status {resp.status_code}: {resp.text[:200]}")
        else:
            print("INFO: Mailaroo email sent successfully.")
    except Exception as e:
        print(f"WARNING: Mailaroo email exception: {type(e).__name__}: {str(e)[:200]}")
