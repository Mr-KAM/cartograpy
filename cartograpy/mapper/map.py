import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiPoint
from matplotlib.patches import Patch
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import matplotlib.colors as mcolors
import matplotlib.patheffects as patheffects
import importlib.resources
import os
import warnings
from typing import Optional, Union, List, Tuple, Dict, Any
import matplotlib.font_manager as fm
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.transforms import Bbox
from io import BytesIO
from PIL import Image
from pyproj import Geod
import rasterio
from cartograpy.styling import load_cmap, get_available_palettes
import seaborn as sns
from .helpers import read_image
from .bivariate import plot_bivariate_choropleth
from .hexgrid import make_hex_grid, aggregate_to_hex, plot_hexgrid_choropleth
from ._optional_deps import *  # noqa: F401,F403
import logging

logger = logging.getLogger(__name__)


class Map:
    """
    Class to create interactive maps with matplotlib, geopandas, and cartopy.
    Allows adding GeoDataFrames with custom styles.
    Supports international paper formats (A0, A1, A2, A3, A4, B0, B1, B2, B3, C0, C1, C2, C3).
    """

    # Paper format dimensions in millimeters (width x height)
    PAPER_SIZES = {
        # A series (ISO 216)
        "4A0": (1682, 2378),
        "2A0": (1189, 1682),
        "A0": (841, 1189),
        "A1": (594, 841),
        "A2": (420, 594),
        "A3": (297, 420),
        "A4": (210, 297),
        "A5": (148, 210),
        "A6": (105, 148),
        "A7": (74, 105),
        "A8": (52, 74),
        "A9": (37, 52),
        "A10": (26, 37),
        # B series (ISO 216)
        "B0": (1000, 1414),
        "B1": (707, 1000),
        "B2": (500, 707),
        "B3": (353, 500),
        "B4": (250, 353),
        "B5": (176, 250),
        "B6": (125, 176),
        "B7": (88, 125),
        "B8": (62, 88),
        "B9": (44, 62),
        "B10": (31, 44),
        # C series (ISO 269) - mainly for envelopes
        "C0": (917, 1297),
        "C1": (648, 917),
        "C2": (458, 648),
        "C3": (324, 458),
        "C4": (229, 324),
        "C5": (162, 229),
        "C6": (114, 162),
        "C7": (81, 114),
        "C8": (57, 81),
        "C9": (40, 57),
        "C10": (28, 40),
    }

    def __init__(
        self,
        figsize=(12, 8),
        title="",
        projection=ccrs.PlateCarree(),
        data_crs="EPSG:4326",
        dpi=300,
        verbose=False,
        basemap=True,
    ):
        """
        Initializes a new map with cartopy.

        Parameters:
        -----------
        figsize : tuple, str, or dict
            - tuple: Figure size (width, height) in inches
            - str: Paper format (e.g.: 'A4', 'A3', 'B2', 'C1')
            - dict: {'paper': 'A4', 'orientation': 'portrait'/'landscape'}
        title : str
            Map title
        projection : cartopy.crs
            Cartographic projection (defaults to PlateCarree)
        data_crs : str
            Data coordinate system (defaults to WGS84)
        verbose : bool
            Display information messages (defaults to False)
        basemap : bool
            Automatically add coastlines and borders (defaults to True).
            Set to False for a blank map (keeps the cartopy projection,
            useful if you need add_north_arrow/add_scale_bar/add_inset_map
            without the coastlines+borders background).
        """
        self.verbose = verbose
        self.basemap = basemap
        self.figsize = self._process_figsize(figsize)
        self.paper_info = self._get_paper_info(figsize)
        self.dpi = dpi
        self.fig = plt.figure(figsize=self.figsize, dpi=self.dpi)
        self.ax = self.fig.add_subplot(111, projection=projection)
        self.title = title
        self.projection = projection
        self.data_crs = data_crs
        self.layers = []
        self.legend_elements = []
        self.gridlines = None
        self.legend_params = {}
        self.custom_palettes = {}
        self._north_arrow_artist = None
        self._scale_bar_artist = None
        self._north_arrow_kwargs = None
        self._gridline_kwargs = None
        self._background_image_kwargs = None
        self._background_image_artist = None
        self._first_layer = False

        # Basic configuration
        self.ax.set_title(title, fontsize=16, fontweight="bold")

        # Default bounds (whole world)
        self.bounds = [-180, -90, 180, 90]  # [minx, miny, maxx, maxy]

        # Add the default features
        if self.basemap:
            self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
            self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # Display the paper format information
        if self.paper_info:
            self._log(
                f"📄 Format de papier: {self.paper_info['format']} "
                f"({self.paper_info['orientation']}) - "
                f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
                f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
            )

    # --- Internal helpers ---------------------------------------------------

    def _log(self, *args, **kwargs):
        """Displays a message only if verbose is enabled."""
        if self.verbose:
            logger.info(" ".join(str(a) for a in args), **kwargs)

    def _invalidate_render(self):
        """Resets the canvas and flags the layers for re-rendering."""
        self.ax.clear()
        self.ax.set_title(
            self.title,
            fontsize=16 if self.projection else 14,
            fontweight="bold",
        )
        # ax.clear() destroys every artist (including the grid and north
        # arrow): the existing references are now stale.
        self.gridlines = None
        self._north_arrow_artist = None
        if self.projection is not None:
            if self.basemap:
                self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
                self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)
        else:
            self.ax.set_aspect("equal")
        self._reapply_persistent_artists()
        for layer in self.layers:
            layer["rendered"] = False

    def _reapply_persistent_artists(self):
        """Recreates the background image, grid, and north arrow after an
        ax.clear()/fig.clear(): unlike the layers and scale bar, they
        aren't automatically redrawn by _render()."""
        if self._background_image_kwargs is not None:
            self._background_image_artist = None  # the old artist was cleared
            self.add_background_image(**self._background_image_kwargs)
        if self._gridline_kwargs is not None:
            self.add_gridlines(**self._gridline_kwargs)
        if self._north_arrow_kwargs is not None:
            self.add_north_arrow(**self._north_arrow_kwargs)

    def __enter__(self):
        """Context manager support (with Map(...) as m:)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes the matplotlib figure when exiting the context manager."""
        plt.close(self.fig)
        return False

    # ----------------------------------------------------------------------
    # ================Custom paper size ====================================
    # ----------------------------------------------------------------------

    def _process_figsize(self, figsize):
        """
        Processes the figsize parameter to determine the figure size.

        Parameters:
        -----------
        figsize : tuple, str, or dict
            Desired format

        Returns:
        --------
        tuple: Figure size in inches (width, height)
        """
        if isinstance(figsize, tuple):
            return figsize
        elif isinstance(figsize, str):
            return self._paper_to_inches(figsize, "landscape")
        elif isinstance(figsize, dict):
            paper = figsize.get("paper", "A4")
            orientation = figsize.get("orientation", "landscape")
            return self._paper_to_inches(paper, orientation)
        else:
            raise ValueError(
                "figsize doit être un tuple, une chaîne (format papier) ou un dict"
            )

    def _get_paper_info(self, figsize):
        """
        Returns information about the paper format used.

        Parameters:
        -----------
        figsize : tuple, str, or dict
            Desired format

        Returns:
        --------
        dict or None: Paper format information
        """
        if isinstance(figsize, tuple):
            return None
        elif isinstance(figsize, str):
            orientation = "landscape"
            paper = figsize.upper()
        elif isinstance(figsize, dict):
            paper = figsize.get("paper", "A4").upper()
            orientation = figsize.get("orientation", "landscape")
        else:
            return None

        if paper in self.PAPER_SIZES:
            width_mm, height_mm = self.PAPER_SIZES[paper]
            # PAPER_SIZES stores the dimensions in portrait reference
            # (width < height); swap them in landscape to stay consistent
            # with self.figsize (see _paper_to_inches).
            if orientation.lower() == "landscape":
                width_mm, height_mm = height_mm, width_mm
            return {
                "format": paper,
                "orientation": orientation,
                "dimensions_mm": f"{width_mm} x {height_mm}",
                "dimensions_inches": f"{width_mm/25.4:.1f} x {height_mm/25.4:.1f}",
            }
        return None

    def _paper_to_inches(self, paper_format, orientation="landscape"):
        """
        Converts a paper format into inch dimensions for matplotlib.

        Parameters:
        -----------
        paper_format : str
            Paper format (e.g.: 'A4', 'A3', 'B2')
        orientation : str
            'portrait' or 'landscape'

        Returns:
        --------
        tuple: Dimensions in inches (width, height)
        """
        paper_format = paper_format.upper()

        if paper_format not in self.PAPER_SIZES:
            available_formats = ", ".join(sorted(self.PAPER_SIZES.keys()))
            raise ValueError(
                f"Format de papier '{paper_format}' non supporté. "
                f"Formats disponibles: {available_formats}"
            )

        # Get the dimensions in mm
        width_mm, height_mm = self.PAPER_SIZES[paper_format]

        # Convert to inches (1 inch = 25.4 mm)
        width_inches = width_mm / 25.4
        height_inches = height_mm / 25.4

        # Orientation
        if orientation.lower() == "portrait":
            return (width_inches, height_inches)
        elif orientation.lower() == "landscape":
            return (height_inches, width_inches)
        else:
            raise ValueError("orientation doit être 'portrait' ou 'landscape'")

    def set_paper(self, paper_format, orientation="landscape"):
        """
        Sets the map's paper format and orientation.

        Parameters:
        -----------
        paper_format : str
            Paper format (e.g.: 'A4', 'A3', 'B2', 'C1')
        orientation : str
            'portrait' or 'landscape'

        Returns:
        --------
        Map: Map instance for chaining
        """
        # Compute the new dimensions
        new_figsize = self._paper_to_inches(paper_format, orientation)

        # dimensions_mm must follow the same convention as new_figsize
        # (width/height swapped in landscape), otherwise the displayed mm
        # would contradict the inches in the same info string.
        width_mm, height_mm = self.PAPER_SIZES[paper_format.upper()]
        if orientation.lower() == "landscape":
            width_mm, height_mm = height_mm, width_mm

        # Update the information
        self.figsize = new_figsize
        self.paper_info = {
            "format": paper_format.upper(),
            "orientation": orientation,
            "dimensions_mm": f"{width_mm} x {height_mm}",
            "dimensions_inches": f"{new_figsize[0]:.1f} x {new_figsize[1]:.1f}",
        }

        # Resize the figure
        self.fig.set_size_inches(new_figsize[0], new_figsize[1])

        # Display the information
        self._log(
            f"📄 Format mis à jour: {self.paper_info['format']} "
            f"({self.paper_info['orientation']}) - "
            f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
            f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
        )

        return self

    def list_paper_formats(self):
        """
        Displays all available paper formats with their dimensions.

        Returns:
        --------
        Map: Map instance for chaining
        """
        logger.info("📋 Formats de papier disponibles:")
        logger.info("=" * 50)

        # Series A
        logger.info("🅰️  Série A (ISO 216):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("A") or format_name.endswith("A0"):
                logger.info(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        # Series B
        logger.info("\n🅱️  Série B (ISO 216):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("B"):
                logger.info(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        # Series C
        logger.info("\n🅲  Série C (ISO 269 - Enveloppes):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("C"):
                logger.info(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        logger.info("\n Utilisations courantes:")
        logger.info("   A4: Documents, lettres")
        logger.info("   A3: Dessins, plans, affiches")
        logger.info("   A2: Grandes affiches, plans")
        logger.info("   A1: Affiches, plans architecturaux")
        logger.info("   A0: Très grandes affiches, plans")
        logger.info("   B series: Livres, affiches, dépliants")
        logger.info("   C series: Enveloppes")

        return self

    # ----------------------------------------------------------------------
    # ================Add map layer=========================================
    # ----------------------------------------------------------------------

    def _validate_geodataframe(self, gdf, expected_geom_type=None):
        """
        Validates and prepares a GeoDataFrame for display.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame to validate
        expected_geom_type : str, optional
            Expected geometry type ('Point', 'LineString', 'Polygon')

        Returns:
        --------
        gpd.GeoDataFrame: Validated and prepared GeoDataFrame
        """
        if not isinstance(gdf, gpd.GeoDataFrame):
            raise TypeError("Le paramètre doit être un GeoDataFrame")

        if gdf.empty:
            raise ValueError("Le GeoDataFrame ne peut pas être vide")

        # Check the geometry column
        if gdf.geometry.isnull().any():
            self._log(
                "⚠️  Attention: Le GeoDataFrame contient des géométries nulles qui seront ignorées"
            )
            gdf = gdf.dropna(subset=["geometry"])

        # Check the CRS
        if gdf.crs is None:
            msg = f"Aucun CRS défini. Attribution du CRS par défaut: {self.data_crs}"
            warnings.warn(msg, UserWarning, stacklevel=3)
            gdf = gdf.set_crs(self.data_crs)

        # Check the geometry type if specified
        if expected_geom_type:
            geom_types = gdf.geometry.geom_type.unique()
            if not all(geom_type == expected_geom_type for geom_type in geom_types):
                self._log(
                    f"⚠️  Attention: Types de géométries trouvés: {geom_types}. "
                    f"Type attendu: {expected_geom_type}"
                )

        return gdf

    def _add_gdf_layer(self, gdf, layer_type, style_kwargs, label,
                       legend_factory=None, column=None, scheme=None,
                       cmap="viridis", color_key="color"):
        """
        Internal method: shared logic for adding a GeoDataFrame layer.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            Source GeoDataFrame
        layer_type : str
            Layer type ('point', 'line', 'polygon')
        style_kwargs : dict
            Style parameters specific to the type
        label : str
            Legend label
        legend_factory : callable(bool) -> artist, optional
            Function that creates the legend element. Receives use_column (bool).
        column : str, optional
            Column for data-driven coloring
        scheme : str, optional
            Classification scheme
        cmap : str
            Color palette
        color_key : str
            Color key to remove if column is used ('color' or 'facecolor')
        """
        gdf = self._validate_geodataframe(gdf)

        # Reproject to EPSG:4326 for cartopy PlateCarree compatibility
        if gdf.crs is not None and not gdf.crs.equals("EPSG:4326"):
            gdf = gdf.to_crs(epsg=4326)

        plot_kwargs = {
            "ax": self.ax,
            "transform": ccrs.PlateCarree(),
            **style_kwargs,
        }

        # Handle column-based coloring
        use_column = False
        if column and column in gdf.columns:
            plot_kwargs["column"] = column
            if scheme:
                plot_kwargs["scheme"] = scheme
            plot_kwargs["cmap"] = cmap
            plot_kwargs.pop(color_key, None)
            use_column = True

        # Add the layer
        layer_info = {
            "type": layer_type, "name": label, "gdf": gdf, "data": gdf,
            "style": plot_kwargs, "label": label, "src": None,
        }
        self.layers.append(layer_info)

        # Add to the legend
        if label and legend_factory:
            self.legend_elements.append(legend_factory(use_column))

        self._update_bounds(gdf)
        return self

    def _add_raw_layer(self, gdf, layer_type, style_kwargs, label, legend_factory=None):
        """
        Internal method: shared logic for adding a layer from raw coordinates.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame built from the coordinates
        layer_type : str
            Layer type ('point', 'line', 'polygon')
        style_kwargs : dict
            Style parameters
        label : str
            Legend label
        legend_factory : callable() -> artist, optional
            Function that creates the legend element
        """
        layer_info = {
            "type": layer_type, "name": label, "gdf": gdf, "data": gdf,
            "style": style_kwargs, "label": label, "src": None,
        }
        self.layers.append(layer_info)

        if label and legend_factory:
            self.legend_elements.append(legend_factory())

        self._update_bounds(gdf)
        return self

    def add_layer(self, data=None, layer_type="auto", label=None, name=None,
                  style: Optional[Dict[str, Any]] = None, **style_kwargs):
        """
        Adds a generic layer to the map (vector or raster).

        The data type is detected automatically:
        - GeoDataFrame → vector layer (point, line, polygon)
        - numpy.ndarray → raster layer (requires extent in style_kwargs)
        - str (file path) → raster or vector depending on the extension

        Parameters:
        -----------
        data : gpd.GeoDataFrame, numpy.ndarray, str, or None
            Data to add. Can be:
            - a GeoDataFrame (vector layer)
            - a numpy.ndarray (raster layer, provide extent)
            - a str file path (.tif, .shp, .geojson, .gpkg, etc.)
        layer_type : str
            Layer type ('auto', 'point', 'line', 'polygon', 'raster').
            Defaults to 'auto', which detects the type automatically.
        label : str
            Legend label (alias for name, kept for backward compatibility)
        name : str, optional
            Layer name shown in the legend. Takes priority over label.
        style : dict, optional
            Style dictionary with the following keys:
            - font : FontProperties (font for labels, via google_font/local_font/path_font)
            - color : str or list (fill/point/line color)
            - palette : str (color palette, alias for cmap)
            - border : str (border color)
            - border_width : float (border width)
            - column : str (column for data-driven coloring)
            - scheme : str (classification scheme: 'quantiles', 'equal_interval', etc.)
            - alpha : float (transparency 0-1)
            - size : int (point size)
            - marker : str (marker style: 'o', 's', '^', etc.)
            - linewidth : float (line width)
            - linestyle : str (line style: '-', '--', '-.', ':')
            - legend : bool (show in the legend, defaults to True)
        **style_kwargs : dict
            Style parameters specific to the layer type (backward compatible).
            For rasters: cmap, alpha, vmin, vmax, extent, title,
            show_colorbar.
            For vectors: color, facecolor, edge_color, linewidth, etc.
            style_kwargs keys are overridden by those in the style dict.
        """
        # --- Merge the style dict into style_kwargs ---
        if style is not None:
            _STYLE_KEY_MAP = {
                "palette": "cmap",
                "border": "edge_color",
                "border_width": "border_linewidth",
            }
            for key, value in style.items():
                mapped_key = _STYLE_KEY_MAP.get(key, key)
                style_kwargs[mapped_key] = value

        # name takes priority over label
        legend_label = name if name is not None else label

        # Original source (file path), captured before data gets
        # replaced by the loaded GeoDataFrame (vector branch below)
        src = data if isinstance(data, str) else None

        # --- Known raster and vector extensions ---
        _RASTER_EXTENSIONS = (".tif", ".tiff", ".img", ".nc", ".hdf", ".vrt", ".jp2")
        _VECTOR_EXTENSIONS = (
            ".shp", ".geojson", ".json", ".gpkg", ".fgb", ".kml",
            ".gml", ".parquet", ".feather", ".csv", ".xlsx",
        )

        def _extract_raster_kwargs():
            raster_kwargs = {}
            for key in ("cmap", "alpha", "vmin", "vmax", "extent",
                        "title", "show_colorbar", "transform"):
                if key in style_kwargs:
                    raster_kwargs[key] = style_kwargs.pop(key)
            return raster_kwargs

        # --- 1) Explicit raster via layer_type ---
        if layer_type == "raster":
            raster_kwargs = _extract_raster_kwargs()
            if isinstance(data, np.ndarray):
                return self.add_raster(raster_array=data, **raster_kwargs)
            elif isinstance(data, str):
                return self.add_raster(raster_path=data, **raster_kwargs)
            else:
                raise TypeError(
                    "layer_type='raster' nécessite un chemin fichier (str) "
                    "ou un numpy.ndarray."
                )

        # --- 2) numpy.ndarray → raster ---
        if isinstance(data, np.ndarray):
            raster_kwargs = _extract_raster_kwargs()
            return self.add_raster(raster_array=data, **raster_kwargs)

        # --- 3) File path (str) → detection by extension ---
        if isinstance(data, str):
            ext = os.path.splitext(data)[1].lower()
            if ext in _RASTER_EXTENSIONS:
                raster_kwargs = _extract_raster_kwargs()
                return self.add_raster(raster_path=data, **raster_kwargs)
            elif ext in _VECTOR_EXTENSIONS:
                data = gpd.read_file(data)
                # continue on to the vector branch below
            else:
                raise TypeError(
                    f"Extension '{ext}' non reconnue. "
                    f"Extensions raster supportées : {_RASTER_EXTENSIONS}. "
                    f"Extensions vecteur supportées : {_VECTOR_EXTENSIONS}."
                )

        # --- 4) GeoDataFrame → vector layer ---
        if data is None:
            raise ValueError(
                "Fournir data (GeoDataFrame, ndarray ou chemin fichier)."
            )

        if not isinstance(data, gpd.GeoDataFrame):
            raise TypeError(
                f"Type non supporté : {type(data).__name__}. "
                f"Attendu : GeoDataFrame, numpy.ndarray ou str (chemin fichier)."
            )

        gdf = self._validate_geodataframe(data)

        # Automatic detection of the geometry type(s)
        _TYPE_BUCKETS = {
            "point": ("Point", "MultiPoint"),
            "line": ("LineString", "MultiLineString"),
            "polygon": ("Polygon", "MultiPolygon"),
        }
        _mixed_buckets = None

        if layer_type == "auto":
            geom_types = set(gdf.geometry.geom_type.unique())
            if len(geom_types) == 1:
                geom_type = next(iter(geom_types))
                if geom_type in ("Point", "MultiPoint"):
                    layer_type = "point"
                elif geom_type in ("LineString", "MultiLineString"):
                    layer_type = "line"
                elif geom_type in ("Polygon", "MultiPolygon"):
                    layer_type = "polygon"
                else:
                    raise ValueError(f"Type de géométrie non supporté: {geom_type}")
            elif len(geom_types) > 1:
                unrecognized = geom_types - {
                    t for types in _TYPE_BUCKETS.values() for t in types
                }
                if unrecognized:
                    raise ValueError(
                        f"Géométries mixtes détectées: {sorted(geom_types)}. "
                        f"Spécifiez explicitement le layer_type."
                    )
                buckets_present = [
                    bucket for bucket, types in _TYPE_BUCKETS.items()
                    if geom_types & set(types)
                ]
                if len(buckets_present) == 1:
                    layer_type = buckets_present[0]
                else:
                    # Truly mixed geometries (e.g. points + polygons):
                    # one sub-layer per type, each with its own style and
                    # its own legend entry. Without this, everything went
                    # to a single add_*() and the legend only represented
                    # the dominant type (the other geometries ended up
                    # drawn but missing from the legend).
                    _mixed_buckets = buckets_present
            else:
                raise ValueError(
                    "Aucune géométrie exploitable : le GeoDataFrame ne "
                    "contient que des géométries nulles ou vides (elles ont "
                    "été retirées lors de la validation)."
                )

        # --- Prepare the kwargs based on the layer type ---
        def _prepare_kwargs(layer_t):
            kw = dict(style_kwargs)
            # Map border_linewidth → outline linewidth
            bw = kw.pop("border_linewidth", None)
            # font is stored but not sent to the plot methods
            font = kw.pop("font", None)
            # legend controls whether it shows up in the legend
            show_legend = kw.pop("legend", True)
            effective_label = legend_label if show_legend else None

            if layer_t == "polygon":
                # color → facecolor for polygons
                if "color" in kw and "facecolor" not in kw:
                    kw["facecolor"] = kw.pop("color")
                if bw is not None:
                    kw.setdefault("linewidth", bw)
            elif layer_t == "point":
                if bw is not None:
                    kw.setdefault("linewidth", bw)
            elif layer_t == "line":
                if bw is not None:
                    kw.setdefault("linewidth", bw)

            return kw, effective_label, font

        # Truly mixed geometries: one sub-layer per detected type, each
        # with its own style and its own legend entry.
        if _mixed_buckets is not None:
            _SUFFIXES = {"point": "points", "line": "lignes", "polygon": "polygones"}
            _ADD_METHODS = {
                "point": self.add_points,
                "line": self.add_lines,
                "polygon": self.add_polygons,
            }
            result = self
            for bucket in _mixed_buckets:
                sub_gdf = gdf[gdf.geometry.geom_type.isin(_TYPE_BUCKETS[bucket])]
                if sub_gdf.empty:
                    continue
                kw, effective_label, font = _prepare_kwargs(bucket)
                if effective_label is not None:
                    effective_label = f"{effective_label} ({_SUFFIXES[bucket]})"
                sub_name = (
                    f"{legend_label} ({_SUFFIXES[bucket]})"
                    if legend_label is not None else None
                )
                result = _ADD_METHODS[bucket](sub_gdf, label=effective_label, **kw)
                if self.layers:
                    self.layers[-1]["name"] = sub_name
                    self.layers[-1]["src"] = src
                    if font is not None:
                        self.layers[-1]["font"] = font
            return result

        # Add the layer based on the type
        if layer_type == "point":
            kw, effective_label, font = _prepare_kwargs("point")
            result = self.add_points(gdf, label=effective_label, **kw)
        elif layer_type == "line":
            kw, effective_label, font = _prepare_kwargs("line")
            result = self.add_lines(gdf, label=effective_label, **kw)
        elif layer_type == "polygon":
            kw, effective_label, font = _prepare_kwargs("polygon")
            result = self.add_polygons(gdf, label=effective_label, **kw)
        else:
            raise ValueError(f"Type de couche non supporté: {layer_type}")

        # name must survive even if legend=False set label to None
        if self.layers:
            self.layers[-1]["name"] = legend_label
            self.layers[-1]["src"] = src
            if font is not None:
                self.layers[-1]["font"] = font

        return result

    def add_points(
        self,
        gdf,
        label=None,
        color="red",
        size=50,
        marker="o",
        alpha=1.0,
        edge_color="black",
        linewidth=0.5,
        column=None,
        scheme=None,
        cmap="viridis",
        **kwargs,
    ):
        """
        Adds points from a GeoDataFrame.
        To add points from raw coordinates, use add_point().

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame containing Point geometries
        label : str
            Legend label
        color : str, list, or column name
            Point color(s) or column name for coloring
        size : int, list, or column name
            Point size(s) or column name for sizing
        marker : str
            Marker style ('o', 's', '^', etc.)
        alpha : float
            Transparency (0-1)
        edge_color : str
            Outline color
        linewidth : float
            Outline width
        column : str
            Column name for coloring/classification
        scheme : str
            Classification scheme ('quantiles', 'equal_interval', etc.)
        cmap : str
            Color palette
        **kwargs : dict
            Other parameters for geopandas.plot()
        """
        style = {
            "color": color, "markersize": size, "marker": marker,
            "alpha": alpha, "edgecolor": edge_color, "linewidth": linewidth,
            **kwargs,
        }

        def _legend(use_column):
            return plt.scatter(
                [], [], c=color if not use_column else "gray",
                s=size, marker=marker, alpha=alpha,
                edgecolors=edge_color, linewidth=linewidth, label=label,
            )

        return self._add_gdf_layer(
            gdf, "point", style, label, _legend, column, scheme, cmap, "color"
        )

    def add_lines(
        self,
        gdf,
        label=None,
        color="blue",
        linewidth=2,
        linestyle="-",
        alpha=1.0,
        column=None,
        scheme=None,
        cmap="viridis",
        **kwargs,
    ):
        """
        Adds lines from a GeoDataFrame.
        To add lines from raw coordinates, use add_line().

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame containing LineString geometries
        label : str
            Legend label
        color : str, list, or column name
            Line color(s) or column name for coloring
        linewidth : float
            Line width
        linestyle : str
            Line style ('-', '--', '-.', ':')
        alpha : float
            Transparency (0-1)
        column : str
            Column name for coloring/classification
        scheme : str
            Classification scheme ('quantiles', 'equal_interval', etc.)
        cmap : str
            Color palette
        **kwargs : dict
            Other parameters for geopandas.plot()
        """
        style = {
            "color": color, "linewidth": linewidth, "linestyle": linestyle,
            "alpha": alpha, **kwargs,
        }

        def _legend(use_column):
            return plt.Line2D(
                [0], [0], color=color if not use_column else "gray",
                linewidth=linewidth, linestyle=linestyle, alpha=alpha, label=label,
            )

        return self._add_gdf_layer(
            gdf, "line", style, label, _legend, column, scheme, cmap, "color"
        )

    def add_polygons(
        self,
        gdf,
        label=None,
        facecolor="green",
        alpha=0.5,
        edge_color="black",
        linewidth=1,
        column=None,
        scheme=None,
        cmap="viridis",
        **kwargs,
    ):
        """
        Adds polygons from a GeoDataFrame.
        To add polygons from raw coordinates, use add_polygon().

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame containing Polygon geometries
        label : str
            Legend label
        facecolor : str, list, or column name
            Fill color(s) or column name for coloring
        alpha : float
            Transparency (0-1)
        edge_color : str
            Outline color
        linewidth : float
            Outline width
        column : str
            Column name for coloring/classification
        scheme : str
            Classification scheme ('quantiles', 'equal_interval', etc.)
        cmap : str
            Color palette
        **kwargs : dict
            Other parameters for geopandas.plot()
        """
        style = {
            "facecolor": facecolor, "alpha": alpha,
            "edgecolor": edge_color, "linewidth": linewidth,
            **kwargs,
        }

        def _legend(use_column):
            return Patch(
                facecolor=facecolor if not use_column else "gray",
                edgecolor=edge_color, linewidth=linewidth, alpha=alpha, label=label,
            )

        return self._add_gdf_layer(
            gdf, "polygon", style, label, _legend, column, scheme, cmap, "facecolor"
        )

    def add_point(
        self,
        coordinates,
        label=None,
        color="red",
        size=50,
        marker="o",
        alpha=1.0,
        edge_color="black",
        linewidth=0.5,
        transform=None,
    ):
        """
        Adds one or more points to the map.

        Parameters:
        -----------
        coordinates : tuple, list of tuples, or dict
            Coordinates of the point(s). Format: (lon, lat) or [(lon1, lat1), (lon2, lat2), ...]
            Or a dict with 'lon' and 'lat' keys for a DataFrame
        label : str
            Legend label
        color : str or list
            Color(s) of the point(s)
        size : int or list
            Size(s) of the point(s)
        marker : str
            Marker style ('o', 's', '^', etc.)
        alpha : float
            Transparency (0-1)
        edge_color : str
            Outline color
        linewidth : float
            Outline width
        transform : cartopy.crs
            Data projection (defaults to data_crs)
        """
        # Normalize the coordinates
        if isinstance(coordinates, dict):
            points = [
                Point(lon, lat)
                for lon, lat in zip(coordinates["lon"], coordinates["lat"])
            ]
        elif isinstance(coordinates, tuple) and len(coordinates) == 2:
            points = [Point(coordinates[0], coordinates[1])]
        else:
            points = [Point(lon, lat) for lon, lat in coordinates]

        gdf = gpd.GeoDataFrame(geometry=points, crs=self.data_crs)
        if transform is None:
            transform = ccrs.PlateCarree()

        style = {
            "color": color, "markersize": size, "marker": marker,
            "alpha": alpha, "edgecolor": edge_color, "linewidth": linewidth,
            "transform": transform,
        }

        def _legend():
            return plt.scatter(
                [], [], c=color, s=size, marker=marker, alpha=alpha,
                edgecolors=edge_color, linewidth=linewidth, label=label,
            )

        return self._add_raw_layer(gdf, "point", style, label, _legend)

    def add_line(
        self,
        coordinates,
        label=None,
        color="blue",
        linewidth=2,
        linestyle="-",
        alpha=1.0,
        transform=None,
    ):
        """
        Adds one or more lines to the map.

        Parameters:
        -----------
        coordinates : list of tuples or list of lists
            Line coordinates. Format: [(lon1, lat1), (lon2, lat2), ...]
            Or [[(lon1, lat1), (lon2, lat2)], [(lon3, lat3), (lon4, lat4)]] for several lines
        label : str
            Legend label
        color : str
            Line color
        linewidth : float
            Line width
        linestyle : str
            Line style ('-', '--', '-.', ':')
        alpha : float
            Transparency (0-1)
        transform : cartopy.crs
            Data projection (defaults to data_crs)
        """
        # Check the coordinate format
        if isinstance(coordinates[0][0], (int, float)):
            lines = [LineString(coordinates)]
        else:
            lines = [LineString(coord) for coord in coordinates]

        gdf = gpd.GeoDataFrame(geometry=lines, crs=self.data_crs)
        if transform is None:
            transform = ccrs.PlateCarree()

        style = {
            "color": color, "linewidth": linewidth, "linestyle": linestyle,
            "alpha": alpha, "transform": transform,
        }

        def _legend():
            return plt.Line2D(
                [0], [0], color=color, linewidth=linewidth,
                linestyle=linestyle, alpha=alpha, label=label,
            )

        return self._add_raw_layer(gdf, "line", style, label, _legend)

    def add_polygon(
        self,
        coordinates,
        label=None,
        color="green",
        alpha=0.5,
        edge_color="black",
        linewidth=1,
        fill=True,
        transform=None,
    ):
        """
        Adds one or more polygons to the map.

        Parameters:
        -----------
        coordinates : list of tuples or list of lists
            Polygon coordinates. Format: [(lon1, lat1), (lon2, lat2), ...]
            Or [[(lon1, lat1), ...], [(lon3, lat3), ...]] for several polygons
        label : str
            Legend label
        color : str
            Fill color
        alpha : float
            Transparency (0-1)
        edge_color : str
            Outline color
        linewidth : float
            Outline width
        fill : bool
            If True, fills the polygon
        transform : cartopy.crs
            Data projection (defaults to data_crs)
        """
        # Check the coordinate format
        if isinstance(coordinates[0][0], (int, float)):
            polygons = [Polygon(coordinates)]
        else:
            polygons = [Polygon(coord) for coord in coordinates]

        gdf = gpd.GeoDataFrame(geometry=polygons, crs=self.data_crs)
        if transform is None:
            transform = ccrs.PlateCarree()

        style = {
            "color": color if fill else "none",
            "edgecolor": edge_color, "linewidth": linewidth,
            "alpha": alpha, "transform": transform,
        }

        def _legend():
            return Patch(
                facecolor=color if fill else "none",
                edgecolor=edge_color, linewidth=linewidth, alpha=alpha, label=label,
            )

        return self._add_raw_layer(gdf, "polygon", style, label, _legend)

    def add_natural_features(
        self,
        features=None,
        coastline_color="black",
        coastline_width=0.5,
        border_color="gray",
        border_width=0.5,
        land_color=None,
        ocean_color=None,
        lakes=False,
        rivers=False,
    ):
        """
        Adds natural features to the map.

        Parameters:
        -----------
        features : list, optional
            List of features to add ('coastline', 'borders', 'land', 'ocean').
            Defaults to ``['coastline', 'borders']``.
        coastline_color : str
            Coastline color
        coastline_width : float
            Coastline width
        border_color : str
            Border color
        border_width : float
            Border width
        land_color : str
            Land color (optional)
        ocean_color : str
            Ocean color (optional)
        lakes : bool
            Add lakes
        rivers : bool
            Add rivers
        """
        if features is None:
            features = ["coastline", "borders"]

        if "coastline" in features:
            self.ax.coastlines(
                resolution="50m", color=coastline_color, linewidth=coastline_width
            )

        if "borders" in features:
            self.ax.add_feature(
                cfeature.BORDERS, color=border_color, linewidth=border_width
            )

        if "land" in features or land_color:
            self.ax.add_feature(cfeature.LAND, color=land_color or "lightgray")

        if "ocean" in features or ocean_color:
            self.ax.add_feature(cfeature.OCEAN, color=ocean_color or "lightblue")

        if lakes:
            self.ax.add_feature(cfeature.LAKES, alpha=0.8)

        if rivers:
            self.ax.add_feature(cfeature.RIVERS, alpha=0.8)

        return self

    def add_basemap(
        self,
        source=None,
        zoom="auto",
        alpha=1.0,
        attribution=True,
        attribution_size=8,
        crs=None,
    ) -> "Map":
        """
        Adds a basemap (web tiles) via contextily.

        Parameters:
        -----------
        source : contextily provider or str, optional
            Tile provider. Defaults to OpenStreetMap.Mapnik.
            Examples: ctx.providers.Stamen.Terrain, ctx.providers.CartoDB.Positron,
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        zoom : int or 'auto'
            Tile zoom level
        alpha : float
            Basemap transparency (0-1)
        attribution : bool
            Show the provider's attribution
        attribution_size : int
            Attribution font size
        crs : str, optional
            Target CRS (defaults to the map's projection)

        Returns:
        ---------
        Map: Map instance for chaining
        """
        if not HAS_CONTEXTILY:
            raise ImportError(
                "contextily est requis pour add_basemap(). "
                "Installez-le avec : pip install contextily"
            )

        if source is None:
            source = ctx.providers.OpenStreetMap.Mapnik

        try:
            ctx.add_basemap(
                self.ax,
                source=source,
                zoom=zoom,
                alpha=alpha,
                attribution=attribution,
                attribution_size=attribution_size,
                crs=crs or self.projection,
            )
            self._log("\U0001f5fa\ufe0f  Fond de carte ajouté")
        except Exception as e:
            # warnings.warn (not self._log): a silent failure with
            # verbose=False would give the false impression that the
            # basemap was added when it wasn't.
            warnings.warn(
                f"\u00c9chec de l'ajout du fond de carte (contextily) : {e}",
                RuntimeWarning, stacklevel=2,
            )

        return self

    def _draw_inset_data_indicator(
        self, inset_ax, bounds, data_gdf, mode,
        facecolor, edgecolor, alpha, linewidth, zorder,
    ):
        """Draws on `inset_ax` the `data` area from add_inset_map: its
        actual geometry (mode="geometry") or the rectangle of its extent
        (mode="bbox", or any `data` provided as a bbox)."""
        if mode == "geometry" and data_gdf is not None:
            inset_ax.add_geometries(
                data_gdf.geometry, crs=ccrs.PlateCarree(),
                facecolor=facecolor, edgecolor=edgecolor,
                alpha=alpha, linewidth=linewidth, zorder=zorder,
            )
        else:
            minx, miny, maxx, maxy = bounds
            rect = mpatches.Rectangle(
                (minx, miny), maxx - minx, maxy - miny,
                linewidth=linewidth, edgecolor=edgecolor,
                facecolor=facecolor, alpha=alpha,
                transform=ccrs.PlateCarree(), zorder=zorder,
            )
            inset_ax.add_patch(rect)

    @staticmethod
    def _resolve_on_bounds(on):
        """Total extent [minx, miny, maxx, maxy] of everything passed to
        add_inset_map's `on` parameter (a single GeoDataFrame or a list of
        `{"data": gdf, ...}`)."""
        items = on if isinstance(on, list) else [on]
        all_bounds = np.array([
            (item["data"] if isinstance(item, dict) else item).total_bounds
            for item in items
        ])
        return [
            all_bounds[:, 0].min(), all_bounds[:, 1].min(),
            all_bounds[:, 2].max(), all_bounds[:, 3].max(),
        ]

    def _make_inset_circular(self, inset_ax):
        """Clips `inset_ax` (GeoAxes) into a circle instead of the default
        rectangle, via `set_boundary`. Corrects the axes' physical aspect
        (which isn't always square, e.g. `size=(4, 3)` or a non-square
        `position`) to get a true circle on screen rather than an ellipse.

        A GeoAxes' aspect adjustment (`set_global`/`set_extent`) is lazy —
        its final position (`get_position()`) is only correct after a
        render. So we force a `draw()` before measuring.
        """
        self.fig.canvas.draw()
        pos = inset_ax.get_position()
        fig_w, fig_h = self.fig.get_size_inches()
        box_w, box_h = pos.width * fig_w, pos.height * fig_h
        if box_w >= box_h:
            rx, ry = 0.5 * (box_h / box_w), 0.5
        else:
            rx, ry = 0.5, 0.5 * (box_w / box_h)
        theta = np.linspace(0, 2 * np.pi, 100)
        verts = np.column_stack([
            0.5 + rx * np.cos(theta),
            0.5 + ry * np.sin(theta),
        ])
        inset_ax.set_boundary(mpath.Path(verts), transform=inset_ax.transAxes)

    def add_inset_map(
        self,
        data=None,
        on=None,
        mode: str = "bbox",
        zoom_to_on: bool = False,
        position: Tuple[float, float, float, float] = (0.65, 0.02, 0.33, 0.33),
        to: str = "ax",
        circular: bool = False,
        facecolor="white",
        edgecolor="black",
        linewidth=1.5,
        alpha=0.9,
        box_color="red",
        box_linewidth=2,
        land_color="lightgray",
        ocean_color="lightblue",
        projection=None,
        style: str = "auto",
        location: str = "lower right",
        size: Union[float, Tuple[float, float]] = None,
        pad: Union[float, Tuple[float, float]] = None,
        coords: Tuple[float, float] = None,
        transform=None,
        global_view: bool = True,
        extent: list = None,
        indicator: str = "extent",
        indicator_facecolor: str = "red",
        indicator_linecolor: str = "red",
        indicator_alpha: float = 0.5,
        indicator_linewidth: float = 1,
        indicator_straighten: bool = True,
        indicator_pad: float = 0.05,
        connector_color: str = "black",
        connector_width: float = 1,
        inset_size: str = None,
        zorder: int = 99,
        show_borders: bool = True,
        show_coastlines: bool = True,
        **kwargs,
    ) -> "Map":
        """
        Adds a small situation (inset) map showing the study area within a
        wider geographic context.

        Automatically uses ``matplotlib-map-utils`` if installed for smart
        placement, otherwise falls back to manual placement.

        Parameters:
        -----------
        data : list[float] or GeoDataFrame, optional
            The area to highlight on the inset: either a bbox
            ``[minx, miny, maxx, maxy]``, or a GeoDataFrame (its geometry
            or its extent is used depending on ``mode``).
            Defaults to ``None``, which uses ``self.bounds``.
        on : GeoDataFrame or list, optional
            Context layer(s) to draw on the inset (e.g. every country of a
            continent, to place ``data`` within it). A single GeoDataFrame
            or a list of dicts ``[{"data": gdf, "kwargs": {...}}, ...]``.
        mode : str
            How to draw ``data`` when it is a GeoDataFrame:
            - ``"bbox"`` (default): rectangle matching its extent
              (``total_bounds``).
            - ``"geometry"``: its actual geometry (outline of the polygon(s)).
            Has no effect if ``data`` is already a bbox (always drawn as a
            rectangle).
        zoom_to_on : bool
            If True, zooms the inset to the total extent of ``on`` (instead
            of the global view) and frames it with a rectangle (color
            ``box_color``/``box_linewidth``). Has no effect if ``on`` isn't
            provided. Takes priority over ``global_view``/``extent``.
        position : tuple (x, y, w, h)
            Position and size of the inset, in relative coordinates (0-1)
            of the anchor chosen via ``to`` (classic mode only — has no
            effect in map-utils mode, which uses ``location``/``coords``).
            (x, y) = bottom-left corner.
        to : str
            Positioning anchor: ``"ax"`` (default) — ``position`` (classic
            mode) or ``location``/``coords`` (map-utils mode) relative to
            the main map's axes; ``"fig"`` — relative to the whole figure.
            Same convention as ``add_north_arrow``.
        circular : bool
            If True, clips the inset into a circle instead of a rectangle
            (``Axes.set_boundary``), regardless of the axes' actual shape
            (the aspect is corrected to get a true circle, not an ellipse).
        facecolor : str
            Inset background color.
        edgecolor : str
            Border color.
        linewidth : float
            Border width.
        alpha : float
            Transparency.
        box_color : str
            Color of the rectangle showing the study area (classic mode,
            ``data`` not provided).
        box_linewidth : float
            Width of the rectangle (classic mode, ``data`` not provided).
        land_color : str
            Land color on the inset.
        ocean_color : str
            Ocean color.
        projection : cartopy.crs, optional
            Inset projection (defaults to PlateCarree).
        style : str
            Rendering mode:
            - ``"auto"``: matplotlib-map-utils if available, otherwise classic.
            - ``"map-utils"``: forces map-utils mode.
            - ``"classic"``: fig.add_axes placement (legacy behavior).
        location : str
            Position (map-utils mode): "upper left", "upper right",
            "lower left", "lower right", "center", etc.
        size : float or tuple, optional
            Inset size in inches (map-utils mode). Can be a scalar
            (square) or a tuple (width, height).
        pad : float or tuple, optional
            Padding in inches (map-utils mode).
        coords : tuple (x, y), optional
            Exact position in axes coordinates (map-utils mode).
            Overrides ``location`` if provided.
        transform : matplotlib.transforms.Transform, optional
            Transform for the coordinates (map-utils mode).
        global_view : bool
            If True (default), the inset shows the whole globe via set_global().
            If False, the inset is zoomed to ``extent`` or auto-adjusted.
        extent : list, optional
            [x0, x1, y0, y1] to restrict the inset's extent.
            Useful when ``global_view=False``.
        indicator : str
            Indicator type when ``data`` isn't provided (legacy behavior,
            based on the main axes' current extent): "extent", "detail", or
            "none". Has no effect if ``data`` is provided — the indicator is
            then always drawn from ``data``/``mode``.
        indicator_facecolor : str
            Indicator fill color.
        indicator_linecolor : str
            Indicator border color.
        indicator_alpha : float
            Indicator transparency.
        indicator_linewidth : float
            Indicator line width.
        indicator_straighten : bool
            If True (default), aligns the indicator rectangle with the axes
            (``data`` not provided only).
        indicator_pad : float
            Indicator rectangle padding (default 0.05, ``data`` not
            provided only).
        connector_color : str
            Connector line color ("detail" mode, ``data`` not provided).
        connector_width : float
            Connector line width ("detail" mode, ``data`` not provided).
        inset_size : str, optional
            Preset size ("xs", "sm", "md", "lg", "xl") — map-utils mode.
            Calls ``InsetMap.set_size()`` to adjust the global defaults.
        zorder : int
            Inset z-order (default 99).
        show_borders : bool
            Show borders on the inset (default True).
        show_coastlines : bool
            Show coastlines on the inset (default True).
        **kwargs
            Additional parameters passed to ``InsetMap`` or to the inset
            axes (e.g. ``xticks=[], yticks=[]``).

        Returns:
        ---------
        Map: Map instance for chaining.

        Example:
        --------
        >>> m.add_inset_map(
        ...     data=bound.get_country("Côte d'Ivoire"), mode="geometry",
        ...     on=bound.get_continent("Africa"),
        ... )
        """
        if projection is None:
            projection = ccrs.PlateCarree()

        if mode not in ("bbox", "geometry"):
            raise ValueError(f"mode doit être 'bbox' ou 'geometry', reçu: {mode!r}")
        if to not in ("ax", "fig"):
            raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

        # Resolve `data` into (bbox, optional geometry) --------------------
        data_gdf = None
        if data is None:
            bounds = self.bounds  # [minx, miny, maxx, maxy]
        elif isinstance(data, (gpd.GeoDataFrame, gpd.GeoSeries)):
            data_gdf = data
            bounds = list(data.total_bounds)
            if mode == "geometry" and len(data_gdf) == 0:
                raise ValueError("`data` est un GeoDataFrame vide.")
        elif isinstance(data, (list, tuple)) and len(data) == 4:
            bounds = list(data)
            if mode == "geometry":
                warnings.warn(
                    "mode='geometry' nécessite un GeoDataFrame pour `data` ; "
                    "une bbox a été fournie, utilisation de mode='bbox'.",
                    RuntimeWarning, stacklevel=2,
                )
                mode = "bbox"
        else:
            raise TypeError(
                "`data` doit être un GeoDataFrame/GeoSeries ou une bbox "
                f"[minx, miny, maxx, maxy], reçu: {type(data).__name__}"
            )

        on_bounds = None
        if zoom_to_on:
            if on is None:
                warnings.warn(
                    "zoom_to_on=True nécessite `on`, ignoré (on=None).",
                    RuntimeWarning, stacklevel=2,
                )
            else:
                on_bounds = self._resolve_on_bounds(on)

        if style == "auto":
            style = "map-utils" if HAS_MAP_UTILS else "classic"

        if style == "map-utils":
            if not HAS_MAP_UTILS:
                warnings.warn(
                    "matplotlib-map-utils n'est pas installé, "
                    "mode classique utilisé. "
                    "Installez-le avec : pip install matplotlib-map-utils",
                    RuntimeWarning, stacklevel=2,
                )
                style = "classic"
            else:
                # Apply set_size() on the global defaults BEFORE creation
                if inset_size is not None:
                    MmuInsetMap.set_size(inset_size)

                # Prepare to_plot (context layer(s))
                to_plot = None
                if on is not None:
                    to_plot = on if isinstance(on, list) else [{"data": on}]

                im_kwargs = dict(location=location, zorder=zorder)
                if size is not None:
                    im_kwargs["size"] = size
                if pad is not None:
                    im_kwargs["pad"] = pad
                if coords is not None:
                    im_kwargs["coords"] = coords
                if transform is not None:
                    im_kwargs["transform"] = transform
                if to_plot is not None:
                    im_kwargs["to_plot"] = to_plot
                im_kwargs.update(kwargs)

                # Create the inset axes via map-utils
                # to="fig": InsetMap always anchors via `pax.inset_axes()`,
                # so relative to the axes passed in — we pass it a ghost
                # axes covering the whole figure (instead of self.ax) so
                # location/coords become relative to the whole figure.
                im = MmuInsetMap(**im_kwargs)
                if to == "fig":
                    host_ax = self.fig.add_axes([0, 0, 1, 1], frameon=False)
                    host_ax.set_axis_off()
                else:
                    host_ax = self.ax
                inset_ax = im.create(host_ax, projection=projection)

                # Global, restricted, or zoomed-to-`on` view
                if on_bounds is not None:
                    minx, miny, maxx, maxy = on_bounds
                    inset_ax.set_extent((minx, maxx, miny, maxy), crs=ccrs.PlateCarree())
                elif global_view:
                    inset_ax.set_global()
                elif extent is not None:
                    inset_ax.set_extent(extent, crs=ccrs.PlateCarree())

                if circular:
                    self._make_inset_circular(inset_ax)

                # Add the cartographic features
                inset_ax.add_feature(cfeature.LAND, facecolor=land_color)
                inset_ax.add_feature(cfeature.OCEAN, facecolor=ocean_color)
                if show_borders:
                    inset_ax.add_feature(
                        cfeature.BORDERS, linewidth=0.3, edgecolor="gray"
                    )
                if show_coastlines:
                    inset_ax.coastlines(resolution="110m", linewidth=0.4)

                # Frame around `on`'s extent (zoom_to_on=True)
                if on_bounds is not None:
                    self._draw_inset_data_indicator(
                        inset_ax, on_bounds, None, "bbox",
                        "none", box_color, 1.0, box_linewidth, zorder,
                    )

                # Apply the visual style
                for spine in inset_ax.spines.values():
                    spine.set_edgecolor(edgecolor)
                    spine.set_linewidth(linewidth)
                inset_ax.patch.set_alpha(alpha)
                inset_ax.patch.set_facecolor(facecolor)

                if data is not None:
                    # `data` explicitly provided: draw exactly what was
                    # requested (bbox or geometry), instead of inferring
                    # the indicator from the main axes' current extent
                    # (legacy behavior below).
                    self._draw_inset_data_indicator(
                        inset_ax, bounds, data_gdf, mode,
                        indicator_facecolor, indicator_linecolor,
                        indicator_alpha, indicator_linewidth, zorder,
                    )
                else:
                    # Extent or detail indicator (legacy behavior, based on
                    # self.ax's current extent)
                    pcrs = self.projection
                    bcrs = projection
                    _indicator_ok = False
                    if indicator == "extent":
                        try:
                            mmu_indicate_extent(
                                pax=inset_ax, bax=self.ax,
                                pcrs=bcrs, bcrs=pcrs,
                                facecolor=indicator_facecolor,
                                linecolor=indicator_linecolor,
                                alpha=indicator_alpha,
                                linewidth=indicator_linewidth,
                                straighten=indicator_straighten,
                                pad=indicator_pad,
                                zorder=zorder,
                            )
                            _indicator_ok = True
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Indicateur extent échoué : {e}")
                            _indicator_ok = False
                    elif indicator == "detail":
                        try:
                            mmu_indicate_detail(
                                pax=self.ax, iax=inset_ax,
                                pcrs=pcrs, icrs=bcrs,
                                facecolor=indicator_facecolor,
                                linecolor=indicator_linecolor,
                                alpha=indicator_alpha,
                                linewidth=indicator_linewidth,
                                straighten=indicator_straighten,
                                pad=indicator_pad,
                                connector_color=connector_color,
                                connector_width=connector_width,
                                zorder=zorder,
                            )
                            _indicator_ok = True
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Indicateur detail échoué : {e}")
                            _indicator_ok = False

                    # Fallback: manually draw the extent rectangle
                    if not _indicator_ok and indicator in ("extent", "detail"):
                        self._draw_inset_data_indicator(
                            inset_ax, bounds, None, "bbox",
                            indicator_facecolor, box_color,
                            indicator_alpha, box_linewidth, 10,
                        )

                self._inset_ax = inset_ax
                self._inset_map_obj = im
                self._log("🔍 Carte de situation ajoutée (map-utils)")
                return self

        # ------- classic mode (fallback) -------
        # to="ax": `position` is a fraction (0-1) of the main axes,
        # converted here to absolute figure coordinates (fig.add_axes()
        # only understands figure coordinates). to="fig" (legacy
        # behavior): `position` is already in figure coordinates.
        if to == "ax":
            ax_bbox = self.ax.get_position()
            px, py, pw, ph = position
            resolved_position = (
                ax_bbox.x0 + px * ax_bbox.width,
                ax_bbox.y0 + py * ax_bbox.height,
                pw * ax_bbox.width,
                ph * ax_bbox.height,
            )
        else:
            resolved_position = position
        inset_ax = self.fig.add_axes(
            resolved_position, projection=projection, frameon=True
        )
        if on_bounds is not None:
            minx, miny, maxx, maxy = on_bounds
            inset_ax.set_extent((minx, maxx, miny, maxy), crs=ccrs.PlateCarree())
        elif global_view:
            inset_ax.set_global()
        elif extent is not None:
            inset_ax.set_extent(extent, crs=ccrs.PlateCarree())
        else:
            inset_ax.set_global()

        if circular:
            self._make_inset_circular(inset_ax)

        inset_ax.add_feature(cfeature.LAND, facecolor=land_color)
        inset_ax.add_feature(cfeature.OCEAN, facecolor=ocean_color)
        if show_borders:
            inset_ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor="gray")
        if show_coastlines:
            inset_ax.coastlines(resolution="110m", linewidth=0.4)

        # Study area (bbox rectangle or actual geometry depending on `mode`)
        self._draw_inset_data_indicator(
            inset_ax, bounds, data_gdf, mode,
            "none" if data is None else indicator_facecolor, box_color,
            indicator_alpha, box_linewidth, 10,
        )

        # Frame around `on`'s extent (zoom_to_on=True)
        if on_bounds is not None:
            self._draw_inset_data_indicator(
                inset_ax, on_bounds, None, "bbox",
                "none", box_color, 1.0, box_linewidth, 10,
            )

        # Inset border
        for spine in inset_ax.spines.values():
            spine.set_edgecolor(edgecolor)
            spine.set_linewidth(linewidth)

        inset_ax.patch.set_alpha(alpha)
        inset_ax.patch.set_facecolor(facecolor)

        # Draw the optional context layers on the classic inset
        if on is not None:
            items = on if isinstance(on, list) else [{"data": on}]
            for item in items:
                gdf = item["data"] if isinstance(item, dict) else item
                plot_kw = item.get("kwargs", {}) if isinstance(item, dict) else {}
                gdf.plot(ax=inset_ax, transform=ccrs.PlateCarree(), **plot_kw)

        self._inset_ax = inset_ax
        self._log("🔍 Carte de situation ajoutée")

        return self

    # Alias
    add_inset = add_inset_map

    def set_background_color(self, color: str = "white") -> "Map":
        """
        Sets the map's background color.

        Parameters:
        -----------
        color : str
            Background color (CSS name, hex, etc.)

        Returns:
        ---------
        Map: Map instance for chaining
        """
        self.ax.set_facecolor(color)
        self.fig.patch.set_facecolor(color)
        return self

    def add_colorbar(
        self,
        cmap: str = "viridis",
        vmin: float = 0,
        vmax: float = 1,
        label: str = None,
        orientation: str = "vertical",
        shrink: float = 0.6,
        pad: float = 0.05,
        aspect: int = 20,
        ticks=None,
        tick_labels=None,
    ) -> "Map":
        """
        Adds a standalone colorbar to the map.

        Parameters:
        -----------
        cmap : str
            Color palette
        vmin : float
            Minimum value
        vmax : float
            Maximum value
        label : str, optional
            Colorbar title
        orientation : str
            'vertical' or 'horizontal'
        shrink : float
            Shrink factor (0-1)
        pad : float
            Padding relative to the map
        aspect : int
            Length/width ratio of the bar
        ticks : list, optional
            Tick positions
        tick_labels : list, optional
            Custom labels for the ticks

        Returns:
        ---------
        Map: Map instance for chaining
        """
        cmap_obj = load_cmap(cmap)
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
        sm.set_array([])

        cbar = plt.colorbar(
            sm, ax=self.ax, orientation=orientation,
            shrink=shrink, pad=pad, aspect=aspect,
        )

        if ticks is not None:
            cbar.set_ticks(ticks)
        if tick_labels is not None:
            cbar.set_ticklabels(tick_labels)
        if label:
            if orientation == "vertical":
                cbar.set_label(label, rotation=270, labelpad=20)
            else:
                cbar.set_label(label)

        self._colorbar = cbar
        return self

    def zoom_to_layer(self, index: int = None, label: str = None,
                      margin: float = 0.05) -> "Map":
        """
        Zooms to the extent of a specific layer.

        Parameters:
        -----------
        index : int, optional
            Layer index (see list_layers())
        label : str, optional
            Layer label
        margin : float
            Relative margin around the layer (0-1)

        Returns:
        ---------
        Map: Map instance for chaining
        """
        if index is None and label is None:
            raise ValueError("Fournir index ou label pour identifier la couche.")

        target = None
        if index is not None:
            if not 0 <= index < len(self.layers):
                raise IndexError(
                    f"Index {index} hors limites (0\u2013{len(self.layers) - 1})."
                )
            target = self.layers[index]
        else:
            for layer in self.layers:
                if layer.get("label") == label:
                    target = layer
                    break
            if target is None:
                raise ValueError(f"Aucune couche avec le label '{label}' trouvée.")

        if "gdf" not in target:
            raise ValueError(
                "Cette couche ne contient pas de GeoDataFrame (ex: raster, scalebar)."
            )

        bounds = target["gdf"].total_bounds  # minx, miny, maxx, maxy
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        extent = [
            bounds[0] - width * margin,
            bounds[2] + width * margin,
            bounds[1] - height * margin,
            bounds[3] + height * margin,
        ]
        self.ax.set_extent(extent, crs=ccrs.PlateCarree())
        self.bounds = [extent[0], extent[2], extent[1], extent[3]]

        return self

    def add_raster(
        self,
        raster_path=None,
        raster_array=None,
        extent=None,
        cmap="viridis",
        alpha=0.7,
        vmin=None,
        vmax=None,
        transform=None,
        title=None,
        show_colorbar=True,
    ):
        """
        Adds a raster layer to the map.

        Parameters:
        -----------
        raster_path : str
            Path to the raster file
        raster_array : numpy.ndarray
            Numpy array containing the raster data
        extent : tuple
            Raster extent (xmin, xmax, ymin, ymax)
        cmap : str
            Color palette
        alpha : float
            Transparency
        vmin, vmax : float
            Min/max values for normalization
        transform : rasterio.transform
            Geographic transform
        title : str
            Colorbar title
        show_colorbar : bool
            Show the colorbar
        """
        raster_crs = None
        if raster_path:
            with rasterio.open(raster_path) as src:
                raster_data = src.read(1)
                extent = [
                    src.bounds.left,
                    src.bounds.right,
                    src.bounds.bottom,
                    src.bounds.top,
                ]
                raster_crs = src.crs
        elif raster_array is not None:
            raster_data = raster_array
            if extent is None:
                raise ValueError("extent doit être fourni avec raster_array")
        else:
            raise ValueError("raster_path ou raster_array doit être fourni")

        # Mask NaN values
        raster_data = np.ma.masked_invalid(raster_data)

        # Normalization
        if vmin is None:
            vmin = np.nanmin(raster_data)
        if vmax is None:
            vmax = np.nanmax(raster_data)

        # Determine the cartopy CRS for the raster
        data_transform = ccrs.PlateCarree()  # default for EPSG:4326
        if raster_crs is not None:
            epsg = raster_crs.to_epsg()
            if epsg and epsg != 4326:
                try:
                    data_transform = ccrs.epsg(epsg)
                except Exception:
                    self._log(
                        f"⚠️  CRS EPSG:{epsg} non supporté par cartopy, "
                        f"utilisation de PlateCarree par défaut"
                    )

        # Display the raster
        im = self.ax.imshow(
            raster_data,
            extent=extent,
            transform=data_transform,
            cmap=cmap,
            alpha=alpha,
            vmin=vmin,
            vmax=vmax,
            origin="upper",
        )

        # Add the colorbar
        if show_colorbar:
            cbar = plt.colorbar(im, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Store the layer information (already rendered directly)
        layer_info = {
            "type": "raster",
            "name": title,
            "data": raster_data,
            "rendered": True,
            "label": None,
            "src": raster_path,
            "style": {
                "extent": extent,
                "transform": data_transform,
                "cmap": cmap,
                "alpha": alpha,
                "vmin": vmin,
                "vmax": vmax,
                "origin": "upper",
            }
        }
        self.layers.append(layer_info)

        return im

    def add_polygons_choropleth(
        self,
        gdf,
        column_to_plot,
        label_column=None,
        cmap="viridis",
        alpha=1,
        edge_color="black",
        linewidth=0.5,
        show_labels=True,
        label_size=10,
        text_outline_color="white",
        text_outline_width=2,
        show_colorbar=True,
        title=None,
        default_crs="EPSG:4326",
    ):
        """
        Adds a choropleth vector layer.

        Parameters:
        -----------
        gdf : GeoDataFrame
            Geographic data
        column_to_plot : str
            Column used for coloring
        label_column : str
            Column used for labels
        cmap : str
            Color palette
        alpha : float
            Transparency
        edge_color : str
            Outline color
        linewidth : float
            Outline width
        show_labels : bool
            Show the labels
        label_size : int
            Label size
        text_outline_color : str
            Text outline color
        text_outline_width : float
            Text outline width
        show_colorbar : bool
            Show the colorbar
        title : str
            Colorbar title
        default_crs : str
            Default CRS if geodf doesn't have one
        """
        # Check and set the CRS if needed
        geodf = gdf.copy()
        if geodf.crs is None:
            self._log(
                f"⚠️  Aucun CRS défini. Attribution du CRS par défaut: {default_crs}"
            )
            geodf = geodf.set_crs(default_crs)

        # Reproject to EPSG:4326 for cartopy compatibility
        if geodf.crs is not None and not geodf.crs.equals("EPSG:4326"):
            try:
                geodf = geodf.to_crs(epsg=4326)
            except Exception as e:
                logger.warning(f"Erreur de transformation CRS: {e}. Utilisation des coordonnées originales.")

        # Check that the column exists
        if column_to_plot not in geodf.columns:
            raise ValueError(f"Colonne '{column_to_plot}' introuvable dans le GeoDataFrame")

        # Filter out null/empty geometries
        geodf = geodf[geodf.geometry.notna() & ~geodf.geometry.is_empty]

        # Vectorized plotting with gdf.plot() (replaces the per-feature loop)
        cmap_obj = load_cmap(cmap)
        vmin = geodf[column_to_plot].min()
        vmax = geodf[column_to_plot].max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)

        geodf.plot(
            column=column_to_plot,
            cmap=cmap_obj,
            ax=self.ax,
            alpha=alpha,
            edgecolor=edge_color,
            linewidth=linewidth,
            vmin=vmin,
            vmax=vmax,
            transform=ccrs.PlateCarree(),
        )

        # Add the labels (vectorized via apply)
        if show_labels and label_column and label_column in geodf.columns:
            for idx, row in geodf.iterrows():
                try:
                    centroid = row.geometry.representative_point()
                    label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"
                    self.ax.text(
                        centroid.x,
                        centroid.y,
                        label_text,
                        fontsize=label_size,
                        ha="center",
                        va="center",
                        color="#0f172a",
                        transform=ccrs.PlateCarree(),
                        path_effects=[
                            patheffects.withStroke(
                                linewidth=text_outline_width,
                                foreground=text_outline_color,
                            )
                        ],
                    )
                except Exception as e:
                    self._log(
                        f"⚠️  Étiquette impossible pour {row.get(label_column, 'inconnu')}: {e}"
                    )

        # Colorbar
        if show_colorbar:
            sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Store the information (already rendered directly)
        layer_info = {
            "type": "polygon",
            "name": title,
            "gdf": geodf,
            "data": geodf,
            "rendered": True,
            "label": None,
            "src": None,
            "column_to_plot": column_to_plot,
            "style": {
                "cmap": cmap,
                "alpha": alpha,
            },
        }
        self.layers.append(layer_info)
        self._update_bounds(geodf)
        self._apply_smart_centering()

        return self

    def add_points_choropleth(
        self,
        gdf,
        column_to_plot,
        label_column=None,
        point_size_column=None,
        cmap="viridis",
        alpha=0.7,
        min_point_size=40,
        max_point_size=200,
        edge_color="black",
        linewidth=0.5,
        show_labels=True,
        label_size=10,
        text_outline_color="white",
        text_outline_width=2,
        show_colorbar=True,
        show_size_legend=True,
        title=None,
        default_crs="EPSG:4326",
    ):
        """
        Adds a vector point layer.

        Parameters:
        -----------
        gdf : GeoDataFrame
            Geographic data
        column_to_plot : str
            Column used for coloring
        label_column : str
            Column used for labels
        point_size_column : str
            Column used to size the points
        cmap : str
            Color palette
        alpha : float
            Transparency
        min_point_size : float
            Minimum point size
        max_point_size : float
            Maximum point size
        edge_color : str
            Outline color
        linewidth : float
            Outline width
        show_labels : bool
            Show the labels
        label_size : int
            Label size
        text_outline_color : str
            Text outline color
        text_outline_width : float
            Text outline width
        show_colorbar : bool
            Show the colorbar
        show_size_legend : bool
            Show the size legend
        title : str
            Colorbar title
        default_crs : str
            Default CRS if geodf doesn't have one
        """
        # Check and set the CRS if needed
        geodf = gdf.copy()
        if geodf.crs is None:
            self._log(
                f"⚠️  Aucun CRS défini. Attribution du CRS par défaut: {default_crs}"
            )
            geodf = geodf.set_crs(default_crs)

        # Reproject to EPSG:4326 for cartopy compatibility
        if geodf.crs is not None and not geodf.crs.equals("EPSG:4326"):
            try:
                geodf = geodf.to_crs(epsg=4326)
            except Exception as e:
                logger.warning(f"Erreur de transformation CRS: {e}. Utilisation des coordonnées originales.")

        # Check that the column exists
        if column_to_plot not in geodf.columns:
            raise ValueError(f"Colonne '{column_to_plot}' introuvable dans le GeoDataFrame")

        # Filter out null/empty geometries
        geodf = geodf[geodf.geometry.notna() & ~geodf.geometry.is_empty]

        # Color normalization
        vmin = geodf[column_to_plot].min()
        vmax = geodf[column_to_plot].max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        cmap_obj = load_cmap(cmap)

        # Vectorized coordinate computation (centroid for non-points)
        xs = geodf.geometry.apply(lambda g: g.x if g.geom_type == "Point" else g.centroid.x)
        ys = geodf.geometry.apply(lambda g: g.y if g.geom_type == "Point" else g.centroid.y)

        # Vectorized size computation
        if point_size_column:
            if point_size_column not in geodf.columns:
                self._log(
                    f"⚠️  Colonne '{point_size_column}' introuvable. Taille par défaut utilisée."
                )
                point_size_column = None

        if point_size_column:
            size_min = geodf[point_size_column].min()
            size_max = geodf[point_size_column].max()
            size_norm = plt.Normalize(vmin=size_min, vmax=size_max)
            sizes = min_point_size + size_norm(geodf[point_size_column].values) * (
                max_point_size - min_point_size
            )
        else:
            sizes = min_point_size

        # Vectorized plotting (a single scatter call)
        colors = cmap_obj(norm(geodf[column_to_plot].values))
        self.ax.scatter(
            xs.values,
            ys.values,
            s=sizes,
            c=colors,
            alpha=alpha,
            edgecolor=edge_color,
            linewidth=linewidth,
            transform=ccrs.PlateCarree(),
        )

        # Add the labels
        if show_labels and label_column and label_column in geodf.columns:
            for idx, (x, y) in enumerate(zip(xs, ys)):
                try:
                    row = geodf.iloc[idx]
                    label_text = f"{row[label_column]}"
                    self.ax.text(
                        x,
                        y,
                        label_text,
                        fontsize=label_size,
                        ha="center",
                        va="center",
                        color="#0f172a",
                        transform=ccrs.PlateCarree(),
                        path_effects=[
                            patheffects.withStroke(
                                linewidth=text_outline_width,
                                foreground=text_outline_color,
                            )
                        ],
                    )
                except Exception as e:
                    self._log(
                        f"⚠️  Étiquette impossible pour {row.get(label_column, 'inconnu')}: {e}"
                    )

        # Colorbar
        if show_colorbar:
            sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Size legend
        if show_size_legend and point_size_column:
            sizes = [size_min, (size_min + size_max) / 2, size_max]
            handles = []
            labels = []

            for size_value in sizes:
                normalized_size = size_norm(size_value)
                display_size = min_point_size + normalized_size * (
                    max_point_size - min_point_size
                )
                handles.append(
                    plt.scatter(
                        [],
                        [],
                        s=display_size,
                        color="gray",
                        edgecolor="black",
                        alpha=0.7,
                    )
                )
                labels.append(f"{size_value:,.0f}")

            legend = self.ax.legend(
                handles,
                labels,
                title=point_size_column,
                loc="lower right",
                frameon=True,
                framealpha=0.9,
            )

        # Store the layer information (already rendered directly) —
        # without this, this layer was invisible to list_layers()/
        # remove_layer() and didn't survive a clear_layers() elsewhere
        # (ax.clear() wipes it, unlike add_polygons_choropleth which
        # registers itself correctly).
        layer_info = {
            "type": "point",
            "name": title,
            "gdf": geodf,
            "data": geodf,
            "rendered": True,
            "label": None,
            "src": None,
            "column_to_plot": column_to_plot,
            "style": {
                "cmap": cmap,
                "alpha": alpha,
            },
        }
        self.layers.append(layer_info)

        self._update_bounds(geodf)
        self._apply_smart_centering()

        return self

    # Backward-compatible aliases (old misspelled names)
    def add_polygons_cloropleth(self, *args, **kwargs):
        """Deprecated alias — use add_polygons_choropleth."""
        warnings.warn(
            "add_polygons_cloropleth est déprécié, "
            "utiliser add_polygons_choropleth à la place.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.add_polygons_choropleth(*args, **kwargs)

    def add_points_cloropleth(self, *args, **kwargs):
        """Deprecated alias — use add_points_choropleth."""
        warnings.warn(
            "add_points_cloropleth est déprécié, "
            "utiliser add_points_choropleth à la place.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.add_points_choropleth(*args, **kwargs)

    # ----------------------------------------------------------------------
    # =========== Bivariate maps and hexagonal grids =======================
    # ----------------------------------------------------------------------

    def _prepare_display_gdf(self, gdf):
        """Validates a GeoDataFrame and prepares it for the current axes.

        Returns ``(geodf, transform)``: reprojected to EPSG:4326 with
        ``transform=ccrs.PlateCarree()`` if the map has a cartopy projection
        (``Map``), or unchanged with ``transform=None`` otherwise (``Map2D``).
        """
        geodf = self._validate_geodataframe(gdf)
        if self.projection is None:
            return geodf, None
        if geodf.crs is not None and not geodf.crs.equals("EPSG:4326"):
            try:
                geodf = geodf.to_crs(epsg=4326)
            except Exception as e:
                logger.warning(f"Erreur de transformation CRS: {e}")
        return geodf, ccrs.PlateCarree()

    def _register_rendered_layer(self, layer_type, geodf, name=None, replay=None):
        """Registers a layer already drawn directly onto ``self.ax``.

        ``replay``: a no-argument callable that redraws the layer onto
        ``self.ax``, called by ``_render()`` after an ``ax.clear()``
        (triggered by ``set_paper``/``set_projection``...).
        """
        self.layers.append({
            "type": layer_type, "name": name,
            "gdf": geodf, "data": geodf, "rendered": True,
            "label": None, "src": None, "style": {}, "_replay": replay,
        })
        if self.projection is not None:
            self._update_bounds(geodf)
            self._apply_smart_centering()

    def add_bivariate(self, gdf, var1, var2, **kwargs):
        """Adds a bivariate choropleth (two crossed variables) to the map.

        A wrapper around :func:`cartograpy.mapper.plot_bivariate_choropleth`
        that draws onto this map's axes (``self.ax``) instead of creating a
        figure. All of its named parameters go through ``**kwargs``
        (``var1_label``, ``var2_label``, ``palette``, ``n_classes``,
        ``method``, ``legend_position``...). The enriched GeoDataFrame
        (bivariate classes and colors) is also stored in
        ``self.last_bivariate``.

        Returns ``self`` (chainable).
        """
        geodf, transform = self._prepare_display_gdf(gdf)

        def _draw():
            return plot_bivariate_choropleth(
                geodf, var1, var2, ax_map=self.ax, transform=transform, **kwargs
            )

        _, _, gdf_bi = _draw()
        self.last_bivariate = gdf_bi
        self._register_rendered_layer(
            "bivariate", gdf_bi, name=kwargs.get("title"), replay=_draw
        )
        return self

    def add_hexgrid(self, gdf, column, hex_size=None, hex_grid=None,
                    value_cols=None, agg_funcs=None, predicate="within",
                    count_col="n_points", **kwargs):
        """Adds a hexbin map (aggregated hexagonal grid) to the map.

        Chains :func:`~cartograpy.mapper.make_hex_grid`,
        :func:`~cartograpy.mapper.aggregate_to_hex`, and
        :func:`~cartograpy.mapper.plot_hexgrid_choropleth`, drawing onto
        ``self.ax``.

        Parameters:
        -----------
        gdf : GeoDataFrame
            Data to aggregate (points or polygons) if ``hex_size`` or
            ``hex_grid`` is provided; otherwise, an already-aggregated
            grid plotted as-is.
        column : str
            Column to map.
        hex_size : float, optional
            Hexagon radius (in ``gdf``'s CRS unit — use a projected CRS).
            Triggers the grid generation and aggregation.
        hex_grid : GeoDataFrame, optional
            Existing grid (output of ``make_hex_grid``) instead of
            generating one.
        value_cols : list[str], optional
            Columns to aggregate (default: ``[column]``).
        agg_funcs, predicate, count_col :
            Passed to ``aggregate_to_hex``.
        **kwargs :
            Passed to ``plot_hexgrid_choropleth`` (``cmap``, ``min_count``,
            ``edgecolor``, ``colorbar_label``...).

        The hexagonal GeoDataFrame is stored in ``self.last_hexgrid``.
        Returns ``self`` (chainable).
        """
        if hex_size is not None or hex_grid is not None:
            grid = hex_grid if hex_grid is not None else make_hex_grid(gdf, hex_size)
            hex_gdf = aggregate_to_hex(
                gdf, grid, value_cols or [column],
                agg_funcs=agg_funcs, count_col=count_col, predicate=predicate,
            )
        else:
            hex_gdf = gdf

        geodf, transform = self._prepare_display_gdf(hex_gdf)
        kwargs.setdefault("count_col", count_col)

        def _draw():
            return plot_hexgrid_choropleth(
                geodf, column, ax_map=self.ax, transform=transform, **kwargs
            )

        _draw()
        self.last_hexgrid = geodf
        self._register_rendered_layer(
            "hexgrid", geodf, name=kwargs.get("title"), replay=_draw
        )
        return self

    # ----------------------------------------------------------------------
    # ================Custom map appearance==================================
    # ----------------------------------------------------------------------

    def add_gridlines(
        self,
        draw_labels=True,
        top_right=True,
        dms=False,
        x_inline=False,
        y_inline=False,
        xlocs=None,
        ylocs=None,
        color="gray",
        linestyle="--",
        linewidth=0.5,
        alpha=0.7,
        fontsize=10,
    ):
        """
        Adds a coordinate grid with cartopy.

        Parameters:
        -----------
        draw_labels : bool
            Show the coordinate labels
        dms : bool
            Degrees-minutes-seconds format instead of decimal degrees
        x_inline : bool
            Inline X labels
        y_inline : bool
            Inline Y labels
        xlocs : list
            Specific positions for the longitude lines
        ylocs : list
            Specific positions for the latitude lines
        color : str
            Grid color
        linestyle : str
            Grid line style
        linewidth : float
            Grid width
        alpha : float
            Grid transparency
        fontsize : int
            Label font size
        """
        # Remember the parameters so the grid can be recreated after an
        # ax.clear() (remove_layer/clear_layers/set_projection).
        self._gridline_kwargs = dict(
            draw_labels=draw_labels, top_right=top_right, dms=dms,
            x_inline=x_inline, y_inline=y_inline, xlocs=xlocs, ylocs=ylocs,
            color=color, linestyle=linestyle, linewidth=linewidth,
            alpha=alpha, fontsize=fontsize,
        )

        # Remove the existing grid if present
        if self.gridlines:
            self.gridlines.remove()

        # Create the grid
        gl = self.ax.gridlines(
            draw_labels=draw_labels,
            dms=dms,
            x_inline=x_inline,
            y_inline=y_inline,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=alpha,
        )

        # Configure the labels
        if draw_labels:
            gl.xlabel_style = {"size": fontsize}
            gl.ylabel_style = {"size": fontsize}

            # Label positioning
            if top_right:
                gl.top_labels = True
                gl.right_labels = True
            else:
                gl.top_labels = False
                gl.right_labels = False
            gl.bottom_labels = True
            gl.left_labels = True

            # Coordinate formatting
            if not dms:
                gl.xformatter = LONGITUDE_FORMATTER
                gl.yformatter = LATITUDE_FORMATTER

        # Configure the grid line positions
        if xlocs is not None:
            gl.xlocator = mticker.FixedLocator(xlocs)

        if ylocs is not None:
            gl.ylocator = mticker.FixedLocator(ylocs)

        self.gridlines = gl

        return self

    def set_extent(self, bounds, crs=None):
        """
        Sets the map's bounds.

        Parameters:
        -----------
        bounds : list or tuple
            Bounds in cartopy format ``[x0, x1, y0, y1]`` (west, east, south,
            north), like ``GeoAxes.set_extent``.
        crs : cartopy.crs
            Coordinate system of the bounds (defaults to PlateCarree)
        """
        if crs is None:
            crs = ccrs.PlateCarree()

        self.ax.set_extent(bounds, crs=crs)
        # `self.bounds` is always stored in [minx, miny, maxx, maxy] format
        # (the rest of the code — _apply_smart_centering,
        # add_background_image… — reads it in this order), regardless of
        # the order passed in here.
        x0, x1, y0, y1 = bounds
        self.bounds = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

        return self

    def set_projection(self, projection):
        """
        Changes the map's projection (requires recreating the axes).

        Parameters:
        -----------
        projection : cartopy.crs
            New projection
        """
        # Save the current parameters
        title = self.title
        figsize = self.figsize

        # Recreate the axes with the new projection
        self.fig.clear()
        self.ax = self.fig.add_subplot(111, projection=projection)
        self.projection = projection
        self.ax.set_title(title, fontsize=16, fontweight="bold")

        # Restore the default features
        if self.basemap:
            self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
            self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # fig.clear() destroys every artist of the figure (grid, north
        # arrow, scale bar, inset, colorbar): the existing references are
        # now stale.
        self.gridlines = None
        self._north_arrow_artist = None
        self._scale_bar_artist = None
        self._inset_ax = None
        self._colorbar = None

        # Recreate the grid and north arrow for the new projection
        self._reapply_persistent_artists()

        # Flag the layers for re-rendering (including the scale bar, which
        # is handled as a layer and will be redrawn by _render())
        for layer in self.layers:
            layer["rendered"] = False

        return self
    
    def hide_gridline(self):
        """
        Hides every border, tick, and label of the axes.

        Example:
            m = Map()
            m.hide_gridline()
            m.show()
        """
        ax=self.ax
        # Hide the spines (borders)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Hide the ticks
        ax.set_xticks([])
        ax.set_yticks([])

        # Hide the tick labels
        ax.set_xticklabels([])
        ax.set_yticklabels([])

        # Hide the grid if enabled
        ax.grid(False)

    def add_annotation(
        self,
        text: str,
        xy: tuple,
        xytext: tuple = None,
        arrow: bool = True,
        arrow_kwargs: dict = None,
        text_kwargs: dict = None
    ):
        """
        Adds an annotation with or without an arrow to a matplotlib axes.

        Args:
            ax: matplotlib.axes.Axes object
            text (str): Annotation text.
            xy (tuple): Coordinates of the point to annotate (x, y).
            xytext (tuple, optional): Text position. If None, uses xy.
            arrow (bool): If True, adds an arrow.
            arrow_kwargs (dict, optional): Dictionary of arrow options.
            text_kwargs (dict, optional): Dictionary of text options.

        Example:
            add_annotation(ax, "Here", (3, 3), xytext=(2, 4))
        """
        ax=self.ax
        if arrow_kwargs is None and arrow:
            arrow_kwargs = dict(facecolor='black', arrowstyle="->")
        elif not arrow:
            arrow_kwargs = None

        if text_kwargs is None:
            text_kwargs = dict(fontsize=12, color='black')

        ax.annotate(
            text,
            xy=xy,
            xytext=xytext if xytext is not None else xy,
            arrowprops=arrow_kwargs,
            **text_kwargs
        )


    # ----------------------------------------------------------------------
    # ================Custom labels=========================================
    # ----------------------------------------------------------------------

    def add_labels(
        self,
        gdf,
        label_column=None,
        # label_func=None,
        custom_label=None,
        filter_column=None,
        filter_values=None,
        fontsize=10,
        color="#0f172a",
        outline_width=2,
        outline_color="white",
        format_str=None,
        **text_kwargs,
    ):
        """
        Adds text labels at the centroid of polygons OR at the position of points of a GeoDataFrame.

        Parameters
        ----------
        gdf : gpd.GeoDataFrame
            The GeoDataFrame containing the features.
        label_column : str, optional
            The column to display as text (unnecessary if label_func is provided).
        custom_label : callable, optional
            Function that takes a row and returns the label text.
            Example: lambda row: f"{row['nom']}\n{row['pop']:,d}"
        filter_column : str, optional
            Column name used to filter the features to label.
        filter_values : list, optional
            Accepted values for the filter.
        fontsize : int
            Text size.
        color : str
            Text color.
        outline_width : int or float
            Text outline width.
        outline_color : str
            Text outline color.
        format_str : str, optional
            Format string to display the value (e.g.: '{:,d}' for an integer).
        **text_kwargs : other Matplotlib text options.
        """

        # Filter if requested
        if filter_column and filter_values is not None:
            gdf = gdf[gdf[filter_column].isin(filter_values)]

        for idx, row in gdf.iterrows():
            geom = row.geometry

            # For Points/MultiPoints
            if geom.geom_type == "Point":
                coords = [(geom.x, geom.y)]
            elif geom.geom_type == "MultiPoint":
                coords = [(pt.x, pt.y) for pt in geom.geoms]
            # For Polygons/MultiPolygons
            elif geom.geom_type == "Polygon":
                coords = [(geom.centroid.x, geom.centroid.y)]
            elif geom.geom_type == "MultiPolygon":
                coords = [(poly.centroid.x, poly.centroid.y) for poly in geom.geoms]
            else:
                # Ignore LineString/GeometryCollection/etc.
                continue

            # Generate the label
            if custom_label is not None:
                if callable(custom_label):
                    label = custom_label(row)
                else:
                    raise TypeError(
                        "custom_label doit être un callable (ex: lambda row: f\"{row['nom']}\")"
                    )
            elif label_column is not None:
                label = str(row[label_column])
                if format_str:
                    try:
                        label = format_str.format(row[label_column])
                    except Exception:
                        label = label_column
            else:
                raise ValueError("Vous devez fournir label_column OU custom_label.")

            # Display the text at each coordinate found
            for x, y in coords:
                self.ax.text(
                    x,
                    y,
                    label,
                    fontsize=fontsize,
                    ha="center",
                    va="center",
                    color=color,
                    path_effects=[
                        patheffects.withStroke(
                            linewidth=outline_width, foreground=outline_color
                        )
                    ],
                    **text_kwargs,
                )
        return self

    def add_title(self, title, fontsize=16, pad=20):
        """
        Adds a title to the map.

        Parameters:
        -----------
        title : str
            Map title
        fontsize : int
            Font size
        pad : int
            Padding
        """
        self.ax.set_title(title, fontsize=fontsize, pad=pad)

    def add_text(
        self,
        text: str,
        xy: tuple,
        fontsize: int = 12,
        color: str = "black",
        outline_width: float = 0,
        outline_color: str = "white",
        **kwargs
    ):
        """
        Adds custom text to the map.

        Parameters:
        -----------
        text : str
            The text to display
        xy : tuple
            Text position (x, y) in geographic coordinates
        fontsize : int
            Font size (default: 12)
        color : str
            Text color (default: "black")
        outline_width : float
            Text outline width (default: 0 = no outline)
        outline_color : str
            Text outline color (default: "white")
        **kwargs : dict
            Other parameters for matplotlib.text()
            (ha, va, rotation, alpha, weight, style, etc.)

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> map_obj.add_text("Paris", (2.3522, 48.8566),
        ...                   fontsize=14, color="red",
        ...                   ha="center", va="center")
        """
        # Default text parameters
        text_params = {
            'fontsize': fontsize,
            'color': color,
            'ha': 'left',  # default horizontal alignment
            'va': 'bottom',  # default vertical alignment
            'transform': ccrs.PlateCarree(),  # use geographic coordinates
        }

        # Update with the custom parameters
        text_params.update(kwargs)

        # Add the outline if specified
        if outline_width > 0:
            from matplotlib import patheffects
            text_params['path_effects'] = [
                patheffects.withStroke(
                    linewidth=outline_width,
                    foreground=outline_color
                )
            ]

        # Add the text to the map
        self.ax.text(xy[0], xy[1], text, **text_params)

        return self

    def add_highlight_text(
        self,
        text: str,
        xy: tuple,
        fontsize: int = 12,
        color: str = "black",
        highlight_textprops: list = None,
        **kwargs
    ):
        """
        Adds text with <highlighted> segments (different font/color, e.g.
        bold) via the `highlight_text` library.

        Parameters:
        -----------
        text : str
            Text to display. The segments to highlight are surrounded by
            `<...>` (e.g.: "<Paris>: 48.85").
        xy : tuple
            Text position (x, y) in geographic coordinates.
        fontsize : int
            Default font size (default: 12).
        color : str
            Default color (default: "black").
        highlight_textprops : list of dict, optional
            A dict of matplotlib.text properties per `<...>` segment, in
            order of appearance (e.g.: [{"font": bold_font}]).
        **kwargs : dict
            Other parameters for highlight_text.ax_text()
            (ha, va, font, transform, etc.)

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> map_obj.add_highlight_text(
        ...     "<Paris>: 48.85", (2.3522, 48.8566),
        ...     highlight_textprops=[{"color": "red"}],
        ...     ha="center", va="center",
        ... )
        """
        from highlight_text import ax_text

        text_params = {
            "fontsize": fontsize,
            "color": color,
            "ha": "left",
            "va": "bottom",
            "transform": ccrs.PlateCarree(),
        }
        text_params.update(kwargs)

        ax_text(
            x=xy[0], y=xy[1], s=text,
            ax=self.ax,
            highlight_textprops=highlight_textprops or [],
            **text_params,
        )

        return self

    def add_highlight_fig_text(
        self,
        text: str,
        x: float,
        y: float,
        fontsize: int = 12,
        color: str = "black",
        highlight_textprops: list = None,
        **kwargs
    ):
        """
        Adds off-map text (title, subtitle) with <highlighted> segments,
        positioned in figure coordinates (0-1), via the `highlight_text`
        library.

        Parameters:
        -----------
        text : str
            Text to display. The segments to highlight are surrounded by
            `<...>` (e.g.: "<Unit>: metric tons").
        x, y : float
            Position in figure coordinates (0-1, like fig.text()).
        fontsize : int
            Default font size (default: 12).
        color : str
            Default color (default: "black").
        highlight_textprops : list of dict, optional
            A dict of matplotlib.text properties per `<...>` segment, in
            order of appearance (e.g.: [{"font": bold_font}]).
        **kwargs : dict
            Other parameters for highlight_text.fig_text()
            (ha, va, font, etc.)

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> map_obj.add_highlight_fig_text(
        ...     "<Unit>: metric tons", x=0.5, y=0.87,
        ...     highlight_textprops=[{"color": "red"}],
        ...     ha="center", va="top",
        ... )
        """
        from highlight_text import fig_text

        text_params = {
            "fontsize": fontsize,
            "color": color,
            "ha": "center",
            "va": "top",
        }
        text_params.update(kwargs)

        fig_text(
            x=x, y=y, s=text,
            fig=self.fig,
            highlight_textprops=highlight_textprops or [],
            **text_params,
        )

        return self

    def add_custom_text(self, text: str, xy: tuple, to: str = "ax", **kwargs):
        """
        Adds text with <highlighted> segments, on the map (``to="ax"``,
        geographic coordinates) or off-map (``to="fig"``, figure
        coordinates 0-1). Dispatches to `add_highlight_text()` /
        `add_highlight_fig_text()` — see their docstring for parameter
        details.

        Parameters:
        -----------
        text : str
            Text to display, `<...>` segments highlighted.
        xy : tuple
            Position (x, y).
        to : str
            ``"ax"`` (default, map coordinates) or ``"fig"`` (figure
            coordinates 0-1, for title/subtitle).
        **kwargs : dict
            Passed to the target method (fontsize, color,
            highlight_textprops, ha, va, font, etc.)

        Returns:
        --------
        Map : self for method chaining
        """
        if to == "ax":
            return self.add_highlight_text(text, xy, **kwargs)
        elif to == "fig":
            return self.add_highlight_fig_text(text, xy[0], xy[1], **kwargs)
        raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

    def add_custom_labels(
        self,
        gdf,
        template,
        dx=0.0,
        dy=0.0,
        except_=None,
        highlight_textprops=None,
        **kwargs,
    ):
        """
        Batch-labels each feature of a GeoDataFrame with text composed
        from its columns — "per feature" version of `add_custom_text()`,
        with the same support for `<highlighted>` segments
        (`highlight_textprops`).

        The text of each label is produced by `template.format(**row)`:
        the `{...}` in `template` are GeoDataFrame column names (format
        specifiers allowed, e.g. `{densite:.0f}`). Segments surrounded by
        `<...>` are highlighted.

        The label anchor is:

        - the point position if the geometry is a `Point`/`MultiPoint`;
        - the `representative_point()` (point guaranteed to be inside) for
          a `Polygon`/`MultiPolygon` — a single point per feature, including
          for multipolygons (unlike `add_labels`).

        Parameters:
        -----------
        gdf : geopandas.GeoDataFrame
            Features to label (reprojected to EPSG:4326 if needed, like
            other `Map` layers).
        template : str
            f-string-style template, e.g. `"<{NAME_1}>\\n{densite:.0f} hab/km²"`.
        dx, dy : float
            Offset applied to the anchor, in axis units (degrees for
            `Map`). Positive = towards the east / north.
        except_ : tuple (str, list), optional
            `(column_name, values)`: features whose `row[column_name]` is
            in `values` do not receive a label
            (e.g. `except_=("shapeName", ["Côte d'Ivoire", "Guinée"])`).
        highlight_textprops : list[dict], optional
            A properties dict per `<...>` segment of the template, in order
            (e.g. `[{"font": font_bold}]`) — applied to each label.
        **kwargs :
            Passed to `add_highlight_text()` for each label
            (`fontsize`, `color`, `font`, `ha`, `va`…). `ha`/`va` default
            to `"center"` here.

        Returns:
        --------
        Map : self (chainable).

        Raises:
        -------
            KeyError: if `template` references a missing column.
            ValueError: if `except_` is not a `(str, list)` pair.

        Examples:
        ---------
            >>> m.add_custom_labels(
            ...     regions, "<{NAME_1}> : {densite:.0f}",
            ...     dy=0.15, fontsize=8, color="#222",
            ...     highlight_textprops=[{"font": font_bold}],
            ...     except_=("NAME_1", ["Abidjan"]),
            ... )
        """
        if except_ is not None:
            if (not isinstance(except_, (tuple, list)) or len(except_) != 2):
                raise ValueError(
                    "except_ doit être un couple (nom_colonne, liste_de_valeurs), "
                    f"reçu : {except_!r}"
                )
            skip_col, skip_values = except_
            skip_values = set(skip_values)
        else:
            skip_col = None

        geodf, transform = self._prepare_display_gdf(gdf)
        kwargs.setdefault("ha", "center")
        kwargs.setdefault("va", "center")
        kwargs.setdefault(
            "transform", transform if transform is not None else self.ax.transData
        )

        for _, row in geodf.iterrows():
            if skip_col is not None and row[skip_col] in skip_values:
                continue

            try:
                label = template.format(**row.to_dict())
            except KeyError as e:
                raise KeyError(
                    f"Colonne {e} référencée par `template` mais absente du "
                    f"GeoDataFrame. Colonnes disponibles : {list(geodf.columns)}"
                ) from None

            # highlight_text requires as many dicts as <...> segments;
            # if the caller doesn't provide any, neutralize each segment.
            props = highlight_textprops
            if props is None:
                n_seg = label.count("<")
                props = [{}] * n_seg if n_seg else None

            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            if geom.geom_type == "Point":
                anchors = [(geom.x, geom.y)]
            elif geom.geom_type == "MultiPoint":
                anchors = [(p.x, p.y) for p in geom.geoms]
            else:
                p = geom.representative_point()
                anchors = [(p.x, p.y)]

            for x, y in anchors:
                self.add_highlight_text(
                    label, (x + dx, y + dy),
                    highlight_textprops=props,
                    **kwargs,
                )

        return self

    def add_fig_arrow(
        self,
        tail_position: tuple,
        head_position: tuple,
        radius: float = 0,
        color: str = "black",
        width: float = 1,
        head_width: float = 4,
        head_length: float = 8,
        **kwargs
    ):
        """
        Adds an off-map arrow in figure coordinates (0-1), via the
        `drawarrow` library. Useful for pointing at a feature too small
        to be annotated directly on it (e.g. micro-state).

        Parameters:
        -----------
        tail_position, head_position : tuple
            (x, y) positions in figure coordinates (0-1) of the tail and
            head of the arrow.
        radius : float
            Arrow curvature (0 = straight).
        color : str
            Arrow color (default: "black").
        width, head_width, head_length : float
            Line thickness / head width and length.
        **kwargs : dict
            Other parameters for drawarrow.fig_arrow()
            (double_headed, fill_head, invert, shadow_style, etc.)

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> map_obj.add_fig_arrow((0.32, 0.70), (0.375, 0.45), radius=0.3)
        """
        from drawarrow import fig_arrow

        fig_arrow(
            tail_position=tail_position,
            head_position=head_position,
            radius=radius,
            color=color,
            width=width,
            head_width=head_width,
            head_length=head_length,
            fig=self.fig,
            **kwargs,
        )

        return self

    def set_title(
        self,
        title: str,
        fontsize: int = 14,
        fontweight: str = "bold",
        color: str = "black",
        pad: float = 20,
    ) -> "Map":
        """Sets the map title with customization options."""
        self.ax.set_title(
            title, fontsize=fontsize, fontweight=fontweight, color=color, pad=pad
        )
        return self

    # ----------------------------------------------------------------------
    # ================Custom north arrow====================================
    # ----------------------------------------------------------------------

    def get_north_arrows(self, arrows_subdir="arrows"):
        files = []
        try:
            import importlib.resources

            with importlib.resources.files("cartograpy").joinpath(
                arrows_subdir
            ) as arrows_dir:
                for item in arrows_dir.iterdir():
                    if item.is_file():
                        files.append(str(item))
            return files
        except Exception:
            try:
                import cartograpy

                package_dir = os.path.dirname(cartograpy.__file__)
                arrows_dir = os.path.join(package_dir, arrows_subdir)
                if os.path.exists(arrows_dir):
                    for fname in os.listdir(arrows_dir):
                        fpath = os.path.join(arrows_dir, fname)
                        if os.path.isfile(fpath):
                            files.append(fpath)
            except Exception as e:
                logger.error(f"Impossible de retrouver le dossier : {e}")
        return files

    def add_image(
        self,
        image,
        xy: tuple,
        to: str = "fig",
        zoom: float = 1,
        alpha: float = 1.0,
        zorder: int = 100,
        frameon: bool = False,
        color: str = None,
        **kwargs,
    ):
        """
        Adds an image (logo, photo, illustration) at a precise location on
        the map, via `OffsetImage` + `AnnotationBbox`.

        Parameters:
        -----------
        image : str, array-like or PIL.Image
            Path to an image file (png, jpg, svg...) or already-loaded
            image (numpy array / `PIL.Image`).
        xy : tuple
            Position (x, y).
        to : str
            ``"fig"`` (default, figure coordinates 0-1 — for an off-map
            logo/watermark) or ``"ax"`` (map geographic coordinates).
            Same convention as `add_custom_text`.
        zoom : float
            Image scale factor (default 1).
        alpha : float
            Transparency (0-1).
        zorder : int
            Stacking order (default 100, above the layers).
        frameon : bool
            Show a frame around the image.
        color : str, optional
            Recolors SVGs (see `read_image`), ignored for other formats.
        **kwargs : dict
            Other parameters for `AnnotationBbox` (pad, box_alignment,
            bboxprops, etc.)

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> map_obj.add_image("logo.png", (0.92, 0.08), zoom=0.15)
        >>> map_obj.add_image("photo.jpg", (2.35, 48.85), to="ax", zoom=0.3)
        """
        if to not in ("ax", "fig"):
            raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

        img = read_image(image, color) if isinstance(image, str) else image
        imagebox = OffsetImage(np.asarray(img), zoom=zoom, alpha=alpha)

        if to == "ax":
            xycoords = ccrs.PlateCarree()._as_mpl_transform(self.ax)
        else:
            xycoords = "figure fraction"

        ab = AnnotationBbox(
            imagebox, xy, frameon=frameon, xycoords=xycoords,
            zorder=zorder, **kwargs,
        )
        self.ax.add_artist(ab)
        self._log("🖼️ Image ajoutée")
        return self

    def add_background_image(
        self,
        image,
        extent: tuple = None,
        zoom: float = 1,
        aspect: str = "equal",
        alpha: float = 1.0,
        zorder: int = -100,
        color: str = None,
        **kwargs,
    ):
        """
        Adds a background image (texture, static base map, etc.) behind
        all layers, over the map extent.

        Parameters:
        -----------
        image : str, array-like or PIL.Image
            Path to an image file or already-loaded image.
        extent : tuple, optional
            ``(minx, miny, maxx, maxy)`` covered by the image (geographic
            coordinates). Defaults to the map's current extent
            (`self.bounds`, updated by layers already added or by
            `set_extent()`).
        zoom : float
            Scale factor (> 0) applied to the image around the center of
            `extent` (default 1 = no change). > 1 enlarges the image
            (it covers a larger area); < 1 shrinks it.
        aspect : str
            ``"equal"`` (default): x/y geographic units stay at equal
            scale, consistent with the rest of the map — the image is not
            distorted by a stretched axis. ``"auto"``: stretches the image
            to fill the whole `extent` (may distort it).
        alpha : float
            Transparency (0-1).
        zorder : int
            Stacking order (default -100, below all other layers).
        color : str, optional
            Recolors SVGs (see `read_image`), ignored for other formats.
        **kwargs : dict
            Other parameters for `Axes.imshow()`.

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> map_obj.set_extent([-11, 32, 41, 73])
        >>> map_obj.add_background_image("texture.jpg")
        """
        # Stores the original arguments: used to redraw the image after
        # an ax.clear() (set_paper/set_projection) and to merge
        # set_background_image() modifications.
        extent_arg = tuple(extent) if extent is not None else None

        # Only one background image at a time: remove the previous one.
        if getattr(self, "_background_image_artist", None) is not None:
            try:
                self._background_image_artist.remove()
            except (ValueError, NotImplementedError):
                pass
            self._background_image_artist = None

        img = read_image(image, color) if isinstance(image, str) else image
        img_arr = np.asarray(img)

        if extent is None:
            if not getattr(self, "bounds", None):
                raise ValueError(
                    "Aucune étendue disponible : passez extent=... ou "
                    "appelez set_extent() / ajoutez une couche d'abord."
                )
            # self.bounds is in [minx, miny, maxx, maxy] format;
            # imshow() expects (left, right, bottom, top).
            minx, miny, maxx, maxy = self.bounds
            extent = (minx, maxx, miny, maxy)
        else:
            minx, miny, maxx, maxy = extent
            extent = (minx, maxx, miny, maxy)

        if zoom <= 0:
            raise ValueError(f"zoom doit être > 0, reçu: {zoom!r}")

        if zoom != 1:
            cx, cy = (extent[0] + extent[1]) / 2, (extent[2] + extent[3]) / 2
            half_w = (extent[1] - extent[0]) / 2 * zoom
            half_h = (extent[3] - extent[2]) / 2 * zoom
            extent = (cx - half_w, cx + half_w, cy - half_h, cy + half_h)

        # `aspect="equal"` alone is not enough: imshow() always stretches
        # the image content to exactly fill `extent`, regardless of
        # `aspect`. To avoid distorting the image, `extent` is shrunk
        # (centered) to its own width/height ratio in pixels — the rest
        # of the box stays empty rather than stretching the image.
        img_h, img_w = img_arr.shape[0], img_arr.shape[1]
        img_ratio = img_w / img_h
        x0, x1, y0, y1 = extent
        box_w, box_h = abs(x1 - x0), abs(y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if box_h > 0 and img_ratio > box_w / box_h:
            new_h = box_w / img_ratio
            extent = (x0, x1, cy - new_h / 2, cy + new_h / 2)
        elif box_w > 0:
            new_w = box_h * img_ratio
            extent = (cx - new_w / 2, cx + new_w / 2, y0, y1)

        # imshow() may automatically readjust the axis view to its own
        # extent: the current extent is explicitly restored so the
        # caller doesn't see it change.
        try:
            current_view = self.ax.get_extent(crs=ccrs.PlateCarree())
        except Exception:
            current_view = None

        self._background_image_artist = self.ax.imshow(
            img_arr, extent=extent, transform=ccrs.PlateCarree(),
            aspect=aspect, alpha=alpha, zorder=zorder, **kwargs,
        )
        self._background_image_kwargs = dict(
            image=image, extent=extent_arg, zoom=zoom, aspect=aspect,
            alpha=alpha, zorder=zorder, color=color, **kwargs,
        )

        if current_view is not None:
            self.ax.set_extent(current_view, crs=ccrs.PlateCarree())

        self._log("🖼️ Image de fond ajoutée")
        return self

    def set_background_image(self, **kwargs) -> "Map":
        """
        Modifies the existing background image created by
        ``add_background_image``.

        Each parameter passed replaces the one stored from the last
        ``add_background_image()`` / ``set_background_image()`` call; the
        others are kept. The old image is removed and a new one is drawn
        with the merged parameters.

        Parameters
        ----------
        image : str, array-like or PIL.Image, optional
            New image.
        extent, zoom, aspect, alpha, zorder, color : optional
            See ``add_background_image``.
        **kwargs :
            Other parameters passed to ``Axes.imshow()``.

        Returns
        -------
        Map : self for method chaining.

        Example
        -------
        >>> m.add_background_image("notebooks/bg_image.jpg", alpha=0.5)
        >>> m.set_background_image(alpha=0.25, zoom=1.2)   # adjusts without rewriting everything
        """
        if self._background_image_kwargs is None:
            raise RuntimeError(
                "Aucune image de fond. Utilisez add_background_image() d'abord."
            )
        merged = {**self._background_image_kwargs, **kwargs}
        return self.add_background_image(**merged)

    def add_north_arrow(
        self,
        arrow=1,
        position: Tuple[float, float] = (0.95, 0.95),
        zoom: float = 1,
        color: str = "black",
        style: str = "auto",
        location: str = "upper right",
        scale: float = None,
        rotation: Union[float, dict, str] = "auto",
        label: str = "N",
        fancy: bool = True,
        shadow: bool = False,
        size: str = None,
        base: dict = None,
        pack: dict = None,
        aob: dict = None,
        zorder: int = 99,
        to: str = "ax",
        **kwargs,
    ):
        """
        Adds a North arrow to the map.

        Automatically uses ``matplotlib-map-utils`` if installed for a
        professional rendering (NorthArrow), otherwise the embedded SVGs.

        Parameters
        ----------
        arrow : int
            SVG arrow number (svg mode, 1-based).
        position : tuple (x, y)
            Position in axes fraction 0-1 coordinates (svg mode).
        zoom : float
            Zoom factor (svg mode), applied after an automatic
            normalization that brings each icon to a common reference
            size — the 17 embedded SVGs have very different native
            resolutions (from 5x16 to 580x580 px), without which
            `zoom=1` would produce inconsistent sizes from one arrow to
            another.
        color : str
            Arrow color.
        style : str
            Rendering mode:
            - ``"auto"``: matplotlib-map-utils if available, otherwise SVG.
            - ``"svg"``: embedded vector arrows.
            - ``"fancy"``: 3D arrow with shadow (matplotlib-map-utils).
            - ``"simple"``: flat arrow (matplotlib-map-utils).
        location : str
            Position ("upper left", "upper right", etc.) — map-utils mode.
        scale : float, optional
            Height in inches (map-utils mode). Auto if None.
        rotation : float, dict or "auto"
            - ``"auto"``: computed from the projection.
            - ``float``: manual degrees.
            - ``dict``: passed directly (e.g. {"crs": ..., "reference": ...}).
        label : str or dict
            Arrow text (default "N"). Can be a full dict:
            ``{"text": "N", "fontsize": 14, "color": "black"}``.
        fancy : bool or dict
            Fancy style with shadow (map-utils mode). Can be a dict to
            configure colors: ``{"facecolor": "black", "edgecolor": "k"}``.
        shadow : bool or dict
            Drop shadow (map-utils mode). Can be a dict:
            ``{"facecolor": "gray", "alpha": 0.5}``.
        size : str, optional
            Predefined size ("xs", "sm", "md", "lg", "xl") — map-utils mode.
            Calls ``NorthArrow.set_size()`` to adjust the global defaults
            **before** the artist is created.
        base : dict, optional
            Arrow base configuration (map-utils mode).
        pack : dict, optional
            Packing configuration (map-utils mode).
        aob : dict, optional
            AnnotationBbox configuration (map-utils mode).
        zorder : int
            Artist z-order (default 99).
        to : str
            ``"ax"`` (default, ``location``/``position`` relative to the
            map axis) or ``"fig"`` (relative to the whole figure — then
            uses ``position`` as the anchor point, in both rendering
            modes). Same convention as `add_custom_text`.
        **kwargs
            Additional parameters for ``NorthArrow``.

        Returns
        -------
        Map : Map instance for chaining.
        """
        if to not in ("ax", "fig"):
            raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

        # Stores the parameters so the arrow can be recreated after an
        # ax.clear() (remove_layer/clear_layers/set_projection).
        self._north_arrow_kwargs = dict(
            arrow=arrow, position=position, zoom=zoom, color=color,
            style=style, location=location, scale=scale, rotation=rotation,
            label=label, fancy=fancy, shadow=shadow, size=size, base=base,
            pack=pack, aob=aob, zorder=zorder, to=to, **kwargs,
        )

        if style == "auto":
            style = "map-utils" if HAS_MAP_UTILS else "svg"

        if style in ("map-utils", "fancy", "simple"):
            if not HAS_MAP_UTILS:
                warnings.warn(
                    "matplotlib-map-utils n'est pas installé, "
                    "utilisation du mode SVG. "
                    "Installez-le avec : pip install matplotlib-map-utils",
                    RuntimeWarning, stacklevel=2,
                )
                style = "svg"
            else:
                # Apply set_size() to the global defaults BEFORE creation
                if size is not None:
                    MmuNorthArrow.set_size(size)

                if rotation == "auto":
                    rot = {"crs": self.projection, "reference": "center"}
                elif isinstance(rotation, (int, float)):
                    rot = {"degrees": rotation}
                else:
                    rot = rotation

                na_kwargs = dict(location=location, rotation=rot, zorder=zorder)
                if scale is not None:
                    na_kwargs["scale"] = scale

                # fancy / shadow: accepts bool or dict
                if style == "simple":
                    na_kwargs["fancy"] = False
                    na_kwargs["shadow"] = False
                else:
                    na_kwargs["fancy"] = fancy
                    na_kwargs["shadow"] = shadow

                # label: accepts str or dict
                if isinstance(label, dict):
                    na_kwargs["label"] = label
                elif label:
                    na_kwargs["label"] = {"text": label}

                # `color` drives the arrow's fill/outline (map-utils mode)
                # via `base` — without this the `color` parameter was
                # ignored, the arrow always stayed black.
                base_style = {"facecolor": color, "edgecolor": color}
                if base is not None:
                    base_style.update(base)
                na_kwargs["base"] = base_style
                if pack is not None:
                    na_kwargs["pack"] = pack
                # to="fig": anchors the arrow on the whole figure rather
                # than on the map axis, via bbox_to_anchor/bbox_transform.
                aob_style = {}
                if to == "fig":
                    aob_style = {
                        "bbox_to_anchor": position,
                        "bbox_transform": self.fig.transFigure,
                    }
                if aob is not None:
                    aob_style.update(aob)
                if aob_style:
                    na_kwargs["aob"] = aob_style
                na_kwargs.update(kwargs)

                na = MmuNorthArrow(**na_kwargs)
                self.ax.add_artist(na)
                self._north_arrow_artist = na
                self._log("🧭 Flèche du Nord ajoutée (map-utils)")
                return self

        # SVG mode (legacy behavior)
        arrow_path = self.get_north_arrows()[arrow - 1]
        img = read_image(arrow_path, color)
        # The embedded SVGs have very heterogeneous native dimensions once
        # rasterized (from 5x16 to 580x580 px depending on the icon):
        # without normalization, the same zoom=1 produces radically
        # different arrow sizes depending on the chosen icon. The largest
        # side of each image is brought to a common reference size before
        # applying the zoom requested by the user.
        _REFERENCE_ARROW_PX = 120
        largest_side = max(img.size)
        auto_scale = _REFERENCE_ARROW_PX / largest_side if largest_side else 1
        imagebox = OffsetImage(img, zoom=zoom * auto_scale)
        xycoords = "figure fraction" if to == "fig" else "axes fraction"
        ab = AnnotationBbox(
            imagebox, position, frameon=False, xycoords=xycoords
        )
        self.ax.add_artist(ab)
        self._north_arrow_artist = ab
        self._log("🧭 Flèche du Nord ajoutée (SVG)")
        return self

    # Alias for compatibility
    add_arrow = add_north_arrow

    def set_north_arrow(self, **kwargs) -> "Map":
        """
        Modifies the existing North arrow created by ``add_north_arrow``.

        Only works if the arrow was created with ``map-utils`` mode
        (``NorthArrow`` object). Each parameter passed is applied
        directly via ``NorthArrow``'s property setters.

        Parameters
        ----------
        location : str, optional
            New position ("upper left", "lower right", …).
        scale : float, optional
            New height in inches.
        rotation : dict or float, optional
            New rotation (dict or degrees).
        fancy : bool or dict, optional
            Enable/configure the fancy style.
        shadow : bool or dict, optional
            Enable/configure the shadow.
        label : dict, optional
            Text configuration (e.g. {"text": "N", "fontsize": 14}).
        base : dict, optional
            Arrow base configuration.
        pack : dict, optional
            Packing configuration.
        aob : dict, optional
            AnnotationBbox configuration.
        zorder : int, optional
            Z-order.
        size : str, optional
            Predefined size ("xs", "sm", "md", "lg", "xl").
            Applies ``NorthArrow.set_size()`` to the global defaults,
            removes the old arrow and recreates a new one.

        Returns
        -------
        Map : Map instance for chaining.
        """
        if self._north_arrow_artist is None:
            raise RuntimeError(
                "Aucune flèche du Nord n'a été ajoutée. "
                "Utilisez add_north_arrow() d'abord."
            )
        if not HAS_MAP_UTILS or not isinstance(
            self._north_arrow_artist, MmuNorthArrow
        ):
            raise RuntimeError(
                "set_north_arrow() nécessite une flèche créée avec "
                "matplotlib-map-utils (style='map-utils', 'fancy' ou 'simple')."
            )

        na = self._north_arrow_artist

        if "size" in kwargs:
            # set_size modifies the global defaults, the artist must be recreated
            MmuNorthArrow.set_size(kwargs.pop("size"))
            na.remove()
            new_na = MmuNorthArrow(
                location=na.location,
                rotation=na.rotation,
                zorder=na.zorder,
            )
            self.ax.add_artist(new_na)
            self._north_arrow_artist = new_na
            na = new_na

        for key, value in kwargs.items():
            if hasattr(na, key):
                setattr(na, key, value)
            else:
                logger.warning(f"Propriété inconnue : {key}")

        self._log("🧭 Flèche du Nord mise à jour")
        return self

    def set_scale_bar(self, **kwargs) -> "Map":
        """
        Modifies the existing scale bar created by ``add_scale_bar``.

        Works with ``MmuScaleBar`` or ``MplScaleBar`` artists. For
        ``MmuScaleBar``, each parameter is applied via its property
        setters.

        Parameters
        ----------
        style : str, optional
            Bar style ("ticks" or "boxes") — MmuScaleBar only.
        location : str, optional
            New position.
        bar : dict, optional
            Bar parameters (projection, unit, length, major_div, etc.).
        labels : dict, optional
            Label parameters (style, loc, fontsize, etc.).
        units : dict, optional
            Unit parameters (loc, label, fontsize, etc.).
        text : dict, optional
            Text parameters.
        aob : dict, optional
            AnnotationBbox configuration.
        zorder : int, optional
            Z-order.
        size : str, optional
            Predefined size ("xs", "sm", "md", "lg", "xl").
            Applies ``ScaleBar.set_size()`` to the global defaults,
            removes the old bar and recreates a new one.

        Returns
        -------
        Map : Map instance for chaining.
        """
        if self._scale_bar_artist is None:
            raise RuntimeError(
                "Aucune barre d'échelle n'a été ajoutée. "
                "Utilisez add_scale_bar() d'abord."
            )

        sb = self._scale_bar_artist

        if HAS_MAP_UTILS and isinstance(sb, MmuScaleBar):
            if "size" in kwargs:
                # set_size modifies the global defaults, it must be recreated
                MmuScaleBar.set_size(kwargs.pop("size"))
                sb.remove()
                new_sb = MmuScaleBar(
                    style=sb.style,
                    location=sb.location,
                    bar=sb.bar,
                    zorder=sb.zorder,
                )
                self.ax.add_artist(new_sb)
                self._scale_bar_artist = new_sb
                sb = new_sb

            for key, value in kwargs.items():
                if hasattr(sb, key):
                    setattr(sb, key, value)
                else:
                    logger.warning(f"Propriété inconnue : {key}")
        elif HAS_MPL_SCALEBAR and isinstance(sb, MplScaleBar):
            for key, value in kwargs.items():
                if hasattr(sb, key):
                    setattr(sb, key, value)
                else:
                    logger.warning(f"Propriété inconnue : {key}")
        else:
            raise RuntimeError(
                "set_scale_bar() nécessite une barre d'échelle créée avec "
                "matplotlib-map-utils ou matplotlib-scalebar."
            )

        self._log("📏 Barre d'échelle mise à jour")
        return self

    def set_inset(self, **kwargs) -> "Map":
        """
        Modifies the existing situation mini-map (inset map).

        Parameters:
        -----------
        facecolor : str, optional
            New background color.
        edgecolor : str, optional
            New border color.
        linewidth : float, optional
            New border thickness.
        alpha : float, optional
            New transparency.
        land_color : str, optional
            New land color (redraws the feature).
        ocean_color : str, optional
            New ocean color (redraws the feature).
        global_view : bool, optional
            If True, shows the global map via set_global().
        extent : list, optional
            [x0, x1, y0, y1] to restrict the inset extent.

        Returns:
        --------
        Map : Map instance for chaining.
        """
        if not hasattr(self, "_inset_ax") or self._inset_ax is None:
            raise RuntimeError(
                "Aucune carte de situation n'a été ajoutée. "
                "Utilisez add_inset_map() d'abord."
            )

        iax = self._inset_ax

        if "facecolor" in kwargs:
            iax.patch.set_facecolor(kwargs["facecolor"])
        if "alpha" in kwargs:
            iax.patch.set_alpha(kwargs["alpha"])
        if "edgecolor" in kwargs:
            for spine in iax.spines.values():
                spine.set_edgecolor(kwargs["edgecolor"])
        if "linewidth" in kwargs:
            for spine in iax.spines.values():
                spine.set_linewidth(kwargs["linewidth"])
        if "global_view" in kwargs and kwargs["global_view"]:
            iax.set_global()
        if "extent" in kwargs:
            iax.set_extent(kwargs["extent"], crs=ccrs.PlateCarree())
        if "land_color" in kwargs:
            iax.add_feature(cfeature.LAND, facecolor=kwargs["land_color"])
        if "ocean_color" in kwargs:
            iax.add_feature(cfeature.OCEAN, facecolor=kwargs["ocean_color"])

        self._log("🔍 Carte de situation mise à jour")
        return self

    # ----------------------------------------------------------------------
    # ================Custom color palette==================================
    # ----------------------------------------------------------------------

    def create_custom_palette(
        self, name: str, colors: List[str], save_palette: bool = True
    ) -> "Map":
        """
        Creates a custom color palette.

        Parameters:
        -----------
        name : str
            Name of the custom palette
        colors : List[str]
            List of color values (hex codes, color names, etc.)
        save_palette : bool
            Save the palette for future use

        Returns:
        --------
        Map : self for method chaining

        Example:
            map.create_custom_palette(name='my_palette',
                                       colors=['#FF5733', 'blue', 'green'],
                                       save_palette=True)
        """
        # Validate colors
        valid_colors = []
        for color in colors:
            try:
                # Test if color is valid
                mcolors.to_rgba(color)
                valid_colors.append(color)
            except ValueError:
                logger.warning(f"Invalid color '{color}' ignored")

        if not valid_colors:
            logger.error("No valid colors provided")
            return self

        if save_palette:
            self.custom_palettes[name] = valid_colors

        self.current_palette = valid_colors
        plt.rcParams["axes.prop_cycle"] = plt.cycler(color=valid_colors)

        self._log(f"Custom palette '{name}' created with {len(valid_colors)} colors")
        return self

    def get_available_palettes(
        self,
        include_custom: bool = True,
        include_seaborn: bool = True,
        include_matplotlib: bool = True,
    ) -> Dict[str, List[str]]:
        """
        Retrieves all available color palettes.
        Delegates to styling.get_available_palettes() and adds
        this instance's custom palettes.
        """
        palettes = get_available_palettes(
            include_custom=include_custom,
            include_seaborn=include_seaborn,
            include_matplotlib=include_matplotlib,
        )
        # Override custom palettes with instance-specific ones
        if include_custom:
            instance_custom = list(self.custom_palettes.keys())
            existing = palettes.get("custom", [])
            palettes["custom"] = list(dict.fromkeys(instance_custom + existing))
        return palettes

    @staticmethod
    def print_available_palettes(category: str = "all", limit: int = None) -> None:
        """
        Displays the available color palettes in a formatted way.

        Parameters:
        -----------
        category : str
            Category to display ('all', 'custom', 'seaborn', 'matplotlib', or a specific category)
        limit : int
            Limits the number of palettes per category

        Example:
            Map.print_available_palettes(category='seaborn', limit=5)
        """
        # Direct palette retrieval without creating a Map instance
        palettes = get_available_palettes()

        categories_to_show = []
        if category == "all":
            categories_to_show = list(palettes.keys())
        elif category == "seaborn":
            categories_to_show = [k for k in palettes.keys() if k.startswith("seaborn")]
        elif category == "matplotlib":
            categories_to_show = [
                k for k in palettes.keys() if k.startswith("matplotlib")
            ]
        elif category in palettes:
            categories_to_show = [category]
        else:
            logger.warning(f"Unknown category: {category}. Available categories: {list(palettes.keys())}")
            return

        logger.info("Available Color Palettes:")
        logger.info("=" * 50)

        for cat in categories_to_show:
            if palettes[cat]:  # Only show non-empty categories
                logger.info(f"\n{cat.replace('_', ' ').title()}:")
                logger.info("-" * 30)

                palette_list = palettes[cat][:limit] if limit else palettes[cat]

                for i, palette in enumerate(palette_list, 1):
                    logger.info(f"{i:3d}. {palette}")

                if limit and len(palettes[cat]) > limit:
                    remaining = len(palettes[cat]) - limit
                    logger.info(f"    ... and {remaining} more")

    def preview_palette(self, palette_name: str, n_colors: int = 8) -> "Map":
        """
        Previews a color palette as a colored bar.

        Parameters:
        -----------
        palette_name : str
            Name of the palette to preview
        n_colors : int
            Number of colors to display

        Returns:
        --------
        Map : self for method chaining

        Example:
            map.preview_palette('Set1', n_colors=5)
        """
        # Clear current plot
        self.ax.clear()

        # Get colors
        colors = []
        if palette_name in self.custom_palettes:
            colors = self.custom_palettes[palette_name][:n_colors]
        else:
            try:
                # Try seaborn palette
                colors = sns.color_palette(palette_name, n_colors)
            except (ValueError, KeyError):
                try:
                    # Try matplotlib colormap
                    cmap = load_cmap(palette_name)
                    colors = [cmap(i / (n_colors - 1)) for i in range(n_colors)]
                except Exception:
                    logger.warning(f"Palette '{palette_name}' not found")
                    return self

        # Create color preview
        y_pos = [0] * len(colors)
        x_pos = range(len(colors))

        for i, color in enumerate(colors):
            self.ax.barh(0, 1, left=i, color=color, edgecolor="white", linewidth=0.5)

        self.ax.set_xlim(0, len(colors))
        self.ax.set_ylim(-0.5, 0.5)
        self.ax.set_yticks([])
        self.ax.set_xticks(range(len(colors)))
        self.ax.set_xticklabels([f"C{i+1}" for i in range(len(colors))])
        self.ax.set_title(f"Palette Preview: {palette_name}")

        # Add color codes as text
        for i, color in enumerate(colors):
            if isinstance(color, str):
                color_text = color
            else:
                # Convert to hex
                color_text = mcolors.to_hex(color)
            self.ax.text(
                i + 0.5,
                0,
                color_text,
                ha="center",
                va="center",
                rotation=90,
                fontsize=8,
                color="white",
                weight="bold",
            )

        return self

    def generate_gradient_palette(
        self,
        name: str,
        start_color: str,
        end_color: str,
        n_colors: int = 10,
        save_palette: bool = True,
    ) -> "Map":
        """
        Generates a gradient palette between two colors.

        Parameters:
        -----------
        name : str
            Palette name
        start_color : str
            Starting color
        end_color : str
            Ending color
        n_colors : int
            Number of colors in the gradient
        save_palette : bool
            Save the palette

        Returns:
        --------
        Map : self for method chaining

        Example:
            map.generate_gradient_palette(name='my_gradient',
                                           start_color='blue',
                                           end_color='red',
                                           n_colors=5,
                                           save_palette=True)
        """
        try:
            # Create gradient
            start_rgb = mcolors.to_rgba(start_color)
            end_rgb = mcolors.to_rgba(end_color)

            colors = []
            for i in range(n_colors):
                ratio = i / (n_colors - 1)
                r = start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio
                g = start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio
                b = start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio
                a = start_rgb[3] * (1 - ratio) + end_rgb[3] * ratio

                colors.append(mcolors.to_hex((r, g, b, a)))

            if save_palette:
                self.custom_palettes[name] = colors

            self.current_palette = colors
            plt.rcParams["axes.prop_cycle"] = plt.cycler(color=colors)

            self._log(f"Gradient palette '{name}' created: {start_color} → {end_color}")
            return self

        except ValueError as e:
            logger.error(f"Error creating gradient: {e}")
            return self

    # ----------------------------------------------------------------------
    # ================Custom font===========================================
    # ----------------------------------------------------------------------

    def get_available_fonts(self, pattern: str = None, sort: bool = True) -> List[str]:
        """
        Retrieves the list of fonts available on the system.

        Parameters:
        -----------
        pattern : str, optional
            Filters fonts containing this pattern (case-insensitive)
        sort : bool
            Sort the names alphabetically

        Returns:
        --------
        List[str] : List of available font names

        Example:
            map.get_available_fonts(pattern='Arial', sort=True)
        """
        # Get all font properties
        fonts = [f.name for f in fm.fontManager.ttflist]

        # Remove duplicates
        fonts = list(set(fonts))

        # Filter by pattern if provided
        if pattern:
            fonts = [font for font in fonts if pattern.lower() in font.lower()]

        # Sort if requested
        if sort:
            fonts.sort()

        return fonts

    @staticmethod
    def print_available_fonts(pattern: str = None, limit: int = None) -> None:
        """
        Displays the available fonts in the console in a formatted way.

        Parameters:
        -----------
        pattern : str, optional
            Filters fonts containing this pattern
        limit : int, optional
            Limits the number of fonts displayed

        Example:
            Map.print_available_fonts(pattern='Arial', limit=10)
        """
        # Direct font retrieval without creating a Map instance
        all_fonts = sorted(set(f.name for f in fm.fontManager.ttflist))
        if pattern:
            all_fonts = [f for f in all_fonts if pattern.lower() in f.lower()]
        fonts = all_fonts[:limit] if limit else all_fonts

        filter_info = f' (filtered by "{pattern}")' if pattern else ''
        logger.info(f"Available fonts{filter_info}: {len(fonts)} found")
        logger.info("-" * 50)

        # Print in columns for better readability
        for i, font in enumerate(fonts, 1):
            logger.info(f"{i:3d}. {font}")

        if limit and len(all_fonts) > limit:
            remaining = len(all_fonts) - limit
            logger.info(f"\n... and {remaining} more fonts")

    def set_font(
        self, family: str = "sans-serif", size: int = 10, weight: str = "normal"
    ) -> "Map":
        """
        Sets the global font properties.

        Parameters:
        -----------
        family : str
            Font family name (use get_available_fonts() to see options)
        size : int
            Font size
        weight : str
            Font weight ('normal', 'bold', 'light', etc.)

        Example:
            map.set_font(family='Arial', size=12, weight='bold')
        """
        # Validate font exists
        available_fonts = self.get_available_fonts()
        if (
            family not in ["sans-serif", "serif", "monospace", "fantasy", "cursive"]
            and family not in available_fonts
        ):
            self._log(
                f"Warning: Font '{family}' not found. Available fonts can be checked with get_available_fonts()"
            )
            self._log(f"Using default font instead.")
            family = "sans-serif"

        plt.rcParams.update(
            {"font.family": family, "font.size": size, "font.weight": weight}
        )
        return self

    # ----------------------------------------------------------------------
    # ================Custom boundary=======================================
    # ----------------------------------------------------------------------

    def _update_bounds(self, gdf):
        """Automatic bounds update based on the added data."""
        bounds = gdf.total_bounds
        if self._first_layer:
            self.bounds = [
                min(self.bounds[0], bounds[0]),
                min(self.bounds[1], bounds[1]),
                max(self.bounds[2], bounds[2]),
                max(self.bounds[3], bounds[3]),
            ]
        else:
            self.bounds = bounds.tolist()
            self._first_layer = True

    def _apply_smart_centering(self):
        """
        Applies smart centering based on the paper dimensions and the data.
        """
        # Compute data dimensions
        data_width = self.bounds[2] - self.bounds[0]
        data_height = self.bounds[3] - self.bounds[1]
        data_center_x = (self.bounds[0] + self.bounds[2]) / 2
        data_center_y = (self.bounds[1] + self.bounds[3]) / 2

        # Degenerate case: a single point (or features perfectly aligned
        # horizontally/vertically) gives a zero width and/or height.
        # Without this guard, set_extent() receives a zero-size extent on
        # that axis; cartopy then widens it on its own with a
        # UserWarning, but the "smart" centering no longer does anything
        # smart. Arbitrary 1° fallback view around the center — the user
        # can still refine it via set_extent().
        _fallback_span = 1.0  # degrees
        if data_width == 0:
            data_width = _fallback_span
        if data_height == 0:
            data_height = _fallback_span

        # Retrieve figure dimensions
        fig_width_inches, fig_height_inches = self.figsize

        # Compute the figure's aspect ratio
        fig_aspect_ratio = fig_width_inches / fig_height_inches

        # Compute the data's aspect ratio
        data_aspect_ratio = data_width / data_height if data_height > 0 else 1

        # Determine the margin suited to the paper format
        if self.paper_info:
            paper_format = self.paper_info["format"]
            orientation = self.paper_info["orientation"]

            # Margins adapted to the format
            if paper_format in ["A4", "A5"]:
                base_margin = 0.1  # Larger margin for small formats
            elif paper_format in ["A3", "A2"]:
                base_margin = 0.08  # Medium margin for medium formats
            elif paper_format in ["A1", "A0"]:
                base_margin = 0.05  # Reduced margin for large formats
            else:
                base_margin = 0.07  # Default margin

            # Adjustment based on orientation
            if orientation == "portrait":
                margin_x = base_margin
                margin_y = base_margin * 0.8  # Reduced vertical margin in portrait
            else:  # landscape
                margin_x = base_margin * 0.8  # Reduced horizontal margin in landscape
                margin_y = base_margin
        else:
            # Default values if no paper info
            margin_x = margin_y = 0.07

        # Compute optimal display dimensions
        if fig_aspect_ratio > data_aspect_ratio:
            # The figure is wider than the data
            # Adjust height first
            display_height = data_height * (1 + 2 * margin_y)
            display_width = display_height * fig_aspect_ratio
        else:
            # The figure is taller than the data
            # Adjust width first
            display_width = data_width * (1 + 2 * margin_x)
            display_height = display_width / fig_aspect_ratio

        # Compute the final centered extent
        extent = [
            data_center_x - display_width / 2,
            data_center_x + display_width / 2,
            data_center_y - display_height / 2,
            data_center_y + display_height / 2,
        ]

        # Apply the extent
        self.ax.set_extent(extent, crs=ccrs.PlateCarree())

        # Display debug information
        self._log(f"📊 Centrage intelligent appliqué:")
        self._log(
            f"   Format: {self.paper_info['format'] if self.paper_info else 'Personnalisé'} "
            f"({self.paper_info['orientation'] if self.paper_info else 'N/A'})"
        )
        self._log(f"   Ratio figure: {fig_aspect_ratio:.2f}")
        self._log(f"   Ratio données: {data_aspect_ratio:.2f}")
        self._log(
            f"   Étendue: [{extent[0]:.2f}, {extent[1]:.2f}, {extent[2]:.2f}, {extent[3]:.2f}]"
        )

    def center_on_bounds(self, bounds, margin="auto"):
        """
        Centers the map on specific bounds with adapted margins.

        Parameters:
        -----------
        bounds : list or tuple
            Bounds [minx, miny, maxx, maxy] to center on
        margin : str, float, or dict
            'auto' for automatic margin, float for uniform margin,
            or dict {'x': float, 'y': float} for differentiated margins
        """
        # Update the data bounds
        self.bounds = bounds

        # Compute dimensions
        data_width = bounds[2] - bounds[0]
        data_height = bounds[3] - bounds[1]
        data_center_x = (bounds[0] + bounds[2]) / 2
        data_center_y = (bounds[1] + bounds[3]) / 2

        # Margin handling
        if margin == "auto":
            # Automatic margin based on the paper format
            if self.paper_info:
                paper_format = self.paper_info["format"]
                if paper_format in ["A4", "A5"]:
                    margin_x = margin_y = 0.1
                elif paper_format in ["A3", "A2"]:
                    margin_x = margin_y = 0.08
                elif paper_format in ["A1", "A0"]:
                    margin_x = margin_y = 0.05
                else:
                    margin_x = margin_y = 0.07
            else:
                margin_x = margin_y = 0.07
        elif isinstance(margin, dict):
            margin_x = margin.get("x", 0.05)
            margin_y = margin.get("y", 0.05)
        else:
            margin_x = margin_y = float(margin)

        # Compute the extent with margins
        fig_width_inches, fig_height_inches = self.figsize
        fig_aspect_ratio = fig_width_inches / fig_height_inches
        data_aspect_ratio = data_width / data_height if data_height > 0 else 1

        if fig_aspect_ratio > data_aspect_ratio:
            display_height = data_height * (1 + 2 * margin_y)
            display_width = display_height * fig_aspect_ratio
        else:
            display_width = data_width * (1 + 2 * margin_x)
            display_height = display_width / fig_aspect_ratio

        extent = [
            data_center_x - display_width / 2,
            data_center_x + display_width / 2,
            data_center_y - display_height / 2,
            data_center_y + display_height / 2,
        ]

        self.ax.set_extent(extent, crs=ccrs.PlateCarree())

        return self

    def get_optimal_margins(self):
        """
        Returns the optimal margins for the current paper format.

        Returns:
        --------
        dict: Recommended margins {'x': float, 'y': float}
        """
        if self.paper_info:
            paper_format = self.paper_info["format"]
            orientation = self.paper_info["orientation"]

            if paper_format in ["A4", "A5"]:
                base_margin = 0.1
            elif paper_format in ["A3", "A2"]:
                base_margin = 0.08
            elif paper_format in ["A1", "A0"]:
                base_margin = 0.05
            else:
                base_margin = 0.07

            if orientation == "portrait":
                return {"x": base_margin, "y": base_margin * 0.8}
            else:
                return {"x": base_margin * 0.8, "y": base_margin}
        else:
            return {"x": 0.07, "y": 0.07}

    # ----------------------------------------------------------------------
    # ================Custom legend=========================================
    # ----------------------------------------------------------------------
    def custom_legend(
        self,
        elements=None,
        title=None,
        loc="best",
        bbox_to_anchor=None,
        ncol=1,
        fontsize=10,
        title_fontsize=12,
        frameon=True,
        fancybox=True,
        shadow=True,
        framealpha=0.9,
        facecolor="white",
        edgecolor="black",
        linewidth=1,
        columnspacing=2,
        handlelength=2,
        handletextpad=0.8,
        borderpad=1,
        markerscale=1,
        markerfirst=True,
        numpoints=1,
        scatterpoints=1,
        replace=True,
        **kwargs,
    ):
        """
        Creates a custom legend with full control over appearance.

        Parameters:
        -----------
        elements : list, optional
            List of custom legend elements. If None, uses self.legend_elements
        title : str, optional
            Legend title
        loc : str or int
            Legend position ('best', 'upper right', 'lower left', etc.)
        bbox_to_anchor : tuple, optional
            Absolute position (x, y) or (x, y, width, height)
        ncol : int
            Number of columns in the legend
        fontsize : int or str
            Text font size
        title_fontsize : int or str
            Title font size
        frameon : bool
            Show the legend frame
        fancybox : bool
            Rounded corners for the frame
        shadow : bool
            Drop shadow
        framealpha : float
            Frame transparency (0-1)
        facecolor : str
            Frame background color
        edgecolor : str
            Frame border color
        linewidth : float
            Border thickness
        columnspacing : float
            Spacing between columns
        handlelength : float
            Symbol length
        handletextpad : float
            Spacing between symbol and text
        borderpad : float
            Internal frame padding
        markerscale : float
            Marker scale
        markerfirst : bool
            Marker before or after the text
        numpoints : int
            Number of points for lines
        scatterpoints : int
            Number of points for scatter
        replace : bool
            Replace the existing legend or add to it
        **kwargs : dict
            Other parameters for matplotlib.legend()

        Returns:
        --------
        Map: Map instance for chaining
        """
        self._log("🛑Element de légende ajouté", elements)
        # Use the provided elements or the stored ones
        if elements is None:
            self.legend_elements = self.legend_elements
        else:
            self.legend_elements = self.legend_elements + elements
        legend_elements = self.legend_elements

        if not legend_elements:
            logger.warning("Aucun élément de légende disponible")
            return self

        # Prepare the legend parameters
        legend_params = {
            "handles": legend_elements,
            "loc": loc,
            "ncol": ncol,
            "fontsize": fontsize,
            "frameon": frameon,
            "fancybox": fancybox,
            "shadow": shadow,
            "framealpha": framealpha,
            "facecolor": facecolor,
            "edgecolor": edgecolor,
            "columnspacing": columnspacing,
            "handlelength": handlelength,
            "handletextpad": handletextpad,
            "borderpad": borderpad,
            "markerscale": markerscale,
            "markerfirst": markerfirst,
            "numpoints": numpoints,
            "scatterpoints": scatterpoints,
        }
        self.legend_params = {**self.legend_params, **legend_params, **kwargs}
        legend_params = self.legend_params
        # Add the title if provided
        if title:
            legend_params["title"] = title
            legend_params["title_fontsize"] = title_fontsize

        # Add bbox_to_anchor if provided
        if bbox_to_anchor:
            legend_params["bbox_to_anchor"] = bbox_to_anchor

        legend_params.pop("linewidth", None)

        # Remove or replace the existing legend
        if replace and hasattr(self.ax, "legend_") and self.ax.legend_:
            self.ax.legend_.remove()

        # Create the legend
        legend = self.ax.legend(**legend_params)

        # Store the reference for later modifications
        self.current_legend = legend

        self._log(f"✅ Légende personnalisée créée avec {len(legend_elements)} éléments")

        return self

    def add_legend_element(
        self,
        element_type,
        label,
        color="black",
        marker="o",
        linestyle="-",
        linewidth=2,
        markersize=8,
        alpha=1.0,
        **kwargs,
    ):
        """
        Adds a custom element to the legend.

        Parameters:
        -----------
        element_type : str
            Element type ('point', 'line', 'patch', 'text')
        label : str
            Element text
        color : str
            Element color
        marker : str
            Marker type for points
        linestyle : str
            Line style ('-', '--', '-.', ':')
        linewidth : float
            Line thickness
        markersize : float
            Marker size
        alpha : float
            Transparency (0-1)
        **kwargs : dict
            Other parameters specific to the element type

        Returns:
        --------
        Map: Map instance for chaining
        """

        if element_type == "point":
            element = mlines.Line2D(
                [],
                [],
                color=color,
                marker=marker,
                linestyle="None",
                markersize=markersize,
                alpha=alpha,
                label=label,
                **kwargs,
            )

        elif element_type == "line":
            element = mlines.Line2D(
                [],
                [],
                color=color,
                linestyle=linestyle,
                linewidth=linewidth,
                alpha=alpha,
                label=label,
                **kwargs,
            )

        elif element_type == "patch":
            element = mpatches.Patch(color=color, alpha=alpha, label=label, **kwargs)

        elif element_type == "text":
            # Simple text element (uses a transparent patch)
            element = mpatches.Patch(color="none", label=label, **kwargs)

        else:
            raise ValueError(f"Type d'élément non supporté: {element_type}")

        self.legend_elements.append(element)
        self._log(f"➕ Élément '{label}' ajouté à la légende")

        return self

    def create_legend_from_column(
        self,
        gdf,
        column,
        element_type="patch",
        cmap=None,
        color_scheme="viridis",
        title=None,
        max_items=25,
        sort_by="value",
        **legend_kwargs,
    ):
        """
        Automatically creates a legend based on a GeoDataFrame column.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            Source GeoDataFrame
        column : str
            Column name for the legend
        element_type : str
            Legend element type ('patch', 'point', 'line')
        color_scheme : str or list
            Color scheme or list of colors
        title : str
            Legend title (uses the column name by default)
        max_items : int
            Maximum number of items in the legend
        sort_by : str
            Sort by 'value', 'alphabetical', or 'frequency'
        **legend_kwargs : dict
            Parameters for custom_legend()

        Returns:
        --------
        Map: Map instance for chaining
        """
        if cmap is not None:
            color_scheme = cmap
        if column not in gdf.columns:
            raise ValueError(f"Colonne '{column}' non trouvée dans le GeoDataFrame")

        # Extract unique values
        unique_values = gdf[column].dropna().unique()

        # Sort according to the specified method
        if sort_by == "alphabetical":
            unique_values = sorted(unique_values)
        elif sort_by == "frequency":
            value_counts = gdf[column].value_counts()
            unique_values = value_counts.index.tolist()
        elif sort_by == "value":
            try:
                unique_values = sorted(unique_values)
            except TypeError:
                unique_values = sorted(unique_values, key=str)

        # Limit the number of items
        if len(unique_values) > max_items:
            self._log(
                f"Il y a plus de 25 éléments uniques dans la colonne {column} ({len(unique_values)} valeurs exactement). Modifiez la valeur de max_items à {len(unique_values)} pour afficher tous les éléments."
            )
            unique_values = unique_values[: max_items - 1]
            show_others = True
        else:
            show_others = False

        # Generate colors
        if isinstance(color_scheme, str):
            # Use a matplotlib palette
            cmap = load_cmap(color_scheme)
            colors = [cmap(i / len(unique_values)) for i in range(len(unique_values))]
        elif isinstance(color_scheme, list):
            # Provided list of colors
            colors = color_scheme[: len(unique_values)]
            if len(colors) < len(unique_values):
                # Repeat colors if necessary
                colors = (colors * (len(unique_values) // len(colors) + 1))[
                    : len(unique_values)
                ]
        else:
            raise ValueError("color_scheme doit être une chaîne ou une liste")

        # Create legend elements
        legend_elements = []
        for value, color in zip(unique_values, colors):
            # Convert the color if necessary
            if isinstance(color, tuple) and len(color) == 4:
                color = mcolors.to_hex(color)

            if element_type == "patch":
                element = mpatches.Patch(color=color, label=str(value))
            elif element_type == "point":
                element = mlines.Line2D(
                    [],
                    [],
                    color=color,
                    marker="o",
                    linestyle="None",
                    markersize=8,
                    label=str(value),
                )
            elif element_type == "line":
                element = mlines.Line2D(
                    [], [], color=color, linewidth=2, label=str(value)
                )

            legend_elements.append(element)

        # Add an "Others" element if necessary
        if show_others:
            if element_type == "patch":
                element = mpatches.Patch(color="lightgray", label="Autres...")
            elif element_type == "point":
                element = mlines.Line2D(
                    [],
                    [],
                    color="lightgray",
                    marker="o",
                    linestyle="None",
                    markersize=8,
                    label="Autres...",
                )
            elif element_type == "line":
                element = mlines.Line2D(
                    [], [], color="lightgray", linewidth=2, label="Autres..."
                )
            legend_elements.append(element)

        # Create the legend
        legend_title = title if title else column.replace("_", " ").title()

        self.custom_legend(
            elements=legend_elements, title=legend_title, **legend_kwargs
        )

        self._log(
            f"📊 Légende créée pour la colonne '{column}' avec {len(legend_elements)} éléments"
        )

        return self

    def add_swatch_legend(
        self,
        items,
        xy,
        rect_width=2,
        rect_height=1.5,
        y_step=1.5,
        label_dx=2.5,
        label_dy=0.7,
        fontsize=12,
        color="black",
        edge_color="black",
        linewidth=0.6,
        font=None,
        ha="left",
        va="center",
        to="ax",
    ):
        """
        Adds a "hand-made" legend: color rectangles stacked vertically at
        a given position (like on a printed map), instead of an axis
        corner via `custom_legend()`.

        Parameters:
        -----------
        items : list of (label, color)
            (text, color) pairs to display, top to bottom.
        xy : tuple
            Position (x, y) of the top-left corner of the first rectangle.
        rect_width, rect_height : float
            Rectangle dimensions (same units as xy).
        y_step : float
            Vertical spacing between successive rectangles.
        label_dx, label_dy : float
            Text offset relative to the rectangle corner.
        fontsize : int
            Text size.
        color : str
            Text color.
        edge_color, linewidth :
            Rectangle outline.
        font : FontProperties, optional
            Text font (via google_font/local_font/path_font).
        ha, va : str
            Text alignment.
        to : str
            ``"ax"`` (default, geographic coordinates) or ``"fig"``
            (figure coordinates 0-1, as with `add_custom_text`).

        Returns:
        --------
        Map : self for method chaining

        Example:
        --------
        >>> items = [(lab, cmap(v)) for lab, v in zip(labels, values)]
        >>> map_obj.add_swatch_legend(items, xy=(35, 65), font=my_font)
        >>> map_obj.add_swatch_legend(items, xy=(0.05, 0.4), to="fig")
        """
        if to == "ax":
            add_patch, add_text = self.ax.add_patch, self.ax.text
            rect_transform = ccrs.PlateCarree()
            text_kwargs = {"transform": ccrs.PlateCarree()}
        elif to == "fig":
            add_patch, add_text = self.fig.add_artist, self.fig.text
            rect_transform = self.fig.transFigure
            text_kwargs = {}
        else:
            raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

        text_kwargs.update({"fontsize": fontsize, "color": color, "ha": ha, "va": va})
        if font is not None:
            text_kwargs["fontproperties"] = font

        x0, y0 = xy
        for i, (label, swatch_color) in enumerate(items):
            y = y0 - i * y_step
            add_patch(
                plt.Rectangle(
                    (x0, y), rect_width, rect_height,
                    color=swatch_color, ec=edge_color, lw=linewidth,
                    transform=rect_transform,
                )
            )
            add_text(x0 + label_dx, y + label_dy, label, **text_kwargs)

        return self

    def legend_presets(self, preset="default", **override_kwargs):
        """
        Applies legend presets.

        Parameters:
        -----------
        preset : str
            Preset name ('default', 'minimal', 'fancy', 'academic', 'poster,'simple')
        **override_kwargs : dict
            Parameters to override the preset

        Returns:
        --------
        Map: Map instance for chaining
        """
        presets = {
            "simple": {
                "fontsize": 11,
                "title_fontsize": 13,
                "frameon": True,
                "fancybox": True,
                "shadow": False,
                "framealpha": 1.0,
                "facecolor": "white",
                "edgecolor": "#888",
                "borderpad": 1.0,
                "columnspacing": 2.0,
            },
            "default": {
                "fontsize": 10,
                "frameon": True,
                "fancybox": True,
                "shadow": True,
                "framealpha": 0.9,
                "facecolor": "white",
                "edgecolor": "black",
            },
            "minimal": {
                "fontsize": 9,
                "frameon": False,
                "fancybox": False,
                "shadow": False,
                "framealpha": 1.0,
                "handlelength": 1.5,
                "handletextpad": 0.5,
            },
            "fancy": {
                "fontsize": 11,
                "title_fontsize": 14,
                "frameon": True,
                "fancybox": True,
                "shadow": True,
                "framealpha": 0.95,
                "facecolor": "#f8f9fa",
                "edgecolor": "#88939e",
                # 'linewidth': 1.5,
                "borderpad": 1.5,
                "columnspacing": 2.5,
            },
            "academic": {
                "fontsize": 8,
                "title_fontsize": 10,
                "frameon": True,
                "fancybox": False,
                "shadow": False,
                "framealpha": 1.0,
                "facecolor": "white",
                "edgecolor": "black",
                # 'linewidth': 0.8,
                "handlelength": 1.8,
                "handletextpad": 0.6,
            },
            "poster": {
                "fontsize": 14,
                "title_fontsize": 18,
                "frameon": True,
                "fancybox": True,
                "shadow": True,
                "framealpha": 0.9,
                "facecolor": "white",
                "edgecolor": "black",
                # 'linewidth': 2,
                "borderpad": 2,
                "handlelength": 3,
                "markerscale": 1.5,
            },
        }

        if preset not in presets:
            available_presets = ", ".join(presets.keys())
            raise ValueError(
                f"Préréglage '{preset}' non disponible. "
                f"Préréglages disponibles: {available_presets}"
            )

        # Merge the preset parameters with the overrides
        params = {**presets[preset], **override_kwargs}
        self._log(params)

        self.custom_legend(**params)

        self._log(f"🎨 Préréglage '{preset}' appliqué à la légende")

        return self

    def remove_legend(self):
        """
        Removes the current legend.

        Returns:
        --------
        Map: Map instance for chaining
        """
        if hasattr(self.ax, "legend_") and self.ax.legend_:
            self.ax.legend_.remove()
            self._log("🗑️  Légende supprimée")
        else:
            logger.warning("Aucune légende à supprimer")

        return self

    def clear_legend_elements(self):
        """
        Clears the list of legend elements.

        Returns:
        --------
        Map: Map instance for chaining
        """
        self.legend_elements = []
        self._log("🧹 Éléments de légende effacés")

        return self

    # ----------------------------------------------------------------------
    # ================Layer management======================================
    # ----------------------------------------------------------------------

    def list_layers(self) -> List[Dict[str, Any]]:
        """
        Lists all layers added to the map.

        Returns:
        --------
        List[Dict]: List of dictionaries with each layer's info
            (index, type, label, rendered)
        """
        summary = []
        for i, layer in enumerate(self.layers):
            info = {
                "index": i,
                "type": layer.get("type", "unknown"),
                "label": layer.get("label"),
                "rendered": layer.get("rendered", False),
            }
            summary.append(info)
            logger.info(
                f"  [{i}] {info['type']:10s} | "
                f"label={info['label'] or '—':20s} | "
                f"rendered={info['rendered']}"
            )
        logger.info(f"📋 {len(self.layers)} couche(s) au total")
        return summary

    def remove_layer(self, index: int = None, label: str = None) -> "Map":
        """
        Removes a layer by its index or label.

        Parameters:
        -----------
        index : int, optional
            Index of the layer to remove (see list_layers())
        label : str, optional
            Label of the layer to remove. If several layers share the
            same label, only the first one found is removed.

        Returns:
        --------
        Map: Map instance for chaining

        Example:
        --------
        >>> m = Map()
        >>> m.add_polygons(gdf, label="Régions")
        >>> m.list_layers()
        >>> m.remove_layer(label="Régions")   # by label
        >>> m.remove_layer(index=0)            # by index
        """
        if index is None and label is None:
            raise ValueError("Fournir index ou label pour identifier la couche à supprimer.")

        if index is not None:
            if not 0 <= index < len(self.layers):
                raise IndexError(
                    f"Index {index} hors limites (0–{len(self.layers) - 1})."
                )
            removed = self.layers.pop(index)
            self._log(f"🗑️  Couche [{index}] ({removed.get('type')}) supprimée")
        else:
            for i, layer in enumerate(self.layers):
                if layer.get("label") == label:
                    removed = self.layers.pop(i)
                    self._log(f"🗑️  Couche [{i}] label='{label}' ({removed.get('type')}) supprimée")
                    break
            else:
                logger.warning(f"Aucune couche avec le label '{label}' trouvée")

        self._invalidate_render()
        return self

    def clear_layers(self) -> "Map":
        """
        Removes all layers from the map.

        Returns:
        --------
        Map: Map instance for chaining
        """
        count = len(self.layers)
        self.layers.clear()
        self.legend_elements.clear()
        self._invalidate_render()
        self._log(f"🧹 {count} couche(s) supprimée(s)")
        return self

    # ----------------------------------------------------------------------
    # ================custom scale bar======================================
    # ----------------------------------------------------------------------


    def add_scale_bar(self, length=None, location="lower left", linewidth=2,
                      units="km", color="black", fontsize=11,
                      pad=0.1, alpha=1, label=None,
                      style="auto", box_color="white", box_alpha=0.8,
                      scale_loc="bottom", label_loc="top",
                      add_as_layer=True,
                      bar_style="boxes", major_div=None, minor_div=None,
                      size=None, bar=None, labels=None, text=None,
                      to="ax", position=(0.05, 0.05), aob=None,
                      font=None,
                      **kwargs):
        """
        Adds a scale bar to the map.

        Automatically selects the best available engine:
        ``matplotlib-map-utils`` > ``matplotlib-scalebar`` > manual drawing.

        Parameters
        ----------
        length : float, optional
            Desired length (in *units*). Auto-computed if None.
        location : str or tuple
            Position: matplotlib string ("lower left", "upper right", …)
            or tuple (x, y) in relative coordinates 0-1 (manual mode).
        linewidth : float
            Line thickness.
        units : str
            Display unit: "km", "m", "mi", "ft", "nmi".
        color : str
            Main color.
        fontsize : int
            Font size.
        pad : float
            Text / bar spacing (manual mode only).
        alpha : float
            Transparency.
        label : str, optional
            Custom label.
        style : str
            Rendering mode:
            - ``"auto"``: best available library
              (map-utils > scalebar > manual).
            - ``"map-utils"`` / ``"ticks"`` / ``"boxes"``:
              forces matplotlib-map-utils.
            - ``"scalebar"``: forces matplotlib-scalebar.
            - ``"manual"``: hand-drawn (legacy behavior).
        box_color : str
            Background color (scalebar mode).
        box_alpha : float
            Background transparency (scalebar mode).
        scale_loc : str
            Bar position ("top", "bottom") — scalebar mode.
        label_loc : str
            Text position ("top", "bottom", "left", "right") —
            scalebar mode.
        add_as_layer : bool
            If True, deferred rendering on show()/save().
        bar_style : str
            Bar style for map-utils: "boxes" or "ticks".
        major_div : int, optional
            Number of major divisions (map-utils mode). Auto-computed if
            None (matplotlib-map-utils default behavior).
        minor_div : int, optional
            Number of minor divisions (map-utils mode). Auto-computed if
            None (matplotlib-map-utils default behavior).
        size : str, optional
            Predefined size ("sm", "md", "lg", "xl") — map-utils mode.
        bar : dict, optional
            Bar parameters dictionary (map-utils mode).
            Keys: projection, unit, max, length, major_div, minor_div, etc.
        labels : dict, optional
            Label parameters dictionary (map-utils mode).
            Keys: style, loc, format, fontsize, textcolors, etc.
        text : dict, optional
            Text parameters dictionary (map-utils mode).
        to : str
            ``"ax"`` (default, ``location`` relative to the main map
            axis) or ``"fig"`` (relative to the whole figure — e.g. to
            place the scale bar in the margin, outside the axis). Same
            convention as ``add_north_arrow``. ``"map-utils"`` and
            ``"scalebar"`` modes only — no effect (with a warning) in
            ``"manual"`` mode, which is intrinsically anchored to the
            axis's geographic coordinates.
        position : tuple (x, y)
            Exact anchor point in figure coordinates (0-1), used only if
            ``to="fig"`` (ignored otherwise). ``location`` is still used
            to determine which corner of the bar touches that point.
        aob : dict, optional
            Configuration of the underlying AnchoredOffsetBox (map-utils
            mode) — merged with, and taking priority over, the one
            derived from ``to``.
        font : matplotlib.font_manager.FontProperties, optional
            Precise font for the text (e.g. via ``google_font()``).
            matplotlib-map-utils only supports a generic CSS family
            (``fontfamily`` in ``labels``/``text``: "serif",
            "sans-serif", "cursive", "fantasy", "monospace") — if this
            style is active and ``font`` is provided, automatically
            switches to ``style="scalebar"`` (with a warning) to actually
            apply it. Works natively in ``"scalebar"`` and ``"manual"``
            modes.
        **kwargs
            Additional parameters passed to the library.
        """
        scale_bar_info = {
            "length": length,
            "location": location,
            "linewidth": linewidth,
            "units": units,
            "color": color,
            "fontsize": fontsize,
            "pad": pad,
            "alpha": alpha,
            "label": label,
            "style": style,
            "box_color": box_color,
            "box_alpha": box_alpha,
            "scale_loc": scale_loc,
            "label_loc": label_loc,
            "bar_style": bar_style,
            "major_div": major_div,
            "minor_div": minor_div,
            "size": size,
            "bar": bar,
            "labels": labels,
            "text": text,
            "to": to,
            "position": position,
            "aob": aob,
            "font": font,
            "kwargs": kwargs,
        }
        if add_as_layer:
            self.layers.append({
                "type": "scalebar",
                "name": scale_bar_info.get("label"),
                "data": None,
                "style": scale_bar_info,
                "label": scale_bar_info.get("label"),
                "src": None,
                "params": scale_bar_info,
            })
        else:
            self._draw_scale_bar(**scale_bar_info)
        return self

    def _compute_scalebar_dx(self):
        """Computes *dx* (meters per axis unit) for matplotlib-scalebar."""
        is_geographic = isinstance(
            self.projection, (ccrs.PlateCarree, ccrs.Geodetic)
        )
        if is_geographic:
            x0, x1 = self.ax.get_xlim()
            y0, y1 = self.ax.get_ylim()
            mid_lat = float(np.clip((y0 + y1) / 2, -89, 89))
            mid_lon = float((x0 + x1) / 2)
            geod = Geod(ellps="WGS84")
            _, _, dist = geod.inv(mid_lon, mid_lat, mid_lon + 1, mid_lat)
            return abs(dist)
        return 1

    def _draw_scale_bar(self, length=None, location="lower left", linewidth=2,
                        units="km", color="black", fontsize=11,
                        pad=0.05, alpha=1, label=None,
                        style="auto", box_color="white", box_alpha=0.8,
                        scale_loc="bottom", label_loc="top",
                        bar_style="boxes", major_div=None, minor_div=None,
                        size=None, bar=None, labels=None, text=None,
                        to="ax", position=(0.05, 0.05), aob=None,
                        font=None,
                        kwargs=None):
        """Draws the scale bar on self.ax."""
        if kwargs is None:
            kwargs = {}

        # ------- style resolution -------
        if style == "auto":
            if HAS_MAP_UTILS:
                style = "map-utils"
            elif HAS_MPL_SCALEBAR:
                style = "scalebar"
            else:
                style = "manual"

        # Aliases for map-utils sub-styles
        if style in ("ticks", "boxes"):
            bar_style = style
            style = "map-utils"

        # matplotlib-map-utils cannot apply a precise font (FontProperties):
        # its fontfamily parameter only accepts the 5 generic CSS families
        # ("serif", "sans-serif", "cursive", "fantasy", "monospace"), not a
        # font name or a FontProperties object. If the caller explicitly
        # requests `font`, switch to matplotlib-scalebar (which accepts it
        # natively) rather than silently ignoring it.
        if font is not None and style == "map-utils":
            if HAS_MPL_SCALEBAR:
                warnings.warn(
                    "font= n'est pas supporté en mode 'map-utils' "
                    "(matplotlib-map-utils n'accepte qu'une famille CSS "
                    "générique via labels={'fontfamily': ...}) ; bascule "
                    "vers style='scalebar' pour appliquer la police demandée.",
                    RuntimeWarning, stacklevel=2,
                )
                style = "scalebar"
            else:
                warnings.warn(
                    "font= n'est pas supporté en mode 'map-utils' et "
                    "matplotlib-scalebar n'est pas installé pour basculer "
                    "dessus ; police ignorée. Installez-le avec : "
                    "pip install matplotlib-scalebar",
                    RuntimeWarning, stacklevel=2,
                )

        # ------- matplotlib-map-utils -------
        if style == "map-utils":
            if not HAS_MAP_UTILS:
                warnings.warn(
                    "matplotlib-map-utils n'est pas installé, "
                    "mode scalebar/manuel utilisé. "
                    "Installez-le avec : pip install matplotlib-map-utils",
                    RuntimeWarning, stacklevel=2,
                )
                style = "scalebar" if HAS_MPL_SCALEBAR else "manual"
            else:
                # Apply set_size() to the global defaults BEFORE creation
                if size is not None:
                    MmuScaleBar.set_size(size)

                loc = location if isinstance(location, str) else "lower left"
                # matplotlib-map-utils resolves axis units via
                # pyproj.CRS(projection).axis_info[...].unit_name; cartopy's
                # geographic CRS (PlateCarree, Geodetic) do not carry the
                # metadata pyproj recognizes as "degree" (they come out as
                # "unknown"), which breaks the bar's auto calculation.
                # EPSG:4326 is substituted, equivalent in degrees.
                bar_projection = (
                    "EPSG:4326"
                    if isinstance(self.projection, (ccrs.PlateCarree, ccrs.Geodetic))
                    else self.projection
                )
                bar_dict = dict(projection=bar_projection)
                # major_div requires major_mult to be valid on
                # matplotlib-map-utils's side; without major_mult (not
                # exposed here), passing it alone breaks the bar's auto
                # calculation.
                if major_div is not None:
                    bar_dict["major_div"] = major_div
                if minor_div is not None:
                    bar_dict["minor_div"] = minor_div
                if length is not None:
                    bar_dict["length"] = length
                    bar_dict["unit"] = units
                if bar is not None:
                    bar_dict.update(bar)

                labels_dict = dict(fontsize=fontsize)
                if labels is not None:
                    labels_dict.update(labels)

                sb_kwargs = dict(
                    style=bar_style,
                    location=loc,
                    bar=bar_dict,
                    labels=labels_dict,
                )
                if text is not None:
                    sb_kwargs["text"] = text
                # to="fig": anchors the bar to a point of the whole figure
                # rather than the map axis, via bbox_to_anchor/bbox_transform
                # — same convention as add_north_arrow(..., to="fig").
                aob_style = {}
                if to == "fig":
                    aob_style = {
                        "bbox_to_anchor": position,
                        "bbox_transform": self.fig.transFigure,
                    }
                if aob is not None:
                    aob_style.update(aob)
                if aob_style:
                    sb_kwargs["aob"] = aob_style
                sb_kwargs.update(kwargs)

                sb = MmuScaleBar(**sb_kwargs)
                self.ax.add_artist(sb)
                self._scale_bar_artist = sb
                return

        # ------- matplotlib-scalebar -------
        if style == "scalebar":
            if not HAS_MPL_SCALEBAR:
                warnings.warn(
                    "matplotlib-scalebar n'est pas installé, "
                    "mode manuel utilisé. "
                    "Installez-le avec : pip install matplotlib-scalebar",
                    RuntimeWarning, stacklevel=2,
                )
                style = "manual"
            else:
                dx = self._compute_scalebar_dx()
                loc = location if isinstance(location, str) else "lower left"
                dimension = (
                    "imperial-length" if units in ("mi", "ft", "yd")
                    else "si-length"
                )
                # matplotlib-scalebar validates font_properties as a dict
                # (FontProperties kwargs) or a fontconfig string — not a
                # FontProperties object despite what its docstring suggests
                # (verified on the installed version: raises ValueError otherwise).
                if font is not None:
                    if font.get_file():
                        font_properties = {"fname": font.get_file(), "size": fontsize}
                    else:
                        font_properties = {
                            "family": font.get_family(), "weight": font.get_weight(),
                            "style": font.get_style(), "size": fontsize,
                        }
                else:
                    font_properties = {"size": fontsize}
                sb_kwargs = dict(
                    location=loc,
                    color=color,
                    box_color=box_color,
                    box_alpha=box_alpha,
                    scale_loc=scale_loc,
                    label_loc=label_loc,
                    font_properties=font_properties,
                    length_fraction=0.2,
                )
                if label:
                    sb_kwargs["label"] = label
                if length is not None:
                    sb_kwargs["fixed_value"] = length
                    sb_kwargs["fixed_units"] = units
                # to="fig": matplotlib-scalebar accepts bbox_to_anchor/
                # bbox_transform directly (no nested "aob" dict).
                if to == "fig":
                    sb_kwargs["bbox_to_anchor"] = position
                    sb_kwargs["bbox_transform"] = self.fig.transFigure
                if aob is not None:
                    sb_kwargs.update(aob)
                sb_kwargs.update(kwargs)
                sb = MplScaleBar(dx, units="m", dimension=dimension,
                                 **sb_kwargs)
                self.ax.add_artist(sb)
                self._scale_bar_artist = sb
                return

        # ------- manual mode (fallback) -------
        if to == "fig":
            warnings.warn(
                "to='fig' n'est pas supporté en mode 'manual' (barre "
                "d'échelle ancrée aux coordonnées géographiques de l'axe "
                "par nature) ; position relative à l'axe utilisée.",
                RuntimeWarning, stacklevel=2,
            )
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        geod = Geod(ellps="WGS84")
        mid_lat = (y0 + y1) / 2

        try:
            map_width_m, _, _ = geod.inv(x0, mid_lat, x1, mid_lat)
            map_width_km = abs(map_width_m) / 1000
        except Exception as e:
            logger.error(f"Erreur calcul géodésique : {e}")
            map_width_km = 100

        if length is None:
            raw = map_width_km / 5
            if raw <= 0:
                raw = 10
            pow10 = 10 ** int(np.floor(np.log10(raw)))
            length = int(raw / pow10) * pow10
            if length == 0:
                length = max(1, int(raw))

        if isinstance(location, str):
            _loc_map = {
                "lower left": (0.1, 0.05), "lower right": (0.7, 0.05),
                "upper left": (0.1, 0.9), "upper right": (0.7, 0.9),
                "lower center": (0.4, 0.05), "upper center": (0.4, 0.9),
                "center": (0.4, 0.45),
            }
            location = _loc_map.get(location, (0.1, 0.05))

        x_ax, y_ax = location
        start_x = x0 + x_ax * (x1 - x0)
        start_y = y0 + y_ax * (y1 - y0)
        self._log(
            f"Scale bar placée à {x_ax * 100:.0f}% × {y_ax * 100:.0f}%"
        )

        try:
            lon_end, _, _ = geod.fwd(start_x, start_y, 90, length * 1000)
            bar_length_deg = lon_end - start_x
        except Exception:
            bar_length_deg = (
                length * 1000 / (111320 * np.cos(np.radians(start_y)))
            )

        # **kwargs is only used to style the label text (e.g. font=,
        # fontstyle=) — the line itself has no free kwargs, its only
        # options are color/linewidth/alpha (already explicit).
        self.ax.plot(
            [start_x, start_x + bar_length_deg],
            [start_y, start_y],
            color=color, linewidth=linewidth,
            solid_capstyle="butt", alpha=alpha,
        )

        if label is None:
            label = f"{length} {units}"

        text_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("solid_capstyle",)
        }
        # The default "bold" weight is only applied if no specific font is
        # provided (that font carries its own weight, e.g.
        # google_font("Fira Sans", weight="light")).
        if font is not None:
            text_kwargs["fontproperties"] = font
        else:
            text_kwargs.setdefault("fontweight", "bold")
        self.ax.text(
            start_x + bar_length_deg / 2,
            start_y + pad,
            label,
            ha="center", va="bottom", color=color,
            fontsize=fontsize, alpha=alpha,
            **text_kwargs,
        )


    # ----------------------------------------------------------------------
    # ================show and save map=====================================
    # ----------------------------------------------------------------------

    def show(
        self,
        legend=True,
        auto_extent=True,
        tight_layout=True,
        smart_centering=True,
        title=None,
        **kwargs,
    ):
        """
        Displays the map with all added layers.

        Parameters:
        -----------
        legend : bool
            Show the legend
        auto_extent : bool
            Automatically fit the extent to the data
        tight_layout : bool
            Automatically adjust the layout
        smart_centering : bool
            Smart centering adapted to the paper dimensions
        title : str
            Map title
        """
        self._render(legend=legend, auto_extent=auto_extent, tight_layout=tight_layout, smart_centering=smart_centering, title=title, **kwargs)
        plt.show()

        return self

    def _render(self, legend=True, auto_extent=True, tight_layout=True, smart_centering=True, title=None, **kwargs):
        """
        Internal map rendering (layers, extent, legend) without calling plt.show().
        Used by show() and save() to avoid double rendering.
        """
        # Render all layers
        for layer in self.layers:
            # Skip layers already rendered (choropleth, raster)
            if layer.get("rendered"):
                continue

            layer_type = layer.get("type")

            if layer_type in ("point", "line", "polygon"):
                gdf = layer["gdf"]
                style = layer["style"].copy()
                style.pop("ax", None)
                style.pop("transform", None)
                # Re-render choropleth layers with column_to_plot
                column_to_plot = layer.get("column_to_plot")
                if column_to_plot:
                    style["column"] = column_to_plot
                gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
                layer["rendered"] = True
            elif layer_type == "raster":
                rstyle = layer["style"].copy()
                data_transform = rstyle.pop("transform", ccrs.PlateCarree())
                self.ax.imshow(layer["data"], transform=data_transform, **rstyle)
                layer["rendered"] = True
            elif layer.get("_replay") is not None:
                # bivariate / hexbin: drawn directly when added, replayed
                # via their closure after an ax.clear() (set_paper, etc.).
                # ponytail: the bivariate legend is re-added via add_axes on
                # each replay; without fig.clear() (set_paper) they stack on
                # top of each other at the same spot — acceptable, the last one wins.
                layer["_replay"]()
                layer["rendered"] = True

        if title is not None:
            self.ax.set_title(title)

        # Automatic extent adjustment
        if auto_extent and hasattr(self, "_first_layer"):
            if smart_centering:
                self._apply_smart_centering()
            else:
                margin = 0.05
                width = self.bounds[2] - self.bounds[0]
                height = self.bounds[3] - self.bounds[1]
                extent = [
                    self.bounds[0] - width * margin,
                    self.bounds[2] + width * margin,
                    self.bounds[1] - height * margin,
                    self.bounds[3] + height * margin,
                ]
                self.ax.set_extent(extent, crs=ccrs.PlateCarree())

        legend_params = self.legend_params
        if legend and self.legend_elements:
            self.custom_legend(**legend_params, **kwargs)

        for layer in self.layers:
            if layer.get("type") == "scalebar" and not layer.get("rendered"):
                self._draw_scale_bar(**layer["params"])
                layer["rendered"] = True

        if tight_layout:
            self.fig.tight_layout()

    def _resolve_bbox_inches(self, bbox_inches):
        """
        Fixes `bbox_inches="tight"` when a North arrow anchored to the
        figure (`add_north_arrow(..., to="fig")`) is present:
        `matplotlib-map-utils`'s `NorthArrow` artist does not correctly
        report its extent via `get_window_extent()` (always a null bbox),
        so the standard "tight" calculation can crop it if it falls
        outside the map axis (e.g. position in the figure margin). The
        computed bbox is manually extended to cover its known position.
        """
        na_kwargs = self._north_arrow_kwargs
        if bbox_inches != "tight" or not na_kwargs or na_kwargs.get("to") != "fig":
            return bbox_inches

        renderer = self.fig.canvas.get_renderer()
        tight_bbox = self.fig.get_tightbbox(renderer)
        x, y = na_kwargs["position"]
        fig_w, fig_h = self.fig.get_size_inches()
        pad = 0.6  # inches, generous margin to cover the arrow + "N" label
        arrow_bbox = Bbox.from_extents(
            x * fig_w - pad, y * fig_h - pad,
            x * fig_w + pad, y * fig_h + pad,
        )
        return Bbox.union([tight_bbox, arrow_bbox])

    def save(self, filename, dpi=300, bbox_inches="tight", legend=True, auto_extent=True, tight_layout=True, smart_centering=True, title=None, **kwargs):
        """
        Saves the map to a file.

        Parameters:
        -----------
        filename : str
            File name (with extension)
        dpi : int
            Resolution
        bbox_inches : str
            Margin adjustment
        legend : bool
            Show the legend
        auto_extent : bool
            Automatically fit the extent
        tight_layout : bool
            Automatically adjust the layout
        smart_centering : bool
            Smart centering
        title : str
            Map title
        """
        self._render(legend=legend, auto_extent=auto_extent, tight_layout=tight_layout, smart_centering=smart_centering, title=title, **kwargs)
        self.fig.savefig(filename, dpi=dpi, bbox_inches=self._resolve_bbox_inches(bbox_inches))
        self._log(f"Carte sauvegardée: {filename}")

        return self

    def to_image(self, format: str = "png", dpi: int = 300,
                 legend: bool = True, auto_extent: bool = True,
                 tight_layout: bool = True, smart_centering: bool = True,
                 title: str = None, **kwargs) -> Image.Image:
        """
        Exports the map as a PIL.Image object (in memory, no file).

        Parameters:
        -----------
        format : str
            Image format ('png', 'jpeg', etc.)
        dpi : int
            Resolution
        legend : bool
            Show the legend
        auto_extent : bool
            Fit the extent
        tight_layout : bool
            Adjust the layout
        smart_centering : bool
            Smart centering
        title : str
            Map title

        Returns:
        --------
        PIL.Image.Image : In-memory image
        """
        buf = self.to_bytes(format=format, dpi=dpi, legend=legend,
                            auto_extent=auto_extent, tight_layout=tight_layout,
                            smart_centering=smart_centering, title=title, **kwargs)
        buf.seek(0)
        return Image.open(buf).copy()

    def to_bytes(self, format: str = "png", dpi: int = 300,
                 bbox_inches: str = "tight",
                 legend: bool = True, auto_extent: bool = True,
                 tight_layout: bool = True, smart_centering: bool = True,
                 title: str = None, **kwargs) -> BytesIO:
        """
        Exports the map as BytesIO (in memory, no file).
        Useful for Jupyter notebooks, web applications, etc.

        Parameters:
        -----------
        format : str
            Image format ('png', 'jpeg', 'svg', 'pdf')
        dpi : int
            Resolution
        bbox_inches : str
            Margin adjustment
        legend : bool
            Show the legend
        auto_extent : bool
            Fit the extent
        tight_layout : bool
            Adjust the layout
        smart_centering : bool
            Smart centering
        title : str
            Map title

        Returns:
        --------
        BytesIO : Buffer containing the image
        """
        self._render(
            legend=legend, auto_extent=auto_extent,
            tight_layout=tight_layout, smart_centering=smart_centering,
            title=title, **kwargs,
        )
        buf = BytesIO()
        self.fig.savefig(buf, format=format, dpi=dpi, bbox_inches=self._resolve_bbox_inches(bbox_inches))
        buf.seek(0)
        return buf

    def layout(self, template: str = "scientific", **kwargs):
        """
        Wraps this map as the single panel of a `Layout`, using a named
        template. Shortcut for `Layout(template=template, **kwargs).add_map(self)`.

        Parameters:
        -----------
        template : str
            One of `Layout.TEMPLATES` ("scientific", "journal", "thesis",
            "atlas", "report", "poster", "minimal").
        **kwargs : dict
            Forwarded to `Layout(...)` (e.g. `paper_format`, `orientation`).

        Returns:
        --------
        Layout: ready to receive `.add_title()`, `.add_legend()`,
        `.add_source()`, `.add_credits()`, `.add_logo()`, then `.export()`.
        """
        from .layout import Layout
        return Layout(template=template, **kwargs).add_map(self)
