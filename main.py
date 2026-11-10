#!/usr/bin/env python3
"""
AI Rock Paper Scissors
A web-based desktop game using Flask, OpenCV, and MediaPipe.
Run with: python main.py
Then open http://localhost:5000 in your browser.
"""

import sys
import os

# Make sure the project root (this file's directory) is on sys.path so
# that "src" is importable as a package, regardless of the current
# working directory the script is launched from.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_dotenv(path):
    """
    Minimal .env loader (no python-dotenv dependency). Only sets a variable
    if it isn't already present in the real environment, so real env vars
    always win. Used for optional Supabase credentials (see .env.example).
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from src.app import create_app
from src import supabase_rest

# Module-level `app` so a production WSGI server can import this file
# directly (e.g. `gunicorn main:app` — see Procfile). Creating it here,
# not inside the __main__ guard below, is what makes that importable.
app = create_app()

# Almost every PaaS (Render, Railway, Heroku, Fly.io, ...) assigns a port
# at deploy time via the PORT env var and routes external traffic to
# THAT port — if the app listens on a different one instead, the
# platform's edge proxy can never reach it, which shows up to visitors
# as a bare "502 Bad Gateway" with no application-level detail at all.
# Falls back to 5000 for local development, where nothing sets PORT.
PORT = int(os.environ.get('PORT', 5000))

if __name__ == '__main__':
    leaderboard_mode = "ONLINE (Supabase)" if supabase_rest.is_configured() else "LOCAL ONLY (no Supabase configured)"
    print("\n" + "="*50)
    print("  AI Rock Paper Scissors")
    print("="*50)
    print(f"  Open: http://localhost:{PORT}")
    print(f"  Leaderboard: {leaderboard_mode}")
    print("  Press Ctrl+C to quit")
    print("="*50 + "\n")
    print("  NOTE: this is Flask's development server. For a real")
    print("  deployment, use a production WSGI server instead, e.g.:")
    print("    gunicorn -w 2 -b 0.0.0.0:$PORT main:app")
    print("  (see Procfile)\n")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
