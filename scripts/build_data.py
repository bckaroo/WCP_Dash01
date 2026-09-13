#!/usr/bin/env python3
"""Build WCP dashboard data and GIS deliverables from official live APIs."""
from __future__ import annotations

import csv
import io
import json
import math
import os
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GIS_DIR = ROOT / "artifacts" / "gis"
SHP_DIR = GIS_DIR / "shapefile"
CROSSWALK = ROOT / "config" / "geography_crosswalk.csv"
ACS_YEAR = 2024
ACS_DATASET = f"{ACS_YEAR}/acs/acs5"
CENSUS_BASE = f"https://api.census.gov/data/{ACS_DATASET}"
BOUNDARY_URL = "https://giswww.westchestergov.com/arcgis/rest/services/Datahub_Boundaries/MapServer/163/query"
PARCEL_URL = "https://giswww.westchestergov.com/arcgis/rest/services/DataHub_TaxParcels/MapServer/0/query"
TIGER_COUSUB_URL = "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_36_cousub.zip"
USER_AGENT = "WCP-Community-Dashboard/1.0 (public-data build; Westchester County profile prototype)"

AGGREGATE_TOWNS = [
    {
        "id": "pelham-town",
        "name": "Town of Pelham",
        "census_name": "Pelham town, Westchester County, New York",
        "tiger_geoid": "3611957012",
        "swis_prefix": "5544",
        "geography_note": "Overlapping town aggregate containing the Village of Pelham and Village of Pelham Manor. Do not add this total to either village profile.",
    },
    {
        "id": "rye-town",
        "name": "Town of Rye",
        "census_name": "Rye town, Westchester County, New York",
        "tiger_geoid": "3611964320",
        "swis_prefix": "5548",
        "geography_note": "Overlapping, noncontiguous town aggregate containing Port Chester, Rye Brook, and the Rye Neck section of Mamaroneck Village. Do not add this total to those village profiles; Rye City is separate.",
    },
]

BASE_VARS = [
    "B01001_001", "B03003_003", "B02001_002", "B02001_003", "B02001_005", "B09001_001",
    "B01001_020", "B01001_021", "B01001_022", "B01001_023", "B01001_024", "B01001_025",
    "B01001_044", "B01001_045", "B01001_046", "B01001_047", "B01001_048", "B01001_049",
    "B11001_001", "B25001_001", "B25002_002", "B25002_003", "B25003_002", "B25003_003",
    "B19013_001", "B19113_001", "B19301_001", "B17001_001", "B17001_002",
    "B25064_001", "B25077_001", "B25070_001", "B25070_007", "B25070_008", "B25070_009", "B25070_010",
    "B25024_001", "B25024_002", "B25024_003", "B25024_004", "B25024_005", "B25024_006",
    "B25024_007", "B25024_008", "B25024_009", "B25024_010", "B25024_011",
    "B08301_001", "B08301_003", "B08301_004", "B08301_010", "B08301_018", "B08301_019",
    "B08301_020", "B08301_021",
]

LAND_USE = {
    "1": "Agricultural",
    "2": "Residential",
    "3": "Vacant land",
    "4": "Commercial",
    "5": "Recreation & entertainment",
    "6": "Community services",
    "7": "Industrial",
    "8": "Public services",
    "9": "Wild, forested, conservation & public parks",
}


def load_census_key() -> str | None:
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        return key.strip()
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("CENSUS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"\'')
    return None


def get_json(url: str, params: dict | None = None, attempts: int = 4):
    target = url
    if params:
        target += ("&" if "?" in target else "?") + urllib.parse.urlencode(params)
    last_error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(target, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as response:
                return json.load(response)
        except Exception as exc:  # pragma: no cover - network fallback
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}: {last_error}")


def get_bytes(url: str, attempts: int = 4) -> bytes:
    last_error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=180) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - network fallback
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}: {last_error}")


def chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def census_rows(for_geo: str, in_geo: str | None = None) -> list[dict]:
    requested = [f"{base}{suffix}" for base in BASE_VARS for suffix in ("E", "M")]
    merged: dict[str, dict] = {}
    key = load_census_key()
    for part in chunks(requested, 45):
        params = {"get": ",".join(["NAME", *part]), "for": for_geo}
        if in_geo:
            params["in"] = in_geo
        if key:
            params["key"] = key
        payload = get_json(CENSUS_BASE, params)
        header = payload[0]
        for values in payload[1:]:
            row = dict(zip(header, values))
            merged.setdefault(row["NAME"], {}).update(row)
    return list(merged.values())


