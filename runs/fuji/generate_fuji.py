#!/usr/bin/env python3
"""Programmatically generate a complex, static Mount Fuji SVG."""

from __future__ import annotations

import html
import math
import os
import random
import re
from collections import Counter


WIDTH = 1600
HEIGHT = 1000
WATERLINE = 735
SEED = 20260629
OUTPUT = "fuji.svg"

FUJI_OUTLINE = (
    "M 210 640 "
    "C 295 617 365 570 436 505 "
    "C 510 437 586 333 715 219 "
    "C 756 181 793 174 822 193 "
    "C 855 216 888 267 936 331 "
    "C 1042 469 1158 581 1386 643 "
    "C 1128 633 934 625 749 629 "
    "C 564 633 392 637 210 640 Z"
)


def fmt(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    number = float(value)
    if abs(number) < 0.005:
        number = 0
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def attrs_to_text(attrs: dict[str, object]) -> str:
    parts: list[str] = []
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, float):
            value = fmt(value)
        escaped = html.escape(str(value), quote=True)
        parts.append(f'{key}="{escaped}"')
    return (" " + " ".join(parts)) if parts else ""


class SvgWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def raw(self, line: str) -> None:
        self.lines.append(line)

    def comment(self, text: str) -> None:
        self.lines.append(f"<!-- {text} -->")

    def open(self, tag: str, attrs: dict[str, object] | None = None) -> None:
        self.lines.append(f"<{tag}{attrs_to_text(attrs or {})}>")

    def close(self, tag: str) -> None:
        self.lines.append(f"</{tag}>")

    def elem(self, tag: str, attrs: dict[str, object] | None = None) -> None:
        self.lines.append(f"<{tag}{attrs_to_text(attrs or {})} />")


def d_line(points: list[tuple[float, float]], close: bool = False) -> str:
    if not points:
        return ""
    head = f"M {fmt(points[0][0])} {fmt(points[0][1])}"
    rest = " ".join(f"L {fmt(x)} {fmt(y)}" for x, y in points[1:])
    suffix = " Z" if close else ""
    return f"{head} {rest}{suffix}".strip()


def cubic_path(points: list[tuple[float, float]], rng: random.Random, wiggle: float = 20) -> str:
    if len(points) < 2:
        return ""
    d = [f"M {fmt(points[0][0])} {fmt(points[0][1])}"]
    for a, b in zip(points, points[1:]):
        x1, y1 = a
        x2, y2 = b
        c1x = x1 + (x2 - x1) * 0.35 + rng.uniform(-wiggle, wiggle)
        c1y = y1 + (y2 - y1) * 0.35 + rng.uniform(-wiggle, wiggle)
        c2x = x1 + (x2 - x1) * 0.68 + rng.uniform(-wiggle, wiggle)
        c2y = y1 + (y2 - y1) * 0.68 + rng.uniform(-wiggle, wiggle)
        d.append(f"C {fmt(c1x)} {fmt(c1y)} {fmt(c2x)} {fmt(c2y)} {fmt(x2)} {fmt(y2)}")
    return " ".join(d)


def cloud_path(cx: float, cy: float, w: float, h: float, lobes: int, rng: random.Random) -> str:
    left = clamp(cx - w / 2, -40, WIDTH + 40)
    right = clamp(cx + w / 2, -40, WIDTH + 40)
    base_y = cy + h * rng.uniform(0.05, 0.18)
    d = [f"M {fmt(left)} {fmt(base_y)}"]
    last_x = left
    last_y = base_y
    for i in range(lobes):
        nx = left + (right - left) * (i + 1) / lobes
        lift = h * rng.uniform(0.22, 0.72)
        ny = cy + h * rng.uniform(-0.2, 0.15)
        c1x = last_x + (nx - last_x) * rng.uniform(0.25, 0.45)
        c2x = last_x + (nx - last_x) * rng.uniform(0.58, 0.82)
        c1y = last_y - lift * rng.uniform(0.35, 0.75)
        c2y = cy - lift
        d.append(f"C {fmt(c1x)} {fmt(c1y)} {fmt(c2x)} {fmt(c2y)} {fmt(nx)} {fmt(ny)}")
        last_x = nx
        last_y = ny
    bottom_y = cy + h * rng.uniform(0.28, 0.55)
    d.append(
        f"C {fmt(right - w * 0.1)} {fmt(bottom_y + h * 0.12)} "
        f"{fmt(left + w * 0.16)} {fmt(bottom_y + h * 0.18)} {fmt(left)} {fmt(base_y)} Z"
    )
    return " ".join(d)


def low_cloud_path(cx: float, cy: float, w: float, h: float, rng: random.Random) -> str:
    lobes = rng.randint(5, 9)
    return cloud_path(cx, cy, w, h, lobes, rng)


def snow_patch_path(cx: float, cy: float, w: float, h: float, rng: random.Random, lean: float) -> str:
    left = cx - w / 2
    right = cx + w / 2
    top = cy - h / 2
    bottom = cy + h / 2
    p1 = (left + rng.uniform(-w * 0.08, w * 0.1), cy + rng.uniform(-h * 0.2, h * 0.1))
    p2 = (cx - w * 0.18 + lean * h, top + rng.uniform(-h * 0.08, h * 0.16))
    p3 = (right + rng.uniform(-w * 0.05, w * 0.1), cy + rng.uniform(-h * 0.18, h * 0.08))
    p4 = (cx + w * 0.2 + lean * h * 0.6, bottom + rng.uniform(-h * 0.1, h * 0.18))
    p5 = (left + w * 0.22 + lean * h * 0.3, bottom + rng.uniform(-h * 0.05, h * 0.2))
    return (
        f"M {fmt(p1[0])} {fmt(p1[1])} "
        f"C {fmt(p1[0] + w * 0.2)} {fmt(top)} {fmt(p2[0] - w * 0.08)} {fmt(p2[1])} {fmt(p2[0])} {fmt(p2[1])} "
        f"C {fmt(cx + w * 0.12)} {fmt(top - h * 0.1)} {fmt(p3[0] - w * 0.16)} {fmt(p3[1])} {fmt(p3[0])} {fmt(p3[1])} "
        f"C {fmt(right - w * 0.08)} {fmt(cy + h * 0.2)} {fmt(p4[0])} {fmt(p4[1])} {fmt(p4[0])} {fmt(p4[1])} "
        f"C {fmt(cx)} {fmt(bottom + h * 0.1)} {fmt(p5[0])} {fmt(p5[1])} {fmt(p5[0])} {fmt(p5[1])} "
        f"C {fmt(left)} {fmt(bottom - h * 0.05)} {fmt(p1[0] - w * 0.08)} {fmt(cy)} {fmt(p1[0])} {fmt(p1[1])} Z"
    )


