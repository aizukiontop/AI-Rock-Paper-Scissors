import { useCallback, useEffect, useRef, useState } from "react";
import type { GestureRecognizer } from "@mediapipe/tasks-vision";
import type { Move } from "./components";
import { pushGesture } from "./api";

const RAW_GESTURE: Record<Move, "Closed_Fist" | "Open_Palm" | "Victory"> = {
  Rock: "Closed_Fist",
  Paper: "Open_Palm",
  Scissors: "Victory",
};
const PUSH_INTERVAL_MS = 90; // ~11/sec -- plenty for the backend's stability buffer

/**
 * Turns whatever a failed promise rejected with into an actually readable
 * message. Needed because some loaders inside @mediapipe/tasks-vision's
 * WASM/script-loading chain reject with a raw DOM Event (e.g. a <script>
 * or <img> element's onerror), not an Error -- and String(event) on those
 * always produces the unhelpful literal "[object Event]".
 */
function describeError(err: unknown): string {
  if (err instanceof DOMException) return `${err.name}: ${err.message}`;
  if (err instanceof Error) return err.message;
  if (typeof ErrorEvent !== "undefined" && err instanceof ErrorEvent) {
    return err.message || `error loading ${err.filename || "a resource"}`;
  }
  if (typeof Event !== "undefined" && err instanceof Event) {
    const target = err.target as { src?: string; href?: string; tagName?: string } | null;
    const source = target?.src || target?.href;
    return source
      ? `failed to load ${source}`
      : `a "${err.type}" event on ${target?.tagName?.toLowerCase() || "an element"} (likely a blocked or failed network request -- check an ad blocker, firewall, or offline CDN access)`;
  }
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recognizer = useRef<GestureRecognizer | null>(null);
  const frame = useRef(0);
  const generation = useRef(0);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [gesture, setGesture] = useState<Move | null>(null);
  const gestureRef = useRef<Move | null>(null);
  const stop = useCallback(() => {
    generation.current++;
    cancelAnimationFrame(frame.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recognizer.current?.close();
    recognizer.current = null;
    setEnabled(false);
    setLoading(false);
    setGesture(null);
    gestureRef.current = null;
    void pushGesture(null);
  }, []);
  const start = async () => {
    const current = ++generation.current;
    setLoading(true);
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setLoading(false);
      setError(
        window.isSecureContext
          ? "This browser doesn't support camera access. Try a recent Chrome, Firefox, or Safari, or use buttons."
          : "Camera access needs a secure connection (HTTPS), or http://localhost during development. This page is neither, so the browser disables it entirely.",
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
        audio: false,
      });
      if (current !== generation.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;
      setEnabled(true);
      const { FilesetResolver, GestureRecognizer } = await import("@mediapipe/tasks-vision");
      const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm",
      );
      const MODEL_URL =
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
      let detector;
      try {
        detector = await GestureRecognizer.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
          runningMode: "VIDEO",
          numHands: 1,
        });
      } catch (gpuErr) {
        // GPU/WebGL unavailable is a common, well-documented cause of this
        // call failing even though the camera stream itself was already
        // granted -- retry once on CPU before giving up entirely.
        console.warn("GPU delegate failed, retrying on CPU:", gpuErr);
        detector = await GestureRecognizer.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
          runningMode: "VIDEO",
          numHands: 1,
        });
      }
      if (current !== generation.current) {
        detector.close();
        return;
      }
      recognizer.current = detector;
      setLoading(false);
      let previousTime = -1;
      let lastPush = 0;
      const detect = () => {
        const video = videoRef.current;
        if (
          video &&
          video.readyState >= 2 &&
          video.currentTime !== previousTime &&
          recognizer.current
        ) {
          previousTime = video.currentTime;
          try {
            const result = recognizer.current.recognizeForVideo(video, performance.now());
            const top = result.gestures[0]?.[0];
            const map: Record<string, Move> = {
              Closed_Fist: "Rock",
              Open_Palm: "Paper",
              Victory: "Scissors",
            };
            const value = top && top.score > 0.55 ? map[top.categoryName] || null : null;
            setGesture(value);
            gestureRef.current = value;
            const now = performance.now();
            if (now - lastPush >= PUSH_INTERVAL_MS) {
              lastPush = now;
              void pushGesture(value ? RAW_GESTURE[value] : null);
            }
          } catch {
            setError("Gesture tracking paused. Switch to buttons or restart the camera.");
            return;
          }
        }
        frame.current = requestAnimationFrame(detect);
      };
      detect();
    } catch (err) {
      if (current !== generation.current) return;
      stop();
      console.error("Camera/gesture-model startup failed:", err);
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Camera access was denied. Allow it in your browser, or play with buttons.");
      } else if (err instanceof DOMException && err.name === "NotFoundError") {
        setError("No camera was found on this device. Play with buttons instead.");
      } else {
        setError(
          `Couldn't start gesture detection (${describeError(err)}). Check your connection, or use buttons.`,
        );
      }
    }
  };
  useEffect(() => {
    if (enabled && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current
        .play()
        .catch(() => setError("Camera playback was interrupted. Please restart the camera."));
    }
  }, [enabled]);
  useEffect(
    () => () => {
      generation.current++;
      cancelAnimationFrame(frame.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      recognizer.current?.close();
    },
    [],
  );
  return { videoRef, enabled, loading, error, gesture, gestureRef, start, stop };
}
