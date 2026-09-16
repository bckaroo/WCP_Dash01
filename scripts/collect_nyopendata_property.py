#!/usr/bin/env python3
"""
NY Open Data property/parcel collector for WCP Dashboard.

Sources (verified live, keyless, Socrata):
  1. tnwc-mx3q  Parcel Counts By Type By Municipality: Beginning Roll Year 2000
     https://data.ny.gov/resource/tnwc-mx3q.json
  2. 7vem-aaz7  Property Assessment Data from Local Assessment Rolls
     https://data.ny.gov/resource/7vem-aaz7.json

Both are NYS Department of Tax and Finance (ORPTS) roll extracts published on
data.ny.gov, SWIS-coded by municipality, so they join to Westchester municipal
boundaries and cover the whole County.

Output: data/parcels/nyopendata_property_inventory.json
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "parcels" / "nyopendata_property_inventory.json"
BOUNDARIES = REPO / "data" / "municipal_boundaries.geojson"

PARCEL_COUNTS_DS = "https://data.ny.gov/resource/tnwc-mx3q.json"
ASSESSMENT_DS = "https://data.ny.gov/resource/7vem-aaz7.json"
COUNTY = "Westchester"

UA = {"User-Agent": "wcp-dashboard/1.0"}

# Apartment / multi-dwelling residential classes. NYS RPS class 411
# "Apartments" is the class under which condominium and cooperative units are
# reported; ORPTS publishes no separate "condominium" class.
MULTIFAMILY_CLASSES = {"411", "230", "280"}


def socrata(url: str, **params) -> list | dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    target = f"{url}?{query}" if query else url
    req = urllib.request.Request(target, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as resp:
        return json.load(resp)


def normalize(name: str) -> str:
    """Normalize municipal names so ORPTS labels join to County boundary names."""
    n = name.strip().lower()
    n = n.replace("&", "and")
    n = re.sub(r"^(town|village|city)\s+of\s+", "", n)
    n = re.sub(r"\s+(town|village|city)$", "", n)
    n = re.sub(r"[^a-z0-9 ]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    aliases = {
        "mt vernon": "mount vernon",
        "mount vernon": "mount vernon",
        "north castle": "north castle",
        "sleepy hollow": "sleepy hollow",
        "dobbs ferry": "dobbs ferry",
        "pleasantville": "pleasantville",
        "briarcliff manor": "briarcliff manor",
        "croton on hudson": "croton-on-hudson",
        "crotononhudson": "croton-on-hudson",
        "rye brook": "rye brook",
        "buchanan": "buchanan",
        "pelham": "pelham",
        "pelham manor": "pelham manor",
        "harrison": "harrison",
        "larchmont": "larchmont",
        "mamaroneck": "mamaroneck",
        "ossining": "ossining",
        "tarrytown": "tarrytown",
        "tuckahoe": "tuckahoe",
        "hastings on hudson": "hastings-on-hudson",
        "irvington": "irvington",
        "elmsford": "elmsford",
    }
    return aliases.get(n, n)


def boundary_names() -> dict[str, str]:
    data = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    return {normalize(f["properties"]["name"]): f["properties"]["name"]
            for f in data["features"]}


def collect_parcel_counts() -> tuple[list[dict], str]:
    rows = socrata(
        PARCEL_COUNTS_DS,
        **{"$where": f"county_name='{COUNTY}'", "$limit": "500"},
    )
    if not rows:
        return [], ""
    latest = max(r["roll_year"] for r in rows)
    return [r for r in rows if r["roll_year"] == latest], latest


def collect_property_classes(roll_year: str) -> list[dict]:
    """Parcel counts by municipality x property class, grouped server-side.

    The dataset carries multiple roll years; filtering to one year is essential,
    otherwise counts are inflated by the number of years present.
    """
    out: list[dict] = []
    offset = 0
    while True:
        page = socrata(
            ASSESSMENT_DS,
            **{
                "$select": "municipality_name,property_class,"
                           "property_class_description,count(*) as parcel_count,"
                           "sum(full_market_value) as total_market_value",
                "$where": f"county_name='{COUNTY}' AND roll_year='{roll_year}'",
                "$group": "municipality_name,property_class,property_class_description",
                "$order": "municipality_name,parcel_count DESC",
                "$limit": "2000",
                "$offset": str(offset),
            },
        )
        if not page:
            break
        out.extend(page)
        if len(page) < 2000:
            break
        offset += 2000
        if offset > 20000:
            print("  WARN: pagination guard hit", file=sys.stderr)
            break
    return out


def main() -> int:
    print("fetching parcel counts by type (tnwc-mx3q) ...")
    counts, roll_year = collect_parcel_counts()
    print(f"  {len(counts)} municipalities, roll year {roll_year}")

    print("fetching assessment roll property classes (7vem-aaz7) ...")
    classes = collect_property_classes(roll_year)
    print(f"  {len(classes)} municipality x class rows")

    lookup = boundary_names()
    munis: dict[str, dict] = {}

    for row in counts:
        key = normalize(row["municipality_name"])
        canonical = lookup.get(key, row["municipality_name"])
        entry = munis.setdefault(canonical, {
            "roll_year": roll_year,
            "swis_code": row.get("swis_code"),
            "matched_to_profile": key in lookup,
            "parcel_counts": {},
            "property_classes": [],
        })
        for field, value in row.items():
            if field.startswith("broad_use_") or field == "total_parcel_count":
                try:
                    entry["parcel_counts"][field] = int(value)
                except (TypeError, ValueError):
                    entry["parcel_counts"][field] = None

    for row in classes:
        key = normalize(row["municipality_name"])
        canonical = lookup.get(key, row["municipality_name"])
        entry = munis.setdefault(canonical, {
            "roll_year": roll_year, "swis_code": None,
            "matched_to_profile": key in lookup,
            "parcel_counts": {}, "property_classes": [],
        })
        try:
            n = int(row["parcel_count"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            mv = int(row["total_market_value"]) if row.get("total_market_value") else None
        except (TypeError, ValueError):
            mv = None
        entry["property_classes"].append({
            "class": row.get("property_class") or "unknown",
            "description": row.get("property_class_description") or "",
            "parcels": n,
            "total_market_value_usd": mv,
            "is_multifamily": row.get("property_class") in MULTIFAMILY_CLASSES,
        })

    # Derived headline metrics per municipality.
    for name, entry in munis.items():
        pc = entry["property_classes"]
        entry["property_classes"] = sorted(pc, key=lambda r: -r["parcels"])
        total = entry["parcel_counts"].get("total_parcel_count")
        entry["multifamily_parcels"] = sum(r["parcels"] for r in pc if r["is_multifamily"])
        entry["residential_parcels"] = entry["parcel_counts"].get(
            "broad_use_200_residential_property_count")
        entry["total_market_value_usd"] = sum(
            r["total_market_value_usd"] for r in pc if r["total_market_value_usd"])
        entry["multifamily_share_pct"] = (
            round(100 * entry["multifamily_parcels"] / total, 2) if total else None
        )

    matched = sum(1 for e in munis.values() if e["matched_to_profile"])
    payload = {
        "sources": [
            {"name": "Parcel Counts By Type By Municipality",
             "dataset_id": "tnwc-mx3q",
             "url": "https://data.ny.gov/d/tnwc-mx3q",
             "publisher": "NYS Dept. of Taxation and Finance (ORPTS)"},
            {"name": "Property Assessment Data from Local Assessment Rolls",
             "dataset_id": "7vem-aaz7",
             "url": "https://data.ny.gov/d/7vem-aaz7",
             "publisher": "NYS Dept. of Taxation and Finance (ORPTS)"},
        ],
        "county": COUNTY,
        "roll_year": roll_year,
        "municipalities_in_source": len(munis),
        "municipalities_matched_to_profile": matched,
        "multifamily_class_note": (
            "is_multifamily marks RPS classes comprising the apartment / "
            "multi-dwelling universe (411 Apartments, 280, 230, 483-485). "
            "ORPTS does not publish a separate 'condominium' class, so condo "
            "and co-op units appear within these apartment-class totals."
        ),
        "municipalities": dict(sorted(munis.items())),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nroll year {roll_year}: {len(munis)} municipalities, "
          f"{matched} matched to dashboard profiles")
    print("top by multifamily (apartment-class) parcels:")
    for name, e in sorted(munis.items(), key=lambda kv: -(kv[1]["multifamily_parcels"] or 0))[:12]:
        print(f"  {name:<24} mf={e['multifamily_parcels']:>7,} "
              f"total_parcels={e['parcel_counts'].get('total_parcel_count'):>7,} "
              f"mf_share={e['multifamily_share_pct']}%")
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
