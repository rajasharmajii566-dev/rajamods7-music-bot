import socket
import time

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus

from config import OWNER_ID
from KHUSHI.core.mongo import mongodb
from KHUSHI.logger_setup import LOGGER

SUDOERS = filters.user()
COMMANDERS = [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
_boot_ = time.time()

db = {}


def is_heroku():
    return "heroku" in socket.getfqdn()


def dbb():
    global db
    db = {}
    LOGGER(__name__).info("KHUSHI: In-memory DB initialized.")


async def sudo():
    global SUDOERS
    SUDOERS.add(OWNER_ID)

    sudoersdb = mongodb.sudoers
    data = await sudoersdb.find_one({"sudo": "sudo"}) or {}
    sudoers_list = data.get("sudoers", [])

    if OWNER_ID not in sudoers_list:
        sudoers_list.append(OWNER_ID)
        await sudoersdb.update_one(
            {"sudo": "sudo"},
            {"$set": {"sudoers": sudoers_list}},
            upsert=True,
        )

    for uid in sudoers_list:
        SUDOERS.add(uid)

    LOGGER(__name__).info("KHUSHI: Sudo users loaded.")

    try:
        onoffdb = mongodb.onoffper
        await onoffdb.delete_one({"on_off": 1})
        from KHUSHI.utils.database import maintenance
        maintenance.clear()
        maintenance.append(2)
        LOGGER(__name__).info("KHUSHI: Maintenance mode reset on startup.")
    except Exception as e:
        LOGGER(__name__).warning(f"KHUSHI: Could not reset maintenance flag: {e}")