def tapered_stroke_path(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: float,
    rng: random.Random,
) -> str:
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy) or 1
    nx = -dy / length * width
    ny = dx / length * width
    midx = (x1 + x2) / 2 + rng.uniform(-width * 3, width * 3)
    midy = (y1 + y2) / 2 + rng.uniform(-width * 4, width * 4)
    return (
        f"M {fmt(x1 + nx)} {fmt(y1 + ny)} "
        f"C {fmt(midx + nx)} {fmt(midy + ny)} {fmt(midx + nx * 0.4)} {fmt(midy + ny * 0.4)} {fmt(x2 + nx * 0.25)} {fmt(y2 + ny * 0.25)} "
        f"L {fmt(x2 - nx * 0.25)} {fmt(y2 - ny * 0.25)} "
        f"C {fmt(midx - nx * 0.4)} {fmt(midy - ny * 0.4)} {fmt(midx - nx)} {fmt(midy - ny)} {fmt(x1 - nx)} {fmt(y1 - ny)} Z"
    )


def mountain_span_at_y(y: float) -> tuple[float, float]:
    t = clamp((y - 190) / (645 - 190), 0, 1)
    left = 805 - 600 * (t ** 0.92) - 22 * math.sin(t * math.pi * 1.8)
    right = 812 + 575 * (t ** 0.88) + 34 * math.sin(t * math.pi * 1.3 + 0.2)
    return left, right


def mountain_x_for_slope(y: float, side: str, offset: float = 0) -> float:
    left, right = mountain_span_at_y(y)
    if side == "left":
        return left + (right - left) * offset
    return right - (right - left) * offset


def add_linear_gradient(svg: SvgWriter, gid: str, x1: float, y1: float, x2: float, y2: float, stops: list[tuple[str, str, float | None]]) -> None:
    svg.open("linearGradient", {"id": gid, "x1": fmt(x1), "y1": fmt(y1), "x2": fmt(x2), "y2": fmt(y2), "gradientUnits": "userSpaceOnUse"})
    for offset, color, opacity in stops:
        attrs: dict[str, object] = {"offset": offset, "stop-color": color}
        if opacity is not None:
            attrs["stop-opacity"] = opacity
        svg.elem("stop", attrs)
    svg.close("linearGradient")


def add_radial_gradient(svg: SvgWriter, gid: str, cx: float, cy: float, r: float, stops: list[tuple[str, str, float | None]]) -> None:
    svg.open("radialGradient", {"id": gid, "cx": fmt(cx), "cy": fmt(cy), "r": fmt(r), "gradientUnits": "userSpaceOnUse"})
    for offset, color, opacity in stops:
        attrs: dict[str, object] = {"offset": offset, "stop-color": color}
        if opacity is not None:
            attrs["stop-opacity"] = opacity
        svg.elem("stop", attrs)
    svg.close("radialGradient")


def add_defs(svg: SvgWriter) -> None:
    svg.open("defs")
    add_linear_gradient(svg, "sky-main-gradient", 0, 0, 0, HEIGHT, [
        ("0%", "#4569ad", None),
        ("24%", "#789bd0", None),
        ("52%", "#f3bd91", None),
        ("76%", "#f7ddb0", None),
        ("100%", "#88a6c1", None),
    ])
    add_linear_gradient(svg, "horizon-warm-gradient", 0, 380, 0, 720, [
        ("0%", "#f3a56d", 0.05),
        ("45%", "#ffd9a2", 0.65),
        ("100%", "#b7c5d7", 0.18),
    ])
    add_radial_gradient(svg, "sun-radial-gradient", 245, 418, 290, [
        ("0%", "#fff8cf", 1),
        ("18%", "#ffd47a", 0.88),
        ("45%", "#ff9d6b", 0.28),
        ("100%", "#ff9d6b", 0.02),
    ])
    add_linear_gradient(svg, "mountain-lit-gradient", 340, 250, 1040, 640, [
        ("0%", "#f7cfb4", 1),
        ("28%", "#c9c7ce", 1),
        ("62%", "#8298b8", 1),
        ("100%", "#4e668c", 1),
    ])
    add_linear_gradient(svg, "mountain-shadow-gradient", 700, 240, 1300, 660, [
        ("0%", "#8ca0c4", 0.42),
        ("40%", "#506893", 0.68),
        ("100%", "#273d61", 0.82),
    ])
    add_linear_gradient(svg, "snow-warm-gradient", 360, 180, 840, 610, [
        ("0%", "#fff9df", 1),
        ("35%", "#fff0c8", 0.96),
        ("73%", "#e7d6d7", 0.9),
        ("100%", "#c7d5eb", 0.82),
    ])
    add_linear_gradient(svg, "snow-cool-gradient", 700, 190, 1220, 630, [
        ("0%", "#f3f1f4", 0.9),
        ("40%", "#bfd0ea", 0.82),
        ("100%", "#798bb3", 0.72),
    ])
    add_linear_gradient(svg, "cloud-highlight-gradient", 0, 430, 0, 780, [
        ("0%", "#fff2c8", 0.88),
        ("55%", "#f4cfa8", 0.56),
        ("100%", "#b7c6e2", 0.2),
    ])
    add_linear_gradient(svg, "cloud-shadow-gradient", 0, 480, 0, 820, [
        ("0%", "#f7d6bf", 0.42),
        ("56%", "#b0bdd9", 0.48),
        ("100%", "#7185ad", 0.42),
    ])
    add_linear_gradient(svg, "lake-base-gradient", 0, WATERLINE, 0, HEIGHT, [
        ("0%", "#94aeca", 1),
        ("35%", "#607b9d", 1),
        ("68%", "#354f75", 1),
        ("100%", "#152742", 1),
    ])
    add_linear_gradient(svg, "lake-reflection-gradient", 0, WATERLINE, 0, HEIGHT, [
        ("0%", "#f6c18a", 0.46),
        ("28%", "#c2b8c5", 0.28),
        ("62%", "#647ca5", 0.18),
        ("100%", "#273a58", 0.05),
    ])
    add_linear_gradient(svg, "city-atmosphere-gradient", 0, 610, 0, 760, [
        ("0%", "#e8d7c4", 0.52),
        ("55%", "#9aaac1", 0.4),
        ("100%", "#4d6382", 0.2),
    ])
    add_linear_gradient(svg, "foreground-forest-gradient", 0, 790, 0, HEIGHT, [
        ("0%", "#183a45", 0.96),
        ("44%", "#102b3b", 1),
        ("100%", "#071421", 1),
    ])
    add_linear_gradient(svg, "ridge-warm-gradient", 380, 210, 1060, 650, [
        ("0%", "#ffe5bc", 0.52),
        ("50%", "#8c7992", 0.38),
        ("100%", "#243454", 0.34),
    ])
    add_linear_gradient(svg, "mist-fade-gradient", 0, 480, 0, 760, [
        ("0%", "#ffffff", 0.05),
        ("56%", "#f4dfca", 0.33),
        ("100%", "#d9e4f1", 0.08),
    ])
    svg.open("filter", {"id": "soft-mist-filter", "x": "-8%", "y": "-8%", "width": "116%", "height": "116%"})
    svg.elem("feGaussianBlur", {"stdDeviation": 4.5})
    svg.close("filter")
    svg.open("filter", {"id": "distant-blur-filter", "x": "-5%", "y": "-5%", "width": "110%", "height": "110%"})
    svg.elem("feGaussianBlur", {"stdDeviation": 1.4})
    svg.close("filter")
    svg.open("clipPath", {"id": "fuji-clip", "clipPathUnits": "userSpaceOnUse"})
    svg.elem("path", {"d": FUJI_OUTLINE})
    svg.close("clipPath")
    svg.open("clipPath", {"id": "lake-clip", "clipPathUnits": "userSpaceOnUse"})
    svg.elem("rect", {"x": 0, "y": WATERLINE, "width": WIDTH, "height": HEIGHT - WATERLINE})
    svg.close("clipPath")
    svg.open("clipPath", {"id": "city-clip", "clipPathUnits": "userSpaceOnUse"})
    svg.elem("path", {"d": "M 120 600 C 430 588 730 602 1010 592 C 1230 585 1410 605 1510 627 L 1510 772 L 120 772 Z"})
    svg.close("clipPath")
    svg.close("defs")


