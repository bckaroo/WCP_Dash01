"""
Sanity tests for WCP dashboard external-data collectors.

These guard the *integrity* of collected datasets rather than re-testing the
remote APIs. They exist because a real defect shipped during development:
assessment-roll class counts were summed across every roll year present in the
source dataset, inflating per-municipality shares above 100%.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"

GTFS = DATA / "gtfs" / "mnr_station_frequency.json"
QCEW = DATA / "employment" / "qcew_westchester.json"
PROPERTY = DATA / "parcels" / "nyopendata_property_inventory.json"


def load(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"collector output not built yet: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- property ---

def test_property_multifamily_share_never_exceeds_100_percent():
    """Regression: summing multiple roll years produced >100% shares."""
    doc = load(PROPERTY)
    offenders = {
        name: entry["multifamily_share_pct"]
        for name, entry in doc["municipalities"].items()
        if entry.get("multifamily_share_pct") is not None
        and entry["multifamily_share_pct"] > 100
    }
    assert not offenders, f"multifamily share >100% for: {offenders}"


def test_property_multifamily_never_exceeds_total_parcels():
    doc = load(PROPERTY)
    for name, entry in doc["municipalities"].items():
        total = entry["parcel_counts"].get("total_parcel_count")
        if total:
            assert entry["multifamily_parcels"] <= total, (
                f"{name}: multifamily {entry['multifamily_parcels']} > total {total}"
            )


def test_property_counts_are_non_negative():
    doc = load(PROPERTY)
    for name, entry in doc["municipalities"].items():
        for field, value in entry["parcel_counts"].items():
            if value is not None:
                assert value >= 0, f"{name}.{field} negative: {value}"
        for rec in entry["property_classes"]:
            assert rec["parcels"] >= 0


def test_property_roll_year_is_single_valued():
    """The collector must collapse the source to exactly one roll year."""
    doc = load(PROPERTY)
    years = {entry["roll_year"] for entry in doc["municipalities"].values()}
    assert len(years) == 1, f"multiple roll years present: {years}"
    assert doc["roll_year"] in years


# ------------------------------------------------------------------- qcew ---

def test_qcew_has_total_covered_headline():
    doc = load(QCEW)
    total = doc["latest_total_covered"]
    assert total["employment"] > 0
    assert total["establishments"] > 0


def test_qcew_ownership_sums_near_total_covered():
    """Ownership components should reconstruct the headline within rounding."""
    doc = load(QCEW)
    total = doc["latest_total_covered"]["employment"]
    parts = sum(v["employment"] for v in doc["latest_ownership"].values())
    assert parts > 0
    assert abs(parts - total) / total < 0.05, (
        f"ownership sum {parts} vs total covered {total} diverge >5%"
    )


def test_qcew_industries_have_naics_and_labels():
    doc = load(QCEW)
    industries = doc["latest_industries"]
    assert len(industries) >= 15, f"expected full NAICS sector set, got {len(industries)}"
    for rec in industries:
        assert rec["naics"], "industry missing NAICS code"
        assert rec["label"], f"industry {rec['naics']} missing label"
        assert rec["employment"] >= 0


# ------------------------------------------------------------------- gtfs ---

def test_gtfs_station_accounting_balances():
    doc = load(GTFS)
    matched = doc["stations_matched_to_municipality"]
    outside = doc["stations_outside_westchester"]
    assert matched + outside == doc["total_stations_in_feed"]


def test_gtfs_per_municipality_totals_are_consistent():
    doc = load(GTFS)
    for name, entry in doc["municipalities"].items():
        assert entry["stations"] == len(entry["station_names"]), name
        assert entry["weekday_scheduled_calls"] >= 0, name
    assert doc["municipalities_with_rail_service"] == len(doc["municipalities"])


def test_gtfs_service_date_is_present():
    doc = load(GTFS)
    assert doc["service_date_used"], "service date must be recorded for provenance"
    assert doc["active_trips"] > 0
