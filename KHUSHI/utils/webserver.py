"""
KHUSHI — Built-in aiohttp web server for the web player.
Serves KHUSHI/web/index.html and JSON API endpoints on the configured host:port.
"""

import asyncio
import logging
import os
import time
from typing import Optional

import aiohttp
from aiohttp import web

_log = logging.getLogger(__name__)

_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
_INDEX   = os.path.join(_WEB_DIR, "index.html")

# ── simple in-process cache for trending results (TTL = 30 min) ──────────────
_trending_cache: list = []
_trending_ts: float = 0.0
_TRENDING_TTL: float = 1800.0

# tracks in-progress audio downloads so we don't double-download
_audio_locks: dict = {}


# ── helpers ───────────────────────────────────────────────────────────────────

def _download_dir() -> str:
    try:
        from KHUSHI.core.dir import DOWNLOAD_DIR
        return DOWNLOAD_DIR
    except Exception:
        return os.path.join(os.getcwd(), "downloads")


def _find_audio(vid: str) -> Optional[str]:
    """Return a local audio file path if the video id was already downloaded."""
    d = _download_dir()
    for ext in ("m4a", "mp3", "webm", "opus"):
        p = os.path.join(d, f"{vid}.{ext}")
        if os.path.isfile(p):
            return p
    return None


_COMPILATION_KW = {
    "jukebox", "playlist", "non stop", "nonstop", "mashup",
    "part 1", "part 2", "part-1", "part-2", "vol.", "vol ",
    "top 10", "top 20", "top 50", "best of", "hits of",
    "collection", "compilation", "audio jukebox", "video jukebox",
    "full album", "all songs", "back to back", "evergreen",
    "jhankar beats", "ringtone", "instrumental", "karaoke",
}


def _is_individual_song(song: dict) -> bool:
    """Return True if song looks like a proper individual track (not a long compilation)."""
    title = song.get("title", "").lower()
    for kw in _COMPILATION_KW:
        if kw in title:
            return False
    dur = song.get("duration", "")
    if dur:
        parts = dur.strip().split(":")
        try:
            if len(parts) == 3:
                total_min = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 2:
                total_min = int(parts[0])
            else:
                total_min = 0
            if total_min >= 12:
                return False
        except (ValueError, IndexError):
            pass
    return True


