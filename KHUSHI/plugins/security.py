"""KHUSHI — Security Plugin: Anti-Link & Anti-Flood."""

import asyncio
import time
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from KHUSHI import app
from KHUSHI.core.mongo import mongodb
from KHUSHI.utils.decorators import KhushiGroupAdmin as AdminRightsCheck
from config import BANNED_USERS

_secdb = mongodb.security_settings

_BRAND = (
    "<emoji id='5042192219960771668'>🧸</emoji>"
    "<emoji id='5210820276748566172'>🔤</emoji>"
    "<emoji id='5213301251722203632'>🔤</emoji>"
    "<emoji id='5213301251722203632'>🔤</emoji>"
    "<emoji id='5211032856154885824'>🔤</emoji>"
    "<emoji id='5213337333742454261'>🔤</emoji>"
)

_EM = {
    "shield": "<emoji id='5895483165182529286'>🛡</emoji>",
    "zap":    "<emoji id='5042334757040423886'>⚡️</emoji>",
    "dot":    "<emoji id='5972072533833289156'>🔹</emoji>",
    "warn":   "<emoji id='5420323339723881652'>⚠️</emoji>",
    "on":     "<emoji id='6041597085009056322'>✅</emoji>",
    "off":    "<emoji id='5040042498634810056'>❌</emoji>",
}

_flood_cache: dict[int, list[float]] = defaultdict(list)

_settings_cache: dict[int, dict] = {}

LINK_PATTERN = (
    r"(?i)(https?://|t\.me/|@[a-zA-Z0-9_]{5,}|(bit\.ly|tinyurl|goo\.gl|youtu\.be)/)"
)

import re as _re


def _reply(text: str) -> str:
    return f"<blockquote>{_BRAND}</blockquote>\n\n<blockquote>{text}</blockquote>"


def _close():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("˹ᴄʟᴏꜱᴇ˼", callback_data="close"),
    ]])


async def _get_settings(chat_id: int) -> dict:
    if chat_id in _settings_cache:
        return _settings_cache[chat_id]
    doc = await _secdb.find_one({"chat_id": chat_id})
    if not doc:
        doc = {"chat_id": chat_id, "antilink": False, "antiflood": False, "flood_limit": 5}
    _settings_cache[chat_id] = doc
    return doc


async def _save_settings(chat_id: int, data: dict):
    _settings_cache[chat_id] = data
    await _secdb.update_one(
        {"chat_id": chat_id},
        {"$set": data},
        upsert=True,
    )


async def _is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


