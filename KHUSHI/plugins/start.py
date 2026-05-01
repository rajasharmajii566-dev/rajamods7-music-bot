"""KHUSHI — Start & Help Plugin."""

import logging
import random
import re

_LOGGER = logging.getLogger(__name__)


def _safe_text(text: str) -> str:
    """Strip <emoji id="..."> custom-emoji wrappers, keep fallback unicode char."""
    return re.sub(r'<emoji id=["\'][^"\']*["\']>(.*?)</emoji>', r'\1', text, flags=re.DOTALL)


from pyrogram import enums, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.parser import Parser
from pyrogram.raw import functions as raw_func, types as raw_types
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InputMediaPhoto, Message

from KHUSHI import app
from KHUSHI.utils.database import (
    add_served_chat,
    get_lang,
    get_served_chats,
    remove_served_chat,
)
from KHUSHI.utils.inline import InlineKeyboardButton
from KHUSHI.utils.reactions import react_to_command
from KHUSHI.utils.inline.help import first_page, second_page, help_back_markup, private_help_panel
from KHUSHI.utils.sys import bot_sys_stats
from KHUSHI.utils.weburl import WEB_URL
from pyrogram.types import WebAppInfo
from config import BANNED_USERS, HELP_IMG_URL, LOGGER_ID, OWNER_USERNAME, START_IMGS, SUPPORT_CHAT, SUPPORT_CHANNEL
from strings import get_string, helpers

_BRAND = (
    "<emoji id='5042192219960771668'>🧸</emoji> "
    "<b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳 𝗠𝗨𝗦𝗜𝗖</b>"
)

# ── Card-style /start template (matches RAJA mockup) ─────────────────────────
# Uses plain unicode emojis only (premium custom emoji IDs need Premium bot
# permissions and cause 400 DOCUMENT_INVALID otherwise).
START_TEXT = (
    "🍭 <b>ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ</b>  ●\n\n"
    "💫 <b>ʜᴇʏ, {mention}</b>\n"
    "ɪ ᴀᴍ <b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳 𝗠𝗨𝗦𝗜𝗖</b> 🇮🇳\n\n"
    "🌸 <b>ᴛʜᴇ ᴍᴏsᴛ ᴘᴏᴡᴇʀꜰᴜʟ &amp; ꜰᴀsᴛᴇsᴛ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ!</b>\n\n"
    "🌷 <b>ᴜᴘᴛɪᴍᴇ :</b>  {up}\n"
    "❄️ <b>sᴇʀᴠᴇʀ sᴛᴏʀᴀɢᴇ :</b>  {disk}\n"
    "❄️ <b>ᴄᴘᴜ ʟᴏᴀᴅ :</b>  {cpu}\n"
    "❄️ <b>ʀᴀᴍ ᴄᴏɴsᴜᴍᴘᴛɪᴏɴ :</b>  {ram}\n\n"
    "🧪 ◆ <b>ᴘᴏᴡᴇʀᴇᴅ ʙʏ »</b> <b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳</b> ✝️\n"
    "<i>#RAJAMODS7_MUSIC</i> 🇮🇳"
)


def _start_kb():
    """Card-style /start keyboard — matches RAJA mockup colour layout."""
    rows = [
        # Row 1 — full-width green MAGIC
        [InlineKeyboardButton("🧸 ᴍᴀɢɪᴄ", callback_data="khushi_help", style="success")],
        # Row 2 — blue COMMANDS / VERSION
        [
            InlineKeyboardButton("🌙 ᴄᴏᴍᴍᴀɴᴅs", callback_data="khushi_help", style="primary"),
            InlineKeyboardButton("🧙 ᴠᴇʀsɪᴏɴ",  callback_data="khushi_version", style="primary"),
        ],
        # Row 3 — purple MASTER GC / red CHATTING HUB
        [
            InlineKeyboardButton("💀 ᴍᴀsᴛᴇʀ ɢᴄ", url=SUPPORT_CHAT, style="premium"),
            InlineKeyboardButton("🧪 ᴄʜᴀᴛᴛɪɴɢ ʜᴜʙ", url="https://t.me/rajamods7pro", style="danger"),
        ],
    ]
    # Row 4 — full-width purple WEBSITE (Web App if available, else channel)
    if WEB_URL:
        rows.append([InlineKeyboardButton("🍭 ᴡᴇʙsɪᴛᴇ", web_app=WebAppInfo(url=WEB_URL), style="premium")])
    else:
        rows.append([InlineKeyboardButton("🍭 ᴡᴇʙsɪᴛᴇ", url="https://t.me/rajamods7pro", style="premium")])
    # Row 5 — full-width red MY MASTER RAJA
    rows.append([InlineKeyboardButton("🎃 ᴍʏ ᴍᴀsᴛᴇʀ ʀᴀᴊᴀ", url="https://t.me/rajamods7pro", style="danger")])
    return InlineKeyboardMarkup(rows)


