import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from KHUSHI.utils.database import is_on_off
from KHUSHI.utils.downloader import download_audio_concurrent, extract_video_id, fast_get_stream, yt_dlp_download
from KHUSHI.utils.errors import capture_internal_err
from KHUSHI.utils.formatters import time_to_seconds
from KHUSHI.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL
from KHUSHI.utils.yt_api import yt_api_search, yt_api_video_details, is_api_available, _seconds_to_min

_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()


def _ydl_base_opts() -> Dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "mweb", "android_vr"],
                "skip": ["hls", "translated_subs"],
            }
        },
        "http_headers": {
            "User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)",
        },
    }


def _extract_info_sync(link: str, opts: Optional[Dict] = None) -> Optional[Dict]:
    final_opts = _ydl_base_opts()
    if opts:
        final_opts.update(opts)
    with yt_dlp.YoutubeDL(final_opts) as ydl:
        return ydl.extract_info(link, download=False)


async def _extract_info(link: str, opts: Optional[Dict] = None) -> Optional[Dict]:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_extract_info_sync, link, opts), timeout=YTDLP_TIMEOUT)
    except Exception:
        return None


def _pick_stream_url(info: Dict) -> Optional[str]:
    if not info:
        return None
    if info.get("url"):
        return info["url"]
    requested_downloads = info.get("requested_downloads") or []
    if len(requested_downloads) == 1 and requested_downloads[0].get("url"):
        return requested_downloads[0]["url"]
    requested_formats = info.get("requested_formats") or []
    if len(requested_formats) == 1 and requested_formats[0].get("url"):
        return requested_formats[0]["url"]
    return None


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()
    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    # ── Check MongoDB persistent search cache (survives restarts) ─────────────
    try:
        from KHUSHI.utils.url_cache import get_search as _get_search, put_search as _put_search
        mongo_hit = await _get_search(key)
        if mongo_hit:
            async with _cache_lock:
                _cache[key] = (now, mongo_hit)
            return mongo_hit
    except Exception:
        _get_search = None
        _put_search = None

    result = []

    if is_api_available():
        try:
            api_results = await yt_api_search(query, max_results=5)
            if api_results:
                result = _normalize_api_results(api_results)
        except Exception:
            pass

    if not result:
        try:
            data = await VideosSearch(query, limit=1).next()
            result = data.get("result", [])
        except Exception:
            result = []

    # Final layer: Invidious search — works when both yt-dlp and youtubesearchpython
    # are blocked or rate-limited (different IPs/infrastructure).
    if not result:
        try:
            from KHUSHI.utils.ytdl_smart import _invidious_search
            result = await asyncio.to_thread(_invidious_search, query, 5)
        except Exception:
            result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)
        try:
            if _put_search:
                import asyncio as _asyncio
                _asyncio.create_task(_put_search(key, result))
        except Exception:
            pass
    return result


