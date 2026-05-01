"""
YouTube Search — Permanent Free Solution using Invidious API
============================================================
Priority order:
  1. Invidious API  — free, unlimited, no API key needed (used by most music bots)
  2. YouTube Data API v3 — only if YOUTUBE_API_KEY is set (optional, 100 searches/day quota)
  3. youtubesearchpython — final fallback (always free)

Invidious is an open-source YouTube frontend with a public API.
Multiple instances are tried so even if one is down, others work.
"""

import asyncio
import random
import time
from typing import Dict, List, Optional

import aiohttp

_search_cache: Dict[str, tuple] = {}
_search_lock = asyncio.Lock()
_SEARCH_TTL = 300

_instance_health: Dict[str, float] = {}
_COOLDOWN = 120


_INVIDIOUS_INSTANCES = [
    "https://invidious.nerdvpn.de",
    "https://inv.nadeko.net",
    "https://invidious.privacyredirect.com",
    "https://yt.cdaut.de",
    "https://invidious.flokinet.to",
    "https://invidious.perennialte.ch",
    "https://iv.datura.network",
    "https://invidious.protokolla.fi",
    "https://invidious.fdn.fr",
    "https://invidious.einfachzocken.eu",
]


def _seconds_to_min(secs: int) -> str:
    if not secs:
        return "0:00"
    return f"{secs // 60}:{secs % 60:02d}"


def _get_api_key() -> str:
    try:
        from config import YOUTUBE_API_KEY
        return YOUTUBE_API_KEY or ""
    except Exception:
        return ""


def _available_instances() -> List[str]:
    now = time.time()
    available = [i for i in _INVIDIOUS_INSTANCES if now - _instance_health.get(i, 0) > _COOLDOWN]
    if not available:
        _instance_health.clear()
        available = list(_INVIDIOUS_INSTANCES)
    random.shuffle(available)
    return available


def _mark_failed(instance: str) -> None:
    _instance_health[instance] = time.time()


async def _search_invidious(query: str, max_results: int = 10) -> List[Dict]:
    """
    Search using Invidious public API — completely free, no quota, no API key.
    Tries multiple instances automatically if one fails.
    """
    params = {
        "q": query,
        "type": "video",
        "fields": "videoId,title,author,lengthSeconds,videoThumbnails",
    }

    instances = _available_instances()
    timeout = aiohttp.ClientTimeout(total=6)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for instance in instances[:5]:
            try:
                url = f"{instance}/api/v1/search"
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        _mark_failed(instance)
                        continue
                    data = await resp.json(content_type=None)
                    if not data or not isinstance(data, list):
                        _mark_failed(instance)
                        continue

                    results = []
                    for item in data[:max_results]:
                        vid = item.get("videoId", "")
                        if not vid:
                            continue
                        secs = int(item.get("lengthSeconds") or 0)
                        thumbs = item.get("videoThumbnails") or []
                        thumb = next(
                            (t["url"] for t in thumbs if t.get("quality") == "medium"),
                            next(
                                (t["url"] for t in thumbs if t.get("url")),
                                f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"
                            )
                        )
                        if thumb and thumb.startswith("/vi/"):
                            thumb = f"https://img.youtube.com{thumb}"
                        results.append({
                            "id": vid,
                            "title": item.get("title", "Unknown"),
                            "channel": item.get("author", ""),
                            "duration": _seconds_to_min(secs),
                            "duration_sec": secs,
                            "thumb": thumb,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                        })
                    return results

            except (asyncio.TimeoutError, aiohttp.ClientError):
                _mark_failed(instance)
                continue
            except Exception:
                _mark_failed(instance)
                continue

    return []


async def _search_ytapi_v3(query: str, max_results: int = 10) -> List[Dict]:
    """Search using YouTube Data API v3 — requires YOUTUBE_API_KEY."""
    api_key = _get_api_key()
    if not api_key:
        return []

    _YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    _YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def _iso8601_to_seconds(duration: str) -> int:
        import re
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
        if not m:
            return 0
        return int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(_YT_SEARCH_URL, params={
                "key": api_key, "q": query, "part": "snippet",
                "type": "video", "maxResults": min(max_results, 50),
                "videoCategoryId": "10",
            }) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

            items = data.get("items", [])
            video_ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
            if not video_ids:
                return []

            async with session.get(_YT_VIDEOS_URL, params={
                "key": api_key, "id": ",".join(video_ids), "part": "contentDetails,snippet",
            }) as resp:
                detail_data = await resp.json() if resp.status == 200 else {"items": []}

            detail_map = {
                v["id"]: _iso8601_to_seconds(v.get("contentDetails", {}).get("duration", ""))
                for v in detail_data.get("items", [])
            }

            results = []
            for item in items:
                vid = item.get("id", {}).get("videoId", "")
                if not vid:
                    continue
                snippet = item.get("snippet", {})
                secs = detail_map.get(vid, 0)
                results.append({
                    "id": vid,
                    "title": snippet.get("title", "Unknown"),
                    "channel": snippet.get("channelTitle", ""),
                    "duration": _seconds_to_min(secs),
                    "duration_sec": secs,
                    "thumb": (
                        snippet.get("thumbnails", {}).get("medium", {}).get("url")
                        or f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"
                    ),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                })
            return results
    except Exception:
        return []


