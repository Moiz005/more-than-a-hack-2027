import itertools
import math
import unittest
from types import SimpleNamespace

from starter_v6.hmm import HMMConfig, decode


class DecoderTest(unittest.TestCase):
    def test_matches_exhaustive_paths(self):
        initial = (0.4, 0.4, 0.2)
        transitions = ((0.8, 0.1, 0.1), (0.1, 0.8, 0.1), (0.2, 0.2, 0.6))
        observations = [(0.8, 0.1, 0.1), (0.2, 0.7, 0.1), (0.05, 0.05, 0.9)]
        emissions = [SimpleNamespace(home=h, away=a, dead=d) for h, a, d in observations]
        labels, score = decode(emissions, initial, transitions)
        def value(path):
            return (math.log(initial[path[0]]) + sum(math.log(observations[t][s]) for t, s in enumerate(path))
                    + sum(math.log(transitions[path[t-1]][path[t]]) for t in range(1, len(path))))
        best = max(itertools.product(range(3), repeat=3), key=value)
        self.assertEqual(labels, ['HAD'[i] for i in best])
        self.assertAlmostEqual(score, value(best))

    def test_matches_exhaustive_oracle_across_many_short_sequences(self):
        patterns = ((0.75, 0.20, 0.05), (0.15, 0.75, 0.10), (0.10, 0.10, 0.80))
        initial = (0.43, 0.39, 0.18)
        transitions = ((0.91, 0.06, 0.03), (0.05, 0.92, 0.03), (0.12, 0.12, 0.76))
        checked = 0
        for length in range(1, 5):
            for observation in itertools.product(patterns, repeat=length):
                emissions = [SimpleNamespace(home=h, away=a, dead=d) for h, a, d in observation]
                labels, score = decode(emissions, initial, transitions)

                def path_score(path):
                    return (math.log(initial[path[0]])
                            + sum(math.log(observation[t][state]) for t, state in enumerate(path))
                            + sum(math.log(transitions[path[t - 1]][path[t]]) for t in range(1, length)))

                candidates = itertools.product(range(3), repeat=length)
                best = max(candidates, key=path_score)
                self.assertEqual(labels, ["HAD"[state] for state in best])
                self.assertAlmostEqual(score, path_score(best), places=10)
                checked += 1
        self.assertEqual(checked, 120)

    def test_invalid_emission_is_rejected(self):
        with self.assertRaises(ValueError):
            decode([SimpleNamespace(home=float('nan'), away=0, dead=1)], (0.4, 0.4, 0.2), ((0.8, 0.1, 0.1), (0.1, 0.8, 0.1), (0.2, 0.2, 0.6)))

    def test_weak_opponent_touch_does_not_force_turnover(self):
        cfg = HMMConfig((0.98, 0.01, 0.01), ((0.97, 0.01, 0.02), (0.01, 0.97, 0.02), (0.05, 0.05, 0.90)))
        seq = [(0.96, 0.02, 0.02), (0.50, 0.48, 0.02), (0.96, 0.02, 0.02)]
        labels, _ = decode([SimpleNamespace(home=h, away=a, dead=d) for h,a,d in seq], config=cfg)
        self.assertEqual(labels, ['H', 'H', 'H'])

    def test_h_d_h_keeps_stoppage_and_splits_spells(self):
        cfg = HMMConfig((0.98, 0.01, 0.01), ((0.97, 0.01, 0.02), (0.01, 0.97, 0.02), (0.01, 0.01, 0.98)))
        seq = [(0.98, 0.01, 0.01)] * 3 + [(0.01, 0.01, 0.98)] * 2 + [(0.98, 0.01, 0.01)] * 3
        labels, _ = decode([SimpleNamespace(home=h, away=a, dead=d) for h,a,d in seq], config=cfg)
        self.assertEqual(labels, ['H']*3 + ['D']*2 + ['H']*3)

    def test_missing_ball_neutral_evidence_does_not_create_dead_ball(self):
        cfg = HMMConfig((0.98, 0.01, 0.01), ((0.97, 0.01, 0.02), (0.01, 0.97, 0.02), (0.025, 0.025, 0.95)))
        seq = [(0.98, 0.01, 0.01), (1 / 3, 1 / 3, 1 / 3), (0.98, 0.01, 0.01)]
        labels, _ = decode([SimpleNamespace(home=h, away=a, dead=d) for h, a, d in seq], config=cfg)
        self.assertEqual(labels, ["H", "H", "H"])

    def test_uniform_uninformative_emissions_are_neutral_and_ties_are_deterministic(self):
        cfg = HMMConfig()
        neutral = [SimpleNamespace(home=1 / 3, away=1 / 3, dead=1 / 3) for _ in range(4)]
        first, _ = decode(neutral, config=cfg)
        second, _ = decode(neutral, config=cfg)
        self.assertEqual(first, ["H"] * 4)
        self.assertEqual(first, second)

    def test_strong_single_frame_dead_ball_and_direct_turnover_survive(self):
        cfg = HMMConfig()
        dead_values = [(0.98, 0.01, 0.01), (0.00005, 0.00005, 0.9999), (0.98, 0.01, 0.01)]
        dead, _ = decode([SimpleNamespace(home=h, away=a, dead=d) for h, a, d in dead_values], config=cfg)
        self.assertEqual(dead, ["H", "D", "H"])
        turnover_values = [(0.98, 0.01, 0.01), (0.01, 0.98, 0.01), (0.01, 0.98, 0.01)]
        turnover, _ = decode([SimpleNamespace(home=h, away=a, dead=d) for h, a, d in turnover_values], config=cfg)
        self.assertEqual(turnover, ["H", "A", "A"])
