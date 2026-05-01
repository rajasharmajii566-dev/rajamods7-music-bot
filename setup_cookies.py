"""
YouTube Cookies Setup Helper — AnnieMusic Bot
=============================================

Agar YouTube 403 / "Please sign in" errors aa rahe hain toh
cookies add karo is script se.

USAGE:
  python setup_cookies.py <cookies.txt path>

COOKIES KAISE EXPORT KARO (Chrome/Firefox):
  1. Chrome mein "Get cookies.txt LOCALLY" extension install karo:
     https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
  2. YouTube.com open karo aur login karo apne Google account se
  3. Extension click karo → "Export" → cookies.txt file download karo
  4. Yeh script run karo:
     python setup_cookies.py /path/to/cookies.txt

RAILWAY DEPLOYMENT:
  Script ek base64 string print karega jise Railway mein
  YOUTUBE_COOKIES_B64 env variable mein daalo.

LOCAL DEPLOYMENT (Replit):
  Script cookies file automatically copy kar dega.
"""

import sys
import os
import base64
import shutil


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cookies_path = sys.argv[1]
    if not os.path.exists(cookies_path):
        print(f"ERROR: File not found: {cookies_path}")
        return

    with open(cookies_path, "rb") as f:
        data = f.read()

    if len(data) < 10:
        print("ERROR: Cookies file is too small / empty")
        return

    # Encode to base64 for Railway env var
    b64 = base64.b64encode(data).decode()

    print("=" * 60)
    print("COOKIES SETUP COMPLETE")
    print("=" * 60)
    print()
    print("OPTION 1 — Railway/Cloud Deployment:")
    print("  Add this to Railway Variables:")
    print(f"  Variable Name:  YOUTUBE_COOKIES_B64")
    print(f"  Variable Value: (copied below)")
    print()
    print("--- COPY FROM HERE ---")
    print(b64)
    print("--- COPY UNTIL HERE ---")
    print()
    print("OPTION 2 — Local (Replit):")

    # Copy to project root
    dest = os.path.join(os.path.dirname(__file__), "youtube_cookies.txt")
    shutil.copy2(cookies_path, dest)
    print(f"  Cookies copied to: {dest}")
    print("  Bot will use them automatically on next restart.")
    print()
    print("OPTION 3 — Set env var directly:")
    print(f"  export YOUTUBE_COOKIES_B64='{b64[:40]}...'")
    print()
    print("After setting Railway variable → redeploy your service.")


if __name__ == "__main__":
    main()
