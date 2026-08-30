"""Tests pour le module mapper.hexgrid."""

import numpy as np
import pytest
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for testing

from cartograpy.mapper import make_hex_grid, aggregate_to_hex, plot_hexgrid_choropleth


@pytest.fixture
def sample_points():
    rng = np.random.default_rng(0)
    n = 500
    xs = rng.uniform(0, 2000, n)
    ys = rng.uniform(0, 2000, n)
    return gpd.GeoDataFrame(
        {"value": rng.normal(50, 15, n)},
        geometry=gpd.points_from_xy(xs, ys),
        crs="EPSG:32630",
    )


class TestMakeHexGrid:
    def test_from_gdf(self, sample_points):
        grid = make_hex_grid(sample_points, hex_size=250)
        assert {"cell_id", "geometry"}.issubset(grid.columns)
        assert len(grid) > 0
        assert grid.crs == sample_points.crs

    def test_from_bounds_requires_crs(self, sample_points):
        with pytest.raises(ValueError):
            make_hex_grid(sample_points.total_bounds, hex_size=250)

    def test_from_bounds(self, sample_points):
        grid = make_hex_grid(sample_points.total_bounds, hex_size=250, crs="EPSG:32630")
        assert len(grid) > 0

    def test_gdf_without_crs_raises(self, sample_points):
        with pytest.raises(ValueError):
            make_hex_grid(sample_points.set_crs(None, allow_override=True), hex_size=250)


class TestAggregateToHex:
    def test_aggregate_counts_and_means(self, sample_points):
        grid = make_hex_grid(sample_points, hex_size=250)
        result = aggregate_to_hex(sample_points, grid, value_cols=["value"])
        assert "value" in result.columns
        assert "n_points" in result.columns
        assert result["n_points"].sum() == len(sample_points)
        assert len(result) == len(grid)


class TestPlotHexgridChoropleth:
    def test_returns_fig_ax(self, sample_points):
        grid = make_hex_grid(sample_points, hex_size=250)
        hex_data = aggregate_to_hex(sample_points, grid, value_cols=["value"])
        fig, ax = plot_hexgrid_choropleth(hex_data, "value", show_colorbar=False)
        assert fig is not None
        assert ax is not None

    def test_min_count_filters(self, sample_points):
        grid = make_hex_grid(sample_points, hex_size=250)
        hex_data = aggregate_to_hex(sample_points, grid, value_cols=["value"])
        fig, ax = plot_hexgrid_choropleth(
            hex_data, "value", min_count=hex_data["n_points"].max() + 1, show_colorbar=False,
        )
        assert len(ax.collections) == 0 or all(c.get_paths() == [] for c in ax.collections)


class TestMapIntegration:
    """Map.add_hexgrid() / Map.add_bivariate() délèguent aux modules et
    dessinent sur l'axe de la carte."""

    def test_add_hexgrid_aggregates_and_draws(self, sample_points):
        from cartograpy.mapper import Map

        m = Map(title="hex", basemap=False, verbose=False)
        n_before = len(m.ax.collections)
        out = m.add_hexgrid(sample_points, "value", hex_size=250, show_colorbar=False)
        assert out is m                                   # chaînable
        assert len(m.ax.collections) > n_before           # quelque chose est tracé
        assert "value" in m.last_hexgrid.columns
        assert m.layers[-1]["type"] == "hexgrid"

    def test_add_bivariate_draws_and_stores_classes(self):
        from shapely.geometry import box
        from cartograpy.mapper import Map

        polys = gpd.GeoDataFrame(
            {"v1": [1, 2, 3, 4, 5, 6, 7, 8, 9],
             "v2": [9, 1, 5, 2, 8, 4, 6, 3, 7]},
            geometry=[box(i, j, i + 1, j + 1) for i in range(3) for j in range(3)],
            crs="EPSG:4326",
        )
        m = Map(title="bi", basemap=False, verbose=False)
        out = m.add_bivariate(polys, "v1", "v2", n_classes=3)
        assert out is m
        assert {"bi_class", "bi_color"}.issubset(m.last_bivariate.columns)
        assert m.layers[-1]["type"] == "bivariate"

    def test_replayed_after_ax_clear(self, sample_points):
        """set_paper/set_projection font ax.clear() : la couche hexbin doit
        être re-tracée par _render() via sa closure de rejeu."""
        from cartograpy.mapper import Map

        m = Map(title="hex", basemap=False, verbose=False)
        m.add_hexgrid(sample_points, "value", hex_size=250, show_colorbar=False)
        m._invalidate_render()
        assert all(not lyr["rendered"] for lyr in m.layers)
        assert len(m.ax.collections) == 0
        m._render(legend=False)
        assert len(m.ax.collections) > 0
        assert m.layers[-1]["rendered"] is True
