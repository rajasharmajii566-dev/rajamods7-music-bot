from . import InlineKeyboardButton
from pyrogram.types import InlineKeyboardMarkup

from config import SUPPORT_CHAT


def botplaylist_markup(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["S_B_4"], url=SUPPORT_CHAT, style="success"),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger"),
        ],
    ]
    return buttons


def close_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close",
                    style="danger",
                ),
            ]
        ]
    )
    return upl


def add_to_channel_markup(_, bot_username):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="✚ ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ ✚",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                    style="primary",
                ),
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close",
                    style="danger",
                ),
            ]
        ]
    )
    return upl


def supp_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["S_B_4"],
                    url=SUPPORT_CHAT,
                    style="success",
                ),
            ]
        ]
    )
    return upl