async def _get_lang(user_id):
    try:
        return await get_lang(user_id)
    except Exception:
        return "en"


async def _raw_edit(client, chat_id, msg_id, caption, markup) -> bool:
    """Edit a message caption via raw MTProto (same parser as SendMedia, supports custom emoji)."""
    try:
        peer = await client.resolve_peer(chat_id)
        parser = Parser(client)
        parsed = await parser.parse(caption, mode=enums.ParseMode.HTML)
        text = parsed.get("message", "")
        entities = parsed.get("entities") or []
        raw_markup = await markup.write(client) if markup else None
        await client.invoke(
            raw_func.messages.EditMessage(
                peer=peer,
                id=msg_id,
                message=text,
                entities=entities,
                reply_markup=raw_markup,
                no_webpage=True,
            )
        )
        return True
    except Exception as e:
        err_str = str(e)
        if "MESSAGE_NOT_MODIFIED" not in err_str and "MESSAGE_ID_INVALID" not in err_str:
            _LOGGER.warning("[RAW_EDIT] failed: %s", e)
        return False


async def _try_send_photo(client, chat_id, photo_url, caption, markup) -> bool:
    """Try to send a photo with spoiler via raw API, then fallback."""
    try:
        peer = await client.resolve_peer(chat_id)
        parser = Parser(client)
        parsed = await parser.parse(caption, mode=enums.ParseMode.HTML)
        text = parsed.get("message", "")
        entities = parsed.get("entities") or []
        raw_markup = await markup.write(client) if markup else None
        media = raw_types.InputMediaPhotoExternal(url=photo_url, spoiler=True)
        await client.invoke(
            raw_func.messages.SendMedia(
                peer=peer,
                media=media,
                message=text,
                random_id=random.randint(-(2**63), 2**63 - 1),
                reply_markup=raw_markup,
                entities=entities,
            )
        )
        return True
    except Exception:
        pass
    try:
        await client.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=caption,
            reply_markup=markup,
        )
        return True
    except Exception:
        pass
    return False


# ── /start ────────────────────────────────────────────────────────────────────

