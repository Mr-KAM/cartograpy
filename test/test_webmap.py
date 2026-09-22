"""Tests for cartograpy.mapper.webmap (WebMap: folium + optional GPU engines)."""
import json

import numpy as np
import pytest
import geopandas as gpd
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import Point, Polygon

from cartograpy import WebMap


@pytest.fixture
def polygons():
    return gpd.GeoDataFrame(
        {"pop": [10, 20, 30]},
        geometry=[
            Polygon([(-5, 4), (-4, 4), (-4, 5), (-5, 5)]),
            Polygon([(-4, 4), (-3, 4), (-3, 5), (-4, 5)]),
            Polygon([(-5, 5), (-4, 5), (-4, 6), (-5, 6)]),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def points():
    return gpd.GeoDataFrame(
        {"name": ["a", "b"], "date": ["2024-01-01", "2024-02-01"]},
        geometry=[Point(-4.5, 4.5), Point(-3.5, 4.7)],
        crs="EPSG:4326",
    )


@pytest.fixture
def tiny_geotiff(tmp_path):
    path = str(tmp_path / "tiny.tif")
    data = (np.random.default_rng(0).random((3, 10, 10)) * 255).astype("uint8")
    transform = from_bounds(-5, 4, -3, 6, 10, 10)
    profile = dict(driver="GTiff", dtype="uint8", width=10, height=10, count=3,
                   crs="EPSG:4326", transform=transform)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)
    return path


@pytest.fixture
def tiny_dem_with_nodata(tmp_path):
    """Single-band raster with a nodata corner, for cmap/transparency tests."""
    path = str(tmp_path / "dem.tif")
    data = (np.random.default_rng(2).random((1, 20, 20)) * 2000 + 100).astype("float32")
    data[0, :4, :4] = -9999
    transform = from_bounds(-5, 4, -3, 6, 20, 20)
    profile = dict(driver="GTiff", dtype="float32", width=20, height=20, count=1,
                   crs="EPSG:4326", transform=transform, nodata=-9999)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)
    return path


def _extract_overlay_png(html):
    import base64
    import re
    from io import BytesIO
    from PIL import Image

    match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", html)
    assert match, "no embedded PNG overlay found in the saved HTML"
    return Image.open(BytesIO(base64.b64decode(match.group(1)))).convert("RGBA")


def _html(wm, tmp_path, name="out.html"):
    out = tmp_path / name
    wm.save(str(out))
    return out.read_text(encoding="utf-8")


class TestWebMapInit:
    def test_default_engine_is_folium(self):
        assert WebMap().engine == "folium"

    def test_invalid_engine_raises(self):
        with pytest.raises(ValueError):
            WebMap(engine="nope")

    def test_has_map_attribute(self):
        wm = WebMap()
        assert hasattr(wm, "map")


