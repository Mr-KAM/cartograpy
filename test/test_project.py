"""Tests pour le module project."""

import os
import pytest
import tempfile
import shutil
from cartograpy.project import Project, VECTOR_EXTENSIONS, RASTER_EXTENSIONS, TABULAR_EXTENSIONS


class TestProjectConstants:
    """Tests des constantes du module project."""

    def test_vector_extensions_is_set(self):
        assert isinstance(VECTOR_EXTENSIONS, set)
        assert ".shp" in VECTOR_EXTENSIONS
        assert ".geojson" in VECTOR_EXTENSIONS
        assert ".gpkg" in VECTOR_EXTENSIONS
        assert ".kml" in VECTOR_EXTENSIONS

    def test_raster_extensions_is_set(self):
        assert isinstance(RASTER_EXTENSIONS, set)
        assert ".tif" in RASTER_EXTENSIONS
        assert ".tiff" in RASTER_EXTENSIONS
        assert ".png" in RASTER_EXTENSIONS

    def test_tabular_extensions_is_set(self):
        assert isinstance(TABULAR_EXTENSIONS, set)
        assert ".csv" in TABULAR_EXTENSIONS
        assert ".xlsx" in TABULAR_EXTENSIONS
        assert ".json" in TABULAR_EXTENSIONS


class TestProject:
    """Tests de la classe Project."""

    def test_default_init(self):
        project = Project()
        assert project.path == os.getcwd()
        assert project.data_dir == os.path.join(os.getcwd(), "data")
        assert project.output_dir == os.path.join(os.getcwd(), "output")
        assert project.crs is not None

    def test_custom_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            assert project.path == os.path.abspath(tmpdir)

    def test_custom_data_dir(self):
        project = Project(data_dir="my_data")
        assert project.data_dir.endswith("my_data")

    def test_custom_output_dir(self):
        project = Project(output_dir="my_output")
        assert project.output_dir.endswith("my_output")

    def test_custom_crs(self):
        project = Project(crs="EPSG:3857")
        assert project.crs is not None

    def test_default_crs_epsg4326(self):
        project = Project()
        assert "4326" in str(project.crs)

    def test_empty_file_lists(self):
        project = Project()
        assert project.vector_files == []
        assert project.raster_files == []
        assert project.tabular_files == []

    def test_init_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            result = project.init()
            assert os.path.isdir(project.data_dir)
            assert os.path.isdir(project.output_dir)
            assert result == project.path

    def test_init_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            project.init()
            # Second call should not raise
            project.init()
            assert os.path.isdir(project.data_dir)

    def test_available_crs(self):
        results = Project.available_crs()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_available_crs_with_filter(self):
        results = Project.available_crs(contains="WGS")
        assert isinstance(results, list)
        # WGS 84 should appear
        if results:
            names = [r["name"] for r in results]
            assert any("WGS" in name for name in names)
