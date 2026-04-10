"""Tests pour le module project."""

import os
import tempfile
import pytest
from cartograpy.project import (
    Project, VECTOR_EXTENSIONS, RASTER_EXTENSIONS, TABULAR_EXTENSIONS,
    SHAPEFILE_SIDECARS, TAB_SIDECARS,
    _classify_extension, _get_sidecars_for, _ALL_SIDECAR_EXTENSIONS,
)


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
        results = Project.available_crs(name_contains="WGS")
        assert isinstance(results, list)
        # WGS 84 should appear
        if results:
            names = [r["name"] for r in results]
            assert any("WGS" in name for name in names)

    def test_available_crs_filter_excludes_non_matching(self):
        results = Project.available_crs(name_contains="WGS")
        for r in results:
            assert "wgs" in r["name"].lower()


class TestSidecarConstants:
    """Tests des constantes de sidecars."""

    def test_shapefile_sidecars(self):
        assert isinstance(SHAPEFILE_SIDECARS, set)
        assert ".shx" in SHAPEFILE_SIDECARS
        assert ".dbf" in SHAPEFILE_SIDECARS
        assert ".prj" in SHAPEFILE_SIDECARS

    def test_tab_sidecars(self):
        assert isinstance(TAB_SIDECARS, set)
        assert ".dat" in TAB_SIDECARS


def _make_project(tmpdir):
    """Helper : crée un Project initialisé dans un dossier temporaire."""
    project = Project(path=tmpdir)
    project.init()
    return project


def _create_dummy_files(directory, filenames):
    """Helper : crée des fichiers vides dans un dossier."""
    for name in filenames:
        path = os.path.join(directory, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("dummy")


class TestAddDataFromPath:
    """Tests de add_data() avec un chemin de fichier."""

    def test_copy_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            # Créer un fichier source
            src = os.path.join(tmpdir, "source.geojson")
            with open(src, "w") as f:
                f.write('{"type":"FeatureCollection","features":[]}')
            result = project.add_data(src)
            assert os.path.isfile(result)
            assert result.endswith("source.geojson")
            assert os.path.dirname(result) == project.data_dir

    def test_copy_with_custom_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "original.csv")
            with open(src, "w") as f:
                f.write("a,b\n1,2")
            result = project.add_data(src, filename="renamed")
            assert "renamed.csv" in os.path.basename(result)

    def test_copy_shapefile_with_sidecars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
                with open(os.path.join(src_dir, f"roads{ext}"), "w") as f:
                    f.write("dummy")
            result = project.add_data(os.path.join(src_dir, "roads.shp"))
            assert os.path.isfile(result)
            # Vérifier que les sidecars ont été copiés
            for ext in [".shx", ".dbf", ".prj", ".cpg"]:
                assert os.path.isfile(os.path.join(project.data_dir, f"roads{ext}"))

    def test_copy_nonexistent_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project.add_data("/chemin/inexistant.geojson")

    def test_extension_deduced_from_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "data.gpkg")
            with open(src, "w") as f:
                f.write("dummy")
            result = project.add_data(src)
            assert result.endswith(".gpkg")

    def test_missing_extension_without_path_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises((ValueError, TypeError)):
                project.add_data(42)  # ni chemin, ni GeoDataFrame, pas d'extension


class TestListData:
    """Tests de list_data()."""

    def test_list_data_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            assert project.list_data() == []

    def test_list_data_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.geojson", "elevation.tif", "stats.csv",
            ])
            result = project.list_data()
            assert len(result) == 3
            names = {r["name"] for r in result}
            assert names == {"carte", "elevation", "stats"}

    def test_list_data_filter_vector(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.geojson", "elevation.tif", "stats.csv",
            ])
            result = project.list_data(type_filter="vector")
            assert len(result) == 1
            assert result[0]["name"] == "carte"

    def test_list_data_filter_raster(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["elevation.tif"])
            result = project.list_data(type_filter="raster")
            assert len(result) == 1
            assert result[0]["type"] == "raster"

    def test_list_data_includes_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["data.csv"])
            result = project.list_data()
            assert "size" in result[0]
            assert result[0]["size"] > 0

    def test_list_data_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                os.path.join("vector", "carte.shp"),
                "stats.csv",
            ])
            result = project.list_data()
            assert len(result) == 2

    def test_list_data_no_data_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            # Ne pas appeler init() → pas de data_dir
            assert project.list_data() == []


