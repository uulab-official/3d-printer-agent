"""Deterministic, millimetre-based CAD templates and their export evidence."""

from collections import Counter
import inspect
import math
from pathlib import Path
import zipfile

import cadquery as cq

from .schemas import PALETTE, GeometryRequest
from .geometry_rules import _validate_geometry
from .printability import assess_printability


def template_catalog() -> list[dict]:
    catalog = [
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
        {"id": "wall_hook", "title": "벽걸이 후크",
         "description": "나사 구멍 두 개가 있는 등판과 앞으로 나온 걸이, 끝 턱으로 된 후크입니다. 놓인 방향 그대로 서포트 없이 출력합니다.",
         "defaults": {"width": 20, "depth": 35, "height": 50, "wall": 4, "bottom": 4, "hole_diameter": 4, "lip_height": 10},
         "editable_fields": ["width", "depth", "height", "wall", "bottom", "hole_diameter", "lip_height"]},
        {"id": "phone_stand", "title": "휴대폰 거치대",
         "description": "앞턱과 기울어진 등판 사이에 휴대폰을 세워 두는 거치대입니다.",
         "defaults": {"width": 70, "depth": 80, "height": 90, "wall": 4, "bottom": 4,
                      "lean_angle": 65, "device_thickness": 12, "lip_height": 12, "fit_clearance": 1},
         "editable_fields": ["width", "depth", "height", "wall", "bottom", "lean_angle",
                             "device_thickness", "lip_height", "fit_clearance"]},
    ]
    # Colours are optional on every template; letters get their own colour only on a name tag.
    for item in catalog:
        extra = ["color", "accent_color"] if item["id"] == "name_tag" else ["color"]
        item["defaults"] = {**item["defaults"], **{key: "" for key in extra}}
        item["editable_fields"] = [*item["editable_fields"], *extra]
    return catalog


def _name_tag_font() -> dict:
    """Pinned, known-good bold sans fonts per platform; a font name only as a last resort.

    Some decorative fonts have overlapping outlines that make invalid solids, so the
    template never picks an arbitrary system font.
    """
    import os
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return {"fontPath": path, "label": os.path.basename(path)}
    return {"font": "Arial", "label": "Arial(시스템 대체 글꼴)"}


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
        font = _name_tag_font()
        options = {"fontPath": font["fontPath"]} if "fontPath" in font else {"font": font["font"], "kind": "bold"}
        letters = cq.Workplane("XY").text(text, p["text_size"], p["text_depth"], combine=False,
                                          halign="left", valign="bottom", **options)
        if not letters.val().isValid():
            raise ValueError(f"이 PC의 글꼴({font['label']})로 만든 글자 형상이 올바르지 않습니다. 글자 크기를 키우거나 글자를 바꿔 다시 시도하세요.")
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
    elif p["template"] == "wall_hook":
        # Printed as modelled: the arm lies on the bed, the back plate and tip stand up (no supports).
        arm = cq.Workplane("XY").box(w, d, bottom, centered=False)
        back = cq.Workplane("XY").box(w, wall, h, centered=False)
        tip = cq.Workplane("XY").box(w, wall, bottom + p["lip_height"], centered=False).translate((0, d - wall, 0))
        body = arm.union(back).union(tip)
        # Teardrop screw holes: the top closes at 45° so the horizontal hole prints without support.
        import math
        radius = p["hole_diameter"] / 2
        tangent = radius * math.sqrt(0.5)
        for z in (bottom + (h - bottom) * 0.45, bottom + (h - bottom) * 0.8):
            screw = cq.Workplane("XZ").workplane(offset=1).center(w / 2, z).circle(radius).extrude(-(wall + 2))
            point = (cq.Workplane("XZ").workplane(offset=1).center(w / 2, z)
                     .polyline([(-tangent, tangent), (0, radius * math.sqrt(2)), (tangent, tangent)]).close().extrude(-(wall + 2)))
            body = body.cut(screw.union(point))
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


