"""
KHUSHI — Centralised UI constants & message builders
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Single source of truth for all premium emojis, brand row, and
reusable blockquote message helpers.  Import from here everywhere.
"""

# ── RAJAMODS7 brand row ─────────────────────────────────────────────────────
# Animated bear emoji + bold sans-serif RAJAMODS7 MUSIC text.
BRAND = (
    "<emoji id='5042192219960771668'>🧸</emoji> "
    "<b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳 𝗠𝗨𝗦𝗜𝗖</b>"
)

# ── Premium emoji set (verified working IDs) ────────────────────────────────
E = {
    # Status
    "check":    "<emoji id='6041597085009056322'>✅</emoji>",
    "cross":    "<emoji id='5447644880824181073'>❌</emoji>",
    "warn":     "<emoji id='5420323339723881652'>⚠️</emoji>",
    "shield":   "<emoji id='5895483165182529286'>🛡</emoji>",
    "ban":      "<emoji id='5361313453196476596'>🚫</emoji>",
    "lock":     "<emoji id='5381645965313085884'>🔒</emoji>",

    # Music / media
    "music":    "<emoji id='5373043798411215697'>🎵</emoji>",
    "notes":    "<emoji id='5373123168026207226'>🎶</emoji>",
    "mic":      "<emoji id='5357418988672927257'>🎙</emoji>",
    "headset":  "<emoji id='5373074324779186371'>🎧</emoji>",
    "radio":    "<emoji id='5373180492080903524'>📻</emoji>",
    "video":    "<emoji id='5375464961822695044'>🎬</emoji>",
    "live":     "<emoji id='5346027782059532469'>▶️</emoji>",

    # Actions / states
    "zap":      "<emoji id='5337120015363304150'>⚡</emoji>",
    "fire":     "<emoji id='5347895529033462557'>🔥</emoji>",
    "star":     "<emoji id='5356706551848769325'>🌟</emoji>",
    "sparkle":  "<emoji id='5432693215988770596'>✨</emoji>",
    "diamond":  "<emoji id='5368319008979943541'>💎</emoji>",
    "bell":     "<emoji id='5386367538735104399'>🔔</emoji>",
    "clock":    "<emoji id='5434890496440903643'>⏰</emoji>",
    "hourglass":"<emoji id='4979027931234830344'>⏳</emoji>",
    "search":   "<emoji id='5395444784611480792'>🔍</emoji>",
    "link":     "<emoji id='5373024494633049785'>🔗</emoji>",
    "crown":    "<emoji id='5394892612508411389'>👑</emoji>",
    "gift":     "<emoji id='5360542106742268290'>🎁</emoji>",
    "pin":      "<emoji id='5472282911506501403'>📌</emoji>",

    # Indicators
    "dot":      "<emoji id='5972072533833289156'>🔹</emoji>",
    "arrow":    "<emoji id='5197521876529545705'>➤</emoji>",
    "play_btn": "<emoji id='5346099622383056961'>▶</emoji>",
    "repeat":   "<emoji id='5373150762449421436'>🔁</emoji>",
    "shuffle":  "<emoji id='5370894089711388826'>🔀</emoji>",
    "skip":     "<emoji id='5373018274545775531'>⏭</emoji>",
    "prev":     "<emoji id='5373040281539151958'>⏮</emoji>",
    "stop":     "<emoji id='5371843862470941498'>⏹</emoji>",
    "pause":    "<emoji id='5373103055199560996'>⏸</emoji>",
    "queue":    "<emoji id='5350982073854661706'>🔊</emoji>",
    "speed":    "<emoji id='5373042927648818686'>🚀</emoji>",
    "seek_fwd": "<emoji id='5349880790124955266'>⏩</emoji>",
    "seek_bk":  "<emoji id='5373054327609502403'>⏪</emoji>",
}


# ── Message builder helpers ──────────────────────────────────────────────────

def _box(content: str, expandable: bool = False) -> str:
    """Wrap content in a Telegram blockquote (optionally expandable)."""
    tag = "blockquote expandable" if expandable else "blockquote"
    return f"<{tag}>{content}</{tag}>"


def brand_block() -> str:
    """Compact brand header blockquote."""
    return _box(BRAND)


def msg(
    header: str,
    body: str,
    *,
    emoji_key: str = "dot",
    expandable: bool = False,
) -> str:
    """
    Build a two-blockquote Annie message:

        ╔ brand row ╗
        ╔ emoji  header ╗
          body lines

    Usage::

        msg("ꜱᴇᴇᴋᴇᴅ", f"Jumped to <code>1:45</code>", emoji_key="zap")
    """
    em = E.get(emoji_key, E["dot"])
    inner = f"{em} <b>{header}</b>"
    if body:
        inner += f"\n{body}"
    return f"{brand_block()}\n{_box(inner, expandable=expandable)}"


def err(text: str) -> str:
    """Standard error message."""
    return msg("ᴇʀʀᴏʀ", text, emoji_key="cross")


def ok(text: str) -> str:
    """Standard success message."""
    return msg("sᴜᴄᴄᴇss", text, emoji_key="check")


def info(header: str, body: str = "", expandable: bool = False) -> str:
    """Standard info message."""
    return msg(header, body, emoji_key="dot", expandable=expandable)


def panel(title: str, rows: list[str], *, expandable: bool = False) -> str:
    """
    Build a box-drawing panel inside a blockquote:

        ┌── ˹ TITLE ˼ ──●
        ┆ emoji  row 1
        ┆ emoji  row 2
        └──────────────●

    ``rows`` is a list of already-formatted line strings (including emoji).
    """
    bar_open  = f"┌────── ˹ {title} ˼ ─── ⏤‌●"
    bar_close = "└──────────────────●"
    body = bar_open + "\n" + "\n".join(f"┆{r}" for r in rows) + "\n" + bar_close
    return f"{brand_block()}\n{_box(body, expandable=expandable)}"
