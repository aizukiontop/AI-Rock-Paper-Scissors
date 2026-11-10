"""
Flask routes for the game API and page serving.

Frontend: the UI is the built React SPA under ../static/app (see
frontend/, built with `npm run build`). Flask serves its compiled
index.html for every page route below and its JS/CSS/assets as plain
static files — the SPA itself switches between Arena / Leaderboard /
Robot Lab client-side (see frontend/src/App.tsx), so every route here
renders the same shell.

Webcam: gesture detection runs client-side, in the player's own browser
(Figma's useCamera.ts, via @mediapipe/tasks-vision) — the backend never
opens a camera device. The browser pushes its live reading to
POST /api/camera/gesture on every detection tick; `gesture_buffer` (see
gesture_buffer.py) keeps a short rolling history of those pushes so the
round state machine can sample a stable value at its own chosen moment,
exactly as it did when reading a server-side camera before. The old
server-side OpenCV/MediaPipe capture path (camera.py, gesture_recognizer.py,
model_downloader.py) is left in the repo but is no longer wired into live
gameplay, since it only ever had access to whatever camera was attached to
the SERVER, not the player's own device.

Identity model (see players.py for details):
  - A username is "claimed" via POST /api/player/claim, which returns a
    secret token the browser stores (e.g. localStorage) and resends on
    future visits to resume the same identity. The server — never the
    client — decides whether a resume is authorized, by comparing a
    hash of that token against the one stored for that username.
  - `current_player` below is who the single shared game session (and
    therefore the single shared gesture buffer) currently belongs to.
    This app has exactly one session per running server, matching the
    existing architecture, so identity here is process-wide rather than
    per-browser-tab.
  - Round outcomes are always computed server-side in game_session.py
    from the actual gesture detected (locally, by the player's browser,
    then read by the server at its own chosen "locked" moment); the
    browser never submits a win/loss/streak value, so scores can't be
    forged client-side.
"""

import os
from flask import jsonify, request, send_from_directory
from .gesture_buffer import GestureBuffer
from .game_session import GameSession, GameState
from . import players

# Global singletons (one gesture buffer + game session per server instance)
gesture_buffer: GestureBuffer = GestureBuffer()
session: GameSession = GameSession()
current_player: dict | None = None  # {"username": ...} of whoever is playing

# Button-mode moves are translated to the same MediaPipe class names the
# webcam path produces, so game_session.py's map_gesture() handles both
# input methods identically -- no changes needed to the round state
# machine or scoring logic to support Buttons mode alongside Webcam mode.
_BUTTON_MOVE_TO_GESTURE = {"rock": "Closed_Fist", "paper": "Open_Palm", "scissors": "Victory"}

_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'static', 'app')


def _record_round_for_current_player(outcome, player_move, ai_move):
    """Wired into GameSession as its stat_hook — see game_session.py."""
    if not current_player:
        return None
    return players.record_round(current_player["username"], outcome, player_move, ai_move)


session.stat_hook = _record_round_for_current_player


