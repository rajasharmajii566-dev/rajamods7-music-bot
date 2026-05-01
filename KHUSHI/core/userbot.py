import asyncio

from pyrogram import Client, enums, errors

import config
from KHUSHI.logger_setup import LOGGER

assistants = []
assistantids = []

GROUPS_TO_JOIN = []


class Userbot:
    """KHUSHI's own userbot/assistant manager."""

    def __init__(self):
        def _make(session, name):
            if not session:
                return None
            return Client(
                name,
                config.API_ID,
                config.API_HASH,
                session_string=session,
                parse_mode=enums.ParseMode.HTML,
                no_updates=True,
            )

        self.one   = _make(config.STRING1,  "KhushiAssis1")
        self.two   = _make(config.STRING2,  "KhushiAssis2")
        self.three = _make(config.STRING3,  "KhushiAssis3")
        self.four  = _make(config.STRING4,  "KhushiAssis4")
        self.five  = _make(config.STRING5,  "KhushiAssis5")

    async def _setup(self, client, index: int):
        if client is None:
            return
        try:
            me = await client.get_me()
            client.id = me.id
            client.name = me.first_name
            client.username = me.username
            assistantids.append(me.id)
            assistants.append(index)

            for group in GROUPS_TO_JOIN:
                try:
                    await client.join_chat(group)
                except Exception:
                    pass

            try:
                from KHUSHI import app
                await app.send_message(
                    config.LOGGER_ID,
                    f"<blockquote>✅ <b>RAJAMODS7 Assistant {index}</b> started as {me.first_name}</blockquote>",
                )
            except Exception:
                pass

            LOGGER(__name__).info(f"KHUSHI Assistant {index} started as {client.name}")

        except errors.AuthKeyDuplicated:
            LOGGER(__name__).error(f"Assistant {index}: AUTH_KEY_DUPLICATED — generate new STRING{index}.")
        except errors.AuthKeyUnregistered:
            LOGGER(__name__).error(f"Assistant {index}: Session expired — generate new STRING{index}.")
        except errors.UserDeactivated:
            LOGGER(__name__).error(f"Assistant {index}: Account deactivated. Remove STRING{index}.")
        except Exception as e:
            LOGGER(__name__).error(f"KHUSHI Assistant {index} setup failed: {e}")

    async def start(self):
        LOGGER(__name__).info("KHUSHI: Starting assistants...")
        for i, client in enumerate([self.one, self.two, self.three, self.four, self.five], 1):
            await self._setup(client, i)

    async def post_start(self):
        """Called after PyTgCalls starts the clients."""
        for i, client in enumerate([self.one, self.two, self.three, self.four, self.five], 1):
            await self._setup(client, i)

    async def stop(self):
        for client in [self.one, self.two, self.three, self.four, self.five]:
            if client:
                try:
                    await client.stop()
                except Exception:
                    pass
