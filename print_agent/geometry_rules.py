"""Pure geometry constraints shared by CAD and contextual edits."""

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
