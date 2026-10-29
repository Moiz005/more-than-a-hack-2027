import math
import unittest

from starter_v5.emissions import FrameEmission, frame_emission, validate_emission_stream


class EmissionTests(unittest.TestCase):
    def test_all_missing_is_neutral_and_uninformative(self):
        emission = frame_emission(0, 1)
        self.assertEqual((emission.home, emission.away, emission.dead), (1 / 3, 1 / 3, 1 / 3))
        self.assertFalse(emission.informative)

    def test_evidence_is_normalized(self):
        emission = frame_emission(3, 1, home=2, away=1, informative=True)
        self.assertEqual((emission.home, emission.away, emission.dead), (2 / 3, 1 / 3, 0))
        self.assertTrue(emission.informative)

    def test_rejects_nonfinite_or_negative_evidence(self):
        for value in (float("nan"), float("inf"), -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                frame_emission(0, 1, home=value)

    def test_rejects_invalid_probabilities(self):
        for values in ((float("nan"), 0, 0), (1.2, 0, 0), (0.2, 0.2, 0.2)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                FrameEmission(0, 1, *values, True)

    def test_stream_requires_contiguous_complete_frames(self):
        emissions = [frame_emission(i, 1, home=1, informative=True) for i in range(3)]
        self.assertEqual([item.frame for item in validate_emission_stream(emissions, 3)], [0, 1, 2])
        with self.assertRaises(ValueError):
            list(validate_emission_stream([emissions[0], emissions[2]], 2))


if __name__ == "__main__":
    unittest.main()