async def _fetch_search(query: str, limit: int = 10) -> list:
    """Search YouTube via the bot's existing search utilities."""
    try:
        from KHUSHI.utils.yt_api import yt_api_search
        results = await yt_api_search(query, max_results=limit)
        if results:
            return results
    except Exception:
        pass
    try:
        from KHUSHI.utils.fast_stream import search_youtube
        raw = await search_youtube(query, limit=limit)
        out = []
        for r in raw:
            vid_id = r.get("vid_id") or r.get("id", "")
            if not vid_id:
                continue
            out.append({
                "id":       vid_id,
                "title":    r.get("title", "Unknown"),
                "channel":  r.get("channel", ""),
                "duration": r.get("duration", ""),
                "thumb":    r.get("thumbnail", f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"),
            })
        return out
    except Exception:
        pass
    return []


async def _get_trending() -> list:
    global _trending_cache, _trending_ts
    now = time.monotonic()
    if _trending_cache and (now - _trending_ts) < _TRENDING_TTL:
        return _trending_cache

    queries = [
        ("hindi",         "new hindi song 2025 official video",    "hindi"),
        ("punjabi",       "new punjabi song 2025 official video",   "punjabi"),
        ("bollywood",     "bollywood hit song 2025 official audio", "bollywood"),
        ("romantic",      "romantic hindi song 2025",               "romantic"),
        ("international", "english pop hit 2025 official",          "international"),
    ]

    songs: list = []
    seen: set = set()

    async def _fetch(cat_id: str, q: str, cat_label: str):
        results = await _fetch_search(q, limit=15)
        for r in results:
            if r["id"] not in seen and _is_individual_song(r):
                seen.add(r["id"])
                songs.append({**r, "category": cat_id})

    await asyncio.gather(*[_fetch(c, q, l) for c, q, l in queries])

    if songs:
        _trending_cache = songs
        _trending_ts = now
    return songs


async def _download_audio(vid: str) -> Optional[str]:
    """Download audio for vid and return local file path (or None on failure)."""
    existing = _find_audio(vid)
    if existing:
        return existing

    lock = _audio_locks.get(vid)
    if lock is None:
        lock = asyncio.Lock()
        _audio_locks[vid] = lock

    async with lock:
        existing = _find_audio(vid)
        if existing:
            return existing
        try:
            loop = asyncio.get_running_loop()
            from KHUSHI.utils.ytdl_smart import smart_download, _AUDIO_FMT
            d = _download_dir()
            os.makedirs(d, exist_ok=True)
            path = await loop.run_in_executor(None, smart_download, vid, d, _AUDIO_FMT)
            return path if path and os.path.isfile(path) else None
        except Exception as e:
            _log.warning(f"[WebAPI] audio download failed for {vid}: {e}")
            return None
        finally:
            _audio_locks.pop(vid, None)


# ── static & health ───────────────────────────────────────────────────────────

async def _handle_index(request: web.Request) -> web.Response:
    try:
        with open(_INDEX, "r", encoding="utf-8") as f:
            html = f.read()
        return web.Response(text=html, content_type="text/html", charset="utf-8")
    except FileNotFoundError:
        return web.Response(text="<h1>Web player not found.</h1>",
                            content_type="text/html", status=404)


async def _handle_health(request: web.Request) -> web.Response:
    return web.Response(text="OK", content_type="text/plain")


async def _handle_static(request: web.Request) -> web.Response:
    filename = request.match_info.get("filename", "")
    path = os.path.join(_WEB_DIR, filename)
    if os.path.isfile(path) and os.path.abspath(path).startswith(os.path.abspath(_WEB_DIR)):
        return web.FileResponse(path)
    raise web.HTTPNotFound()


# ── API: /api/trending ────────────────────────────────────────────────────────

async def _api_trending(request: web.Request) -> web.Response:
    songs = await _get_trending()
    return web.json_response({"songs": songs})


# ── API: /api/suggested ───────────────────────────────────────────────────────

def _web_extract_artist(title: str):
    """Extract (clean_title, artist) from common patterns like 'Song - Artist' or 'Song | Artist'."""
    import re as _re
    for sep in [" - ", " – ", " — ", " | "]:
        if sep in title:
            parts = title.split(sep, 1)
            clean = parts[0].strip()
            artist_raw = _re.sub(r"[\(\[].+?[\)\]]", "", parts[1]).strip()
            artist_words = artist_raw.split()
            artist = " ".join(artist_words[:2]) if len(artist_words) > 2 else artist_raw
            return clean, artist
    return title.strip(), ""


async def _api_suggested(request: web.Request) -> web.Response:
    """Return songs related to the currently playing video (by video id or title)."""
    vid = request.rel_url.query.get("v", "").strip()
    title_hint = request.rel_url.query.get("title", "").strip()

    if not vid and not title_hint:
        return web.json_response({"songs": []})

    songs: list = []
    seen: set = {vid} if vid else set()

    # ── Priority 1: Invidious recommendedVideos (actual YouTube algorithm) ────
    if vid:
        try:
            from KHUSHI.utils.yt_api import yt_api_related_videos
            related = await yt_api_related_videos(vid, max_results=14)
            for r in related:
                rid = r.get("id", "")
                if rid and rid not in seen and _is_individual_song(r):
                    seen.add(rid)
                    songs.append(r)
        except Exception:
            pass

    if len(songs) >= 8:
        return web.json_response({"songs": songs[:10]})

    # ── Priority 2: Keyword search based on title ─────────────────────────────
    title = title_hint
    if title:
        clean_title, artist = _web_extract_artist(title)
        title_words = clean_title.split()
        first_word = title_words[0] if title_words else ""

        queries = []
        if artist:
            queries.append(f"{artist} best songs official")
            queries.append(f"{artist} new songs 2025")
        else:
            if first_word and len(first_word) > 2:
                queries.append(f"{first_word} songs official")
                queries.append(f"{first_word} new songs 2025")
        queries.append(f"songs similar to {clean_title}")
        queries.append(f"{clean_title} official audio")

        for q in queries:
            if len(songs) >= 10:
                break
            try:
                results = await _fetch_search(q, limit=10)
                for r in results:
                    if r["id"] not in seen and _is_individual_song(r):
                        seen.add(r["id"])
                        songs.append(r)
            except Exception:
                pass

        # Broader fallback if still nothing
        if not songs and clean_title:
            try:
                results = await _fetch_search(f"{clean_title} song", limit=12)
                for r in results:
                    if r["id"] not in seen and _is_individual_song(r):
                        seen.add(r["id"])
                        songs.append(r)
            except Exception:
                pass

    # ── Absolute last resort: trending ────────────────────────────────────────
    if not songs:
        trending = await _get_trending()
        return web.json_response({"songs": trending[:8]})

    return web.json_response({"songs": songs[:10]})


# ── API: /api/status ──────────────────────────────────────────────────────────

async def _api_status(request: web.Request) -> web.Response:
    try:
        from KHUSHI.misc import db
        from KHUSHI.core.call import JARVIS
        chats = []
        for chat_id in list(JARVIS.active_calls):
            queue = db.get(chat_id, [])
            if not queue:
                continue
            cur = queue[0]
            chats.append({
                "chat_id":     chat_id,
                "queue_count": len(queue) - 1,
                "current": {
                    "title":     cur.get("title", ""),
                    "duration":  cur.get("dur", ""),
                    "thumbnail": f"https://img.youtube.com/vi/{cur.get('vidid','')}/mqdefault.jpg",
                    "vidid":     cur.get("vidid", ""),
                    "by":        cur.get("by", ""),
                },
            })
        return web.json_response({"chats": chats, "active_count": len(chats)})
    except Exception as e:
        return web.json_response({"chats": [], "error": str(e)})


# ── API: /api/search ──────────────────────────────────────────────────────────

async def _api_search(request: web.Request) -> web.Response:
    q = request.rel_url.query.get("q", "").strip()
    if not q:
        return web.json_response({"results": [], "error": "missing query"})
    results = await _fetch_search(q, limit=12)
    return web.json_response({"results": results})


# ── API: /api/stream (metadata) ───────────────────────────────────────────────

async def _api_stream(request: web.Request) -> web.Response:
    vid = request.rel_url.query.get("v", "").strip()
    if not vid:
        return web.json_response({"error": "missing v"}, status=400)
    info = {
        "id":    vid,
        "thumb": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
        "url":   f"https://www.youtube.com/watch?v={vid}",
    }
    try:
        results = await _fetch_search(f"https://www.youtube.com/watch?v={vid}", limit=1)
        if results:
            info.update(results[0])
    except Exception:
        pass
    return web.json_response(info)


# ── API: /api/audio ───────────────────────────────────────────────────────────

async def _api_audio(request: web.Request) -> web.Response:
    vid = request.rel_url.query.get("v", "").strip()
    if not vid:
        return web.Response(status=400, text="missing v")

    is_probe = request.method == "HEAD" or request.rel_url.query.get("_probe")

    existing = _find_audio(vid)
    if not existing:
        if is_probe:
            # Signal to client: still downloading, retry later
            return web.Response(status=503, text="downloading")
        existing = await _download_audio(vid)

    if not existing or not os.path.isfile(existing):
        return web.Response(status=404, text="audio not found")

    ext = existing.rsplit(".", 1)[-1].lower()
    mime = {
        "m4a": "audio/mp4",
        "mp3": "audio/mpeg",
        "webm": "audio/webm",
        "opus": "audio/ogg",
    }.get(ext, "audio/mpeg")

    if is_probe:
        return web.Response(
            status=200,
            headers={"Content-Type": mime, "Accept-Ranges": "bytes"},
        )

    file_size = os.path.getsize(existing)
    range_header = request.headers.get("Range")

    if range_header:
        try:
            byte_range = range_header.strip().replace("bytes=", "")
            start_s, end_s = byte_range.split("-", 1)
            start = int(start_s) if start_s else 0
            end   = int(end_s)   if end_s   else file_size - 1
            end   = min(end, file_size - 1)
            length = end - start + 1

            def _read_chunk(path, s, l):
                with open(path, "rb") as f:
                    f.seek(s)
                    return f.read(l)

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _read_chunk, existing, start, length)
            return web.Response(
                status=206,
                body=data,
                headers={
                    "Content-Type":  mime,
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                },
            )
        except Exception:
            pass

    return web.FileResponse(
        existing,
        headers={
            "Content-Type":  mime,
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        },
    )


