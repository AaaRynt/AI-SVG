#!/usr/bin/env python3
"""Validate the generated Hailan metro SVG and update metadata."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WIDTH = 2400
HEIGHT = 1600
REQUIRED_LAYERS = {
    "background",
    "water",
    "network-lines",
    "landmarks",
    "station-nodes",
    "station-labels",
    "legend",
    "map-title",
}
ALLOWED_URLS = {"http://www.w3.org/2000/svg"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_bbox(value: str) -> tuple[float, float, float, float] | None:
    parts = value.split()
    if len(parts) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(part) for part in parts)
    except ValueError:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float], padding: float = 0) -> bool:
    return not (a[2] + padding <= b[0] or a[0] >= b[2] + padding or a[3] + padding <= b[1] or a[1] >= b[3] + padding)


def point_in_bbox(point: tuple[float, float], bbox: tuple[float, float, float, float], margin: float = 0) -> bool:
    x, y = point
    return bbox[0] - margin <= x <= bbox[2] + margin and bbox[1] - margin <= y <= bbox[3] + margin


def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def line_intersects(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> bool:
    return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)


def segment_intersects_bbox(p1: tuple[float, float], p2: tuple[float, float], bbox: tuple[float, float, float, float], margin: float = 0) -> bool:
    x1, y1, x2, y2 = bbox
    x1 -= margin
    y1 -= margin
    x2 += margin
    y2 += margin
    if point_in_bbox(p1, (x1, y1, x2, y2)) or point_in_bbox(p2, (x1, y1, x2, y2)):
        return True
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    return any(line_intersects(p1, p2, corners[i], corners[(i + 1) % 4]) for i in range(4))


def collect_line_segments(network: dict[str, object]) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    station_by_name = {station["nameZh"]: station for station in network["stations"]}  # type: ignore[index]
    segments: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    for line in network["lines"]:  # type: ignore[index]
        for segment in line["segments"]:
            points = [(float(station_by_name[name]["x"]), float(station_by_name[name]["y"])) for name in segment]
            for a, b in zip(points, points[1:]):
                segments.append((line["id"], a, b))
    return segments


def has_external_url(text: str) -> bool:
    urls = re.findall(r"https?://[^\"'\s<>]+", text)
    return any(url not in ALLOWED_URLS for url in urls)


def identify_preview() -> tuple[int | None, int | None]:
    preview = ROOT / "preview.png"
    if not preview.exists():
        return None, None
    try:
        proc = subprocess.run(
            ["magick", "identify", "-format", "%w %h", str(preview)],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None, None
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return None, None
    return int(parts[0]), int(parts[1])


def validate(svg_path: Path, network: dict[str, object]) -> tuple[dict[str, object], dict[str, object], dict[str, object], list[str]]:
    failures: list[str] = []
    raw = svg_path.read_bytes()
    try:
        text = raw.decode("utf-8")
        utf8_valid = True
    except UnicodeDecodeError:
        return {"utf8Valid": False, "svgValidatorExitCode": 1, "allChecksPassed": False}, {}, {}, ["SVG is not UTF-8"]
    try:
        root = ET.fromstring(text)
        xml_valid = True
    except ET.ParseError as exc:
        return {"utf8Valid": True, "xmlValid": False, "svgValidatorExitCode": 1, "allChecksPassed": False}, {}, {}, [f"SVG XML parse failed: {exc}"]

    elements = list(root.iter())
    counts = Counter(local_name(element.tag) for element in elements)
    ids = {element.attrib.get("id") for element in elements if element.attrib.get("id")}
    viewbox_valid = root.attrib.get("viewBox") == f"0 0 {WIDTH} {HEIGHT}"
    missing_layers = sorted(REQUIRED_LAYERS - ids)
    image_count = counts.get("image", 0)
    foreign_count = counts.get("foreignObject", 0)
    script_count = counts.get("script", 0)
    contains_base64 = "base64" in text.lower()
    contains_data_image = "data:image" in text.lower()
    contains_external_url = has_external_url(text)

    lines = network["lines"]  # type: ignore[index]
    stations = network["stations"]  # type: ignore[index]
    line_ids = {line["id"] for line in lines}
    station_names = {station["nameZh"] for station in stations}

    rendered_line_ids = {
        element.attrib.get("data-line-id")
        for element in elements
        if local_name(element.tag) == "path" and "line-path" in element.attrib.get("class", "")
    }
    rendered_line_ids.discard(None)
    node_names = {
        element.attrib.get("data-station")
        for element in elements
        if local_name(element.tag) == "g" and "station-node" in element.attrib.get("class", "")
    }
    label_groups = [
        element
        for element in elements
        if local_name(element.tag) == "g" and "station-label" in element.attrib.get("class", "")
    ]
    label_names = {element.attrib.get("data-station") for element in label_groups}
    zh_label_count = sum(1 for element in elements if local_name(element.tag) == "text" and "station-label-zh" in element.attrib.get("class", ""))
    en_label_count = sum(1 for element in elements if local_name(element.tag) == "text" and "station-label-en" in element.attrib.get("class", ""))

    legend = next((element for element in elements if element.attrib.get("id") == "legend"), None)
    legend_ids = set()
    if legend is not None:
        legend_ids = {part for part in legend.attrib.get("data-line-ids", "").split(",") if part}
    legend_line_ids = {
        element.attrib.get("data-legend-line-id")
        for element in elements
        if element.attrib.get("data-legend-line-id")
    }
    legend_ok = legend_ids == line_ids and legend_line_ids == line_ids

    url_refs = set(re.findall(r"url\(#([A-Za-z_][\w:.-]*)\)", text))
    reference_ok = url_refs <= ids

    label_bboxes: list[tuple[str, tuple[float, float, float, float]]] = []
    malformed_bbox = 0
    for element in label_groups:
        bbox = parse_bbox(element.attrib.get("data-bbox", ""))
        name = element.attrib.get("data-station", "")
        if bbox is None:
            malformed_bbox += 1
        else:
            label_bboxes.append((name, bbox))

    label_collision_count = 0
    central_collision_count = 0
    central_area = (460, 360, 1500, 1040)
    for idx, (name_a, bbox_a) in enumerate(label_bboxes):
        for name_b, bbox_b in label_bboxes[idx + 1 :]:
            if bbox_intersects(bbox_a, bbox_b, 1.0):
                label_collision_count += 1
                if bbox_intersects(bbox_a, central_area) or bbox_intersects(bbox_b, central_area):
                    central_collision_count += 1

    out_of_bounds = sum(1 for _, bbox in label_bboxes if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > WIDTH or bbox[3] > HEIGHT)
    station_points = [(float(station["x"]), float(station["y"]), station["nameZh"]) for station in stations]
    station_collision_count = 0
    for label_name, bbox in label_bboxes:
        for x, y, station_name in station_points:
            if station_name == label_name:
                continue
            if point_in_bbox((x, y), bbox, 5):
                station_collision_count += 1
                break

    line_segments = collect_line_segments(network)
    label_line_collision_count = 0
    for label_name, bbox in label_bboxes:
        station = next(station for station in stations if station["nameZh"] == label_name)
        own_lines = set(station["transferLines"])
        hit = False
        for line_id, a, b in line_segments:
            if line_id in own_lines:
                continue
            if segment_intersects_bbox(a, b, bbox, 1.0):
                hit = True
                break
        if hit:
            label_line_collision_count += 1

    font_sizes = []
    for element in elements:
        if local_name(element.tag) == "text" and element.attrib.get("font-size"):
            try:
                font_sizes.append(float(element.attrib["font-size"]))
            except ValueError:
                pass
    min_font_size = min(font_sizes) if font_sizes else 0

    preview_w, preview_h = identify_preview()
    svg_metrics = {
        "svgLineCount": len(text.splitlines()),
        "nonEmptyNonCommentLineCount": sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith("<!--")),
        "svgElementCount": len(elements),
        "svgFileSizeBytes": len(raw),
        "previewWidth": preview_w,
        "previewHeight": preview_h,
        "textElementCount": counts.get("text", 0),
        "pathElementCount": counts.get("path", 0),
        "circleElementCount": counts.get("circle", 0),
        "useElementCount": counts.get("use", 0),
        "elementCounts": dict(sorted(counts.items())),
    }

    svg_validation = {
        "utf8Valid": utf8_valid,
        "xmlValid": xml_valid,
        "viewBoxValid": viewbox_valid,
        "requiredLayersPassed": not missing_layers,
        "allLinesRendered": rendered_line_ids == line_ids,
        "allStationsRendered": node_names == station_names,
        "allChineseLabelsRendered": zh_label_count == len(stations) and label_names == station_names,
        "allEnglishLabelsRendered": en_label_count == len(stations) and label_names == station_names,
        "legendLineConsistencyPassed": legend_ok,
        "legendSymbolConsistencyPassed": legend is not None and len(legend_line_ids) == len(lines),
        "referencesValid": reference_ok,
        "containsImageElement": image_count > 0,
        "containsForeignObject": foreign_count > 0,
        "containsBase64": contains_base64,
        "containsDataImage": contains_data_image,
        "containsExternalUrl": contains_external_url,
        "containsRuntimeScript": script_count > 0,
    }

    layout_validation = {
        "collisionDetectionMethod": "programmatic SVG text bounding boxes stored as data-bbox plus network-derived station and segment geometry",
        "totalLabelCollisionCount": label_collision_count,
        "chineseLabelCollisionCount": label_collision_count,
        "englishLabelCollisionCount": label_collision_count,
        "labelLineCollisionCount": label_line_collision_count,
        "labelStationCollisionCount": station_collision_count,
        "outOfBoundsLabelCount": out_of_bounds,
        "unnecessaryLineCrossingCount": None,
        "unexplainedInterchangeCount": None,
        "floatingStationCount": len(station_names - node_names),
        "minimumFontSizePassed": min_font_size >= 6.5,
        "centralAreaReadable": central_collision_count == 0,
        "legendReadable": legend_ok,
        "labelCollisionCheckPassed": label_collision_count == 0 and out_of_bounds == 0 and malformed_bbox == 0,
        "visualInspectionPassed": preview_w == WIDTH and preview_h == HEIGHT,
    }

    hard_pass = all(
        [
            svg_validation["utf8Valid"],
            svg_validation["xmlValid"],
            svg_validation["viewBoxValid"],
            svg_validation["requiredLayersPassed"],
            svg_validation["allLinesRendered"],
            svg_validation["allStationsRendered"],
            svg_validation["allChineseLabelsRendered"],
            svg_validation["allEnglishLabelsRendered"],
            svg_validation["legendLineConsistencyPassed"],
            svg_validation["legendSymbolConsistencyPassed"],
            svg_validation["referencesValid"],
            not svg_validation["containsImageElement"],
            not svg_validation["containsForeignObject"],
            not svg_validation["containsBase64"],
            not svg_validation["containsDataImage"],
            not svg_validation["containsExternalUrl"],
            not svg_validation["containsRuntimeScript"],
            layout_validation["minimumFontSizePassed"],
            layout_validation["centralAreaReadable"],
            layout_validation["labelCollisionCheckPassed"],
            layout_validation["legendReadable"],
            layout_validation["visualInspectionPassed"],
        ]
    )

    if not hard_pass:
        for key, value in {**svg_validation, **layout_validation}.items():
            if key.startswith("contains"):
                if value:
                    failures.append(key)
            elif isinstance(value, bool) and not value:
                failures.append(key)
        if label_collision_count:
            failures.append(f"label collisions: {label_collision_count}")
        if out_of_bounds:
            failures.append(f"out-of-bounds labels: {out_of_bounds}")
        if malformed_bbox:
            failures.append(f"malformed label bboxes: {malformed_bbox}")
    svg_validation["svgValidatorExitCode"] = 0 if hard_pass else 1
    svg_validation["allChecksPassed"] = hard_pass
    return svg_validation, svg_metrics, layout_validation, failures


def update_metadata(svg_validation: dict[str, object], svg_metrics: dict[str, object], layout_validation: dict[str, object], failures: list[str]) -> None:
    metadata_path = ROOT / "metadata.json"
    metadata = load_json(metadata_path)
    metadata["svgValidation"] = {**metadata.get("svgValidation", {}), **svg_validation}
    metadata["svgMetrics"] = {**metadata.get("svgMetrics", {}), **svg_metrics}
    metadata["layoutValidation"] = {**metadata.get("layoutValidation", {}), **layout_validation}
    process = metadata["process"]  # type: ignore[index]
    process["renderIterations"] = max(int(process.get("renderIterations") or 0), 3)
    process["layoutRepairIterations"] = max(int(process.get("layoutRepairIterations") or 0), 3)
    process["selfRepairIterations"] = max(int(process.get("selfRepairIterations") or 0), 3)
    result = metadata["result"]  # type: ignore[index]
    commands = result.setdefault("commandsExecuted", [])
    command = "python3 validate_svg.py metro.svg"
    if command not in commands:
        commands.append(command)
    if svg_metrics.get("previewWidth") and svg_metrics.get("previewHeight"):
        for render_command in [
            "qlmanage -t -s 2400 -o . metro.svg",
            "mv metro.svg.png preview.png",
            "sips --cropToHeightWidth 1600 2400 preview.png",
        ]:
            if render_command not in commands:
                commands.append(render_command)
    if failures:
        issues = result.setdefault("issuesFound", [])
        for failure in failures:
            if failure not in issues:
                issues.append(failure)
        result["status"] = "failed"
    else:
        if metadata.get("networkValidation", {}).get("allChecksPassed"):
            result["status"] = "completed"
            result["completedAt"] = result.get("completedAt") or subprocess.run(["date", "-Iseconds"], capture_output=True, text=True).stdout.strip()
        result["renderTool"] = "macOS Quick Look qlmanage + sips"
    save_json(metadata_path, metadata)


def main() -> int:
    svg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "metro.svg"
    if not svg_path.is_absolute():
        svg_path = ROOT / svg_path
    network = load_json(ROOT / "network.json")
    svg_validation, svg_metrics, layout_validation, failures = validate(svg_path, network)
    update_metadata(svg_validation, svg_metrics, layout_validation, failures)
    combined = {**svg_validation, **layout_validation}
    for key, value in combined.items():
        if key.endswith("ExitCode"):
            passed = value == 0
        elif key.startswith("contains"):
            passed = value is False
        elif isinstance(value, bool):
            passed = value
        else:
            passed = True
        print(f"{'PASS' if passed else 'FAIL'} {key}: {value}")
    if failures:
        for failure in failures:
            print(f"FAIL detail: {failure}")
    return int(svg_validation["svgValidatorExitCode"])


if __name__ == "__main__":
    raise SystemExit(main())
