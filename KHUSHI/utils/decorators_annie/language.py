import asyncio
from pyrogram.errors import MessageNotModified, QueryIdInvalid
from KHUSHI import app
from KHUSHI.logger_setup import LOGGER
from config import SUPPORT_CHAT
from KHUSHI.misc import SUDOERS
from KHUSHI.utils.database import get_lang, is_maintenance
from KHUSHI.utils.reactions import react_to_command
from strings import get_string

_log = LOGGER("KHUSHI.decorators.language")


def language(mystic):
    async def wrapper(_, message, **kwargs):
        asyncio.create_task(react_to_command(message))
        try:
            maintenance = await is_maintenance()
        except Exception:
            maintenance = False
        if maintenance:
            user_id = message.from_user.id if message.from_user else None
            if user_id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )
        try:
            lang = await get_lang(message.chat.id)
            lang = get_string(lang)
        except Exception:
            lang = get_string("en")
        return await mystic(_, message, lang)

    return wrapper

def languageCB(mystic):
    async def wrapper(_, CallbackQuery, **kwargs):
        try:
            maintenance = await is_maintenance()
        except Exception:
            maintenance = False
        if maintenance:
            if CallbackQuery.from_user.id not in SUDOERS:
                return await CallbackQuery.answer(
                    f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    show_alert=True,
                )
        try:
            lang = await get_lang(CallbackQuery.message.chat.id)
            lang = get_string(lang)
        except Exception:
            lang = get_string("en")
        try:
            return await mystic(_, CallbackQuery, lang)
        except (MessageNotModified, QueryIdInvalid):
            pass

    return wrapper


def LanguageStart(mystic):
    async def wrapper(_, message, **kwargs):
        asyncio.create_task(react_to_command(message))
        try:
            lang = await get_lang(message.chat.id)
            lang = get_string(lang)
        except:
            lang = get_string("en")
        try:
            return await mystic(_, message, lang)
        except (MessageNotModified, QueryIdInvalid):
            pass

    return wrapper
