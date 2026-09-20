from __future__ import annotations

import pandas as pd
import geopandas as gpd
import numpy as np
import os
from pathlib import Path
import rasterio
import datetime
import logging

logger = logging.getLogger(__name__)


def load(filepath,layer=None):
    """
    Loads a vector or raster file based on its extension.

    Parameters:
        filepath : str
            Full path to the file to load. The extension determines the data type.
        layer : str, optional
            For multi-layer files (.gpkg, GPX), specifies the layer to load
            (e.g.: "zones", "tracks", "waypoints"). Defaults to None = default layer.

    Returns:
        - geopandas.GeoDataFrame: For vector files (.shp, .geojson, .gpkg, .kml, .gpx)
        - pandas.DataFrame: For tabular files (.csv, .parquet)
        - rasterio.io.DatasetReader: For raster files (.tif, .tiff).
          Data access: .read(1), metadata: .meta, CRS: .crs,
          transform: .transform, extent: .bounds.
          Remember to close the file after use with .close() or use a context manager.

    Supported formats:
        Vector: shp, geojson, gpkg, kml, gpx, csv, parquet
        Raster: tif, tiff

    Examples:
        >>> # Load a shapefile
        >>> gdf = load("data/ma_carte.shp")

        >>> # Load a GeoJSON file
        >>> gdf = load("data/ma_carte.geojson")

        >>> # Load a raster file
        >>> raster = load("data/elevation.tif")

    Raises:
        ValueError: If the file format is not supported
        RuntimeError: If an error occurs while reading the file
    """
    # Convert filepath to a string in case it's a Path object
    filepath_str = str(filepath)
    ext = filepath_str.split('.')[-1].lower()

    # Vector formats
    vector_exts = ['shp', 'geojson', 'gpkg', 'kml', 'gpx', 'csv', 'parquet']
    raster_exts = ['tif', 'tiff']

    if ext in vector_exts:
        if ext in ['shp', 'geojson', 'gpkg']:
            # `layer` only matters for multi-layer containers (.gpkg);
            # gpd ignores it for shp/geojson, None = default layer.
            return gpd.read_file(filepath, layer=layer) if layer else gpd.read_file(filepath)
        elif ext == 'kml':
            try:
                return gpd.read_file(filepath, driver="LIBKML")
            except Exception as e:
                raise RuntimeError(f"Erreur lors de la lecture KML : {e}")
        elif ext == 'gpx':
            try:
                return gpd.read_file(filepath, layer=layer or "tracks")
            except Exception as e:
                raise RuntimeError(f"Erreur lors de la lecture GPX : {e}")
        elif ext == 'csv':
            return pd.read_csv(filepath)
        elif ext == 'parquet':
            return pd.read_parquet(filepath)
    # Loading raster data
    elif ext in raster_exts:
        try:
            return rasterio.open(filepath)
        except Exception as e:
            raise RuntimeError(f"Erreur lors de la lecture raster : {e}")
    else:
        raise ValueError(f"Format '{ext}' non supporté pour le chargement.")

def describe(filepath) -> dict:
    """
    Displays a summary of the layers and metadata of a geospatial file.

    Parameters:
        filepath : str or Path
            Path to the file to describe.

    Returns:
        dict: Dictionary containing the file's metadata:
            - type: "vector", "raster" or "tabular"
            - format: file extension
            - layers: list of dicts describing each layer
            - nb_layers: number of layers

    Examples:
        >>> describe("data/gadm41_CIV.gpkg")
        >>> describe("data/elevation.tif")
    """
    import pyogrio

    filepath_str = str(filepath)
    ext = filepath_str.split('.')[-1].lower()

    vector_exts = ['shp', 'geojson', 'gpkg', 'kml', 'gpx']
    raster_exts = ['tif', 'tiff']
    tabular_exts = ['csv', 'parquet']

    result = {"path": filepath_str, "format": ext}

    if ext in raster_exts:
        result["type"] = "raster"
        try:
            with rasterio.open(filepath) as src:
                result["nb_layers"] = src.count
                result["layers"] = []
                for i in range(1, src.count + 1):
                    band = {
                        "band": i,
                        "dtype": str(src.dtypes[i - 1]),
                        "nodata": src.nodata,
                    }
                    result["layers"].append(band)
                result["crs"] = str(src.crs) if src.crs else None
                result["dimensions"] = {"width": src.width, "height": src.height}
                result["bounds"] = {
                    "left": src.bounds.left, "bottom": src.bounds.bottom,
                    "right": src.bounds.right, "top": src.bounds.top,
                }
                result["resolution"] = {"x": src.res[0], "y": src.res[1]}
        except Exception as e:
            result["error"] = str(e)

        _print_describe(result)
        return result

    if ext in tabular_exts:
        result["type"] = "tabular"
        try:
            if ext == 'csv':
                df = pd.read_csv(filepath)
            else:
                df = pd.read_parquet(filepath)
            result["nb_layers"] = 1
            result["layers"] = [{
                "name": Path(filepath_str).stem,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
            }]
        except Exception as e:
            result["error"] = str(e)

        _print_describe(result)
        return result

    if ext in vector_exts:
        result["type"] = "vector"
        try:
            layer_table = pyogrio.list_layers(filepath)
            layer_names = [row[0] for row in layer_table]
            result["nb_layers"] = len(layer_names)
            result["layers"] = []
            for layer_name in layer_names:
                try:
                    info = pyogrio.read_info(filepath, layer=layer_name)
                    layer_info = {
                        "name": layer_name,
                        "features": info.get("features", 0),
                        "geometry_types": [info["geometry_type"]] if info.get("geometry_type") else [],
                        "columns": list(info.get("fields", [])),
                        "nb_columns": len(info.get("fields", [])),
                        "crs": info.get("crs", None),
                    }
                    total_bounds = info.get("total_bounds")
                    if total_bounds is not None:
                        layer_info["bounds"] = dict(zip(
                            ["left", "bottom", "right", "top"], total_bounds
                        ))
                    else:
                        layer_info["bounds"] = {}
                except Exception:
                    layer_info = {"name": layer_name, "features": 0,
                                  "geometry_types": [], "columns": [],
                                  "nb_columns": 0, "crs": None, "bounds": {}}
                result["layers"].append(layer_info)
        except Exception as e:
            result["error"] = str(e)

        _print_describe(result)
        return result

    raise ValueError(f"Format '{ext}' non supporté. "
                     f"Formats acceptés : {vector_exts + raster_exts + tabular_exts}")

