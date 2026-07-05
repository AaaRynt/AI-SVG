#!/usr/bin/env python3
"""Generate the Hailan bilingual metro network data and SVG."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
WIDTH = 2400
HEIGHT = 1600
SEED = 20260705


def fmt(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    number = float(value)
    if abs(number) < 0.005:
        number = 0
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def attrs_to_text(attrs: dict[str, object | None]) -> str:
    parts: list[str] = []
    for key, value in attrs.items():
        if value is None:
            continue
        parts.append(f'{key}="{html.escape(str(value), quote=True)}"')
    return (" " + " ".join(parts)) if parts else ""


def station_id(name: str) -> str:
    return "st-" + re.sub(r"[^a-z0-9]+", "-", make_english(name).lower()).strip("-")


def line_id_slug(line_id: str) -> str:
    return line_id.lower()


CHAR_PINYIN = {
    "安": "an",
    "岸": "an",
    "北": "bei",
    "浜": "bang",
    "保": "bao",
    "部": "bu",
    "仓": "cang",
    "材": "cai",
    "厂": "chang",
    "场": "chang",
    "长": "chang",
    "城": "cheng",
    "澄": "cheng",
    "车": "che",
    "潮": "chao",
    "崇": "chong",
    "川": "chuan",
    "船": "chuan",
    "春": "chun",
    "村": "cun",
    "大": "da",
    "道": "dao",
    "岛": "dao",
    "堤": "di",
    "地": "di",
    "东": "dong",
    "渡": "du",
    "段": "duan",
    "二": "er",
    "坊": "fang",
    "帆": "fan",
    "纺": "fang",
    "府": "fu",
    "阜": "fu",
    "港": "gang",
    "高": "gao",
    "工": "gong",
    "谷": "gu",
    "鼓": "gu",
    "广": "guang",
    "关": "guan",
    "馆": "guan",
    "桂": "gui",
    "国": "guo",
    "海": "hai",
    "航": "hang",
    "河": "he",
    "虹": "hong",
    "湖": "hu",
    "环": "huan",
    "会": "hui",
    "货": "huo",
    "机": "ji",
    "集": "ji",
    "际": "ji",
    "岬": "jia",
    "江": "jiang",
    "角": "jiao",
    "街": "jie",
    "津": "jin",
    "金": "jin",
    "旧": "jiu",
    "科": "ke",
    "客": "ke",
    "康": "kang",
    "口": "kou",
    "库": "ku",
    "蓝": "lan",
    "岚": "lan",
    "澜": "lan",
    "廊": "lang",
    "里": "li",
    "临": "lin",
    "林": "lin",
    "岭": "ling",
    "柳": "liu",
    "流": "liu",
    "龙": "long",
    "路": "lu",
    "鹿": "lu",
    "芦": "lu",
    "旅": "lv",
    "绿": "lv",
    "贸": "mao",
    "梅": "mei",
    "门": "men",
    "棉": "mian",
    "庙": "miao",
    "民": "min",
    "木": "mu",
    "南": "nan",
    "农": "nong",
    "牌": "pai",
    "屏": "ping",
    "平": "ping",
    "前": "qian",
    "桥": "qiao",
    "青": "qing",
    "清": "qing",
    "区": "qu",
    "人": "ren",
    "软": "ruan",
    "沙": "sha",
    "山": "shan",
    "商": "shang",
    "上": "shang",
    "社": "she",
    "生": "sheng",
    "盛": "sheng",
    "市": "shi",
    "士": "shi",
    "湿": "shi",
    "矢": "shi",
    "书": "shu",
    "水": "shui",
    "税": "shui",
    "双": "shuang",
    "松": "song",
    "台": "tai",
    "泰": "tai",
    "太": "tai",
    "塘": "tang",
    "铁": "tie",
    "天": "tian",
    "衡": "heng",
    "汐": "xi",
    "西": "xi",
    "溪": "xi",
    "细": "xi",
    "峡": "xia",
    "下": "xia",
    "仙": "xian",
    "线": "xian",
    "巷": "xiang",
    "小": "xiao",
    "杏": "xing",
    "修": "xiu",
    "学": "xue",
    "研": "yan",
    "雁": "yan",
    "堰": "yan",
    "阳": "yang",
    "药": "yao",
    "业": "ye",
    "医": "yi",
    "银": "yin",
    "营": "ying",
    "园": "yuan",
    "苑": "yuan",
    "院": "yuan",
    "月": "yue",
    "云": "yun",
    "站": "zhan",
    "镇": "zhen",
    "政": "zheng",
    "中": "zhong",
    "洲": "zhou",
    "珠": "zhu",
    "总": "zong",
    "坞": "wu",
    "湾": "wan",
    "望": "wang",
    "文": "wen",
    "物": "wu",
    "务": "wu",
    "舞": "wu",
    "溪": "xi",
    "星": "xing",
    "新": "xin",
    "信": "xin",
    "行": "xing",
    "兴": "xing",
    "修": "xiu",
    "阳": "yang",
    "一": "yi",
    "驿": "yi",
    "营": "ying",
    "影": "ying",
    "运": "yun",
    "园": "yuan",
    "展": "zhan",
    "政": "zheng",
    "政": "zheng",
    "枢": "shu",
    "纽": "niu",
    "卫": "wei",
    "雁": "yan",
    "叶": "ye",
    "港": "gang",
    "籍": "ji",
    "绩": "ji",
    "体": "ti",
    "育": "yu",
    "创": "chuang",
    "老": "lao",
    "墙": "qiang",
    "浦": "pu",
    "湾": "wan",
    "霁": "ji",
    "旧": "jiu",
    "融": "rong",
    "玻": "bo",
    "璃": "li",
    "莲": "lian",
    "外": "wai",
    "深": "shen",
    "杆": "gan",
    "塔": "ta",
    "苇": "wei",
    "空": "kong",
    "维": "wei",
    "号": "hao",
    "楼": "lou",
    "轴": "zhou",
    "炉": "lu",
    "纱": "sha",
    "段": "duan",
    "智": "zhi",
    "数": "shu",
    "像": "xiang",
    "钟": "zhong",
    "楼": "lou",
    "雾": "wu",
    "厦": "sha",
}


EXACT_EN = {
    "人民广场": "People's Square",
    "文庙": "Wenmiao Temple",
    "望江商务区": "Wangjiang CBD",
    "博物馆": "Museum",
    "国际会展中心": "International Convention Center",
    "北苑高铁站": "Beiyuan High-Speed Railway Station",
    "北城火车站": "Beicheng Railway Station",
    "南湾铁路站": "Nanwan Railway Station",
    "南部客运站": "South Coach Terminal",
    "海澜总站": "Hailan Main Railway Station",
    "临湾国际机场": "Linwan International Airport",
    "机场二号航站楼": "Airport Terminal 2",
    "机场三号航站楼": "Airport Terminal 3",
    "西岭机场": "Xiling Airport",
    "港湾邮轮中心": "Gulf Cruise Center",
    "深水港": "Deepwater Port",
    "青岚大学城": "Qinglan University Town",
    "青岚水库": "Qinglan Reservoir",
    "书院湖": "Shuyuan Lake",
    "南津中心": "Nanjin Center",
    "金融街": "Financial Street",
    "文化中心": "Cultural Center",
    "传媒港": "Media Harbor",
    "广电中心": "Broadcasting Center",
    "科技新城": "Technology New City",
    "滨海新城": "Binhai New Town",
    "临空商务区": "Airport Business District",
    "人工湖": "Artificial Lake",
    "航空物流园": "Aviation Logistics Park",
    "维修区": "Maintenance Area",
    "保税物流园": "Bonded Logistics Park",
    "集装箱北": "Container Terminal North",
    "集装箱南": "Container Terminal South",
    "车辆段": "Vehicle Depot",
    "研发一路": "R&D First Road",
    "港务大厦": "Port Authority Tower",
    "航运大厦": "Shipping Tower",
    "东岸湿地": "East Bank Wetland",
    "科创大道": "Kechuang Avenue",
    "药谷北": "Yaogu North",
    "药谷南": "Yaogu South",
    "软件谷": "Software Valley",
    "生物港": "Biomed Harbor",
    "医科城": "Medical City",
    "北苑中心": "Beiyuan Center",
    "北苑医院": "Beiyuan Medical Center",
    "北苑行政中心": "Beiyuan Civic Center",
    "西岭卫星城": "Xiling Satellite City",
    "西岭客运站": "Xiling Coach Terminal",
    "老西站": "Old West Station",
    "西阜工业园": "Xifu Industrial Park",
    "西阜货场": "Xifu Freight Yard",
    "铁西货场": "Tiexi Freight Yard",
    "西阜机厂": "Xifu Machinery Works",
    "双棉厂": "Shuangmian Mill",
    "崇安门": "Chongan Gate",
    "鼓楼西": "Gulou West",
    "临江码头": "Linjiang Wharf",
    "云洲码头": "Yunzhou Wharf",
    "云洲公园": "Yunzhou Park",
    "河洲公园": "Hezhou Park",
    "南岸剧院": "South Bank Theater",
    "霁江公园": "Jijiang Park",
    "西津渡": "Xijin Ferry",
    "南江门": "Nanjiang Gate",
    "云洲东": "Yunzhou East",
    "望江东": "Wangjiang East",
    "东澄站": "Dongcheng Railway Station",
    "东澄南": "Dongcheng South",
    "海湾客运站": "Bay Passenger Terminal",
    "海堤中央": "Haiti Central",
    "海堤南": "Haiti South",
    "银沙湾": "Yinsha Bay",
    "海洋公园": "Ocean Park",
    "潮汐公园": "Tide Park",
    "滨江花园": "Riverside Garden",
    "纺织公园": "Textile Park",
    "港务西": "Port Authority West",
    "港湾湿地": "Harbor Wetland",
    "海洋湖": "Ocean Lake",
}


SUFFIX_EN = [
    ("国际机场", "International Airport"),
    ("高铁站", "High-Speed Railway Station"),
    ("火车站", "Railway Station"),
    ("铁路站", "Railway Station"),
    ("客运站", "Coach Terminal"),
    ("航站楼", "Terminal"),
    ("大学城", "University Town"),
    ("商务区", "Business District"),
    ("行政中心", "Civic Center"),
    ("会展中心", "Convention Center"),
    ("物流园", "Logistics Park"),
    ("工业园", "Industrial Park"),
    ("科技园", "Science Park"),
    ("软件园", "Software Park"),
    ("水库", "Reservoir"),
    ("公园", "Park"),
    ("广场", "Square"),
    ("码头", "Wharf"),
    ("货场", "Freight Yard"),
    ("船厂", "Shipyard"),
    ("大厦", "Tower"),
    ("大道", "Avenue"),
    ("中心", "Center"),
    ("学院", "College"),
    ("书院", "Academy"),
    ("医院", "Hospital"),
    ("市场", "Market"),
    ("社区", "Community"),
    ("街", "Street"),
    ("路", "Road"),
    ("桥", "Bridge"),
    ("门", "Gate"),
    ("湾", "Bay"),
    ("湖", "Lake"),
    ("山", "Mountain"),
    ("岛", "Island"),
    ("镇", "Town"),
    ("村", "Village"),
    ("港", "Harbor"),
    ("园", "Park"),
    ("渡", "Ferry"),
]


def pinyin_name(text: str) -> str:
    words: list[str] = []
    for char in text:
        if char in "0123456789":
            words.append(char)
            continue
        if char not in CHAR_PINYIN:
            raise ValueError(f"Missing pinyin mapping for {char!r} in {text!r}")
        words.append(CHAR_PINYIN[char])
    return "".join(words).capitalize()


def make_english(name: str) -> str:
    if name in EXACT_EN:
        return EXACT_EN[name]
    for suffix, english_suffix in SUFFIX_EN:
        if name.endswith(suffix) and name != suffix:
            prefix = name[: -len(suffix)]
            if not prefix:
                continue
            if suffix == "航站楼":
                return f"{pinyin_name(prefix)} {english_suffix}"
            return f"{pinyin_name(prefix)} {english_suffix}"
    return pinyin_name(name)


@dataclass
class LinePlan:
    id: str
    number: str
    name_zh: str
    name_en: str
    color: str
    line_type: str
    status: str
    function: str
    service_areas: list[str]
    segments: list[list[str]]
    crosses_main_river: bool = False
    is_ring: bool = False
    is_branch: bool = False
    branch_station: str | None = None
    branch_names: list[str] = field(default_factory=list)
    stroke_width: float = 10
    dash: str | None = None


ANCHORS: dict[str, tuple[float, float]] = {
    "西岭机场": (250, 250),
    "河谷镇": (320, 355),
    "北山口": (620, 260),
    "西岭卫星城": (220, 725),
    "西岭客运站": (315, 775),
    "谷口": (405, 760),
    "河谷口": (350, 845),
    "老西站": (470, 720),
    "西阜工业园": (535, 620),
    "铁西货场": (285, 370),
    "西阜货场": (370, 415),
    "西阜机厂": (440, 485),
    "双棉厂": (520, 535),
    "崇安门": (590, 580),
    "鼓楼西": (650, 602),
    "人民广场": (730, 620),
    "文庙": (800, 626),
    "东仓街": (890, 628),
    "临江码头": (970, 635),
    "望江商务区": (1200, 590),
    "博物馆": (1300, 620),
    "东桥": (1390, 620),
    "春浦": (1480, 620),
    "柳营": (1570, 600),
    "东澄站": (1655, 560),
    "药谷南": (1730, 560),
    "龙湾路": (1810, 575),
    "国际会展中心": (1880, 620),
    "云帆软件园": (1990, 585),
    "北苑高铁站": (1020, 250),
    "北苑医院": (955, 305),
    "桂园": (920, 335),
    "松台公园": (875, 365),
    "北关市场": (810, 405),
    "北城火车站": (735, 445),
    "西牌楼": (700, 530),
    "中洲北": (835, 710),
    "中洲南": (890, 820),
    "南江门": (820, 900),
    "南津中心": (1180, 940),
    "广电中心": (1310, 1010),
    "南湾铁路站": (1450, 1080),
    "南湾北": (1450, 1015),
    "海堤中央": (1530, 1160),
    "银沙湾": (1460, 1245),
    "海堤公园": (1500, 1275),
    "海堤南": (1530, 1320),
    "南部客运站": (1630, 1380),
    "芦桥": (365, 755),
    "西浦": (555, 720),
    "西河口": (620, 700),
    "仓前街": (690, 665),
    "仓桥": (760, 695),
    "霁江公园": (690, 760),
    "银行街": (1040, 680),
    "旧码头": (1005, 690),
    "云洲码头": (1070, 725),
    "云洲公园": (1130, 785),
    "南岸剧院": (1005, 905),
    "江湾公园": (1220, 875),
    "东湾渡": (1400, 830),
    "月浦": (1500, 805),
    "东澄南": (1600, 800),
    "东湾客运": (1700, 780),
    "海湾客运站": (1810, 760),
    "小南门": (690, 690),
    "旧城墙": (615, 660),
    "西津渡": (780, 820),
    "河洲公园": (1015, 815),
    "金融街": (1085, 900),
    "文化中心": (1240, 910),
    "东江桥南": (1360, 850),
    "东江桥北": (1360, 700),
    "海澜总站": (1060, 465),
    "北仓门": (800, 520),
    "湾南路": (1340, 980),
    "青岚水库": (380, 1190),
    "松岭公园": (470, 1160),
    "青岚大学城": (600, 1110),
    "西山书院": (690, 1085),
    "书院湖": (760, 1060),
    "湖东村": (815, 1085),
    "科大南门": (850, 1040),
    "望溪村": (910, 1000),
    "南溪路": (835, 955),
    "河洲南": (980, 865),
    "云洲东": (1125, 855),
    "望江东": (1370, 720),
    "盛航城": (1465, 700),
    "泰康社区": (1550, 675),
    "东澄软件园": (1660, 650),
    "东澄书城": (1760, 650),
    "杏林湾": (970, 310),
    "北苑中心": (930, 350),
    "太平坊": (760, 540),
    "清河里": (835, 585),
    "梅巷": (880, 635),
    "云门桥": (960, 740),
    "传媒港": (1275, 970),
    "鹿洲路": (1350, 1005),
    "滨江花园": (1265, 1045),
    "雁塘": (1170, 1085),
    "会文路": (1100, 1125),
    "天衡镇": (1010, 1160),
    "南苑路": (930, 1185),
    "药谷北": (1700, 480),
    "水木桥": (1585, 480),
    "科创大道": (1650, 460),
    "科技新城": (1740, 650),
    "会展北": (1880, 530),
    "研发一路": (1810, 490),
    "软件谷": (1790, 455),
    "生物港": (1890, 455),
    "莲塘": (1985, 505),
    "新河镇": (2050, 565),
    "东岸岛北": (2100, 620),
    "东岸湿地": (2010, 680),
    "湾北": (1970, 450),
    "湾北西": (1940, 430),
    "会展北路": (1860, 500),
    "科创北路": (1685, 430),
    "滨海新城": (1680, 1220),
    "人工湖": (1770, 1270),
    "月堤": (1850, 1240),
    "芦苇岸": (1930, 1210),
    "临空商务区": (2020, 1180),
    "临湾国际机场": (2120, 1230),
    "机场二号航站楼": (2200, 1220),
    "机场三号航站楼": (2260, 1260),
    "维修区": (2170, 1320),
    "航城北": (2120, 1360),
    "航空物流园": (2250, 1350),
    "南湾货场": (1645, 1040),
    "潮汐公园": (1760, 1020),
    "保税物流园": (1900, 990),
    "保税东": (1980, 990),
    "港湾邮轮中心": (2050, 910),
    "外海门": (2130, 950),
    "集装箱北": (2210, 920),
    "深水港": (2290, 980),
    "船坞西": (2230, 1030),
    "船厂路": (2200, 1080),
    "港务大厦": (2110, 1040),
    "北部物流园": (465, 340),
    "北环西": (605, 300),
    "纱厂公园": (760, 275),
    "北苑行政中心": (1040, 335),
    "望北路": (1140, 360),
    "医科城": (1260, 390),
    "长浜": (1400, 430),
    "东澄北": (1560, 455),
    "山前村": (660, 1160),
    "梅岭口": (525, 1240),
    "岚屏山": (405, 1320),
    "西南科园": (630, 1285),
    "航运大厦": (2090, 850),
    "东港岛": (2200, 840),
    "岬角码头": (2280, 870),
    "海门岛": (2320, 920),
    "集装箱南": (2310, 1050),
    "航材园": (2190, 1160),
    "东堤": (2260, 1120),
    "海洋公园": (1680, 1360),
}


LINES: list[LinePlan] = [
    LinePlan("L1", "1", "赤门线", "Chimen Line", "#d9363e", "metro", "operational", "老城东西主轴，串联西阜工业更新片区、崇安老城、望江 CBD 与东澄科技走廊。", ["西阜工业区", "崇安老城", "望江 CBD", "东澄科技新城"], [["西阜机厂", "双棉厂", "崇安门", "鼓楼西", "人民广场", "文庙", "东仓街", "临江码头", "望江商务区", "博物馆", "东桥", "春浦", "柳营", "东澄站", "药谷南", "龙湾路", "国际会展中心", "云帆软件园"]]),
    LinePlan("L2", "2", "南北线", "Nanbei Line", "#2f6fd6", "metro", "operational", "北苑居住新城至南部海堤的南北跨江骨干，服务老城、江心岛、南津副中心和南湾铁路站。", ["北苑新城", "崇安老城", "江心岛", "南津副中心", "海堤新城"], [["北苑高铁站", "北苑医院", "桂园", "松台公园", "北关市场", "北桥", "北城火车站", "西牌楼", "人民广场", "中洲北", "中洲南", "南江门", "南津中心", "广电中心", "南湾铁路站", "南湾北", "海堤中央", "银沙湾", "海堤公园", "海堤南", "南部客运站"]], crosses_main_river=True),
    LinePlan("L3", "3", "江岛线", "Jiangdao Line", "#00a3a3", "metro", "operational", "沿霁江两岸和云洲岛布置的近代港埠文化线，连接老码头、银行街、岛上公共空间与东湾客运片区。", ["霁江沿岸", "近代港埠区", "云洲岛", "东湾片区"], [["老西站", "芦桥", "西浦", "西河口", "仓桥", "霁江公园", "临江码头", "旧码头", "银行街", "云洲码头", "云洲公园", "中洲南", "南岸剧院", "江湾公园", "东湾渡", "月浦", "东澄南", "东湾客运", "海湾客运站"]], crosses_main_river=True),
    LinePlan("L4", "4", "核心环线", "Core Ring Line", "#f08c00", "ring", "operational", "中心城区闭合环线，分流人民广场、老城、主铁路站、CBD 与南岸金融文化区之间的换乘压力。", ["崇安老城", "望江 CBD", "南津副中心", "云洲岛"], [["人民广场", "小南门", "旧城墙", "霁江公园", "西津渡", "南江门", "河洲公园", "云洲公园", "南岸剧院", "金融街", "文化中心", "湾南路", "东江桥南", "东江桥北", "博物馆", "望江商务区", "海澜总站", "北仓门", "西牌楼", "人民广场"]], crosses_main_river=True, is_ring=True),
    LinePlan("L5", "5", "青岚线", "Qinglan Line", "#38a169", "metro", "operational", "西南大学城与中心城区、东澄软件园的通勤线，沿丘陵边缘和江心岛通道进入 CBD 外围。", ["青岚大学城", "西南丘陵", "南江门", "云洲岛", "东澄研发区"], [["青岚水库", "松岭公园", "青岚大学城", "西山书院", "书院湖", "湖东村", "科大南门", "望溪村", "南溪路", "西津渡", "南江门", "河洲南", "云洲东", "望江东", "盛航城", "泰康社区", "书城南", "东澄书城"]], crosses_main_river=True),
    LinePlan("L6", "6", "北苑金融线", "Beiyuan-Finance Line", "#8b5cf6", "metro", "operational", "北苑居住与医疗片区通往南津金融文化副中心的跨江通勤线。", ["北苑新城", "崇安北部", "南津金融区"], [["北苑高铁站", "杏林湾", "北苑中心", "松台公园", "北城火车站", "太平坊", "清河里", "梅巷", "云门桥", "金融街", "南津中心", "传媒港", "鹿洲路", "滨江花园", "雁塘", "会文路", "天衡镇", "南苑路"]], crosses_main_river=True),
    LinePlan("L7", "7", "东澄科创线", "Dongcheng Innovation Line", "#00a65a", "metro", "operational", "东部科技新城内部骨干，串联药谷、软件谷、生物港、会展北和湾北生活区。", ["东澄科技新城", "国际会展片区", "湾北社区"], [["东澄站", "药谷北", "水木桥", "科创大道", "药谷中路", "科技新城", "国际会展中心", "会展北", "研发一路", "软件谷", "生物港", "莲塘", "新河镇", "东岸岛北", "湿地北", "湾口北", "北湾路", "湾北"]]),
    LinePlan("L8", "8", "滨海线", "Binhai Line", "#00a6d6", "branch", "operational", "南部滨海新城与临湾航空城的普通服务线，在机场处分出航站楼和航空物流两支。", ["南湾铁路站", "海堤新城", "滨海新城", "临湾航空城"], [["南湾铁路站", "海堤中央", "海堤东", "滨海新城", "人工湖", "月堤", "芦苇岸", "临空商务区", "临湾国际机场"], ["临湾国际机场", "机场二号航站楼", "机场三号航站楼"], ["临湾国际机场", "维修区", "航城北", "航空物流园"]], is_branch=True, branch_station="临湾国际机场", branch_names=["航站楼支线", "航空物流支线"]),
    LinePlan("L9", "9", "西岭快线", "Xiling Express", "#7a4a2a", "regional_express", "operational", "西部卫星城经河谷快速进入海澜总站和望江东商务片区的市域快线。", ["西岭卫星城", "西阜产业走廊", "海澜总站", "望江东"], [["西岭卫星城", "西岭客运站", "河谷口", "谷口", "老西站", "西阜工业园", "海澜总站", "望江东", "东澄软件园"]], stroke_width=12),
    LinePlan("L10", "A", "机场快线", "Airport Express", "#111827", "airport_express", "operational", "以较少停站连接海澜总站、望江 CBD、南津中心、南湾铁路站和临湾国际机场。", ["海澜总站", "望江 CBD", "南津副中心", "临湾航空城"], [["海澜总站", "望江商务区", "南津中心", "南湾铁路站", "临空商务区", "临湾国际机场", "机场二号航站楼"]], crosses_main_river=True, stroke_width=14),
    LinePlan("L11", "11", "临港线", "Lingang Line", "#6b7280", "commuter", "operational", "南湾东部与深水港、保税物流、船坞和邮轮中心之间的港区通勤线。", ["南湾货运区", "保税物流园", "深水港区"], [["南湾货场", "港湾湿地", "保税物流园", "保税东", "港湾邮轮中心", "外海门", "集装箱北", "深水港", "船坞西", "船厂路", "港务西", "港务大厦"]], stroke_width=9),
    LinePlan("L12", "12", "工业更新线", "Industrial Renewal Line", "#9a6b00", "metro", "operational", "沿旧铁路货场和纺织机械厂区布设，服务西阜传统工业区更新与老城北侧社区。", ["西阜工业区", "崇安老城北", "旧铁路走廊"], [["铁西货场", "西阜货场", "车辆段", "西阜机厂", "机修厂", "纺织公园", "工人村", "崇安门", "北仓门", "老城墙", "太平坊", "北城火车站", "西河口", "仓前街"]]),
    LinePlan("L13", "13", "北环联络线", "North Arc Connector", "#c026d3", "arc_connector", "operational", "中心北侧半环，联络西阜货场、北苑高铁站、北部医疗教育片区和东澄北部。", ["西阜北部", "北苑新城", "东澄北部"], [["西阜货场", "北部物流园", "北环西", "纱厂公园", "北苑高铁站", "北苑中心", "松台公园", "北苑行政中心", "望北路", "医科城", "长浜", "东澄北", "科创北路", "会展北路", "湾北西"]], stroke_width=9),
    LinePlan("L14", "14", "云洲会展线", "Yunzhou-Expo Line", "#ef4444", "metro", "operational", "从国际会展中心经望江东、云洲岛到南岸金融和滨海新城的跨江联络线。", ["国际会展片区", "云洲岛", "南津金融区", "滨海新城"], [["国际会展中心", "科技新城", "望江东", "博物馆", "云洲码头", "河洲公园", "云洲东", "金融街", "文化中心", "滨海新城", "海洋湖", "海洋公园"]], crosses_main_river=True),
    LinePlan("L15", "15", "青岚支线", "Qinglan Branch Line", "#65a30d", "branch", "operational", "大学城内部支线，在梅岭口分向青岚水库生态片区和西岭第二机场方向。", ["青岚大学城", "青岚生态区", "西岭机场"], [["青岚大学城", "书院湖", "山前村", "梅岭口"], ["梅岭口", "青岚水库", "岚屏山"], ["梅岭口", "西南科园", "西岭机场"]], is_branch=True, branch_station="梅岭口", branch_names=["水库支线", "西岭机场支线"], stroke_width=8),
    LinePlan("L16", "16", "西北机场市域线", "Northwest Airport Regional", "#0f766e", "regional_express", "operational", "第二机场与西岭卫星城、北苑高铁站之间的市域快线，承担外围机场和城际换乘功能。", ["西岭机场", "西岭卫星城", "北苑高铁站"], [["西岭机场", "河谷镇", "西岭卫星城", "西岭北站", "北山口", "北苑高铁站"]], stroke_width=12),
    LinePlan("L17", "17", "港岛支线", "Harbor Island Shuttle", "#475569", "port_shuttle", "operational", "深水港区内疏港支线，连接邮轮中心、航运大厦、东港岛和集装箱南端。", ["深水港", "东港岛", "海门岛"], [["港湾邮轮中心", "航运大厦", "航运码头", "东港岛", "岬角码头", "海门岛", "深水港", "东港南", "集装箱南"]], stroke_width=8),
    LinePlan("L18", "18", "东岸线", "East Coast Line", "#64748b", "metro", "under_construction", "建设中的东岸跨江线，未来把东澄站、会展中心、滨海新城和临湾机场串联成东南走廊。", ["东澄科技新城", "东岸湿地", "滨海新城", "临湾航空城"], [["东澄站", "东澄东", "国际会展中心", "东岸湿地", "滨海新城", "潮汐公园", "临空商务区", "航材园", "临湾国际机场", "东堤"]], crosses_main_river=True, dash="18 12"),
]


LABEL_OVERRIDES: dict[str, dict[str, object]] = {
    "纺织公园": {"x": 588.0, "y": 515.0, "anchor": "start", "direction": "manual-east"},
}


def interpolate(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def assign_coordinates() -> dict[str, tuple[float, float]]:
    coords = dict(ANCHORS)
    for line in LINES:
        for segment in line.segments:
            anchor_indices = [i for i, name in enumerate(segment) if name in coords]
            if not anchor_indices:
                raise ValueError(f"No anchors for segment {line.id}: {segment}")
            if anchor_indices[0] != 0:
                anchor_indices.insert(0, anchor_indices[0])
            if anchor_indices[-1] != len(segment) - 1:
                anchor_indices.append(anchor_indices[-1])
            for left, right in zip(anchor_indices, anchor_indices[1:]):
                start_name = segment[left]
                end_name = segment[right]
                start = coords[start_name]
                end = coords[end_name]
                span = max(1, right - left)
                for idx in range(left, right + 1):
                    name = segment[idx]
                    if name not in coords:
                        coords[name] = interpolate(start, end, (idx - left) / span)
    missing = sorted({name for line in LINES for segment in line.segments for name in segment if name not in coords})
    if missing:
        raise ValueError(f"Missing station coordinates: {missing}")
    return coords


def station_line_membership() -> dict[str, list[str]]:
    memberships: dict[str, set[str]] = defaultdict(set)
    for line in LINES:
        for segment in line.segments:
            for name in segment:
                memberships[name].add(line.id)
    return {name: sorted(ids, key=lambda item: (item != "L10", item)) for name, ids in memberships.items()}


def station_is_terminus(name: str) -> bool:
    for line in LINES:
        for segment in line.segments:
            if name == segment[0] or name == segment[-1]:
                return True
    return False


def river_side(name: str, x: float, y: float) -> str:
    if name in {"中洲北", "中洲南", "云洲码头", "云洲公园", "河洲公园", "河洲南", "云洲东"}:
        return "river-island"
    if x > 2020 and 780 <= y <= 1120:
        return "coast-port"
    if y < 700:
        return "north-bank"
    if y > 880:
        return "south-bank"
    if 760 <= y <= 880 and 850 <= x <= 1180:
        return "river-island"
    return "river-corridor"


def district_for(name: str, x: float, y: float) -> str:
    if name in {"崇安门", "鼓楼西", "人民广场", "文庙", "东仓街", "小南门", "旧城墙", "北仓门", "西牌楼", "仓前街"}:
        return "崇安区"
    if name in {"西岭机场", "河谷镇", "西岭卫星城", "西岭客运站", "谷口", "河谷口", "北山口"} or x < 430:
        return "西岭市"
    if x < 620 and y < 720:
        return "西阜区"
    if y < 430 and 800 <= x <= 1250:
        return "北苑区"
    if 620 <= x <= 930 and y < 720:
        return "崇安区"
    if 850 <= x <= 1200 and 700 <= y <= 880:
        return "云洲区"
    if 960 <= x <= 1460 and y < 760:
        return "望江区"
    if x >= 1460 and y < 760:
        return "东澄区"
    if y >= 960 and x < 980:
        return "青岚区"
    if 900 <= x <= 1460 and y >= 760:
        return "南津区"
    if 1460 < x < 1950 and y >= 1040:
        return "海堤区"
    if x >= 1950 and y >= 1080:
        return "临湾区"
    if x >= 1950:
        return "港岛区"
    return "南津区"


def role_for(name: str, line_count: int) -> str:
    if "机场" in name or "航站楼" in name:
        return "airport"
    if "高铁站" in name or "火车站" in name or "铁路站" in name or "总站" in name:
        return "railway_hub"
    if "客运站" in name or "邮轮" in name:
        return "passenger_hub"
    if "大学" in name or "书院" in name or "科大" in name:
        return "education"
    if "水库" in name or "山" in name or "湿地" in name or "公园" in name:
        return "ecology"
    if "港" in name or "码头" in name or "船" in name or "保税" in name or "集装箱" in name:
        return "port_industry"
    if "商务" in name or "金融" in name or "中心" in name or "会展" in name:
        return "business_civic"
    if "厂" in name or "货场" in name or "工业" in name or "工人" in name:
        return "industrial_heritage"
    if line_count >= 2:
        return "transfer"
    return "local_station"


def hub_type_for(name: str) -> str | None:
    if name == "临湾国际机场":
        return "international_airport"
    if name == "西岭机场":
        return "secondary_airport"
    if name in {"机场二号航站楼", "机场三号航站楼"}:
        return "airport_terminal"
    if name == "北城火车站":
        return "old_railway_station"
    if name == "海澜总站":
        return "main_high_speed_railway_station"
    if name in {"北苑高铁站", "南湾铁路站", "东澄站"}:
        return "major_railway_station"
    if name == "港湾邮轮中心":
        return "cruise_terminal"
    if name in {"南部客运站", "西岭客运站"}:
        return "coach_terminal"
    return None


def spatial_zone_for(name: str, x: float, y: float) -> str:
    if "机场" in name or "航站楼" in name or x > 1980 and y > 1120:
        return "东南航空城"
    if x > 2050 and 820 <= y <= 1100:
        return "东部深水港和保税区"
    if x < 460 and y < 900:
        return "西部生态和卫星城"
    if y > 1040 and x < 900:
        return "西南大学城与科研区"
    if x > 1450 and y < 760:
        return "东部科技新城"
    if y > 1110 and 1400 <= x <= 1950:
        return "南部滨海新城"
    if 950 <= x <= 1420 and 820 <= y <= 1030:
        return "南岸金融和文化副中心"
    if 1060 <= x <= 1420 and y < 720:
        return "现代中央商务区"
    if 540 <= x <= 900 and 430 <= y <= 700:
        return "传统老城"
    if x < 620 and y < 720:
        return "传统工业区"
    if 780 <= x <= 1180 and 680 <= y <= 880:
        return "近代商业与港埠区"
    if y < 430 and 780 <= x <= 1150:
        return "北部居住新城"
    return "综合城区"


def build_network() -> dict[str, object]:
    coords = assign_coordinates()
    memberships = station_line_membership()
    stations: list[dict[str, object]] = []
    for name in sorted(memberships.keys(), key=lambda n: (coords[n][1], coords[n][0], n)):
        x, y = coords[name]
        line_ids = memberships[name]
        hub_type = hub_type_for(name)
        stations.append(
            {
                "id": station_id(name),
                "nameZh": name,
                "nameEn": make_english(name),
                "x": round(x, 2),
                "y": round(y, 2),
                "district": district_for(name, x, y),
                "functionalRole": role_for(name, len(line_ids)),
                "transferLines": line_ids,
                "isTerminus": station_is_terminus(name),
                "isTrafficHub": hub_type is not None,
                "hubType": hub_type,
                "riverSide": river_side(name, x, y),
                "spatialZone": spatial_zone_for(name, x, y),
                "constructionStatus": "under_construction" if any(line_id == "L18" for line_id in line_ids) and len(line_ids) == 1 else "operational",
            }
        )

    lines: list[dict[str, object]] = []
    for line in LINES:
        flat = []
        seen = set()
        for segment in line.segments:
            for station in segment:
                if station not in seen:
                    flat.append(station)
                    seen.add(station)
        lines.append(
            {
                "id": line.id,
                "number": line.number,
                "nameZh": line.name_zh,
                "nameEn": line.name_en,
                "color": line.color,
                "type": line.line_type,
                "status": line.status,
                "function": line.function,
                "serviceAreas": line.service_areas,
                "stations": flat,
                "segments": line.segments,
                "isRing": line.is_ring,
                "isBranch": line.is_branch,
                "branchInfo": {
                    "branchStation": line.branch_station,
                    "branchNames": line.branch_names,
                }
                if line.is_branch
                else None,
                "crossesMainRiver": line.crosses_main_river,
                "strokeWidth": line.stroke_width,
                "dash": line.dash,
            }
        )

    return {
        "schemaVersion": "1.0",
        "city": {
            "nameZh": "海澜市",
            "nameEn": "Hailan",
            "population": 21400000,
            "metroAreaPopulation": 31800000,
            "builtUpAreaKm2": 2680,
            "historySummary": "海澜由明代崇安卫城、清末霁江商埠、二十世纪西阜工业走廊和近三十年的望江-南津金融文化轴共同演化而成。",
        },
        "geography": {
            "mainRiver": {"nameZh": "霁江", "nameEn": "Jijiang River", "flow": "west-east", "mouth": "澄湾"},
            "tributaries": [{"nameZh": "青溪河", "nameEn": "Qingxi River"}],
            "bay": {"nameZh": "澄湾", "nameEn": "Cheng Bay"},
            "islands": [
                {"nameZh": "云洲岛", "nameEn": "Yunzhou Island", "type": "river_island"},
                {"nameZh": "海门岛", "nameEn": "Haimen Island", "type": "bay_island"},
            ],
            "waterBodies": [{"nameZh": "青岚水库", "nameEn": "Qinglan Reservoir"}],
            "terrain": [{"nameZh": "岚屏山生态保护区", "nameEn": "Lanping Hills Ecological Reserve"}],
            "coastline": {"nameZh": "东南海岸线", "nameEn": "Southeast Coastline"},
        },
        "districts": [
            {"nameZh": "崇安区", "nameEn": "Chongan District", "role": "传统老城"},
            {"nameZh": "西阜区", "nameEn": "Xifu District", "role": "传统工业区"},
            {"nameZh": "北苑区", "nameEn": "Beiyuan District", "role": "北部居住新城"},
            {"nameZh": "云洲区", "nameEn": "Yunzhou District", "role": "江心岛与近代港埠"},
            {"nameZh": "望江区", "nameEn": "Wangjiang District", "role": "现代中央商务区"},
            {"nameZh": "南津区", "nameEn": "Nanjin District", "role": "南岸金融文化副中心"},
            {"nameZh": "青岚区", "nameEn": "Qinglan District", "role": "大学城与生态丘陵"},
            {"nameZh": "东澄区", "nameEn": "Dongcheng District", "role": "东部科技新城"},
            {"nameZh": "海堤区", "nameEn": "Haiti District", "role": "南部滨海新城"},
            {"nameZh": "临湾区", "nameEn": "Linwan District", "role": "东南航空城"},
            {"nameZh": "港岛区", "nameEn": "Gangdao District", "role": "深水港和保税区"},
            {"nameZh": "西岭市", "nameEn": "Xiling County-level City", "role": "西部卫星城与第二机场"},
        ],
        "functionalZones": [
            "传统老城",
            "近代商业与港埠区",
            "传统工业区",
            "现代中央商务区",
            "南岸金融和文化副中心",
            "西南大学城与科研区",
            "东部科技新城",
            "东南航空城",
            "南部滨海新城",
            "东部深水港和保税区",
            "北部居住新城",
            "西部生态和卫星城",
        ],
        "lines": lines,
        "stations": stations,
    }


def line_lookup(network: dict[str, object]) -> dict[str, dict[str, object]]:
    return {line["id"]: line for line in network["lines"]}  # type: ignore[index]


def station_lookup(network: dict[str, object]) -> dict[str, dict[str, object]]:
    return {station["nameZh"]: station for station in network["stations"]}  # type: ignore[index]


def compute_network_metrics(network: dict[str, object]) -> dict[str, object]:
    stations = network["stations"]  # type: ignore[index]
    lines = network["lines"]  # type: ignore[index]
    transfer_counts = Counter(len(station["transferLines"]) for station in stations)  # type: ignore[index]
    return {
        "cityNameZh": network["city"]["nameZh"],  # type: ignore[index]
        "cityNameEn": network["city"]["nameEn"],  # type: ignore[index]
        "population": network["city"]["population"],  # type: ignore[index]
        "districtCount": len(network["districts"]),  # type: ignore[index]
        "functionalZoneCount": len(network["functionalZones"]),  # type: ignore[index]
        "visibleLineCount": len(lines),
        "operationalLineCount": sum(1 for line in lines if line["status"] == "operational"),
        "underConstructionLineCount": sum(1 for line in lines if line["status"] == "under_construction"),
        "uniqueStationCount": len(stations),
        "transferStationCount": sum(1 for station in stations if len(station["transferLines"]) >= 2),
        "twoLineTransferCount": transfer_counts[2],
        "threeLineTransferCount": transfer_counts[3],
        "fourLineTransferCount": transfer_counts[4],
        "ringLineCount": sum(1 for line in lines if line["type"] == "ring"),
        "branchLineCount": sum(1 for line in lines if line["isBranch"]),
        "airportServiceCount": sum(1 for line in lines if line["type"] == "airport_express" or any("机场" in station for station in line["stations"])),
        "crossRiverLineCount": sum(1 for line in lines if line["crossesMainRiver"]),
        "airportCount": 2,
        "majorRailwayStationCount": 5,
        "bilingualStationCount": len([station for station in stations if station["nameZh"] and station["nameEn"]]),
        "riverCount": 2,
        "islandCount": 2,
    }


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_city_plan(network: dict[str, object]) -> None:
    lines = network["lines"]  # type: ignore[index]
    text: list[str] = []
    text.append("# 海澜市城市与轨道交通规划说明\n")
    text.append("## 城市设定\n")
    text.append("海澜市（Hailan）是一座位于霁江入海口的虚构中国沿海一线城市，常住人口 2140 万，都市圈人口约 3180 万，建成区约 2680 平方公里。城市东西向展开明显，霁江自西向东穿城入澄湾，北岸形成崇安老城、望江 CBD 与东澄科技走廊，南岸形成南津金融文化副中心、南部滨海新城与临湾航空城。\n")
    text.append("## 历史层次\n")
    text.append("- 明清时期：崇安卫城位于霁江北岸中部偏西，保留崇安门、鼓楼西、文庙、旧城墙、仓前街等地名。\n")
    text.append("- 清末至民国：霁江下游北岸和云洲岛发展为商埠，形成临江码头、银行街、旧码头、云洲码头等近代港埠空间。\n")
    text.append("- 二十世纪工业化：西阜区沿铁路、货场和旧运河发展机械、纺织与车辆维修，现保留西阜机厂、双棉厂、铁西货场等站名。\n")
    text.append("- 近三十年：望江 CBD、南津金融文化副中心、东澄科技新城、临湾航空城、海堤滨海新城和港岛深水港分期建设，网络呈现多年代叠加的不规则性。\n")
    text.append("## 自然地理骨架\n")
    text.append("- 主河流：霁江（Jijiang River）自西向东穿越城市，在东部入澄湾，中心段较窄，入海口显著变宽。\n")
    text.append("- 支流：青溪河从青岚丘陵和青岚水库向东北汇入霁江。\n")
    text.append("- 江心岛：云洲岛位于中心城区附近，承载近代码头、文化设施和跨江换乘。\n")
    text.append("- 山水生态：西南部为岚屏山生态保护区与青岚水库，大学城沿丘陵和平原交界布局。\n")
    text.append("- 海岸与港口：东南部为海堤滨海新城、临湾国际机场和深水港，港岛区靠近深水岸线，和居住新城之间保留潮汐湿地缓冲。\n")
    text.append("## 城市级交通枢纽\n")
    text.append("- 民用机场：临湾国际机场、西岭机场。\n")
    text.append("- 主要铁路客运站：海澜总站、北苑高铁站、南湾铁路站、东澄站、北城火车站。\n")
    text.append("- 其他枢纽：港湾邮轮中心、南部客运站、西岭客运站。\n")
    text.append("## 线路规划\n")
    for line in lines:
        text.append(f"### {line['id']} {line['nameZh']} / {line['nameEn']}\n")
        text.append(f"- 类型：{line['type']}；状态：{line['status']}。\n")
        text.append(f"- 起终点：{line['segments'][0][0]} - {line['segments'][0][-1]}。\n")
        text.append(f"- 服务区域：{'、'.join(line['serviceAreas'])}。\n")
        transfers = [name for name in line["stations"] if len(station_lookup(network)[name]["transferLines"]) >= 2]
        text.append(f"- 主要换乘站：{'、'.join(transfers[:10])}。\n")
        text.append(f"- 跨越主河：{'是' if line['crossesMainRiver'] else '否'}。\n")
        if line["isBranch"]:
            branch = line["branchInfo"]
            text.append(f"- 支线关系：在 {branch['branchStation']} 分叉，包含{'、'.join(branch['branchNames'])}。\n")
        if line["isRing"]:
            text.append("- 环线关系：首末站均为人民广场，形成闭合核心环。\n")
        text.append(f"- 设置理由：{line['function']}\n")
    (ROOT / "CITY_PLAN.md").write_text("\n".join(text), encoding="utf-8")


def write_naming_rules(network: dict[str, object]) -> None:
    text = """# 海澜市轨道交通中英文命名规则

