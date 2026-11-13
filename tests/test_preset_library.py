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


if __name__ == "__main__":
    unittest.main()
