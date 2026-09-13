# WCP community profile GIS package

This folder contains the unchanged **43 unique, non-overlapping Westchester community profile polygons** plus a separate two-feature file for the overlapping Town of Pelham and Town of Rye legal boundaries. County GIS source parts are unioned by profile name where necessary. The County total is intentionally not included as a duplicate overlay feature.

## Files

- `wcp_community_profiles_2024.gpkg` — GeoPackage, layer `community_profiles`, rich field names.
- `wcp_community_profiles_2024.geojson` — web/GIS GeoJSON with the same 43 features.
- `wcp_profiles_2024_shapefile.zip` — portable shapefile bundle.
- `shapefile/wcp_profiles.shp/.shx/.dbf/.prj/.cpg` — unzipped shapefile components.
- `FIELD_DICTIONARY.csv` — mapping between ten-character-safe shapefile fields and rich names.
- `wcp_town_aggregates_2024.gpkg` — separate `town_aggregates` layer with two overlapping legal town boundaries.
- `wcp_town_aggregates_2024.geojson` — the same two aggregate overlays in GeoJSON.

## CRS and sources

- CRS: **EPSG:4326 — WGS 84**.
- Boundaries: Westchester County GIS `Datahub_Boundaries/MapServer/163`, retrieved by the build recorded in `data/build_report.json`.
- Aggregate boundaries: U.S. Census Bureau 2024 TIGER/Line New York county subdivisions, filtered to GEOIDs `3611957012` (Pelham town) and `3611964320` (Rye town), then reprojected from EPSG:4269 to EPSG:4326.
- Attributes: U.S. Census Bureau 2024 ACS 5-year detailed tables; land-use acreage from Westchester County GIS 2025 Tax Parcels (`DataHub_TaxParcels/MapServer/0`).

## Important geography note

The 43 base profiles are the unique names in the County profile boundary layer. The two aggregate overlays complete the 45 municipal-government selector profiles without changing the base layer. Village ACS place estimates overlap town ACS subdivision estimates. Do not sum profile values to calculate a County total; use the separately queried County profile.

## Land-use note

`lu_acres` is assessment-parcel acreage by primary property class with duplicate geometry records excluded. It is not zoning, land cover, or total municipal land area. See `docs/METHODOLOGY.md`.