@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
async def khushi_start_private(client, message: Message):
    await react_to_command(message, emoji="🍓")
    param = message.command[1] if len(message.command) > 1 else None

    # ── /start info_<videoid> — show song details in DM ──────────────────────
    if param and param.startswith("info_"):
        vidid = param[5:]
        try:
            from KHUSHI import YouTube
            title, duration_min, duration_sec, thumbnail, _ = await YouTube.details(
                vidid, videoid=True
            )
        except Exception:
            title, duration_min, thumbnail = None, None, None

        if title:
            info_caption = (
                f"<blockquote>{_BRAND}</blockquote>\n\n"
                f"<blockquote>"
                f"<emoji id='5463107823946717464'>🎵</emoji> <b>{title}</b>\n\n"
                f"<emoji id='5972072533833289156'>🔹</emoji> <b>Duration:</b> <code>{duration_min}</code>\n"
                f"<emoji id='5972072533833289156'>🔹</emoji> <b>YouTube ID:</b> <code>{vidid}</code>"
                f"</blockquote>"
            )
            info_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "˹ʏᴏᴜᴛᴜʙᴇ˼",
                        url=f"https://youtu.be/{vidid}",
                        style="danger",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "˹ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴩ˼",
                        url=f"https://t.me/{app.username}?startgroup=true",
                        style="primary",
                    ),
                ],
            ])
            sent = await _try_send_photo(client, message.chat.id, thumbnail or random.choice(START_IMGS), info_caption, info_markup)
            if not sent:
                await message.reply_text(info_caption, reply_markup=info_markup, disable_web_page_preview=True)
        else:
            await message.reply_text(
                f"<blockquote>{_BRAND}</blockquote>\n\n"
                f"<blockquote>❌ ꜱᴏɴɢ ɪɴꜰᴏ ɴᴏᴛ ꜰᴏᴜɴᴅ.</blockquote>",
                disable_web_page_preview=True,
            )
        return

    # ── /start help — open help menu in DM ───────────────────────────────────
    if param == "help" or param == "start":
        lang = await _get_lang(message.from_user.id)
        _ = get_string(lang)
        keyboard = first_page(_)
        caption = _["help_1"].format(SUPPORT_CHAT)
        sent = await _try_send_photo(client, message.chat.id, HELP_IMG_URL, caption, keyboard)
        if not sent:
            await message.reply_text(
                caption,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        return

    # ── Normal /start ─────────────────────────────────────────────────────────
    try:
        UP, CPU, RAM, DISK = await bot_sys_stats()
    except Exception:
        UP, CPU, RAM, DISK = "—", "—", "—", "—"
    caption = START_TEXT.format(
        mention=message.from_user.mention,
        up=UP, cpu=CPU, ram=RAM, disk=DISK,
    )
    markup = _start_kb()
    img = random.choice(START_IMGS)
    sent = await _try_send_photo(client, message.chat.id, img, caption, markup)
    if not sent:
        await message.reply_text(caption, reply_markup=markup, disable_web_page_preview=True)


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
async def khushi_start_group(client, message: Message):
    grp = message.chat.title or "ᴛʜɪꜱ ɢʀᴏᴜᴩ"
    mention = message.from_user.mention if message.from_user else "ʏᴏᴜ"
    caption = (
        f"<blockquote>{_BRAND}</blockquote>\n\n"
        "<blockquote>"
        "<emoji id='5039598514980520994'>❤️‍🔥</emoji>"
        f" ɴᴀᴍᴀsᴛᴇ {mention}!\n\n"
        "<emoji id='5972072533833289156'>🔹</emoji>"
        f" <b>{grp}</b> ᴍᴇɪɴ ᴡᴇʟᴄᴏᴍᴇ ʜᴀɪ!\n"
        "<emoji id='5972072533833289156'>🔹</emoji>"
        " ᴍᴇɪɴ ᴀᴀᴘᴋᴇ ɢʀᴏᴜᴘ ᴋᴀ ᴍᴜꜱɪᴄ ʙᴏᴛ ʜᴏᴏɴ.\n\n"
        "<emoji id='5042334757040423886'>⚡️</emoji>"
        " <b>ǫᴜɪᴄᴋ ᴄᴏᴍᴍᴀɴᴅꜱ</b>\n"
        "<emoji id='5972072533833289156'>🔹</emoji>"
        " <code>/play [ɢᴀᴀɴᴀ]</code> — VC ᴍᴇɪɴ ʙᴀᴊᴀᴏ\n"
        "<emoji id='5972072533833289156'>🔹</emoji>"
        " <code>/reco</code> — ʜɪɴᴅɪ / ᴘᴜɴᴊᴀʙɪ ꜱᴜɢɢᴇꜱᴛɪᴏɴꜱ\n"
        "<emoji id='5972072533833289156'>🔹</emoji>"
        " <code>/help</code> — ᴘᴜʀᴀ ʜᴇʟᴘ ᴅᴇᴋʜᴏ"
        "</blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("˹ʜᴇʟᴘ˼", url=f"https://t.me/{app.username}?start=start", style="primary"),
            InlineKeyboardButton("˹sᴜᴩᴘᴏʀᴛ˼", url=SUPPORT_CHAT, style="success"),
        ],
        [
            InlineKeyboardButton("˹ᴄʜᴀɴɴᴇʟ˼", url=SUPPORT_CHANNEL, style="default"),
            InlineKeyboardButton("˹ᴀᴅᴅ ᴍᴇ˼", url=f"https://t.me/{app.username}?startgroup=true", style="primary"),
        ],
    ])
    img = random.choice(START_IMGS)
    sent = await _try_send_photo(client, message.chat.id, img, caption, markup)
    if not sent:
        await message.reply_text(caption, reply_markup=markup, disable_web_page_preview=True)


