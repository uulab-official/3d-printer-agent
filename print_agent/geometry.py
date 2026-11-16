"""Deterministic, millimetre-based CAD templates and their export evidence."""

from collections import Counter
import inspect
import math
from pathlib import Path

import cadquery as cq

from .schemas import GeometryRequest
from .geometry_rules import _validate_geometry
from .printability import assess_printability


def template_catalog() -> list[dict]:
    return [
        {"id": "tray", "title": "칸막이 수납함",
         "description": "위가 열린 수납함. 폭 방향을 같은 크기의 칸으로 나눕니다.",
         "defaults": {"width": 120, "depth": 80, "height": 35, "wall": 2, "bottom": 2, "dividers": 0},
         "editable_fields": ["width", "depth", "height", "wall", "bottom", "dividers"]},
        {"id": "cable_comb", "title": "열린 케이블 받침",
         "description": "깊이 방향으로 열린 U형 홈에 케이블을 올려놓는 받침입니다.",
         "defaults": {"width": 80, "depth": 18, "height": 12, "wall": 2, "bottom": 2,
                      "slots": 5, "cable_diameter": 6, "fit_clearance": 0.3},
         "editable_fields": ["width", "depth", "height", "wall", "bottom", "slots",
                             "cable_diameter", "fit_clearance"]},
        {"id": "magnet_frame", "title": "원형 인셋 프레임",
         "description": "원판을 넣는 막힌 원형 포켓입니다. 여유값은 지름에 한 번 더합니다.",
         "defaults": {"width": 65, "depth": 65, "height": 7, "wall": 2, "bottom": 2,
                      "inset_diameter": 52, "inset_depth": 2, "fit_clearance": 0.3},
         "editable_fields": ["width", "depth", "height", "wall", "bottom", "inset_diameter",
                             "inset_depth", "fit_clearance"]},
        {"id": "name_tag", "title": "이름 키링",
         "description": "둥근 받침판 위에 글자를 올리고 고리 구멍을 둔 키링입니다. 가로·세로는 글자 길이에 맞춰 정해집니다.",
         "defaults": {"text": "MINSU", "text_size": 12, "text_depth": 2, "wall": 3, "bottom": 2, "hole_diameter": 4},
         "editable_fields": ["text", "text_size", "text_depth", "wall", "bottom", "hole_diameter"]},
        {"id": "phone_stand", "title": "휴대폰 거치대",
         "description": "앞턱과 기울어진 등판 사이에 휴대폰을 세워 두는 거치대입니다.",
         "defaults": {"width": 70, "depth": 80, "height": 90, "wall": 4, "bottom": 4,
                      "lean_angle": 65, "device_thickness": 12, "lip_height": 12, "fit_clearance": 1},
         "editable_fields": ["width", "depth", "height", "wall", "bottom", "lean_angle",
                             "device_thickness", "lip_height", "fit_clearance"]},
    ]