class TestLoadData:
    """Tests de load_data()."""

    def test_load_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            csv_path = os.path.join(project.data_dir, "test.csv")
            with open(csv_path, "w") as f:
                f.write("col1,col2\n1,2\n3,4")
            df = project.load_data("test.csv")
            assert len(df) == 2

    def test_load_by_basename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            csv_path = os.path.join(project.data_dir, "test.csv")
            with open(csv_path, "w") as f:
                f.write("col1,col2\n1,2")
            df = project.load_data("test")
            assert len(df) == 1

    def test_load_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            sub = os.path.join(project.data_dir, "tabular")
            os.makedirs(sub)
            with open(os.path.join(sub, "deep.csv"), "w") as f:
                f.write("a,b\n1,2")
            df = project.load_data("deep.csv")
            assert len(df) == 1

    def test_load_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project.load_data("inexistant.csv")

    def test_load_no_data_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            with pytest.raises(FileNotFoundError):
                project.load_data("test.csv")


class TestRemoveData:
    """Tests de remove_data()."""

    def test_remove_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["test.geojson"])
            removed = project.remove_data("test.geojson")
            assert len(removed) == 1
            assert not os.path.isfile(os.path.join(project.data_dir, "test.geojson"))

    def test_remove_shapefile_with_sidecars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                with open(os.path.join(project.data_dir, f"roads{ext}"), "w") as f:
                    f.write("dummy")
            removed = project.remove_data("roads.shp")
            assert len(removed) == 4
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                assert not os.path.isfile(os.path.join(project.data_dir, f"roads{ext}"))

    def test_remove_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project.remove_data("inexistant.csv")


class TestGetPath:
    """Tests de get_path()."""

    def test_get_path_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["carte.geojson"])
            path = project.get_path("carte.geojson")
            assert os.path.isfile(path)

    def test_get_path_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.output_dir, ["result.png"])
            path = project.get_path("result.png", folder="output")
            assert os.path.isfile(path)

    def test_get_path_by_basename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["carte.geojson"])
            path = project.get_path("carte")
            assert path.endswith("carte.geojson")

    def test_get_path_recursive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                os.path.join("vector", "deep.gpkg"),
            ])
            path = project.get_path("deep.gpkg")
            assert os.path.isfile(path)

    def test_get_path_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project.get_path("inexistant.csv")


class TestSetCrs:
    """Tests de set_crs()."""

    def test_set_crs(self):
        project = Project()
        assert "4326" in str(project.crs)
        project.set_crs("EPSG:3857")
        assert "3857" in str(project.crs)

    def test_set_crs_returns_crs(self):
        project = Project()
        result = project.set_crs("EPSG:32630")
        assert result is project.crs


class TestCleanOutput:
    """Tests de clean_output()."""

    def test_clean_output_removes_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.output_dir, ["a.png", "b.tif"])
            count = project.clean_output()
            assert count == 2
            assert os.listdir(project.output_dir) == []

    def test_clean_output_removes_subdirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.output_dir, [
                os.path.join("sub", "file.png"),
            ])
            count = project.clean_output()
            assert count == 1
            # Sous-dossier supprimé aussi
            assert not os.path.isdir(os.path.join(project.output_dir, "sub"))

    def test_clean_output_no_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            count = project.clean_output()
            assert count == 0

    def test_clean_output_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            count = project.clean_output()
            assert count == 0


class TestValidate:
    """Tests de validate()."""

    def test_validate_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            report = project.validate()
            assert report["valid"] is True
            assert report["data_dir_exists"] is True
            assert report["output_dir_exists"] is True
            assert report["warnings"] == []
            assert report["errors"] == []

    def test_validate_missing_data_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            # Pas de init() → pas de dossiers
            report = project.validate()
            assert report["valid"] is False
            assert len(report["errors"]) > 0

    def test_validate_missing_output_dir_is_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(path=tmpdir)
            os.makedirs(project.data_dir)
            report = project.validate()
            assert report["valid"] is True
            assert any("output" in w.lower() for w in report["warnings"])

    def test_validate_shapefile_missing_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            # .shp sans .shx ni .dbf
            _create_dummy_files(project.data_dir, ["carte.shp"])
            report = project.validate()
            sidecar_warnings = [w for w in report["warnings"] if "Sidecar" in w]
            assert len(sidecar_warnings) == 2  # .shx et .dbf manquants

    def test_validate_shapefile_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.shp", "carte.shx", "carte.dbf",
            ])
            report = project.validate()
            sidecar_warnings = [w for w in report["warnings"] if "Sidecar" in w]
            assert len(sidecar_warnings) == 0