# ── Helper: send join/leave log to LOGGER_ID ─────────────────────────────────

async def _send_join_log(chat, adder):
    """Send an advanced styled group-join log to the logger channel."""
    if not LOGGER_ID:
        return
    try:
        total = len(await get_served_chats())
        uname = f"@{chat.username}" if getattr(chat, "username", None) else "ɴᴏɴᴇ"
        adder_text = adder.mention if adder else "ᴜɴᴋɴᴏᴡɴ"
        adder_id   = adder.id if adder else "—"
        log_text = (
            f"<blockquote>{_BRAND}</blockquote>\n\n"
            "<blockquote>"
            "<emoji id='5039827436737397847'>✨</emoji> "
            "<b>ɴᴇᴡ ɢʀᴏᴜᴩ ᴊᴏɪɴᴇᴅ</b>\n\n"
            "<emoji id='5972072533833289156'>🔹</emoji> "
            f"<b>ɢʀᴏᴜᴩ :</b> {chat.title}\n"
            "<emoji id='5972072533833289156'>🔹</emoji> "
            f"<b>ɪᴅ :</b> <code>{chat.id}</code>\n"
            "<emoji id='5972072533833289156'>🔹</emoji> "
            f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {uname}\n\n"
            "<emoji id='5042334757040423886'>⚡️</emoji> "
            f"<b>ᴀᴅᴅᴇᴅ ʙʏ :</b> {adder_text}\n"
            "<emoji id='5042334757040423886'>⚡️</emoji> "
            f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{adder_id}</code>\n\n"
            "<emoji id='5041975203853239332'>🎁</emoji> "
            f"<b>ᴛᴏᴛᴀʟ ɢʀᴏᴜᴩs :</b> <code>{total}</code>"
            "</blockquote>"
        )
        await app.send_message(
            LOGGER_ID, log_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as _e:
        _LOGGER.warning(f"[JoinLog] Failed to send join log: {_e}")


async def _send_leave_log(chat_id: int, chat_title: str, chat_username: str, remover):
    """Send an advanced styled group-leave log to the logger channel."""
    if not LOGGER_ID:
        return
    try:
        total = len(await get_served_chats())
        uname = f"@{chat_username}" if chat_username else "ɴᴏɴᴇ"
        remover_text = remover.mention if remover else "ᴜɴᴋɴᴏᴡɴ"
        remover_id   = remover.id if remover else "—"
        log_text = (
            f"<blockquote>{_BRAND}</blockquote>\n\n"
            "<blockquote>"
            "<emoji id='5039598514980520994'>❤️‍🔥</emoji> "
            "<b>ʟᴇꜰᴛ / ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ɢʀᴏᴜᴩ</b>\n\n"
            "<emoji id='5972072533833289156'>🔹</emoji> "
            f"<b>ɢʀᴏᴜᴩ :</b> {chat_title}\n"
            "<emoji id='5972072533833289156'>🔹</emoji> "
            f"<b>ɪᴅ :</b> <code>{chat_id}</code>\n"
            "<emoji id='5972072533833289156'>🔹</emoji> "
            f"<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {uname}\n\n"
            "<emoji id='5042334757040423886'>⚡️</emoji> "
            f"<b>ʀᴇᴍᴏᴠᴇᴅ ʙʏ :</b> {remover_text}\n"
            "<emoji id='5042334757040423886'>⚡️</emoji> "
            f"<b>ᴜsᴇʀ ɪᴅ :</b> <code>{remover_id}</code>\n\n"
            "<emoji id='5041975203853239332'>🎁</emoji> "
            f"<b>ʀᴇᴍᴀɪɴɪɴɢ ɢʀᴏᴜᴩs :</b> <code>{total}</code>"
            "</blockquote>"
        )
        await app.send_message(
            LOGGER_ID, log_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as _e:
        _LOGGER.warning(f"[LeaveLog] Failed to send leave log: {_e}")


# ── Bot added to group — welcome + log ───────────────────────────────────────

@app.on_message(filters.new_chat_members)
async def bot_added_to_group(client, message: Message):
    """Send a rich welcome card when this bot itself is added to a group."""
    if not message.new_chat_members:
        return
    bot_id = (await client.get_me()).id
    is_bot_added = any(m.id == bot_id for m in message.new_chat_members)
    if not is_bot_added:
        return

    grp = message.chat.title or "ᴀᴀᴘᴋᴀ ɢʀᴏᴜᴩ"
    adder = message.from_user

    # ── Register this chat in DB ──────────────────────────────────────────────
    try:
        await add_served_chat(message.chat.id)
    except Exception:
        pass

    # ── Advanced log to LOGGER_ID ─────────────────────────────────────────────
    await _send_join_log(message.chat, adder)

    # ── Welcome message in the group ──────────────────────────────────────────
    adder_mention = adder.mention if adder else "ᴀᴅᴍɪɴ"
    caption = (
        f"<blockquote>{_BRAND}</blockquote>\n\n"
        "<blockquote>"
        "<emoji id='5039598514980520994'>❤️‍🔥</emoji>"
        f" <b>ʜᴇʟʟᴏ {grp}!</b>\n\n"
        "<emoji id='5972072533833289156'>🔹</emoji>"
        f" ᴛʜᴀɴᴋ ʏᴏᴜ {adder_mention} ꜰᴏʀ ᴀᴅᴅɪɴɢ ᴍᴇ!\n\n"
        "<emoji id='5042334757040423886'>⚡️</emoji>"
        " <b>ᴍᴇʀɪ ᴩᴏᴡᴇʀ</b>\n"
        "<emoji id='5972072533833289156'>🔹</emoji> 🎵 ʜɪɴᴅɪ · ᴩᴜɴᴊᴀʙɪ · ʙᴏʟʟʏᴡᴏᴏᴅ · ɪɴᴛᴇʀɴᴀᴛɪᴏɴᴀʟ\n"
        "<emoji id='5972072533833289156'>🔹</emoji> ᴜʟᴛʀᴀ ᴩᴏꜱᴛ VC ꜱᴛʀᴇᴀᴍɪɴɢ\n"
        "<emoji id='5972072533833289156'>🔹</emoji> ʏᴏᴜᴛᴜʙᴇ · ꜱᴩᴏᴛɪꜰʏ · ꜱᴏᴜɴᴅᴄʟᴏᴜᴅ\n"
        "<emoji id='5972072533833289156'>🔹</emoji> ɢʀᴏᴜᴩ ꜱᴇᴄᴜʀɪᴛʏ + ʜᴜ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ\n\n"
        "<emoji id='5039827436737397847'>✨</emoji>"
        " <code>/play [ɢᴀᴀɴᴀ ᴋᴀ ɴᴀᴀᴍ]</code> ꜱᴇ ʙᴀᴊᴀᴏ!\n"
        "<b>ᴍᴜᴊʜᴇ ᴀᴅᴍɪɴ ʙᴀɴᴀᴏ ᴛᴀᴋɪ ᴍᴀɪɴ VC ᵴᴜɴᴀ ꜱᴀᴋᴏᴏɴ.</b>"
        "</blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("˹ʜᴇʟᴘ˼", url=f"https://t.me/{app.username}?start=start", style="primary"),
            InlineKeyboardButton("˹sᴜᴩᴘᴏʀᴛ˼", url=SUPPORT_CHAT, style="success"),
        ],
        [
            InlineKeyboardButton("˹ᴄʜᴀɴɴᴇʟ˼", url=SUPPORT_CHANNEL, style="default"),
            InlineKeyboardButton("˹ᴀᴅᴅ ᴛᴏ ɢʀᴏᴜᴩ˼", url=f"https://t.me/{app.username}?startgroup=true", style="primary"),
        ],
    ])
    img = random.choice(START_IMGS)
    sent = await _try_send_photo(client, message.chat.id, img, caption, markup)
    if not sent:
        await message.reply_text(caption, reply_markup=markup, disable_web_page_preview=True)


