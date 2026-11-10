"""
Downloads the MediaPipe HandLandmarker model file on first run.
The model is a small (~8MB) .task file required by the new MediaPipe Tasks API.
"""

import os
import urllib.request

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'hand_landmarker.task')


def ensure_model() -> str:
    """
    Make sure the hand landmarker model file exists locally.
    Downloads it if missing. Returns the local file path.
    Raises RuntimeError if the download fails and no local copy exists.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 0:
        return MODEL_PATH

    print(f"Downloading hand gesture model (one-time setup, ~8MB)...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Model downloaded successfully.")
        return MODEL_PATH
    except Exception as e:
        raise RuntimeError(
            f"Could not download the hand landmark model from {MODEL_URL}.\n"
            f"Error: {e}\n"
            f"Please check your internet connection, or manually download the file to:\n"
            f"{MODEL_PATH}"
        )
