import asyncio
import os
from random import randint
from typing import Union

from pyrogram import enums
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
from KHUSHI import Carbon, YouTube, app
from KHUSHI.core.call import JARVIS
from KHUSHI.misc import db
from KHUSHI.utils.content_filter import is_bad_text
from KHUSHI.utils.database import add_active_video_chat, is_active_chat, is_autoplay, is_content_guard_on, is_global_nsfw_off, is_thumb_enabled
from KHUSHI.utils.exceptions import AssistantErr
from KHUSHI.utils.inline import aq_markup, close_markup, stream_markup, stream_markup_timer
from KHUSHI.utils.pastebin import ANNIEBIN
from KHUSHI.utils.stream.queue import put_queue, put_queue_index
from KHUSHI.utils.thumbnails import get_thumb
from KHUSHI.utils.errors import capture_internal_err
from KHUSHI.utils.raw_send import send_msg_invert_preview
from KHUSHI.plugins.Kishu.nsfw_filter import has_nsfw_text, is_thumb_nsfw_local

THUMB_OFF_VIDEO_URL = "https://files.catbox.moe/4vr2jc.mp4"

# Per-group whitelist: chat_id -> set of whitelisted vidids (by owner/admin)
NSFW_WHITELIST: dict[int, set] = {}


async def _send_stream_msg(
    chat_id: int,
    original_chat_id: int,
    photo,
    caption: str,
    reply_markup,
    has_spoiler: bool = False,
) -> object:
    """
    Thumbnail permanently disabled.
    Sends the stream message with the video URL as a link preview shown ABOVE
    the text (invert_media=True via send_msg_invert_preview).
    """
    # Embed the video URL as an invisible hyperlink at the start of the text.
    # send_msg_invert_preview uses invert_media=True → preview appears at the TOP.
    link_text = f'<a href="{THUMB_OFF_VIDEO_URL}">&#8203;</a>'
    return await send_msg_invert_preview(
        app,
        original_chat_id,
        text=f"{link_text}{caption}",
        reply_markup=reply_markup,
    )


async def _stop_and_block(
    client,
    chat_id: int,
    original_chat_id: int,
    title: str = "Unknown",
    vidid: str = None,
    user_name: str = "Unknown",
    user_id: int = None,
) -> None:
    """Stop any running stream, clear queue, and DM the group owner with details."""
    try:
        await JARVIS.force_stop_stream(chat_id)
    except Exception:
        pass
    try:
        db[chat_id] = []
    except Exception:
        pass

    # Find the group owner to DM them
    owner_id = None
    try:
        async for member in client.get_chat_members(
            original_chat_id, filter=enums.ChatMembersFilter.OWNERS
        ):
            owner_id = member.user.id
            break
    except Exception:
        pass

    if not owner_id:
        return

    user_mention = f"<a href='tg://user?id={user_id}'>{user_name}</a>" if user_id else user_name

    msg = (
        "<blockquote>"
        "🚫 <b>Content Blocked!</b>\n\n"
        f"👤 <b>Play kiya:</b> {user_mention}\n"
        f"🎵 <b>Track:</b> {title}\n\n"
        "⚠️ Is track ka <b>thumbnail ya title</b> mein\n"
        "18+ / illegal / drug content detect hua hai.\n\n"
        "⛔ <b>This is Blocked.</b>"
        "</blockquote>"
    )

    button = None
    if vidid:
        button = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ Unblock — Allow This Track",
                callback_data=f"nsfw_unblock#{original_chat_id}#{vidid}#{title[:30]}"
            )
        ]])

    try:
        await client.send_message(
            owner_id,
            msg,
            parse_mode=ParseMode.HTML,
            reply_markup=button,
        )
    except Exception:
        pass


