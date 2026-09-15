# Development Log

Append-only log of each round of development on this repo (part of DevOS
project **PROJ-023**). New entries go at the top.

## Round 5 — 2026-09-15 · GitHub publication preparation (DEV-119)
- User authorized upload of the current dashboard to the existing public `bckaroo/WCP_Dash01` repository; preserve its MIT license and remote history without force-pushing.
- Verified current workspace: `python3 -m pytest -q` (12 passed), `node --check app.js`, and Gitleaks v8.30.1 scans of existing Git history and working directory (no leaks found).
- Expanded environment-file ignores while retaining the project-owned `.env.PORT` port configuration. Included the current design refresh, data/GIS downloads, and browser QA evidence in the publication snapshot.

## Round 4 — 2026-09-15 · Live redesign rendering verification
- Reproduced the reported loading-state screenshot against the live Tailnet URL in a fresh Chrome 152 session. The application reached the concrete ready state (`#status[hidden]`, visible `#dashboard`) with 43 map paths, four key facts, and populated theme content; no JavaScript or promise errors were captured. The earlier screenshot was taken before asynchronous JSON/GeoJSON initialization completed, not from a persistent application/data-load defect, so no product-code repair was required.
- Exercised all 46 profile routes across all six themes (276 route/theme combinations), including Economy and Coverage & methods, with zero failures. Verified municipality-select, tab, directory-search, and SVG-map interactions, plus the Town of Rye aggregate overlay (43 base paths + one overlay).
- Verified the live index, app assets, all three runtime data files, and all seven GIS/download artifacts returned HTTP 200. Automated verification passed: `python3 -m pytest -q` (12 passed), `node --check app.js`, and Python compile checks.
- Verified responsive rendering at 390 px with zero horizontal overflow and populated Mount Kisco Economy content. Evidence: `artifacts/verification/browser-qa-report.json`, `final-populated-desktop.png`, `final-populated-mobile.png`, `final-populated-mobile-economy.png`, and `final-populated-mobile-economy-content.png`.

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
