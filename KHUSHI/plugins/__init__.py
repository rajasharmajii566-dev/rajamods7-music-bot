import glob
from os.path import dirname, isfile


def _list_modules():
    work_dir = dirname(__file__)
    paths = glob.glob(work_dir + "/*.py")
    return sorted([
        f.replace(work_dir, "").replace("/", ".").replace(".py", "").lstrip(".")
        for f in paths
        if isfile(f) and not f.endswith("__init__.py")
    ])


ALL_MODULES = _list_modules()
__all__ = ALL_MODULES + ["ALL_MODULES"]
