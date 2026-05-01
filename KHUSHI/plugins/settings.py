"""KHUSHI — Settings: /settings with full interactive panel"""

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from KHUSHI import app
from KHUSHI.utils.database import (
    add_nonadmin_chat,
    get_authuser,
    get_authuser_names,
    get_playmode,
    get_playtype,
    get_upvote_count,
    is_nonadmin_chat,
    is_skipmode,
    remove_nonadmin_chat,
    set_playmode,
    set_playtype,
    set_upvotes,
    skip_off,
    skip_on,
)
from KHUSHI.utils.decorators_annie.admins import ActualAdminCB
from KHUSHI.utils.decorators_annie.language import language, languageCB
from KHUSHI.utils.inline import InlineKeyboardButton
from KHUSHI.utils.inline.settings import (
    auth_users_markup,
    playmode_users_markup,
    setting_markup,
    vote_mode_markup,
)
from config import BANNED_USERS
from KHUSHI.utils.ui import BRAND as _BRAND, E as _UIE

_E_GEAR  = "<emoji id='5258096772776991776'>⚙️</emoji>"
_E_GLOBE = "<emoji id='5316832074047441823'>🌐</emoji>"
_E_USER  = "<emoji id='5884366771913233289'>👤</emoji>"


def _settings_text(chat_id: int, chat_title: str) -> str:
    return (
        f"<blockquote>{_BRAND}</blockquote>\n\n"
        "<blockquote>"
        f"┌────── ˹ {_E_GEAR} ꜱᴇᴛᴛɪɴɢs ˼─── ⏤‌‌●\n"
        f"┆{_E_GLOBE} <b>ɢʀᴏᴜᴘ :</b> {chat_title}\n"
        f"┆{_E_USER} <b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{chat_id}</code>\n"
        "└──────────────────────●"
        "</blockquote>"
    )


@app.on_message(filters.command(["settings", "setting"]) & filters.group & ~BANNED_USERS)
@language
async def settings_cmd(client, message: Message, _):
    buttons = setting_markup(_)
    await message.reply_text(
        _settings_text(message.chat.id, message.chat.title or ""),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@app.on_callback_query(filters.regex(r"^SETTINGS_BACK$") & ~BANNED_USERS)
@languageCB
async def settings_back_cb(client, callback: CallbackQuery, _):
    try:
        await callback.answer(_["set_cb_5"])
    except Exception:
        pass
    buttons = setting_markup(_)
    try:
        return await callback.edit_message_text(
            _settings_text(callback.message.chat.id, callback.message.chat.title or ""),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex(r"^SETTINGS_PRIVATE_BACK$") & ~BANNED_USERS)
@languageCB
async def settings_private_back_cb(client, callback: CallbackQuery, _):
    try:
        await callback.answer()
    except Exception:
        pass
    if callback.message.chat.type == ChatType.PRIVATE:
        return await callback.answer(_["set_cb_5"], show_alert=True)
    buttons = setting_markup(_)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex(r"^AUTOPLAY_SETTINGS$") & ~BANNED_USERS)
@languageCB
async def autoplay_settings_cb(client, callback: CallbackQuery, _):
    from KHUSHI.utils.database import is_autoplay
    from KHUSHI.plugins.autoplay import _autoplay_text, autoplay_markup
    chat_id = callback.message.chat.id
    enabled = await is_autoplay(chat_id)
    try:
        await callback.message.edit_text(
            text=_autoplay_text(enabled),
            reply_markup=autoplay_markup(_, enabled, from_settings=True),
        )
    except Exception:
        await callback.answer()


