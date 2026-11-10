import { useEffect, useRef, useState } from "react";
import { Hand, Icon, Robot, type Move } from "./components";
import { moves } from "./game";
import { useCamera } from "./useCamera";
import IdentityGate, { loadStoredIdentity, clearStoredIdentity } from "./IdentityGate";
import { applyTheme, getStoredTheme, type Theme } from "./theme";
import {
  startGame,
  fetchGameStatus,
  claimUsername,
  resetPlayerStats,
  fetchLeaderboard,
  ApiError,
  type GameStatus,
  type PlayerStats,
  type LeaderboardRow,
  type Mode,
  type BackendMove,
} from "./api";

type Page = "arena" | "leaderboard" | "lab";
const colors = ["#d7f75b", "#bcb0ee", "#ffb38a", "#86d4cd"];
const MODE_LABEL: Record<string, string> = {
  "": "Single Round",
  best3: "Best of 3",
  best5: "Best of 5",
  best10: "Best of 10",
};
const TO_BACKEND_MOVE: Record<Move, BackendMove> = {
  Rock: "rock",
  Paper: "paper",
  Scissors: "scissors",
};
const FROM_BACKEND_MOVE: Record<string, Move | undefined> = {
  rock: "Rock",
  paper: "Paper",
  scissors: "Scissors",
};
const IDLE_STATUS: GameStatus = {
  state: "idle",
  round_id: 0,
  countdown: 0,
  mode: "",
  session_wins: 0,
  session_losses: 0,
  session_draws: 0,
  session_round: 0,
  target_wins: 0,
};
const ROBOT_PREFS_KEY = "rps_robot_prefs";

function loadRobotPrefs() {
  try {
    const raw = localStorage.getItem(ROBOT_PREFS_KEY);
    if (raw) return JSON.parse(raw) as { color: string; accessory: string };
  } catch {
    /* ignore */
  }
  return { color: colors[0], accessory: "antenna" };
}

