"""
Shared API utilities — used by both webserver.py (port 5000)
and health_check.py (port 8080).
"""
import io
import os
import requests as _requests

# ── NSFW skin-ratio check ─────────────────────────────────────────────────────

def nsfw_skin_ratio(image_bytes: bytes) -> float:
    try:
        from PIL import Image
        import numpy as np
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((300, 300))
        arr = np.array(img, dtype=float)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        skin = (
            (r > 95) & (g > 40) & (b > 20) &
            (r > g) & (r > b) &
            ((r - g) > 15) &
            (r < 240) & (g < 200) & (b < 180)
        )
        return float(skin.sum()) / (300 * 300)
    except Exception:
        return 0.0


def nsfw_nudenet_check(image_bytes: bytes):
    try:
        from PIL import Image
        from nudenet import NudeDetector
        import tempfile
        detector = NudeDetector()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.save(tmp_path, "PNG")
        try:
            detections = detector.detect(tmp_path)
            # Per official NudeNet docs (pypi.org/project/nudenet):
            # Only EXPOSED classes indicate actual NSFW content.
            # COVERED classes are NOT NSFW — they cause false positives on
            # swimwear, anime/cartoon art, stickers, etc.
            EXPOSED = {
                "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED",
                "FEMALE_BREAST_EXPOSED", "ANUS_EXPOSED", "BUTTOCKS_EXPOSED",
            }
            labels, is_nsfw = [], False
            for det in detections:
                cls, score = det.get("class", ""), det.get("score", 0)
                if cls in EXPOSED and score >= 0.60:
                    is_nsfw = True
                    labels.append({"label": cls, "confidence": round(score, 3)})
            return is_nsfw, labels
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    except Exception:
        return None, []


def _detect_media_type(content_type: str, url: str) -> str:
    """Detect media type from Content-Type header or URL extension."""
    ct = content_type.lower()
    if "video/" in ct or url.lower().endswith((".mp4", ".webm", ".avi", ".mov")):
        return "video"
    if "image/gif" in ct or url.lower().endswith(".gif"):
        return "gif"
    if any(x in ct for x in ("image/", "application/octet-stream")):
        return "image"
    return "unknown"


def _extract_gif_frames_bytes(data: bytes, max_frames: int = 6) -> list[bytes]:
    """Extract evenly-spaced frames from a GIF, return list of PNG bytes."""
    from PIL import Image
    frames_bytes = []
    try:
        img = Image.open(io.BytesIO(data))
        n = getattr(img, "n_frames", 1)
        step = max(1, n // max_frames)
        for i in range(0, n, step):
            if len(frames_bytes) >= max_frames:
                break
            try:
                img.seek(i)
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "PNG")
                frames_bytes.append(buf.getvalue())
            except EOFError:
                break
    except Exception:
        frames_bytes = [data]  # fallback: try the raw data
    return frames_bytes


