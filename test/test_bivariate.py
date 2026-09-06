"""Tests pour le module mapper.bivariate."""

import numpy as np
import pytest
import geopandas as gpd
from shapely.geometry import box
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for testing

from cartograpy.mapper import (  # noqa: E402
    plot_bivariate_choropleth,
    plot_bivariate_legend,
    assign_bivariate_classes,
    classify_variable,
    get_bivariate_palette,
    generate_bivariate_palette,
    list_bivariate_palettes,
    BIVARIATE_PALETTES,
)


@pytest.fixture
def sample_gdf():
    rng = np.random.default_rng(0)
    geoms = [box(c, r, c + 1, r + 1) for r in range(4) for c in range(4)]
    n = len(geoms)
    return gpd.GeoDataFrame(
        {"var1": rng.normal(50, 15, n), "var2": rng.normal(60, 20, n)},
        geometry=geoms,
    )


class TestListAndGetPalette:
    def test_list_bivariate_palettes(self):
        names = list_bivariate_palettes()
        assert "blue_pink" in names
        assert names == list(BIVARIATE_PALETTES.keys())

    def test_get_named_palette_default_size(self):
        grid = get_bivariate_palette("blue_pink")
        assert grid.shape == (3, 3, 3)
        assert grid.min() >= 0 and grid.max() <= 1

    def test_get_unknown_palette_raises(self):
        with pytest.raises(ValueError):
            get_bivariate_palette("does-not-exist")

    def test_get_named_palette_interpolated(self):
        grid = get_bivariate_palette("blue_pink", n_classes=5)
        assert grid.shape == (5, 5, 3)

    def test_get_custom_flat_hex_palette(self):
        colors = ["#ffffff", "#888888", "#000000", "#ff0000"]
        grid = get_bivariate_palette(colors, n_classes=2)
        assert grid.shape == (2, 2, 3)
        assert grid[0, 0] == pytest.approx((1, 1, 1))

    def test_get_custom_flat_palette_wrong_length_raises(self):
        with pytest.raises(ValueError):
            get_bivariate_palette(["#fff", "#000"], n_classes=3)

    def test_get_custom_grid_wrong_shape_raises(self):
        with pytest.raises(ValueError):
            get_bivariate_palette(np.zeros((2, 2, 3)), n_classes=3)


class TestGenerateBivariatePalette:
    def test_shape(self):
        grid = generate_bivariate_palette("Blues", "Reds", n_classes=4)
        assert grid.shape == (4, 4, 3)
        assert grid.min() >= 0 and grid.max() <= 1

    def test_low_low_corner_is_light(self):
        # Deux colormaps séquentiels commencent clairs -> le coin où les
        # deux variables sont basses doit rester clair après le blend.
        grid = generate_bivariate_palette("Blues", "Reds", n_classes=3)
        assert grid[0, 0].mean() > 0.8

    def test_multiply_high_high_is_darker_than_screen(self):
        g_mult = generate_bivariate_palette("Blues", "Reds", blend="multiply")
        g_screen = generate_bivariate_palette("Blues", "Reds", blend="screen")
        assert g_mult[-1, -1].mean() < g_screen[-1, -1].mean()

    def test_mean_blend_is_average(self):
        ramp_grid = generate_bivariate_palette(
            ["#000000", "#000000"], ["#ffffff", "#ffffff"], n_classes=2, blend="mean",
        )
        assert ramp_grid[0, 0] == pytest.approx((0.5, 0.5, 0.5))

    def test_custom_gradient_colors(self):
        grid = generate_bivariate_palette(
            ["#f7fbff", "#08306b"], ["#fff5f0", "#67000d"], n_classes=3,
        )
        assert grid.shape == (3, 3, 3)

    def test_invalid_blend_raises(self):
        with pytest.raises(ValueError):
            generate_bivariate_palette("Blues", "Reds", blend="nonsense")

    def test_invalid_ramp_type_raises(self):
        with pytest.raises(TypeError):
            generate_bivariate_palette(42, "Reds")

    def test_single_color_ramp_raises(self):
        with pytest.raises(ValueError):
            generate_bivariate_palette(["#ffffff"], "Reds")

    def test_output_usable_as_palette_param(self, sample_gdf):
        import matplotlib.pyplot as plt

        grid = generate_bivariate_palette("Blues", "Reds")
        fig, ax, gdf_bi = plot_bivariate_choropleth(sample_gdf, "var1", "var2", palette=grid)
        assert "bi_color" in gdf_bi.columns
        plt.close(fig)


