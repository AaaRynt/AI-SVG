#!/usr/bin/env python3
"""Validate the generated static SVG against the run requirements."""

from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


REQUIRED_LAYERS = [
    "background-sky",
    "sun-and-glow",
    "high-clouds",
    "distant-atmosphere",
    "mount-fuji-base",
    "mount-fuji-snow",
    "mount-fuji-ridges",
    "mount-fuji-light",
    "cloud-sea-back",
    "cloud-sea-middle",
    "cloud-sea-front",
    "distant-city",
    "city-lights",
    "shoreline",
    "lake",
    "reflections",
    "water-ripples",
    "foreground-forest",
    "final-atmosphere",
]

VISIBLE_TAGS = {
    "circle",
    "ellipse",
    "line",
    "path",
    "polygon",
    "polyline",
    "rect",
    "text",
    "use",
}

DEFINITION_TAGS = {
    "defs",
    "linearGradient",
    "radialGradient",
    "stop",
    "filter",
    "feGaussianBlur",
    "clipPath",
    "mask",
    "title",
    "desc",
}

ALLOWED_NAMESPACE_URLS = {
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/1999/xlink",
    "http://www.w3.org/XML/1998/namespace",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_viewbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (float(part) for part in parts)
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def numeric_values(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", text)]


def element_bbox(element: ET.Element) -> tuple[float, float, float, float] | None:
    tag = local_name(element.tag)
    attrs = element.attrib
    try:
        if tag == "rect":
            x = float(attrs.get("x", "0"))
            y = float(attrs.get("y", "0"))
            w = float(attrs.get("width", "0"))
            h = float(attrs.get("height", "0"))
            return x, y, x + w, y + h
        if tag == "circle":
            cx = float(attrs.get("cx", "0"))
            cy = float(attrs.get("cy", "0"))
            r = float(attrs.get("r", "0"))
            return cx - r, cy - r, cx + r, cy + r
        if tag == "ellipse":
            cx = float(attrs.get("cx", "0"))
            cy = float(attrs.get("cy", "0"))
            rx = float(attrs.get("rx", "0"))
            ry = float(attrs.get("ry", "0"))
            return cx - rx, cy - ry, cx + rx, cy + ry
        if tag == "line":
            x1 = float(attrs.get("x1", "0"))
            y1 = float(attrs.get("y1", "0"))
            x2 = float(attrs.get("x2", "0"))
            y2 = float(attrs.get("y2", "0"))
            return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if tag in {"path", "polygon", "polyline"}:
            source = attrs.get("d") or attrs.get("points") or ""
            nums = numeric_values(source)
            if len(nums) < 2:
                return None
            xs = nums[0::2]
            ys = nums[1::2]
            return min(xs), min(ys), max(xs), max(ys)
    except ValueError:
        return None
    return None


def intersects(bbox: tuple[float, float, float, float], viewbox: tuple[float, float, float, float], margin: float = 80) -> bool:
    vx, vy, vw, vh = viewbox
    x1, y1, x2, y2 = bbox
    return not (x2 < vx - margin or x1 > vx + vw + margin or y2 < vy - margin or y1 > vy + vh + margin)


def is_effectively_zero(value: str | None) -> bool:
    if value is None:
        return False
    try:
        return float(value) <= 0.001
    except ValueError:
        return False


def visible_descendant_count(element: ET.Element) -> int:
    total = 0
    for child in element.iter():
        if child is element:
            continue
        tag = local_name(child.tag)
        if tag in VISIBLE_TAGS:
            if child.attrib.get("display") == "none":
                continue
            if is_effectively_zero(child.attrib.get("opacity")):
                continue
            total += 1
    return total


def collect_ids(root: ET.Element) -> set[str]:
    ids: set[str] = set()
    for element in root.iter():
        element_id = element.attrib.get("id")
        if element_id:
            ids.add(element_id)
    return ids


def collect_url_refs(text: str) -> list[str]:
    return re.findall(r"url\(#([A-Za-z_][\w:.-]*)\)", text)


def collect_use_refs(root: ET.Element) -> list[str]:
    refs: list[str] = []
    for element in root.iter():
        if local_name(element.tag) != "use":
            continue
        for key, value in element.attrib.items():
            if key.endswith("href") and value.startswith("#"):
                refs.append(value[1:])
    return refs


def has_external_url(text: str) -> bool:
    candidates = re.findall(r"https?://[^\"'\s<>]+", text)
    return any(candidate not in ALLOWED_NAMESPACE_URLS for candidate in candidates)


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "fuji.svg")
    checks: list[tuple[str, bool, str]] = []
    if not path.exists():
        print(f"FAIL exists: {path} not found")
        return 1

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        utf8_valid = True
    except UnicodeDecodeError as exc:
        print(f"FAIL utf8: {exc}")
        return 1

    checks.append(("utf8Valid", utf8_valid, "valid UTF-8"))
    try:
        root = ET.fromstring(text)
        xml_valid = True
    except ET.ParseError as exc:
        print(f"FAIL xmlValid: {exc}")
        return 1
    checks.append(("xmlValid", xml_valid, "XML parsed"))

    root_ok = local_name(root.tag) == "svg"
    checks.append(("rootSvg", root_ok, "root element is svg"))
    viewbox = parse_viewbox(root.attrib.get("viewBox"))
    checks.append(("viewBoxValid", viewbox is not None, "valid viewBox"))
    if viewbox is None:
        viewbox = (0, 0, 0, 0)

    lines = text.splitlines()
    line_count = len(lines)
    non_empty_non_comment = sum(1 for line in lines if line.strip() and not line.strip().startswith("<!--"))
    checks.append(("minimumLineCountPassed", line_count >= 3000, f"line count {line_count} >= 3000"))
    checks.append(("minimumEffectiveLineCountPassed", non_empty_non_comment >= 2800, f"effective lines {non_empty_non_comment} >= 2800"))

    all_elements = list(root.iter())
    type_counts = Counter(local_name(element.tag) for element in all_elements)
    element_count = len(all_elements)
    visible_count = sum(1 for element in all_elements if local_name(element.tag) in VISIBLE_TAGS)
    checks.append(("elementComplexityPassed", element_count >= 3000 and visible_count >= 2800, f"elements {element_count}, visible-shape elements {visible_count}"))

    by_id = {element.attrib.get("id"): element for element in all_elements if element.attrib.get("id")}
    missing_layers = [layer for layer in REQUIRED_LAYERS if layer not in by_id]
    checks.append(("requiredLayersPassed", not missing_layers, f"missing layers: {missing_layers or 'none'}"))
    empty_layers = []
    for layer in REQUIRED_LAYERS:
        element = by_id.get(layer)
        if element is not None and visible_descendant_count(element) == 0:
            empty_layers.append(layer)
    checks.append(("requiredLayersVisiblePassed", not empty_layers, f"empty visible layers: {empty_layers or 'none'}"))

    image_count = type_counts.get("image", 0)
    foreign_count = type_counts.get("foreignObject", 0)
    checks.append(("containsImageElement", image_count == 0, f"image elements: {image_count}"))
    checks.append(("containsForeignObject", foreign_count == 0, f"foreignObject elements: {foreign_count}"))
    checks.append(("containsBase64", "base64" not in text.lower(), "no base64 token"))
    checks.append(("containsDataImage", "data:image" not in text.lower(), "no data:image token"))
    checks.append(("containsExternalUrl", not has_external_url(text), "no external URL except SVG namespace"))
    checks.append(("containsRuntimeScript", type_counts.get("script", 0) == 0, f"script elements: {type_counts.get('script', 0)}"))

    zero_opacity_elements = [
        element
        for element in all_elements
        if is_effectively_zero(element.attrib.get("opacity"))
        or is_effectively_zero(element.attrib.get("fill-opacity"))
        or is_effectively_zero(element.attrib.get("stroke-opacity"))
        or element.attrib.get("display") == "none"
    ]
    checks.append(("zeroOpacityPassed", len(zero_opacity_elements) == 0, f"zero-opacity/display-none elements: {len(zero_opacity_elements)}"))

    outside = []
    for element in all_elements:
        tag = local_name(element.tag)
        if tag not in VISIBLE_TAGS:
            continue
        parent_def = False
        for ancestor in []:
            if ancestor in DEFINITION_TAGS:
                parent_def = True
        if parent_def:
            continue
        bbox = element_bbox(element)
        if bbox and not intersects(bbox, viewbox):
            outside.append((tag, bbox))
    checks.append(("canvasBoundsPassed", len(outside) <= 20, f"fully off-canvas visible elements: {len(outside)}"))

    ids = collect_ids(root)
    url_refs = collect_url_refs(text)
    missing_url_refs = sorted({ref for ref in url_refs if ref not in ids})
    checks.append(("referencesValid", not missing_url_refs, f"missing url refs: {missing_url_refs or 'none'}"))
    use_refs = collect_use_refs(root)
    missing_use_refs = sorted({ref for ref in use_refs if ref not in ids})
    checks.append(("useReferencesValid", not missing_use_refs, f"missing use refs: {missing_use_refs or 'none'}"))

    file_size = path.stat().st_size
    checks.append(("fileSizeReasonable", 120_000 <= file_size <= 8_000_000, f"file size {file_size} bytes"))

    failed = [name for name, passed, _message in checks if not passed]
    print(f"svg={path}")
    print(f"line_count={line_count}")
    print(f"non_empty_non_comment_line_count={non_empty_non_comment}")
    print(f"element_count={element_count}")
    print(f"visible_shape_element_count={visible_count}")
    print(f"file_size_bytes={file_size}")
    for name, count in sorted(type_counts.items()):
        print(f"element_type.{name}={count}")
    for name, passed, message in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status} {name}: {message}")
    if failed:
        print("validation_failed=" + ",".join(failed))
        return 1
    print("validation_passed=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
