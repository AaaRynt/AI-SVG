#!/usr/bin/env python3
"""Measure and score the v4 octilinear metro layout.

Geometry is read from explicit per-line paths when present, then from a
top-level ``paths`` mapping, and finally from ordered station schematic
coordinates.  The output contains measured counts, evidence, per-line values,
and a transparent penalty calculation.  Unknown browser-only measurements stay
``null`` instead of being guessed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from validate_svg import NUMBER_RE, _path_segments
except ImportError:  # pragma: no cover - useful when invoked as a module
    from .validate_svg import NUMBER_RE, _path_segments  # type: ignore


VERSION = "1.0"
Point = tuple[float, float]
Segment = dict[str, Any]


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            if isinstance(item, dict):
                copy = dict(item)
                copy.setdefault("id", str(key))
                result.append(copy)
        return result
    return []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            item_id = item.strip()
        elif isinstance(item, dict):
            item_id = _string(item.get("id") or item.get("stationId") or item.get("station"))
        else:
            item_id = ""
        if item_id:
            result.append(item_id)
    return result


def _tokens(*values: Any) -> str:
    chunks: list[str] = []
    for value in values:
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, (list, tuple, set)):
            chunks.extend(str(item) for item in value)
        elif isinstance(value, dict):
            chunks.extend(str(item) for item in value.values())
    return " ".join(chunks).casefold()


def _point(value: Any, station_points: dict[str, Point]) -> tuple[Point, str | None] | None:
    station_id: str | None = None
    if isinstance(value, str):
        station_id = value.strip()
        point = station_points.get(station_id)
        return (point, station_id) if point else None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        if isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
            return ((float(value[0]), float(value[1])), None)
        return None
    if not isinstance(value, dict):
        return None
    station_id = _string(value.get("stationId") or value.get("station") or value.get("id")) or None
    if isinstance(value.get("schematic"), dict):
        source = value["schematic"]
    elif isinstance(value.get("point"), dict):
        source = value["point"]
    else:
        source = value
    x, y = source.get("x"), source.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return ((float(x), float(y)), station_id)
    if station_id and station_id in station_points:
        return (station_points[station_id], station_id)
    return None


def _split_contiguous(segments: list[Segment], tolerance: float = 1e-6) -> list[list[Segment]]:
    paths: list[list[Segment]] = []
    current: list[Segment] = []
    for segment in segments:
        if current and _distance(current[-1]["end"], segment["start"]) > tolerance:
            paths.append(current)
            current = []
        current.append(segment)
    if current:
        paths.append(current)
    return paths


def _segments_from_path_string(value: str) -> tuple[list[list[Segment]], list[str]]:
    if re.search(r"[MmLlHhVvCcSsQqTtAaZz]", value):
        raw, errors = _path_segments(value)
        segments = [
            {"start": start, "end": end, "kind": kind, "startStation": None, "endStation": None}
            for start, end, kind in raw
        ]
        return _split_contiguous(segments), errors
    numbers = [float(number) for number in re.findall(NUMBER_RE, value)]
    points = list(zip(numbers[0::2], numbers[1::2]))
    return _segments_from_points([(point, None) for point in points]), []


def _segments_from_points(points: list[tuple[Point, str | None]]) -> list[list[Segment]]:
    if len(points) < 2:
        return []
    segments: list[Segment] = []
    for index in range(1, len(points)):
        start, start_station = points[index - 1]
        end, end_station = points[index]
        if start == end:
            continue
        segments.append(
            {
                "start": start,
                "end": end,
                "kind": "line-points",
                "startStation": start_station,
                "endStation": end_station,
            }
        )
    return [segments] if segments else []


def _normalise_geometry(value: Any, station_points: dict[str, Point]) -> tuple[list[list[Segment]], list[str]]:
    if isinstance(value, str):
        return _segments_from_path_string(value)
    if isinstance(value, dict):
        for key in ("d", "path", "points", "coordinates", "geometry"):
            if key in value:
                return _normalise_geometry(value[key], station_points)
        return [], ["geometry object contains no recognised path field"]
    if not isinstance(value, list) or not value:
        return [], []
    parsed_points = [_point(item, station_points) for item in value]
    if all(point is not None for point in parsed_points):
        return _segments_from_points([point for point in parsed_points if point is not None]), []
    paths: list[list[Segment]] = []
    errors: list[str] = []
    for item in value:
        subpaths, suberrors = _normalise_geometry(item, station_points)
        paths.extend(subpaths)
        errors.extend(suberrors)
    return paths, errors


def _is_loop(line: dict[str, Any]) -> bool:
    line_type = _string(line.get("type")).casefold()
    if line_type in {"semi-ring", "semi ring", "half-ring", "half ring"}:
        return False
    if line_type == "ring":
        return True
    text = _tokens(line.get("type"), line.get("role"), line.get("nameZh"), line.get("nameEn"))
    return any(token in text for token in ("环线", "环状", "loop", "ring", "circle"))


def _is_closed(line: dict[str, Any], station_ids: list[str]) -> bool:
    if len(station_ids) >= 3 and station_ids[0] == station_ids[-1]:
        return True
    if any(line.get(key) is True for key in ("closed", "isClosed", "loopClosed")):
        return True
    topology = line.get("topology")
    return isinstance(topology, dict) and topology.get("closed") is True


def _paths_are_closed(paths: list[list[Segment]], tolerance: float = 1e-6) -> bool:
    return any(path and _distance(path[0]["start"], path[-1]["end"]) <= tolerance for path in paths)


def _extract_line_paths(
    line: dict[str, Any],
    network: dict[str, Any],
    station_points: dict[str, Point],
) -> tuple[list[list[Segment]], str, list[str]]:
    line_id = _string(line.get("id"))
    for key in ("schematicPath", "schematicPaths", "path", "paths", "route", "geometry", "points"):
        if key in line and line.get(key) not in (None, [], ""):
            paths, errors = _normalise_geometry(line[key], station_points)
            if paths:
                return paths, f"line.{key}", errors
    top_paths = network.get("paths")
    if isinstance(top_paths, dict) and line_id in top_paths:
        paths, errors = _normalise_geometry(top_paths[line_id], station_points)
        if paths:
            return paths, "network.paths", errors
    if isinstance(top_paths, list):
        for item in top_paths:
            if isinstance(item, dict) and _string(item.get("lineId") or item.get("id")) == line_id:
                paths, errors = _normalise_geometry(item, station_points)
                if paths:
                    return paths, "network.paths[]", errors

    ordered_ids = _id_list(line.get("stations"))
    points = [(station_points[station_id], station_id) for station_id in ordered_ids if station_id in station_points]
    errors = []
    if len(points) != len(ordered_ids):
        missing = [station_id for station_id in ordered_ids if station_id not in station_points]
        errors.append(f"missing schematic coordinates for stations: {', '.join(missing)}")
    if _is_loop(line) and _is_closed(line, ordered_ids) and points and points[0] != points[-1]:
        points.append(points[0])
    return _segments_from_points(points), "station.schematic", errors


def _distance(first: Point, second: Point) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def _angle(start: Point, end: Point) -> tuple[float, float, int]:
    angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 360.0
    bucket = int(round(angle / 45.0)) % 8
    nearest = bucket * 45.0
    error = abs((angle - nearest + 180.0) % 360.0 - 180.0)
    return angle, error, bucket


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Point, b: Point) -> Point:
    return (a[0] + b[0], a[1] + b[1])


def _scale(a: Point, factor: float) -> Point:
    return (a[0] * factor, a[1] * factor)


def _segment_intersection(first: Segment, second: Segment, tolerance: float = 1e-7) -> tuple[str, Point | None]:
    p, p2 = first["start"], first["end"]
    q, q2 = second["start"], second["end"]
    r, s = _subtract(p2, p), _subtract(q2, q)
    r_cross_s = _cross(r, s)
    q_minus_p = _subtract(q, p)
    qmp_cross_r = _cross(q_minus_p, r)
    if abs(r_cross_s) <= tolerance and abs(qmp_cross_r) <= tolerance:
        r_squared = r[0] * r[0] + r[1] * r[1]
        if r_squared <= tolerance:
            return ("none", None)
        t0 = (q_minus_p[0] * r[0] + q_minus_p[1] * r[1]) / r_squared
        t1 = t0 + (s[0] * r[0] + s[1] * r[1]) / r_squared
        low, high = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
        if high < low - tolerance:
            return ("none", None)
        if high - low <= tolerance:
            return ("point", _add(p, _scale(r, (low + high) / 2.0)))
        return ("overlap", _add(p, _scale(r, (low + high) / 2.0)))
    if abs(r_cross_s) <= tolerance:
        return ("none", None)
    t = _cross(q_minus_p, s) / r_cross_s
    u = _cross(q_minus_p, r) / r_cross_s
    if -tolerance <= t <= 1.0 + tolerance and -tolerance <= u <= 1.0 + tolerance:
        return ("point", _add(p, _scale(r, t)))
    return ("none", None)


def _point_in_bounds(point: Point, bounds: tuple[float, float, float, float]) -> bool:
    return bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]


def _parse_bounds(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) >= 4 and all(isinstance(number, (int, float)) for number in value[:4]):
        x1, y1, x2, y2 = map(float, value[:4])
        if x2 > x1 and y2 > y1:
            return (x1, y1, x2, y2)
    if not isinstance(value, dict):
        return None
    if all(isinstance(value.get(key), (int, float)) for key in ("xMin", "yMin", "xMax", "yMax")):
        return (float(value["xMin"]), float(value["yMin"]), float(value["xMax"]), float(value["yMax"]))
    if all(isinstance(value.get(key), (int, float)) for key in ("x", "y", "width", "height")):
        return (
            float(value["x"]),
            float(value["y"]),
            float(value["x"] + value["width"]),
            float(value["y"] + value["height"]),
        )
    return None


def _core_bounds(
    network: dict[str, Any],
    stations: list[dict[str, Any]],
    width: float,
    height: float,
) -> tuple[tuple[float, float, float, float], str]:
    city = network.get("city") if isinstance(network.get("city"), dict) else {}
    geography = network.get("geography") if isinstance(network.get("geography"), dict) else {}
    for source_name, source in (("city", city), ("geography", geography), ("network", network)):
        for key in ("coreBounds", "schematicCoreBounds"):
            bounds = _parse_bounds(source.get(key)) if isinstance(source, dict) else None
            if bounds:
                return bounds, f"{source_name}.{key}"
        schematic = source.get("schematic") if isinstance(source, dict) else None
        if isinstance(schematic, dict):
            bounds = _parse_bounds(schematic.get("coreBounds"))
            if bounds:
                return bounds, f"{source_name}.schematic.coreBounds"

    core_tokens = ("老城", "中心城", "核心", "cbd", "central business", "人民广场", "南岸副中心")
    points: list[Point] = []
    for station in stations:
        descriptor = _tokens(station.get("area"), station.get("district"), station.get("role"), station.get("nameZh"), station.get("nameEn"))
        schematic = station.get("schematic")
        if any(token in descriptor for token in core_tokens) and isinstance(schematic, dict):
            x, y = schematic.get("x"), schematic.get("y")
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                points.append((float(x), float(y)))
    if points:
        margin = min(width, height) * 0.05
        return (
            max(0.0, min(point[0] for point in points) - margin),
            max(0.0, min(point[1] for point in points) - margin),
            min(width, max(point[0] for point in points) + margin),
            min(height, max(point[1] for point in points) + margin),
        ), "core-labelled station envelope"
    return (width * 0.25, height * 0.25, width * 0.75, height * 0.75), "central 50% fallback"


def _canvas_size(svg_path: Path, network: dict[str, Any]) -> tuple[float, float, str]:
    if svg_path.exists():
        try:
            root = ET.parse(svg_path).getroot()
            numbers = [float(number) for number in re.findall(NUMBER_RE, root.get("viewBox", ""))]
            if len(numbers) == 4 and numbers[2] > 0 and numbers[3] > 0:
                return numbers[2], numbers[3], f"{svg_path.name}:viewBox"
        except (OSError, ET.ParseError, ValueError):
            pass
    city = network.get("city") if isinstance(network.get("city"), dict) else {}
    for source in (network.get("schematic"), city.get("schematic") if isinstance(city, dict) else None):
        if isinstance(source, dict):
            width, height = source.get("width"), source.get("height")
            if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
                return float(width), float(height), "network schematic dimensions"
    return 2400.0, 1600.0, "v4 default 2400x1600"


def _bend_limit(line: dict[str, Any]) -> int:
    if isinstance(line.get("maxBends"), int):
        return int(line["maxBends"])
    text = _tokens(line.get("type"), line.get("role"), line.get("nameZh"), line.get("nameEn"), line.get("branchOf"))
    if _is_loop(line):
        return 18
    if "支线" in text or "branch" in text or line.get("branchOf"):
        return 6
    if "机场" in text or "airport express" in text:
        return 8
    if "市域" in text or "regional" in text or "suburban" in text:
        return 9
    if "快线" in text or "express" in text:
        return 9
    return 14


def _is_express(line: dict[str, Any]) -> bool:
    text = _tokens(line.get("type"), line.get("role"), line.get("nameZh"), line.get("nameEn"))
    return any(token in text for token in ("快线", "市域", "机场", "express", "regional", "suburban"))


def _repeated_area_visits(line: dict[str, Any], station_by_id: dict[str, dict[str, Any]]) -> int:
    sequence: list[str] = []
    for station_id in _id_list(line.get("stations")):
        station = station_by_id.get(station_id, {})
        area = _string(station.get("area") or station.get("district"))
        if area and (not sequence or sequence[-1] != area):
            sequence.append(area)
    return sum(count - 1 for count in Counter(sequence).values() if count > 1)


def _load_bbox_metrics(path: Path, width: float, height: float) -> dict[str, Any]:
    result = {
        "labelCollisionCount": None,
        "labelOutOfBoundsCount": None,
        "minimumChineseFontSize": None,
        "minimumEnglishFontSize": None,
        "source": None,
        "error": None,
    }
    if not path.exists():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("optimized"), dict):
            measured = payload["optimized"]
            method = _string(measured.get("collisionDetectionMethod"))
            if not re.search(r"getbbox|render|freetype", method, flags=re.I):
                raise ValueError("optimized bbox report must identify rendered getbbox/FreeType measurement")
            result.update({
                "labelCollisionCount": measured.get("totalLabelCollisionCount"),
                "labelOutOfBoundsCount": measured.get("outOfBoundsLabelCount"),
                "minimumChineseFontSize": measured.get("minimumChineseFontSize"),
                "minimumEnglishFontSize": measured.get("minimumEnglishFontSize"),
                "source": f"{path.name}:{method}",
            })
            return result
        boxes = payload.get("boxes") if isinstance(payload, dict) else payload
        method = _string(payload.get("measurementMethod") or payload.get("source")) if isinstance(payload, dict) else ""
        if not isinstance(boxes, list):
            raise ValueError("bbox payload must be a list or contain a boxes list")
        if not re.search(r"getbbox|browser|render", method, flags=re.I):
            raise ValueError("bbox source must identify browser/getBBox rendered measurements")
        normalised: list[dict[str, Any]] = []
        for index, box in enumerate(boxes):
            if not isinstance(box, dict) or not all(isinstance(box.get(key), (int, float)) for key in ("x", "y", "width", "height")):
                continue
            if box["width"] < 0 or box["height"] < 0:
                continue
            normalised.append({**box, "_index": index})
        collisions = 0
        for first_index, first in enumerate(normalised):
            for second in normalised[first_index + 1 :]:
                if first.get("stationId") and first.get("stationId") == second.get("stationId") and first.get("language") != second.get("language"):
                    # Chinese and English belonging to one label unit may touch,
                    # but a positive-area overlap still counts below.
                    pass
                overlap_x = min(first["x"] + first["width"], second["x"] + second["width"]) - max(first["x"], second["x"])
                overlap_y = min(first["y"] + first["height"], second["y"] + second["height"]) - max(first["y"], second["y"])
                if overlap_x > 0.5 and overlap_y > 0.5:
                    collisions += 1
        out_of_bounds = sum(
            box["x"] < 0 or box["y"] < 0 or box["x"] + box["width"] > width or box["y"] + box["height"] > height
            for box in normalised
        )
        zh_sizes = [
            float(box["fontSize"])
            for box in normalised
            if isinstance(box.get("fontSize"), (int, float)) and _tokens(box.get("language"), box.get("type")) in {"zh", "chinese", "station zh", "station chinese"}
        ]
        en_sizes = [
            float(box["fontSize"])
            for box in normalised
            if isinstance(box.get("fontSize"), (int, float)) and _tokens(box.get("language"), box.get("type")) in {"en", "english", "station en", "station english"}
        ]
        result.update(
            {
                "labelCollisionCount": collisions,
                "labelOutOfBoundsCount": int(out_of_bounds),
                "minimumChineseFontSize": min(zh_sizes) if zh_sizes else None,
                "minimumEnglishFontSize": min(en_sizes) if en_sizes else None,
                "source": f"{path.name}:{method}",
            }
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result["error"] = str(exc)
    return result


def score(network: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    lines = _records(network.get("lines"))
    stations = _records(network.get("stations"))
    station_by_id = {_string(station.get("id")): station for station in stations if _string(station.get("id"))}
    station_points: dict[str, Point] = {}
    for station_id, station in station_by_id.items():
        schematic = station.get("schematic")
        if isinstance(schematic, dict) and isinstance(schematic.get("x"), (int, float)) and isinstance(schematic.get("y"), (int, float)):
            station_points[station_id] = (float(schematic["x"]), float(schematic["y"]))

    width, height, canvas_source = _canvas_size(Path(args.svg), network)
    core_bounds, core_source = _core_bounds(network, stations, width, height)
    line_paths: dict[str, list[list[Segment]]] = {}
    source_by_line: dict[str, str] = {}
    geometry_errors: dict[str, list[str]] = {}
    line_by_id: dict[str, dict[str, Any]] = {}
    for line in lines:
        line_id = _string(line.get("id"))
        if not line_id:
            continue
        line_by_id[line_id] = line
        paths, source, errors = _extract_line_paths(line, network, station_points)
        line_paths[line_id] = paths
        source_by_line[line_id] = source
        if errors:
            geometry_errors[line_id] = errors

    per_line: dict[str, dict[str, Any]] = {}
    non_octilinear: list[dict[str, Any]] = []
    overlong: list[dict[str, Any]] = []
    total_bends = 0
    total_segments = 0
    excess_bends = 0
    repeated_area_visits = 0
    all_segments_by_line: dict[str, list[Segment]] = {}
    for line_id, paths in line_paths.items():
        line = line_by_id[line_id]
        line_non_octilinear = 0
        line_overlong = 0
        line_bends = 0
        lengths: list[float] = []
        flat_segments: list[Segment] = []
        for path_index, path in enumerate(paths):
            previous_angle: float | None = None
            for segment_index, segment in enumerate(path):
                start, end = segment["start"], segment["end"]
                angle, error, bucket = _angle(start, end)
                length = _distance(start, end)
                if length <= 0.5:
                    continue
                record = {
                    **segment,
                    "lineId": line_id,
                    "pathIndex": path_index,
                    "segmentIndex": segment_index,
                    "angle": angle,
                    "angleError": error,
                    "directionBucket": bucket,
                    "length": length,
                }
                flat_segments.append(record)
                lengths.append(length)
                total_segments += 1
                if error > args.angle_tolerance:
                    line_non_octilinear += 1
                    non_octilinear.append(
                        {
                            "lineId": line_id,
                            "pathIndex": path_index,
                            "segmentIndex": segment_index,
                            "start": [round(start[0], 3), round(start[1], 3)],
                            "end": [round(end[0], 3), round(end[1], 3)],
                            "angle": round(angle, 3),
                            "error": round(error, 3),
                            "length": round(length, 3),
                        }
                    )
                if previous_angle is not None:
                    direction_change = abs((angle - previous_angle + 180.0) % 360.0 - 180.0)
                    if direction_change > args.angle_tolerance:
                        line_bends += 1
                previous_angle = angle

                midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
                if _is_express(line):
                    threshold_fraction = args.express_segment_fraction
                    threshold_class = "express/regional"
                elif _point_in_bounds(midpoint, core_bounds):
                    threshold_fraction = args.core_segment_fraction
                    threshold_class = "core"
                else:
                    threshold_fraction = args.outer_segment_fraction
                    threshold_class = "outer ordinary"
                threshold = width * threshold_fraction
                if length > threshold:
                    line_overlong += 1
                    overlong.append(
                        {
                            "lineId": line_id,
                            "pathIndex": path_index,
                            "segmentIndex": segment_index,
                            "length": round(length, 3),
                            "threshold": round(threshold, 3),
                            "thresholdClass": threshold_class,
                            "start": [round(start[0], 3), round(start[1], 3)],
                            "end": [round(end[0], 3), round(end[1], 3)],
                        }
                    )
        bend_limit = _bend_limit(line)
        line_excess = max(0, line_bends - bend_limit)
        excess_bends += line_excess
        total_bends += line_bends
        repeated = _repeated_area_visits(line, station_by_id)
        repeated_area_visits += repeated
        all_segments_by_line[line_id] = flat_segments
        mean_length = sum(lengths) / len(lengths) if lengths else None
        spacing_cv = None
        if lengths and mean_length and len(lengths) >= 2:
            spacing_cv = math.sqrt(sum((length - mean_length) ** 2 for length in lengths) / len(lengths)) / mean_length
        per_line[line_id] = {
            "geometrySource": source_by_line.get(line_id),
            "pathCount": len(paths),
            "segmentCount": len(flat_segments),
            "nonOctilinearSegmentCount": line_non_octilinear,
            "bendCount": line_bends,
            "bendLimit": bend_limit,
            "excessBendCount": line_excess,
            "overlongSegmentCount": line_overlong,
            "meanSegmentLength": round(mean_length, 3) if mean_length is not None else None,
            "maximumSegmentLength": round(max(lengths), 3) if lengths else None,
            "segmentLengthCoefficientOfVariation": round(spacing_cv, 4) if spacing_cv is not None else None,
            "repeatedAreaVisitCount": repeated,
        }

    # Inter-line crossings.  Shared station coordinates are the only automatic
    # interchange exemptions; collinear overlap is classified separately.
    shared_station_points: dict[tuple[str, str], list[Point]] = defaultdict(list)
    for station_id, station in station_by_id.items():
        point = station_points.get(station_id)
        if not point:
            continue
        line_ids = sorted(set(_id_list(station.get("lines"))))
        for first_index, first in enumerate(line_ids):
            for second in line_ids[first_index + 1 :]:
                shared_station_points[(first, second)].append(point)

    non_interchange_crossings: list[dict[str, Any]] = []
    shared_overlaps: list[dict[str, Any]] = []
    crossing_keys: set[tuple[str, str, int, int]] = set()
    overlap_keys: set[tuple[str, str, int, int]] = set()
    line_ids = sorted(all_segments_by_line)
    for first_index, first_line in enumerate(line_ids):
        for second_line in line_ids[first_index + 1 :]:
            pair = (first_line, second_line)
            interchange_points = shared_station_points.get(pair, [])
            for first_segment in all_segments_by_line[first_line]:
                for second_segment in all_segments_by_line[second_line]:
                    kind, point = _segment_intersection(first_segment, second_segment)
                    if kind == "none" or point is None:
                        continue
                    quantised = (first_line, second_line, round(point[0] / args.crossing_merge_tolerance), round(point[1] / args.crossing_merge_tolerance))
                    if kind == "overlap":
                        if quantised not in overlap_keys:
                            overlap_keys.add(quantised)
                            shared_overlaps.append(
                                {"lineIds": [first_line, second_line], "point": [round(point[0], 3), round(point[1], 3)]}
                            )
                        continue
                    if any(_distance(point, station_point) <= args.interchange_tolerance for station_point in interchange_points):
                        continue
                    if quantised in crossing_keys:
                        continue
                    crossing_keys.add(quantised)
                    non_interchange_crossings.append(
                        {
                            "lineIds": [first_line, second_line],
                            "point": [round(point[0], 3), round(point[1], 3)],
                            "inCoreArea": _point_in_bounds(point, core_bounds),
                        }
                    )

    # Self-intersections, excluding adjacent segments and the intended first /
    # last meeting of a closed loop.
    self_intersections: list[dict[str, Any]] = []
    for line_id, paths in line_paths.items():
        line = line_by_id[line_id]
        for path_index, path in enumerate(paths):
            for first_index, first in enumerate(path):
                for second_index in range(first_index + 2, len(path)):
                    if first_index == 0 and second_index == len(path) - 1 and _is_loop(line) and (
                        _is_closed(line, _id_list(line.get("stations"))) or _paths_are_closed([path])
                    ):
                        continue
                    kind, point = _segment_intersection(first, path[second_index])
                    if kind != "none" and point is not None:
                        self_intersections.append(
                            {
                                "lineId": line_id,
                                "pathIndex": path_index,
                                "segments": [first_index, second_index],
                                "kind": kind,
                                "point": [round(point[0], 3), round(point[1], 3)],
                            }
                        )

    loop_lines = [line for line in lines if _is_loop(line)]
    unclosed_loop_ids = [
        _string(line.get("id"))
        for line in loop_lines
        if not (
            _is_closed(line, _id_list(line.get("stations")))
            or _paths_are_closed(line_paths.get(_string(line.get("id")), []))
        )
    ]
    core_crossing_count = sum(crossing["inCoreArea"] for crossing in non_interchange_crossings)
    bbox = _load_bbox_metrics(Path(args.label_bboxes), width, height)

    interchange_line_counts = [len(set(_id_list(station.get("lines")))) for station in stations]
    overconcentrated_hubs = sum(count > 4 for count in interchange_line_counts) + max(0, sum(count == 4 for count in interchange_line_counts) - 2)

    high_penalties = {
        "nonOctilinearSegments": len(non_octilinear) * 8.0,
        "nonInterchangeCrossings": len(non_interchange_crossings) * 2.5,
        "unclosedLoops": len(unclosed_loop_ids) * 25.0,
        "lineSelfIntersections": len(self_intersections) * 10.0,
        "labelCollisions": (bbox["labelCollisionCount"] * 5.0) if bbox["labelCollisionCount"] is not None else None,
        "labelsOutOfBounds": (bbox["labelOutOfBoundsCount"] * 5.0) if bbox["labelOutOfBoundsCount"] is not None else None,
    }
    medium_penalties = {
        "excessBends": excess_bends * 1.5,
        "overlongSegments": len(overlong) * 3.0,
        "overconcentratedHubs": overconcentrated_hubs * 5.0,
    }
    low_penalties = {"repeatedAreaVisits": repeated_area_visits * 1.0}
    numeric_penalties = [
        value
        for group in (high_penalties, medium_penalties, low_penalties)
        for value in group.values()
        if isinstance(value, (int, float))
    ]
    penalty_total = sum(numeric_penalties)
    final_score = max(0.0, 100.0 - penalty_total)

    average_bends = total_bends / len(line_paths) if line_paths else 0.0
    result: dict[str, Any] = {
        "scorer": "score_layout",
        "version": VERSION,
        "input": args.input,
        "geometryComplete": bool(line_paths) and all(per_line[line_id]["segmentCount"] > 0 for line_id in per_line),
        "geometryErrors": geometry_errors,
        "canvas": {"width": width, "height": height, "source": canvas_source},
        "coreAreaBounds": {
            "xMin": core_bounds[0],
            "yMin": core_bounds[1],
            "xMax": core_bounds[2],
            "yMax": core_bounds[3],
            "source": core_source,
        },
        "lineCountMeasured": len(line_paths),
        "totalSegmentCount": total_segments,
        "nonOctilinearSegmentCount": len(non_octilinear),
        "nonInterchangeCrossingCount": len(non_interchange_crossings),
        "coreAreaCrossingCount": int(core_crossing_count),
        "totalBendCount": total_bends,
        "averageBendsPerLine": round(average_bends, 4),
        "excessBendCount": excess_bends,
        "overlongSegmentCount": len(overlong),
        "lineSelfIntersectionCount": len(self_intersections),
        "unclosedLoopCount": len(unclosed_loop_ids),
        "sharedCorridorOverlapCount": len(shared_overlaps),
        "repeatedAreaVisitCount": repeated_area_visits,
        "labelCollisionCount": bbox["labelCollisionCount"],
        "labelOutOfBoundsCount": bbox["labelOutOfBoundsCount"],
        "minimumChineseFontSize": bbox["minimumChineseFontSize"],
        "minimumEnglishFontSize": bbox["minimumEnglishFontSize"],
        "labelMeasurementSource": bbox["source"],
        "labelMeasurementError": bbox["error"],
        "angleToleranceDegrees": args.angle_tolerance,
        "perLine": per_line,
        "evidence": {
            "nonOctilinearSegments": non_octilinear,
            "nonInterchangeCrossings": non_interchange_crossings,
            "overlongSegments": overlong,
            "lineSelfIntersections": self_intersections,
            "sharedCorridorOverlaps": shared_overlaps,
            "unclosedLoopLineIds": unclosed_loop_ids,
        },
        "penalties": {
            "high": high_penalties,
            "medium": medium_penalties,
            "low": low_penalties,
            "totalApplied": round(penalty_total, 3),
            "note": "null browser-only metrics are unknown and contribute no penalty; they are not treated as passing",
        },
        "score": round(final_score, 3),
    }
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure v4 layout geometry and write layout_metrics.json.")
    parser.add_argument("--input", default="network.json", help="network JSON path")
    parser.add_argument("--output", default="layout_metrics.json", help="metrics output path")
    parser.add_argument("--svg", default="metro.svg", help="SVG used only to obtain the actual viewBox")
    parser.add_argument("--label-bboxes", default="label_bbox_report.json", help="rendered text-bounds JSON")
    parser.add_argument("--angle-tolerance", type=float, default=1.5)
    parser.add_argument("--core-segment-fraction", type=float, default=0.10)
    parser.add_argument("--outer-segment-fraction", type=float, default=0.16)
    parser.add_argument("--express-segment-fraction", type=float, default=0.24)
    parser.add_argument("--interchange-tolerance", type=float, default=2.0)
    parser.add_argument("--crossing-merge-tolerance", type=float, default=1.0)
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        network = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(network, dict):
            raise ValueError("network top-level value must be an object")
        payload = score(network, args)
        exit_code = 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload = {
            "scorer": "score_layout",
            "version": VERSION,
            "input": args.input,
            "geometryComplete": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        exit_code = 2

    text = json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2)
    print(text)
    try:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"score_layout: cannot write {args.output}: {exc}", file=sys.stderr)
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
