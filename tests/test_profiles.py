"""Contract examples use synthetic settings, never printing recommendations."""

from copy import deepcopy
import json
import unittest

from print_agent import profiles as profile_api


def fixture_setup():
    return {
        "printer_model": "Fixture Printer",
        "printer_preset": "Fixture Printer 0.4 nozzle",
        "nozzle_diameter": 0.4,
        "plate_type": "Textured PEI Plate",
        "extruder": "main_standard",
        "feed_mode": "external_spool",
        "material_id": "fixture:pla-basic",
        "material_identity_status": "exact",
    }


def fixture_profile():
    return {
        "id": "synthetic-profile",
        "settings": {
            "type": "filament",
            "name": "Synthetic contract fixture; not a recommendation",
            "compatible_printers": ["Fixture Printer 0.4 nozzle"],
            "nozzle_temperature": ["205"],
            "nozzle_temperature_initial_layer": ["205"],
            "filament_flow_ratio": ["0.98"],
            "filament_max_volumetric_speed": ["12"],
            "textured_plate_temp": ["55"],
            "textured_plate_temp_initial_layer": ["55"],
        },
        "scope": {
            key: value for key, value in fixture_setup().items()
            if key != "material_identity_status"
        },
        "source": {
            "authority": "manufacturer",
            "publisher": "Synthetic fixture publisher",
            "url": "https://example.invalid/fixture",
            "retrieved_at": "2026-11-12",
        },
    }


