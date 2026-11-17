"""Pure geometry constraints shared by CAD and contextual edits."""

def keycap_layout(p: dict) -> dict:
    """Derived Cherry MX-compatible keycap sizes in millimetres, shared with the CAD builder.

    Base pitch 19.05 mm per unit with a 1.05 mm gap, an 18 mm deep base, a top inset
    2.7 mm on each side, a cylindrical dish (radius 40 mm) that leaves 0.5 mm flat on
    the long top edges, and a 5.6 mm stem with a 4.0 x 1.17 mm cross plus clearance."""
    import math
    pitch, gap, depth, inset, dish_radius, dish_edge = 19.05, 1.05, 18.0, 2.7, 40.0, 0.5
    stem, cross_length, cross_width, cross_depth = 5.6, 4.0, 1.17, 4.0
    width = round(p["key_units"] * pitch - gap, 6)
    top_w, top_d = width - 2 * inset, depth - 2 * inset
    half = top_d / 2 - dish_edge
    dish = dish_radius - math.sqrt(dish_radius ** 2 - half ** 2)
    cavity_top = p["height"] - dish - p["bottom"]
    def inner(base, top):
        return base - (base - top) * cavity_top / p["height"] - 2 * p["wall"]
    return {"width": width, "depth": depth, "top_width": top_w, "top_depth": top_d,
            "dish_radius": dish_radius, "dish_depth": dish, "cavity_top": cavity_top,
            "cavity_top_width": inner(width, top_w), "cavity_top_depth": inner(depth, top_d),
            "stem_diameter": stem, "cross_depth": cross_depth,
            "cross": (round(cross_length + p["fit_clearance"], 6), round(cross_width + p["fit_clearance"], 6)),
            "stem_ring": (stem - cross_length - p["fit_clearance"]) / 2,
            # Cherry plate-mounted stabilizer offsets from the centre stem.
            "stabilizers": {2.0: 11.938, 2.25: 11.938, 2.75: 11.938, 6.25: 50.0, 7.0: 57.15}.get(p["key_units"])}


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
    elif p["template"] == "wall_hook":
        hole = p["hole_diameter"]
        if bottom + p["lip_height"] >= h:
            raise ValueError("끝 턱 높이와 걸이 두께가 전체 높이보다 낮아야 합니다.")
        if d < 2 * wall + 5:
            raise ValueError(f"걸이 길이(세로)는 등판·끝 턱 두께를 빼고 5 mm 이상 남아야 합니다. {2 * wall + 5:g} mm 이상으로 늘리세요.")
        if w < hole + 4:
            raise ValueError("나사 구멍 양옆에 2 mm 이상 남도록 가로를 늘리거나 구멍을 줄이세요.")
        if h - bottom < 3 * hole + 6:
            raise ValueError("나사 구멍 두 개가 들어가도록 높이를 늘리거나 구멍을 줄이세요.")
    elif p["template"] == "keycap":
        if not 6 <= h <= 14:
            raise ValueError("키캡 높이는 6~14 mm로 정하세요.")
        if not 0.8 <= wall <= 3:
            raise ValueError("키캡 옆벽 두께는 0.8~3 mm로 정하세요.")
        if not 1 <= bottom <= 4:
            raise ValueError("키캡 윗면 두께는 1~4 mm로 정하세요.")
        if p["fit_clearance"] > 0.5:
            raise ValueError("스템 십자 여유는 0~0.5 mm로 정하세요.")
        if p["text_depth"] > bottom - 0.6:
            raise ValueError(f"새긴 글자 아래에 0.6 mm 이상 남아야 합니다. 글자 깊이를 {bottom - 0.6:g} mm 이하로 줄이거나 윗면을 두껍게 하세요.")
        layout = keycap_layout(p)
        if layout["cavity_top"] < layout["cross_depth"] + 0.6:
            raise ValueError(f"스위치 스템이 들어갈 안쪽 높이({layout['cross_depth'] + 0.6:g} mm)가 부족합니다. 높이를 늘리거나 윗면 두께를 줄이세요.")
        if layout["cavity_top_depth"] < layout["stem_diameter"] + 1:
            raise ValueError("옆벽이 두꺼워 안쪽에 스템이 들어갈 자리가 없습니다. 옆벽 두께를 줄이세요.")
        if p["text"].strip() and p["text_size"] > layout["top_depth"] - 2:
            raise ValueError(f"글자 크기는 윗면에 맞도록 {layout['top_depth'] - 2:g} mm 이하로 정하세요.")
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
