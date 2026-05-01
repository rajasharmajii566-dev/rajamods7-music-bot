import os
import asyncio
import shlex
import time
from typing import Tuple

os.environ['GIT_PYTHON_REFRESH'] = 'quiet'
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config

from ..logger_setup import LOGGER


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.get_event_loop().run_until_complete(install_requirements())


def _remove_stale_lock(repo_path: str, max_age_secs: int = 5):
    lock_file = os.path.join(repo_path, ".git", "config.lock")
    try:
        if os.path.exists(lock_file):
            age = time.time() - os.path.getmtime(lock_file)
            if age > max_age_secs:
                os.remove(lock_file)
    except Exception:
        pass


def git():
    REPO_LINK = config.UPSTREAM_REPO
    if config.GIT_TOKEN:
        GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]
        TEMP_REPO = REPO_LINK.split("https://")[1]
        UPSTREAM_REPO = f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
    else:
        UPSTREAM_REPO = config.UPSTREAM_REPO

    try:
        repo = Repo()
        LOGGER(__name__).info("Git Client Found [VPS DEPLOYER]")
    except (GitCommandError, InvalidGitRepositoryError):
        try:
            repo = Repo.init()
            LOGGER(__name__).info("Initialized new Git repository.")
        except Exception as e:
            LOGGER(__name__).error(f"Failed to initialize Git: {e}")
            return

    _remove_stale_lock(repo.working_dir)

    os.environ['GIT_TERMINAL_PROMPT'] = '0'

    try:
        if "origin" in repo.remotes:
            origin = repo.remote("origin")
            current_url = next(iter(origin.urls), "")
            if current_url != UPSTREAM_REPO:
                try:
                    origin.set_url(UPSTREAM_REPO)
                except Exception:
                    pass
        else:
            try:
                origin = repo.create_remote("origin", UPSTREAM_REPO)
            except Exception:
                pass

        try:
            with repo.config_writer() as cw:
                cw.set_value("core", "askpass", "true")
                cw.set_value("credential", "helper", "")
        except Exception:
            pass

        LOGGER(__name__).info("Successfully updated from upstream repository.")

    except Exception as e:
        LOGGER(__name__).error(f"Unexpected Git Error: {e}")
