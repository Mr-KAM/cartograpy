"""Tests pour le module processing."""

import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from cartograpy.processing import (
    centroids,
    join,
    fusion,
    add_column,
    split_multipolygon,
    VectorTools,
)


@pytest.fixture
def sample_gdf():
    """GeoDataFrame de test avec des polygones."""
    return gpd.GeoDataFrame(
        {
            "name": ["A", "B", "C"],
            "value": [10, 20, 30],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
                Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def sample_gdf_points():
    """GeoDataFrame de test avec des points."""
    return gpd.GeoDataFrame(
        {
            "name": ["P1", "P2", "P3"],
            "code": ["a", "b", "c"],
            "geometry": [Point(0.5, 0.5), Point(1.5, 0.5), Point(2.5, 0.5)],
        },
        crs="EPSG:4326",
    )


class TestCentroids:
    """Tests de la fonction centroids."""

    def test_returns_geodataframe(self, sample_gdf):
        result = centroids(sample_gdf)
        assert isinstance(result, gpd.GeoDataFrame)

    def test_preserves_crs(self, sample_gdf):
        result = centroids(sample_gdf)
        assert result.crs == sample_gdf.crs

    def test_preserves_columns(self, sample_gdf):
        result = centroids(sample_gdf)
        assert "name" in result.columns
        assert "value" in result.columns

    def test_centroids_are_points(self, sample_gdf):
        result = centroids(sample_gdf)
        for geom in result.geometry:
            assert geom.geom_type == "Point"

    def test_same_row_count(self, sample_gdf):
        result = centroids(sample_gdf)
        assert len(result) == len(sample_gdf)

    def test_no_geometry_raises(self):
        df = pd.DataFrame({"name": ["A"]})
        gdf = gpd.GeoDataFrame(df)
        with pytest.raises(ValueError):
            centroids(gdf)


class TestJoin:
    """Tests de la fonction join."""

    def test_basic_join(self, sample_gdf):
        target = gpd.GeoDataFrame(
            {"code": ["A", "B", "C"], "pop": [100, 200, 300]},
            geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
            crs="EPSG:4326",
        )
        result = join(
            (sample_gdf, "name"),
            (target, "code"),
            columns_to_join=["pop"],
        )
        assert isinstance(result, gpd.GeoDataFrame)
        assert "pop" in result.columns

    def test_join_preserves_crs(self, sample_gdf):
        target = gpd.GeoDataFrame(
            {"code": ["A", "B", "C"], "pop": [100, 200, 300]},
            geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
            crs="EPSG:4326",
        )
        result = join(
            (sample_gdf, "name"),
            (target, "code"),
            columns_to_join=["pop"],
        )
        assert result.crs is not None

    def test_join_invalid_column_source(self, sample_gdf, sample_gdf_points):
        with pytest.raises(ValueError):
            join(
                (sample_gdf, "nonexistent"),
                (sample_gdf_points, "code"),
            )

    def test_join_invalid_column_target(self, sample_gdf, sample_gdf_points):
        with pytest.raises(ValueError):
            join(
                (sample_gdf, "name"),
                (sample_gdf_points, "nonexistent"),
            )

    def test_join_not_geodataframe(self):
        df = pd.DataFrame({"a": [1]})
        gdf = gpd.GeoDataFrame(
            {"b": [1], "geometry": [Point(0, 0)]}, crs="EPSG:4326"
        )
        with pytest.raises(TypeError):
            join((df, "a"), (gdf, "b"))


class TestFusion:
    """Tests de la fonction fusion."""

    def test_fusion_geodataframes(self, sample_gdf):
        gdf2 = sample_gdf.copy()
        gdf2["name"] = ["D", "E", "F"]
        result = fusion([sample_gdf, gdf2])
        assert len(result) == 6

    def test_fusion_dataframes(self):
        df1 = pd.DataFrame({"a": [1, 2]})
        df2 = pd.DataFrame({"a": [3, 4]})
        result = fusion([df1, df2])
        assert len(result) == 4
        assert list(result["a"]) == [1, 2, 3, 4]

    def test_fusion_reset_index(self, sample_gdf):
        gdf2 = sample_gdf.copy()
        result = fusion([sample_gdf, gdf2], reset_index=True)
        assert list(result.index) == list(range(len(result)))

    def test_fusion_crs_conflict(self):
        gdf1 = gpd.GeoDataFrame(
            {"geometry": [Point(0, 0)]}, crs="EPSG:4326"
        )
        gdf2 = gpd.GeoDataFrame(
            {"geometry": [Point(0, 0)]}, crs="EPSG:3857"
        )
        with pytest.raises(ValueError):
            fusion([gdf1, gdf2], ignore_crs=False)

    def test_fusion_ignore_crs(self):
        gdf1 = gpd.GeoDataFrame(
            {"geometry": [Point(0, 0)]}, crs="EPSG:4326"
        )
        gdf2 = gpd.GeoDataFrame(
            {"geometry": [Point(0, 0)]}, crs="EPSG:4326"
        )
        # Same CRS fusion should work
        result = fusion([gdf1, gdf2], ignore_crs=True)
        assert len(result) == 2


class TestAddColumn:
    """Tests de la fonction add_column."""

    def test_callable_expression(self, sample_gdf):
        result = add_column(sample_gdf.copy(), "double", lambda row: row["value"] * 2)
        assert "double" in result.columns
        assert list(result["double"]) == [20, 40, 60]

    def test_string_expression(self, sample_gdf):
        result = add_column(sample_gdf.copy(), "incremented", "value + 1")
        assert "incremented" in result.columns
        assert list(result["incremented"]) == [11, 21, 31]

    def test_invalid_expression_type(self, sample_gdf):
        with pytest.raises(TypeError):
            add_column(sample_gdf, "bad", 42)


class TestSplitMultipolygon:
    """Tests de la fonction split_multipolygon."""

    def test_split_multipolygon_geometry(self):
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        poly2 = Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])
        mp = MultiPolygon([poly1, poly2])
        result = split_multipolygon(mp)
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 2

    def test_split_from_gdf(self):
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        poly2 = Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])
        mp = MultiPolygon([poly1, poly2])
        gdf = gpd.GeoDataFrame({"name": ["test"], "geometry": [mp]}, crs="EPSG:4326")
        result = split_multipolygon(gdf)
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 2


