"""
SmartYTDL — Permanent YouTube bypass using yt-dlp (2026 edition).

BYPASS LAYERS (tried in order):
  1. android_vr client  — YouTube's default jsless client, no PO token, no cookies
  2. web_safari client  — Requires Node.js for signature solving (also default)
  3. ios / android / mweb / web_creator / web — additional fallback clients
  4. Invidious public API (last resort — multiple instances)
  5. Cookie support  — set YOUTUBE_COOKIES_B64 env var (base64 cookies.txt)
  6. Proxy support   — set YTDL_PROXY env var (socks5://... or http://...)
"""

import base64
import json
import logging
import os
import queue
import random
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional
import yt_dlp

_log = logging.getLogger(__name__)

# ── Persistent best-client state file ────────────────────────────────────────
_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "cache", "best_yt_client.json"
)

# ── Node.js path detection ────────────────────────────────────────────────────
def _find_node() -> Optional[str]:
    path = shutil.which("node")
    if path:
        return path
    for p in ["/usr/bin/node", "/usr/local/bin/node", "/opt/homebrew/bin/node"]:
        if os.path.isfile(p):
            return p
    nix_dirs = [d for d in (os.environ.get("PATH", "").split(":")) if "nodejs" in d or "node" in d.lower()]
    for d in nix_dirs:
        candidate = os.path.join(d, "node")
        if os.path.isfile(candidate):
            return candidate
    return None


_NODE_PATH = _find_node()
if _NODE_PATH:
    _log.info(f"[SmartYTDL] Node.js found: {_NODE_PATH}")
else:
    _log.warning("[SmartYTDL] Node.js NOT found — web_safari client may fail, android_vr will still work")


def _js_runtimes() -> Dict:
    if _NODE_PATH:
        return {"node": {"path": _NODE_PATH}}
    return {}


# ── Proxy ─────────────────────────────────────────────────────────────────────
_PROXY = (
    os.environ.get("YTDL_PROXY")
    or os.environ.get("HTTPS_PROXY")
    or os.environ.get("HTTP_PROXY")
    or ""
)

# ── YouTube player clients (2026 verified working order) ──────────────────────
# Sources:
#   _DEFAULT_CLIENTS      = ['android_vr', 'web_safari']  (yt-dlp 2026.03.17)
#   _DEFAULT_JSLESS_CLIENTS = ['android_vr']
#   tv_embedded / ios_downgraded removed Jan 2026 — DO NOT USE
ALL_CLIENTS: List[str] = [
    "android_vr",    # PRIMARY — jsless, no PO token, works on cloud IPs
    "web_safari",    # SECONDARY — needs Node.js for signature, but reliable
    "ios",           # Good fallback — iPhone app UA
    "android",       # Android app client
    "mweb",          # Mobile web
    "web_creator",   # YouTube Studio — fewer restrictions
    "web",           # Desktop web (needs Node.js)
    "tv",            # Smart TV (may need PO token on some videos)
]

_CLIENT_UA: Dict[str, str] = {
    "android_vr": (
        "Mozilla/5.0 (Linux; Android 14; Oculus Quest 3) "
        "AppleWebKit/537.36 (KHTML, like Gecko) OculusBrowser/35.0.0 "
        "VR SamsungBrowser/4.0 Chrome/124.0.6367.118 Mobile Safari/537.36"
    ),
    "web_safari": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
    ),
    "ios": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)",
    "android": (
        "com.google.android.youtube/19.29.37 (Linux; U; Android 14; "
        "en_US; Pixel 8; Build/AP2A.240805.005; Cronet/113.0.5672.24)"
    ),
    "mweb": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "web_creator": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36"
    ),
    "web": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36"
    ),
    "tv": (
        "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/538.1 "
        "(KHTML, like Gecko) Version/6.0 TV Safari/538.1"
    ),
}
_DEFAULT_UA = _CLIENT_UA["android_vr"]

# Clients that work WITHOUT a JS runtime (Node.js not needed)
_JSLESS_CLIENTS = {"android_vr", "ios", "android", "mweb"}

