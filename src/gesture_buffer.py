"""
Browser-fed gesture buffer.

The player's own browser now runs gesture detection locally (Figma's
useCamera.ts, using @mediapipe/tasks-vision client-side) and pushes each
reading here via POST /api/camera/gesture -- see routes.py. No image data
ever crosses the wire and the backend never opens a camera device of its
own; the physical camera always belongs to whoever is playing.

This class only holds a short rolling history of the most recent pushes
and answers "what's the stable gesture right now?", exactly like
CameraManager.get_stable_gesture() used to when it read a local OpenCV
capture loop. game_session.py calls this lazily, at its own chosen
moment, when a round reaches the LOCKED phase -- so the server-authoritative
timing (AI move committed before the player's gesture is ever read) is
unchanged from before.
"""

import threading


class GestureBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._current_gesture = None
        self._history = []

    def push(self, gesture: str | None):
        """Record one browser-detected reading (called on every detection tick)."""
        with self._lock:
            self._current_gesture = gesture
            self._history.append(gesture)
            if len(self._history) > 10:
                self._history.pop(0)

    def clear(self):
        with self._lock:
            self._current_gesture = None
            self._history = []

    def get_gesture(self) -> str | None:
        with self._lock:
            return self._current_gesture

    def get_stable_gesture(self, min_stable_frames: int = 3) -> str | None:
        """
        Identical logic to the previous CameraManager.get_stable_gesture():
        a gesture only counts once it's been consistent across the last
        few readings, so a momentary misread can't cause an accidental
        forfeit.
        """
        with self._lock:
            if len(self._history) < min_stable_frames:
                return self._current_gesture

            recent = self._history[-min_stable_frames:]
            if len(set(recent)) == 1:
                return recent[0]

            non_none = [g for g in recent if g is not None]
            if len(non_none) >= min_stable_frames - 1:
                gestures = set(non_none)
                if len(gestures) == 1:
                    return non_none[0]

            return self._current_gesture
