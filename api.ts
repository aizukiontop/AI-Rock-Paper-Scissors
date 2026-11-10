/**
 * Thin, typed wrapper around the existing Flask backend's JSON API
 * (see ../../src/routes.py). This file is the ONLY place that knows about
 * HTTP/fetch — every component talks to it through these functions, never
 * to `fetch` directly, so the backend contract lives in one place.
 *
 * Nothing here simulates or mocks a response: every function is a direct
 * call to a real endpoint, and errors are surfaced, not swallowed.
 */

export type BackendMove = "rock" | "paper" | "scissors" | "forfeit";
export type Outcome = "win" | "loss" | "draw" | "forfeit";
export type RoundState =
  | "idle"
  | "countdown"
  | "detecting"
  | "locked"
  | "revealing"
  | "result"
  | "game_over";
export type Mode = "" | "best3" | "best5" | "best10" | null;

export interface PlayerStats {
  username: string;
  current_streak: number;
  best_streak: number;
  total_wins: number;
  total_losses: number;
  total_draws: number;
  robot_breaks: number;
  win_rate: number;
  total_rounds: number;
  history: { round: number; player: BackendMove; ai: BackendMove; outcome: Outcome }[];
}

export interface GameStatus {
  state: RoundState;
  round_id: number;
  countdown: number;
  mode: Mode;
  session_wins: number;
  session_losses: number;
  session_draws: number;
  session_round: number;
  target_wins: number;
  player_move?: BackendMove | null;
  ai_move?: BackendMove | null;
  outcome?: Outcome;
  result?: { headline: string; sub: string; color: string };
  stats?: PlayerStats;
}

export interface LeaderboardRow {
  username: string;
  current_streak: number;
  best_streak: number;
  total_wins: number;
  win_rate: number;
  total_rounds: number;
  is_you: boolean;
}

export interface LeaderboardResponse {
  rows: LeaderboardRow[];
  source: "supabase" | "local";
  sort: "streak" | "wins" | "winrate";
  min_rounds_for_winrate: number;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const { json, headers, ...rest } = init ?? {};
  const res = await fetch(path, {
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError((data as { error?: string }).error || res.statusText, res.status);
  }
  return data as T;
}

// ── Player identity ──────────────────────────────────────────────────────

export function claimUsername(username: string, token: string | null) {
  return request<{ ok: true; token: string; stats: PlayerStats; rank: number | null }>(
    "/api/player/claim",
    { method: "POST", json: { username, token } },
  );
}

export function fetchCurrentPlayer() {
  return request<{ player: string | null; stats?: PlayerStats; rank?: number | null }>(
    "/api/player/me",
  );
}

export function resetPlayerStats() {
  return request<{ ok: true; stats: PlayerStats; rank: number | null }>(
    "/api/player/stats/reset",
    { method: "POST" },
  );
}

// ── Leaderboard ───────────────────────────────────────────────────────────

export function fetchLeaderboard(sort: "streak" | "wins" | "winrate" = "streak", search?: string) {
  const params = new URLSearchParams({ sort });
  if (search) params.set("search", search);
  return request<LeaderboardResponse>(`/api/leaderboard?${params.toString()}`);
}

// ── Game ──────────────────────────────────────────────────────────────────

export function startGame(opts: { mode: Mode; newSession: boolean; inputMode: "buttons" | "webcam"; move?: BackendMove }) {
  return request<{ ok: true } | { ok: false; error: string }>("/api/game/start", {
    method: "POST",
    json: {
      mode: opts.mode || null,
      new_session: opts.newSession,
      input_mode: opts.inputMode,
      move: opts.move,
    },
  });
}

export function restartRound(opts: { inputMode: "buttons" | "webcam"; move?: BackendMove }) {
  return request<{ ok: true } | { ok: false; error: string }>("/api/game/restart", {
    method: "POST",
    json: { input_mode: opts.inputMode, move: opts.move },
  });
}

export function fetchGameStatus() {
  return request<GameStatus>("/api/game/status");
}

// ── Webcam gesture (browser-detected; see useCamera.ts) ────────────────────
// The browser does its own on-device detection (Figma's MediaPipe
// tasks-vision recognizer) and pushes the live reading here on every
// detection tick. The backend keeps its own short rolling buffer (see
// src/gesture_buffer.py) and samples ONE stable value from it, at a moment
// of its own choosing, when a round reaches the "locked" phase -- exactly
// the same server-authoritative timing the original webcam mode had, just
// fed from the player's own browser instead of a server-attached camera.
export function pushGesture(gesture: "Closed_Fist" | "Open_Palm" | "Victory" | null) {
  return fetch("/api/camera/gesture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gesture }),
    keepalive: true,
  }).catch(() => {
    /* Best-effort; a dropped push just means this tick isn't counted. */
  });
}

export { ApiError };