def add_background(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("background-sky: 冷暖过渡的清晨天空")
    svg.open("g", {"id": "background-sky"})
    svg.elem("rect", {"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT, "fill": "url(#sky-main-gradient)"})
    svg.elem("rect", {"x": 0, "y": 0, "width": WIDTH, "height": 540, "fill": "#6f95c8", "opacity": 0.72})
    svg.elem("rect", {"x": 0, "y": 275, "width": WIDTH, "height": 300, "fill": "#f2bd92", "opacity": 0.34})
    svg.elem("rect", {"x": 0, "y": 492, "width": WIDTH, "height": 265, "fill": "#d4deea", "opacity": 0.28})
    svg.elem("rect", {"x": 0, "y": 355, "width": WIDTH, "height": 390, "fill": "url(#horizon-warm-gradient)", "opacity": 0.18})
    for i in range(18):
        y = 80 + i * 25 + rng.uniform(-8, 8)
        opacity = 0.05 + i * 0.006
        svg.elem("path", {
            "d": f"M 0 {fmt(y)} C 330 {fmt(y + rng.uniform(-20, 20))} 720 {fmt(y + rng.uniform(18, 36))} 1600 {fmt(y + rng.uniform(-18, 18))} L 1600 {fmt(y + 18)} C 970 {fmt(y + 30)} 460 {fmt(y + 16)} 0 {fmt(y + 34)} Z",
            "fill": "#ffffff",
            "opacity": round(opacity, 3),
        })
    svg.close("g")


def add_sun(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("sun-and-glow: 左侧低角度暖光来源")
    svg.open("g", {"id": "sun-and-glow"})
    svg.elem("circle", {"cx": 250, "cy": 417, "r": 288, "fill": "#ffd08a", "opacity": 0.18})
    svg.elem("circle", {"cx": 242, "cy": 414, "r": 188, "fill": "#ffe5aa", "opacity": 0.16})
    svg.elem("circle", {"cx": 238, "cy": 410, "r": 112, "fill": "#fff0bc", "opacity": 0.18})
    svg.elem("circle", {"cx": 235, "cy": 410, "r": 68, "fill": "#fff3bb", "opacity": 0.92})
    for i in range(22):
        y = 377 + i * 4.8 + rng.uniform(-1.4, 1.4)
        width = 75 + rng.random() * 160
        x = 205 - width * 0.15 + rng.uniform(-18, 18)
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(y)} C {fmt(x + width * 0.32)} {fmt(y - 4)} {fmt(x + width * 0.72)} {fmt(y + 4)} {fmt(x + width)} {fmt(y)}",
            "stroke": "#ffe4a6",
            "stroke-width": round(rng.uniform(1.1, 3.6), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.18, 0.44), 3),
        })
    svg.close("g")


def add_high_clouds(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("high-clouds: 高空薄云和远处冷暖空气层")
    svg.open("g", {"id": "high-clouds"})
    for i in range(96):
        y = rng.uniform(55, 360)
        x = rng.uniform(-80, WIDTH + 80)
        width = rng.uniform(120, 470)
        drift = rng.uniform(-40, 70)
        color = "#fff1cf" if x < 760 else "#d4def4"
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(y)} C {fmt(x + width * 0.28)} {fmt(y - rng.uniform(5, 22))} {fmt(x + width * 0.65)} {fmt(y + rng.uniform(-14, 18))} {fmt(x + width)} {fmt(y + drift * 0.12)}",
            "stroke": color,
            "stroke-width": round(rng.uniform(0.8, 3.6), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.07, 0.28), 3),
        })
    for i in range(24):
        cx = rng.uniform(90, 1510)
        cy = rng.uniform(210, 410)
        w = rng.uniform(180, 520)
        h = rng.uniform(14, 42)
        svg.elem("path", {
            "d": cloud_path(cx, cy, w, h, rng.randint(4, 7), rng),
            "fill": "#f7d8b9" if cx < 700 else "#bfcde7",
            "opacity": round(rng.uniform(0.08, 0.2), 3),
        })
    svg.close("g")


