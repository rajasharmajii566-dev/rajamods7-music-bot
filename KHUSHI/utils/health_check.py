import asyncio
import os
import sys
import re
import time
import tempfile
import threading
import psutil
import yt_dlp
import requests
from urllib.parse import urlparse, parse_qs
from flask import Flask, jsonify, send_from_directory, request, Response, send_file

# ── SmartYTDL import ──────────────────────────────────────────────────────────
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from KHUSHI.utils.ytdl_smart import smart_extract_url, smart_download
from KHUSHI.utils.internal_secret import get_secret

app = Flask(__name__)

# ── CORS — allow anyone to use these APIs from any bot/server ─────────────────
try:
    from flask_cors import CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
except Exception:
    @app.after_request
    def _add_cors(response):
        response.headers["Access-Control-Allow-Origin"]  = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

_INTERNAL_KEY = get_secret()   # random per-process, never logged
_boot_time = time.time()

WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
_DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'downloads')
os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
_ytdl_locks: dict = {}
_ytdl_lock_guard = threading.Lock()


def _sec_to_min(s):
    if not s:
        return "0:00"
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def _url_still_valid(data):
    try:
        exp = parse_qs(urlparse(data.get("url", "")).query).get("expire", [None])[0]
        if exp:
            return time.time() < int(exp) - 300
    except Exception:
        pass
    return time.time() - data.get("ts", 0) < 3600


def _fetch_stream(vid):
    """
    Fetch YouTube stream URL using SmartYTDL — adaptive, permanent bypass.
    Tries cached best client first, then parallel-probes all known clients.
    """
    info = smart_extract_url(vid)
    if not info:
        return None
    dur = info.get("duration", 0)
    return {
        "url":      info["url"],
        "ext":      info.get("ext", "m4a"),
        "title":    info.get("title", "Unknown"),
        "channel":  info.get("channel", ""),
        "duration": _sec_to_min(dur),
        "seconds":  dur,
        "thumb":    f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
        "ts":       time.time(),
    }


# ── Trending cache ───────────────────────────────────────────────
_trending_cache = {"data": [], "ts": 0}
_CACHE_TTL = 1800

TRENDING_QUERIES = [
    ("Hindi",         "ytsearch10:hindi songs trending 2025"),
    ("Punjabi",       "ytsearch10:punjabi songs trending 2025"),
    ("Bollywood",     "ytsearch10:bollywood hits 2025"),
    ("International", "ytsearch10:top hits 2025 pop english"),
]


def _fetch_trending():
    results = []
    ydl_opts = {
        "quiet": True, "no_warnings": True,
        "extract_flat": True, "skip_download": True,
        "ignoreerrors": True,
    }
    for category, query in TRENDING_QUERIES:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                entries = info.get("entries", []) if info else []
                for e in entries:
                    if not e:
                        continue
                    vid = e.get("id") or e.get("url", "")
                    if not vid or len(vid) != 11:
                        continue
                    results.append({
                        "id":       vid,
                        "title":    e.get("title", "Unknown"),
                        "channel":  e.get("channel") or e.get("uploader", ""),
                        "duration": e.get("duration_string") or _sec_to_min(e.get("duration", 0)),
                        "thumb":    f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                        "category": category,
                    })
        except Exception:
            pass
    return results


def get_trending():
    now = time.time()
    if now - _trending_cache["ts"] > _CACHE_TTL or not _trending_cache["data"]:
        try:
            data = _fetch_trending()
            if data:
                _trending_cache["data"] = data
                _trending_cache["ts"] = now
        except Exception:
            pass
    return _trending_cache["data"]


# ── Stream URL cache ─────────────────────────────────────────────
_stream_cache = {}
_stream_lock  = threading.Lock()


def _get_stream_data(vid, force_refresh=False):
    if not force_refresh:
        with _stream_lock:
            cached = _stream_cache.get(vid)
        if cached and _url_still_valid(cached):
            return cached
    data = _fetch_stream(vid)
    if data:
        with _stream_lock:
            _stream_cache[vid] = data
    return data


