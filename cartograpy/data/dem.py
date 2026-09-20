from __future__ import annotations

import pandas as pd
import geopandas as gpd
from typing import TYPE_CHECKING, Union, List, Optional, Tuple
import math
import numpy as np
from requests_cache import CachedSession
import time
import requests
from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import warnings
import datetime
from tqdm import tqdm
import gzip
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from rasterio.transform import Affine
    from rasterio.merge import merge as rio_merge
    from rasterio.windows import from_bounds
except ImportError as e:
    raise ImportError(
        """Cette classe nécessite rasterio.
        Installez-le avec: pip install rasterio"""
    ) from e
from ._types import BBox
import logging

logger = logging.getLogger(__name__)


class DEMDownloadError(RuntimeError):
    """DEM download/processing error."""
    pass

class DEM:
    """
    Downloads an SRTM DEM (Digital Elevation Model, ~30 m) without an API
    key via the Skadi tiles hosted on AWS, then mosaics and clips it to
    an extent (EPSG:4326).

    Parameters
    ----------
    work_dir : working directory for intermediate files.
    timeout : maximum delay (in seconds) per HTTP request.
    keep_intermediate : if True, keeps the .hgt.gz and .tif tiles.
    output_dir : deprecated alias for work_dir (backward compatibility).

    Example
    -------
    >>> dem = DEM(work_dir="_dem_tiles", timeout=180)
    >>> chemin = dem.download(bbox=(-8, 4, -2, 11), out_tif="srtm_ci.tif")
    """

    def __init__(
        self,
        work_dir: Union[str, Path] = "_dem_tiles",
        timeout: int = 180,
        keep_intermediate: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if output_dir is not None:
            if work_dir != "_dem_tiles":
                warnings.warn(
                    "Les paramètres 'work_dir' et 'output_dir' sont tous deux fournis. "
                    "'output_dir' est prioritaire.",
                    UserWarning,
                    stacklevel=2,
                )
            work_dir = output_dir

        self.work_dir = Path(work_dir)
        self.timeout = int(timeout)
        self.keep_intermediate = bool(keep_intermediate)

        self.gz_dir = self.work_dir / "hgt_gz"
        self.tif_dir = self.work_dir / "tile_tif"
        self.gz_dir.mkdir(parents=True, exist_ok=True)
        self.tif_dir.mkdir(parents=True, exist_ok=True)

        # Public endpoint (no key)
        self._base_url = "https://s3.amazonaws.com/elevation-tiles-prod/skadi"

        # P3: HTTP cache to avoid re-downloads
        self._session = CachedSession(
            cache_name=str(self.work_dir / ".http_cache"),
            backend="filesystem",
            expire_after=datetime.timedelta(days=30),
        )

    # -----------------------
    # Helpers (private)
    # -----------------------
    @staticmethod
    def _lat_code(lat: int) -> str:
        return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"

    @staticmethod
    def _lon_code(lon: int) -> str:
        return f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"

    def _skadi_url(self, lat_ll: int, lon_ll: int) -> str:
        latc = self._lat_code(lat_ll)
        lonc = self._lon_code(lon_ll)
        return f"{self._base_url}/{latc}/{latc}{lonc}.hgt.gz"

    # Expected size of a 1-arc-second SRTM .hgt.gz file (3601×3601 × 2 bytes)
    _HGT_RAW_SIZE = 3601 * 3601 * 2  # 25,934,402 uncompressed bytes
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 2  # seconds, doubled on each attempt

    @staticmethod
    def _validate_bbox(bbox: BBox) -> None:
        west, south, east, north = bbox
        if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
            raise ValueError("Longitude hors limites [-180, 180].")
        if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
            raise ValueError("Latitude hors limites [-90, 90].")
        if south >= north:
            raise ValueError("BBox invalide: 'south' doit être < 'north'.")

    @staticmethod
    def _split_antimeridian_bbox(bbox: BBox) -> List[BBox]:
        """Splits a bbox crossing the antimeridian into two valid bboxes."""
        west, south, east, north = bbox
        if west <= east:
            return [bbox]
        # west > east → crosses the antimeridian
        return [
            (west, south, 180.0, north),   # eastern part
            (-180.0, south, east, north),  # western part
        ]

    @staticmethod
    def _iter_degree_tiles_for_bbox(bbox: BBox) -> List[Tuple[int, int]]:
        """
        Returns the list of 1°x1° tiles (lat_ll, lon_ll) covering the bbox.
        """
        west, south, east, north = bbox

        lat_start = math.floor(south)
        lat_end = math.ceil(north) - 1
        lon_start = math.floor(west)
        lon_end = math.ceil(east) - 1

        tiles: List[Tuple[int, int]] = []
        for lat_ll in range(lat_start, lat_end + 1):
            for lon_ll in range(lon_start, lon_end + 1):
                tiles.append((lat_ll, lon_ll))
        return tiles

    def _download_file(self, url: str, dst: Path, allow_missing: bool = False) -> bool:
        """Downloads a file with retry and atomic writing.

        Returns True if the file was downloaded (or already existed),
        False if the tile doesn't exist on the server (HTTP 403/404)
        and allow_missing=True.
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size > 0:
            return True

        tmp_dst = dst.with_suffix(dst.suffix + ".part")
        try:
            if tmp_dst.exists():
                tmp_dst.unlink()
        except OSError:
            pass

        last_exc: Optional[Exception] = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                with self._session.get(url, stream=True, timeout=self.timeout) as r:
                    # R4: missing tile (ocean) → don't raise an error
                    if r.status_code in (403, 404) and allow_missing:
                        return False
                    if not r.ok:
                        raise DEMDownloadError(
                            f"Échec téléchargement {url} (HTTP {r.status_code})."
                        )
                    with open(tmp_dst, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)

                if not tmp_dst.exists() or tmp_dst.stat().st_size == 0:
                    raise DEMDownloadError(f"Téléchargement incomplet ou vide: {url}")

                # R3: integrity check — the decompressed .hgt.gz must
                # contain exactly _HGT_RAW_SIZE bytes
                try:
                    with gzip.open(tmp_dst, "rb") as gz:
                        raw = gz.read()
                    if len(raw) != self._HGT_RAW_SIZE:
                        raise DEMDownloadError(
                            f"Intégrité : {dst.name} → {len(raw)} octets "
                            f"(attendu {self._HGT_RAW_SIZE})."
                        )
                except (gzip.BadGzipFile, OSError) as e:
                    raise DEMDownloadError(
                        f"Fichier corrompu (décompression échouée) : {dst.name}"
                    ) from e

                tmp_dst.replace(dst)
                return True

            except DEMDownloadError:
                last_exc = None
                # Don't retry unrecoverable errors
                try:
                    if tmp_dst.exists():
                        tmp_dst.unlink()
                except OSError:
                    pass
                raise
            except (requests.RequestException, OSError) as exc:
                last_exc = exc
                wait = self._RETRY_BACKOFF * (2 ** (attempt - 1))
                warnings.warn(
                    f"Tentative {attempt}/{self._MAX_RETRIES} échouée pour {url} "
                    f"({exc}). Nouvel essai dans {wait}s…",
                    UserWarning,
                    stacklevel=2,
                )
                time.sleep(wait)
                try:
                    if tmp_dst.exists():
                        tmp_dst.unlink()
                except OSError:
                    pass

        # All attempts exhausted
        try:
            if tmp_dst.exists():
                tmp_dst.unlink()
        except OSError:
            pass
        raise DEMDownloadError(
            f"Échec après {self._MAX_RETRIES} tentatives pour {url}"
        ) from last_exc

    @staticmethod
    def _make_nodata_geotiff(tif_path: Path, lat_ll: int, lon_ll: int) -> None:
        """Creates a GeoTIFF tile filled with nodata (missing ocean tile)."""
        arr = np.full((3601, 3601), -32768, dtype=np.int16)
        res = 1.0 / 3600.0
        transform = Affine(
            res, 0.0, lon_ll - res / 2.0,
            0.0, -res, (lat_ll + 1) + res / 2.0,
        )
        profile = {
            "driver": "GTiff", "height": 3601, "width": 3601,
            "count": 1, "dtype": np.int16, "crs": "EPSG:4326",
            "transform": transform, "compress": "deflate",
            "predictor": 2, "tiled": True,
            "blockxsize": 256, "blockysize": 256, "nodata": -32768,
        }
        tif_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(tif_path, "w", **profile) as dst:
            dst.write(arr, 1)

    @staticmethod
    def _hgt_gz_to_geotiff(hgt_gz: Path, tif_path: Path, lat_ll: int, lon_ll: int) -> None:
        """
        Converts a .hgt.gz tile (3601×3601, big-endian int16) into a GeoTIFF (EPSG:4326).
        """
        with gzip.open(hgt_gz, "rb") as gz:
            raw = gz.read()

        arr = np.frombuffer(raw, dtype=">i2")
        if arr.size != 3601 * 3601:
            raise DEMDownloadError(
                f"Taille inattendue pour {hgt_gz.name}: {arr.size} valeurs."
            )

        arr = arr.reshape((3601, 3601)).astype(np.int16)

        res = 1.0 / 3600.0  # 1 arc-second in degrees

        transform = Affine(
            res, 0.0, lon_ll - res / 2.0,
            0.0, -res, (lat_ll + 1) + res / 2.0
        )

        profile = {
            "driver": "GTiff",
            "height": arr.shape[0],
            "width": arr.shape[1],
            "count": 1,
            "dtype": arr.dtype,
            "crs": "EPSG:4326",
            "transform": transform,
            "compress": "deflate",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
            "nodata": -32768,
        }

        tif_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(tif_path, "w", **profile) as dst:
            dst.write(arr, 1)

    def _cleanup(self) -> None:
        if self.keep_intermediate:
            return

        for p in self.gz_dir.glob("*.hgt.gz"):
            try:
                p.unlink()
            except OSError:
                pass
        for p in self.tif_dir.glob("*.tif"):
            try:
                p.unlink()
            except OSError:
                pass

    # -----------------------
    # Public API
    # -----------------------
    def _download_and_convert_tile(
        self, lat_ll: int, lon_ll: int
    ) -> Path:
        """Downloads and converts a single tile. Returns the GeoTIFF path."""
        url = self._skadi_url(lat_ll, lon_ll)
        gz_path = self.gz_dir / f"{self._lat_code(lat_ll)}{self._lon_code(lon_ll)}.hgt.gz"

        downloaded = self._download_file(url, gz_path, allow_missing=True)

        tif_path = self.tif_dir / f"{self._lat_code(lat_ll)}{self._lon_code(lon_ll)}.tif"
        if not tif_path.exists() or tif_path.stat().st_size == 0:
            if downloaded:
                self._hgt_gz_to_geotiff(gz_path, tif_path, lat_ll, lon_ll)
            else:
                self._make_nodata_geotiff(tif_path, lat_ll, lon_ll)

        return tif_path

    def download(
        self,
        bbox: BBox,
        out_tif: Union[str, Path],
        verbose: bool = True,
        max_workers: int = 4,
    ) -> Path:
        """
        Downloads an SRTM DEM (~30 m) for an extent (EPSG:4326),
        without an API key, via Skadi.

        Parameters
        ----------
        bbox : (west, south, east, north) or GeoDataFrame.
               If west > east, the bbox is automatically split into
               two parts on either side of the antimeridian.
        out_tif : path to the final GeoTIFF (mosaic + bbox clip).
        verbose : if True, shows a tqdm progress bar.
        max_workers : number of threads for parallel downloading.
                      Set to 1 for a sequential download.

        Returns
        ------
        Path to the final GeoTIFF.
        """
        if isinstance(bbox, gpd.GeoDataFrame):
            bbox = tuple(bbox.total_bounds)  # type: ignore[assignment]

        west, south, east, north = bbox
        sub_bboxes = self._split_antimeridian_bbox(bbox)
        for sb in sub_bboxes:
            self._validate_bbox(sb)

        out_tif = Path(out_tif)

        # Collect every tile from every sub-bbox
        all_tiles: List[Tuple[int, int]] = []
        for sb in sub_bboxes:
            all_tiles.extend(self._iter_degree_tiles_for_bbox(sb))
        all_tiles = list(dict.fromkeys(all_tiles))

        # F5 + P1: parallel download
        tile_tifs: List[Path] = []
        n_workers = max(1, min(max_workers, len(all_tiles)))

        if n_workers == 1:
            # Sequential (backward compatibility / debug)
            iterator = (
                tqdm(all_tiles, desc="Téléchargement DEM", unit="tuile")
                if verbose else all_tiles
            )
            for lat_ll, lon_ll in iterator:
                tile_tifs.append(self._download_and_convert_tile(lat_ll, lon_ll))
        else:
            # Parallel
            futures = {}
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                for lat_ll, lon_ll in all_tiles:
                    fut = pool.submit(self._download_and_convert_tile, lat_ll, lon_ll)
                    futures[fut] = (lat_ll, lon_ll)

                pbar = tqdm(
                    total=len(futures), desc="Téléchargement DEM", unit="tuile",
                    disable=not verbose,
                )
                for fut in as_completed(futures):
                    fut.result()  # propagates exceptions
                    pbar.update(1)
                pbar.close()

            # Reconstruct tile order (important for the mosaic)
            for lat_ll, lon_ll in all_tiles:
                tif_path = self.tif_dir / f"{self._lat_code(lat_ll)}{self._lon_code(lon_ll)}.tif"
                tile_tifs.append(tif_path)

        # P2: mosaic — rio_merge accepts open datasets,
        # we close them properly via ExitStack
        with ExitStack() as stack:
            srcs = [stack.enter_context(rasterio.open(p)) for p in tile_tifs]
            mosaic, mosaic_transform = rio_merge(srcs)
            mosaic = mosaic[0]  # band 1
            crs = srcs[0].crs

        # Bbox clipping — for the antimeridian we use the mosaic's
        # bounding bbox (which already covers the right tiles), then
        # clip normally on each sub-bbox.
        if len(sub_bboxes) == 1:
            clip_bounds = sub_bboxes[0]
        else:
            # Antimeridian: clip on the mosaic's total extent
            clip_bounds = (
                min(sb[0] for sb in sub_bboxes),
                south,
                max(sb[2] for sb in sub_bboxes),
                north,
            )

        cw, cs, ce, cn = clip_bounds
        window = from_bounds(cw, cs, ce, cn, transform=mosaic_transform)
        row_off = max(0, int(math.floor(window.row_off)))
        col_off = max(0, int(math.floor(window.col_off)))
        row_end = min(mosaic.shape[0], int(math.ceil(window.row_off + window.height)))
        col_end = min(mosaic.shape[1], int(math.ceil(window.col_off + window.width)))

        if row_end <= row_off or col_end <= col_off:
            raise DEMDownloadError("Fenêtre de découpe invalide pour la bbox demandée.")

        height, width = row_end - row_off, col_end - col_off
        clipped = mosaic[row_off: row_off + height, col_off: col_off + width]

        new_transform = mosaic_transform * Affine.translation(col_off, row_off)

        profile = {
            "driver": "GTiff",
            "height": clipped.shape[0],
            "width": clipped.shape[1],
            "count": 1,
            "dtype": clipped.dtype,
            "crs": crs,
            "transform": new_transform,
            "compress": "deflate",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
            "nodata": -32768,
        }

        out_tif.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_tif, "w", **profile) as dst:
            dst.write(clipped, 1)

        self._cleanup()
        return out_tif

    def sources(self) -> pd.DataFrame:
        """Returns a table of the data sources used by this class."""
        return pd.DataFrame([
            {
                "name": "AWS Terrain Tiles (SRTM, Skadi format)",
                "url": "https://registry.opendata.aws/terrain-tiles/",
                "description": "SRTM digital elevation model ~30 m, no API key needed (used by download()).",
            },
        ])

    # -----------------------
    # Analysis & visualization
    # -----------------------

    @staticmethod
    def info(tif_path: Union[str, Path]) -> dict:
        """
        Displays and returns the metadata of a DEM GeoTIFF.

        Parameters
        ----------
        tif_path : path to a GeoTIFF.

        Returns
        ------
        dict with keys: crs, transform, resolution, bounds, shape, nodata,
                         dtype, stats (min, max, mean, std).
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            arr = ds.read(1, masked=True)
            res_x, res_y = ds.res
            meta = {
                "chemin": str(tif_path),
                "crs": str(ds.crs),
                "transform": ds.transform,
                "résolution": (res_x, abs(res_y)),
                "emprise": ds.bounds,
                "dimensions": (ds.height, ds.width),
                "nodata": ds.nodata,
                "dtype": str(ds.dtypes[0]),
                "stats": {
                    "min": float(arr.min()) if arr.count() > 0 else None,
                    "max": float(arr.max()) if arr.count() > 0 else None,
                    "moyenne": float(arr.mean()) if arr.count() > 0 else None,
                    "écart-type": float(arr.std()) if arr.count() > 0 else None,
                },
            }
        # Readable display
        logger.info(f"── Informations MNT : {tif_path.name} ──")
        logger.info(f"  CRS           : {meta['crs']}")
        logger.info(f"  Dimensions    : {meta['dimensions'][0]} × {meta['dimensions'][1]} pixels")
        logger.info(f"  Résolution    : {meta['résolution'][0]:.6f}° × {meta['résolution'][1]:.6f}°")
        logger.info(f"  Emprise       : {meta['emprise']}")
        logger.info(f"  Nodata        : {meta['nodata']}")
        stats = meta["stats"]
        if stats["min"] is not None:
            logger.info(f"  Altitude      : {stats['min']:.1f} m → {stats['max']:.1f} m "
                  f"(moy. {stats['moyenne']:.1f} m, σ {stats['écart-type']:.1f} m)")
        return meta

    @staticmethod
    def hillshade(
        tif_path: Union[str, Path],
        out_path: Optional[Union[str, Path]] = None,
        azimuth: float = 315.0,
        altitude: float = 45.0,
        z_factor: float = 1.0,
    ) -> np.ndarray:
        """
        Computes a hillshade from a DEM GeoTIFF.

        Parameters
        ----------
        tif_path  : path to the source GeoTIFF.
        out_path  : if provided, saves the hillshade as a GeoTIFF.
        azimuth   : solar azimuth in degrees (default 315 = northwest).
        altitude  : solar elevation in degrees (default 45).
        z_factor  : vertical exaggeration of the relief (default 1 = real;
                    2-3 clearly emphasizes slopes).

        Returns
        ------
        ndarray (float32) of the hillshade (0-255).
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            transform = ds.transform
            profile = ds.profile.copy()

        # Mask nodata
        if nodata is not None:
            elev[elev == nodata] = np.nan

        # Resolution in meters (approximation for EPSG:4326)
        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)
        # deg → m conversion (average-latitude approximation)
        lat_center = transform.f - (elev.shape[0] / 2) * cellsize_y
        m_per_deg = 111_320 * math.cos(math.radians(lat_center))
        dx = cellsize_x * m_per_deg
        dy = cellsize_y * m_per_deg

        # Gradients
        dzdx = z_factor * (
            np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)
        ) / (2 * dx)
        dzdy = z_factor * (
            np.roll(elev, 1, axis=0) - np.roll(elev, -1, axis=0)
        ) / (2 * dy)

        # Solar angles
        az_rad = math.radians(360 - azimuth + 90)
        alt_rad = math.radians(altitude)

        slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        aspect_rad = np.arctan2(-dzdy, dzdx)

        hs = (
            np.sin(alt_rad) * np.cos(slope_rad)
            + np.cos(alt_rad) * np.sin(slope_rad)
            * np.cos(az_rad - aspect_rad)
        )
        hs = np.clip(hs * 255, 0, 255).astype(np.float32)
        hs = np.nan_to_num(hs, nan=0.0)

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            profile.update(dtype="float32", count=1, nodata=0, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(hs, 1)

        return hs

    @staticmethod
    def slope(
        tif_path: Union[str, Path],
        out_path: Optional[Union[str, Path]] = None,
        degrees: bool = True,
    ) -> np.ndarray:
        """
        Computes the slope from a DEM GeoTIFF.

        Parameters
        ----------
        tif_path : path to the source GeoTIFF.
        out_path : if provided, saves it as a GeoTIFF.
        degrees  : if True, returns degrees; otherwise radians.

        Returns
        ------
        ndarray (float32) of the slope.
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            transform = ds.transform
            profile = ds.profile.copy()

        if nodata is not None:
            elev[elev == nodata] = np.nan

        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)
        lat_center = transform.f - (elev.shape[0] / 2) * cellsize_y
        m_per_deg = 111_320 * math.cos(math.radians(lat_center))
        dx = cellsize_x * m_per_deg
        dy = cellsize_y * m_per_deg

        dzdx = (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)) / (2 * dx)
        dzdy = (np.roll(elev, 1, axis=0) - np.roll(elev, -1, axis=0)) / (2 * dy)

        slp = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        if degrees:
            slp = np.degrees(slp)
        slp = np.nan_to_num(slp, nan=0.0).astype(np.float32)

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            profile.update(dtype="float32", count=1, nodata=0, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(slp, 1)

        return slp

    @staticmethod
    def aspect(
        tif_path: Union[str, Path],
        out_path: Optional[Union[str, Path]] = None,
    ) -> np.ndarray:
        """
        Computes the aspect (orientation) from a DEM GeoTIFF.

        Parameters
        ----------
        tif_path : path to the source GeoTIFF.
        out_path : if provided, saves it as a GeoTIFF.

        Returns
        ------
        ndarray (float32) of the orientation in degrees (0-360, 0 = north, clockwise).
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            transform = ds.transform
            profile = ds.profile.copy()

        if nodata is not None:
            elev[elev == nodata] = np.nan

        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)
        lat_center = transform.f - (elev.shape[0] / 2) * cellsize_y
        m_per_deg = 111_320 * math.cos(math.radians(lat_center))
        dx = cellsize_x * m_per_deg
        dy = cellsize_y * m_per_deg

        dzdx = (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)) / (2 * dx)
        dzdy = (np.roll(elev, 1, axis=0) - np.roll(elev, -1, axis=0)) / (2 * dy)

        # Convention: 0 = north, 90 = east, 180 = south, 270 = west
        asp = np.degrees(np.arctan2(-dzdx, dzdy))
        asp = np.where(asp < 0, asp + 360, asp)
        asp = np.nan_to_num(asp, nan=-1.0).astype(np.float32)

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            profile.update(dtype="float32", count=1, nodata=-1, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(asp, 1)

        return asp

    @staticmethod
    def plot(
        tif_path: Union[str, Path],
        cmap: str = "terrain",
        title: Optional[str] = None,
        figsize: Tuple[int, int] = (10, 8),
        hillshade_alpha: float = 0.35,
        colorbar: bool = True,
    ) -> None:
        """
        Displays a quick preview of the DEM with an overlaid hillshade.

        Parameters
        ----------
        tif_path        : path to the GeoTIFF.
        cmap            : matplotlib color palette (default 'terrain').
        title           : optional figure title.
        figsize         : figure size (width, height).
        hillshade_alpha : hillshade transparency (0 = invisible, 1 = opaque).
        colorbar        : if True, adds a colorbar.
        """
        import matplotlib.pyplot as plt

        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            bounds = ds.bounds

        if nodata is not None:
            elev[elev == nodata] = np.nan

        hs = DEM.hillshade(tif_path)

        extent = (bounds.left, bounds.right, bounds.bottom, bounds.top)

        fig, ax = plt.subplots(1, 1, figsize=figsize)
        im = ax.imshow(
            elev, cmap=cmap, extent=extent, origin="upper", aspect="auto",
        )
        ax.imshow(
            hs, cmap="gray", extent=extent, origin="upper",
            alpha=hillshade_alpha, aspect="auto",
        )
        if colorbar:
            cbar = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
            cbar.set_label("Altitude (m)")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        if title:
            ax.set_title(title)
        else:
            ax.set_title(f"MNT — {tif_path.name}")
        plt.tight_layout()
        plt.show()

    @staticmethod
    def reproject(
        tif_path: Union[str, Path],
        out_path: Union[str, Path],
        dst_crs: str = "EPSG:3857",
        resampling: str = "bilinear",
    ) -> Path:
        """
        Reprojects a DEM GeoTIFF to another CRS.

        Parameters
        ----------
        tif_path   : path to the source GeoTIFF (EPSG:4326).
        out_path   : path to the reprojected GeoTIFF.
        dst_crs    : target CRS (default 'EPSG:3857').
        resampling : resampling method ('nearest', 'bilinear',
                     'cubic', 'lanczos'...). Default 'bilinear'.

        Returns
        ------
        Path to the reprojected GeoTIFF.
        """
        resampling_methods = {
            "nearest": Resampling.nearest,
            "bilinear": Resampling.bilinear,
            "cubic": Resampling.cubic,
            "lanczos": Resampling.lanczos,
        }
        if resampling not in resampling_methods:
            raise ValueError(
                f"Méthode de rééchantillonnage inconnue : '{resampling}'. "
                f"Valeurs possibles : {list(resampling_methods.keys())}"
            )

        tif_path = Path(tif_path)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(tif_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds,
            )
            profile = src.profile.copy()
            profile.update(
                crs=dst_crs,
                transform=transform,
                width=width,
                height=height,
                compress="deflate",
                predictor=2,
                tiled=True,
                blockxsize=256,
                blockysize=256,
            )

            with rasterio.open(out_path, "w", **profile) as dst:
                for band in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band),
                        destination=rasterio.band(dst, band),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=resampling_methods[resampling],
                    )
        return out_path