def clean_number(value):
    if value in (None, "", "null"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= -555555555:
        return None
    return number


def estimate(row: dict, base: str):
    return clean_number(row.get(f"{base}E"))


def moe(row: dict, base: str):
    value = clean_number(row.get(f"{base}M"))
    return abs(value) if value is not None else None


def summed(row: dict, bases: list[str]):
    values = [estimate(row, base) for base in bases]
    moes = [moe(row, base) for base in bases]
    est = sum(v for v in values if v is not None) if any(v is not None for v in values) else None
    margin = math.sqrt(sum(v * v for v in moes if v is not None)) if any(v is not None for v in moes) else None
    return est, margin


def rounded(value, digits=1):
    return round(value, digits) if value is not None and math.isfinite(value) else None


def pct_metric(num, num_moe, den, den_moe):
    if num is None or den in (None, 0):
        return {"estimate": None, "moe": None}
    ratio = num / den
    margin = None
    if num_moe is not None and den_moe is not None:
        radicand = num_moe**2 - (ratio**2 * den_moe**2)
        if radicand < 0:
            radicand = num_moe**2 + (ratio**2 * den_moe**2)
        margin = math.sqrt(radicand) / den * 100
    return {"estimate": rounded(ratio * 100), "moe": rounded(margin)}


def direct_metric(row, base, integer=False):
    value, margin = estimate(row, base), moe(row, base)
    if integer:
        value = int(round(value)) if value is not None else None
        margin = int(round(margin)) if margin is not None else None
    else:
        value, margin = rounded(value), rounded(margin)
    return {"estimate": value, "moe": margin}


def geoid_for(row: dict, geography: str):
    if geography == "county":
        return f"0500000US{row['state']}{row['county']}"
    if geography == "county subdivision":
        return f"0600000US{row['state']}{row['county']}{row['county subdivision']}"
    if geography == "place":
        return f"1600000US{row['state']}{row['place']}"
    raise ValueError(geography)


def profile_metrics(row: dict, land_use: dict):
    pop, pop_moe = estimate(row, "B01001_001"), moe(row, "B01001_001")
    under18, under18_moe = estimate(row, "B09001_001"), moe(row, "B09001_001")
    senior_bases = [
        "B01001_020", "B01001_021", "B01001_022", "B01001_023", "B01001_024", "B01001_025",
        "B01001_044", "B01001_045", "B01001_046", "B01001_047", "B01001_048", "B01001_049",
    ]
    senior, senior_moe = summed(row, senior_bases)
    poverty_universe, poverty_universe_moe = estimate(row, "B17001_001"), moe(row, "B17001_001")
    below_poverty, below_poverty_moe = estimate(row, "B17001_002"), moe(row, "B17001_002")
    occupied, occupied_moe = estimate(row, "B25002_002"), moe(row, "B25002_002")
    vacant, vacant_moe = estimate(row, "B25002_003"), moe(row, "B25002_003")
    housing_units, housing_units_moe = estimate(row, "B25001_001"), moe(row, "B25001_001")
    owner, owner_moe = estimate(row, "B25003_002"), moe(row, "B25003_002")
    renter, renter_moe = estimate(row, "B25003_003"), moe(row, "B25003_003")
    tenure_total = (owner or 0) + (renter or 0) if owner is not None or renter is not None else None
    tenure_moe = math.sqrt((owner_moe or 0) ** 2 + (renter_moe or 0) ** 2) if tenure_total is not None else None
    rent_total, rent_total_moe = estimate(row, "B25070_001"), moe(row, "B25070_001")
    burdened, burdened_moe = summed(row, ["B25070_007", "B25070_008", "B25070_009", "B25070_010"])
    commute_total, commute_total_moe = estimate(row, "B08301_001"), moe(row, "B08301_001")

    def share(base):
        return pct_metric(estimate(row, base), moe(row, base), pop, pop_moe)

    def commute_share(base):
        return pct_metric(estimate(row, base), moe(row, base), commute_total, commute_total_moe)

    housing_structure = {}
    structure_groups = {
        "Single-family detached": ["B25024_002"],
        "Single-family attached": ["B25024_003"],
        "2–4 units": ["B25024_004", "B25024_005"],
        "5–19 units": ["B25024_006", "B25024_007"],
        "20+ units": ["B25024_008", "B25024_009"],
        "Mobile / other": ["B25024_010", "B25024_011"],
    }
    structure_total, structure_total_moe = estimate(row, "B25024_001"), moe(row, "B25024_001")
    for label, bases in structure_groups.items():
        value, margin = summed(row, bases)
        housing_structure[label] = pct_metric(value, margin, structure_total, structure_total_moe)

    return {
        "population": {
            "total": {"estimate": int(round(pop)) if pop is not None else None, "moe": int(round(pop_moe)) if pop_moe is not None else None},
            "under_18_pct": pct_metric(under18, under18_moe, pop, pop_moe),
            "age_65_plus_pct": pct_metric(senior, senior_moe, pop, pop_moe),
            "white_alone_pct": share("B02001_002"),
            "black_alone_pct": share("B02001_003"),
            "asian_alone_pct": share("B02001_005"),
            "hispanic_latino_pct": share("B03003_003"),
        },
        "households": {"total": direct_metric(row, "B11001_001", True)},
        "housing": {
            "units": direct_metric(row, "B25001_001", True),
            "occupied": direct_metric(row, "B25002_002", True),
            "vacant": direct_metric(row, "B25002_003", True),
            "vacancy_rate_pct": pct_metric(vacant, vacant_moe, housing_units, housing_units_moe),
            "owner_occupied_pct": pct_metric(owner, owner_moe, tenure_total, tenure_moe),
            "renter_occupied_pct": pct_metric(renter, renter_moe, tenure_total, tenure_moe),
            "median_gross_rent": direct_metric(row, "B25064_001", True),
            "median_home_value": direct_metric(row, "B25077_001", True),
            "rent_burden_30_plus_pct": pct_metric(burdened, burdened_moe, rent_total, rent_total_moe),
            "structure_share_pct": housing_structure,
        },
        "income": {
            "median_household": direct_metric(row, "B19013_001", True),
            "median_family": direct_metric(row, "B19113_001", True),
            "per_capita": direct_metric(row, "B19301_001", True),
            "poverty_rate_pct": pct_metric(below_poverty, below_poverty_moe, poverty_universe, poverty_universe_moe),
        },
        "commute": {
            "workers_16_plus": direct_metric(row, "B08301_001", True),
            "drove_alone_pct": commute_share("B08301_003"),
            "carpooled_pct": commute_share("B08301_004"),
            "public_transit_pct": commute_share("B08301_010"),
            "bicycle_pct": commute_share("B08301_018"),
            "walked_pct": commute_share("B08301_019"),
            "other_means_pct": commute_share("B08301_020"),
            "worked_from_home_pct": commute_share("B08301_021"),
        },
        "land_use": land_use,
    }


def load_crosswalk():
    with CROSSWALK.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 43 or len({r["profile_id"] for r in rows}) != 43:
        raise AssertionError("Geography crosswalk must contain 43 unique profile IDs")
    return rows


def boundary_features():
    payload = get_json(BOUNDARY_URL, {
        "where": "1=1", "outFields": "NAME,SQMILES", "returnGeometry": "true",
        "outSR": "4326", "geometryPrecision": "6", "f": "geojson",
    })
    grouped = defaultdict(list)
    sq_miles = defaultdict(float)
    for feature in payload["features"]:
        name = feature["properties"]["NAME"]
        grouped[name].append(shape(feature["geometry"]))
        sq_miles[name] += float(feature["properties"].get("SQMILES") or 0)
    dissolved = {}
    for name, geometries in grouped.items():
        geom = unary_union(geometries)
        if not geom.is_valid:
            geom = geom.buffer(0)
        dissolved[name] = {"geometry": geom, "source_parts": len(geometries), "source_sq_miles": sq_miles[name]}
    return payload, dissolved


def aggregate_boundary_features():
    """Read the two legal town boundaries from the official 2024 TIGER/Line file."""
    with zipfile.ZipFile(io.BytesIO(get_bytes(TIGER_COUSUB_URL))) as archive:
        members = archive.namelist()
        with io.BytesIO() as buffer:
            # GeoPandas/GDAL needs the full archive, not an extracted .shp alone.
            with zipfile.ZipFile(buffer, "w") as copy:
                for member in members:
                    copy.writestr(member, archive.read(member))
            frame = gpd.read_file(io.BytesIO(buffer.getvalue()))
    frame = frame[
        (frame["STATEFP"] == "36")
        & (frame["COUNTYFP"] == "119")
        & (frame["LSAD"] == "43")
        & (frame["GEOID"].isin({item["tiger_geoid"] for item in AGGREGATE_TOWNS}))
    ].copy()
    if set(frame["GEOID"]) != {item["tiger_geoid"] for item in AGGREGATE_TOWNS}:
        raise AssertionError(f"Missing TIGER/Line town boundaries: observed={set(frame['GEOID'])}")
    frame = frame.to_crs("EPSG:4326")
    if not frame.geometry.notna().all() or not frame.geometry.is_valid.all():
        raise AssertionError("Invalid TIGER/Line aggregate town geometry")
    return frame


def parcel_group_query(label, where):
    statistics = [
        {"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "parcel_count"},
        {"statisticType": "sum", "onStatisticField": "CALC_ACRES", "outStatisticFieldName": "acres_sum"},
    ]
    payload = get_json(PARCEL_URL, {
        "where": f"DUP_GEO IS NULL AND ({where})",
        "outStatistics": json.dumps(statistics, separators=(",", ":")),
        "groupByFieldsForStatistics": "PROP_CLASS", "orderByFields": "PROP_CLASS",
        "returnGeometry": "false", "resultRecordCount": "1000", "f": "json",
    })
    if payload.get("exceededTransferLimit"):
        raise AssertionError(f"Parcel class query was truncated for {label}")
    records = []
    for feature in payload.get("features", []):
        record = feature["attributes"]
        record["MUNI_NAME"] = label
        records.append(record)
    return records


def parcel_stats():
    # The service ignores resultOffset on grouped statistical queries and repeats
    # the first 1,000 rows. Query each of the 43 municipality names instead; each
    # result is small, complete, and independently attributable.
    municipality_names = sorted({row["parcel_name"] for row in load_crosswalk()})

    base_records = []
    aggregate_records = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}
        for muni in municipality_names:
            escaped = muni.replace("'", "''")
            futures[pool.submit(parcel_group_query, muni, f"MUNI_NAME='{escaped}'")] = ("base", muni)
        for town in AGGREGATE_TOWNS:
            futures[pool.submit(parcel_group_query, town["name"], f"SWIS LIKE '{town['swis_prefix']}%'")] = ("aggregate", town["name"])
        for future in as_completed(futures):
            target, _ = futures[future]
            (base_records if target == "base" else aggregate_records).extend(future.result())
    observed = {record["MUNI_NAME"] for record in base_records}
    if observed != set(municipality_names):
        raise AssertionError(f"Parcel municipality mismatch: missing={set(municipality_names)-observed}")
    aggregate_observed = {record["MUNI_NAME"] for record in aggregate_records}
    if aggregate_observed != {town["name"] for town in AGGREGATE_TOWNS}:
        raise AssertionError(f"Aggregate parcel geography mismatch: observed={aggregate_observed}")

    vintage_stats = [
        {"statisticType": "max", "onStatisticField": "ROLL_YR", "outStatisticFieldName": "max_roll_year"},
        {"statisticType": "max", "onStatisticField": "SPATIAL_YR", "outStatisticFieldName": "max_spatial_year"},
    ]
    vintage = get_json(PARCEL_URL, {
        "where": "1=1", "outStatistics": json.dumps(vintage_stats, separators=(",", ":")),
        "returnGeometry": "false", "f": "json",
    })["features"][0]["attributes"]
    return base_records, aggregate_records, vintage


def summarize_land_use(records: list[dict]):
    by_muni = defaultdict(lambda: defaultdict(lambda: {"acres": 0.0, "parcels": 0}))
    for record in records:
        muni = record.get("MUNI_NAME") or "Unknown"
        code = str(record.get("PROP_CLASS") or "")
        category = LAND_USE.get(code[:1], "Unclassified")
        by_muni[muni][category]["acres"] += float(record.get("ACRES_SUM") or 0)
        by_muni[muni][category]["parcels"] += int(record.get("PARCEL_COUNT") or 0)

    def finish(groups):
        total_acres = sum(item["acres"] for item in groups.values())
        total_parcels = sum(item["parcels"] for item in groups.values())
        categories = []
        for category, item in sorted(groups.items(), key=lambda pair: pair[1]["acres"], reverse=True):
            categories.append({
                "category": category,
                "acres": round(item["acres"], 1),
                "share_pct": round(item["acres"] / total_acres * 100, 1) if total_acres else None,
                "parcel_records": item["parcels"],
            })
        return {"assessor_parcel_acres": round(total_acres, 1), "parcel_records": total_parcels, "categories": categories}

    county_groups = defaultdict(lambda: {"acres": 0.0, "parcels": 0})
    for groups in by_muni.values():
        for category, item in groups.items():
            county_groups[category]["acres"] += item["acres"]
            county_groups[category]["parcels"] += item["parcels"]
    return {muni: finish(groups) for muni, groups in by_muni.items()}, finish(county_groups)


def export_gis(crosswalk, profiles_by_id, dissolved):
    GIS_DIR.mkdir(parents=True, exist_ok=True)
    SHP_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    geometries = []
    web_features = []
    for item in crosswalk:
        profile = profiles_by_id[item["profile_id"]]
        geom_info = dissolved[item["geometry_name"]]
        geom = geom_info["geometry"]
        pop = profile["metrics"]["population"]["total"]
        income = profile["metrics"]["income"]["median_household"]
        housing = profile["metrics"]["housing"]
        commute = profile["metrics"]["commute"]
        land = profile["metrics"]["land_use"]
        props = {
            "profile_id": profile["id"], "name": profile["name"], "profile_type": profile["profile_type"],
            "census_geography": profile["census_geography"], "census_geoid": profile["census_geoid"],
            "acs_year": ACS_YEAR, "population": pop["estimate"], "population_moe": pop["moe"],
            "median_household_income": income["estimate"], "median_household_income_moe": income["moe"],
            "housing_units": housing["units"]["estimate"],
            "owner_occupied_pct": housing["owner_occupied_pct"]["estimate"],
            "vacancy_rate_pct": housing["vacancy_rate_pct"]["estimate"],
            "public_transit_pct": commute["public_transit_pct"]["estimate"],
            "worked_from_home_pct": commute["worked_from_home_pct"]["estimate"],
            "assessor_parcel_acres": land["assessor_parcel_acres"],
            "source_parts": geom_info["source_parts"],
        }
        rows.append(props)
        geometries.append(geom)
        web_features.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})

    gdf = gpd.GeoDataFrame(rows, geometry=geometries, crs="EPSG:4326")
    geojson_path = GIS_DIR / "wcp_community_profiles_2024.geojson"
    gpkg_path = GIS_DIR / "wcp_community_profiles_2024.gpkg"
    gdf.to_file(geojson_path, driver="GeoJSON")
    if gpkg_path.exists():
        gpkg_path.unlink()
    gdf.to_file(gpkg_path, layer="community_profiles", driver="GPKG")

    shp_rows = []
    for row in rows:
        shp_rows.append({
            "id": row["profile_id"], "name": row["name"], "type": row["profile_type"],
            "cgeog": row["census_geography"], "geoid": row["census_geoid"], "acsyr": row["acs_year"],
            "pop": row["population"], "pop_moe": row["population_moe"], "medhhinc": row["median_household_income"],
            "mhi_moe": row["median_household_income_moe"], "hunits": row["housing_units"],
            "own_pct": row["owner_occupied_pct"], "vac_pct": row["vacancy_rate_pct"],
            "trn_pct": row["public_transit_pct"], "wfh_pct": row["worked_from_home_pct"],
            "lu_acres": row["assessor_parcel_acres"],
        })
    shp_gdf = gpd.GeoDataFrame(shp_rows, geometry=geometries, crs="EPSG:4326")
    shp_path = SHP_DIR / "wcp_profiles.shp"
    for old in SHP_DIR.glob("wcp_profiles.*"):
        old.unlink()
    shp_gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="UTF-8")

    field_dictionary = [
        ("id", "profile_id", "Stable dashboard slug"), ("name", "name", "County profile display name"),
        ("type", "profile_type", "City, town, or village"), ("cgeog", "census_geography", "ACS geography used"),
        ("geoid", "census_geoid", "Full Census GEOID"), ("acsyr", "acs_year", "ACS 5-year vintage"),
        ("pop", "population", "Total population estimate"), ("pop_moe", "population_moe", "Population 90% MOE"),
        ("medhhinc", "median_household_income", "Median household income, nominal vintage dollars"),
        ("mhi_moe", "median_household_income_moe", "Median household income 90% MOE"),
        ("hunits", "housing_units", "Housing units estimate"), ("own_pct", "owner_occupied_pct", "Owner share of occupied tenure units"),
        ("vac_pct", "vacancy_rate_pct", "Vacant share of housing units"), ("trn_pct", "public_transit_pct", "Public transit share, workers 16+"),
        ("wfh_pct", "worked_from_home_pct", "Work-from-home share, workers 16+"),
        ("lu_acres", "assessor_parcel_acres", "Mapped assessment-parcel acres, duplicate geometries excluded"),
    ]
    with (GIS_DIR / "FIELD_DICTIONARY.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["shapefile_field", "rich_field", "definition"])
        writer.writerows(field_dictionary)

    zip_path = GIS_DIR / "wcp_profiles_2024_shapefile.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for component in sorted(SHP_DIR.glob("wcp_profiles.*")):
            archive.write(component, component.name)
        archive.write(GIS_DIR / "FIELD_DICTIONARY.csv", "FIELD_DICTIONARY.csv")
        if (GIS_DIR / "README.md").exists():
            archive.write(GIS_DIR / "README.md", "README.md")
    return {"geojson": str(geojson_path.relative_to(ROOT)), "gpkg": str(gpkg_path.relative_to(ROOT)), "shapefile_zip": str(zip_path.relative_to(ROOT))}


def export_aggregate_gis(profiles_by_id, tiger_frame):
    """Export separate overlapping town boundaries without changing the 43-feature base layer."""
    GIS_DIR.mkdir(parents=True, exist_ok=True)
    tiger_by_geoid = {row["GEOID"]: row.geometry for _, row in tiger_frame.iterrows()}
    rows = []
    geometries = []
    for item in AGGREGATE_TOWNS:
        profile = profiles_by_id[item["id"]]
        rows.append({
            "profile_id": profile["id"],
            "name": profile["name"],
            "profile_type": profile["profile_type"],
            "map_role": profile["map_role"],
            "census_geoid": profile["census_geoid"],
            "acs_year": ACS_YEAR,
            "population": profile["metrics"]["population"]["total"]["estimate"],
            "population_moe": profile["metrics"]["population"]["total"]["moe"],
            "median_household_income": profile["metrics"]["income"]["median_household"]["estimate"],
            "assessor_parcel_acres": profile["metrics"]["land_use"]["assessor_parcel_acres"],
            "geography_note": profile["geography_note"],
        })
        geometries.append(tiger_by_geoid[item["tiger_geoid"]])
    gdf = gpd.GeoDataFrame(rows, geometry=geometries, crs="EPSG:4326")
    geojson_path = GIS_DIR / "wcp_town_aggregates_2024.geojson"
    gpkg_path = GIS_DIR / "wcp_town_aggregates_2024.gpkg"
    gdf.to_file(geojson_path, driver="GeoJSON")
    if gpkg_path.exists():
        gpkg_path.unlink()
    gdf.to_file(gpkg_path, layer="town_aggregates", driver="GPKG")
    web_geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    (DATA_DIR / "town_aggregate_boundaries.geojson").write_text(
        json.dumps(web_geojson, separators=(",", ":")), encoding="utf-8"
    )
    return {
        "geojson": str(geojson_path.relative_to(ROOT)),
        "gpkg": str(gpkg_path.relative_to(ROOT)),
        "web_geojson": "data/town_aggregate_boundaries.geojson",
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    crosswalk = load_crosswalk()
    raw_boundary, dissolved = boundary_features()
    aggregate_boundaries = aggregate_boundary_features()
    expected_names = {row["geometry_name"] for row in crosswalk}
    if set(dissolved) != expected_names:
        raise AssertionError(f"Boundary/crosswalk mismatch: missing={expected_names-set(dissolved)}, extra={set(dissolved)-expected_names}")

    county_rows = census_rows("county:119", "state:36")
    subdivision_rows = census_rows("county subdivision:*", "state:36 county:119")
    place_rows = census_rows("place:*", "state:36")
    if len(county_rows) != 1 or len(subdivision_rows) != 25:
        raise AssertionError(f"Unexpected Census geography counts: county={len(county_rows)}, subdivisions={len(subdivision_rows)}")
    by_subdivision = {row["NAME"]: row for row in subdivision_rows}
    by_place = {row["NAME"]: row for row in place_rows}

    parcel_records, aggregate_parcel_records, parcel_vintage = parcel_stats()
    land_by_muni, county_land = summarize_land_use(parcel_records)
    aggregate_land, _ = summarize_land_use(aggregate_parcel_records)
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    county_row = county_rows[0]
    county_profile = {
        "id": "westchester-county", "name": "Westchester County", "profile_type": "county",
        "map_role": "county overview",
        "census_geography": "county", "census_name": county_row["NAME"],
        "census_geoid": geoid_for(county_row, "county"), "metrics": profile_metrics(county_row, county_land),
    }
    profiles = [county_profile]
    for item in crosswalk:
        source = by_subdivision if item["census_geography"] == "county subdivision" else by_place
        if item["census_name"] not in source:
            matches = [name for name in source if item["census_name"].split(",")[0] in name]
            raise AssertionError(f"No exact ACS match for {item['census_name']!r}; candidates={matches}")
        row = source[item["census_name"]]
        if item["parcel_name"] not in land_by_muni:
            raise AssertionError(f"No parcel statistics for {item['parcel_name']}")
        profiles.append({
            "id": item["profile_id"], "name": item["geometry_name"], "profile_type": item["profile_type"],
            "map_role": "base",
            "census_geography": item["census_geography"], "census_name": row["NAME"],
            "census_geoid": geoid_for(row, item["census_geography"]),
            "metrics": profile_metrics(row, land_by_muni[item["parcel_name"]]),
        })

    for item in AGGREGATE_TOWNS:
        row = by_subdivision.get(item["census_name"])
        if row is None:
            raise AssertionError(f"No exact ACS match for aggregate {item['census_name']!r}")
        if item["name"] not in aggregate_land:
            raise AssertionError(f"No aggregate parcel statistics for {item['name']}")
        if geoid_for(row, "county subdivision") != f"0600000US{item['tiger_geoid']}":
            raise AssertionError(f"ACS/TIGER GEOID mismatch for {item['name']}")
        profiles.append({
            "id": item["id"],
            "name": item["name"],
            "profile_type": "overlapping town aggregate",
            "map_role": "aggregate overlay",
            "census_geography": "county subdivision",
            "census_name": row["NAME"],
            "census_geoid": geoid_for(row, "county subdivision"),
            "geography_note": item["geography_note"],
            "metrics": profile_metrics(row, aggregate_land[item["name"]]),
        })

    if len(profiles) != 46 or len({p["id"] for p in profiles}) != 46:
        raise AssertionError("Expected county plus 43 base profiles and 2 overlapping town aggregates")
    profiles_by_id = {profile["id"]: profile for profile in profiles}

    metadata = {
        "title": "Westchester County Community Profiles",
        "generated_at": retrieved_at,
        "acs": {
            "dataset": "American Community Survey 5-year detailed tables", "vintage": ACS_YEAR,
            "confidence_level": "90% margins of error", "dollar_basis": f"Nominal {ACS_YEAR} inflation-adjusted dollars as published by ACS",
            "county_geography": "County FIPS 36119", "municipality_strategy": "25 city/town county subdivisions plus 20 village Census places; Town of Pelham and Town of Rye are separate overlapping aggregates and must not be summed with constituent village profiles",
            "source": CENSUS_BASE,
        },
        "boundaries": {
            "source": BOUNDARY_URL.rsplit("/query", 1)[0], "crs": "EPSG:4326 (WGS 84)",
            "source_feature_rows": len(raw_boundary["features"]), "unique_profile_communities": len(dissolved),
            "multipart_dissolves": sorted(name for name, info in dissolved.items() if info["source_parts"] > 1),
        },
        "aggregate_boundaries": {
            "source": TIGER_COUSUB_URL,
            "source_kind": "U.S. Census Bureau TIGER/Line county subdivisions",
            "vintage": 2024,
            "crs": "EPSG:4326 (reprojected from TIGER/Line EPSG:4269)",
            "feature_count": len(aggregate_boundaries),
            "note": "Separate authoritative legal town boundaries used only as overlays; the 43-feature County GIS base layer is unchanged.",
        },
        "municipal_coverage": {
            "state_reported_municipal_corporations": 48,
            "selector_profiles": 45,
            "non_overlapping_map_geographies": 43,
            "overlapping_town_aggregates": 2,
            "coterminous_town_villages_represented_once": ["Harrison", "Mount Kisco", "Scarsdale"],
            "state_source": "https://www.ny.gov/counties/westchester",
            "county_source": "https://www.westchestercountyny.gov/online-data",
        },
        "land_use": {
            "source": PARCEL_URL.rsplit("/query", 1)[0], "roll_year_max": parcel_vintage.get("MAX_ROLL_YEAR"),
            "spatial_year_max": parcel_vintage.get("MAX_SPATIAL_YEAR"),
            "definition": "Assessment parcel property class summarized by calculated parcel acres; records flagged DUP_GEO='Y' are excluded to avoid overlapping duplicate geometry.",
            "limitations": "This is assessed use, not zoning or remote-sensing land cover. Parcel acreage excludes rights-of-way/water and may not equal total municipal land area; mixed-use parcels are represented by their primary assessment class.",
            "classification": "First digit of NYS ORPTS property class (100–900 series).",
        },
        "commute_universe": "Workers 16 years and over (ACS B08301). Mode shares include work from home; they are not peak-period trip shares.",
        "known_gaps": [
            "Municipal building-permit detail is not public in one countywide source.",
            "Condominium/cooperative inventory lacks a complete public feed.",
            "Major-employer establishment employment requires a curated County source; QCEW microdata are confidential.",
            "CDBG-funded project locations lack a verified public countywide spatial layer.",
            "This prototype does not yet integrate GTFS service frequency, school enrollment, ORPTS sales, or historical boundary-normalized trends from GR-04/05/12/14/16.",
        ],
    }

    output = {"metadata": metadata, "profiles": profiles}
    (DATA_DIR / "profiles.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    (DATA_DIR / "census_variables.json").write_text(json.dumps({
        "vintage": ACS_YEAR, "dataset": ACS_DATASET, "variables": BASE_VARS,
        "note": "Every estimate variable E was retrieved with its 90% margin-of-error companion M.",
    }, indent=2), encoding="utf-8")

    gis_paths = export_gis(crosswalk, profiles_by_id, dissolved)
    aggregate_gis_paths = export_aggregate_gis(profiles_by_id, aggregate_boundaries)
    # Export a small web-map copy after GIS generation to preserve rich geometry and flat attributes.
    web_geojson = json.loads((ROOT / gis_paths["geojson"]).read_text(encoding="utf-8"))
    (DATA_DIR / "municipal_boundaries.geojson").write_text(json.dumps(web_geojson, separators=(",", ":")), encoding="utf-8")

    build_report = {
        "generated_at": retrieved_at, "profile_count_including_county": len(profiles),
        "municipality_profile_count": len(profiles) - 1, "base_map_profile_count": len(crosswalk),
        "overlapping_town_aggregate_count": len(AGGREGATE_TOWNS), "county_subdivision_rows_observed": len(subdivision_rows),
        "county_boundary_rows_observed": len(raw_boundary["features"]), "county_boundary_unique_names": len(dissolved),
        "parcel_stat_groups": len(parcel_records), "aggregate_parcel_stat_groups": len(aggregate_parcel_records),
        "parcel_roll_year_max": parcel_vintage.get("MAX_ROLL_YEAR"),
        "parcel_spatial_year_max": parcel_vintage.get("MAX_SPATIAL_YEAR"), "gis": gis_paths,
        "aggregate_gis": aggregate_gis_paths,
    }
    (DATA_DIR / "build_report.json").write_text(json.dumps(build_report, indent=2), encoding="utf-8")
    print(json.dumps(build_report, indent=2))


if __name__ == "__main__":
    main()