@app.on_callback_query(
    filters.regex(
        r"^(SEARCH_MODE_INFO|PLAY_TYPE_INFO|CHANNEL_MODE_INFO|AUTH_USERS_INFO|CURRENT_VOTE_INFO|VOTE_MODE_INFO|PLAYBACK_SETTINGS|AUTH_SETTINGS|VOTE_SETTINGS)$"
    ) & ~BANNED_USERS
)
@languageCB
async def settings_info_cb(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)

    if command == "SEARCH_MODE_INFO":
        return await callback.answer(_["setting_2"], show_alert=True)
    if command == "CHANNEL_MODE_INFO":
        return await callback.answer(_["setting_5"], show_alert=True)
    if command == "PLAY_TYPE_INFO":
        return await callback.answer(_["setting_6"], show_alert=True)
    if command == "AUTH_USERS_INFO":
        return await callback.answer(_["setting_3"], show_alert=True)
    if command == "VOTE_MODE_INFO":
        return await callback.answer(_["setting_8"], show_alert=True)
    if command == "CURRENT_VOTE_INFO":
        current = await get_upvote_count(callback.message.chat.id)
        return await callback.answer(_["setting_9"].format(current), show_alert=True)

    buttons = None
    if command == "PLAYBACK_SETTINGS":
        try:
            await callback.answer(_["set_cb_2"], show_alert=True)
        except Exception:
            pass
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)

    elif command == "AUTH_SETTINGS":
        try:
            await callback.answer(_["set_cb_1"], show_alert=True)
        except Exception:
            pass
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        buttons = auth_users_markup(_, True) if not is_non_admin else auth_users_markup(_)

    elif command == "VOTE_SETTINGS":
        mode = await is_skipmode(callback.message.chat.id)
        current = await get_upvote_count(callback.message.chat.id)
        buttons = vote_mode_markup(_, current, mode)

    if buttons is None:
        return
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex(r"^(INCREASE_VOTE_COUNT|DECREASE_VOTE_COUNT)$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_count_cb(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    if not await is_skipmode(callback.message.chat.id):
        return await callback.answer(_["setting_10"], show_alert=True)
    current = await get_upvote_count(callback.message.chat.id)
    if command == "DECREASE_VOTE_COUNT":
        final = max(current - 2, 2)
        if final == current:
            await callback.answer(_["setting_11"], show_alert=True)
    else:
        final = min(current + 2, 15)
        if final == current:
            await callback.answer(_["setting_12"], show_alert=True)
    await set_upvotes(callback.message.chat.id, final)
    buttons = vote_mode_markup(_, final, True)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return


@app.on_callback_query(
    filters.regex(r"^(TOGGLE_SEARCH_MODE|TOGGLE_CHANNEL_MODE|TOGGLE_PLAY_TYPE)$") & ~BANNED_USERS
)
@ActualAdminCB
async def playmode_toggle_cb(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)

    if command == "TOGGLE_CHANNEL_MODE":
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(callback.message.chat.id)
            Group = None
        else:
            await remove_nonadmin_chat(callback.message.chat.id)
            Group = True
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)

    elif command == "TOGGLE_SEARCH_MODE":
        try:
            await callback.answer(_["set_cb_3"], show_alert=True)
        except Exception:
            pass
        playmode = await get_playmode(callback.message.chat.id)
        if playmode == "Direct":
            await set_playmode(callback.message.chat.id, "Inline")
            Direct = None
        else:
            await set_playmode(callback.message.chat.id, "Direct")
            Direct = True
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)

    elif command == "TOGGLE_PLAY_TYPE":
        try:
            await callback.answer(_["set_cb_3"], show_alert=True)
        except Exception:
            pass
        playty = await get_playtype(callback.message.chat.id)
        if playty == "Everyone":
            await set_playtype(callback.message.chat.id, "Admin")
            Playtype = True
        else:
            await set_playtype(callback.message.chat.id, "Everyone")
            Playtype = None
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        buttons = playmode_users_markup(_, Direct, Group, Playtype)

    else:
        return

    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex(r"^(TOGGLE_AUTH_MODE|VIEW_AUTH_USERS)$") & ~BANNED_USERS)
@ActualAdminCB
async def auth_settings_cb(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)

    if command == "VIEW_AUTH_USERS":
        _authusers = await get_authuser_names(callback.message.chat.id)
        if not _authusers:
            return await callback.answer(_["setting_4"], show_alert=True)
        try:
            await callback.answer(_["set_cb_4"], show_alert=True)
        except Exception:
            pass
        counter = 0
        msg = _["auth_7"].format(callback.message.chat.title)
        for note in _authusers:
            _note = await get_authuser(callback.message.chat.id, note)
            user_id = _note["auth_user_id"]
            admin_id = _note["admin_id"]
            admin_name = _note["admin_name"]
            try:
                user_obj = await app.get_users(user_id)
                user_name = user_obj.first_name
                counter += 1
            except Exception:
                continue
            msg += f"{counter}➤ {user_name}[<code>{user_id}</code>]\n"
            msg += f"   {_['auth_8']} {admin_name}[<code>{admin_id}</code>]\n\n"
        upl = InlineKeyboardMarkup([[
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="AUTH_SETTINGS", style="primary"),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger"),
        ]])
        try:
            return await callback.edit_message_text(msg, reply_markup=upl)
        except MessageNotModified:
            return

    try:
        await callback.answer(_["set_cb_3"], show_alert=True)
    except Exception:
        pass
    is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
    if not is_non_admin:
        await add_nonadmin_chat(callback.message.chat.id)
        buttons = auth_users_markup(_)
    else:
        await remove_nonadmin_chat(callback.message.chat.id)
        buttons = auth_users_markup(_, True)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return


@app.on_callback_query(filters.regex(r"^TOGGLE_VOTE_MODE$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_mode_cb(client, callback: CallbackQuery, _):
    try:
        await callback.answer(_["set_cb_3"], show_alert=True)
    except Exception:
        pass
    mod = None
    if await is_skipmode(callback.message.chat.id):
        await skip_off(callback.message.chat.id)
    else:
        mod = True
        await skip_on(callback.message.chat.id)
    current = await get_upvote_count(callback.message.chat.id)
    buttons = vote_mode_markup(_, current, mod)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return