# ── Routes ───────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/api/status')
def api_status():
    try:
        from KHUSHI.misc import db, _boot_
        boot_time = _boot_
    except Exception:
        db = {}
        boot_time = _boot_time

    chats_data = []
    for chat_id, queue in db.items():
        if not queue:
            continue
        cur = queue[0]
        vid = str(cur.get("vidid", ""))
        thumb = f"https://img.youtube.com/vi/{vid}/mqdefault.jpg" if len(vid) == 11 else ""
        user_id = cur.get("user_id", 0)
        chats_data.append({
            "chat_id": chat_id,
            "current": {
                "title":      cur.get("title", "Unknown"),
                "duration":   cur.get("dur", "0:00"),
                "played":     cur.get("played", 0),
                "seconds":    cur.get("seconds", 0),
                "by":         cur.get("by", "Unknown"),
                "user_id":    user_id,
                "tg_link":    f"tg://user?id={user_id}" if user_id else "",
                "streamtype": cur.get("streamtype", "youtube"),
                "vidid":      vid,
                "thumbnail":  thumb,
            },
            "queue_count": max(len(queue) - 1, 0),
            "queue": [
                {
                    "title":    t.get("title", "Unknown"),
                    "duration": t.get("dur", "0:00"),
                    "by":       t.get("by", "Unknown"),
                    "vidid":    str(t.get("vidid", "")),
                    "thumb":    f"https://img.youtube.com/vi/{str(t.get('vidid',''))}/default.jpg"
                                if len(str(t.get("vidid", ""))) == 11 else "",
                }
                for t in queue[1:8]
            ],
        })

    try:
        cpu     = psutil.cpu_percent(interval=None)
        ram     = psutil.virtual_memory()
        ram_used  = f"{ram.used // (1024**2)} MB"
        ram_total = f"{ram.total // (1024**2)} MB"
        ram_pct   = round(ram.percent, 1)
    except Exception:
        cpu, ram_used, ram_total, ram_pct = 0, "N/A", "N/A", 0

    up = int(time.time() - boot_time)
    h, rem = divmod(up, 3600)
    m, s   = divmod(rem, 60)

    return jsonify({
        "status":       "online",
        "uptime":       f"{h}h {m}m {s}s",
        "active_chats": len(chats_data),
        "cpu":          cpu,
        "ram_used":     ram_used,
        "ram_total":    ram_total,
        "ram_percent":  ram_pct,
        "chats":        chats_data,
    })


@app.route('/api/trending')
def api_trending():
    data = get_trending()
    return jsonify({"songs": data, "cached": bool(data)})


