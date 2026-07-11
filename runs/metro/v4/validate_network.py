#!/usr/bin/env python3
"""Validate the v4 fictional metro network.

The validator deliberately emits machine-readable JSON on stdout.  It accepts
the canonical v4 schema, while tolerating records stored as either lists or
``{id: record}`` mappings so that it remains useful while network.json is being
assembled.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


VERSION = "1.0"


def _records(value: Any) -> list[dict[str, Any]]:
    """Return object records from a list or an id-keyed mapping."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                copy = dict(item)
                copy.setdefault("id", str(key))
                result.append(copy)
        return result
    return []


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            item_id = item.strip()
        elif isinstance(item, dict):
            item_id = _string(
                item.get("id")
                or item.get("stationId")
                or item.get("lineId")
                or item.get("station")
                or item.get("line")
            )
        else:
            item_id = ""
        if item_id:
            result.append(item_id)
    return result


def _tokens(*values: Any) -> str:
    chunks: list[str] = []
    for value in values:
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, (list, tuple, set)):
            chunks.extend(str(part) for part in value)
        elif isinstance(value, dict):
            chunks.extend(str(part) for part in value.values())
    return " ".join(chunks).casefold()


class Report:
    def __init__(self, input_path: Path) -> None:
        self.payload: dict[str, Any] = {
            "validator": "validate_network",
            "version": VERSION,
            "input": str(input_path),
            "valid": False,
            "summary": {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0},
            "metrics": {},
            "checks": [],
            "errors": [],
        }

    def add(
        self,
        check_id: str,
        status: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        item: dict[str, Any] = {"id": check_id, "status": status, "message": message}
        if details is not None:
            item["details"] = details
        self.payload["checks"].append(item)
        counter = {
            "pass": "passed",
            "fail": "failed",
            "warn": "warnings",
            "skip": "skipped",
        }[status]
        self.payload["summary"][counter] += 1

    def finish(self) -> dict[str, Any]:
        self.payload["valid"] = self.payload["summary"]["failed"] == 0 and not self.payload["errors"]
        return self.payload


def _normalised_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _duplicate_values(records: Iterable[dict[str, Any]], key: str) -> dict[str, list[str]]:
    by_value: dict[str, list[str]] = defaultdict(list)
    display: dict[str, str] = {}
    for record in records:
        value = _string(record.get(key))
        if not value:
            continue
        normalised = _normalised_name(value)
        display.setdefault(normalised, value)
        by_value[normalised].append(_string(record.get("id")) or "<missing-id>")
    return {display[value]: ids for value, ids in by_value.items() if len(ids) > 1}


def _is_pinyin_syllable(token: str) -> bool:
    """Conservative detector for *space-separated* pinyin syllables.

    It is intentionally not a transliterator: the source Chinese is never
    converted.  The check only detects traces such as ``Qing Yun Lu`` that are
    already present in the English field.
    """
    token = token.casefold().replace("ü", "v")
    if not re.fullmatch(r"[a-zv]{1,7}", token):
        return False
    initials = (
        "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
        "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w",
    )
    finals = {
        "a", "o", "e", "i", "u", "v", "ai", "ei", "ao", "ou", "an", "en",
        "ang", "eng", "ong", "er", "ia", "ie", "iao", "iu", "ian", "in",
        "iang", "ing", "iong", "ua", "uo", "uai", "ui", "uan", "un", "uang",
        "ueng", "ue", "ve", "van", "vn",
    }
    if token in finals:
        return True
    for initial in initials:
        if token.startswith(initial) and token[len(initial) :] in finals:
            return True
    return False


def _suspicious_english(station: dict[str, Any]) -> str | None:
    english = _string(station.get("nameEn"))
    if not english:
        return "empty"
    words = re.findall(r"[A-Za-zÜüVv]+", english)
    if any(len(word) == 1 and word.casefold() not in {"s"} for word in words) and len(words) >= 2:
        return "single-letter token suggests character-by-character romanisation"
    # Functional suffixes are valid translations, but the proper-name portion
    # before them should still be joined (Qingyun Road, not Qing Yun Road).
    functional = {
        "road", "avenue", "street", "square", "plaza", "park", "bridge", "gate",
        "lake", "bay", "island", "port", "harbor", "harbour", "wharf", "ferry",
        "railway", "station", "airport", "international", "terminal", "university",
        "town", "center", "centre", "civic", "convention", "exhibition", "museum",
        "hospital", "theater", "theatre", "opera", "financial", "science", "technology",
        "north", "south", "east", "west", "old", "new", "city", "people", "people's",
    }
    name_words = [word for word in words if word.casefold() not in functional]
    han_count = len(re.findall(r"[\u3400-\u9fff]", _string(station.get("nameZh"))))
    if len(name_words) >= 2 and han_count >= len(name_words) and all(
        _is_pinyin_syllable(word) for word in name_words
    ):
        return "space-separated pinyin-like syllables; proprietary names should normally be joined"
    return None


def _normalise_bank(value: Any) -> str | None:
    text = _tokens(value)
    if not text:
        return None
    if any(token in text for token in ("北岸", "north bank", "northbank", "northern bank")) or text in {"n", "north"}:
        return "north"
    if any(token in text for token in ("南岸", "south bank", "southbank", "southern bank")) or text in {"s", "south"}:
        return "south"
    if any(token in text for token in ("江心", "河洲", "island", "mid-river")):
        return "island"
    return None


def _is_loop_line(line: dict[str, Any]) -> bool:
    line_type = _string(line.get("type")).casefold()
    if line_type in {"semi-ring", "semi ring", "half-ring", "half ring"}:
        return False
    if line_type == "ring":
        return True
    text = _tokens(line.get("type"), line.get("role"), line.get("nameZh"), line.get("nameEn"))
    return any(token in text for token in ("环线", "环状", "loop", "ring", "circle"))


def _loop_is_explicitly_closed(line: dict[str, Any], station_ids: list[str]) -> bool:
    if len(station_ids) >= 3 and station_ids[0] == station_ids[-1]:
        return True
    for key in ("closed", "isClosed", "loopClosed"):
        if line.get(key) is True:
            return True
    topology = line.get("topology")
    if isinstance(topology, dict) and topology.get("closed") is True:
        return True
    for key in ("schematicPath", "points", "path"):
        points = line.get(key)
        if not isinstance(points, list) or len(points) < 4:
            continue

        def coordinate(value: Any) -> tuple[float, float] | None:
            if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                return (float(value[0]), float(value[1]))
            if isinstance(value, dict) and isinstance(value.get("x"), (int, float)) and isinstance(value.get("y"), (int, float)):
                return (float(value["x"]), float(value["y"]))
            return None

        first, last = coordinate(points[0]), coordinate(points[-1])
        if first is not None and first == last:
            return True
    return False


def _normalise_branch_relations(data: dict[str, Any], lines: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    raw = data.get("branchRelations")
    candidates: list[Any]
    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        candidates = []
        for key, value in raw.items():
            if isinstance(value, dict):
                copy = dict(value)
                copy.setdefault("branchLine", key)
                candidates.append(copy)
            elif isinstance(value, str):
                candidates.append({"branchLine": key, "parentLine": value})
    else:
        candidates = []

    for relation in candidates:
        if not isinstance(relation, dict):
            continue
        branch = _string(
            relation.get("branchLine")
            or relation.get("branchLineId")
            or relation.get("branch")
            or relation.get("child")
        )
        parent = _string(
            relation.get("parentLine")
            or relation.get("parentLineId")
            or relation.get("parent")
            or relation.get("trunk")
        )
        junction = _string(
            relation.get("junctionStation")
            or relation.get("junctionStationId")
            or relation.get("junction")
            or relation.get("branchPoint")
        )
        if branch or parent or junction:
            result.append({"branch": branch, "parent": parent, "junction": junction})

    existing_branches = {relation["branch"] for relation in result if relation["branch"]}
    for line in lines:
        branch = _string(line.get("id"))
        parent_value = line.get("branchOf")
        parent = _string(parent_value)
        junction = _string(line.get("junctionStation") or line.get("branchPoint"))
        if isinstance(parent_value, dict):
            parent = _string(parent_value.get("line") or parent_value.get("lineId") or parent_value.get("id"))
            junction = junction or _string(
                parent_value.get("station") or parent_value.get("stationId") or parent_value.get("junction")
            )
        if parent and branch not in existing_branches:
            result.append({"branch": branch, "parent": parent, "junction": junction})
    return result


def _airport_key(station: dict[str, Any]) -> str:
    hub = station.get("hub")
    if isinstance(hub, dict):
        explicit = _string(hub.get("id") or hub.get("nameEn") or hub.get("nameZh"))
    else:
        explicit = _string(hub)
    if explicit:
        return explicit.casefold()
    english = _string(station.get("nameEn"))
    chinese = _string(station.get("nameZh"))
    english = re.sub(r"\b(?:airport\s+)?terminal\s*\d+\b", "", english, flags=re.I).strip(" -–—")
    chinese = re.sub(r"(?:机场)?(?:航站楼|航站区|[TＴ]\s*\d+)$", "", chinese, flags=re.I).strip()
    return (english or chinese or _string(station.get("id"))).casefold()


def validate(data: dict[str, Any], args: argparse.Namespace, report: Report) -> dict[str, Any]:
    lines = _records(data.get("lines"))
    stations = _records(data.get("stations"))
    line_by_id = {_string(line.get("id")): line for line in lines if _string(line.get("id"))}
    station_by_id = {_string(station.get("id")): station for station in stations if _string(station.get("id"))}

    report.payload["metrics"].update(
        {
            "lineCount": len(lines),
            "stationCount": len(stations),
            "interchangeStationCount": 0,
            "crossRiverLineCount": 0,
            "loopLineCount": 0,
            "branchRelationCount": 0,
            "constructionLineCount": 0,
        }
    )

    city = data.get("city")
    city_ok = isinstance(city, dict) and bool(
        _string(city.get("nameZh") or city.get("name"))
    ) and bool(_string(city.get("nameEn") or city.get("englishName")))
    report.add(
        "schema.city",
        "pass" if city_ok else "fail",
        "city contains non-empty Chinese and English names" if city_ok else "city must contain non-empty Chinese and English names",
    )
    geo_ok = bool(data.get("regions")) and bool(data.get("geography"))
    report.add(
        "schema.regions_geography",
        "pass" if geo_ok else "fail",
        "regions and geography are present" if geo_ok else "top-level regions and geography must both be present",
    )

    line_ids = [_string(line.get("id")) for line in lines]
    station_ids = [_string(station.get("id")) for station in stations]
    missing_line_ids = [index for index, value in enumerate(line_ids) if not value]
    duplicate_line_ids = sorted(key for key, count in Counter(line_ids).items() if key and count > 1)
    missing_station_ids = [index for index, value in enumerate(station_ids) if not value]
    duplicate_station_ids = sorted(key for key, count in Counter(station_ids).items() if key and count > 1)
    ids_ok = not (missing_line_ids or duplicate_line_ids or missing_station_ids or duplicate_station_ids)
    report.add(
        "schema.unique_ids",
        "pass" if ids_ok else "fail",
        "all line and station ids are non-empty and unique" if ids_ok else "line/station ids must be non-empty and unique",
        {
            "missingLineIdIndexes": missing_line_ids,
            "duplicateLineIds": duplicate_line_ids,
            "missingStationIdIndexes": missing_station_ids,
            "duplicateStationIds": duplicate_station_ids,
        },
    )

    report.add(
        "scale.line_count",
        "pass" if len(lines) == args.expected_lines else "fail",
        f"line count is {len(lines)}; expected exactly {args.expected_lines}",
        {"actual": len(lines), "expected": args.expected_lines},
    )
    station_count_ok = args.min_stations <= len(stations) <= args.max_stations
    report.add(
        "scale.station_count",
        "pass" if station_count_ok else "fail",
        f"unique station record count is {len(stations)}; expected {args.min_stations}–{args.max_stations}",
        {"actual": len(stations), "minimum": args.min_stations, "maximum": args.max_stations},
    )

    missing_line_names = [
        _string(line.get("id")) or f"index:{index}"
        for index, line in enumerate(lines)
        if not _string(line.get("nameZh")) or not _string(line.get("nameEn"))
    ]
    duplicate_line_zh = _duplicate_values(lines, "nameZh")
    duplicate_line_en = _duplicate_values(lines, "nameEn")
    line_names_ok = not (missing_line_names or duplicate_line_zh or duplicate_line_en)
    report.add(
        "names.lines",
        "pass" if line_names_ok else "fail",
        "all bilingual line names are non-empty and unique" if line_names_ok else "line names must be bilingual and unique",
        {
            "missing": missing_line_names,
            "duplicateChinese": duplicate_line_zh,
            "duplicateEnglish": duplicate_line_en,
        },
    )

    missing_zh = [_string(s.get("id")) or f"index:{i}" for i, s in enumerate(stations) if not _string(s.get("nameZh"))]
    missing_en = [_string(s.get("id")) or f"index:{i}" for i, s in enumerate(stations) if not _string(s.get("nameEn"))]
    duplicate_zh = _duplicate_values(stations, "nameZh")
    duplicate_en = _duplicate_values(stations, "nameEn")
    report.add(
        "names.station_chinese_unique",
        "pass" if not missing_zh and not duplicate_zh else "fail",
        "all Chinese station names are non-empty and unique" if not missing_zh and not duplicate_zh else "Chinese station names must be non-empty and unique",
        {"missing": missing_zh, "duplicates": duplicate_zh},
    )
    report.add(
        "names.station_english_unique",
        "pass" if not missing_en and not duplicate_en else "fail",
        "all English station names are non-empty and unique" if not missing_en and not duplicate_en else "English station names must be non-empty and unique",
        {"missing": missing_en, "duplicates": duplicate_en},
    )

    suspicious = []
    for station in stations:
        reason = _suspicious_english(station)
        if reason and reason != "empty":
            suspicious.append(
                {
                    "id": _string(station.get("id")),
                    "nameZh": _string(station.get("nameZh")),
                    "nameEn": _string(station.get("nameEn")),
                    "reason": reason,
                }
            )
    report.add(
        "names.no_character_pinyin_traces",
        "pass" if not suspicious else "fail",
        "no character-by-character pinyin traces detected" if not suspicious else f"detected {len(suspicious)} suspicious English station names",
        {"suspicious": suspicious[:50], "truncated": len(suspicious) > 50},
    )

    missing_order: list[str] = []
    duplicate_order: dict[str, list[str]] = {}
    unknown_stations_on_lines: dict[str, list[str]] = {}
    for line in lines:
        line_id = _string(line.get("id")) or "<missing-id>"
        ordered = _id_list(line.get("stations"))
        if len(ordered) < 2:
            missing_order.append(line_id)
        counts = Counter(ordered)
        duplicates = [sid for sid, count in counts.items() if count > 1]
        # A repeated first station is the conventional explicit ring closure.
        if duplicates and not (len(duplicates) == 1 and ordered and duplicates[0] == ordered[0] == ordered[-1]):
            duplicate_order[line_id] = sorted(duplicates)
        unknown = sorted({sid for sid in ordered if sid not in station_by_id})
        if unknown:
            unknown_stations_on_lines[line_id] = unknown
    order_ok = not (missing_order or duplicate_order or unknown_stations_on_lines)
    report.add(
        "topology.line_station_order",
        "pass" if order_ok else "fail",
        "all lines have complete ordered station lists" if order_ok else "line station lists are incomplete or reference invalid stations",
        {
            "fewerThanTwoStations": missing_order,
            "unexpectedDuplicates": duplicate_order,
            "unknownStationIds": unknown_stations_on_lines,
        },
    )

    asymmetric: list[dict[str, str]] = []
    unknown_lines_on_stations: dict[str, list[str]] = {}
    for line in lines:
        line_id = _string(line.get("id"))
        for station_id in _id_list(line.get("stations")):
            station = station_by_id.get(station_id)
            if station is not None and line_id not in _id_list(station.get("lines")):
                asymmetric.append({"station": station_id, "line": line_id, "missingFrom": "station.lines"})
    for station in stations:
        station_id = _string(station.get("id"))
        declared_lines = _id_list(station.get("lines"))
        unknown = sorted({line_id for line_id in declared_lines if line_id not in line_by_id})
        if unknown:
            unknown_lines_on_stations[station_id] = unknown
        for line_id in declared_lines:
            line = line_by_id.get(line_id)
            if line is not None and station_id not in _id_list(line.get("stations")):
                asymmetric.append({"station": station_id, "line": line_id, "missingFrom": "line.stations"})
    symmetry_ok = not asymmetric and not unknown_lines_on_stations
    report.add(
        "topology.symmetric_line_membership",
        "pass" if symmetry_ok else "fail",
        "station.lines and line.stations are symmetric" if symmetry_ok else "station/line membership is not symmetric",
        {
            "asymmetricRelations": asymmetric[:100],
            "asymmetricTruncated": len(asymmetric) > 100,
            "unknownLineIds": unknown_lines_on_stations,
        },
    )

    explicit_interchange_flags = any("isInterchange" in station for station in stations)
    interchange_stations = [
        station for station in stations
        if station.get("isInterchange") is True
        or (not explicit_interchange_flags and len(set(_id_list(station.get("lines")))) >= 2)
    ]
    interchange_count = len(interchange_stations)
    report.payload["metrics"]["interchangeStationCount"] = interchange_count
    interchange_ok = args.min_interchanges <= interchange_count <= args.max_interchanges
    report.add(
        "scale.interchange_count",
        "pass" if interchange_ok else "fail",
        f"interchange count is {interchange_count}; expected {args.min_interchanges}–{args.max_interchanges}",
        {"actual": interchange_count, "minimum": args.min_interchanges, "maximum": args.max_interchanges},
    )
    excessive = [
        {"id": _string(station.get("id")), "lineCount": len(set(_id_list(station.get("lines"))))}
        for station in interchange_stations
        if len(set(_id_list(station.get("lines")))) > 4
    ]
    four_line = [
        _string(station.get("id"))
        for station in interchange_stations
        if len(set(_id_list(station.get("lines")))) == 4
    ]
    concentration_ok = not excessive and len(four_line) <= 2
    report.add(
        "topology.interchange_concentration",
        "pass" if concentration_ok else "fail",
        "interchanges are limited to at most two four-line hubs and no five-line hubs" if concentration_ok else "interchange hubs are over-concentrated",
        {"moreThanFourLines": excessive, "fourLineStations": four_line},
    )

    loop_lines = [line for line in lines if _is_loop_line(line)]
    report.payload["metrics"]["loopLineCount"] = len(loop_lines)
    unclosed_loops = [
        _string(line.get("id"))
        for line in loop_lines
        if not _loop_is_explicitly_closed(line, _id_list(line.get("stations")))
    ]
    loop_ok = bool(loop_lines) and not unclosed_loops
    report.add(
        "topology.loop_closed",
        "pass" if loop_ok else "fail",
        "at least one loop line has explicit closure evidence" if loop_ok else "a loop line is required and every loop must be explicitly closed",
        {"loopLines": [_string(line.get("id")) for line in loop_lines], "unclosed": unclosed_loops},
    )

    relations = _normalise_branch_relations(data, lines)
    report.payload["metrics"]["branchRelationCount"] = len(relations)
    invalid_relations: list[dict[str, Any]] = []
    valid_relations: list[dict[str, Any]] = []
    for relation in relations:
        branch = line_by_id.get(relation["branch"])
        parent = line_by_id.get(relation["parent"])
        branch_stations = _id_list(branch.get("stations")) if branch else []
        parent_stations = _id_list(parent.get("stations")) if parent else []
        shared = sorted(set(branch_stations) & set(parent_stations))
        junction = relation["junction"]
        reasons: list[str] = []
        if branch is None:
            reasons.append("unknown branch line")
        if parent is None:
            reasons.append("unknown parent line")
        if branch is not None and parent is not None and not shared:
            reasons.append("branch and parent share no station")
        if not junction:
            reasons.append("junction station is not explicit")
        elif junction not in shared:
            reasons.append("junction is not shared by branch and parent")
        if branch is not None and parent is not None and set(branch_stations) <= set(parent_stations):
            reasons.append("branch never diverges from parent")
        evidence = {**relation, "sharedStations": shared, "reasons": reasons}
        (invalid_relations if reasons else valid_relations).append(evidence)
    branch_ok = len(valid_relations) >= args.min_branches and not invalid_relations
    report.add(
        "topology.real_branches",
        "pass" if branch_ok else "fail",
        f"at least {args.min_branches} explicit, divergent branch relations are valid" if branch_ok else "two valid branch relations with explicit junctions and real divergence are required",
        {"valid": valid_relations, "invalid": invalid_relations, "minimum": args.min_branches},
    )

    airport_groups: dict[str, set[str]] = defaultdict(set)
    airport_records: dict[str, list[str]] = defaultdict(list)
    for station in stations:
        descriptor = _tokens(
            station.get("nameZh"), station.get("nameEn"), station.get("role"), station.get("hub"), station.get("area")
        )
        if "机场" in descriptor or "airport" in descriptor or "terminal" in descriptor:
            key = _airport_key(station)
            airport_groups[key].update(_id_list(station.get("lines")))
            airport_records[key].append(_string(station.get("id")))
    international_keys = [
        key
        for key, ids in airport_records.items()
        if any(
            "国际机场" in _tokens(station_by_id[sid].get("nameZh"), station_by_id[sid].get("hub"))
            or "international airport" in _tokens(station_by_id[sid].get("nameEn"), station_by_id[sid].get("hub"))
            for sid in ids
            if sid in station_by_id
        )
    ]
    candidate_airports = international_keys or list(airport_groups)
    main_airport_key = max(candidate_airports, key=lambda key: len(airport_groups[key]), default=None)
    main_airport_lines = sorted(airport_groups[main_airport_key]) if main_airport_key is not None else []
    airport_ok = len(main_airport_lines) >= 2
    report.payload["metrics"]["airportHubCount"] = len(airport_groups)
    report.payload["metrics"]["mainAirportLineCount"] = len(main_airport_lines)
    report.add(
        "hubs.international_airport_two_lines",
        "pass" if airport_ok else "fail",
        "the international airport complex is served by at least two lines" if airport_ok else "the international airport complex must be served by at least two lines",
        {
            "selectedAirportGroup": main_airport_key,
            "lineIds": main_airport_lines,
            "groups": {key: {"stations": airport_records[key], "lines": sorted(value)} for key, value in airport_groups.items()},
        },
    )

    high_speed_stations = []
    for station in stations:
        descriptor = _tokens(station.get("nameZh"), station.get("nameEn"), station.get("role"), station.get("hub"))
        if "高铁" in descriptor or "high-speed" in descriptor or "high speed" in descriptor or "hsr" in descriptor:
            high_speed_stations.append(station)
    best_hsr = max(high_speed_stations, key=lambda station: len(set(_id_list(station.get("lines")))), default=None)
    hsr_lines = sorted(set(_id_list(best_hsr.get("lines")))) if best_hsr else []
    hsr_ok = len(hsr_lines) >= 3
    report.payload["metrics"]["highSpeedRailHubMaxLineCount"] = len(hsr_lines)
    report.add(
        "hubs.high_speed_rail_three_lines",
        "pass" if hsr_ok else "fail",
        "a high-speed railway hub is served by at least three lines" if hsr_ok else "a high-speed railway hub with at least three metro lines is required",
        {
            "station": _string(best_hsr.get("id")) if best_hsr else None,
            "lineIds": hsr_lines,
            "candidates": [
                {"id": _string(station.get("id")), "lines": sorted(set(_id_list(station.get("lines"))))}
                for station in high_speed_stations
            ],
        },
    )

    cross_river_lines: list[str] = []
    for line in lines:
        ordered = _id_list(line.get("stations"))
        banks = {
            bank
            for sid in ordered
            if sid in station_by_id
            for bank in [_normalise_bank(station_by_id[sid].get("riverBank"))]
            if bank
        }
        if {"north", "south"} <= banks:
            cross_river_lines.append(_string(line.get("id")))
    report.payload["metrics"]["crossRiverLineCount"] = len(cross_river_lines)
    cross_river_ok = len(cross_river_lines) >= args.min_cross_river_lines
    report.add(
        "geography.cross_river_lines",
        "pass" if cross_river_ok else "fail",
        f"{len(cross_river_lines)} lines connect north and south banks; minimum is {args.min_cross_river_lines}",
        {"lineIds": cross_river_lines, "minimum": args.min_cross_river_lines},
    )

    construction_lines = [
        line
        for line in lines
        if any(
            token in _tokens(line.get("status"), line.get("type"))
            for token in ("建设中", "在建", "under construction", "construction")
        )
    ]
    report.payload["metrics"]["constructionLineCount"] = len(construction_lines)
    report.add(
        "operations.construction_line",
        "pass" if len(construction_lines) == 1 else "fail",
        f"construction line count is {len(construction_lines)}; expected exactly 1",
        {"lineIds": [_string(line.get("id")) for line in construction_lines], "expected": 1},
    )

    missing_fields: dict[str, list[str]] = {}
    station_required = (
        "nameZh", "nameEn", "district", "role", "lines", "terminal", "hub",
        "riverBank", "area", "geoKm", "schematic", "label",
    )
    for station in stations:
        absent = [key for key in station_required if key not in station]
        geo = station.get("geoKm")
        schematic = station.get("schematic")
        if not isinstance(geo, dict) or not all(isinstance(geo.get(axis), (int, float)) for axis in ("x", "y")):
            absent.append("geoKm{x,y}")
        if not isinstance(schematic, dict) or not all(isinstance(schematic.get(axis), (int, float)) for axis in ("x", "y")):
            absent.append("schematic{x,y}")
        if absent:
            missing_fields[_string(station.get("id")) or "<missing-id>"] = sorted(set(absent))
    report.add(
        "schema.station_fields",
        "pass" if not missing_fields else "fail",
        "all station records contain the required v4 fields and coordinates" if not missing_fields else "station records are missing required v4 fields",
        {"stations": dict(list(missing_fields.items())[:100]), "truncated": len(missing_fields) > 100},
    )

    line_missing_fields: dict[str, list[str]] = {}
    for line in lines:
        absent = [
            key for key in ("nameZh", "nameEn", "color", "type", "status", "corridors", "stations")
            if key not in line or line.get(key) in (None, "", [])
        ]
        if absent:
            line_missing_fields[_string(line.get("id")) or "<missing-id>"] = absent
    report.add(
        "schema.line_fields",
        "pass" if not line_missing_fields else "fail",
        "all line records contain required v4 fields" if not line_missing_fields else "line records are missing required v4 fields",
        {"lines": line_missing_fields},
    )

    return report.finish()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the v4 fictional metro network and emit JSON.")
    parser.add_argument("--input", default="network.json", help="network JSON path (default: network.json)")
    parser.add_argument("--output", help="also write the JSON report to this path")
    parser.add_argument("--expected-lines", type=int, default=17)
    parser.add_argument("--min-stations", type=int, default=180)
    parser.add_argument("--max-stations", type=int, default=190)
    parser.add_argument("--min-interchanges", type=int, default=35)
    parser.add_argument("--max-interchanges", type=int, default=50)
    parser.add_argument("--min-branches", type=int, default=2)
    parser.add_argument("--min-cross-river-lines", type=int, default=6)
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    report = Report(input_path)
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top-level JSON value must be an object")
        payload = validate(data, args, report)
        exit_code = 0 if payload["valid"] else 1
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report.payload["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        payload = report.finish()
        exit_code = 2

    text = json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2, sort_keys=False)
    print(text)
    if args.output:
        try:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"validate_network: cannot write {args.output}: {exc}", file=sys.stderr)
            return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
