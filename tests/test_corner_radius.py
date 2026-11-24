"""Optional rounded edges: tray corners and the side profile of a wall hook and phone stand."""

import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cadquery as cq

from print_agent.geometry import generate_model, preview_model, template_catalog
from print_agent.model_edits import plan_model_edit
from print_agent.schemas import GeometryRequest


def spec(template, **values):
    defaults = next(item["defaults"] for item in template_catalog() if item["id"] == template)
    data = {key: value for key, value in defaults.items() if value != ""}
    return GeometryRequest(**{**data, **values, "template": template})


class CornerRadiusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_zero_is_omitted_so_earlier_parameters_and_hashes_keep_their_shape(self):
        for template in ("tray", "wall_hook", "phone_stand"):
            with self.subTest(template=template):
                self.assertNotIn("corner_radius", spec(template).model_dump())
                self.assertEqual(spec(template, corner_radius=2).model_dump()["corner_radius"], 2)
        # Other templates refuse the field.
        with self.assertRaises(ValueError):
            spec("cup", corner_radius=2)

    def test_rounded_tray_keeps_size_and_wall_around_each_corner(self):
        result = generate_model(spec("tray", corner_radius=8, dividers=2), self.root / "tray")
        self.assertEqual(result["dimensions_mm"], {"x": 120.0, "y": 80.0, "z": 35.0})
        shape = cq.importers.importStep(str(self.root / "tray" / result["files"]["step"])).val()
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), 1)
        # The sharp corner is gone; along the diagonal the wall is still 2 mm thick.
        self.assertFalse(shape.isInside((0.5, 0.5, 20)))
        corner = 8 - 8 / math.sqrt(2)
        self.assertTrue(shape.isInside((corner + 1, corner + 1, 20)))
        self.assertFalse(shape.isInside((corner + 2.6, corner + 2.6, 20)))
        # Dividers stay inside the rounded outline.
        self.assertLess(result["volume_mm3"], generate_model(spec("tray", dividers=2), self.root / "sharp")["volume_mm3"])

    def test_hook_and_stand_round_their_profile_and_reproduce(self):
        for template in ("wall_hook", "phone_stand"):
            with self.subTest(template=template):
                sharp = preview_model(spec(template))
                rounded = generate_model(spec(template, corner_radius=1.5), self.root / template)
                self.assertEqual(rounded["dimensions_mm"], sharp["dimensions_mm"])
                self.assertLess(rounded["volume_mm3"], sharp["volume_mm3"])
                source = self.root / template / rounded["files"]["source"]
                out = self.root / f"{template}-reproduced"
                run = subprocess.run([sys.executable, "-I", str(source), str(out)], cwd=self.root, capture_output=True, text=True, timeout=240)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                reproduced = cq.importers.importStep(str(out / "model.step")).val()
                self.assertAlmostEqual(reproduced.Volume(), rounded["volume_mm3"], places=3)

    def test_rules_refuse_radii_that_do_not_fit(self):
        cases = [("tray", dict(corner_radius=0.2)), ("tray", dict(corner_radius=20, width=30, depth=30)),
                 ("wall_hook", dict(corner_radius=2.5)), ("phone_stand", dict(corner_radius=0.1))]
        for template, values in cases:
            with self.subTest(template=template, values=values), self.assertRaises(ValueError):
                preview_model(spec(template, **values))

    def test_an_edit_sets_the_rounding(self):
        base = spec("tray").model_dump()
        proposal = plan_model_edit("모서리 둥글기 4mm로 바꿔줘", base)
        self.assertEqual(proposal["status"], "ready")
        self.assertEqual(proposal["review"]["parameters"]["corner_radius"], 4)


if __name__ == "__main__":
    unittest.main()
