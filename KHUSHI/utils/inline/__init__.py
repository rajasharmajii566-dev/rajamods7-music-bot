from pyrogram.types import InlineKeyboardButton as OriginalIKB
import inspect

try:
    from pyrogram.enums import ButtonStyle
    _HAS_BUTTON_STYLE = True
except ImportError:
    ButtonStyle = None
    _HAS_BUTTON_STYLE = False

_IKB_PARAMS = set(inspect.signature(OriginalIKB.__init__).parameters.keys())
_HAS_ICON  = "icon_custom_emoji_id" in _IKB_PARAMS
_HAS_STYLE = "style" in _IKB_PARAMS and _HAS_BUTTON_STYLE

if _HAS_BUTTON_STYLE:
    _STYLE_MAP = {
        "primary": ButtonStyle.PRIMARY,
        "success": ButtonStyle.SUCCESS,
        "danger":  ButtonStyle.DANGER,
        "default": ButtonStyle.DEFAULT,
    }
else:
    _STYLE_MAP = {}

_COLOR_BLOCK = {
    "primary": "🟦",
    "success": "🟩",
    "danger":  "🟥",
    "premium": "🟪",
    "warning": "🟧",
}
_ALL_BLOCKS = ("🟦", "🟩", "🟥", "🟪", "🟧", "🔵", "🟢", "🔴")


def InlineKeyboardButton(*args, **kwargs):
    raw_style = kwargs.pop("style", None)

    # ── Premium clean buttons ─────────────────────────────────────────────────
    # No box-wrapping. Buttons look clean & premium with the themed emoji
    # already present in the button text (🧸 🌙 🧙 💀 🧪 🍭 🎃 etc.).
    # If the text accidentally still starts with an old colour-block square,
    # strip it so old layouts auto-clean.
    text_val = kwargs.get("text") if "text" in kwargs else (args[0] if args else "")
    if text_val and isinstance(text_val, str):
        cleaned = text_val.strip()
        # Strip leading colour block + space (e.g. legacy "🟦 X")
        for blk in _ALL_BLOCKS:
            if cleaned.startswith(blk + " "):
                cleaned = cleaned[len(blk) + 1:]
                break
        # Strip trailing colour block (e.g. legacy " X 🟦")
        for blk in _ALL_BLOCKS:
            if cleaned.endswith(" " + blk):
                cleaned = cleaned[: -(len(blk) + 1)]
                break
        if cleaned != text_val:
            if "text" in kwargs:
                kwargs["text"] = cleaned
            else:
                args = (cleaned,) + tuple(args[1:])

    if _HAS_STYLE and raw_style is not None:
        if isinstance(raw_style, str):
            kwargs["style"] = _STYLE_MAP.get(raw_style.lower(), ButtonStyle.DEFAULT)
        else:
            kwargs["style"] = raw_style

    if not _HAS_ICON:
        kwargs.pop("icon_custom_emoji_id", None)
    else:
        icon = kwargs.get("icon_custom_emoji_id")
        if icon and isinstance(icon, str):
            try:
                kwargs["icon_custom_emoji_id"] = int(icon)
            except ValueError:
                kwargs.pop("icon_custom_emoji_id", None)

    return OriginalIKB(*args, **kwargs)


from pyrogram.types import InlineKeyboardMarkup


def close_markup(_):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text=_["CLOSE_BUTTON"],
            callback_data="close",
            style="danger",
        )
    ]])


from .extras import *
from .help import *
from .play import *
from .queue import *
from .settings import *
from .start import *
from .speed import *