class TestInfos:
    """Tests de infos()."""

    def test_infos_empty_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            info = project.infos()
            assert info["total_data_files"] == 0
            assert info["output_files"] == 0
            assert info["data_exists"] is True

    def test_infos_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.geojson", "dem.tif", "stats.csv",
            ])
            _create_dummy_files(project.output_dir, ["result.png"])
            info = project.infos()
            assert info["vector_files"] == 1
            assert info["raster_files"] == 1
            assert info["tabular_files"] == 1
            assert info["total_data_files"] == 3
            assert info["output_files"] == 1

    def test_infos_returns_crs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            info = project.infos()
            assert "4326" in info["crs"]


class TestOrganizeProject:
    """Tests de organize_project()."""

    def test_organize_moves_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.geojson", "dem.tif", "stats.csv",
            ])
            project.organize_project()
            assert "carte.geojson" in project.vector_files
            assert "dem.tif" in project.raster_files
            assert "stats.csv" in project.tabular_files

    def test_organize_creates_subdirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            project.organize_project()
            assert os.path.isdir(os.path.join(project.data_dir, "vector"))
            assert os.path.isdir(os.path.join(project.data_dir, "raster"))
            assert os.path.isdir(os.path.join(project.data_dir, "tabular"))


# ---------------------------------------------------------------------------
#  Tests des helpers module-level
# ---------------------------------------------------------------------------

class TestClassifyExtension:
    def test_vector(self):
        assert _classify_extension(".shp") == "vector"
        assert _classify_extension(".geojson") == "vector"

    def test_raster(self):
        assert _classify_extension(".tif") == "raster"

    def test_tabular(self):
        assert _classify_extension(".csv") == "tabular"

    def test_other(self):
        assert _classify_extension(".xyz") == "other"

    def test_case_insensitive(self):
        assert _classify_extension(".SHP") == "vector"


class TestGetSidecarsFor:
    def test_shp(self):
        assert _get_sidecars_for(".shp") == SHAPEFILE_SIDECARS

    def test_tab(self):
        assert _get_sidecars_for(".tab") == TAB_SIDECARS

    def test_other(self):
        assert _get_sidecars_for(".geojson") == set()


# ---------------------------------------------------------------------------
#  Tests de _resolve_data
# ---------------------------------------------------------------------------