def add_distant_atmosphere(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("distant-atmosphere: 地平线薄雾和空气透视")
    svg.open("g", {"id": "distant-atmosphere"})
    for i in range(34):
        y = 430 + i * 7.5 + rng.uniform(-4, 4)
        svg.elem("path", {
            "d": f"M 0 {fmt(y)} C 265 {fmt(y - 21)} 520 {fmt(y + 18)} 790 {fmt(y - 4)} C 1070 {fmt(y - 23)} 1355 {fmt(y + 24)} 1600 {fmt(y - 6)} L 1600 {fmt(y + rng.uniform(15, 33))} C 1220 {fmt(y + 20)} 875 {fmt(y + 13)} 520 {fmt(y + 25)} C 260 {fmt(y + 34)} 120 {fmt(y + 18)} 0 {fmt(y + 28)} Z",
            "fill": "#e7d9cf",
            "opacity": round(0.035 + i * 0.0028, 3),
        })
    svg.elem("rect", {"x": 0, "y": 525, "width": WIDTH, "height": 185, "fill": "#e4edf4", "filter": "url(#soft-mist-filter)", "opacity": 0.22})
    svg.close("g")


def add_mount_fuji(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("mount-fuji-base: 不对称山体轮廓、岩面和冷暖坡面")
    svg.open("g", {"id": "mount-fuji-base"})
    svg.elem("path", {"d": FUJI_OUTLINE, "fill": "#8699b5"})
    svg.elem("path", {"d": FUJI_OUTLINE, "fill": "url(#mountain-lit-gradient)", "opacity": 0.15})
    svg.elem("path", {
        "d": "M 813 194 C 887 271 965 388 1065 497 C 1133 571 1248 621 1386 643 C 1146 635 964 626 786 630 C 821 510 842 365 813 194 Z",
        "fill": "#304c75",
        "opacity": 0.52,
    })
    svg.elem("path", {
        "d": "M 210 640 C 352 606 460 534 576 400 C 637 329 721 228 792 185 C 735 312 688 457 687 630 C 520 632 371 637 210 640 Z",
        "fill": "#f0b99f",
        "opacity": 0.24,
    })
    svg.open("g", {"id": "mount-fuji-faceted-rock", "clip-path": "url(#fuji-clip)"})
    for i in range(155):
        y = rng.uniform(260, 640)
        left, right = mountain_span_at_y(y)
        span = right - left
        x = rng.uniform(left + span * 0.08, right - span * 0.08)
        h = rng.uniform(18, 72)
        w = rng.uniform(35, 145) * (0.45 + (y - 220) / 520)
        lean = -1 if x < 805 else 1
        color = "#d9aa9a" if x < 770 and rng.random() < 0.45 else "#587190"
        opacity = rng.uniform(0.07, 0.23) if color == "#405879" else rng.uniform(0.08, 0.2)
        p = [
            (x - w * rng.uniform(0.3, 0.58), y + rng.uniform(-8, 8)),
            (x + lean * rng.uniform(15, 48), y - h * rng.uniform(0.4, 0.85)),
            (x + w * rng.uniform(0.28, 0.62), y + rng.uniform(4, 22)),
            (x + lean * rng.uniform(-12, 18), y + h * rng.uniform(0.22, 0.55)),
        ]
        svg.elem("path", {"d": d_line(p, True), "fill": color, "opacity": round(opacity, 3)})
    svg.close("g")
    svg.close("g")

    svg.comment("mount-fuji-snow: 雪帽、雪线、雪沟和积雪舌")
    svg.open("g", {"id": "mount-fuji-snow", "clip-path": "url(#fuji-clip)"})
    summit_cap = (
        "M 704 246 C 731 205 772 181 813 194 "
        "C 849 206 875 249 904 290 "
        "C 870 278 838 283 810 266 "
        "C 779 247 747 259 704 246 Z"
    )
    svg.elem("path", {"d": summit_cap, "fill": "#fff3d2", "opacity": 0.98})
    svg.elem("path", {
        "d": "M 807 195 C 842 212 870 255 904 290 C 864 280 837 280 812 264 C 818 241 817 218 807 195 Z",
        "fill": "#c9d8ef",
        "opacity": 0.78,
    })
    fixed_snowfields = [
        ("M 666 285 C 717 266 760 267 808 291 C 770 322 736 365 690 438 C 655 396 646 339 666 285 Z", "#fff0cd", 0.76),
        ("M 828 276 C 873 291 905 332 944 388 C 911 396 879 376 849 420 C 846 366 842 319 828 276 Z", "#bed0ea", 0.66),
        ("M 560 424 C 625 390 680 410 733 452 C 694 488 657 527 611 596 C 590 533 559 489 560 424 Z", "#f5ddcc", 0.56),
        ("M 903 430 C 968 443 1011 487 1068 552 C 999 543 951 566 901 615 C 916 545 925 489 903 430 Z", "#b7c8e2", 0.5),
    ]
    for d, fill, opacity in fixed_snowfields:
        svg.elem("path", {"d": d, "fill": fill, "opacity": opacity})
    for i in range(225):
        y = rng.uniform(255, 620)
        left, right = mountain_span_at_y(y)
        span = right - left
        side_bias = rng.random()
        if side_bias < 0.48:
            x = rng.uniform(left + span * 0.08, 805)
            lean = rng.uniform(-0.42, -0.05)
            fill = rng.choice(["#fff0c8", "#f6dfd1", "#f9e8d7"])
            op = rng.uniform(0.34, 0.86)
        else:
            x = rng.uniform(805, right - span * 0.07)
            lean = rng.uniform(0.04, 0.46)
            fill = rng.choice(["#c7d7ef", "#b8c9e6", "#d7dfef"])
            op = rng.uniform(0.28, 0.74)
        w = rng.uniform(18, 86) * (0.55 + (y - 240) / 470)
        h = rng.uniform(11, 42)
        if rng.random() < 0.58:
            x2 = x + lean * rng.uniform(70, 210)
            y2 = y + rng.uniform(40, 160)
            path_d = tapered_stroke_path(x, y, x2, y2, rng.uniform(2.2, 8.5), rng)
        else:
            path_d = snow_patch_path(x, y, w, h, rng, lean)
        svg.elem("path", {"d": path_d, "fill": fill, "opacity": round(op, 3)})
    for i in range(88):
        y = rng.uniform(230, 520)
        side = "left" if rng.random() < 0.52 else "right"
        x = mountain_x_for_slope(y, side, rng.uniform(0.1, 0.4))
        x2 = x + (-1 if side == "left" else 1) * rng.uniform(60, 180)
        y2 = y + rng.uniform(55, 165)
        svg.elem("path", {
            "d": cubic_path([(x, y), ((x + x2) / 2 + rng.uniform(-25, 25), (y + y2) / 2), (x2, y2)], rng, 10),
            "stroke": "#fff8dd" if side == "left" else "#cad9f2",
            "stroke-width": round(rng.uniform(1.0, 3.4), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.28, 0.68), 3),
        })
    svg.close("g")

    svg.comment("mount-fuji-ridges: 山脊、侵蚀线和岩层纹理")
    svg.open("g", {"id": "mount-fuji-ridges", "clip-path": "url(#fuji-clip)"})
    for i in range(285):
        start_y = rng.uniform(220, 390) if rng.random() < 0.36 else rng.uniform(330, 620)
        left, right = mountain_span_at_y(start_y)
        side = -1 if rng.random() < 0.52 else 1
        start_x = 805 + side * rng.uniform(8, max(12, (right - left) * 0.18))
        end_y = clamp(start_y + rng.uniform(45, 235), 250, 650)
        left2, right2 = mountain_span_at_y(end_y)
        target = left2 if side < 0 else right2
        end_x = start_x + (target - start_x) * rng.uniform(0.28, 0.78) + rng.uniform(-45, 45)
        color = "#ffe0b8" if side < 0 and rng.random() < 0.42 else "#243958"
        svg.elem("path", {
            "d": cubic_path([(start_x, start_y), ((start_x + end_x) / 2, (start_y + end_y) / 2), (end_x, end_y)], rng, rng.uniform(4, 18)),
            "stroke": color,
            "stroke-width": round(rng.uniform(0.45, 2.2), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.1, 0.36), 3),
        })
    for i in range(96):
        y = rng.uniform(310, 625)
        left, right = mountain_span_at_y(y)
        x1 = rng.uniform(left + 20, right - 120)
        x2 = clamp(x1 + rng.uniform(50, 190), left + 20, right - 12)
        svg.elem("path", {
            "d": f"M {fmt(x1)} {fmt(y)} C {fmt(x1 + (x2 - x1) * 0.36)} {fmt(y + rng.uniform(-14, 14))} {fmt(x1 + (x2 - x1) * 0.72)} {fmt(y + rng.uniform(-10, 18))} {fmt(x2)} {fmt(y + rng.uniform(-6, 12))}",
            "stroke": "#1a2c49",
            "stroke-width": round(rng.uniform(0.35, 1.4), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.07, 0.22), 3),
        })
    svg.close("g")

    svg.comment("mount-fuji-light: 左暖右冷的定向光照和雪峰边缘高光")
    svg.open("g", {"id": "mount-fuji-light", "clip-path": "url(#fuji-clip)"})
    for i in range(76):
        y = rng.uniform(210, 615)
        left, right = mountain_span_at_y(y)
        span = right - left
        x = rng.uniform(left + span * 0.03, left + span * 0.48)
        length = rng.uniform(30, 150)
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(y)} C {fmt(x + length * 0.32)} {fmt(y - rng.uniform(6, 24))} {fmt(x + length * 0.72)} {fmt(y - rng.uniform(4, 18))} {fmt(x + length)} {fmt(y + rng.uniform(-8, 10))}",
            "stroke": "#ffe4b7",
            "stroke-width": round(rng.uniform(0.5, 2.4), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.12, 0.44), 3),
        })
    svg.elem("path", {"d": "M 716 219 C 751 181 793 175 823 193 C 790 197 758 211 716 219 Z", "fill": "#fff4cb", "opacity": 0.36})
    svg.close("g")


