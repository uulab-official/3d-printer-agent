"""Synthetic preset chains exercise provenance, never printing recommendations."""
from copy import deepcopy
import hashlib
import json
import unittest

from print_agent.preset_library import resolve_profile_documents
from tests.test_profiles import fixture_profile, fixture_setup


def document(name, parent=None, **settings):
    profile = {"type": "filament", "name": name, **settings}
    if parent is not None:
        profile["inherits"] = parent
    return {"filename": name + ".json", "profile": profile}


class PresetLibraryTests(unittest.TestCase):
    def resolve(self, documents, target="Child", setup=None):
        return resolve_profile_documents(documents, target, {} if setup is None else setup)

    def assert_unresolved(self, result, status, code):
        self.assertEqual(result["status"], status)
        self.assertIn(code, {issue["code"] for issue in result["issues"]})
        self.assertIsNone(result["resolved_profile"])
        self.assertIsNone(result["review"])
        self.assertEqual(result["chain"], [])
        self.assertEqual(result["field_sources"], {})
        self.assertFalse(result["full_config"])
        self.assertFalse(result["native_verified"])

    def test_three_levels_overlay_whole_values_and_keep_assignment_history(self):
        docs = [
            document("Grandchild", "Child", nozzle_temperature=["215"], vendor_notes={"c": 3}),
            document("Base", nozzle_temperature=["200"], filament_flow_ratio=["0.98"],
                     vendor_notes={"a": 1, "b": 2}),
            document("Child", "Base", nozzle_temperature=["205", "210"], vendor_notes={"b": 4}),
        ]
        result = self.resolve(docs, "Grandchild")
        self.assertEqual(result["status"], "resolved")
        self.assertEqual([row["name"] for row in result["chain"]], ["Base", "Child", "Grandchild"])
        settings = result["resolved_profile"]["settings"]
        self.assertEqual(settings["nozzle_temperature"], ["215"])
        self.assertEqual(settings["filament_flow_ratio"], ["0.98"])
        self.assertEqual(settings["vendor_notes"], {"c": 3})
        self.assertNotIn("inherits", settings)
        self.assertEqual(result["documents"][0]["profile"]["inherits"], "Child")
        temperature = result["field_sources"]["nozzle_temperature"]
        self.assertEqual(temperature["preset_name"], "Grandchild")
        self.assertEqual(temperature["filename"], "Grandchild.json")
        self.assertFalse(temperature["inherited"])
        self.assertEqual([row["value"] for row in temperature["history"]], [
            ["200"], ["205", "210"], ["215"]
        ])
        self.assertEqual([row["preset_name"] for row in temperature["history"]], [
            "Base", "Child", "Grandchild"
        ])
        flow = result["field_sources"]["filament_flow_ratio"]
        self.assertTrue(flow["inherited"])
        self.assertEqual(flow["preset_name"], "Base")
        self.assertEqual(flow["sha256"], result["chain"][0]["sha256"])

    def test_empty_array_is_an_explicit_replacement_not_a_request_to_inherit(self):
        docs = [document("Base", compatible_printers=["Fixture Printer 0.4 nozzle"]),
                document("Child", "Base", compatible_printers=[])]
        result = self.resolve(docs)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["resolved_profile"]["settings"]["compatible_printers"], [])
        self.assertEqual(result["field_sources"]["compatible_printers"]["preset_name"], "Child")

    def test_originals_setup_and_output_components_do_not_alias(self):
        docs = [document("Base", vendor_notes={"values": [1, 2]}), document("Child", "Base")]
        setup = fixture_setup()
        original, original_setup = deepcopy(docs), deepcopy(setup)
        result = self.resolve(docs, setup=setup)
        self.assertEqual(result["setup"], setup)
        result["resolved_profile"]["settings"]["vendor_notes"]["values"].append(3)
        result["field_sources"]["vendor_notes"]["history"][0]["value"]["values"].append(4)
        result["setup"]["material_id"] = "different"
        self.assertEqual(docs, original)
        self.assertEqual(setup, original_setup)
        self.assertEqual(result["documents"][0]["profile"], original[0]["profile"])

    def test_hash_is_canonical_profile_content_not_filename_or_claim_authentication(self):
        first = {"filename": "../any/location.json", "profile": {
            "name": "한글", "type": "filament", "vendor_notes": "값"
        }}
        second = {"filename": "renamed.json", "profile": {
            "vendor_notes": "값", "type": "filament", "name": "한글"
        }}
        a, b = self.resolve([first], "한글"), self.resolve([second], "한글")
        expected = hashlib.sha256('{"name":"한글","type":"filament","vendor_notes":"값"}'.encode()).hexdigest()
        self.assertEqual(a["documents"][0]["sha256"], expected)
        self.assertEqual(a["documents"][0]["sha256"], b["documents"][0]["sha256"])
        second["profile"]["vendor_notes"] = "변경"
        self.assertNotEqual(self.resolve([second], "한글")["documents"][0]["sha256"], expected)
        self.assertFalse(a["full_config"])
        self.assertFalse(a["native_verified"])
        self.assertEqual(a["review"]["source_authority"], "unknown")

    def test_ancestor_identity_and_claims_do_not_become_target_identity_or_claims(self):
        parent = fixture_profile()
        parent["settings"].update({
            "name": "Base", "from": "system", "version": "9",
            "setting_id": "parent-id", "instantiation": "false",
            "url": "https://example.invalid/parent", "user_id": "owner",
            "base_id": "ancestor", "updated_time": "past",
            "is_custom_defined": "0", "alias": "Alias", "renamed_from": ["Older"],
            "filament_settings_id": ["Base"],
            "description": "Parent description", "filament_id": "parent-material-id"
        })
        parent["validation"] = {"status": "verified", "setup_fingerprint": fixture_setup()}
        docs = [{"filename": "base.json", "profile": parent}, document("Child", "Base")]
        result = self.resolve(docs, setup=fixture_setup())
        self.assertEqual(result["status"], "resolved")
        profile = result["resolved_profile"]
        for field in ("scope", "source", "validation", "id"):
            self.assertNotIn(field, profile)
        for field in ("from", "version", "setting_id", "instantiation", "url", "user_id",
                      "base_id", "updated_time", "is_custom_defined", "alias",
                      "renamed_from", "filament_settings_id"):
            self.assertNotIn(field, profile["settings"])
            self.assertNotIn(field, result["field_sources"])
        self.assertEqual(profile["settings"]["description"], "Parent description")
        self.assertEqual(profile["settings"]["filament_id"], "parent-material-id")
        self.assertEqual(profile["settings"]["name"], "Child")
        self.assertEqual(result["review"]["validation_status"], "unverified")
        self.assertEqual(result["review"]["source_authority"], "unknown")
        self.assertFalse(result["review"]["can_prepare_profile"])

    def test_target_envelope_claims_stay_claims_and_review_is_separate_from_resolution(self):
        parent = fixture_profile()["settings"]
        parent["name"] = "Base"
        target = fixture_profile()
        target["settings"] = {"name": "Child", "type": "filament", "inherits": "Base"}
        target["validation"] = {"status": "verified", "setup_fingerprint": fixture_setup()}
        docs = [{"filename": "base.json", "profile": parent},
                {"filename": "child.json", "profile": target}]
        result = self.resolve(docs, setup=fixture_setup())
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["review"]["decision"], "ready_to_prepare")
        self.assertEqual(result["review"]["validation_status"], "reported_validated")
        self.assertEqual(result["resolved_profile"]["source"], target["source"])
        self.assertEqual(result["resolved_profile"]["scope"], target["scope"])
        mismatch = self.resolve(docs, setup={**fixture_setup(), "nozzle_diameter": 0.6})
        self.assertEqual(mismatch["status"], "resolved")
        self.assertEqual(mismatch["review"]["decision"], "blocked")
        self.assertFalse(mismatch["native_verified"])
        self.assertFalse(mismatch["full_config"])

    def test_missing_parent_and_target_are_actionable_without_partial_effective_settings(self):
        docs = [document("Child", "Missing Base")]
        result = self.resolve(docs)
        self.assert_unresolved(result, "needs_input", "PARENT_NOT_FOUND")
        self.assertIn("Missing Base", result["issues"][0]["message"])
        self.assertEqual(result["documents"][0]["profile"], docs[0]["profile"])
        result = self.resolve(docs, "Missing Target")
        self.assert_unresolved(result, "needs_input", "TARGET_NOT_FOUND")
        self.assertIn("Missing Target", result["issues"][0]["message"])

    def test_parent_lookup_never_falls_back_to_case_filename_or_alias(self):
        parent = document("Base", alias="Alias", setting_id="setting-id",
                          filament_settings_id=["filament-name"])
        parent["filename"] = "file-id.json"
        for reference in ("base", " Base", "Base ", "Alias", "setting-id", "filament-name", "file-id.json"):
            with self.subTest(reference=reference):
                result = self.resolve([parent, document("Child", reference)])
                self.assert_unresolved(result, "needs_input", "PARENT_NOT_FOUND")

    def test_duplicate_names_block_even_when_contents_are_identical(self):
        for duplicate in (document("Base"), document("Base", vendor_notes="different")):
            with self.subTest(duplicate=duplicate):
                docs = [document("Base"), duplicate, document("Child", "Base")]
                result = self.resolve(docs)
                self.assert_unresolved(result, "blocked", "DUPLICATE_NAME")

    def test_cycles_never_emit_a_flattened_profile(self):
        for docs in (
            [document("Child", "Child")],
            [document("Child", "Base"), document("Base", "Grand"), document("Grand", "Child")],
        ):
            with self.subTest(docs=docs):
                self.assert_unresolved(self.resolve(docs), "blocked", "INHERITANCE_CYCLE")

    def test_depth_boundary_allows_32_documents_but_not_33(self):
        docs = [document("P0")]
        for index in range(1, 33):
            docs.append(document(f"P{index}", f"P{index - 1}"))
        allowed = self.resolve(docs[:32], "P31")
        self.assertEqual(allowed["status"], "resolved")
        self.assertEqual(len(allowed["chain"]), 32)
        self.assert_unresolved(self.resolve(docs, "P32"), "blocked", "INHERITANCE_DEPTH_EXCEEDED")

    def test_document_count_and_serialized_size_are_bounded(self):
        docs = [document(f"P{i}") for i in range(64)]
        self.assertEqual(self.resolve(docs, "P63")["status"], "resolved")
        with self.assertRaises(ValueError):
            self.resolve(docs + [document("extra")], "P63")
        with self.assertRaises(ValueError):
            self.resolve([document("Child", vendor_notes="가" * (1024 * 1024))])
        with self.assertRaises(ValueError):
            self.resolve([document("Child")], setup={"oversized": "x" * (2 * 1024 * 1024)})

    def test_include_is_not_treated_as_ordinary_overlay(self):
        for include in ("Other", ["Other"], {"name": "Other"}, False, 0):
            with self.subTest(include=include):
                self.assert_unresolved(self.resolve([document("Child", include=include)]),
                                       "blocked", "INCLUDE_UNSUPPORTED")
        for include in ("", []):
            with self.subTest(empty_include=include):
                result = self.resolve([document("Child", include=include)])
                self.assertEqual(result["status"], "resolved")
                self.assertNotIn("include", result["resolved_profile"]["settings"])
                self.assertEqual(result["documents"][0]["profile"]["include"], include)

    def test_non_string_inherits_is_never_interpreted_as_multiple_parents(self):
        for parent in (None, [], ["Base"], {"name": "Base"}, False, 0):
            with self.subTest(parent=parent):
                child = document("Child")
                child["profile"]["inherits"] = parent
                self.assert_unresolved(self.resolve([document("Base"), child]),
                                       "blocked", "INHERITS_UNSUPPORTED")
        self.assertEqual(self.resolve([document("Child", "")])["status"], "resolved")

    def test_nil_null_and_variant_fields_cannot_look_resolved(self):
        for value in ("nil", ["nil"], {"nested": ["nil"]}, None, [None]):
            with self.subTest(value=value):
                result = self.resolve([document("Base", vendor_notes=value), document("Child", "Base")])
                self.assert_unresolved(result, "blocked", "SETTING_VALUE_UNSUPPORTED")
        for key in ("filament_extruder_variant", "print_extruder_id", "print_extruder_variant",
                    "printer_extruder_id", "printer_extruder_variant"):
            with self.subTest(key=key):
                result = self.resolve([document("Child", **{key: []})])
                self.assert_unresolved(result, "blocked", "VARIANT_UNSUPPORTED")

    def test_reserved_key_case_variants_do_not_bypass_the_resolver(self):
        for key in ("Inherits", "INCLUDE", "Name", "Type", "FROM", "Filament_Id",
                    "Filament_Settings_Id", "FILAMENT_EXTRUDER_VARIANT"):
            with self.subTest(key=key):
                result = self.resolve([document("Child", **{key: "ignored?"})])
                self.assert_unresolved(result, "blocked", "NONCANONICAL_METADATA")

    def test_wrong_type_and_missing_name_are_blocked(self):
        for kind in ("machine", "process", "", None, []):
            with self.subTest(kind=kind):
                result = self.resolve([document("Base", type=kind), document("Child", "Base")])
                self.assert_unresolved(result, "blocked", "PROFILE_TYPE_MISMATCH")
        for name in (None, "", "   ", 7, []):
            with self.subTest(name=name):
                profile = {"type": "filament", "name": name}
                self.assert_unresolved(self.resolve([{"filename": "bad.json", "profile": profile}]),
                                       "blocked", "PROFILE_NAME_INVALID")

    def test_unused_unsupported_chain_does_not_block_a_separate_supported_target(self):
        docs = [document("Other", include="Vendor defaults"), document("Child", vendor_notes="plain")]
        self.assertEqual(self.resolve(docs)["status"], "resolved")

    def test_unknown_fields_are_preserved_and_the_existing_review_gate_still_applies(self):
        result = self.resolve([document("Child", experimental_nozzle_speed=["20"])],
                              setup=fixture_setup())
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["resolved_profile"]["settings"]["experimental_nozzle_speed"], ["20"])
        self.assertFalse(result["review"]["can_prepare_profile"])
        self.assertIn("EXECUTION_FIELD_UNRESOLVED", {row["code"] for row in result["review"]["reasons"]})

    def test_malformed_non_json_and_nonfinite_input_is_rejected_as_a_value_error(self):
        bad_documents = [
            None, [], {}, [None], [{"filename": "a.json"}],
            [{"filename": "a.json", "profile": []}],
            [{"filename": "", "profile": {}}],
            [{"filename": 3, "profile": {}}],
            [{"filename": "a.json", "profile": {"settings": []}}],
            [{"filename": "a.json", "profile": {"settings": {}, "scope": []}}],
            [document("Child", vendor_notes={1: "non-string key"})],
            [document("Child", vendor_notes={"set"})],
            [document("Child", vendor_notes=("tuple",))],
            [document("Child", nozzle_temperature=[float("nan")])],
            [document("Child", nozzle_temperature=[float("inf")])],
        ]
        for docs in bad_documents:
            with self.subTest(docs=docs):
                with self.assertRaises(ValueError):
                    self.resolve(docs)
        for target in (None, "", "   ", 3):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    self.resolve([document("Child")], target)
        for setup in ([], None, {"value": float("inf")}):
            with self.subTest(setup=setup):
                with self.assertRaises(ValueError):
                    resolve_profile_documents([document("Child")], "Child", setup)

    def test_json_serialization_has_no_hidden_nonfinite_output(self):
        result = self.resolve([document("Child", vendor_notes="NaN remains an ordinary string")])
        json.dumps(result, allow_nan=False)


