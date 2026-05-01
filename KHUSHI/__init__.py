"""
KHUSHI — Independent core initialization.
Own Pyrogram client, own PyTgCalls, own Userbot.
KHUSHI's own platform classes — fully self-contained.
"""

import httpx as _httpx
_orig_httpx_init = _httpx.AsyncClient.__init__
def _patched_httpx_init(self, *args, **kwargs):
    kwargs.pop("proxies", None)
    return _orig_httpx_init(self, *args, **kwargs)
_httpx.AsyncClient.__init__ = _patched_httpx_init


# ── Pyrogram patch: strip <emoji id=...>X</emoji> → X ────────────────────────
# Bot accounts cannot send arbitrary premium custom emojis; Telegram rejects
# the whole message with `400 DOCUMENT_INVALID`. Strip the tag pre-parse so
# only the inner unicode emoji is sent. Keeps every existing string usable.
import re as _re
from pyrogram.parser import html as _phtml

_EMOJI_TAG_RE = _re.compile(
    r'<emoji\s+[^>]*id=["\']?\d+["\']?[^>]*>(.*?)</emoji>',
    _re.IGNORECASE | _re.DOTALL,
)

_orig_html_parse = _phtml.HTML.parse


async def _patched_html_parse(self, text):
    if isinstance(text, str) and "<emoji" in text:
        text = _EMOJI_TAG_RE.sub(r"\1", text)
    return await _orig_html_parse(self, text)


_phtml.HTML.parse = _patched_html_parse

from KHUSHI.logger_setup import LOGGER
from KHUSHI.core.bot import KhushiBot
from KHUSHI.core.userbot import Userbot
from KHUSHI.misc import dbb

from KHUSHI.platforms import (
    AppleAPI,
    CarbonAPI,
    RessoAPI,
    SoundAPI,
    SpotifyAPI,
    TeleAPI,
    YouTubeAPI,
)

# ── KHUSHI's OWN instances ────────────────────────────────────────────────────
app = KhushiBot()
userbot = Userbot()

# ── Platform API instances (stateless, safe to share) ────────────────────────
Apple      = AppleAPI()
Carbon     = CarbonAPI()
SoundCloud = SoundAPI()
Spotify    = SpotifyAPI()
Resso      = RessoAPI()
Telegram   = TeleAPI()
YouTube    = YouTubeAPI()

dbb()

__all__ = [
    "LOGGER",
    "app",
    "userbot",
    "Apple",
    "Carbon",
    "SoundCloud",
    "Spotify",
    "Resso",
    "Telegram",
    "YouTube",
]
