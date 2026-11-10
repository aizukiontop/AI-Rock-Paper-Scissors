"""
Integration tests for the browser-fed webcam pipeline introduced when the
Figma frontend replaced the old server-side OpenCV camera capture.

These prove:
  - POST /api/camera/gesture is the only way gesture data reaches the
    server now (no camera device is ever opened server-side).
  - Webcam-mode rounds read a stable value out of that buffer, with the
    same "3 consistent readings in a row" stability rule the old
    CameraManager used, so a momentary misread can't cause a forfeit.
  - The player never has to have sent a gesture before the round starts
    (unlike Buttons mode) -- the backend samples it lazily, at the
    "locked" phase, same as the original server-side-camera design.
"""

import time
import unittest

from src.app import create_app
from src.gesture_buffer import GestureBuffer


class TestGestureBufferStability(unittest.TestCase):
    """Unit-level check of the buffer's own stability logic."""

    def test_requires_consistent_recent_readings(self):
        buf = GestureBuffer()
        buf.push("Closed_Fist")
        buf.push("Open_Palm")  # flickers
        buf.push("Closed_Fist")
        # Not yet 3 consistent readings in the last 3 -- falls back to latest.
        self.assertEqual(buf.get_stable_gesture(), "Closed_Fist")

    def test_three_consistent_readings_are_stable(self):
        buf = GestureBuffer()
        for _ in range(3):
            buf.push("Victory")
        self.assertEqual(buf.get_stable_gesture(), "Victory")

    def test_clear_resets_the_buffer(self):
        buf = GestureBuffer()
        buf.push("Open_Palm")
        buf.clear()
        self.assertIsNone(buf.get_gesture())


class TestWebcamRoundReadsFromBrowserPushedBuffer(unittest.TestCase):
    """End-to-end: push gestures via the API, then play a webcam-mode round."""

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        import uuid
        self.username = f"gestest_{uuid.uuid4().hex[:8]}"
        r = self.client.post('/api/player/claim', json={'username': self.username})
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_camera_gesture_endpoint_feeds_the_round(self):
        # Simulate the browser pushing a stable "Rock" reading a few times,
        # the way useCamera.ts's throttled detection loop does.
        for _ in range(5):
            r = self.client.post('/api/camera/gesture', json={'gesture': 'Closed_Fist'})
            self.assertEqual(r.status_code, 200)

        r = self.client.post('/api/game/start', json={
            'mode': None, 'new_session': True, 'input_mode': 'webcam',
        })
        self.assertEqual(r.status_code, 200)

        # Poll until the round resolves (countdown + detecting + lock + reveal).
        status = None
        for _ in range(20):
            time.sleep(0.5)
            status = self.client.get('/api/game/status').get_json()
            if status['state'] in ('result', 'game_over'):
                break
        self.assertIn(status['state'], ('result', 'game_over'))
        self.assertEqual(status['player_move'], 'rock')

    def test_no_gesture_pushed_results_in_forfeit_not_an_error(self):
        from src import routes as routes_module
        routes_module.gesture_buffer.clear()
        r = self.client.post('/api/game/start', json={
            'mode': None, 'new_session': True, 'input_mode': 'webcam',
        })
        self.assertEqual(r.status_code, 200)
        status = None
        for _ in range(20):
            time.sleep(0.5)
            status = self.client.get('/api/game/status').get_json()
            if status['state'] in ('result', 'game_over'):
                break
        self.assertIn(status['state'], ('result', 'game_over'))
        self.assertEqual(status['player_move'], 'forfeit')

    def test_malformed_gesture_value_is_rejected(self):
        r = self.client.post('/api/camera/gesture', json={'gesture': 'Not_A_Real_Gesture'})
        self.assertEqual(r.status_code, 400)

    def test_old_server_side_camera_endpoints_are_gone(self):
        """
        The server-attached-camera endpoints are removed entirely -- this
        app must never try to open a webcam that belongs to the hosting
        server rather than the player.
        """
        for path in ('/api/camera/start', '/api/camera/stop', '/api/frame', '/api/cameras'):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 404, f"{path} should no longer exist")


if __name__ == '__main__':
    unittest.main()