# ── Bot removed from group — leave log ───────────────────────────────────────

@app.on_chat_member_updated(filters.group)
async def bot_member_updated(client, update: ChatMemberUpdated):
    """Detect when the bot is removed/banned from a group and log it."""
    try:
        me = await client.get_me()
        bot_id = me.id

        new = update.new_chat_member
        old = update.old_chat_member

        # Only care about the bot itself
        if not new or new.user.id != bot_id:
            return

        new_status = new.status
        old_status = old.status if old else None

        # Bot was removed / banned / left
        left_statuses = {ChatMemberStatus.BANNED, ChatMemberStatus.LEFT, ChatMemberStatus.RESTRICTED}
        was_active = old_status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER, ChatMemberStatus.OWNER}
        is_gone    = new_status in left_statuses

        if was_active and is_gone:
            chat = update.chat
            chat_id    = chat.id
            chat_title = getattr(chat, "title", str(chat_id))
            chat_uname = getattr(chat, "username", None)
            remover    = update.from_user

            # Remove from served chats DB
            try:
                await remove_served_chat(chat_id)
            except Exception:
                pass

            await _send_leave_log(chat_id, chat_title, chat_uname, remover)

    except Exception as _e:
        _LOGGER.debug(f"[MemberUpdate] Error: {_e}")


