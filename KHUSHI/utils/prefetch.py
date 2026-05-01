"""
Pre-fetch next queue tracks in background while current song plays.

Strategy:
  1. Use fast_get_stream() which:
     - checks local file (instant)
     - races webserver URL cache vs SmartYTDL extraction (parallel)
     - kicks off background local file download after URL is found
  2. After prefetch, when the song's turn comes, fast_get_stream() hits
     the webserver URL cache instantly → near-zero play delay.
  3. Pre-fetch the next TWO songs in queue (not just one).
"""

import asyncio
import logging

from KHUSHI.misc import db
from KHUSHI.utils.downloader import file_exists, fast_get_stream

_log = logging.getLogger(__name__)

_prefetch_tasks: dict[str, asyncio.Task] = {}


async def _prefetch_worker(vidid: str) -> None:
    try:
        if file_exists(vidid):
            _log.info(f"[PREFETCH] Already cached locally: {vidid}")
            return
        _log.info(f"[PREFETCH] Pre-warming CDN URL + bg download for {vidid}")
        result = await fast_get_stream(vidid)
        if result:
            _log.info(f"[PREFETCH] Ready: {vidid} → {'local' if not result.startswith('http') else 'cdn'}")
        else:
            _log.warning(f"[PREFETCH] Failed for {vidid}")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        _log.debug(f"[PREFETCH] Error for {vidid}: {e}")
    finally:
        _prefetch_tasks.pop(vidid, None)


def trigger_prefetch(chat_id: int) -> None:
    """
    Pre-fetch the next 1-2 YouTube songs in queue while the current song plays.
    Uses fast_get_stream which warms both the webserver URL cache and local file.
    Called right after a song starts playing.
    """
    try:
        queue = db.get(chat_id)
        if not queue or len(queue) < 2:
            return

        for next_item in queue[1:3]:
            queued_file: str = next_item.get("file", "")
            vidid: str = next_item.get("vidid", "")
            streamtype: str = next_item.get("streamtype", "")

            if "vid_" not in queued_file:
                continue
            if not vidid or streamtype not in ("audio", "video"):
                continue
            if file_exists(vidid):
                _log.info(f"[PREFETCH] Already cached: {vidid}")
                continue

            existing = _prefetch_tasks.get(vidid)
            if existing and not existing.done():
                _log.info(f"[PREFETCH] Already in flight: {vidid}")
                continue

            task = asyncio.create_task(_prefetch_worker(vidid))
            _prefetch_tasks[vidid] = task
            _log.info(f"[PREFETCH] Triggered for vidid={vidid} chat={chat_id}")

    except Exception as e:
        _log.debug(f"[PREFETCH] trigger error: {e}")


def cancel_prefetch(chat_id: int) -> None:
    """Cancel prefetch tasks for songs in this chat's queue (on skip/stop)."""
    try:
        queue = db.get(chat_id) or []
        for item in queue[1:3]:
            vidid = item.get("vidid", "")
            if vidid and vidid in _prefetch_tasks:
                task = _prefetch_tasks.pop(vidid)
                if not task.done():
                    task.cancel()
    except Exception:
        pass
