"""
Automated proof that the AI opponent is fair.

Run with:  python3 -m unittest tests.test_ai_fairness -v
(from the project root; no extra dependencies needed -- uses only the
standard library's unittest).

These tests check two different kinds of claims:
  1. STRUCTURAL claims ("the AI cannot see the player's gesture") are
     proven by inspecting the actual function signatures and call order --
     not by sampling, since no amount of sampling can prove an impossibility
     as convincingly as showing the code has no path for it to happen.
  2. STATISTICAL claims ("the AI is unbiased") are proven by sampling
     ai_choose() a large number of times and checking the distribution.
"""

import inspect
import time
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.game_logic import ai_choose, map_gesture, determine_winner, Move
from src.game_session import GameSession, GameState


class TestAIChoiceIsUniform(unittest.TestCase):
    """Statistical fairness: ai_choose() must pick each move ~1/3 of the time."""

    def test_all_three_moves_are_selectable(self):
        seen = {ai_choose() for _ in range(300)}
        self.assertEqual(seen, {Move.ROCK, Move.PAPER, Move.SCISSORS},
                          "ai_choose() should be able to produce all three moves")

    def test_distribution_is_reasonably_uniform(self):
        N = 30000
        counts = {Move.ROCK: 0, Move.PAPER: 0, Move.SCISSORS: 0}
        for _ in range(N):
            counts[ai_choose()] += 1

        for move, count in counts.items():
            proportion = count / N
            # Expected 1/3 (~0.333). A generous +-0.02 band is ~7x the
            # theoretical standard error at this N, so a fair RNG passes
            # this virtually every run, while a badly biased one would not.
            self.assertAlmostEqual(
                proportion, 1 / 3, delta=0.02,
                msg=f"{move} appeared {proportion:.4f} of the time over {N} trials -- not close to 1/3"
            )


class TestAICannotSeePlayerGesture(unittest.TestCase):
    """
    Structural fairness: ai_choose() has no parameters at all, so it is not
    merely 'statistically' independent of the player's gesture -- it is
    IMPOSSIBLE for it to read it, by construction.
    """

    def test_ai_choose_accepts_no_arguments(self):
        sig = inspect.signature(ai_choose)
        self.assertEqual(
            len(sig.parameters), 0,
            "ai_choose() must take zero parameters -- if it ever needs one, "
            "that would be the moment to re-audit for a player-gesture leak"
        )

    def test_ai_move_is_committed_before_the_player_gesture_is_ever_read(self):
        """
        Drives one real round and proves, by call order, that the AI's move
        is already fixed before the camera is ever consulted.
        """
        gesture_read_log = []

        def spy_gesture_fn():
            # By the time this is called, ai_move must already be set and
            # must not change no matter what we return here.
            gesture_read_log.append(session.ai_move)
            return 'Closed_Fist'

        session = GameSession()
        session.start_round(spy_gesture_fn)

        # The AI's move is set synchronously, inside start_round(), before
        # the background thread (and therefore the gesture read) even
        # begins -- so it must already be visible right now.
        ai_move_at_commit_time = session.ai_move
        self.assertIsNotNone(ai_move_at_commit_time, "AI must commit its move immediately, before any countdown time passes")

        time.sleep(4.5)  # let the full round (countdown + detecting + locked + revealing) finish

        self.assertEqual(len(gesture_read_log), 1, "the camera must be read exactly once per round")
        self.assertEqual(
            gesture_read_log[0], ai_move_at_commit_time,
            "the AI's move must already have been fixed at the moment the gesture was read"
        )
        self.assertEqual(
            session.ai_move, ai_move_at_commit_time,
            "the AI's move must not change between commit and the end of the round"
        )


class TestAIMoveIsLockedAfterCommit(unittest.TestCase):
    """The AI must not be able to change its move after the round starts,
    regardless of what the player does."""

    def test_ai_move_unchanged_across_different_player_gestures(self):
        for gesture, expected_player_move in [
            ('Closed_Fist', 'rock'), ('Open_Palm', 'paper'), ('Victory', 'scissors'), (None, 'forfeit')
        ]:
            with self.subTest(gesture=gesture):
                session = GameSession()
                session.start_round(lambda g=gesture: g)
                committed = session.ai_move
                time.sleep(4.5)
                final = session.get_status()
                self.assertEqual(final['ai_move'], committed.value,
                                  "AI move must be identical before and after the round, "
                                  "no matter what the player showed")
                self.assertEqual(final['player_move'], expected_player_move)


class TestStandardRulesAndDraws(unittest.TestCase):
    """Exhaustively check every (player, ai) combination against the
    textbook Rock-Paper-Scissors rule set."""

    def test_all_nine_combinations(self):
        expected = {
            (Move.ROCK, Move.ROCK): 'draw',
            (Move.ROCK, Move.PAPER): 'loss',
            (Move.ROCK, Move.SCISSORS): 'win',
            (Move.PAPER, Move.ROCK): 'win',
            (Move.PAPER, Move.PAPER): 'draw',
            (Move.PAPER, Move.SCISSORS): 'loss',
            (Move.SCISSORS, Move.ROCK): 'loss',
            (Move.SCISSORS, Move.PAPER): 'win',
            (Move.SCISSORS, Move.SCISSORS): 'draw',
        }
        for (player, ai), outcome in expected.items():
            with self.subTest(player=player, ai=ai):
                self.assertEqual(determine_winner(player, ai), outcome)

    def test_forfeit_is_always_a_loss_for_the_player(self):
        for ai_move in (Move.ROCK, Move.PAPER, Move.SCISSORS):
            self.assertEqual(determine_winner(Move.FORFEIT, ai_move), 'forfeit')

    def test_gesture_mapping_is_unambiguous(self):
        self.assertEqual(map_gesture('Closed_Fist'), Move.ROCK)
        self.assertEqual(map_gesture('Open_Palm'), Move.PAPER)
        self.assertEqual(map_gesture('Victory'), Move.SCISSORS)
        self.assertIsNone(map_gesture('Something_Else'))
        self.assertIsNone(map_gesture(None))


if __name__ == '__main__':
    unittest.main()
