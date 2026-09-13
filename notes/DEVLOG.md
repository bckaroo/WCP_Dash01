# Development Log

Append-only log of each round of development on this repo (part of DevOS
project **PROJ-023**). New entries go at the top.

## Round 3 — 2026-09-13 · All-municipalities aggregate coverage
- Added separate `Town of Pelham` and `Town of Rye` selector profiles from direct 2024 ACS county-subdivision observations (GEOIDs `0600000US3611957012` and `0600000US3611964320`), bringing the product to county + 45 municipal-government profiles.
- Preserved the 43-feature non-overlapping County GIS base map and added a separate two-feature 2024 Census TIGER/Line overlay. Rye town correctly renders as a noncontiguous MultiPolygon covering Port Chester/Rye Brook plus the Rye Neck section of Mamaroneck Village; Rye City remains separate.
- Added 2025 County parcel land-use aggregates using SWIS `5544%` (Pelham) and `5548%` (Rye, including Mamaroneck Village's `554803` Rye portion and excluding Rye City's `551400`). Aggregate rows remain isolated from the County land-use total.
- Relabeled Harrison, Mount Kisco, and Scarsdale as `coterminous town-village`; updated the sidebar, methods disclosure, README, GIS package notes, methodology, and download links to explain 48 state-reported corporations / 45 government profiles / 43 non-overlapping base map geographies.
- Live rebuild evidence: 46 total profiles, 45 municipal profiles, 43 base features, 2 valid aggregate overlays, 25 ACS county-subdivision rows, 45 County boundary source rows / 43 names, 3,047 base + 148 aggregate parcel-stat groups, 2025 roll/spatial vintages.
- Verification: `11 passed`; JS/Python syntax checks passed; all app/data/download URLs returned HTTP 200; browser exercised all 46 county/profile routes and all five tabs on both new town profiles with no failures or runtime errors. Evidence: `artifacts/verification/pelham-town-aggregate-overlay.png` and `rye-town-aggregate-overlay.png`.

## Round 2 — 2026-09-13 · Post-build verification and geography clarification
- Rebuilt all data from the live 2024 ACS and Westchester County GIS services: county + 43 profiles, 45 boundary source rows / 43 unique profile geometries, and 3,047 parcel statistic groups with 2025 roll/spatial vintages.
- Verified the iterative SVG bounds fix in a real browser: the County map renders 43 populated paths without stack overflow; all 44 county/community routes, select navigation, map clicks, directory search, reset, topic tabs, charts, and 390px responsive layout passed. Browser runtime error capture returned none.
- Added explicit administrative-geography disclosure: 43 non-overlapping County GIS profiles are not falsely labeled as every municipal corporation; coterminous Harrison/Mount Kisco/Scarsdale and overlapping Pelham/Rye town totals are explained, with Rye City kept distinct.
- Repaired prototype asset caching after browser QA exposed stale `app.js`; HTML/CSS/JS/JSON/GeoJSON now return `Cache-Control: no-cache`, and a service restart confirmed the repaired methods view.
- Saved visual evidence under `artifacts/verification/`: County overview/map, Rye City land use, coverage methods, and 390px Mount Kisco mobile views.
- Automated verification: `9 passed`; `node --check app.js`; Python compile; valid EPSG:4326 GeoJSON/GeoPackage/Shapefile; all live app/data/download endpoints returned HTTP 200.
- DevOS: `PROJ-023` doctor verdict OK; expected warning remains that no remote is configured.

## Round 1 — <YYYY-MM-DD> · Initial commit
- Created via `devos init-repo`.
