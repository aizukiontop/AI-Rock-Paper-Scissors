-- AI Rock Paper Scissors — global leaderboard schema
--
-- Run this once in your Supabase project's SQL editor (Project > SQL Editor > New query).
--
-- Design notes:
--   * This table is written to ONLY by the Flask backend using the
--     SERVICE ROLE key (never exposed to the browser). The frontend never
--     talks to Supabase directly, so Row Level Security is enabled with
--     NO public policies at all — anon/authenticated clients get zero
--     access, and the service role bypasses RLS entirely. This is the
--     simplest way to guarantee "never let the browser submit arbitrary
--     scores" at the database layer, not just in application code.
--   * Usernames are validated both in Python (players.py) and again here
--     with a CHECK constraint, and the UNIQUE constraint is what the
--     insert-race-handling in supabase_rest.py / players.py relies on.

create table if not exists public.leaderboard (
  id             uuid primary key default gen_random_uuid(),
  username       text not null unique check (
                   char_length(username) between 3 and 16
                   and username ~ '^[A-Za-z0-9_]+$'
                 ),
  current_streak integer not null default 0 check (current_streak >= 0),
  best_streak    integer not null default 0 check (best_streak >= 0),
  total_wins     integer not null default 0 check (total_wins >= 0),
  total_losses   integer not null default 0 check (total_losses >= 0),
  total_draws    integer not null default 0 check (total_draws >= 0),
  robot_breaks   integer not null default 0 check (robot_breaks >= 0),
  -- Generated (computed, stored) columns so the three leaderboard
  -- categories -- streak, total wins, win rate -- can all be sorted
  -- directly by PostgREST with a plain `order=` query, with no app-side
  -- computation and no risk of the stored value drifting out of sync with
  -- its inputs (Postgres recomputes it automatically on every write).
  total_rounds   integer generated always as (total_wins + total_losses + total_draws) stored,
  win_rate       numeric generated always as (
                   case when (total_wins + total_losses + total_draws) = 0 then 0
                        else round((total_wins::numeric / (total_wins + total_losses + total_draws)) * 100, 1)
                   end
                 ) stored,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- One index per leaderboard category this app offers (Win Streak, Total
-- Wins, Win Rate), so "top 10 by X" is fast for all three, not just streak.
create index if not exists leaderboard_best_streak_idx on public.leaderboard (best_streak desc);
create index if not exists leaderboard_total_wins_idx  on public.leaderboard (total_wins desc);
create index if not exists leaderboard_win_rate_idx    on public.leaderboard (win_rate desc) where total_rounds > 0;

create index if not exists leaderboard_username_lower_idx
  on public.leaderboard (lower(username));

-- ─────────────────────────────────────────────────────────────────────
-- MIGRATION: if you already created this table before total_rounds/
-- win_rate existed, run just this block (it's safe to re-run; it does
-- nothing if the columns are already there):
--
--   alter table public.leaderboard
--     add column if not exists total_rounds integer generated always as
--       (total_wins + total_losses + total_draws) stored;
--   alter table public.leaderboard
--     add column if not exists win_rate numeric generated always as (
--       case when (total_wins + total_losses + total_draws) = 0 then 0
--            else round((total_wins::numeric / (total_wins + total_losses + total_draws)) * 100, 1)
--       end
--     ) stored;
--   create index if not exists leaderboard_total_wins_idx on public.leaderboard (total_wins desc);
--   create index if not exists leaderboard_win_rate_idx   on public.leaderboard (win_rate desc) where total_rounds > 0;
-- ─────────────────────────────────────────────────────────────────────

-- Lock the table down completely from the browser. Only the service-role
-- key (used exclusively by the Flask server) can read or write — it
-- bypasses RLS by design, so no policy is needed for the backend to work.
alter table public.leaderboard enable row level security;
-- Intentionally no CREATE POLICY statements: default-deny for anon/authenticated.
