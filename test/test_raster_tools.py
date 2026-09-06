"""Tests unitaires pour RasterTools."""
import pytest
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box
import os
import tempfile

from cartograpy.processing import RasterTools


# ── Helpers ────────────────────────────────────────────────────────

def _make_raster(data=None, nodata=-9999, crs="EPSG:4326"):
    """Crée un RasterTools en mémoire pour les tests."""
    if data is None:
        data = np.array([
            [10, 20, 30, 40],
            [50, 60, 70, 80],
            [90, 100, 110, 120],
        ], dtype="float64")
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    h, w = data.shape[1], data.shape[2]
    transform = from_bounds(0, 0, w * 10, h * 10, w, h)
    profile = {
        "driver": "GTiff",
        "dtype": str(data.dtype),
        "width": w,
        "height": h,
        "count": data.shape[0],
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    return RasterTools((data, profile))


def _make_dem():
    """Crée un petit MNT synthétique."""
    dem = np.array([
        [100, 95, 90, 85],
        [80, 70, 60, 50],
        [60, 45, 30, 20],
    ], dtype="float64")
    return _make_raster(dem, nodata=-9999)


def _make_multiband():
    """Crée un raster multi-bande (4 bandes, simule R/G/B/NIR)."""
    np.random.seed(42)
    data = np.random.randint(0, 255, (4, 3, 4)).astype("float64")
    return _make_raster(data)


# ── 1. Prétraitements ─────────────────────────────────────────────

class TestRasterInit:
    def test_from_tuple(self):
        rt = _make_raster()
        assert rt.data is not None
        assert rt.profile is not None

    def test_from_file(self):
        rt = _make_raster()
        path = rt._write_tmp()
        try:
            rt2 = RasterTools(path)
            assert rt2.data.shape == rt.data.shape
        finally:
            os.remove(path)

    def test_invalid_source(self):
        try:
            RasterTools(42)
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_repr(self):
        rt = _make_raster()
        assert "RasterTools" in repr(rt)

    def test_len(self):
        rt = _make_raster()
        assert len(rt) == 1


class TestRasterValidation:
    def test_get_raster_info(self):
        rt = _make_raster()
        info = rt.get_raster_info()
        assert info["width"] == 4
        assert info["height"] == 3
        assert info["count"] == 1
        assert info["nodata"] == -9999

    def test_check_raster_metadata_valid(self):
        rt = _make_raster()
        result = rt.check_raster_metadata()
        assert result["valid"]
        assert len(result["issues"]) == 0

    def test_check_raster_metadata_no_crs(self):
        rt = _make_raster(crs=None)
        result = rt.check_raster_metadata()
        assert not result["valid"]
        assert any("CRS" in i for i in result["issues"])

    def test_validate_raster(self):
        rt = _make_raster()
        assert rt.validate_raster()

    def test_check_nodata(self):
        data = np.array([[10, -9999, 30, 40],
                         [50, 60, -9999, 80],
                         [90, 100, 110, 120]], dtype="float64")
        rt = _make_raster(data, nodata=-9999)
        result = rt.check_nodata()
        assert result["nodata_value"] == -9999
        assert result["nodata_count"] == 2

    def test_check_band_count(self):
        rt = _make_multiband()
        assert rt.check_band_count() == 4

    def test_check_resolution(self):
        rt = _make_raster()
        res = rt.check_resolution()
        assert res[0] is not None
        assert res[1] is not None
        assert res[0] > 0 and res[1] > 0

    def test_check_alignment_same(self):
        rt1 = _make_raster()
        rt2 = _make_raster()
        result = rt1.check_alignment(rt2)
        assert result["compatible"]


class TestRasterHarmonisation:
    def test_set_crs(self):
        rt = _make_raster()
        rt2 = rt.set_crs("EPSG:32630")
        assert "32630" in str(rt2.profile["crs"])

    def test_reproject_raster(self):
        rt = _make_raster()
        rt2 = rt.reproject_raster("EPSG:3857")
        assert "3857" in str(rt2.profile["crs"])

    def test_resample_raster(self):
        rt = _make_raster()
        original_res = rt.check_resolution()
        rt2 = rt.resample_raster(original_res[0] * 2)
        new_res = rt2.check_resolution()
        assert new_res[0] == pytest.approx(original_res[0] * 2)
        assert rt2.profile["width"] != rt.profile["width"] or rt2.profile["height"] != rt.profile["height"]

    def test_align_rasters(self):
        rt1 = _make_raster()
        rt2 = _make_raster()
        aligned = rt1.align_rasters(rt2)
        assert aligned.data.shape[1] == rt2.profile["height"]
        assert aligned.data.shape[2] == rt2.profile["width"]


class TestRasterClipping:
    def test_crop_raster(self):
        rt = _make_raster()
        bounds = rasterio.transform.array_bounds(
            rt.profile["height"], rt.profile["width"], rt.profile["transform"]
        )
        cropped = rt.crop_raster(bounds)
        assert cropped.data is not None

    def test_clip_raster_with_geodf(self):
        rt = _make_raster()
        bounds = rasterio.transform.array_bounds(
            rt.profile["height"], rt.profile["width"], rt.profile["transform"]
        )
        gdf = gpd.GeoDataFrame(geometry=[box(*bounds)], crs="EPSG:4326")
        clipped = rt.clip_raster(gdf)
        assert clipped.data.size > 0

    def test_mask_raster(self):
        rt = _make_raster()
        bounds = rasterio.transform.array_bounds(
            rt.profile["height"], rt.profile["width"], rt.profile["transform"]
        )
        gdf = gpd.GeoDataFrame(geometry=[box(*bounds)], crs="EPSG:4326")
        masked = rt.mask_raster(gdf)
        assert masked.data.shape == rt.data.shape


class TestRasterCleaning:
    def test_replace_nodata(self):
        data = np.array([[10, -9999, 30],
                         [40, 50, -9999]], dtype="float64")
        rt = _make_raster(data, nodata=-9999)
        rt2 = rt.replace_nodata(-9999, 0)
        assert rt2.profile["nodata"] == 0
        assert np.sum(rt2.data == -9999) == 0

    def test_fill_nodata(self):
        data = np.array([[10, -9999, 30],
                         [40, 50, 60]], dtype="float64")
        rt = _make_raster(data, nodata=-9999)
        rt2 = rt.fill_nodata()
        assert rt2.data is not None

    def test_scale_raster_values(self):
        rt = _make_raster()
        rt2 = rt.scale_raster_values(factor=2, offset=5)
        np.testing.assert_allclose(rt2.data, rt.data * 2 + 5)

    def test_convert_dtype(self):
        rt = _make_raster()
        rt2 = rt.convert_dtype("float32")
        assert rt2.data.dtype == np.float32

    def test_normalize_raster(self):
        rt = _make_raster()
        rt2 = rt.normalize_raster()
        valid = rt2.data[rt2.data != rt2.profile.get("nodata")]
        assert valid.min() >= 0.0
        assert valid.max() <= 1.0


# ── 2. Traitements et analyses ────────────────────────────────────

class TestRasterCalculator:
    def test_raster_calculator(self):
        rt = _make_multiband()
        result = rt.raster_calculator("(B4 - B1) / (B4 + B1 + 1e-10)")
        assert result.data.shape[0] == 1

    def test_ndvi(self):
        data = np.array([
            [[100, 200], [150, 250]],
            [[200, 300], [250, 350]],
        ], dtype="float64")
        rt = _make_raster(data)
        ndvi = rt.ndvi(red_band=0, nir_band=1)
        assert ndvi.data.shape[0] == 1
        assert ndvi.data.min() >= -1
        assert ndvi.data.max() <= 1

    def test_ndwi(self):
        rt = _make_multiband()
        ndwi = rt.ndwi(green_band=1, nir_band=3)
        assert ndwi.data.shape[0] == 1

    def test_ndbi(self):
        rt = _make_multiband()
        ndbi = rt.ndbi(swir_band=2, nir_band=3)
        assert ndbi.data.shape[0] == 1

    def test_spectral_index(self):
        rt = _make_multiband()
        idx = rt.spectral_index(0, 1)
        assert idx.data.shape[0] == 1


class TestRasterReclassify:
    def test_reclassify_with_rules(self):
        rt = _make_raster()
        result = rt.reclassify_raster([(0, 50, 1), (50, 100, 2), (100, 200, 3)])
        unique = np.unique(result.data[result.data != result.profile.get("nodata")])
        assert set(unique).issubset({1, 2, 3})

    def test_reclassify_with_dict(self):
        data = np.array([[1, 2, 3], [1, 2, 3]], dtype="float64")
        rt = _make_raster(data)
        result = rt.reclassify_raster({1: 10, 2: 20, 3: 30})
        assert 10 in result.data
        assert 20 in result.data

    def test_threshold_raster(self):
        rt = _make_raster()
        result = rt.threshold_raster(60)
        unique = np.unique(result.data)
        assert set(unique).issubset({0, 1})


class TestRasterStatistics:
    def test_raster_statistics(self):
        rt = _make_raster()
        stats = rt.raster_statistics()
        assert stats["min"] == 10
        assert stats["max"] == 120
        assert stats["mean"] is not None
        assert stats["valid_pixels"] == 12

    def test_band_statistics(self):
        rt = _make_multiband()
        stats = rt.band_statistics()
        assert len(stats) == 4

    def test_histogram_raster(self):
        rt = _make_raster()
        hist = rt.histogram_raster(bins=10)
        assert "counts" in hist
        assert "edges" in hist

    def test_class_areas(self):
        data = np.array([[1, 1, 2, 2], [1, 2, 2, 3], [3, 3, -9999, 3]], dtype="float64")
        rt = _make_raster(data, crs="EPSG:32630")  # pixels de 10 m -> 100 m2
        df = rt.class_areas(unit="m2")
        by_class = dict(zip(df["class"], df["area"]))
        assert by_class[1] == 300.0 and by_class[2] == 400.0 and by_class[3] == 400.0
        assert -9999 not in by_class  # nodata exclu
        assert abs(df["percent"].sum() - 100.0) < 1e-6

    def test_class_areas_geographic_rejects_metric(self):
        rt = _make_raster(np.array([[1, 2], [2, 1]], dtype="float64"))  # EPSG:4326
        with pytest.raises(ValueError):
            rt.class_areas(unit="ha")
        assert rt.class_areas(unit="pixel")["area"].sum() == 4

    def test_zonal_statistics(self):
        rt = _make_raster()
        bounds = rasterio.transform.array_bounds(
            rt.profile["height"], rt.profile["width"], rt.profile["transform"]
        )
        gdf = gpd.GeoDataFrame(geometry=[box(*bounds)], crs="EPSG:4326")
        result = rt.zonal_statistics(gdf, stats=["mean", "count"])
        assert "mean" in result.columns
        assert "count" in result.columns


class TestFocalAnalysis:
    def test_focal_mean(self):
        rt = _make_raster()
        result = rt.focal_mean(size=3)
        assert result.data.shape == rt.data.shape

    def test_focal_median(self):
        rt = _make_raster()
        result = rt.focal_median(size=3)
        assert result.data.shape == rt.data.shape

    def test_focal_max(self):
        rt = _make_raster()
        result = rt.focal_max(size=3)
        assert result.data.shape == rt.data.shape

    def test_focal_min(self):
        rt = _make_raster()
        result = rt.focal_min(size=3)
        assert result.data.shape == rt.data.shape


class TestTerrainAnalysis:
    def test_compute_slope(self):
        rt = _make_dem()
        slope = rt.compute_slope()
        assert slope.data.shape[0] == 1
        assert slope.data.min() >= 0

    def test_compute_aspect(self):
        rt = _make_dem()
        aspect = rt.compute_aspect()
        assert aspect.data.shape[0] == 1

    def test_compute_hillshade(self):
        rt = _make_dem()
        hs = rt.compute_hillshade()
        assert hs.data.shape[0] == 1
        assert hs.data.max() <= 255

    def test_compute_curvature(self):
        rt = _make_dem()
        curv = rt.compute_curvature()
        assert curv.data.shape[0] == 1

    def test_compute_tpi(self):
        rt = _make_dem()
        tpi = rt.compute_tpi()
        assert tpi.data.shape[0] == 1

    def test_compute_tri(self):
        rt = _make_dem()
        tri = rt.compute_tri()
        assert tri.data.shape[0] == 1

    def test_flow_direction(self):
        rt = _make_dem()
        fdir = rt.flow_direction()
        assert fdir.data.shape[0] == 1
        assert fdir.data.dtype == np.int32


class TestChangeDetection:
    def test_change_detection(self):
        rt1 = _make_raster()
        data2 = rt1.data.copy() + 10
        rt2 = _make_raster(data2[0])
        diff = rt1.change_detection(rt2)
        assert diff.data.shape[0] == 1

    def test_post_classification_comparison(self):
        data1 = np.array([[1, 2], [3, 1]], dtype="float64")
        data2 = np.array([[1, 3], [2, 1]], dtype="float64")
        rt1 = _make_raster(data1)
        rt2 = _make_raster(data2)
        result = rt1.post_classification_comparison(rt2)
        # pixel (0,1): data1=2, data2=3 -> 2*100+3 = 203
        assert 203 in result.data


class TestWeightedOverlay:
    def test_weighted_overlay(self):
        rt1 = _make_raster()
        rt2 = _make_raster()
        result = rt1.weighted_overlay([rt2], [0.6, 0.4])
        assert result.data.shape[0] == 1

    def test_normalize_criteria(self):
        rt = _make_raster()
        normalized = rt.normalize_criteria(method="minmax")
        valid = normalized.data[normalized.data != rt.profile.get("nodata")]
        assert valid.min() >= 0
        assert valid.max() <= 1.0


# ── 3. Post-traitements ──────────────────────────────────────────

class TestPostProcessing:
    def test_remove_small_patches(self):
        data = np.array([[1, 1, 2, 2],
                         [1, 1, 2, 2],
                         [3, 1, 1, 2]], dtype="float64")
        rt = _make_raster(data, nodata=0)
        result = rt.remove_small_patches(min_size=2)
        assert result.data is not None

    def test_sieve_raster(self):
        data = np.array([[1, 1, 2, 2],
                         [1, 1, 2, 2],
                         [3, 1, 1, 2]], dtype="float64")
        rt = _make_raster(data)
        result = rt.sieve_raster(threshold=2)
        assert result.data is not None


class TestRasterVectorConversion:
    def test_polygonize_raster(self):
        data = np.array([[1, 1, 2, 2],
                         [1, 1, 2, 2],
                         [3, 3, 2, 2]], dtype="float64")
        rt = _make_raster(data)
        gdf = rt.polygonize_raster()
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0
        assert "value" in gdf.columns

    def test_raster_to_points(self):
        rt = _make_raster()
        gdf = rt.raster_to_points()
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) == 12  # 3x4 = 12 pixels

    def test_contours_from_raster(self):
        rt = _make_dem()
        gdf = rt.contours_from_raster(levels=5)
        assert isinstance(gdf, gpd.GeoDataFrame)


