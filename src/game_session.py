"""
Game session manager — authoritative round-lifecycle state machine.

Each round moves through these states, in order, and ONLY in this order:

    IDLE -> COUNTDOWN -> DETECTING -> LOCKED -> REVEALING -> RESULT
                                                           (or GAME_OVER
                                                            if the match
                                                            is decided)

The backend is the single source of truth for which phase the round is in
and what data is visible at each phase:
  - COUNTDOWN: nothing about the round is visible yet.
  - DETECTING: a short window where the camera's gesture reading is given
    a moment to stabilize before anything is captured.
  - LOCKED: the player's gesture has just been read ONCE (the single
    authoritative read for this round) and is now fixed. It's exposed to
    the frontend here so the UI can show "your move is locked in" --
    the AI's move, the outcome, and stats are still withheld.
  - REVEALING: a short anticipation beat. Still nothing new exposed.
  - RESULT / GAME_OVER: the AI's move, the outcome, and stats all appear
    together, in the same response, for the first time. They then stay
    exactly as they are -- nothing in get_status() changes again -- until
    the next start_round() call, so repeated polling can never make
    completed-round data flicker or disappear.

Every round gets a strictly increasing `round_id`. The frontend uses it
(not any derived/optional field like player stats) to tell a freshly
completed round apart from one it has already processed, so a result is
never handled twice and a stale response can never overwrite a newer one.
"""

import time
import threading
from .game_logic import ai_choose, map_gesture, determine_winner, result_message, Move

# Best-of mode -> number of wins needed to clinch the match (a strict
# majority of the available rounds: 2 of 3, 3 of 5, 6 of 10).
TARGET_WINS = {"best3": 2, "best5": 3, "best10": 6}

# How long each post-countdown phase holds the screen, in seconds. Short
# and fixed, so every phase is genuinely visible without slowing the game
# down noticeably.
DETECTING_SECONDS = 0.6
LOCKED_SECONDS = 0.35
REVEALING_SECONDS = 0.35


class GameState:
    IDLE = "idle"
    COUNTDOWN = "countdown"
    DETECTING = "detecting"
    LOCKED = "locked"
    REVEALING = "revealing"
    RESULT = "result"
    GAME_OVER = "game_over"


# A round is "in progress" in any of these states; start_round() refuses to
# begin a new round while in one of them, so a duplicate/accidental start
# call (e.g. a stray double click) can never interrupt or race a round
# that's already running.
_IN_PROGRESS = {GameState.COUNTDOWN, GameState.DETECTING, GameState.LOCKED, GameState.REVEALING}