def _extract_video_frames_bytes(data: bytes, max_frames: int = 6) -> list[bytes]:
    """Extract frames from a video (mp4/webm) using ffmpeg. Returns list of PNG bytes."""
    import subprocess, tempfile, glob as _glob
    frames_bytes = []
    tmp_in = tmp_out = None
    try:
        suffix = ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            tmp_in = f.name
        out_base = tmp_in + "_vf"
        cmd = [
            "ffmpeg", "-y", "-i", tmp_in,
            "-vf", "fps=1,scale=640:-2",
            "-vframes", str(max_frames),
            f"{out_base}%03d.png",
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        for fp in sorted(_glob.glob(f"{out_base}*.png"))[:max_frames]:
            with open(fp, "rb") as f:
                frames_bytes.append(f.read())
            try:
                os.remove(fp)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        if tmp_in and os.path.exists(tmp_in):
            try:
                os.remove(tmp_in)
            except Exception:
                pass
    return frames_bytes


def _check_frames_nsfw(frames: list[bytes]) -> tuple[bool, list, float]:
    """Run NudeNet + skin ratio on a list of frame byte blobs. Returns (is_nsfw, labels, max_skin)."""
    all_labels = []
    max_skin = 0.0
    for fb in frames:
        is_bad, lbs = nsfw_nudenet_check(fb)
        if is_bad:
            return True, lbs, max(max_skin, nsfw_skin_ratio(fb))
        skin = nsfw_skin_ratio(fb)
        max_skin = max(max_skin, skin)
        all_labels.extend(lbs)
    return False, all_labels, max_skin


def nsfw_check_url(url: str) -> dict:
    """Check image / GIF / video URL for NSFW content. Returns result dict."""
    _SIZE_LIMIT_IMAGE = 5_000_000   # 5 MB
    _SIZE_LIMIT_VIDEO = 15_000_000  # 15 MB
    try:
        resp = _requests.get(url, timeout=15, stream=True)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "by": "t.me/PGL_B4CHI"}

        ct = resp.headers.get("Content-Type", "")
        media_type = _detect_media_type(ct, url)

        if media_type == "unknown":
            return {"error": "Unsupported media type. Supported: image (jpg/png/webp/gif), GIF, video (mp4/webm)", "by": "t.me/PGL_B4CHI"}

        size_limit = _SIZE_LIMIT_VIDEO if media_type == "video" else _SIZE_LIMIT_IMAGE
        raw = b""
        for chunk in resp.iter_content(65536):
            raw += chunk
            if len(raw) > size_limit:
                return {"error": f"File too large (limit: {size_limit // 1_000_000} MB for {media_type})", "by": "t.me/PGL_B4CHI"}
        if not raw:
            return {"error": "Empty response", "by": "t.me/PGL_B4CHI"}

        # ── Extract frames based on media type ───────────────────────────
        if media_type == "gif":
            frames = _extract_gif_frames_bytes(raw)
        elif media_type == "video":
            frames = _extract_video_frames_bytes(raw)
        else:
            frames = [raw]  # single image

        if not frames:
            return {"error": "Could not extract frames from media", "by": "t.me/PGL_B4CHI"}

        # ── Run NudeNet on all frames ─────────────────────────────────────
        is_nsfw, labels, max_skin = _check_frames_nsfw(frames)
        frames_checked = len(frames)

        if labels or is_nsfw:
            return {
                "is_nsfw": is_nsfw,
                "media_type": media_type,
                "method": "nudenet",
                "frames_checked": frames_checked,
                "confidence": max((l["confidence"] for l in labels), default=round(max_skin, 3)),
                "skin_ratio": round(max_skin, 3),
                "labels": labels,
                "by": "t.me/PGL_B4CHI",
            }

        # ── Skin ratio fallback ───────────────────────────────────────────
        is_nsfw_skin = max_skin >= 0.48
        return {
            "is_nsfw": is_nsfw_skin,
            "media_type": media_type,
            "method": "skin_ratio",
            "frames_checked": frames_checked,
            "confidence": round(max_skin, 3),
            "skin_ratio": round(max_skin, 3),
            "labels": [],
            "by": "t.me/PGL_B4CHI",
        }
    except Exception as e:
        return {"error": str(e), "by": "t.me/PGL_B4CHI"}


# ── API Docs HTML ─────────────────────────────────────────────────────────────