class TestWebMapFolium:
    def test_add_layer_plain(self, polygons):
        wm = WebMap()
        wm.add_layer(polygons)
        assert wm.map is not None

    def test_add_layer_choropleth_respects_cmap(self, polygons, tmp_path):
        # Regression: cmap used to be silently ignored (hardcoded YlOrRd).
        wm_default = WebMap()
        wm_default.add_layer(polygons, column="pop", cmap="YlOrRd")
        wm_viridis = WebMap()
        wm_viridis.add_layer(polygons, column="pop", cmap="viridis")
        html_default = _html(wm_default, tmp_path, "a.html")
        html_viridis = _html(wm_viridis, tmp_path, "b.html")
        assert html_default != html_viridis

    def test_add_layer_unknown_cmap_raises(self, polygons):
        wm = WebMap()
        with pytest.raises(ValueError):
            wm.add_layer(polygons, column="pop", cmap="not-a-real-cmap")

    def test_add_geojson_from_dict(self, polygons, tmp_path):
        wm = WebMap()
        wm.add_geojson(json.loads(polygons.to_json()), name="g")
        html = _html(wm, tmp_path)
        assert "L.geoJson(" in html

    def test_add_geojson_from_gdf(self, polygons, tmp_path):
        wm = WebMap()
        wm.add_geojson(polygons, name="g")
        html = _html(wm, tmp_path)
        assert "L.geoJson(" in html

    def test_add_marker(self, tmp_path):
        wm = WebMap()
        wm.add_marker((4.5, -4.5), popup="hi")
        html = _html(wm, tmp_path)
        assert "marker" in html.lower()

    def test_add_cluster(self, points, tmp_path):
        wm = WebMap()
        wm.add_cluster(points, popup_columns=["name"])
        html = _html(wm, tmp_path)
        assert "markercluster" in html.lower()

    def test_add_heatmap_from_gdf(self, points, tmp_path):
        wm = WebMap()
        wm.add_heatmap(points)
        html = _html(wm, tmp_path)
        assert "heatlayer" in html.lower()

    def test_add_heatmap_from_raw_list(self, tmp_path):
        wm = WebMap()
        wm.add_heatmap([[4.5, -4.5, 0.5], [4.6, -4.4, 0.8]])
        html = _html(wm, tmp_path)
        assert "heatlayer" in html.lower()

    def test_add_basemap(self, tmp_path):
        wm = WebMap()
        wm.add_basemap("CartoDB positron", name="carto")
        html = _html(wm, tmp_path)
        assert "cartocdn" in html.lower()

    def test_add_xyz(self, tmp_path):
        wm = WebMap()
        wm.add_xyz("https://example.com/{z}/{x}/{y}.png", name="xyz", attr="Example")
        html = _html(wm, tmp_path)
        assert "example.com" in html

    def test_add_wms(self, tmp_path):
        wm = WebMap()
        wm.add_wms("https://example.com/wms", layers="test:layer", name="wms")
        html = _html(wm, tmp_path)
        assert "tileLayer.wms" in html
        assert "test:layer" in html

    def test_add_raster(self, tiny_geotiff, tmp_path):
        wm = WebMap()
        wm.add_raster(tiny_geotiff, name="raster")
        html = _html(wm, tmp_path)
        assert "imageoverlay" in html.lower()
        assert "base64" in html

    def test_add_cog_delegates_to_raster(self, tiny_geotiff, tmp_path):
        wm = WebMap()
        wm.add_cog(tiny_geotiff, name="cog", max_size=5)
        html = _html(wm, tmp_path)
        assert "imageoverlay" in html.lower()

    def test_add_cog_with_cmap_produces_colored_pixels(self, tiny_dem_with_nodata, tmp_path):
        wm = WebMap()
        wm.add_cog(tiny_dem_with_nodata, cmap="terrain")
        img = _extract_overlay_png(_html(wm, tmp_path))
        assert img.size == (20, 20)
        # a mid-value pixel should get a real (non-gray) terrain color
        r, g, b, a = img.getpixel((10, 10))
        assert a == 255
        assert (r, g, b) != (r, r, r)

    def test_add_cog_nodata_is_transparent(self, tiny_dem_with_nodata, tmp_path):
        wm = WebMap()
        wm.add_cog(tiny_dem_with_nodata, cmap="terrain")
        img = _extract_overlay_png(_html(wm, tmp_path))
        assert img.getpixel((0, 0))[3] == 0  # nodata corner -> fully transparent

    def test_add_raster_unknown_cmap_raises(self, tiny_dem_with_nodata):
        wm = WebMap()
        with pytest.raises(Exception):
            wm.add_raster(tiny_dem_with_nodata, cmap="not-a-real-cmap")

    def test_add_raster_vmin_vmax_override(self, tiny_dem_with_nodata, tmp_path):
        wm = WebMap()
        wm.add_raster(tiny_dem_with_nodata, cmap="viridis", vmin=0, vmax=5000)
        html = _html(wm, tmp_path)
        assert "imageoverlay" in html.lower()

    def test_add_raster_decimates_to_max_size(self, tiny_dem_with_nodata, tmp_path):
        wm = WebMap()
        wm.add_raster(tiny_dem_with_nodata, max_size=8)
        img = _extract_overlay_png(_html(wm, tmp_path))
        assert max(img.size) <= 8

    def test_add_legend_dict(self, tmp_path):
        wm = WebMap()
        wm.add_legend({"Low": "green", "High": "red"}, title="Legend")
        html = _html(wm, tmp_path)
        assert "Legend" in html
        assert "position: fixed" in html

    def test_add_colorbar(self, tmp_path):
        wm = WebMap()
        wm.add_colorbar(0, 100, cmap="YlOrRd", caption="pop")
        html = _html(wm, tmp_path)
        assert "pop" in html

    def test_add_layer_control(self, polygons, tmp_path):
        wm = WebMap()
        wm.add_layer(polygons, name="l1")
        wm.add_layer_control()
        html = _html(wm, tmp_path)
        assert "layercontrol" in html.lower() or "layers" in html.lower()

    def test_add_measure_control(self, tmp_path):
        wm = WebMap()
        wm.add_measure_control()
        html = _html(wm, tmp_path)
        assert "measure" in html.lower()

    def test_add_draw_control(self, tmp_path):
        wm = WebMap()
        wm.add_draw_control()
        html = _html(wm, tmp_path)
        assert "draw(" in html.lower()

    def test_add_fullscreen(self, tmp_path):
        wm = WebMap()
        wm.add_fullscreen()
        html = _html(wm, tmp_path)
        assert "fullscreen" in html.lower()

    def test_fit_bounds(self, polygons):
        wm = WebMap()
        wm.fit_bounds(polygons)  # should not raise

    def test_split_creates_dual_map(self, polygons, tmp_path):
        import folium.plugins as plugins
        left = polygons.iloc[[0]]
        right = polygons.iloc[[1]]
        wm = WebMap(location=(4.5, -4.2), zoom_start=8)
        wm.split(left=left, right=right, left_name="2015", right_name="2025")
        assert isinstance(wm.map, plugins.DualMap)
        html = _html(wm, tmp_path)
        assert html.count("L.geoJson(") == 2

    def test_time_slider(self, points, tmp_path):
        wm = WebMap()
        wm.time_slider(points, time_column="date")
        html = _html(wm, tmp_path)
        assert "timedimension" in html.lower()

    def test_show_returns_map(self):
        wm = WebMap()
        assert wm.show() is wm.map

    def test_repr_html(self, polygons):
        wm = WebMap()
        wm.add_layer(polygons)
        assert "<div" in wm._repr_html_()