# ── Invidious instances (fallback pool) ───────────────────────────────────────
_INVIDIOUS_INSTANCES = [
    "https://invidious.io.lol",
    "https://yewtu.be",
    "https://invidious.fdn.fr",
    "https://inv.nadeko.net",
    "https://invidious.privacyredirect.com",
    "https://inv.ggtyler.dev",
    "https://invidious.perennialte.ch",
    "https://invidious.private.coffee",
    "https://invidious.0011.lt",
    "https://vid.priv.au",
    "https://invidious.darkness.services",
    "https://yt.artemislena.eu",
    "https://invidious.nerdvpn.de",
]

# ── Instance failure tracking ─────────────────────────────────────────────────
_inst_lock = threading.Lock()
_inst_failed: Dict[str, float] = {}
_INST_FAIL_TTL = 600


def _alive_instances(pool: List[str]) -> List[str]:
    now = time.time()
    with _inst_lock:
        good = [i for i in pool if now - _inst_failed.get(i, 0) > _INST_FAIL_TTL]
        bad  = [i for i in pool if i not in good]
    random.shuffle(good)
    return good + bad


def _fail_instance(inst: str):
    with _inst_lock:
        _inst_failed[inst] = time.time()


# ── Cookie support ────────────────────────────────────────────────────────────
_cookie_cache: Optional[str] = None
_cookie_ts: float = 0.0
_COOKIE_TTL = 120


def _find_cookie_file() -> Optional[str]:
    global _cookie_cache, _cookie_ts
    now = time.time()
    if now - _cookie_ts < _COOKIE_TTL and _cookie_cache:
        if os.path.exists(_cookie_cache) and os.path.getsize(_cookie_cache) > 10:
            return _cookie_cache

    _cookie_ts = now

    b64 = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if b64:
        tmp = "/tmp/youtube_cookies.txt"
        try:
            with open(tmp, "wb") as f:
                f.write(base64.b64decode(b64))
            if os.path.getsize(tmp) > 10:
                _cookie_cache = tmp
                _log.info("[SmartYTDL] Using cookies from YOUTUBE_COOKIES_B64 env var")
                return tmp
        except Exception as e:
            _log.warning(f"[SmartYTDL] YOUTUBE_COOKIES_B64 decode failed: {e}")

    for path in [
        os.path.join(os.path.dirname(__file__), "..", "..", "youtube_cookies.txt"),
        os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt"),
        "/app/youtube_cookies.txt",
        "/app/cookies.txt",
        "/tmp/youtube_cookies.txt",
    ]:
        p = os.path.abspath(path)
        if os.path.exists(p) and os.path.getsize(p) > 10:
            _cookie_cache = p
            return p

    _cookie_cache = None
    return None


