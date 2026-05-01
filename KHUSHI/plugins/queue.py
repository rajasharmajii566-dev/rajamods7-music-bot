"""KHUSHI — Queue display with new premium UI."""

from pyrogram import filters
from pyrogram.types import Message

from KHUSHI import app
from KHUSHI.misc import db
from KHUSHI.utils import seconds_to_min
from KHUSHI.utils.database import get_cmode, is_active_chat
from config import BANNED_USERS

_BRAND = (
    "<emoji id='5042192219960771668'>🧸</emoji>"
    "<emoji id='5210820276748566172'>🔤</emoji>"
    "<emoji id='5213301251722203632'>🔤</emoji>"
    "<emoji id='5213301251722203632'>🔤</emoji>"
    "<emoji id='5211032856154885824'>🔤</emoji>"
    "<emoji id='5213337333742454261'>🔤</emoji>"
)
_dot = "<emoji id='5972072533833289156'>🔹</emoji>"
_fire = "<emoji id='5039598514980520994'>❤️‍🔥</emoji>"


@app.on_message(
    filters.command(
        ["q", "queue", "cqueue", "player", "cplayer", "playing", "cplaying"],
        prefixes=["/", ".", "!"],
    )
    & filters.group
    & ~BANNED_USERS
)
async def kqueue(_, message: Message):
    is_channel = message.command[0].startswith("c")
    if is_channel:
        chat_id = await get_cmode(message.chat.id)
        if not chat_id:
            return await message.reply_text("⚠️ ᴄʜᴀɴɴᴇʟ ᴘʟᴀʏ ɴᴏᴛ ꜱᴇᴛ.")
    else:
        chat_id = message.chat.id

    if not await is_active_chat(chat_id):
        return await message.reply_text(
            f"<blockquote>{_BRAND}</blockquote>\n\n"
            "<blockquote>⚠️ ʙᴏᴛ ɪꜱ ɴᴏᴛ ᴀᴄᴛɪᴠᴇ ɪɴ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ.</blockquote>"
        )

    q = db.get(chat_id)
    if not q:
        return await message.reply_text(
            f"<blockquote>{_BRAND}</blockquote>\n\n"
            "<blockquote>📭 ǫᴜᴇᴜᴇ ɪꜱ ᴇᴍᴘᴛʏ.</blockquote>"
        )

    now = q[0]
    title = now.get("title", "Unknown").title()
    user = now.get("by", "Unknown")
    dur = now.get("dur", "Unknown")
    stype = now.get("streamtype", "audio").upper()
    played = now.get("played", 0)
    seconds = now.get("seconds", 0)

    if seconds and int(seconds) > 0:
        progress = int((int(played) / int(seconds)) * 10)
        bar = "▰" * progress + "▱" * (10 - progress)
        time_str = f"{seconds_to_min(played)} / {dur}"
    else:
        bar = "— LIVE —"
        time_str = "LIVE"

    # Build now-playing card
    text = (
        f"<blockquote>{_BRAND}</blockquote>\n\n"
        f"<blockquote>"
        f"┌────── ˹ ɴᴏᴡ ᴘʟᴀʏɪɴɢ ˼\n"
        f"│\n"
        f"│ {_fire} <b>{title}</b>\n"
        f"│\n"
        f"│ {_dot} ᴛʏᴘᴇ  : <code>{stype}</code>\n"
        f"│ {_dot} ᴅᴜʀ   : <code>{time_str}</code>\n"
        f"│ {_dot} ʙʏ    : {user}\n"
        f"│\n"
        f"│ [{bar}]\n"
        f"└─────────────────────"
        f"</blockquote>"
    )

    # Queue list
    if len(q) > 1:
        text += f"\n\n<blockquote><b>📋 ᴜᴘ ɴᴇxᴛ ({len(q)-1})</b>\n"
        for i, item in enumerate(q[1:8], 1):
            t = item.get("title", "Unknown").title()[:40]
            d = item.get("dur", "?")
            by = item.get("by", "?")
            text += f"{_dot} <b>{i}.</b> {t}  <code>{d}</code>  — {by}\n"
        if len(q) > 9:
            text += f"\n<i>... and {len(q)-9} more</i>"
        text += "</blockquote>"

    await message.reply_text(text)