class TestRasterExport:
    def test_export_geotiff(self):
        rt = _make_raster()
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            path = f.name
        try:
            rt.export_geotiff(path)
            assert os.path.exists(path)
            with rasterio.open(path) as src:
                assert src.count == 1
                assert src.width == 4
                assert src.height == 3
        finally:
            os.remove(path)

    def test_export_cog(self):
        # Use a larger raster so overviews can be built
        data = np.random.default_rng(0).random((1, 64, 64)).astype("float64")
        rt = _make_raster(data[0])
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
            path = f.name
        try:
            rt.export_cog(path)
            assert os.path.exists(path)
        finally:
            os.remove(path)

    def test_export_ascii_grid(self):
        rt = _make_raster()
        with tempfile.NamedTemporaryFile(suffix=".asc", delete=False) as f:
            path = f.name
        try:
            rt.export_ascii_grid(path)
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert "ncols" in content
            assert "nrows" in content
        finally:
            os.remove(path)

    def test_export_png_map(self):
        rt = _make_raster()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            rt.export_png_map(path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.remove(path)


class TestRasterColormap:
    def test_apply_colormap(self):
        rt = _make_raster()
        rgb = rt.apply_colormap("viridis")
        assert rgb.data.shape[0] == 3
        assert rgb.data.dtype == np.uint8

    def test_stretch_contrast(self):
        rt = _make_raster()
        result = rt.stretch_contrast()
        assert result.data.shape[0] == 1


class TestBandOperations:
    def test_band_selection(self):
        rt = _make_multiband()
        result = rt.band_selection([0, 2])
        assert result.data.shape[0] == 2

    def test_band_stacking(self):
        rt1 = _make_raster()
        rt2 = _make_raster()
        stacked = rt1.band_stacking([rt2])
        assert stacked.data.shape[0] == 2

    def test_cloud_masking(self):
        data = np.zeros((2, 3, 4), dtype="float64")
        data[0] = 100  # bande données
        data[1] = np.array([[0, 0, 1, 1],
                            [0, 1, 0, 0],
                            [0, 0, 0, 1]])  # bande QA nuage
        rt = _make_raster(data)
        result = rt.cloud_masking(cloud_band_index=1, cloud_values=[1])
        assert result.data is not None
