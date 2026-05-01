"""
Audio file validation helpers.

The bot's biggest "song plays half then stops" symptom comes from yt-dlp,
Invidious or CDN downloads that succeed-but-truncate (server hangs up,
network blip, expired signed URL, etc.). The resulting file is small but
non-empty, so legacy size-only checks (>1 KB) accept it. PyTgCalls then
reaches EOF mid-track and the stream simply ends.

These helpers fix that by probing the actual playable duration of the file
with ffprobe and comparing it against the expected duration looked up from
a process-wide cache populated during URL extraction.
"""

import asyncio
import os
import shutil
import subprocess
from typing import Dict, Optional

from KHUSHI.logger_setup import LOGGER

# vid -> expected duration in seconds (populated by extract calls everywhere)
DURATION_CACHE: Dict[str, int] = {}

# Acceptable shortfall — anything < EXPECTED * TOL is considered truncated.
_TOL = 0.92
# When expected duration is unknown, reject obviously-tiny clips
_MIN_UNKNOWN_SEC = 25.0
# Hard floor on file size (bytes). Smaller than this is always garbage.
_MIN_BYTES = 32 * 1024

_FFPROBE = shutil.which("ffprobe") or "ffprobe"


def set_expected_duration(vid: Optional[str], dur: Optional[int]) -> None:
    """Store the expected playback duration for a video id, in seconds."""
    if not vid or not dur:
        return
    try:
        d = int(dur)
    except (TypeError, ValueError):
        return
    if d <= 0:
        return
    DURATION_CACHE[vid] = d


def get_expected_duration(vid: Optional[str]) -> int:
    """Return cached expected duration (sec), or 0 if unknown."""
    if not vid:
        return 0
    return DURATION_CACHE.get(vid, 0)


def _probe_duration(path: str, timeout: float = 8.0) -> float:
    """Return file's actual audio/video duration in seconds, or 0 on failure."""
    try:
        proc = subprocess.run(
            [
                _FFPROBE, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            timeout=timeout,
        )
        out = (proc.stdout or b"").decode("utf-8", "ignore").strip()
        return float(out) if out else 0.0
    except Exception:
        return 0.0


def audio_ok_sync(
    path: Optional[str],
    expected_sec: int = 0,
    *,
    vid: Optional[str] = None,
) -> bool:
    """Synchronous version of the duration check. Safe to call from threads."""
    if not path:
        return False
    try:
        if not os.path.exists(path):
            return False
        size = os.path.getsize(path)
    except OSError:
        return False
    if size < _MIN_BYTES:
        LOGGER(__name__).warning(f"[VAL] Tiny file {path} ({size} bytes)")
        return False

    if not expected_sec:
        expected_sec = get_expected_duration(vid)

    actual = _probe_duration(path)
    if actual <= 0:
        # ffprobe couldn't read the file → almost certainly corrupt.
        LOGGER(__name__).warning(f"[VAL] ffprobe could not read {path}")
        return False

    if expected_sec and expected_sec > 0:
        if actual < expected_sec * _TOL:
            LOGGER(__name__).warning(
                f"[VAL] Truncated {path}: {actual:.1f}s/{expected_sec}s — discarding"
            )
            return False
        return True

    # Unknown expected duration — accept anything that decodes for at least 25s
    if actual < _MIN_UNKNOWN_SEC:
        LOGGER(__name__).warning(
            f"[VAL] Suspiciously short clip {path}: {actual:.1f}s — discarding"
        )
        return False
    return True


async def audio_ok_async(
    path: Optional[str],
    expected_sec: int = 0,
    *,
    vid: Optional[str] = None,
) -> bool:
    """Async wrapper that runs the (sync) ffprobe check off the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: audio_ok_sync(path, expected_sec, vid=vid)
    )
