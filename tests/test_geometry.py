"""Real CAD/export checks for the three supported templates."""

from collections import Counter
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import cadquery as cq

from print_agent.schemas import GeometryRequest

try:
    from print_agent.geometry import generate_model, template_catalog
except ModuleNotFoundError as exc:
    if exc.name != "print_agent.geometry":
        raise
    generate_model = template_catalog = None


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def generate(self, spec=None, name="job"):
        self.assertIsNotNone(generate_model, "The geometry implementation is missing")
        return generate_model(spec or GeometryRequest(), self.root / name)

    def shape(self, result, name="job"):
        return cq.importers.importStep(str(self.root / name / result["files"]["step"])).val()

    def test_tray_has_requested_dimensions_and_analytic_volume(self):
        result = self.generate()
        self.assertEqual(result["dimensions_mm"], {"x": 120.0, "y": 80.0, "z": 35.0})
        self.assertAlmostEqual(result["volume_mm3"], 45072.0, places=5)
        self.assertEqual(result["geometry_status"], "validated")
        self.assertEqual(result["print_status"], "not_tested")
        self.assertTrue(result["checks"])
        self.assertTrue(all(check["passed"] for check in result["checks"]))
        shape = self.shape(result)
        self.assertFalse(shape.isInside((60, 40, 20)))
        self.assertTrue(shape.isInside((60, 40, 1)))

    def test_dividers_add_correct_volume_and_equal_compartments(self):
        result = self.generate(GeometryRequest(width=60, depth=40, height=20, dividers=2))
        self.assertAlmostEqual(result["volume_mm3"], 14304.0, places=5)
        shape = self.shape(result)
        for x in (20, 40):
            self.assertTrue(shape.isInside((x, 20, 10)))
        for x in (10, 30, 50):
            self.assertFalse(shape.isInside((x, 20, 10)))

    def test_invalid_trays_are_rejected_before_writing(self):
        cases = [dict(width=10, wall=6), dict(depth=10, wall=6),
                 dict(height=2, bottom=2), dict(width=20, dividers=12)]
        self.assertIsNotNone(generate_model, "The geometry implementation is missing")
        for index, values in enumerate(cases):
            with self.subTest(values=values):
                target = self.root / str(index)
                with self.assertRaises(ValueError):
                    generate_model(GeometryRequest(**values), target)
                self.assertFalse(target.exists())

    def test_cable_comb_has_open_channels_and_rounded_floors(self):
        result = self.generate(GeometryRequest(template="cable_comb", width=80, depth=16,
                              height=12, slots=4, cable_diameter=6, fit_clearance=0.4))
        expected = 15360 - 4 * 16 * (6.4 * 6.8 + math.pi * 3.2 ** 2 / 2)
        self.assertAlmostEqual(result["volume_mm3"], expected, places=5)
        self.assertEqual(result["dimensions_mm"], {"x": 80.0, "y": 16.0, "z": 12.0})
        shape = self.shape(result)
        self.assertFalse(shape.isInside((14.08, 8, 11)))
        self.assertTrue(shape.isInside((14.08, 8, 1)))
        self.assertTrue(shape.isInside((16.58, 8, 2.1)))
        self.assertFalse(shape.isInside((16.58, 8, 3.4)))

    def test_cable_comb_rejects_insufficient_wall_or_floor_space(self):
        self.assertIsNotNone(generate_model, "The geometry implementation is missing")
        for values in (dict(width=20), dict(height=4), dict(slots=20)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                generate_model(GeometryRequest(template="cable_comb", **values), self.root / "bad")

    def test_frame_clearance_is_added_to_diameter_and_pocket_is_blind(self):
        result = self.generate(GeometryRequest(template="magnet_frame", width=70, depth=65,
                              height=8, inset_depth=3, fit_clearance=0.4))
        self.assertAlmostEqual(result["volume_mm3"], 36400 - math.pi * 26.2 ** 2 * 3, places=5)
        shape = self.shape(result)
        self.assertFalse(shape.isInside((35, 32.5, 6)))
        self.assertTrue(shape.isInside((35, 32.5, 4)))
        self.assertFalse(shape.isInside((61.15, 32.5, 6)))
        self.assertTrue(shape.isInside((61.3, 32.5, 6)))
        self.assertTrue(result["warnings"])

    def test_frame_rejects_pocket_through_bottom_or_insufficient_rim(self):
        self.assertIsNotNone(generate_model, "The geometry implementation is missing")
        for values in (dict(height=4, inset_depth=3), dict(width=55), dict(depth=55)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                generate_model(GeometryRequest(template="magnet_frame", **values), self.root / "bad")

    def test_catalog_templates_each_reimport_as_one_valid_solid(self):
        self.assertIsNotNone(template_catalog, "The geometry catalog is missing")
        catalog = template_catalog()
        templates = {item["id"] for item in catalog}
        self.assertEqual(templates, {"tray", "cable_comb", "magnet_frame"})
        for item in catalog:
            template = item["id"]
            with self.subTest(template=template):
                self.assertTrue(item["title"] and item["description"] and item["editable_fields"])
                result = self.generate(GeometryRequest(template=template, **item["defaults"]), name=template)
                shape = self.shape(result, name=template)
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids()), 1)
                self.assertGreater(shape.Volume(), 0)
                self.assertAlmostEqual(shape.Volume(), result["volume_mm3"], places=5)

    def test_generated_source_reproduces_each_template_without_project_imports(self):
        for template in ("tray", "cable_comb", "magnet_frame"):
            with self.subTest(template=template):
                result = self.generate(GeometryRequest(template=template), name=template)
                source = self.root / template / result["files"]["source"]
                destination = self.root / (template + "-reproduced")
                run = subprocess.run([sys.executable, "-I", str(source), str(destination)],
                                     cwd=self.root, capture_output=True, text=True, timeout=40)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                reproduced = cq.importers.importStep(str(destination / "model.step")).val()
                self.assertAlmostEqual(reproduced.Volume(), result["volume_mm3"], places=5)
                bounds = reproduced.BoundingBox()
                for axis in "xyz":
                    self.assertAlmostEqual(getattr(bounds, axis + "len"),
                                           result["dimensions_mm"][axis], places=5)
                for filename in ("model.stl", "model.3mf"):
                    self.assertGreater((destination / filename).stat().st_size, 100)

    def test_preview_mesh_and_stl_are_closed_and_match_cad_dimensions(self):
        result = self.generate(GeometryRequest(template="cable_comb"))
        vertices, faces = result["mesh"]["vertices"], result["mesh"]["faces"]
        self.assertTrue(vertices)
        edges = Counter()
        for face in faces:
            self.assertEqual(len(set(face)), 3)
            for a, b in zip(face, face[1:] + face[:1]):
                self.assertTrue(0 <= a < len(vertices) and 0 <= b < len(vertices))
                edges[tuple(sorted((a, b)))] += 1
        self.assertEqual(set(edges.values()), {2})
        self.assertTrue(all(math.isfinite(v) for point in vertices for v in point))
        data = (self.root / "job" / result["files"]["stl"]).read_bytes()
        count = struct.unpack_from("<I", data, 80)[0]
        self.assertEqual(len(data), 84 + count * 50)
        stl_points = []
        for index in range(count):
            facet = struct.unpack_from("<12fH", data, 84 + index * 50)
            self.assertGreater(sum(v * v for v in facet[:3]), 0.9)
            stl_points.extend((facet[3:6], facet[6:9], facet[9:12]))
        for index, axis in enumerate("xyz"):
            length = max(p[index] for p in stl_points) - min(p[index] for p in stl_points)
            self.assertAlmostEqual(length, result["dimensions_mm"][axis], places=4)

    def test_3mf_contains_real_millimetre_geometry(self):
        result = self.generate(GeometryRequest(template="magnet_frame"))
        with zipfile.ZipFile(self.root / "job" / result["files"]["three_mf"]) as archive:
            models = [name for name in archive.namelist() if name.endswith(".model")]
            self.assertTrue(models)
            root = ET.fromstring(archive.read(models[0]))
        self.assertEqual(root.attrib["unit"], "millimeter")
        vertices = root.findall(".//{*}vertex")
        triangles = root.findall(".//{*}triangle")
        self.assertGreater(len(vertices), 8)
        self.assertGreater(len(triangles), 12)
        for axis in "xyz":
            values = [float(v.attrib[axis]) for v in vertices]
            self.assertAlmostEqual(max(values) - min(values), result["dimensions_mm"][axis], places=4)

    def test_existing_model_files_are_never_overwritten(self):
        self.assertIsNotNone(generate_model, "The geometry implementation is missing")
        self.root.joinpath("model.step").write_text("preserve this model", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            generate_model(GeometryRequest(), self.root)
        self.assertEqual(self.root.joinpath("model.step").read_text(), "preserve this model")


if __name__ == "__main__":
    unittest.main()
