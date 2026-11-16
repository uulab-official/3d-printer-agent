"""Deterministic oracle checks for axis-aligned print-volume placement.

These synthetic integer-grid cases are not a physical printer certification.
They compare the optimized boundary-candidate search with a deliberately simple
exhaustive placement oracle, to catch false positives and false negatives.
"""
import random
import unittest

from print_agent.print_volume import _placement, review_print_volume


def exhaustive_fit(width, depth, bed, exclusions):
    """Check all integer origins in a small integer-coordinate bed."""
    left, bottom, right, top = bed
    for y in range(bottom, top - depth + 1):
        for x in range(left, right - width + 1):
            if all(
                min(x + width, ex_right) <= max(x, ex_left)
                or min(y + depth, ex_top) <= max(y, ex_bottom)
                for ex_left, ex_bottom, ex_right, ex_top in exclusions
            ):
                return True
    return False


class CandidatePlacementOracleTests(unittest.TestCase):
    def test_exclusion_placement_matches_exhaustive_integer_grid(self):
        randomizer = random.Random(20261116)
        bed = (-2, -3, 6, 5)
        for case in range(300):
            width = randomizer.randint(1, 9)
            depth = randomizer.randint(1, 9)
            exclusions = []
            for _ in range(randomizer.randint(0, 5)):
                x0 = randomizer.randint(-4, 6)
                x1 = randomizer.randint(x0 + 1, 9)
                y0 = randomizer.randint(-5, 5)
                y1 = randomizer.randint(y0 + 1, 8)
                exclusions.append((x0, y0, x1, y1))
            with self.subTest(case=case, width=width, depth=depth, exclusions=exclusions):
                placement = _placement(width, depth, bed, exclusions)
                self.assertEqual(
                    placement is not None,
                    exhaustive_fit(width, depth, bed, exclusions),
                )
                if placement is not None:
                    x, y, z = placement
                    self.assertEqual(z, 0)
                    self.assertGreaterEqual(x, bed[0])
                    self.assertGreaterEqual(y, bed[1])
                    self.assertLessEqual(x + width, bed[2])
                    self.assertLessEqual(y + depth, bed[3])
                    for x0, y0, x1, y1 in exclusions:
                        self.assertTrue(
                            min(x + width, x1) <= max(x, x0)
                            or min(y + depth, y1) <= max(y, y0)
                        )

    def test_narrow_corridor_between_exclusions_requires_exact_candidate(self):
        bed = (0, 0, 10, 10)
        exclusions = [(0, 0, 4, 10), (6, 0, 10, 10)]
        self.assertEqual(_placement(2, 10, bed, exclusions), [4, 0, 0])
        self.assertIsNone(_placement(3, 10, bed, exclusions))

    def test_height_overrun_never_becomes_a_fit_when_bed_is_large(self):
        config = {
            "printable_area": ["0x0", "500x0", "500x500", "0x500"],
            "printable_height": "9",
            "bed_exclude_area": ["0x0"],
        }
        report = review_print_volume([(0, 0, 0), (1, 1, 10)], config)
        self.assertEqual(report["status"], "height_exceeded")
        self.assertFalse(report["can_prepare"])
        self.assertIsNone(report["placement_mm"])


if __name__ == "__main__":
    unittest.main()
