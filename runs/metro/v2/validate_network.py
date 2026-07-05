from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
NETWORK_PATH = BASE_DIR / "network.json"


def line_station_names(line):
    names = list(line["stations"])
    for branch in line.get("branches", []):
        for name in branch["stations"]:
            if name not in names:
                names.append(name)
    return names


def main():
    network = json.loads(NETWORK_PATH.read_text(encoding="utf-8"))
    errors = []
    warnings = []
    station_by_name = {s["name"]: s for s in network["stations"]}

    if len(station_by_name) != len(network["stations"]):
        errors.append("中文站名不唯一")
    english_counts = Counter(s["englishName"] for s in network["stations"])
    duplicate_english = [name for name, count in english_counts.items() if count > 1]
    if duplicate_english:
        errors.append(f"英文站名不唯一: {duplicate_english[:8]}")

    line_ids = [line["id"] for line in network["lines"]]
    if len(line_ids) != len(set(line_ids)):
        errors.append("线路编号不唯一")

    if not (16 <= len(network["lines"]) <= 20):
        errors.append(f"线路数量不在 16-20: {len(network['lines'])}")
    if not (180 <= len(network["stations"]) <= 230):
        errors.append(f"唯一车站数量不在 180-230: {len(network['stations'])}")

    membership = defaultdict(set)
    for line in network["lines"]:
        if len(line["stations"]) < 2:
            errors.append(f"{line['id']} 站序过短")
        for name in line_station_names(line):
            if name not in station_by_name:
                errors.append(f"{line['id']} 引用了不存在的车站 {name}")
            membership[name].add(line["id"])
        if line.get("closedLoop") and line["type"] != "核心环线":
            errors.append(f"{line['id']} 标记为环线但类型不是核心环线")
        for branch in line.get("branches", []):
            branch_point = branch["from"]
            if branch_point not in line["stations"]:
                errors.append(f"{line['id']} 支线分叉点 {branch_point} 不在主线")
            if branch["stations"][0] != branch_point:
                errors.append(f"{line['id']} 支线 {branch['name']} 未以分叉点开头")
            if len(branch["stations"]) < 3:
                errors.append(f"{line['id']} 支线 {branch['name']} 站数不足")

    for station in network["stations"]:
        expected = sorted(membership[station["name"]])
        actual = sorted(station["transferLines"])
        if expected != actual:
            errors.append(f"{station['name']} 换乘关系不一致: expected {expected}, got {actual}")

    transfer_count = sum(1 for s in network["stations"] if len(s["transferLines"]) > 1)
    if not (35 <= transfer_count <= 50):
        errors.append(f"换乘站数量不在 35-50: {transfer_count}")
    four_line = [s["name"] for s in network["stations"] if len(s["transferLines"]) >= 4]
    if len(four_line) > 2:
        errors.append(f"四线及以上换乘站超过两个: {four_line}")
    if any(len(s["transferLines"]) > 4 for s in network["stations"]):
        errors.append("存在五线及以上换乘站")

    loops = [line for line in network["lines"] if line.get("closedLoop")]
    if len(loops) != 1:
        errors.append(f"核心环线数量应为 1，实际 {len(loops)}")
    elif loops[0]["id"] != "L5":
        warnings.append("核心环线不是 L5")

    branch_lines = [line for line in network["lines"] if line.get("branches")]
    if len(branch_lines) < 2:
        errors.append("真实分叉支线少于 2 条")

    airport_lines = {
        line_id
        for station in network["stations"]
        if station["role"] == "international_airport_terminal"
        for line_id in station["transferLines"]
    }
    if len(airport_lines) < 2:
        errors.append(f"国际机场服务线路少于 2 条: {airport_lines}")

    pujiang_north = station_by_name.get("浦江北站")
    if not pujiang_north or len(pujiang_north["transferLines"]) < 3:
        errors.append("浦江北站未达到三线换乘")

    university_bad = [
        s["name"]
        for s in network["stations"]
        if s["spatialArea"] == "university" and s["district"] == "东沧港区"
    ]
    if university_bad:
        errors.append(f"大学城站点落入港区: {university_bad}")

    port_bad = [
        s["name"]
        for s in network["stations"]
        if s["spatialArea"] == "port" and s["x"] < 1700
    ]
    if port_bad:
        errors.append(f"港区站点不靠近海岸: {port_bad[:8]}")

    people = station_by_name.get("人民广场")
    if not people or not (760 <= people["x"] <= 1040 and 500 <= people["y"] <= 720):
        errors.append("人民广场不在中心城区合理范围")

    old_city_bad = [
        s["name"]
        for s in network["stations"]
        if s["spatialArea"] == "old-city" and s["x"] > 1500
    ]
    if old_city_bad:
        errors.append(f"老城站点出现在东部填海或新区: {old_city_bad}")

    airport_bad = [
        s["name"]
        for s in network["stations"]
        if "airport" in s["role"] and 700 <= s["x"] <= 1500 and 450 <= s["y"] <= 900
    ]
    if airport_bad:
        errors.append(f"机场站点位于核心城区: {airport_bad}")

    crossing_lines = []
    island_lines = []
    old_city_lines = set()
    cbd_lines = set()
    university_lines = set()
    east_tech_lines = set()
    coastal_lines = set()
    port_lines = set()
    for line in network["lines"]:
        station_names = line_station_names(line)
        sides = {station_by_name[name]["riverSide"] for name in station_names}
        areas = {station_by_name[name]["spatialArea"] for name in station_names}
        if "north" in sides and ("south" in sides or "coast" in sides):
            crossing_lines.append(line["id"])
        if "island" in sides:
            island_lines.append(line["id"])
        if "old-city" in areas:
            old_city_lines.add(line["id"])
        if "cbd" in areas or "south-subcenter" in areas:
            cbd_lines.add(line["id"])
        if "university" in areas:
            university_lines.add(line["id"])
        if "east-tech" in areas:
            east_tech_lines.add(line["id"])
        if "coastal-new-town" in areas:
            coastal_lines.add(line["id"])
        if "port" in areas:
            port_lines.add(line["id"])

    if len(crossing_lines) < 6:
        errors.append(f"跨浦江线路少于 6 条: {crossing_lines}")
    if len(island_lines) < 2:
        errors.append(f"经过鹤洲岛线路少于 2 条: {island_lines}")
    if len(old_city_lines) < 3:
        errors.append(f"服务老城线路少于 3 条: {sorted(old_city_lines)}")
    if len(cbd_lines) < 3:
        errors.append(f"服务 CBD / 南岸副中心线路少于 3 条: {sorted(cbd_lines)}")
    if len(university_lines) < 2:
        errors.append(f"服务大学城线路少于 2 条: {sorted(university_lines)}")
    if len(east_tech_lines) < 2:
        errors.append(f"服务东部科技新城线路少于 2 条: {sorted(east_tech_lines)}")
    if len(coastal_lines) < 2:
        errors.append(f"进入滨海新城线路少于 2 条: {sorted(coastal_lines)}")
    if len(port_lines) < 1:
        errors.append("没有线路进入深水港区")

    construction = [line for line in network["lines"] if line["status"] == "under_construction"]
    if len(construction) != 1:
        errors.append(f"建设中线路数量应为 1，实际 {len(construction)}")

    metrics = {
        "lineCount": len(network["lines"]),
        "uniqueStationCount": len(network["stations"]),
        "transferStationCount": transfer_count,
        "fourLineTransferStations": four_line,
        "mainRiverCrossingLineCount": len(crossing_lines),
        "hezhouIslandLineCount": len(island_lines),
        "oldCityLineCount": len(old_city_lines),
        "cbdAndSouthSubcenterLineCount": len(cbd_lines),
        "universityLineCount": len(university_lines),
        "eastTechLineCount": len(east_tech_lines),
        "coastalLineCount": len(coastal_lines),
        "portLineCount": len(port_lines),
        "airportLineCount": len(airport_lines),
        "branchLineCount": len(branch_lines),
    }
    result = {"ok": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