@app.on_message(
    filters.command(["antilink"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def antilink_cmd(client, message: Message, lang, chat_id):
    args = message.command[1:]
    settings = await _get_settings(chat_id)

    if not args or args[0].lower() not in ("on", "off"):
        state = f"{_EM['on']} ᴏɴ" if settings.get("antilink") else f"{_EM['off']} ᴏꜰꜰ"
        return await message.reply_text(
            _reply(
                f"{_EM['shield']} <b>Anti-Link</b>\n\n"
                f"{_EM['dot']} <b>Status:</b> <b>{state}</b>\n\n"
                f"{_EM['dot']} Automatically deletes any links, Telegram invite URLs, "
                f"or external URLs shared by non-admins — stops spam and unwanted "
                f"promotions from entering the group."
            ),
            reply_markup=_close(),
        )

    enable = args[0].lower() == "on"
    settings["antilink"] = enable
    await _save_settings(chat_id, settings)
    state = f"{_EM['on']} ᴇɴᴀʙʟᴇᴅ" if enable else f"{_EM['off']} ᴅɪꜱᴀʙʟᴇᴅ"
    await message.reply_text(
        _reply(
            f"{_EM['shield']} <b>ᴀɴᴛɪ-ʟɪɴᴋ — {state}</b>\n"
            f"{_EM['dot']} ʟɪɴᴋꜱ ꜰʀᴏᴍ ɴᴏɴ-ᴀᴅᴍɪɴꜱ ᴡɪʟʟ ʙᴇ "
            f"{'ᴅᴇʟᴇᴛᴇᴅ' if enable else 'ᴀʟʟᴏᴡᴇᴅ'}.\n"
            f"{_EM['dot']} ʙʏ: {message.from_user.mention}"
        ),
        reply_markup=_close(),
    )


@app.on_message(
    filters.command(["antiflood"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def antiflood_cmd(client, message: Message, lang, chat_id):
    args = message.command[1:]
    settings = await _get_settings(chat_id)

    if not args or args[0].lower() not in ("on", "off"):
        state = f"{_EM['on']} ᴏɴ" if settings.get("antiflood") else f"{_EM['off']} ᴏꜰꜰ"
        limit = settings.get("flood_limit", 5)
        return await message.reply_text(
            _reply(
                f"{_EM['zap']} <b>Anti-Flood</b>\n\n"
                f"{_EM['dot']} <b>Status:</b> <b>{state}</b>\n"
                f"{_EM['dot']} <b>Limit:</b> <code>{limit}</code> messages per 5 seconds\n\n"
                f"{_EM['dot']} Detects users who send too many messages in a short time "
                f"and automatically deletes the flood messages — keeps the chat calm and "
                f"prevents spam bursts."
            ),
            reply_markup=_close(),
        )

    enable = args[0].lower() == "on"
    limit = 5
    if len(args) >= 2:
        try:
            limit = max(2, min(int(args[1]), 20))
        except ValueError:
            pass

    settings["antiflood"] = enable
    settings["flood_limit"] = limit
    await _save_settings(chat_id, settings)
    state = f"{_EM['on']} ᴇɴᴀʙʟᴇᴅ" if enable else f"{_EM['off']} ᴅɪꜱᴀʙʟᴇᴅ"
    await message.reply_text(
        _reply(
            f"{_EM['zap']} <b>ᴀɴᴛɪ-ꜰʟᴏᴏᴅ — {state}</b>\n"
            f"{_EM['dot']} ʟɪᴍɪᴛ: <code>{limit}</code> ᴍsɢs ᴘᴇʀ 5 ꜱᴇᴄᴏɴᴅꜱ\n"
            f"{_EM['dot']} ʙʏ: {message.from_user.mention}"
        ),
        reply_markup=_close(),
    )


@app.on_message(filters.group & ~BANNED_USERS & ~filters.service, group=3)
async def security_message_guard(client, message: Message):
    if not message.from_user:
        return
    chat_id = message.chat.id
    user_id = message.from_user.id

    settings = await _get_settings(chat_id)

    if await _is_admin(client, chat_id, user_id):
        return

    text = message.text or message.caption or ""

    if settings.get("antilink") and _re.search(LINK_PATTERN, text):
        try:
            await message.delete()
            warn = await message.reply_text(
                _reply(
                    f"{_EM['warn']} {message.from_user.mention} — "
                    f"<b>ʟɪɴᴋꜱ ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ</b> ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ."
                )
            )
            await asyncio.sleep(5)
            await warn.delete()
        except Exception:
            pass
        return

    if settings.get("antiflood"):
        now = time.time()
        limit = settings.get("flood_limit", 5)
        history = _flood_cache[user_id]
        history = [t for t in history if now - t < 5]
        history.append(now)
        _flood_cache[user_id] = history
        if len(history) > limit:
            try:
                await message.delete()
                warn = await message.reply_text(
                    _reply(
                        f"{_EM['warn']} {message.from_user.mention} — "
                        f"<b>ᴘʟᴇᴀꜱᴇ ꜱʟᴏᴡ ᴅᴏᴡɴ!</b> ꜰʟᴏᴏᴅɪɴɢ ᴅᴇᴛᴇᴄᴛᴇᴅ."
                    )
                )
                _flood_cache[user_id] = []
                await asyncio.sleep(5)
                await warn.delete()
            except Exception:
                pass
