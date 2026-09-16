#!/usr/bin/env python3
"""
BLS QCEW employment collector for WCP Dashboard (Westchester County, NY).

Source (verified live, keyless):
  https://data.bls.gov/cew/data/api/{year}/{qtr}/area/{area_fips}.csv

Westchester County area FIPS: 36119

QCEW aggregation levels present in the county file:
  70  county, total all industries, all ownerships  -> headline total
  71  county, total all industries, by ownership
  72-78  successively finer industry detail
  74  county, NAICS 2-digit sector, private ownership

QCEW publishes at county granularity, so this enriches the County profile and
is NOT decomposable to individual municipalities.

Output: data/employment/qcew_westchester.json
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AREA = "36119"  # Westchester County, NY
OUT = REPO / "data" / "employment" / "qcew_westchester.json"
YEARS = (2024, 2023)
QUARTERS = (1,)
BASE = "https://data.bls.gov/cew/data/api/{year}/{qtr}/area/{area}.csv"

OWN_CODES = {
    "0": "Total covered",
    "1": "Federal government",
    "2": "State government",
    "3": "Local government",
    "5": "Private",
}

NAICS_LABELS = {
    "11": "Agriculture, forestry, fishing & hunting",
    "21": "Mining, quarrying, oil & gas",
    "22": "Utilities",
    "23": "Construction",
    "31-33": "Manufacturing",
    "42": "Wholesale trade",
    "44-45": "Retail trade",
    "48-49": "Transportation & warehousing",
    "51": "Information",
    "52": "Finance & insurance",
    "53": "Real estate, rental & leasing",
    "54": "Professional, scientific & technical services",
    "55": "Management of companies & enterprises",
    "56": "Administrative & support, waste management",
    "61": "Educational services",
    "62": "Health care & social assistance",
    "71": "Arts, entertainment & recreation",
    "72": "Accommodation & food services",
    "81": "Other services (except public administration)",
    "92": "Public administration",
    "99": "Unclassified",
}


def num(value: str | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def peak_employment(row: dict) -> int:
    return max(num(row.get("month1_emplvl")),
               num(row.get("month2_emplvl")),
               num(row.get("month3_emplvl")))


def fetch(year: int, qtr: int) -> list[dict] | None:
    url = BASE.format(year=year, qtr=qtr, area=AREA)
    req = urllib.request.Request(url, headers={"User-Agent": "wcp-dashboard/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            text = resp.read().decode("utf-8-sig", errors="replace")
    except Exception as exc:
        print(f"  WARN {year}Q{qtr}: {exc}", file=sys.stderr)
        return None
    if not text.strip():
        return None
    return list(csv.DictReader(io.StringIO(text)))


def build_period(rows: list[dict]) -> dict:
    out: dict = {"ownership": {}, "industries": [], "total_covered": {}}

    for row in rows:
        agglvl = row.get("agglvl_code")
        own = row.get("own_code", "")

        # Headline: county, all industries, all ownerships.
        if agglvl == "70":
            out["total_covered"] = {
                "establishments": num(row.get("qtrly_estabs")),
                "employment": peak_employment(row),
                "total_qtrly_wages_usd": num(row.get("total_qtrly_wages")),
                "avg_weekly_wage_usd": num(row.get("avg_wkly_wage")),
            }
            continue

        # Ownership split: county, all industries, per ownership.
        if agglvl == "71":
            out["ownership"][OWN_CODES.get(own, own)] = {
                "establishments": num(row.get("qtrly_estabs")),
                "employment": peak_employment(row),
                "total_qtrly_wages_usd": num(row.get("total_qtrly_wages")),
                "avg_weekly_wage_usd": num(row.get("avg_wkly_wage")),
            }
            continue

        # NAICS 2-digit sectors, private ownership.
        if agglvl == "74" and own == "5":
            code = (row.get("industry_code") or "").strip()
            emp = peak_employment(row)
            if not code or emp <= 0:
                continue
            disclosure = (row.get("disclosure_code") or "").strip()
            out["industries"].append({
                "naics": code,
                "label": NAICS_LABELS.get(code, f"NAICS {code}"),
                "establishments": num(row.get("qtrly_estabs")),
                "employment": emp,
                "avg_weekly_wage_usd": num(row.get("avg_wkly_wage")),
                # "N" means BLS suppressed the figure to protect confidentiality.
                "suppressed": disclosure.upper() == "N",
            })

    out["industries"] = sorted(out["industries"], key=lambda r: -r["employment"])
    return out


def main() -> int:
    periods: dict[str, dict] = {}
    for year in YEARS:
        for qtr in QUARTERS:
            print(f"fetching {year} Q{qtr} (area {AREA}) ...")
            rows = fetch(year, qtr)
            if rows is None:
                continue
            period = build_period(rows)
            period["rows_in_file"] = len(rows)
            periods[f"{year}Q{qtr}"] = period

    if not periods:
        print("ERROR: no QCEW periods retrieved", file=sys.stderr)
        return 1

    latest_key = sorted(periods)[-1]
    latest = periods[latest_key]

    payload = {
        "source": "U.S. Bureau of Labor Statistics, Quarterly Census of "
                  "Employment and Wages (QCEW)",
        "source_url": BASE.format(year=YEARS[0], qtr=QUARTERS[0], area=AREA),
        "area_fips": AREA,
        "area_name": "Westchester County, New York",
        "latest_period": latest_key,
        "latest_total_covered": latest["total_covered"],
        "latest_ownership": latest["ownership"],
        "latest_industries": latest["industries"],
        "periods": periods,
        "granularity_note": (
            "QCEW publishes at county granularity. These figures describe "
            "Westchester County as a whole and cannot be decomposed into "
            "individual municipalities from this source."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    tc = latest["total_covered"]
    print(f"\nlatest period        : {latest_key}")
    print(f"total covered        : estabs={tc.get('establishments'):,} "
          f"emp={tc.get('employment'):,} wage=${tc.get('avg_weekly_wage_usd'):,}")
    print("ownership split:")
    for name, vals in latest["ownership"].items():
        print(f"  {name:<20} estabs={vals['establishments']:>6,} "
              f"emp={vals['employment']:>8,} avg_wkly_wage=${vals['avg_weekly_wage_usd']:,}")
    print(f"\nNAICS sectors ({len(latest['industries'])}):")
    for rec in latest["industries"]:
        flag = " [suppressed]" if rec["suppressed"] else ""
        print(f"  {rec['naics']:<6} {rec['label'][:44]:<46} "
              f"emp={rec['employment']:>7,} estabs={rec['establishments']:>6,}{flag}")
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