# ── API: /api/proxy ───────────────────────────────────────────────────────────
# Ultra-fast audio proxy: streams YouTube CDN URL directly to the browser.
# No local download needed — audio starts in < 1 second.
# Supports byte-range requests for seeking.

_proxy_url_cache: dict = {}   # vid → (cdn_url, ext, expires_at)
_proxy_extract_locks: dict = {}


def _get_proxy_cached(vid: str):
    entry = _proxy_url_cache.get(vid)
    if not entry:
        return None
    cdn_url, ext, exp = entry
    if time.time() < exp:
        return cdn_url, ext
    _proxy_url_cache.pop(vid, None)
    return None


async def _get_proxy_url(vid: str):
    """Return (cdn_url, ext) — uses in-process cache, then SmartYTDL."""
    hit = _get_proxy_cached(vid)
    if hit:
        return hit

    lock = _proxy_extract_locks.get(vid)
    if lock is None:
        lock = asyncio.Lock()
        _proxy_extract_locks[vid] = lock

    async with lock:
        hit = _get_proxy_cached(vid)
        if hit:
            return hit
        try:
            loop = asyncio.get_running_loop()
            from KHUSHI.utils.ytdl_smart import smart_extract_url
            info = await loop.run_in_executor(None, smart_extract_url, vid)
            if info and info.get("url"):
                cdn_url = info["url"]
                ext = info.get("ext", "m4a")
                try:
                    from urllib.parse import urlparse, parse_qs
                    exp_param = parse_qs(urlparse(cdn_url).query).get("expire", [None])[0]
                    expires_at = int(exp_param) - 120 if exp_param else time.time() + 3600
                except Exception:
                    expires_at = time.time() + 3600
                _proxy_url_cache[vid] = (cdn_url, ext, expires_at)
                return cdn_url, ext
        except Exception as e:
            _log.warning(f"[Proxy] URL extraction failed for {vid}: {e}")
        finally:
            _proxy_extract_locks.pop(vid, None)
    return None


