from typing import Union
from . import InlineKeyboardButton


def setting_markup(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["ST_B_1"], callback_data="AUTH_SETTINGS", style="primary"),
            InlineKeyboardButton(text=_["ST_B_3"], callback_data="LANGUAGE_SETTINGS", style="primary"),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_2"], callback_data="PLAYBACK_SETTINGS", style="primary"),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_4"], callback_data="VOTE_SETTINGS", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🔁 ᴀᴜᴛᴏᴘʟᴀʏ", callback_data="AUTOPLAY_SETTINGS", style="primary"),
        ],
        [
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger"),
        ],
    ]
    return buttons


def vote_mode_markup(_, current, mode: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(text="🗳 Vᴏᴛɪɴɢ ᴍᴏᴅᴇ ➜", callback_data="VOTE_MODE_INFO", style="primary"),
            InlineKeyboardButton(
                text=_["ST_B_5"] if mode == True else _["ST_B_6"],
                callback_data="TOGGLE_VOTE_MODE",
                style="success" if mode == True else "danger"
            ),
        ],
        [
            InlineKeyboardButton(text="-2", callback_data="DECREASE_VOTE_COUNT", style="primary"),
            InlineKeyboardButton(
                text=f"ᴄᴜʀʀᴇɴᴛ : {current}",
                callback_data="CURRENT_VOTE_INFO",
                style="primary"
            ),
            InlineKeyboardButton(text="+2", callback_data="INCREASE_VOTE_COUNT", style="primary"),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
                style="primary"
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger"),
        ],
    ]
    return buttons


def auth_users_markup(_, status: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(text=_["ST_B_7"], callback_data="AUTH_USERS_INFO", style="primary"),
            InlineKeyboardButton(
                text=_["ST_B_8"] if status == True else _["ST_B_9"],
                callback_data="TOGGLE_AUTH_MODE",
                style="success" if status == True else "danger"
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_1"], callback_data="VIEW_AUTH_USERS", style="primary"),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
                style="primary"
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger"),
        ],
    ]
    return buttons


def playmode_users_markup(
    _,
    Direct: Union[bool, str] = None,
    Group: Union[bool, str] = None,
    Playtype: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(text=_["ST_B_10"], callback_data="SEARCH_MODE_INFO", style="primary"),
            InlineKeyboardButton(
                text=_["ST_B_11"] if Direct == True else _["ST_B_12"],
                callback_data="TOGGLE_SEARCH_MODE",
                style="success" if Direct == True else "danger"
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_13"], callback_data="CHANNEL_MODE_INFO", style="primary"),
            InlineKeyboardButton(
                text=_["ST_B_8"] if Group == True else _["ST_B_9"],
                callback_data="TOGGLE_CHANNEL_MODE",
                style="success" if Group == True else "danger"
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_14"], callback_data="PLAY_TYPE_INFO", style="primary"),
            InlineKeyboardButton(
                text=_["ST_B_8"] if Playtype == True else _["ST_B_9"],
                callback_data="TOGGLE_PLAY_TYPE",
                style="success" if Playtype == True else "danger"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
                style="primary"
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close", style="danger"),
        ],
    ]
    return buttons