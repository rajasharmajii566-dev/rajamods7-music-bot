"""
KHUSHI Fast Stream — millisecond-level YouTube search, extract & stream.

Flow:
  1. Check local cache → instant (0 ms)
  2. Race webserver cache vs SmartYTDL extract → ~10-50 ms on hit
  3. Full yt-dlp download fallback → ~10-25 s

Uses KHUSHI's SmartYTDL engine for multi-client YouTube bypass (2026).
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import aiohttp
from youtubesearchpython.__future__ import VideosSearch

from KHUSHI.utils.ytdl_smart import (
    smart_extract_url,
    smart_download,
    get_cdn_headers,
    get_base_ytdlp_opts,
)
from KHUSHI.core.dir import DOWNLOAD_DIR as _DOWNLOAD_DIR

_log = logging.getLogger("KHUSHI.fast_stream")

_WEB_PORT = int(os.environ.get("WEB_PORT") or 5000)
_YTURL_ENDPOINT = f"http://localhost:{_WEB_PORT}/api/yturl"

_bg_tasks: Dict[str, asyncio.Task] = {}


def _extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]
    return link.split("/")[-1].split("?")[0]


def _file_exists(vid: str) -> Optional[str]:
    for ext in ("m4a", "mp3", "mp4", "webm", "opus", "ogg", "flac"):
        path = os.path.join(_DOWNLOAD_DIR, f"{vid}.{ext}")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    return None


async def _webserver_url(vid: str) -> Optional[str]:
    try:
        from KHUSHI.utils.internal_secret import get_secret
        params = {"v": vid, "key": get_secret()}
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(_YTURL_ENDPOINT, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("url") or data.get("stream_url")
                    if url:
                        _log.info(f"[KHUSHI-FAST] Webserver cache hit for {vid}")
                        return url
    except Exception as e:
        _log.debug(f"[KHUSHI-FAST] Webserver miss for {vid}: {e}")
    return None


async def _smart_extract(vid: str) -> Optional[str]:
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, smart_extract_url, vid)
        if info and info.get("url"):
            _log.info(f"[KHUSHI-FAST] SmartYTDL extracted for {vid} via {info.get('client','?')}")
            return info["url"]
    except Exception as e:
        _log.debug(f"[KHUSHI-FAST] SmartYTDL extract failed for {vid}: {e}")
    return None


def _trigger_bg_cache(vid: str) -> None:
    if _file_exists(vid):
        return
    if vid in _bg_tasks:
        t = _bg_tasks[vid]
        if not t.done():
            return

    async def _bg():
        try:
            loop = asyncio.get_running_loop()
            fmt = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
            path = await loop.run_in_executor(None, smart_download, vid, _DOWNLOAD_DIR, fmt)
            if path:
                _log.info(f"[KHUSHI-FAST] BG cache done: {path}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _log.debug(f"[KHUSHI-FAST] BG cache failed for {vid}: {e}")
        finally:
            _bg_tasks.pop(vid, None)

    try:
        task = asyncio.get_event_loop().create_task(_bg())
        _bg_tasks[vid] = task
    except Exception:
        pass


async def fast_get_stream(vid: str) -> Optional[str]:
    """
    Get a playable stream URL or local file path for a YouTube video ID.

    Priority (millisecond resolution):
      1. Local file cache       → 0 ms (instant)
      2. Webserver cache        → ~10 ms (parallel race)
      3. SmartYTDL extract      → ~2-5 s (parallel race, already running)
      4. Full yt-dlp download   → ~10-25 s (last resort)
    """
    t0 = time.monotonic()

    cached = _file_exists(vid)
    if cached:
        _log.info(f"[KHUSHI-FAST] Local cache hit for {vid} in 0 ms")
        return cached

    tasks = [
        asyncio.create_task(_webserver_url(vid)),
        asyncio.create_task(_smart_extract(vid)),
    ]

    url = None
    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            if result:
                url = result
                break
        except Exception:
            pass

    for t in tasks:
        if not t.done():
            t.cancel()

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if url:
        _log.info(f"[KHUSHI-FAST] Stream URL ready in {elapsed_ms} ms for {vid}")
        _trigger_bg_cache(vid)
        return url

    _log.warning(f"[KHUSHI-FAST] URL methods failed for {vid}, doing full download...")
    loop = asyncio.get_running_loop()
    fmt = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
    path = await loop.run_in_executor(None, smart_download, vid, _DOWNLOAD_DIR, fmt)
    if path:
        total_ms = int((time.monotonic() - t0) * 1000)
        _log.info(f"[KHUSHI-FAST] Full download done in {total_ms} ms: {path}")
    return path


async def search_youtube(query: str, limit: int = 5) -> List[Dict]:
    """
    Search YouTube and return a list of results with title, duration, url, thumbnail.
    """
    try:
        results = VideosSearch(query, limit=limit)
        data = await results.next()
        items = data.get("result") or []
        out = []
        for item in items:
            out.append({
                "title":     item.get("title") or "Unknown",
                "duration":  item.get("duration") or "0:00",
                "url":       item.get("link") or "",
                "vid_id":    _extract_video_id(item.get("link") or ""),
                "thumbnail": ((item.get("thumbnails") or [{}])[0].get("url") or "").split("?")[0],
                "channel":   (item.get("channel") or {}).get("name") or "Unknown",
                "views":     (item.get("viewCount") or {}).get("short") or "0",
            })
        return out
    except Exception as e:
        _log.warning(f"[KHUSHI-FAST] YouTube search failed: {e}")
        return []


async def search_and_stream(query: str) -> Optional[Tuple[str, Dict]]:
    """
    Search YouTube for a query, pick the top result, and return (stream_url_or_path, info_dict).
    Returns None if nothing found or stream extraction fails.
    """
    results = await search_youtube(query, limit=1)
    if not results:
        _log.warning(f"[KHUSHI-FAST] No results for query: {query}")
        return None

    top = results[0]
    vid = top["vid_id"]
    if not vid:
        return None

    _log.info(f"[KHUSHI-FAST] search_and_stream: '{query}' → {top['title']} ({vid})")
    stream = await fast_get_stream(vid)
    if not stream:
        return None

    return stream, top


__all__ = [
    "fast_get_stream",
    "search_youtube",
    "search_and_stream",
]
