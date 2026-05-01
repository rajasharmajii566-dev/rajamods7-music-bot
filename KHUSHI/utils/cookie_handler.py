"""
Cookie handler — no longer required.
Bot uses android_vr / ios_downgraded yt-dlp clients which work without cookies.
This module is kept for backward compatibility.
"""

from pathlib import Path

COOKIE_PATH = Path("KHUSHI/assets/cookies.txt")


async def fetch_and_store_cookies():
    """No-op: cookies not needed with android_vr client."""
    pass
