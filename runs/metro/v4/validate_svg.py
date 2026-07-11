#!/usr/bin/env python3
"""Validate metro.svg structure, content, typography and route geometry.

Only Python's standard library is used.  Geometry checks inspect the rendered
coordinate system (including SVG transforms) and accept straight route segments
only when they are within ±1.5° of an octilinear direction.  Curves are allowed
for short rounded corners, but a long curve cannot be used to hide an arbitrary
route direction.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


VERSION = "1.0"
NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


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


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.fullmatch(rf"\s*({NUMBER_RE})(?:px)?\s*", value, flags=re.I)
    return float(match.group(1)) if match else None


def _matrix_multiply(
    left: tuple[float, float, float, float, float, float],
    right: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply_matrix(
    matrix: tuple[float, float, float, float, float, float], point: tuple[float, float]
) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def _parse_transform(value: str) -> tuple[float, float, float, float, float, float]:
    result = IDENTITY
    for match in re.finditer(r"([A-Za-z]+)\s*\(([^)]*)\)", value or ""):
        name = match.group(1).casefold()
        nums = [float(number) for number in re.findall(NUMBER_RE, match.group(2))]
        matrix = IDENTITY
        if name == "matrix" and len(nums) == 6:
            matrix = tuple(nums)  # type: ignore[assignment]
        elif name == "translate" and nums:
            matrix = (1.0, 0.0, 0.0, 1.0, nums[0], nums[1] if len(nums) > 1 else 0.0)
        elif name == "scale" and nums:
            matrix = (nums[0], 0.0, 0.0, nums[1] if len(nums) > 1 else nums[0], 0.0, 0.0)
        elif name == "rotate" and nums:
            angle = math.radians(nums[0])
            rotation = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle), 0.0, 0.0)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                matrix = _matrix_multiply(
                    _matrix_multiply((1, 0, 0, 1, cx, cy), rotation),
                    (1, 0, 0, 1, -cx, -cy),
                )
            else:
                matrix = rotation
        elif name == "skewx" and nums:
            matrix = (1.0, 0.0, math.tan(math.radians(nums[0])), 1.0, 0.0, 0.0)
        elif name == "skewy" and nums:
            matrix = (1.0, math.tan(math.radians(nums[0])), 0.0, 1.0, 0.0, 0.0)
        result = _matrix_multiply(result, matrix)
    return result


def _parse_style(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for declaration in (value or "").split(";"):
        if ":" not in declaration:
            continue
        key, raw = declaration.split(":", 1)
        result[key.strip().casefold()] = raw.strip()
    return result


def _parse_css(root: ET.Element) -> list[tuple[str, dict[str, str]]]:
    rules: list[tuple[str, dict[str, str]]] = []
    for element in root.iter():
        if _local_name(element.tag) != "style":
            continue
        css = re.sub(r"/\*.*?\*/", "", "".join(element.itertext()), flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            declarations = _parse_style(match.group(2))
            for selector in match.group(1).split(","):
                selector = selector.strip()
                if selector and not selector.startswith("@"):
                    rules.append((selector, declarations))
    return rules


def _selector_matches(element: ET.Element, selector: str) -> bool:
    # Descendant combinators are conservatively reduced to their final simple
    # selector.  That is sufficient for the stylesheet patterns generated here.
    simple = re.split(r"\s+|>", selector.strip())[-1]
    simple = re.sub(r":[\w-]+(?:\([^)]*\))?", "", simple)
    element_id = element.get("id", "")
    classes = set(element.get("class", "").split())
    id_matches = re.findall(r"#([\w:-]+)", simple)
    class_matches = re.findall(r"\.([\w:-]+)", simple)
    tag_match = re.match(r"^[A-Za-z][\w:-]*", simple)
    if id_matches and element_id not in id_matches:
        return False
    if any(class_name not in classes for class_name in class_matches):
        return False
    if tag_match and _local_name(element.tag) != tag_match.group(0).casefold().split(":")[-1]:
        return False
    return bool(id_matches or class_matches or tag_match)


def _computed_property(
    element: ET.Element,
    property_name: str,
    rules: list[tuple[str, dict[str, str]]],
) -> str | None:
    value: str | None = None
    for selector, declarations in rules:
        if property_name in declarations and _selector_matches(element, selector):
            value = declarations[property_name]
    if property_name in element.attrib:
        value = element.get(property_name)
    inline = _parse_style(element.get("style", ""))
    if property_name in inline:
        value = inline[property_name]
    return value


def _font_size(value: str | None, inherited: float) -> float | None:
    if value is None:
        return inherited
    match = re.fullmatch(rf"\s*({NUMBER_RE})\s*(px|pt|em|rem|%)?\s*", value, flags=re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "px").casefold()
    if unit == "pt":
        return number * 96.0 / 72.0
    if unit == "em":
        return number * inherited
    if unit == "rem":
        return number * 16.0
    if unit == "%":
        return number * inherited / 100.0
    return number


def _path_segments(d: str) -> tuple[list[tuple[tuple[float, float], tuple[float, float], str]], list[str]]:
    tokens = re.findall(rf"[AaCcHhLlMmQqSsTtVvZz]|{NUMBER_RE}", d or "")
    counts = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    segments: list[tuple[tuple[float, float], tuple[float, float], str]] = []
    errors: list[str] = []
    current = (0.0, 0.0)
    subpath_start = current
    command: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"[A-Za-z]", token):
            command = token
            index += 1
            if command.upper() == "Z":
                if current != subpath_start:
                    segments.append((current, subpath_start, "line-Z"))
                current = subpath_start
                command = None
                continue
        if command is None:
            errors.append(f"number without path command at token {index}")
            break
        upper = command.upper()
        needed = counts.get(upper)
        if needed is None:
            errors.append(f"unsupported path command {command}")
            command = None
            continue
        if index + needed > len(tokens) or any(re.fullmatch(r"[A-Za-z]", value) for value in tokens[index : index + needed]):
            errors.append(f"incomplete {command} command at token {index}")
            break
        values = [float(value) for value in tokens[index : index + needed]]
        index += needed
        relative = command.islower()
        old = current
        if upper in {"M", "L", "T"}:
            endpoint = (values[-2], values[-1])
        elif upper == "H":
            endpoint = (values[0], 0.0 if relative else current[1])
            if relative:
                endpoint = (values[0], 0.0)
        elif upper == "V":
            endpoint = (0.0 if relative else current[0], values[0])
            if relative:
                endpoint = (0.0, values[0])
        else:  # C, S, Q and A all end with x,y.
            endpoint = (values[-2], values[-1])
        if relative:
            endpoint = (current[0] + endpoint[0], current[1] + endpoint[1])
        if upper == "M":
            current = endpoint
            subpath_start = current
            command = "l" if relative else "L"
            continue
        kind = "line-" + upper if upper in {"L", "H", "V"} else "curve-" + upper
        current = endpoint
        if old != current:
            segments.append((old, current, kind))
    return segments, errors


def _points_segments(value: str, close: bool = False) -> list[tuple[tuple[float, float], tuple[float, float], str]]:
    numbers = [float(number) for number in re.findall(NUMBER_RE, value or "")]
    points = list(zip(numbers[0::2], numbers[1::2]))
    segments = [(points[index - 1], points[index], "line-points") for index in range(1, len(points))]
    if close and len(points) >= 3 and points[-1] != points[0]:
        segments.append((points[-1], points[0], "line-points"))
    return segments


def _angle_error(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float, float]:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    nearest = round(angle / 45.0) * 45.0 % 360.0
    error = abs((angle - nearest + 180.0) % 360.0 - 180.0)
    return angle, error, length


def _route_hint(element: ET.Element) -> bool:
    value = " ".join((element.get("id", ""), element.get("class", ""), element.get("data-role", ""))).casefold()
    tokens = set(re.split(r"[^a-z0-9_-]+", value))
    exact = {"line", "route", "routes", "track", "tracks", "metro-line", "line-route", "route-path", "line-path", "service-path"}
    return bool(tokens & exact) or any(
        element.get(attribute) is not None for attribute in ("data-line-id", "data-line", "data-route-id")
    )


def _legend_hint(element: ET.Element) -> bool:
    value = " ".join((element.get("id", ""), element.get("class", ""), element.get("data-role", ""))).casefold()
    return bool(re.search(r"(?:^|[^a-z])legend(?:[^a-z]|$)", value)) or "图例" in value


def _marker_hint(element: ET.Element) -> bool:
    value = " ".join((element.get("id", ""), element.get("class", ""), element.get("data-role", ""))).casefold()
    return bool(re.search(r"(?:station|stations|stop|stops|interchange|terminal|hub)(?:[-_\s]|$)", value)) or any(
        element.get(attribute) is not None for attribute in ("data-station-id", "data-station")
    )


def _known_ids_in_text(value: str, known_ids: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for known_id in known_ids:
        if not known_id:
            continue
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(known_id)}(?![A-Za-z0-9])", value, flags=re.I):
            result.add(known_id)
    return result


class Report:
    def __init__(self, svg_path: Path, network_path: Path) -> None:
        self.payload: dict[str, Any] = {
            "validator": "validate_svg",
            "version": VERSION,
            "input": str(svg_path),
            "network": str(network_path),
            "valid": False,
            "summary": {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0},
            "metrics": {},
            "checks": [],
            "errors": [],
        }

    def add(self, check_id: str, status: str, message: str, details: Any | None = None) -> None:
        item: dict[str, Any] = {"id": check_id, "status": status, "message": message}
        if details is not None:
            item["details"] = details
        self.payload["checks"].append(item)
        key = {"pass": "passed", "fail": "failed", "warn": "warnings", "skip": "skipped"}[status]
        self.payload["summary"][key] += 1

    def finish(self) -> dict[str, Any]:
        self.payload["valid"] = self.payload["summary"]["failed"] == 0 and not self.payload["errors"]
        return self.payload


def validate_svg(
    raw_svg: str,
    root: ET.Element,
    network: dict[str, Any] | None,
    args: argparse.Namespace,
    report: Report,
) -> dict[str, Any]:
    report.add(
        "document.svg_root",
        "pass" if _local_name(root.tag) == "svg" else "fail",
        "document root is svg" if _local_name(root.tag) == "svg" else "document root must be svg",
    )

    lines = _records(network.get("lines")) if network else []
    stations = _records(network.get("stations")) if network else []
    line_ids = [_string(line.get("id")) for line in lines if _string(line.get("id"))]
    station_ids = [_string(station.get("id")) for station in stations if _string(station.get("id"))]
    report.add(
        "document.network_loaded",
        "pass" if network is not None else "fail",
        f"loaded {len(lines)} lines and {len(stations)} stations from network" if network is not None else "network.json is required for exact SVG content verification",
    )

    elements = list(root.iter())
    forbidden_tags = defaultdict(int)
    for element in elements:
        tag = _local_name(element.tag)
        if tag in {"image", "foreignobject", "script", "iframe", "object", "embed"}:
            forbidden_tags[tag] += 1
    report.add(
        "self_contained.forbidden_elements",
        "pass" if not forbidden_tags else "fail",
        "no image, foreignObject, script, or embedded external document elements found" if not forbidden_tags else "forbidden SVG elements were found",
        dict(forbidden_tags),
    )

    external_references: list[dict[str, str]] = []
    for element in elements:
        for key, value in element.attrib.items():
            local_key = _local_name(key)
            if local_key in {"href", "src"} and value and not value.lstrip().startswith("#"):
                external_references.append({"element": _local_name(element.tag), "attribute": local_key, "value": value[:160]})
            for url in re.findall(r"url\(\s*['\"]?([^)'\"]+)", value, flags=re.I):
                if not url.lstrip().startswith("#"):
                    external_references.append({"element": _local_name(element.tag), "attribute": local_key, "value": url[:160]})
    # Namespace declarations contain W3C URLs but are identifiers, not fetched
    # resources.  Remove them before scanning the remaining source for URLs.
    raw_without_xmlns = re.sub(
        r"\s+xmlns(?::[\w.-]+)?\s*=\s*(['\"]).*?\1",
        "",
        raw_svg,
        flags=re.I | re.S,
    )
    raw_flags = {
        "base64": bool(re.search(r"base64\s*,", raw_svg, flags=re.I)),
        "externalUrl": bool(re.search(r"(?:https?:)?//", raw_without_xmlns, flags=re.I)),
        "cssImport": bool(re.search(r"@import\b", raw_svg, flags=re.I)),
        "externalEntity": bool(re.search(r"<!ENTITY\s+[^>]*(?:SYSTEM|PUBLIC)", raw_svg, flags=re.I)),
    }
    references_ok = not external_references and not any(raw_flags.values())
    report.add(
        "self_contained.external_references",
        "pass" if references_ok else "fail",
        "SVG has no Base64 data or external references" if references_ok else "SVG contains Base64 data or external references",
        {"references": external_references[:50], "rawFlags": raw_flags, "truncated": len(external_references) > 50},
    )

    viewbox_numbers = [float(number) for number in re.findall(NUMBER_RE, root.get("viewBox", ""))]
    viewbox_ok = len(viewbox_numbers) == 4 and viewbox_numbers[2] > 0 and viewbox_numbers[3] > 0
    report.add(
        "canvas.viewbox",
        "pass" if viewbox_ok else "fail",
        f"valid viewBox is {viewbox_numbers}" if viewbox_ok else "viewBox must contain x, y, positive width and positive height",
        {"value": root.get("viewBox"), "parsed": viewbox_numbers},
    )
    canvas_width = viewbox_numbers[2] if viewbox_ok else 2400.0
    canvas_height = viewbox_numbers[3] if viewbox_ok else 1600.0
    report.payload["metrics"].update({"viewBox": viewbox_numbers if viewbox_ok else None})

    css_rules = _parse_css(root)
    text_records: list[dict[str, Any]] = []
    geometry_records: list[dict[str, Any]] = []
    exact_station_markers: set[str] = set()
    fallback_marker_count = 0
    legend_elements: list[ET.Element] = []
    path_errors: list[dict[str, str]] = []

    def walk(
        element: ET.Element,
        parent_matrix: tuple[float, float, float, float, float, float],
        parent_route: bool,
        parent_line_ids: set[str],
        parent_legend: bool,
        parent_marker: bool,
        inherited_font: float,
    ) -> None:
        nonlocal fallback_marker_count
        matrix = _matrix_multiply(parent_matrix, _parse_transform(element.get("transform", "")))
        direct_route = _route_hint(element)
        route = parent_route or direct_route
        legend = parent_legend or _legend_hint(element)
        marker_context = parent_marker or _marker_hint(element)
        if _legend_hint(element):
            legend_elements.append(element)
        line_context = set(parent_line_ids) if parent_route else set()
        explicit_line_value = element.get("data-line-id") or element.get("data-line") or element.get("data-route-id") or ""
        explicit_line_ids = re.split(r"[,\s]+", explicit_line_value.strip()) if explicit_line_value else []
        line_context.update(line_id for line_id in explicit_line_ids if line_id)
        if direct_route:
            descriptor = " ".join(element.attrib.values())
            line_context.update(_known_ids_in_text(descriptor, line_ids))

        font_value = _computed_property(element, "font-size", css_rules)
        current_font = _font_size(font_value, inherited_font)
        effective_font = inherited_font if current_font is None else current_font
        tag = _local_name(element.tag)
        if tag in {"text", "tspan", "textpath"}:
            content = _normalise_text("".join(element.itertext()))
            if content:
                text_records.append(
                    {
                        "text": content,
                        "fontSize": current_font,
                        "id": element.get("id"),
                        "class": element.get("class", ""),
                        "legend": legend,
                        "stationHint": _marker_hint(element) or "label" in element.get("class", "").casefold(),
                    }
                )

        marker = marker_context and not legend
        if marker:
            data_station = element.get("data-station-id") or element.get("data-station") or ""
            if data_station in station_ids:
                exact_station_markers.add(data_station)
            descriptor = " ".join(element.attrib.values())
            exact_station_markers.update(_known_ids_in_text(descriptor, station_ids))
            if tag in {"circle", "ellipse", "rect", "path", "use"}:
                fallback_marker_count += 1

        if route and not legend and tag in {"path", "polyline", "polygon", "line"}:
            segments: list[tuple[tuple[float, float], tuple[float, float], str]] = []
            errors: list[str] = []
            if tag == "path":
                segments, errors = _path_segments(element.get("d", ""))
            elif tag in {"polyline", "polygon"}:
                segments = _points_segments(element.get("points", ""), close=tag == "polygon")
            elif tag == "line":
                x1, y1 = _float(element.get("x1")), _float(element.get("y1"))
                x2, y2 = _float(element.get("x2")), _float(element.get("y2"))
                if None not in (x1, y1, x2, y2):
                    segments = [((x1, y1), (x2, y2), "line-element")]  # type: ignore[arg-type]
                else:
                    errors.append("line element has invalid coordinates")
            transformed = [(_apply_matrix(matrix, start), _apply_matrix(matrix, end), kind) for start, end, kind in segments]
            if errors:
                path_errors.extend(
                    {"element": element.get("id") or tag, "message": error} for error in errors
                )
            geometry_records.append(
                {
                    "element": element.get("id") or tag,
                    "lineIds": sorted(line_context),
                    "segments": transformed,
                    "dasharray": _computed_property(element, "stroke-dasharray", css_rules),
                }
            )

        for child in list(element):
            walk(child, matrix, route, line_context, legend, marker_context, effective_font)

    walk(root, IDENTITY, False, set(), False, False, 16.0)

    full_text = "\n".join(record["text"] for record in text_records)
    document_annotation = "不按比例" in full_text and bool(re.search(r"not\s+to\s+scale", full_text, flags=re.I))
    report.add(
        "annotation.not_to_scale",
        "pass" if document_annotation else "fail",
        "bilingual not-to-scale annotation is present" if document_annotation else "SVG must state ‘线路示意图，不按比例 / Schematic map — not to scale’",
    )

    legend_unique = []
    seen_legend_ids: set[int] = set()
    for element in legend_elements:
        if id(element) not in seen_legend_ids:
            legend_unique.append(element)
            seen_legend_ids.add(id(element))
    legend_text = "\n".join(_normalise_text("".join(element.itertext())) for element in legend_unique)
    missing_legend_lines: list[str] = []
    for line in lines:
        candidates = [_string(line.get("nameZh")), _string(line.get("nameEn")), _string(line.get("id"))]
        if not any(candidate and candidate in legend_text for candidate in candidates):
            missing_legend_lines.append(_string(line.get("id")) or _string(line.get("nameZh")))
    legend_ok = bool(legend_unique) and (not lines or not missing_legend_lines)
    report.add(
        "content.legend",
        "pass" if legend_ok else "fail",
        "legend exists and covers every network line" if legend_ok else "legend is missing or does not cover every network line",
        {"legendContainerCount": len(legend_unique), "missingLineIds": missing_legend_lines},
    )

    associated_geometry: dict[str, int] = defaultdict(int)
    unknown_geometry_count = 0
    for geometry in geometry_records:
        if geometry["lineIds"]:
            for line_id in geometry["lineIds"]:
                if line_id in line_ids:
                    associated_geometry[line_id] += 1
        else:
            unknown_geometry_count += 1
    missing_geometry = [line_id for line_id in line_ids if associated_geometry[line_id] == 0]
    geometry_ok = bool(geometry_records) and (not lines or not missing_geometry)
    report.add(
        "content.line_geometry",
        "pass" if geometry_ok else "fail",
        "route geometry exists for every line" if geometry_ok else "route geometry is absent or cannot be associated with every line",
        {
            "geometryElementCount": len(geometry_records),
            "unassociatedGeometryElementCount": unknown_geometry_count,
            "missingLineIds": missing_geometry,
            "associatedElementsByLine": dict(associated_geometry),
        },
    )

    non_octilinear: list[dict[str, Any]] = []
    long_curves: list[dict[str, Any]] = []
    straight_count = 0
    curve_count = 0
    curve_limit = min(canvas_width, canvas_height) * args.max_rounded_curve_fraction
    for geometry in geometry_records:
        for start, end, kind in geometry["segments"]:
            angle, error, length = _angle_error(start, end)
            if length <= 0.5:
                continue
            evidence = {
                "element": geometry["element"],
                "lineIds": geometry["lineIds"],
                "start": [round(start[0], 3), round(start[1], 3)],
                "end": [round(end[0], 3), round(end[1], 3)],
                "angle": round(angle, 3),
                "error": round(error, 3),
                "length": round(length, 3),
                "kind": kind,
            }
            if kind.startswith("line"):
                straight_count += 1
                if error > args.angle_tolerance:
                    non_octilinear.append(evidence)
            else:
                curve_count += 1
                if length > curve_limit:
                    long_curves.append(evidence)
    route_ok = not non_octilinear and not long_curves and not path_errors
    report.payload["metrics"].update(
        {
            "routeStraightSegmentCount": straight_count,
            "routeCurveSegmentCount": curve_count,
            "nonOctilinearSegmentCount": len(non_octilinear),
            "longCurveChordCount": len(long_curves),
            "pathParseErrorCount": len(path_errors),
            "angleToleranceDegrees": args.angle_tolerance,
        }
    )
    report.add(
        "routing.octilinear",
        "pass" if route_ok else "fail",
        "all straight route segments are octilinear and curves are limited to short corners" if route_ok else "non-octilinear segments, long curves, or malformed route paths were found",
        {
            "nonOctilinear": non_octilinear[:100],
            "longCurves": long_curves[:100],
            "pathErrors": path_errors[:100],
            "truncated": len(non_octilinear) > 100 or len(long_curves) > 100 or len(path_errors) > 100,
            "curveChordLimit": round(curve_limit, 3),
        },
    )

    marker_count = len(exact_station_markers) if exact_station_markers else fallback_marker_count
    marker_ok = marker_count >= len(stations) if stations else marker_count > 0
    missing_markers = sorted(set(station_ids) - exact_station_markers) if exact_station_markers else []
    report.payload["metrics"].update(
        {
            "stationMarkerCount": marker_count,
            "stationMarkerEvidence": "exact-data-or-id" if exact_station_markers else "class-based-fallback",
        }
    )
    report.add(
        "content.station_symbols",
        "pass" if marker_ok else "fail",
        "station symbols cover all network stations" if marker_ok else "station symbols do not cover all network stations",
        {
            "actual": marker_count,
            "expected": len(stations) if stations else ">=1",
            "missingExactIds": missing_markers[:100],
            "missingExactIdsTruncated": len(missing_markers) > 100,
            "evidence": report.payload["metrics"]["stationMarkerEvidence"],
        },
    )

    def label_matches(name: str) -> list[dict[str, Any]]:
        exact = [record for record in text_records if record["text"] == name]
        hinted = [record for record in exact if record["stationHint"] and not record["legend"]]
        return hinted or [record for record in exact if not record["legend"]] or exact

    missing_chinese: list[str] = []
    missing_english: list[str] = []
    chinese_sizes: list[float] = []
    english_sizes: list[float] = []
    unknown_chinese_sizes: list[str] = []
    unknown_english_sizes: list[str] = []
    for station in stations:
        station_id = _string(station.get("id"))
        zh = _string(station.get("nameZh"))
        en = _string(station.get("nameEn"))
        zh_matches = label_matches(zh) if zh else []
        en_matches = label_matches(en) if en else []
        if not zh_matches:
            missing_chinese.append(station_id)
        else:
            sizes = [record["fontSize"] for record in zh_matches if isinstance(record["fontSize"], (int, float))]
            if sizes:
                chinese_sizes.append(min(sizes))
            else:
                unknown_chinese_sizes.append(station_id)
        if not en_matches:
            missing_english.append(station_id)
        else:
            sizes = [record["fontSize"] for record in en_matches if isinstance(record["fontSize"], (int, float))]
            if sizes:
                english_sizes.append(min(sizes))
            else:
                unknown_english_sizes.append(station_id)

    chinese_labels_ok = bool(stations) and not missing_chinese
    english_labels_ok = bool(stations) and not missing_english
    report.add(
        "content.chinese_station_labels",
        "pass" if chinese_labels_ok else "fail",
        "every station has an exact Chinese text label" if chinese_labels_ok else "one or more exact Chinese station labels are absent",
        {"found": len(stations) - len(missing_chinese), "expected": len(stations), "missingStationIds": missing_chinese[:100], "truncated": len(missing_chinese) > 100},
    )
    report.add(
        "content.english_station_labels",
        "pass" if english_labels_ok else "fail",
        "every station has an exact English text label" if english_labels_ok else "one or more exact English station labels are absent",
        {"found": len(stations) - len(missing_english), "expected": len(stations), "missingStationIds": missing_english[:100], "truncated": len(missing_english) > 100},
    )

    minimum_zh = min(chinese_sizes) if chinese_sizes else None
    minimum_en = min(english_sizes) if english_sizes else None
    report.payload["metrics"].update(
        {
            "minimumChineseStationFontSize": minimum_zh,
            "minimumEnglishStationFontSize": minimum_en,
        }
    )
    zh_font_ok = minimum_zh is not None and minimum_zh >= args.min_chinese_font and not unknown_chinese_sizes
    en_font_ok = minimum_en is not None and minimum_en >= args.min_english_font and not unknown_english_sizes
    report.add(
        "typography.minimum_chinese_station_font",
        "pass" if zh_font_ok else "fail",
        f"minimum Chinese station font is {minimum_zh}px; required ≥{args.min_chinese_font}px",
        {"minimum": minimum_zh, "required": args.min_chinese_font, "unknownSizeStationIds": unknown_chinese_sizes},
    )
    report.add(
        "typography.minimum_english_station_font",
        "pass" if en_font_ok else "fail",
        f"minimum English station font is {minimum_en}px; required ≥{args.min_english_font}px",
        {"minimum": minimum_en, "required": args.min_english_font, "unknownSizeStationIds": unknown_english_sizes},
    )

    construction_ids = {
        _string(line.get("id"))
        for line in lines
        if any(token in " ".join(str(value) for value in (line.get("status"), line.get("type"))).casefold() for token in ("建设中", "在建", "under construction", "construction"))
    }
    undashed_construction: list[str] = []
    for line_id in sorted(construction_ids):
        associated = [record for record in geometry_records if line_id in record["lineIds"]]
        if not associated or not any(
            record["dasharray"] and str(record["dasharray"]).strip().casefold() not in {"none", "0"}
            for record in associated
        ):
            undashed_construction.append(line_id)
    construction_ok = bool(construction_ids) and not undashed_construction
    report.add(
        "operations.construction_style",
        "pass" if construction_ok else "fail",
        "construction line geometry uses a dashed style" if construction_ok else "construction status is absent or its route is not visibly dashed",
        {"constructionLineIds": sorted(construction_ids), "undashedOrMissing": undashed_construction},
    )

    report.payload["metrics"].update(
        {
            "elementCount": len(elements),
            "textElementCount": len(text_records),
            "legendContainerCount": len(legend_unique),
            "lineGeometryElementCount": len(geometry_records),
            "networkLineCount": len(lines),
            "networkStationCount": len(stations),
        }
    )
    return report.finish()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the final metro SVG and emit JSON.")
    parser.add_argument("--input", default="metro.svg", help="SVG path (default: metro.svg)")
    parser.add_argument("--network", default="network.json", help="network JSON path (default: network.json)")
    parser.add_argument("--output", help="also write the JSON report to this path")
    parser.add_argument("--angle-tolerance", type=float, default=1.5, help="maximum octilinear angle error in degrees")
    parser.add_argument("--min-chinese-font", type=float, default=18.0)
    parser.add_argument("--min-english-font", type=float, default=10.0)
    parser.add_argument(
        "--max-rounded-curve-fraction",
        type=float,
        default=0.02,
        help="maximum rounded-corner curve chord as fraction of shorter canvas side",
    )
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    svg_path = Path(args.input)
    network_path = Path(args.network)
    report = Report(svg_path, network_path)
    try:
        raw_svg = svg_path.read_text(encoding="utf-8")
        root = ET.fromstring(raw_svg)
        try:
            network_value = json.loads(network_path.read_text(encoding="utf-8"))
            if not isinstance(network_value, dict):
                raise ValueError("network top-level value is not an object")
            network: dict[str, Any] | None = network_value
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            network = None
            report.payload["errors"].append({"type": "NetworkLoadError", "message": str(exc)})
        payload = validate_svg(raw_svg, root, network, args, report)
        exit_code = 0 if payload["valid"] else 1
    except (OSError, ET.ParseError, ValueError) as exc:
        report.payload["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        payload = report.finish()
        exit_code = 2

    text = json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2)
    print(text)
    if args.output:
        try:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"validate_svg: cannot write {args.output}: {exc}", file=sys.stderr)
            return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
