"""Invented streams through the production E02 emissions and E04 decoder."""
from dataclasses import replace
import unittest

from starter_v6.features import E02Config
from starter_v6.hmm import HMMConfig, decode
from starter_v6.inference import iter_infer_e02
from starter_v6.possession import FrameEvidence, PlayerEvidence, PossessionConfig, possession_spells, iter_raw_play_state


def frame(i, kind, half=1):
    players = (PlayerEvidence('H', 10.1, 10., 1.), PlayerEvidence('A', 18., 10., 1.))
    if kind == 'missing':
        return FrameEvidence(i, half, None, ())
    if kind == 'stop':
        return FrameEvidence(i, half, (10., 10.), (), .1, True)
    return FrameEvidence(i, half, (10., 10.), players,
                         .1 if kind == 'keeper' else 1.,
                         restart_action='restart_delivery' if kind == 'restart' else None)


def run(kinds, window=25, halves=None):
    frames = [frame(i, k, halves[i] if halves else 1) for i, k in enumerate(kinds)]
    results = list(iter_infer_e02(frames, PossessionConfig(deadball_persistence_frames=window),
                                E02Config(quality_reference_players=2, low_player_count=1)))
    labels = ['X'] * len(results)
    for half in (1, 2):
        indices = [i for i, r in enumerate(results) if r.emission.half == half]
        decoded, _ = decode([results[i].emission for i in indices], config=HMMConfig())
        for i, label in zip(indices, decoded):
            labels[i] = label
    return results, labels


class DeadBallPersistenceTests(unittest.TestCase):
    def test_a_causal_stoppage_gap_restart_two_home_spells(self):
        kinds = ['live']*4 + ['stop']*3 + ['missing']*3 + ['restart'] + ['live']*4
        on, labels = run(kinds)
        off, old = run(kinds, 0)
        self.assertEqual(labels, ['H']*4 + ['D']*6 + ['H']*5)
        self.assertEqual(old, ['H']*4 + ['D']*3 + ['H']*8)
        self.assertEqual(len(possession_spells(labels)), 2)
        for a, b in zip(on[7:10], off[7:10]):
            self.assertGreater(a.emission.dead, b.emission.dead)
            self.assertLess(a.emission.dead, 1.)
            self.assertFalse(a.inference.dead_ball_evidence.confirmed)
            self.assertIn('confirmed_stoppage_memory', a.inference.dead_ball_evidence.source)

    def test_b_live_missing_does_not_seed_memory(self):
        kinds = ['live']*4 + ['missing']*30 + ['live']*4
        on, labels = run(kinds)
        off, old = run(kinds, 0)
        self.assertEqual([r.emission for r in on], [r.emission for r in off])
        self.assertEqual(labels, old)
        self.assertNotIn('D', labels)

    def test_c_expiry_is_neutral_and_does_not_reconfirm_itself(self):
        rows, _ = run(['stop']*3 + ['missing']*60, 3)
        scores = [r.emission.dead for r in rows[3:6]]
        self.assertTrue(all(a > b for a, b in zip(scores, scores[1:])))
        for r in rows[6:]:
            self.assertAlmostEqual(r.emission.dead, 1/3)
            self.assertAlmostEqual(r.emission.home, 1/3)
            self.assertFalse(r.inference.dead_ball_evidence.confirmed)

    def test_d_live_motion_retires_memory_before_next_gap(self):
        rows, _ = run(['stop']*3 + ['missing']*2 + ['live'] + ['missing']*2)
        self.assertTrue(all(r.emission.dead == 0 for r in rows[5:]))

    def test_e_restart_retires_memory_immediately(self):
        rows, _ = run(['stop']*3 + ['missing']*2 + ['restart'] + ['missing']*2)
        self.assertEqual(rows[5].inference.dead_ball_evidence.event_context, 'restart_action')
        self.assertTrue(all(r.emission.dead == 0 for r in rows[5:]))

    def test_f_goalkeeper_live_gap_does_not_start_stoppage(self):
        rows, labels = run(['keeper']*4 + ['missing']*4 + ['keeper']*4)
        self.assertNotIn('D', labels)
        self.assertTrue(all(r.emission.dead == 0 for r in rows))

    def test_g_half_and_ungraded_reset(self):
        rows, _ = run(['stop']*3 + ['missing']*4, halves=[1,1,1,0,2,2,2])
        self.assertTrue(all(r.emission.dead == 0 for r in rows[3:]))

    def test_h_strong_control_retires_memory_even_if_ball_speed_missing(self):
        fs = [frame(i, k) for i, k in enumerate(['stop']*3 + ['missing']*2 + ['live','missing'])]
        fs[5] = replace(fs[5], ball_speed_mps=None)
        rows = list(iter_infer_e02(fs, PossessionConfig(),
                    E02Config(quality_reference_players=2, low_player_count=1)))
        self.assertTrue(all(r.emission.dead == 0 for r in rows[5:]))

    def test_unconfirmed_cue_cannot_seed_persistence(self):
        rows, _ = run(['stop'] + ['missing']*5)
        self.assertTrue(all(r.emission.dead == 0 for r in rows[1:]))

    def test_window_validation(self):
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                PossessionConfig(deadball_persistence_frames=value)

    def test_boundary_memory_expires_even_when_disappearance_cue_would_recur(self):
        fs = [FrameEvidence(0, 1, (-1., 10.), ())] + [frame(i, 'missing') for i in range(1, 65)]
        rows = list(iter_infer_e02(fs, PossessionConfig(deadball_persistence_frames=3)))
        self.assertGreater(rows[1].emission.dead, 1/3)
        self.assertTrue(all(abs(r.emission.dead - 1/3) < 1e-12 for r in rows[4:]))

    def test_bad_jump_does_not_retire_memory_or_refresh_its_age(self):
        fs = [frame(i, k) for i, k in enumerate(['stop']*3 + ['live','missing'])]
        fs[3] = replace(fs[3], ball_xy=(80., 40.))
        rows = list(iter_infer_e02(fs))
        self.assertTrue(rows[3].features.quality.implausible_ball_jump)
        self.assertIn('confirmed_stoppage_memory', rows[4].inference.dead_ball_evidence.source)

    def test_raw_stream_shares_memory_policy(self):
        fs = [frame(i,k) for i,k in enumerate(['stop']*3 + ['missing']*4)]
        cfg = PossessionConfig(deadball_persistence_frames=3)
        raw = list(iter_raw_play_state(fs,cfg))
        prod = list(iter_infer_e02(fs,cfg))
        self.assertEqual([r.dead_ball_evidence for r in raw[3:]],
                         [r.inference.dead_ball_evidence for r in prod[3:]])

    def test_prespecified_window_grid(self):
        for window in (1, 3, 25):
            rows, _ = run(['stop']*3 + ['missing']*(window+2),window)
            self.assertTrue(all(r.emission.dead > 1/3 for r in rows[3:3+window]))
            self.assertTrue(all(abs(r.emission.dead-1/3)<1e-12 for r in rows[3+window:]))
