"""
Minimal server-side Supabase (PostgREST) client for the `leaderboard` table.

This module is ONLY ever imported by players.py / routes.py and runs on the
Flask server. Credentials come from environment variables and are never
sent to the browser — the frontend never talks to Supabase directly.

If SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set, is_configured()
returns False and every caller falls back to the local JSON store in
players.py, so the app still works fully offline.
"""

import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "leaderboard"
TIMEOUT = 5  # seconds — fail fast rather than blocking gameplay


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers(extra: dict | None = None) -> dict:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def username_exists(username: str) -> bool:
    """Check whether a username is already claimed in the global table."""
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    r = requests.get(
        url,
        headers=_headers(),
        params={"select": "username", "username": f"eq.{username}"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return len(r.json()) > 0


def insert_leaderboard_row(row: dict):
    """
    Plain INSERT for a brand-new player. Relies on the table's UNIQUE
    constraint on username: if two machines race to claim the same new
    name at the same instant, the loser gets a 409 Conflict here, which
    players.py treats as 'username just taken'.
    """
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    r = requests.post(url, json=row, headers=_headers({"Prefer": "return=minimal"}), timeout=TIMEOUT)
    r.raise_for_status()


def upsert_leaderboard_row(row: dict):
    """
    Update an existing player's row (we already own this username locally).
    Uses merge-duplicates so it behaves as an UPDATE keyed on username.
    """
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    headers = _headers({"Prefer": "resolution=merge-duplicates,return=minimal"})
    r = requests.post(url, json=row, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()


# Each supported leaderboard category maps to the column PostgREST should
# order by. "winrate" additionally requires total_rounds >= min_rounds so a
# single lucky game can't rank above players with a real track record --
# that filter is applied in get_leaderboard() below.
_SORT_COLUMNS = {
    "streak": "best_streak",
    "wins": "total_wins",
    "winrate": "win_rate",
}


def get_leaderboard(limit: int = 10, search: str | None = None,
                     sort_by: str = "streak", min_rounds: int = 10) -> list[dict]:
    column = _SORT_COLUMNS.get(sort_by, "best_streak")
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    params = {
        "select": "username,best_streak,total_wins,total_losses,total_draws,total_rounds,win_rate",
        "order": f"{column}.desc,username.asc",
        "limit": str(limit),
    }
    if sort_by == "winrate":
        params["total_rounds"] = f"gte.{min_rounds}"
    if search:
        params["username"] = f"ilike.*{search}*"
    r = requests.get(url, headers=_headers(), params=params, timeout=TIMEOUT)
    r.raise_for_status()
    rows = r.json()
    return [
        {
            "rank": i + 1,
            "username": row["username"],
            "best_streak": row["best_streak"],
            "total_wins": row["total_wins"],
            "win_rate": row.get("win_rate", 0),
            "total_rounds": row.get("total_rounds", 0),
        }
        for i, row in enumerate(rows)
    ]


def get_rank(username: str, sort_by: str = "streak") -> int:
    """1-based global rank in the given category. Raises if the player isn't found."""
    column = _SORT_COLUMNS.get(sort_by, "best_streak")
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    r = requests.get(
        url,
        headers=_headers(),
        params={"select": column, "username": f"eq.{username}"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError("player not found in Supabase")
    value = rows[0][column]

    count_headers = _headers({"Prefer": "count=exact"})
    r2 = requests.get(
        url,
        headers=count_headers,
        params={"select": "username", column: f"gt.{value}"},
        timeout=TIMEOUT,
    )
    r2.raise_for_status()
    content_range = r2.headers.get("Content-Range", "")
    total_higher = int(content_range.split("/")[-1]) if "/" in content_range else len(r2.json())
    return total_higher + 1