def _normalize_api_results(api_results: List[Dict]) -> List[Dict]:
    normalized = []
    for r in api_results:
        dur_str = r.get("duration", "0:00")
        parts = dur_str.split(":")
        yt_dur = f"{parts[0]}:{parts[1]}" if len(parts) == 2 else dur_str
        normalized.append(
            {
                "id": r.get("id", ""),
                "title": r.get("title", "Unknown"),
                "duration": yt_dur,
                "thumbnails": [{"url": r.get("thumb", "")}],
                "channel": {"name": r.get("channel", "")},
                "link": r.get("url", f"https://www.youtube.com/watch?v={r.get('id', '')}"),
                "thumbnail": r.get("thumb", ""),
                "viewCount": {"short": ""},
            }
        )
    return normalized


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            if res:
                return res[0]

            def _entry_to_info(e: Dict) -> Dict:
                return {
                    "id": e.get("id", ""),
                    "title": e.get("title", "Unknown"),
                    "duration": e.get("duration_string") or _seconds_to_min(int(e.get("duration") or 0)),
                    "thumbnails": [{"url": e.get("thumbnail", "")}],
                    "channel": {"name": e.get("uploader", "")},
                    "link": e.get("webpage_url", ""),
                    "thumbnail": e.get("thumbnail", ""),
                    "viewCount": {"short": ""},
                }

            # Fallback 1: yt-dlp ytsearch1 — works when Invidious/youtubesearchpython fail
            info = await _extract_info(f"ytsearch1:{q}", {"skip_download": True, "default_search": "ytsearch"})
            entries = (info or {}).get("entries") or []
            for e in entries:
                if e and e.get("id"):
                    return _entry_to_info(e)

            # Fallback 2: ytsearch5 — broader recall when single result fails
            info = await _extract_info(f"ytsearch5:{q}", {"skip_download": True, "default_search": "ytsearch"})
            entries = (info or {}).get("entries") or []
            for e in entries:
                if e and e.get("id"):
                    return _entry_to_info(e)

            # Fallback 3: ytsearch5 with "song" hint — disambiguates obscure titles
            info = await _extract_info(f"ytsearch5:{q} song", {"skip_download": True, "default_search": "ytsearch"})
            entries = (info or {}).get("entries") or []
            for e in entries:
                if e and e.get("id"):
                    return _entry_to_info(e)

            # Fallback 4: Invidious public search API — different infrastructure
            # entirely, bypasses YouTube/yt-dlp blocks. Bulletproof last resort.
            try:
                from KHUSHI.utils.ytdl_smart import _invidious_search
                inv_results = await asyncio.to_thread(_invidious_search, q, 5)
                for r in inv_results:
                    if r and r.get("id"):
                        return r
            except Exception:
                pass

            # Fallback 5: Invidious search with "song" hint
            try:
                from KHUSHI.utils.ytdl_smart import _invidious_search
                inv_results = await asyncio.to_thread(_invidious_search, f"{q} song", 5)
                for r in inv_results:
                    if r and r.get("id"):
                        return r
            except Exception:
                pass

            return None
        # URL path: try VideosSearch first, fall back to yt-dlp extract
        try:
            data = await VideosSearch(q, limit=1).next()
            result = data.get("result", [])
            if result:
                return result[0]
        except Exception:
            pass
        info = await _extract_info(q, {"skip_download": True})
        if info:
            secs = int(info.get("duration") or 0)
            return {
                "id": info.get("id", ""),
                "title": info.get("title", "Unknown"),
                "duration": _seconds_to_min(secs),
                "thumbnails": [{"url": info.get("thumbnail", "")}],
                "channel": {"name": info.get("uploader", "")},
                "link": info.get("webpage_url", q),
                "thumbnail": info.get("thumbnail", ""),
                "viewCount": {"short": ""},
            }
        return None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        info = await _extract_info(self._prepare_link(link), {"skip_download": True})
        return bool(info and info.get("is_live"))

    async def check_live(self, link: str) -> bool:
        """
        Fast live-stream detector.
        - Instant pattern check for /live/ and /shorts/ URLs (no network call).
        - Falls back to yt-dlp is_live() only for ambiguous watch URLs.
        """
        if "/live/" in link or "youtube.com/live" in link:
            return True
        try:
            return await self.is_live(link)
        except Exception:
            return False

    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        prepared = self._prepare_link(link, videoid)
        info = None
        if is_api_available():
            try:
                vid = extract_video_id(prepared)
                if vid:
                    api_info = await yt_api_video_details(vid)
                    if api_info:
                        title = api_info.get("title", "")
                        dt = api_info.get("duration")
                        ds = int(api_info.get("duration_sec") or time_to_seconds(dt) or 0)
                        thumb = (api_info.get("thumb") or "").split("?")[0]
                        return title, dt, ds, thumb, api_info.get("id", vid)
            except Exception:
                pass
        info = await self._fetch_video_info(prepared)
        if not info:
            return "", None, 0, "", ""
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0] if info else ""

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        info = await _extract_info(
            self._prepare_link(link, videoid),
            {
                "format": "best[height<=?720][width<=?1280]/best",
                "skip_download": True,
            },
        )
        stream_url = _pick_stream_url(info or {})
        return (1, stream_url) if stream_url else (0, "Unable to fetch stream URL")

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        info = await _extract_info(
            link,
            {
                "extract_flat": "in_playlist",
                "skip_download": True,
                "playlistend": limit,
            },
        )
        entries = info.get("entries", []) if info else []
        items = []
        for entry in entries[:limit]:
            vid = entry.get("id")
            if vid:
                items.append(vid)
        return items

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared = self._prepare_link(link, videoid)
        info = await self._fetch_video_info(prepared)
        if not info:
            ydl_info = await _extract_info(prepared, {"skip_download": True})
            if not ydl_info:
                raise ValueError("Track not found")
            thumb = (ydl_info.get("thumbnail") or "").split("?")[0]
            duration_val = ydl_info.get("duration")
            details = {
                "title": ydl_info.get("title", ""),
                "link": ydl_info.get("webpage_url", prepared),
                "vidid": ydl_info.get("id", ""),
                "duration_min": str(duration_val) if isinstance(duration_val, str) else None,
                "thumb": thumb,
            }
            return details, ydl_info.get("id", "")
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", prepared),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration") if isinstance(info.get("duration"), str) else None,
            "thumb": thumb,
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()
        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        opts = {
            "quiet": True,
            "nocheckcertificate": True,
            "source_address": "0.0.0.0",
            "extractor_args": {
                "youtube": {
                    "player_client": ["tv", "web_embedded", "web_creator", "android_vr"],
                    "skip": ["hls", "translated_subs"],
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/538.1 (KHTML, like Gecko) Version/6.0 TV Safari/538.1",
            },
        }
        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.wait_for(asyncio.to_thread(ydl.extract_info, link, False), timeout=YTDLP_TIMEOUT)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append(
                        {
                            "format": fmt["format"],
                            "filesize": size,
                            "format_id": fmt["format_id"],
                            "ext": fmt["ext"],
                            "format_note": fmt["format_note"],
                            "yturl": link,
                        }
                    )
        except Exception:
            pass

        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)

        if songvideo:
            p = await yt_dlp_download(link, type="song_video", format_id=format_id, title=title)
            return (p, True) if p else (None, None)

        if songaudio:
            p = await yt_dlp_download(link, type="song_audio", format_id=format_id, title=title)
            return (p, True) if p else (None, None)

        if video:
            # Live streams have to use the URL — they have no fixed length.
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                raise ValueError("Unable to fetch live stream link")
            # Always download the file for /vplay. Streaming a googlevideo
            # signed URL directly via PyTgCalls/ffmpeg is extremely fragile —
            # the connection is dropped after ~15-30 s, the video may be
            # adaptive (video-only, no audio), and the URL can rotate. The
            # local file path is far more reliable and lets ffprobe verify
            # the full duration before we hand it to PyTgCalls.
            p = await yt_dlp_download(link, type="video")
            return (p, True) if p else (None, None)

        vid = extract_video_id(link)
        p = await fast_get_stream(vid)
        if p:
            is_local = not p.startswith("http")
            return (p, is_local)
        return (None, None)
