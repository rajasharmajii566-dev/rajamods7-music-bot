from random import randint

from pyrogram import raw
from pyrogram.enums import ParseMode
from pyrogram.parser import html as html_mod


async def send_msg_invert_preview(
    client,
    chat_id: int,
    text: str,
    reply_markup=None,
    reply_to_message_id: int = None,
):
    """
    Send a message with the link preview displayed ABOVE the text
    (invert_media=True) using Pyrogram's raw API.
    Falls back to a normal send_message if the raw call fails.
    """
    try:
        parser = html_mod.HTML(client)
        parsed = await parser.parse(text)
        msg_text = parsed["message"]
        entities = parsed.get("entities", [])

        peer = await client.resolve_peer(chat_id)
        raw_markup = await reply_markup.write(client) if reply_markup else None

        reply_to = None
        if reply_to_message_id:
            reply_to = raw.types.InputReplyToMessage(reply_to_msg_id=reply_to_message_id)

        result = await client.invoke(
            raw.functions.messages.SendMessage(
                peer=peer,
                message=msg_text,
                random_id=randint(1, 2**31 - 1),
                no_webpage=False,
                invert_media=True,
                reply_markup=raw_markup,
                entities=entities,
                reply_to=reply_to,
            )
        )

        for update in result.updates:
            if isinstance(
                update,
                (raw.types.UpdateNewMessage, raw.types.UpdateNewChannelMessage),
            ):
                return await client.get_messages(chat_id, update.message.id)

        return None

    except Exception:
        return await client.send_message(
            chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
