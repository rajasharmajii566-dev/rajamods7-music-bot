"""
Annie X Music — Security Guard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detects and blocks injection / exfiltration attacks in play queries.
Sends an owner DM alert in Annie style when an attack is detected.
"""

import re
import html
from datetime import datetime

from pyrogram.enums import ParseMode

# ── Attack pattern groups ─────────────────────────────────────────────────────

# Shell metacharacters that should NEVER appear in a legit music URL/query
_SHELL_METACHAR = re.compile(
    r"[;&`|]|\$\(|\$\{|`|\x00|\r?\n",
    re.IGNORECASE,
)

# Known exfiltration / RCE tools
_EXEC_KEYWORDS = re.compile(
    r"\b(curl|wget|nc\b|ncat|netcat|bash|sh\b|python|perl|ruby|php|exec|eval|system)\b",
    re.IGNORECASE,
)

# File read attempts targeting sensitive files
_FILE_READ = re.compile(
    r"(cat|tac|head|tail|less|more|nano|vi\b|vim)\s*\S*(\.env|/etc/|/proc/|config\.py|\.json|\.key|\.pem|\.secret|passw|token|credential)",
    re.IGNORECASE,
)

# Encoding tricks used to bypass filters
_ENCODING_TRICKS = re.compile(
    r"\$\{IFS\}|\\x[0-9a-f]{2}|\\u00|%00|%0[aAdD]|base64|xxd|od\b|hexdump",
    re.IGNORECASE,
)

# Webhook / outbound data exfiltration
_EXFIL_PATTERN = re.compile(
    r"(webhook\.site|requestbin|ngrok\.io|burpcollaborator|canarytokens|pipedream|interactsh|\.oast\.|hookbin|requestcatcher)",
    re.IGNORECASE,
)

# URL injection — extra commands after the legit URL (;cmd, &&cmd etc.)
_URL_INJECTION = re.compile(
    r"(youtube\.com|youtu\.be|spotify\.com|soundcloud\.com|music\.apple\.com|resso\.me)"
    r"[^\s]*[;&|`]",
    re.IGNORECASE,
)


def _classify(text: str) -> str | None:
    """Return the attack type string if malicious, else None."""
    if _URL_INJECTION.search(text):
        return "URL Injection (shell metachar after legitimate domain)"
    if _SHELL_METACHAR.search(text):
        return "Shell Metacharacter Injection"
    if _EXFIL_PATTERN.search(text):
        return "Webhook / Data Exfiltration Attempt"
    if _ENCODING_TRICKS.search(text):
        return "Encoding Bypass / Obfuscation"
    if _FILE_READ.search(text):
        return "Sensitive File Read Attempt"
    if _EXEC_KEYWORDS.search(text):
        return "Remote Code Execution Keyword"
    return None


def is_malicious(text: str) -> tuple[bool, str | None]:
    """
    Returns (True, attack_type) if the text looks malicious,
    (False, None) otherwise.
    """
    if not text:
        return False, None
    attack = _classify(text)
    return (True, attack) if attack else (False, None)


async def send_attack_alert(app, owner_id: int, message, query: str, attack_type: str):
    """
    Send an Annie-style attack alert DM to the bot owner.
    """
    now = datetime.utcnow().strftime("%d %b %Y • %H:%M:%S UTC")

    safe_query = html.escape(query[:400])
    chat_username = f"@{message.chat.username}" if message.chat.username else "—"
    user_username = f"@{message.from_user.username}" if message.from_user.username else "—"

    alert_text = f"""
<b>˹𝐀ɴɴɪᴇ ✘ 𝙼ᴜsɪᴄ˼ ♪ — 🚨 SECURITY ALERT</b>

<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
⚠️ <b>Attack Type:</b> <code>{html.escape(attack_type)}</code>
🕐 <b>Time:</b> <code>{now}</code>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>🏠 Chat Info</b>
├ <b>Chat:</b> {html.escape(message.chat.title)}
├ <b>Chat ID:</b> <code>{message.chat.id}</code>
└ <b>Username:</b> {chat_username}

<b>👤 User Info</b>
├ <b>User:</b> {message.from_user.mention}
├ <b>User ID:</b> <code>{message.from_user.id}</code>
└ <b>Username:</b> {user_username}

<b>🔴 Malicious Query</b>
<code>{safe_query}</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
<i>Query blocked. Bot is safe. ✅</i>
"""

    try:
        await app.send_message(
            chat_id=owner_id,
            text=alert_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception:
        pass


async def check_and_alert(app, owner_id: int, message, query: str) -> bool:
    """
    Full security check. Returns True if the query is malicious (and alert is sent).
    Call this before processing any user-supplied URL or search query.
    """
    bad, attack_type = is_malicious(query)
    if bad:
        await send_attack_alert(app, owner_id, message, query, attack_type)
        return True
    return False
