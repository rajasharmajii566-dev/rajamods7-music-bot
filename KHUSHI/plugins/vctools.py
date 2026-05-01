"""KHUSHI — VC Tools: /vcinfo, /vclogger, /mutevc, /unmutevc."""

from pyrogram import filters
from pyrogram.raw.types import (
    GroupCallParticipant,
    PeerChannel,
    PeerChat,
    PeerUser,
    UpdateGroupCall,
    UpdateGroupCallParticipants,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from KHUSHI import app
from KHUSHI.core.call import JARVIS
from KHUSHI.core.mongo import mongodb
from KHUSHI.misc import LOGGER
from KHUSHI.utils.database import group_assistant, is_active_chat
from KHUSHI.utils.decorators import KhushiAdminCheck as AdminRightsCheck
from config import BANNED_USERS

_vclogdb = mongodb.vclogger_settings

# Maps group-call-id → full Telegram chat_id (negative).
# Populated by UpdateGroupCall (fires on VC start / property change).
_call_chat_map: dict[int, int] = {}

_BRAND = (
    "<emoji id='5042192219960771668'>🧸</emoji>"
    "<emoji id='5210820276748566172'>🔤</emoji>"
    "<emoji id='5213301251722203632'>🔤</emoji>"
    "<emoji id='5213301251722203632'>🔤</emoji>"
    "<emoji id='5211032856154885824'>🔤</emoji>"
    "<emoji id='5213337333742454261'>🔤</emoji>"
)

_EM = {
    "vc":    "<emoji id='5226772700113935347'>📞</emoji>",
    "dot":   "<emoji id='5972072533833289156'>🔹</emoji>",
    "zap":   "<emoji id='5042334757040423886'>⚡️</emoji>",
    "mute":  "<emoji id='5467666044815377227'>⚠️</emoji>",
    "log":   "<emoji id='5116468787377341336'>💬</emoji>",
}

_vclog_cache: dict[int, bool] = {}


def _reply(text: str) -> str:
    return f"<blockquote>{_BRAND}</blockquote>\n\n<blockquote>{text}</blockquote>"


def _close():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("˹ᴄʟᴏꜱᴇ˼", callback_data="close"),
    ]])


async def _is_vclog_on(chat_id: int) -> bool:
    if chat_id in _vclog_cache:
        return _vclog_cache[chat_id]
    doc = await _vclogdb.find_one({"chat_id": chat_id})
    result = doc.get("enabled", False) if doc else False
    _vclog_cache[chat_id] = result
    return result


async def _set_vclog(chat_id: int, status: bool):
    _vclog_cache[chat_id] = status
    await _vclogdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True,
    )