def color_parts(parameters: dict) -> list[dict]:
    """Named colour parts of the model; empty when no colour was chosen.

    A name tag whose letters have their own colour has two parts split at the
    plate top: the plate (filament 1) and the raised letters (filament 2)."""
    body, accent = parameters.get("color", ""), parameters.get("accent_color", "")
    if not body and not accent:
        return []
    def part(key, label, color, filament):
        return {"key": key, "label": label, "color": color or "",
                "name": PALETTE[color][0] if color else "기본 필라멘트",
                "hex": PALETTE[color][1] if color else None, "filament": filament}
    if parameters["template"] == "name_tag" and accent and accent != body:
        return [part("base", "받침", body, 1), part("letters", "글자", accent, 2)]
    return [part("body", "모델 전체", body or accent, 1)]


def _split_letters(shape: cq.Shape, bottom: float) -> tuple[cq.Shape, cq.Shape]:
    """Cut a name tag at the plate top into the plate and the letters above it."""
    bounds = shape.BoundingBox()
    span = 2 * max(bounds.xlen, bounds.ylen, bounds.zlen) + 10
    below = cq.Solid.makeBox(span, span, bottom + span, cq.Vector(bounds.xmin - span / 4, bounds.ymin - span / 4, -span))
    above = cq.Solid.makeBox(span, span, span, cq.Vector(bounds.xmin - span / 4, bounds.ymin - span / 4, bottom))
    return shape.intersect(below), shape.intersect(above)


def _face_parts(mesh: dict, parameters: dict, parts: list[dict]) -> list[int] | None:
    if len(parts) < 2:
        return None
    limit = parameters["bottom"] + 1e-6
    vertices = mesh["vertices"]
    return [1 if sum(vertices[index][2] for index in face) / 3 > limit else 0 for face in mesh["faces"]]


def _colored_three_mf(parts_meshes: list[tuple[dict, dict]], target: Path) -> None:
    """A Bambu Studio project-style 3MF: one object whose parts carry their filament number.

    Only geometry and the per-part filament assignment are written; printer,
    process and filament settings come from the person's own Studio setup."""
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"기존 모델 파일을 덮어쓸 수 없습니다: {target.name}")
    xs = [vertex[0] for _, mesh in parts_meshes for vertex in mesh["vertices"]]
    ys = [vertex[1] for _, mesh in parts_meshes for vertex in mesh["vertices"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    objects, components, settings = [], [], []
    for index, (part, mesh) in enumerate(parts_meshes, start=1):
        vertices = "".join(f'<vertex x="{x - cx:.6f}" y="{y - cy:.6f}" z="{z:.6f}"/>' for x, y, z in mesh["vertices"])
        triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh["faces"])
        objects.append(f'<object id="{index}" type="model"><mesh><vertices>{vertices}</vertices>'
                       f'<triangles>{triangles}</triangles></mesh></object>')
        components.append(f'<component objectid="{index}"/>')
        settings.append(f'<part id="{index}" subtype="normal_part"><metadata key="name" value="{part["label"]} ({part["name"]})"/>'
                        '<metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>'
                        f'<metadata key="extruder" value="{part["filament"]}"/></part>')
    parent = len(parts_meshes) + 1
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">'
             '<metadata name="Application">3D Printer Agent</metadata><metadata name="BambuStudio:3mfVersion">1</metadata>'
             f'<resources>{"".join(objects)}<object id="{parent}" type="model"><components>{"".join(components)}</components></object></resources>'
             f'<build><item objectid="{parent}" transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1"/></build></model>')
    config = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>'
              f'<object id="{parent}"><metadata key="name" value="colored model"/><metadata key="extruder" value="1"/>'
              f'{"".join(settings)}</object></config>')
    types = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '<Default Extension="config" ContentType="text/xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("[Content_Types].xml", types), ("_rels/.rels", rels),
                              ("3D/3dmodel.model", model), ("Metadata/model_settings.config", config)):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)


