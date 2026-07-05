#!/usr/bin/env python3
"""Validate Hailan metro network data and update metadata."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dist(a: dict[str, object], b: dict[str, object]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def metrics(network: dict[str, object]) -> dict[str, object]:
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
        "ringLineCount": sum(1 for line in lines if line["isRing"]),
        "branchLineCount": sum(1 for line in lines if line["isBranch"]),
        "airportServiceCount": sum(1 for line in lines if line["type"] == "airport_express" or any("机场" in name or "航站楼" in name for name in line["stations"])),
        "crossRiverLineCount": sum(1 for line in lines if line["crossesMainRiver"]),
        "airportCount": len([s for s in stations if s.get("hubType") in {"international_airport", "secondary_airport"}]),
        "majorRailwayStationCount": len([s for s in stations if s.get("hubType") in {"main_high_speed_railway_station", "major_railway_station", "old_railway_station"}]),
        "bilingualStationCount": len([s for s in stations if s.get("nameZh") and s.get("nameEn")]),
        "riverCount": 1 + len(network["geography"]["tributaries"]),  # type: ignore[index]
        "islandCount": len(network["geography"]["islands"]),  # type: ignore[index]
    }


def validate(network: dict[str, object]) -> tuple[dict[str, bool | int], list[str]]:
    failures: list[str] = []
    checks: dict[str, bool | int] = {}
    stations = network["stations"]  # type: ignore[index]
    lines = network["lines"]  # type: ignore[index]
    station_by_name = {station["nameZh"]: station for station in stations}
    line_by_id = {line["id"]: line for line in lines}
    derived_memberships: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        for segment in line["segments"]:
            for name in segment:
                derived_memberships[name].add(line["id"])

    def check(key: str, condition: bool, message: str) -> None:
        checks[key] = condition
        if not condition:
            failures.append(message)

    check("jsonValid", True, "network.json is not valid JSON")
    check("cityPlanPresent", (ROOT / "CITY_PLAN.md").exists(), "CITY_PLAN.md missing")
    check("namingRulesPresent", (ROOT / "NAMING_RULES.md").exists(), "NAMING_RULES.md missing")
    check("uniqueChineseStationNamesPassed", len(station_by_name) == len(stations), "Chinese station names are not unique")
    check("uniqueEnglishStationNamesPassed", len({station["nameEn"] for station in stations}) == len(stations), "English station names are not unique")
    check("uniqueLineIdsPassed", len(line_by_id) == len(lines), "Line IDs are not unique")
    check(
        "stationOrderPassed",
        all(segment and all(name in station_by_name for name in segment) for line in lines for segment in line["segments"]),
        "A line segment has missing stations or empty order",
    )
    symmetry_ok = True
    for name, station in station_by_name.items():
        if set(station["transferLines"]) != derived_memberships[name]:
            symmetry_ok = False
            failures.append(f"Transfer membership mismatch at {name}")
    check("transferSymmetryPassed", symmetry_ok, "Transfer relationships are not symmetric")
    ring_ok = all(line["segments"][0][0] == line["segments"][0][-1] for line in lines if line["isRing"])
    check("ringLineClosedPassed", ring_ok, "Ring line is not closed")
    branch_ok = True
    for line in lines:
        if not line["isBranch"]:
            continue
        branch = line["branchInfo"]
        station = branch["branchStation"]
        containing = [segment for segment in line["segments"] if station in segment]
        branch_ok = branch_ok and bool(station) and len(containing) >= 3
    check("branchTopologyPassed", branch_ok, "Branch line topology is invalid")

    linwan = station_by_name.get("临湾国际机场")
    airport_ok = bool(linwan and len(linwan["transferLines"]) >= 2)
    check("airportCoveragePassed", airport_ok, "International airport is not served by at least two lines")

    railway_names = ["海澜总站", "北苑高铁站", "南湾铁路站", "东澄站", "北城火车站"]
    railway_ok = all(name in station_by_name and len(station_by_name[name]["transferLines"]) >= 3 for name in railway_names)
    check("railwayHubCoveragePassed", railway_ok, "A major railway station has fewer than three lines")

    university = station_by_name.get("青岚大学城")
    port = station_by_name.get("深水港")
    university_ok = bool(university and port and university["district"] == "青岚区" and dist(university, port) > 1300)
    check("universityIndustrialSeparationPassed", university_ok, "University town is too close to port or industrial district")

    port_ok = bool(port and float(port["x"]) > 2100 and 780 <= float(port["y"]) <= 1120)
    check("portCoastAlignmentPassed", port_ok, "Deepwater port is not aligned with coast")

    core = station_by_name.get("人民广场")
    core_ok = bool(core and 520 <= float(core["x"]) <= 900 and 500 <= float(core["y"]) <= 720)
    check("cityCorePlacementPassed", core_ok, "People's Square is not in the central old-city area")

    old_city = station_by_name.get("崇安门")
    old_city_ok = bool(old_city and old_city["district"] == "崇安区" and float(old_city["x"]) < 1000 and float(old_city["y"]) < 720)
    check("oldCityPlacementPassed", old_city_ok, "Old city marker is misplaced")

    xiling = station_by_name.get("西岭机场")
    airport_location_ok = bool(linwan and xiling and float(linwan["x"]) > 1900 and float(linwan["y"]) > 1100 and float(xiling["x"]) < 420 and float(xiling["y"]) < 480)
    check("airportLocationPassed", airport_location_ok, "Airport locations are not peripheral or directionally separated")

    m = metrics(network)
    line_type_ok = (
        16 <= int(m["visibleLineCount"]) <= 20
        and 180 <= int(m["uniqueStationCount"]) <= 230
        and 35 <= int(m["transferStationCount"]) <= 50
        and int(m["fourLineTransferCount"]) <= 2
        and int(m["ringLineCount"]) == 1
        and int(m["branchLineCount"]) >= 2
        and int(m["underConstructionLineCount"]) == 1
        and int(m["airportServiceCount"]) >= 2
    )
    check("crossRiverLineCountPassed", int(m["crossRiverLineCount"]) >= 6, "Fewer than six lines cross the main river")
    check("lineTypeRequirementsPassed", line_type_ok, "Line/station/transfer/type requirements not satisfied")
    checks["networkValidatorExitCode"] = 0 if not failures else 1
    checks["allChecksPassed"] = not failures
    return checks, failures


def update_metadata(checks: dict[str, bool | int], failures: list[str], network: dict[str, object], exit_code: int) -> None:
    metadata_path = ROOT / "metadata.json"
    metadata = load_json(metadata_path)
    metadata["networkMetrics"] = {**metadata.get("networkMetrics", {}), **metrics(network)}
    checks["networkValidatorExitCode"] = exit_code
    checks["allChecksPassed"] = exit_code == 0
    metadata["networkValidation"] = {**metadata.get("networkValidation", {}), **checks}
    process = metadata["process"]  # type: ignore[index]
    process["networkValidationIterations"] = int(process.get("networkValidationIterations") or 0) + 1
    result = metadata["result"]  # type: ignore[index]
    commands = result.setdefault("commandsExecuted", [])
    command = "python3 validate_network.py network.json"
    if command not in commands:
        commands.append(command)
    if failures:
        issues = result.setdefault("issuesFound", [])
        for failure in failures:
            if failure not in issues:
                issues.append(failure)
    save_json(metadata_path, metadata)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "network.json"
    if not path.is_absolute():
        path = ROOT / path
    try:
        network = load_json(path)
    except Exception as exc:
        print(f"FAIL jsonValid: {exc}")
        metadata = load_json(ROOT / "metadata.json")
        metadata["networkValidation"]["jsonValid"] = False  # type: ignore[index]
        metadata["networkValidation"]["networkValidatorExitCode"] = 1  # type: ignore[index]
        metadata["networkValidation"]["allChecksPassed"] = False  # type: ignore[index]
        save_json(ROOT / "metadata.json", metadata)
        return 1
    checks, failures = validate(network)
    exit_code = 0 if not failures else 1
    update_metadata(checks, failures, network, exit_code)
    for key, value in checks.items():
        passed = (value == 0) if key.endswith("ExitCode") else bool(value)
        print(f"{'PASS' if passed else 'FAIL'} {key}: {value}")
    if failures:
        for failure in failures:
            print(f"FAIL detail: {failure}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
