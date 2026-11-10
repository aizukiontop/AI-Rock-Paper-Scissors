"""
Gesture recognition using MediaPipe's HandLandmarker (Tasks API).
Classifies hand poses into Rock, Paper, or Scissors using rule-based
landmark geometry (no gesture-specific model required beyond hand landmarks).
"""

import cv2
import time
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

from .model_downloader import ensure_model

drawing_utils = vision.drawing_utils
drawing_styles = vision.drawing_styles
HAND_CONNECTIONS = vision.HandLandmarksConnections.HAND_CONNECTIONS


class GestureRecognizer:
    """
    Detects hand landmarks via MediaPipe's HandLandmarker and classifies
    the pose into Rock, Paper, or Scissors using finger-extension geometry.
    """

    def __init__(self):
        model_path = ensure_model()

        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.last_gesture = None
        self._start_time = time.monotonic()
        self._last_timestamp_ms = -1

    def _finger_extended(self, landmarks, tip_id, pip_id):
        """A finger is extended if its tip is above (smaller y) than its PIP joint."""
        return landmarks[tip_id].y < landmarks[pip_id].y

    def _thumb_extended(self, landmarks, handedness="Right"):
        """Thumb extension is judged on the x-axis since it moves sideways."""
        tip = landmarks[4]
        mcp = landmarks[2]
        if handedness == "Right":
            return tip.x < mcp.x
        else:
            return tip.x > mcp.x

    def classify_gesture(self, landmarks, handedness="Right"):
        """
        Classify a hand pose from 21 hand landmarks.
        Returns 'Closed_Fist', 'Open_Palm', 'Victory', or None if unrecognized.
        """
        index_ext = self._finger_extended(landmarks, 8, 6)
        middle_ext = self._finger_extended(landmarks, 12, 10)
        ring_ext = self._finger_extended(landmarks, 16, 14)
        pinky_ext = self._finger_extended(landmarks, 20, 18)

        num_extended = sum([index_ext, middle_ext, ring_ext, pinky_ext])

        # Rock: a closed fist, no fingers extended
        if num_extended == 0:
            return "Closed_Fist"

        # Paper: an open palm, at least 3 fingers extended including middle+ring
        if num_extended >= 3 and middle_ext and ring_ext:
            return "Open_Palm"

        # Scissors: index + middle extended, ring + pinky curled
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return "Victory"

        return None

    def process_frame(self, frame: np.ndarray):
        """
        Run hand detection + gesture classification on a BGR frame.
        Returns (annotated_frame, gesture_name_or_None).
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        timestamp_ms = int((time.monotonic() - self._start_time) * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        gesture = None
        annotated = frame.copy()

        if result.hand_landmarks:
            for hand_landmarks, handedness_list in zip(
                result.hand_landmarks, result.handedness
            ):
                # The Tasks API drawing utility accepts the landmark list directly
                drawing_utils.draw_landmarks(
                    annotated,
                    hand_landmarks,
                    HAND_CONNECTIONS,
                    drawing_styles.get_default_hand_landmarks_style(),
                    drawing_styles.get_default_hand_connections_style(),
                )

                handedness_label = handedness_list[0].category_name
                gesture = self.classify_gesture(hand_landmarks, handedness_label)

        self.last_gesture = gesture
        return annotated, gesture

    def release(self):
        """Release MediaPipe resources."""
        self.landmarker.close()
