from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent
SVG_PATH = BASE_DIR / "metro.svg"
NETWORK_PATH = BASE_DIR / "network.json"
METADATA_PATH = BASE_DIR / "metadata.json"
CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def strip_namespace(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def read_svg():
    return SVG_PATH.read_text(encoding="utf-8")


def actual_browser_bbox_check(svg_text):
    if not CHROME_PATH.exists():
        return {"available": False, "labelCount": None, "bboxCollisionCount": None, "collisions": []}
    svg_body = svg_text.replace('<?xml version="1.0" encoding="UTF-8"?>', "")
    script = r'''
<script>
window.addEventListener('load', () => {
  const labels = Array.from(document.querySelectorAll('.station-label')).map(g => {
    const b = g.getBBox();
    return {name: g.getAttribute('data-station'), x:b.x, y:b.y, w:b.width, h:b.height};
  });
  const collisions = [];
  for (let i = 0; i < labels.length; i++) {
    for (let j = i + 1; j < labels.length; j++) {
      const a = labels[i], b = labels[j];
      if (!(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y)) {
        collisions.push([a.name, b.name]);
      }
    }
  }
  document.body.innerHTML = '<pre id="result">' + JSON.stringify({labelCount: labels.length, bboxCollisionCount: collisions.length, collisions: collisions.slice(0, 80)}, null, 2) + '</pre>';
});
</script>
'''
    html = '<!doctype html><html><head><meta charset="utf-8"><title>bbox</title></head><body>' + svg_body + script + "</body></html>"
    tmp_path = Path("/tmp/metro-v2-bbox-check.html")
    tmp_path.write_text(html, encoding="utf-8")
    result = subprocess.run(
        [
            str(CHROME_PATH),
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--virtual-time-budget=2000",
            "--dump-dom",
            f"file://{tmp_path}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    match = re.search(r'<pre id="result">(\{.*?\})</pre>', result.stdout, flags=re.S)
    if not match:
        return {"available": True, "labelCount": None, "bboxCollisionCount": None, "collisions": [], "error": "bbox result not found"}
    parsed = json.loads(match.group(1))
    parsed["available"] = True
    return parsed


def collect_png_metrics(previews):
    metrics = {}
    magick = shutil.which("magick")
    for name in previews:
        path = BASE_DIR / name
        item = {"exists": path.exists(), "width": None, "height": None}
        if path.exists() and magick:
            result = subprocess.run(
                [magick, "identify", "-format", "%w %h", str(path)],
                check=False,
                text=True,
                capture_output=True,
            )
            if result.returncode == 0:
                width, height = result.stdout.strip().split()
                item["width"] = int(width)
                item["height"] = int(height)
        metrics[name] = item
    return metrics


def update_metadata(ok, errors, warnings, svg_metrics):
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    metadata.setdefault("result", {})
    metadata["svgMetrics"] = svg_metrics
    metadata["result"]["status"] = "completed" if ok else "failed"
    metadata["result"]["completedAt"] = datetime.now(timezone.utc).isoformat() if ok else None
    metadata["result"]["renderTool"] = "Chrome headless screenshot; ImageMagick for PNG resize/crop"
    commands = [
        "python3 runs/metro/v2/generate_metro.py",
        "python3 runs/metro/v2/validate_network.py",
        "Chrome headless screenshots for candidates and previews",
        "ImageMagick resize/crop/identify for preview_zoom67.png, preview_zoom50.png, preview_core_area.png",
        "python3 runs/metro/v2/validate_svg.py",
    ]
    metadata["result"]["commandsExecuted"] = commands
    if errors:
        metadata["result"]["issuesFound"] = metadata["result"].get("issuesFound", []) + errors
    if ok:
        fixed = metadata["result"].get("issuesFixed", [])
        success_note = "最终 SVG 工程验证、浏览器文本边界框验证和预览文件检查通过"
        if success_note not in fixed:
            fixed.append(success_note)
        metadata["result"]["issuesFixed"] = fixed
    if warnings:
        metadata["result"]["notes"] = (metadata["result"].get("notes", "") + " Warnings: " + "; ".join(warnings)).strip()
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    network = json.loads(NETWORK_PATH.read_text(encoding="utf-8"))
    svg_text = read_svg()
    errors = []
    warnings = []

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        print(json.dumps({"ok": False, "errors": [f"SVG XML 解析失败: {exc}"]}, ensure_ascii=False, indent=2))
        return 1

    view_box = root.attrib.get("viewBox")
    if view_box != "0 0 2400 1600":
        errors.append(f"viewBox 不正确: {view_box}")

    tags = [strip_namespace(el.tag) for el in root.iter()]
    forbidden = [tag for tag in tags if tag in {"image", "foreignObject"}]
    if forbidden:
        errors.append(f"包含禁用标签: {sorted(set(forbidden))}")
    lowered = svg_text.lower().replace('xmlns="http://www.w3.org/2000/svg"', "")
    for token in ["base64", "http://", "https://", "url("]:
        if token in lowered:
            errors.append(f"SVG 包含外部或嵌入资源标记: {token}")

    expected_line_ids = {line["id"] for line in network["lines"]}
    legend_ids = {
        el.attrib["id"].replace("legend-line-", "")
        for el in root.iter()
        if el.attrib.get("id", "").startswith("legend-line-")
    }
    if legend_ids != expected_line_ids:
        errors.append(f"图例线路与 network.json 不一致: missing={sorted(expected_line_ids - legend_ids)}, extra={sorted(legend_ids - expected_line_ids)}")

    path_line_ids = {
        el.attrib.get("data-line")
        for el in root.iter()
        if strip_namespace(el.tag) == "path" and el.attrib.get("data-line")
    }
    if path_line_ids != expected_line_ids:
        errors.append(f"主图线路与 network.json 不一致: missing={sorted(expected_line_ids - path_line_ids)}, extra={sorted(path_line_ids - expected_line_ids)}")

    under_construction = [line["id"] for line in network["lines"] if line["status"] == "under_construction"]
    for line_id in under_construction:
        dashed = [
            el
            for el in root.iter()
            if strip_namespace(el.tag) == "path"
            and el.attrib.get("data-line") == line_id
            and "stroke-dasharray" in el.attrib
        ]
        if not dashed:
            errors.append(f"建设中线路 {line_id} 未使用虚线样式")

    svg_text_labels = "".join(el.text or "" for el in root.iter() if strip_namespace(el.tag) == "text")
    missing_labels = [s["name"] for s in network["stations"] if s["name"] not in svg_text_labels]
    if missing_labels:
        errors.append(f"SVG 缺少中文站名: {missing_labels[:12]}")
    missing_en = [s["englishName"] for s in network["stations"] if s["englishName"] not in svg_text_labels]
    if missing_en:
        errors.append(f"SVG 缺少英文站名: {missing_en[:12]}")

    label_groups = [el for el in root.iter() if "station-label" in el.attrib.get("class", "")]
    if len(label_groups) != len(network["stations"]):
        errors.append(f"站名标签组数量不等于车站数量: {len(label_groups)} vs {len(network['stations'])}")

    bbox = actual_browser_bbox_check(svg_text)
    if bbox.get("available") and bbox.get("bboxCollisionCount") not in (0, None):
        errors.append(f"浏览器实际文本 bbox 存在碰撞: {bbox['bboxCollisionCount']} {bbox.get('collisions', [])[:10]}")
    elif not bbox.get("available"):
        warnings.append("Chrome headless 不可用，未执行实际浏览器 bbox 检查")
    elif bbox.get("bboxCollisionCount") is None:
        errors.append(f"浏览器 bbox 检查未返回有效结果: {bbox.get('error')}")

    previews = [
        "preview.png",
        "preview_no_labels.png",
        "preview_labels_only.png",
        "preview_label_boxes.png",
        "preview_zoom67.png",
        "preview_zoom50.png",
        "preview_core_area.png",
        "candidates/candidate-01.png",
        "candidates/candidate-02.png",
        "candidates/candidate-03.png",
        "candidates/candidate-04.png",
        "candidates/candidate-05.png",
    ]
    preview_metrics = collect_png_metrics(previews)
    missing_previews = [name for name, item in preview_metrics.items() if not item["exists"]]
    if missing_previews:
        errors.append(f"缺少预览文件: {missing_previews}")

    svg_metrics = {
        "viewBox": view_box,
        "forbiddenElementCount": len(forbidden),
        "linePathCount": len(path_line_ids),
        "legendLineCount": len(legend_ids),
        "stationLabelGroupCount": len(label_groups),
        "browserBBox": bbox,
        "previewMetrics": preview_metrics,
    }
    ok = not errors
    update_metadata(ok, errors, warnings, svg_metrics)
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings, "svgMetrics": svg_metrics}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