def _reproduction_source(parameters: dict) -> str:
    preamble = ("# Generated with CadQuery " + cq.__version__ + "; all lengths are millimetres.\n"
                "# This source reproduces geometry, not slicer settings or print success.\n"
                "from pathlib import Path\nimport sys\nimport cadquery as cq\n\n")
    functions = "\n\n".join(inspect.getsource(fn) for fn in (_validate_geometry, _name_tag_font, _build_solid, _export_cad))
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
    parts = color_parts(parameters)
    if len(parts) > 1:
        files["color_three_mf"] = "model-colors.3mf"
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
    color_volumes = None
    if len(parts) > 1:
        plate, letters = _split_letters(shape, parameters["bottom"])
        pieces = [(plate, parts[0]), (letters, parts[1])]
        split_volume = sum(piece.Volume() for piece, _ in pieces)
        if not all(piece.isValid() and piece.Volume() > 0 for piece, _ in pieces) or not math.isclose(split_volume, volume, rel_tol=1e-6):
            raise ValueError("색별 부품으로 나눈 형상이 원래 모델과 다릅니다.")
        color_volumes = [piece.Volume() for piece, _ in pieces]
    _export_cad(shape, output_dir)
    if len(parts) > 1:
        _colored_three_mf([(part, _preview_mesh(piece)) for piece, part in pieces], output_dir / files["color_three_mf"])
    if parts:
        mesh["parts"] = [{key: part[key] for key in ("key", "label", "name", "hex")} for part in parts]
        face_parts = _face_parts(mesh, parameters, parts)
        if face_parts is not None:
            mesh["face_parts"] = face_parts
        for index, part in enumerate(parts):
            part["volume_mm3"] = color_volumes[index] if color_volumes else volume
    (output_dir / files["source"]).write_text(_reproduction_source(parameters), encoding="utf-8")
    warnings = ["CAD 형상 검증만 완료했습니다. 출력 성공·강도·치수 맞춤은 실제 프린터에서 확인해야 합니다."]
    if spec.template == "cable_comb":
        warnings.append("위가 열린 케이블 받침입니다. 스냅 고정이나 케이블 유지력을 보장하지 않습니다.")
    elif spec.template == "name_tag":
        warnings.append(f"글꼴 {_name_tag_font()['label']}로 글자를 만들었습니다. 운영체제마다 정해진 굵은 글꼴(Arial Bold·DejaVu Sans Bold)을 쓰므로 다른 PC에서는 글자 모양이 조금 다를 수 있고, 고리의 강도는 보장하지 않습니다.")
    elif spec.template == "wall_hook":
        warnings.append("걸 물건의 무게와 벽 재질에 맞는 나사·앵커를 쓰세요. 후크의 하중이나 벽 고정력은 보장하지 않습니다.")
    elif spec.template == "phone_stand":
        warnings.append("기기 두께와 여유로 홈 폭을 정합니다. 실제 기기·케이스 두께와 넘어짐·충전 케이블 위치는 직접 확인하세요.")
    elif spec.template == "magnet_frame":
        warnings.append("원형 포켓의 여유값은 지름에 더합니다. 자석 고정력이나 구조 강도를 보장하지 않습니다.")
    if len(parts) > 1:
        warnings.append("받침(필라멘트 1)과 글자(필라멘트 2)를 나눈 색상 3MF를 함께 만들었습니다. 두 색을 한 번에 출력하려면 AMS 등 자동 필라멘트 교체가 필요하며, Studio에서 각 필라멘트 슬롯의 실제 색을 확인하세요.")
    elif parts:
        warnings.append(f"모델 색은 {parts[0]['name']}입니다. 화면 색은 비슷하게 보여 줄 뿐이며, 출력 색은 프린터에 넣은 필라멘트가 정합니다.")
    return {"template": spec.template, "parameters": parameters, "dimensions_mm": dimensions,
            "color_parts": parts,
            "volume_mm3": volume, "geometry_status": "validated", "print_status": "not_tested",
            "checks": checks, "files": files, "mesh": mesh, "warnings": warnings,
            "printability": _safe_printability(shape, parameters, mesh)}
