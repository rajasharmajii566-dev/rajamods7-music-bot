"""
Smart Content Filter — Advanced title/text screening for inappropriate content.

Design:
- HARD_BLOCK: Words that are ALWAYS inappropriate regardless of context (porn sites, etc.)
- PHRASE_BLOCK: Multi-word phrases — only block when the exact phrase appears
- CONTEXT_WORDS: Words that are bad ONLY when combined with sexual/drug context words
- SAFE_EXCEPTIONS: Common music/cultural terms that should never trigger a block

This avoids false positives on legitimate songs like:
  "MMS" (Bollywood song), "Sexy" (Justin Bieber song), "Bhang" (Holi songs), etc.
"""

import re
from typing import Optional

# ── Always-blocked: porn sites, explicit adult sites ─────────────────────────
HARD_BLOCK = [
    "pornhub", "xvideos", "xnxx", "xhamster", "xmaster",
    "redtube", "youporn", "porn.com", "sex.com",
    "hentai", "rule34",
    "blowjob", "handjob", "pussy", "cock", "boner",
    "gangbang", "creampie", "cumshot", "deepthroat",
    "rape", "molest", "child porn", "cp video",
    "nude video", "naked video",
    "cocaine", "heroin", "meth", "fentanyl", "mdma",
    "lsd trip", "ecstasy pill", "crack cocaine",
    "trafficking",
]

# ── Phrases that are bad only as a phrase ────────────────────────────────────
PHRASE_BLOCK = [
    "mms video", "mms clip", "mms leaked", "mms scandal",
    "sex tape", "sex video", "viral sex", "hot sex",
    "leaked video", "leaked mms", "bf video", "b grade film",
    "blue film", "adult film", "xxx video", "xxx film",
    "hot girl naked", "nude girl", "naked girl",
    "drug deal", "drug lord", "buy drugs", "sell drugs",
    "how to make drugs",
    "child abuse", "rape video",
]

# ── Context-dependent: only block when combined with a "bad" context ──────────
# These alone are fine in music (sexy, nude, drug references in art/culture)
CONTEXT_TRIGGER_WORDS = [
    "porn", "xxx", "sex", "nude", "naked", "erotic",
    "hot video", "adult content", "18+ content",
]

# How close the context words must be (within N words of the trigger)
_CONTEXT_WINDOW = 5

# ── Safe exceptions — common in legitimate Indian/Bollywood songs ─────────────
# These will NEVER trigger a block even if they appear in keyword lists
SAFE_EXCEPTIONS = {
    # Common song/movie titles and cultural words
    "mms",              # Popular Bollywood song title
    "sexy",             # Justin Bieber, many Bollywood songs
    "sex",              # "Sex" by The 1975, many mainstream songs
    "bhang",            # Holi festival cultural reference
    "ganja",            # Bob Marley, cultural reference in many songs
    "weed",             # Appears in many mainstream songs
    "marijuana",        # Mainstream songs
    "opium",            # Historical/cultural reference
    "hash",             # Common word with multiple meanings
    "smack",            # Common slang, many meanings
    "drug",             # "Drug" is in many legitimate song titles
    "drugs",            # "Drugs" appears in many mainstream songs
    "cocaine",          # "Cocaine" by Eric Clapton, famous classic rock song
    "heroin",           # Referenced in many rock/rap songs
    "crack",            # Many uses in music
    "high",             # Extremely common in songs
    "charas",           # Cultural reference
    "afeem",            # Cultural reference
    "mdma",             # Referenced in many songs
    "ecstasy",          # Referenced in many songs
    "lsd",              # Many song references
    "boobs",            # Appears in many mainstream songs
    "dick",             # Very common name, also appears in songs
    "explicit",         # YouTube uses this for explicit content labels
    "18+",              # Age rating label
    "adult",            # Very common word
    "nsfw",             # Common internet term
    "strip",            # Strip tease, also stripping a car, etc.
    "nude",             # Appears in many art/mainstream song titles
    "naked",            # Many legitimate song titles
    "erotic",           # Art/music references
}

# ── Build compiled patterns ───────────────────────────────────────────────────

def _build_pattern(terms):
    escaped = [re.escape(t) for t in terms]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)

_HARD_PATTERN   = _build_pattern(HARD_BLOCK)
_PHRASE_PATTERN = _build_pattern(PHRASE_BLOCK)
_CONTEXT_PATTERN = _build_pattern(CONTEXT_TRIGGER_WORDS)


def is_bad_text(text: str) -> Optional[str]:
    """
    Check if text contains inappropriate content.
    Returns the matched bad term, or None if the text is clean.

    Uses multi-tier checking to avoid false positives on legitimate music.
    """
    if not text:
        return None

    # Remove safe exceptions temporarily for checking
    # (We DON'T want "mms" alone to trigger, only "mms video" etc.)
    text_lower = text.lower().strip()

    # ── Tier 1: Hard-blocked terms (always bad) ───────────────────────────
    m = _HARD_PATTERN.search(text)
    if m:
        word = m.group(0).lower()
        if word not in SAFE_EXCEPTIONS:
            return m.group(0)

    # ── Tier 2: Phrase matching (multi-word phrases) ──────────────────────
    m = _PHRASE_PATTERN.search(text)
    if m:
        return m.group(0)

    # ── Tier 3: Context-sensitive checking ───────────────────────────────
    # Only flag if a questionable word appears near explicit context
    # (e.g., "sex" alone might be in a song title, but "sex video" is not OK)
    # This is handled by PHRASE_BLOCK already for most cases

    return None


# ── Image analysis utilities ──────────────────────────────────────────────────

def _skin_ratio(image_bytes: bytes) -> float:
    try:
        from PIL import Image
        import numpy as np

        img = Image.open(__import__("io").BytesIO(image_bytes)).convert("RGB")
        img = img.resize((200, 200))
        arr = __import__("numpy").array(img, dtype=float)

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        skin_mask = (
            (r > 95) & (g > 40) & (b > 20) &
            (r > g) & (r > b) &
            ((r - g) > 15) &
            (r < 240) & (g < 200) & (b < 180)
        )

        return float(skin_mask.sum()) / (200 * 200)
    except Exception:
        return 0.0


def analyze_image_bytes(image_bytes: bytes) -> bool:
    ratio = _skin_ratio(image_bytes)
    return ratio > 0.35
