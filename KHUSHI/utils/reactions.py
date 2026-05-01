from pyrogram.types import Message

async def react_to_command(message: Message, emoji: str = "❤"):
    try:
        await message.react(emoji=emoji)
    except Exception:
        pass
