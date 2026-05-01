import random
from typing import Dict, List, Union

from KHUSHI.core.mongo import mongodb

authdb = mongodb.adminauth
authuserdb = mongodb.authuser
autoenddb = mongodb.autoend
autplaydb = mongodb.autoplaymode
assdb = mongodb.assistants
assistantdb = mongodb.mode247
blacklist_chatdb = mongodb.blacklistChat
blockeddb = mongodb.blockedusers
chatsdb = mongodb.chats
channeldb = mongodb.cplaymode
countdb = mongodb.upcount
gbansdb = mongodb.gban
langdb = mongodb.language
onoffdb = mongodb.onoffper
playmodedb = mongodb.playmode
playtypedb = mongodb.playtypedb
skipdb = mongodb.skipmode
sudoersdb = mongodb.sudoers
usersdb = mongodb.tgusersdb
contentguarddb = mongodb.contentguard


active = []
activevideo = []
assistantdict = {}
autoend = {}
autoplay_cache = {}
count = {}
channelconnect = {}
langm = {}
loop = {}
maintenance = []
nonadmin = {}
pause = {}
playmode = {}
playtype = {}
skipmode = {}
mute = {}

async def get_assistant_number(chat_id: int) -> str:
    assistant = assistantdict.get(chat_id)
    return assistant


async def get_client(assistant: int):
    from KHUSHI import userbot
    if int(assistant) == 1:
        return userbot.one
    elif int(assistant) == 2:
        return userbot.two
    elif int(assistant) == 3:
        return userbot.three
    elif int(assistant) == 4:
        return userbot.four
    elif int(assistant) == 5:
        return userbot.five


async def set_assistant_new(chat_id, number):
    number = int(number)
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": number}},
        upsert=True,
    )


async def set_assistant(chat_id):
    from KHUSHI.core.userbot import assistants

    ran_assistant = random.choice(assistants)
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    userbot = await get_client(ran_assistant)
    return userbot


async def get_assistant(chat_id: int) -> str:
    from KHUSHI.core.userbot import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if not dbassistant:
            userbot = await set_assistant(chat_id)
            return userbot
        else:
            got_assis = dbassistant["assistant"]
            if got_assis in assistants:
                assistantdict[chat_id] = got_assis
                userbot = await get_client(got_assis)
                return userbot
            else:
                userbot = await set_assistant(chat_id)
                return userbot
    else:
        if assistant in assistants:
            userbot = await get_client(assistant)
            return userbot
        else:
            userbot = await set_assistant(chat_id)
            return userbot


async def set_calls_assistant(chat_id):
    from KHUSHI.core.userbot import assistants
    from KHUSHI.utils.exceptions import AssistantErr

    if not assistants:
        raise AssistantErr(
            "No assistant accounts are active. Please add at least one session string (STRING1–STRING5) to use voice chat features."
        )
    ran_assistant = random.choice(assistants)
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    return ran_assistant


async def group_assistant(self, chat_id: int) -> int:
    from KHUSHI.core.userbot import assistants
    from KHUSHI.utils.exceptions import AssistantErr

    if not assistants:
        raise AssistantErr(
            "No assistant accounts are active. Please add at least one session string (STRING1–STRING5) to use voice chat features."
        )
    assistant = assistantdict.get(chat_id)
    if not assistant:
        try:
            dbassistant = await assdb.find_one({"chat_id": chat_id})
        except Exception:
            dbassistant = None
        if not dbassistant:
            try:
                assis = await set_calls_assistant(chat_id)
            except Exception:
                assis = min(assistants)
        else:
            assis = dbassistant["assistant"]
            if assis in assistants:
                assistantdict[chat_id] = assis
                assis = assis
            else:
                try:
                    assis = await set_calls_assistant(chat_id)
                except Exception:
                    assis = min(assistants)
    else:
        if assistant in assistants:
            assis = assistant
        else:
            try:
                assis = await set_calls_assistant(chat_id)
            except Exception:
                assis = min(assistants)
    if int(assis) == 1:
        return self.one
    elif int(assis) == 2:
        return self.two
    elif int(assis) == 3:
        return self.three
    elif int(assis) == 4:
        return self.four
    elif int(assis) == 5:
        return self.five


async def is_skipmode(chat_id: int) -> bool:
    mode = skipmode.get(chat_id)
    if not mode:
        user = await skipdb.find_one({"chat_id": chat_id})
        if not user:
            skipmode[chat_id] = True
            return True
        skipmode[chat_id] = False
        return False
    return mode


