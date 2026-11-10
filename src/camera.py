"""
Camera manager.
Runs webcam capture in a background thread and provides frames via a shared buffer.
"""

import cv2
import threading
import base64
import time
import numpy as np
from .gesture_recognizer import GestureRecognizer


class CameraManager:
    """
    Manages webcam capture and gesture detection in a background thread.
    Provides JPEG frames as base64 strings for streaming to the browser.
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.running = False
        self.thread = None

        self.recognizer = GestureRecognizer()

        # Shared state (protected by lock)
        self._lock = threading.Lock()
        self._frame_b64 = None          # Latest annotated frame as base64 JPEG
        self._current_gesture = None    # Latest detected gesture name
        self._gesture_history = []      # Recent gesture detections for stability check
        self._error = None

    def start(self) -> bool:
        """Start the camera capture thread. Returns True on success."""
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            self._error = f"Cannot open camera {self.camera_index}"
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        """Stop the camera capture thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        self.recognizer.release()

    def _capture_loop(self):
        """Background loop: capture frames, run gesture detection, encode to JPEG."""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.033)
                continue

            # Flip horizontally for mirror effect
            frame = cv2.flip(frame, 1)

            # Run gesture detection
            annotated, gesture = self.recognizer.process_frame(frame)

            # Add gesture label overlay
            self._draw_overlay(annotated, gesture)

            # Encode to JPEG base64
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64 = base64.b64encode(buffer).decode('utf-8')

            with self._lock:
                self._frame_b64 = b64
                self._current_gesture = gesture
                # Keep last 10 gesture readings for stability
                self._gesture_history.append(gesture)
                if len(self._gesture_history) > 10:
                    self._gesture_history.pop(0)

    def _draw_overlay(self, frame, gesture: str | None):
        """Draw gesture label and status indicator on the frame."""
        h, w = frame.shape[:2]

        # Status bar at bottom
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 50), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        if gesture:
            label_map = {
                "Closed_Fist": "✊ ROCK",
                "Open_Palm": "✋ PAPER",
                "Victory": "✌ SCISSORS",
            }
            label = label_map.get(gesture, gesture)
            color = (100, 220, 100)
        else:
            label = "⟳ No gesture detected"
            color = (100, 100, 220)

        cv2.putText(
            frame, label,
            (10, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8, color, 2, cv2.LINE_AA
        )

    def get_frame(self) -> str | None:
        """Get the latest annotated frame as base64 JPEG string."""
        with self._lock:
            return self._frame_b64

    def get_gesture(self) -> str | None:
        """Get the latest detected gesture."""
        with self._lock:
            return self._current_gesture

    def get_stable_gesture(self, min_stable_frames: int = 3) -> str | None:
        """
        Get a gesture that has been stable for at least min_stable_frames.
        This prevents transient detection failures from causing accidental forfeits.
        """
        with self._lock:
            if len(self._gesture_history) < min_stable_frames:
                return self._current_gesture

            recent = self._gesture_history[-min_stable_frames:]
            # If all recent frames show the same gesture, it's stable
            if len(set(recent)) == 1:
                return recent[0]

            # Allow one None in the last frames
            non_none = [g for g in recent if g is not None]
            if len(non_none) >= min_stable_frames - 1:
                gestures = set(non_none)
                if len(gestures) == 1:
                    return non_none[0]

            return self._current_gesture

    @property
    def error(self) -> str | None:
        return self._error

    @staticmethod
    def list_cameras(max_index: int = 5) -> list[int]:
        """Return indices of available cameras."""
        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available
