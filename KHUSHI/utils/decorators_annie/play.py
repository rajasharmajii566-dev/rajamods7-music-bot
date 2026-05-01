import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    InviteHashExpired,
    InviteRequestSent,
    PeerIdInvalid,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string
from KHUSHI import YouTube, app
from KHUSHI.misc import SUDOERS
from KHUSHI.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from KHUSHI.utils.inline import botplaylist_markup

# Cache for invite links per chat
links = {}

# Cache for chats where assistant is already a member
assistant_in_chat = {}


def PlayWrapper(command):
    async def wrapper(client, message):
        language = await get_lang(message.chat.id)
        _ = get_string(language)

        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="AnonymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_3"], reply_markup=upl)

        if await is_maintenance():
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)

        if audio_telegram is None and video_telegram is None and url is None:
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                buttons = botplaylist_markup(_)
                return await message.reply_photo(
                    photo=PLAYLIST_IMG_URL,
                    caption=_["play_18"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
            except Exception:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None

        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
        if playty != "Everyone":
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                elif message.from_user.id not in admins:
                    return await message.reply_text(_["play_4"])

        if message.command[0][0] == "v":
            video = True
        else:
            if "-v" in message.text:
                video = True
            else:
                video = True if message.command[0][1] == "v" else None

        if message.command[0][-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = None

        if not await is_active_chat(chat_id):
            try:
                userbot = await get_assistant(chat_id)
            except (IndexError, ValueError):
                return await message.reply_text(
                    "❌ <b>ᴄᴏᴜʟᴅɴ'ᴛ ᴘʟᴀʏ</b>\n\n"
                    "ɴᴏ ᴀssɪsᴛᴀɴᴛ ᴀᴄᴄᴏᴜɴᴛ ɪs ᴄᴏɴɴᴇᴄᴛᴇᴅ.\n"
                    "ᴘʟᴇᴀsᴇ ᴀᴅᴅ ᴀɴ ᴀssɪsᴛᴀɴᴛ ᴀᴄᴄᴏᴜɴᴛ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ."
                )

            # Skip member check if assistant is already confirmed in this chat
            if assistant_in_chat.get(chat_id) != userbot.id:
                try:
                    try:
                        member = await app.get_chat_member(chat_id, userbot.id)
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])

                    if member.status in (
                        ChatMemberStatus.BANNED,
                        ChatMemberStatus.RESTRICTED,
                    ):
                        # Remove from cache if banned/restricted
                        assistant_in_chat.pop(chat_id, None)
                        return await message.reply_text(
                            _["call_2"].format(
                                app.mention, userbot.id, userbot.name, userbot.username
                            ),
                            reply_markup=InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            text="๏ 𝗨ɴʙᴀɴ 𝗔ssɪsᴛᴀɴᴛ ๏",
                                            callback_data="unban_assistant",
                                        )
                                    ]
                                ]
                            ),
                        )

                    # Assistant is already in the group - cache it and skip join
                    assistant_in_chat[chat_id] = userbot.id

                except (UserNotParticipant, PeerIdInvalid):
                    if chat_id in links:
                        invitelink = links[chat_id]
                    else:
                        if message.chat.username:
                            invitelink = message.chat.username
                        else:
                            try:
                                invitelink = await app.export_chat_invite_link(chat_id)
                            except ChatAdminRequired:
                                return await message.reply_text(_["call_1"])
                            except Exception as e:
                                return await message.reply_text(
                                    _["call_3"].format(app.mention, type(e).__name__)
                                )

                    if invitelink.startswith("https://t.me/+"):
                        invitelink = invitelink.replace(
                            "https://t.me/+", "https://t.me/joinchat/"
                        )

                    myu = None
                    try:
                        await userbot.join_chat(invitelink)
                        # Actually joined - show and immediately delete status message
                        try:
                            myu = await message.reply_text(_["call_4"].format(app.mention))
                            await myu.delete()
                            myu = None
                        except Exception:
                            pass
                    except InviteHashExpired:
                        if chat_id in links:
                            del links[chat_id]
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_1"])
                        except Exception as e:
                            return await message.reply_text(
                                _["call_3"].format(app.mention, type(e).__name__)
                            )
                        if invitelink.startswith("https://t.me/+"):
                            invitelink = invitelink.replace(
                                "https://t.me/+", "https://t.me/joinchat/"
                            )
                        links[chat_id] = invitelink
                        await userbot.join_chat(invitelink)
                    except InviteRequestSent:
                        try:
                            await app.approve_chat_join_request(chat_id, userbot.id)
                        except Exception as e:
                            return await message.reply_text(
                                _["call_3"].format(app.mention, type(e).__name__)
                            )
                    except UserAlreadyParticipant:
                        # Already in group - just cache silently, no message
                        pass
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                        try:
                            await userbot.join_chat(invitelink)
                        except Exception:
                            pass
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    finally:
                        if myu:
                            try:
                                await myu.delete()
                            except Exception:
                                pass

                    links[chat_id] = invitelink
                    assistant_in_chat[chat_id] = userbot.id

        return await command(
            client, message, _, chat_id, video, channel, playmode, url, fplay
        )

    return wrapper
