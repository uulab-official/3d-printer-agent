"""Recorded-volume checks use synthetic geometry, never physical qualification."""

from copy import deepcopy
import math
import unittest

from print_agent.print_volume import review_print_volume


def coordinates(width=80, depth=18, height=12, origin=(0, 0, 0)):
    """Two opposite corners suffice for this bounding-box-only contract."""
    x, y, z = origin
    return [(x, y, z), (x + width, y + depth, z + height)]


def settings(width=100, depth=100, height=100, **extra):
    return {
        "printable_area": ["0x0", f"{width}x0", f"{width}x{depth}", f"0x{depth}"],
        "printable_height": str(height),
        **extra,
    }


class PrintVolumeTests(unittest.TestCase):
    def review(self, points=None, config=None):
        return review_print_volume(coordinates() if points is None else points,
                                   settings() if config is None else config)

    def test_rectangular_fit_reports_a_witness_without_applying_placement(self):
        result = self.review()
        self.assertEqual(result["status"], "fits")
        self.assertTrue(result["can_prepare"])
        self.assertEqual(result["scope"], "upright_bounding_box_0_90")
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["model_dimensions_mm"], [80, 18, 12])
        self.assertEqual(result["recorded_volume_mm"], [100, 100, 100])
        self.assertEqual(result["orientations"], [
            {"rotation_degrees": 0, "fits": True},
            {"rotation_degrees": 90, "fits": True},
        ])
        self.assertEqual(result["placement_mm"], [0, 0, 0])
        self.assertEqual(result["rotation_degrees"], 0)
        self.assertFalse(result["placement_applied"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["tolerance_mm"], 1e-6)
        self.assertTrue(result["limitations"])

    def test_only_ninety_degree_orientation_fits(self):
        result = self.review(config=settings(width=70, depth=100))
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["rotation_degrees"], 90)
        self.assertEqual(result["orientations"], [
            {"rotation_degrees": 0, "fits": False},
            {"rotation_degrees": 90, "fits": True},
        ])

    def test_height_overflow_is_definitive(self):
        result = self.review(config=settings(height=11))
        self.assertEqual(result["status"], "height_exceeded")
        self.assertFalse(result["can_prepare"])
        self.assertIsNone(result["placement_mm"])
        self.assertIsNone(result["rotation_degrees"])
        self.assertTrue(any(item.get("field") == "printable_height" for item in result["issues"]))
        self.assertTrue(all(item["fits"] is False for item in result["orientations"]))

    def test_height_overflow_remains_known_with_unsupported_bed_geometry(self):
        result = self.review(config={"printable_height": "11", "printable_area": ["0x0", "20x0", "0x20"]})
        self.assertEqual(result["status"], "height_exceeded")
        self.assertEqual(result["recorded_volume_mm"], [None, None, 11])

    def test_failed_checked_orientations_do_not_claim_diagonal_impossibility(self):
        for points, config in ((coordinates(110, 1, 2), settings()),
                               (coordinates(), settings(width=70, depth=10))):
            with self.subTest(points=points, config=config):
                result = self.review(points, config)
                self.assertEqual(result["status"], "needs_review")
                self.assertFalse(result["can_prepare"])
                self.assertIsNone(result["placement_mm"])
                self.assertIsNone(result["rotation_degrees"])
                self.assertTrue(all(item["fits"] is False for item in result["orientations"]))
                self.assertTrue(result["issues"])

    def test_exact_boundary_and_tolerance_are_absolute(self):
        for width, height, expected in ((100, 100, "fits"),
                                        (100.0000005, 100, "fits"),
                                        (100, 100.0000005, "fits"),
                                        (100.000002, 100, "needs_review"),
                                        (100, 100.000002, "height_exceeded")):
            with self.subTest(width=width, height=height):
                self.assertEqual(self.review(coordinates(width, 100, height))["status"], expected)

    def test_translated_negative_bed_uses_dimensions_and_candidate_coordinates(self):
        config = {"printable_area": ["-90x-30", "10x-30", "10x70", "-90x70"],
                  "printable_height": "100"}
        result = self.review(coordinates(origin=(450, -250, -12)), config)
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["model_dimensions_mm"], [80, 18, 12])
        self.assertEqual(result["recorded_volume_mm"], [100, 100, 100])
        self.assertEqual(result["placement_mm"], [-90, -30, 0])

    def test_clockwise_counterclockwise_closed_and_comma_rectangles(self):
        polygons = [
            ["100x100", "0x100", "0x0", "100x0"],
            ["0x0", "0x100", "100x100", "100x0"],
            ["0x0", "100x0", "100x100", "0x100", "0x0"],
            ["0,0", "1e2,0", "100,100", "0,100"],
        ]
        for area in polygons:
            with self.subTest(area=area):
                result = self.review(config=settings(printable_area=area))
                self.assertEqual(result["status"], "fits")
                self.assertEqual(result["recorded_volume_mm"], [100, 100, 100])

    def test_nonrectangular_or_ambiguous_polygons_cannot_pass_by_outer_bounds(self):
        polygons = [
            ["0x0", "100x0", "100x10", "10x10", "10x100", "0x100"],
            ["0x50", "50x0", "100x50", "50x100"],
            ["0x0", "100x100", "0x100", "100x0"],
            ["0x0", "100x0", "100x100", "100x0", "0x100"],
            ["0x0", "100x0", "100x100"],
            ["0x0", "100x0", "100x100", "0x100", "0x0", "0x0"],
        ]
        for area in polygons:
            with self.subTest(area=area):
                result = self.review(config=settings(printable_area=area))
                self.assertEqual(result["status"], "needs_review")
                self.assertFalse(result["can_prepare"])
                self.assertEqual(result["recorded_volume_mm"], [None, None, 100])

    def test_missing_settings_remain_unknown(self):
        cases = [({}, [None, None, None]),
                 ({"printable_height": "100"}, [None, None, 100]),
                 ({"printable_area": settings()["printable_area"]}, [100, 100, None])]
        for config, volume in cases:
            with self.subTest(config=config):
                result = self.review(config=config)
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["recorded_volume_mm"], volume)
                self.assertFalse(result["can_prepare"])

    def test_malformed_native_height_cannot_be_silently_coerced(self):
        invalid = [None, 100, True, {}, [], ["100", "200"], [100], "0", "-1",
                   "NaN", "Infinity", "1e999", "1_00", "100mm", " ", "1" * 200]
        for height in invalid:
            with self.subTest(height=height):
                result = self.review(config=settings(printable_height=height))
                self.assertEqual(result["status"], "needs_review")
                self.assertIsNone(result["recorded_volume_mm"][2])
        self.assertEqual(self.review(config=settings(printable_height=["100"]))["status"], "fits")

    def test_malformed_native_points_cannot_establish_a_rectangle(self):
        invalid = [None, "0x0,100x0,100x100,0x100", {}, [[0, 0], [100, 0], [100, 100], [0, 100]],
                   [0, 1, 2, 3], ["0x0", "Infinityx0", "100x100", "0x100"],
                   ["0x0", "1_00x0", "100x100", "0x100"],
                   ["0x0", "100x0x0", "100x100", "0x100"],
                   ["-1e308x0", "1e308x0", "1e308x100", "-1e308x100"],
                   ["0x0"] * 129]
        for area in invalid:
            with self.subTest(area=area):
                result = self.review(config=settings(printable_area=area))
                self.assertEqual(result["status"], "needs_review")
                self.assertFalse(result["can_prepare"])

    def test_no_explicit_optional_constraints_preserves_the_bounded_positive_result(self):
        config = settings(bed_exclude_area=["0x0"], extruder_printable_area=[],
                          extruder_printable_height=["0"], wrapping_exclude_area=[])
        self.assertEqual(self.review(config=config)["status"], "fits")
        self.assertEqual(self.review(config=settings(bed_exclude_area=[]))["status"], "fits")

    def test_center_exclusion_does_not_prevent_a_proven_corner_placement(self):
        config = settings(bed_exclude_area=["40x40", "60x40", "60x60", "40x60"])
        result = self.review(coordinates(30, 30, 12), config)
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["placement_mm"], [0, 0, 0])

    def test_exclusion_at_origin_requires_a_boundary_candidate(self):
        config = settings(bed_exclude_area=["0x0", "30x0", "30x100", "0x100"])
        result = self.review(coordinates(70, 100, 12), config)
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["placement_mm"], [30, 0, 0])
        self.assertEqual(result["rotation_degrees"], 0)

    def test_multiple_exclusions_require_combined_x_and_y_boundary_candidates(self):
        exclusion = ["0x0", "100x0", "100x10", "0x10",
                     "0x10", "20x10", "20x100", "0x100",
                     "70x10", "100x10", "100x100", "70x100",
                     "20x80", "70x80", "70x100", "20x100"]
        result = self.review(coordinates(50, 70, 12), settings(bed_exclude_area=exclusion))
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["placement_mm"], [20, 10, 0])

    def test_exclusions_can_allow_only_the_rotated_envelope(self):
        exclusion = ["0x0", "30x0", "30x100", "0x100"]
        result = self.review(config=settings(bed_exclude_area=exclusion))
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["rotation_degrees"], 90)
        self.assertEqual(result["placement_mm"], [30, 0, 0])

    def test_exclusion_strip_blocks_both_checked_orientations(self):
        exclusion = ["40x0", "60x0", "60x100", "40x100"]
        result = self.review(coordinates(45, 45, 12), settings(bed_exclude_area=exclusion))
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["can_prepare"])
        self.assertIsNone(result["placement_mm"])

    def test_overlapping_exclusions_are_all_respected(self):
        exclusion = ["0x0", "60x0", "60x100", "0x100",
                     "40x0", "100x0", "100x100", "40x100"]
        result = self.review(coordinates(5, 5, 12), settings(bed_exclude_area=exclusion))
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["can_prepare"])

    def test_exclusions_outside_the_bed_do_not_create_false_obstacles(self):
        exclusion = ["-50x-50", "0x-50", "0x0", "-50x0",
                     "200x200", "300x200", "300x300", "200x300"]
        self.assertEqual(self.review(config=settings(bed_exclude_area=exclusion))["status"], "fits")

    def test_malformed_exclusion_groups_do_not_allow_positive_fit(self):
        rectangle = ["0x0", "10x0", "10x10", "0x10"]
        invalid = [None, "", ["1x1"], ["0x0", "0x0"], rectangle + ["0x0"],
                   ["0x0", "10x10", "0x10", "10x0"],
                   ["0x0", "10x0", "10x10", "0x9"],
                   ["0x0", "0x0", "0x0", "0x0"], rectangle * 33]
        for exclusion in invalid:
            with self.subTest(exclusion=exclusion):
                result = self.review(config=settings(bed_exclude_area=exclusion))
                self.assertEqual(result["status"], "needs_review")
                self.assertFalse(result["can_prepare"])
                self.assertTrue(any(item.get("field") == "bed_exclude_area" for item in result["issues"]))

    def test_unresolved_extra_geometry_never_yields_positive_orientation(self):
        cases = [("extruder_printable_area", ["0x0", "20x0", "20x20", "0x20"]),
                 ("extruder_printable_area", None),
                 ("extruder_printable_height", ["200"]),
                 ("extruder_printable_height", ["-1"]),
                 ("extruder_printable_height", [0]),
                 ("extruder_printable_height", ["0", "0"]),
                 ("extruder_printable_height", "0"),
                 ("wrapping_exclude_area", ["0x0"]),
                 ("wrapping_exclude_area", None)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                result = self.review(config=settings(**{field: value}))
                self.assertEqual(result["status"], "needs_review")
                self.assertFalse(result["can_prepare"])
                self.assertTrue(all(item["fits"] is False for item in result["orientations"]))
                self.assertTrue(any(item.get("field") == field for item in result["issues"]))

    def test_invalid_model_coordinates_raise_instead_of_returning_fit(self):
        invalid = [[], (), None, "not coordinates", {}, [(0, 0, 0)], [(0, 0), (10, 10)],
                   [(0, 0, 0), (10, 10, 10, 10)], [(False, 0, 0), (10, 10, 10)],
                   [("0", 0, 0), (10, 10, 10)], [(0, 0, 0), (math.nan, 10, 10)],
                   [(0, 0, 0), (math.inf, 10, 10)], [(-1e308, 0, 0), (1e308, 10, 10)],
                   [(0, 0, 0), (10, 10, 0)], [(0, 0, 0)] * 100001]
        for points in invalid:
            with self.subTest(points=str(points)[:100]), self.assertRaises(ValueError):
                review_print_volume(points, settings())

    def test_nonobject_settings_return_review_instead_of_crashing(self):
        for config in (None, [], "settings", True):
            with self.subTest(config=config):
                result = review_print_volume(coordinates(), config)
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["recorded_volume_mm"], [None, None, None])

    def test_review_does_not_mutate_or_share_inputs(self):
        points = coordinates()
        config = settings(bed_exclude_area=["0x0"])
        before = deepcopy((points, config))
        result = self.review(points, config)
        result["model_dimensions_mm"][0] = 999
        result["recorded_volume_mm"][0] = 999
        result["placement_mm"][0] = 999
        self.assertEqual((points, config), before)


if __name__ == "__main__":
    unittest.main()
