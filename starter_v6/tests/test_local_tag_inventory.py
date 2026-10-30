"""Optional local-asset regression check; emits aggregate counts only."""

import unittest
from collections import Counter
from pathlib import Path

from starter_v5.ingestion import parse_smart_tagging


TAG_PATH = Path(__file__).resolve().parents[2] / "data" / "tactical" / "BAR-ATH_tactical_smart_tagging.xml"


@unittest.skipUnless(TAG_PATH.is_file(), "authorized local Smart Tagging asset is unavailable")
class LocalTagInventoryTests(unittest.TestCase):
    def test_published_inventory_count_and_normalized_team_totals(self):
        events = parse_smart_tagging(TAG_PATH)
        counts = Counter(event.team or "UNKNOWN" for event in events)
        self.assertEqual(len(events), 638)
        self.assertEqual(counts, {"H": 314, "A": 288, "N/A": 36})


if __name__ == "__main__":
    unittest.main()
