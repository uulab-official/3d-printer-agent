# Generated with CadQuery 2.7.0; all lengths are millimetres.
# This source reproduces geometry, not slicer settings or print success.
from pathlib import Path
import sys
import cadquery as cq

def _validate_geometry(p: dict) -> None:
    w, d, h, wall, bottom = (p[key] for key in ("width", "depth", "height", "wall", "bottom"))
    if p["template"] == "tray":
        if min(w, d) <= 2 * wall or h <= bottom:
            raise ValueError("수납함의 벽과 바닥 안쪽에 양수 크기의 공간이 필요합니다.")
        if w - 2 * wall - p["dividers"] * wall <= 0:
            raise ValueError("분할벽을 넣고 나면 칸의 너비가 남지 않습니다.")
    elif p["template"] == "cable_comb":
        diameter = p["cable_diameter"] + p["fit_clearance"]
        if p["slots"] * diameter + (p["slots"] + 1) * wall > w:
            raise ValueError("케이블 홈 사이와 양끝에 지정한 벽 두께를 확보할 수 없습니다.")
        if h < bottom + diameter / 2:
            raise ValueError("둥근 케이블 홈과 지정한 바닥 두께에 비해 높이가 부족합니다.")
    else:
        diameter = p["inset_diameter"] + p["fit_clearance"]
        if diameter + 2 * wall > min(w, d):
            raise ValueError("원형 포켓 바깥에 지정한 벽 두께가 남아야 합니다.")
        if h - p["inset_depth"] < bottom:
            raise ValueError("원형 포켓 아래에 지정한 바닥 두께가 남아야 합니다.")


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
    elif p["template"] == "magnet_frame":
        radius = (p["inset_diameter"] + p["fit_clearance"]) / 2
        pocket = cq.Solid.makeCylinder(radius, p["inset_depth"] + 1,
                                      cq.Vector(w / 2, d / 2, h - p["inset_depth"]))
        body = body.cut(pocket)
    else:
        raise ValueError("지원하지 않는 모델 템플릿입니다.")
    return body.clean().val()


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


PARAMETERS = {'template': 'tray', 'width': 120.0, 'depth': 80.0, 'height': 35.0, 'wall': 2.0, 'bottom': 2.0, 'dividers': 2, 'slots': 5, 'cable_diameter': 6.0, 'inset_diameter': 52.0, 'inset_depth': 2.0, 'fit_clearance': 0.3}

if __name__ == '__main__':
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'reproduced'
    _validate_geometry(PARAMETERS)
    result = _build_solid(PARAMETERS)
    if not result.isValid() or len(result.Solids()) != 1 or result.Volume() <= 0:
        raise ValueError('Reproduced CAD failed solid validation')
    _export_cad(result, destination)
