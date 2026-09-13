import csv
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
import scripts.build_data as build_data
import scripts.serve as serve

ROOT = Path(__file__).resolve().parents[1]


def load_profiles():
    return json.loads((ROOT / "data" / "profiles.json").read_text(encoding="utf-8"))


def test_profile_completeness_and_uniqueness():
    payload = load_profiles()
    profiles = payload["profiles"]
    municipalities = [profile for profile in profiles if profile["profile_type"] != "county"]
    assert len(profiles) == 46
    assert len(municipalities) == 45
    assert len({profile["id"] for profile in profiles}) == 46
    assert len({profile["name"] for profile in municipalities}) == 45
    assert payload["metadata"]["acs"]["vintage"] == 2024
    assert payload["metadata"]["boundaries"]["source_feature_rows"] == 45
    assert payload["metadata"]["boundaries"]["unique_profile_communities"] == 43


def test_all_communities_resolve_to_census_and_land_use():
    payload = load_profiles()
    for profile in payload["profiles"]:
        assert profile["census_geoid"].endswith(tuple("0123456789"))
        assert profile["metrics"]["population"]["total"]["estimate"] is not None
        # ACS control totals such as total population can publish no sampling MOE;
        # the paired M field is still requested and its sentinel is preserved as null.
        assert profile["metrics"]["income"]["median_household"]["moe"] is not None
        land = profile["metrics"]["land_use"]
        assert land["assessor_parcel_acres"] > 0
        assert land["parcel_records"] > 0
        assert land["categories"]
    municipalities = payload["profiles"][1:]
    assert {p["census_geography"] for p in municipalities} == {"county subdivision", "place"}
    assert sum(p["census_geography"] == "county subdivision" for p in municipalities) == 25
    assert sum(p["census_geography"] == "place" for p in municipalities) == 20


def test_county_observation_is_plausible_and_documented():
    payload = load_profiles()
    county = payload["profiles"][0]
    assert county["id"] == "westchester-county"
    assert 900_000 < county["metrics"]["population"]["total"]["estimate"] < 1_100_000
    assert "Workers 16 years and over" in payload["metadata"]["commute_universe"]
    assert "Nominal 2024" in payload["metadata"]["acs"]["dollar_basis"]
    assert len(payload["metadata"]["known_gaps"]) >= 4


def test_crosswalk_matches_profiles():
    with (ROOT / "config" / "geography_crosswalk.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = {
        profile["id"]
        for profile in load_profiles()["profiles"][1:]
        if profile.get("map_role") == "base"
    }
    assert len(rows) == 43
    assert {row["profile_id"] for row in rows} == ids
    assert len({row["geometry_name"] for row in rows}) == 43