def add_cloud_bank(svg: SvgWriter, rng: random.Random, group_id: str, count: int, y_min: float, y_max: float, w_min: float, w_max: float, h_min: float, h_max: float, base_opacity: float, foreground: bool = False) -> None:
    svg.comment(f"{group_id}: 贝塞尔曲线构成的分层云海")
    svg.open("g", {"id": group_id})
    for i in range(count):
        cx = rng.uniform(-40, WIDTH + 40)
        cy = rng.uniform(y_min, y_max)
        w = rng.uniform(w_min, w_max)
        h = rng.uniform(h_min, h_max)
        lobes = rng.randint(5, 10 if foreground else 8)
        fill = rng.choice(["#f6dec4", "#f1cfae", "#d7d9e4"]) if rng.random() < 0.58 else rng.choice(["#9cafcd", "#8498bd", "#b6c2d9"])
        op = clamp(base_opacity + rng.uniform(-0.12, 0.16), 0.06, 0.82)
        svg.elem("path", {"d": cloud_path(cx, cy, w, h, lobes, rng), "fill": fill, "opacity": round(op, 3)})
        if rng.random() < (0.72 if foreground else 0.48):
            shadow_y = cy + h * rng.uniform(0.18, 0.34)
            shadow_d = cloud_path(cx + rng.uniform(-18, 18), shadow_y, w * rng.uniform(0.62, 0.94), h * rng.uniform(0.28, 0.5), rng.randint(4, 7), rng)
            svg.elem("path", {"d": shadow_d, "fill": "#526895", "opacity": round(op * rng.uniform(0.18, 0.38), 3)})
    svg.close("g")


def add_clouds(svg: SvgWriter, rng: random.Random) -> None:
    add_cloud_bank(svg, rng, "cloud-sea-back", 96, 510, 625, 90, 260, 22, 62, 0.2, False)
    add_cloud_bank(svg, rng, "cloud-sea-middle", 126, 575, 690, 120, 340, 30, 82, 0.34, False)
    add_cloud_bank(svg, rng, "cloud-sea-front", 154, 640, 760, 150, 440, 38, 96, 0.44, True)


