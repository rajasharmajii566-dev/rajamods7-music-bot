import os


def get_web_url() -> str:
    """
    Resolve the web player public URL.

    Priority:
      1. web_config.WEB_PUBLIC_URL  — set WEB_DOMAIN / WEB_HTTPS in web_config.py
      2. WEB_APP_URL env var        — manual override for Railway / any host
      3. RAILWAY_PUBLIC_DOMAIN / RAILWAY_STATIC_URL  — Railway auto-injects this
      4. REPLIT_DEV_DOMAIN          — Replit auto-injects this
      5. Empty string               — web player disabled / URL unavailable
    """
    # 1. web_config.py (VPS / Cloudflare domain setup)
    try:
        from web_config import WEB_PUBLIC_URL, WEB_ENABLED
        if WEB_ENABLED and WEB_PUBLIC_URL:
            return WEB_PUBLIC_URL.rstrip("/")
    except ImportError:
        pass

    # 2. Manual env var override
    url = os.getenv("WEB_APP_URL", "").strip()
    if url:
        return url.rstrip("/")

    # 3. Railway
    for key in ("RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL"):
        val = os.getenv(key, "").strip()
        if val:
            if not val.startswith("http"):
                val = f"https://{val}"
            return val.rstrip("/")

    # 4. Replit
    replit = os.getenv("REPLIT_DEV_DOMAIN", "").strip()
    if replit:
        return f"https://{replit}".rstrip("/")

    return ""


# Module-level singleton – evaluated once at import time.
WEB_URL: str = get_web_url()
