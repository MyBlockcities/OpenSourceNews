import os
import time
import json
import httpx
from typing import List, Dict, Tuple

YT_API_KEY = os.getenv("YT_API_KEY") or os.getenv("YOUTUBE_API_KEY") or ""
BASE = "https://www.googleapis.com/youtube/v3"

# Basic rate limiter (very light)
_last_call = 0.0
def _throttle(min_interval=0.2):
    global _last_call
    dt = time.time() - _last_call
    if dt < min_interval:
        time.sleep(min_interval - dt)
    _last_call = time.time()

def _get(endpoint: str, params: Dict) -> Dict:
    if not YT_API_KEY:
        raise RuntimeError("YT_API_KEY not set")
    _throttle()
    params = dict(params or {})
    params["key"] = YT_API_KEY
    url = f"{BASE}/{endpoint}"
    with httpx.Client(timeout=30.0) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()

def resolve_channel_id(identifier: str) -> str:
    """
    Accepts:
      - a channel ID (starts with 'UC...')
      - a handle like '@TwoMinutePapers' or '@vrsen'
      - a plain query like 'indydevdan'
    Returns a channelId (UCxxxx...) or '' if not found.
    """
    if not identifier:
        return ""
    ident = identifier.strip()
    if ident.startswith("UC") and len(ident) >= 20:
        return ident  # already a channel ID
    # Search for a channel matching the handle or query
    data = _get("search", {
        "part": "snippet",
        "q": ident,
        "type": "channel",
        "maxResults": 1
    })
    items = data.get("items", [])
    if not items:
        return ""
    return items[0]["id"]["channelId"]

def fetch_latest_videos(identifier: str, max_results: int = 5) -> List[Dict]:
    """
    Returns a list of {title, url, publishedAt, channelTitle, source}
    """
    ch_id = resolve_channel_id(identifier)
    if not ch_id:
        return []
    # Search latest videos by channelId
    data = _get("search", {
        "part": "snippet",
        "channelId": ch_id,
        "order": "date",
        "type": "video",
        "maxResults": max(1, min(max_results, 10))
    })
    out = []
    for it in data.get("items", []):
        sn = it["snippet"]
        out.append({
            "title": sn["title"],
            "url": f"https://youtu.be/{it['id']['videoId']}",
            "publishedAt": sn["publishedAt"],
            "channelTitle": sn["channelTitle"],
            "source": "YouTube"
        })
    return out
