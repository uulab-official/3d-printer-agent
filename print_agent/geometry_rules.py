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
    elif p["template"] == "name_tag":
        if p["hole_diameter"] > p["text_size"]:
            raise ValueError("고리 구멍이 글자 높이보다 클 수 없습니다. 구멍 지름을 줄이거나 글자를 키우세요.")
    elif p["template"] == "phone_stand":
        import math
        slot_front = wall + p["device_thickness"] + p["fit_clearance"]
        lean = math.radians(90 - p["lean_angle"])
        reach = slot_front + (h - bottom) * math.tan(lean) + wall / math.cos(lean)
        if bottom + p["lip_height"] >= h:
            raise ValueError("앞턱 높이와 바닥 두께가 전체 높이보다 낮아야 합니다.")
        if reach > d:
            raise ValueError(f"기울어진 등판이 바닥 밖으로 나갑니다. 세로(깊이)를 {math.ceil(reach)} mm 이상으로 늘리거나 높이·기울기를 줄이세요.")
    else:
        diameter = p["inset_diameter"] + p["fit_clearance"]
        if diameter + 2 * wall > min(w, d):
            raise ValueError("원형 포켓 바깥에 지정한 벽 두께가 남아야 합니다.")
        if h - p["inset_depth"] < bottom:
            raise ValueError("원형 포켓 아래에 지정한 바닥 두께가 남아야 합니다.")