class GameSession:
    """
    Manages a single game session. The round itself runs end-to-end in one
    background thread per round (_run_round), updating self.state under a
    lock at each phase transition; get_status() is a read-only snapshot.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Set from the outside (routes.py) to persist/sync a round result
        # for whichever player currently "owns" this session. Signature:
        # stat_hook(outcome, player_move_value, ai_move_value) -> dict | None
        self.stat_hook = None
        # Ever-increasing id, bumped once per round in start_round(). Not
        # touched by _reset_state() -- it must never go backwards, even
        # across new_session() calls, so a response from a round that was
        # abandoned by a new_session() can never be mistaken for current.
        self.round_id = 0
        self._reset_state()

    def _reset_state(self):
        self.state = GameState.IDLE
        self.countdown_value = 0
        self.ai_move = None
        self.player_move = None
        self.outcome = None
        self.result_msg = None
        self.stats = None
        self.get_gesture_fn = None

        # Best-of tracking
        self.mode = None
        self.session_wins = 0
        self.session_losses = 0
        self.session_draws = 0
        self.target_wins = 0
        self.session_round = 0

    def start_round(self, get_gesture_fn, mode=None):
        """
        Start a new round. Refuses to do anything if a round is already
        in progress (see _IN_PROGRESS) -- this is the backend-side
        safeguard against duplicate/overlapping rounds, independent of
        whatever the frontend does.
        """
        with self._lock:
            if self.state in _IN_PROGRESS:
                return  # A round is already running; ignore this call entirely

            if mode and self.state in (GameState.IDLE, GameState.GAME_OVER):
                self.mode = mode
                self.session_wins = 0
                self.session_losses = 0
                self.session_draws = 0
                self.session_round = 0
                self.target_wins = TARGET_WINS.get(mode, 0)

            self.round_id += 1
            self.state = GameState.COUNTDOWN
            self.countdown_value = 3
            self.ai_move = ai_choose()
            self.player_move = None
            self.outcome = None
            self.result_msg = None
            self.get_gesture_fn = get_gesture_fn

        threading.Thread(target=self._run_round, daemon=True).start()

    def _run_round(self):
        """Drive one round through every phase of the state machine, in order."""
        for i in range(3, 0, -1):
            with self._lock:
                self.countdown_value = i
            time.sleep(1.0)

        with self._lock:
            self.state = GameState.DETECTING
        time.sleep(DETECTING_SECONDS)

        # The single authoritative read of the camera for this round.
        gesture_name = self.get_gesture_fn() if self.get_gesture_fn else None
        player_move = map_gesture(gesture_name) if gesture_name else Move.FORFEIT
        if player_move is None:
            player_move = Move.FORFEIT
        with self._lock:
            self.player_move = player_move
            self.state = GameState.LOCKED
        time.sleep(LOCKED_SECONDS)

        with self._lock:
            ai_move = self.ai_move
        outcome = determine_winner(player_move, ai_move)
        msg = result_message(outcome, player_move, ai_move)

        stats = None
        if self.stat_hook:
            try:
                stats = self.stat_hook(outcome, player_move.value, ai_move.value)
            except Exception as e:
                print(f"[game_session] stat_hook failed: {e}")

        with self._lock:
            self.state = GameState.REVEALING
        time.sleep(REVEALING_SECONDS)

        with self._lock:
            self.outcome = outcome
            self.result_msg = msg
            self.stats = stats
            self.session_round += 1

            if outcome == "win":
                self.session_wins += 1
            elif outcome in ("loss", "forfeit"):
                self.session_losses += 1
            else:
                self.session_draws += 1

            if (self.mode and self.target_wins > 0
                    and (self.session_wins >= self.target_wins or self.session_losses >= self.target_wins)):
                self.state = GameState.GAME_OVER
            else:
                self.state = GameState.RESULT

    def get_status(self) -> dict:
        """Get current game state as a JSON-serializable, read-only snapshot."""
        with self._lock:
            base = {
                "state": self.state,
                "round_id": self.round_id,
                "countdown": self.countdown_value,
                "mode": self.mode,
                "session_wins": self.session_wins,
                "session_losses": self.session_losses,
                "session_draws": self.session_draws,
                "session_round": self.session_round,
                "target_wins": self.target_wins,
            }

            # The player's own move becomes visible the instant it's locked
            # in -- before the AI's move, so "locked before reveal" is a
            # real, inspectable fact and not just a frontend animation.
            if self.state in (GameState.LOCKED, GameState.REVEALING, GameState.RESULT, GameState.GAME_OVER):
                base["player_move"] = self.player_move.value if self.player_move else None

            # The AI's move, the outcome, and stats all appear together,
            # for the first time, only once the round is fully settled --
            # and then never change again until the next round starts.
            if self.state in (GameState.RESULT, GameState.GAME_OVER):
                base.update({
                    "ai_move": self.ai_move.value if self.ai_move else None,
                    "outcome": self.outcome,
                    "result": self.result_msg,
                    "stats": self.stats,
                })

            return base

    def restart_round(self, get_gesture_fn):
        """Start another round in the current mode (e.g. 'Next round')."""
        self.start_round(get_gesture_fn)

    def new_session(self, get_gesture_fn, mode=None):
        """Reset session and start fresh (e.g. 'Start match')."""
        with self._lock:
            self._reset_state()
        self.start_round(get_gesture_fn, mode=mode)
