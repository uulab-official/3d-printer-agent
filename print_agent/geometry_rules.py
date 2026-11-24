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
    # Row sculpt: the top and dish tilt about the X axis through the top centre, so the
    # lower long edge drops by depth/2 · tan(tilt); the cavity stops below that edge.
    tilt = math.radians(p.get("top_tilt", 0) or 0)
    drop = top_d / 2 * abs(math.tan(tilt))
    cavity_top = p["height"] - dish - p["bottom"] - drop
    # Sculpted shell: at height fraction s each side has moved in inset · s^1.25 (a wall that
    # swells past a straight taper and rounds into the top) and the section has turned
    # tilt · s about its own centre, so a tilted top bends the whole wall smoothly.
    power, levels = 1.25, (0.0, 0.25, 0.5, 0.7, 0.85, 1.0)
    sections = [(s, width - 2 * inset * s ** power, depth - 2 * inset * s ** power, 1.2 + 1.7 * s, math.degrees(tilt) * s)
                for s in levels]
    def low_side(z):
        # Half-depth of the outer wall on the lower long side at height z (exact for the profile).
        lo, hi = 0.0, 1.0
        for _ in range(48):
            s = (lo + hi) / 2
            half = depth / 2 - inset * s ** power
            if s * p["height"] - half * math.sin(abs(tilt) * s) < z:
                lo = s
            else:
                hi = s
        return (depth / 2 - inset * lo ** power) * math.cos(tilt * lo)
    def inner(base, top):
        return base - (base - top) * cavity_top / p["height"] - 2 * p["wall"]
    # The cavity follows a straight taper; on a tilted key it also keeps the full wall on the lower side.
    cavity_depth = min(inner(depth, top_d), 2 * (low_side(max(cavity_top, 0)) - p["wall"]))
    return {"width": width, "depth": depth, "top_width": top_w, "top_depth": top_d,
            "sections": sections, "rim_radius": 0.4,
            "dish_radius": dish_radius, "dish_depth": dish, "cavity_top": cavity_top,
            "top_tilt": p.get("top_tilt", 0) or 0, "tilt_drop": drop,
            "cavity_top_width": inner(width, top_w), "cavity_top_depth": cavity_depth,
            "stem_diameter": stem, "cross_depth": cross_depth, "entry_chamfer": 0.3,
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
        radius = p.get("corner_radius", 0) or 0
        if radius and radius < 0.5:
            raise ValueError("모서리 반경은 0(각진 모서리)이거나 0.5 mm 이상으로 정하세요.")
        if radius > min(w, d) / 2 - 1:
            raise ValueError(f"모서리 반경은 짧은 변의 절반보다 작아야 합니다. {min(w, d) / 2 - 1:g} mm 이하로 줄이세요.")
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
        _edge_rounding_fits(p)
        if bottom + p["lip_height"] >= h:
            raise ValueError("끝 턱 높이와 걸이 두께가 전체 높이보다 낮아야 합니다.")
        if d < 2 * wall + 5:
            raise ValueError(f"걸이 길이(세로)는 등판·끝 턱 두께를 빼고 5 mm 이상 남아야 합니다. {2 * wall + 5:g} mm 이상으로 늘리세요.")
        if w < hole + 4:
            raise ValueError("나사 구멍 양옆에 2 mm 이상 남도록 가로를 늘리거나 구멍을 줄이세요.")
        if h - bottom < 3 * hole + 6:
            raise ValueError("나사 구멍 두 개가 들어가도록 높이를 늘리거나 구멍을 줄이세요.")
    elif p["template"] == "cup":
        # width is the outer diameter; depth is not used.
        inner = w - 2 * wall
        if inner < 10:
            raise ValueError(f"안쪽 지름이 10 mm 이상 남도록 지름을 {2 * wall + 10:g} mm 이상으로 늘리거나 벽을 얇게 하세요.")
        if h < bottom + 5:
            raise ValueError(f"바닥 위로 5 mm 이상 담을 공간이 남도록 높이를 {bottom + 5:g} mm 이상으로 정하세요.")
        hole = p["drain_hole"]
        if hole and hole < 3:
            raise ValueError("배수 구멍은 막히지 않도록 지름 3 mm 이상으로 하거나, 0으로 두어 구멍을 없애세요.")
        if hole and hole > inner - 6:
            raise ValueError(f"배수 구멍 둘레에 바닥이 3 mm 이상 남도록 구멍을 {inner - 6:g} mm 이하로 줄이세요.")
    elif p["template"] == "keycap":
        if not 6 <= h <= 14:
            raise ValueError("키캡 높이는 6~14 mm로 정하세요.")
        if not 0.8 <= wall <= 3:
            raise ValueError("키캡 옆벽 두께는 0.8~3 mm로 정하세요.")
        if not 1 <= bottom <= 4:
            raise ValueError("키캡 윗면 두께는 1~4 mm로 정하세요.")
        if not -12 <= p.get("top_tilt", 0) <= 12:
            raise ValueError("키캡 윗면 기울기는 −12~12°로 정하세요.")
        if p["fit_clearance"] > 0.5:
            raise ValueError("스템 십자 여유는 0~0.5 mm로 정하세요.")
        if p["text_depth"] > bottom - 0.6:
            raise ValueError(f"새긴 글자 아래에 0.6 mm 이상 남아야 합니다. 글자 깊이를 {bottom - 0.6:g} mm 이하로 줄이거나 윗면을 두껍게 하세요.")
        layout = keycap_layout(p)
        if layout["cavity_top"] < layout["cross_depth"] + 0.6:
            raise ValueError(f"스위치 스템이 들어갈 안쪽 높이({layout['cross_depth'] + 0.6:g} mm)가 부족합니다. 높이를 늘리거나 윗면 두께를 줄이세요"
                             + ("(윗면을 기울이면 낮은 쪽 가장자리가 내려가므로 기울기를 줄여도 됩니다)." if layout["top_tilt"] else "."))
        if layout["cavity_top_depth"] < layout["stem_diameter"] + 1:
            raise ValueError("옆벽이 두꺼워 안쪽에 스템이 들어갈 자리가 없습니다. 옆벽 두께를 줄이세요.")
        if p["text"].strip() and p["text_size"] > layout["top_depth"] - 2:
            raise ValueError(f"글자 크기는 윗면에 맞도록 {layout['top_depth'] - 2:g} mm 이하로 정하세요.")
    elif p["template"] == "phone_stand":
        import math
        _edge_rounding_fits(p)
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


def _edge_rounding_fits(p: dict) -> None:
    """A profile edge can be rounded by less than half of the thinner plate it sits on."""
    radius = p.get("corner_radius", 0) or 0
    limit = min(p["wall"], p["bottom"]) / 2 - 0.05
    if radius and radius < 0.3:
        raise ValueError("모서리 둥글기는 0(각진 모서리)이거나 0.3 mm 이상으로 정하세요.")
    if radius > limit:
        raise ValueError(f"모서리 둥글기는 얇은 판 두께의 절반보다 작아야 합니다. {max(limit, 0):.2f} mm 이하로 줄이거나 두께를 늘리세요.")
