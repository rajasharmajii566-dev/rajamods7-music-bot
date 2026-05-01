from pyrogram.types import WebAppInfo

from . import InlineKeyboardButton
import config
from KHUSHI.utils.weburl import WEB_URL


def start_panel(_):
    from KHUSHI import app
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_1"],
                url=f"https://t.me/{app.username}?startgroup=true",
                style="primary",
            ),
            InlineKeyboardButton(
                text=_["S_B_2"],
                url=config.SUPPORT_CHANNEL,
                style="success",
            ),
        ],
    ]
    return buttons


def private_panel(_):
    from KHUSHI import app
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_1"],
                url=f"https://t.me/{app.username}?startgroup=true",
                style="primary",
            )
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_4"],
                url=config.SUPPORT_CHAT,
                style="success",
            ),
            InlineKeyboardButton(
                text=_["S_B_2"],
                url=config.SUPPORT_CHANNEL,
                style="success",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                callback_data="open_help",
                style="primary",
            ),
        ],
    ]

    if WEB_URL:
        buttons.append([
            InlineKeyboardButton(
                text="˹ᴡᴇʙ ᴘʟᴀʏᴇʀ˼",
                web_app=WebAppInfo(url=WEB_URL),
                style="success",
            )
        ])

    return buttons
