from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Union
import numpy as np
import pandas as pd
import rasterio
import rasterio.windows
import rasterio.warp

from ._types import BBox
from ._optional import _require_pystac_client, _require_planetary_computer
from ..processing.raster import RasterTools

if TYPE_CHECKING:
    import pystac

import logging

logger = logging.getLogger(__name__)


class STACResults:
    """
    Result of a STAC search: a list of matched items, with helpers to
    inspect, narrow down, and load them as raster data.
    """

    def __init__(self, items: List["pystac.Item"]):
        self.items = list(items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __repr__(self) -> str:
        return f"STACResults({len(self.items)} item(s))"

    def to_dataframe(self) -> pd.DataFrame:
        """Summarizes the matched items as a DataFrame (id, datetime, cloud cover, collection)."""
        return pd.DataFrame([
            {
                "id": item.id,
                "datetime": item.datetime,
                "cloud_cover": item.properties.get("eo:cloud_cover"),
                "collection": item.collection_id,
            }
            for item in self.items
        ])

    def best(self, sort_by: str = "eo:cloud_cover") -> "STACResults":
        """
        Returns a new STACResults containing only the single item with
        the lowest `sort_by` property (lowest cloud cover by default).
        Items missing that property are ranked last.
        """
        if not self.items:
            raise ValueError(
                "Aucun élément à trier : la recherche n'a retourné aucun résultat."
            )
        ranked = sorted(
            self.items,
            key=lambda it: (
                it.properties.get(sort_by) is None,
                it.properties.get(sort_by, float("inf")),
            ),
        )
        return STACResults([ranked[0]])

    def assets(self) -> pd.DataFrame:
        """
        Lists the assets (bands/files) available on the first item:
        asset key, common name (from the STAC `eo` extension, if any),
        media type, and href.
        """
        if not self.items:
            raise ValueError(
                "Aucun élément : la recherche n'a retourné aucun résultat."
            )
        item = self.items[0]
        rows = []
        for key, asset in item.assets.items():
            eo_bands = asset.extra_fields.get("eo:bands") or []
            common_name = eo_bands[0].get("common_name") if eo_bands else None
            rows.append({
                "key": key,
                "common_name": common_name,
                "media_type": getattr(asset, "media_type", None),
                "href": asset.href,
            })
        return pd.DataFrame(rows)

    def _resolve_asset(self, item: "pystac.Item", band: str):
        """Resolves `band` to an asset, by exact key or `eo:bands` common name."""
        if band in item.assets:
            return item.assets[band]
        for asset in item.assets.values():
            eo_bands = asset.extra_fields.get("eo:bands") or []
            if eo_bands and eo_bands[0].get("common_name") == band:
                return asset
        raise ValueError(
            f"Bande '{band}' introuvable parmi les assets: {list(item.assets)}"
        )

    def load(self, bands: List[str], bbox: Optional[BBox] = None) -> RasterTools:
        """
        Loads the given bands of the selected item as a RasterTools,
        stacking them in the requested order via rasterio (bands are
        read directly from their (remote) href, no local download).

        Requires exactly one item — call `.best()` first if the search
        matched several. `bands` accepts exact asset keys (e.g. "B04")
        or common names from the STAC `eo` extension (e.g. "red",
        "nir"). `bbox` optionally restricts the read to a
        [xmin, ymin, xmax, ymax] window instead of the full scene.
        Bands must share the same grid (shape/transform); mixing bands
        of different native resolutions will raise — reproject/resample
        them to a common grid first if needed.
        """
        if len(self.items) != 1:
            raise ValueError(
                f"load() nécessite un seul élément (obtenu: {len(self.items)}). "
                "Appelez .best() pour sélectionner le meilleur élément."
            )
        item = self.items[0]
        hrefs = [self._resolve_asset(item, band).href for band in bands]

        arrays = []
        profile = None
        for href in hrefs:
            with rasterio.open(href) as src:
                if bbox is not None:
                    # `bbox` is EPSG:4326 (STAC convention); reproject it to
                    # the asset's native CRS before turning it into a window.
                    native_bbox = rasterio.warp.transform_bounds(
                        "EPSG:4326", src.crs, *bbox
                    )
                    window = rasterio.windows.from_bounds(
                        *native_bbox, transform=src.transform
                    )
                    data = src.read(1, window=window)
                    transform = src.window_transform(window)
                else:
                    data = src.read(1)
                    transform = src.transform
                if profile is None:
                    profile = dict(src.profile)
            arrays.append(data)
        stacked = np.stack(arrays, axis=0)
        profile.update(
            transform=transform,
            count=stacked.shape[0],
            height=stacked.shape[1],
            width=stacked.shape[2],
        )
        return RasterTools((stacked, profile))


class STAC:
    """
    High-level interface for searching STAC (SpatioTemporal Asset
    Catalog) catalogs and loading the matched imagery.

    Quick example
    --------------
    >>> stac = STAC("planetary-computer")
    >>> images = stac.search(
    ...     collection="sentinel-2-l2a",
    ...     bbox=[-4.05, 5.28, -3.95, 5.38],
    ...     start="2024-01-01",
    ...     end="2024-03-01",
    ...     cloud_cover=20,
    ... )
    >>> best = images.best()
    >>> best.assets()
    >>> rt = best.load(["red", "nir"])
    >>> ndvi = rt.ndvi()
    """

    CATALOGS = {
        "planetary-computer": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "earth-search": "https://earth-search.aws.element84.com/v1",
        "aws-earth-search": "https://earth-search.aws.element84.com/v1",
        "element84": "https://earth-search.aws.element84.com/v1",
        "digital-earth-africa": "https://explorer.digitalearth.africa/stac",
        "copernicus-dataspace": "https://catalogue.dataspace.copernicus.eu/stac",
    }

    def __init__(self, catalog: str = "planetary-computer"):
        """
        Parameters
        ----------
        catalog : name of a preset catalog (see `STAC.CATALOGS` for the
                  available keys) or a direct STAC API root URL.
                  "planetary-computer" automatically signs asset hrefs
                  (required to read Planetary Computer assets) via the
                  `planetary-computer` package.
        """
        pystac_client = _require_pystac_client()
        self.catalog_name = catalog
        self.url = self.CATALOGS.get(catalog, catalog)
        modifier = None
        if catalog == "planetary-computer":
            modifier = _require_planetary_computer().sign_inplace
        self._client = pystac_client.Client.open(self.url, modifier=modifier)

    def search(
        self,
        collection: Union[str, List[str]],
        bbox: BBox,
        start: str,
        end: str,
        cloud_cover: Optional[float] = None,
        limit: int = 100,
        **kwargs,
    ) -> STACResults:
        """
        Searches the catalog.

        Parameters
        ----------
        collection  : collection id, or list of ids (e.g. "sentinel-2-l2a")
        bbox        : [xmin, ymin, xmax, ymax] (EPSG:4326)
        start, end  : "YYYY-MM-DD" bounds of the search window
        cloud_cover : maximum cloud cover percentage (0-100), if the
                      collection publishes an `eo:cloud_cover` property
        limit       : maximum number of items to fetch
        kwargs      : forwarded to `pystac_client.Client.search`
                      (e.g. `query` for additional filters, `sortby`)

        Returns
        -------
        STACResults
        """
        collections = [collection] if isinstance(collection, str) else list(collection)
        query = kwargs.pop("query", {}) or {}
        if cloud_cover is not None:
            query.setdefault("eo:cloud_cover", {"lt": cloud_cover})
        search = self._client.search(
            collections=collections,
            bbox=list(bbox),
            datetime=f"{start}/{end}",
            query=query or None,
            max_items=limit,
            **kwargs,
        )
        return STACResults(list(search.items()))

    def sources(self) -> pd.DataFrame:
        """Returns a table of the preset STAC catalogs known to this class."""
        return pd.DataFrame([
            {
                "name": "Microsoft Planetary Computer",
                "url": self.CATALOGS["planetary-computer"],
                "description": "Open geospatial data catalog (Sentinel, Landsat, MODIS...); asset hrefs require signing (handled automatically).",
            },
            {
                "name": "AWS Earth Search (Element 84)",
                "url": self.CATALOGS["earth-search"],
                "description": "STAC API of public datasets hosted on AWS (Sentinel-2, Landsat, NAIP...).",
            },
            {
                "name": "Digital Earth Africa",
                "url": self.CATALOGS["digital-earth-africa"],
                "description": "STAC API for Digital Earth Africa's continental Earth observation datasets.",
            },
            {
                "name": "Copernicus Data Space Ecosystem",
                "url": self.CATALOGS["copernicus-dataspace"],
                "description": "ESA's Copernicus Data Space STAC catalog (Sentinel missions).",
            },
        ])

    def __repr__(self) -> str:
        return f"STAC(catalog={self.catalog_name!r}, url={self.url!r})"