class TestVectorTools:
    """Tests de la classe VectorTools."""

    def test_init(self, sample_gdf):
        vt = VectorTools(sample_gdf)
        assert isinstance(vt.gdf, gpd.GeoDataFrame)

    def test_init_not_geodataframe(self):
        with pytest.raises(TypeError):
            VectorTools(pd.DataFrame({"a": [1]}))

    def test_validity(self, sample_gdf):
        vt = VectorTools(sample_gdf)
        result = vt.validity()
        assert isinstance(result, pd.Series)
        assert all(result)

    def test_fix_invalid(self, sample_gdf):
        vt = VectorTools(sample_gdf)
        result = vt.fix_invalid()
        assert isinstance(result, VectorTools)
        assert len(result.gdf) == len(sample_gdf)

    def test_remove_empty(self, sample_gdf):
        vt = VectorTools(sample_gdf)
        result = vt.remove_empty()
        assert isinstance(result, VectorTools)

    def test_drop_duplicates(self, sample_gdf):
        gdf = pd.concat([sample_gdf, sample_gdf]).reset_index(drop=True)
        gdf = gpd.GeoDataFrame(gdf, crs="EPSG:4326")
        vt = VectorTools(gdf)
        result = vt.drop_duplicates()
        assert len(result.gdf) == 3

    def test_chaining(self, sample_gdf):
        result = (
            VectorTools(sample_gdf)
            .fix_invalid()
            .remove_empty()
            .gdf
        )
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 3

    def test_duplicates(self, sample_gdf):
        gdf = pd.concat([sample_gdf, sample_gdf]).reset_index(drop=True)
        gdf = gpd.GeoDataFrame(gdf, crs="EPSG:4326")
        vt = VectorTools(gdf)
        dups = vt.duplicates()
        assert len(dups) == 6  # all are duplicates


class TestSmartCRS:
    """Tests for CRS-aware measurements (crs_info, estimate_utm, unit-aware buffer/area/distance)."""

    def test_crs_info_geographic(self, sample_gdf):
        info = VectorTools(sample_gdf).crs_info()
        assert info["is_geographic"] is True
        assert info["epsg"] == 4326

    def test_crs_info_no_crs(self, sample_gdf):
        gdf = sample_gdf.copy()
        gdf.crs = None
        info = VectorTools(gdf).crs_info()
        assert info == {"epsg": None, "name": None, "is_geographic": None, "unit": None}

    def test_estimate_utm_is_projected(self, sample_gdf):
        utm_crs = VectorTools(sample_gdf).estimate_utm()
        assert not utm_crs.is_geographic

    def test_to_local_crs_reprojects(self, sample_gdf):
        result = VectorTools(sample_gdf).to_local_crs()
        assert not result.gdf.crs.is_geographic

    def test_buffer_invalid_unit(self, sample_gdf):
        with pytest.raises(ValueError):
            VectorTools(sample_gdf).buffer(10, unit="miles")

    def test_buffer_auto_project_vs_raw_degrees(self, sample_gdf):
        vt = VectorTools(sample_gdf)
        original_area = sample_gdf.geometry.iloc[0].area
        raw_area = vt.buffer(0.1, auto_project=False).gdf.geometry.iloc[0].area
        meter_buffered_area = vt.buffer(
            0.1, unit="m", auto_project=True
        ).gdf.geometry.iloc[0].area
        # A 0.1-degree buffer (~11 km) inflates the area far more than a
        # 0.1-meter one, once both are measured back in the same (degree) CRS.
        assert (raw_area - original_area) > (meter_buffered_area - original_area)
        assert meter_buffered_area == pytest.approx(original_area, rel=1e-2)
        assert vt.buffer(1, auto_project=True).gdf.crs == sample_gdf.crs

    def test_area_unit_conversion(self, sample_gdf):
        vt = VectorTools(sample_gdf)
        area_m2 = vt.area(unit="m2").gdf["area"].iloc[0]
        area_ha = vt.area(unit="ha").gdf["area"].iloc[0]
        assert area_ha == pytest.approx(area_m2 / 10_000)

    def test_area_invalid_unit(self, sample_gdf):
        with pytest.raises(ValueError):
            VectorTools(sample_gdf).area(unit="acres")

    def test_distance_to_nearest_unit_conversion(self):
        pts_a = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
        pts_b = gpd.GeoDataFrame(geometry=[Point(0.01, 0)], crs="EPSG:4326")
        vt = VectorTools(pts_a)
        meters = vt.distance_to_nearest(pts_b, unit="m").gdf["dist_nearest"].iloc[0]
        km = vt.distance_to_nearest(pts_b, unit="km").gdf["dist_nearest"].iloc[0]
        assert meters > 0
        assert km * 1000 == pytest.approx(meters)
