"""
Internal API Secret — used to authenticate calls between the bot process
and the local Flask webserver.

This is a RANDOM UUID generated once per process startup.
It is NEVER the bot token, NEVER logged, and NEVER sent outside localhost.
"""

import secrets

_SECRET = secrets.token_urlsafe(32)


def get_secret() -> str:
    return _SECRET