@app.route('/api/yturl')
def api_yturl():
    """
    Internal bot API: returns stream URL for a YouTube video.
    Uses android_vr client — no cookies required.
    GET /api/yturl?v=VIDEO_ID&key=INTERNAL_KEY
    """
    vid = request.args.get("v", "").strip()
    key = request.args.get("key", "").strip()

    if not vid or len(vid) != 11:
        return jsonify({"error": "Invalid video id"}), 400

    if key != _INTERNAL_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = _get_stream_data(vid)
        if not data or not data.get("url"):
            return jsonify({"error": "Could not fetch stream URL"}), 500
        return jsonify({
            "url":      data["url"],
            "ext":      data.get("ext", "m4a"),
            "title":    data["title"],
            "channel":  data["channel"],
            "duration": data["duration"],
            "seconds":  data["seconds"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/stream')
def api_stream():
    vid = request.args.get("v", "").strip()
    if not vid or len(vid) != 11:
        return jsonify({"error": "Invalid video id"}), 400
    try:
        data = _get_stream_data(vid)
        if not data:
            return jsonify({"error": "Could not fetch stream"}), 500
        return jsonify({
            "title":    data["title"],
            "channel":  data["channel"],
            "duration": data["duration"],
            "seconds":  data["seconds"],
            "thumb":    data["thumb"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/play')
def api_play():
    """
    Bot-style play API — accepts song name, YouTube URL, or video ID.
    Returns full metadata + direct stream URL + audio proxy URL.

    Params:
      q  — song name / search query / YouTube URL  (required if v not given)
      v  — YouTube video ID (11 chars)              (required if q not given)
    """
    q   = request.args.get("q", "").strip()
    vid = request.args.get("v", "").strip()

    if not q and not vid:
        return jsonify({
            "error": "Provide either ?q=song+name or ?v=VIDEO_ID",
            "usage": "GET /api/play?q=Arijit+Singh+tum+hi+ho"
        }), 400

    # ── Step 1: resolve video ID ─────────────────────────────────
    if not vid:
        # Check if q is a YouTube URL → extract video ID
        yt_patterns = [
            r"(?:v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/live/)([A-Za-z0-9_-]{11})"
        ]
        for pat in yt_patterns:
            m = re.search(pat, q)
            if m:
                vid = m.group(1)
                break

    if not vid:
        # Search YouTube for top result
        try:
            ydl_opts = {
                "quiet": True, "no_warnings": True,
                "extract_flat": True, "skip_download": True,
                "ignoreerrors": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{q}", download=False)
                entries = info.get("entries", []) if info else []
                for e in (entries or []):
                    if e and e.get("id") and len(e["id"]) == 11:
                        vid = e["id"]
                        break
        except Exception as e:
            return jsonify({"error": f"Search failed: {e}"}), 500

    if not vid or len(vid) != 11:
        return jsonify({"error": "Song not found on YouTube"}), 404

    # ── Step 2: get stream data (URL + metadata) ─────────────────
    try:
        data = _get_stream_data(vid)
        if not data:
            return jsonify({"error": "Could not fetch stream URL"}), 500

        base_url = request.host_url.rstrip("/")
        return jsonify({
            "id":          vid,
            "title":       data["title"],
            "channel":     data["channel"],
            "duration":    data["duration"],
            "seconds":     data["seconds"],
            "thumb":       data["thumb"],
            "youtube_url": f"https://www.youtube.com/watch?v={vid}",
            "stream_url":  data["url"],
            "audio_proxy": f"{base_url}/api/audio?v={vid}",
            "download":    f"{base_url}/api/download?v={vid}",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/audio')
def api_audio():
    """Proxy audio stream — fetches from YouTube CDN and streams to browser."""
    vid = request.args.get("v", "").strip()
    if not vid or len(vid) != 11:
        return jsonify({"error": "Invalid video id"}), 400
    try:
        data = _get_stream_data(vid)
        if not data:
            return jsonify({"error": "Could not fetch stream"}), 500

        stream_url = data["url"]
        ext = data.get("ext", "m4a")
        content_type = "audio/mp4" if ext in ("m4a", "mp4") else f"audio/{ext}"

        range_header = request.headers.get("Range")
        req_headers = {
            "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept":          "*/*",
            "Accept-Encoding": "identity",
            "Connection":      "keep-alive",
            "Referer":         "https://www.youtube.com/",
        }
        if range_header:
            req_headers["Range"] = range_header

        upstream = requests.get(stream_url, headers=req_headers, stream=True, timeout=30)

        if upstream.status_code in (400, 403, 410):
            upstream.close()
            data = _get_stream_data(vid, force_refresh=True)
            if not data:
                return jsonify({"error": "Could not refresh stream"}), 500
            stream_url = data["url"]
            upstream = requests.get(stream_url, headers=req_headers, stream=True, timeout=30)

        resp_headers = {
            "Content-Type":  upstream.headers.get("Content-Type", content_type),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }
        if "Content-Length" in upstream.headers:
            resp_headers["Content-Length"] = upstream.headers["Content-Length"]
        if "Content-Range" in upstream.headers:
            resp_headers["Content-Range"] = upstream.headers["Content-Range"]

        status_code = upstream.status_code

        def generate():
            for chunk in upstream.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        return Response(generate(), status=status_code, headers=resp_headers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/search')
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    try:
        ydl_opts = {
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch8:{q}", download=False)
            entries = info.get("entries", []) if info else []
            results = []
            for e in (entries or []):
                if not e:
                    continue
                vid = e.get("id") or ""
                if not vid or len(vid) != 11:
                    continue
                results.append({
                    "id":       vid,
                    "title":    e.get("title", "Unknown"),
                    "channel":  e.get("channel") or e.get("uploader", ""),
                    "duration": e.get("duration_string") or _sec_to_min(e.get("duration", 0)),
                    "thumb":    f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
                })
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e), "results": []}), 500


@app.route('/api/download')
def api_download():
    vid = request.args.get("v", "").strip()
    if not vid or len(vid) != 11:
        return jsonify({"error": "Invalid video id"}), 400
    try:
        tmp_dir = tempfile.mkdtemp()
        fmt = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
        path = smart_download(vid, tmp_dir, fmt)
        if not path:
            return jsonify({"error": "Download failed — all methods exhausted"}), 500
        ext = os.path.splitext(path)[1].lstrip('.')
        mime = "audio/mp4" if ext in ("m4a", "mp4") else f"audio/{ext}"
        # Try to get a nice filename from the stream info
        info = smart_extract_url(vid)
        title = (info.get("title", vid) if info else vid)
        safe_title = re.sub(r'[^\w\s\-\.]', '', title)[:80]
        filename = f"{safe_title}.{ext}"
        return send_file(path, mimetype=mime, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/ytdl')
def api_ytdl():
    """
    Internal API: download YouTube audio to local MP3 file via yt-dlp.
    Protected by internal random key — only the bot (same process) should call this.
    GET /api/ytdl?v=VIDEO_ID&key=INTERNAL_KEY
    Returns: {"path": "/abs/path/to/VIDEO_ID.mp3"}
    """
    vid = request.args.get("v", "").strip()
    key = request.args.get("key", "").strip()

    if not vid or len(vid) != 11:
        return jsonify({"error": "Invalid video id"}), 400
    if key != _INTERNAL_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    out_path = os.path.join(_DOWNLOAD_DIR, f"{vid}.mp3")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
        return jsonify({"path": out_path, "cached": True})

    with _ytdl_lock_guard:
        if vid not in _ytdl_locks:
            _ytdl_locks[vid] = threading.Lock()
        vid_lock = _ytdl_locks[vid]

    with vid_lock:
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            return jsonify({"path": out_path, "cached": True})

        # Use SmartYTDL — tries all clients, returns first success
        fmt = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
        try:
            path = smart_download(vid, _DOWNLOAD_DIR, fmt)
            if path:
                return jsonify({"path": path})
            return jsonify({"error": "All download methods failed"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            with _ytdl_lock_guard:
                _ytdl_locks.pop(vid, None)



@app.route('/api/nsfw')
def api_nsfw():
    """Proxy NSFW check to webserver or handle inline."""
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({
            "error": "url parameter required",
            "usage": "GET /api/nsfw?url=https://example.com/image.jpg",
            "by": "t.me/PGL_B4CHI"
        }), 400
    try:
        import io
        from PIL import Image
        resp = requests.get(url, timeout=12, stream=True)
        if resp.status_code != 200:
            return jsonify({"error": f"Could not fetch image: HTTP {resp.status_code}", "by": "t.me/PGL_B4CHI"}), 400
        content_type = resp.headers.get("Content-Type", "")
        if not any(ct in content_type for ct in ("image/", "application/octet-stream")):
            return jsonify({"error": "URL does not point to an image", "by": "t.me/PGL_B4CHI"}), 400
        image_bytes = b""
        for chunk in resp.iter_content(chunk_size=65536):
            image_bytes += chunk
            if len(image_bytes) > 5_000_000:
                break
        if not image_bytes:
            return jsonify({"error": "Empty image response", "by": "t.me/PGL_B4CHI"}), 400
        try:
            from nudenet import NudeDetector
            detector = NudeDetector()
            import tempfile as _tmpfile
            with _tmpfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img.save(tmp_path, "PNG")
            try:
                detections = detector.detect(tmp_path)
                EXPOSED = {"FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED",
                           "FEMALE_BREAST_EXPOSED", "ANUS_EXPOSED", "BUTTOCKS_EXPOSED"}
                COVERED = {"FEMALE_GENITALIA_COVERED", "FEMALE_BREAST_COVERED", "BUTTOCKS_COVERED"}
                labels = []
                is_nsfw = False
                for det in detections:
                    cls = det.get("class", "")
                    score = det.get("score", 0)
                    if cls in EXPOSED and score >= 0.50:
                        is_nsfw = True
                        labels.append({"label": cls, "confidence": round(score, 3)})
                    elif cls in COVERED and score >= 0.65:
                        is_nsfw = True
                        labels.append({"label": cls, "confidence": round(score, 3)})
                return jsonify({
                    "is_nsfw": is_nsfw,
                    "method": "nudenet",
                    "confidence": max((l["confidence"] for l in labels), default=0.0),
                    "labels": labels,
                    "by": "t.me/PGL_B4CHI"
                })
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception:
            return jsonify({"error": "Detection failed", "by": "t.me/PGL_B4CHI"}), 500
    except Exception as e:
        return jsonify({"error": str(e), "by": "t.me/PGL_B4CHI"}), 500


@app.route('/api/related')
def api_related():
    vid = request.args.get("v", "").strip()
    if not vid or len(vid) != 11:
        return jsonify({"results": []}), 400
    try:
        ydl_opts = {
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:related {vid}", download=False)
            entries = info.get("entries", []) if info else []
            results = []
            for e in (entries or []):
                if not e:
                    continue
                eid = e.get("id") or ""
                if not eid or len(eid) != 11 or eid == vid:
                    continue
                results.append({
                    "id":       eid,
                    "title":    e.get("title", "Unknown"),
                    "channel":  e.get("channel") or e.get("uploader", ""),
                    "duration": e.get("duration_string") or _sec_to_min(e.get("duration", 0)),
                    "thumb":    f"https://img.youtube.com/vi/{eid}/mqdefault.jpg",
                })
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"results": [], "error": str(e)}), 500


# ── API Documentation page ─────────────────────────────────────────────────────
def _get_api_docs_html():
    try:
        import sys as _sys
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        if repo_root not in _sys.path:
            _sys.path.insert(0, repo_root)
        from webserver import _API_DOCS_HTML
        return _API_DOCS_HTML
    except Exception:
        return "<h1>API Docs</h1><p>Could not load docs. Please check webserver.py</p>"


@app.route('/api')
def api_docs_main():
    base = request.host_url.rstrip("/")
    html = _get_api_docs_html().replace("https://yourbot.replit.dev", base)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route('/api/docs')
def api_docs_alias():
    base = request.host_url.rstrip("/")
    html = _get_api_docs_html().replace("https://yourbot.replit.dev", base)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ── Bot asyncio event loop (set from __main__.py) ──────────────────────────────
_bot_loop = None


def set_bot_loop(loop):
    """Register the bot's asyncio event loop so Flask threads can call async functions."""
    global _bot_loop
    _bot_loop = loop


def _run_async(coro, timeout=15):
    """Run an async coroutine from a sync Flask thread using the bot's event loop."""
    if _bot_loop is None:
        raise RuntimeError("Bot event loop not registered yet")
    import concurrent.futures
    future = asyncio.run_coroutine_threadsafe(coro, _bot_loop)
    return future.result(timeout=timeout)


def _get_db():
    from KHUSHI.misc import db
    return db


# ── VC Control Endpoints ────────────────────────────────────────────────────────

@app.route('/api/queue', methods=['GET'])
def api_queue():
    """
    View full queue for a chat.
    GET /api/queue?chat_id=-1001234567890
    Returns: { current: {...}, queue: [...], total: N }
    """
    chat_id = request.args.get("chat_id", "").strip()
    if not chat_id:
        return jsonify({"error": "chat_id required"}), 400
    try:
        chat_id = int(chat_id)
    except ValueError:
        return jsonify({"error": "Invalid chat_id"}), 400

    db = _get_db()
    queue = db.get(chat_id, [])
    if not queue:
        return jsonify({"current": None, "queue": [], "total": 0})

    def _fmt(t):
        vid = str(t.get("vidid", ""))
        return {
            "title":    t.get("title", "Unknown"),
            "duration": t.get("dur", "0:00"),
            "by":       t.get("by", "Unknown"),
            "vidid":    vid,
            "streamtype": t.get("streamtype", "audio"),
            "thumb": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg" if len(vid) == 11 else "",
        }

    cur = queue[0]
    vid = str(cur.get("vidid", ""))
    return jsonify({
        "current": {
            **_fmt(cur),
            "played":  cur.get("played", 0),
            "seconds": cur.get("seconds", 0),
        },
        "queue": [_fmt(t) for t in queue[1:]],
        "total": len(queue),
    })


@app.route('/api/pause', methods=['GET', 'POST'])
def api_pause():
    """
    Pause VC playback.
    GET/POST /api/pause?chat_id=-1001234567890
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    try:
        chat_id = int(str(chat_id).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id"}), 400
    try:
        from KHUSHI.core.call import JARVIS
        _run_async(JARVIS.pause_stream(chat_id))
        return jsonify({"ok": True, "action": "paused", "chat_id": chat_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/resume', methods=['GET', 'POST'])
def api_resume():
    """
    Resume VC playback.
    GET/POST /api/resume?chat_id=-1001234567890
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    try:
        chat_id = int(str(chat_id).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id"}), 400
    try:
        from KHUSHI.core.call import JARVIS
        _run_async(JARVIS.resume_stream(chat_id))
        return jsonify({"ok": True, "action": "resumed", "chat_id": chat_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/stop', methods=['GET', 'POST'])
def api_stop():
    """
    Stop VC and leave call.
    GET/POST /api/stop?chat_id=-1001234567890
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    try:
        chat_id = int(str(chat_id).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id"}), 400
    try:
        from KHUSHI.core.call import JARVIS
        _run_async(JARVIS.stop_stream(chat_id))
        return jsonify({"ok": True, "action": "stopped", "chat_id": chat_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/skip', methods=['GET', 'POST'])
def api_skip():
    """
    Skip current song to next in queue.
    GET/POST /api/skip?chat_id=-1001234567890
    Optional: ?count=2  to skip N songs
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    count   = int(request.args.get("count") or (request.json or {}).get("count", 1) or 1)
    try:
        chat_id = int(str(chat_id).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id"}), 400

    try:
        import random as _rand
        from KHUSHI.core.call import JARVIS
        from KHUSHI.utils.stream.autoclear import auto_clean

        db = _get_db()
        check = db.get(chat_id, [])
        if not check:
            return jsonify({"ok": False, "error": "Nothing playing"}), 400

        async def _do_skip():
            _check = db.get(chat_id, [])
            popped = None
            for _ in range(max(1, count)):
                if not _check:
                    break
                try:
                    popped = _check.pop(0)
                    if popped:
                        await auto_clean(popped)
                except Exception:
                    break

            if not _check:
                await JARVIS.stop_or_autoplay(chat_id, popped)
                return {"action": "stopped_queue_empty"}

            nxt = _check[0]
            queued = nxt["file"]
            streamtype = nxt.get("streamtype", "audio")
            video = str(streamtype) == "video"
            await JARVIS.skip_stream(chat_id, queued, video=video)
            return {
                "action":   "skipped",
                "now_playing": {
                    "title":    nxt.get("title", "Unknown"),
                    "duration": nxt.get("dur", "0:00"),
                    "by":       nxt.get("by", "Unknown"),
                    "vidid":    str(nxt.get("vidid", "")),
                }
            }

        result = _run_async(_do_skip())
        return jsonify({"ok": True, "chat_id": chat_id, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/loop', methods=['GET', 'POST'])
def api_loop():
    """
    Set loop count for current chat.
    GET/POST /api/loop?chat_id=-1001234567890&count=0
    count=0 means no loop, count=1+ means loop N times, count=-1 means infinite loop
    Returns: { ok, loop_count }
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    count   = request.args.get("count") or (request.json or {}).get("count", None)
    try:
        chat_id = int(str(chat_id).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id"}), 400

    try:
        from KHUSHI.utils.database import set_loop, get_loop

        async def _do():
            if count is None:
                current = await get_loop(chat_id)
                new = 0 if current != 0 else 1
            else:
                new = int(count)
            await set_loop(chat_id, new)
            return new

        new_count = _run_async(_do())
        return jsonify({"ok": True, "chat_id": chat_id, "loop_count": new_count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/shuffle', methods=['GET', 'POST'])
def api_shuffle():
    """
    Shuffle the queue for a chat.
    GET/POST /api/shuffle?chat_id=-1001234567890
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    try:
        chat_id = int(str(chat_id).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id"}), 400

    import random as _rand
    db = _get_db()
    queue = db.get(chat_id, [])
    if len(queue) < 3:
        return jsonify({"ok": False, "error": "Need at least 2 songs in queue to shuffle"}), 400

    playing = queue[0]
    rest = queue[1:]
    _rand.shuffle(rest)
    db[chat_id] = [playing] + rest
    return jsonify({"ok": True, "chat_id": chat_id, "queue_count": len(rest)})


@app.route('/api/seek', methods=['GET', 'POST'])
def api_seek():
    """
    Seek to position in current song (audio only).
    GET/POST /api/seek?chat_id=-1001234567890&seconds=60
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    seek_sec = request.args.get("seconds") or (request.json or {}).get("seconds")
    try:
        chat_id  = int(str(chat_id).strip())
        seek_sec = int(str(seek_sec).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id or seconds"}), 400

    try:
        db = _get_db()
        queue = db.get(chat_id, [])
        if not queue:
            return jsonify({"ok": False, "error": "Nothing playing"}), 400

        cur = queue[0]
        file_path = cur.get("file", "")
        total_sec = cur.get("seconds", 0)
        streamtype = cur.get("streamtype", "audio")
        mode = "video" if str(streamtype) == "video" else "audio"

        def _fmt_time(s):
            s = max(0, int(s))
            return f"{s // 60}:{s % 60:02d}"

        to_seek   = _fmt_time(seek_sec)
        to_end    = _fmt_time(total_sec)

        from KHUSHI.core.call import JARVIS
        _run_async(JARVIS.seek_stream(chat_id, file_path, to_seek, to_end, mode))

        db[chat_id][0]["played"] = seek_sec
        return jsonify({"ok": True, "chat_id": chat_id, "seeked_to": to_seek})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/speed', methods=['GET', 'POST'])
def api_speed():
    """
    Change playback speed.
    GET/POST /api/speed?chat_id=-1001234567890&speed=1.5
    Supported: 0.5, 0.75, 1.0, 1.25, 1.5, 2.0
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    speed   = request.args.get("speed") or (request.json or {}).get("speed", 1.0)
    try:
        chat_id = int(str(chat_id).strip())
        speed   = float(str(speed).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id or speed"}), 400

    allowed = {0.5, 0.75, 1.0, 1.25, 1.5, 2.0}
    if speed not in allowed:
        return jsonify({"error": f"Speed must be one of: {sorted(allowed)}"}), 400

    try:
        db = _get_db()
        queue = db.get(chat_id, [])
        if not queue:
            return jsonify({"ok": False, "error": "Nothing playing"}), 400

        cur = queue[0]
        file_path = cur.get("file", "")

        from KHUSHI.core.call import JARVIS
        _run_async(JARVIS.speedup_stream(chat_id, file_path, speed, queue))
        return jsonify({"ok": True, "chat_id": chat_id, "speed": speed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/volume', methods=['GET', 'POST'])
def api_volume():
    """
    Change VC volume (0–200).
    GET/POST /api/volume?chat_id=-1001234567890&level=80
    """
    chat_id = (request.args.get("chat_id") or (request.json or {}).get("chat_id", ""))
    level   = request.args.get("level") or (request.json or {}).get("level", 100)
    try:
        chat_id = int(str(chat_id).strip())
        level   = int(str(level).strip())
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid chat_id or level"}), 400

    if not 0 <= level <= 200:
        return jsonify({"error": "Volume level must be between 0 and 200"}), 400

    try:
        from KHUSHI.core.call import JARVIS
        from KHUSHI.utils.database import group_assistant

        async def _do():
            assistant = await group_assistant(JARVIS, chat_id)
            await assistant.change_volume_call(chat_id, level)

        _run_async(_do())
        return jsonify({"ok": True, "chat_id": chat_id, "volume": level})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/nowplaying', methods=['GET'])
def api_nowplaying():
    """
    Get currently playing song info for a chat.
    GET /api/nowplaying?chat_id=-1001234567890
    """
    chat_id = request.args.get("chat_id", "").strip()
    if not chat_id:
        return jsonify({"error": "chat_id required"}), 400
    try:
        chat_id = int(chat_id)
    except ValueError:
        return jsonify({"error": "Invalid chat_id"}), 400

    db = _get_db()
    queue = db.get(chat_id, [])
    if not queue:
        return jsonify({"playing": False, "current": None})

    cur = queue[0]
    vid = str(cur.get("vidid", ""))
    return jsonify({
        "playing": True,
        "current": {
            "title":      cur.get("title", "Unknown"),
            "duration":   cur.get("dur", "0:00"),
            "played":     cur.get("played", 0),
            "seconds":    cur.get("seconds", 0),
            "by":         cur.get("by", "Unknown"),
            "user_id":    cur.get("user_id", 0),
            "streamtype": cur.get("streamtype", "audio"),
            "vidid":      vid,
            "thumb": f"https://img.youtube.com/vi/{vid}/mqdefault.jpg" if len(vid) == 11 else "",
            "youtube_url": f"https://www.youtube.com/watch?v={vid}" if len(vid) == 11 else "",
        },
        "queue_count": max(len(queue) - 1, 0),
    })


def start_health_server():
    port = int(os.environ.get('PORT', 8080))
    threading.Thread(target=get_trending, daemon=True).start()
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False),
        daemon=True
    ).start()