class PresetEditReviewTests(unittest.TestCase):
    def setUp(self):
        self.setup = fixture_setup()
        parent = fixture_profile()["settings"]
        parent["name"] = "Base"
        child = fixture_profile()
        child["settings"] = {"name": "Child", "type": "filament", "inherits": "Base"}
        child["validation"] = {
            "status": "measured_on_matching_setup", "setup_fingerprint": deepcopy(self.setup),
        }
        self.originals = [
            {"filename": "base.json", "profile": parent},
            {"filename": "child.json", "profile": child},
        ]

    def resolve(self, documents=None, baseline=None, target="Child"):
        return resolve_profile_documents(
            self.originals if documents is None else documents, target, self.setup,
            baseline={"documents": self.originals, "target_name": "Child"} if baseline is None else baseline,
        )

    def test_changed_parent_invalidates_validation_but_preserves_original_claim(self):
        edited = deepcopy(self.originals)
        edited[0]["profile"]["nozzle_temperature"] = ["260"]
        preserved = deepcopy(self.originals)
        report = self.resolve(edited)
        self.assertEqual(report["status"], "resolved")
        self.assertEqual(report["edit_review"]["status"], "changed")
        self.assertEqual(report["edit_review"]["changed_fields"], ["nozzle_temperature"])
        self.assertTrue(report["edit_review"]["validation_invalidated"])
        self.assertEqual(report["review"]["validation_status"], "stale")
        self.assertEqual(report["review"]["decision"], "needs_evidence")
        self.assertFalse(report["review"]["can_prepare_profile"])
        self.assertIsNone(report["review"]["selected_profile_id"])
        self.assertIn("VALIDATION_SETTINGS_CHANGED", {row["code"] for row in report["review"]["reasons"]})
        self.assertIn("validation_settings_changed", {row["reason"] for row in report["review"]["calibration_actions"]})
        self.assertTrue(report["field_sources"]["nozzle_temperature"]["edited"])
        self.assertTrue(report["field_sources"]["nozzle_temperature"]["inherited"])
        self.assertFalse(report["field_sources"]["filament_flow_ratio"]["edited"])
        self.assertEqual(report["resolved_profile"]["validation"], self.originals[1]["profile"]["validation"])
        self.assertEqual(report["review"]["source_authority"], self.originals[1]["profile"]["source"]["authority"])
        self.assertEqual(self.originals, preserved)
        self.assertEqual(report["imported_documents"][0]["profile"], preserved[0]["profile"])
        self.assertEqual(report["documents"][0]["profile"], edited[0]["profile"])
        self.assertNotEqual(report["documents"][0]["sha256"], report["imported_documents"][0]["sha256"])

    def test_target_override_is_changed_and_original_restoration_is_unchanged(self):
        edited = deepcopy(self.originals)
        edited[1]["profile"]["settings"]["filament_flow_ratio"] = ["0.91"]
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"]["changed_fields"], ["filament_flow_ratio"])
        self.assertTrue(report["field_sources"]["filament_flow_ratio"]["edited"])
        self.assertFalse(report["field_sources"]["filament_flow_ratio"]["inherited"])
        restored = self.resolve(deepcopy(self.originals))
        self.assertEqual(restored["edit_review"]["status"], "unchanged")
        self.assertEqual(restored["edit_review"]["changed_fields"], [])
        self.assertFalse(restored["edit_review"]["validation_invalidated"])
        self.assertEqual(restored["review"]["validation_status"], "reported_validated")
        self.assertTrue(restored["review"]["can_prepare_profile"])

    def test_unused_document_and_overridden_parent_changes_do_not_invalidate(self):
        self.originals.append(document("Unrelated", nozzle_temperature=["10"]))
        self.originals[1]["profile"]["settings"]["nozzle_temperature"] = ["215"]
        edited = deepcopy(self.originals)
        edited[0]["profile"]["nozzle_temperature"] = ["260"]
        edited[2]["profile"]["nozzle_temperature"] = ["20"]
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"]["status"], "unchanged")
        self.assertEqual(report["review"]["validation_status"], "reported_validated")
        self.assertFalse(report["field_sources"]["nozzle_temperature"]["edited"])

    def test_key_order_is_ignored_but_numeric_and_array_representation_changes_are_visible(self):
        reordered = deepcopy(self.originals)
        reordered[0]["profile"] = dict(reversed(list(reordered[0]["profile"].items())))
        self.assertEqual(self.resolve(reordered)["edit_review"]["status"], "unchanged")
        for value in (210, [210], "210"):
            with self.subTest(value=value):
                edited = deepcopy(self.originals)
                edited[0]["profile"]["nozzle_temperature"] = value
                self.assertIn("nozzle_temperature", self.resolve(edited)["edit_review"]["changed_fields"])

    def test_removed_field_is_recorded_without_fabricating_current_provenance(self):
        self.originals[0]["profile"]["vendor_notes"] = "Original supplied note"
        edited = deepcopy(self.originals)
        del edited[0]["profile"]["vendor_notes"]
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"]["changed_fields"], ["vendor_notes"])
        self.assertNotIn("vendor_notes", report["field_sources"])

    def test_unavailable_original_chain_invalidates_positive_claim_without_faking_differences(self):
        for baseline in (
            {"documents": [self.originals[1]], "target_name": "Child"},
            {"documents": self.originals, "target_name": "Missing"},
            {"documents": self.originals, "target_name": ""},
            {"documents": [document("Child", include="Unsupported native include")], "target_name": "Child"},
        ):
            with self.subTest(target=baseline["target_name"], documents=len(baseline["documents"])):
                report = self.resolve(baseline=baseline)
                self.assertEqual(report["status"], "resolved")
                self.assertEqual(report["edit_review"]["status"], "baseline_unresolved")
                self.assertIn(report["edit_review"]["baseline_status"], {"needs_input", "blocked"})
                self.assertEqual(report["edit_review"]["changed_fields"], [])
                self.assertTrue(report["edit_review"]["validation_invalidated"])
                self.assertIsNone(report["field_sources"]["nozzle_temperature"]["edited"])
                self.assertEqual(report["review"]["validation_status"], "stale")
                self.assertFalse(report["review"]["can_prepare_profile"])
                self.assertIn("VALIDATION_BASELINE_UNRESOLVED", {row["code"] for row in report["review"]["reasons"]})

    def test_malformed_baseline_is_rejected_even_when_current_chain_cannot_resolve(self):
        malformed = [
            [], {}, {"documents": self.originals},
            {"documents": self.originals, "target_name": None},
            {"documents": self.originals, "target_name": "Child", "unexpected": True},
            {"documents": [], "target_name": "Child"},
            {"documents": [{"filename": "bad.json", "profile": []}], "target_name": "Child"},
            {"documents": [document("Child", vendor_notes=float("nan"))], "target_name": "Child"},
        ]
        for baseline in malformed:
            with self.subTest(baseline=baseline):
                with self.assertRaises(ValueError):
                    self.resolve([document("Child", "Missing")], baseline=baseline)

    def test_current_and_original_sets_keep_independent_size_and_depth_limits(self):
        docs = [document("Child", vendor_notes="x" * (1200 * 1024))]
        report = self.resolve(docs, baseline={"documents": docs, "target_name": "Child"})
        self.assertEqual(report["edit_review"]["status"], "unchanged")
        oversized = [document("Child", vendor_notes="x" * (2 * 1024 * 1024))]
        with self.assertRaises(ValueError):
            self.resolve(baseline={"documents": oversized, "target_name": "Child"})
        nested = "leaf"
        for _ in range(65):
            nested = [nested]
        with self.assertRaisesRegex(ValueError, "중첩"):
            self.resolve(baseline={"documents": [document("Child", vendor_notes=nested)], "target_name": "Child"})

    def test_all_positive_claim_spellings_are_invalidated_even_without_scope_fingerprint(self):
        for status in ("measured_on_matching_setup", "verified", "validated", "reported_validated"):
            with self.subTest(status=status):
                edited = deepcopy(self.originals)
                edited[1]["profile"]["validation"] = {"status": status}
                edited[0]["profile"]["filament_flow_ratio"] = ["0.9"]
                report = self.resolve(edited)
                self.assertEqual(report["review"]["validation_status"], "stale")
                self.assertTrue(report["edit_review"]["validation_invalidated"])

    def test_unverified_draft_changes_are_visible_without_inventing_prior_validation(self):
        edited = deepcopy(self.originals)
        edited[1]["profile"]["validation"] = {"status": "unverified"}
        edited[0]["profile"]["filament_flow_ratio"] = ["0.9"]
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"]["status"], "changed")
        self.assertEqual(report["review"]["validation_status"], "unverified")
        self.assertFalse(report["edit_review"]["validation_invalidated"])

    def test_changed_settings_do_not_downgrade_a_stronger_blocker(self):
        edited = deepcopy(self.originals)
        edited[0]["profile"]["nozzle_temperature"] = ["-1"]
        report = self.resolve(edited)
        self.assertEqual(report["review"]["decision"], "blocked")
        self.assertEqual(report["review"]["validation_status"], "stale")

    def test_untracked_and_current_unresolved_reports_do_not_claim_a_comparison(self):
        report = resolve_profile_documents(self.originals, "Child", self.setup)
        self.assertEqual(report["edit_review"]["status"], "untracked")
        self.assertIsNone(report["edit_review"]["baseline_status"])
        self.assertEqual(report["review"]["validation_status"], "reported_validated")
        self.assertEqual(report["imported_documents"], [])
        unavailable = self.resolve([document("Child", "Missing")])
        self.assertEqual(unavailable["edit_review"]["status"], "untracked")
        self.assertEqual(unavailable["edit_review"]["baseline_status"], "resolved")
        self.assertIsNone(unavailable["review"])
        self.assertEqual(len(unavailable["imported_documents"]), 2)

    def test_imported_evidence_is_copied_and_hashed_without_aliasing(self):
        report = self.resolve()
        preserved = deepcopy(self.originals)
        for original, record in zip(preserved, report["imported_documents"]):
            canonical = json.dumps(original["profile"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            self.assertEqual(record["sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        report["imported_documents"][0]["profile"]["nozzle_temperature"].append("999")
        self.assertEqual(self.originals, preserved)
        self.assertEqual(report["documents"][0]["profile"], preserved[0]["profile"])


class PresetEvidenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.setup = fixture_setup()
        profile = fixture_profile()
        profile["settings"]["name"] = "Child"
        profile["validation"] = {
            "status": "measured_on_matching_setup", "setup_fingerprint": deepcopy(self.setup),
        }
        self.originals = [{"filename": "child.json", "profile": profile}]

    def resolve(self, documents=None, baseline=None, target="Child"):
        return resolve_profile_documents(
            self.originals if documents is None else documents, target, self.setup,
            baseline={"documents": self.originals, "target_name": "Child"} if baseline is None else baseline,
        )

    def test_wrapping_raw_settings_records_evidence_without_inventing_measurement(self):
        raw = deepcopy(self.originals[0]["profile"]["settings"])
        raw["vendor_notes"] = {"opaque": ["retained"]}
        origin = {
            "type": "bambu_preset_archive", "archive_name": "synthetic.bbsflmt",
            "archive_sha256": "a" * 64, "member_path": "filament/child.json",
            "member_sha256": "b" * 64,
        }
        original = {"filename": "child.json", "profile": raw, "origin": origin}
        current = {
            "filename": "child.json", "origin": deepcopy(origin),
            "profile": {"settings": deepcopy(raw), "scope": {"material_id": "fixture:pla-basic"},
                        "source": {"publisher": "User supplied publisher"}},
        }
        report = self.resolve([current], {"documents": [original], "target_name": "Child"})
        edit = report["edit_review"]
        self.assertEqual(edit.get("evidence_status"), "compared")
        self.assertEqual(edit["evidence_changes"], [
            {"path": "scope.material_id", "before_present": False, "after_present": True,
             "after": "fixture:pla-basic"},
            {"path": "source.publisher", "before_present": False, "after_present": True,
             "after": "User supplied publisher"},
        ])
        self.assertEqual(edit["status"], "unchanged")
        self.assertEqual(edit["changed_fields"], [])
        self.assertFalse(edit["validation_invalidated"])
        self.assertEqual(report["review"]["validation_status"], "unverified")
        self.assertEqual(report["resolved_profile"]["settings"], raw)
        self.assertTrue(all(source["edited"] is False for source in report["field_sources"].values()))
        self.assertEqual(report["imported_documents"][0]["profile"], raw)
        self.assertEqual(report["documents"][0]["origin"], origin)
        self.assertEqual(report["imported_documents"][0]["origin"], origin)
        self.assertNotEqual(report["documents"][0]["sha256"], report["imported_documents"][0]["sha256"])

    def test_source_corrections_remain_claims_without_invalidating_matching_measurement(self):
        edited = deepcopy(self.originals)
        edited[0]["profile"]["source"] = {
            "authority": "user-reported", "publisher": "Corrected publisher",
            "url": "https://example.invalid/corrected", "retrieved_at": "date supplied by user",
        }
        report = self.resolve(edited)
        edit = report["edit_review"]
        self.assertEqual(edit.get("evidence_status"), "compared")
        self.assertEqual(edit["evidence_changes"], [
            {"path": "source.authority", "before_present": True, "after_present": True,
             "before": "manufacturer", "after": "user-reported"},
            {"path": "source.publisher", "before_present": True, "after_present": True,
             "before": "Synthetic fixture publisher", "after": "Corrected publisher"},
            {"path": "source.retrieved_at", "before_present": True, "after_present": True,
             "before": "2026-11-12", "after": "date supplied by user"},
            {"path": "source.url", "before_present": True, "after_present": True,
             "before": "https://example.invalid/fixture", "after": "https://example.invalid/corrected"},
        ])
        self.assertEqual(edit["status"], "unchanged")
        self.assertEqual(edit["changed_fields"], [])
        self.assertFalse(edit["validation_invalidated"])
        self.assertEqual(report["review"]["validation_status"], "reported_validated")
        self.assertTrue(report["review"]["can_prepare_profile"])
        self.assertEqual(report["review"]["source_authority"], "user-reported")
        self.assertTrue(any(w.startswith("SOURCE_CLAIM_ONLY:") for w in report["review"]["warnings"]))
        self.assertEqual(report["resolved_profile"]["validation"], self.originals[0]["profile"]["validation"])

    def test_scope_edits_invalidate_positive_claims_without_weakening_blockers(self):
        for status in ("measured_on_matching_setup", "verified", "validated", "reported_validated"):
            for nozzle, decision in (("0.40", "needs_evidence"), (0.6, "blocked")):
                with self.subTest(status=status, nozzle=nozzle):
                    originals = deepcopy(self.originals)
                    originals[0]["profile"]["validation"]["status"] = status
                    edited = deepcopy(originals)
                    edited[0]["profile"]["scope"]["nozzle_diameter"] = nozzle
                    report = self.resolve(edited, {"documents": originals, "target_name": "Child"})
                    self.assertEqual(report["review"]["validation_status"], "stale")
                    self.assertEqual(report["review"]["decision"], decision)
                    self.assertFalse(report["review"]["can_prepare_profile"])
                    self.assertIsNone(report["review"]["selected_profile_id"])
                    self.assertEqual(report["edit_review"]["status"], "unchanged")
                    self.assertEqual(report["edit_review"]["changed_fields"], [])
                    self.assertEqual(report["edit_review"]["evidence_changes"], [
                        {"path": "scope.nozzle_diameter", "before_present": True, "after_present": True,
                         "before": 0.4, "after": nozzle},
                    ])
                    self.assertTrue(report["edit_review"]["validation_invalidated"])
                    self.assertIn("VALIDATION_EVIDENCE_CHANGED", {r["code"] for r in report["review"]["reasons"]})
                    self.assertIn("validation_evidence_changed", {a["reason"] for a in report["review"]["calibration_actions"]})
                    self.assertFalse(any(w.startswith("VALIDATION_CLAIM_ONLY:") for w in report["review"]["warnings"]))
                    self.assertEqual(report["resolved_profile"]["validation"], originals[0]["profile"]["validation"])

    def test_validation_claim_edits_are_distinct_from_setting_changes(self):
        replacements = [
            ("status", "verified"),
            ("setup_fingerprint", {**self.setup, "nozzle_diameter": "0.40"}),
            ("measurement_note", {"record": "a different supplied account"}),
        ]
        for field, value in replacements:
            with self.subTest(field=field):
                edited = deepcopy(self.originals)
                edited[0]["profile"]["validation"][field] = deepcopy(value)
                report = self.resolve(edited)
                self.assertEqual(report["review"]["validation_status"], "stale")
                self.assertEqual(report["review"]["decision"], "needs_evidence")
                self.assertEqual(report["edit_review"]["changed_fields"], [])
                self.assertEqual([c["path"] for c in report["edit_review"]["evidence_changes"]], [f"validation.{field}"])
                self.assertEqual(report["resolved_profile"]["validation"], edited[0]["profile"]["validation"])
                self.assertEqual(report["imported_documents"][0]["profile"], self.originals[0]["profile"])

    def test_lowering_a_claim_to_unverified_does_not_invent_stale_measurement(self):
        edited = deepcopy(self.originals)
        edited[0]["profile"]["validation"]["status"] = "unverified"
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
        self.assertEqual(report["edit_review"]["evidence_changes"], [
            {"path": "validation.status", "before_present": True, "after_present": True,
             "before": "measured_on_matching_setup", "after": "unverified"},
        ])
        self.assertEqual(report["review"]["validation_status"], "unverified")
        self.assertFalse(report["edit_review"]["validation_invalidated"])
        self.assertTrue(report["review"]["can_prepare_profile"])

    def test_empty_groups_and_json_key_order_do_not_fabricate_evidence_edits(self):
        raw = deepcopy(self.originals[0]["profile"]["settings"])
        empty = {"settings": deepcopy(raw), "scope": {}, "source": {}, "validation": {}}
        for before, after in ((raw, empty), (empty, raw)):
            with self.subTest(before_envelope="settings" in before):
                report = self.resolve(
                    [{"filename": "child.json", "profile": after}],
                    {"documents": [{"filename": "child.json", "profile": before}], "target_name": "Child"},
                )
                self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
                self.assertEqual(report["edit_review"]["evidence_changes"], [])
        self.originals[0]["profile"]["source"]["extra"] = {"first": 1, "second": ["2"]}
        edited = deepcopy(self.originals)
        edited[0]["profile"]["source"]["extra"] = {"second": ["2"], "first": 1}
        edited[0]["profile"]["scope"] = dict(reversed(list(edited[0]["profile"]["scope"].items())))
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
        self.assertEqual(report["edit_review"]["evidence_changes"], [])
        self.assertEqual(report["review"]["validation_status"], "reported_validated")

    def test_absent_keys_and_explicit_null_are_distinguishable_in_evidence(self):
        self.originals[0]["profile"]["source"]["old_null"] = None
        edited = deepcopy(self.originals)
        del edited[0]["profile"]["source"]["old_null"]
        edited[0]["profile"]["source"]["new_null"] = None
        edited[0]["profile"]["source"]["publisher"] = None
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
        self.assertEqual(report["edit_review"]["evidence_changes"], [
            {"path": "source.new_null", "before_present": False, "after_present": True, "after": None},
            {"path": "source.old_null", "before_present": True, "after_present": False, "before": None},
            {"path": "source.publisher", "before_present": True, "after_present": True,
             "before": "Synthetic fixture publisher", "after": None},
        ])
        self.assertEqual(report["review"]["validation_status"], "reported_validated")

    def test_parent_metadata_never_becomes_selected_child_evidence(self):
        parent = deepcopy(self.originals[0])
        parent["filename"] = "base.json"
        parent["profile"]["settings"]["name"] = "Base"
        self.originals[0]["profile"]["settings"] = {"name": "Child", "type": "filament", "inherits": "Base"}
        self.originals.append(parent)
        edited = deepcopy(self.originals)
        edited[1]["profile"]["scope"]["material_id"] = "another product"
        edited[1]["profile"]["source"]["publisher"] = "Different parent publisher"
        edited[1]["profile"]["validation"]["status"] = "unverified"
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
        self.assertEqual(report["edit_review"]["evidence_changes"], [])
        self.assertEqual(report["edit_review"]["status"], "unchanged")
        self.assertFalse(report["edit_review"]["validation_invalidated"])
        self.assertEqual(report["review"]["validation_status"], "reported_validated")

    def test_unique_target_evidence_compares_before_missing_parent_resolution(self):
        self.originals[0]["profile"]["settings"]["inherits"] = "Missing"
        edited = deepcopy(self.originals)
        edited[0]["profile"]["source"]["url"] = "https://example.invalid/corrected"
        for current_resolves in (False, True):
            with self.subTest(current_resolves=current_resolves):
                documents = edited + ([document("Missing")] if current_resolves else [])
                report = self.resolve(documents)
                self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
                self.assertEqual([c["path"] for c in report["edit_review"]["evidence_changes"]], ["source.url"])
                self.assertEqual(report["edit_review"]["baseline_status"], "needs_input")
                if current_resolves:
                    self.assertEqual(report["edit_review"]["status"], "baseline_unresolved")
                    self.assertEqual(report["review"]["validation_status"], "stale")
                    self.assertIn("VALIDATION_BASELINE_UNRESOLVED", {r["code"] for r in report["review"]["reasons"]})
                else:
                    self.assertEqual(report["edit_review"]["status"], "untracked")
                    self.assertIsNone(report["review"])
                    self.assertFalse(report["edit_review"]["validation_invalidated"])

    def test_unidentified_targets_and_absent_baseline_do_not_claim_evidence_comparison(self):
        unnamed = deepcopy(self.originals)
        unnamed[0]["profile"]["settings"]["name"] = ""
        cases = [
            ([document("Other")], {"documents": self.originals, "target_name": "Child"}),
            (self.originals, {"documents": [document("Other")], "target_name": "Child"}),
            (self.originals + deepcopy(self.originals), {"documents": self.originals, "target_name": "Child"}),
            (self.originals, {"documents": self.originals + deepcopy(self.originals), "target_name": "Child"}),
            (self.originals, {"documents": unnamed, "target_name": ""}),
            (self.originals, None),
        ]
        for index, (documents, baseline) in enumerate(cases):
            with self.subTest(case=index):
                report = resolve_profile_documents(documents, "Child", self.setup, baseline=baseline)
                self.assertEqual(report["edit_review"].get("evidence_status"), "untracked")
                self.assertEqual(report["edit_review"]["evidence_changes"], [])

    def test_setting_and_evidence_invalidations_keep_both_reasons(self):
        edited = deepcopy(self.originals)
        edited[0]["profile"]["settings"]["nozzle_temperature"] = ["210"]
        edited[0]["profile"]["scope"]["material_id"] = "different product"
        report = self.resolve(edited)
        reasons = {r["code"] for r in report["review"]["reasons"]}
        self.assertIn("VALIDATION_EVIDENCE_CHANGED", reasons)
        self.assertIn("VALIDATION_SETTINGS_CHANGED", reasons)
        self.assertEqual(report["edit_review"]["changed_fields"], ["nozzle_temperature"])
        self.assertEqual([c["path"] for c in report["edit_review"]["evidence_changes"]], ["scope.material_id"])
        self.assertEqual(report["review"]["decision"], "blocked")
        self.assertEqual(report["review"]["validation_status"], "stale")

    def test_evidence_values_are_independent_of_inputs_and_other_report_components(self):
        self.originals[0]["profile"]["source"]["extra"] = {"notes": ["before"]}
        edited = deepcopy(self.originals)
        edited[0]["profile"]["source"]["extra"]["notes"] = ["after"]
        report = self.resolve(edited)
        self.assertEqual(report["edit_review"].get("evidence_status"), "compared")
        change = report["edit_review"]["evidence_changes"][0]
        self.assertEqual(change["path"], "source.extra")
        change["before"]["notes"].append("mutation")
        change["after"]["notes"].append("mutation")
        self.assertEqual(self.originals[0]["profile"]["source"]["extra"], {"notes": ["before"]})
        self.assertEqual(edited[0]["profile"]["source"]["extra"], {"notes": ["after"]})
        self.assertEqual(report["imported_documents"][0]["profile"]["source"]["extra"], {"notes": ["before"]})
        self.assertEqual(report["documents"][0]["profile"]["source"]["extra"], {"notes": ["after"]})
        self.assertEqual(report["resolved_profile"]["source"]["extra"], {"notes": ["after"]})


if __name__ == "__main__":
    unittest.main()