API_DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>RAJAMODS7 Music — API Docs</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#050508;--s1:#0f0f14;--s2:#16161e;--s3:#1e1e28;--s4:#2a2a38;
  --acc:#a855f7;--green:#10b981;--blue:#3b82f6;
  --red:#ef4444;--orange:#f97316;--pink:#ec4899;
  --text:#fff;--text2:#a0a0b8;--text3:#505068;
  --border:rgba(168,85,247,0.15);--border2:rgba(255,255,255,0.07);
}
body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
code,pre{font-family:'JetBrains Mono',monospace}
.header{background:linear-gradient(135deg,#0f0820,#1a0a2e 50%,#0d1a3a);border-bottom:1px solid var(--border);padding:40px 24px 32px;text-align:center;position:relative;overflow:hidden}
.header::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(168,85,247,0.12),transparent);pointer-events:none}
.badge{display:inline-flex;align-items:center;gap:8px;background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.3);border-radius:100px;padding:6px 18px;font-size:12px;font-weight:700;color:var(--acc);margin-bottom:18px;letter-spacing:.5px}
.badge::before{content:'●';font-size:8px;color:var(--green);animation:pulse 2s ease infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.header h1{font-size:clamp(26px,5vw,44px);font-weight:800;background:linear-gradient(135deg,#fff,#c084fc 60%,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:10px}
.header p{color:var(--text2);font-size:15px;margin-bottom:20px}
.by-link{display:inline-flex;align-items:center;gap:8px;background:rgba(168,85,247,0.1);border:1px solid rgba(168,85,247,0.25);border-radius:10px;padding:10px 20px;font-size:14px;font-weight:700;color:var(--acc);transition:all .2s}
.by-link:hover{background:rgba(168,85,247,0.2);text-decoration:none}
.by-link svg{width:18px;height:18px;fill:currentColor}
.container{max-width:980px;margin:0 auto;padding:36px 20px}
.search-wrap{margin-bottom:28px;position:relative}
.search-wrap input{width:100%;background:var(--s2);border:1px solid var(--border2);border-radius:12px;padding:14px 20px 14px 50px;font-size:14px;color:var(--text);font-family:'Inter',sans-serif;outline:none;transition:border-color .2s}
.search-wrap input:focus{border-color:var(--acc)}
.search-wrap input::placeholder{color:var(--text3)}
.sico{position:absolute;left:17px;top:50%;transform:translateY(-50%);color:var(--text3)}
.sico svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:32px}
.scard{flex:1;min-width:110px;background:var(--s2);border:1px solid var(--border2);border-radius:12px;padding:18px 16px;text-align:center}
.snum{font-size:26px;font-weight:800;background:linear-gradient(135deg,var(--acc),var(--pink));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.slbl{font-size:11px;color:var(--text3);margin-top:3px;text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.sec-title{font-size:12px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px;margin-top:28px;display:flex;align-items:center;gap:10px}
.sec-title::after{content:'';flex:1;height:1px;background:var(--border2)}
.card{background:var(--s2);border:1px solid var(--border2);border-radius:16px;margin-bottom:14px;overflow:hidden;transition:border-color .2s}
.card:hover{border-color:rgba(168,85,247,.3)}
.card.open{border-color:rgba(168,85,247,.4)}
.card-head{display:flex;align-items:center;gap:12px;padding:16px 20px;cursor:pointer;user-select:none}
.method{padding:4px 10px;border-radius:6px;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:.5px;flex-shrink:0}
.get{background:rgba(16,185,129,.15);color:var(--green);border:1px solid rgba(16,185,129,.3)}
.post{background:rgba(59,130,246,.15);color:var(--blue);border:1px solid rgba(59,130,246,.3)}
.path{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text);flex:1;font-weight:500}
.short{font-size:13px;color:var(--text2);margin-left:8px}
.tog{color:var(--text3);transition:transform .2s;flex-shrink:0}
.tog svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
.card.open .tog{transform:rotate(180deg)}
.body{display:none;border-top:1px solid var(--border2);padding:20px}
.card.open .body{display:block}
.desc{color:var(--text2);font-size:14px;line-height:1.6;margin-bottom:16px}
.ptitle{font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.prow{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--border2)}
.prow:last-child{border-bottom:none}
.pname{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:var(--acc);min-width:90px}
.ptype{font-size:11px;background:var(--s4);padding:2px 8px;border-radius:4px;color:var(--text2);flex-shrink:0}
.preq{font-size:10px;background:rgba(239,68,68,.15);color:var(--red);padding:2px 6px;border-radius:4px;flex-shrink:0;font-weight:700}
.pdesc{font-size:13px;color:var(--text2);flex:1}
.cw{margin-top:14px}
.clbl{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;display:flex;align-items:center;justify-content:space-between}
.cbtn{background:var(--s4);border:none;color:var(--text2);padding:4px 10px;border-radius:6px;font-size:11px;cursor:pointer;font-family:'Inter',sans-serif;transition:all .15s}
.cbtn:hover{background:var(--acc);color:#fff}
pre{background:var(--s3);border:1px solid var(--border2);border-radius:10px;padding:14px 16px;font-size:12px;line-height:1.7;overflow-x:auto;color:#e2e8f0}
pre .k{color:#c084fc}
pre .s{color:#86efac}
pre .n{color:#fbbf24}
pre .b{color:#60a5fa}
.rtags{display:flex;gap:6px;flex-wrap:wrap;margin-top:14px}
.rt{padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600}
.r200{background:rgba(16,185,129,.12);color:var(--green);border:1px solid rgba(16,185,129,.25)}
.r400{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}
.r500{background:rgba(249,115,22,.1);color:var(--orange);border:1px solid rgba(249,115,22,.2)}
.footer{text-align:center;padding:44px 20px 32px;color:var(--text3);font-size:13px}
.footer a{color:var(--acc)}
@media(max-width:580px){.short{display:none}.stats{gap:8px}}
</style>
</head>
<body>
<div class="header">
  <div class="badge">API &nbsp;·&nbsp; Live &amp; Free</div>
  <h1>RAJAMODS7 Music API</h1>
  <p>Public REST API — Music, Search, NSFW Detection &amp; more</p>
  <a class="by-link" href="https://t.me/PGL_B4CHI" target="_blank">
    <svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.8 13.917l-2.963-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.351 1.642z"/></svg>
    by t.me/PGL_B4CHI
  </a>
</div>

<div class="container">
  <div class="search-wrap">
    <span class="sico"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg></span>
    <input type="text" id="srch" placeholder="Search APIs by name or keyword..." oninput="filterApis(this.value)"/>
  </div>

  <div class="stats">
    <div class="scard"><div class="snum">13</div><div class="slbl">Endpoints</div></div>
    <div class="scard"><div class="snum">Free</div><div class="slbl">No Auth</div></div>
    <div class="scard"><div class="snum">REST</div><div class="slbl">JSON API</div></div>
    <div class="scard"><div class="snum">24/7</div><div class="slbl">Uptime</div></div>
  </div>

  <!-- MUSIC -->
  <div class="sec-title" id="sec-music">Music &amp; YouTube</div>

  <div class="card" data-tags="search youtube music songs">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/search</span>
      <span class="short">Search songs on YouTube</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Search YouTube for songs. Returns title, channel, duration, thumbnail for each result.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">q</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">Search query — e.g. "Arijit Singh"</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c1')">Copy</button></div><pre id="c1">GET /api/search?q=Arijit+Singh</pre></div>
      <div class="cw"><div class="clbl">Response</div><pre>{ <span class="k">"results"</span>: [{ <span class="k">"id"</span>:<span class="s">"abc123"</span>, <span class="k">"title"</span>:<span class="s">"Song"</span>, <span class="k">"channel"</span>:<span class="s">"Artist"</span>, <span class="k">"duration"</span>:<span class="s">"4:32"</span>, <span class="k">"thumb"</span>:<span class="s">"https://..."</span> }] }</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span><span class="rt r400">400 Missing q</span></div>
    </div>
  </div>

  <div class="card" data-tags="stream metadata youtube video info">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/stream</span>
      <span class="short">Video metadata</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Get metadata for a YouTube video — title, channel, duration, thumbnail. No stream URL is exposed.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">v</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">YouTube video ID (11 chars)</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c2')">Copy</button></div><pre id="c2">GET /api/stream?v=dQw4w9WgXcQ</pre></div>
      <div class="cw"><div class="clbl">Response</div><pre>{ <span class="k">"title"</span>:<span class="s">"Song Name"</span>, <span class="k">"channel"</span>:<span class="s">"Artist"</span>, <span class="k">"duration"</span>:<span class="s">"3:33"</span>, <span class="k">"seconds"</span>:<span class="n">213</span>, <span class="k">"thumb"</span>:<span class="s">"https://..."</span> }</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span><span class="rt r400">400 Invalid ID</span></div>
    </div>
  </div>

  <div class="card" data-tags="audio proxy youtube stream browser cors">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/audio</span>
      <span class="short">Proxy audio stream</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Proxy YouTube audio stream to browser — bypasses CORS. Supports Range requests for seeking. Returns audio/mp4 or audio/webm.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">v</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">YouTube video ID</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c3')">Copy</button></div><pre id="c3">GET /api/audio?v=dQw4w9WgXcQ</pre></div>
      <div class="rtags"><span class="rt r200">200 Audio Stream</span><span class="rt r500">503 Unavailable</span></div>
    </div>
  </div>

  <div class="card" data-tags="download youtube audio file mp3 m4a">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/download</span>
      <span class="short">Download audio file</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Download audio as a file. Returns with Content-Disposition header — opens download dialog in browser.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">v</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">YouTube video ID</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c4')">Copy</button></div><pre id="c4">GET /api/download?v=dQw4w9WgXcQ</pre></div>
      <div class="rtags"><span class="rt r200">200 File Download</span><span class="rt r500">500 Error</span></div>
    </div>
  </div>

  <div class="card" data-tags="video youtube proxy browser stream mp4">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/video</span>
      <span class="short">Proxy video stream</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Proxy YouTube video+audio stream for web player. Returns video/mp4, supports Range requests.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">v</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">YouTube video ID</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c5')">Copy</button></div><pre id="c5">GET /api/video?v=dQw4w9WgXcQ</pre></div>
      <div class="rtags"><span class="rt r200">200 Video Stream</span><span class="rt r500">500 Error</span></div>
    </div>
  </div>

  <div class="card" data-tags="trending songs youtube popular hindi punjabi bollywood">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/trending</span>
      <span class="short">Trending songs</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Get trending songs — Hindi, Punjabi, Bollywood, International. Updated every 30 minutes. No parameters needed.</p>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c6')">Copy</button></div><pre id="c6">GET /api/trending</pre></div>
      <div class="cw"><div class="clbl">Response</div><pre>{ <span class="k">"songs"</span>: [{ <span class="k">"id"</span>:<span class="s">"abc"</span>, <span class="k">"title"</span>:<span class="s">"Song"</span>, <span class="k">"category"</span>:<span class="s">"Hindi"</span>, <span class="k">"duration"</span>:<span class="s">"3:45"</span> }] }</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span></div>
    </div>
  </div>

  <div class="card" data-tags="related songs youtube recommendations autoplay">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/related</span>
      <span class="short">Related songs</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Get recommended / related songs for a given YouTube video ID.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">v</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">YouTube video ID</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c7')">Copy</button></div><pre id="c7">GET /api/related?v=dQw4w9WgXcQ</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span><span class="rt r400">400 Invalid ID</span></div>
    </div>
  </div>

  <!-- BOT -->
  <div class="sec-title" id="sec-bot">Bot &amp; System</div>

  <div class="card" data-tags="bot info name username features">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/botinfo</span>
      <span class="short">Bot information</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Returns bot name, username, bio and list of supported platforms.</p>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c8')">Copy</button></div><pre id="c8">GET /api/botinfo</pre></div>
      <div class="cw"><div class="clbl">Response</div><pre>{ <span class="k">"name"</span>:<span class="s">"RAJAMODS7 Music"</span>, <span class="k">"username"</span>:<span class="s">"VcAnnieBot"</span>, <span class="k">"features"</span>:[<span class="s">"YouTube"</span>,<span class="s">"Spotify"</span>] }</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span></div>
    </div>
  </div>

  <div class="card" data-tags="status uptime system stats cpu ram active chats">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/status</span>
      <span class="short">Bot &amp; system status</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Returns bot uptime, CPU/RAM usage and currently active voice chat queues across all groups.</p>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c9')">Copy</button></div><pre id="c9">GET /api/status</pre></div>
      <div class="cw"><div class="clbl">Response</div><pre>{ <span class="k">"status"</span>:<span class="s">"online"</span>, <span class="k">"uptime"</span>:<span class="s">"2h 15m"</span>, <span class="k">"active_chats"</span>:<span class="n">5</span>, <span class="k">"cpu"</span>:<span class="n">12.4</span>, <span class="k">"ram_used"</span>:<span class="s">"512 MB"</span> }</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span></div>
    </div>
  </div>

  <div class="card" data-tags="health ping alive check uptime">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/health</span>
      <span class="short">Health check</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Simple alive check. Returns HTTP 200 and <code>{"status":"running"}</code> if the server is up.</p>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c10')">Copy</button></div><pre id="c10">GET /api/health</pre></div>
      <div class="cw"><div class="clbl">Response</div><pre>{ <span class="k">"status"</span>: <span class="s">"running"</span> }</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span></div>
    </div>
  </div>

  <div class="card" data-tags="bot profile picture avatar pfp image">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/botpfp</span>
      <span class="short">Bot profile picture</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Returns the bot's profile picture as PNG. Useful for embedding in other apps.</p>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c11')">Copy</button></div><pre id="c11">GET /api/botpfp</pre></div>
      <div class="rtags"><span class="rt r200">200 image/png</span><span class="rt r400">404 No picture</span></div>
    </div>
  </div>

  <!-- NSFW -->
  <div class="sec-title" id="sec-nsfw">NSFW &amp; Content Safety</div>

  <div class="card" data-tags="nsfw detection image gif video sticker adult content check 18+ explicit nudity frames">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/nsfw</span>
      <span class="short">Detect adult / explicit content in image, GIF &amp; video</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Check any media URL for NSFW / adult / explicit content. Supports <b>images</b> (jpg, png, webp), <b>GIFs</b> (multi-frame scan), and <b>videos</b> (mp4, webm — ffmpeg frame extraction). Uses AI-based <b>NudeNet</b> detection per official docs. Only fully <b>EXPOSED</b> body-part classes are flagged (confidence ≥ 0.60) — COVERED classes are intentionally skipped to avoid false positives on swimwear, anime/cartoon art and normal stickers. Size limits: images 5 MB · GIF 5 MB · video 15 MB.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">url</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">Direct URL of the media to check (image / GIF / video)</span></div>
      <div class="cw"><div class="clbl">Example — Image <button class="cbtn" onclick="cp('c12a')">Copy</button></div><pre id="c12a">GET /api/nsfw?url=https://example.com/photo.jpg</pre></div>
      <div class="cw"><div class="clbl">Example — GIF <button class="cbtn" onclick="cp('c12b')">Copy</button></div><pre id="c12b">GET /api/nsfw?url=https://example.com/animation.gif</pre></div>
      <div class="cw"><div class="clbl">Example — Video <button class="cbtn" onclick="cp('c12c')">Copy</button></div><pre id="c12c">GET /api/nsfw?url=https://example.com/clip.mp4</pre></div>
      <div class="cw"><div class="clbl">Response — Safe</div>
<pre>{
  <span class="k">"is_nsfw"</span>: <span class="b">false</span>,
  <span class="k">"media_type"</span>: <span class="s">"image"</span>,
  <span class="k">"method"</span>: <span class="s">"nudenet"</span>,
  <span class="k">"frames_checked"</span>: <span class="n">1</span>,
  <span class="k">"confidence"</span>: <span class="n">0.08</span>,
  <span class="k">"skin_ratio"</span>: <span class="n">0.06</span>,
  <span class="k">"labels"</span>: [],
  <span class="k">"by"</span>: <span class="s">"t.me/PGL_B4CHI"</span>
}</pre></div>
      <div class="cw"><div class="clbl">Response — NSFW GIF (frame scan)</div>
<pre>{
  <span class="k">"is_nsfw"</span>: <span class="b">true</span>,
  <span class="k">"media_type"</span>: <span class="s">"gif"</span>,
  <span class="k">"method"</span>: <span class="s">"nudenet"</span>,
  <span class="k">"frames_checked"</span>: <span class="n">6</span>,
  <span class="k">"confidence"</span>: <span class="n">0.91</span>,
  <span class="k">"skin_ratio"</span>: <span class="n">0.57</span>,
  <span class="k">"labels"</span>: [{ <span class="k">"label"</span>: <span class="s">"FEMALE_BREAST_EXPOSED"</span>, <span class="k">"confidence"</span>: <span class="n">0.91</span> }],
  <span class="k">"by"</span>: <span class="s">"t.me/PGL_B4CHI"</span>
}</pre></div>
      <div class="cw"><div class="clbl">Response — NSFW Video (frame scan)</div>
<pre>{
  <span class="k">"is_nsfw"</span>: <span class="b">true</span>,
  <span class="k">"media_type"</span>: <span class="s">"video"</span>,
  <span class="k">"method"</span>: <span class="s">"nudenet"</span>,
  <span class="k">"frames_checked"</span>: <span class="n">6</span>,
  <span class="k">"confidence"</span>: <span class="n">0.85</span>,
  <span class="k">"skin_ratio"</span>: <span class="n">0.49</span>,
  <span class="k">"labels"</span>: [{ <span class="k">"label"</span>: <span class="s">"BUTTOCKS_EXPOSED"</span>, <span class="k">"confidence"</span>: <span class="n">0.85</span> }],
  <span class="k">"by"</span>: <span class="s">"t.me/PGL_B4CHI"</span>
}</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span><span class="rt r400">400 Missing / bad URL</span><span class="rt r400">400 File too large</span><span class="rt r500">500 Error</span></div>
    </div>
  </div>

  <div class="card" data-tags="nsfw text check drug keyword explicit content guard">
    <div class="card-head" onclick="toggle(this)">
      <span class="method get">GET</span><span class="path">/api/nsfw/text</span>
      <span class="short">Check text for explicit keywords</span>
      <span class="tog"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></span>
    </div>
    <div class="body">
      <p class="desc">Check if a text string contains NSFW, drug-related, or explicit keywords. Returns the matched term and category.</p>
      <div class="ptitle">Parameters</div>
      <div class="prow"><span class="pname">q</span><span class="ptype">string</span><span class="preq">required</span><span class="pdesc">Text to check</span></div>
      <div class="cw"><div class="clbl">Example <button class="cbtn" onclick="cp('c13')">Copy</button></div><pre id="c13">GET /api/nsfw/text?q=some+text+here</pre></div>
      <div class="cw"><div class="clbl">Response</div>
<pre>{
  <span class="k">"is_nsfw"</span>: <span class="b">false</span>,
  <span class="k">"matched"</span>: <span class="b">null</span>,
  <span class="k">"category"</span>: <span class="b">null</span>,
  <span class="k">"by"</span>: <span class="s">"t.me/PGL_B4CHI"</span>
}</pre></div>
      <div class="rtags"><span class="rt r200">200 OK</span><span class="rt r400">400 Missing q</span></div>
    </div>
  </div>

</div>

<div class="footer">
  <p>Made with ♥ &nbsp;·&nbsp; <a href="https://t.me/PGL_B4CHI" target="_blank">@PGL_B4CHI</a> &nbsp;·&nbsp; <a href="/">🎵 Music Player</a></p>
  <p style="margin-top:8px;font-size:12px;color:var(--text3)">RAJAMODS7 Music API — Free · No authentication required · 24/7</p>
</div>

<script>
function toggle(h){h.closest('.card').classList.toggle('open')}
function cp(id){
  const el=document.getElementById(id);
  if(!el)return;
  navigator.clipboard.writeText(el.innerText).then(()=>{
    const btn=document.querySelector(`[onclick="cp('${id}')"]`);
    if(btn){btn.textContent='Copied!';setTimeout(()=>btn.textContent='Copy',1500)}
  });
}
function filterApis(q){
  q=q.toLowerCase().trim();
  document.querySelectorAll('.card').forEach(c=>{
    const tags=c.dataset.tags||'';
    const path=c.querySelector('.path')?.textContent||'';
    const short=c.querySelector('.short')?.textContent||'';
    const ok=!q||tags.includes(q)||path.includes(q)||short.toLowerCase().includes(q);
    c.style.display=ok?'':'none';
  });
  ['sec-music','sec-bot','sec-nsfw'].forEach(id=>{
    const sec=document.getElementById(id);
    if(!sec)return;
    let el=sec.nextElementSibling,has=false;
    while(el&&!el.classList.contains('sec-title')){
      if(el.classList.contains('card')&&el.style.display!=='none')has=true;
      el=el.nextElementSibling;
    }
    sec.style.display=has?'':'none';
  });
}
document.querySelector('.card')?.classList.add('open');
</script>
</body>
</html>"""
