import unittest

from starter_v6.intervals import intervals


class IntervalTests(unittest.TestCase):
    def test_empty_single_state_direct_turnover_and_one_frame_stoppage(self):
        self.assertEqual(intervals("", []), [])
        self.assertEqual(intervals("H", [1]), [("H", 1, 0, 1)])
        self.assertEqual(intervals("HAD", [1, 1, 1]), [
            ("H", 1, 0, 1), ("A", 1, 1, 2), ("D", 1, 2, 3),
        ])

    def test_stoppage_and_half_reset_split_spells(self):
        self.assertEqual(intervals('HDHHXH', [1, 1, 1, 2, 0, 2]), [
            ('H', 1, 0, 1), ('D', 1, 1, 2), ('H', 1, 2, 3),
            ('H', 2, 3, 4), ('H', 2, 5, 6)])

    def test_misalignment_rejected(self):
        with self.assertRaises(ValueError):
            intervals('H', [])
