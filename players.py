"""
Player identity and persistent, server-authoritative statistics.

Local JSON (data/players.json) is always the source of truth for THIS
machine and for authentication (a secret token per username, never sent
to Supabase). When Supabase is configured, every completed round and new
registration is mirrored into the shared `leaderboard` table so the top-10
is visible across machines. If Supabase is unreachable, local stats are
still saved — the next successful round retries the sync automatically.

Round outcomes are only ever passed in here by game_session.py, which
computes them itself from the camera/gesture state — the browser never
submits a win/loss/streak value directly, so a client can't forge scores.
"""

import os
import re
import json
import secrets
import hashlib
import threading
from datetime import datetime, timezone

from . import supabase_rest as sb

PLAYERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'players.json')
USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,16}$')
ROBOT_BREAK_EVERY = 10  # trigger the glass-smash achievement every 10 consecutive wins

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _load() -> dict:
    try:
        with open(PLAYERS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(PLAYERS_FILE), exist_ok=True)
    with open(PLAYERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def validate_username(username: str) -> str | None:
    """Return an error message, or None if the username is valid."""
    if not username or not USERNAME_RE.match(username):
        return "Username must be 3-16 characters: letters, numbers, underscores only."
    return None


def _public_stats(record: dict) -> dict:
    total = record["total_wins"] + record["total_losses"] + record["total_draws"]
    win_rate = round(record["total_wins"] / total * 100, 1) if total else 0.0
    return {
        "username": record["username"],
        "current_streak": record["current_streak"],
        "best_streak": record["best_streak"],
        "total_wins": record["total_wins"],
        "total_losses": record["total_losses"],
        "total_draws": record["total_draws"],
        "robot_breaks": record["robot_breaks"],
        "win_rate": win_rate,
        "total_rounds": total,
        "history": record.get("history", []),
    }


def claim_username(username: str, token: str | None):
    """
    Register a brand-new username, or resume an existing one with a
    matching token. Returns (ok, error, token_to_store, stats).
    The returned token must be stored by the client (e.g. localStorage)
    and sent back on `token` for future resumes — but it is the server-side
    hash comparison, not the client's say-so, that actually authorizes it.
    """
    err = validate_username(username)
    if err:
        return False, err, None, None

    with _lock:
        players = _load()
        key = username.lower()
        existing = players.get(key)

        if existing is not None:
            # Username already claimed on this machine — only the matching
            # token may resume it.
            if token and _hash_token(token) == existing["token_hash"]:
                return True, None, token, _public_stats(existing)
            return False, "That username is already taken.", None, None

        # Brand-new username on this machine. If Supabase is configured,
        # check there first so the name can't collide with another machine.
        if sb.is_configured():
            try:
                if sb.username_exists(username):
                    return False, "That username is already taken.", None, None
            except Exception as e:
                print(f"[leaderboard] availability check failed, continuing offline: {e}")

        new_token = secrets.token_hex(16)
        record = {
            "username": username,
            "token_hash": _hash_token(new_token),
            "current_streak": 0,
            "best_streak": 0,
            "total_wins": 0,
            "total_losses": 0,
            "total_draws": 0,
            "robot_breaks": 0,
            "history": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        players[key] = record
        _save(players)

        if sb.is_configured():
            try:
                sb.insert_leaderboard_row(_leaderboard_row(record))
            except Exception as e:
                if "409" in str(e):
                    # Lost a simultaneous race for this exact name on another
                    # machine — roll back the local claim.
                    del players[key]
                    _save(players)
                    return False, "That username was just taken by someone else.", None, None
                print(f"[leaderboard] initial sync failed, will retry later: {e}")

        return True, None, new_token, _public_stats(record)


def get_stats(username: str) -> dict | None:
    players = _load()
    record = players.get(username.lower())
    return _public_stats(record) if record else None


def record_round(username: str, outcome: str, player_move: str, ai_move: str) -> dict:
    """
    Update a player's persistent stats after a server-computed round
    result. Returns the updated public stats plus an 'achievement' flag
    that is only non-null on the exact round that triggers it.
    """
    with _lock:
        players = _load()
        key = username.lower()
        record = players.get(key)
        if record is None:
            return {"error": "unknown player"}

        achievement = None
        if outcome == "win":
            record["current_streak"] += 1
            record["total_wins"] += 1
            if record["current_streak"] > record["best_streak"]:
                record["best_streak"] = record["current_streak"]
            if record["current_streak"] % ROBOT_BREAK_EVERY == 0:
                record["robot_breaks"] += 1
                achievement = "robot_break"
        elif outcome == "draw":
            record["total_draws"] += 1
        else:  # loss or forfeit
            record["current_streak"] = 0
            record["total_losses"] += 1

        record.setdefault("history", [])
        record["history"].insert(0, {
            "round": record["total_wins"] + record["total_losses"] + record["total_draws"],
            "player": player_move,
            "ai": ai_move,
            "outcome": outcome,
        })
        record["history"] = record["history"][:20]

        record["updated_at"] = _now()
        players[key] = record
        _save(players)

    _sync_to_supabase(record)

    stats = _public_stats(record)
    stats["achievement"] = achievement
    return stats


def reset_player_stats(username: str) -> dict:
    with _lock:
        players = _load()
        key = username.lower()
        record = players.get(key)
        if record is None:
            return {"error": "unknown player"}
        for field in ("current_streak", "best_streak", "total_wins",
                      "total_losses", "total_draws", "robot_breaks"):
            record[field] = 0
        record["history"] = []
        record["updated_at"] = _now()
        players[key] = record
        _save(players)
    _sync_to_supabase(record)
    return _public_stats(record)


def _leaderboard_row(record: dict) -> dict:
    return {
        "username": record["username"],
        "current_streak": record["current_streak"],
        "best_streak": record["best_streak"],
        "total_wins": record["total_wins"],
        "total_losses": record["total_losses"],
        "total_draws": record["total_draws"],
        "robot_breaks": record["robot_breaks"],
        "updated_at": record["updated_at"],
    }


def _sync_to_supabase(record: dict):
    """Best-effort push of one player's row to Supabase. Never raises."""
    if not sb.is_configured():
        return
    try:
        sb.upsert_leaderboard_row(_leaderboard_row(record))
    except Exception as e:
        # Local JSON stays authoritative if Supabase is unreachable; the
        # next successful round retries automatically.
        print(f"[leaderboard] sync failed for {record['username']}: {e}")


#: Minimum completed rounds a player needs before they're eligible for the
#: Win Rate leaderboard, so a single lucky game can't outrank players with
#: a real track record. Kept as one constant so the Supabase path
#: (supabase_rest.get_leaderboard's default) and this local-file fallback
#: can never silently disagree on the threshold.
MIN_ROUNDS_FOR_WIN_RATE = 10

#: field each sort category ranks by, for the local-file fallback -- kept
#: in lockstep with supabase_rest._SORT_COLUMNS so "streak"/"wins"/"winrate"
#: mean exactly the same thing online or offline.
_LOCAL_SORT_FIELDS = {"streak": "best_streak", "wins": "total_wins", "winrate": "win_rate"}


def get_rank(username: str, sort_by: str = "streak") -> int | None:
    """Global rank in the given category (1 = best). sort_by: streak|wins|winrate."""
    if sb.is_configured():
        try:
            return sb.get_rank(username, sort_by=sort_by)
        except Exception as e:
            print(f"[leaderboard] rank lookup failed, using local file: {e}")

    players = _load()
    record = players.get(username.lower())
    if not record:
        return None
    field = _LOCAL_SORT_FIELDS.get(sort_by, "best_streak")
    my_value = _public_stats(record)[field] if field == "win_rate" else record[field]
    higher = 0
    for p in players.values():
        value = _public_stats(p)[field] if field == "win_rate" else p[field]
        if value > my_value:
            higher += 1
    return higher + 1


def get_leaderboard(limit: int = 10, search: str | None = None,
                     sort_by: str = "streak", min_rounds: int = MIN_ROUNDS_FOR_WIN_RATE):
    """
    Returns (rows, source) where source is 'online' or 'local'.
    sort_by: 'streak' (highest win streak), 'wins' (all-time total wins),
    or 'winrate' (win rate, restricted to players with >= min_rounds
    completed rounds so a one-game lucky streak can't dominate).
    """
    if sb.is_configured():
        try:
            return sb.get_leaderboard(limit=limit, search=search, sort_by=sort_by, min_rounds=min_rounds), "online"
        except Exception as e:
            print(f"[leaderboard] fetch failed, falling back to local file: {e}")

    players = _load()
    candidates = [_public_stats(p) for p in players.values()]
    if sort_by == "winrate":
        candidates = [p for p in candidates if p["total_rounds"] >= min_rounds]

    field = _LOCAL_SORT_FIELDS.get(sort_by, "best_streak")
    candidates.sort(key=lambda p: (-p[field], p["username"].lower()))

    if search:
        s = search.lower()
        candidates = [p for p in candidates if s in p["username"].lower()]
    candidates = candidates[:limit]
    out = [
        {
            "rank": i + 1,
            "username": p["username"],
            "best_streak": p["best_streak"],
            "total_wins": p["total_wins"],
            "win_rate": p["win_rate"],
            "total_rounds": p["total_rounds"],
        }
        for i, p in enumerate(candidates)
    ]
    return out, "local"