@capture_internal_err
async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
) -> None:
    if not result:
        return

    forceplay = bool(forceplay)
    is_video = bool(video)

    if not await is_global_nsfw_off() and await is_content_guard_on(original_chat_id):
        title_to_check = None
        if isinstance(result, dict):
            title_to_check = result.get("title") or result.get("filename")
        elif isinstance(result, str):
            title_to_check = result
        if title_to_check:
            bad_word = is_bad_text(title_to_check)
            if bad_word:
                raise AssistantErr(
                    f"🚫 <b>Play Block!</b>\n\n"
                    f"Ye track play nahi ho sakta.\n"
                    f"Title mein inappropriate content detect hua: <code>{bad_word}</code>\n\n"
                    f"<i>Content Guard is group mein active hai. 🛡️</i>"
                )

    if forceplay:
        await JARVIS.force_stop_stream(chat_id)

    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        position = 0

        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(
                    search, videoid=search
                )
            except Exception:
                continue

            if str(duration_min) == "None":
                continue
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

            if has_nsfw_text(title) or (not await is_global_nsfw_off() and await is_content_guard_on(original_chat_id) and is_bad_text(title)):
                continue

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=is_video, videoid=vidid
                    )
                except Exception:
                    raise AssistantErr(_["play_14"])
                if not file_path:
                    raise AssistantErr(_["play_14"])

                await JARVIS.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=is_video,
                    image=thumbnail,
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                    forceplay=forceplay,
                )
                img = await get_thumb(vidid)

                # ── NSFW thumbnail check (always on, respects whitelist) ─
                _wl_p = NSFW_WHITELIST.get(original_chat_id, set())
                _nsfw_p = vidid not in _wl_p and await asyncio.get_event_loop().run_in_executor(None, is_thumb_nsfw_local, img)
                if _nsfw_p:
                    await _stop_and_block(_, chat_id, original_chat_id, title, vidid, user_name, user_id)
                    continue

                button = stream_markup_timer(_, chat_id, "0:00", duration_min, autoplay_on=await is_autoplay(chat_id))
                run = await _send_stream_msg(
                    chat_id,
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:23],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True,
                )
                if db.get(chat_id):
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

        if count == 0:
            return
        link = await ANNIEBIN(msg)
        lines = msg.count("\n")
        car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
        try:
            carbon = await Carbon.generate(car, randint(100, 10000000))
            playlist_photo = carbon
        except Exception:
            playlist_photo = config.PLAYLIST_IMG_URL
        upl = close_markup(_)
        final_position = len(db.get(chat_id) or []) - 1
        if final_position < 0:
            final_position = 0
        return await _send_stream_msg(
            chat_id,
            original_chat_id,
            photo=playlist_photo,
            caption=_["play_21"].format(final_position, link),
            reply_markup=upl,
            has_spoiler=True,
        )

    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]

        # ── NSFW title check (always on, respects whitelist) ────────────
        _wl = NSFW_WHITELIST.get(original_chat_id, set())
        if vidid not in _wl and has_nsfw_text(title):
            return await _stop_and_block(_, chat_id, original_chat_id, title, vidid, user_name, user_id)

        file_path, direct = await YouTube.download(
            vidid, mystic, video=is_video, videoid=vidid
        )
        if not file_path:
            return await mystic.edit_text(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await JARVIS.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            img = await get_thumb(vidid)

            # ── NSFW thumbnail check (always on, respects whitelist) ─────
            _nsfw_yt = vidid not in _wl and await asyncio.get_event_loop().run_in_executor(None, is_thumb_nsfw_local, img)
            if _nsfw_yt:
                return await _stop_and_block(_, chat_id, original_chat_id, title, vidid, user_name, user_id)

            button = stream_markup_timer(_, chat_id, "0:00", duration_min, autoplay_on=await is_autoplay(chat_id))
            run = await _send_stream_msg(
                chat_id,
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True,
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await JARVIS.join_call(chat_id, original_chat_id, file_path, video=False)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            button = stream_markup_timer(_, chat_id, "0:00", duration_min, autoplay_on=await is_autoplay(chat_id))
            run = await _send_stream_msg(
                chat_id,
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True,
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await JARVIS.join_call(chat_id, original_chat_id, file_path, video=is_video)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            if is_video:
                await add_active_video_chat(chat_id)
            button = stream_markup_timer(_, chat_id, "0:00", duration_min, autoplay_on=await is_autoplay(chat_id))
            run = await _send_stream_msg(
                chat_id,
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL,
                caption=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True,
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "Live Track"

        # ── NSFW title check (always on, respects whitelist) ────────────
        _wl = NSFW_WHITELIST.get(original_chat_id, set())
        if vidid not in _wl and has_nsfw_text(title):
            return await _stop_and_block(_, chat_id, original_chat_id, title, vidid, user_name, user_id)

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            if not file_path:
                raise AssistantErr(_["play_14"])

            await JARVIS.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail or None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            img = await get_thumb(vidid)

            # ── NSFW thumbnail check (always on, respects whitelist) ─────
            _nsfw_live = vidid not in _wl and await asyncio.get_event_loop().run_in_executor(None, is_thumb_nsfw_local, img)
            if _nsfw_live:
                return await _stop_and_block(_, chat_id, original_chat_id, title, vidid, user_name, user_id)

            button = stream_markup(_, chat_id)
            run = await _send_stream_msg(
                chat_id,
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True,
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await JARVIS.join_call(
                chat_id,
                original_chat_id,
                link,
                video=is_video,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            run = await _send_stream_msg(
                chat_id,
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True,
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