export default function App() {
  // ── Identity ──────────────────────────────────────────────────────────
  const [identityState, setIdentityState] = useState<"checking" | "gate" | "ready">("checking");
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [rank, setRank] = useState<number | null>(null);
  const [username, setUsername] = useState("");

  useEffect(() => {
    (async () => {
      const stored = loadStoredIdentity();
      if (!stored) {
        setIdentityState("gate");
        return;
      }
      // This server keeps one shared "current player" in memory (see
      // routes.py), which only happens to already be this browser's
      // identity if nobody else has played since this browser last did.
      // So don't rely on that -- resume directly with the saved
      // username+token, the same call IdentityGate itself would make.
      setUsername(stored.username);
      try {
        const res = await claimUsername(stored.username, stored.token);
        setStats(res.stats);
        setRank(res.rank);
        setIdentityState("ready");
      } catch {
        // Token no longer valid (e.g. local data was cleared server-side)
        // -- fall back to the gate, pre-filled with the saved username so
        // the player can see what happened and pick a name.
        setIdentityState("gate");
      }
    })();
  }, []);

  function handleIdentityReady(newStats: PlayerStats) {
    setUsername(newStats.username);
    setStats(newStats);
    setIdentityState("ready");
  }

  function signOut() {
    clearStoredIdentity();
    setStats(null);
    setUsername("");
    setIdentityState("gate");
  }

  // ── Page / chrome ────────────────────────────────────────────────────
  const [page, setPage] = useState<Page>("arena");
  const [help, setHelp] = useState(false);
  const [sound, setSound] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => getStoredTheme());
  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
  }
  const [input, setInput] = useState<"buttons" | "camera">("buttons");
  const [selected, setSelected] = useState<Move | null>(null);
  const [roundError, setRoundError] = useState("");
  const [bestOf, setBestOf] = useState<Mode>("best3");
  const [freshMatch, setFreshMatch] = useState(true);
  const [status, setStatus] = useState<GameStatus>(IDLE_STATUS);
  const busy =
    status.state === "countdown" ||
    status.state === "detecting" ||
    status.state === "locked" ||
    status.state === "revealing";
  const busyRef = useRef(false);
  const camera = useCamera();
  const audio = useRef<AudioContext | null>(null);
  const prefs = useRef(loadRobotPrefs());
  const [color, setColor] = useState(prefs.current.color);
  const [accessory, setAccessory] = useState(prefs.current.accessory);
  const [previewMood, setPreviewMood] = useState("idle");

  useEffect(() => {
    localStorage.setItem(ROBOT_PREFS_KEY, JSON.stringify({ color, accessory }));
  }, [color, accessory]);

  const matchOver = status.state === "game_over";
  const target = status.target_wins || 1;
  const scores = freshMatch
    ? { player: 0, robot: 0 }
    : { player: status.session_wins, robot: status.session_losses };
  const lastPlayerMove =
    status.player_move && status.player_move !== "forfeit"
      ? FROM_BACKEND_MOVE[status.player_move]
      : null;
  const lastAiMove = status.ai_move ? FROM_BACKEND_MOVE[status.ai_move] : null;
  const hasResult = status.state === "result" || status.state === "game_over";
  const mood =
    status.state === "countdown" || status.state === "detecting" || status.state === "locked"
      ? "thinking"
      : hasResult
        ? status.outcome === "win"
          ? "sad"
          : status.outcome === "loss" || status.outcome === "forfeit"
            ? "happy"
            : "thinking"
        : "idle";

  function beep(freq = 440, duration = 0.08) {
    if (!sound) return;
    try {
      audio.current ??= new AudioContext();
      void audio.current.resume();
      const oscillator = audio.current.createOscillator();
      const gain = audio.current.createGain();
      oscillator.connect(gain);
      gain.connect(audio.current.destination);
      oscillator.frequency.value = freq;
      gain.gain.setValueAtTime(0.045, audio.current.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audio.current.currentTime + duration);
      oscillator.start();
      oscillator.stop(audio.current.currentTime + duration);
    } catch {
      /* Audio is optional when unavailable in the browser. */
    }
  }

  // ── Server-driven round polling ─────────────────────────────────────
  // The backend owns the entire round timeline (countdown -> detecting ->
  // locked -> revealing -> result), including exactly when the player's
  // gesture is read -- this just mirrors whatever it reports, rather than
  // simulating timing locally.
  const prevStateRef = useRef<string>("idle");
  const prevCountRef = useRef<number>(0);
  useEffect(() => {
    if (page !== "arena" || identityState !== "ready") return;
    let alive = true;
    const tick = async () => {
      try {
        const next = await fetchGameStatus();
        if (!alive) return;
        if (next.countdown !== prevCountRef.current && (next.state === "countdown")) {
          beep(340 + (3 - next.countdown) * 90);
        }
        if (next.state === "locked" && prevStateRef.current !== "locked") beep(600);
        if (
          (next.state === "result" || next.state === "game_over") &&
          prevStateRef.current !== "result" &&
          prevStateRef.current !== "game_over"
        ) {
          beep(next.outcome === "win" ? 880 : next.outcome === "loss" ? 220 : 440, 0.2);
          if (next.stats) {
            setStats(next.stats);
            setRank((r) => r); // rank refreshed lazily on leaderboard view
          }
          busyRef.current = false;
        }
        prevStateRef.current = next.state;
        prevCountRef.current = next.countdown;
        setStatus(next);
      } catch {
        /* a dropped poll just retries on the next tick */
      }
    };
    void tick();
    const id = setInterval(tick, 250);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [page, identityState, sound]);

  useEffect(() => {
    return () => void audio.current?.close();
  }, []);

  async function play() {
    if (
      busyRef.current ||
      busy ||
      (input === "buttons" && !selected) ||
      (input === "camera" && (!camera.enabled || camera.loading))
    )
      return;
    busyRef.current = true;
    setRoundError("");
    const newSession = freshMatch || matchOver;
    try {
      const res = await startGame({
        mode: bestOf,
        newSession,
        inputMode: input === "camera" ? "webcam" : "buttons",
        move: input === "buttons" && selected ? TO_BACKEND_MOVE[selected] : undefined,
      });
      if (!res.ok) {
        setRoundError(res.error);
        busyRef.current = false;
        return;
      }
      setFreshMatch(false);
      beep(340);
    } catch (err) {
      setRoundError(
        err instanceof ApiError ? err.message : "Couldn't reach the server. Try again.",
      );
      busyRef.current = false;
    }
  }
  const playRef = useRef(play);
  playRef.current = play;

  useEffect(() => {
    const keydown = (e: KeyboardEvent) => {
      if (
        help ||
        page !== "arena" ||
        /INPUT|SELECT|BUTTON|TEXTAREA/.test((e.target as HTMLElement).tagName)
      )
        return;
      const move = ({ "1": "Rock", "2": "Paper", "3": "Scissors" } as Record<string, Move>)[e.key];
      if (move && !busyRef.current) {
        setInput("buttons");
        setSelected(move);
      }
      if (e.code === "Space") {
        e.preventDefault();
        void playRef.current();
      }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [help, page]);

  useEffect(() => {
    if (page !== "arena") {
      camera.stop();
      setInput("buttons");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  function resetMatch() {
    if (busy) return;
    setFreshMatch(true);
  }

  const title =
    status.state === "countdown" || status.state === "detecting"
      ? "Rock. Paper. Scissors."
      : status.state === "locked"
        ? "Moves locked in."
        : status.state === "revealing"
          ? "The moment of truth…"
          : hasResult
            ? matchOver
              ? status.session_wins >= target
                ? "Match won. Nicely played."
                : "Rookie takes the match."
              : status.outcome === "win"
                ? "Human intuition: 1. AI: 0."
                : status.outcome === "loss"
                  ? "Rookie got you this time."
                  : status.outcome === "forfeit"
                    ? "No gesture detected."
                    : "Great minds think alike."
            : "Your move, human.";
  const description = hasResult
    ? status.outcome === "forfeit"
      ? "No clear gesture was seen in time — no points lost. Try again, and hold your hand steady until the countdown ends."
      : `${lastPlayerMove ?? "Your move"} ${status.outcome === "draw" ? "meets" : status.outcome === "win" ? "beats" : "loses to"} ${(lastAiMove ?? "").toLowerCase()}. ${matchOver ? "Ready for a rematch?" : status.outcome === "draw" ? "A tie. Go again — no points lost." : "Pick your next move and keep it going."}`
    : input === "camera"
      ? "Show a fist, an open palm, or a victory sign when the countdown ends."
      : "Pick your move below. A little instinct goes a long way.";

  if (identityState !== "ready") {
    return (
      <>
        <div className="app-shell" aria-hidden="true" />
        {identityState === "gate" && (
          <IdentityGate initialUsername={username} onReady={handleIdentityReady} />
        )}
      </>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#arena"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            if (!busy) setPage("arena");
          }}
          aria-label="RPS Club home"
        >
          <span className="brand-symbol">
            <Hand move="Scissors" size={30} />
          </span>
          <span>
            rps<span className="brand-dot">.</span>club<small>HUMANS WELCOME.</small>
          </span>
        </a>
        <div className="nav-label">THE PLAYGROUND</div>
        <nav aria-label="Main navigation">
          {(["arena", "leaderboard", "lab"] as Page[]).map((p) => (
            <button
              key={p}
              className={`nav-item ${page === p ? "active" : ""}`}
              disabled={busy}
              onClick={() => setPage(p)}
            >
              <Icon name={p === "arena" ? "arena" : p === "lab" ? "robot" : "trophy"} />
              <span>{p === "arena" ? "The Arena" : p === "lab" ? "Robot Lab" : "Leaderboard"}</span>
              {page === p && <span className="nav-dot" />}
              {p === "lab" && <span className="tiny-tag">LAB</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="challenge-note">
            <span className="note-star">✳</span>
            <span>
              Built different?
              <br />
              <strong>Prove it.</strong>
            </span>
            <p>
              Win 10 rounds in a row.
              <br />
              Break the robot.
            </p>
            <div className="note-progress">
              <i style={{ width: `${Math.min((stats?.current_streak ?? 0) / 10, 1) * 100}%` }} />
            </div>
            <div className="note-footer">
              <span>THE 10-WIN CHALLENGE</span>
              <span>{stats?.current_streak ?? 0}/10</span>
            </div>
          </div>
          <button className="how-link" onClick={() => setHelp(true)}>
            <Icon name="help" size={18} /> How to play <Icon name="diagonal" size={15} />
          </button>
          <button
            className="profile"
            onClick={signOut}
            title="Not you? Click to switch accounts"
            style={{ cursor: "pointer", border: "none", width: "100%", textAlign: "left" }}
          >
            <span className="avatar">{username.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{username}</strong>
              <small>Challenger, not a bot.</small>
            </div>
            <span className="online-dot" />
          </button>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Playground <span>/</span>{" "}
            <strong>
              {page === "arena" ? "The Arena" : page === "lab" ? "Robot Lab" : "Leaderboard"}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="live-label">
              <i /> ALL SYSTEMS PLAY
            </span>
            <span className="topbar-divider" />
            <button
              className="icon-button"
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              onClick={toggleTheme}
            >
              <Icon name={theme === "dark" ? "sun" : "moon"} size={19} />
            </button>
            <button
              className="icon-button"
              aria-label={sound ? "Mute sound" : "Enable sound"}
              onClick={() => setSound((s) => !s)}
            >
              <Icon name={sound ? "sound" : "mute"} size={19} />
            </button>
            <button className="icon-button" aria-label="How to play" onClick={() => setHelp(true)}>
              <Icon name="help" size={19} />
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span /> HUMAN INSTINCT. ARTIFICIAL CONFIDENCE.
              </div>
              <h1>
                {page === "arena" ? (
                  <>
                    Outsmart the <span>machine.</span>
                  </>
                ) : page === "lab" ? (
                  <>
                    A little more <span>personality.</span>
                  </>
                ) : (
                  <>
                    Big streaks. <span>Bragging rights.</span>
                  </>
                )}
              </h1>
              <p>
                {page === "arena"
                  ? "Three moves. One rival. Think you've got the upper hand?"
                  : page === "lab"
                    ? "Meet your rival. Then make it your own."
                    : "Every legend starts with a winning streak."}
              </p>
            </div>
            <div className="heading-tag">
              <span className="heading-tag-icon">
                <Icon name={page === "lab" ? "robot" : "bolt"} size={17} />
              </span>
              {page === "lab" ? "ROOKIE WORKSHOP" : "HUMAN vs. AI"}
            </div>
          </div>

          {page === "arena" && (
            <>
              <section className="arena" aria-label="Game arena">
                <div className="arena-toolbar">
                  <div className="arena-label">
                    <span className="live-dot" /> THE ARENA <span className="toolbar-line" />
                    <span className="round-label">
                      ROUND {matchOver ? status.session_round : status.session_round + 1}
                    </span>
                  </div>
                  <div className="match-options">
                    <label>
                      <select
                        aria-label="Match format"
                        value={bestOf ?? ""}
                        disabled={busy}
                        onChange={(e) => {
                          setBestOf(e.target.value as Mode);
                          resetMatch();
                        }}
                      >
                        {Object.entries(MODE_LABEL).map(([v, label]) => (
                          <option key={v} value={v}>
                            {label}
                          </option>
                        ))}
                      </select>
                      <Icon name="chevron" size={14} />
                    </label>
                    <button
                      className="icon-button"
                      onClick={resetMatch}
                      disabled={busy}
                      aria-label="Reset current match"
                      title="Reset match"
                    >
                      <Icon name="reset" size={16} />
                    </button>
                  </div>
                </div>
                <div className="combatants">
                  <div className="robot-panel">
                    <div className="player-panel-heading">
                      <div>
                        <span className="opponent-icon">
                          <Icon name="robot" size={16} />
                        </span>
                        <strong>Rookie</strong>
                        <span className="ai-tag">AI OPPONENT</span>
                      </div>
                      <span className="score">
                        {scores.robot}
                        <span> / {target}</span>
                      </span>
                    </div>
                    <div className="robot-stage">
                      <div className="orbit orbit-one" />
                      <div className="orbit orbit-two" />
                      <div className="crosshair crosshair-one">+</div>
                      <div className="crosshair crosshair-two">+</div>
                      <div className="robot-speech">
                        {status.state === "countdown" || status.state === "detecting"
                          ? "Calculating your downfall…"
                          : hasResult
                            ? status.outcome === "win"
                              ? "That was… statistically unlikely."
                              : status.outcome === "loss"
                                ? "All part of my programming."
                                : status.outcome === "forfeit"
                                  ? "I'll take the free win."
                                  : "Did we just become best friends?"
                            : "I've got a good feeling about this."}
                      </div>
                      <Robot mood={mood} color={color} accessory={accessory} />
                      {hasResult && lastAiMove && (
                        <div className="robot-move">
                          <Hand move={lastAiMove} size={25} />
                          <span>{lastAiMove}</span>
                        </div>
                      )}
                    </div>
                    <div className="panel-footer">
                      <span>
                        <i className="status-dot" />
                        {busy ? "Thinking very hard" : "Ready to rumble"}
                      </span>
                      <div className="score-pips">
                        {Array.from({ length: target }, (_, i) => (
                          <i key={i} className={i < scores.robot ? "filled" : ""} />
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="versus">
                    <span>VS</span>
                  </div>
                  <div
                    className={`human-panel ${input === "camera" && camera.enabled ? "camera-active" : ""}`}
                  >
                    <div className="player-panel-heading">
                      <div>
                        <span className="human-icon">{username.slice(0, 1).toUpperCase()}</span>
                        <strong>You</strong>
                        <span className="you-tag">THE HUMAN</span>
                      </div>
                      <span className="score">
                        {scores.player}
                        <span> / {target}</span>
                      </span>
                    </div>
                    <div className="human-stage">
                      {input === "camera" && camera.enabled ? (
                        <>
                          <video
                            ref={camera.videoRef}
                            autoPlay
                            muted
                            playsInline
                            className="camera-video"
                          />
                          <div className="camera-reticle" />
                          <span className="gesture-badge">
                            {camera.loading
                              ? "Loading gesture detection…"
                              : camera.gesture
                                ? `${camera.gesture} detected`
                                : "Show your hand"}
                          </span>
                        </>
                      ) : (
                        <>
                          <div className="hand-disc">
                            <Hand move={selected || "Scissors"} size={110} />
                          </div>
                          <span className="hand-orbit-label">100% HUMAN. PROBABLY.</span>
                        </>
                      )}
                      {(status.state === "countdown" || status.state === "detecting") && (
                        <div className="countdown-overlay" key={status.countdown}>
                          <span>{status.countdown || 1}</span>
                        </div>
                      )}
                      {status.state === "locked" && (
                        <div className="locked-overlay">
                          <Icon name="check" size={32} />
                          <span>LOCKED IN</span>
                        </div>
                      )}
                    </div>
                    <div className="panel-footer">
                      <span>
                        <i
                          className={`status-dot ${input === "camera" && camera.enabled ? "lime" : ""}`}
                        />
                        {input === "camera"
                          ? camera.enabled
                            ? "Camera connected"
                            : "Camera is off"
                          : selected
                            ? `${selected} selected`
                            : "Make your move"}
                      </span>
                      <div className="score-pips">
                        {Array.from({ length: target }, (_, i) => (
                          <i key={i} className={i < scores.player ? "filled" : ""} />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="game-controls">
                  <div
                    className={`round-message ${hasResult ? `result-${status.outcome}` : ""}`}
                    aria-live="polite"
                  >
                    <div className="round-message-heading">
                      <span className="round-status">
                        <i />
                        {status.state === "idle"
                          ? "LET'S PLAY"
                          : hasResult
                            ? matchOver
                              ? "MATCH COMPLETE"
                              : status.outcome === "draw"
                                ? "IT'S A TIE"
                                : status.outcome === "win"
                                  ? "YOU WIN"
                                  : status.outcome === "forfeit"
                                    ? "FORFEIT"
                                    : "ROOKIE WINS"
                            : status.state.toUpperCase()}
                      </span>
                      <div className="input-switch" aria-label="Input method">
                        <button
                          disabled={busy}
                          className={input === "buttons" ? "selected" : ""}
                          onClick={() => {
                            setInput("buttons");
                            camera.stop();
                          }}
                        >
                          Buttons
                        </button>
                        <button
                          disabled={busy}
                          className={input === "camera" ? "selected" : ""}
                          onClick={() => setInput("camera")}
                        >
                          <Icon name="camera" size={13} /> Webcam
                        </button>
                      </div>
                    </div>
                    <h2>{title}</h2>
                    <p>{description}</p>
                  </div>
                  {input === "buttons" ? (
                    <div className="move-options">
                      {moves.map((move, i) => (
                        <button
                          key={move}
                          disabled={busy}
                          className={`move-button ${selected === move ? "chosen" : ""}`}
                          onClick={() => setSelected(move)}
                          aria-pressed={selected === move}
                        >
                          <Hand move={move} size={34} />
                          <span>{move}</span>
                          <kbd>{i + 1}</kbd>
                          {selected === move && (
                            <span className="move-check">
                              <Icon name="check" size={10} />
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="camera-controls">
                      <div>
                        <Icon name="camera" size={24} />
                        <span>
                          {camera.enabled
                            ? "Your hand is your controller."
                            : "Your next move? Go hands-free."}
                          <small>Your camera stays private. Video is never uploaded.</small>
                        </span>
                      </div>
                      <button
                        className="secondary-button"
                        disabled={busy || camera.loading}
                        onClick={() => (camera.enabled ? camera.stop() : void camera.start())}
                      >
                        {camera.loading
                          ? "Connecting…"
                          : camera.enabled
                            ? "Turn camera off"
                            : "Enable camera"}
                        <Icon name={camera.enabled ? "cameraOff" : "camera"} size={16} />
                      </button>
                    </div>
                  )}
                  {(camera.error || roundError) && (
                    <p className="camera-error" role="alert">
                      {camera.error || roundError}
                    </p>
                  )}
                  <div className="play-row">
                    <span className="keyboard-hint">
                      {input === "buttons" ? (
                        <>
                          <kbd>1</kbd>
                          <kbd>2</kbd>
                          <kbd>3</kbd> to choose <span>·</span> <kbd>space</kbd> to play
                        </>
                      ) : (
                        <>
                          <Icon name="help" size={14} /> Hold your gesture until the countdown ends
                        </>
                      )}
                    </span>
                    <button
                      className="play-button"
                      disabled={
                        busy ||
                        (input === "buttons" ? !selected : !camera.enabled || camera.loading)
                      }
                      onClick={() => void play()}
                    >
                      {busy
                        ? status.state === "countdown" || status.state === "detecting"
                          ? "Get ready…"
                          : "Here we go…"
                        : matchOver
                          ? "Play again"
                          : hasResult
                            ? "Next round"
                            : "Let's play"}
                      <Icon name={busy ? "clock" : "arrow"} size={19} />
                    </button>
                  </div>
                </div>
              </section>

              <div className="bottom-grid">
                <section className="stats-card">
                  <div className="section-heading">
                    <h3>Your track record</h3>
                    <span className="session-label">
                      YOUR RECORD <i />
                    </span>
                  </div>
                  <div className="stats-grid">
                    <div className="streak-stat">
                      <span className="stat-label">
                        <Icon name="flame" size={15} /> CURRENT STREAK
                      </span>
                      <strong>
                        {stats?.current_streak ?? 0}
                        <span> wins</span>
                      </strong>
                      <small>Keep the momentum.</small>
                    </div>
                    <div className="small-stat">
                      <span className="stat-label">PERSONAL BEST</span>
                      <strong>
                        {stats?.best_streak ?? 0}
                        <Icon name="trophy" size={19} />
                      </strong>
                      <small>Your streak to beat</small>
                    </div>
                    <div className="small-stat">
                      <span className="stat-label">WIN RATE</span>
                      <strong>
                        {stats?.win_rate ?? 0}
                        <span>%</span>
                      </strong>
                      <small>
                        {stats?.total_wins ?? 0} wins · {stats?.total_losses ?? 0} losses
                      </small>
                    </div>
                  </div>
                </section>
                <section className="history-card">
                  <div className="section-heading">
                    <h3>
                      Round history <span className="history-count">{stats?.total_rounds ?? 0}</span>
                    </h3>
                    <Icon name="clock" size={17} />
                  </div>
                  {stats && stats.history.length ? (
                    <div className="round-list">
                      {stats.history.slice(0, 4).map((r) => {
                        const playerMove = r.player !== "forfeit" ? FROM_BACKEND_MOVE[r.player] : null;
                        const aiMove = FROM_BACKEND_MOVE[r.ai];
                        return (
                          <div className="round-item" key={r.round}>
                            <span className="round-number">{String(r.round).padStart(2, "0")}</span>
                            <span className="history-moves">
                              {playerMove ? (
                                <Hand move={playerMove} size={21} />
                              ) : (
                                <Icon name="close" size={16} />
                              )}
                              <span>vs</span>
                              {aiMove && <Hand move={aiMove} size={21} />}
                            </span>
                            <span className={`outcome outcome-${r.outcome}`}>
                              {r.outcome === "win"
                                ? "You won"
                                : r.outcome === "loss"
                                  ? "Rookie won"
                                  : r.outcome === "forfeit"
                                    ? "Forfeit"
                                    : "Draw"}
                              <Icon
                                name={
                                  r.outcome === "win"
                                    ? "diagonal"
                                    : r.outcome === "draw"
                                      ? "reset"
                                      : "arrow"
                                }
                                size={13}
                              />
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="history-empty">
                      <div className="empty-history-icon">
                        <Icon name="clock" size={24} />
                      </div>
                      <strong>A clean slate.</strong>
                      <p>Your story starts with the first round.</p>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}

          {page === "lab" && (
            <section className="lab-layout">
              <div className="lab-preview">
                <span className="lab-unit">RPS–01 / ROOKIE</span>
                <Robot mood={previewMood} color={color} accessory={accessory} />
                <div className="lab-expression">
                  {["idle", "happy", "sad", "thinking"].map((m) => (
                    <button
                      className={previewMood === m ? "selected" : ""}
                      key={m}
                      onClick={() => setPreviewMood(m)}
                    >
                      {m}
                    </button>
                  ))}
                </div>
                <p>Small robot. Big competitive energy.</p>
              </div>
              <div className="lab-settings">
                <div className="section-heading">
                  <h3>Make it your rival.</h3>
                  <Icon name="robot" />
                </div>
                <div className="setting-group">
                  <span className="stat-label">01 / SIGNATURE COLOR</span>
                  <h3>A fresh coat of confidence.</h3>
                  <div className="color-options">
                    {colors.map((c, i) => (
                      <button
                        key={c}
                        aria-label={["Electric lime", "Soft lilac", "Apricot", "Sea glass"][i]}
                        aria-pressed={color === c}
                        style={{ background: c }}
                        className={color === c ? "selected" : ""}
                        onClick={() => setColor(c)}
                      >
                        {color === c && <Icon name="check" />}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="setting-group">
                  <span className="stat-label">02 / THE FINISHING TOUCH</span>
                  <h3>Good looks. Questionable intentions.</h3>
                  <div className="accessory-options">
                    {["antenna", "ears", "none"].map((a) => (
                      <button
                        className={`secondary-button ${accessory === a ? "selected" : ""}`}
                        key={a}
                        onClick={() => setAccessory(a)}
                      >
                        {a === "antenna"
                          ? "Classic antenna"
                          : a === "ears"
                            ? "Cat ears"
                            : "Minimal"}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="setting-group">
                  <span className="stat-label">03 / BRAIN SETTINGS</span>
                  <div className="lab-info">
                    <Icon name="help" size={17} />
                    <p>
                      Rookie plays every move completely at random, with equal odds — there are no
                      difficulty levels wired up on the backend yet, so this app doesn't pretend
                      there are.
                    </p>
                  </div>
                </div>
                <button
                  className="secondary-button"
                  style={{ marginBottom: 12 }}
                  onClick={async () => {
                    if (!confirm("Reset all of your stats (wins, streaks, history)? This can't be undone.")) return;
                    const res = await resetPlayerStats();
                    setStats(res.stats);
                    setRank(res.rank);
                  }}
                >
                  Reset my stats
                </button>
                <button className="play-button" onClick={() => setPage("arena")}>
                  Meet you in the arena
                  <Icon name="arrow" size={18} />
                </button>
              </div>
            </section>
          )}

          {page === "leaderboard" && (
            <LeaderboardPage
              color={color}
              accessory={accessory}
              stats={stats}
              rank={rank}
              onPlay={() => setPage("arena")}
            />
          )}
          <footer className="footer">
            <span>A classic game. A worthy opponent.</span>
            <span>
              NO LUCK? TRY INSTINCT. <span className="footer-star">✳</span>
            </span>
          </footer>
        </main>
      </div>
      {help && <HelpModal onClose={() => setHelp(false)} />}
    </div>
  );
}

function LeaderboardPage({
  color,
  accessory,
  stats,
  rank,
  onPlay,
}: {
  color: string;
  accessory: string;
  stats: PlayerStats | null;
  rank: number | null;
  onPlay: () => void;
}) {
  const [sort, setSort] = useState<"streak" | "wins" | "winrate">("streak");
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [source, setSource] = useState<"supabase" | "local">("local");
  const [loading, setLoading] = useState(true);
  const [minRounds, setMinRounds] = useState(10);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetchLeaderboard(sort)
      .then((res) => {
        if (!alive) return;
        setRows(res.rows);
        setSource(res.source);
        setMinRounds(res.min_rounds_for_winrate);
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [sort]);

  return (
    <section className="leaderboard-page">
      <div className="leaderboard-banner">
        <div>
          <span className="eyebrow">THE 10-WIN CHALLENGE</span>
          <h2>Can you break the robot?</h2>
          <p>Ten consecutive wins. Zero artificial assistance.</p>
          <button className="play-button" onClick={onPlay}>
            Take the challenge
            <Icon name="arrow" size={18} />
          </button>
        </div>
        <Robot mood="happy" color={color} accessory={accessory} />
      </div>
      <div className="leaderboard-stats">
        <div>
          <span className="stat-label">YOUR BEST STREAK</span>
          <strong>{stats?.best_streak ?? 0}</strong>
        </div>
        <div>
          <span className="stat-label">TOTAL ROUND WINS</span>
          <strong>{stats?.total_wins ?? 0}</strong>
        </div>
        <div>
          <span className="stat-label">ROBOTS BROKEN</span>
          <strong>{stats?.robot_breaks ?? 0}</strong>
        </div>
      </div>
      <div className="leaderboard-table">
        <div className="section-heading">
          <h3>Global leaderboard{rank ? ` · you're #${rank}` : ""}</h3>
          <span className="session-label">
            {source === "supabase" ? "LIVE · SUPABASE" : "LOCAL ONLY"}{" "}
            <i className={source === "supabase" ? "" : "offline"} />
          </span>
        </div>
        <div className="lb-sort">
          {(["streak", "wins", "winrate"] as const).map((s) => (
            <button
              key={s}
              className={`secondary-button ${sort === s ? "selected" : ""}`}
              onClick={() => setSort(s)}
            >
              {s === "streak" ? "Best streak" : s === "wins" ? "Total wins" : "Win rate"}
            </button>
          ))}
        </div>
        {loading ? (
          <p className="lb-loading">Loading rankings…</p>
        ) : rows.length === 0 ? (
          <div className="leaderboard-unavailable">
            <span className="leaderboard-trophy">
              <Icon name="trophy" size={32} />
            </span>
            <h3>Nobody's on the board yet.</h3>
            <p>
              {sort === "winrate"
                ? `Play ${minRounds}+ rounds to qualify for the win-rate ranking.`
                : "Play a round to claim the very first spot."}
            </p>
            <button className="secondary-button" onClick={onPlay}>
              Back to the arena
              <Icon name="arrow" size={17} />
            </button>
          </div>
        ) : (
          <div className="lb-rows">
            {rows.map((row, i) => (
              <div className={`lb-row ${row.is_you ? "you" : ""}`} key={row.username}>
                <span className="lb-rank">
                  {i === 0 ? <Icon name="trophy" size={16} /> : i + 1}
                </span>
                <span className="lb-name">{row.username}</span>
                <span className="lb-metric">
                  <Icon name="flame" size={13} /> {row.best_streak}
                </span>
                <span className="lb-metric">{row.total_wins} wins</span>
                <span className="lb-metric">{row.win_rate}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function HelpModal({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.querySelector("button")?.focus();
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const items = ref.current?.querySelectorAll<HTMLButtonElement>("button");
        if (!items?.length) return;
        if (e.shiftKey && document.activeElement === items[0]) {
          e.preventDefault();
          items[items.length - 1].focus();
        } else if (!e.shiftKey && document.activeElement === items[items.length - 1]) {
          e.preventDefault();
          items[0].focus();
        }
      }
    }
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="help-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        ref={ref}
      >
        <div className="section-heading">
          <span className="eyebrow">A QUICK FIELD GUIDE</span>
          <button className="icon-button" onClick={onClose} aria-label="Close help">
            <Icon name="close" />
          </button>
        </div>
        <h2 id="help-title">Instinct over algorithms.</h2>
        <p>The rules are timeless. The opponent is a little different.</p>
        <div className="rules">
          {moves.map((move, i) => (
            <div key={move}>
              <Hand move={move} size={40} />
              <strong>{move}</strong>
              <span>beats {["scissors", "rock", "paper"][i]}</span>
            </div>
          ))}
        </div>
        <ol>
          <li>
            <strong>Choose your controller.</strong>
            <p>Click a move or use keys 1, 2, 3. Feeling hands-on? Enable your webcam.</p>
          </li>
          <li>
            <strong>Beat the countdown.</strong>
            <p>
              Press "Let's play" or space. With a webcam, hold a fist, open palm, or victory sign
              until the countdown ends.
            </p>
          </li>
          <li>
            <strong>Win the match. Build a streak.</strong>
            <p>
              Win the most rounds in your chosen format. Ties don't count. Win 10 rounds in a row
              to break Rookie.
            </p>
          </li>
        </ol>
        <button className="play-button" onClick={onClose}>
          Got it. Let's play.
          <Icon name="arrow" size={18} />
        </button>
      </div>
    </div>
  );
}