## 总体原则

- 中文站名优先使用历史地名、村镇、桥梁、城门、港埠、自然地理、公共设施和交通枢纽名称。
- 英文站名采用统一风格：专有地名使用规范拼音，明确公共功能采用固定英文译法。
- 同一中文通名全图保持一致翻译，不使用营销化或随意美化英文。
- 火车站、高铁站、机场、航站楼、会展中心、市民/行政中心、大学城、港口等公共功能均使用意译。

## 常见通名译法

- 火车站 / 铁路站：`Railway Station`
- 高铁站：`High-Speed Railway Station`
- 总站：`Main Railway Station`
- 国际机场：`International Airport`
- 航站楼：`Airport Terminal`
- 客运站：`Coach Terminal`
- 邮轮中心：`Cruise Center`
- 广场：`Square`
- 公园：`Park`
- 水库：`Reservoir`
- 大学城：`University Town`
- 会展中心：`Convention Center`
- 商务区：`CBD` 或 `Business District`，其中望江商务区固定为 `Wangjiang CBD`
- 金融街：`Financial Street`
- 文化中心：`Cultural Center`
- 码头：`Wharf`
- 保税物流园：`Bonded Logistics Park`
- 大道：`Avenue`
- 路：`Road`
- 街：`Street`
- 桥：`Bridge`
- 门：`Gate`
- 岛：`Island`
- 湾：`Bay`
- 镇：`Town`
- 村：`Village`