# ── /help ─────────────────────────────────────────────────────────────────────

@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
async def khushi_help_pm(client, message: Message):
    await react_to_command(message, emoji="🍓")
    lang = await _get_lang(message.from_user.id)
    _ = get_string(lang)
    keyboard = first_page(_)
    caption = _["help_1"].format(SUPPORT_CHAT)
    try:
        await message.delete()
    except Exception:
        pass
    sent = await _try_send_photo(client, message.chat.id, HELP_IMG_URL, caption, keyboard)
    if not sent:
        await client.send_message(
            message.chat.id,
            caption,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )


@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
async def khushi_help_group(client, message: Message):
    await react_to_command(message, emoji="🍓")
    lang = await _get_lang(message.from_user.id)
    _ = get_string(lang)
    markup = InlineKeyboardMarkup(private_help_panel(_))
    await message.reply_text(
        _["help_2"],
        reply_markup=markup,
        disable_web_page_preview=True,
    )


# ── Help button callback — open category list ─────────────────────────────────

@app.on_callback_query(filters.regex("^(khushi_help|annie_help|open_help)$") & ~BANNED_USERS)
async def khushi_help_cb(client, query):
    await query.answer()
    lang = await _get_lang(query.from_user.id)
    _ = get_string(lang)
    keyboard = first_page(_)
    caption = _["help_1"].format(SUPPORT_CHAT)

    msg = query.message
    edited = await _raw_edit(client, msg.chat.id, msg.id, caption, keyboard)

    if not edited:
        try:
            await msg.edit_caption(
                caption, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML
            )
            edited = True
        except Exception as e:
            _LOGGER.warning("[HELP_CB] edit_caption failed: %s", e)

    if not edited:
        try:
            await msg.edit_text(
                caption, reply_markup=keyboard,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
            edited = True
        except Exception as e:
            _LOGGER.warning("[HELP_CB] edit_text failed: %s", e)

    if not edited:
        _LOGGER.warning("[HELP_CB] All edits failed — falling back to delete+send")
        safe_caption = _safe_text(caption)
        try:
            await msg.delete()
        except Exception:
            pass
        try:
            await client.send_photo(
                msg.chat.id,
                photo=HELP_IMG_URL,
                caption=safe_caption,
                reply_markup=keyboard,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            try:
                await client.send_message(
                    msg.chat.id,
                    safe_caption,
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                _LOGGER.error("[HELP_CB] send_message also failed: %s", e)


# ── Category button callbacks — show specific help section ────────────────────

@app.on_callback_query(filters.regex(r"^help_callback hb(\d+)_p(\d+)$") & ~BANNED_USERS)
async def help_section_cb(client, query):
    match = re.match(r"help_callback hb(\d+)_p(\d+)", query.data)
    if not match:
        return await query.answer("Invalid callback.", show_alert=True)

    number = int(match.group(1))
    current_page = int(match.group(2))
    await query.answer()

    lang = await _get_lang(query.from_user.id)
    _ = get_string(lang)

    help_text = getattr(helpers, f"HELP_{number}", None)
    if not help_text:
        return await query.answer("ɪɴᴠᴀʟɪᴅ ʜᴇʟᴘ ᴛᴏᴘɪᴄ.", show_alert=True)

    back_kb = help_back_markup(_, number)
    safe_help_text = _safe_text(help_text)

    edited = False
    try:
        await query.message.edit_caption(
            help_text, reply_markup=back_kb, parse_mode=enums.ParseMode.HTML
        )
        edited = True
    except Exception as e:
        _LOGGER.warning("[HELP_SEC] edit_caption hb%d failed: %s", number, e)

    if not edited:
        try:
            await query.message.edit_text(
                help_text, reply_markup=back_kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
            edited = True
        except Exception as e2:
            _LOGGER.warning("[HELP_SEC] edit_text hb%d failed: %s", number, e2)

    if not edited:
        _LOGGER.warning("[HELP_SEC] hb%d — falling back to delete+send", number)
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await client.send_message(
                query.message.chat.id,
                safe_help_text,
                reply_markup=back_kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e3:
            _LOGGER.error("[HELP_SEC] send_message hb%d also failed: %s", number, e3)


# ── Next / Prev section navigation (loop) ────────────────────────────────────

@app.on_callback_query(filters.regex(r"^help_nav_(\d+)$") & ~BANNED_USERS)
async def help_nav_cb(client, query):
    match = re.match(r"help_nav_(\d+)", query.data)
    if not match:
        return await query.answer()

    section = int(match.group(1))
    await query.answer()

    lang = await _get_lang(query.from_user.id)
    _ = get_string(lang)

    help_text = getattr(helpers, f"HELP_{section}", None)
    if not help_text:
        return await query.answer("ɪɴᴠᴀʟɪᴅ sᴇᴄᴛɪᴏɴ.", show_alert=True)

    nav_kb = help_back_markup(_, section)
    safe_help_text = _safe_text(help_text)

    edited = False
    try:
        await query.message.edit_caption(
            help_text, reply_markup=nav_kb, parse_mode=enums.ParseMode.HTML
        )
        edited = True
    except Exception:
        pass

    if not edited:
        try:
            await query.message.edit_text(
                help_text, reply_markup=nav_kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
            edited = True
        except Exception:
            pass

    if not edited:
        edited = await _raw_edit(client, query.message.chat.id, query.message.id, help_text, nav_kb)

    if not edited:
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await client.send_message(
                query.message.chat.id,
                safe_help_text,
                reply_markup=nav_kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            _LOGGER.error("[HELP_NAV] send_message failed: %s", e)


# ── Back to category list (page 1 or 2) ──────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(help_back|help_page)_(\d+)$") & ~BANNED_USERS)
async def help_back_cb(client, query):
    await query.answer()
    match = re.match(r"^(?:help_back|help_page)_(\d+)$", query.data)
    page = int(match.group(1)) if match else 1
    lang = await _get_lang(query.from_user.id)
    _ = get_string(lang)
    keyboard = second_page(_) if page == 2 else first_page(_)
    caption = _["help_1"].format(SUPPORT_CHAT)

    edited = False
    try:
        await query.message.edit_caption(
            caption, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML
        )
        edited = True
    except Exception:
        pass

    if not edited:
        try:
            await query.message.edit_text(
                caption, reply_markup=keyboard,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
            edited = True
        except Exception:
            pass

    if not edited:
        try:
            await query.message.delete()
        except Exception:
            pass
        sent = await _try_send_photo(client, query.message.chat.id, HELP_IMG_URL, caption, keyboard)
        if not sent:
            try:
                await client.send_message(
                    query.message.chat.id,
                    _safe_text(caption),
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                _LOGGER.error("[HELP_BACK] send_message also failed: %s", e)


# ── Back to main start panel ──────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^back_to_main$") & ~BANNED_USERS)
async def back_to_main_cb(client, query):
    await query.answer()
    try:
        UP, CPU, RAM, DISK = await bot_sys_stats()
    except Exception:
        UP, CPU, RAM, DISK = "—", "—", "—", "—"
    caption = (
        f"<blockquote>{_BRAND}</blockquote>\n\n"
        + START_TEXT.format(
            mention=query.from_user.mention,
            up=UP, cpu=CPU, ram=RAM, disk=DISK,
        )
    )
    markup = _start_kb()
    img = random.choice(START_IMGS)

    edited = False
    try:
        await query.message.edit_media(
            InputMediaPhoto(media=img, caption=caption, parse_mode=enums.ParseMode.HTML),
            reply_markup=markup,
        )
        edited = True
    except Exception:
        pass

    if not edited:
        try:
            await query.message.edit_caption(
                caption, reply_markup=markup, parse_mode=enums.ParseMode.HTML
            )
            edited = True
        except Exception:
            pass

    if not edited:
        try:
            await query.message.edit_text(
                caption, reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
            edited = True
        except Exception:
            pass

    if not edited:
        try:
            await query.message.delete()
        except Exception:
            pass
        sent = await _try_send_photo(client, query.message.chat.id, img, caption, markup)
        if not sent:
            try:
                await client.send_message(
                    query.message.chat.id,
                    caption,
                    reply_markup=markup,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass


# ── Version callback ─────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^khushi_version$") & ~BANNED_USERS)
async def khushi_version_cb(client, query):
    """Show bot version & runtime info on the version button."""
    try:
        UP, CPU, RAM, DISK = await bot_sys_stats()
    except Exception:
        UP, CPU, RAM, DISK = "—", "—", "—", "—"
    import platform, sys as _sys
    try:
        import pyrogram as _pyro
        pyro_ver = _pyro.__version__
    except Exception:
        pyro_ver = "—"
    try:
        from pytgcalls import __version__ as ptc_ver
    except Exception:
        ptc_ver = "—"

    text = (
        "<blockquote>🧙 <b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳 𝗠𝗨𝗦𝗜𝗖 — ᴠᴇʀsɪᴏɴ</b></blockquote>\n"
        "<blockquote>"
        f"🌷 <b>ʙᴏᴛ ᴠᴇʀsɪᴏɴ :</b>  <code>v3.0.0</code>\n"
        f"🌷 <b>ᴘʏᴛʜᴏɴ :</b>  <code>{platform.python_version()}</code>\n"
        f"🌷 <b>ᴘʏʀᴏɢʀᴀᴍ :</b>  <code>{pyro_ver}</code>\n"
        f"🌷 <b>ᴘʏᴛɢᴄᴀʟʟs :</b>  <code>{ptc_ver}</code>\n"
        f"🌷 <b>sʏsᴛᴇᴍ :</b>  <code>{platform.system()} {platform.release()}</code>"
        "</blockquote>\n"
        "<blockquote>"
        f"❄️ <b>ᴜᴘᴛɪᴍᴇ :</b>  {UP}\n"
        f"❄️ <b>ᴄᴘᴜ :</b>  {CPU}    <b>ʀᴀᴍ :</b>  {RAM}    <b>ᴅɪsᴋ :</b>  {DISK}"
        "</blockquote>\n"
        "<blockquote>🧪 ◆ <b>ᴘᴏᴡᴇʀᴇᴅ ʙʏ »</b> <b>𝗥𝗔𝗝𝗔𝗠𝗢𝗗𝗦𝟳</b> ✝️</blockquote>"
    )
    back_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="khushi_back", style="primary"),
    ]])
    try:
        await query.message.edit_caption(text, reply_markup=back_kb, parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await query.message.edit_text(text, reply_markup=back_kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        except Exception:
            await query.answer("ᴠᴇʀsɪᴏɴ ɪɴғᴏ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)


# ── Start back button ─────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^(khushi_back|annie_back)$") & ~BANNED_USERS)
async def khushi_back_cb(client, query):
    await query.answer()
    try:
        UP, CPU, RAM, DISK = await bot_sys_stats()
    except Exception:
        UP, CPU, RAM, DISK = "—", "—", "—", "—"
    caption = START_TEXT.format(
        mention=query.from_user.mention,
        up=UP, cpu=CPU, ram=RAM, disk=DISK,
    )
    markup = _start_kb()
    try:
        await query.message.edit_caption(
            caption, reply_markup=markup, parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        try:
            await query.message.edit_text(
                caption, reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass


# ── Close button ──────────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex("^close$") & ~BANNED_USERS)
async def close_message(client, query):
    try:
        await query.message.delete()
    except Exception:
        await query.answer()
