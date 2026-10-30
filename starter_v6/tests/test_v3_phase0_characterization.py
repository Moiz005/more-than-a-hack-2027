"""Exact Phase 0 invented fixture, retained as the Phase 1 regression."""
from dataclasses import replace
import unittest

from starter_v6.hmm import HMMConfig, decode
from starter_v6.inference import iter_infer_e02
from starter_v6.pipeline import RuntimeRestartActionDetector, restart_frame_mask
from starter_v6.possession import FrameEvidence
from starter_v6.synthetic import tag_event


def overlong_tag_trace():
    mask = restart_frame_mask([tag_event('SET PIECES', 0, 9, tag_type='Free Kick')], 9)
    detector = RuntimeRestartActionDetector()
    motion = [(10., .1)]*3 + [(10.3, 2.), (10.6, 2.)] + [(10.6, .1)]*4
    frames = [detector.observe(FrameEvidence(i, 1, (x, 10.), (), speed, bool(mask[i])))
              for i, (x, speed) in enumerate(motion)]
    results = list(iter_infer_e02(frames))
    labels, _ = decode([r.emission for r in results], config=HMMConfig())
    return frames, results, ''.join(labels)


class V3Phase0Characterization(unittest.TestCase):
    def test_baseline_false_second_dead_interval_and_redundant_restart(self):
        frames, results, labels = overlong_tag_trace()
        self.assertEqual(labels, 'DDDHHHHHH')
        self.assertEqual(frames[3].restart_action, 'restart_delivery')
        self.assertTrue(all(f.restart_action is None for f in frames[4:]))
        self.assertTrue(all(f.restart_context_consumed for f in frames[3:]))
        self.assertEqual(results[5].inference.dead_ball_evidence.cues, ())
        self.assertFalse(results[5].inference.dead_ball_evidence.confirmed)
        self.assertFalse(results[6].inference.dead_ball_evidence.confirmed)
        self.assertAlmostEqual(results[6].emission.dead, 0.)
        disabled = list(iter_infer_e02(replace(f, restart_action=None) for f in frames))
        self.assertEqual([r.emission for r in results], [r.emission for r in disabled])

    def test_desired_live_return_consumes_old_restart_context(self):
        # Intended synthetic semantics: no new stoppage occurs after delivery.
        self.assertEqual(overlong_tag_trace()[2], 'DDDHHHHHH')