def add_city(svg: SvgWriter, rng: random.Random) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    windows: list[tuple[float, float, float]] = []
    street_lights: list[tuple[float, float, float]] = []
    buildings: list[tuple[float, float, float, float, str, float]] = []
    rows = [
        (145, 645, 1260, 10, 28, 18, 56, 0.44),
        (120, 672, 1380, 12, 34, 26, 82, 0.58),
        (190, 704, 1230, 15, 46, 32, 112, 0.72),
        (320, 724, 1040, 20, 58, 30, 96, 0.82),
    ]
    for start_x, base_y, total_w, min_w, max_w, min_h, max_h, opacity in rows:
        x = start_x
        while x < start_x + total_w:
            w = rng.uniform(min_w, max_w)
            gap = rng.uniform(1.5, 5.5)
            h = rng.uniform(min_h, max_h)
            ground = base_y + math.sin(x * 0.013) * 7 + rng.uniform(-4, 5)
            color_choices = ["#7e91a9", "#687e9c", "#9b928d", "#526985", "#a78f80"]
            fill = rng.choice(color_choices)
            buildings.append((x, ground - h, w, h, fill, opacity))
            x += w + gap

    svg.comment("distant-city: 山脚与岸线之间的城市远景")
    svg.open("g", {"id": "distant-city", "clip-path": "url(#city-clip)"})
    svg.elem("path", {"d": "M 105 705 C 320 676 540 690 745 661 C 940 633 1165 655 1505 623 L 1505 772 L 105 772 Z", "fill": "#d5dbe3", "opacity": 0.38})
    for idx, (x, y, w, h, fill, opacity) in enumerate(buildings):
        roof_kind = idx % 5
        body_path = f"M {fmt(x)} {fmt(y)} L {fmt(x + w)} {fmt(y + rng.uniform(-2, 2))} L {fmt(x + w)} {fmt(y + h)} L {fmt(x)} {fmt(y + h)} Z"
        svg.elem("path", {"d": body_path, "fill": fill, "opacity": round(opacity, 3)})
        if roof_kind == 0:
            roof = f"M {fmt(x - 1)} {fmt(y)} L {fmt(x + w * 0.5)} {fmt(y - h * rng.uniform(0.12, 0.28))} L {fmt(x + w + 1)} {fmt(y)} Z"
            svg.elem("path", {"d": roof, "fill": "#4c5a70", "opacity": round(min(0.88, opacity + 0.1), 3)})
        elif roof_kind == 1:
            svg.elem("rect", {"x": round(x + w * 0.08, 2), "y": round(y - h * 0.08, 2), "width": round(w * 0.84, 2), "height": round(max(2.4, h * 0.08), 2), "fill": "#4b607a", "opacity": round(min(0.86, opacity + 0.06), 3)})
        elif roof_kind == 2:
            roof = f"M {fmt(x)} {fmt(y)} L {fmt(x + w * 0.38)} {fmt(y - h * 0.16)} L {fmt(x + w)} {fmt(y - h * 0.05)} L {fmt(x + w)} {fmt(y + 3)} L {fmt(x)} {fmt(y + 3)} Z"
            svg.elem("path", {"d": roof, "fill": "#54657d", "opacity": round(min(0.86, opacity + 0.04), 3)})
        if w > 21 and h > 35 and rng.random() < 0.38:
            svg.elem("path", {
                "d": f"M {fmt(x + w * 0.18)} {fmt(y - rng.uniform(7, 16))} L {fmt(x + w * 0.18)} {fmt(y)} M {fmt(x + w * 0.18)} {fmt(y - rng.uniform(7, 16))} L {fmt(x + w * 0.72)} {fmt(y - rng.uniform(4, 12))}",
                "stroke": "#33455d",
                "stroke-width": round(rng.uniform(0.6, 1.4), 2),
                "stroke-linecap": "round",
                "fill": "none",
                "opacity": round(opacity * 0.55, 3),
            })
        if h > 48:
            svg.elem("rect", {"x": round(x + w * 0.76, 2), "y": round(y + 2, 2), "width": round(w * 0.18, 2), "height": round(h - 3, 2), "fill": "#20334f", "opacity": round(0.08 + opacity * 0.12, 3)})
        cols = max(1, int(w // rng.uniform(6.5, 9.0)))
        floors = max(1, int(h // rng.uniform(9.0, 13.0)))
        for floor in range(floors):
            for col in range(cols):
                if rng.random() < (0.22 if y < 670 else 0.36):
                    wx = x + 3 + col * (w - 6) / max(1, cols) + rng.uniform(-0.7, 0.7)
                    wy = y + 5 + floor * (h - 9) / max(1, floors) + rng.uniform(-0.5, 0.5)
                    size = rng.uniform(1.3, 3.6) * (1.08 if y > 690 else 0.82)
                    windows.append((wx, wy, size))
    for i in range(32):
        y = rng.uniform(675, 742)
        x1 = rng.uniform(120, 430)
        x2 = rng.uniform(1150, 1510)
        svg.elem("path", {
            "d": f"M {fmt(x1)} {fmt(y)} C 520 {fmt(y + rng.uniform(-30, 25))} 920 {fmt(y + rng.uniform(-18, 26))} {fmt(x2)} {fmt(y + rng.uniform(-12, 20))}",
            "stroke": "#334862",
            "stroke-width": round(rng.uniform(1.2, 4.4), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.18, 0.48), 3),
        })
    for i in range(28):
        x = 150 + i * rng.uniform(42, 62)
        y = 705 + math.sin(i * 0.7) * 9 + rng.uniform(-3, 3)
        svg.elem("path", {"d": f"M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y - rng.uniform(18, 36))}", "stroke": "#263950", "stroke-width": round(rng.uniform(0.8, 1.7), 2), "stroke-linecap": "round", "fill": "none", "opacity": 0.54})
        if rng.random() < 0.72:
            street_lights.append((x, y - rng.uniform(18, 32), rng.uniform(1.8, 3.4)))
    svg.close("g")

    svg.comment("city-lights: 克制的窗户、街灯和晨光反射源")
    svg.open("g", {"id": "city-lights", "clip-path": "url(#city-clip)"})
    for wx, wy, size in windows[:640]:
        color = "#ffd47b" if rng.random() < 0.65 else "#e7edf4"
        op = rng.uniform(0.35, 0.86) if color == "#ffd47b" else rng.uniform(0.14, 0.42)
        svg.elem("rect", {"x": round(wx, 2), "y": round(wy, 2), "width": round(size * rng.uniform(0.75, 1.45), 2), "height": round(size * rng.uniform(0.65, 1.25), 2), "rx": round(size * 0.12, 2), "fill": color, "opacity": round(op, 3)})
    for x, y, r in street_lights:
        svg.elem("circle", {"cx": round(x, 2), "cy": round(y, 2), "r": round(r, 2), "fill": "#ffd178", "opacity": round(rng.uniform(0.38, 0.75), 3)})
        windows.append((x, y, r * 1.2))
    svg.close("g")
    return windows[:640], street_lights


def add_shoreline(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("shoreline: 岸线、湿地、桥梁和护栏")
    svg.open("g", {"id": "shoreline"})
    svg.elem("path", {"d": "M 0 746 C 196 719 358 735 555 718 C 776 700 990 727 1188 707 C 1360 690 1500 713 1600 704 L 1600 773 C 1300 769 1052 752 781 762 C 487 773 240 761 0 786 Z", "fill": "#243f56", "opacity": 0.72})
    svg.elem("path", {"d": "M 0 732 C 260 711 486 724 720 706 C 996 685 1225 708 1600 690", "stroke": "#f1c695", "stroke-width": 3.2, "stroke-linecap": "round", "fill": "none", "opacity": 0.28})
    for i in range(120):
        x = rng.uniform(0, WIDTH)
        y = 730 + rng.uniform(-18, 38) + math.sin(x * 0.01) * 6
        length = rng.uniform(8, 35)
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(y)} C {fmt(x + length * 0.4)} {fmt(y + rng.uniform(-4, 4))} {fmt(x + length * 0.8)} {fmt(y + rng.uniform(-3, 5))} {fmt(x + length)} {fmt(y + rng.uniform(-2, 4))}",
            "stroke": rng.choice(["#20374b", "#e0b987", "#586d7f"]),
            "stroke-width": round(rng.uniform(0.8, 2.4), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.16, 0.48), 3),
        })
    for i in range(56):
        x = 80 + i * 26 + rng.uniform(-5, 5)
        y = 721 + math.sin(i * 0.4) * 9
        svg.elem("path", {"d": f"M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y + rng.uniform(12, 25))}", "stroke": "#1b3146", "stroke-width": round(rng.uniform(0.8, 1.6), 2), "stroke-linecap": "round", "fill": "none", "opacity": 0.58})
    svg.close("g")


def add_lake(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("lake: 下方三分之一湖面基础层")
    svg.open("g", {"id": "lake"})
    svg.elem("rect", {"x": 0, "y": WATERLINE, "width": WIDTH, "height": HEIGHT - WATERLINE, "fill": "#496f91"})
    svg.elem("rect", {"x": 0, "y": WATERLINE, "width": WIDTH, "height": HEIGHT - WATERLINE, "fill": "url(#lake-base-gradient)", "opacity": 0.14})
    svg.elem("rect", {"x": 0, "y": WATERLINE, "width": WIDTH, "height": 130, "fill": "#d6b7a3", "opacity": 0.26})
    svg.elem("rect", {"x": 0, "y": WATERLINE, "width": WIDTH, "height": 130, "fill": "url(#lake-reflection-gradient)", "opacity": 0.14})
    for i in range(44):
        y = WATERLINE + i * 6.2 + rng.uniform(-2, 2)
        color = "#f5c08d" if i < 13 else ("#8ea5c4" if i < 28 else "#253e5f")
        svg.elem("path", {
            "d": f"M 0 {fmt(y)} C 260 {fmt(y + rng.uniform(-5, 7))} 560 {fmt(y + rng.uniform(-6, 8))} 840 {fmt(y + rng.uniform(-5, 5))} C 1110 {fmt(y + rng.uniform(-7, 6))} 1370 {fmt(y + rng.uniform(-4, 7))} 1600 {fmt(y + rng.uniform(-6, 6))}",
            "stroke": color,
            "stroke-width": round(rng.uniform(0.6, 2.0), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.06, 0.22), 3),
        })
    svg.close("g")


