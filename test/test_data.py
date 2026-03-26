"""Tests pour le module data."""

import os
import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from cartograpy.data import load, save, list_geofiles, GeoBoundaries, Bound


class TestLoad:
    """Tests de la fonction load."""

    def test_load_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n")
        df = load(str(csv_file))
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2

    def test_load_geojson(self, tmp_path):
        gdf = gpd.GeoDataFrame(
            {"name": ["A"]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        )
        path = tmp_path / "test.geojson"
        gdf.to_file(str(path), driver="GeoJSON")
        result = load(str(path))
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1

    def test_load_unsupported_format(self, tmp_path):
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("hello")
        with pytest.raises(ValueError, match="non supporté"):
            load(str(bad_file))

    def test_load_shapefile(self, tmp_path):
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(1, 2)],
            crs="EPSG:4326",
        )
        path = tmp_path / "test.shp"
        gdf.to_file(str(path))
        result = load(str(path))
        assert isinstance(result, gpd.GeoDataFrame)

    def test_load_gpkg(self, tmp_path):
        gdf = gpd.GeoDataFrame(
            {"val": [10]},
            geometry=[Point(5, 5)],
            crs="EPSG:4326",
        )
        path = tmp_path / "test.gpkg"
        gdf.to_file(str(path), driver="GPKG")
        result = load(str(path))
        assert isinstance(result, gpd.GeoDataFrame)


class TestSave:
    """Tests de la fonction save."""

    def test_save_geojson(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gdf = gpd.GeoDataFrame(
            {"name": ["A"]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        )
        result = save(gdf, "geojson", "out")
        assert os.path.exists(result)
        assert result.endswith(".geojson")

    def test_save_csv(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = save(df, "csv", "out")
        assert os.path.exists(result)
        loaded = pd.read_csv(result)
        assert list(loaded.columns) == ["a", "b"]

    def test_save_unsupported_format(self):
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match="non supporté"):
            save(df, "xyz", "out")

    def test_save_unsupported_type(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(TypeError, match="non pris en charge"):
            save("not a dataframe", "csv", "out")

    def test_save_with_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        df = pd.DataFrame({"x": [1]})
        result = save(df, "csv", "out", timestamp=True)
        assert os.path.exists(result)
        basename = os.path.basename(result)
        # Should contain date stamp pattern
        assert "out_" in basename

    def test_save_shapefile(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gdf = gpd.GeoDataFrame(
            {"name": ["B"]},
            geometry=[Point(1, 1)],
            crs="EPSG:4326",
        )
        result = save(gdf, "shp", "out")
        assert os.path.exists(result)


class TestListGeofiles:
    """Tests de la fonction list_geofiles."""

    def test_empty_folder(self, tmp_path):
        assert list_geofiles(str(tmp_path)) == []

    def test_finds_geofiles(self, tmp_path):
        (tmp_path / "data.shp").write_text("")
        (tmp_path / "data.geojson").write_text("")
        (tmp_path / "readme.txt").write_text("")
        result = list_geofiles(str(tmp_path))
        assert len(result) == 2
        extensions = {os.path.splitext(f)[1] for f in result}
        assert ".shp" in extensions
        assert ".geojson" in extensions

    def test_finds_in_subdirectories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.gpkg").write_text("")
        result = list_geofiles(str(tmp_path))
        assert len(result) == 1

    def test_finds_raster_files(self, tmp_path):
        (tmp_path / "raster.tif").write_text("")
        (tmp_path / "raster2.tiff").write_text("")
        result = list_geofiles(str(tmp_path))
        assert len(result) == 2

    def test_ignores_non_geo_files(self, tmp_path):
        (tmp_path / "notes.txt").write_text("")
        (tmp_path / "image.png").write_text("")
        (tmp_path / "doc.pdf").write_text("")
        assert list_geofiles(str(tmp_path)) == []


class TestGeoBoundaries:
    """Tests de la classe GeoBoundaries."""

    def test_instantiation(self):
        gb = GeoBoundaries()
        assert gb._base_url == "https://www.geoboundaries.org/api/current/gbOpen"

    def test_validate_adm_int(self):
        gb = GeoBoundaries()
        assert gb._validate_adm(0) == "ADM0"
        assert gb._validate_adm(3) == "ADM3"

    def test_validate_adm_string(self):
        gb = GeoBoundaries()
        assert gb._validate_adm("adm1") == "ADM1"
        assert gb._validate_adm("ADM2") == "ADM2"

    def test_validate_adm_invalid(self):
        gb = GeoBoundaries()
        with pytest.raises(KeyError, match="invalide"):
            gb._validate_adm("ADM9")

    def test_is_valid_iso3(self):
        gb = GeoBoundaries()
        assert gb._is_valid_iso3_code("fra") is True
        assert gb._is_valid_iso3_code("mli") is True

    def test_is_invalid_iso3(self):
        gb = GeoBoundaries()
        assert gb._is_valid_iso3_code("zzz") is False

    def test_get_iso3_from_iso3_code(self):
        gb = GeoBoundaries()
        assert gb.get_iso3("fra") == "FRA"
        assert gb.get_iso3("mli") == "MLI"

    def test_get_iso3_from_name(self):
        gb = GeoBoundaries()
        result = gb.get_iso3("France")
        assert result == "FRA"

    def test_get_iso3_unknown(self):
        gb = GeoBoundaries()
        result = gb.get_iso3("xyznonexistent")
        assert result is None

    def test_list_countries(self):
        gb = GeoBoundaries()
        countries = gb.list_countries()
        assert isinstance(countries, list)
        assert len(countries) > 100

    def test_continent_mapping(self):
        gb = GeoBoundaries()
        mapping = gb._CONTINENT_MAPPING
        assert mapping["africa"] == "Africa"
        assert mapping["afrique"] == "Africa"
        assert mapping["europe"] == "Europe"

    def test_admin_levels_returns_string(self):
        gb = GeoBoundaries()
        result = gb.adminLevels()
        assert isinstance(result, str)
        assert "ADM0" in result
        assert "ADM5" in result

    def test_list_continents_names(self):
        gb = GeoBoundaries()
        result = gb.list_continents_names()
        assert isinstance(result, dict)
        assert "africa" in result


class TestBound:
    """Tests de la classe Bound."""

    def test_inherits_geoboundaries(self):
        assert issubclass(Bound, GeoBoundaries)

    def test_instantiation(self):
        b = Bound()
        assert b._base_url == "https://www.geoboundaries.org/api/current/gbOpen"

    def test_get_world_invalid_level(self):
        b = Bound()
        with pytest.raises(ValueError, match="non supporté"):
            b.get_world("invalid_level")
