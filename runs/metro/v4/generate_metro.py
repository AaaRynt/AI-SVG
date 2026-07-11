#!/usr/bin/env python3
"""Generate the Ningcang v4 metro experiment from corridor-first route skeletons.

The generator is intentionally staged.  Candidate skeletons are generated and
reviewed before the station network and final bilingual map are produced.
Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import math
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
W, H = 3000, 2000
MAP_RIGHT = 2500
GRID = 20


LINE_DEFS = [
    {"id": "L1", "nameZh": "沧江一号线", "nameEn": "Cangjiang Line 1", "color": "#C83E4D", "type": "metro", "status": "operational", "width": 10,
     "points": [(320, 780), (2160, 780), (2380, 560)]},
    {"id": "L2", "nameZh": "南北二号线", "nameEn": "North–South Line 2", "color": "#2F5FA7", "type": "metro", "status": "operational", "width": 10,
     "points": [(1360, 240), (1360, 1560), (1580, 1780)]},
    {"id": "L3", "nameZh": "书岭三号线", "nameEn": "Shuling Line 3", "color": "#009B77", "type": "metro", "status": "operational", "width": 10,
     "points": [(520, 1480), (520, 1320), (920, 920), (920, 720), (1300, 720), (1500, 520), (2200, 520)]},
    {"id": "L4", "nameZh": "云港四号线", "nameEn": "Yungang Line 4", "color": "#E8792E", "type": "metro", "status": "operational", "width": 10,
     "points": [(260, 360), (560, 360), (980, 780), (1440, 780), (2050, 1390), (2320, 1390)]},
    {"id": "L5", "nameZh": "南岸五号线", "nameEn": "South Bank Line 5", "color": "#8558A8", "type": "metro", "status": "operational", "width": 10,
     "points": [(480, 1210), (2100, 1210), (2450, 1560)]},
    {"id": "L6", "nameZh": "内环六号线", "nameEn": "Inner Ring Line 6", "color": "#C49A00", "type": "ring", "status": "operational", "width": 12,
     "points": [(820, 520), (1750, 520), (2070, 840), (2070, 1160), (1780, 1450), (1080, 1450), (780, 1150), (780, 560), (820, 520)]},
    {"id": "L7", "nameZh": "洲心七号线", "nameEn": "Zhouxin Line 7", "color": "#00A6B2", "type": "metro", "status": "operational", "width": 10,
     "points": [(900, 260), (900, 620), (1180, 900), (1180, 1060), (1480, 1360), (1480, 1720)]},
    {"id": "L8", "nameZh": "机厂八号线", "nameEn": "Jichang Line 8", "color": "#8C4A32", "type": "metro", "status": "operational", "width": 10,
     "points": [(360, 520), (740, 520), (1040, 820), (1040, 1040), (1320, 1320), (1900, 1320), (2140, 1560)]},
    {"id": "L9", "nameZh": "西南九号线", "nameEn": "Southwest Line 9", "color": "#D0448D", "type": "metro", "status": "operational", "width": 10,
     "points": [(180, 1580), (620, 1580), (980, 1220), (1320, 1220), (1680, 860), (2280, 860)]},
    {"id": "L10", "nameZh": "临港十号线", "nameEn": "Lingang Line 10", "color": "#658B2A", "type": "metro", "status": "operational", "width": 10,
     "points": [(1700, 240), (1700, 620), (1920, 840), (1920, 1060), (2360, 1500), (2540, 1500)]},
    {"id": "L11", "nameZh": "东弧十一号线", "nameEn": "Eastern Arc Line 11", "color": "#436B8A", "type": "semi-ring", "status": "operational", "width": 10,
     "points": [(1050, 280), (1920, 280), (2400, 760), (2400, 1120), (2080, 1440), (1760, 1440)]},
    {"id": "L12", "nameZh": "科城十二号线", "nameEn": "Science City Line 12", "color": "#008DB8", "type": "metro", "status": "operational", "width": 10,
     "points": [(1480, 600), (2280, 600), (2520, 840)]},
    {"id": "L13", "nameZh": "海门机场快线", "nameEn": "Haimen Airport Express", "color": "#D7263D", "type": "airport-express", "status": "operational", "width": 12,
     "points": [(1080, 420), (1480, 420), (1680, 620), (1680, 800), (2300, 1420)]},
    {"id": "L14", "nameZh": "宁西市域快线", "nameEn": "Ningxi Regional Express", "color": "#6F2DBD", "type": "regional-express", "status": "operational", "width": 12,
     "points": [(220, 320), (620, 320), (1020, 720), (1500, 720), (1700, 920), (2300, 1520)]},
    {"id": "L15", "nameZh": "滨海十五号线", "nameEn": "Coastal Line 15", "color": "#73777F", "type": "metro", "status": "under-construction", "width": 10,
     "points": [(620, 1740), (980, 1740), (1280, 1440), (1800, 1440), (2180, 1060), (2480, 1060)]},
    {"id": "B1", "nameZh": "十号线港区支线", "nameEn": "Line 10 Harbor Branch", "color": "#658B2A", "type": "branch", "status": "operational", "width": 8,
     "branchOf": "L10", "points": [(1920, 1060), (2220, 1060), (2500, 1340)]},
    {"id": "B2", "nameZh": "三号线书岭支线", "nameEn": "Line 3 Shuling Branch", "color": "#009B77", "type": "branch", "status": "operational", "width": 8,
     "branchOf": "L3", "points": [(520, 1320), (320, 1320), (180, 1460)]},
]


ZONES = [
    ("西部丘陵与宁西卫星城", "Western Hills & Ningxi", 130, 240, 570, 420, "#E8F0E1"),
    ("北部新城", "Northern New City", 1030, 190, 910, 320, "#EDF2F7"),
    ("传统老城", "Historic City", 760, 560, 540, 370, "#F6EEE3"),
    ("中央商务区", "Central Business District", 1430, 540, 420, 330, "#F2EDF7"),
    ("东部科技城", "Eastern Science City", 1900, 420, 500, 380, "#E7F3F1"),
    ("书岭大学城", "Shuling University Town", 420, 1190, 620, 410, "#EEF4E7"),
    ("南岸金融文化区", "South Bank Center", 1240, 1060, 620, 400, "#F4EDF3"),
    ("滨海新城与航空港", "Coastal New City & Airport", 1810, 1260, 650, 420, "#EAF2F7"),
]


MAJOR_NODES = [
    (980, 780, "人民广场"), (1360, 780, "沧江路"), (1680, 780, "金融城"),
    (1360, 1060, "白鹭洲"), (1680, 1210, "南岸中心"), (1700, 520, "北站"),
    (520, 1320, "书岭"), (2070, 840, "科城西"), (2300, 1420, "海门机场"),
]


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def path_d(points: list[tuple[float, float]], close: bool = False) -> str:
    parts = [f"M {fmt(points[0][0])} {fmt(points[0][1])}"]
    for x, y in points[1:]:
        parts.append(f"L {fmt(x)} {fmt(y)}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def svg_header(title: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<title>{html.escape(title)}</title>',
        '<desc>Original fictional metro map for Ningcang. Static, self-contained SVG.</desc>',
        '<rect width="3000" height="2000" fill="#F8FAFC"/>',
    ]


def geography_svg() -> list[str]:
    out = ['<g id="geography">']
    for zh, en, x, y, w, h, fill in ZONES:
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="52" fill="{fill}" opacity="0.68"/>')
        out.append(f'<text x="{x+26}" y="{y+42}" font-size="24" font-weight="650" fill="#68747F">{html.escape(zh)}</text>')
        out.append(f'<text x="{x+26}" y="{y+67}" font-size="13" fill="#8C969E">{html.escape(en)}</text>')
    out.extend([
        '<path d="M 100 925 C 500 900 760 930 1030 948 C 1320 968 1650 928 1910 940 C 2180 952 2390 920 2590 860 L 2590 1060 C 2370 1080 2190 1070 1950 1040 C 1650 1004 1360 1050 1040 1028 C 700 1004 420 1020 100 1045 Z" fill="#DCEFF6"/>',
        '<path d="M 2490 790 C 2630 860 2750 990 2860 1200 L 3000 2000 L 2350 2000 C 2420 1750 2470 1490 2500 1260 C 2520 1080 2500 920 2490 790 Z" fill="#D6EBF3"/>',
        '<path d="M 1210 935 L 1440 920 L 1550 978 L 1430 1042 L 1195 1028 L 1135 982 Z" fill="#F8FAFC" stroke="#B8D5E0" stroke-width="3"/>',
        '<path d="M 210 1690 L 470 1430 L 640 1510 L 490 1750 Z" fill="#DCE8D7" opacity="0.9"/>',
        '<path d="M 330 1510 C 430 1460 540 1470 620 1540 C 560 1620 440 1650 340 1605 Z" fill="#C9E1EA"/>',
        '<text x="1830" y="1000" font-size="34" font-weight="650" fill="#73A7BA" transform="rotate(-2 1830 1000)">沧江 · CANGJIANG RIVER</text>',
        '<text x="2700" y="1320" font-size="42" font-weight="650" fill="#77A9BA" transform="rotate(78 2700 1320)">澄湾 · CHENG BAY</text>',
        '<text x="1250" y="995" font-size="22" font-weight="650" fill="#668C78">白鹭洲 Bailuzhou</text>',
        '<text x="270" y="1740" font-size="20" fill="#66816B">书岭生态保育区</text>',
    ])
    out.append('</g>')
    return out


def route_variant(candidate: int) -> list[dict]:
    lines = copy.deepcopy(LINE_DEFS)
    by_id = {line["id"]: line for line in lines}
    if candidate == 1:
        # Deliberately over-centralized: too many services converge on one node.
        hub = (1460, 900)
        for lid in ("L1", "L3", "L4", "L5", "L7", "L8", "L9", "L10", "L13", "L14"):
            pts = by_id[lid]["points"]
            by_id[lid]["points"] = [pts[0], hub, pts[-1]]
    elif candidate == 2:
        # An over-wide ring and long through diagonals weaken the core hierarchy.
        by_id["L6"]["points"] = [(600, 420), (1980, 420), (2300, 740), (2300, 1360), (2020, 1640), (720, 1640), (520, 1440), (520, 500), (600, 420)]
        by_id["L8"]["points"] = [(360, 520), (820, 520), (1920, 1620), (2160, 1620)]
        by_id["L9"]["points"] = [(180, 1580), (620, 1580), (1720, 480), (2280, 480)]
    elif candidate == 3:
        # Strong axes, but east-side services crowd the CBD gateway.
        for lid in ("L10", "L11", "L12", "L13"):
            pts = by_id[lid]["points"]
            by_id[lid]["points"] = [pts[0], (1820, 760), (2050, 990), pts[-1]]
    elif candidate in (5, 6, 7, 8):
        # Full corridor rewrite: three stable horizontal axes, three north-south
        # axes, a compact ring, and only a few intentional diagonal trunks.
        rewritten = {
            "L1": [(320, 760), (2380, 760)],
            "L2": [(1360, 240), (1360, 1760)],
            "L3": [(520, 1480), (520, 1320), (920, 920), (920, 660), (1320, 660), (1480, 500), (2200, 500)],
            "L4": [(260, 360), (560, 360), (980, 780), (1500, 780), (2100, 1380), (2320, 1380)],
            "L5": [(480, 1220), (2100, 1220), (2440, 1560)],
            "L6": [(820, 520), (1750, 520), (2070, 840), (2070, 1160), (1780, 1450), (1080, 1450), (780, 1150), (780, 560), (820, 520)],
            "L7": [(1040, 260), (1040, 620), (1200, 780), (1200, 1100), (1480, 1380), (1480, 1720)],
            "L8": [(360, 520), (740, 520), (1040, 820), (1040, 1320), (1900, 1320), (2140, 1560)],
            "L9": [(180, 1580), (620, 1580), (980, 1220), (1320, 1220), (1680, 860), (2280, 860)],
            "L10": [(1900, 240), (1900, 640), (2060, 800), (2060, 1100), (2460, 1500)],
            "L11": [(1050, 280), (1920, 280), (2400, 760), (2400, 1120), (2080, 1440), (1760, 1440)],
            "L12": [(1480, 620), (2280, 620), (2480, 820)],
            "L13": [(1120, 420), (1540, 420), (1700, 580), (1700, 900), (2280, 1480)],
            "L14": [(220, 320), (620, 320), (1020, 720), (1500, 720)],
            "L15": [(620, 1740), (980, 1740), (1280, 1440), (1800, 1440), (2180, 1060), (2480, 1060)],
            "B1": [(2060, 1100), (2320, 1100), (2500, 1280)],
            "B2": [(520, 1320), (320, 1320), (180, 1460)],
        }
        if candidate in (6, 7, 8):
            # Second rewrite: move the southwest crosstown below the ring and
            # separate the airport express from the ordinary airport metro.
            rewritten["L9"] = [(180, 1580), (720, 1580), (720, 1380), (1000, 1100), (1400, 1100), (1660, 840), (2280, 840)]
            rewritten["L13"] = [(1120, 420), (1540, 420), (1700, 580), (1700, 940), (2240, 1480)]
            rewritten["L4"] = [(260, 360), (560, 360), (980, 780), (1500, 780), (2040, 1320), (2320, 1320)]
        if candidate in (7, 8):
            # Remove the unnecessary southern construction arc and the old
            # industrial tail from the airport fan.  These services now end at
            # real destinations instead of filling empty coastline.
            rewritten["L15"] = [(620, 1740), (980, 1740), (1280, 1440), (1800, 1440)]
            rewritten["L8"] = [(360, 520), (740, 520), (1040, 820), (1040, 1320), (1900, 1320)]
        if candidate == 8:
            # Final refinement: the local science-city and southwest services
            # terminate at their subcentres rather than crossing the outer arc.
            rewritten["L12"] = [(1480, 620), (2280, 620)]
            rewritten["L9"] = [(180, 1580), (720, 1580), (720, 1380), (1000, 1100), (1400, 1100), (1660, 840), (2000, 840)]
            # Both airports are genuine shared terminals: the western airport
            # is served by L4 and the regional express; the international
            # airport by L4 and the airport express.
            rewritten["L4"] = [(260, 360), (560, 360), (980, 780), (1500, 780), (2040, 1320), (2200, 1480), (2240, 1480)]
            rewritten["L14"] = [(260, 360), (260, 320), (620, 320), (1020, 720), (1500, 720)]
        for lid, points in rewritten.items():
            by_id[lid]["points"] = points
    return lines


def angle_deviation(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return 0.0
    angle = math.degrees(math.atan2(dy, dx)) % 360
    return min(abs(((angle - allowed + 180) % 360) - 180) for allowed in range(0, 360, 45))


def orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def proper_intersection(a, b, c, d) -> bool:
    # Count proper crossings only; shared endpoints and collinear corridors are excluded.
    if a in (c, d) or b in (c, d):
        return False
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 == 0 or o2 == 0 or o1 * o2 < 0) and (o3 == 0 or o4 == 0 or o3 * o4 < 0) and not (o1 == o2 == o3 == o4 == 0)


def segment_intersection(a, b, c, d, eps: float = 1e-7):
    """Return a unique point intersection for two non-collinear segments."""
    x1, y1 = a
    x2, y2 = b
    x3, y3 = c
    x4, y4 = d
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < eps:
        # Collinear shared corridors are not single transfer points. Exact
        # shared endpoints are handled as junctions.
        shared = set((a, b)).intersection((c, d))
        return next(iter(shared)) if len(shared) == 1 else None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    if (min(x1, x2) - eps <= px <= max(x1, x2) + eps and
            min(y1, y2) - eps <= py <= max(y1, y2) + eps and
            min(x3, x4) - eps <= px <= max(x3, x4) + eps and
            min(y3, y4) - eps <= py <= max(y3, y4) + eps):
        return (round(px, 3), round(py, 3))
    return None


def intersection_clusters(lines: list[dict]) -> list[dict]:
    clusters: dict[tuple[float, float], set[str]] = {}
    for i, first in enumerate(lines):
        for second in lines[i + 1:]:
            points = set()
            for a, b in zip(first["points"], first["points"][1:]):
                for c, d in zip(second["points"], second["points"][1:]):
                    point = segment_intersection(a, b, c, d)
                    if point is not None:
                        points.add(point)
            for point in points:
                clusters.setdefault(point, set()).update((first["id"], second["id"]))
    result = []
    for (x, y), memberships in clusters.items():
        result.append({"x": x, "y": y, "lines": sorted(memberships)})
    return sorted(result, key=lambda item: (-len(item["lines"]), abs(item["x"] - 1450) + abs(item["y"] - 950), item["x"], item["y"]))


def skeleton_metrics(lines: list[dict]) -> dict:
    deviations, bends, long_segments = [], 0, 0
    segments = []
    for line in lines:
        pts = line["points"]
        bends += max(0, len(pts) - 2)
        for a, b in zip(pts, pts[1:]):
            deviations.append(angle_deviation(a, b))
            if math.dist(a, b) > 580:
                long_segments += 1
            segments.append((line["id"], a, b))
    crossings = 0
    for i, (lid1, a, b) in enumerate(segments):
        for lid2, c, d in segments[i + 1:]:
            if lid1 != lid2 and proper_intersection(a, b, c, d):
                crossings += 1
    return {
        "lineCount": len(lines),
        "segmentCount": len(segments),
        "nonOctilinearSegmentCount": sum(d > 1.5 for d in deviations),
        "maximumAngleDeviation": round(max(deviations, default=0), 3),
        "rawProperCrossingCount": crossings,
        "totalBendCount": bends,
        "overlongSegmentCount": long_segments,
        "ringLineClosed": by_id(lines, "L6")["points"][0] == by_id(lines, "L6")["points"][-1],
    }


def by_id(lines: list[dict], line_id: str) -> dict:
    return next(line for line in lines if line["id"] == line_id)


def write_skeleton_svg(path: Path, lines: list[dict], candidate: int) -> None:
    out = svg_header(f"Ningcang Metro Skeleton Candidate {candidate:02d}")
    out.extend(geography_svg())
    out.append('<g id="routes" fill="none" stroke-linecap="round" stroke-linejoin="round">')
    for line in lines:
        dash = ' stroke-dasharray="22 16"' if line["status"] == "under-construction" else ""
        if line["type"] in ("airport-express", "regional-express"):
            out.append(f'<path d="{path_d(line["points"])}" stroke="#FFFFFF" stroke-width="{line["width"] + 8}" opacity="0.92"/>')
        out.append(f'<path data-line="{line["id"]}" d="{path_d(line["points"])}" stroke="{line["color"]}" stroke-width="{line["width"]}"{dash}/>' )
    out.append('</g>')
    out.append('<g id="major-nodes">')
    for x, y, label in MAJOR_NODES:
        out.append(f'<circle cx="{x}" cy="{y}" r="14" fill="#FFFFFF" stroke="#26343D" stroke-width="4"/>')
        out.append(f'<text x="{x+20}" y="{y-16}" font-size="20" font-weight="650" fill="#33434D">{label}</text>')
    out.append('</g>')
    out.extend([
        '<rect x="60" y="46" width="1040" height="100" rx="18" fill="#FFFFFF" opacity="0.94"/>',
        f'<text x="92" y="93" font-size="34" font-weight="750" fill="#1D2A32">宁沧轨道交通 · 骨架候选 {candidate:02d}</text>',
        '<text x="92" y="124" font-size="18" fill="#65737C">NINGCANG METRO · CORRIDOR-FIRST OCTILINEAR SKELETON</text>',
        '<text x="2420" y="1900" text-anchor="end" font-size="17" fill="#6C7880">线路示意图，不按比例 · Schematic map — not to scale</text>',
        '<g id="legend">',
        '<rect x="2570" y="160" width="370" height="1600" rx="26" fill="#FFFFFF" stroke="#DCE3E8" stroke-width="2"/>',
        '<text x="2610" y="218" font-size="26" font-weight="750" fill="#24323A">线路图例</text>',
        '<text x="2610" y="246" font-size="14" fill="#7A8790">LINE KEY · SKELETON ONLY</text>',
    ])
    y = 294
    for line in lines:
        dash = ' stroke-dasharray="16 10"' if line["status"] == "under-construction" else ""
        out.append(f'<line x1="2610" y1="{y}" x2="2676" y2="{y}" stroke="{line["color"]}" stroke-width="8" stroke-linecap="round"{dash}/>')
        out.append(f'<text x="2694" y="{y+7}" font-size="18" font-weight="650" fill="#33434D">{line["id"]} {line["nameZh"]}</text>')
        y += 78
    out.append('</g></svg>')
    path.write_text("\n".join(out), encoding="utf-8")


def generate_candidates() -> None:
    candidates_root = ROOT / "candidates"
    candidates_root.mkdir(exist_ok=True)
    for candidate in range(1, 9):
        folder = candidates_root / f"candidate-{candidate:02d}"
        folder.mkdir(exist_ok=True)
        lines = route_variant(candidate)
        metrics = skeleton_metrics(lines)
        write_skeleton_svg(folder / "skeleton.svg", lines, candidate)
        (folder / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        review = (
            f"# 骨架候选 {candidate:02d} 视觉审查\n\n"
            "状态：待真实图像检查。\n\n"
            "## 检查项\n\n"
            "- 线路逐线追踪：待检查\n"
            "- 彩色意大利面：待检查\n"
            "- 环线清晰度：待检查\n"
            "- 稳定主轴：待检查\n"
            "- 长距离乱飞斜线：待检查\n"
            "- 非换乘交叉：待分类\n"
            "- 核心与外围层次：待检查\n"
            "- 是否晋级：待决定\n"
        )
        review_path = folder / "review.md"
        if not review_path.exists():
            review_path.write_text(review, encoding="utf-8")
    print("generated 8 skeleton candidates")


def accept_skeleton(candidate: int) -> None:
    source = ROOT / "candidates" / f"candidate-{candidate:02d}"
    target = ROOT / "skeleton"
    target.mkdir(exist_ok=True)
    shutil.copy2(source / "skeleton.svg", target / "skeleton.svg")
    if (source / "skeleton.png").exists():
        shutil.copy2(source / "skeleton.png", target / "skeleton.png")
    shutil.copy2(source / "metrics.json", target / "skeleton_metrics.json")
    shutil.copy2(source / "review.md", target / "REVIEW.md")
    print(f"accepted candidate {candidate:02d} into skeleton/")


TARGET_LINE_COUNTS = {
    "L1": 18, "L2": 17, "L3": 17, "L4": 16, "L5": 17,
    "L6": 20, "L7": 15, "L8": 16, "L9": 12, "L10": 14,
    "L11": 15, "L12": 14, "L13": 8, "L14": 10, "L15": 14,
    "B1": 7, "B2": 7,
}


BRANCH_COORDS = {(2060.0, 1100.0), (520.0, 1320.0)}


MANDATORY_TRANSFER_COORDS = {
    (260.0, 360.0),       # West Ridge Airport: L4/L14
    (980.0, 760.0),       # People's Square: L1/L8
    (1200.0, 780.0),      # historic railway station: L4/L7
    (1360.0, 280.0),      # north railway station: L2/L11
    (1360.0, 760.0),      # core east-west/north-south interchange
    (1360.0, 1220.0),     # Civic Center: L2/L5
    (1700.0, 760.0),      # finance district: L1/L13
    (1790.0, 1440.0),     # high-speed rail central: L6/L11/L15
    (1900.0, 620.0),      # east railway station: L10/L12
    (2240.0, 1480.0),     # international airport: L4/L13
}


SPECIAL_POINTS = {
    "L2": [(1360.0, 360.0)],
    "L4": [(2200.0, 1480.0)],
    "L5": [(2100.0, 1220.0)],
    "L8": [(1040.0, 820.0)],
    "L13": [(2200.0, 1440.0)],
    "B1": [(2320.0, 1100.0), (2500.0, 1280.0)],
}


SPECIAL_NAME_IDS = {
    (260.0, 360.0): "NC-AP-012",
    (520.0, 1320.0): "NC-UN-019",
    (980.0, 760.0): "NC-OC-028",
    (1200.0, 780.0): "NC-RH-001",
    (1320.0, 1220.0): "NC-RH-010",
    (1360.0, 280.0): "NC-RH-002",
    (1360.0, 1220.0): "NC-SF-015",
    (1700.0, 760.0): "NC-CB-011",
    (1790.0, 1440.0): "NC-RH-016",
    (1900.0, 620.0): "NC-RH-003",
    (2060.0, 1100.0): "NC-CO-002",
    (2200.0, 1440.0): "NC-AP-003",
    (2200.0, 1480.0): "NC-AP-002",
    (2240.0, 1480.0): "NC-AP-001",
    (2320.0, 1100.0): "NC-PT-010",
    (2500.0, 1280.0): "NC-PT-001",
}


def polyline_lengths(points: list[tuple[float, float]]):
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    cumulative = [0.0]
    for length in lengths:
        cumulative.append(cumulative[-1] + length)
    return lengths, cumulative


def point_at_distance(points: list[tuple[float, float]], distance: float):
    lengths, cumulative = polyline_lengths(points)
    total = cumulative[-1]
    distance = max(0.0, min(total, distance))
    for index, length in enumerate(lengths):
        if distance <= cumulative[index + 1] + 1e-7:
            ratio = 0 if length == 0 else (distance - cumulative[index]) / length
            a, b = points[index], points[index + 1]
            return (round(a[0] + (b[0] - a[0]) * ratio, 3), round(a[1] + (b[1] - a[1]) * ratio, 3))
    return points[-1]


def distance_on_path(points: list[tuple[float, float]], point: tuple[float, float]):
    _, cumulative = polyline_lengths(points)
    px, py = point
    for index, (a, b) in enumerate(zip(points, points[1:])):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        cross = dx * (py - ay) - dy * (px - ax)
        if abs(cross) > 0.2:
            continue
        dot = (px - ax) * dx + (py - ay) * dy
        length_sq = dx * dx + dy * dy
        if -0.2 <= dot <= length_sq + 0.2:
            return cumulative[index] + math.hypot(px - ax, py - ay)
    return None


def choose_crossing_classes(lines: list[dict]):
    clusters = intersection_clusters(lines)
    by_coord = {(item["x"], item["y"]): item for item in clusters}
    missing = sorted(MANDATORY_TRANSFER_COORDS - set(by_coord))
    if missing:
        raise ValueError(f"mandatory transfer coordinates absent from skeleton: {missing}")
    selected = set(MANDATORY_TRANSFER_COORDS)
    candidates = [item for item in clusters if (item["x"], item["y"]) not in BRANCH_COORDS and (item["x"], item["y"]) not in selected]
    candidates.sort(key=lambda item: (
        0 if 700 <= item["x"] <= 2100 and 480 <= item["y"] <= 1460 else 1,
        -len(item["lines"]),
        abs(item["x"] - 1450) + abs(item["y"] - 950),
    ))
    for item in candidates:
        if len(selected) >= 50:
            break
        selected.add((item["x"], item["y"]))
    if len(selected) != 50:
        raise ValueError(f"expected 50 ordinary transfer points, got {len(selected)}")
    crossings = []
    for index, item in enumerate(clusters, 1):
        coord = (item["x"], item["y"])
        if coord in BRANCH_COORDS:
            classification = "branch-junction"
        elif coord in selected:
            classification = "interchange"
        else:
            classification = "grade-separated"
        crossings.append({
            "id": f"X{index:03d}",
            "schematic": {"x": item["x"], "y": item["y"]},
            "lines": item["lines"],
            "classification": classification,
            "coreArea": 700 <= item["x"] <= 2100 and 480 <= item["y"] <= 1460,
            "note": {
                "interchange": "same-station paid-area interchange",
                "branch-junction": "through-service branch junction; excluded from transfer metric",
                "grade-separated": "schematic flyover without passenger interchange",
            }[classification],
        })
    return clusters, selected, crossings


def station_region(x: float, y: float) -> str:
    if x <= 360 and y <= 420:
        return "西岭机场片区"
    if x < 620 and y < 700:
        return "西部卫星城"
    if x < 820 and y >= 1180:
        return "西南大学城"
    if x < 820:
        return "旧工业更新区"
    if y < 500:
        return "北部居住新城"
    if 920 <= y <= 1080 and 1080 <= x <= 1580:
        return "沧洲江心岛"
    if x <= 1250 and y < 1040:
        return "传统老城"
    if 1250 < x <= 1850 and y < 980:
        return "北岸中央商务区"
    if y >= 1040 and x < 1950:
        return "南岸金融文化区"
    if x >= 2320 and y >= 1080:
        return "东部深水港区"
    if x >= 2100 and y >= 1320:
        return "东南航空城"
    if x >= 1850 and y < 1080:
        return "东部科技新城"
    if y >= 1120:
        return "南部滨海新城"
    return "北岸中央商务区"


def build_line_station_points(lines: list[dict], selected_transfers: set[tuple[float, float]], clusters: list[dict]):
    shared_coords = selected_transfers | BRANCH_COORDS
    station_points: dict[str, dict] = {}
    line_keys: dict[str, list[str]] = {}
    cluster_by_coord = {(item["x"], item["y"]): item for item in clusters}
    for line in lines:
        lid = line["id"]
        points = line["points"]
        total = polyline_lengths(points)[1][-1]
        entries = []
        for coord in shared_coords:
            cluster = cluster_by_coord.get(coord)
            if cluster and lid in cluster["lines"]:
                along = distance_on_path(points, coord)
                if along is not None:
                    entries.append((along, coord, f"A-{fmt(coord[0])}-{fmt(coord[1])}"))
        for coord in SPECIAL_POINTS.get(lid, []):
            along = distance_on_path(points, coord)
            if along is not None:
                entries.append((along, coord, f"S-{lid}-{fmt(coord[0])}-{fmt(coord[1])}"))
        endpoints = [(0.0, points[0], f"E-{lid}-0")]
        if line["type"] != "ring":
            endpoints.append((total, points[-1], f"E-{lid}-1"))
        for along, coord, key in endpoints:
            shared_key = f"A-{fmt(coord[0])}-{fmt(coord[1])}"
            if coord in shared_coords:
                key = shared_key
            entries.append((along, coord, key))
        # De-duplicate exact anchors on this service.
        unique = {}
        for along, coord, key in entries:
            unique[key] = (along, coord, key)
        entries = list(unique.values())
        target = max(TARGET_LINE_COUNTS[lid], len(entries))
        candidates = []
        for n in range(1, 401):
            along = total * n / 401
            coord = point_at_distance(points, along)
            candidates.append((along, coord))
        min_gap = 42.0 if line["type"] not in ("airport-express", "regional-express") else 76.0
        while len(entries) < target:
            viable = [item for item in candidates if all(abs(item[0] - existing[0]) >= min_gap for existing in entries)]
            if not viable:
                min_gap *= 0.82
                if min_gap < 18:
                    raise ValueError(f"unable to place {target} stations on {lid}")
                continue
            along, coord = max(viable, key=lambda item: min(abs(item[0] - existing[0]) for existing in entries))
            key = f"U-{lid}-{len([e for e in entries if e[2].startswith('U-')])+1:02d}"
            entries.append((along, coord, key))
            candidates.remove((along, coord))
        entries.sort(key=lambda item: item[0])
        line_keys[lid] = [entry[2] for entry in entries]
        for position, (along, coord, key) in enumerate(entries):
            record = station_points.setdefault(key, {
                "key": key,
                "schematic": {"x": round(coord[0], 3), "y": round(coord[1], 3)},
                "lines": [],
                "linePositions": {},
                "terminalLines": [],
                "isBranchJunction": coord in BRANCH_COORDS,
                "isOrdinaryInterchange": coord in selected_transfers,
            })
            if lid not in record["lines"]:
                record["lines"].append(lid)
            record["linePositions"][lid] = position
            if line["type"] != "ring" and position in (0, len(entries) - 1):
                record["terminalLines"].append(lid)
    return station_points, line_keys


def assign_station_names(station_points: dict[str, dict]):
    catalog = json.loads((ROOT / "station_catalog.json").read_text(encoding="utf-8"))["stations"]
    catalog_by_id = {item["id"]: item for item in catalog}
    used = set()
    by_region: dict[str, list[dict]] = {}
    for item in catalog:
        by_region.setdefault(item["region"], []).append(item)
    records = sorted(station_points.values(), key=lambda item: (item["schematic"]["y"], item["schematic"]["x"], item["key"]))
    # Reserve all special names before regional allocation.
    reserved = set(SPECIAL_NAME_IDS.values())
    for record in records:
        coord = (record["schematic"]["x"], record["schematic"]["y"])
        preferred = SPECIAL_NAME_IDS.get(coord)
        if preferred and preferred not in used:
            chosen = catalog_by_id[preferred]
        else:
            region = station_region(*coord)
            choices = [item for item in by_region.get(region, []) if item["id"] not in used and item["id"] not in reserved]
            if not choices:
                choices = [item for item in catalog if item["id"] not in used and item["id"] not in reserved]
            if not choices:
                raise ValueError("station catalog exhausted")
            chosen = choices[0]
        used.add(chosen["id"])
        record.update({
            "id": chosen["id"],
            "nameZh": chosen["nameZh"],
            "nameEn": chosen["nameEn"],
            "district": chosen["region"],
            "role": chosen["role"],
        })
    return records


def geo_from_schematic(x: float, y: float):
    return {"x": round((x - 100) / 24.0, 2), "y": round((y - 180) / 24.0, 2)}


def generate_network(candidate: int = 8) -> None:
    lines = route_variant(candidate)
    clusters, selected_transfers, crossings = choose_crossing_classes(lines)
    station_points, line_keys = build_line_station_points(lines, selected_transfers, clusters)
    station_records = assign_station_names(station_points)
    key_to_id = {record["key"]: record["id"] for record in station_records}
    line_index = {line["id"]: line for line in lines}
    for record in station_records:
        x, y = record["schematic"]["x"], record["schematic"]["y"]
        record["geoKm"] = geo_from_schematic(x, y)
        record["riverBank"] = "island" if 930 <= y <= 1060 and 1080 <= x <= 1580 else ("north" if y < 980 else "south")
        record["area"] = "core" if 760 <= x <= 2050 and 500 <= y <= 1450 else ("inner" if 500 <= x <= 2300 and 320 <= y <= 1680 else "outer")
        record["hub"] = any(token in record["role"] for token in ("枢纽", "机场", "铁路", "客运", "港", "核心广场"))
        record["terminal"] = bool(record["terminalLines"])
        record["isInterchange"] = record["isOrdinaryInterchange"]
        record["label"] = {"x": None, "y": None, "anchor": None, "side": None, "leader": False}
        record.pop("key", None)
    corridor_payload = json.loads((ROOT / "corridors.json").read_text(encoding="utf-8")) if (ROOT / "corridors.json").exists() else {"corridors": []}
    line_corridors = {line["id"]: [] for line in lines}
    for corridor in corridor_payload.get("corridors", []):
        for line_id in corridor.get("servedBy", []):
            if line_id in line_corridors:
                line_corridors[line_id].append(corridor.get("id"))
    line_corridors["B1"] = line_corridors["B1"] or ["C13"]
    line_corridors["B2"] = line_corridors["B2"] or ["C08"]
    network_lines = []
    for line in lines:
        ys = [point[1] for point in line["points"]]
        network_lines.append({
            "id": line["id"],
            "nameZh": line["nameZh"],
            "nameEn": line["nameEn"],
            "color": line["color"],
            "type": line["type"],
            "status": line["status"],
            "corridors": line_corridors[line["id"]] or ["C01"],
            "branchOf": line.get("branchOf"),
            "junctionStation": key_to_id.get("A-2060-1100") if line["id"] == "B1" else (key_to_id.get("A-520-1320") if line["id"] == "B2" else None),
            "closed": line["type"] == "ring",
            "crossesMainRiver": min(ys) < 930 and max(ys) > 1060,
            "schematicPath": [{"x": point[0], "y": point[1]} for point in line["points"]],
            "stations": [key_to_id[key] for key in line_keys[line["id"]]],
        })
    geography = json.loads((ROOT / "geography.json").read_text(encoding="utf-8")) if (ROOT / "geography.json").exists() else {}
    catalog_root = json.loads((ROOT / "station_catalog.json").read_text(encoding="utf-8"))
    network = {
        "schemaVersion": "4.0",
        "city": {
            "nameZh": "宁沧市",
            "nameEn": "Ningcang",
            "population": 21800000,
            "metropolitanPopulation": 31700000,
            "builtUpAreaKm2": 2640,
            "railHistoryYears": 37,
        },
        "regions": catalog_root["regions"],
        "geography": geography,
        "lines": network_lines,
        "stations": station_records,
        "branchRelations": [
            {"branchLine": "B1", "parentLine": "L10", "junctionStation": key_to_id["A-2060-1100"]},
            {"branchLine": "B2", "parentLine": "L3", "junctionStation": key_to_id["A-520-1320"]},
        ],
        "metricsDefinition": {
            "transferStation": "shared station between independent lines; through-service branch junctions are tracked separately",
            "crossing": "unique schematic intersection point, not pairwise segment count",
        },
    }
    network_text = json.dumps(network, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "network.json").write_text(network_text, encoding="utf-8")
    (ROOT / "network_unlabeled.json").write_text(network_text, encoding="utf-8")
    crossing_payload = {
        "schemaVersion": "1.0",
        "candidate": f"candidate-{candidate:02d}",
        "uniqueIntersectionCount": len(crossings),
        "ordinaryInterchangeCount": sum(item["classification"] == "interchange" for item in crossings),
        "branchJunctionCount": sum(item["classification"] == "branch-junction" for item in crossings),
        "nonInterchangeCrossingCount": sum(item["classification"] == "grade-separated" for item in crossings),
        "coreAreaNonInterchangeCrossingCount": sum(item["classification"] == "grade-separated" and item["coreArea"] for item in crossings),
        "crossings": crossings,
    }
    (ROOT / "crossings.json").write_text(json.dumps(crossing_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    transfer_count = sum(record["isInterchange"] for record in station_records)
    print(json.dumps({
        "lineCount": len(network_lines),
        "stationCount": len(station_records),
        "transferStationCount": transfer_count,
        "branchJunctionCount": 2,
        "nonInterchangeCrossingCount": crossing_payload["nonInterchangeCrossingCount"],
    }, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["candidates", "accept", "intersections", "network"], required=True)
    parser.add_argument("--candidate", type=int, default=4)
    args = parser.parse_args()
    if args.stage == "candidates":
        generate_candidates()
    elif args.stage == "accept":
        accept_skeleton(args.candidate)
    elif args.stage == "intersections":
        clusters = intersection_clusters(route_variant(args.candidate))
        print(json.dumps({"count": len(clusters), "clusters": clusters}, ensure_ascii=False, indent=2))
    elif args.stage == "network":
        generate_network(args.candidate)


if __name__ == "__main__":
    main()
