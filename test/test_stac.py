"""Tests for cartograpy.data.stac — offline, pystac_client.Client.open mocked."""
import numpy as np
import pytest
import rasterio
import rasterio.warp
import rasterio.windows
from rasterio.transform import from_bounds, from_origin
import pystac_client

from cartograpy.data.stac import STAC, STACResults


class FakeAsset:
    def __init__(self, href, media_type=None, common_name=None):
        self.href = href
        self.media_type = media_type
        self.extra_fields = (
            {"eo:bands": [{"common_name": common_name}]} if common_name else {}
        )


class FakeItem:
    def __init__(self, id, cloud_cover, assets, collection_id="sentinel-2-l2a"):
        self.id = id
        self.datetime = None
        self.properties = {"eo:cloud_cover": cloud_cover}
        self.assets = assets
        self.collection_id = collection_id


class FakeItemSearch:
    def __init__(self, items):
        self._items = items

    def items(self):
        return iter(self._items)


class FakeClient:
    def __init__(self, items):
        self._items = items
        self.last_kwargs = None

    def search(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeItemSearch(self._items)


def _make_tif(tmp_path, name, value, crs="EPSG:4326"):
    """Writes a tiny 4x4 single-band GeoTIFF filled with `value`."""
    path = str(tmp_path / name)
    data = np.full((1, 4, 4), value, dtype="float32")
    transform = from_bounds(-4.02, 5.30, -3.98, 5.34, 4, 4)
    profile = dict(
        driver="GTiff", dtype="float32", width=4, height=4, count=1,
        crs=crs, transform=transform,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)
    return path


def _make_utm_tif(tmp_path, name):
    """
    Writes an 8x8 EPSG:32630 GeoTIFF with distinct per-pixel values
    (0..63), used to check that `.load(bbox=...)` correctly reprojects
    a WGS84 bbox into the asset's native (projected) CRS before windowing.
    """
    path = str(tmp_path / name)
    transform = from_origin(500000, 600080, 10, 10)
    data = np.arange(64, dtype="float32").reshape(8, 8)
    profile = dict(
        driver="GTiff", dtype="float32", width=8, height=8, count=1,
        crs="EPSG:32630", transform=transform,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data[np.newaxis, ...])
    return path, data


@pytest.fixture
def fake_items(tmp_path):
    return [
        FakeItem("scene_cloudy", 80, {
            "B04": FakeAsset(_make_tif(tmp_path, "cloudy_red.tif", 10), common_name="red"),
            "B08": FakeAsset(_make_tif(tmp_path, "cloudy_nir.tif", 20), common_name="nir"),
        }),
        FakeItem("scene_clear", 5, {
            "B04": FakeAsset(_make_tif(tmp_path, "clear_red.tif", 100), common_name="red"),
            "B08": FakeAsset(_make_tif(tmp_path, "clear_nir.tif", 300), common_name="nir"),
        }),
    ]


@pytest.fixture
def stac(monkeypatch, fake_items):
    fake_client = FakeClient(fake_items)
    monkeypatch.setattr(
        pystac_client.Client, "open",
        classmethod(lambda cls, url, modifier=None: fake_client),
    )
    return STAC("earth-search")


class TestSTACInit:
    def test_preset_catalog_resolves_url(self, stac):
        assert stac.url == STAC.CATALOGS["earth-search"]

    def test_custom_url_passthrough(self, monkeypatch, fake_items):
        fake_client = FakeClient(fake_items)
        monkeypatch.setattr(
            pystac_client.Client, "open",
            classmethod(lambda cls, url, modifier=None: fake_client),
        )
        custom = STAC("https://example.com/stac/v1")
        assert custom.url == "https://example.com/stac/v1"

    def test_planetary_computer_applies_signer(self, monkeypatch, fake_items):
        import planetary_computer
        fake_client = FakeClient(fake_items)
        captured = {}

        def fake_open(cls, url, modifier=None):
            captured["url"] = url
            captured["modifier"] = modifier
            return fake_client

        monkeypatch.setattr(pystac_client.Client, "open", classmethod(fake_open))
        STAC("planetary-computer")
        assert captured["url"] == STAC.CATALOGS["planetary-computer"]
        assert captured["modifier"] is planetary_computer.sign_inplace

    def test_repr(self, stac):
        assert "STAC" in repr(stac)


class TestSTACSearch:
    def test_search_forwards_expected_kwargs(self, stac):
        results = stac.search(
            collection="sentinel-2-l2a",
            bbox=[-4.05, 5.28, -3.95, 5.38],
            start="2024-01-01",
            end="2024-03-01",
            cloud_cover=20,
        )
        assert isinstance(results, STACResults)
        assert len(results) == 2
        kwargs = stac._client.last_kwargs
        assert kwargs["collections"] == ["sentinel-2-l2a"]
        assert kwargs["bbox"] == [-4.05, 5.28, -3.95, 5.38]
        assert kwargs["datetime"] == "2024-01-01/2024-03-01"
        assert kwargs["query"] == {"eo:cloud_cover": {"lt": 20}}

    def test_search_accepts_collection_list(self, stac):
        stac.search(
            collection=["sentinel-2-l2a", "landsat-c2-l2"],
            bbox=[-4.05, 5.28, -3.95, 5.38], start="2024-01-01", end="2024-03-01",
        )
        assert stac._client.last_kwargs["collections"] == ["sentinel-2-l2a", "landsat-c2-l2"]

    def test_to_dataframe(self, stac):
        results = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        )
        df = results.to_dataframe()
        assert set(df["id"]) == {"scene_cloudy", "scene_clear"}
        assert "cloud_cover" in df.columns