async def _api_proxy(request: web.Request) -> web.Response:
    """
    Fast-stream proxy: pipes YouTube CDN audio directly to the browser.
    Falls through to local file if already downloaded.
    Supports Range requests for seeking.
    """
    vid = request.rel_url.query.get("v", "").strip()
    if not vid:
        return web.Response(status=400, text="missing v")

    # ── Try local file first (instant) ────────────────────────────────────────
    existing = _find_audio(vid)
    if existing:
        ext = existing.rsplit(".", 1)[-1].lower()
        mime = {
            "m4a": "audio/mp4", "mp3": "audio/mpeg",
            "webm": "audio/webm", "opus": "audio/ogg",
        }.get(ext, "audio/mpeg")
        return web.FileResponse(existing, headers={
            "Content-Type": mime,
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        })

    # ── Extract CDN URL ────────────────────────────────────────────────────────
    result = await _get_proxy_url(vid)
    if not result:
        return web.Response(status=503, text="stream unavailable")

    cdn_url, ext = result
    mime = {
        "m4a": "audio/mp4", "mp3": "audio/mpeg",
        "webm": "audio/webm", "opus": "audio/ogg",
    }.get(ext, "audio/mpeg")

    try:
        from KHUSHI.utils.ytdl_smart import get_cdn_headers
        cdn_headers = get_cdn_headers()
    except Exception:
        cdn_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; Oculus Quest 3) "
                "AppleWebKit/537.36 Chrome/124.0.6367.118 Mobile Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Origin":  "https://www.youtube.com",
        }

    req_headers = dict(cdn_headers)
    range_header = request.headers.get("Range")
    if range_header:
        req_headers["Range"] = range_header

    try:
        timeout = aiohttp.ClientTimeout(total=300, connect=8, sock_read=30)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(cdn_url, headers=req_headers) as cdn_resp:
                if cdn_resp.status not in (200, 206):
                    # CDN URL might be expired — remove from cache and retry
                    _proxy_url_cache.pop(vid, None)
                    return web.Response(status=502, text="CDN returned error")

                out_headers = {
                    "Content-Type":  mime,
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "no-cache",
                }
                cl = cdn_resp.headers.get("Content-Length")
                cr = cdn_resp.headers.get("Content-Range")
                if cl:
                    out_headers["Content-Length"] = cl
                if cr:
                    out_headers["Content-Range"] = cr

                response = web.StreamResponse(
                    status=cdn_resp.status,
                    headers=out_headers,
                )
                await response.prepare(request)

                CHUNK = 65536
                async for chunk in cdn_resp.content.iter_chunked(CHUNK):
                    await response.write(chunk)

                await response.write_eof()
                return response

    except asyncio.CancelledError:
        return web.Response(status=499, text="client disconnected")
    except Exception as e:
        _log.warning(f"[Proxy] Stream error for {vid}: {e}")
        # Remove stale cache entry
        _proxy_url_cache.pop(vid, None)
        return web.Response(status=503, text="proxy error")


# ── API: /api/video ───────────────────────────────────────────────────────────

