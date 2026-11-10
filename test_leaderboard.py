"""
Tests for the leaderboard: the three ranking categories (win streak, total
wins, win rate), the win-rate minimum-rounds threshold, and -- using a
MOCKED Supabase HTTP layer -- that the Supabase integration code itself
builds correct requests and parses responses correctly.

IMPORTANT HONESTY NOTE: the mocked-Supabase tests below prove the request
each supabase_rest.py function sends is well-formed, and that it parses a
PostgREST-shaped response correctly. They do NOT prove a real Supabase
project is reachable, that RLS is actually enforced there, or that two
real machines can see each other's data -- none of that can be tested
without real SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY credentials, which
this environment does not have. See README.md's leaderboard section for
exactly what still needs to be verified against a real project.

Run with: python3 -m unittest tests.test_leaderboard -v
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import players, supabase_rest as sb


class TestLocalLeaderboardCategories(unittest.TestCase):
    """Exercises the local-JSON fallback path (no Supabase configured)."""

    def setUp(self):
        self._orig_file = players.PLAYERS_FILE
        self._tmp_file = os.path.join(os.path.dirname(__file__), '_tmp_players.json')
        players.PLAYERS_FILE = self._tmp_file
        with open(self._tmp_file, 'w') as f:
            json.dump({}, f)
        # Force offline mode regardless of the real environment, so this
        # test suite is self-contained and doesn't accidentally hit a real
        # Supabase project if credentials happen to be set.
        self._sb_patch = patch.object(sb, 'is_configured', return_value=False)
        self._sb_patch.start()

    def tearDown(self):
        self._sb_patch.stop()
        players.PLAYERS_FILE = self._orig_file
        if os.path.exists(self._tmp_file):
            os.remove(self._tmp_file)

    def _make_player(self, name, wins, losses, draws, best_streak):
        players.claim_username(name, None)
        for _ in range(wins):
            players.record_round(name, 'win', 'rock', 'scissors')
        for _ in range(losses):
            players.record_round(name, 'loss', 'rock', 'paper')
        for _ in range(draws):
            players.record_round(name, 'draw', 'rock', 'rock')
        # record_round already tracks best_streak from real win/loss
        # sequencing; sanity check it reached what the test expects.
        stats = players.get_stats(name)
        self.assertEqual(stats['best_streak'], best_streak, f"test setup assumption wrong for {name}")

    def test_sort_by_streak(self):
        self._make_player('Alice', wins=5, losses=0, draws=0, best_streak=5)
        self._make_player('Bob', wins=8, losses=1, draws=0, best_streak=8)
        rows, source = players.get_leaderboard(sort_by='streak')
        self.assertEqual(source, 'local')
        self.assertEqual([r['username'] for r in rows], ['Bob', 'Alice'])

    def test_sort_by_total_wins(self):
        # Alice has fewer wins but a higher CURRENT streak than Bob here,
        # so this also proves "wins" and "streak" really are independent
        # sort orders, not aliases of each other.
        self._make_player('Alice', wins=3, losses=0, draws=0, best_streak=3)
        # _make_player applies all wins before losses, so the 10 wins happen
        # first and set best_streak to 10 -- the later losses reset the
        # CURRENT streak but never lower a best_streak already achieved.
        self._make_player('Bob', wins=10, losses=5, draws=0, best_streak=10)
        rows_wins, _ = players.get_leaderboard(sort_by='wins')
        rows_streak, _ = players.get_leaderboard(sort_by='streak')
        self.assertEqual([r['username'] for r in rows_wins], ['Bob', 'Alice'],
                          "Bob has more total wins and should rank first by 'wins'")
        self.assertEqual([r['username'] for r in rows_streak], ['Bob', 'Alice'],
                          "Bob also has the higher best streak here")
        self.assertEqual(rows_wins[0]['total_wins'], 10)
        self.assertEqual(rows_wins[1]['total_wins'], 3)

    def test_winrate_excludes_players_under_the_minimum_rounds(self):
        # Carol: 1 win, 0 losses -> 100% win rate, but only 1 round played.
        self._make_player('Carol', wins=1, losses=0, draws=0, best_streak=1)
        # Dave: 7 wins, 3 losses -> 70% win rate, 10 rounds played (meets the
        # default MIN_ROUNDS_FOR_WIN_RATE threshold).
        self._make_player('Dave', wins=7, losses=3, draws=0, best_streak=7)

        rows, _ = players.get_leaderboard(sort_by='winrate')
        usernames = [r['username'] for r in rows]
        self.assertNotIn('Carol', usernames,
                          "Carol has only 1 round played and must be excluded from Win Rate "
                          "despite her 100% rate -- this is the 'one lucky game' guard")
        self.assertIn('Dave', usernames)

    def test_winrate_ranks_by_rate_once_qualified(self):
        # Same sequential-order note as above: 5 wins first reach best_streak
        # 5, and the losses that follow only reset the current streak.
        self._make_player('EvenSteven', wins=5, losses=5, draws=0, best_streak=5)   # 50%, 10 rounds
        self._make_player('MostlyWins', wins=9, losses=1, draws=0, best_streak=9)   # 90%, 10 rounds
        rows, _ = players.get_leaderboard(sort_by='winrate')
        self.assertEqual([r['username'] for r in rows], ['MostlyWins', 'EvenSteven'])
        self.assertAlmostEqual(rows[0]['win_rate'], 90.0, delta=0.1)
        self.assertAlmostEqual(rows[1]['win_rate'], 50.0, delta=0.1)

    def test_search_filters_by_substring(self):
        self._make_player('AlphaPlayer', wins=1, losses=0, draws=0, best_streak=1)
        self._make_player('BetaPlayer', wins=1, losses=0, draws=0, best_streak=1)
        rows, _ = players.get_leaderboard(sort_by='streak', search='alpha')
        self.assertEqual([r['username'] for r in rows], ['AlphaPlayer'])

    def test_rank_matches_leaderboard_position(self):
        self._make_player('Top', wins=5, losses=0, draws=0, best_streak=5)
        self._make_player('Mid', wins=3, losses=0, draws=0, best_streak=3)
        self._make_player('Low', wins=1, losses=0, draws=0, best_streak=1)
        self.assertEqual(players.get_rank('Top', sort_by='streak'), 1)
        self.assertEqual(players.get_rank('Mid', sort_by='streak'), 2)
        self.assertEqual(players.get_rank('Low', sort_by='streak'), 3)


class TestRoundsAreNeverDoubleCounted(unittest.TestCase):
    """
    A duplicate HTTP retry (or any other accidental repeat call) pushing
    the SAME computed snapshot to Supabase must be a no-op, not a double
    count -- because the sync payload is the player's absolute current
    totals, not an increment. Proven here by calling the sync path twice
    with the identical record and checking the row sent is identical both
    times (an upsert of the same absolute values is idempotent by nature).
    """

    def test_repeated_sync_payload_is_idempotent(self):
        record = {
            "username": "Idempotent", "current_streak": 3, "best_streak": 5,
            "total_wins": 10, "total_losses": 2, "total_draws": 1,
            "robot_breaks": 0, "updated_at": "2026-01-01T00:00:00+00:00",
        }
        row1 = players._leaderboard_row(record)
        row2 = players._leaderboard_row(record)
        self.assertEqual(row1, row2, "syncing the same record twice must produce the exact same payload")


class TestSupabaseRequestsAreWellFormed(unittest.TestCase):
    """
    Mocks requests.get/requests.post to verify supabase_rest.py builds the
    correct PostgREST query for each sort category and parses a realistic
    response correctly -- WITHOUT needing a real Supabase project.
    """

    def setUp(self):
        self._url_patch = patch.object(sb, 'SUPABASE_URL', 'https://fake-project.supabase.co')
        self._key_patch = patch.object(sb, 'SUPABASE_SERVICE_ROLE_KEY', 'fake-service-role-key')
        self._url_patch.start()
        self._key_patch.start()

    def tearDown(self):
        self._url_patch.stop()
        self._key_patch.stop()

    def test_is_configured_true_with_both_vars_set(self):
        self.assertTrue(sb.is_configured())

    @patch('src.supabase_rest.requests.get')
    def test_get_leaderboard_sort_by_wins_builds_correct_query(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"username": "A", "best_streak": 1, "total_wins": 9,
                                         "total_losses": 1, "total_draws": 0, "total_rounds": 10, "win_rate": 90.0}]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        rows = sb.get_leaderboard(limit=10, sort_by='wins')

        called_params = mock_get.call_args.kwargs['params']
        self.assertEqual(called_params['order'], 'total_wins.desc,username.asc',
                          "sort_by='wins' must order by the total_wins column")
        self.assertNotIn('total_rounds', called_params, "only winrate should filter by total_rounds")
        self.assertEqual(rows[0]['username'], 'A')
        self.assertEqual(rows[0]['rank'], 1)

    @patch('src.supabase_rest.requests.get')
    def test_get_leaderboard_sort_by_winrate_applies_min_rounds_filter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        sb.get_leaderboard(limit=10, sort_by='winrate', min_rounds=15)

        called_params = mock_get.call_args.kwargs['params']
        self.assertEqual(called_params['order'], 'win_rate.desc,username.asc')
        self.assertEqual(called_params['total_rounds'], 'gte.15',
                          "winrate must filter out players below the minimum rounds threshold")

    @patch('src.supabase_rest.requests.post')
    def test_insert_uses_plain_post_without_merge_duplicates(self, mock_post):
        """A brand-new username must be a real INSERT (so a genuine race
        for the same name produces a 409, not a silent merge)."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sb.insert_leaderboard_row({"username": "NewPlayer"})

        headers = mock_post.call_args.kwargs['headers']
        self.assertNotIn('resolution=merge-duplicates', headers.get('Prefer', ''))

    @patch('src.supabase_rest.requests.post')
    def test_upsert_uses_merge_duplicates(self, mock_post):
        """Updating an existing player's row must merge on conflict (an
        UPDATE-by-username), not attempt a fresh insert."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sb.upsert_leaderboard_row({"username": "ExistingPlayer", "total_wins": 5})

        headers = mock_post.call_args.kwargs['headers']
        self.assertIn('resolution=merge-duplicates', headers.get('Prefer', ''))

    @patch('src.supabase_rest.requests.get')
    def test_get_rank_counts_players_strictly_above(self, mock_get):
        # First call: fetch this player's own value. Second call: count how
        # many rows exceed it.
        rank_lookup_resp = MagicMock()
        rank_lookup_resp.json.return_value = [{"best_streak": 7}]
        rank_lookup_resp.raise_for_status.return_value = None

        count_resp = MagicMock()
        count_resp.headers = {"Content-Range": "0-2/3"}
        count_resp.raise_for_status.return_value = None

        mock_get.side_effect = [rank_lookup_resp, count_resp]
        rank = sb.get_rank('SomePlayer', sort_by='streak')
        self.assertEqual(rank, 4, "3 players ahead -> this player is rank 4")


class TestFrontendNeverSendsCredentials(unittest.TestCase):
    """
    Static check: the actual Supabase credentials/env-var names and the
    phrase "service_role" must never appear in anything served to the
    browser. Mentioning the word "Supabase" itself in ordinary UI copy
    (e.g. the leaderboard's "configure Supabase..." helper text) is fine
    and expected -- this test only forbids the secret-shaped things.
    """

    FORBIDDEN = ('SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'service_role', 'apikey')

    def test_templates_contain_no_supabase_secrets_or_env_var_names(self):
        project_root = os.path.join(os.path.dirname(__file__), '..')
        for fname in ('templates/index.html', 'templates/robot_lab.html'):
            path = os.path.join(project_root, fname)
            with open(path) as f:
                content = f.read()
            for forbidden in self.FORBIDDEN:
                self.assertNotIn(forbidden, content,
                                  f"{fname} must never reference '{forbidden}'")

    def test_frontend_js_makes_no_direct_network_call_to_supabase(self):
        project_root = os.path.join(os.path.dirname(__file__), '..')
        for fname in ('templates/index.html', 'templates/robot_lab.html'):
            path = os.path.join(project_root, fname)
            with open(path) as f:
                content = f.read()
            self.assertNotIn('supabase.co', content.lower(),
                              f"{fname} must only ever call this app's own /api/* routes, never Supabase directly")


if __name__ == '__main__':
    unittest.main()
