# WCP Community Profiles — Data and GIS Methodology

## Scope recovered from the approved inventory

The source-of-truth inventory is `/mnt/e/OC_Projects/projects/internal/wcp-dashboard/data/inventory.db`, exported as `2026-09-02-westchester-county-data-inventory-v2.xlsx`. This implementation exposes the dashboard components directly supported by GR-01, GR-02, GR-03, GR-07, GR-12, GR-13, GR-15, and GR-16: population/demographics, households/occupancy, housing stock and affordability, commute mode, municipal geography, parcel-assessment land use, and explicit vintage/geography metadata. The broader inventory also calls for permits, sales, condo/co-op inventory, labor/economic conditions, employers, CPI, schools, and historical crosswalks; these are documented as remaining integrations rather than filled with substitutes.

## ACS source and vintage

- **Dataset:** U.S. Census Bureau, 2024 American Community Survey 5-year detailed tables (`2024/acs/acs5`).
- **Confidence:** Every published ACS estimate is retrieved with its **90% margin of error** (`E` and `M` variables).
- **Currency:** Income, home value, and rent are the nominal inflation-adjusted dollars published for the 2024 ACS 5-year vintage. Values are not converted to another base year.
- **County:** Westchester County FIPS 36119.
- **Community profiles:** all 25 Westchester city/town county subdivisions use ACS county-subdivision observations; 20 separately represented villages use ACS places. This produces 45 municipal-government profiles because the three coterminous town-villages are represented once. Town and village profiles overlap and must not be summed.
- **Commute universe:** ACS B08301, workers age 16 and over. Mode shares include people who worked from home; they are not peak-period trips, station entries, or work-location employment.
- **Derived MOEs:** Sums use root-sum-of-squares. Percentages use the Census subset ratio approximation and fall back to the conservative sum form if the subtraction radicand is negative.

## Community geography

The Westchester County GIS Municipal Boundaries layer returned 45 polygon features but 43 unique, non-overlapping profile names. `Briarcliff Manor` and `Mamaroneck Village` each occur as two geographic parts and are unioned by name. The original 43-feature output remains unchanged in EPSG:4326 / WGS 84.

The County layer is a non-overlapping profile geography, while Census legal geographies are hierarchical and overlapping. It must not be described as a list of every municipal corporation:

- New York State's [Westchester overview](https://www.ny.gov/counties/westchester) counts **48** city, town, and village corporations.
- Westchester County's [city, town, and village assessment list](https://www.westchestercountyny.gov/online-data) separately identifies the Towns of Pelham and Rye, their constituent villages, and Mamaroneck Village as crossing the Mamaroneck/Rye town boundary.
- The dashboard exposes **45 municipal-government selectors**: the 43 non-overlapping County GIS names plus Pelham-town and Rye-town aggregate profiles. Each aggregate uses a direct ACS county-subdivision observation and a separate legal town boundary from the U.S. Census Bureau's 2024 TIGER/Line county-subdivision file. No parcels were dissolved or otherwise fabricated into a boundary.
- Town of Pelham overlaps the Pelham and Pelham Manor village profiles. Town of Rye is a noncontiguous legal geography containing Port Chester, Rye Brook, and the Rye Neck section of Mamaroneck Village. **Rye City is separate from and outside Town of Rye.**

The 43-geography County GIS base layer is preserved for non-overlapping county coverage. The two town boundaries live in separate `data/town_aggregate_boundaries.geojson` and `artifacts/gis/wcp_town_aggregates_2024.*` overlay files. Selecting one draws its dashed overlay above the base map. The explicit 43-geography base crosswalk remains `config/geography_crosswalk.csv`.

## Land use

Land use is based on the County's 2025 Tax Parcels layer, not on zoning, ACS units-in-structure, or remote-sensing land cover. The build groups `PROP_CLASS` by its first NYS ORPTS classification digit and sums `CALC_ACRES`. Records with `DUP_GEO='Y'` are excluded to avoid overlapping duplicate parcel geometry, including many condo/co-op records.

Town aggregate parcel observations are separately queried by official assessment SWIS prefixes: `5544%` for Town of Pelham and `5548%` for Town of Rye. The latter includes the Rye-side (`554803`) portion of Mamaroneck Village; City of Rye uses `551400` and is not included. These aggregate rows are not added into the separately calculated County total.

This measure is best described as **assessment-parcel acres by primary property class**. It does not cover rights-of-way or water, mixed-use parcels have one primary class, and the summed acreage will not equal municipal land area. Parcel record counts are included as QA context.

## Honest gaps

1. Municipal building-permit detail is not available in one verified public countywide source.
2. A complete condominium/cooperative inventory has no verified public feed.
3. Establishment-level employment for major employers requires a curated County source; QCEW microdata are confidential.
4. CDBG-funded project locations lack a verified public countywide spatial layer.
5. GTFS service frequency, NYSED enrollment, ORPTS sales, and historical boundary-normalized trends remain future integrations.

## Rebuild

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build_data.py
pytest -q
```

The Census API key is read from `CENSUS_API_KEY` or `~/.hermes/.env` and is never written to output.
