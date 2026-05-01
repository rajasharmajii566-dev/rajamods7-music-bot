"""
KHUSHI Web Server
Serves KHUSHI's own web UI from KHUSHI/web/
All API endpoints are identical to the main webserver.
"""
import os
import sys

# Add project root so KHUSHI utils can be imported
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Import the main webserver module and override WEB_DIR to point to KHUSHI/web/
import webserver as _ws

_ws.WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    _ws.app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
