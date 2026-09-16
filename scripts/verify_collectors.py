import json
from pathlib import Path

print("=" * 66)
print("REAL DATA COLLECTED FROM VERIFIED LIVE SOURCES")
print("=" * 66)

q = json.load(open("data/employment/qcew_westchester.json"))
t = q["latest_total_covered"]
print()
print("1. QCEW EMPLOYMENT  (BLS, " + q["latest_period"] + ", keyless)")
print("   Westchester: {:,} jobs | {:,} establishments | ${:,}/wk".format(
    t["employment"], t["establishments"], t["avg_weekly_wage_usd"]))
print("   NAICS sectors captured: {}".format(len(q["latest_industries"])))

g = json.load(open("data/gtfs/mnr_station_frequency.json"))
print()
print("2. TRANSIT FREQUENCY  (MTA Metro-North GTFS, service date " + g["service_date_used"] + ")")
print("   {} stations in feed -> {} matched to Westchester".format(
    g["total_stations_in_feed"], g["stations_matched_to_municipality"]))
print("   {} municipalities served | {} active trips".format(
    g["municipalities_with_rail_service"], g["active_trips"]))

p = json.load(open("data/parcels/nyopendata_property_inventory.json"))
m = p["municipalities"]
tf = sum(e["parcel_counts"].get("total_parcel_count") or 0 for e in m.values())
print()
print("3. PROPERTY INVENTORY  (NYS ORPTS via data.ny.gov, roll year " + p["roll_year"] + ")")
print("   {} municipalities | {} matched to dashboard profiles".format(
    p["municipalities_in_source"], p["municipalities_matched_to_profile"]))
print("   {:,} parcels classified; {} municipality x class rows".format(
    tf, sum(len(e["property_classes"]) for e in m.values())))

print()
print("   Largest apartment/multifamily inventories:")
for n, e in sorted(m.items(), key=lambda kv: -(kv[1]["multifamily_parcels"] or 0))[:5]:
    print("     {:<22} {:>6,} units ({}% of parcels)".format(
        n, e["multifamily_parcels"], e["multifamily_share_pct"]))

print()
print("=" * 66)
print("FILES ON DISK:")
for f in [
    "data/employment/qcew_westchester.json",
    "data/gtfs/mnr_station_frequency.json",
    "data/parcels/nyopendata_property_inventory.json",
]:
    print("  {:>9,} B  {}".format(Path(f).stat().st_size, f))