class TestSTACResults:
    def test_best_picks_lowest_cloud_cover(self, stac):
        results = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        )
        best = results.best()
        assert len(best) == 1
        assert best.items[0].id == "scene_clear"

    def test_best_raises_on_empty_results(self):
        with pytest.raises(ValueError):
            STACResults([]).best()

    def test_assets_lists_common_names(self, stac):
        results = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        )
        df = results.best().assets()
        assert set(df["common_name"]) == {"red", "nir"}

    def test_load_requires_single_item(self, stac):
        results = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        )
        with pytest.raises(ValueError):
            results.load(["red", "nir"])

    def test_load_unknown_band_raises(self, stac):
        best = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        ).best()
        with pytest.raises(ValueError):
            best.load(["swir16"])

    def test_load_by_common_name_stacks_bands(self, stac):
        best = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        ).best()
        rt = best.load(["red", "nir"])
        assert rt.data.shape == (2, 4, 4)
        assert rt.data[0].mean() == 100  # red band of scene_clear
        assert rt.data[1].mean() == 300  # nir band of scene_clear

    def test_load_by_exact_asset_key(self, stac):
        best = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        ).best()
        rt = best.load(["B04"])
        assert rt.data.shape == (1, 4, 4)

    def test_load_reprojects_wgs84_bbox_onto_utm_asset(self, monkeypatch, tmp_path):
        # Real STAC assets (e.g. Sentinel-2 on Planetary Computer) are
        # natively in UTM while `bbox` is always WGS84 (EPSG:4326) — this
        # is the exact mismatch that must be reprojected before windowing.
        utm_path, full_data = _make_utm_tif(tmp_path, "utm_band.tif")
        item = FakeItem("utm_scene", 1, {
            "B04": FakeAsset(utm_path, common_name="red"),
        })
        fake_client = FakeClient([item])
        monkeypatch.setattr(
            pystac_client.Client, "open",
            classmethod(lambda cls, url, modifier=None: fake_client),
        )
        stac = STAC("earth-search")
        results = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        )

        # bbox of the central 4x4 sub-window (rows/cols 2:6), expressed in
        # WGS84 by round-tripping through the raster's own transform.
        with rasterio.open(utm_path) as src:
            sub_transform = rasterio.windows.transform(
                rasterio.windows.Window(2, 2, 4, 4), src.transform
            )
            sub_bounds_utm = rasterio.transform.array_bounds(4, 4, sub_transform)
            sub_bbox_wgs84 = rasterio.warp.transform_bounds(
                src.crs, "EPSG:4326", *sub_bounds_utm
            )

        rt = results.load(["red"], bbox=sub_bbox_wgs84)
        assert rt.data.shape == (1, 4, 4)
        np.testing.assert_array_equal(rt.data[0], full_data[2:6, 2:6])

    def test_ndvi_chains_on_loaded_raster(self, stac):
        best = stac.search(
            "sentinel-2-l2a", [-4.05, 5.28, -3.95, 5.38], "2024-01-01", "2024-03-01"
        ).best()
        ndvi = best.load(["red", "nir"]).ndvi()
        # NDVI = (nir - red) / (nir + red) = (300-100)/(300+100) = 0.5
        assert ndvi.data.mean() == pytest.approx(0.5)


class TestSTACSources:
    def test_sources_lists_presets(self, stac):
        df = stac.sources()
        assert len(df) == 4
        assert set(df["name"]) == {
            "Microsoft Planetary Computer",
            "AWS Earth Search (Element 84)",
            "Digital Earth Africa",
            "Copernicus Data Space Ecosystem",
        }
