"""
KHUSHI Web Player — Configuration
══════════════════════════════════════════════════════════════
Copy this file and edit the values below.

SETUP OPTIONS
─────────────
Option A — Cloudflare Domain (recommended):
  1. Point your domain to your VPS IP in Cloudflare DNS
  2. Set WEB_DOMAIN to your domain, e.g.  "music.yourdomain.com"
  3. Set WEB_PORT to 80 (or 443 for SSL)
  4. Leave WEB_HOST as "0.0.0.0" so the server binds on all interfaces

Option B — VPS direct IP (no domain):
  1. Set WEB_DOMAIN to your VPS IPv4 or IPv6, e.g.  "203.0.113.42"
  2. Set WEB_PORT to any open port, e.g.  8080
  3. URL will be  http://203.0.113.42:8080

Option C — Replit / Railway (auto-detected, no changes needed):
  The URL is auto-detected from environment variables.
  Set WEB_ENABLED = False to disable the web player completely.

SSL NOTES
─────────
  Telegram WebApp requires HTTPS.  Use Cloudflare proxy (orange cloud)
  which handles SSL for you — the bot connects to Cloudflare over HTTP,
  Cloudflare serves it to users over HTTPS.  No local SSL cert needed.

FIREWALL
────────
  Open WEB_PORT in your VPS firewall (UFW / iptables).
  Example:  sudo ufw allow 8080/tcp
══════════════════════════════════════════════════════════════
"""

from os import getenv

# ── Enable / disable the built-in web server ──────────────────────────────────
WEB_ENABLED: bool = getenv("WEB_ENABLED", "true").lower() in ("1", "true", "yes")

# ── Network binding ───────────────────────────────────────────────────────────
# Address the server listens on.  Keep "0.0.0.0" to accept all connections.
WEB_HOST: str = getenv("WEB_HOST", "0.0.0.0")

# Port the web server listens on.
# • Railway / Heroku inject $PORT automatically — that takes priority.
# • Replit webview requires port 5000 — auto-detected via REPLIT_DEV_DOMAIN.
# • Override via WEB_PORT env var, or leave as 8080 for VPS/direct.
_on_replit: bool = bool(getenv("REPLIT_DEV_DOMAIN"))
_default_port: str = "5000" if _on_replit else "8080"
WEB_PORT: int = int(getenv("PORT", getenv("WEB_PORT", _default_port)))

# ── Public URL (what Telegram sees) ──────────────────────────────────────────
# Your public domain or VPS IP.  Examples:
#   "music.yourdomain.com"   →  served as  https://music.yourdomain.com  (Cloudflare)
#   "203.0.113.42"           →  served as  http://203.0.113.42:8080
#   ""                       →  auto-detect from Railway / Replit env vars
WEB_DOMAIN: str = getenv("WEB_DOMAIN", "").strip()

# Force HTTPS in the generated URL.
# Set to True when using Cloudflare proxy or your own SSL termination.
WEB_HTTPS: bool = getenv("WEB_HTTPS", "true").lower() in ("1", "true", "yes")

# ── Computed public URL (do not edit) ────────────────────────────────────────
def get_public_url() -> str:
    if not WEB_ENABLED:
        return ""
    if not WEB_DOMAIN:
        return ""
    scheme = "https" if WEB_HTTPS else "http"
    domain = WEB_DOMAIN.rstrip("/")
    if not domain.startswith("http"):
        if WEB_HTTPS:
            url = f"https://{domain}"
        else:
            url = f"http://{domain}"
            if WEB_PORT not in (80, 443):
                url += f":{WEB_PORT}"
        return url
    return domain

WEB_PUBLIC_URL: str = get_public_url()
