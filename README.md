# RAJAMODS7 MUSIC BOT

A Telegram voice/video chat music bot powered by Pyrogram + PyTgCalls. Plays
audio and full-quality video in Telegram group calls with a card-style UI.

> Based on the KHUSHI / Annie codebase, hardened for reliability:
> - Multi-layer YouTube fallback (ShrutiMusic API → VideosSearch → ytsearch → Invidious)
> - Hardened ffmpeg flags so streams don't drop after 15 seconds
> - `/vplay` always downloads true video (no audio-only fallback bug)
> - Smart yt-dlp client rotation, MongoDB URL cache, full song duration playback

## Features

- `/play <song>` — stream audio
- `/vplay <song>` — stream video with audio
- Card-style `/start` and `/vplay` panels with inline controls
- Hinglish chat replies, emoji-free in messages (UI emojis OK)
- Queue, skip, pause, resume, loop, shuffle
- Channel play, autoplay, autoend, sudo system, broadcast, ping, stats
- Web player at `:7200/music` for live now-playing display
- ShrutiMusic API integration with offline fallback
- Watchdog auto-restart on crash

## Deploy on Railway

1. **Fork this repo** to your own GitHub account.
2. Go to [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo** → pick your fork.
3. Railway will auto-detect the `Dockerfile` and `railway.toml`.
4. Open the **Variables** tab and add the following (see `.env.example` for the full list):

   | Variable          | Required | How to get it |
   | ----------------- | -------- | ------------- |
   | `API_ID`          | ✅       | https://my.telegram.org → API Development |
   | `API_HASH`        | ✅       | same page as `API_ID` |
   | `BOT_TOKEN`       | ✅       | https://t.me/BotFather → `/newbot` |
   | `STRING_SESSION`  | ✅       | https://t.me/StringFatherBot (assistant userbot session) |
   | `MONGO_DB_URI`    | ✅       | https://cloud.mongodb.com → free cluster → connection string |
   | `OWNER_ID`        | ✅       | your Telegram numeric user id (forward msg to @userinfobot) |
   | `LOGGER_ID`       | ✅       | id of a private group/channel where logs go (negative number) |
   | `API_URL`         | optional | defaults to `https://xbit-yt-api.vercel.app` |
   | `API_KEY`         | optional | xbit/ShrutiMusic API key for premium streams |
   | `START_IMG_URL`   | optional | start card thumbnail URL |
   | `HELP_IMG_URL`    | optional | help card thumbnail URL |

5. Click **Deploy**. The bot will boot in ~60 seconds. Send `/start` to your bot to verify.

## Run locally (Linux / macOS)

```bash
# 1. Install system deps
#    Debian/Ubuntu:
sudo apt-get install -y python3 python3-pip ffmpeg git build-essential nodejs

# 2. Clone and install python deps
git clone <your-fork-url>
cd raja-music
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
nano .env          # fill in BOT_TOKEN, API_ID, API_HASH, STRING_SESSION, etc.

# 4. Load env and run
set -a && source .env && set +a
bash start.sh      # auto-restarts on crash
# or
python3 -m KHUSHI  # one-shot
```

## Run with Docker

```bash
docker build -t raja-music .
docker run -d --env-file .env --name raja-music raja-music
```

## Branding

- Bot title: `RAJAMODS7 MUSIC`
- Owner contact link: `t.me/rajamods7pro`
- Default chat language: Hinglish

To change branding, edit `config.py` and the strings under `strings/`.

## Project layout

```
.
├── KHUSHI/              # bot package (plugins, core, utils, platforms)
├── strings/             # i18n / message strings
├── config.py            # env-driven configuration
├── webserver.py         # web player (port 7200)
├── start.sh             # watchdog wrapper for python3 -m KHUSHI
├── Dockerfile           # Railway / Docker build
├── railway.toml         # Railway service config
├── Procfile             # Heroku-style worker entry
├── requirements.txt     # python deps
└── .env.example         # template — copy to .env and fill in
```

## License

LGPL-3.0 — see [LICENSE](LICENSE).

## Credits

- Original **KHUSHI / Annie** music bot codebase
- [Pyrogram](https://docs.pyrogram.org/) · [PyTgCalls](https://pytgcalls.github.io/) · [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ShrutiMusic / xbit](https://xbit-yt-api.vercel.app) YouTube API