class TestClassifyVariable:
    def test_quantiles_default(self, sample_gdf):
        classes = classify_variable(sample_gdf["var1"], n_classes=3)
        assert set(classes.unique()) <= {1, 2, 3}

    def test_equal_method(self, sample_gdf):
        classes = classify_variable(sample_gdf["var1"], n_classes=3, method="equal")
        assert set(classes.unique()) <= {1, 2, 3}

    def test_invalid_method_raises(self, sample_gdf):
        with pytest.raises(ValueError):
            classify_variable(sample_gdf["var1"], method="bogus")


class TestAssignBivariateClasses:
    def test_adds_expected_columns(self, sample_gdf):
        gdf_bi, grid = assign_bivariate_classes(sample_gdf, "var1", "var2")
        for col in ("var1_class", "var2_class", "bi_class", "bi_color"):
            assert col in gdf_bi.columns
        assert grid.shape == (3, 3, 3)

    def test_bi_class_matches_component_classes(self, sample_gdf):
        gdf_bi, _ = assign_bivariate_classes(sample_gdf, "var1", "var2")
        expected = gdf_bi["var1_class"].astype(str) + "-" + gdf_bi["var2_class"].astype(str)
        assert (gdf_bi["bi_class"] == expected).all()

    def test_does_not_mutate_input(self, sample_gdf):
        original_cols = list(sample_gdf.columns)
        assign_bivariate_classes(sample_gdf, "var1", "var2")
        assert list(sample_gdf.columns) == original_cols

    def test_nan_values_raise(self, sample_gdf):
        gdf = sample_gdf.copy()
        gdf.loc[0, "var1"] = np.nan
        with pytest.raises(ValueError):
            assign_bivariate_classes(gdf, "var1", "var2")

    def test_custom_palette_used(self, sample_gdf):
        colors = ["#ffffff", "#888888", "#000000",
                  "#ff0000", "#00ff00", "#0000ff",
                  "#ffff00", "#ff00ff", "#00ffff"]
        gdf_bi, grid = assign_bivariate_classes(sample_gdf, "var1", "var2", palette=colors)
        assert grid[0, 0] == pytest.approx((1, 1, 1))


class TestPlotBivariateChoropleth:
    def test_returns_fig_ax_gdf(self, sample_gdf):
        import matplotlib.pyplot as plt

        fig, ax, gdf_bi = plot_bivariate_choropleth(sample_gdf, "var1", "var2")
        assert fig is not None
        assert ax is not None
        assert "bi_color" in gdf_bi.columns
        plt.close(fig)

    def test_custom_legend_position_places_legend_there(self, sample_gdf):
        import matplotlib.pyplot as plt

        fig, ax, _ = plot_bivariate_choropleth(
            sample_gdf, "var1", "var2",
            legend_position=(0.02, 0.7, 0.2, 0.2),
        )
        legend_ax = fig.axes[-1]
        # set_aspect("equal") ajuste la boîte de l'axe pour préserver le
        # ratio -> la position finale n'est correcte qu'après un draw().
        fig.canvas.draw()
        pos = legend_ax.get_position()
        assert pos.x0 == pytest.approx(0.02, abs=0.03)
        assert pos.y0 == pytest.approx(0.7, abs=0.03)
        plt.close(fig)

    def test_custom_palette_end_to_end(self, sample_gdf):
        import matplotlib.pyplot as plt

        fig, ax, gdf_bi = plot_bivariate_choropleth(
            sample_gdf, "var1", "var2", palette="green_purple",
        )
        assert gdf_bi["bi_color"].iloc[0] is not None
        plt.close(fig)

    def test_reuses_existing_ax_map(self, sample_gdf):
        import matplotlib.pyplot as plt

        fig0, ax0 = plt.subplots()
        fig, ax, _ = plot_bivariate_choropleth(sample_gdf, "var1", "var2", ax_map=ax0)
        assert ax is ax0
        assert fig is fig0
        plt.close(fig0)

    def test_save_path_writes_file(self, sample_gdf, tmp_path):
        import matplotlib.pyplot as plt

        out = tmp_path / "bivar.png"
        fig, ax, _ = plot_bivariate_choropleth(sample_gdf, "var1", "var2", save_path=str(out))
        assert out.exists()
        plt.close(fig)


class TestPlotBivariateLegend:
    def test_requires_position_when_given_figure(self, sample_gdf):
        import matplotlib.pyplot as plt

        fig = plt.figure()
        grid = get_bivariate_palette("blue_pink")
        with pytest.raises(ValueError):
            plot_bivariate_legend(fig, grid)
        plt.close(fig)

    def test_draws_on_existing_ax(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        grid = get_bivariate_palette("blue_pink")
        n_patches_before = len(ax.patches)
        plot_bivariate_legend(ax, grid, "A", "B")
        assert len(ax.patches) > n_patches_before
        plt.close(fig)