def _print_describe(info: dict):
    """Displays the describe() summary in a readable way."""
    sep = "=" * 60
    dash = "-" * 56
    logger.info(sep)
    logger.info(f"  Fichier : {info['path']}")
    logger.info(f"  Type    : {info['type']}")
    logger.info(f"  Format  : {info['format']}")

    if "error" in info:
        logger.info(f"  [Erreur] {info['error']}")
        logger.info(sep)
        return

    logger.info(f"  Couches  : {info['nb_layers']}")

    if info["type"] == "raster":
        dims = info.get("dimensions", {})
        logger.info(f"  Dimensions : {dims.get('width')} x {dims.get('height')} pixels")
        res = info.get("resolution", {})
        logger.info(f"  Resolution : {res.get('x'):.6f} x {res.get('y'):.6f}")
        logger.info(f"  CRS : {info.get('crs')}")
        b = info.get("bounds", {})
        logger.info(f"  Emprise : [{b.get('left'):.4f}, {b.get('bottom'):.4f}, "
              f"{b.get('right'):.4f}, {b.get('top'):.4f}]")
        logger.info(f"  {dash}")
        for band in info["layers"]:
            logger.info(f"  Bande {band['band']} : dtype={band['dtype']}, "
                  f"nodata={band['nodata']}")

    elif info["type"] == "vector":
        for layer in info["layers"]:
            logger.info(f"  {dash}")
            logger.info(f"  Couche : {layer['name']}")
            logger.info(f"    Entites   : {layer['features']}")
            logger.info(f"    Geometrie : {', '.join(layer['geometry_types']) if layer['geometry_types'] else 'aucune'}")
            logger.info(f"    Colonnes  : {layer['nb_columns']} -> {layer['columns']}")
            logger.info(f"    CRS       : {layer['crs']}")
            b = layer.get("bounds", {})
            if b:
                logger.info(f"    Emprise   : [{b.get('left', 0):.4f}, {b.get('bottom', 0):.4f}, "
                      f"{b.get('right', 0):.4f}, {b.get('top', 0):.4f}]")

    elif info["type"] == "tabular":
        for layer in info["layers"]:
            logger.info(f"  {dash}")
            logger.info(f"  Table : {layer['name']}")
            logger.info(f"    Lignes   : {layer['rows']}")
            logger.info(f"    Colonnes : {layer['columns']} -> {layer['column_names']}")

    logger.info(sep)

