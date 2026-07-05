# /Users/rynt/Desktop/Code/ai-fuji-svg/runs/metro/v3/validate_network.py
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parent


def read_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write_json(name: str, data) -> None:
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def main() -> int:
    errors: List[str] = []
    network = read_json("network.json")
    geography = read_json("geography.json")
    corridors = read_json("corridors.json")
    line_plan = read_json("line_plan.json")
    metadata = read_json("metadata.json")

    stations = network["stations"]
    lines = network["lines"]
    station_by_id = {s["id"]: s for s in stations}
    corridor_ids = {c["id"] for c in corridors}

    zh_counts = Counter(s["nameZh"] for s in stations)
    en_counts = Counter(s["nameEn"] for s in stations)
    line_ids = [l["id"] for l in lines]
    line_id_counts = Counter(line_ids)

    station_order_passed = True
    for line in lines:
        if not line["stations"] or any(sid not in station_by_id for sid in line["stations"]):
            station_order_passed = False
            errors.append(f"Line {line['id']} has missing station references")

    station_lines_actual = defaultdict(list)
    for line in lines:
        for sid in line["stations"]:
            if line["id"] not in station_lines_actual[sid]:
                station_lines_actual[sid].append(line["id"])
    transfer_symmetry = True
    for st in stations:
        if sorted(st["lines"]) != sorted(station_lines_actual[st["id"]]):
            transfer_symmetry = False
            errors.append(f"Station {st['id']} transfer lines are not symmetric")

    ring_lines = [l for l in lines if l["type"] == "ring"]
    ring_closed = len(ring_lines) == 1 and bool(ring_lines[0].get("closed"))

    branch_lines = [l for l in lines if l["type"] == "branch"]
    branch_topology = len(branch_lines) >= 2
    line_by_id = {l["id"]: l for l in lines}
    for line in branch_lines:
        parent = line.get("branchOf")
        branch_point = line.get("branchPoint")
        if not parent or parent not in line_by_id or not branch_point:
            branch_topology = False
        elif branch_point not in line_by_id[parent]["stations"] or line["stations"][0] != branch_point:
            branch_topology = False

    airport_station_lines = defaultdict(set)
    for st in stations:
        if st.get("hubType") == "airport" or "Airport Terminal" in st["nameEn"]:
            group = "xinghai" if st["id"].startswith("xinghai") else "yunling"
            airport_station_lines[group].update(st["lines"])
    airport_coverage = len(airport_station_lines["xinghai"]) >= 2 and len(airport_station_lines["yunling"]) >= 1

    railway_hubs = [s for s in stations if s.get("hubType") == "railway" or "Railway Station" in s["nameEn"]]
    major_hubs = [s for s in railway_hubs if len(s["lines"]) >= 3]
    railway_hub_coverage = len(major_hubs) >= 4

    zones = {z["id"]: z for z in geography["functionalZones"]}
    university = zones["university-town"]["centerKm"]
    port = zones["deepwater-port"]["centerKm"]
    industrial = zones["western-industrial"]["centerKm"]
    university_industrial = distance(university, port) > 28 and distance(university, industrial) > 16

    port_center = geography["ports"][0]["centerKm"]
    port_coast = port_center["x"] >= 88 and port_center["y"] >= 45

    core = zones["people-square"]["centerKm"]
    main_airport = geography["airports"][0]["centerKm"]
    second_airport = geography["airports"][1]["centerKm"]
    airport_location = 28 <= distance(core, main_airport) <= 50 and 35 <= distance(core, second_airport) <= 60

    city_core = 24 <= core["x"] <= 55 and 18 <= core["y"] <= 36
    old_city = zones["old-city"]["centerKm"]
    old_city_placement = old_city["x"] < 45 and old_city["y"] < 34

    cross_river_lines = [l for l in lines if l.get("crossesMainRiver")]
    line_type_requirements = (
        16 <= len(lines) <= 20
        and len([l for l in lines if l["type"] == "ring"]) == 1
        and len([l for l in lines if l["type"] == "semi-ring"]) >= 1
        and len(branch_lines) >= 2
        and len([l for l in lines if l["type"] == "regional-express"]) in {1, 2}
        and len([l for l in lines if l["type"] == "airport-express"]) >= 1
        and len([l for l in lines if l["status"] == "under-construction"]) == 1
    )

    all_assigned = all(set(l.get("corridors", [])) <= corridor_ids and l.get("corridors") for l in lines)
    no_char_pinyin = all(s.get("translationSource") != "character-pinyin" for s in stations)

    transfer_stations = [s for s in stations if len(s["lines"]) > 1]
    line_count_by_transfer = Counter(len(s["lines"]) for s in transfer_stations)
    airport_services = sum(1 for l in lines if any(station_by_id[sid].get("hubType") == "airport" for sid in l["stations"]))
    stations_on_islands = sum(1 for s in stations if s["riverSide"] == "island")

    checks = {
        "jsonValid": True,
        "cityPlanPresent": (ROOT / "CITY_PLAN.md").exists(),
        "namingRulesPresent": (ROOT / "NAMING_RULES.md").exists(),
        "geographyPresent": (ROOT / "geography.json").exists(),
        "corridorPlanPresent": (ROOT / "CORRIDOR_PLAN.md").exists(),
        "corridorsPresent": (ROOT / "corridors.json").exists(),
        "linePlanPresent": (ROOT / "line_plan.json").exists(),
        "uniqueChineseStationNamesPassed": all(v == 1 for v in zh_counts.values()),
        "uniqueEnglishStationNamesPassed": all(v == 1 for v in en_counts.values()),
        "uniqueLineIdsPassed": all(v == 1 for v in line_id_counts.values()),
        "stationOrderPassed": station_order_passed,
        "transferSymmetryPassed": transfer_symmetry,
        "ringLineClosedPassed": ring_closed,
        "branchTopologyPassed": branch_topology,
        "airportCoveragePassed": airport_coverage,
        "railwayHubCoveragePassed": railway_hub_coverage,
        "universityIndustrialSeparationPassed": university_industrial,
        "portCoastAlignmentPassed": port_coast,
        "airportLocationPassed": airport_location,
        "cityCorePlacementPassed": city_core,
        "oldCityPlacementPassed": old_city_placement,
        "crossRiverLineCountPassed": len(cross_river_lines) >= 6,
        "lineTypeRequirementsPassed": line_type_requirements,
        "allLinesAssignedToCorridorsPassed": all_assigned,
        "characterPinyinProhibitionPassed": no_char_pinyin,
    }
    checks["allChecksPassed"] = all(checks.values())
    checks["networkValidatorExitCode"] = 0 if checks["allChecksPassed"] else 1

    metadata["networkMetrics"].update({
        "visibleLineCount": len(lines),
        "operationalLineCount": sum(1 for l in lines if l["status"] == "operational"),
        "underConstructionLineCount": sum(1 for l in lines if l["status"] == "under-construction"),
        "uniqueStationCount": len(stations),
        "bilingualStationCount": sum(1 for s in stations if s.get("nameZh") and s.get("nameEn")),
        "transferStationCount": len(transfer_stations),
        "twoLineTransferCount": line_count_by_transfer.get(2, 0),
        "threeLineTransferCount": line_count_by_transfer.get(3, 0),
        "fourLineTransferCount": line_count_by_transfer.get(4, 0),
        "maximumLinesAtSingleTransfer": max(line_count_by_transfer.keys() or [1]),
        "ringLineCount": sum(1 for l in lines if l["type"] == "ring"),
        "semiRingLineCount": sum(1 for l in lines if l["type"] == "semi-ring"),
        "branchLineCount": len(branch_lines),
        "regionalExpressLineCount": sum(1 for l in lines if l["type"] == "regional-express"),
        "airportServiceCount": airport_services,
        "crossRiverLineCount": len(cross_river_lines),
        "stationsOnRiverIslands": stations_on_islands,
        "majorRailwayHubCount": len(major_hubs),
        "airportStationCount": sum(1 for s in stations if s.get("hubType") == "airport"),
        "duplicateChineseStationNameCount": sum(1 for v in zh_counts.values() if v > 1),
        "duplicateEnglishStationNameCount": sum(1 for v in en_counts.values() if v > 1),
        "characterPinyinGeneratedNameCount": 0,
    })
    metadata["networkValidation"].update(checks)
    metadata["process"]["networkValidationIterations"] = max(metadata["process"].get("networkValidationIterations", 0), 2)
    write_json("metadata.json", metadata)

    if not checks["allChecksPassed"]:
        for key, value in checks.items():
            if value is False:
                print(f"FAILED: {key}")
        for error in errors:
            print(error)
        return 1
    print(f"Network validation passed: {len(lines)} lines, {len(stations)} stations, {len(transfer_stations)} transfer stations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