def register_routes(app):

    def _serve_spa():
        """Serve the built SPA shell. All client-side pages share this route."""
        index_path = os.path.join(_FRONTEND_DIST, 'index.html')
        if not os.path.isfile(index_path):
            return (
                "Frontend build not found. Run `npm install && npm run build` "
                "inside frontend/ to produce static/app/index.html.",
                503,
            )
        return send_from_directory(_FRONTEND_DIST, 'index.html')

    @app.route('/')
    def index():
        return _serve_spa()

    @app.route('/robot-lab')
    def robot_lab():
        """
        Robot Lab is now a page inside the SPA itself (see App.tsx's "lab"
        page), not a separate Jinja template. This route is kept only so an
        existing bookmark/link still lands on the app; the SPA's own sidebar
        nav takes it from there.
        """
        return _serve_spa()

    # ── Camera (browser-fed; the server never opens a camera device) ───
    @app.route('/api/camera/gesture', methods=['POST'])
    def camera_gesture():
        """
        Called by the player's own browser on every client-side gesture
        detection tick (see frontend/src/useCamera.ts). `gesture` is one of
        the MediaPipe class names ("Closed_Fist", "Open_Palm", "Victory")
        or null when nothing recognizable is currently in frame. No image
        data is ever sent — only the already-classified gesture name.
        """
        data = request.json or {}
        gesture = data.get('gesture')
        if gesture not in ('Closed_Fist', 'Open_Palm', 'Victory', None):
            return jsonify({"ok": False, "error": "Unrecognized gesture value"}), 400
        gesture_buffer.push(gesture)
        return jsonify({"ok": True})

    # ── Player identity ──────────────────────────────────────────────
    @app.route('/api/player/claim', methods=['POST'])
    def player_claim():
        """Register a new username, or resume an existing one with a token."""
        global current_player
        data = request.json or {}
        username = (data.get('username') or '').strip()
        token = data.get('token')

        ok, error, new_token, stats = players.claim_username(username, token)
        if not ok:
            return jsonify({"ok": False, "error": error}), 409

        current_player = {"username": stats["username"]}
        rank = players.get_rank(stats["username"])
        return jsonify({"ok": True, "token": new_token, "stats": stats, "rank": rank})

    @app.route('/api/player/me')
    def player_me():
        """Return the currently active player's stats, if any."""
        if not current_player:
            return jsonify({"player": None})
        stats = players.get_stats(current_player["username"])
        if not stats:
            return jsonify({"player": None})
        rank = players.get_rank(current_player["username"])
        return jsonify({"player": stats["username"], "stats": stats, "rank": rank})

    @app.route('/api/player/stats/reset', methods=['POST'])
    def player_stats_reset():
        if not current_player:
            return jsonify({"ok": False, "error": "No active player"}), 400
        stats = players.reset_player_stats(current_player["username"])
        return jsonify({"ok": True, "stats": stats, "rank": players.get_rank(current_player["username"])})

    # ── Leaderboard ───────────────────────────────────────────────────
    @app.route('/api/leaderboard')
    def leaderboard():
        search = request.args.get('search') or None
        sort_by = request.args.get('sort', 'streak')
        if sort_by not in ('streak', 'wins', 'winrate'):
            sort_by = 'streak'
        rows, source = players.get_leaderboard(limit=10, search=search, sort_by=sort_by)
        you = current_player["username"] if current_player else None
        for row in rows:
            row["is_you"] = you is not None and row["username"].lower() == you.lower()
        return jsonify({
            "rows": rows,
            "source": source,
            "sort": sort_by,
            "min_rounds_for_winrate": players.MIN_ROUNDS_FOR_WIN_RATE,
        })

    # ── Game ─────────────────────────────────────────────────────────
    def _resolve_move_source(data):
        """
        Returns (gesture_fn, error_response_or_None). Buttons mode needs no
        camera at all -- it hands the round a fixed, already-known value.
        Webcam mode reads the live, stability-checked reading from
        `gesture_buffer`, fed continuously by the player's own browser (see
        module docstring) -- the server samples it lazily, at its own
        chosen "locked" moment, same as before.
        """
        input_mode = data.get('input_mode', 'webcam')
        if input_mode == 'buttons':
            move = data.get('move')
            gesture_name = _BUTTON_MOVE_TO_GESTURE.get(move)
            if not gesture_name:
                return None, (jsonify({"ok": False, "error": "A move (rock/paper/scissors) is required in Buttons mode"}), 400)
            return (lambda g=gesture_name: g), None

        return gesture_buffer.get_stable_gesture, None

    @app.route('/api/game/start', methods=['POST'])
    def game_start():
        if not current_player:
            return jsonify({"ok": False, "error": "Choose a username first"}), 400

        data = request.json or {}
        gesture_fn, err = _resolve_move_source(data)
        if err:
            return err

        mode = data.get('mode')  # None, 'best3', 'best5', 'best10'
        new_sess = data.get('new_session', False)

        if new_sess:
            session.new_session(gesture_fn, mode=mode)
        else:
            session.start_round(gesture_fn, mode=mode)

        return jsonify({"ok": True})

    @app.route('/api/game/restart', methods=['POST'])
    def game_restart():
        data = request.json or {}
        gesture_fn, err = _resolve_move_source(data)
        if err:
            return err
        session.restart_round(gesture_fn)
        return jsonify({"ok": True})

    @app.route('/api/game/status')
    def game_status():
        return jsonify(session.get_status())
