"""Tests pour le module mapper."""

import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from cartograpy.mapper import Map, Map2D, WebMap, SituationMap, read_image, plot_choropleth
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for testing


@pytest.fixture
def sample_gdf():
    return gpd.GeoDataFrame(
        {
            "name": ["A", "B"],
            "value": [10, 20],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
            ],
        },
        crs="EPSG:4326",
    )


class TestMapClass:
    """Tests de la classe Map."""

    def test_paper_sizes_exist(self):
        assert "A4" in Map.PAPER_SIZES
        assert "A3" in Map.PAPER_SIZES
        assert "A0" in Map.PAPER_SIZES

    def test_paper_sizes_dimensions(self):
        w, h = Map.PAPER_SIZES["A4"]
        assert w == 210
        assert h == 297

    def test_instantiation_default(self):
        m = Map(verbose=False)
        assert m.title == "Carte"
        assert m.fig is not None
        assert m.ax is not None
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_instantiation_custom_title(self):
        m = Map(title="Test Map", verbose=False)
        assert m.title == "Test Map"
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_instantiation_custom_figsize(self):
        m = Map(figsize=(10, 6), verbose=False)
        assert m.figsize == (10, 6)
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_instantiation_paper_format(self):
        m = Map(figsize="A4", verbose=False)
        assert m.paper_info is not None
        assert m.paper_info["format"] == "A4"
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_layers_empty_initially(self):
        m = Map(verbose=False)
        assert m.layers == []
        import matplotlib.pyplot as plt
        plt.close(m.fig)

    def test_default_bounds(self):
        m = Map(verbose=False)
        assert m.bounds == [-180, -90, 180, 90]
        import matplotlib.pyplot as plt
        plt.close(m.fig)


class TestMap2D:
    """Tests de la classe Map2D."""

    def test_inherits_map(self):
        assert issubclass(Map2D, Map)

    def test_instantiation(self):
        m = Map2D(verbose=False)
        assert m.fig is not None
        import matplotlib.pyplot as plt
        plt.close(m.fig)


class TestWebMap:
    """Tests de la classe WebMap."""

    def test_instantiation(self):
        wm = WebMap()
        assert wm is not None

    def test_has_map_attribute(self):
        wm = WebMap()
        # WebMap wraps folium.Map
        assert hasattr(wm, "m") or hasattr(wm, "map")


class TestSituationMap:
    """Tests de la classe SituationMap."""

    def test_instantiation(self):
        sm = SituationMap(verbose=False)
        assert sm is not None
        assert sm.fig is not None
        import matplotlib.pyplot as plt
        plt.close(sm.fig)

    def test_custom_title(self):
        sm = SituationMap(title="Test", verbose=False)
        assert sm.figsize == (14, 10)
        import matplotlib.pyplot as plt
        plt.close(sm.fig)


class TestPlotChoropleth:
    """Tests de la fonction plot_choropleth."""

    def test_callable(self):
        assert callable(plot_choropleth)

    def test_basic_call(self, sample_gdf):
        import matplotlib.pyplot as plt
        # Should not raise
        plot_choropleth(
            sample_gdf,
            column_to_plot="value",
            label_column="name",
            title="Test",
        )
        plt.close("all")


class TestReadImage:
    """Tests de la fonction read_image."""

    def test_callable(self):
        assert callable(read_image)

    def test_read_png(self, tmp_path):
        from PIL import Image
        img = Image.new("RGB", (10, 10), "red")
        path = tmp_path / "test.png"
        img.save(str(path))
        result = read_image(str(path))
        assert result is not None
        assert result.size == (10, 10)
