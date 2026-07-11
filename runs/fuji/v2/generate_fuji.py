#!/usr/bin/env python3
"""以固定种子生成一幅静态、代码原生的写实风富士山 SVG。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import math
import random
import re


WIDTH = 1600
HEIGHT = 1000
SEED = 20260629
LAKE_TOP = 690
REFLECTION_AXIS = 610
BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "fuji.svg"

MOUNTAIN_PATH = (
    "M 132 668 C 250 644 362 591 476 520 C 550 474 602 404 654 320 "
    "C 683 273 698 236 720 211 C 732 198 745 199 757 206 "
    "C 769 201 782 202 794 207 C 805 209 815 215 823 224 C 853 257 879 294 912 333 "
    "C 969 401 1022 466 1091 511 C 1195 580 1322 629 1472 665 "
    "L 1498 708 L 102 708 Z"
)

SNOW_CAP_PATH = (
    "M 472 522 C 535 477 600 405 654 320 C 681 278 699 235 722 209 "
    "C 733 198 745 199 757 206 C 769 201 782 202 794 207 C 805 209 815 215 823 224 "
    "C 852 257 879 294 912 333 C 947 375 980 416 1017 454 "
    "C 981 443 947 432 914 440 C 892 446 878 430 858 411 "
    "C 838 393 821 401 802 424 C 786 442 769 435 752 408 "
    "C 736 385 718 392 699 421 C 680 450 662 458 642 440 "
    "C 621 421 602 437 582 466 C 557 501 527 517 492 531 Z"
)


def fmt(value: float) -> str:
    """最多保留两位小数，同时避免无意义的小数尾零。"""
    value = round(value, 2)
    if abs(value) < 0.005:
        value = 0.0
    return f"{value:.2f}".rstrip("0").rstrip(".")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def cloud_path(rng: random.Random, cx: float, cy: float, width: float, height: float, lobes: int) -> str:
    """生成不依赖规则圆形堆叠的连续贝塞尔云体。"""
    left = clamp(cx - width / 2, 0, WIDTH)
    right = clamp(cx + width / 2, 0, WIDTH)
    width = right - left
    base = cy + height * rng.uniform(0.20, 0.38)
    step = width / lobes
    parts = [f"M {fmt(left)} {fmt(base)}"]
    x = left
    for i in range(lobes):
        x_next = left + (i + 1) * step
        peak = cy - height * rng.uniform(0.25, 0.61)
        shoulder = cy - height * rng.uniform(0.02, 0.18)
        parts.append(
            f"C {fmt(x + step * 0.10)} {fmt(shoulder)} "
            f"{fmt(x + step * 0.22)} {fmt(peak)} {fmt(x + step * 0.48)} {fmt(peak)}"
        )
        parts.append(
            f"C {fmt(x + step * 0.72)} {fmt(peak)} "
            f"{fmt(x + step * 0.88)} {fmt(shoulder)} {fmt(x_next)} {fmt(base)}"
        )
        x = x_next
    lower = cy + height * rng.uniform(0.45, 0.72)
    parts.append(
        f"C {fmt(right - width * 0.18)} {fmt(lower)} {fmt(left + width * 0.18)} {fmt(lower)} {fmt(left)} {fmt(base)} Z"
    )
    return " ".join(parts)


def thin_cloud_path(rng: random.Random, x: float, y: float, width: float, height: float) -> str:
    x2 = clamp(x + width, 0, WIDTH)
    x = clamp(x, 0, WIDTH)
    c1 = x + (x2 - x) * rng.uniform(0.22, 0.34)
    c2 = x + (x2 - x) * rng.uniform(0.60, 0.76)
    return (
        f"M {fmt(x)} {fmt(y)} C {fmt(c1)} {fmt(y - height)} {fmt(c2)} {fmt(y + height * 0.55)} {fmt(x2)} {fmt(y - height * 0.12)} "
        f"C {fmt(c2)} {fmt(y + height * 0.98)} {fmt(c1)} {fmt(y + height * 0.58)} {fmt(x)} {fmt(y)} Z"
    )


def mountain_bounds(y: float) -> tuple[float, float]:
    """近似富士山在给定高度的左右边界，用于约束内部纹理。"""
    t = clamp((y - 204) / 474, 0, 1)
    center = 768 + 18 * t
    half = 24 + 660 * (t ** 0.88)
    return center - half, center + half


def tree_foliage_path(rng: random.Random, x: float, base: float, height: float, width: float) -> str:
    top = base - height
    tiers = rng.randint(4, 7)
    pts: list[tuple[float, float]] = [(x, top)]
    for tier in range(tiers):
        t = (tier + 1) / tiers
        yy = top + height * (0.16 + 0.78 * t)
        half = width * (0.16 + 0.42 * t) * rng.uniform(0.86, 1.12)
        pts.append((x - half, yy))
        pts.append((x - half * 0.33, yy - height * rng.uniform(0.04, 0.10)))
        pts.append((x + half, yy))
        pts.append((x + half * 0.28, yy - height * rng.uniform(0.04, 0.10)))
    pts.append((x + width * 0.10, base))
    pts.append((x - width * 0.10, base))
    return "M " + " L ".join(f"{fmt(px)} {fmt(py)}" for px, py in pts) + " Z"


def main() -> None:
    rng = random.Random(SEED)
    lines: list[str] = []

    def add(line: str) -> None:
        lines.append(line)

    def group(group_id: str, extra: str = "") -> None:
        suffix = f" {extra}" if extra else ""
        add(f'<g id="{group_id}"{suffix}>')

    add('<?xml version="1.0" encoding="UTF-8"?>')
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title description">')
    add('<title id="title">冬日清晨的富士山、云海、湖面与山脚城市</title>')
    add('<desc id="description">左侧金色日出照亮非对称雪峰，冷暖光线跨越多层云海、城市、湖面倒影和前景树林。</desc>')
    add('<metadata>seed=20260629; generator=generate_fuji.py; static-vector=true</metadata>')

    # 统一颜色、裁剪、遮罩与有限滤镜系统。
    add('<defs>')
    gradients = [
        ('sky-main-gradient', 'linearGradient', 'x1="0" y1="0" x2="0" y2="720" gradientUnits="userSpaceOnUse"', [
            ('0%', '#18284e', '1'), ('28%', '#506b9c', '1'), ('62%', '#b7a9bd', '1'), ('86%', '#f2b58f', '1'), ('100%', '#ffe1ad', '1')]),
        ('horizon-warm-gradient', 'linearGradient', 'x1="0" y1="0" x2="1600" y2="0" gradientUnits="userSpaceOnUse"', [
            ('0%', '#ffd39b', '.86'), ('32%', '#e9a587', '.70'), ('68%', '#9d8fa9', '.34'), ('100%', '#7186ad', '.16')]),
        ('mount-fuji-light-gradient', 'linearGradient', 'x1="210" y1="280" x2="1260" y2="610" gradientUnits="userSpaceOnUse"', [
            ('0%', '#c99689', '1'), ('35%', '#8f8294', '1'), ('70%', '#52627e', '1'), ('100%', '#283852', '1')]),
        ('mount-fuji-shadow-gradient', 'linearGradient', 'x1="580" y1="300" x2="1400" y2="650" gradientUnits="userSpaceOnUse"', [
            ('0%', '#666d8a', '.72'), ('45%', '#394b6d', '.88'), ('100%', '#1d304e', '.96')]),
        ('snow-warm-light-gradient', 'linearGradient', 'x1="570" y1="220" x2="840" y2="520" gradientUnits="userSpaceOnUse"', [
            ('0%', '#fff9dd', '1'), ('40%', '#f7dfcf', '1'), ('78%', '#d9c7d0', '1'), ('100%', '#afadbf', '1')]),
        ('snow-cool-shadow-gradient', 'linearGradient', 'x1="760" y1="220" x2="1040" y2="520" gradientUnits="userSpaceOnUse"', [
            ('0%', '#e7e8ed', '1'), ('40%', '#bec9dc', '1'), ('100%', '#798aa8', '1')]),
        ('cloud-top-light-gradient', 'linearGradient', 'x1="0" y1="430" x2="0" y2="700" gradientUnits="userSpaceOnUse"', [
            ('0%', '#fff1d2', '.96'), ('46%', '#e6cad0', '.88'), ('100%', '#a9abc3', '.72')]),
        ('cloud-bottom-shadow-gradient', 'linearGradient', 'x1="0" y1="470" x2="0" y2="735" gradientUnits="userSpaceOnUse"', [
            ('0%', '#b7adc1', '.78'), ('58%', '#727c9d', '.82'), ('100%', '#485979', '.90')]),
        ('lake-water-base-gradient', 'linearGradient', 'x1="0" y1="690" x2="0" y2="1000" gradientUnits="userSpaceOnUse"', [
            ('0%', '#7187a2', '1'), ('30%', '#435f7d', '1'), ('68%', '#223f5c', '1'), ('100%', '#102d43', '1')]),
        ('lake-reflection-gradient', 'linearGradient', 'x1="100" y1="760" x2="1500" y2="980" gradientUnits="userSpaceOnUse"', [
            ('0%', '#c99480', '.58'), ('35%', '#7d7b91', '.43'), ('70%', '#536886', '.38'), ('100%', '#263f61', '.28')]),
        ('city-atmosphere-haze-gradient', 'linearGradient', 'x1="0" y1="580" x2="1600" y2="710" gradientUnits="userSpaceOnUse"', [
            ('0%', '#9d8e8c', '.80'), ('42%', '#7f7884', '.72'), ('100%', '#4f6179', '.66')]),
        ('forest-tree-depth-gradient', 'linearGradient', 'x1="0" y1="700" x2="0" y2="1000" gradientUnits="userSpaceOnUse"', [
            ('0%', '#25414c', '.90'), ('55%', '#122f3b', '.98'), ('100%', '#071d29', '1')]),
        ('mountain-reflection-gradient', 'linearGradient', 'x1="200" y1="760" x2="1400" y2="980" gradientUnits="userSpaceOnUse"', [
            ('0%', '#927b83', '.44'), ('48%', '#53637d', '.36'), ('100%', '#253e5d', '.24')]),
        ('sun-track-reflect-gradient', 'linearGradient', 'x1="0" y1="690" x2="0" y2="1000" gradientUnits="userSpaceOnUse"', [
            ('0%', '#ffe2a1', '.74'), ('55%', '#f0b778', '.44'), ('100%', '#f39a5d', '.12')]),
        ('window-warm-light-gradient', 'linearGradient', 'x1="0" y1="0" x2="0" y2="10" gradientUnits="userSpaceOnUse"', [
            ('0%', '#fff2af', '1'), ('100%', '#e59b58', '.72')]),
        ('foreground-mist-gradient', 'linearGradient', 'x1="0" y1="560" x2="0" y2="760" gradientUnits="userSpaceOnUse"', [
            ('0%', '#f0d1c7', '.05'), ('52%', '#b9aebe', '.32'), ('100%', '#7d8da5', '.03')]),
        ('reflection-fade-gradient', 'linearGradient', 'x1="0" y1="690" x2="0" y2="1000" gradientUnits="userSpaceOnUse"', [
            ('0%', '#ffffff', '.76'), ('48%', '#d8d8d8', '.43'), ('100%', '#737373', '.15')]),
    ]
    for gradient_id, tag, attrs, stops in gradients:
        add(f'<{tag} id="{gradient_id}" {attrs}>')
        for offset, color, opacity in stops:
            add(f'<stop offset="{offset}" stop-color="{color}" stop-opacity="{opacity}"/>')
        add(f'</{tag}>')
    add('<radialGradient id="sun-radial-gradient" cx="270" cy="230" r="115" gradientUnits="userSpaceOnUse">')
    add('<stop offset="0%" stop-color="#fffbd1" stop-opacity="1"/>')
    add('<stop offset="28%" stop-color="#ffd78c" stop-opacity=".92"/>')
    add('<stop offset="64%" stop-color="#f2a26f" stop-opacity=".42"/>')
    add('<stop offset="100%" stop-color="#df7f75" stop-opacity="0.02"/>')
    add('</radialGradient>')
    add('<clipPath id="clip-mountain" clipPathUnits="userSpaceOnUse">')
    add(f'<path d="{MOUNTAIN_PATH}"/>')
    add('</clipPath>')
    add('<clipPath id="clip-lake" clipPathUnits="userSpaceOnUse">')
    add('<path d="M 0 704 C 230 695 396 709 602 699 C 820 688 1016 704 1225 696 C 1390 691 1518 698 1600 693 L 1600 1000 L 0 1000 Z"/>')
    add('</clipPath>')
    add('<clipPath id="clip-city-band" clipPathUnits="userSpaceOnUse">')
    add('<path d="M 30 548 C 330 545 520 574 800 565 C 1050 556 1290 542 1570 557 L 1570 724 L 30 724 Z"/>')
    add('</clipPath>')
    add('<mask id="mask-reflection-breakup" maskUnits="userSpaceOnUse" x="0" y="690" width="1600" height="310">')
    # ImageMagick 的本地 SVG 委托不稳定支持 mask 内的渐变填充；使用中灰基底，
    # 纵向衰减由反射元素本身的透明度完成，黑色断裂线仍负责切碎倒影。
    add('<rect x="0" y="690" width="1600" height="310" fill="#b8b8b8"/>')
    for index in range(26):
        y = 708 + index * 11.2 + rng.uniform(-2, 2)
        width = 0.8 + index * 0.07
        add(f'<path d="M 35 {fmt(y)} C 410 {fmt(y + rng.uniform(-2, 2))} 1170 {fmt(y + rng.uniform(-2, 2))} 1565 {fmt(y)}" fill="none" stroke="#111111" stroke-width="{fmt(width)}" stroke-opacity="{fmt(rng.uniform(.18, .52))}"/>')
    add('</mask>')
    add('<filter id="filter-sun-bloom" x="-40%" y="-40%" width="180%" height="180%" color-interpolation-filters="sRGB">')
    add('<feGaussianBlur stdDeviation="18"/>')
    add('</filter>')
    add('<filter id="filter-cloud-soft" x="-12%" y="-20%" width="124%" height="150%" color-interpolation-filters="sRGB">')
    add('<feGaussianBlur stdDeviation="3.2"/>')
    add('</filter>')
    add('<filter id="filter-distant-haze" x="-8%" y="-80%" width="116%" height="260%" color-interpolation-filters="sRGB">')
    add('<feGaussianBlur stdDeviation="2"/>')
    add('</filter>')
    add('<filter id="filter-reflection-soft" x="-8%" y="-8%" width="116%" height="116%" color-interpolation-filters="sRGB">')
    add('<feGaussianBlur stdDeviation="1.6"/>')
    add('</filter>')
    add('</defs>')

    # 深冷高空过渡到桃金色地平线。
    add('<!-- 背景天空：冷蓝高空与左侧暖色地平线 -->')
    group('background-sky')
    add('<rect x="0" y="0" width="1600" height="720" fill="url(#sky-main-gradient)"/>')
    add('<rect x="0" y="410" width="1600" height="310" fill="url(#horizon-warm-gradient)" opacity=".58"/>')
    for index in range(16):
        y = 54 + index * 30 + rng.uniform(-5, 5)
        add(f'<path d="M 0 {fmt(y)} C 380 {fmt(y + rng.uniform(-9, 9))} 1090 {fmt(y + rng.uniform(-8, 8))} 1600 {fmt(y + rng.uniform(-4, 4))}" fill="none" stroke="{rng.choice(["#a8b6d2", "#d6c4cf", "#8e9cbe"])}" stroke-width="{fmt(rng.uniform(.5, 1.8))}" stroke-opacity="{fmt(rng.uniform(.05, .14))}"/>')
    add('</g>')

    # 低角度太阳只在左侧形成主光和克制光晕。
    add('<!-- 太阳与辉光：左侧低角度黄金时刻光源 -->')
    group('sun-and-glow')
    add('<circle cx="270" cy="230" r="128" fill="url(#sun-radial-gradient)" filter="url(#filter-sun-bloom)" opacity=".48"/>')
    add('<circle cx="270" cy="230" r="58" fill="url(#sun-radial-gradient)"/>')
    add('<circle cx="258" cy="218" r="31" fill="#fffbd8" opacity=".76"/>')
    add('<ellipse cx="292" cy="248" rx="92" ry="34" fill="#ffd6a0" opacity=".08" transform="rotate(-12 292 248)"/>')
    for index in range(18):
        angle = -0.62 + index * 0.071 + rng.uniform(-0.018, 0.018)
        length = rng.uniform(92, 205)
        x2 = 270 + math.cos(angle) * length
        y2 = 230 + math.sin(angle) * length
        add(f'<path d="M 270 230 L {fmt(x2)} {fmt(y2)}" stroke="#ffd7a1" stroke-width="{fmt(rng.uniform(.6, 1.8))}" stroke-opacity="{fmt(rng.uniform(.045, .13))}"/>')
    add('</g>')

    # 高空薄云使用长而轻的贝塞尔带状结构。
    add('<!-- 高空薄云：长尺度卷云和暖冷交界 -->')
    group('high-clouds')
    for index in range(68):
        y = rng.uniform(55, 395)
        width = rng.uniform(90, 380)
        x = rng.uniform(0, WIDTH - width)
        height = rng.uniform(3, 12)
        color = '#f6d9cf' if x + width / 2 < 720 else '#bcc7dd'
        add(f'<path d="{thin_cloud_path(rng, x, y, width, height)}" fill="{color}" opacity="{fmt(rng.uniform(.055, .20))}"/>')
    add('</g>')

    # 地平线和山后远空气层。
    add('<!-- 远处大气：地平线薄雾与冷暖空气层 -->')
    group('distant-atmosphere', 'filter="url(#filter-distant-haze)"')
    for index in range(44):
        y = 420 + index * 4.1 + rng.uniform(-1.8, 1.8)
        amp = rng.uniform(2, 9)
        color = rng.choice(['#e9c7bb', '#c7b8c6', '#9ba9c0', '#f2d3bd'])
        add(f'<path d="M 0 {fmt(y)} C 330 {fmt(y - amp)} 620 {fmt(y + amp)} 890 {fmt(y)} C 1120 {fmt(y - amp * .7)} 1390 {fmt(y + amp * .5)} 1600 {fmt(y - amp * .2)}" fill="none" stroke="{color}" stroke-width="{fmt(rng.uniform(2.2, 7.2))}" stroke-opacity="{fmt(rng.uniform(.06, .20))}"/>')
    add('</g>')

    # 山后云层尺度小、颜色淡、对比低。
    add('<!-- 后景云海：山后小尺度冷淡云层 -->')
    group('cloud-sea-back', 'filter="url(#filter-cloud-soft)"')
    for index in range(88):
        cx = rng.uniform(20, 1580)
        cy = rng.uniform(438, 558)
        width = rng.uniform(48, 142)
        height = rng.uniform(14, 38)
        fill = 'url(#cloud-top-light-gradient)' if index % 3 else 'url(#cloud-bottom-shadow-gradient)'
        add(f'<path d="{cloud_path(rng, cx, cy, width, height, rng.randint(4, 7))}" fill="{fill}" opacity="{fmt(rng.uniform(.15, .36))}"/>')
    add('</g>')

    # 富士山基础体块：广阔基底、左暖右冷的大坡面。
    add('<!-- 富士山基础：自然略不对称的山峰与大尺度坡面 -->')
    group('mount-fuji-base')
    add(f'<path d="{MOUNTAIN_PATH}" fill="url(#mount-fuji-light-gradient)"/>')
    add('<path d="M 766 204 C 806 226 870 316 931 385 C 1034 502 1210 596 1498 708 L 792 708 C 814 650 772 601 798 548 C 822 498 775 449 799 401 C 818 357 786 312 795 270 C 793 243 780 220 766 204 Z" fill="url(#mount-fuji-shadow-gradient)" opacity=".88" clip-path="url(#clip-mountain)"/>')
    add('<path d="M 132 668 C 386 599 549 468 654 320 C 630 437 532 569 356 676 Z" fill="#d39a8b" opacity=".22" clip-path="url(#clip-mountain)"/>')
    add('<polygon points="548,472 654,320 615,456 500,548" fill="#d3a093" opacity=".16" clip-path="url(#clip-mountain)"/>')
    for index in range(22):
        y1 = rng.uniform(300, 575)
        left, right = mountain_bounds(y1)
        x1 = rng.uniform(left + 8, right - 8)
        side = -1 if x1 < 768 else 1
        y2 = rng.uniform(y1 + 45, 675)
        x2 = clamp(x1 + side * rng.uniform(85, 270), *mountain_bounds(y2))
        x3 = clamp((x1 + x2) / 2 + rng.uniform(-45, 45), *mountain_bounds((y1 + y2) / 2))
        fill = rng.choice(['#aa7f80', '#695f72', '#475675', '#7f6c78', '#354865'])
        add(f'<path d="M {fmt(x1)} {fmt(y1)} C {fmt(x3)} {fmt((y1+y2)/2)} {fmt(x2)} {fmt(y2-18)} {fmt(x2)} {fmt(y2)} L {fmt(x2 + side * rng.uniform(28, 82))} {fmt(y2 + rng.uniform(8, 28))} C {fmt(x3 + side * 20)} {fmt((y1+y2)/2 + 34)} {fmt(x1 + side * rng.uniform(18, 55))} {fmt(y1 + rng.uniform(20, 48))} {fmt(x1)} {fmt(y1)} Z" fill="{fill}" opacity="{fmt(rng.uniform(.12, .34))}" clip-path="url(#clip-mountain)"/>')
    add('</g>')

    # 雪盖、互咬雪面、雪沟与积雪舌。
    add('<!-- 富士山积雪：不等高雪线、雪沟和雪舌 -->')
    group('mount-fuji-snow', 'clip-path="url(#clip-mountain)"')
    add(f'<path d="{SNOW_CAP_PATH}" fill="url(#snow-warm-light-gradient)"/>')
    add('<path d="M 766 204 C 793 197 811 208 829 226 C 856 260 884 303 914 338 C 946 377 979 416 1017 454 C 981 443 947 432 914 440 C 892 446 878 430 858 411 C 838 393 821 401 802 424 C 786 442 769 435 752 408 Z" fill="url(#snow-cool-shadow-gradient)" opacity=".84"/>')
    snow_colors = ['url(#snow-warm-light-gradient)', 'url(#snow-cool-shadow-gradient)', '#f5e4d8', '#d6d9e3', '#bbc7d9']
    for index in range(174):
        y = rng.uniform(238, 525)
        left, right = mountain_bounds(y)
        x = rng.uniform(left + 6, right - 6)
        max_w = max(8, min(54, (right - left) * .13))
        width = rng.uniform(7, max_w)
        length = rng.uniform(18, 92) * (1.15 if y > 390 else .82)
        lean = -0.24 if x < 765 else 0.28
        x2 = x + length * lean + rng.uniform(-9, 9)
        y2 = min(584, y + length)
        fill = snow_colors[0] if x < 730 and index % 3 else rng.choice(snow_colors[1:])
        opacity = rng.uniform(.20, .58)
        add(f'<path d="M {fmt(x - width*.48)} {fmt(y)} C {fmt(x - width*.15)} {fmt(y + length*.20)} {fmt(x2 - width*.35)} {fmt(y2 - length*.22)} {fmt(x2)} {fmt(y2)} C {fmt(x2 + width*.26)} {fmt(y2 - length*.24)} {fmt(x + width*.50)} {fmt(y + length*.17)} {fmt(x + width*.42)} {fmt(y)} C {fmt(x + width*.10)} {fmt(y + rng.uniform(-5, 5))} {fmt(x - width*.18)} {fmt(y + rng.uniform(-4, 6))} {fmt(x - width*.48)} {fmt(y)} Z" fill="{fill}" opacity="{fmt(opacity)}"/>')
    add('</g>')

    # 岩层、山脊和侵蚀纹理沿坡面方向分布。
    add('<!-- 富士山山脊：岩层、侵蚀沟与坡向纹理 -->')
    group('mount-fuji-ridges', 'clip-path="url(#clip-mountain)"')
    add('<polyline points="722,209 707,246 681,292 654,320 615,377" fill="none" stroke="#f0bea6" stroke-width="1.7" stroke-opacity=".42" stroke-linejoin="round"/>')
    for index in range(272):
        side = -1 if index % 2 == 0 else 1
        y1 = rng.uniform(230, 445)
        l1, r1 = mountain_bounds(y1)
        center = (l1 + r1) / 2
        half = (r1 - l1) / 2
        x1 = center + side * rng.uniform(half * .02, half * .34)
        y2 = rng.uniform(max(y1 + 48, 350), 674)
        l2, r2 = mountain_bounds(y2)
        target = rng.uniform(l2 + 10, 748) if side < 0 else rng.uniform(790, r2 - 10)
        bend = rng.uniform(18, 95) * side
        color = rng.choice(['#3a4560', '#4b536c', '#697087', '#8b747a']) if side > 0 else rng.choice(['#8f6c70', '#a77976', '#6f6174', '#d09a8d'])
        add(f'<path d="M {fmt(x1)} {fmt(y1)} C {fmt(x1 + bend*.18)} {fmt(y1 + (y2-y1)*.24)} {fmt(target - bend*.42)} {fmt(y1 + (y2-y1)*.68)} {fmt(target)} {fmt(y2)}" fill="none" stroke="{color}" stroke-width="{fmt(rng.uniform(.5, 1.95))}" stroke-opacity="{fmt(rng.uniform(.09, .33))}" stroke-linecap="round"/>')
    for index in range(188):
        y = rng.uniform(282, 625)
        left, right = mountain_bounds(y)
        x = rng.uniform(left + 8, right - 8)
        available = max(10, min(88, right - x - 4))
        width = rng.uniform(8, available)
        slant = rng.uniform(-12, 14)
        color = '#d6af9e' if x < 735 else rng.choice(['#394a67', '#56627c', '#746e82'])
        add(f'<path d="M {fmt(x)} {fmt(y)} C {fmt(x + width*.28)} {fmt(y + slant*.25)} {fmt(x + width*.67)} {fmt(y + slant*.82)} {fmt(x + width)} {fmt(y + slant)}" fill="none" stroke="{color}" stroke-width="{fmt(rng.uniform(.4, 1.45))}" stroke-opacity="{fmt(rng.uniform(.08, .30))}" stroke-linecap="round"/>')
    add('</g>')

    # 左坡暖光碎面和峰顶轮廓高光。
    add('<!-- 富士山光照：左暖右冷的方向性晨光 -->')
    group('mount-fuji-light', 'clip-path="url(#clip-mountain)"')
    add('<path d="M 716 213 C 697 252 682 290 655 332 C 590 435 510 531 357 612" fill="none" stroke="#ffe0bf" stroke-width="6" stroke-opacity=".52" stroke-linecap="round"/>')
    add('<path d="M 720 211 C 732 198 745 199 757 206 C 769 201 782 202 794 207 C 805 209 815 215 823 224" fill="none" stroke="#fff2d4" stroke-width="3.2" stroke-opacity=".72" stroke-linecap="round"/>')
    for index in range(98):
        y = rng.uniform(270, 606)
        left, right = mountain_bounds(y)
        x = rng.uniform(left + 4, min(770, right - 4))
        length = rng.uniform(12, 72)
        add(f'<path d="M {fmt(x)} {fmt(y)} C {fmt(x - length*.16)} {fmt(y + length*.16)} {fmt(x - length*.55)} {fmt(y + length*.52)} {fmt(x - length)} {fmt(y + length*.72)}" fill="none" stroke="{rng.choice(["#f2b79d", "#ffd2ae", "#e5a797"])}" stroke-width="{fmt(rng.uniform(.55, 1.7))}" stroke-opacity="{fmt(rng.uniform(.08, .25))}" stroke-linecap="round"/>')
    add('</g>')

    # 中景云海在山脚前形成体积遮挡。
    add('<!-- 中景云海：山腰暖顶冷底的体积云带 -->')
    group('cloud-sea-middle', 'filter="url(#filter-cloud-soft)"')
    for index in range(136):
        cx = rng.uniform(25, 1575)
        cy = rng.uniform(545, 666)
        width = rng.uniform(66, 176)
        height = rng.uniform(14, 38)
        fill = 'url(#cloud-top-light-gradient)' if index % 4 else 'url(#cloud-bottom-shadow-gradient)'
        add(f'<path d="{cloud_path(rng, cx, cy, width, height, rng.randint(5, 8))}" fill="{fill}" opacity="{fmt(rng.uniform(.18, .44))}"/>')
    add('</g>')

    # 湖水基础先于城市和岸线绘制。
    add('<!-- 湖面：冷色深度渐变与远细近宽的基础色带 -->')
    group('lake', 'clip-path="url(#clip-lake)"')
    add('<rect x="0" y="688" width="1600" height="312" fill="url(#lake-water-base-gradient)"/>')
    add('<rect x="0" y="690" width="1600" height="310" fill="url(#lake-reflection-gradient)" opacity=".24"/>')
    for index in range(86):
        y = 700 + index * 3.45 + rng.uniform(-1.5, 1.5)
        amp = rng.uniform(.5, 3.2)
        color = rng.choice(['#9ba7b6', '#536d88', '#284c69', '#c19282'])
        add(f'<path d="M 0 {fmt(y)} C 330 {fmt(y+amp)} 610 {fmt(y-amp)} 860 {fmt(y)} C 1110 {fmt(y+amp*.7)} 1360 {fmt(y-amp*.6)} 1600 {fmt(y+amp*.3)}" fill="none" stroke="{color}" stroke-width="{fmt(rng.uniform(.35, 1.5))}" stroke-opacity="{fmt(rng.uniform(.06, .19))}"/>')
    add('</g>')

    # 城市记录先生成，确保立面、窗户与倒影共享真实坐标。
    buildings: list[dict[str, float | str]] = []
    for row, (count, base_y, far) in enumerate(((58, 674, True), (91, 711, False))):
        row_rng = random.Random(SEED + 400 + row)
        x = 35 + row_rng.uniform(0, 12)
        for index in range(count):
            remaining = WIDTH - 35 - x
            if remaining < 10:
                break
            width = min(row_rng.uniform(12, 31) if far else row_rng.uniform(14, 36), remaining)
            kind = row_rng.choice(['residential', 'residential', 'hotel', 'commercial', 'warehouse'])
            if kind == 'hotel':
                height = row_rng.uniform(48, 98) if not far else row_rng.uniform(35, 67)
                width = min(width * .85, remaining)
            elif kind == 'warehouse':
                height = row_rng.uniform(17, 33)
                width = min(width * 1.34, remaining)
            else:
                height = row_rng.uniform(25, 65) if not far else row_rng.uniform(18, 43)
            base = base_y + 4 * math.sin((x + row * 70) / 95) + row_rng.uniform(-2.5, 2.5)
            buildings.append({'x': x, 'y': base - height, 'w': width, 'h': height, 'base': base, 'kind': kind, 'far': '1' if far else '0'})
            x += width + row_rng.uniform(2.5, 8)

    lit_windows: list[tuple[float, float, float, float, float]] = []
    add('<!-- 山脚城市：建筑服从两层地形基线，远淡近清 -->')
    group('distant-city', 'clip-path="url(#clip-city-band)"')
    add('<path d="M 0 669 C 280 652 528 674 774 660 C 1040 646 1270 659 1600 650 L 1600 720 L 0 720 Z" fill="url(#city-atmosphere-haze-gradient)" opacity=".48"/>')
    facade_palette = ['#536377', '#606979', '#756d78', '#657486', '#817477', '#465a70']
    roof_palette = ['#34495f', '#4f4c60', '#5a5262', '#2d465c']
    for index, building in enumerate(buildings):
        x = float(building['x'])
        y = float(building['y'])
        w = float(building['w'])
        h = float(building['h'])
        base = float(building['base'])
        kind = str(building['kind'])
        far = building['far'] == '1'
        opacity = rng.uniform(.42, .62) if far else rng.uniform(.68, .90)
        facade = rng.choice(facade_palette)
        roof = rng.choice(roof_palette)
        add(f'<g id="city-building-{index+1}">')
        if kind == 'residential':
            add(f'<rect x="{fmt(x)}" y="{fmt(y+5)}" width="{fmt(w)}" height="{fmt(h-5)}" rx="{fmt(rng.uniform(.3, 1.2))}" fill="{facade}" opacity="{fmt(opacity)}"/>')
            ridge = x + w * rng.uniform(.38, .62)
            add(f'<path d="M {fmt(x-1)} {fmt(y+6)} L {fmt(ridge)} {fmt(y-rng.uniform(3,10))} L {fmt(x+w+1)} {fmt(y+6)} Z" fill="{roof}" opacity="{fmt(min(1, opacity+.10))}"/>')
        elif kind == 'hotel':
            add(f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="1" fill="{facade}" opacity="{fmt(opacity)}"/>')
            add(f'<rect x="{fmt(x-1)}" y="{fmt(y-3)}" width="{fmt(w+2)}" height="4" fill="{roof}" opacity="{fmt(min(1, opacity+.12))}"/>')
            add(f'<path d="M {fmt(x+w*.18)} {fmt(y+6)} H {fmt(x+w*.82)}" stroke="#a49aa2" stroke-width="1" stroke-opacity=".36"/>')
        elif kind == 'commercial':
            add(f'<rect x="{fmt(x)}" y="{fmt(y+3)}" width="{fmt(w)}" height="{fmt(h-3)}" fill="{facade}" opacity="{fmt(opacity)}"/>')
            add(f'<rect x="{fmt(x-1)}" y="{fmt(y)}" width="{fmt(w+2)}" height="4" fill="{roof}" opacity="{fmt(min(1, opacity+.12))}"/>')
            add(f'<path d="M {fmt(x+1)} {fmt(y+h*.54)} H {fmt(x+w-1)}" stroke="#c0a69d" stroke-width="1.2" stroke-opacity=".32"/>')
        else:
            add(f'<path d="M {fmt(x)} {fmt(base)} L {fmt(x)} {fmt(y+7)} L {fmt(x+w*.38)} {fmt(y)} L {fmt(x+w)} {fmt(y+6)} L {fmt(x+w)} {fmt(base)} Z" fill="{facade}" opacity="{fmt(opacity)}"/>')
            add(f'<path d="M {fmt(x)} {fmt(y+7)} L {fmt(x+w*.38)} {fmt(y)} L {fmt(x+w)} {fmt(y+6)}" fill="none" stroke="{roof}" stroke-width="2" stroke-opacity="{fmt(min(1, opacity+.14))}"/>')
        cols = max(1, min(5, int(w / (5.4 if far else 6.2))))
        rows = max(1, min(7, int((h - 8) / (7.0 if far else 8.0))))
        pad_x = w * .13
        pad_y = 7 if kind != 'warehouse' else 9
        win_w = min(3.3, max(1.2, (w - 2 * pad_x) / max(cols, 1) * .44))
        win_h = 2.2 if far else rng.uniform(2.2, 3.8)
        for row in range(rows):
            for col in range(cols):
                wx = x + pad_x + col * ((w - 2 * pad_x) / max(cols, 1)) + rng.uniform(-.35, .35)
                wy = y + pad_y + row * ((h - pad_y - 4) / max(rows, 1)) + rng.uniform(-.3, .3)
                if wy + win_h >= base - 2:
                    continue
                if rng.random() < (.18 if far else .27):
                    lit_windows.append((wx, wy, win_w, win_h, rng.uniform(.45, .92)))
                else:
                    color = rng.choice(['#253b54', '#8a8d9a', '#b0a39f'])
                    add(f'<rect x="{fmt(wx)}" y="{fmt(wy)}" width="{fmt(win_w)}" height="{fmt(win_h)}" fill="{color}" opacity="{fmt(rng.uniform(.22, .50))}"/>')
        add('</g>')
    # 后排道路与基础设施把建筑固定在地形上。
    add('<path d="M 20 688 C 390 676 605 695 815 682 C 1060 669 1330 685 1580 674" fill="none" stroke="#283d51" stroke-width="8" stroke-opacity=".72"/>')
    add('<path d="M 20 686 C 390 674 605 693 815 680 C 1060 667 1330 683 1580 672" fill="none" stroke="#d2b69b" stroke-width="1.2" stroke-dasharray="18 13" stroke-opacity=".42"/>')
    add('<line x1="46" y1="640" x2="1554" y2="633" stroke="#394b5d" stroke-width=".7" stroke-opacity=".34"/>')
    for index in range(28):
        x = 58 + index * 55 + rng.uniform(-6, 6)
        y = 674 + 5 * math.sin(x / 95)
        add(f'<path d="M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y-22-rng.uniform(0,15))}" stroke="#304457" stroke-width="1.4" opacity=".72"/>')
        add(f'<path d="M {fmt(x-6)} {fmt(y-18-rng.uniform(0,12))} L {fmt(x+6)} {fmt(y-18-rng.uniform(0,12))}" stroke="#394c5d" stroke-width="1" opacity=".64"/>')
    add('</g>')

    # 克制暖黄窗灯，不让城市抢过雪峰。
    add('<!-- 城市灯光：不同尺寸和亮度的克制暖窗 -->')
    group('city-lights')
    for index, (x, y, w, h, opacity) in enumerate(lit_windows):
        add(f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx=".35" fill="url(#window-warm-light-gradient)" opacity="{fmt(opacity)}"/>')
        if index % 11 == 0:
            add(f'<path d="M {fmt(x-1.2)} {fmt(y+h/2)} H {fmt(x+w+1.2)}" stroke="#ffd792" stroke-width=".7" stroke-opacity=".24"/>')
    add('</g>')

    # 前景云海局部遮挡建筑下缘和山脚。
    add('<!-- 前景云海：清晰轮廓局部遮挡山脚与城市 -->')
    group('cloud-sea-front')
    for index in range(116):
        cx = rng.uniform(20, 1580)
        cy = rng.uniform(644, 710)
        width = rng.uniform(74, 194)
        height = rng.uniform(15, 40)
        if index % 5 == 0:
            fill = 'url(#cloud-bottom-shadow-gradient)'
            opacity = rng.uniform(.18, .36)
        else:
            fill = 'url(#cloud-top-light-gradient)'
            opacity = rng.uniform(.22, .46)
        add(f'<path d="{cloud_path(rng, cx, cy, width, height, rng.randint(5, 8))}" fill="{fill}" opacity="{fmt(opacity)}"/>')
    add('</g>')

    # 岸线、道路、桥梁、护栏、路灯、电线杆和芦苇。
    add('<!-- 岸线与基础设施：城市、道路和湖面之间的实体连接 -->')
    group('shoreline')
    add('<path d="M 0 700 C 215 690 402 708 602 698 C 811 688 1015 704 1220 696 C 1390 690 1518 699 1600 692 L 1600 725 C 1370 719 1130 729 900 721 C 640 713 350 730 0 719 Z" fill="#263f4a"/>')
    add('<path d="M 0 702 C 245 694 430 711 620 701 C 890 687 1115 711 1600 696" fill="none" stroke="#bc9a83" stroke-width="3" stroke-opacity=".55"/>')
    add('<path d="M 0 710 C 320 700 520 719 802 707 C 1065 696 1305 716 1600 704" fill="none" stroke="#142f3c" stroke-width="7" stroke-opacity=".88"/>')
    # 低桥和岸边通道。
    add('<path d="M 930 692 C 1045 682 1168 684 1284 695" fill="none" stroke="#4b5260" stroke-width="10"/>')
    add('<path d="M 928 687 C 1044 677 1169 679 1287 690" fill="none" stroke="#a89891" stroke-width="2"/>')
    for index in range(22):
        x = 942 + index * 15
        y = 687 + 4 * math.sin((x - 930) / 350 * math.pi)
        add(f'<path d="M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y+18+rng.uniform(-2,4))}" stroke="#2b3d4d" stroke-width="2" opacity=".84"/>')
    # 护栏随岸线曲线走向变化。
    for index in range(82):
        x = 18 + index * 19.25 + rng.uniform(-1.5, 1.5)
        y = 701 + 5.2 * math.sin(x / 128)
        add(f'<path d="M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y-8-rng.uniform(0,4))}" stroke="#78818c" stroke-width="1" stroke-opacity=".62"/>')
    add('<path d="M 15 694 C 310 684 540 704 808 691 C 1085 680 1315 701 1585 688" fill="none" stroke="#7f8993" stroke-width="1.3" stroke-opacity=".58"/>')
    # 路灯和少量暖光。
    for index in range(26):
        x = 48 + index * 60 + rng.uniform(-5, 5)
        y = 699 + 5 * math.sin(x / 130)
        pole_h = rng.uniform(18, 31)
        add(f'<path d="M {fmt(x)} {fmt(y)} L {fmt(x)} {fmt(y-pole_h)} Q {fmt(x+2)} {fmt(y-pole_h-4)} {fmt(x+7)} {fmt(y-pole_h-3)}" fill="none" stroke="#263846" stroke-width="1.5"/>')
        add(f'<circle cx="{fmt(x+7)}" cy="{fmt(y-pole_h-3)}" r="{fmt(rng.uniform(1.2,2.1))}" fill="#ffd287" opacity="{fmt(rng.uniform(.45,.78))}"/>')
    # 芦苇在近岸形成细碎的垂直节奏。
    for index in range(96):
        x = rng.uniform(0, 1600)
        base = 719 + rng.uniform(-2, 8)
        h = rng.uniform(5, 23)
        bend = rng.uniform(-4, 5)
        add(f'<path d="M {fmt(x)} {fmt(base)} Q {fmt(x+bend*.35)} {fmt(base-h*.55)} {fmt(x+bend)} {fmt(base-h)}" fill="none" stroke="{rng.choice(["#263d43", "#4a514e", "#6b6259"])}" stroke-width="{fmt(rng.uniform(.55,1.25))}" stroke-opacity="{fmt(rng.uniform(.45,.78))}"/>')
    add('</g>')

    # 反射：几何翻转基底叠加水平断裂，颜色偏移且逐渐衰减。
    add('<!-- 倒影：按 y\'=2H-y 翻转，并用分段水纹破坏完整性 -->')
    group('reflections', 'clip-path="url(#clip-lake)" mask="url(#mask-reflection-breakup)"')
    add(f'<path d="{MOUNTAIN_PATH}" transform="matrix(1 0 0 -1 0 {2*REFLECTION_AXIS})" fill="url(#mountain-reflection-gradient)" opacity=".13" filter="url(#filter-reflection-soft)"/>')
    add(f'<path d="{SNOW_CAP_PATH}" transform="matrix(1 0 0 -1 0 {2*REFLECTION_AXIS})" fill="#9aa6ba" opacity=".09" filter="url(#filter-reflection-soft)"/>')
    # 山体和雪面被波纹切成不同长度的冷暖碎片。
    for index in range(292):
        y = rng.uniform(704, 997)
        source_y = 2 * REFLECTION_AXIS - y
        left, right = mountain_bounds(source_y)
        if right <= 0 or left >= WIDTH:
            continue
        left = clamp(left, 0, WIDTH)
        right = clamp(right, 0, WIDTH)
        span = max(12, right - left)
        seg_w = rng.uniform(span * .05, span * .28)
        x = rng.uniform(left, max(left, right - seg_w))
        curve = rng.uniform(-2.2, 2.2)
        color = rng.choice(['#8e8291', '#687993', '#b58d86', '#4e6683', '#a9a7b5'])
        opacity = rng.uniform(.07, .24) * (1 - (y - 704) / 540)
        add(f'<path d="M {fmt(x)} {fmt(y)} Q {fmt(x+seg_w*.48)} {fmt(y+curve)} {fmt(x+seg_w)} {fmt(y+curve*.18)}" fill="none" stroke="{color}" stroke-width="{fmt(rng.uniform(.6,2.2))}" stroke-opacity="{fmt(max(.06,opacity))}" stroke-linecap="round"/>')
    # 云反射保留低频大形。
    for index in range(76):
        y = rng.uniform(710, 875)
        width = rng.uniform(55, 220)
        x = rng.uniform(0, WIDTH - width)
        add(f'<path d="M {fmt(x)} {fmt(y)} C {fmt(x+width*.28)} {fmt(y+rng.uniform(-3,3))} {fmt(x+width*.72)} {fmt(y+rng.uniform(-3,3))} {fmt(x+width)} {fmt(y+rng.uniform(-1,1))}" fill="none" stroke="{rng.choice(["#a8a2b0", "#7e899f", "#c0a79f"])}" stroke-width="{fmt(rng.uniform(2.2,6.5))}" stroke-opacity="{fmt(rng.uniform(.06,.16))}" stroke-linecap="round"/>')
    # 太阳纵向碎光严格位于左侧光源下方。
    for index in range(94):
        y = 704 + index * 3.05 + rng.uniform(-1.3, 1.3)
        spread = 12 + (y - 704) * .20
        x = 270 + rng.uniform(-spread, spread)
        width = rng.uniform(5, 20 + (y - 704) * .09)
        add(f'<path d="M {fmt(x-width/2)} {fmt(y)} Q {fmt(x)} {fmt(y+rng.uniform(-1.5,1.5))} {fmt(x+width/2)} {fmt(y)}" fill="none" stroke="url(#sun-track-reflect-gradient)" stroke-width="{fmt(rng.uniform(.7,2.8))}" stroke-opacity="{fmt(rng.uniform(.18,.56))}" stroke-linecap="round"/>')
    # 实际亮窗坐标生成短小、不规则的城市灯光反射。
    for index, (x, _y, w, _h, opacity) in enumerate(lit_windows[:132]):
        start = 711 + rng.uniform(0, 7)
        length = rng.uniform(5, 22)
        add(f'<path d="M {fmt(x+w/2)} {fmt(start)} C {fmt(x+w/2+rng.uniform(-1.5,1.5))} {fmt(start+length*.35)} {fmt(x+w/2+rng.uniform(-2,2))} {fmt(start+length*.72)} {fmt(x+w/2+rng.uniform(-1,1))} {fmt(start+length)}" fill="none" stroke="#f4b76f" stroke-width="{fmt(rng.uniform(.5,1.5))}" stroke-opacity="{fmt(opacity*.34)}" stroke-linecap="round"/>')
    add('</g>')

    # 远处细密、近处宽阔的水平水纹。
    add('<!-- 水面波纹：透视控制长度、间距、线宽和对比 -->')
    group('water-ripples', 'clip-path="url(#clip-lake)"')
    ripple_bands = [(260, 704, 792), (230, 790, 894), (220, 890, 998)]
    for band_index, (count, y_min, y_max) in enumerate(ripple_bands):
        band_rng = random.Random(SEED + 700 + band_index)
        for index in range(count):
            y = band_rng.uniform(y_min, y_max)
            depth = (y - LAKE_TOP) / (HEIGHT - LAKE_TOP)
            length = band_rng.uniform(12 + depth * 24, 48 + depth * 126)
            x = band_rng.uniform(0, WIDTH - length)
            curve = band_rng.uniform(-1.6, 1.6) * (0.45 + depth)
            color = band_rng.choice(['#a8b0bb', '#6f849b', '#294d69', '#d0aa92', '#173b55'])
            stroke = band_rng.uniform(.35 + depth * .22, .78 + depth * 1.15)
            opacity = band_rng.uniform(.07, .30 + depth * .11)
            add(f'<path d="M {fmt(x)} {fmt(y)} C {fmt(x+length*.28)} {fmt(y+curve)} {fmt(x+length*.68)} {fmt(y-curve*.65)} {fmt(x+length)} {fmt(y+curve*.12)}" fill="none" stroke="{color}" stroke-width="{fmt(stroke)}" stroke-opacity="{fmt(opacity)}" stroke-linecap="round"/>')
    add('</g>')

    # 前景树林在两侧和底边建立深色框景，中央保持低矮。
    add('<!-- 前景树林：深蓝绿岸林、树干和受光边缘 -->')
    group('foreground-forest')
    add('<path d="M 0 947 C 210 925 375 972 566 956 C 790 938 1010 974 1210 951 C 1380 932 1495 923 1600 934 L 1600 1000 L 0 1000 Z" fill="url(#forest-tree-depth-gradient)"/>')
    tree_specs: list[tuple[float, float, float, float, float]] = []
    tree_rng = random.Random(SEED + 880)
    # 后景岸林较矮且横贯画面。
    for index in range(112):
        x = 4 + index * 14.25 + tree_rng.uniform(-4, 4)
        base = 724 + tree_rng.uniform(-2, 9)
        height = tree_rng.uniform(13, 31)
        width = tree_rng.uniform(7, 15)
        tree_specs.append((x, base, height, width, tree_rng.uniform(.42, .70)))
    # 左右近景树更高，中央下缘只留低矮轮廓。
    for index in range(118):
        side = -1 if index % 2 == 0 else 1
        if side < 0:
            x = tree_rng.uniform(0, 350)
        else:
            x = tree_rng.uniform(1245, 1600)
        base = 1004 + tree_rng.uniform(-6, 4)
        center_factor = min(abs(x - 800) / 800, 1)
        height = tree_rng.uniform(48, 105 + 78 * center_factor)
        width = height * tree_rng.uniform(.24, .38)
        tree_specs.append((x, base, height, width, tree_rng.uniform(.74, .98)))
    for index in range(78):
        x = 8 + index * 20.5 + tree_rng.uniform(-6, 6)
        base = 1006
        height = tree_rng.uniform(22, 58) * (1 + .38 * abs(x - 800) / 800)
        width = height * tree_rng.uniform(.28, .42)
        tree_specs.append((x, base, height, width, tree_rng.uniform(.68, .94)))
    for index, (x, base, height, width, opacity) in enumerate(tree_specs):
        trunk_color = '#102a33' if base > 800 else '#29434a'
        foliage = 'url(#forest-tree-depth-gradient)' if base > 800 else rng.choice(['#294653', '#304d55', '#3b5359'])
        add(f'<path d="M {fmt(x-width*.07)} {fmt(base)} L {fmt(x-width*.035)} {fmt(base-height*.72)} L {fmt(x+width*.035)} {fmt(base-height*.72)} L {fmt(x+width*.08)} {fmt(base)} Z" fill="{trunk_color}" opacity="{fmt(opacity)}"/>')
        add(f'<path d="{tree_foliage_path(tree_rng, x, base, height, width)}" fill="{foliage}" opacity="{fmt(opacity)}"/>')
        if index % 3 == 0:
            add(f'<path d="M {fmt(x-width*.08)} {fmt(base-height*.84)} L {fmt(x-width*.34)} {fmt(base-height*.48)}" fill="none" stroke="#b58c77" stroke-width="{fmt(max(.45,height*.009))}" stroke-opacity="{fmt(.12 + .12*(1-opacity))}"/>')
    add('</g>')

    # 局部薄雾、光束和少量鸟群统一空间但不洗平画面。
    add('<!-- 最终大气：局部雾带、斜向光束和微小远鸟 -->')
    group('final-atmosphere')
    add('<path d="M 0 560 C 360 526 610 596 884 561 C 1130 530 1370 568 1600 548 L 1600 726 C 1290 744 1070 706 785 735 C 510 763 250 712 0 742 Z" fill="url(#foreground-mist-gradient)" opacity=".46"/>')
    for index in range(18):
        y = 548 + index * 9.2 + rng.uniform(-2, 2)
        add(f'<path d="M 0 {fmt(y)} C 420 {fmt(y+rng.uniform(-8,8))} 980 {fmt(y+rng.uniform(-8,8))} 1600 {fmt(y+rng.uniform(-4,4))}" fill="none" stroke="{rng.choice(["#e8c8bd", "#b8b3c2", "#94a2b8"])}" stroke-width="{fmt(rng.uniform(1.4,5.2))}" stroke-opacity="{fmt(rng.uniform(.035,.10))}"/>')
    for index in range(12):
        x1 = 285 + index * 18 + rng.uniform(-8, 8)
        x2 = 610 + index * 58 + rng.uniform(-20, 20)
        add(f'<path d="M {fmt(x1)} 270 L {fmt(x2)} 690" stroke="#ffd9b2" stroke-width="{fmt(rng.uniform(2,8))}" stroke-opacity="{fmt(rng.uniform(.025,.075))}"/>')
    for index in range(22):
        x = rng.uniform(900, 1470)
        y = rng.uniform(315, 510)
        wing = rng.uniform(3, 7)
        add(f'<path d="M {fmt(x-wing)} {fmt(y+1)} Q {fmt(x-wing*.42)} {fmt(y-2)} {fmt(x)} {fmt(y)} Q {fmt(x+wing*.44)} {fmt(y-2.4)} {fmt(x+wing)} {fmt(y+.6)}" fill="none" stroke="#40506a" stroke-width="{fmt(rng.uniform(.55,1.15))}" stroke-opacity="{fmt(rng.uniform(.28,.55))}" stroke-linecap="round"/>')
    add('</g>')
    add('</svg>')

    svg_text = "\n".join(lines) + "\n"
    OUTPUT.write_text(svg_text, encoding="utf-8")

    element_pattern = re.compile(r"<([A-Za-z][A-Za-z0-9:_-]*)(?:\s|/?>)")
    counts = Counter(match.group(1) for match in element_pattern.finditer(svg_text))
    element_total = sum(count for tag, count in counts.items() if tag not in {'svg', 'title', 'desc', 'metadata', 'defs'})
    print(f"已生成: {OUTPUT}")
    print(f"随机种子: {SEED}")
    print(f"总行数: {len(lines)}")
    print(f"文件大小: {OUTPUT.stat().st_size} bytes")
    print(f"SVG 元素数（不含根/标题/描述/defs）: {element_total}")
    print("元素类型: " + ", ".join(f"{tag}={count}" for tag, count in sorted(counts.items())))


if __name__ == "__main__":
    main()
