import asyncio
import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL, BOT_USERNAME
from KHUSHI.core.dir import CACHE_DIR

_NSFW_THUMB_KEYWORDS = [
    "sex", "sexy", "nude", "naked", "porn", "xxx", "adult", "hentai",
    "boob", "tit", "nipple", "pussy", "vagina", "penis", "dick", "cock",
    "anal", "blowjob", "erotic", "nsfw", "onlyfans", "escort", "prostitut",
    "rape", "slut", "whore", "stripper", "camgirl", "sexting", "explicit",
    "lewd", "horny", "drug", "cocaine", "heroin", "meth", "lsd", "marijuana",
    "weed", "ganja", "crack", "mdma", "ecstasy", "opium", "cannabis",
    "hashish", "ketamine", "overdose", "narcotics", "pedophil", "child abuse",
    "illegal", "darkweb", "terror", "bomb", "weapon", "18+", "x-rated",
    "chut", "lund", "gaand", "nangi", "nanga", "randi",
]

_NSFW_THUMB_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(re.escape(k) for k in _NSFW_THUMB_KEYWORDS) + r")\b"
)


def _title_is_nsfw(title: str) -> bool:
    return bool(_NSFW_THUMB_PATTERN.search(title))

W, H = 1280, 720

CYAN   = (0, 220, 255)
PINK   = (255, 55, 170)
WHITE  = (255, 255, 255)
GOLD   = (255, 205, 50)
BLACK  = (0, 0, 0)

_FONT_BOLD = "KHUSHI/assets/thumb/font2.ttf"
_FONT_REG  = "KHUSHI/assets/thumb/font.ttf"


def _load_fonts():
    try:
        return (
            ImageFont.truetype(_FONT_BOLD, 46),   # [0] title
            ImageFont.truetype(_FONT_REG,  24),   # [1] meta
            ImageFont.truetype(_FONT_BOLD, 21),   # [2] credit
            ImageFont.truetype(_FONT_REG,  19),   # [3] small
            ImageFont.truetype(_FONT_BOLD, 17),   # [4] badge
        )
    except OSError:
        d = ImageFont.load_default()
        return d, d, d, d, d


def _trim(text, font, max_w):
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + "…") <= max_w:
            return text[:i] + "…"
    return "…"


def _circle_mask(img, size):
    img = img.resize((size, size)).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)
    return img


def _rounded(img, w, h, r):
    img = img.resize((w, h)).convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=r, fill=255)
    img.putalpha(mask)
    return img