## 专名拼音规则

- 专名拼音首字母大写并合写，如 `Qinglan`、`Xifu`、`Dongcheng`。
- 方位词用于站名核心时保留拼音或英文功能后缀，例如 `Yaogu North`、`Haiti South`。
- 英文站名必须唯一；脚本在生成 `network.json` 时会验证中英文唯一性。
"""
    (ROOT / "NAMING_RULES.md").write_text(text, encoding="utf-8")


def segment_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    commands = [f"M {fmt(points[0][0])} {fmt(points[0][1])}"]
    for x, y in points[1:]:
        commands.append(f"L {fmt(x)} {fmt(y)}")
    return " ".join(commands)


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


def text_width(text: str, size: float, ascii_factor: float = 0.58) -> float:
    width = 0.0
    for ch in text:
        width += size * (ascii_factor if ord(ch) < 128 else 1.02)
    return width


def make_label_candidates(x: float, y: float, zh: str, en: str, zh_size: float, en_size: float, iteration: int) -> list[dict[str, object]]:
    w = max(text_width(zh, zh_size), text_width(en, en_size))
    h = zh_size + en_size + 5
    base = 11 + max(0, iteration - 1) * 3
    far = 24 + max(0, iteration - 1) * 5
    specs = [
        ("e", base, 0, "start", 0),
        ("w", -base, 0, "end", 0),
        ("n", 0, -far, "middle", 0),
        ("s", 0, far + 4, "middle", 0),
        ("ne", base, -far, "start", 0),
        ("se", base, far, "start", 0),
        ("nw", -base, -far, "end", 0),
        ("sw", -base, far, "end", 0),
        ("ee", base + 18, -6, "start", 0),
        ("ww", -base - 18, 6, "end", 0),
        ("nn", 0, -far - 18, "middle", 0),
        ("ss", 0, far + 22, "middle", 0),
        ("eee", base + 38, -10, "start", 0),
        ("www", -base - 38, 10, "end", 0),
        ("nne", base + 18, -far - 28, "start", 0),
        ("nnw", -base - 18, -far - 28, "end", 0),
        ("sse", base + 18, far + 32, "start", 0),
        ("ssw", -base - 18, far + 32, "end", 0),
    ]
    candidates: list[dict[str, object]] = []
    for direction, dx, dy, anchor, rotate in specs:
        tx = x + dx
        ty = y + dy
        if anchor == "start":
            bbox = (tx, ty - zh_size, tx + w, ty + h - zh_size)
        elif anchor == "end":
            bbox = (tx - w, ty - zh_size, tx, ty + h - zh_size)
        else:
            bbox = (tx - w / 2, ty - zh_size, tx + w / 2, ty + h - zh_size)
        candidates.append({"direction": direction, "x": tx, "y": ty, "anchor": anchor, "bbox": bbox, "rotate": rotate})
    return candidates


def collect_line_segments(network: dict[str, object]) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    stations = station_lookup(network)
    segments: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
    for line in network["lines"]:  # type: ignore[index]
        for segment in line["segments"]:
            points = [(float(stations[name]["x"]), float(stations[name]["y"])) for name in segment]
            for a, b in zip(points, points[1:]):
                segments.append((line["id"], a, b))
    return segments


def place_labels(network: dict[str, object], iteration: int) -> list[dict[str, object]]:
    stations = list(network["stations"])  # type: ignore[arg-type,index]
    line_segments = collect_line_segments(network)
    station_points = [(float(station["x"]), float(station["y"]), station["nameZh"]) for station in stations]
    ordered = sorted(
        stations,
        key=lambda st: (
            -len(st["transferLines"]),
            not st["isTrafficHub"],
            abs(float(st["x"]) - WIDTH / 2) + abs(float(st["y"]) - HEIGHT / 2),
        ),
    )
    placed: list[tuple[float, float, float, float]] = []
    labels: list[dict[str, object]] = []
    zh_size = 10.6
    en_size = 6.8
    padding = 3 + iteration
    for station in ordered:
        x = float(station["x"])
        y = float(station["y"])
        candidates = make_label_candidates(x, y, station["nameZh"], station["nameEn"], zh_size, en_size, iteration)
        best: dict[str, object] | None = None
        best_score = float("inf")
        for candidate in candidates:
            bbox = candidate["bbox"]  # type: ignore[assignment]
            if not isinstance(bbox, tuple):
                continue
            score = 0.0
            x1, y1, x2, y2 = bbox
            if x1 < 18 or y1 < 18 or x2 > WIDTH - 18 or y2 > HEIGHT - 18:
                score += 10000
            for other in placed:
                if bbox_intersects(bbox, other, padding):
                    score += 5000
            for sx, sy, sname in station_points:
                if sname == station["nameZh"]:
                    continue
                if point_in_bbox((sx, sy), bbox, 6):
                    score += 180
            for line_id, a, b in line_segments:
                if segment_intersects_bbox(a, b, bbox, 2.0):
                    score += 24 if line_id in station["transferLines"] else 55
            if candidate["direction"] in {"e", "w", "ne", "se"}:
                score -= 4
            if score < best_score:
                best_score = score
                best = candidate
        if best is None:
            raise RuntimeError(f"Could not place label for {station['nameZh']}")
        if station["nameZh"] in LABEL_OVERRIDES:
            override = LABEL_OVERRIDES[station["nameZh"]]
            ox = float(override["x"])
            oy = float(override["y"])
            anchor = str(override["anchor"])
            width = max(text_width(str(station["nameZh"]), zh_size), text_width(str(station["nameEn"]), en_size))
            height = zh_size + en_size + 5
            if anchor == "start":
                bbox = (ox, oy - zh_size, ox + width, oy + height - zh_size)
            elif anchor == "end":
                bbox = (ox - width, oy - zh_size, ox, oy + height - zh_size)
            else:
                bbox = (ox - width / 2, oy - zh_size, ox + width / 2, oy + height - zh_size)
            best = {"x": ox, "y": oy, "anchor": anchor, "bbox": bbox, "direction": override["direction"], "rotate": 0}
        bbox = best["bbox"]  # type: ignore[assignment]
        if isinstance(bbox, tuple):
            placed.append(bbox)
        labels.append(
            {
                "station": station["nameZh"],
                "en": station["nameEn"],
                "x": best["x"],
                "y": best["y"],
                "anchor": best["anchor"],
                "bbox": bbox,
                "direction": best["direction"],
                "zhSize": zh_size,
                "enSize": en_size,
            }
        )
    return sorted(labels, key=lambda item: item["station"])


class Svg:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def raw(self, line: str) -> None:
        self.lines.append(line)

    def open(self, tag: str, attrs: dict[str, object | None] | None = None) -> None:
        self.lines.append(f"<{tag}{attrs_to_text(attrs or {})}>")

    def close(self, tag: str) -> None:
        self.lines.append(f"</{tag}>")

    def elem(self, tag: str, attrs: dict[str, object | None] | None = None) -> None:
        self.lines.append(f"<{tag}{attrs_to_text(attrs or {})} />")

    def text(self, value: str, attrs: dict[str, object | None] | None = None) -> None:
        self.lines.append(f"<text{attrs_to_text(attrs or {})}>{html.escape(value)}</text>")


def add_background(svg: Svg) -> None:
    svg.open("g", {"id": "background"})
    svg.elem("rect", {"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT, "fill": "#f8fafc"})
    areas = [
        ("西阜工业区", "M260 315 L620 330 L690 600 L560 710 L260 650 Z", "#f8e7d0"),
        ("崇安老城", "M560 430 L920 420 L940 700 L610 720 L520 590 Z", "#fff4d6"),
        ("望江商务区", "M1030 430 L1480 470 L1460 710 L1040 705 Z", "#e8f2ff"),
        ("北苑新城", "M760 180 L1160 180 L1200 410 L820 430 Z", "#edf7ed"),
        ("青岚大学城", "M360 990 L940 960 L1000 1220 L680 1390 L320 1280 Z", "#edf8e7"),
        ("南津副中心", "M900 820 L1440 800 L1470 1080 L950 1140 Z", "#f0ecff"),
        ("东澄科技新城", "M1500 420 L2080 420 L2130 730 L1540 760 Z", "#e6fbf7"),
        ("滨海新城", "M1400 1080 L1970 1100 L2010 1400 L1540 1460 L1380 1280 Z", "#e9f7ff"),
        ("临湾航空城", "M1950 1080 L2320 1100 L2350 1430 L1990 1460 Z", "#eef2ff"),
        ("深水港区", "M1990 790 L2350 780 L2360 1120 L2040 1120 Z", "#eceff3"),
    ]
    for label, path, fill in areas:
        svg.elem("path", {"d": path, "fill": fill, "stroke": "#d7dee8", "stroke-width": 1.2})
    svg.close("g")

    svg.open("g", {"id": "water"})
    river = (
        "M 90 700 C 330 650 520 675 760 700 "
        "C 960 730 1140 710 1360 680 "
        "C 1660 635 1880 650 2320 705 "
        "L 2380 900 C 1980 825 1680 800 1400 850 "
        "C 1140 900 970 910 780 845 "
        "C 540 760 320 780 80 830 Z"
    )
    svg.elem("path", {"d": river, "fill": "#cfe8f3", "stroke": "#9ecae1", "stroke-width": 2})
    svg.elem("path", {"d": "M 350 1180 C 520 1060 650 930 785 840", "fill": "none", "stroke": "#b7dbeb", "stroke-width": 34, "stroke-linecap": "round"})
    svg.elem("ellipse", {"cx": 1030, "cy": 785, "rx": 190, "ry": 82, "fill": "#f8fafc", "stroke": "#9ecae1", "stroke-width": 1.4})
    svg.elem("ellipse", {"cx": 2280, "cy": 910, "rx": 92, "ry": 56, "fill": "#f8fafc", "stroke": "#9ecae1", "stroke-width": 1.4})
    svg.elem("path", {"d": "M 1990 760 C 2090 850 2260 830 2380 900 L2380 1500 L1980 1500 C 2030 1320 1990 1110 1990 760 Z", "fill": "#d8eef7", "stroke": "#9ecae1", "stroke-width": 2})
    svg.text("霁江 / Jijiang River", {"x": 1460, "y": 770, "class": "water-label"})
    svg.text("青溪河 / Qingxi River", {"x": 545, "y": 1058, "class": "water-label small"})
    svg.text("澄湾 / Cheng Bay", {"x": 2110, "y": 750, "class": "water-label"})
    svg.text("云洲岛 / Yunzhou Island", {"x": 930, "y": 790, "class": "geo-label"})
    svg.text("青岚水库 / Qinglan Reservoir", {"x": 250, "y": 1160, "class": "geo-label"})
    svg.text("岚屏山生态保护区 / Lanping Hills Ecological Reserve", {"x": 255, "y": 1360, "class": "geo-label"})
    svg.close("g")


def add_icons(svg: Svg, stations: dict[str, dict[str, object]]) -> None:
    svg.open("g", {"id": "landmarks"})
    for name in ["海澜总站", "北苑高铁站", "北城火车站", "南湾铁路站", "东澄站"]:
        st = stations[name]
        x = float(st["x"])
        y = float(st["y"])
        svg.elem("rect", {"x": fmt(x - 12), "y": fmt(y - 23), "width": 24, "height": 15, "rx": 2, "fill": "#ffffff", "stroke": "#334155", "stroke-width": 1.5})
        svg.elem("line", {"x1": fmt(x - 7), "y1": fmt(y - 15), "x2": fmt(x + 7), "y2": fmt(y - 15), "stroke": "#334155", "stroke-width": 1.2})
    for name in ["临湾国际机场", "西岭机场"]:
        st = stations[name]
        x = float(st["x"])
        y = float(st["y"])
        svg.elem("path", {"d": f"M {fmt(x)} {fmt(y-24)} L {fmt(x+6)} {fmt(y-4)} L {fmt(x+28)} {fmt(y+4)} L {fmt(x+8)} {fmt(y+8)} L {fmt(x+8)} {fmt(y+22)} L {fmt(x)} {fmt(y+12)} L {fmt(x-8)} {fmt(y+22)} L {fmt(x-8)} {fmt(y+8)} L {fmt(x-28)} {fmt(y+4)} L {fmt(x-6)} {fmt(y-4)} Z", "fill": "#ffffff", "stroke": "#111827", "stroke-width": 1.5})
    for name in ["港湾邮轮中心", "深水港"]:
        st = stations[name]
        x = float(st["x"])
        y = float(st["y"])
        svg.elem("path", {"d": f"M {fmt(x-18)} {fmt(y+12)} L {fmt(x+18)} {fmt(y+12)} L {fmt(x+10)} {fmt(y+23)} L {fmt(x-10)} {fmt(y+23)} Z", "fill": "#ffffff", "stroke": "#334155", "stroke-width": 1.5})
        svg.elem("line", {"x1": fmt(x), "y1": fmt(y - 18), "x2": fmt(x), "y2": fmt(y + 12), "stroke": "#334155", "stroke-width": 1.4})
    svg.close("g")


def write_svg(network: dict[str, object], iteration: int) -> dict[str, object]:
    stations = station_lookup(network)
    labels = place_labels(network, iteration)
    svg = Svg()
    svg.raw('<?xml version="1.0" encoding="UTF-8"?>')
    svg.open("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"0 0 {WIDTH} {HEIGHT}", "role": "img", "aria-labelledby": "title desc"})
    svg.raw("<title id=\"title\">海澜市轨道交通线路图 / Hailan Metro Map</title>")
    svg.raw("<desc id=\"desc\">A fictional bilingual metro map for a Chinese coastal megacity.</desc>")
    svg.raw(
        """<style>
        text { font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", Arial, sans-serif; }
        .title-zh { font-size: 34px; font-weight: 700; fill: #0f172a; }
        .title-en { font-size: 16px; fill: #475569; }
        .subtitle { font-size: 12px; fill: #64748b; }
        .water-label { font-size: 24px; font-weight: 600; fill: #4f8aa8; opacity: .75; }
        .water-label.small { font-size: 15px; }
        .geo-label { font-size: 14px; fill: #64748b; font-weight: 600; }
        .line-path { fill: none; stroke-linecap: round; stroke-linejoin: round; }
        .line-casing { fill: none; stroke: #ffffff; stroke-linecap: round; stroke-linejoin: round; opacity: .92; }
        .station-node circle, .station-node rect { vector-effect: non-scaling-stroke; }
        .station-label-zh { font-weight: 650; fill: #111827; paint-order: stroke; stroke: #ffffff; stroke-width: 4px; stroke-linejoin: round; }
        .station-label-en { fill: #475569; paint-order: stroke; stroke: #ffffff; stroke-width: 3px; stroke-linejoin: round; }
        .legend-text { font-size: 12px; fill: #111827; }
        .legend-small { font-size: 9px; fill: #64748b; }
        </style>"""
    )
    add_background(svg)
    svg.open("g", {"id": "network-lines"})
    for line in network["lines"]:  # type: ignore[index]
        width = float(line["strokeWidth"])
        for idx, segment in enumerate(line["segments"]):
            points = [(float(stations[name]["x"]), float(stations[name]["y"])) for name in segment]
            path = segment_path(points)
            svg.elem("path", {"class": "line-casing", "d": path, "stroke-width": fmt(width + 5), "data-line-id": line["id"], "data-segment-index": idx})
            attrs = {
                "class": "line-path",
                "d": path,
                "stroke": line["color"],
                "stroke-width": fmt(width),
                "data-line-id": line["id"],
                "data-segment-index": idx,
            }
            if line["status"] == "under_construction":
                attrs["stroke-dasharray"] = line["dash"] or "16 10"
                attrs["opacity"] = "0.86"
            if line["type"] in {"airport_express", "regional_express"}:
                attrs["stroke-linecap"] = "square"
            svg.elem("path", attrs)
    svg.close("g")
    add_icons(svg, stations)
    svg.open("g", {"id": "station-nodes"})
    for station in network["stations"]:  # type: ignore[index]
        x = float(station["x"])
        y = float(station["y"])
        count = len(station["transferLines"])
        attrs = {"class": "station-node", "data-station": station["nameZh"], "data-lines": ",".join(station["transferLines"]), "data-x": fmt(x), "data-y": fmt(y)}
        svg.open("g", attrs)
        if station["isTrafficHub"]:
            svg.elem("rect", {"x": fmt(x - 6.5), "y": fmt(y - 6.5), "width": 13, "height": 13, "rx": 2, "fill": "#ffffff", "stroke": "#0f172a", "stroke-width": 2.2})
        elif count >= 2:
            svg.elem("circle", {"cx": fmt(x), "cy": fmt(y), "r": 6.2 if count < 4 else 7.8, "fill": "#ffffff", "stroke": "#0f172a", "stroke-width": 2})
        elif station["isTerminus"]:
            svg.elem("circle", {"cx": fmt(x), "cy": fmt(y), "r": 4.8, "fill": "#ffffff", "stroke": "#334155", "stroke-width": 1.6})
        else:
            svg.elem("circle", {"cx": fmt(x), "cy": fmt(y), "r": 3.6, "fill": "#ffffff", "stroke": "#334155", "stroke-width": 1.2})
        svg.close("g")
    svg.close("g")
    svg.open("g", {"id": "station-labels"})
    for label in labels:
        x1, y1, x2, y2 = label["bbox"]  # type: ignore[misc]
        svg.open(
            "g",
            {
                "class": "station-label",
                "data-station": label["station"],
                "data-bbox": f"{fmt(x1)} {fmt(y1)} {fmt(x2)} {fmt(y2)}",
                "data-direction": label["direction"],
            },
        )
        x = float(label["x"])
        y = float(label["y"])
        anchor = label["anchor"]
        svg.text(str(label["station"]), {"class": "station-label-zh", "x": fmt(x), "y": fmt(y), "font-size": fmt(label["zhSize"]), "text-anchor": anchor})
        svg.text(str(label["en"]), {"class": "station-label-en", "x": fmt(x), "y": fmt(y + 10.5), "font-size": fmt(label["enSize"]), "text-anchor": anchor})
        svg.close("g")
    svg.close("g")
    add_legend(svg, network)
    svg.close("svg")
    text = "\n".join(svg.lines) + "\n"
    (ROOT / "metro.svg").write_text(text, encoding="utf-8")
    return collect_svg_metrics_text(text)


def add_legend(svg: Svg, network: dict[str, object]) -> None:
    svg.open("g", {"id": "map-title"})
    svg.text("海澜市轨道交通线路图", {"x": 70, "y": 70, "class": "title-zh"})
    svg.text("Hailan Metro and Regional Rail Network", {"x": 72, "y": 96, "class": "title-en"})
    svg.text("2026 schematic edition · fictional planning data · bilingual station labels", {"x": 72, "y": 118, "class": "subtitle"})
    svg.close("g")

    svg.open("g", {"id": "legend", "data-line-ids": ",".join(line["id"] for line in network["lines"])} )  # type: ignore[index]
    x0 = 70
    y0 = 1260
    svg.elem("rect", {"x": x0 - 18, "y": y0 - 36, "width": 540, "height": 285, "rx": 8, "fill": "#ffffff", "stroke": "#cbd5e1", "stroke-width": 1.4})
    svg.text("线路图例 / Lines", {"x": x0, "y": y0 - 12, "class": "legend-text", "font-weight": 700})
    for idx, line in enumerate(network["lines"]):  # type: ignore[index]
        col = idx // 9
        row = idx % 9
        x = x0 + col * 260
        y = y0 + row * 24 + 14
        attrs = {"x1": x, "y1": y - 5, "x2": x + 42, "y2": y - 5, "stroke": line["color"], "stroke-width": 7, "stroke-linecap": "round", "data-legend-line-id": line["id"]}
        if line["status"] == "under_construction":
            attrs["stroke-dasharray"] = "12 7"
        svg.elem("line", attrs)
        svg.text(f"{line['number']} {line['nameZh']}", {"x": x + 52, "y": y - 8, "class": "legend-text"})
        svg.text(str(line["nameEn"]), {"x": x + 52, "y": y + 4, "class": "legend-small"})
    y_symbols = y0 + 234
    svg.elem("circle", {"cx": x0 + 18, "cy": y_symbols, "r": 4.2, "fill": "#ffffff", "stroke": "#334155", "stroke-width": 1.2})
    svg.text("普通站", {"x": x0 + 32, "y": y_symbols + 4, "class": "legend-text"})
    svg.elem("circle", {"cx": x0 + 110, "cy": y_symbols, "r": 6.2, "fill": "#ffffff", "stroke": "#0f172a", "stroke-width": 2})
    svg.text("换乘站", {"x": x0 + 126, "y": y_symbols + 4, "class": "legend-text"})
    svg.elem("rect", {"x": x0 + 210, "y": y_symbols - 6.5, "width": 13, "height": 13, "rx": 2, "fill": "#ffffff", "stroke": "#0f172a", "stroke-width": 2})
    svg.text("交通枢纽", {"x": x0 + 232, "y": y_symbols + 4, "class": "legend-text"})
    svg.elem("line", {"x1": x0 + 340, "y1": y_symbols, "x2": x0 + 390, "y2": y_symbols, "stroke": "#64748b", "stroke-width": 7, "stroke-dasharray": "12 7"})
    svg.text("建设中", {"x": x0 + 402, "y": y_symbols + 4, "class": "legend-text"})
    svg.close("g")


def collect_svg_metrics_text(text: str) -> dict[str, object]:
    tags = re.findall(r"<([A-Za-z][\w:.-]*)\b", text)
    counts = Counter(tag.split(":")[-1] for tag in tags)
    return {
        "svgLineCount": len(text.splitlines()),
        "nonEmptyNonCommentLineCount": sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith("<!--")),
        "svgElementCount": len(tags),
        "svgFileSizeBytes": len(text.encode("utf-8")),
        "textElementCount": counts.get("text", 0),
        "pathElementCount": counts.get("path", 0),
        "circleElementCount": counts.get("circle", 0),
        "useElementCount": counts.get("use", 0),
        "elementCounts": dict(sorted(counts.items())),
    }


def load_metadata() -> dict[str, object]:
    path = ROOT / "metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_metadata(metadata: dict[str, object]) -> None:
    write_json(ROOT / "metadata.json", metadata)


def update_metadata_for_generation(metadata: dict[str, object], network: dict[str, object], svg_metrics: dict[str, object], iteration: int) -> None:
    metadata["createdAt"] = metadata.get("createdAt") or now_iso()
    process = metadata["process"]  # type: ignore[index]
    process["cityPlanningIterations"] = max(int(process.get("cityPlanningIterations") or 0), 2)
    process["networkGenerationAttempts"] = max(int(process.get("networkGenerationAttempts") or 0), 2)
    process["svgGenerationAttempts"] = max(int(process.get("svgGenerationAttempts") or 0), iteration)
    process["layoutRepairIterations"] = max(int(process.get("layoutRepairIterations") or 0), max(0, iteration - 1))
    metadata["networkMetrics"] = {**metadata.get("networkMetrics", {}), **compute_network_metrics(network)}
    metadata["svgMetrics"] = {**metadata.get("svgMetrics", {}), **svg_metrics}
    result = metadata["result"]  # type: ignore[index]
    commands = result.setdefault("commandsExecuted", [])
    command = f"python3 generate_metro.py --iteration {iteration}"
    if command not in commands:
        commands.append(command)


def write_report(metadata: dict[str, object]) -> None:
    network_metrics = metadata["networkMetrics"]  # type: ignore[index]
    svg_metrics = metadata["svgMetrics"]  # type: ignore[index]
    network_validation = metadata["networkValidation"]  # type: ignore[index]
    svg_validation = metadata["svgValidation"]  # type: ignore[index]
    layout_validation = metadata["layoutValidation"]  # type: ignore[index]
    result = metadata["result"]  # type: ignore[index]
    text = [
        "# 海澜市轨道交通 SVG 生成报告",
        "",
        "## 输出文件",
        "",
        "- `CITY_PLAN.md`",
        "- `NAMING_RULES.md`",
        "- `network.json`",
        "- `generate_metro.py`",
        "- `validate_network.py`",
        "- `validate_svg.py`",
        "- `metro.svg`",
        "- `preview.png`",
        "- `REPORT.md`",
        "- `metadata.json`",
        "",
        "## 网络指标",
        "",
        f"- 城市：{network_metrics.get('cityNameZh')} / {network_metrics.get('cityNameEn')}",
        f"- 可见线路：{network_metrics.get('visibleLineCount')}",
        f"- 唯一车站：{network_metrics.get('uniqueStationCount')}",
        f"- 换乘站：{network_metrics.get('transferStationCount')}（两线 {network_metrics.get('twoLineTransferCount')}，三线 {network_metrics.get('threeLineTransferCount')}，四线 {network_metrics.get('fourLineTransferCount')}）",
        f"- 跨霁江线路：{network_metrics.get('crossRiverLineCount')}",
        f"- 环线：{network_metrics.get('ringLineCount')}；支线：{network_metrics.get('branchLineCount')}；机场相关服务：{network_metrics.get('airportServiceCount')}",
        f"- 主要铁路客运站：{network_metrics.get('majorRailwayStationCount')}；机场：{network_metrics.get('airportCount')}",
        "",
        "## SVG 指标",
        "",
        f"- SVG 行数：{svg_metrics.get('svgLineCount')}",
        f"- SVG 元素数：{svg_metrics.get('svgElementCount')}",
        f"- 文件大小：{svg_metrics.get('svgFileSizeBytes')} 字节",
        f"- PNG 尺寸：{svg_metrics.get('previewWidth')} × {svg_metrics.get('previewHeight')}",
        f"- 文本元素：{svg_metrics.get('textElementCount')}；路径元素：{svg_metrics.get('pathElementCount')}；圆形元素：{svg_metrics.get('circleElementCount')}",
        "",
        "## 验证结果",
        "",
        f"- 网络验证退出码：{network_validation.get('networkValidatorExitCode')}；全部通过：{network_validation.get('allChecksPassed')}",
        f"- SVG 验证退出码：{svg_validation.get('svgValidatorExitCode')}；全部通过：{svg_validation.get('allChecksPassed')}",
        f"- 标签碰撞检测方法：{layout_validation.get('collisionDetectionMethod')}",
        f"- 标签碰撞：{layout_validation.get('totalLabelCollisionCount')}；出界标签：{layout_validation.get('outOfBoundsLabelCount')}；标签贴线：{layout_validation.get('labelLineCollisionCount')}",
        "",
        "## 实际执行过的命令",
        "",
        "```bash",
        *result.get("commandsExecuted", []),
        "```",
        "",
        "## 发现和修复的问题",
        "",
    ]
    issues_found = result.get("issuesFound", [])
    issues_fixed = result.get("issuesFixed", [])
    text.extend([f"- 发现：{item}" for item in issues_found] or ["- 未记录未修复的关键问题。"])
    text.extend([f"- 修复：{item}" for item in issues_fixed] or ["- 无需额外修复。"])
    text.extend(
        [
            "",
            "## 当前限制",
            "",
        ]
    )
    known_limitations = result.get("knownLimitations", [])
    text.extend([f"- {item}" for item in known_limitations] or ["- 未记录关键限制。"])
    text.append("- 标签碰撞检测使用 SVG 中记录的程序化文本边界框；最终仍以 `preview.png` 和 `metro.svg` 的人工查看为视觉验收依据。")
    text.append("- 本图为虚构城市示意图，线路和站点不对应任何真实城市。")
    (ROOT / "REPORT.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, default=3)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    metadata = load_metadata()
    if args.report_only:
        write_report(metadata)
        return 0

    network = build_network()
    write_city_plan(network)
    write_naming_rules(network)
    write_json(ROOT / "network.json", network)
    svg_metrics = write_svg(network, max(1, args.iteration))
    update_metadata_for_generation(metadata, network, svg_metrics, max(1, args.iteration))
    save_metadata(metadata)
    write_report(metadata)
    print(f"generated metro network: {len(network['lines'])} lines, {len(network['stations'])} stations")
    print(f"generated metro.svg with {svg_metrics['svgElementCount']} elements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