def test_administrative_geography_distinctions_are_explicit():
    with (ROOT / "config" / "geography_crosswalk.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = {row["profile_id"] for row in rows}
    assert {"harrison", "mount-kisco", "scarsdale", "rye-city"} <= ids
    assert {"pelham", "pelham-manor", "port-chester", "rye-brook"} <= ids
    profiles = {profile["id"]: profile for profile in load_profiles()["profiles"]}
    assert {"pelham-town", "rye-town"} <= profiles.keys()
    for profile_id in ("pelham-town", "rye-town"):
        profile = profiles[profile_id]
        assert profile["profile_type"] == "overlapping town aggregate"
        assert profile["map_role"] == "aggregate overlay"
        assert profile["census_geography"] == "county subdivision"
        assert profile["census_geoid"].startswith("0600000US36119")
        assert "overlap" in profile["geography_note"].lower()
    for profile_id in ("harrison", "mount-kisco", "scarsdale"):
        assert profiles[profile_id]["profile_type"] == "coterminous town-village"
    methods = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "43 non-overlapping map geographies + 2 town aggregates" in methods
    assert "Rye Neck section of Mamaroneck Village" in methods


def test_town_aggregate_boundaries_are_authoritative_and_separate():
    payload = load_profiles()
    aggregates = [profile for profile in payload["profiles"] if profile.get("map_role") == "aggregate overlay"]
    assert {profile["id"] for profile in aggregates} == {"pelham-town", "rye-town"}
    assert {profile["census_geoid"] for profile in aggregates} == {
        "0600000US3611957012",
        "0600000US3611964320",
    }
    assert payload["metadata"]["aggregate_boundaries"]["source_kind"] == "U.S. Census Bureau TIGER/Line county subdivisions"
    assert payload["metadata"]["aggregate_boundaries"]["vintage"] == 2024

    web = gpd.read_file(ROOT / "data" / "town_aggregate_boundaries.geojson")
    geojson = gpd.read_file(ROOT / "artifacts" / "gis" / "wcp_town_aggregates_2024.geojson")
    gpkg = gpd.read_file(ROOT / "artifacts" / "gis" / "wcp_town_aggregates_2024.gpkg", layer="town_aggregates")
    for frame in (web, geojson, gpkg):
        assert len(frame) == 2
        assert frame.crs.to_epsg() == 4326
        assert frame.geometry.notna().all()
        assert frame.geometry.is_valid.all()
        assert set(frame["profile_id"]) == {"pelham-town", "rye-town"}
    rye = geojson.loc[geojson["profile_id"] == "rye-town"].iloc[0]
    assert rye.geometry.geom_type == "MultiPolygon"


def test_gis_formats_counts_crs_and_geometry():
    gpkg = gpd.read_file(ROOT / "artifacts" / "gis" / "wcp_community_profiles_2024.gpkg", layer="community_profiles")
    geojson = gpd.read_file(ROOT / "artifacts" / "gis" / "wcp_community_profiles_2024.geojson")
    shp = gpd.read_file(ROOT / "artifacts" / "gis" / "shapefile" / "wcp_profiles.shp")
    for frame in (gpkg, geojson, shp):
        assert len(frame) == 43
        assert frame.crs is not None
        assert frame.crs.to_epsg() == 4326
        assert frame.geometry.notna().all()
        assert frame.geometry.is_valid.all()
    assert set(gpkg["profile_id"]) == set(geojson["profile_id"]) == set(shp["id"])


def test_shapefile_bundle_is_complete_and_ten_character_safe():
    gis = ROOT / "artifacts" / "gis"
    required = {"wcp_profiles.shp", "wcp_profiles.shx", "wcp_profiles.dbf", "wcp_profiles.prj", "wcp_profiles.cpg"}
    assert required <= {path.name for path in (gis / "shapefile").iterdir()}
    with zipfile.ZipFile(gis / "wcp_profiles_2024_shapefile.zip") as archive:
        names = set(archive.namelist())
    assert required <= names
    assert {"FIELD_DICTIONARY.csv", "README.md"} <= names
    shp = gpd.read_file(gis / "shapefile" / "wcp_profiles.shp")
    assert all(len(field) <= 10 for field in shp.columns if field != "geometry")


def test_dashboard_assets_and_download_links_exist():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    assert 'data-theme="population"' in html
    assert 'data-theme="housing"' in html
    assert 'data-theme="commute"' in html
    assert 'data-theme="land-use"' in html
    assert "wcp_profiles_2024_shapefile.zip" in html
    assert "45 municipal-government profiles" in html
    assert "wcp_town_aggregates_2024.geojson" in html
    assert "Profile completeness check failed" in js
    assert "town_aggregate_boundaries.geojson" in js
    for filename in ("index.html", "styles.css", "app.js"):
        assert (ROOT / filename).stat().st_size > 500


def test_server_port_override_and_cache_targets(monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "ROOT", tmp_path)
    monkeypatch.setenv("SERVICE_PORT", "9123")
    assert serve.configured_port() == 9123
    monkeypatch.delenv("SERVICE_PORT")
    (tmp_path / ".env.PORT").write_text("SERVICE_PORT=9010 # WCP prototype\n", encoding="utf-8")
    assert serve.configured_port() == 9010
    assert serve.should_disable_cache("/app.js?v=2")
    assert serve.should_disable_cache("/?qa=final")
    assert not serve.should_disable_cache("/artifacts/gis/wcp_profiles_2024_shapefile.zip?download=1")
    assert serve.parse_port("65535", "test") == 65535
    for invalid in ("", "abc", "0", "65536"):
        with pytest.raises(RuntimeError):
            serve.parse_port(invalid, "test")


def test_parcel_group_query_reports_the_truncated_geography(monkeypatch):
    monkeypatch.setattr(build_data, "get_json", lambda *_args, **_kwargs: {"exceededTransferLimit": True})
    with pytest.raises(AssertionError, match="Town of Rye"):
        build_data.parcel_group_query("Town of Rye", "SWIS LIKE '5548%'")