@app.on_message(
    filters.command(["vcinfo"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def vcinfo_cmd(client, message: Message, lang, chat_id):
    active = await is_active_chat(chat_id)
    if not active:
        return await message.reply_text(
            _reply(f"{_EM['vc']} ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴄ / sᴛʀᴇᴀᴍ ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ."),
            reply_markup=_close(),
        )

    try:
        assistant = await group_assistant(JARVIS, chat_id)
        participants = await assistant.get_participants(chat_id)

        if not participants:
            return await message.reply_text(
                _reply(f"{_EM['vc']} ᴠᴄ ɪs ᴇᴍᴘᴛʏ ʀɪɢʜᴛ ɴᴏᴡ."),
                reply_markup=_close(),
            )

        lines = []
        for i, p in enumerate(participants[:20], 1):
            uid = getattr(p, "user_id", "?")
            muted = "🔇" if getattr(p, "muted", False) else "🔊"
            lines.append(f"{_EM['dot']} <code>{i}.</code> <code>{uid}</code> {muted}")

        total = len(participants)
        text = (
            f"{_EM['vc']} <b>ᴠᴄ ᴘᴀʀᴛɪᴄɪᴘᴀɴᴛs</b> — <code>{total}</code>\n\n"
            + "\n".join(lines)
        )
        if total > 20:
            text += f"\n\n{_EM['zap']} +{total - 20} ᴍᴏʀᴇ..."
    except Exception as e:
        text = (
            f"{_EM['vc']} <b>ᴠᴄ ɪs ᴀᴄᴛɪᴠᴇ</b>\n"
            f"{_EM['dot']} ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰᴇᴛᴄʜ ᴘᴀʀᴛɪᴄɪᴘᴀɴᴛ ʟɪsᴛ.\n"
            f"{_EM['zap']} <code>{e}</code>"
        )

    await message.reply_text(_reply(text), reply_markup=_close())


@app.on_message(
    filters.command(["vclogger"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def vclogger_cmd(client, message: Message, lang, chat_id):
    args = message.command[1:]
    on = await _is_vclog_on(chat_id)

    if not args or args[0].lower() not in ("on", "off"):
        state = "✅ ᴏɴ" if on else "❌ ᴏꜰꜰ"
        return await message.reply_text(
            _reply(
                f"{_EM['log']} <b>VC Logger</b>\n\n"
                f"{_EM['dot']} <b>Status:</b> <b>{state}</b>\n\n"
                f"{_EM['dot']} Logs every voice chat join and leave event in this group — "
                f"useful to track who enters and exits the VC in real time."
            ),
            reply_markup=_close(),
        )

    enable = args[0].lower() == "on"
    await _set_vclog(chat_id, enable)
    state = "✅ ᴇɴᴀʙʟᴇᴅ" if enable else "❌ ᴅɪꜱᴀʙʟᴇᴅ"
    await message.reply_text(
        _reply(
            f"{_EM['log']} <b>ᴠᴄ ʟᴏɢɢᴇʀ {state}</b>\n"
            f"{_EM['dot']} ᴠᴄ ᴊᴏɪɴ/ʟᴇᴀᴠᴇ ᴡɪʟʟ ʙᴇ "
            f"{'ʟᴏɢɢᴇᴅ' if enable else 'ɴᴏᴛ ʟᴏɢɢᴇᴅ'}.\n"
            f"{_EM['dot']} ʙʏ: {message.from_user.mention}"
        ),
        reply_markup=_close(),
    )


@app.on_message(
    filters.command(["mutevc"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def mutevc_cmd(client, message: Message, lang, chat_id):
    active = await is_active_chat(chat_id)
    if not active:
        return await message.reply_text(
            _reply(f"{_EM['mute']} ɴᴏ ᴀᴄᴛɪᴠᴇ sᴛʀᴇᴀᴍ ᴛᴏ ᴍᴜᴛᴇ."),
            reply_markup=_close(),
        )
    try:
        await JARVIS.mute_stream(chat_id)
        await message.reply_text(
            _reply(
                f"{_EM['mute']} <b>ᴀssɪsᴛᴀɴᴛ ᴍᴜᴛᴇᴅ</b> ɪɴ ᴠᴄ.\n"
                f"{_EM['dot']} ᴜꜱᴇ <code>/unmutevc</code> ᴛᴏ ᴜɴᴍᴜᴛᴇ.\n"
                f"{_EM['dot']} ʙʏ: {message.from_user.mention}"
            ),
            reply_markup=_close(),
        )
    except Exception as e:
        await message.reply_text(
            _reply(f"❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ᴍᴜᴛᴇ: <code>{e}</code>"),
            reply_markup=_close(),
        )


@app.on_message(
    filters.command(["unmutevc"], prefixes=["/", ".", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def unmutevc_cmd(client, message: Message, lang, chat_id):
    active = await is_active_chat(chat_id)
    if not active:
        return await message.reply_text(
            _reply(f"{_EM['mute']} ɴᴏ ᴀᴄᴛɪᴠᴇ sᴛʀᴇᴀᴍ ᴛᴏ ᴜɴᴍᴜᴛᴇ."),
            reply_markup=_close(),
        )
    try:
        await JARVIS.unmute_stream(chat_id)
        await message.reply_text(
            _reply(
                f"{_EM['vc']} <b>ᴀssɪsᴛᴀɴᴛ ᴜɴᴍᴜᴛᴇᴅ</b> ɪɴ ᴠᴄ.\n"
                f"{_EM['dot']} ᴀᴜᴅɪᴏ ɪs ɴᴏᴡ ᴀᴄᴛɪᴠᴇ.\n"
                f"{_EM['dot']} ʙʏ: {message.from_user.mention}"
            ),
            reply_markup=_close(),
        )
    except Exception as e:
        await message.reply_text(
            _reply(f"❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ᴜɴᴍᴜᴛᴇ: <code>{e}</code>"),
            reply_markup=_close(),
        )


# ── VC LOGGER — RAW UPDATE HANDLER ────────────────────────────────────────────
# Tracks group-call participants joining / leaving in real time.
# We need TWO raw-update events:
#   1. UpdateGroupCall       → maps the group-call-id to our chat_id
#   2. UpdateGroupCallParticipants → fires every time a participant joins/leaves

def _peer_to_chat_id(peer) -> int:
    """Convert a raw MTProto Peer object to the Telegram chat_id our DB stores."""
    if isinstance(peer, PeerChannel):
        return int(f"-100{peer.channel_id}")
    if isinstance(peer, PeerChat):
        return -peer.chat_id
    if isinstance(peer, PeerUser):
        return peer.user_id
    return 0


@app.on_raw_update()
async def _vclog_raw_handler(client, update, users, chats):
    try:
        # ── 1. Build call_id → chat_id mapping ──────────────────────────────
        if isinstance(update, UpdateGroupCall):
            cid = _peer_to_chat_id(update.peer)
            call_id = getattr(update.call, "id", None)
            if cid and call_id:
                _call_chat_map[call_id] = cid
            return

        # ── 2. Log join / leave events ──────────────────────────────────────
        if not isinstance(update, UpdateGroupCallParticipants):
            return

        call_id = update.call.id
        chat_id = _call_chat_map.get(call_id)
        if not chat_id:
            return

        if not await _is_vclog_on(chat_id):
            return

        for p in update.participants:
            if not isinstance(p, GroupCallParticipant):
                continue
            just_joined = getattr(p, "just_joined", False)
            left = getattr(p, "left", False)
            if not (just_joined or left):
                continue

            # Resolve display name from the `users` / `chats` dicts in the update
            peer = getattr(p, "peer", None)
            name = "ᴜɴᴋɴᴏᴡɴ"
            if isinstance(peer, PeerUser):
                uid = peer.user_id
                u = users.get(uid)
                if u:
                    first = getattr(u, "first_name", "") or ""
                    last = getattr(u, "last_name", "") or ""
                    name = (first + " " + last).strip() or str(uid)
                else:
                    name = str(uid)
            elif isinstance(peer, PeerChannel):
                cobj = chats.get(peer.channel_id)
                name = getattr(cobj, "title", str(peer.channel_id)) if cobj else str(peer.channel_id)

            action = "ᴊᴏɪɴᴇᴅ ᴠᴄ" if just_joined else "ʟᴇꜰᴛ ᴠᴄ"
            icon = _EM["vc"] if just_joined else _EM["dot"]

            try:
                await app.send_message(
                    chat_id,
                    _reply(f"{icon} <b>{name}</b> {action}"),
                )
            except Exception as send_err:
                LOGGER(__name__).debug(f"[vclogger] send failed for chat={chat_id}: {send_err}")

    except Exception as raw_err:
        LOGGER(__name__).debug(f"[vclog_raw_handler] error: {raw_err}")
