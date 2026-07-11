#!/usr/bin/env python3
"""Place bilingual station labels with real FreeType font metrics.

Run with the bundled Codex Python runtime, which provides Pillow.  The script
does not estimate text width from character count: every width and height comes
from the actual Hiragino Sans GB / Helvetica font faces used by the SVG.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from PIL import ImageFont


ROOT = Path(__file__).resolve().parent
ZH_FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
EN_FONT = "/System/Library/Fonts/Helvetica.ttc"
FINAL_SCALE = 1.35
BOUNDS = tuple(value * FINAL_SCALE for value in (70.0, 165.0, 2490.0, 1875.0))


def font_pair(station):
    if station.get("isInterchange") or station.get("hub"):
        return 20, 11
    return 18, 10


def metrics(text, font_path, size):
    font = ImageFont.truetype(font_path, size)
    box = font.getbbox(text)
    return float(font.getlength(text)), float(box[3] - box[1])


def wrap_english(text, size, maximum=112.0):
    words = text.split()
    if metrics(text, EN_FONT, size)[0] <= maximum or len(words) == 1:
        return [text]
    lines = []
    current = []
    for word in words:
        trial = " ".join(current + [word])
        if current and metrics(trial, EN_FONT, size)[0] > maximum:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def wrap_chinese(text, size, maximum=108.0):
    if metrics(text, ZH_FONT, size)[0] <= maximum or len(text) <= 4:
        return [text]
    split = (len(text) + 1) // 2
    return [text[:split], text[split:]]


def overlap(a, b, pad=0.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def overlap_area(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def rect_polygon(box):
    return [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]


def rotate_polygon(polygon, pivot, degrees):
    if not degrees:
        return polygon
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    px, py = pivot
    return [
        (px + (x - px) * cosine - (y - py) * sine,
         py + (x - px) * sine + (y - py) * cosine)
        for x, y in polygon
    ]


def polygon_bbox(polygon):
    xs, ys = zip(*polygon)
    return (min(xs), min(ys), max(xs), max(ys))


def polygon_overlap(first, second):
    for polygon in (first, second):
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            axis = (-(b[1] - a[1]), b[0] - a[0])
            first_projection = [x * axis[0] + y * axis[1] for x, y in first]
            second_projection = [x * axis[0] + y * axis[1] for x, y in second]
            if max(first_projection) <= min(second_projection) or max(second_projection) <= min(first_projection):
                return False
    return True


def point_box(x, y, radius):
    return (x - radius, y - radius, x + radius, y + radius)


def line_boxes(network):
    boxes = []
    for line in network["lines"]:
        points = line["schematicPath"]
        for a, b in zip(points, points[1:]):
            pad = 6.0
            boxes.append((min(a["x"], b["x"]) - pad, min(a["y"], b["y"]) - pad,
                          max(a["x"], b["x"]) + pad, max(a["y"], b["y"]) + pad))
    return boxes


def make_candidate(station, side, distance, rotation=0):
    x, y = station["schematic"]["x"], station["schematic"]["y"]
    zh_size, en_size = font_pair(station)
    zh_lines = wrap_chinese(station["nameZh"], zh_size)
    en_lines = wrap_english(station["nameEn"], en_size, 128.0 if station.get("hub") else 108.0)
    zh_widths = [metrics(line, ZH_FONT, zh_size)[0] for line in zh_lines]
    en_widths = [metrics(line, EN_FONT, en_size)[0] for line in en_lines]
    zh_h = metrics("国", ZH_FONT, zh_size)[1]
    en_h = metrics("Ag", EN_FONT, en_size)[1]
    zh_w, en_w = max(zh_widths), max(en_widths)
    width = max(zh_w, en_w)
    zh_block_h = len(zh_lines) * (zh_h + 1) - 1
    en_block_h = len(en_lines) * (en_h + 2) - 2
    height = zh_block_h + en_block_h + 5
    dx, dy, anchor = {
        "E": (distance, 0, "start"), "W": (-distance, 0, "end"),
        "N": (0, -distance, "middle"), "S": (0, distance, "middle"),
        "NE": (distance, -distance, "start"), "NW": (-distance, -distance, "end"),
        "SE": (distance, distance, "start"), "SW": (-distance, distance, "end"),
    }[side]
    if side in ("E", "W"):
        top = y - height / 2
    elif "N" in side:
        top = y + dy - height
    else:
        top = y + dy
    tx = x + dx
    if anchor == "start":
        left = tx
    elif anchor == "end":
        left = tx - width
    else:
        left = tx - width / 2
    raw_box = (left - 2, top - 2, left + width + 2, top + height + 2)
    zh_y = top + zh_h
    en_y = top + zh_block_h + en_h + 4
    zh_left = left if anchor == "start" else (left + width - zh_w if anchor == "end" else left + (width - zh_w) / 2)
    en_left = left if anchor == "start" else (left + width - en_w if anchor == "end" else left + (width - en_w) / 2)
    raw_zh = (zh_left, top, zh_left + zh_w, top + zh_block_h)
    raw_en = (en_left, top + zh_block_h + 3, en_left + en_w, top + zh_block_h + 3 + en_block_h)
    pivot = (tx, zh_y)
    polygon = rotate_polygon(rect_polygon(raw_box), pivot, rotation)
    polygon_zh = rotate_polygon(rect_polygon(raw_zh), pivot, rotation)
    polygon_en = rotate_polygon(rect_polygon(raw_en), pivot, rotation)
    box = polygon_bbox(polygon)
    box_zh = polygon_bbox(polygon_zh)
    box_en = polygon_bbox(polygon_en)
    return {
        "x": round(tx, 2), "y": round(zh_y, 2), "englishY": round(en_y, 2),
        "anchor": anchor, "side": side, "distance": distance, "rotation": rotation, "leader": distance >= 64,
        "fontSizeZh": zh_size, "fontSizeEn": en_size,
        "zhLines": zh_lines, "enLines": en_lines,
        "zhLineHeight": round(zh_h + 1, 2), "enLineHeight": round(en_h + 2, 2),
        "bbox": [round(value, 2) for value in box],
        "bboxZh": [round(value, 2) for value in box_zh],
        "bboxEn": [round(value, 2) for value in box_en],
        "polygon": [[round(x, 2), round(y, 2)] for x, y in polygon],
        "polygonZh": [[round(x, 2), round(y, 2)] for x, y in polygon_zh],
        "polygonEn": [[round(x, 2), round(y, 2)] for x, y in polygon_en],
    }


def preferred_sides(station):
    x, y = station["schematic"]["x"], station["schematic"]["y"]
    if x > 2250:
        base = ["W", "NW", "SW", "N", "S"]
    elif x < 330:
        base = ["E", "NE", "SE", "N", "S"]
    elif y < 330:
        base = ["S", "SE", "SW", "E", "W"]
    elif y > 1650:
        base = ["N", "NE", "NW", "E", "W"]
    else:
        parity = sum(ord(ch) for ch in station["id"]) % 4
        rotations = [
            ["E", "W", "NE", "SW", "N", "S", "NW", "SE"],
            ["W", "E", "NW", "SE", "S", "N", "SW", "NE"],
            ["N", "S", "NE", "NW", "E", "W", "SE", "SW"],
            ["S", "N", "SE", "SW", "W", "E", "NE", "NW"],
        ]
        base = rotations[parity]
    return base


def label_score(candidate, placed, station_boxes, route_boxes):
    box = candidate["bbox"]
    if box[0] < BOUNDS[0] or box[1] < BOUNDS[1] or box[2] > BOUNDS[2] or box[3] > BOUNDS[3]:
        return 1e12
    score = 0.0
    for other in placed:
        if polygon_overlap(candidate["polygon"], other["polygon"]):
            score += 1e8 + overlap_area(box, other["bbox"]) * 1000
    for obstacle in station_boxes:
        if polygon_overlap(candidate["polygon"], rect_polygon(obstacle)):
            score += 2e6 + overlap_area(box, obstacle) * 200
    for obstacle in route_boxes:
        if overlap(box, obstacle):
            score += overlap_area(box, obstacle) * 0.7
    if candidate["leader"]:
        score += 180
    score += {"E": 0, "W": 3, "N": 6, "S": 7, "NE": 10, "NW": 11, "SE": 12, "SW": 13}[candidate["side"]]
    return score


def place_labels(network, mode):
    network = copy.deepcopy(network)
    stations = network["stations"]
    station_boxes = [point_box(s["schematic"]["x"], s["schematic"]["y"], 14 if s["isInterchange"] else 8) for s in stations]
    routes = line_boxes(network)
    placed = []
    order = sorted(stations, key=lambda s: (
        0 if s.get("hub") else 1,
        0 if s.get("isInterchange") else 1,
        0 if s.get("area") == "core" else 1,
        s["schematic"]["y"], s["schematic"]["x"],
    ))
    for station in order:
        if mode == "naive":
            side = "E" if sum(ord(ch) for ch in station["id"]) % 2 else "W"
            choice = make_candidate(station, side, 15, 0)
        else:
            choices = []
            for distance in (15, 30, 46, 64, 84, 106, 132, 158):
                for side in preferred_sides(station):
                    rotations = (0, -45, 45) if side in ("E", "W", "NE", "NW", "SE", "SW") else (0,)
                    for rotation in rotations:
                        candidate = make_candidate(station, side, distance, rotation)
                        choices.append((label_score(candidate, placed, station_boxes, routes), candidate))
            choice = min(choices, key=lambda item: item[0])[1]
        station["label"] = choice
        placed.append(choice)
    return network


def scale_schematic(network, scale):
    network = copy.deepcopy(network)
    for station in network["stations"]:
        station["schematic"]["x"] = round(station["schematic"]["x"] * scale, 3)
        station["schematic"]["y"] = round(station["schematic"]["y"] * scale, 3)
    for line in network["lines"]:
        for point in line["schematicPath"]:
            point["x"] = round(point["x"] * scale, 3)
            point["y"] = round(point["y"] * scale, 3)
    network["schematicCanvas"] = {"width": int(3000 * scale), "height": int(2000 * scale), "scaleFromSkeleton": scale}
    return network


def collision_report(network):
    stations = network["stations"]
    pairs = []
    zh_pairs = []
    en_pairs = []
    cross_language_pairs = []
    for i, a in enumerate(stations):
        for b in stations[i + 1:]:
            if polygon_overlap(a["label"]["polygon"], b["label"]["polygon"]):
                pairs.append([a["id"], b["id"]])
            if polygon_overlap(a["label"]["polygonZh"], b["label"]["polygonZh"]):
                zh_pairs.append([a["id"], b["id"]])
            if polygon_overlap(a["label"]["polygonEn"], b["label"]["polygonEn"]):
                en_pairs.append([a["id"], b["id"]])
            if polygon_overlap(a["label"]["polygonZh"], b["label"]["polygonEn"]) or polygon_overlap(a["label"]["polygonEn"], b["label"]["polygonZh"]):
                cross_language_pairs.append([a["id"], b["id"]])
    out_of_bounds = []
    station_overlaps = []
    station_boxes = {s["id"]: point_box(s["schematic"]["x"], s["schematic"]["y"], 14 if s["isInterchange"] else 8) for s in stations}
    for station in stations:
        box = station["label"]["bbox"]
        if box[0] < BOUNDS[0] or box[1] < BOUNDS[1] or box[2] > BOUNDS[2] or box[3] > BOUNDS[3]:
            out_of_bounds.append(station["id"])
        for other_id, obstacle in station_boxes.items():
            if other_id != station["id"] and polygon_overlap(station["label"]["polygon"], rect_polygon(obstacle)):
                station_overlaps.append([station["id"], other_id])
    actual_pairs = {tuple(pair) for pair in zh_pairs + en_pairs + cross_language_pairs}
    return {
        "collisionDetectionMethod": "Pillow FreeType getbbox/getlength with Hiragino Sans GB and Helvetica TTC; pairwise rendered bounding boxes",
        "fontFiles": {"zh": ZH_FONT, "en": EN_FONT},
        "stationCount": len(stations),
        "totalLabelCollisionCount": len(actual_pairs),
        "labelUnitProximityCount": len(pairs),
        "chineseLabelCollisionCount": len(zh_pairs),
        "englishLabelCollisionCount": len(en_pairs),
        "crossLanguageCollisionCount": len(cross_language_pairs),
        "labelStationCollisionCount": len(station_overlaps),
        "outOfBoundsLabelCount": len(out_of_bounds),
        "minimumChineseFontSize": min(s["label"]["fontSizeZh"] for s in stations),
        "minimumEnglishFontSize": min(s["label"]["fontSizeEn"] for s in stations),
        "pairs": pairs,
        "outOfBounds": out_of_bounds,
        "labelStationPairs": station_overlaps[:100],
    }


def main():
    source = json.loads((ROOT / "network_unlabeled.json").read_text(encoding="utf-8"))
    source = scale_schematic(source, FINAL_SCALE)
    naive = place_labels(source, "naive")
    optimized = place_labels(source, "optimized")
    naive_report = collision_report(naive)
    optimized_report = collision_report(optimized)
    (ROOT / "network_full_candidate_01.json").write_text(json.dumps(naive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "network_full_candidate_02.json").write_text(json.dumps(optimized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "network.json").write_text(json.dumps(optimized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"naive": naive_report, "optimized": optimized_report}
    (ROOT / "label_bbox_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"naive": naive_report, "optimized": optimized_report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