def save(data, file_extension, filename="output", timestamp=False, raster_meta=None):
    """
    Saves a raster or vector file depending on the data type.

    Parameters:
        data : Data to save.
            - For vector data: GeoDataFrame or pandas DataFrame.
            - For raster data: rasterio DatasetReader or numpy array.
        file_extension : str
            Output file extension (e.g.: 'geojson', 'shp', 'tif').
        filename : str, optional
            Base file name (without extension). Defaults to "output".
        timestamp : bool, optional
            If True, adds a timestamp to the file name. Defaults to False.
        raster_meta : dict, optional
            Raster metadata required if `data` is a numpy array.
            Must contain at least: crs, transform, width, height, dtype, count.

    Returns:
        str: Absolute path to the saved file.

    Raises:
        ValueError: If the format is not supported or raster_meta is missing/incomplete.
        TypeError : If the data type is not supported.

    Examples:
        >>> save(gdf, 'geojson', 'ma_carte')
        >>> save(array, 'tif', 'mon_raster', raster_meta=meta)
    """
    # -- Mapping of supported formats ----------------------------------------
    _VECTOR_DRIVERS = {
        'geojson': 'GeoJSON',
        'shp': 'ESRI Shapefile',
        'gpkg': 'GPKG',
        'kml': 'KML',
    }
    _TABULAR_EXTS = {'csv', 'parquet', 'geoparquet', 'xlsx', 'feather'}
    _RASTER_EXTS = {'tif', 'tiff'}
    _ALL_SUPPORTED = set(_VECTOR_DRIVERS) | _TABULAR_EXTS | _RASTER_EXTS

    # -- Normalization / validation -------------------------------------------
    file_extension = file_extension.lower().lstrip('.')
    if file_extension not in _ALL_SUPPORTED:
        raise ValueError(
            f"Format '{file_extension}' non supporté. "
            f"Formats acceptés : {sorted(_ALL_SUPPORTED)}"
        )

    # S1: prevent path traversal (disallow ".." in the path)
    filename = str(filename)
    if ".." in filename:
        raise ValueError("Le chemin ne doit pas contenir '..' (path traversal interdit).")

    if timestamp:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{now}"
    output_path = f"{filename}.{file_extension}"

    # R1: create the parent directory if needed
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # ── VECTOR / TABULAR ────────────────────────────────────────────────────
    if isinstance(data, (gpd.GeoDataFrame, pd.DataFrame)):
        # Native vector formats (via fiona/GDAL)
        if file_extension in _VECTOR_DRIVERS:
            if not isinstance(data, gpd.GeoDataFrame):
                raise TypeError(
                    f"Le format '{file_extension}' nécessite un GeoDataFrame "
                    f"(pas un DataFrame sans géométrie). "
                    f"Utilisez un format tabulaire (csv, parquet, xlsx) pour un DataFrame."
                )
            data.to_file(output_path, driver=_VECTOR_DRIVERS[file_extension])  # type: ignore[call-overload]

        # Tabular formats (geometry dropped except for geoparquet)
        elif file_extension in _TABULAR_EXTS:
            # GeoParquet keeps the geometry
            if file_extension == 'geoparquet':
                if isinstance(data, gpd.GeoDataFrame):
                    data.to_parquet(output_path, index=False)
                else:
                    raise TypeError(
                        "geoparquet nécessite un GeoDataFrame (pas un DataFrame)."
                    )
            else:
                # Drop the geometry, once
                if isinstance(data, gpd.GeoDataFrame):
                    data = data.drop(columns='geometry', errors='ignore')
                if file_extension == 'csv':
                    data.to_csv(output_path, index=False)
                elif file_extension == 'parquet':
                    data.to_parquet(output_path, index=False)
                elif file_extension == 'xlsx':
                    data.to_excel(output_path, index=False)
                elif file_extension == 'feather':
                    data.to_feather(output_path)
        else:
            raise ValueError(
                f"Le format '{file_extension}' n'est pas un format vectoriel/tabulaire. "
                f"Type de données reçu : {type(data).__name__}"
            )

    # ── RASTER ──────────────────────────────────────────────────────────────
    elif isinstance(data, rasterio.io.DatasetReader):  # type: ignore[attr-defined]
        if file_extension not in _RASTER_EXTS:
            raise ValueError(
                f"Un DatasetReader ne peut être sauvegardé qu'en TIFF, "
                f"pas en '{file_extension}'."
            )
        with rasterio.open(output_path, 'w', **data.meta) as dst:
            dst.write(data.read())

    elif isinstance(data, np.ndarray):
        if file_extension not in _RASTER_EXTS:
            raise ValueError(
                f"Un ndarray raster ne peut être sauvegardé qu'en TIFF, "
                f"pas en '{file_extension}'."
            )
        if raster_meta is None:
            raise ValueError("raster_meta est requis pour enregistrer un ndarray.")
        _required_keys = {'crs', 'transform', 'width', 'height', 'dtype', 'count'}
        missing = _required_keys - set(raster_meta)
        if missing:
            raise ValueError(
                f"Clés manquantes dans raster_meta : {sorted(missing)}"
            )
        # B4: 2D ndarray → 3D automatically
        if data.ndim == 2:
            data = data[np.newaxis, :, :]
        with rasterio.open(output_path, 'w', **raster_meta) as dst:
            dst.write(data)

    else:
        raise TypeError(
            f"Type de données non pris en charge : {type(data).__name__}. "
            f"Attendu : GeoDataFrame, DataFrame, DatasetReader ou ndarray."
        )

    abs_path = os.path.abspath(output_path)
    return abs_path

def list_geofiles(folder_path):
    """
    Lists every geospatial file (vector and raster) in a folder.
    """
    geospatial_extensions = ['.shp', '.geojson', '.gpkg', '.kml', '.csv', '.parquet', '.gpx', '.tif', '.tiff']

    files = []
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in geospatial_extensions):
                files.append(os.path.join(root, filename))
    return files
