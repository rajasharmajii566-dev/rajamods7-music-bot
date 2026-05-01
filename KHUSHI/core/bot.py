import asyncio

from pyrogram import Client, enums, errors

import config
from KHUSHI.logger_setup import LOGGER

BOT_PFP_PATH = "KHUSHI/assets/bot_pfp.png"


class KhushiBot(Client):
    """
    KHUSHI's own Pyrogram client.
    Super fast: 80 workers, 10 concurrent transmissions,
    no_updates=False for full handler support.
    """

    def __init__(self):
        super().__init__(
            name="KhushiX",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            parse_mode=enums.ParseMode.HTML,
            workers=80,
            max_concurrent_transmissions=10,
        )
        LOGGER(__name__).info("KHUSHI Bot client initialized.")

    async def start(self):
        try:
            await super().start()
        except errors.FloodWait as fw:
            LOGGER(__name__).warning(f"FloodWait: waiting {fw.value}s...")
            await asyncio.sleep(fw.value)
            await super().start()

        me = await self.get_me()
        self.username = me.username
        self.id = me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.get_chat(config.LOGGER_ID)
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<blockquote><b>✅ {self.mention} ꜱᴛᴀʀᴛᴇᴅ</b>\n\n"
                    f"ɪᴅ : <code>{self.id}</code>\n"
                    f"ɴᴀᴍᴇ : {self.name}\n"
                    f"ᴜꜱᴇʀɴᴀᴍᴇ : @{self.username}\n"
                    f"ᴍᴏᴅᴇ : <b>RAJAMODS7 MUSIC</b></blockquote>"
                ),
            )
        except Exception as e:
            LOGGER(__name__).warning(f"Log channel not accessible: {e}")

        LOGGER(__name__).info(f"KHUSHI Bot started as {self.name} (@{self.username})")
        await self._cache_pfp()

    async def _cache_pfp(self):
        try:
            import os
            os.makedirs("KHUSHI/assets", exist_ok=True)
            async for p in self.get_chat_photos(self.id, limit=1):
                await self.download_media(p.file_id, file_name=BOT_PFP_PATH)
                LOGGER(__name__).info("KHUSHI: Bot PFP cached.")
                return
            LOGGER(__name__).info("KHUSHI: No PFP — using default.")
        except Exception as e:
            LOGGER(__name__).warning(f"KHUSHI: PFP cache failed: {e}")