async def _api_video(request: web.Request) -> web.Response:
    vid = request.rel_url.query.get("v", "").strip()
    if not vid:
        return web.Response(status=400, text="missing v")

    d = _download_dir()
    for ext in ("mp4", "webm", "mkv"):
        p = os.path.join(d, f"{vid}.{ext}")
        if os.path.isfile(p):
            return web.FileResponse(p, headers={"Accept-Ranges": "bytes"})

    return web.Response(status=404, text="video not found")


# ── API: /api/download ────────────────────────────────────────────────────────

async def _api_download(request: web.Request) -> web.Response:
    vid = request.rel_url.query.get("v", "").strip()
    if not vid:
        return web.Response(status=400, text="missing v")

    # ── Try local file first ──────────────────────────────────────────────────
    existing = _find_audio(vid)
    if not existing:
        existing = await _download_audio(vid)

    if existing and os.path.isfile(existing):
        ext = existing.rsplit(".", 1)[-1].lower()
        return web.FileResponse(
            existing,
            headers={"Content-Disposition": f'attachment; filename="{vid}.{ext}"'},
        )

    # ── Fallback: redirect to CDN URL so browser downloads directly ──────────
    # This ensures download always works even if local storage is full/slow.
    try:
        result = await _get_proxy_url(vid)
        if result:
            cdn_url, ext = result
            return web.HTTPFound(cdn_url)
    except Exception as e:
        _log.warning(f"[Download] CDN fallback failed for {vid}: {e}")

    return web.Response(status=503, text="download unavailable — try again")


# ── API: /api/related ─────────────────────────────────────────────────────────

async def _api_related(request: web.Request) -> web.Response:
    vid = request.rel_url.query.get("v", "").strip()
    if not vid:
        return web.json_response({"results": []})
    try:
        results = await _fetch_search(f"https://www.youtube.com/watch?v={vid}", limit=10)
        if not results:
            results = await _fetch_search("Hindi trending songs", limit=10)
        return web.json_response({"results": results})
    except Exception:
        return web.json_response({"results": []})


# ── App factory ───────────────────────────────────────────────────────────────

def _make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/",                  _handle_index)
    app.router.add_get("/health",            _handle_health)
    app.router.add_get("/api/trending",      _api_trending)
    app.router.add_get("/api/suggested",     _api_suggested)
    app.router.add_get("/api/status",        _api_status)
    app.router.add_get("/api/search",        _api_search)
    app.router.add_get("/api/stream",        _api_stream)
    app.router.add_get("/api/audio",         _api_audio)
    app.router.add_get("/api/proxy",         _api_proxy)
    app.router.add_get("/api/video",         _api_video)
    app.router.add_get("/api/download",      _api_download)
    app.router.add_get("/api/related",       _api_related)
    app.router.add_get("/static/{filename:.+}", _handle_static)
    app.router.add_get("/{filename:.+}",     _handle_static)
    return app


async def start_webserver(host: str, port: int) -> web.AppRunner:
    """Start the aiohttp web server and return the runner (for later cleanup).

    If the requested port is in use, automatically tries a list of common
    fallback ports so the web player never silently fails to start.
    Returns (runner, actual_port) via module-level BOUND_PORT variable.
    """
    try:
        from web_config import WEB_ENABLED
        if not WEB_ENABLED:
            _log.info("Web server disabled via web_config.WEB_ENABLED=False")
            return None
    except ImportError:
        pass

    # Ports to try in order: configured first, then common fallbacks
    _fallbacks = [port, 8080, 5000, 8000, 8008, 9000, 3000, 7000]
    _candidates = list(dict.fromkeys(_fallbacks))  # deduplicate, keep order

    app_obj = _make_app()
    runner = web.AppRunner(app_obj)
    await runner.setup()

    last_err = None
    for try_port in _candidates:
        try:
            site = web.TCPSite(runner, host, try_port)
            await site.start()
            global BOUND_PORT
            BOUND_PORT = try_port
            if try_port != port:
                _log.warning(
                    f"Port {port} was busy — web player bound to fallback port {try_port}. "
                    f"Update WEB_PORT={try_port} in your env or add a firewall rule for port {try_port}."
                )
            _log.info(f"Web player running on http://{host}:{try_port}")
            return runner
        except OSError as e:
            _log.debug(f"Port {try_port} in use ({e}), trying next…")
            last_err = e
            continue

    # All ports failed — log clearly and continue (bot still works without web)
    _log.error(
        f"Web player could NOT start — all candidate ports are busy: {_candidates}. "
        f"Free one of these ports or set WEB_ENABLED=false to suppress this error."
    )
    return None


# Actual port the server bound to (set by start_webserver after successful bind)
BOUND_PORT: int = 0