def _build_solid(p: dict) -> cq.Shape:
    """Build only fixed templates; p contains validated numeric parameters."""
    w, d, h, wall, bottom = (p[key] for key in ("width", "depth", "height", "wall", "bottom"))
    body = cq.Workplane("XY").box(w, d, h, centered=False)
    if p["template"] == "tray":
        cavity = cq.Workplane("XY").box(w - 2 * wall, d - 2 * wall, h, centered=False)
        body = body.cut(cavity.translate((wall, wall, bottom)))
        count = p["dividers"]
        cell_width = (w - 2 * wall - count * wall) / (count + 1)
        for index in range(count):
            x = wall + (index + 1) * cell_width + index * wall
            divider = cq.Workplane("XY").box(wall, d, h, centered=False).translate((x, 0, 0))
            body = body.union(divider)
    elif p["template"] == "cable_comb":
        diameter = p["cable_diameter"] + p["fit_clearance"]
        radius = diameter / 2
        gap = (w - p["slots"] * diameter) / (p["slots"] + 1)
        center_z = bottom + radius
        for index in range(p["slots"]):
            center_x = gap + radius + index * (diameter + gap)
            round_floor = cq.Solid.makeCylinder(radius, d + 2,
                                                cq.Vector(center_x, -1, center_z), cq.Vector(0, 1, 0))
            opening = cq.Workplane("XY").box(diameter, d + 2, h - center_z + 1, centered=False)
            opening = opening.translate((center_x - radius, -1, center_z))
            body = body.cut(round_floor).cut(opening)
    elif p["template"] == "name_tag":
        # Letters stand on a rounded plate; a tab with a hole sits on the left.
        # System fonts are used, so another computer may draw slightly different letters.
        text = p["text"].strip()
        letters = (cq.Workplane("XY").text(text, p["text_size"], p["text_depth"], combine=False,
                                           halign="left", valign="bottom", font="Arial", kind="bold"))
        letter_box = letters.val().BoundingBox()
        margin, hole = wall, p["hole_diameter"]
        tab = hole + 2 * margin
        plate_w = letter_box.xlen + 2 * margin + tab
        plate_d = max(letter_box.ylen, hole) + 2 * margin
        radius = min(plate_d / 2 - 0.01, margin + hole / 2)
        plate = (cq.Workplane("XY").rect(plate_w, plate_d, centered=False).extrude(bottom)
                 .edges("|Z").fillet(radius))
        ring = (cq.Workplane("XY").circle(hole / 2).extrude(bottom + 2)
                .translate((margin + hole / 2, plate_d / 2, -1)))
        body = plate.cut(ring)
        offset = (tab + margin - letter_box.xmin, margin + (plate_d - 2 * margin - letter_box.ylen) / 2 - letter_box.ymin, bottom)
        body = body.union(letters.translate(offset))
    elif p["template"] == "phone_stand":
        import math
        body = cq.Workplane("XY").box(w, d, bottom, centered=False)
        lip = cq.Workplane("XY").box(w, wall, bottom + p["lip_height"], centered=False)
        slot_front = wall + p["device_thickness"] + p["fit_clearance"]
        lean = 90 - p["lean_angle"]
        length = (h - bottom) / math.cos(math.radians(lean)) + 2 * wall
        back = (cq.Workplane("XY").box(w, wall, length, centered=False)
                .rotate((0, 0, 0), (1, 0, 0), -lean).translate((0, slot_front, bottom)))
        envelope = cq.Workplane("XY").box(w, d, h, centered=False)
        body = body.union(lip).union(back).intersect(envelope)
    elif p["template"] == "magnet_frame":
        radius = (p["inset_diameter"] + p["fit_clearance"]) / 2
        pocket = cq.Solid.makeCylinder(radius, p["inset_depth"] + 1,
                                      cq.Vector(w / 2, d / 2, h - p["inset_depth"]))
        body = body.cut(pocket)
    else:
        raise ValueError("지원하지 않는 모델 템플릿입니다.")
    return body.clean().val()


def _preview_mesh(shape: cq.Shape) -> dict:
    points, triangles = shape.tessellate(0.05, 0.1)
    vertices, remap, lookup = [], [], {}
    for point in points:
        key = tuple(round(value, 9) for value in point.toTuple())
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(list(key))
        remap.append(lookup[key])
    return {"vertices": vertices, "faces": [[remap[index] for index in face] for face in triangles]}


def _export_cad(shape: cq.Shape, output_dir: Path) -> None:
    """Also embedded in the standalone reproduction source."""
    filenames = ("model.stl", "model.step", "model.3mf")
    for filename in filenames:
        target = output_dir / filename
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"기존 모델 파일을 덮어쓸 수 없습니다: {filename}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        cq.exporters.export(shape, str(output_dir / filename), tolerance=0.05, angularTolerance=0.1)
        if (output_dir / filename).stat().st_size == 0:
            raise ValueError(f"CAD 파일 내보내기가 실패했습니다: {filename}")


def _reproduction_source(parameters: dict) -> str:
    preamble = ("# Generated with CadQuery " + cq.__version__ + "; all lengths are millimetres.\n"
                "# This source reproduces geometry, not slicer settings or print success.\n"
                "from pathlib import Path\nimport sys\nimport cadquery as cq\n\n")
    functions = "\n\n".join(inspect.getsource(fn) for fn in (_validate_geometry, _build_solid, _export_cad))
    runner = (f"\n\nPARAMETERS = {parameters!r}\n\n"
              "if __name__ == '__main__':\n"
              "    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'reproduced'\n"
              "    _validate_geometry(PARAMETERS)\n"
              "    result = _build_solid(PARAMETERS)\n"
              "    if not result.isValid() or len(result.Solids()) != 1 or result.Volume() <= 0:\n"
              "        raise ValueError('Reproduced CAD failed solid validation')\n"
              "    _export_cad(result, destination)\n")
    return preamble + functions + runner