def calibration_records():
    return [
        {"kind": "flow_dynamics", "value": 0.025, "validity": "valid"},
        {"kind": "flow_ratio", "value": 0.98, "validity": "valid"},
        {"kind": "max_volumetric_speed", "value": 12, "validity": "valid"},
    ]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.api = profile_api

    def test_matching_profile_prepares_without_claiming_physical_validation(self):
        profile, setup = fixture_profile(), fixture_setup()
        original = deepcopy(profile)
        result = self.api.evaluate_profile(profile, setup)
        self.assertEqual(result.get("decision"), "ready_to_prepare")
        self.assertEqual(result.get("compatibility"), "supported")
        self.assertTrue(result.get("can_prepare_profile"))
        self.assertEqual(result.get("selected_profile_id"), "synthetic-profile")
        self.assertEqual(result.get("source_authority"), "manufacturer")
        self.assertEqual(result.get("validation_status"), "unverified")
        self.assertEqual(result.get("effective_settings"), original["settings"])
        self.assertEqual(result.get("missing_fields"), [])
        self.assertTrue(result.get("warnings"))
        result["effective_settings"]["nozzle_temperature"][0] = "changed"
        self.assertEqual(profile, original)

    def test_reported_measurement_requires_matching_complete_fingerprint(self):
        for fingerprint, expected in [
            (fixture_setup(), "reported_validated"),
            ({**fixture_setup(), "nozzle_diameter": 0.6}, "stale"),
            ({"printer_model": "Fixture Printer"}, "unverified"),
            ("opaque-unverifiable-hash", "unverified"),
        ]:
            with self.subTest(expected=expected, fingerprint=fingerprint):
                profile = fixture_profile()
                profile["validation"] = {
                    "status": "measured_on_matching_setup",
                    "setup_fingerprint": fingerprint,
                }
                result = self.api.evaluate_profile(profile, fixture_setup())
                self.assertEqual(result.get("validation_status"), expected)
                if expected == "stale":
                    self.assertFalse(result.get("can_prepare_profile"))
                    self.assertTrue(result.get("calibration_actions"))

    def test_ambiguous_material_identity_never_selects_a_product(self):
        for status in ("ambiguous", "unknown", "", "almost_exact"):
            with self.subTest(status=status):
                setup = {**fixture_setup(), "material_identity_status": status}
                result = self.api.evaluate_profile(fixture_profile(), setup)
                self.assertEqual(result.get("decision"), "needs_input")
                self.assertIsNone(result.get("selected_profile_id"))
                self.assertFalse(result.get("can_prepare_profile"))
                self.assertIn("material_identity_status", result.get("missing_fields", []))

    def test_explicit_scope_mismatches_block_without_material_fuzzy_matching(self):
        mismatches = {
            "material_id": "fixture:pla-cf",
            "printer_model": "Another Fixture Printer",
            "nozzle_diameter": 0.6,
            "plate_type": "Smooth PEI Plate",
            "extruder": "auxiliary_high_flow",
            "feed_mode": "automatic_feeder",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                setup = {**fixture_setup(), field: value}
                result = self.api.evaluate_profile(fixture_profile(), setup)
                self.assertEqual(result.get("decision"), "blocked")
                self.assertEqual(result.get("compatibility"), "unsupported")
                self.assertFalse(result.get("can_prepare_profile"))
        profile = fixture_profile()
        profile["settings"]["textured_plate_temp"] = ["0"]
        result = self.api.evaluate_profile(profile, fixture_setup())
        self.assertEqual(result.get("decision"), "blocked")
        self.assertEqual(result.get("compatibility"), "unsupported")

    def test_compatible_printers_requires_exact_match_not_name_similarity(self):
        profile = fixture_profile()
        profile["settings"]["compatible_printers"] = ["Fixture Printer 0.4"]
        result = self.api.evaluate_profile(profile, fixture_setup())
        self.assertEqual(result.get("decision"), "blocked")
        self.assertIn("PRINTER_PRESET_MISMATCH", {r["code"] for r in result["reasons"]})
        profile["settings"]["compatible_printers"] = []
        result = self.api.evaluate_profile(profile, fixture_setup())
        self.assertEqual(result.get("decision"), "ready_to_prepare")
        profile.pop("scope")
        result = self.api.evaluate_profile(profile, fixture_setup())
        self.assertEqual(result.get("compatibility"), "unknown")
        self.assertFalse(result.get("can_prepare_profile"))

    def test_plain_bambu_profile_does_not_prove_exact_product_identity(self):
        raw = fixture_profile()["settings"]
        raw["filament_type"] = ["PLA"]
        raw["filament_id"] = "generic-material-id"
        result = self.api.evaluate_profile(raw, fixture_setup())
        self.assertEqual(result.get("decision"), "needs_evidence")
        self.assertEqual(result.get("compatibility"), "unknown")
        self.assertIn("scope.material_id", result.get("missing_fields", []))
        self.assertEqual(result.get("effective_settings"), raw)

    def test_unresolved_inheritance_never_becomes_a_full_effective_config(self):
        for key, value in (("inherits", "Parent profile"), ("include", ["Base template"])):
            with self.subTest(key=key):
                profile = fixture_profile()
                profile["settings"][key] = value
                result = self.api.evaluate_profile(profile, fixture_setup())
                self.assertEqual(result.get("decision"), "needs_evidence")
                self.assertFalse(result.get("can_prepare_profile"))
                self.assertIn("UNRESOLVED_INHERITANCE", {r["code"] for r in result["reasons"]})
                self.assertEqual(result["effective_settings"][key], value)

    def test_missing_setup_and_missing_scope_have_different_remediation(self):
        setup = fixture_setup()
        setup["plate_type"] = ""
        result = self.api.evaluate_profile(fixture_profile(), setup)
        self.assertEqual(result.get("decision"), "needs_input")
        self.assertIn("plate_type", result.get("missing_fields", []))
        profile = fixture_profile()
        del profile["scope"]["extruder"]
        result = self.api.evaluate_profile(profile, fixture_setup())
        self.assertEqual(result.get("decision"), "needs_evidence")
        self.assertIn("scope.extruder", result.get("missing_fields", []))

    def test_invalid_numbers_are_blocked_and_nonfinite_reports_are_json_safe(self):
        cases = [
            ("nozzle_temperature", [float("nan")]),
            ("filament_flow_ratio", ["Infinity"]),
            ("filament_max_volumetric_speed", ["-inf"]),
            ("vendor_extension", {"data": [float("inf")]}),
            ("filament_flow_ratio", [True]),
            ("nozzle_temperature", ["-20"]),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                profile = fixture_profile()
                profile["settings"][field] = value
                result = self.api.evaluate_profile(profile, fixture_setup())
                self.assertEqual(result.get("decision"), "blocked")
                self.assertFalse(result.get("can_prepare_profile"))
                json.dumps(result, allow_nan=False)
                if field == "vendor_extension":
                    self.assertEqual(result["effective_settings"][field], {"data": ["Infinity"]})
                    self.assertTrue(any("NONFINITE" in warning for warning in result["warnings"]))

    def test_missing_or_empty_flow_ratio_is_not_replaced_by_k_or_mvs(self):
        for replacement in (None, [], "", ["automatic"], ["0.98", "0.99"]):
            with self.subTest(replacement=replacement):
                profile = fixture_profile()
                profile["settings"]["filament_flow_ratio"] = replacement
                profile["settings"]["pressure_advance_k"] = ["0.025"]
                result = self.api.evaluate_profile(profile, fixture_setup())
                self.assertEqual(result.get("decision"), "needs_evidence")
                self.assertIn("settings.filament_flow_ratio", result.get("missing_fields", []))
                self.assertEqual(result["effective_settings"]["filament_max_volumetric_speed"], ["12"])
                self.assertEqual(result["effective_settings"]["pressure_advance_k"], ["0.025"])

    def test_unknown_fields_are_preserved_but_execution_fields_require_evidence(self):
        for field, expected in (("vendor_notes", "ready_to_prepare"), ("experimental_nozzle_temperature", "needs_evidence")):
            with self.subTest(field=field):
                profile = fixture_profile()
                profile["settings"][field] = {"opaque": "vendor value"}
                result = self.api.evaluate_profile(profile, fixture_setup())
                self.assertEqual(result.get("decision"), expected)
                self.assertEqual(result["effective_settings"][field], {"opaque": "vendor value"})
                self.assertTrue(any("FIELD_NOT_VALIDATED" in w for w in result["warnings"]))

    def test_empty_settings_never_claim_preparation_and_invalid_shape_is_rejected(self):
        profile = fixture_profile()
        profile["settings"] = {}
        result = self.api.evaluate_profile(profile, fixture_setup())
        self.assertEqual(result.get("decision"), "needs_evidence")
        self.assertFalse(result.get("can_prepare_profile"))
        for invalid in (None, [], {"settings": []}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.api.evaluate_profile(invalid, fixture_setup())
        setup = {**fixture_setup(), "plate_type": ["Textured PEI Plate"]}
        result = self.api.evaluate_profile(fixture_profile(), setup)
        self.assertEqual(result.get("decision"), "blocked")


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.api = profile_api

    def test_temperature_and_mvs_changes_stale_k_without_overwriting_distinct_values(self):
        for changes in (
            {"nozzle_temperature": {"before": 205, "after": 215}},
            {"filament_max_volumetric_speed": 14},
        ):
            with self.subTest(changes=changes):
                records = calibration_records()
                original = deepcopy(records)
                result = self.api.review_calibrations(records, changes)
                self.assertEqual(len(result), 3)
                self.assertEqual(result[0]["validity"], "stale")
                self.assertEqual([row["value"] for row in result], [0.025, 0.98, 12])
                self.assertEqual(records, original)
                self.assertTrue(result[0].get("review_reasons"))

    def test_hardware_changes_recheck_all_while_plate_infill_and_noop_preserve_k(self):
        for field in ("nozzle_diameter", "hotend", "material_id"):
            with self.subTest(field=field):
                result = self.api.review_calibrations(calibration_records(), {field: "changed"})
                self.assertEqual([r["validity"] for r in result], ["stale", "stale", "stale"])
        for changes in (
            {"plate_type": "different plate"},
            {"infill_density": 25},
            {"nozzle_temperature": {"before": 205, "after": 205}},
        ):
            with self.subTest(changes=changes):
                result = self.api.review_calibrations(calibration_records(), changes)
                self.assertEqual([r["validity"] for r in result], ["valid", "valid", "valid"])

    def test_unknown_or_invalid_calibrations_are_not_promoted_and_custom_dependencies_work(self):
        records = [
            {"kind": "unrecognized", "value": 8, "validity": "valid"},
            {"kind": "flow_ratio", "value": float("inf"), "validity": "valid"},
            {"kind": "flow_dynamics", "value": 0.025, "validity": "stale"},
            {"kind": "flow_dynamics", "value": 0.025, "validity": "valid", "dependencies": ["feed_mode"]},
            {"kind": [], "value": 8, "validity": "valid"},
        ]
        result = self.api.review_calibrations(records, {"feed_mode": "changed"})
        self.assertEqual([r["validity"] for r in result], ["unknown", "unknown", "stale", "stale", "unknown"])
        self.assertEqual(result[0]["value"], 8)


if __name__ == "__main__":
    unittest.main()
