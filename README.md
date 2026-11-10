# AI Rock Paper Scissors — Robot Arena

Play Rock-Paper-Scissors against an animated AI robot using real-time hand
gesture recognition. Features a global online leaderboard, persistent win
streaks, and a robot opponent with 14 distinct emotional states — including
a signature "glass-smash" sequence at 10 consecutive wins.

> **Interface note (carried over from the original build):** PySide6 was
> not available in the environment this project is built/maintained in, so
> the game runs as a local web app (Flask serving a page at
> `http://localhost:5000`) rather than a native desktop window. Everything
> else — webcam capture, MediaPipe hand tracking, game logic, and now the
> identity/leaderboard/robot-personality system — works as described below.

---

## What's new in this upgrade

| Area | What changed |
|---|---|
| **Identity** | Players choose a username (3–16 chars, letters/numbers/underscores) before playing. A secret token is issued and stored in the browser to resume the same identity later — but the **server** decides whether a resume is valid by comparing a hash of that token, not the browser's say-so. |
| **Leaderboard** | Top 10 players worldwide by highest win streak, via Supabase (optional). Falls back to a local-only leaderboard (this machine's players) if Supabase isn't configured — the app always works, online or not. |
| **Stats** | Per-player (not global) now: current streak, personal best, total wins/losses/draws, win rate, global rank, round history, and robot-break count. All server-computed and persisted. |
| **Robot personality** | 14 expressions (idle, thinking, reveal, 3 laugh levels, crying, smug, 5 anger stages, and the 10-win smash) built with CSS — no image assets needed. |
| **10-win achievement** | At exactly a multiple of 10 consecutive wins, the robot goes furious, an achievement toast appears, and a glass-crack overlay animates over both panels — purely visual, never touches the webcam stream. |
| **Robot Lab** | A dev/demo panel to preview every robot expression on demand, with a streak slider and a "hide" toggle — doesn't touch real stats. |
| **Match modes** | Single Round, Best of 3, Best of 5, Best of 10. Match score resets each match; the win streak persists across all of them. |

Everything from the previous build — MediaPipe gesture recognition, the
threaded camera manager, the core Rock/Paper/Scissors rules, and the
`python main.py` startup command — is unchanged.

---

## 1. Installation

```bash
cd ai-rock-paper-scissors
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

New dependency in this upgrade: **`requests`** (for the optional Supabase
sync — a thin, server-only HTTP client; nothing else was added).

## 2. Build the frontend (one-time, or after editing `frontend/`)

The UI is a React app (see `frontend/`) that Flask serves as static files.
It needs to be built once before `python main.py` has anything to serve:

```bash
cd frontend
npm install
npm run build          # outputs into ../static/app
cd ..
```

Requires internet access for `npm install` (not available in every
environment — in particular not in the sandbox this was developed in, so
this build has been hand-written and syntax-checked but not yet compiled;
please run it once and do a visual pass before shipping). For active
frontend development, `npm run dev` inside `frontend/` runs a hot-reloading
dev server on port 5173 that proxies `/api/*` to Flask on port 5000 (run
`python main.py` in another terminal alongside it).

## 3. Running it

```bash
python main.py
```

Open **http://localhost:5000**. The terminal will print whether the
leaderboard is running online (Supabase configured) or local-only.

### Webcam gesture detection now runs in your browser, not on the server

Gesture detection (MediaPipe) runs **client-side**, in whichever browser is
playing — the Flask server never opens a camera device. This matters for
real deployment: the previous version used the server's own local webcam,
which only worked when the "server" and "player" were the same machine. Now
each visitor's own camera is used, and the server only ever receives
already-classified gesture names (e.g. `"Closed_Fist"`), never image data.

## 4. Deploying to a real host (Render, Railway, Fly.io, Heroku, etc.)

`python main.py` runs Flask's development server -- fine for local use, not
meant for real traffic. For an actual deployment:

- Use the included **`Procfile`**, which runs a production WSGI server
  (`gunicorn`) instead: `web: gunicorn -w 2 --threads 4 --timeout 60 -b
  0.0.0.0:$PORT main:app`. Most platforms (Render, Railway, Heroku, Fly.io)
  auto-detect and use a Procfile.
- The app now reads the **`PORT`** environment variable (`main.py`), which
  virtually every PaaS assigns dynamically and routes traffic to. If the
  app binds to a different port than the one the platform expects, its
  edge proxy can never reach the process -- which shows up to visitors as
  a bare **"502 Bad Gateway"** with no application-level error at all.
  This was a real bug caught during development; if you ever see a 502
  with no other detail, this port mismatch (or the process having
  crashed) is the first thing to check.
- `requirements.txt` no longer installs `opencv-python`, `mediapipe`,
  `numpy`, or `Pillow` -- the live app's import graph doesn't touch them
  (verified by walking every module actually reachable from `main.py`;
  they were only ever used by the now-unwired server-side camera code in
  `src/camera.py`/`src/gesture_recognizer.py`). These are large,
  native-dependency-heavy packages that are a common source of build
  failures on minimal PaaS images, so trimming them makes deploys faster
  and more reliable.
- **HTTPS is required** for webcam gesture detection to work at all --
  browsers block camera access on any plain `http://` origin that isn't
  `localhost`. Most PaaS platforms terminate HTTPS for you automatically;
  if you're using your own reverse proxy, make sure it does too.
- If something still doesn't come up, check your platform's own logs for
  the actual error. "Bad Gateway" is reported by whatever sits in front of
  the app (the platform's edge/proxy), not by Flask itself -- the real
  cause (a crash, a failed build, a missing env var) is almost always in
  those logs, not in anything the browser shows you.

---

## 5. Setting up the online leaderboard (optional but recommended)

Without this step, the app still works fully — usernames, stats, and a
leaderboard all function, just scoped to one machine (`data/players.json`).

### 3.1 Create a Supabase project
Go to [supabase.com](https://supabase.com), create a free project, and wait
for it to finish provisioning.

### 3.2 Run the schema
Open **Project → SQL Editor → New query**, paste the contents of
[`sql/schema.sql`](sql/schema.sql), and run it. This creates the
`leaderboard` table with:
- A `UNIQUE` + format `CHECK` constraint on `username` (3–16 chars,
  letters/numbers/underscores) — enforced at the database layer, not just
  in Python.
- Row Level Security **enabled with no public policies at all** — the
  table is completely inaccessible to the anon/public key. Only the
  **service role** key (used exclusively by the Flask server) can read or
  write, because it bypasses RLS by design. The browser never talks to
  Supabase directly, so there's nothing for a malicious client to exploit
  here even in principle.

### 3.3 Get your credentials
In **Project → Settings → API**, copy:
- **Project URL** → `SUPABASE_URL`
- **service_role** secret key → `SUPABASE_SERVICE_ROLE_KEY`

### 3.4 Configure the app
Copy `.env.example` to `.env` and fill in both values:

```bash
cp .env.example .env
# then edit .env
```

`main.py` loads `.env` automatically (a tiny built-in loader — no new
dependency for this). You can also just export them as real environment
variables instead of using a `.env` file.

**⚠️ Never commit `.env` or share the service-role key.** It bypasses Row
Level Security and must only ever be read by the Flask server
(`src/supabase_rest.py`) — it is never sent to the browser in any
response.

---

## 6. How the security requirements are met

- **No service-role key in frontend code**: all Supabase calls happen in
  `src/supabase_rest.py`, imported only by `src/players.py` and
  `src/routes.py` — server-side Python. The browser only ever talks to
  the Flask API (`/api/...`), never to Supabase.
- **Rounds are validated server-side**: `src/game_session.py` computes the
  winner from the camera's actual detected gesture and a server-rolled AI
  move. The browser only *polls* `/api/game/status` for the result — it
  cannot submit a win, loss, or streak value, so there's nothing for a
  malicious client to forge.
- **No arbitrary leaderboard writes from the browser**: the only backend
  function that changes a player's streak/stats is `players.record_round()`,
  called exclusively from the game's own reveal logic — there is no API
  endpoint that accepts a client-supplied score.
- **Duplicate usernames are prevented** both in the Python validation
  layer (`players.validate_username`) and at the database layer (the
  `UNIQUE` constraint + `CHECK` regex in `sql/schema.sql`). A brand-new
  username is checked against Supabase before being claimed, and a true
  simultaneous race from two machines is caught via the resulting 409
  conflict on insert.
- **Players can't hijack another username**: claiming an *existing*
  username requires presenting a token whose hash matches the one stored
  for that username — checked server-side in `players.claim_username()`.
  A new username typed into the browser never overwrites someone else's
  record; it's rejected outright.

**One honest limitation to flag**, given the brief to preserve the
existing architecture: this app has exactly **one shared camera and one
shared game session per running server** (same as before this upgrade) —
it's a local single-player experience, not a multi-tenant server. So
"current player" is tracked per-server-process (`routes.current_player`),
not per-browser-session. That's sufficient for its purpose (one person
playing locally, with results posted to a shared global leaderboard), but
it isn't designed for several people simultaneously playing different
matches against the same running server instance.

---

## 7. Files changed / added

**New:**
- `src/players.py` — username validation, token-based identity, per-player
  persistent stats (local JSON + Supabase sync), win-streak/achievement logic
- `src/supabase_rest.py` — minimal server-only Supabase REST client
- `sql/schema.sql` — leaderboard table schema + RLS lockdown
- `.env.example` — Supabase credential template

**Modified:**
- `src/routes.py` — added `/api/player/*` and `/api/leaderboard` endpoints;
  wired `GameSession.stat_hook` to `players.record_round` so every round's
  outcome (computed server-side, as before) now updates the active
  player's persistent stats and leaderboard entry
- `src/game_session.py` — added a `stat_hook` injection point (replacing
  the old hard-coded call into the single-player JSON stats module); added
  `best3` match mode
- `templates/index.html` — full redesign: username modal, nav with
  Play/Leaderboard tabs, redesigned scoreboard/arena, CSS-based robot
  personality system (14 states), glass-crack achievement overlay, Robot
  Lab preview panel, leaderboard view
- `main.py` — tiny built-in `.env` loader; prints leaderboard mode on startup
- `requirements.txt` — added `requests`

**Removed:**
- `src/statistics.py` and `data/statistics.json` — the single global stats
  file this used is fully superseded by `src/players.py`'s per-player,
  optionally-online stats. The *feature* (persistent stats) is preserved
  and upgraded, not dropped.

**Unchanged:** `src/camera.py`, `src/gesture_recognizer.py`,
`src/model_downloader.py`, `src/game_logic.py`, `src/app.py` — the webcam
pipeline, MediaPipe gesture classification, and core RPS rules are exactly
as before.

---

## 8. Environment variables

| Variable | Required? | Purpose |
|---|---|---|
| `SUPABASE_URL` | No | Enables the online global leaderboard |
| `SUPABASE_SERVICE_ROLE_KEY` | No | Server-side auth for Supabase (never sent to the browser) |

Leave both unset to run fully offline/local.

---

## 9. Testing checklist

**Identity**
- [ ] First visit shows the username modal; background is dimmed/blocked
- [ ] Typing an invalid username (too short, bad characters) shows an inline error and doesn't submit
- [ ] A fresh valid username succeeds, modal closes, nav shows the username + streak chip
- [ ] Refreshing the page resumes the same identity automatically (no modal)
- [ ] Opening the app in a different browser (clear localStorage) and trying the *same* username is rejected as taken
- [ ] Clearing `data/players.json` resets all local identities (for test resets)

**Gameplay (unchanged core, re-verify after upgrade)**
- [ ] Camera starts/stops from both the nav button and the "Enable camera" button in-panel
- [ ] All three gestures (fist/palm/victory) are detected and labeled correctly
- [ ] A round with no recognizable gesture at reveal time forfeits correctly
- [ ] Single Round, Best of 3, Best of 5, and Best of 10 all track match score separately from the overall streak
- [ ] Win streak increases on win, resets on loss/forfeit, is unchanged on draw
- [ ] Starting a new match after finishing one keeps the win streak intact

**Robot personality**
- [ ] Idle robot breathes/blinks while waiting
- [ ] Robot shows "thinking" during the countdown
- [ ] A player win with streak 1 shows **crying**; streak 2/3/5/7/9 show progressively stronger **anger**
- [ ] A player loss/forfeit shows **laughing** (intensity increases on consecutive robot wins)
- [ ] A draw shows **smug**
- [ ] Reaching exactly 10 (and 20, 30…) consecutive wins triggers the achievement toast + glass-crack overlay on both panels, exactly once per occurrence
- [ ] The webcam feed and gesture detection are unaffected during/after the glass-crack animation

**Robot Lab**
- [ ] Clicking any tile previews that state on the real robot panel without changing stats
- [ ] The streak slider maps to the matching anger/crying/smash state
- [ ] Clicking the 10-win tile replays the glass-break preview
- [ ] "Hide lab" / "Show lab" toggles the panel and persists across reloads
- [ ] None of the above affects `data/players.json` or the leaderboard

**Leaderboard**
- [ ] Switching to the Leaderboard tab shows loading → populated/empty state
- [ ] Top 3 rows are visually highlighted; your own row is highlighted if present
- [ ] Search filters by username
- [ ] Refresh re-fetches
- [ ] With Supabase unset: footer note says "local-only"; with it set: says "live from the global database"
- [ ] (With Supabase configured) stats recorded on one machine appear in the leaderboard when checked from another

**Security**
- [ ] No Supabase key appears anywhere in the browser (view source / devtools network tab)
- [ ] `/api/game/start` and `/api/game/restart` refuse to run without a claimed username
- [ ] Attempting to claim a taken username without the right token is rejected (409)

---

## 10. Bug-fix changelog (round-lifecycle & robot-state overhaul)

A later pass fixed several interrelated bugs reported after initial testing.
**The single root cause behind most of them** was in `templates/index.html`:
the "Start/Next round" button had an `addEventListener` bound once at
startup *and* had `.onclick` reassigned after every round — both handlers
fired on every click, silently starting two concurrent rounds that raced
each other inside the one shared backend `GameSession`. That race is what
produced the flickering AI gesture/result panel, the broken round counter,
and the game appearing to skip straight to "Results."

| Bug | Root cause | Fix |
|---|---|---|
| AI gesture/result flickering | The double-handler bug above caused two overlapping polling loops (`setInterval`) to run at once, each independently re-rendering the result panel at different times. | One handler, driven by a single `btnStartIsNewSession` flag (`templates/index.html`). The backend's RESULT/GAME_OVER data is also now keyed to a `round_id` (`src/game_session.py`) and only ever rendered once per id, so even a stray extra poll can't re-trigger rendering. |
| Round counter wrong for Best of 3/5/10 | Same double-handler race: "Next round" sometimes also fired a hidden `new_session` call, which resets `session_round` to 0. The win-condition math itself (`TARGET_WINS` in `src/game_session.py`) was already correct. | Fixed by the same single-handler change. `session_round` now increments exactly once per real completed round (verified with a full automated Best-of-3 match in testing — see below). |
| AI gesture text/emoji mismatch | `templates/index.html` set the robot's label from `ai_move` but its chest-icon emoji from `player_move` — two different variables for what should've been one value. | Added one `GESTURES` lookup object (`templates/index.html`) used everywhere a gesture needs a name, emoji, or hint — the robot label, chest icon, gesture chip, and round history all read from it. |
| State sequence jumped Ready → Results | The backend (`src/game_session.py`) never had Detecting/Locked/Revealing states — the frontend faked a single quick flash instead. | Rebuilt `GameSession` as a real state machine: `idle → countdown → detecting → locked → revealing → result` (or `game_over`). Each phase has genuine duration and is the backend's own authoritative state; the frontend (`templates/index.html`) now purely renders whatever phase `/api/game/status` reports, with no client-side faking. |
| Robot emotions unreliable | Depended on the same double-handler race, plus a fragile dedupe check (`stats.total_rounds`) that silently did nothing if player stats were ever unavailable. | Fixed by the single-handler change plus the new backend `round_id`, which is always present regardless of player state and is now the one thing that decides whether a round's reaction has already played. |
| Robot Lab visible during normal play | It was a `<div>` at the bottom of the main gameplay page, just hidden/shown by a toggle button. | Moved entirely to its own route, `/robot-lab` (`templates/robot_lab.html`, `src/routes.py`), which is not linked from gameplay navigation and makes zero calls to any `/api/game/*` or `/api/player/*` endpoint — previewing an expression there cannot touch a real match, real stats, or the leaderboard. |
| Duplicate updates / animation restarts | Same root causes as above. | The backend's `round_id` is now the single authoritative "has this round been handled yet" signal everywhere in the frontend; `start_round()` also refuses to begin a new round while one is already in progress (`_IN_PROGRESS` check in `src/game_session.py`), as defense in depth independent of the frontend fix. |

### Files changed
- `src/game_session.py` — rewritten as a real 6-phase state machine with a `round_id`, replacing the previous 4-state version
- `src/routes.py` — added the `/robot-lab` route
- `templates/index.html` — single Start/Next button handler; centralized `GESTURES` map; state-machine-driven rendering (`handleStatus`/`showRoundResult`) replacing the old timer-based `animateReveal`; Robot Lab section and its JS removed
- `templates/robot_lab.html` — new standalone developer preview page (moved out of `index.html`)

### One timing change worth knowing
Each round now genuinely takes a bit longer than before: the 3-second
countdown is followed by real Detecting (0.6s), Locked (0.35s), and
Revealing (0.35s) phases — about 4.3 seconds total before the result
appears, instead of the previous ~3 seconds. This is a direct, necessary
consequence of making those phases real rather than instantaneous.

### What was tested and how
All of the following were run against the real Flask app (via its test
client and, separately, a live `python main.py` server) — not just read
through:
- The full state sequence (`idle → countdown → detecting → locked →
  revealing → result`) was captured by polling `/api/game/status` every
  100–150ms, exactly as the browser does, and asserted to match that exact
  order with no skips, both at the Python object level and over real HTTP.
- Repeated polling (20 requests over 3 seconds) against a completed round
  was asserted to return byte-for-byte identical data every time — zero
  flicker.
- A full Best-of-3 match was played end-to-end against the real timers;
  `session_round` was asserted to match the actual number of completed
  rounds after every round, and the match was confirmed to end exactly at
  a 2-win majority.
- The majority thresholds for Best of 3/5/10 (2, 3, 6) were asserted directly.
- All three gestures (Closed_Fist/Open_Palm/Victory → rock/paper/scissors)
  were driven through the real camera-gesture pipeline and confirmed to
  produce the correct canonical move end-to-end over HTTP.
- The 10-consecutive-win achievement was driven to exactly 10 and confirmed
  present (`achievement: "robot_break"`) in the real HTTP response for
  that round, and absent on the 9th and 11th.
- A duplicate `start_round()` call while a round is already in progress was
  confirmed to be a no-op (`round_id` unchanged).
- The main page was confirmed to contain no Robot Lab markup; `/robot-lab`
  was confirmed to load independently and to contain no calls to any
  game-mutating endpoint.

### What I could not verify
I don't have a browser or a physical webcam in this environment, so I
could not visually confirm the animations, click through the UI myself, or
test real MediaPipe hand detection end-to-end. Everything above was
verified at the HTTP/data level — please click through a real round (one
win, one loss, one draw) and watch the robot/stepper/result panel yourselves
to confirm the visual side matches.

---

## 11. Fairness audit, leaderboard completion, and branding refresh

### 9.1 AI fairness — already correct, now provably so

I inspected `src/game_logic.py` and `src/game_session.py` closely and made
**no changes to the AI logic itself** — it already satisfied every
requirement:
- `ai_choose()` takes zero parameters and uses `random.choice()` over
  exactly the three moves — structurally incapable of seeing the player's
  gesture (it has no way to receive it), and uniformly random.
- In `GameSession._run_round()`, the AI's move is chosen and locked at the
  very start of the round — before the 3-second countdown, before the
  Detecting phase, and therefore long before the player's gesture is ever
  read from the camera.
- The AI's move is never reassigned after that point; both moves are only
  ever exposed to the frontend together, at RESULT.
- Win/loss/draw determination (`determine_winner`) is the textbook rule set.

New: `tests/test_ai_fairness.py` (8 tests, all passing) proves this with:
uniform-distribution sampling over 30,000 trials, a direct signature check
that `ai_choose()` accepts no arguments, a real-round test that records the
AI's move before the camera is ever consulted and confirms it never
changes afterward (tried against all three gestures and a forfeit), and an
exhaustive check of all 9 possible outcome combinations.

### 9.2 Global leaderboard — what's genuinely done vs. what needs your Supabase project

**Already correct before this pass** (reviewed, not rewritten): identity/
auth via per-username tokens, server-side-only outcome computation (the
browser cannot submit a score), the RLS-locked schema with zero public
policies, and the fact that syncing a player's row to Supabase pushes
their *absolute* current totals rather than an increment — which makes a
duplicate/retried sync a no-op rather than a double-count (see
`tests/test_leaderboard.py::TestRoundsAreNeverDoubleCounted`).

**What was missing and is now implemented:** you asked for three
leaderboard categories — only "highest streak" existed before. Added:
- **All-Time Wins** and **Win Rate** as full additional sort categories,
  alongside the existing **Win Streak**, in `src/supabase_rest.py`,
  `src/players.py` (identical logic for the local fallback), and
  `src/routes.py` (`/api/leaderboard?sort=streak|wins|winrate`).
- Win Rate requires **at least 10 completed rounds** to qualify
  (`players.MIN_ROUNDS_FOR_WIN_RATE`), so a single lucky game can't sit at
  the top — enforced identically on both the Supabase path and the local
  fallback.
- `sql/schema.sql` now has `total_rounds` and `win_rate` as Postgres
  **generated (computed, stored) columns**, so PostgREST can sort by them
  directly with no extra app-side computation and no risk of the computed
  value drifting from its inputs. A migration block is included for
  databases that already ran the old schema.
- The Leaderboard page now has three tabs to switch between categories,
  with a note explaining the win-rate qualifier and an empty state for
  "no one has played 10+ rounds yet."

**Honesty check, as requested — tested locally vs. verified online:**

| Claim | Status |
|---|---|
| Local JSON persistence, identity resume across refreshes, server-authoritative stats | ✅ Tested here, against the real app |
| Supabase integration code sends well-formed requests and parses responses correctly | ✅ Tested here, but **only against a mocked HTTP layer** (`unittest.mock`) — see `TestSupabaseRequestsAreWellFormed` |
| RLS policy actually blocks the anon key on a live project | ❌ **Not verified.** I reviewed the SQL; I cannot execute it against a real Supabase project from here |
| Two real devices/machines seeing each other's data via a real Supabase project | ❌ **Not verified.** This environment has no Supabase credentials |
| "Online" vs "local" leaderboard mode actually switching correctly at runtime | ✅ Tested here — confirmed it reports `"source": "local"` with no credentials set; the online code path itself is exercised only via mocks, not a live project |

**What you need to do to make it genuinely global:**
1. Create a Supabase project (if you haven't already).
2. Run `sql/schema.sql` in the SQL Editor — or, if you already created the
   table before this update, run just the migration block near the bottom
   of that file (adds `total_rounds`/`win_rate` and their indexes).
3. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (Project → Settings →
   API → service_role secret) as environment variables, or in a `.env`
   file copied from `.env.example`.
4. Restart `python main.py` — the terminal banner will say "Leaderboard:
   ONLINE (Supabase)" once it's picked up.
5. To actually confirm it's global: play a few rounds, check the row
   appears in your Supabase table editor, then run this same app on a
   second computer with the *same* two environment variables set and
   confirm its leaderboard shows the first machine's player. One nuance
   worth knowing: because this app has one shared camera/session per
   running server (unchanged from before), two people can't play a live
   match against each other through one server — but two *separate*
   running instances of this app, pointed at the same Supabase project,
   will correctly share one global leaderboard and one pool of player
   stats, which is what "global leaderboard" means here.

### 9.3 Top branding

Replaced the "🤖 Rock Paper Scissors" plain emoji+text with a small flat
monogram badge ("RPS", solid accent color, no gradient or glow) plus a
two-line title/kicker lockup ("Rock Paper Scissors" / "ARENA"), on both the
main page and the Robot Lab page, with a mobile breakpoint that drops the
kicker and shrinks the mark. **Nothing about the robot character — its CSS
classes, all 13 expression states, or the Robot Lab previews — was
touched**; confirmed by diffing the exact set of `.state-*` CSS selectors
before and after (unchanged) and by checking the robot's actual DOM markup
is still present and unmodified.

### 9.4 Test summary

```
python3 -m unittest discover tests -v
```
23 tests, all passing (8 AI-fairness, 15 leaderboard). Also re-ran: Flask
app boot via `python main.py`, homepage/`/robot-lab`/`/api/leaderboard`
(all three sort modes) over real HTTP, CSS brace balance and JS syntax
checks on both templates, and a cross-check that every DOM id referenced
in JS actually exists in the HTML.

### 9.5 What still needs manual/browser/webcam testing
- Visual confirmation of the new branding on an actual phone-sized viewport
  (I checked the CSS breakpoint logic but can't render a browser here).
- Clicking through a real game: webcam gesture detection, the countdown/
  reveal sequence, and the Robot Lab's preview tiles, end-to-end in a
  real browser.
- Everything under "online vs. tested-locally" in the table above, once
  you've configured a real Supabase project.

---

## 12. Full UI redesign (rps.club visual identity)

### What changed
`templates/index.html` was rebuilt to match the three design references:
sidebar navigation (The Arena / Leaderboard / Robot Lab, the 10-win
challenge card, How to Play, player identity), a top bar with a status
pill/theme/sound/help, a large "Outsmart the machine." hero, the two-panel
arena (dark forest-green AI panel, light sage human panel), the
Buttons/Webcam input toggle, the Ready-to-play stepper card, and the
stats/history cards — all restyled in the new off-white/sage/lime palette
with a complete, persisted dark mode.

### What is genuinely new (not just reskinned)
**Buttons mode is a real, new input path** — previously the only way to
play was the webcam. Clicking Rock/Paper/Scissors (or pressing `1`/`2`/`3`
then `space`) now submits a real move to the backend. This needed one
small, additive backend change: `src/routes.py` now translates a button
move to the same MediaPipe class name the camera pipeline already
produces (`rock→Closed_Fist`, etc.), so `src/game_session.py` and
`src/game_logic.py` — the actual state machine, AI fairness logic, and
scoring — needed **zero changes** and handle both input methods
identically. Buttons mode doesn't require the camera at all.

### What was deliberately preserved untouched
- `src/game_session.py`, `src/game_logic.py`, `src/camera.py`,
  `src/gesture_recognizer.py`, `src/players.py`, `src/supabase_rest.py` —
  no changes.
- The robot character: I copied its exact CSS block (all 13 expression
  states) and DOM structure verbatim into the new page and re-verified the
  selector set is byte-identical to before. Its accent color now reads as
  lime-green instead of blue-purple purely because it's driven by the same
  `--accent-lt` CSS variable as the rest of the new theme — which matches
  the reference screenshots (the robot has lime eyes there too) — but no
  animation, expression, or piece of logic was touched.
- `templates/robot_lab.html` and its preview tiles/animation system —
  completely untouched.
- Every existing API contract, the six-stage state machine, identity/
  leaderboard/stats wiring, and the glass-break achievement — all reused
  via the same function names and endpoints as before.

### Files modified
- `src/routes.py` — added Buttons-mode move handling (additive only)
- `templates/index.html` — full redesign (structure + style only; same
  backend calls, same function names, same element IDs for everything
  that existed before)

### Tests run
- All 23 pre-existing automated tests still pass unchanged
  (`python3 -m unittest discover tests -v`) — the AI-fairness and
  leaderboard logic they check was not touched by this redesign.
- New: an end-to-end Buttons-mode round through the real Flask app and
  the real timed state machine (not mocked), confirming the full
  countdown → detecting → locked → revealing → result sequence and a
  correct outcome with no camera running at all.
- CSS brace-balance check, JS syntax check (`node --check`) on both the
  pre-paint theme script and the main application script, and a
  cross-check that every DOM id referenced in JS exists in the HTML —
  all clean.
- A live `python main.py` boot, confirming `/`, `/robot-lab`, and
  `/api/leaderboard` all respond correctly together.
- Confirmed the robot's CSS selector set is unchanged (still exactly the
  13 expression states).

### What still needs manual/browser testing
I have no browser here, so the following need your eyes:
- Visual accuracy against the three screenshots, especially spacing,
  proportions, and the panel contrast on an actual display.
- Dark mode toggling and persistence after a real page refresh (the logic
  is in place — theme is read before paint and saved to `localStorage` —
  but I couldn't visually confirm it, or check for any remaining
  light/dark contrast issue in a component I missed).
- The sidebar's mobile collapse behavior and tapping the hamburger toggle
  on an actual small viewport.
- Keyboard shortcuts (`1`/`2`/`3`/`space`) in a real browser, including that
  they don't fire while typing in the username or leaderboard search box.
- Switching Buttons ↔ Webcam mid-session without disrupting an in-progress
  match, and real webcam gesture detection end-to-end.
- Sound toggle — it only persists a preference flag; no sound effects
  exist to wire up yet (none existed before this change either).