async def yt_api_search(query: str, max_results: int = 10) -> List[Dict]:
    """
    Main search function — uses best available method automatically:
    1. Invidious (free, unlimited, primary)
    2. YouTube Data API v3 (if YOUTUBE_API_KEY set, 100/day quota)
    3. Returns [] if both fail (caller will use youtubesearchpython)
    """
    cache_key = f"{query}:{max_results}"
    now = time.time()

    async with _search_lock:
        cached = _search_cache.get(cache_key)
        if cached and now - cached[0] < _SEARCH_TTL:
            return cached[1]

    results = await _search_invidious(query, max_results)

    if not results and _get_api_key():
        results = await _search_ytapi_v3(query, max_results)

    if results:
        async with _search_lock:
            if len(_search_cache) > 200:
                _search_cache.clear()
            _search_cache[cache_key] = (time.time(), results)

    return results


async def yt_api_video_details(video_id: str) -> Optional[Dict]:
    """
    Get video metadata — tries Invidious first, then YouTube API v3.
    Completely free via Invidious.
    """
    if not video_id:
        return None

    timeout = aiohttp.ClientTimeout(total=6)
    instances = _available_instances()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for instance in instances[:3]:
            try:
                url = f"{instance}/api/v1/videos/{video_id}"
                params = {"fields": "videoId,title,author,lengthSeconds,videoThumbnails"}
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        _mark_failed(instance)
                        continue
                    data = await resp.json(content_type=None)
                    secs = int(data.get("lengthSeconds") or 0)
                    thumbs = data.get("videoThumbnails") or []
                    thumb = next(
                        (t["url"] for t in thumbs if t.get("quality") == "medium"),
                        f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                    )
                    if thumb and thumb.startswith("/vi/"):
                        thumb = f"https://img.youtube.com{thumb}"
                    return {
                        "id": video_id,
                        "title": data.get("title", "Unknown"),
                        "channel": data.get("author", ""),
                        "duration": _seconds_to_min(secs),
                        "duration_sec": secs,
                        "thumb": thumb,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    }
            except Exception:
                _mark_failed(instance)
                continue

    if _get_api_key():
        results = await _search_ytapi_v3(f"https://www.youtube.com/watch?v={video_id}", 1)
        return results[0] if results else None

    return None


async def yt_api_related_videos(video_id: str, max_results: int = 8) -> List[Dict]:
    """
    Fetch YouTube-recommended related videos for a given video ID.
    Uses Invidious's recommendedVideos field (actual YouTube algorithm).
    Falls back to keyword search if unavailable.
    """
    if not video_id:
        return []

    timeout = aiohttp.ClientTimeout(total=8)
    instances = _available_instances()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for instance in instances[:4]:
            try:
                url = f"{instance}/api/v1/videos/{video_id}"
                params = {"fields": "recommendedVideos"}
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        _mark_failed(instance)
                        continue
                    data = await resp.json(content_type=None)
                    recs = data.get("recommendedVideos") or []
                    results = []
                    for v in recs:
                        vid = v.get("videoId", "")
                        title = v.get("title", "")
                        secs = int(v.get("lengthSeconds") or 0)
                        if not vid or not title:
                            continue
                        # Skip livestreams (duration 0) and very long videos (>12min)
                        if secs == 0 or secs > 720:
                            continue
                        thumbs = v.get("videoThumbnails") or []
                        thumb = next(
                            (t["url"] for t in thumbs if t.get("quality") == "medium"),
                            f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                        )
                        if thumb and thumb.startswith("/vi/"):
                            thumb = f"https://img.youtube.com{thumb}"
                        results.append({
                            "id": vid,
                            "title": title,
                            "channel": v.get("author", ""),
                            "duration": _seconds_to_min(secs),
                            "thumb": thumb,
                        })
                        if len(results) >= max_results:
                            break
                    if results:
                        return results
            except Exception:
                _mark_failed(instance)
                continue

    return []


def is_api_available() -> bool:
    """Always True — Invidious is always available (free, no key needed)."""
    return True