def _build_thumb_sync(
    raw_path: str,
    cache_path: str,
    title: str,
    duration_txt: str,
    views: str,
) -> str:
    """Heavy PIL processing — runs in a thread executor to avoid blocking the event loop."""
    fonts = _load_fonts()
    ft, fm, fc, fs, fb = fonts

    raw = Image.open(raw_path).convert("RGBA")

    # ══════════════════════════════════════════════════════════════════════
    # 1. CINEMATIC BACKGROUND — extreme blur + very dark
    # ══════════════════════════════════════════════════════════════════════
    bg = ImageEnhance.Brightness(
        raw.resize((W, H)).filter(ImageFilter.GaussianBlur(38))
    ).enhance(0.28).convert("RGBA")

    # Full dark vignette (edges completely black)
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd  = ImageDraw.Draw(vig)
    for i in range(120, 0, -1):
        a = int(210 * (1 - i / 120) ** 1.6)
        vd.rectangle([i, i, W - i, H - i], outline=(0, 0, 0, a), width=1)
    bg = Image.alpha_composite(bg, vig)

    # Right-side gradient (makes text side darker for readability)
    rg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rg)
    for x in range(W // 2, W):
        t = (x - W // 2) / (W // 2)
        a = int(175 * t ** 0.65)
        rd.line([(x, 0), (x, H)], fill=(4, 3, 12, a))
    bg = Image.alpha_composite(bg, rg)

    # Bottom gradient (for text strip)
    bot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd2 = ImageDraw.Draw(bot)
    for y in range(H - 170, H):
        t = (y - (H - 170)) / 170
        a = int(210 * t ** 0.6)
        bd2.line([(0, y), (W, y)], fill=(4, 3, 12, a))
    bg = Image.alpha_composite(bg, bot)

    draw = ImageDraw.Draw(bg)

    # ══════════════════════════════════════════════════════════════════════
    # 2. ALBUM ART — small, elegant, left-center
    # ══════════════════════════════════════════════════════════════════════
    ART_S = 340           # square size
    ART_X = 80
    ART_Y = (H - ART_S) // 2

    # Soft glow behind album art (no borders, just atmosphere)
    for gblur, galpha, gcol in [(48, 18, CYAN), (30, 30, PINK), (16, 50, CYAN)]:
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cx, cy = ART_X + ART_S // 2, ART_Y + ART_S // 2
        r = ART_S // 2 + 40
        ImageDraw.Draw(gl).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*gcol, galpha))
        bg = Image.alpha_composite(bg, gl.filter(ImageFilter.GaussianBlur(gblur)))

    # Thin single accent border (cyan, subtle)
    bl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bl).rounded_rectangle(
        [ART_X - 3, ART_Y - 3, ART_X + ART_S + 3, ART_Y + ART_S + 3],
        radius=22, outline=(*CYAN, 160), width=2
    )
    bg = Image.alpha_composite(bg, bl)

    # Paste rounded art
    art = _rounded(raw, ART_S, ART_S, 20)
    bg.paste(art, (ART_X, ART_Y), art)

    draw = ImageDraw.Draw(bg)

    # ══════════════════════════════════════════════════════════════════════
    # 3. TEXT — floats freely over blurred background, no panel
    # ══════════════════════════════════════════════════════════════════════
    TX = ART_X + ART_S + 60   # text start X
    TEXT_W = W - TX - 50       # available text width

    # ── NOW PLAYING chip (small pill, no big box) ────────────────────────
    chip_txt = "▶  NOW PLAYING"
    chip_w   = int(fb.getlength(chip_txt)) + 22
    chip_y   = 200
    # No fill — just text with a cyan dot accent
    draw.text((TX, chip_y), chip_txt, fill=(*CYAN, 230), font=fb)

    # ── Thin cyan accent line under chip ─────────────────────────────────
    draw.line([(TX, chip_y + 24), (TX + chip_w, chip_y + 24)],
              fill=(*CYAN, 120), width=1)

    # ── Title (large, bold, white) ───────────────────────────────────────
    title_y    = chip_y + 44
    title_line = _trim(title, ft, TEXT_W)
    draw.text((TX, title_y), title_line, fill=WHITE, font=ft)

    # Thin pink underline (matches title width only)
    t_len = int(ft.getlength(title_line))
    draw.line([(TX, title_y + 52), (TX + min(t_len, TEXT_W), title_y + 52)],
              fill=(*PINK, 200), width=2)

    # ── Views & duration (meta line) ─────────────────────────────────────
    meta_y = title_y + 72
    draw.text((TX, meta_y), f"{views} views", fill=(*CYAN, 200), font=fm)

    dur_x = TX + int(fm.getlength(f"{views} views")) + 30
    draw.text((dur_x, meta_y), "·", fill=(*WHITE, 120), font=fm)
    draw.text((dur_x + 18, meta_y), duration_txt, fill=(*PINK, 200), font=fm)

    # ── Equalizer bars (floating, no container) ──────────────────────────
    eq_y  = meta_y + 48
    bar_h_list = [20, 34, 14, 42, 22, 36, 16, 30, 24]
    for i, bh in enumerate(bar_h_list):
        bx = TX + i * 13
        col = CYAN if i % 2 == 0 else PINK
        draw.rounded_rectangle(
            [bx, eq_y + 42 - bh, bx + 8, eq_y + 42],
            radius=3, fill=(*col, 200)
        )

    # ── Progress track (thin, minimal) ───────────────────────────────────
    pb_y   = eq_y + 58
    pb_x1  = TX
    pb_x2  = W - 60
    pb_h   = 4
    draw.rounded_rectangle(
        [pb_x1, pb_y, pb_x2, pb_y + pb_h],
        radius=2, fill=(255, 255, 255, 35)
    )
    fill_end = int(pb_x1 + (pb_x2 - pb_x1) * 0.42)
    draw.rounded_rectangle(
        [pb_x1, pb_y, fill_end, pb_y + pb_h],
        radius=2, fill=(*CYAN, 255)
    )
    # Knob dot
    draw.ellipse(
        [fill_end - 6, pb_y - 4, fill_end + 6, pb_y + pb_h + 4],
        fill=WHITE
    )

    # ── Bottom strip: @username left, Dev credit right ────────────────────
    _uname  = f"@{BOT_USERNAME}" if BOT_USERNAME else "@rajamods7_music2_bot"
    dev_txt = "Dev :- @PGL_B4CHI"

    strip_y = H - 44
    draw.text((ART_X, strip_y), _uname, fill=(*CYAN, 200), font=fc)

    dev_w = int(fc.getlength(dev_txt))
    draw.text((W - dev_w - 40, strip_y), dev_txt, fill=(*GOLD, 220), font=fc)

    # ══════════════════════════════════════════════════════════════════════
    # 4. BOT AVATAR — top left, small circle
    # ══════════════════════════════════════════════════════════════════════
    avatar_path = (
        "KHUSHI/assets/bot_pfp.png"
        if os.path.isfile("KHUSHI/assets/bot_pfp.png")
        else "KHUSHI/assets/upic.png"
    )
    AV, AV_X, AV_Y = 56, 20, 20
    if os.path.isfile(avatar_path):
        try:
            av  = _circle_mask(Image.open(avatar_path), AV)
            acx = AV_X + AV // 2
            acy = AV_Y + AV // 2

            # Soft glow ring behind avatar
            ag = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(ag).ellipse(
                [acx - AV // 2 - 10, acy - AV // 2 - 10,
                 acx + AV // 2 + 10, acy + AV // 2 + 10],
                fill=(*CYAN, 55)
            )
            bg = Image.alpha_composite(bg, ag.filter(ImageFilter.GaussianBlur(8)))

            draw = ImageDraw.Draw(bg)
            draw.ellipse(
                [AV_X - 2, AV_Y - 2, AV_X + AV + 2, AV_Y + AV + 2],
                outline=(*CYAN, 200), width=2
            )
            bg.paste(av, (AV_X, AV_Y), av)
            draw = ImageDraw.Draw(bg)
        except Exception:
            pass

    # ── Cleanup ─────────────────────────────────────────────────────────
    try:
        os.remove(raw_path)
    except OSError:
        pass

    bg.convert("RGB").save(cache_path)
    return cache_path


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v30.png")
    if os.path.exists(cache_path):
        return cache_path

    # ── Fetch metadata ──────────────────────────────────────────────────
    try:
        results_data = await VideosSearch(
            f"https://www.youtube.com/watch?v={videoid}", limit=1
        ).next()
        data      = (results_data.get("result") or [{}])[0]
        title     = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        thumbnail = (data.get("thumbnails") or [{}])[0].get("url") or YOUTUBE_IMG_URL
        duration  = data.get("duration")
        views     = (data.get("viewCount") or {}).get("short") or "Unknown"
    except Exception:
        title, thumbnail, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown"

    if _title_is_nsfw(title):
        return YOUTUBE_IMG_URL

    is_live      = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_txt = "LIVE" if is_live else (duration or "—")

    # ── Download thumbnail ───────────────────────────────────────────────
    raw_path = os.path.join(CACHE_DIR, f"raw_{videoid}.png")
    downloaded = False
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(raw_path, "wb") as f:
                        await f.write(await resp.read())
                    downloaded = True
    except Exception:
        pass

    if not downloaded:
        return YOUTUBE_IMG_URL

    # ── Heavy PIL processing in thread (non-blocking) ────────────────────
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, _build_thumb_sync, raw_path, cache_path, title, duration_txt, views
        )
        return result or YOUTUBE_IMG_URL
    except Exception:
        return YOUTUBE_IMG_URL