def add_reflections(svg: SvgWriter, rng: random.Random, city_lights: list[tuple[float, float, float]]) -> None:
    svg.comment("reflections: 富士山、云层、太阳和城市灯光的破碎倒影")
    svg.open("g", {"id": "reflections", "clip-path": "url(#lake-clip)"})
    for i in range(54):
        y = WATERLINE + 6 + i * rng.uniform(3.0, 5.7)
        width = max(12, 245 - i * 2.6 + rng.uniform(-25, 35))
        x = 230 - width * 0.15 + rng.uniform(-28, 30)
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(y)} C {fmt(x + width * 0.28)} {fmt(y - 3)} {fmt(x + width * 0.66)} {fmt(y + 4)} {fmt(x + width)} {fmt(y + rng.uniform(-2, 3))}",
            "stroke": "#ffd17a",
            "stroke-width": round(rng.uniform(1.0, 5.2), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.12, 0.44) * (1 - i / 70), 3),
        })
    for i in range(108):
        y = WATERLINE + 6 + i * 2.35
        t = (y - WATERLINE) / (HEIGHT - WATERLINE)
        half = 470 * (1 - t * 0.62) + rng.uniform(-26, 20)
        center = 805 + math.sin(t * math.pi * 5) * 12 + rng.uniform(-8, 8)
        h = rng.uniform(3.0, 8.5) * (1 + t * 1.8)
        left = center - half + rng.uniform(0, 65)
        right = center + half - rng.uniform(0, 65)
        if rng.random() < 0.18:
            continue
        d = (
            f"M {fmt(left)} {fmt(y)} "
            f"C {fmt(left + (right - left) * 0.28)} {fmt(y - rng.uniform(2, 8))} {fmt(left + (right - left) * 0.67)} {fmt(y + rng.uniform(-4, 5))} {fmt(right)} {fmt(y + rng.uniform(-2, 4))} "
            f"L {fmt(right - rng.uniform(8, 22))} {fmt(y + h)} "
            f"C {fmt(center + half * 0.24)} {fmt(y + h + rng.uniform(-2, 5))} {fmt(center - half * 0.22)} {fmt(y + h + rng.uniform(-3, 5))} {fmt(left + rng.uniform(7, 26))} {fmt(y + h)} Z"
        )
        fill = "#d59b91" if rng.random() < 0.36 else "#506b95"
        svg.elem("path", {"d": d, "fill": fill, "opacity": round(rng.uniform(0.05, 0.18) * (1 - t * 0.28), 3)})
    for i in range(145):
        y = rng.uniform(WATERLINE + 18, HEIGHT - 16)
        t = (y - WATERLINE) / (HEIGHT - WATERLINE)
        center = 805 + rng.uniform(-175, 175) * (1 - t * 0.4)
        length = rng.uniform(18, 120) * (1.25 - t * 0.42)
        color = "#fff2cf" if rng.random() < 0.42 else "#9eb4d5"
        svg.elem("path", {
            "d": f"M {fmt(center - length * 0.5)} {fmt(y)} C {fmt(center - length * 0.18)} {fmt(y - rng.uniform(2, 7))} {fmt(center + length * 0.22)} {fmt(y + rng.uniform(-4, 5))} {fmt(center + length * 0.5)} {fmt(y + rng.uniform(-2, 4))}",
            "stroke": color,
            "stroke-width": round(rng.uniform(0.7, 3.0), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.05, 0.22) * (1 - t * 0.25), 3),
        })
    for i in range(96):
        cx = rng.uniform(-20, WIDTH + 20)
        cy = rng.uniform(WATERLINE + 5, WATERLINE + 122)
        w = rng.uniform(120, 400)
        h = rng.uniform(10, 36)
        svg.elem("path", {"d": low_cloud_path(cx, cy, w, h, rng), "fill": "#d8c7c0", "opacity": round(rng.uniform(0.05, 0.16), 3)})
    for x, y, size in city_lights[:380]:
        if rng.random() < 0.58:
            reflect_y = WATERLINE + (WATERLINE - y) * rng.uniform(0.22, 0.72) + rng.uniform(0, 34)
            length = rng.uniform(5, 28) * (1 + size * 0.08)
            svg.elem("path", {
                "d": f"M {fmt(x)} {fmt(reflect_y)} C {fmt(x + rng.uniform(-3, 3))} {fmt(reflect_y + length * 0.35)} {fmt(x + rng.uniform(-4, 4))} {fmt(reflect_y + length * 0.72)} {fmt(x + rng.uniform(-5, 5))} {fmt(reflect_y + length)}",
                "stroke": "#ffd070",
                "stroke-width": round(rng.uniform(0.6, 2.2), 2),
                "stroke-linecap": "round",
                "fill": "none",
                "opacity": round(rng.uniform(0.12, 0.42), 3),
            })
    svg.close("g")


def add_water_ripples(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("water-ripples: 远密近疏的水平波纹")
    svg.open("g", {"id": "water-ripples", "clip-path": "url(#lake-clip)"})
    for i in range(520):
        t = rng.random()
        y = WATERLINE + (HEIGHT - WATERLINE) * (t ** 0.78)
        near = (y - WATERLINE) / (HEIGHT - WATERLINE)
        length = rng.uniform(18, 120) * (0.55 + near * 2.2)
        x = rng.uniform(-30, WIDTH + 20)
        amp = rng.uniform(0.6, 3.2) * (0.8 + near * 1.5)
        color_roll = rng.random()
        if color_roll < 0.18 and x < 570:
            color = "#f8ca8b"
        elif color_roll < 0.5:
            color = "#a7b9d4"
        else:
            color = "#162b48"
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(y)} C {fmt(x + length * 0.26)} {fmt(y - amp)} {fmt(x + length * 0.58)} {fmt(y + amp)} {fmt(x + length)} {fmt(y + rng.uniform(-amp, amp))}",
            "stroke": color,
            "stroke-width": round(rng.uniform(0.45, 1.7) * (0.75 + near * 0.8), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.08, 0.34) * (0.75 + near * 0.45), 3),
        })
    svg.close("g")


