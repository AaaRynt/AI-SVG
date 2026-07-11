#!/usr/bin/env python3
"""对本轮富士山 SVG 做严格、可重复的静态验证。

只使用 Python 标准库。验证失败时退出码为 1，全部通过时退出码为 0。
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


SCRIPT_DIR = Path(__file__).resolve().parent
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

# 这里采用任务“行数与复杂度要求”中的最终硬门槛，而不是验证章节中的较低兜底值。
MIN_TOTAL_LINES = 4000
MIN_CONTENT_LINES = 3200
MIN_TOTAL_ELEMENTS = 3000
MIN_RENDERED_GRAPHICS = 2500
MIN_FILE_BYTES = 128 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024

REQUIRED_LAYERS = (
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
)

GRAPHIC_TAGS = frozenset(
    {
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "use",
        "text",
    }
)

# 这些容器内的图元是定义、裁剪或滤镜输入，不能当作画面中的可见复杂度。
NON_RENDERED_CONTAINERS = frozenset(
    {
        "defs",
        "clipPath",
        "mask",
        "symbol",
        "pattern",
        "marker",
        "linearGradient",
        "radialGradient",
        "filter",
    }
)

# 对应 AGENTS.md 中要求放入 defs 的统一颜色与光照系统。名称匹配刻意允许常见变体。
SEMANTIC_GRADIENT_PATTERNS = {
    "天空主渐变": re.compile(r"sky|天空", re.I),
    "地平线暖光": re.compile(r"horizon|地平", re.I),
    "太阳": re.compile(r"sun|solar|太阳", re.I),
    "山体受光": re.compile(
        r"(?=.*(?:mount|fuji|山体))(?=.*(?:light|lit|warm|sunny|受光|暖))", re.I
    ),
    "山体冷阴影": re.compile(
        r"(?=.*(?:mount|fuji|山体))(?=.*(?:shadow|shade|cool|cold|阴影|冷))", re.I
    ),
    "雪面暖光": re.compile(
        r"(?=.*(?:snow|雪))(?=.*(?:light|warm|gold|highlight|暖|高光))", re.I
    ),
    "雪面冷阴影": re.compile(
        r"(?=.*(?:snow|雪))(?=.*(?:shadow|shade|cool|cold|blue|阴影|冷))", re.I
    ),
    "云顶高光": re.compile(
        r"(?=.*(?:cloud|云))(?=.*(?:top|light|warm|highlight|顶|高光|暖))", re.I
    ),
    "云底阴影": re.compile(
        r"(?=.*(?:cloud|云))(?=.*(?:bottom|shadow|shade|cool|底|阴影|冷))", re.I
    ),
    "湖面基础": re.compile(
        r"(?=.*(?:lake|water|湖|水面))(?=.*(?:base|surface|main|基础|主))", re.I
    ),
    "湖面反射": re.compile(r"reflect|reflection|反射|倒影", re.I),
    "城市空气透视": re.compile(
        r"(?=.*(?:city|urban|城市))(?=.*(?:atmos|aerial|haze|mist|远景|雾|空气))", re.I
    ),
    "前景树林": re.compile(r"forest|tree|wood|树林|树", re.I),
}

NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:px)?$")
POINT_NUMBER_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
URL_FUNCTION_RE = re.compile(r"url\(\s*([^)]*?)\s*\)", re.I)
XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class RenderedGraphic:
    element: ET.Element
    has_transform: bool


def local_name(name: str) -> str:
    """移除 ElementTree 展开的 XML 命名空间。"""

    return name.rsplit("}", 1)[-1]


def namespace_of(name: str) -> str | None:
    if name.startswith("{") and "}" in name:
        return name[1:].split("}", 1)[0]
    return None


def add_check(checks: list[Check], name: str, passed: bool, detail: str) -> None:
    checks.append(Check(name=name, passed=bool(passed), detail=detail))


def parse_style(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        key, item = declaration.split(":", 1)
        result[key.strip().lower()] = item.strip().lower()
    return result


def zero_number(value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.strip().lower()
    if cleaned.endswith("%"):
        try:
            return math.isclose(float(cleaned[:-1]), 0.0, abs_tol=1e-12)
        except ValueError:
            return False
    try:
        return math.isclose(float(cleaned), 0.0, abs_tol=1e-12)
    except ValueError:
        return False


def hidden_here(element: ET.Element) -> bool:
    style = parse_style(element.attrib.get("style", ""))
    display = element.attrib.get("display", style.get("display", "")).strip().lower()
    visibility = element.attrib.get("visibility", style.get("visibility", "")).strip().lower()
    opacity = element.attrib.get("opacity", style.get("opacity"))
    return display == "none" or visibility in {"hidden", "collapse"} or zero_number(opacity)


def has_basic_geometry(element: ET.Element) -> bool:
    tag = local_name(element.tag)
    if tag == "path":
        return bool(element.attrib.get("d", "").strip())
    if tag in {"polyline", "polygon"}:
        return len(POINT_NUMBER_RE.findall(element.attrib.get("points", ""))) >= 4
    if tag == "use":
        return any(local_name(key) == "href" and value.strip() for key, value in element.attrib.items())
    if tag == "text":
        return bool("".join(element.itertext()).strip())
    if tag == "rect":
        return positive_length(element.attrib.get("width")) and positive_length(
            element.attrib.get("height")
        )
    if tag == "circle":
        return positive_length(element.attrib.get("r"))
    if tag == "ellipse":
        return positive_length(element.attrib.get("rx")) and positive_length(
            element.attrib.get("ry")
        )
    if tag == "line":
        x1 = parse_number(element.attrib.get("x1", "0"))
        y1 = parse_number(element.attrib.get("y1", "0"))
        x2 = parse_number(element.attrib.get("x2", "0"))
        y2 = parse_number(element.attrib.get("y2", "0"))
        if None in {x1, y1, x2, y2}:
            return True
        return not (math.isclose(x1, x2) and math.isclose(y1, y2))
    return True


def collect_rendered_graphics(root: ET.Element) -> list[RenderedGraphic]:
    rendered: list[RenderedGraphic] = []

    def walk(
        element: ET.Element,
        ancestor_hidden: bool,
        in_non_rendered: bool,
        ancestor_transform: bool,
    ) -> None:
        tag = local_name(element.tag)
        current_non_rendered = in_non_rendered or tag in NON_RENDERED_CONTAINERS
        current_hidden = ancestor_hidden or hidden_here(element)
        current_transform = ancestor_transform or bool(element.attrib.get("transform", "").strip())
        if (
            tag in GRAPHIC_TAGS
            and not current_non_rendered
            and not current_hidden
            and has_basic_geometry(element)
        ):
            rendered.append(RenderedGraphic(element, current_transform))
        for child in element:
            walk(child, current_hidden, current_non_rendered, current_transform)

    walk(root, False, False, False)
    return rendered


def preserve_comment_newlines(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def count_content_lines(text: str) -> int:
    without_comments = XML_COMMENT_RE.sub(preserve_comment_newlines, text)
    return sum(1 for line in without_comments.splitlines() if line.strip())


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not NUMBER_RE.fullmatch(cleaned):
        return None
    if cleaned.lower().endswith("px"):
        cleaned = cleaned[:-2]
    try:
        result = float(cleaned)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def positive_length(value: str | None) -> bool:
    parsed = parse_number(value)
    # 百分比等相对单位无法在静态检查中安全判断，交给浏览器解析。
    return True if value and value.strip().endswith("%") else parsed is not None and parsed > 0


def parse_view_box(root: ET.Element) -> tuple[float, float, float, float] | None:
    raw = root.attrib.get("viewBox", "")
    parts = [part for part in re.split(r"[\s,]+", raw.strip()) if part]
    if len(parts) != 4:
        return None
    try:
        values = tuple(float(part) for part in parts)
    except ValueError:
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    x, y, width, height = values
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def get_float_attrs(element: ET.Element, names: tuple[str, ...]) -> tuple[float, ...] | None:
    values: list[float] = []
    for name in names:
        value = parse_number(element.attrib.get(name))
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def estimated_bbox(element: ET.Element) -> tuple[float, float, float, float] | None:
    """保守估计无需 path 解析的基础图元包围盒。"""

    tag = local_name(element.tag)
    if tag == "rect":
        values = get_float_attrs(element, ("x", "y", "width", "height"))
        if values is None:
            return None
        x, y, width, height = values
        return x, y, x + width, y + height
    if tag == "circle":
        values = get_float_attrs(element, ("cx", "cy", "r"))
        if values is None:
            return None
        cx, cy, radius = values
        return cx - radius, cy - radius, cx + radius, cy + radius
    if tag == "ellipse":
        values = get_float_attrs(element, ("cx", "cy", "rx", "ry"))
        if values is None:
            return None
        cx, cy, rx, ry = values
        return cx - rx, cy - ry, cx + rx, cy + ry
    if tag == "line":
        values = get_float_attrs(element, ("x1", "y1", "x2", "y2"))
        if values is None:
            return None
        x1, y1, x2, y2 = values
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    if tag in {"polygon", "polyline"}:
        numbers = [float(item) for item in POINT_NUMBER_RE.findall(element.attrib.get("points", ""))]
        if len(numbers) < 4 or len(numbers) % 2:
            return None
        xs = numbers[0::2]
        ys = numbers[1::2]
        return min(xs), min(ys), max(xs), max(ys)
    if tag in {"use", "text"}:
        x = parse_number(element.attrib.get("x", "0"))
        y = parse_number(element.attrib.get("y", "0"))
        if x is not None and y is not None:
            return x, y, x, y
    return None


def obvious_outside_count(
    rendered: list[RenderedGraphic], view_box: tuple[float, float, float, float]
) -> tuple[int, list[str]]:
    x, y, width, height = view_box
    # 允许图元为了柔和裁切伸出一整幅画布；只有更远且整体在外的对象才视为可疑。
    far_left = x - width
    far_right = x + 2 * width
    far_top = y - height
    far_bottom = y + 2 * height
    count = 0
    samples: list[str] = []
    for item in rendered:
        if item.has_transform:
            continue
        bbox = estimated_bbox(item.element)
        if bbox is None:
            continue
        x1, y1, x2, y2 = bbox
        outside = x2 < far_left or x1 > far_right or y2 < far_top or y1 > far_bottom
        if outside:
            count += 1
            if len(samples) < 5:
                samples.append(
                    f"{local_name(item.element.tag)}#{item.element.attrib.get('id', '-')}"
                )
    return count, samples


def invalid_geometry_elements(root: ET.Element) -> list[str]:
    invalid: list[str] = []
    for element in root.iter():
        tag = local_name(element.tag)
        bad = False
        if tag == "rect":
            bad = not positive_length(element.attrib.get("width")) or not positive_length(
                element.attrib.get("height")
            )
        elif tag == "circle":
            bad = not positive_length(element.attrib.get("r"))
        elif tag == "ellipse":
            bad = not positive_length(element.attrib.get("rx")) or not positive_length(
                element.attrib.get("ry")
            )
        if bad:
            invalid.append(f"{tag}#{element.attrib.get('id', '-')}")
    return invalid


def resolve_target(value: str | None) -> Path:
    if value is None:
        return SCRIPT_DIR / "fuji.svg"
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or candidate.exists():
        return candidate.resolve()
    return (SCRIPT_DIR / candidate).resolve()


def print_results(checks: list[Check], type_counts: Counter[str] | None = None) -> None:
    for index, check in enumerate(checks, start=1):
        marker = "通过" if check.passed else "失败"
        print(f"[{marker}] {index:02d}. {check.name}: {check.detail}")
    if type_counts is not None:
        print("\nSVG 元素类型统计：")
        for name, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {name}: {count}")
    passed = sum(check.passed for check in checks)
    failed = len(checks) - passed
    print(f"\n验证汇总：{passed} 项通过，{failed} 项失败，共 {len(checks)} 项。")


def validate(target: Path) -> int:
    checks: list[Check] = []
    add_check(checks, "fuji.svg 存在", target.is_file(), str(target))
    if not target.is_file():
        print_results(checks)
        return 1

    in_scope = target.resolve().parent == SCRIPT_DIR
    add_check(checks, "文件位于本轮目录", in_scope, str(target.resolve().parent))

    raw = target.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
        utf8_ok = True
        utf8_detail = "UTF-8 严格解码成功"
    except UnicodeDecodeError as exc:
        text = ""
        utf8_ok = False
        utf8_detail = str(exc)
    add_check(checks, "文件为有效 UTF-8", utf8_ok, utf8_detail)
    if not utf8_ok:
        print_results(checks)
        return 1

    declaration = re.match(r"\s*<\?xml\s+[^>]*encoding=[\"']([^\"']+)[\"']", text, re.I)
    declared_encoding = declaration.group(1).lower().replace("_", "-") if declaration else None
    encoding_ok = declared_encoding in {None, "utf-8", "utf8"}
    add_check(
        checks,
        "XML 编码声明一致",
        encoding_ok,
        f"encoding={declared_encoding or '未声明（允许）'}",
    )

    try:
        root = ET.fromstring(text)
        parse_ok = True
        parse_detail = "ElementTree 解析成功"
    except ET.ParseError as exc:
        root = None
        parse_ok = False
        parse_detail = str(exc)
    add_check(checks, "XML 可以解析", parse_ok, parse_detail)
    add_check(checks, "所有 XML 标签正确闭合", parse_ok, parse_detail)
    if root is None:
        print_results(checks)
        return 1

    root_is_svg = local_name(root.tag) == "svg"
    add_check(checks, "根元素是 svg", root_is_svg, f"根元素={local_name(root.tag)}")
    root_namespace = namespace_of(root.tag)
    add_check(
        checks,
        "使用标准 SVG 命名空间",
        root_namespace == SVG_NAMESPACE,
        f"namespace={root_namespace!r}",
    )

    view_box = parse_view_box(root)
    add_check(
        checks,
        "存在有效 viewBox",
        view_box is not None,
        root.attrib.get("viewBox", "缺失"),
    )
    ratio_ok = False
    ratio_detail = "无法计算"
    if view_box is not None:
        ratio = view_box[2] / view_box[3]
        ratio_ok = 1.55 <= ratio <= 1.65
        ratio_detail = f"比例={ratio:.4f}，期望约 16:10"
    add_check(checks, "画布比例约为 16:10", ratio_ok, ratio_detail)

    total_lines = len(text.splitlines())
    content_lines = count_content_lines(text)
    add_check(
        checks,
        "物理行数达到最终门槛",
        total_lines >= MIN_TOTAL_LINES,
        f"{total_lines} 行，要求 >= {MIN_TOTAL_LINES}",
    )
    add_check(
        checks,
        "非空非纯注释行达到最终门槛",
        content_lines >= MIN_CONTENT_LINES,
        f"{content_lines} 行，要求 >= {MIN_CONTENT_LINES}",
    )

    type_counts: Counter[str] = Counter(local_name(element.tag) for element in root.iter())
    total_elements = sum(type_counts.values())
    add_check(
        checks,
        "SVG 元素总数达到合理复杂度",
        total_elements >= MIN_TOTAL_ELEMENTS,
        f"{total_elements} 个，要求 >= {MIN_TOTAL_ELEMENTS}",
    )

    rendered = collect_rendered_graphics(root)
    add_check(
        checks,
        "可渲染图形元素达到合理复杂度",
        len(rendered) >= MIN_RENDERED_GRAPHICS,
        f"{len(rendered)} 个，要求 >= {MIN_RENDERED_GRAPHICS}",
    )
    visible_types = Counter(local_name(item.element.tag) for item in rendered)
    add_check(
        checks,
        "可见图元类型具有多样性",
        len(visible_types) >= 6,
        f"{len(visible_types)} 类：{', '.join(sorted(visible_types)) or '无'}",
    )

    ids = [element.attrib["id"] for element in root.iter() if "id" in element.attrib]
    id_counts = Counter(ids)
    duplicate_ids = sorted(name for name, count in id_counts.items() if count > 1)
    add_check(
        checks,
        "所有 id 唯一",
        not duplicate_ids,
        "无重复" if not duplicate_ids else f"重复：{', '.join(duplicate_ids[:10])}",
    )
    id_set = set(ids)

    missing_layers = [name for name in REQUIRED_LAYERS if name not in id_set]
    add_check(
        checks,
        "19 个关键语义图层全部存在",
        not missing_layers,
        "全部存在" if not missing_layers else f"缺失：{', '.join(missing_layers)}",
    )

    id_to_element = {
        element.attrib["id"]: element for element in root.iter() if "id" in element.attrib
    }
    empty_layers: list[str] = []
    for layer_name in REQUIRED_LAYERS:
        layer = id_to_element.get(layer_name)
        if layer is not None and not collect_rendered_graphics(layer):
            empty_layers.append(layer_name)
    add_check(
        checks,
        "每个关键图层都包含可见图元",
        not missing_layers and not empty_layers,
        "全部含可见图元" if not empty_layers else f"空图层：{', '.join(empty_layers)}",
    )

    image_elements = [element for element in root.iter() if local_name(element.tag).lower() == "image"]
    add_check(checks, "不存在 image 元素", not image_elements, f"数量={len(image_elements)}")

    foreign_objects = [
        element for element in root.iter() if local_name(element.tag).lower() == "foreignobject"
    ]
    add_check(
        checks,
        "不存在 foreignObject 元素",
        not foreign_objects,
        f"数量={len(foreign_objects)}",
    )

    add_check(
        checks,
        "不存在 Base64 内容",
        re.search(r"base64", text, re.I) is None,
        "未发现" if re.search(r"base64", text, re.I) is None else "发现 base64 字样",
    )
    add_check(
        checks,
        "不存在 data:image 内容",
        re.search(r"data\s*:\s*image", text, re.I) is None,
        "未发现" if re.search(r"data\s*:\s*image", text, re.I) is None else "发现 data:image",
    )

    raster_matches = sorted(
        set(match.group(0).lower() for match in re.finditer(r"\.(?:png|jpe?g|webp|gif|avif|bmp|tiff?)\b", text, re.I))
    )
    add_check(
        checks,
        "不存在位图文件引用",
        not raster_matches,
        "未发现" if not raster_matches else f"发现：{', '.join(raster_matches)}",
    )

    forbidden_xml = re.findall(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I)
    add_check(
        checks,
        "不存在 DTD 或外部实体",
        not forbidden_xml,
        f"数量={len(forbidden_xml)}",
    )

    script_elements = [element for element in root.iter() if local_name(element.tag).lower() == "script"]
    event_attributes: list[str] = []
    javascript_values: list[str] = []
    for element in root.iter():
        for key, value in element.attrib.items():
            attr_name = local_name(key).lower()
            if attr_name.startswith("on") and len(attr_name) > 2:
                event_attributes.append(attr_name)
            if re.search(r"javascript\s*:", value, re.I):
                javascript_values.append(value[:80])
    scripts_ok = not script_elements and not event_attributes and not javascript_values
    add_check(
        checks,
        "不存在脚本或事件处理器",
        scripts_ok,
        f"script={len(script_elements)}, 事件属性={len(event_attributes)}, javascript URI={len(javascript_values)}",
    )

    external_references: list[str] = []
    local_url_references: list[str] = []
    for match in URL_FUNCTION_RE.finditer(text):
        value = match.group(1).strip().strip("\"'")
        if value.startswith("#") and len(value) > 1:
            local_url_references.append(value[1:])
        else:
            external_references.append(value or "空 url()")
    for element in root.iter():
        for key, value in element.attrib.items():
            attr_name = local_name(key).lower()
            stripped = value.strip()
            if attr_name in {"href", "src"} and stripped and not stripped.startswith("#"):
                external_references.append(stripped)
            elif re.search(r"(?:https?|ftp|file)\s*:|^//", stripped, re.I):
                external_references.append(stripped)
    for element in root.iter():
        if local_name(element.tag).lower() == "style":
            css = "".join(element.itertext())
            if re.search(r"@import\b|(?:https?|ftp|file)\s*:|//", css, re.I):
                external_references.append("style 中的外部引用")
    add_check(
        checks,
        "不存在外部 URL 或资源",
        not external_references,
        "未发现" if not external_references else f"发现：{'; '.join(external_references[:8])}",
    )

    missing_url_ids = sorted(set(local_url_references) - id_set)
    add_check(
        checks,
        "所有 url(#...) 引用均有定义",
        not missing_url_ids,
        "全部可解析" if not missing_url_ids else f"缺失：{', '.join(missing_url_ids[:15])}",
    )

    use_count = 0
    invalid_uses: list[str] = []
    for element in root.iter():
        if local_name(element.tag) != "use":
            continue
        use_count += 1
        href = next(
            (value.strip() for key, value in element.attrib.items() if local_name(key) == "href"),
            "",
        )
        if not href.startswith("#") or len(href) == 1 or href[1:] not in id_set:
            invalid_uses.append(href or "缺少 href")
    add_check(
        checks,
        "所有 use 引用均有对应元素",
        not invalid_uses,
        f"use={use_count}，全部可解析" if not invalid_uses else f"无效：{', '.join(invalid_uses[:15])}",
    )

    direct_hidden: list[str] = []
    in_definition: set[int] = set()

    def mark_definition_tree(element: ET.Element, inside: bool = False) -> None:
        current = inside or local_name(element.tag) in NON_RENDERED_CONTAINERS
        if current:
            in_definition.add(id(element))
        for child in element:
            mark_definition_tree(child, current)

    mark_definition_tree(root)
    for element in root.iter():
        if id(element) not in in_definition and hidden_here(element):
            direct_hidden.append(f"{local_name(element.tag)}#{element.attrib.get('id', '-')}")
    css_hidden = re.findall(
        r"(?:^|[;{])\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|opacity\s*:\s*0(?:\.0*)?\s*(?:[;}]))",
        text,
        re.I | re.M,
    )
    hidden_ok = not direct_hidden and not css_hidden
    add_check(
        checks,
        "不存在 opacity=0 或 display:none 等隐藏凑数元素",
        hidden_ok,
        "未发现" if hidden_ok else f"直接隐藏={len(direct_hidden)}，CSS 隐藏规则={len(css_hidden)}；示例={', '.join(direct_hidden[:5])}",
    )

    if view_box is not None:
        outside_count, outside_samples = obvious_outside_count(rendered, view_box)
        outside_limit = max(8, math.ceil(len(rendered) * 0.005))
        outside_ok = outside_count <= outside_limit
        outside_detail = (
            f"明显远离画布={outside_count}，允许上限={outside_limit}"
            + (f"；示例={', '.join(outside_samples)}" if outside_samples else "")
        )
    else:
        outside_ok = False
        outside_detail = "viewBox 无效，无法判断"
    add_check(checks, "不存在大批明显位于画布外的凑数图元", outside_ok, outside_detail)

    invalid_geometry = invalid_geometry_elements(root)
    add_check(
        checks,
        "基础图元尺寸均为正值",
        not invalid_geometry,
        "全部有效" if not invalid_geometry else f"无效：{', '.join(invalid_geometry[:10])}",
    )

    file_size = len(raw)
    size_ok = MIN_FILE_BYTES <= file_size <= MAX_FILE_BYTES
    add_check(
        checks,
        "文件大小处于合理范围",
        size_ok,
        f"{file_size} 字节，范围 {MIN_FILE_BYTES}–{MAX_FILE_BYTES}",
    )

    gradients = [
        element
        for element in root.iter()
        if local_name(element.tag) in {"linearGradient", "radialGradient"}
    ]
    gradient_ids = [element.attrib.get("id", "") for element in gradients]
    add_check(
        checks,
        "defs 中具有足够的复用渐变",
        len(gradients) >= len(SEMANTIC_GRADIENT_PATTERNS),
        f"渐变={len(gradients)}，要求 >= {len(SEMANTIC_GRADIENT_PATTERNS)}",
    )
    missing_gradient_roles = [
        role
        for role, pattern in SEMANTIC_GRADIENT_PATTERNS.items()
        if not any(pattern.search(gradient_id) for gradient_id in gradient_ids)
    ]
    add_check(
        checks,
        "13 类语义光照与颜色渐变齐全",
        not missing_gradient_roles,
        "全部匹配" if not missing_gradient_roles else f"缺失：{', '.join(missing_gradient_roles)}",
    )

    referenced_ids = set(local_url_references)
    for element in root.iter():
        for key, value in element.attrib.items():
            if local_name(key) == "href" and value.strip().startswith("#"):
                referenced_ids.add(value.strip()[1:])
    used_gradient_ids = {gradient_id for gradient_id in gradient_ids if gradient_id in referenced_ids}
    add_check(
        checks,
        "渐变定义得到实际复用",
        len(used_gradient_ids) >= 10,
        f"已引用渐变={len(used_gradient_ids)}，要求 >= 10",
    )

    graphic_tag_pattern = re.compile(
        r"<(?:[A-Za-z_][\w.-]*:)?(?:path|rect|circle|ellipse|line|polyline|polygon|use|text)\b"
    )
    packed_lines = [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if len(graphic_tag_pattern.findall(line)) > 1
    ]
    add_check(
        checks,
        "主要 SVG 图元分别独占物理行",
        not packed_lines,
        "未发现一行多图元" if not packed_lines else f"问题行：{', '.join(map(str, packed_lines[:15]))}",
    )

    add_check(
        checks,
        "已生成元素类型数量统计",
        bool(type_counts),
        f"共 {len(type_counts)} 种元素类型",
    )

    print_results(checks, type_counts)
    return 0 if all(check.passed for check in checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="严格验证本轮静态富士山 SVG")
    parser.add_argument(
        "svg",
        nargs="?",
        help="待验证文件；默认使用脚本同目录下的 fuji.svg",
    )
    args = parser.parse_args()
    return validate(resolve_target(args.svg))


if __name__ == "__main__":
    sys.exit(main())