class TestWebMapUnsupportedOnFolium:
    """Methods with no folium equivalent don't exist; nothing to test here.

    The reverse (folium-only methods rejected by other engines) is
    covered in TestWebMapEngineGuards below.
    """


class TestWebMapEngineGuards:
    def test_lonboard_rejects_marker(self):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        with pytest.raises(NotImplementedError):
            wm.add_marker((0, 0))

    def test_lonboard_rejects_split(self):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        with pytest.raises(NotImplementedError):
            wm.split(left=None, right=None)

    def test_keplergl_rejects_heatmap(self):
        pytest.importorskip("keplergl")
        wm = WebMap(engine="kepler.gl")
        with pytest.raises(NotImplementedError):
            wm.add_heatmap([[0, 0]])


class TestWebMapLonboard:
    def test_add_layer_polygons(self, polygons):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        wm.add_layer(polygons)
        assert wm.map is not None
        assert len(wm.map.layers) >= 1

    def test_add_layer_accumulates(self, polygons, points):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        wm.add_layer(polygons)
        wm.add_layer(points)
        assert len(wm.map.layers) >= 2

    def test_save_html(self, polygons, tmp_path):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        wm.add_layer(polygons)
        out = tmp_path / "lonboard.html"
        wm.save(str(out))
        assert out.exists() and out.stat().st_size > 0

    def test_starts_with_empty_layers(self):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        assert len(wm.map.layers) == 0

    def test_add_basemap_valid_style(self, polygons):
        pytest.importorskip("lonboard")
        import lonboard.basemap as bm
        wm = WebMap(engine="lonboard")
        wm.add_layer(polygons)
        wm.add_basemap("positron")
        assert wm.map.basemap.style == bm.CartoStyle.Positron

    def test_add_basemap_unknown_style_raises(self):
        pytest.importorskip("lonboard")
        wm = WebMap(engine="lonboard")
        with pytest.raises(ValueError):
            wm.add_basemap("not-a-real-style")


class TestWebMapKeplerGl:
    def test_add_layer(self, polygons):
        pytest.importorskip("keplergl")
        wm = WebMap(engine="kepler.gl")
        wm.add_layer(polygons, name="polys")
        assert wm.map is not None

    def test_save_html(self, polygons, tmp_path):
        pytest.importorskip("keplergl")
        wm = WebMap(engine="kepler.gl")
        wm.add_layer(polygons, name="polys")
        out = tmp_path / "kepler.html"
        wm.save(str(out))
        assert out.exists() and out.stat().st_size > 0
