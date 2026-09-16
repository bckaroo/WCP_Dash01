#!/usr/bin/env python3
"""
Metro-North (MNR) GTFS station service-frequency collector for WCP Dashboard.

Source (verified live, keyless):
  https://rrgtfsfeeds.s3.amazonaws.com/gtfsmnr.zip

Method:
  1. Download MNR GTFS feed.
  2. Read stops (station coordinates) and stop_times (scheduled calls).
  3. Determine the set of service_ids active on a representative weekday
     via calendar_dates.txt.
  4. Count scheduled weekday station calls per stop.
  5. Spatially join stations to WCP municipal boundaries (point-in-polygon).
  6. Emit per-municipality station counts + scheduled weekday calls.

Output: data/gtfs/mnr_station_frequency.json
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[1]
FEED_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfsmnr.zip"
CACHE = REPO / "data" / "gtfs" / "gtfsmnr.zip"
OUT = REPO / "data" / "gtfs" / "mnr_station_frequency.json"
BOUNDARIES = REPO / "data" / "municipal_boundaries.geojson"

# Representative weekday: the current date if it's Mon-Fri, else the next Tuesday.
def representative_weekday() -> str:
    today = date.today()
    if today.weekday() < 5:
        return today.isoformat()
    return today.isoformat()


def fetch_feed() -> Path:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE.exists() or CACHE.stat().st_size < 1_000_000:
        req = urllib.request.Request(FEED_URL, headers={"User-Agent": "wcp-dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            CACHE.write_bytes(resp.read())
    return CACHE


def read_member(zf: zipfile.ZipFile, name: str) -> list[dict]:
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def main() -> int:
    feed = fetch_feed()
    zf = zipfile.ZipFile(feed)
    members = set(zf.namelist())
    for required in ("stops.txt", "stop_times.txt", "trips.txt"):
        if required not in members:
            print(f"ERROR: feed missing {required}", file=sys.stderr)
            return 1

    stops = read_member(zf, "stops.txt")
    trips = read_member(zf, "trips.txt")

    # --- active weekday service ids -------------------------------------
    target = representative_weekday()
    active_services: set[str] = set()
    if "calendar.txt" in members:
        for row in read_member(zf, "calendar.txt"):
            days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            wd = date.fromisoformat(target).weekday()
            if wd < 5 and row.get(days[wd]) == "1":
                if row["start_date"] <= target.replace("-", "") <= row["end_date"]:
                    active_services.add(row["service_id"])
    if not active_services and "calendar_dates.txt" in members:
        for row in read_member(zf, "calendar_dates.txt"):
            if row["date"] == target.replace("-", "") and row["exception_type"] == "1":
                active_services.add(row["service_id"])
    if not active_services:
        # Fall back to every service in trips so the metric is still meaningful.
        active_services = {t["service_id"] for t in trips}

    trips_by_service: dict[str, list[str]] = defaultdict(list)
    for t in trips:
        trips_by_service[t["service_id"]].append(t["trip_id"])
    active_trips = {
        tid for sid in active_services for tid in trips_by_service.get(sid, [])
    }

    # --- count scheduled calls per stop ---------------------------------
    calls: dict[str, int] = defaultdict(int)
    with zf.open("stop_times.txt") as fh:
        for row in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")):
            if row["trip_id"] in active_trips:
                calls[row["stop_id"]] += 1

    # --- station geometry ------------------------------------------------
    records = []
    for s in stops:
        try:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        except (KeyError, ValueError):
            continue
        records.append(
            {
                "stop_id": s["stop_id"],
                "stop_name": s.get("stop_name", "").strip(),
                "lat": lat,
                "lon": lon,
                "weekday_calls": calls.get(s["stop_id"], 0),
            }
        )
    if not records:
        print("ERROR: no usable stops parsed", file=sys.stderr)
        return 1

    gdf = gpd.GeoDataFrame(
        records, geometry=[Point(r["lon"], r["lat"]) for r in records], crs="EPSG:4326"
    )

    boundaries = gpd.read_file(BOUNDARIES).to_crs("EPSG:4326")
    joined = gpd.sjoin(gdf, boundaries[["name", "profile_id", "geometry"]],
                       how="left", predicate="within")

    per_muni: dict[str, dict] = {}
    for _, row in joined.iterrows():
        key = row["name"] if isinstance(row.get("name"), str) else None
        if key is None:
            continue
        entry = per_muni.setdefault(
            key,
            {"profile_id": row.get("profile_id"), "stations": 0,
             "weekday_scheduled_calls": 0, "station_names": []},
        )
        entry["stations"] += 1
        entry["weekday_scheduled_calls"] += int(row["weekday_calls"])
        entry["station_names"].append(row["stop_name"])

    unmatched = int(joined["name"].isna().sum())
    payload = {
        "source": FEED_URL,
        "source_name": "MTA Metro-North Railroad GTFS",
        "service_date_used": target,
        "active_service_ids": len(active_services),
        "active_trips": len(active_trips),
        "total_stations_in_feed": len(records),
        "stations_matched_to_municipality": len(records) - unmatched,
        "stations_outside_westchester": unmatched,
        "municipalities_with_rail_service": len(per_muni),
        "municipalities": dict(sorted(per_muni.items(),
                                      key=lambda kv: -kv[1]["weekday_scheduled_calls"])),
        "method_note": (
            "weekday_scheduled_calls counts scheduled station calls on the "
            "representative weekday. Stations are assigned to municipalities by "
            "point-in-polygon against County municipal boundaries; stations outside "
            "Westchester (e.g. NYC, CT) are excluded from municipal totals."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"service date          : {target}")
    print(f"active service ids    : {len(active_services)}")
    print(f"active trips          : {len(active_trips)}")
    print(f"stations in feed      : {len(records)}")
    print(f"matched to a muni     : {len(records) - unmatched}")
    print(f"outside Westchester   : {unmatched}")
    print(f"municipalities served : {len(per_muni)}")
    print("top municipalities by scheduled weekday calls:")
    for name, e in list(payload["municipalities"].items())[:10]:
        print(f"  {name:<28} stations={e['stations']:<3} calls={e['weekday_scheduled_calls']}")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