# ── Client registry ───────────────────────────────────────────────────────────
class _ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._best: Optional[str] = "android_vr"   # 2026 default — jsless, no PO token
        self._best_ts: float = 0.0
        self._failed: Dict[str, float] = {}
        self._FAIL_TTL = 900
        self._BEST_TTL = 1800
        self._DISK_TTL = 86400  # 24 hours — persist best client across restarts
        self._load_state()

    def _load_state(self) -> None:
        """Load best client from disk so it survives bot restarts."""
        try:
            if os.path.exists(_STATE_FILE):
                with open(_STATE_FILE, "r") as f:
                    data = json.load(f)
                client = data.get("best")
                ts = float(data.get("ts", 0.0))
                if client and client in ALL_CLIENTS:
                    if time.time() - ts < self._DISK_TTL:
                        self._best = client
                        self._best_ts = ts
                        _log.info(f"[SmartYTDL] Loaded best client from disk: '{client}'")
                    else:
                        _log.info("[SmartYTDL] Disk state expired, using default android_vr")
        except Exception as e:
            _log.debug(f"[SmartYTDL] Could not load state: {e}")

    def _save_state(self) -> None:
        """Persist best client to disk for faster startup after restart."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(_STATE_FILE)), exist_ok=True)
            with open(_STATE_FILE, "w") as f:
                json.dump({"best": self._best, "ts": self._best_ts}, f)
        except Exception as e:
            _log.debug(f"[SmartYTDL] Could not save state: {e}")

    def mark_ok(self, client: str):
        with self._lock:
            self._best = client
            self._best_ts = time.time()
            self._failed.pop(client, None)
        self._save_state()

    def mark_failed(self, client: str):
        with self._lock:
            self._failed[client] = time.time()
            if self._best == client:
                self._best = None

    def get_best(self) -> Optional[str]:
        with self._lock:
            if self._best and time.time() - self._best_ts < self._BEST_TTL:
                return self._best
            return None

    def ordered_clients(self) -> List[str]:
        now = time.time()
        with self._lock:
            best = self._best
            failed = {c for c, t in self._failed.items() if now - t < self._FAIL_TTL}
        result = []
        # android_vr is ALWAYS first — it's the primary jsless client for cloud IPs.
        # If it's not in the failed set, put it at position 0 regardless of 'best'.
        if "android_vr" not in failed:
            result.append("android_vr")
        # Remaining jsless clients go next; if one of them is 'best', put it after android_vr
        for c in ALL_CLIENTS:
            if c == "android_vr":
                continue
            if c in _JSLESS_CLIENTS and c not in failed:
                if c == best and best != "android_vr":
                    result.insert(1, c)
                else:
                    result.append(c)
        # If 'best' is android_vr and it's healthy, it's already at position 0.
        # If 'best' is something else but android_vr is healthy, still keep android_vr first.
        # Then JS-dependent clients
        for c in ALL_CLIENTS:
            if c not in _JSLESS_CLIENTS and c not in result and c not in failed:
                result.append(c)
        # Finally failed ones as last resort
        for c in ALL_CLIENTS:
            if c not in result:
                result.append(c)
        return result


_registry = _ClientRegistry()


# ── yt-dlp option builder ─────────────────────────────────────────────────────
def _opts(client: str, cookie_file: Optional[str] = None) -> Dict:
    ua = _CLIENT_UA.get(client, _DEFAULT_UA)
    needs_js = client not in _JSLESS_CLIENTS
    runtimes = _js_runtimes() if needs_js and _NODE_PATH else {}

    o: Dict = {
        "quiet":              True,
        "no_warnings":        True,
        "nocheckcertificate": True,
        "source_address":     "0.0.0.0",
        "socket_timeout":     4,
        "retries":            1,
        "extractor_args": {
            "youtube": {
                "player_client": [client],
                "skip": ["hls", "translated_subs"],
            }
        },
        "http_headers": {"User-Agent": ua},
    }
    if runtimes:
        o["js_runtimes"] = runtimes
    if cookie_file:
        o["cookiefile"] = cookie_file
    if _PROXY:
        o["proxy"] = _PROXY
    return o


# ── Per-client extract/download ───────────────────────────────────────────────
_AUDIO_FMT = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"


def _client_extract(vid: str, client: str, cookie_file: Optional[str]) -> Optional[Dict]:
    o = _opts(client, cookie_file)
    o.update({
        "skip_download": True,
        "format": _AUDIO_FMT,
        "format_sort": ["abr", "ext:m4a:0"],
    })
    try:
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        if info and info.get("url"):
            return {
                "url":      info["url"],
                "ext":      info.get("ext", "m4a"),
                "title":    info.get("title", "Unknown"),
                "channel":  info.get("channel") or info.get("uploader", ""),
                "duration": int(info.get("duration") or 0),
                "client":   client,
            }
    except Exception as e:
        _log.debug(f"[SmartYTDL] {client} extract {vid}: {e}")
    return None


def _client_download(vid: str, client: str, out_dir: str,
                     fmt: str, cookie_file: Optional[str]) -> Optional[str]:
    from KHUSHI.utils.media_validate import audio_ok_sync, set_expected_duration
    o = _opts(client, cookie_file)
    o.update({
        "format":   fmt,
        "outtmpl":  os.path.join(out_dir, f"{vid}.%(ext)s"),
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "noprogress": True,
        "socket_timeout": 20,
        "retries": 2,
    })
    try:
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
            if info:
                set_expected_duration(vid, int(info.get("duration") or 0))
        for ext in ("m4a", "webm", "opus", "ogg", "mp3", "mp4"):
            p = os.path.join(out_dir, f"{vid}.{ext}")
            if os.path.exists(p) and os.path.getsize(p) > 32 * 1024:
                if audio_ok_sync(p, vid=vid):
                    return p
                _log.warning(f"[SmartYTDL] {client} produced truncated file for {vid}; discarding")
                try: os.remove(p)
                except Exception: pass
    except Exception as e:
        _log.debug(f"[SmartYTDL] {client} download {vid}: {e}")
    return None


def _direct_extract(vid: str) -> Optional[Dict]:
    """
    Extract stream URL using android_vr first (jsless, no cookies, no bot-detection wall).
    Falls back to unrestricted yt-dlp if android_vr fails (e.g. format not available).
    """
    # PRIMARY: android_vr — jsless, no PO token, bypasses "Sign in to confirm" entirely
    res = _client_extract(vid, "android_vr", None)
    if res:
        return res

    # SECONDARY: no player_client restriction — yt-dlp picks best default
    o: Dict = {
        "quiet":              True,
        "no_warnings":        True,
        "nocheckcertificate": True,
        "source_address":     "0.0.0.0",
        "socket_timeout":     6,
        "retries":            0,
        "skip_download":      True,
        "format":             _AUDIO_FMT,
    }
    if _PROXY:
        o["proxy"] = _PROXY
    try:
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        if info and info.get("url"):
            return {
                "url":      info["url"],
                "ext":      info.get("ext", "m4a"),
                "title":    info.get("title", "Unknown"),
                "channel":  info.get("channel") or info.get("uploader", ""),
                "duration": int(info.get("duration") or 0),
                "client":   "direct",
            }
    except Exception as e:
        _log.debug(f"[SmartYTDL] direct_extract fallback {vid}: {e}")
    return None


def _direct_download(vid: str, out_dir: str, fmt: str,
                     cookie_file: Optional[str] = None) -> Optional[str]:
    """
    Download using android_vr first — jsless client that bypasses YouTube bot-detection.
    Falls back to unrestricted yt-dlp if android_vr fails.
    android_vr is the default yt-dlp client in 2026 and works on cloud IPs without cookies.
    """
    from KHUSHI.utils.media_validate import audio_ok_sync, set_expected_duration
    # PRIMARY: android_vr — fastest, no "Sign in" wall, works on cloud IPs
    p = _client_download(vid, "android_vr", out_dir, fmt, None)
    if p:
        _log.info(f"[SmartYTDL] android_vr direct_download ok: {p}")
        _registry.mark_ok("android_vr")
        return p

    # SECONDARY: unrestricted (no extractor_args) — yt-dlp auto-selects
    o: Dict = {
        "format":             fmt,
        "outtmpl":            os.path.join(out_dir, f"{vid}.%(ext)s"),
        "quiet":              True,
        "no_warnings":        True,
        "noplaylist":         True,
        "overwrites":         True,
        "continuedl":         True,
        "noprogress":         True,
        "nocheckcertificate": True,
        "source_address":     "0.0.0.0",
        "socket_timeout":     20,
        "retries":            2,
    }
    if cookie_file:
        o["cookiefile"] = cookie_file
    if _PROXY:
        o["proxy"] = _PROXY
    try:
        with yt_dlp.YoutubeDL(o) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
            if info:
                set_expected_duration(vid, int(info.get("duration") or 0))
        for ext in ("m4a", "webm", "opus", "ogg", "mp3", "mp4"):
            p = os.path.join(out_dir, f"{vid}.{ext}")
            if os.path.exists(p) and os.path.getsize(p) > 32 * 1024:
                if audio_ok_sync(p, vid=vid):
                    _log.info(f"[SmartYTDL] direct_download ok: {p}")
                    return p
                _log.warning(f"[SmartYTDL] direct_download truncated for {vid}; discarding")
                try: os.remove(p)
                except Exception: pass
    except Exception as e:
        _log.debug(f"[SmartYTDL] direct_download unrestricted {vid}: {e}")
    return None


# ── Race helper — first thread to put a result wins ───────────────────────────
def _race(targets, timeout: float = 22.0) -> Optional[any]:
    result_q: queue.Queue = queue.Queue()
    active = [0]
    lock = threading.Lock()

    def worker(fn):
        try:
            res = fn()
        except Exception:
            res = None
        finally:
            with lock:
                active[0] -= 1
                remaining = active[0]
            if res is not None:
                result_q.put(res)
            elif remaining == 0:
                result_q.put(None)

    with lock:
        active[0] = len(targets)

    threads = []
    for fn in targets:
        t = threading.Thread(target=worker, args=(fn,), daemon=True)
        threads.append(t)
        t.start()

    deadline = time.time() + timeout
    while True:
        remaining_time = max(0.1, deadline - time.time())
        try:
            item = result_q.get(timeout=remaining_time)
            if item is not None:
                return item
            with lock:
                if active[0] == 0:
                    return None
        except queue.Empty:
            return None


# ── Invidious search fallback ────────────────────────────────────────────────
def _invidious_search(query: str, limit: int = 5) -> List[Dict]:
    """
    Search YouTube via Invidious /api/v1/search?q=... — bulletproof fallback
    for when both yt-dlp ytsearch and youtubesearchpython are blocked/slow.
    Returns a list of normalised result dicts (same shape as VideosSearch).
    """
    import urllib.request, urllib.parse, json
    encoded = urllib.parse.quote(query)
    out: List[Dict] = []
    for inst in _alive_instances(_INVIDIOUS_INSTANCES):
        try:
            url = f"{inst}/api/v1/search?q={encoded}&type=video"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Annie/2.0)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=6) as r:
                if r.status != 200:
                    _fail_instance(inst)
                    continue
                body = r.read()
                if not body or body[:1] not in (b'{', b'['):
                    _fail_instance(inst)
                    continue
                data = json.loads(body)
            if not isinstance(data, list):
                continue
            for item in data:
                vid = item.get("videoId")
                if not vid:
                    continue
                length_s = int(item.get("lengthSeconds") or 0)
                # Format duration as M:SS or H:MM:SS
                m, s = divmod(length_s, 60)
                h, m = divmod(m, 60)
                dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                thumbs = item.get("videoThumbnails") or []
                thumb_url = thumbs[0].get("url", "") if thumbs else ""
                out.append({
                    "id": vid,
                    "title": item.get("title", "Unknown"),
                    "duration": dur_str,
                    "thumbnails": [{"url": thumb_url}],
                    "channel": {"name": item.get("author", "")},
                    "link": f"https://www.youtube.com/watch?v={vid}",
                    "thumbnail": thumb_url,
                    "viewCount": {"short": ""},
                })
                if len(out) >= limit:
                    break
            if out:
                _log.info(f"[SmartYTDL] Invidious search OK ({inst}) for '{query[:40]}': {len(out)} results")
                return out
        except Exception as e:
            _log.debug(f"[SmartYTDL] Invidious search {inst} failed: {e}")
            _fail_instance(inst)
    return out


# ── Invidious fallback ────────────────────────────────────────────────────────
def _invidious_extract(vid: str) -> Optional[Dict]:
    import urllib.request, json
    for inst in _alive_instances(_INVIDIOUS_INSTANCES):
        try:
            url = f"{inst}/api/v1/videos/{vid}?fields=adaptiveFormats,formatStreams,title,lengthSeconds,author"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Annie/2.0)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status != 200:
                    _fail_instance(inst)
                    continue
                body = r.read()
                if not body or body[:1] not in (b'{', b'['):
                    _fail_instance(inst)
                    continue
                data = json.loads(body)

            best_url, best_br = None, 0
            for fmt in data.get("adaptiveFormats", []):
                if "audio" not in fmt.get("type", ""):
                    continue
                br = int(fmt.get("bitrate", 0))
                if br > best_br:
                    best_br, best_url = br, fmt.get("url")

            if not best_url:
                for fmt in data.get("formatStreams", []):
                    best_url = fmt.get("url")
                    break

            if best_url:
                _log.info(f"[SmartYTDL] Invidious OK {inst} for {vid}")
                return {"url": best_url, "ext": "webm",
                        "title": data.get("title", "Unknown"),
                        "channel": data.get("author", ""),
                        "duration": int(data.get("lengthSeconds") or 0),
                        "client": f"invidious:{inst}"}
        except Exception as e:
            _log.debug(f"[SmartYTDL] Invidious {inst} failed: {e}")
            _fail_instance(inst)
    return None


def _invidious_download(vid: str, out_dir: str) -> Optional[str]:
    import urllib.request
    from KHUSHI.utils.media_validate import audio_ok_sync, set_expected_duration
    info = _invidious_extract(vid)
    if not info:
        return None
    set_expected_duration(vid, int(info.get("duration") or 0))
    out = os.path.join(out_dir, f"{vid}.webm")
    try:
        req = urllib.request.Request(info["url"], headers={
            "User-Agent": "Mozilla/5.0 (compatible; Annie/2.0)",
            "Referer": "https://www.youtube.com/",
        })
        expected_bytes = 0
        with urllib.request.urlopen(req, timeout=180) as r, open(out, "wb") as f:
            try:
                expected_bytes = int(r.headers.get("Content-Length", 0) or 0)
            except (TypeError, ValueError):
                expected_bytes = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
        actual = os.path.getsize(out) if os.path.exists(out) else 0
        if actual < 32 * 1024:
            try: os.remove(out)
            except Exception: pass
            return None
        if expected_bytes > 0 and actual < int(expected_bytes * 0.95):
            _log.warning(f"[SmartYTDL] Invidious truncated for {vid}: {actual}/{expected_bytes}")
            try: os.remove(out)
            except Exception: pass
            return None
        if not audio_ok_sync(out, vid=vid):
            _log.warning(f"[SmartYTDL] Invidious file failed duration check for {vid}")
            try: os.remove(out)
            except Exception: pass
            return None
        _log.info(f"[SmartYTDL] Invidious download ok: {out}")
        return out
    except Exception as e:
        _log.debug(f"[SmartYTDL] Invidious stream download failed: {e}")
    try:
        os.remove(out)
    except Exception:
        pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────
def smart_extract_url(vid: str) -> Optional[Dict]:
    """
    Extract YouTube stream URL.
    Priority: android_vr (jsless) → web_safari → ios → android → others → Invidious
    No cookies required for primary clients.
    """
    # Do NOT pass cookies to yt-dlp unless necessary — expired/invalid cookies force
    # the "tv downgraded" client which returns only image formats (no audio/video).
    # Try cookieless first; use cookies only for the per-client fallback race.
    cookie_file = _find_cookie_file()

    from KHUSHI.utils.media_validate import set_expected_duration as _sxd
    # Fast path — try cached best client first (avoids full race on repeated plays)
    best = _registry.get_best()
    if best:
        res = _client_extract(vid, best, None)  # no cookies on fast path
        if res:
            _registry.mark_ok(best)
            _sxd(vid, int(res.get("duration") or 0))
            _log.info(f"[SmartYTDL] Fast-path client='{best}' for {vid}")
            return res
        _registry.mark_failed(best)
        _log.info(f"[SmartYTDL] Cached '{best}' failed for {vid}, racing all")

    # Race all clients — jsless ones (android_vr, ios, android, mweb) launch first.
    # Also race _direct_extract (no player_client restriction) which succeeds when
    # per-client extraction fails with "Requested format is not available".
    clients = _registry.ordered_clients()
    _log.info(f"[SmartYTDL] Racing {len(clients)} clients + direct for {vid} | order: {clients[:4]}")

    targets = [lambda: _direct_extract(vid)] + [
        (lambda c: lambda: _client_extract(vid, c, cookie_file))(c)
        for c in clients
    ]
    winner = _race(targets, timeout=8.0)

    if winner:
        winning_client = winner["client"]
        # Only update registry for real yt-dlp clients, not "direct" pseudo-client
        if winning_client in ALL_CLIENTS:
            _registry.mark_ok(winning_client)
        _log.info(f"[SmartYTDL] client='{winning_client}' won for {vid}")
        return winner

    # Invidious fallback
    _log.warning(f"[SmartYTDL] All yt-dlp clients failed for {vid} → Invidious")
    res = _invidious_extract(vid)
    if res:
        return res

    _log.error(f"[SmartYTDL] ALL extract methods failed for {vid}")
    return None


def smart_download(vid: str, out_dir: str,
                   fmt: str = _AUDIO_FMT) -> Optional[str]:
    """
    Download YouTube audio/video.
    Priority:
      0. Direct (no player_client restriction) — fastest, most compatible
      1. Cached best client
      2. Race all yt-dlp clients
      3. Invidious fallback
    """
    cookie_file = _find_cookie_file()

    # PRIMARY: no player_client restriction, no cookies — yt-dlp picks its best default client.
    # Expired/invalid cookies force the "tv downgraded" client which has no audio formats,
    # so we always try cookieless first, then retry with cookies only if needed.
    p = _direct_download(vid, out_dir, fmt, cookie_file=None)
    if p:
        _log.info(f"[SmartYTDL] direct_download (no-cookie) succeeded for {vid}")
        return p

    # Retry with cookies in case the video requires authentication
    if cookie_file:
        p = _direct_download(vid, out_dir, fmt, cookie_file=cookie_file)
        if p:
            _log.info(f"[SmartYTDL] direct_download (with-cookie) succeeded for {vid}")
            return p

    _log.info(f"[SmartYTDL] direct_download failed for {vid}, trying per-client race")

    # Fast path — cached best client
    best = _registry.get_best()
    if best:
        p = _client_download(vid, best, out_dir, fmt, cookie_file)
        if p:
            _registry.mark_ok(best)
            return p
        _registry.mark_failed(best)

    # Race all clients
    clients = _registry.ordered_clients()
    targets = [
        (lambda c: lambda: _client_download(vid, c, out_dir, fmt, cookie_file))(c)
        for c in clients
    ]
    winner_path = _race(targets, timeout=40.0)
    if winner_path:
        _log.info(f"[SmartYTDL] Download won for {vid}: {winner_path}")
        return winner_path

    # Invidious fallback
    _log.warning(f"[SmartYTDL] All yt-dlp clients failed download for {vid} → Invidious")
    p = _invidious_download(vid, out_dir)
    if p:
        return p

    _log.error(f"[SmartYTDL] ALL download methods failed for {vid}")
    return None


# ── Helpers used by the rest of the codebase ──────────────────────────────────
def get_cdn_headers() -> Dict:
    """Return HTTP headers suitable for downloading from a YouTube CDN URL."""
    best = _registry.get_best() or "android_vr"
    ua = _CLIENT_UA.get(best, _DEFAULT_UA)
    return {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
    }


def get_base_ytdlp_opts(out_dir: str) -> Dict:
    # Do NOT pass cookies — expired/invalid cookies force the "tv downgraded" client
    # which only returns image formats. Cookieless android_vr gives full format access.
    o = {
        "outtmpl":            os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet":              True,
        "no_warnings":        True,
        "noplaylist":         True,
        "overwrites":         True,
        "continuedl":         True,
        "noprogress":         True,
        "nocheckcertificate": True,
        "source_address":     "0.0.0.0",
        "socket_timeout":     30,
        "retries":            3,
    }
    if _PROXY:
        o["proxy"] = _PROXY
    return o


def get_stream_opts() -> Dict:
    # Do NOT pass cookies — expired/invalid cookies cause "tv downgraded" client
    # which returns only image formats. Cookieless android_vr works reliably.
    o = {
        "quiet":              True,
        "no_warnings":        True,
        "skip_download":      True,
        "format":             _AUDIO_FMT,
        "nocheckcertificate": True,
        "source_address":     "0.0.0.0",
        "socket_timeout":     20,
        "retries":            2,
    }
    if _PROXY:
        o["proxy"] = _PROXY
    return o
