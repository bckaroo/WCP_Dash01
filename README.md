# Westchester Community Profiles

Working public-data prototype for the Westchester County Department of Planning. It provides a county overview and drilldown to **all 45 municipal-government profiles**: 43 non-overlapping County GIS map geographies plus separate overlapping Town of Pelham and Town of Rye aggregates. Harrison, Mount Kisco, and Scarsdale are each accurately labeled and shown once as coterminous town-villages. Town of Rye is distinct from Rye City and includes Port Chester, Rye Brook, and the Rye Neck section of Mamaroneck Village.

## Launch

```bash
python3 scripts/serve.py
```

Open **http://localhost:9010**. The service port is owned by `.env.PORT` and registered in the shared service registry.

## Rebuild data

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build_data.py
pytest -q
node --check app.js
```

The build queries live official sources and writes:

- `data/profiles.json` — county + 43 base-map profiles + 2 overlapping town aggregates;
- `data/municipal_boundaries.geojson` — web map layer;
- `data/town_aggregate_boundaries.geojson` — separate Pelham/Rye legal-town overlays;
- `artifacts/gis/wcp_community_profiles_2024.gpkg`;
- `artifacts/gis/wcp_community_profiles_2024.geojson`;
- `artifacts/gis/wcp_profiles_2024_shapefile.zip`;
- `artifacts/gis/wcp_town_aggregates_2024.geojson` and `.gpkg`;
- `artifacts/gis/FIELD_DICTIONARY.csv`.

## Sources

- U.S. Census Bureau **2024 ACS 5-year detailed tables**, estimates plus 90% margins of error.
- Westchester County GIS Municipal Boundaries, 45 source polygon parts unioned to 43 unique profile names.
- U.S. Census Bureau 2024 TIGER/Line county subdivisions for the two legal town aggregate overlays.
- Westchester County GIS **2025 Tax Parcels**, `PROP_CLASS` and `CALC_ACRES`, excluding duplicate geometry records.
- [Westchester County municipal assessment list](https://www.westchestercountyny.gov/online-data), which separately identifies Town of Pelham, Town of Rye, their villages, and the cross-town Village of Mamaroneck.
- [New York State Westchester overview](https://www.ny.gov/counties/westchester), which reports 48 municipalities. The dashboard has 45 government profiles because each of the three coterminous town-village pairs—Harrison, Mount Kisco, and Scarsdale—has one combined government and is represented once.

See `docs/METHODOLOGY.md` for universes, geography hierarchy, income-dollar basis, land-use definition, and gaps.
