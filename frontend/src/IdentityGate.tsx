import { useState } from "react";
import { Hand, Icon } from "./components";
import { claimUsername, ApiError, type PlayerStats } from "./api";

export const IDENTITY_KEY = "rps_identity";

export interface StoredIdentity {
  username: string;
  token: string;
}

export function loadStoredIdentity(): StoredIdentity | null {
  try {
    const raw = localStorage.getItem(IDENTITY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.username === "string" && typeof parsed.token === "string") {
      return parsed;
    }
  } catch {
    /* corrupt/old value -- treat as signed out */
  }
  return null;
}

function saveStoredIdentity(identity: StoredIdentity) {
  localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
}

export function clearStoredIdentity() {
  localStorage.removeItem(IDENTITY_KEY);
}

/**
 * Shown whenever there's no resumed/claimed identity yet. Registers a new
 * username, or resumes an existing one if a matching token is already in
 * localStorage (see loadStoredIdentity). The server -- not this screen --
 * is the one actually deciding whether a resume is authorized; this just
 * submits whatever credentials it has.
 */
export default function IdentityGate({
  initialUsername,
  onReady,
}: {
  initialUsername: string;
  onReady: (stats: PlayerStats) => void;
}) {
  const [username, setUsername] = useState(initialUsername);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    const trimmed = username.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError("");
    try {
      const existing = loadStoredIdentity();
      const token = existing && existing.username.toLowerCase() === trimmed.toLowerCase()
        ? existing.token
        : null;
      const res = await claimUsername(trimmed, token);
      saveStoredIdentity({ username: res.stats.username, token: res.token });
      onReady(res.stats);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't reach the server. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop identity-gate-backdrop">
      <form className="help-modal identity-gate" onSubmit={submit}>
        <div className="section-heading">
          <span className="eyebrow">WHO'S CHALLENGING ROOKIE?</span>
        </div>
        <span className="identity-gate-symbol">
          <Hand move="Rock" size={40} />
        </span>
        <h2>Pick your fighter name.</h2>
        <p>
          3–16 characters, letters/numbers/underscores. Already played here before? Enter the
          same username to pick up your stats and streak where you left off.
        </p>
        <label className="identity-gate-field">
          <span>Username</span>
          <input
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. scissor_hands"
            maxLength={16}
            disabled={busy}
          />
        </label>
        {error && (
          <p className="camera-error" role="alert">
            <Icon name="close" size={14} /> {error}
          </p>
        )}
        <button className="play-button" type="submit" disabled={busy || !username.trim()}>
          {busy ? "Checking…" : "Enter the arena"}
          <Icon name="arrow" size={18} />
        </button>
      </form>
    </div>
  );
}