class TestResolveData:
    def test_exact_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["points.geojson"])
            result = project._resolve_data("points.geojson")
            assert result.endswith("points.geojson")

    def test_basename_resolution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["points.geojson"])
            result = project._resolve_data("points")
            assert result.endswith("points.geojson")

    def test_recursive_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            sub = os.path.join(project.data_dir, "vector")
            os.makedirs(sub)
            _create_dummy_files(sub, ["carte.gpkg"])
            result = project._resolve_data("carte.gpkg")
            assert result.endswith("carte.gpkg")

    def test_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project._resolve_data("nope.shp")

    def test_ambiguous_strict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["data.csv", "data.geojson"])
            with pytest.raises(ValueError, match="ambigu"):
                project._resolve_data("data")

    def test_ambiguous_non_strict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["data.csv", "data.geojson"])
            result = project._resolve_data("data", strict=False)
            assert os.path.isfile(result)

    def test_ignores_sidecars(self):
        """Searching by basename should not match sidecar files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "rivers.shp", "rivers.shx", "rivers.dbf",
            ])
            result = project._resolve_data("rivers")
            assert result.endswith("rivers.shp")


# ---------------------------------------------------------------------------
#  Tests de list_datasets
# ---------------------------------------------------------------------------

class TestListDatasets:
    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            assert project.list_datasets() == []

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["points.geojson"])
            ds = project.list_datasets()
            assert len(ds) == 1
            assert ds[0]["name"] == "points"
            assert ds[0]["type"] == "vector"

    def test_shapefile_grouped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "rivers.shp", "rivers.shx", "rivers.dbf", "rivers.prj",
            ])
            ds = project.list_datasets()
            assert len(ds) == 1
            assert ds[0]["name"] == "rivers"
            assert len(ds[0]["sidecars"]) == 3  # .shx, .dbf, .prj

    def test_type_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.geojson", "dem.tif", "stats.csv",
            ])
            ds = project.list_datasets(type_filter="raster")
            assert len(ds) == 1
            assert ds[0]["name"] == "dem"

    def test_multiple_datasets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "carte.geojson", "dem.tif", "stats.csv",
            ])
            ds = project.list_datasets()
            assert len(ds) == 3


# ---------------------------------------------------------------------------
#  Tests de rename_data
# ---------------------------------------------------------------------------

class TestRenameData:
    def test_rename_simple_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["old.geojson"])
            pairs = project.rename_data("old.geojson", "new")
            assert len(pairs) == 1
            old_path, new_path = pairs[0]
            assert not os.path.isfile(old_path)
            assert os.path.isfile(new_path)
            assert new_path.endswith("new.geojson")

    def test_rename_shapefile_with_sidecars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "old.shp", "old.shx", "old.dbf", "old.prj",
            ])
            pairs = project.rename_data("old.shp", "new")
            assert len(pairs) == 4
            assert all(os.path.isfile(p[1]) for p in pairs)
            assert not any(os.path.isfile(p[0]) for p in pairs)

    def test_rename_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project.rename_data("nonexistent.shp", "new")

    def test_rename_by_basename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["cities.gpkg"])
            pairs = project.rename_data("cities", "towns")
            assert len(pairs) == 1
            assert pairs[0][1].endswith("towns.gpkg")


# ---------------------------------------------------------------------------
#  Tests de add_data amélioré (overwrite, mode, category)
# ---------------------------------------------------------------------------

class TestAddDataEnhanced:
    def test_overwrite_false_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "src.csv")
            with open(src, "w") as f:
                f.write("a,b")
            project.add_data(src)
            with pytest.raises(FileExistsError):
                project.add_data(src, overwrite=False)

    def test_overwrite_true_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "src.csv")
            with open(src, "w") as f:
                f.write("a,b")
            project.add_data(src)
            result = project.add_data(src, overwrite=True)
            assert os.path.isfile(result)

    def test_mode_move(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "moveme.csv")
            with open(src, "w") as f:
                f.write("x")
            result = project.add_data(src, mode="move")
            assert os.path.isfile(result)
            assert not os.path.isfile(src)

    def test_mode_invalid_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "test.csv")
            with open(src, "w") as f:
                f.write("x")
            with pytest.raises(ValueError, match="mode invalide"):
                project.add_data(src, mode="ftp")

    def test_category_creates_subdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            src = os.path.join(tmpdir, "points.geojson")
            with open(src, "w") as f:
                f.write("{}")
            result = project.add_data(src, category="vector")
            assert os.path.join("data", "vector") in result
            assert os.path.isfile(result)


# ---------------------------------------------------------------------------
#  Tests de save_output
# ---------------------------------------------------------------------------

class TestSaveOutput:
    def test_save_output_not_found_overwrite(self):
        """save_output raises FileExistsError when file exists and overwrite=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            # Create a dummy file in output
            out_file = os.path.join(project.output_dir, "result.csv")
            with open(out_file, "w") as f:
                f.write("a")
            # Mock-free: just test the guard
            import pandas as pd
            df = pd.DataFrame({"a": [1]})
            with pytest.raises(FileExistsError):
                project.save_output(df, "csv", filename="result", overwrite=False)


# ---------------------------------------------------------------------------
#  Tests de save_manifest / load_manifest
# ---------------------------------------------------------------------------

class TestManifest:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["a.geojson", "b.csv"])
            path = project.save_manifest()
            assert os.path.isfile(path)
            assert path.endswith("project.json")

            manifest = project.load_manifest()
            assert manifest["crs"] is not None
            assert len(manifest["datasets"]) == 2

    def test_load_manifest_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            with pytest.raises(FileNotFoundError):
                project.load_manifest()

    def test_manifest_contains_crs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            project.save_manifest()
            m = project.load_manifest()
            assert "4326" in m["crs"]

    def test_manifest_contains_created_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            project.save_manifest()
            m = project.load_manifest()
            assert "created_at" in m


# ---------------------------------------------------------------------------
#  Tests de validate amélioré (deep=True)
# ---------------------------------------------------------------------------

class TestValidateDeep:
    def test_validate_shallow_unchanged(self):
        """shallow validate (default) still works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            report = project.validate()
            assert report["valid"] is True

    def test_orphan_sidecar_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["lonely.shx", "lonely.dbf"])
            report = project.validate(deep=True)
            orphan_warnings = [w for w in report["warnings"] if "orphelin" in w]
            assert len(orphan_warnings) >= 2

    def test_ambiguous_basename_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, [
                "data.csv", "data.geojson",
            ])
            report = project.validate(deep=True)
            ambig_warnings = [w for w in report["warnings"] if "ambigu" in w.lower()]
            assert len(ambig_warnings) >= 1

    def test_deep_false_no_orphan_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _make_project(tmpdir)
            _create_dummy_files(project.data_dir, ["lonely.shx"])
            report = project.validate(deep=False)
            orphan_warnings = [w for w in report["warnings"] if "orphelin" in w]
            assert len(orphan_warnings) == 0