def _safe_printability(shape, parameters, mesh):
    """The review is advice; an unexpected failure must not block a valid CAD result."""
    try:
        return assess_printability(shape, parameters, mesh)
    except Exception:  # noqa: BLE001 - reported as an absent review
        return None


def generate_model(spec: GeometryRequest, output_dir: Path) -> dict:
    spec = GeometryRequest.model_validate(spec.model_dump())
    parameters = spec.model_dump(mode="json")
    _validate_geometry(parameters)
    output_dir = Path(output_dir)
    files = {"stl": "model.stl", "step": "model.step", "three_mf": "model.3mf", "source": "model.py"}
    for filename in files.values():
        target = output_dir / filename
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"기존 모델 파일을 덮어쓸 수 없습니다: {filename}")

    shape = _build_solid(parameters)
    bounds = shape.BoundingBox()
    dimensions = {axis: round(getattr(bounds, axis + "len"), 9) for axis in "xyz"}
    volume = shape.Volume()
    mesh = _preview_mesh(shape)
    edges = Counter(tuple(sorted((face[index], face[(index + 1) % 3])))
                    for face in mesh["faces"] for index in range(3))
    checks = [
        {"name": "valid_cad", "passed": shape.isValid(), "detail": "OpenCascade 형상 유효성 검사"},
        {"name": "single_solid", "passed": len(shape.Solids()) == 1, "detail": "연결된 솔리드 1개"},
        {"name": "positive_volume", "passed": math.isfinite(volume) and volume > 0,
         "detail": f"체적 {volume:.6f} mm³"},
        ({"name": "requested_dimensions",
          "passed": math.isclose(dimensions["z"], parameters["bottom"] + parameters["text_depth"], abs_tol=1e-6),
          "detail": "글자 길이로 정해지는 가로·세로 대신 받침+글자 높이를 비교"}
         if spec.template == "name_tag" else
         {"name": "requested_dimensions",
          "passed": all(math.isclose(dimensions[axis], parameters[key], abs_tol=1e-6)
                        for axis, key in zip("xyz", ("width", "depth", "height"))),
          "detail": "생성 형상의 외부 치수와 요청 치수 비교"}),
        {"name": "closed_preview_mesh", "passed": bool(edges) and all(count == 2 for count in edges.values()),
         "detail": "미리보기 메시의 모서리가 각각 두 면에 연결됨"},
    ]
    if not all(check["passed"] for check in checks):
        failed = ", ".join(check["name"] for check in checks if not check["passed"])
        raise ValueError(f"생성된 CAD 형상 검증 실패: {failed}")
    _export_cad(shape, output_dir)
    (output_dir / files["source"]).write_text(_reproduction_source(parameters), encoding="utf-8")
    warnings = ["CAD 형상 검증만 완료했습니다. 출력 성공·강도·치수 맞춤은 실제 프린터에서 확인해야 합니다."]
    if spec.template == "cable_comb":
        warnings.append("위가 열린 케이블 받침입니다. 스냅 고정이나 케이블 유지력을 보장하지 않습니다.")
    elif spec.template == "name_tag":
        warnings.append("이 PC의 시스템 글꼴(Arial 굵게, 없으면 대체 글꼴)로 글자를 만듭니다. 다른 PC에서 다시 만들면 글자 모양이 조금 다를 수 있고, 고리의 강도는 보장하지 않습니다.")
    elif spec.template == "phone_stand":
        warnings.append("기기 두께와 여유로 홈 폭을 정합니다. 실제 기기·케이스 두께와 넘어짐·충전 케이블 위치는 직접 확인하세요.")
    elif spec.template == "magnet_frame":
        warnings.append("원형 포켓의 여유값은 지름에 더합니다. 자석 고정력이나 구조 강도를 보장하지 않습니다.")
    return {"template": spec.template, "parameters": parameters, "dimensions_mm": dimensions,
            "volume_mm3": volume, "geometry_status": "validated", "print_status": "not_tested",
            "checks": checks, "files": files, "mesh": mesh, "warnings": warnings,
            "printability": _safe_printability(shape, parameters, mesh)}
