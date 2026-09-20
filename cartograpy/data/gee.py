from __future__ import annotations

from typing import TYPE_CHECKING, Union, List, Optional, Tuple
import pandas as pd
import os
from pathlib import Path
import datetime
from ._types import BBox
from ._optional import _require_ee, _require_geemap
if TYPE_CHECKING:
    import ee
    import geemap
import logging

logger = logging.getLogger(__name__)


class Gee:
    """
    High-level interface for Google Earth Engine.

    Quick example
    --------------
    >>> gee = Gee()
    >>> bbox = [2.2, 48.8, 2.5, 49.0]           # Paris
    >>> s2  = gee.get_sentinel2(bbox, "2024-05-01", "2024-06-01")
    >>> gee.download(s2, bbox, filename="paris_s2.tif")
    """

    # ------------------------------------------------------------------ #
    # Configuration constants                                            #
    # ------------------------------------------------------------------ #

    SENTINEL2_COLLECTION   = "COPERNICUS/S2_SR_HARMONIZED"
    LANDSAT9_COLLECTION    = "LANDSAT/LC09/C02/T1_L2"
    MODIS_NDVI_COLLECTION  = "MODIS/061/MOD13A2"
    SENTINEL1_COLLECTION   = "COPERNICUS/S1_GRD"

    # Default RGB + NIR bands
    S2_BANDS    = ["B2", "B3", "B4", "B8"]          # Blue, Green, Red, NIR
    S2_VIS      = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}

    L9_BANDS    = ["SR_B2", "SR_B3", "SR_B4", "SR_B5"]  # Blue, Green, Red, NIR
    L9_VIS      = {"bands": ["SR_B4", "SR_B3", "SR_B2"], "min": 0, "max": 30000}

    # ------------------------------------------------------------------ #
    # Constructor                                                        #
    # ------------------------------------------------------------------ #

    def __init__(self, project: Optional[str] = None, service_account: Optional[str] = None,
                 key_file: Optional[str] = None):
        """
        Initializes the connection to Earth Engine.

        Parameters
        ----------
        project : str, optional
            GCP project ID (e.g. "my-gee-project").
            Can also be provided via the GEE_PROJECT environment variable.
        service_account : str, optional
            Service account email address (non-interactive authentication).
        key_file : str, optional
            Path to the service account's JSON key file.
        """
        self._ee = _require_ee()
        self._geemap = _require_geemap()
        self.project = project or os.environ.get("GEE_PROJECT")
        self._map = None   # lazy-init map
        self._last_collection = None

        self._authenticate(service_account, key_file)

    # ------------------------------------------------------------------ #
    # Authentication                                                     #
    # ------------------------------------------------------------------ #

    def _authenticate(self, service_account: Optional[str], key_file: Optional[str]) -> None:
        """Authenticates and initializes Earth Engine."""
        ee = self._ee
        try:
            if service_account and key_file:
                credentials = ee.ServiceAccountCredentials(service_account, key_file)
                ee.Initialize(credentials=credentials, project=self.project)
            else:
                ee.Initialize(project=self.project)
        except ee.EEException:
            ee.Authenticate()
            ee.Initialize(project=self.project)

    # ------------------------------------------------------------------ #
    # Geometry utilities                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def bbox_to_geometry(bbox: BBox) -> ee.Geometry.Rectangle:
        """Converts a bbox [xmin, ymin, xmax, ymax] to an ee.Geometry."""
        ee = _require_ee()
        xmin, ymin, xmax, ymax = bbox
        return ee.Geometry.Rectangle([xmin, ymin, xmax, ymax])

    # ------------------------------------------------------------------ #
    # Cloud masks                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _mask_s2_clouds(image: ee.Image) -> ee.Image:
        """Masks Sentinel-2 clouds using the QA60 band."""
        qa = image.select("QA60")
        cloud_bit_mask   = 1 << 10
        cirrus_bit_mask  = 1 << 11
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
               qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        return image.updateMask(mask).divide(10000)

    @staticmethod
    def _mask_l9_clouds(image: ee.Image) -> ee.Image:
        """Masks Landsat-9 clouds using the QA_PIXEL band."""
        qa = image.select("QA_PIXEL")
        dilated  = 1 << 1
        clouds   = 1 << 3
        shadows  = 1 << 4
        mask = (qa.bitwiseAnd(dilated).eq(0)
                  .And(qa.bitwiseAnd(clouds).eq(0))
                  .And(qa.bitwiseAnd(shadows).eq(0)))
        # Landsat C2 L2 reflectance factor
        optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
        return image.addBands(optical, overwrite=True).updateMask(mask)

    # ------------------------------------------------------------------ #
    # Sentinel-2                                                         #
    # ------------------------------------------------------------------ #

    def get_sentinel2(
        self,
        bbox: BBox,
        start: str,
        end: str,
        mosaic: bool = True,
        clip: bool = True,
        cloud: float = 0.2,
        bands: Optional[list[str]] = None,
    ) -> ee.Image | ee.ImageCollection:
        """
        Retrieves harmonized Sentinel-2 SR images.

        Parameters
        ----------
        bbox  : [xmin, ymin, xmax, ymax]
        start : start date, format "YYYY-MM-DD"
        end   : end date,   format "YYYY-MM-DD"
        mosaic: if True, returns a median mosaic (ee.Image)
        clip  : if True, clips to the bbox
        cloud : filter on CLOUDY_PIXEL_PERCENTAGE (fraction, e.g. 0.2 = 20%)
        bands : list of bands to select (default: S2_BANDS)

        Returns
        -------
        ee.Image if mosaic=True, otherwise ee.ImageCollection
        """
        ee = self._ee
        geom  = self.bbox_to_geometry(bbox)
        bands = bands or self.S2_BANDS

        col = (ee.ImageCollection(self.SENTINEL2_COLLECTION)
               .filterBounds(geom)
               .filterDate(start, end)
               .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud * 100))
               .map(self._mask_s2_clouds)
               .select(bands))

        self._last_collection = col

        if mosaic:
            result = col.median()
            if clip:
                result = result.clip(geom)
            return result

        if clip:
            col = col.map(lambda img: img.clip(geom))
        return col

    # ------------------------------------------------------------------ #
    # Landsat-9                                                          #
    # ------------------------------------------------------------------ #

    def get_landsat9(
        self,
        bbox: BBox,
        start: str,
        end: str,
        mosaic: bool = True,
        clip: bool = True,
        cloud: float = 0.2,
        bands: Optional[list[str]] = None,
    ) -> ee.Image | ee.ImageCollection:
        """
        Retrieves Landsat-9 Collection 2 Tier 1 L2 images.

        Parameters
        ----------
        Same as get_sentinel2.
        cloud : filter on CLOUD_COVER (fraction)
        """
        ee = self._ee
        geom  = self.bbox_to_geometry(bbox)
        bands = bands or self.L9_BANDS

        col = (ee.ImageCollection(self.LANDSAT9_COLLECTION)
               .filterBounds(geom)
               .filterDate(start, end)
               .filter(ee.Filter.lt("CLOUD_COVER", cloud * 100))
               .map(self._mask_l9_clouds)
               .select(bands))

        self._last_collection = col

        if mosaic:
            result = col.median()
            if clip:
                result = result.clip(geom)
            return result

        if clip:
            col = col.map(lambda img: img.clip(geom))
        return col

    # ------------------------------------------------------------------ #
    # Sentinel-1 SAR                                                     #
    # ------------------------------------------------------------------ #

    def get_sentinel1(
        self,
        bbox: BBox,
        start: str,
        end: str,
        mosaic: bool = True,
        clip: bool = True,
        polarization: str = "VV",
        pass_direction: str = "DESCENDING",
    ) -> ee.Image | ee.ImageCollection:
        """
        Retrieves Sentinel-1 GRD SAR images.

        Parameters
        ----------
        polarization    : "VV", "VH" or both ["VV","VH"]
        pass_direction  : "ASCENDING" | "DESCENDING"
        """
        ee = self._ee
        geom = self.bbox_to_geometry(bbox)
        bands = [polarization] if isinstance(polarization, str) else polarization

        col = (ee.ImageCollection(self.SENTINEL1_COLLECTION)
               .filterBounds(geom)
               .filterDate(start, end)
               .filter(ee.Filter.eq("instrumentMode", "IW"))
               .filter(ee.Filter.eq("orbitProperties_pass", pass_direction))
               .filter(ee.Filter.listContains("transmitterReceiverPolarisation", polarization))
               .select(bands))

        self._last_collection = col

        if mosaic:
            result = col.mean()
            if clip:
                result = result.clip(geom)
            return result

        if clip:
            col = col.map(lambda img: img.clip(geom))
        return col

    # ------------------------------------------------------------------ #
    # NDVI                                                               #
    # ------------------------------------------------------------------ #

    def compute_ndvi(self, image: ee.Image, nir_band: str = "B8",
                     red_band: str = "B4", name: str = "NDVI") -> ee.Image:
        """Computes and adds an NDVI band to the image."""
        ndvi = image.normalizedDifference([nir_band, red_band]).rename(name)
        return image.addBands(ndvi)

    def compute_ndvi_l9(self, image: ee.Image, name: str = "NDVI") -> ee.Image:
        """NDVI for Landsat-9 (NIR=SR_B5, Red=SR_B4)."""
        return self.compute_ndvi(image, nir_band="SR_B5", red_band="SR_B4", name=name)

    # ------------------------------------------------------------------ #
    # Collection inspection                                              #
    # ------------------------------------------------------------------ #

    def collection(
        self,
        collection_id: str,
        bbox: Optional[BBox] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        properties: Optional[dict] = None,
    ) -> ee.ImageCollection:
        """
        Accesses any GEE collection with optional filters.

        Parameters
        ----------
        collection_id : GEE identifier (e.g. "COPERNICUS/S2_SR_HARMONIZED")
        bbox          : optional spatial filter
        start, end    : optional temporal filter ("YYYY-MM-DD")
        properties    : dict {property: value} for additional filters

        Returns
        -------
        Filtered ee.ImageCollection
        """
        ee = self._ee
        col = ee.ImageCollection(collection_id)

        if bbox is not None:
            col = col.filterBounds(self.bbox_to_geometry(bbox))
        if start and end:
            col = col.filterDate(start, end)
        if properties:
            for prop, value in properties.items():
                col = col.filter(ee.Filter.eq(prop, value))

        self._last_collection = col
        return col

    def info(self, data: Union[ee.Image, ee.ImageCollection]) -> dict:
        """Returns the metadata (dict) of an image or collection."""
        return data.getInfo()

    def count(self, col: Optional[ee.ImageCollection] = None) -> int:
        """Number of images in a collection (last one by default)."""
        col = col or self._last_collection
        if col is None:
            raise ValueError("Aucune collection disponible.")
        return col.size().getInfo()

    def dates(self, col: Optional[ee.ImageCollection] = None) -> list[str]:
        """List of acquisition dates for a collection."""
        col = col or self._last_collection
        if col is None:
            raise ValueError("Aucune collection disponible.")
        dates = col.aggregate_array("system:time_start").getInfo()
        import datetime
        return [
            datetime.datetime.utcfromtimestamp(d / 1000).strftime("%Y-%m-%d")
            for d in dates
        ]

    # ------------------------------------------------------------------ #
    # Export / Download                                                  #
    # ------------------------------------------------------------------ #

    def download(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        bbox: Optional[BBox] = None,
        filename: str = "image.tif",
        scale: int = 10,
        crs: str = "EPSG:4326",
        bands: Optional[list[str]] = None,
        output_dir: str = ".",
        mosaic_col: bool = True,
    ) -> Path:
        """
        Downloads an ee.Image (or ee.ImageCollection) locally via geemap.

        Parameters
        ----------
        data        : image or collection to download
        bbox        : export area [xmin, ymin, xmax, ymax] (required if the image isn't clipped)
        filename    : output file name (.tif)
        scale       : resolution in meters (10 m for S2, 30 m for L9)
        crs         : output coordinate system
        bands       : subset of bands to export
        output_dir  : destination folder
        mosaic_col  : if data is a collection, take the median before exporting

        Returns
        -------
        Path to the downloaded file
        """
        ee = self._ee
        geemap = self._geemap
        # Resolve a possible collection
        if isinstance(data, ee.ImageCollection):
            data = data.median() if mosaic_col else data.mosaic()

        # Band selection
        if bands:
            data = data.select(bands)

        # Export region
        region = None
        if bbox is not None:
            region = self.bbox_to_geometry(bbox)

        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        geemap.ee_export_image(
            data,
            filename=str(output_path),
            scale=scale,
            region=region,
            crs=crs,
            file_per_band=False,
        )
        return output_path

    def export_to_drive(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        bbox: Optional[BBox] = None,
        description: str = "gee_export",
        folder: str = "GEE_exports",
        scale: int = 10,
        crs: str = "EPSG:4326",
        max_pixels: int = int(1e13),
    ) -> None:
        """
        Starts an export task to Google Drive (asynchronous).

        Parameters
        ----------
        description : task and file name in Drive
        folder      : destination Drive folder
        """
        ee = self._ee
        if isinstance(data, ee.ImageCollection):
            data = data.median()

        region = self.bbox_to_geometry(bbox) if bbox else None

        task = ee.batch.Export.image.toDrive(
            image=data,
            description=description,
            folder=folder,
            scale=scale,
            region=region,
            crs=crs,
            maxPixels=max_pixels,
        )
        task.start()

    # ------------------------------------------------------------------ #
    # Visualization                                                      #
    # ------------------------------------------------------------------ #

    def map(self, center: Optional[list[float]] = None, zoom: int = 8) -> geemap.Map:
        """
        Returns (or creates) an interactive geemap map.

        Parameters
        ----------
        center : [lat, lon] of the map's center
        zoom   : initial zoom level
        """
        geemap = self._geemap
        if self._map is None:
            self._map = geemap.Map()
        if center:
            self._map.setCenter(center[1], center[0], zoom)
        return self._map

    def add_layer(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        vis_params: Optional[dict] = None,
        name: str = "Layer",
        bbox: Optional[BBox] = None,
    ) -> geemap.Map:
        """
        Adds an image (or collection) to the interactive map.

        Parameters
        ----------
        vis_params : GEE visualization dict (bands, min, max, palette...)
        name       : layer name on the map
        bbox       : if provided, centers the map on the bbox
        """
        ee = self._ee
        m = self.map()

        if isinstance(data, ee.ImageCollection):
            data = data.median()

        m.addLayer(data, vis_params or {}, name)

        if bbox is not None:
            xmin, ymin, xmax, ymax = bbox
            m.centerObject(self.bbox_to_geometry(bbox))

        return m

    def show_map(
        self,
        data: Union[ee.Image, ee.ImageCollection],
        bbox: Optional[BBox] = None,
        vis_params: Optional[dict] = None,
        name: str = "Layer",
    ) -> geemap.Map:
        """Shortcut: creates the map, adds the layer, and displays it."""
        return self.add_layer(data, vis_params=vis_params, name=name, bbox=bbox)

    # ------------------------------------------------------------------ #
    # Zonal statistics                                                   #
    # ------------------------------------------------------------------ #

    def zonal_stats(
        self,
        image: ee.Image,
        bbox: BBox,
        scale: int = 30,
        reducer: str = "mean",
    ) -> dict:
        """
        Computes zonal statistics over a bbox.

        Parameters
        ----------
        reducer : "mean" | "median" | "min" | "max" | "sum"

        Returns
        -------
        dict {band: value}
        """
        ee = self._ee
        reducers = {
            "mean":   ee.Reducer.mean(),
            "median": ee.Reducer.median(),
            "min":    ee.Reducer.min(),
            "max":    ee.Reducer.max(),
            "sum":    ee.Reducer.sum(),
        }
        r = reducers.get(reducer, ee.Reducer.mean())
        geom = self.bbox_to_geometry(bbox)
        stats = image.reduceRegion(reducer=r, geometry=geom, scale=scale, maxPixels=int(1e10))
        return stats.getInfo()

    # ------------------------------------------------------------------ #
    # Sources                                                            #
    # ------------------------------------------------------------------ #

    def sources(self) -> pd.DataFrame:
        """Returns a table of the data sources (GEE collections) used by this class."""
        return pd.DataFrame([
            {
                "name": f"Sentinel-2 ({self.SENTINEL2_COLLECTION})",
                "url": f"https://developers.google.com/earth-engine/datasets/catalog/{self.SENTINEL2_COLLECTION.replace('/', '_')}",
                "description": "Sentinel-2 optical imagery, surface reflectance (get_sentinel2).",
            },
            {
                "name": f"Landsat 9 ({self.LANDSAT9_COLLECTION})",
                "url": f"https://developers.google.com/earth-engine/datasets/catalog/{self.LANDSAT9_COLLECTION.replace('/', '_')}",
                "description": "Landsat 9 optical imagery, level 2 (get_landsat9).",
            },
            {
                "name": f"MODIS NDVI ({self.MODIS_NDVI_COLLECTION})",
                "url": f"https://developers.google.com/earth-engine/datasets/catalog/{self.MODIS_NDVI_COLLECTION.replace('/', '_')}",
                "description": "NDVI vegetation index, 1 km, 16 days (via collection()).",
            },
            {
                "name": f"Sentinel-1 ({self.SENTINEL1_COLLECTION})",
                "url": f"https://developers.google.com/earth-engine/datasets/catalog/{self.SENTINEL1_COLLECTION.replace('/', '_')}",
                "description": "Sentinel-1 radar imagery, GRD (get_sentinel1).",
            },
        ])

    # ------------------------------------------------------------------ #
    # String representation                                              #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        project_str = f"project={self.project!r}" if self.project else "project=default"
        return f"Gee({project_str})"
