import os

from config import autoclean


def _clean_file(rem: str) -> None:
    if not rem:
        return
    try:
        autoclean.remove(rem)
    except ValueError:
        pass
    if autoclean.count(rem) == 0:
        if "vid_" not in rem and "live_" not in rem and "index_" not in rem:
            try:
                if os.path.isfile(rem):
                    os.remove(rem)
            except Exception:
                pass


def _clean_item(item: dict) -> None:
    _clean_file(item.get("file", ""))
    speed = item.get("speed_path")
    if speed:
        try:
            if os.path.isfile(speed):
                os.remove(speed)
        except Exception:
            pass


async def auto_clean(popped) -> None:
    try:
        if isinstance(popped, dict):
            _clean_item(popped)
        elif isinstance(popped, list):
            for item in popped:
                if isinstance(item, dict):
                    _clean_item(item)
    except Exception:
        pass