def add_foreground(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("foreground-forest: 深色前景树林、湿地和近岸植物")
    svg.open("g", {"id": "foreground-forest"})
    svg.elem("path", {"d": "M 0 866 C 115 836 218 872 332 850 C 508 816 705 873 858 836 C 1012 798 1220 858 1370 824 C 1462 803 1546 815 1600 792 L 1600 1000 L 0 1000 Z", "fill": "url(#foreground-forest-gradient)"})
    for i in range(238):
        x = rng.uniform(-20, WIDTH + 20)
        edge_bias = min(abs(x - WIDTH / 2) / (WIDTH / 2), 1)
        base = rng.uniform(850, 1008)
        h = rng.uniform(22, 135) * (0.72 + edge_bias * 0.72)
        w = rng.uniform(8, 34) * (0.75 + edge_bias * 0.55)
        color = rng.choice(["#071927", "#0b2532", "#113542", "#08131f"])
        if rng.random() < 0.68:
            levels = rng.randint(4, 7)
            points: list[tuple[float, float]] = [(x, base - h)]
            for level in range(levels):
                yy = base - h + (level + 1) * h / levels
                spread = w * (1 - level / (levels + 1)) * rng.uniform(0.85, 1.35)
                points.append((x + spread, yy - rng.uniform(1, 8)))
                points.append((x + spread * 0.35, yy + rng.uniform(0, 8)))
                points.append((x + spread * 0.18, yy + rng.uniform(0, 9)))
            points.append((x + w * 0.12, base))
            points.append((x - w * 0.12, base))
            for level in reversed(range(levels)):
                yy = base - h + (level + 1) * h / levels
                spread = w * (1 - level / (levels + 1)) * rng.uniform(0.85, 1.35)
                points.append((x - spread * 0.18, yy + rng.uniform(0, 9)))
                points.append((x - spread * 0.35, yy + rng.uniform(0, 8)))
                points.append((x - spread, yy - rng.uniform(1, 8)))
            svg.elem("path", {"d": d_line(points, True), "fill": color, "opacity": round(rng.uniform(0.72, 0.98), 3)})
        else:
            crown = (
                f"M {fmt(x - w)} {fmt(base - h * 0.38)} "
                f"C {fmt(x - w * 1.2)} {fmt(base - h * 0.7)} {fmt(x - w * 0.35)} {fmt(base - h * 1.02)} {fmt(x + rng.uniform(-3, 3))} {fmt(base - h)} "
                f"C {fmt(x + w * 0.62)} {fmt(base - h * 1.03)} {fmt(x + w * 1.3)} {fmt(base - h * 0.72)} {fmt(x + w)} {fmt(base - h * 0.38)} "
                f"C {fmt(x + w * 0.76)} {fmt(base - h * 0.12)} {fmt(x - w * 0.72)} {fmt(base - h * 0.1)} {fmt(x - w)} {fmt(base - h * 0.38)} Z"
            )
            svg.elem("path", {"d": crown, "fill": color, "opacity": round(rng.uniform(0.68, 0.94), 3)})
            svg.elem("path", {"d": f"M {fmt(x)} {fmt(base - h * 0.45)} L {fmt(x + rng.uniform(-3, 3))} {fmt(base)}", "stroke": "#06111b", "stroke-width": round(rng.uniform(1.4, 4.2), 2), "stroke-linecap": "round", "fill": "none", "opacity": 0.85})
    for i in range(145):
        x = rng.uniform(0, WIDTH)
        base = rng.uniform(850, 1000)
        h = rng.uniform(18, 80)
        bend = rng.uniform(-22, 22)
        svg.elem("path", {
            "d": f"M {fmt(x)} {fmt(base)} C {fmt(x + bend * 0.2)} {fmt(base - h * 0.4)} {fmt(x + bend * 0.72)} {fmt(base - h * 0.72)} {fmt(x + bend)} {fmt(base - h)}",
            "stroke": rng.choice(["#102b2f", "#183f3a", "#071825"]),
            "stroke-width": round(rng.uniform(0.65, 2.2), 2),
            "stroke-linecap": "round",
            "fill": "none",
            "opacity": round(rng.uniform(0.42, 0.9), 3),
        })
    svg.close("g")


def add_final_atmosphere(svg: SvgWriter, rng: random.Random) -> None:
    svg.comment("final-atmosphere: 统一全画面的晨雾、冷暖空气和远近层次")
    svg.open("g", {"id": "final-atmosphere"})
    for i in range(22):
        y = rng.uniform(515, 785)
        h = rng.uniform(18, 72)
        svg.elem("path", {
            "d": f"M 0 {fmt(y)} C 265 {fmt(y - rng.uniform(15, 42))} 560 {fmt(y + rng.uniform(-24, 22))} 830 {fmt(y - rng.uniform(8, 34))} C 1120 {fmt(y - rng.uniform(28, 24))} 1360 {fmt(y + rng.uniform(-18, 28))} 1600 {fmt(y - rng.uniform(8, 22))} L 1600 {fmt(y + h)} C 1170 {fmt(y + h + rng.uniform(-14, 18))} 795 {fmt(y + h - rng.uniform(6, 18))} 400 {fmt(y + h + rng.uniform(-8, 18))} C 210 {fmt(y + h + rng.uniform(-16, 20))} 80 {fmt(y + h - rng.uniform(4, 18))} 0 {fmt(y + h)} Z",
            "fill": "#ffffff" if i < 12 else "#a9bad5",
            "opacity": round(rng.uniform(0.035, 0.13), 3),
            "filter": "url(#soft-mist-filter)" if i % 5 == 0 else None,
        })
    svg.elem("rect", {"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT, "fill": "#1b3154", "opacity": 0.018})
    svg.close("g")


def build_svg() -> str:
    rng = random.Random(SEED)
    svg = SvgWriter()
    svg.raw('<?xml version="1.0" encoding="UTF-8"?>')
    svg.open("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"0 0 {WIDTH} {HEIGHT}", "width": WIDTH, "height": HEIGHT, "role": "img", "aria-labelledby": "title desc"})
    svg.open("title", {"id": "title"})
    svg.raw("写实级富士山清晨风景 SVG")
    svg.close("title")
    svg.open("desc", {"id": "desc"})
    svg.raw("冬季富士山、云海、山脚城市、湖面倒影和前景树林构成的代码原生矢量旅游海报。")
    svg.close("desc")
    add_defs(svg)
    add_background(svg, rng)
    add_sun(svg, rng)
    add_high_clouds(svg, rng)
    add_distant_atmosphere(svg, rng)
    add_mount_fuji(svg, rng)
    add_clouds(svg, rng)
    city_lights, _street_lights = add_city(svg, rng)
    add_shoreline(svg, rng)
    add_lake(svg, rng)
    add_reflections(svg, rng, city_lights)
    add_water_ripples(svg, rng)
    add_foreground(svg, rng)
    add_final_atmosphere(svg, rng)
    svg.close("svg")
    return "\n".join(svg.lines) + "\n"


def main() -> None:
    svg_text = build_svg()
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(svg_text)
    line_count = svg_text.count("\n")
    non_empty = sum(1 for line in svg_text.splitlines() if line.strip() and not line.strip().startswith("<!--"))
    tags = re.findall(r"<(?!/|\?|!)([A-Za-z][\w:-]*)\b", svg_text)
    counts = Counter(tags)
    size = os.path.getsize(OUTPUT)
    print(f"generated={OUTPUT}")
    print(f"seed={SEED}")
    print(f"lines={line_count}")
    print(f"non_empty_non_comment_lines={non_empty}")
    print(f"file_size_bytes={size}")
    print(f"element_count={sum(counts.values())}")
    for name, count in sorted(counts.items()):
        print(f"element_type.{name}={count}")


if __name__ == "__main__":
    main()
