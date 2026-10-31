"""S1-S7: official scorer semantics on invented labels only; no CSV is read."""
import unittest

from evaluation import possession_metrics as metrics


def codes(labels):
    return metrics.label_codes(list(labels))


def spells(labels, reference=None):
    return metrics.possession_spells(codes(labels), metrics.valid_runs(codes(reference or labels)))


class ReleaseSpellSemanticsTests(unittest.TestCase):
    def test_S1_same_team_separated_by_dead(self):
        self.assertEqual(spells('HHHDDHHH'), [(0, 3, metrics.H), (5, 8, metrics.H)])

    def test_S2_false_dead_fragments_one_spell(self):
        gt, pred = codes('HHHHHHHH'), codes('HHHDDHHH')
        result = metrics.spell_scores(gt, pred, metrics.valid_runs(gt))
        self.assertEqual((result['n_gt'], result['n_pred']), (1, 2))
        self.assertEqual([result['per_iou'][t]['n_matched'] for t in metrics.SPELL_IOUS],
                         [1, 0, 0, 0, 0])

    def test_S3_missing_dead_merges_two_spells(self):
        gt, pred = codes('HHHDDHHH'), codes('HHHHHHHH')
        result = metrics.spell_scores(gt, pred, metrics.valid_runs(gt))
        self.assertEqual((result['n_gt'], result['n_pred']), (2, 1))
        self.assertEqual([result['per_iou'][t]['n_matched'] for t in metrics.SPELL_IOUS],
                         [1, 0, 0, 0, 0])

    def test_S4_direct_turnover_needs_no_dead(self):
        self.assertEqual(spells('HHHAAA'), [(0, 3, metrics.H), (3, 6, metrics.A)])

    def test_S5_abstentions_charge_frames_but_fill_temporally_per_valid_run(self):
        gt, pred = codes('HHHAAA'), codes('HXXAXX')
        runs = metrics.valid_runs(gt)
        cm = metrics.scored_confusion(metrics.confusion(gt, pred))
        self.assertAlmostEqual(metrics.macro_f1(cm), 1 / 3)
        perfect = metrics.scored_confusion(metrics.confusion(gt, gt))
        self.assertAlmostEqual(metrics.macro_f1(perfect), 2 / 3)  # absent D has F1=0
        filled = metrics.fill_abstentions(pred, runs)
        self.assertEqual(filled.tolist(), gt.tolist())
        self.assertEqual(metrics.spell_scores(gt, filled, runs)['mean_f1'], 1.)
        self.assertEqual(metrics.fill_abstentions(codes('XXHXXX'), runs).tolist(),
                         codes('HHHHHH').tolist())
        gt, pred = codes('HHHXXAAA'), codes('HXXXXXXA')
        self.assertEqual(metrics.fill_abstentions(pred, metrics.valid_runs(gt)).tolist(),
                         gt.tolist())
        all_x = codes('XXXXXXXX')
        filled = metrics.fill_abstentions(all_x, metrics.valid_runs(gt))
        self.assertEqual(filled.tolist(), all_x.tolist())
        self.assertEqual(metrics.possession_spells(filled, metrics.valid_runs(gt)), [])
        # Prediction outside the reference grading mask cannot add frame errors.
        a = metrics.scored_confusion(metrics.confusion(gt, gt))
        b = metrics.scored_confusion(metrics.confusion(gt, codes('HHHADAAA')))
        self.assertEqual(a.tolist(), b.tolist())

    def test_S6_all_thresholds_same_team_iou_and_one_to_one(self):
        self.assertEqual(metrics.SPELL_IOUS, (.3, .4, .5, .6, .7))
        gt = [(0, 8, metrics.H)]
        pred = [(0, 3, metrics.H), (5, 8, metrics.H), (0, 8, metrics.A)]
        overlap = metrics.spell_overlaps(gt, pred)
        self.assertEqual(overlap, [(3 / 8, 0, 0), (3 / 8, 0, 1)])
        for threshold in metrics.SPELL_IOUS:
            self.assertEqual(metrics.match_spells(overlap, 1, 3, threshold),
                             (1, 2, 0) if threshold == .3 else (0, 3, 1))
        # Two reference spells cannot both claim the same merged prediction.
        gt = [(0, 3, metrics.H), (5, 8, metrics.H)]
        pred = [(0, 8, metrics.H)]
        self.assertEqual(metrics.match_spells(metrics.spell_overlaps(gt, pred), 2, 1, .3),
                         (1, 0, 1))

    def test_S7_grading_gaps_split_halves_and_graded_dead_is_retained(self):
        self.assertEqual(spells('HHXXHH'), [(0, 2, metrics.H), (4, 6, metrics.H)])
        gt = codes('DDXXDD')
        runs = metrics.valid_runs(gt)
        self.assertEqual(runs, [(0, 2), (4, 6)])
        self.assertEqual(metrics.fill_abstentions(gt, runs).tolist(), gt.tolist())
        self.assertEqual(metrics.segments(gt, runs),
                         [(0, 2, metrics.D), (4, 6, metrics.D)])


if __name__ == '__main__':
    unittest.main()
