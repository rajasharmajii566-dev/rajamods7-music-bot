from . import InlineKeyboardButton
from config import BOT_USERNAME as _BOT_USERNAME

# ── Progress bar design ───────────────────────────────────────────────────────
#
#  Format:  01:23  ━━━━━━◈╌╌╌╌╌╌  04:20
#
#   ━  BOX DRAWINGS HEAVY HORIZONTAL  — thick played portion
#   ◈  DIAMOND WITH HORIZONTAL RULE    — unique glowing position cursor
#   ╌  LIGHT DOUBLE DASH HORIZONTAL   — airy remaining portion
#
#  What makes it different:
#   • heavy (━) vs dashed (╌) contrast creates instant depth
#   • ◈ cursor has horizontal lines inside so it "sits" on the track
#   • no two Telegram music bots use this exact combination
#

_PLAYED  = "━"   # U+2501 — BOX DRAWINGS HEAVY HORIZONTAL
_CURSOR  = "◈"   # U+25C8 — DIAMOND WITH HORIZONTAL RULE (unique focal point)
_REMAIN  = "╌"   # U+254C — BOX DRAWINGS LIGHT DOUBLE DASH HORIZONTAL
_BAR_LEN = 11    # total segments not counting cursor


def _progress_bar(played_sec: int, duration_sec: int) -> str:
    """Return the styled progress bar string."""
    if duration_sec <= 0:
        pct = 0.0
    else:
        pct = min(played_sec / duration_sec, 1.0)

    filled = max(0, min(int(round(_BAR_LEN * pct)), _BAR_LEN))

    if filled >= _BAR_LEN:
        return _PLAYED * _BAR_LEN + _CURSOR

    return _PLAYED * filled + _CURSOR + _REMAIN * (_BAR_LEN - filled)


def _fmt(sec: int) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    m, s = divmod(max(0, int(sec)), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _webapp_btn():
    """Return the Add to Group button row."""
    return [[
        InlineKeyboardButton(
            text="✨ ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴘ ✨",
            url=f"https://t.me/{_BOT_USERNAME.lstrip('@')}?startgroup=true",
            style="primary",
        )
    ]]


def _webplayer_btn():
    """Return the RAJAMODS7 channel button row (appears above progress bar)."""
    return [[
        InlineKeyboardButton(
            text="🌐 ᴡᴇʙ ᴘʟᴀʏᴇʀ 🎶",
            url="https://t.me/rajamods7pro",
            style="primary",
        )
    ]]


def track_markup(_, videoid, user_id, channel, fplay):
    rows = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
                style="success",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
                style="success",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
                style="danger",
            )
        ],
    ]
    return _webapp_btn() + rows


def control_buttons(_, chat_id, autoplay_on=None):
    rows = [
        [
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"ADMIN Resume|{chat_id}",
                style="success",
            ),
            InlineKeyboardButton(
                text="⏸️",
                callback_data=f"ADMIN Pause|{chat_id}",
                style="primary",
            ),
            InlineKeyboardButton(
                text="🔁",
                callback_data=f"ADMIN Replay|{chat_id}",
                style="primary",
            ),
            InlineKeyboardButton(
                text="⏭️",
                callback_data=f"ADMIN Skip|{chat_id}",
                style="primary",
            ),
            InlineKeyboardButton(
                text="⏹️",
                callback_data=f"ADMIN Stop|{chat_id}",
                style="danger",
            ),
        ],
    ]
    return rows


def stream_markup_timer(_, chat_id, played, dur, autoplay_on=None):
    from KHUSHI.utils.formatters import time_to_seconds
    played_sec   = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    bar = _progress_bar(played_sec, duration_sec)

    progress_row = [
        InlineKeyboardButton(
            text=f"{_fmt(played_sec)}  {bar}  {_fmt(duration_sec)}",
            url=f"https://t.me/{_BOT_USERNAME.lstrip('@')}?startgroup=true",
            style="primary",
        )
    ]

    return (
        _webplayer_btn()
        + [progress_row]
        + control_buttons(_, chat_id, autoplay_on=autoplay_on)
        + [[InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger")]]
    )


def stream_markup(_, chat_id, autoplay_on=None):
    return (
        _webplayer_btn()
        + control_buttons(_, chat_id, autoplay_on=autoplay_on)
        + [[InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger")]]
    )


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    rows = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"AnniePlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
                style="success",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"AnniePlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
                style="success",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
                style="danger",
            ),
        ],
    ]
    return _webapp_btn() + rows


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    rows = [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
                style="success",
            )
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
                style="danger",
            )
        ],
    ]
    return _webapp_btn() + rows


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    short_query = query[:20]
    rows = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
                style="success",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
                style="success",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{short_query}|{user_id}|{channel}|{fplay}",
                style="primary",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {short_query}|{user_id}",
                style="danger",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{short_query}|{user_id}|{channel}|{fplay}",
                style="primary",
            ),
        ],
    ]
    return _webapp_btn() + rows
