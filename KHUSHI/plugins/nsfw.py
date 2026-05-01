"""KHUSHI — NSFW Filter Plugin."""

import asyncio

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from KHUSHI import app
from KHUSHI.core.mongo import mongodb
from KHUSHI.utils.decorators import KhushiGroupAdmin as AdminRightsCheck
from config import BANNED_USERS

_nsfwdb = mongodb.nsfw_settings

_BRAND = (
    "<emoji id='5042192219960771668'>🧸</emoji> "
    "<b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳 𝗠𝗨𝗦𝗜𝗖</b>"
)

_EM = {
    "nsfw":  "<emoji id='5420323339723881652'>⚠️</emoji>",
    "dot":   "<emoji id='5972072533833289156'>🔹</emoji>",
    "zap":   "<emoji id='5042334757040423886'>⚡️</emoji>",
    "on":    "<emoji id='6041597085009056322'>✅</emoji>",
    "off":   "<emoji id='5040042498634810056'>❌</emoji>",
}

_NSFW_WORDS = {
    "porn", "xxx", "nude", "nudity", "naked", "sex", "hentai", "nsfw",
    "onlyfans", "18+", "adult content", "explicit", "hardcore", "erotic",
    "pornhub", "xvideos", "xnxx", "pussy", "cock", "dick", "ass", "boobs",
    "tits", "fuck", "bitch", "slut", "whore",
}

_nsfw_cache: dict[int, bool] = {}


def _reply(text: str) -> str:
    return f"<blockquote>{_BRAND}</blockquote>\n\n<blockquote>{text}</blockquote>"


def _close():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("˹ᴄʟᴏꜱᴇ˼", callback_data="close"),
    ]])


async def _is_nsfw_on(chat_id: int) -> bool:
    if chat_id in _nsfw_cache:
        return _nsfw_cache[chat_id]
    doc = await _nsfwdb.find_one({"chat_id": chat_id})
    result = doc.get("enabled", False) if doc else False
    _nsfw_cache[chat_id] = result
    return result


async def _set_nsfw(chat_id: int, status: bool):
    _nsfw_cache[chat_id] = status
    await _nsfwdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True,
    )


def _has_nsfw(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _NSFW_WORDS)


@app.on_message(
    filters.command(["nsfw"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def nsfw_cmd(client, message: Message, lang, chat_id):
    args = message.command[1:]
    on = await _is_nsfw_on(chat_id)

    if not args or args[0].lower() not in ("on", "off"):
        state = f"{_EM['on']} ᴏɴ" if on else f"{_EM['off']} ᴏꜰꜰ"
        return await message.reply_text(
            _reply(
                f"{_EM['nsfw']} <b>NSFW Filter</b>\n\n"
                f"{_EM['dot']} <b>Status:</b> <b>{state}</b>\n\n"
                f"{_EM['dot']} Automatically detects and deletes explicit or adult content "
                f"sent by non-admins — including NSFW keywords and inappropriate messages — "
                f"to keep the group safe and clean."
            ),
            reply_markup=_close(),
        )

    enable = args[0].lower() == "on"
    await _set_nsfw(chat_id, enable)
    state = f"{_EM['on']} ᴇɴᴀʙʟᴇᴅ" if enable else f"{_EM['off']} ᴅɪꜱᴀʙʟᴇᴅ"
    await message.reply_text(
        _reply(
            f"{_EM['nsfw']} <b>ɴꜱꜰᴡ ꜰɪʟᴛᴇʀ — {state}</b>\n"
            f"{_EM['dot']} ɴꜱꜰᴡ ᴄᴏɴᴛᴇɴᴛ ᴡɪʟʟ ʙᴇ "
            f"{'ᴅᴇʟᴇᴛᴇᴅ' if enable else 'ᴀʟʟᴏᴡᴇᴅ'}.\n"
            f"{_EM['dot']} ʙʏ: {message.from_user.mention}"
        ),
        reply_markup=_close(),
    )


@app.on_message(filters.group & ~BANNED_USERS & ~filters.service, group=4)
async def nsfw_message_guard(client, message: Message):
    if not message.from_user:
        return
    chat_id = message.chat.id

    if not await _is_nsfw_on(chat_id):
        return

    text = message.text or message.caption or ""
    if not text:
        return

    if _has_nsfw(text):
        try:
            await message.delete()
            warn = await message.reply_text(
                _reply(
                    f"{_EM['nsfw']} {message.from_user.mention} — "
                    f"<b>ɴꜱꜰᴡ ᴄᴏɴᴛᴇɴᴛ ɪꜱ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ</b> ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ."
                )
            )
            await asyncio.sleep(5)
            await warn.delete()
        except Exception:
            pass