async def skip_on(chat_id: int):
    skipmode[chat_id] = True
    user = await skipdb.find_one({"chat_id": chat_id})
    if user:
        return await skipdb.delete_one({"chat_id": chat_id})


async def skip_off(chat_id: int):
    skipmode[chat_id] = False
    user = await skipdb.find_one({"chat_id": chat_id})
    if not user:
        return await skipdb.insert_one({"chat_id": chat_id})


async def get_upvote_count(chat_id: int) -> int:
    mode = count.get(chat_id)
    if not mode:
        mode = await countdb.find_one({"chat_id": chat_id})
        if not mode:
            return 5
        count[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_upvotes(chat_id: int, mode: int):
    count[chat_id] = mode
    await countdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def is_autoend() -> bool:
    chat_id = 1234
    user = await autoenddb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def autoend_on():
    chat_id = 1234
    await autoenddb.insert_one({"chat_id": chat_id})


async def autoend_off():
    chat_id = 1234
    await autoenddb.delete_one({"chat_id": chat_id})


async def get_loop(chat_id: int) -> int:
    lop = loop.get(chat_id)
    if not lop:
        return 0
    return lop


async def set_loop(chat_id: int, mode: int):
    loop[chat_id] = mode


async def get_cmode(chat_id: int) -> int:
    mode = channelconnect.get(chat_id)
    if not mode:
        mode = await channeldb.find_one({"chat_id": chat_id})
        if not mode:
            return None
        channelconnect[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_cmode(chat_id: int, mode: int):
    channelconnect[chat_id] = mode
    await channeldb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playtype(chat_id: int) -> str:
    mode = playtype.get(chat_id)
    if not mode:
        mode = await playtypedb.find_one({"chat_id": chat_id})
        if not mode:
            playtype[chat_id] = "Everyone"
            return "Everyone"
        playtype[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playtype(chat_id: int, mode: str):
    playtype[chat_id] = mode
    await playtypedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playmode(chat_id: int) -> str:
    mode = playmode.get(chat_id)
    if not mode:
        mode = await playmodedb.find_one({"chat_id": chat_id})
        if not mode:
            playmode[chat_id] = "Direct"
            return "Direct"
        playmode[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playmode(chat_id: int, mode: str):
    playmode[chat_id] = mode
    await playmodedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_lang(chat_id: int) -> str:
    mode = langm.get(chat_id)
    if not mode:
        lang = await langdb.find_one({"chat_id": chat_id})
        if not lang:
            langm[chat_id] = "en"
            return "en"
        langm[chat_id] = lang["lang"]
        return lang["lang"]
    return mode


async def set_lang(chat_id: int, lang: str):
    langm[chat_id] = lang
    await langdb.update_one({"chat_id": chat_id}, {"$set": {"lang": lang}}, upsert=True)


async def is_music_playing(chat_id: int) -> bool:
    mode = pause.get(chat_id)
    if not mode:
        return False
    return mode


async def music_on(chat_id: int):
    pause[chat_id] = True


async def music_off(chat_id: int):
    pause[chat_id] = False

async def is_muted(chat_id: int) -> bool:
    mode = mute.get(chat_id)
    if not mode:
        return False
    return mode


async def mute_on(chat_id: int):
    mute[chat_id] = True


async def mute_off(chat_id: int):
    mute[chat_id] = False

async def get_active_chats() -> list:
    return active


async def is_active_chat(chat_id: int) -> bool:
    if chat_id not in active:
        return False
    else:
        return True


async def add_active_chat(chat_id: int):
    if chat_id not in active:
        active.append(chat_id)


async def remove_active_chat(chat_id: int):
    if chat_id in active:
        active.remove(chat_id)


async def get_active_video_chats() -> list:
    return activevideo


async def is_active_video_chat(chat_id: int) -> bool:
    if chat_id not in activevideo:
        return False
    else:
        return True


async def add_active_video_chat(chat_id: int):
    if chat_id not in activevideo:
        activevideo.append(chat_id)


async def remove_active_video_chat(chat_id: int):
    if chat_id in activevideo:
        activevideo.remove(chat_id)


async def check_nonadmin_chat(chat_id: int) -> bool:
    user = await authdb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def is_nonadmin_chat(chat_id: int) -> bool:
    mode = nonadmin.get(chat_id)
    if not mode:
        user = await authdb.find_one({"chat_id": chat_id})
        if not user:
            nonadmin[chat_id] = False
            return False
        nonadmin[chat_id] = True
        return True
    return mode


async def add_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = True
    is_admin = await check_nonadmin_chat(chat_id)
    if is_admin:
        return
    return await authdb.insert_one({"chat_id": chat_id})


async def remove_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = False
    is_admin = await check_nonadmin_chat(chat_id)
    if not is_admin:
        return
    return await authdb.delete_one({"chat_id": chat_id})


async def is_on_off(on_off: int) -> bool:
    onoff = await onoffdb.find_one({"on_off": on_off})
    if not onoff:
        return False
    return True


async def add_on(on_off: int):
    is_on = await is_on_off(on_off)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": on_off})


async def add_off(on_off: int):
    is_off = await is_on_off(on_off)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": on_off})


async def is_maintenance():
    if not maintenance:
        get = await onoffdb.find_one({"on_off": 1})
        if not get:
            maintenance.clear()
            maintenance.append(2)
            return False
        else:
            maintenance.clear()
            maintenance.append(1)
            return True
    else:
        if 1 in maintenance:
            return True
        else:
            return False


async def maintenance_off():
    maintenance.clear()
    maintenance.append(2)
    is_off = await is_on_off(1)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": 1})


async def maintenance_on():
    maintenance.clear()
    maintenance.append(1)
    is_on = await is_on_off(1)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": 1})


async def is_served_user(user_id: int) -> bool:
    user = await usersdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def get_served_users() -> list:
    users_list = []
    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(user)
    return users_list


async def add_served_user(user_id: int):
    is_served = await is_served_user(user_id)
    if is_served:
        return
    return await usersdb.insert_one({"user_id": user_id})


async def get_served_chats() -> list:
    chats_list = []
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat)
    return chats_list


async def is_served_chat(chat_id: int) -> bool:
    chat = await chatsdb.find_one({"chat_id": chat_id})
    if not chat:
        return False
    return True


async def add_served_chat(chat_id: int):
    is_served = await is_served_chat(chat_id)
    if is_served:
        return
    return await chatsdb.insert_one({"chat_id": chat_id})

# New function to remove served chat
async def remove_served_chat(chat_id: int):
    if await is_served_chat(chat_id):
        await chatsdb.delete_one({"chat_id": chat_id})
    

async def blacklisted_chats() -> list:
    chats_list = []
    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat["chat_id"])
    return chats_list


async def blacklist_chat(chat_id: int) -> bool:
    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.insert_one({"chat_id": chat_id})
        return True
    return False


async def whitelist_chat(chat_id: int) -> bool:
    if await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.delete_one({"chat_id": chat_id})
        return True
    return False


async def _get_authusers(chat_id: int) -> Dict[str, int]:
    _notes = await authuserdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes.get("notes", {})


async def get_authuser_names(chat_id: int) -> List[str]:
    notes = await _get_authusers(chat_id)
    return list(notes.keys())


async def get_authuser(chat_id: int, name: str) -> Union[bool, dict]:
    name = name
    _notes = await _get_authusers(chat_id)
    if name in _notes:
        return _notes[name]
    else:
        return False


async def save_authuser(chat_id: int, name: str, note: dict):
    name = name
    _notes = await _get_authusers(chat_id)
    _notes[name] = note

    await authuserdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_authuser(chat_id: int, name: str) -> bool:
    notesd = await _get_authusers(chat_id)
    name = name
    if name in notesd:
        del notesd[name]
        await authuserdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def get_gbanned() -> list:
    results = []
    async for user in gbansdb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def is_gbanned_user(user_id: int) -> bool:
    user = await gbansdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if is_gbanned:
        return
    return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if not is_gbanned:
        return
    return await gbansdb.delete_one({"user_id": user_id})


async def get_sudoers() -> list:
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    if not sudoers:
        return []
    return sudoers["sudoers"]


async def add_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.append(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def remove_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.remove(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def get_banned_users() -> list:
    results = []
    async for user in blockeddb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def get_banned_count() -> int:
    users = blockeddb.find({"user_id": {"$gt": 0}})
    users = await users.to_list(length=100000)
    return len(users)


async def is_banned_user(user_id: int) -> bool:
    user = await blockeddb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if is_gbanned:
        return
    return await blockeddb.insert_one({"user_id": user_id})


async def remove_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if not is_gbanned:
        return
    return await blockeddb.delete_one({"user_id": user_id})


async def is_autoplay(chat_id: int) -> bool:
    """Default is ON. Returns False only if explicitly disabled in DB."""
    mode = autoplay_cache.get(chat_id)
    if mode is None:
        disabled = await autplaydb.find_one({"chat_id": chat_id, "disabled": True})
        result = not bool(disabled)
        autoplay_cache[chat_id] = result
        return result
    return mode


async def autoplay_on(chat_id: int):
    autoplay_cache[chat_id] = True
    await autplaydb.delete_one({"chat_id": chat_id})


async def autoplay_off(chat_id: int):
    autoplay_cache[chat_id] = False
    await autplaydb.update_one(
        {"chat_id": chat_id}, {"$set": {"chat_id": chat_id, "disabled": True}}, upsert=True
    )


_nsfw_disabled_cache: dict[int, bool] = {}


async def is_nsfw_disabled(chat_id: int) -> bool:
    """Returns True if NSFW filter is explicitly disabled for this chat."""
    if chat_id in _nsfw_disabled_cache:
        return _nsfw_disabled_cache[chat_id]
    result = await contentguarddb.find_one({"chat_id": chat_id})
    disabled = result.get("disabled", False) if result else False
    _nsfw_disabled_cache[chat_id] = disabled
    return disabled


async def is_content_guard_on(chat_id: int) -> bool:
    """Returns True if NSFW filter is active (ON by default, unless explicitly disabled)."""
    return not await is_nsfw_disabled(chat_id)


async def content_guard_on(chat_id: int):
    """Re-enable NSFW filter (remove from disabled list)."""
    _nsfw_disabled_cache[chat_id] = False
    await contentguarddb.delete_one({"chat_id": chat_id})


async def content_guard_off(chat_id: int):
    """Disable NSFW filter for this chat."""
    _nsfw_disabled_cache[chat_id] = True
    await contentguarddb.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id, "disabled": True}},
        upsert=True,
    )


async def is_thumb_enabled() -> bool:
    """Thumbnail permanently disabled — always video mode."""
    return False


async def thumb_on():
    pass


async def thumb_off():
    pass


# ── Global NSFW on/off (key 6 in onoffdb) ────────────────────────────────────
# on_off=6 in DB means global NSFW is DISABLED (off).
# Default: not in DB = NSFW is ON globally.
_global_nsfw_off_cache: list = []  # empty = not loaded; [0]=True means globally OFF


async def is_global_nsfw_off() -> bool:
    """Returns True if NSFW filter is globally disabled by the bot owner."""
    if not _global_nsfw_off_cache:
        get = await onoffdb.find_one({"on_off": 6})
        _global_nsfw_off_cache.clear()
        _global_nsfw_off_cache.append(bool(get))
    return _global_nsfw_off_cache[0]


async def set_global_nsfw_off():
    """Globally disable the NSFW filter (owner-only action)."""
    _global_nsfw_off_cache.clear()
    _global_nsfw_off_cache.append(True)
    exists = await is_on_off(6)
    if not exists:
        await onoffdb.insert_one({"on_off": 6})


async def set_global_nsfw_on():
    """Re-enable the NSFW filter globally."""
    _global_nsfw_off_cache.clear()
    _global_nsfw_off_cache.append(False)
    exists = await is_on_off(6)
    if exists:
        await onoffdb.delete_one({"on_off": 6})


# ─── 24/7 Mode ────────────────────────────────────────────────────────────────
_247_cache: dict = {}

async def is_24_7(chat_id: int) -> bool:
    if chat_id in _247_cache:
        return _247_cache[chat_id]
    get = await assistantdb.find_one({"chat_id": chat_id, "mode247": True})
    _247_cache[chat_id] = bool(get)
    return _247_cache[chat_id]


async def enable_247(chat_id: int):
    _247_cache[chat_id] = True
    await assistantdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode247": True}}, upsert=True
    )


async def disable_247(chat_id: int):
    _247_cache[chat_id] = False
    await assistantdb.update_one(
        {"chat_id": chat_id}, {"$unset": {"mode247": 1}}
    )


# ─── Volume Control ───────────────────────────────────────────────────────────
_vol_cache: dict = {}

async def get_volume(chat_id: int) -> int:
    if chat_id in _vol_cache:
        return _vol_cache[chat_id]
    get = await assistantdb.find_one({"chat_id": chat_id})
    vol = get.get("volume", 100) if get else 100
    _vol_cache[chat_id] = vol
    return vol


async def set_volume(chat_id: int, vol: int):
    _vol_cache[chat_id] = vol
    await assistantdb.update_one(
        {"chat_id": chat_id}, {"$set": {"volume": vol}}, upsert=True
    )
