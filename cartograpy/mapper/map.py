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
from ._optional_deps import *  # noqa: F401,F403
import logging

logger = logging.getLogger(__name__)


class Map:
    """
    Classe pour créer des cartes interactives avec matplotlib, geopandas et cartopy.
    Permet d'ajouter des GeoDataFrames avec des styles personnalisés.
    Support des formats de papier internationaux (A0, A1, A2, A3, A4, B0, B1, B2, B3, C0, C1, C2, C3).
    """

    # Dimensions des formats de papier en millimètres (largeur x hauteur)
    PAPER_SIZES = {
        # Série A (ISO 216)
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
        # Série B (ISO 216)
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
        # Série C (ISO 269) - principalement pour les enveloppes
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
        verbose=True,
        basemap=True,
    ):
        """
        Initialise une nouvelle carte avec cartopy.

        Paramètres:
        -----------
        figsize : tuple, str, or dict
            - tuple: Taille de la figure (largeur, hauteur) en pouces
            - str: Format de papier (ex: 'A4', 'A3', 'B2', 'C1')
            - dict: {'paper': 'A4', 'orientation': 'portrait'/'landscape'}
        title : str
            Titre de la carte
        projection : cartopy.crs
            Projection cartographique (par défaut PlateCarree)
        data_crs : str
            Système de coordonnées des données (par défaut WGS84)
        verbose : bool
            Afficher les messages d'information (par défaut True)
        basemap : bool
            Ajouter automatiquement côtes et frontières (par défaut True).
            Mettre à False pour une carte vierge (garde la projection cartopy,
            utile si vous avez besoin de add_north_arrow/add_scale_bar/add_inset_map
            sans le fond côtes+frontières).
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
        self._first_layer = False

        # Configuration de base
        self.ax.set_title(title, fontsize=16, fontweight="bold")

        # Limites par défaut (monde entier)
        self.bounds = [-180, -90, 180, 90]  # [minx, miny, maxx, maxy]

        # Ajout des caractéristiques par défaut
        if self.basemap:
            self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
            self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # Affichage des informations sur le format de papier
        if self.paper_info:
            self._log(
                f"📄 Format de papier: {self.paper_info['format']} "
                f"({self.paper_info['orientation']}) - "
                f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
                f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
            )

    # --- Helpers internes -------------------------------------------------

    def _log(self, *args, **kwargs):
        """Affiche un message seulement si verbose est activé."""
        if self.verbose:
            logger.info(" ".join(str(a) for a in args), **kwargs)

    def _invalidate_render(self):
        """Réinitialise le canvas et marque les couches pour re-rendu."""
        self.ax.clear()
        self.ax.set_title(
            self.title,
            fontsize=16 if self.projection else 14,
            fontweight="bold",
        )
        # ax.clear() détruit tous les artistes (dont grille et flèche du
        # Nord) : les références existantes sont désormais obsolètes.
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
        """Recrée la grille et la flèche du Nord après un ax.clear()/
        fig.clear() : contrairement aux layers et à la scale bar, elles ne
        sont pas re-dessinées automatiquement par _render()."""
        if self._gridline_kwargs is not None:
            self.add_gridlines(**self._gridline_kwargs)
        if self._north_arrow_kwargs is not None:
            self.add_north_arrow(**self._north_arrow_kwargs)

    def __enter__(self):
        """Support du context manager (with Map(...) as m:)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme la figure matplotlib à la sortie du context manager."""
        plt.close(self.fig)
        return False

    # ----------------------------------------------------------------------
    # ================Custom paper size ====================================
    # ----------------------------------------------------------------------

    def _process_figsize(self, figsize):
        """
        Traite le paramètre figsize pour déterminer la taille de la figure.

        Paramètres:
        -----------
        figsize : tuple, str, or dict
            Format désiré

        Returns:
        --------
        tuple: Taille de la figure en pouces (largeur, hauteur)
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
        Retourne les informations sur le format de papier utilisé.

        Paramètres:
        -----------
        figsize : tuple, str, or dict
            Format désiré

        Returns:
        --------
        dict or None: Informations sur le format de papier
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
            # PAPER_SIZES stocke les dimensions en référence portrait
            # (largeur < hauteur) ; les échanger en paysage pour rester
            # cohérent avec self.figsize (voir _paper_to_inches).
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
        Convertit un format de papier en dimensions en pouces pour matplotlib.

        Paramètres:
        -----------
        paper_format : str
            Format de papier (ex: 'A4', 'A3', 'B2')
        orientation : str
            'portrait' ou 'landscape'

        Returns:
        --------
        tuple: Dimensions en pouces (largeur, hauteur)
        """
        paper_format = paper_format.upper()

        if paper_format not in self.PAPER_SIZES:
            available_formats = ", ".join(sorted(self.PAPER_SIZES.keys()))
            raise ValueError(
                f"Format de papier '{paper_format}' non supporté. "
                f"Formats disponibles: {available_formats}"
            )

        # Récupération des dimensions en mm
        width_mm, height_mm = self.PAPER_SIZES[paper_format]

        # Conversion en pouces (1 pouce = 25.4 mm)
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
        Définit le format de papier et l'orientation de la carte.

        Paramètres:
        -----------
        paper_format : str
            Format de papier (ex: 'A4', 'A3', 'B2', 'C1')
        orientation : str
            'portrait' ou 'landscape'

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        # Calcul des nouvelles dimensions
        new_figsize = self._paper_to_inches(paper_format, orientation)

        # dimensions_mm doit suivre la même convention que new_figsize
        # (largeur/hauteur échangées en paysage), sinon les mm affichés
        # contredisent les pouces de la même chaîne d'info.
        width_mm, height_mm = self.PAPER_SIZES[paper_format.upper()]
        if orientation.lower() == "landscape":
            width_mm, height_mm = height_mm, width_mm

        # Mise à jour des informations
        self.figsize = new_figsize
        self.paper_info = {
            "format": paper_format.upper(),
            "orientation": orientation,
            "dimensions_mm": f"{width_mm} x {height_mm}",
            "dimensions_inches": f"{new_figsize[0]:.1f} x {new_figsize[1]:.1f}",
        }

        # Redimensionnement de la figure
        self.fig.set_size_inches(new_figsize[0], new_figsize[1])

        # Affichage des informations
        self._log(
            f"📄 Format mis à jour: {self.paper_info['format']} "
            f"({self.paper_info['orientation']}) - "
            f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
            f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
        )

        return self

    def list_paper_formats(self):
        """
        Affiche tous les formats de papier disponibles avec leurs dimensions.

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        logger.info("📋 Formats de papier disponibles:")
        logger.info("=" * 50)

        # Série A
        logger.info("🅰️  Série A (ISO 216):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("A") or format_name.endswith("A0"):
                logger.info(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        # Série B
        logger.info("\n🅱️  Série B (ISO 216):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("B"):
                logger.info(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        # Série C
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
        Valide et prépare un GeoDataFrame pour l'affichage.

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame à valider
        expected_geom_type : str, optional
            Type de géométrie attendu ('Point', 'LineString', 'Polygon')

        Returns:
        --------
        gpd.GeoDataFrame: GeoDataFrame validé et préparé
        """
        if not isinstance(gdf, gpd.GeoDataFrame):
            raise TypeError("Le paramètre doit être un GeoDataFrame")

        if gdf.empty:
            raise ValueError("Le GeoDataFrame ne peut pas être vide")

        # Vérification de la colonne géométrie
        if gdf.geometry.isnull().any():
            self._log(
                "⚠️  Attention: Le GeoDataFrame contient des géométries nulles qui seront ignorées"
            )
            gdf = gdf.dropna(subset=["geometry"])

        # Vérification du CRS
        if gdf.crs is None:
            msg = f"Aucun CRS défini. Attribution du CRS par défaut: {self.data_crs}"
            warnings.warn(msg, UserWarning, stacklevel=3)
            self._log(f"⚠️  Attention: {msg}")
            gdf = gdf.set_crs(self.data_crs)

        # Vérification du type de géométrie si spécifié
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
        Méthode interne : logique commune pour ajouter un layer GeoDataFrame.

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame source
        layer_type : str
            Type du layer ('point', 'line', 'polygon')
        style_kwargs : dict
            Paramètres de style spécifiques au type
        label : str
            Étiquette pour la légende
        legend_factory : callable(bool) -> artist, optional
            Fonction créant l'élément de légende. Reçoit use_column (bool).
        column : str, optional
            Colonne pour la coloration par données
        scheme : str, optional
            Schéma de classification
        cmap : str
            Palette de couleurs
        color_key : str
            Clé de couleur à retirer si column est utilisé ('color' ou 'facecolor')
        """
        gdf = self._validate_geodataframe(gdf)

        # Reprojection en EPSG:4326 pour compatibilité cartopy PlateCarree
        if gdf.crs is not None and not gdf.crs.equals("EPSG:4326"):
            gdf = gdf.to_crs(epsg=4326)

        plot_kwargs = {
            "ax": self.ax,
            "transform": ccrs.PlateCarree(),
            **style_kwargs,
        }

        # Gestion de la coloration par colonne
        use_column = False
        if column and column in gdf.columns:
            plot_kwargs["column"] = column
            if scheme:
                plot_kwargs["scheme"] = scheme
            plot_kwargs["cmap"] = cmap
            plot_kwargs.pop(color_key, None)
            use_column = True

        # Ajout du layer
        layer_info = {
            "type": layer_type, "name": label, "gdf": gdf, "data": gdf,
            "style": plot_kwargs, "label": label, "src": None,
        }
        self.layers.append(layer_info)

        # Ajout à la légende
        if label and legend_factory:
            self.legend_elements.append(legend_factory(use_column))

        self._update_bounds(gdf)
        return self

    def _add_raw_layer(self, gdf, layer_type, style_kwargs, label, legend_factory=None):
        """
        Méthode interne : logique commune pour ajouter un layer à partir de coordonnées brutes.

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame construit à partir des coordonnées
        layer_type : str
            Type du layer ('point', 'line', 'polygon')
        style_kwargs : dict
            Paramètres de style
        label : str
            Étiquette pour la légende
        legend_factory : callable() -> artist, optional
            Fonction créant l'élément de légende
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
        Ajoute une couche générique à la carte (vecteur ou raster).

        Le type de données est détecté automatiquement :
        - GeoDataFrame → couche vectorielle (point, line, polygon)
        - numpy.ndarray → couche raster (nécessite extent dans style_kwargs)
        - str (chemin fichier) → raster ou vecteur selon l'extension

        Paramètres:
        -----------
        data : gpd.GeoDataFrame, numpy.ndarray, str, or None
            Données à ajouter. Peut être :
            - un GeoDataFrame (couche vectorielle)
            - un numpy.ndarray (couche raster, fournir extent)
            - un chemin fichier str (.tif, .shp, .geojson, .gpkg, etc.)
        layer_type : str
            Type de couche ('auto', 'point', 'line', 'polygon', 'raster').
            Par défaut 'auto' détecte le type automatiquement.
        label : str
            Étiquette pour la légende (alias de name, rétrocompatible)
        name : str, optional
            Nom de la couche affiché dans la légende. Prioritaire sur label.
        style : dict, optional
            Dictionnaire de style avec les clés suivantes :
            - font : FontProperties (police pour les étiquettes, via google_font/local_font/path_font)
            - color : str ou list (couleur de remplissage/points/lignes)
            - palette : str (palette de couleurs, alias de cmap)
            - border : str (couleur de bordure)
            - border_width : float (épaisseur de bordure)
            - column : str (colonne pour la coloration par données)
            - scheme : str (schéma de classification : 'quantiles', 'equal_interval', etc.)
            - alpha : float (transparence 0-1)
            - size : int (taille des points)
            - marker : str (style du marqueur : 'o', 's', '^', etc.)
            - linewidth : float (épaisseur des lignes)
            - linestyle : str (style de ligne : '-', '--', '-.', ':')
            - legend : bool (afficher dans la légende, par défaut True)
        **style_kwargs : dict
            Paramètres de style spécifiques au type de couche (rétrocompatible).
            Pour les rasters : cmap, alpha, vmin, vmax, extent, title,
            show_colorbar.
            Pour les vecteurs : color, facecolor, edge_color, linewidth, etc.
            Les clés de style_kwargs sont écrasées par celles du dict style.
        """
        # --- Fusion du dictionnaire style dans style_kwargs ---
        if style is not None:
            _STYLE_KEY_MAP = {
                "palette": "cmap",
                "border": "edge_color",
                "border_width": "border_linewidth",
            }
            for key, value in style.items():
                mapped_key = _STYLE_KEY_MAP.get(key, key)
                style_kwargs[mapped_key] = value

        # name est prioritaire sur label
        legend_label = name if name is not None else label

        # Source d'origine (chemin fichier), capturée avant que data ne
        # soit remplacé par le GeoDataFrame chargé (branche vecteur ci-dessous)
        src = data if isinstance(data, str) else None

        # --- Extensions raster et vecteur connues ---
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

        # --- 1) Raster explicite via layer_type ---
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

        # --- 3) Chemin fichier (str) → détection par extension ---
        if isinstance(data, str):
            ext = os.path.splitext(data)[1].lower()
            if ext in _RASTER_EXTENSIONS:
                raster_kwargs = _extract_raster_kwargs()
                return self.add_raster(raster_path=data, **raster_kwargs)
            elif ext in _VECTOR_EXTENSIONS:
                data = gpd.read_file(data)
                # on continue vers la branche vectorielle ci-dessous
            else:
                raise TypeError(
                    f"Extension '{ext}' non reconnue. "
                    f"Extensions raster supportées : {_RASTER_EXTENSIONS}. "
                    f"Extensions vecteur supportées : {_VECTOR_EXTENSIONS}."
                )

        # --- 4) GeoDataFrame → couche vectorielle ---
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

        # Détection automatique du/des type(s) de géométrie
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
                    # Géométries réellement mixtes (ex. points + polygones) :
                    # une sous-couche par type, chacune avec son propre style
                    # et sa propre entrée de légende. Sans ça, tout partait
                    # vers un seul add_*() et la légende ne représentait plus
                    # que le type dominant (les autres géométries se
                    # retrouvaient tracées mais absentes de la légende).
                    _mixed_buckets = buckets_present
            else:
                raise ValueError(
                    "Aucune géométrie exploitable : le GeoDataFrame ne "
                    "contient que des géométries nulles ou vides (elles ont "
                    "été retirées lors de la validation)."
                )

        # --- Préparation des kwargs selon le type de couche ---
        def _prepare_kwargs(layer_t):
            kw = dict(style_kwargs)
            # Mapping border_linewidth → linewidth du contour
            bw = kw.pop("border_linewidth", None)
            # font est stocké mais pas envoyé aux méthodes plot
            font = kw.pop("font", None)
            # legend contrôle l'affichage dans la légende
            show_legend = kw.pop("legend", True)
            effective_label = legend_label if show_legend else None

            if layer_t == "polygon":
                # color → facecolor pour les polygones
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

        # Géométries réellement mixtes : une sous-couche par type détecté,
        # chacune avec son propre style et sa propre entrée de légende.
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

        # Ajout de la couche selon le type
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

        # name doit survivre même si legend=False a mis label à None
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
        Ajoute des points à partir d'un GeoDataFrame.
        Pour ajouter des points à partir de coordonnées brutes, utiliser add_point().

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame contenant des géométries Point
        label : str
            Étiquette pour la légende
        color : str, list, or column name
            Couleur(s) des points ou nom de colonne pour coloration
        size : int, list, or column name
            Taille(s) des points ou nom de colonne pour la taille
        marker : str
            Style du marqueur ('o', 's', '^', etc.)
        alpha : float
            Transparence (0-1)
        edge_color : str
            Couleur du contour
        linewidth : float
            Épaisseur du contour
        column : str
            Nom de la colonne pour la coloration/classification
        scheme : str
            Schéma de classification ('quantiles', 'equal_interval', etc.)
        cmap : str
            Palette de couleurs
        **kwargs : dict
            Autres paramètres pour geopandas.plot()
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
        Ajoute des lignes à partir d'un GeoDataFrame.
        Pour ajouter des lignes à partir de coordonnées brutes, utiliser add_line().

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame contenant des géométries LineString
        label : str
            Étiquette pour la légende
        color : str, list, or column name
            Couleur(s) des lignes ou nom de colonne pour coloration
        linewidth : float
            Épaisseur des lignes
        linestyle : str
            Style de ligne ('-', '--', '-.', ':')
        alpha : float
            Transparence (0-1)
        column : str
            Nom de la colonne pour la coloration/classification
        scheme : str
            Schéma de classification ('quantiles', 'equal_interval', etc.)
        cmap : str
            Palette de couleurs
        **kwargs : dict
            Autres paramètres pour geopandas.plot()
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
        Ajoute des polygones à partir d'un GeoDataFrame.
        Pour ajouter des polygones à partir de coordonnées brutes, utiliser add_polygon().

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame contenant des géométries Polygon
        label : str
            Étiquette pour la légende
        facecolor : str, list, or column name
            Couleur(s) de remplissage ou nom de colonne pour coloration
        alpha : float
            Transparence (0-1)
        edge_color : str
            Couleur du contour
        linewidth : float
            Épaisseur du contour
        column : str
            Nom de la colonne pour la coloration/classification
        scheme : str
            Schéma de classification ('quantiles', 'equal_interval', etc.)
        cmap : str
            Palette de couleurs
        **kwargs : dict
            Autres paramètres pour geopandas.plot()
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
        Ajoute un ou plusieurs points à la carte.

        Paramètres:
        -----------
        coordinates : tuple, list of tuples, or dict
            Coordonnées du/des point(s). Format: (lon, lat) ou [(lon1, lat1), (lon2, lat2), ...]
            Ou dict avec clés 'lon' et 'lat' pour DataFrame
        label : str
            Étiquette pour la légende
        color : str or list
            Couleur(s) du/des point(s)
        size : int or list
            Taille(s) du/des point(s)
        marker : str
            Style du marqueur ('o', 's', '^', etc.)
        alpha : float
            Transparence (0-1)
        edge_color : str
            Couleur du contour
        linewidth : float
            Épaisseur du contour
        transform : cartopy.crs
            Projection des données (par défaut utilise data_crs)
        """
        # Normalisation des coordonnées
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
        Ajoute une ou plusieurs lignes à la carte.

        Paramètres:
        -----------
        coordinates : list of tuples or list of lists
            Coordonnées de la ligne. Format: [(lon1, lat1), (lon2, lat2), ...]
            Ou [[(lon1, lat1), (lon2, lat2)], [(lon3, lat3), (lon4, lat4)]] pour plusieurs lignes
        label : str
            Étiquette pour la légende
        color : str
            Couleur de la ligne
        linewidth : float
            Épaisseur de la ligne
        linestyle : str
            Style de ligne ('-', '--', '-.', ':')
        alpha : float
            Transparence (0-1)
        transform : cartopy.crs
            Projection des données (par défaut utilise data_crs)
        """
        # Vérification du format des coordonnées
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
        Ajoute un ou plusieurs polygones à la carte.

        Paramètres:
        -----------
        coordinates : list of tuples or list of lists
            Coordonnées du polygone. Format: [(lon1, lat1), (lon2, lat2), ...]
            Ou [[(lon1, lat1), ...], [(lon3, lat3), ...]] pour plusieurs polygones
        label : str
            Étiquette pour la légende
        color : str
            Couleur de remplissage
        alpha : float
            Transparence (0-1)
        edge_color : str
            Couleur du contour
        linewidth : float
            Épaisseur du contour
        fill : bool
            Si True, remplit le polygone
        transform : cartopy.crs
            Projection des données (par défaut utilise data_crs)
        """
        # Vérification du format des coordonnées
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
        Ajoute des caractéristiques naturelles à la carte.

        Paramètres:
        -----------
        features : list, optional
            Liste des caractéristiques à ajouter ('coastline', 'borders', 'land', 'ocean').
            Par défaut ``['coastline', 'borders']``.
        coastline_color : str
            Couleur des côtes
        coastline_width : float
            Épaisseur des côtes
        border_color : str
            Couleur des frontières
        border_width : float
            Épaisseur des frontières
        land_color : str
            Couleur des terres (optionnel)
        ocean_color : str
            Couleur des océans (optionnel)
        lakes : bool
            Ajouter les lacs
        rivers : bool
            Ajouter les rivières
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
        Ajoute un fond de carte (tuiles web) via contextily.

        Paramètres:
        -----------
        source : contextily provider ou str, optional
            Fournisseur de tuiles. Par défaut OpenStreetMap.Mapnik.
            Exemples : ctx.providers.Stamen.Terrain, ctx.providers.CartoDB.Positron,
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        zoom : int ou 'auto'
            Niveau de zoom des tuiles
        alpha : float
            Transparence du fond de carte (0–1)
        attribution : bool
            Afficher l'attribution du fournisseur
        attribution_size : int
            Taille de police de l'attribution
        crs : str, optional
            CRS cible (par défaut : celui de la projection de la carte)

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage
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
            # warnings.warn (pas self._log) : un \u00e9chec silencieux avec
            # verbose=False laisserait croire que le fond de carte a \u00e9t\u00e9
            # ajout\u00e9 alors qu'il ne l'a pas \u00e9t\u00e9.
            warnings.warn(
                f"\u00c9chec de l'ajout du fond de carte (contextily) : {e}",
                RuntimeWarning, stacklevel=2,
            )

        return self

    def _draw_inset_data_indicator(
        self, inset_ax, bounds, data_gdf, mode,
        facecolor, edgecolor, alpha, linewidth, zorder,
    ):
        """Dessine sur `inset_ax` la zone `data` de add_inset_map : sa
        géométrie réelle (mode="geometry") ou le rectangle de son étendue
        (mode="bbox", ou tout `data` fourni sous forme de bbox)."""
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
        """Étendue totale [minx, miny, maxx, maxy] de tout ce qui est passé
        au paramètre `on` de add_inset_map (GeoDataFrame unique ou liste de
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
        """Découpe `inset_ax` (GeoAxes) en cercle au lieu du rectangle par
        défaut, via `set_boundary`. Corrige l'aspect physique de l'axe (qui
        n'est pas toujours carré, ex. `size=(4, 3)` ou `position` non carré)
        pour obtenir un vrai cercle à l'écran plutôt qu'une ellipse.

        L'ajustement d'aspect d'une GeoAxes (`set_global`/`set_extent`) est
        paresseux — sa position finale (`get_position()`) n'est correcte
        qu'après un rendu. On force donc un `draw()` avant de mesurer.
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
        Ajoute une mini-carte de situation (inset map) montrant la zone étudiée
        dans un contexte géographique plus large.

        Utilise automatiquement ``matplotlib-map-utils`` si installé pour un
        positionnement intelligent, sinon revient au placement manuel.

        Paramètres:
        -----------
        data : list[float] or GeoDataFrame, optional
            La zone à surligner sur l'inset : soit une bbox
            ``[minx, miny, maxx, maxy]``, soit un GeoDataFrame (sa
            géométrie ou son étendue est utilisée selon ``mode``).
            Par défaut (``None``), utilise ``self.bounds``.
        on : GeoDataFrame or list, optional
            Couche(s) de contexte à dessiner sur l'inset (ex. tous les pays
            d'un continent, pour situer ``data`` dedans). Un GeoDataFrame
            unique ou une liste de dicts ``[{"data": gdf, "kwargs": {...}}, ...]``.
        mode : str
            Comment dessiner ``data`` quand c'est un GeoDataFrame :
            - ``"bbox"`` (défaut) : rectangle correspondant à son étendue
              (``total_bounds``).
            - ``"geometry"`` : sa géométrie réelle (contour du/des polygones).
            Sans effet si ``data`` est déjà une bbox (toujours dessinée comme
            rectangle).
        zoom_to_on : bool
            Si True, zoome l'inset sur l'étendue totale de ``on`` (au lieu
            de la vue globale) et l'encadre d'un rectangle (couleur
            ``box_color``/``box_linewidth``). Sans effet si ``on`` n'est pas
            fourni. Prioritaire sur ``global_view``/``extent``.
        position : tuple (x, y, w, h)
            Position et taille de la mini-carte, en coordonnées relatives
            (0–1) de l'ancre choisie via ``to`` (mode classique uniquement —
            sans effet en mode map-utils, qui utilise ``location``/``coords``).
            (x, y) = coin inférieur gauche.
        to : str
            Ancre du positionnement : ``"ax"`` (défaut) — ``position``
            (mode classique) ou ``location``/``coords`` (mode map-utils)
            relatifs à l'axe de la carte principale ; ``"fig"`` — relatifs à
            la figure entière. Même convention que ``add_north_arrow``.
        circular : bool
            Si True, découpe l'inset en cercle plutôt qu'en rectangle
            (``Axes.set_boundary``), quelle que soit la forme réelle de
            l'axe (l'aspect est corrigé pour obtenir un vrai cercle, pas
            une ellipse).
        facecolor : str
            Couleur de fond de la mini-carte.
        edgecolor : str
            Couleur de la bordure.
        linewidth : float
            Épaisseur de la bordure.
        alpha : float
            Transparence.
        box_color : str
            Couleur du rectangle montrant la zone étudiée (mode classique,
            ``data`` non fourni).
        box_linewidth : float
            Épaisseur du rectangle (mode classique, ``data`` non fourni).
        land_color : str
            Couleur des terres sur la mini-carte.
        ocean_color : str
            Couleur des océans.
        projection : cartopy.crs, optional
            Projection de la mini-carte (par défaut PlateCarree).
        style : str
            Mode de rendu :
            - ``"auto"`` : matplotlib-map-utils si disponible, sinon classique.
            - ``"map-utils"`` : force le mode map-utils.
            - ``"classic"`` : placement fig.add_axes (ancien comportement).
        location : str
            Position (mode map-utils) : "upper left", "upper right",
            "lower left", "lower right", "center", etc.
        size : float or tuple, optional
            Taille de l'inset en pouces (mode map-utils). Peut être un
            scalaire (carré) ou un tuple (largeur, hauteur).
        pad : float or tuple, optional
            Espacement en pouces (mode map-utils).
        coords : tuple (x, y), optional
            Position exacte en coordonnées axes (mode map-utils).
            Remplace ``location`` si fourni.
        transform : matplotlib.transforms.Transform, optional
            Transformation pour les coordonnées (mode map-utils).
        global_view : bool
            Si True (défaut), l'inset montre le globe entier via set_global().
            Si False, l'inset est zoomé sur ``extent`` ou ajusté automatiquement.
        extent : list, optional
            [x0, x1, y0, y1] pour restreindre l'étendue de l'inset.
            Utile quand ``global_view=False``.
        indicator : str
            Type d'indicateur quand ``data`` n'est pas fourni (comportement
            hérité, basé sur l'étendue actuelle de l'axe principal) :
            "extent", "detail", ou "none". Sans effet si ``data`` est fourni
            — l'indicateur est alors toujours dessiné d'après ``data``/``mode``.
        indicator_facecolor : str
            Couleur de remplissage de l'indicateur.
        indicator_linecolor : str
            Couleur de bordure de l'indicateur.
        indicator_alpha : float
            Transparence de l'indicateur.
        indicator_linewidth : float
            Épaisseur de trait de l'indicateur.
        indicator_straighten : bool
            Si True (défaut), aligne le rectangle indicateur sur les axes
            (``data`` non fourni uniquement).
        indicator_pad : float
            Espacement du rectangle indicateur (défaut 0.05, ``data`` non
            fourni uniquement).
        connector_color : str
            Couleur des lignes de connexion (mode "detail", ``data`` non fourni).
        connector_width : float
            Épaisseur des lignes de connexion (mode "detail", ``data`` non fourni).
        inset_size : str, optional
            Taille prédéfinie ("xs", "sm", "md", "lg", "xl") — mode map-utils.
            Appelle ``InsetMap.set_size()`` pour ajuster les défauts globaux.
        zorder : int
            Z-order de l'inset (défaut 99).
        show_borders : bool
            Afficher les frontières sur l'inset (défaut True).
        show_coastlines : bool
            Afficher les côtes sur l'inset (défaut True).
        **kwargs
            Paramètres supplémentaires passés à ``InsetMap`` ou à
            l'axe inset (ex. ``xticks=[], yticks=[]``).

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage.

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

        # Résolution de `data` en (bbox, géométrie éventuelle) -------------
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
                # Appliquer set_size() sur les défauts globaux AVANT création
                if inset_size is not None:
                    MmuInsetMap.set_size(inset_size)

                # Préparer to_plot (couche(s) de contexte)
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

                # Créer l'axe inset via map-utils
                # to="fig" : InsetMap ancre toujours via `pax.inset_axes()`,
                # donc relatif à l'axe passé — on lui passe un axe fantôme
                # couvrant toute la figure (au lieu de self.ax) pour que
                # location/coords deviennent relatifs à la figure entière.
                im = MmuInsetMap(**im_kwargs)
                if to == "fig":
                    host_ax = self.fig.add_axes([0, 0, 1, 1], frameon=False)
                    host_ax.set_axis_off()
                else:
                    host_ax = self.ax
                inset_ax = im.create(host_ax, projection=projection)

                # Vue globale, restreinte, ou zoomée sur `on`
                if on_bounds is not None:
                    minx, miny, maxx, maxy = on_bounds
                    inset_ax.set_extent((minx, maxx, miny, maxy), crs=ccrs.PlateCarree())
                elif global_view:
                    inset_ax.set_global()
                elif extent is not None:
                    inset_ax.set_extent(extent, crs=ccrs.PlateCarree())

                if circular:
                    self._make_inset_circular(inset_ax)

                # Ajouter les features cartographiques
                inset_ax.add_feature(cfeature.LAND, facecolor=land_color)
                inset_ax.add_feature(cfeature.OCEAN, facecolor=ocean_color)
                if show_borders:
                    inset_ax.add_feature(
                        cfeature.BORDERS, linewidth=0.3, edgecolor="gray"
                    )
                if show_coastlines:
                    inset_ax.coastlines(resolution="110m", linewidth=0.4)

                # Cadre autour de l'étendue de `on` (zoom_to_on=True)
                if on_bounds is not None:
                    self._draw_inset_data_indicator(
                        inset_ax, on_bounds, None, "bbox",
                        "none", box_color, 1.0, box_linewidth, zorder,
                    )

                # Appliquer le style visuel
                for spine in inset_ax.spines.values():
                    spine.set_edgecolor(edgecolor)
                    spine.set_linewidth(linewidth)
                inset_ax.patch.set_alpha(alpha)
                inset_ax.patch.set_facecolor(facecolor)

                if data is not None:
                    # `data` fourni explicitement : on dessine exactement ce
                    # qui a été demandé (bbox ou géométrie), plutôt que de
                    # déduire l'indicateur de l'étendue actuelle de l'axe
                    # principal (comportement hérité ci-dessous).
                    self._draw_inset_data_indicator(
                        inset_ax, bounds, data_gdf, mode,
                        indicator_facecolor, indicator_linecolor,
                        indicator_alpha, indicator_linewidth, zorder,
                    )
                else:
                    # Indicateur d'étendue ou de détail (comportement hérité,
                    # basé sur l'étendue actuelle de self.ax)
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
                            self._log(f"⚠️  Indicateur extent échoué : {e}")
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
                            self._log(f"⚠️  Indicateur detail échoué : {e}")
                            _indicator_ok = False

                    # Fallback : dessiner manuellement le rectangle d'étendue
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

        # ------- mode classique (fallback) -------
        # to="ax" : `position` est une fraction (0-1) de l'axe principal,
        # convertie ici en coordonnées figure absolues (fig.add_axes() ne
        # comprend que des coordonnées figure). to="fig" (comportement
        # historique) : `position` est déjà en coordonnées figure.
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

        # Zone étudiée (rectangle bbox ou géométrie réelle selon `mode`)
        self._draw_inset_data_indicator(
            inset_ax, bounds, data_gdf, mode,
            "none" if data is None else indicator_facecolor, box_color,
            indicator_alpha, box_linewidth, 10,
        )

        # Cadre autour de l'étendue de `on` (zoom_to_on=True)
        if on_bounds is not None:
            self._draw_inset_data_indicator(
                inset_ax, on_bounds, None, "bbox",
                "none", box_color, 1.0, box_linewidth, 10,
            )

        # Bordure de la mini-carte
        for spine in inset_ax.spines.values():
            spine.set_edgecolor(edgecolor)
            spine.set_linewidth(linewidth)

        inset_ax.patch.set_alpha(alpha)
        inset_ax.patch.set_facecolor(facecolor)

        # Dessiner les couches de contexte optionnelles sur l'inset classique
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
        Définit la couleur de fond de la carte.

        Paramètres:
        -----------
        color : str
            Couleur de fond (nom CSS, hex, etc.)

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage
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
        Ajoute une barre de couleurs autonome à la carte.

        Paramètres:
        -----------
        cmap : str
            Palette de couleurs
        vmin : float
            Valeur minimale
        vmax : float
            Valeur maximale
        label : str, optional
            Titre de la barre de couleurs
        orientation : str
            'vertical' ou 'horizontal'
        shrink : float
            Facteur de réduction (0–1)
        pad : float
            Espacement par rapport à la carte
        aspect : int
            Ratio longueur/largeur de la barre
        ticks : list, optional
            Positions des graduations
        tick_labels : list, optional
            Labels personnalisés pour les graduations

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage
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
        Zoome sur l'étendue d'une couche spécifique.

        Paramètres:
        -----------
        index : int, optional
            Index de la couche (voir list_layers())
        label : str, optional
            Label de la couche
        margin : float
            Marge relative autour de la couche (0–1)

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage
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
        Ajoute une couche raster à la carte.

        Paramètres:
        -----------
        raster_path : str
            Chemin vers le fichier raster
        raster_array : numpy.ndarray
            Tableau numpy contenant les données raster
        extent : tuple
            Étendue du raster (xmin, xmax, ymin, ymax)
        cmap : str
            Palette de couleurs
        alpha : float
            Transparence
        vmin, vmax : float
            Valeurs min/max pour la normalisation
        transform : rasterio.transform
            Transformation géographique
        title : str
            Titre pour la barre de couleur
        show_colorbar : bool
            Afficher la barre de couleur
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

        # Masquer les valeurs NaN
        raster_data = np.ma.masked_invalid(raster_data)

        # Normalisation
        if vmin is None:
            vmin = np.nanmin(raster_data)
        if vmax is None:
            vmax = np.nanmax(raster_data)

        # Détermination du CRS cartopy pour le raster
        data_transform = ccrs.PlateCarree()  # défaut pour EPSG:4326
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

        # Affichage du raster
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

        # Ajout de la barre de couleur
        if show_colorbar:
            cbar = plt.colorbar(im, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Stockage des informations de la couche (déjà rendu directement)
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
        Ajoute une couche vectorielle choroplèthe.

        Paramètres:
        -----------
        gdf : GeoDataFrame
            Données géographiques
        column_to_plot : str
            Colonne pour la colorisation
        label_column : str
            Colonne pour les étiquettes
        cmap : str
            Palette de couleurs
        alpha : float
            Transparence
        edge_color : str
            Couleur des contours
        linewidth : float
            Largeur des contours
        show_labels : bool
            Afficher les étiquettes
        label_size : int
            Taille des étiquettes
        text_outline_color : str
            Couleur du contour du texte
        text_outline_width : float
            Largeur du contour du texte
        show_colorbar : bool
            Afficher la barre de couleur
        title : str
            Titre pour la barre de couleur
        default_crs : str
            CRS par défaut si geodf n'en a pas
        """
        # Vérifier et définir le CRS si nécessaire
        geodf = gdf.copy()
        if geodf.crs is None:
            self._log(
                f"⚠️  Aucun CRS défini. Attribution du CRS par défaut: {default_crs}"
            )
            geodf = geodf.set_crs(default_crs)

        # Reprojection en EPSG:4326 pour compatibilité cartopy
        if geodf.crs is not None and not geodf.crs.equals("EPSG:4326"):
            try:
                geodf = geodf.to_crs(epsg=4326)
            except Exception as e:
                self._log(f"⚠️  Erreur de transformation CRS: {e}")
                self._log("Utilisation des coordonnées originales...")

        # Vérifier que la colonne existe
        if column_to_plot not in geodf.columns:
            raise ValueError(f"Colonne '{column_to_plot}' introuvable dans le GeoDataFrame")

        # Filtrer les géométries nulles/vides
        geodf = geodf[geodf.geometry.notna() & ~geodf.geometry.is_empty]

        # Tracé vectorisé avec gdf.plot() (remplace la boucle par-feature)
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

        # Ajout des étiquettes (vectorisé via apply)
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

        # Barre de couleur
        if show_colorbar:
            sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Stockage des informations (déjà rendu directement)
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
        Ajoute une couche de points vectoriels.

        Paramètres:
        -----------
        gdf : GeoDataFrame
            Données géographiques
        column_to_plot : str
            Colonne pour la colorisation
        label_column : str
            Colonne pour les étiquettes
        point_size_column : str
            Colonne pour dimensionner les points
        cmap : str
            Palette de couleurs
        alpha : float
            Transparence
        min_point_size : float
            Taille minimale des points
        max_point_size : float
            Taille maximale des points
        edge_color : str
            Couleur des contours
        linewidth : float
            Largeur des contours
        show_labels : bool
            Afficher les étiquettes
        label_size : int
            Taille des étiquettes
        text_outline_color : str
            Couleur du contour du texte
        text_outline_width : float
            Largeur du contour du texte
        show_colorbar : bool
            Afficher la barre de couleur
        show_size_legend : bool
            Afficher la légende des tailles
        title : str
            Titre pour la barre de couleur
        default_crs : str
            CRS par défaut si geodf n'en a pas
        """
        # Vérifier et définir le CRS si nécessaire
        geodf = gdf.copy()
        if geodf.crs is None:
            self._log(
                f"⚠️  Aucun CRS défini. Attribution du CRS par défaut: {default_crs}"
            )
            geodf = geodf.set_crs(default_crs)

        # Reprojection en EPSG:4326 pour compatibilité cartopy
        if geodf.crs is not None and not geodf.crs.equals("EPSG:4326"):
            try:
                geodf = geodf.to_crs(epsg=4326)
            except Exception as e:
                self._log(f"⚠️  Erreur de transformation CRS: {e}")
                self._log("Utilisation des coordonnées originales...")

        # Vérifier que la colonne existe
        if column_to_plot not in geodf.columns:
            raise ValueError(f"Colonne '{column_to_plot}' introuvable dans le GeoDataFrame")

        # Filtrer les géométries nulles/vides
        geodf = geodf[geodf.geometry.notna() & ~geodf.geometry.is_empty]

        # Normalisation des couleurs
        vmin = geodf[column_to_plot].min()
        vmax = geodf[column_to_plot].max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        cmap_obj = load_cmap(cmap)

        # Calcul vectorisé des coordonnées (centroïde pour non-points)
        xs = geodf.geometry.apply(lambda g: g.x if g.geom_type == "Point" else g.centroid.x)
        ys = geodf.geometry.apply(lambda g: g.y if g.geom_type == "Point" else g.centroid.y)

        # Calcul vectorisé des tailles
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

        # Tracé vectorisé (un seul appel scatter)
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

        # Ajout des étiquettes
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

        # Barre de couleur
        if show_colorbar:
            sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Légende des tailles
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

        # Stockage des informations de la couche (déjà rendu directement) —
        # sans ça, cette couche était invisible pour list_layers()/
        # remove_layer() et ne survivait pas à un clear_layers() ailleurs
        # (ax.clear() l'efface, contrairement à add_polygons_choropleth qui
        # s'enregistre correctement).
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

    # Alias rétrocompatibles (anciens noms avec faute de frappe)
    def add_polygons_cloropleth(self, *args, **kwargs):
        """Alias déprécié — utiliser add_polygons_choropleth."""
        warnings.warn(
            "add_polygons_cloropleth est déprécié, "
            "utiliser add_polygons_choropleth à la place.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.add_polygons_choropleth(*args, **kwargs)

    def add_points_cloropleth(self, *args, **kwargs):
        """Alias déprécié — utiliser add_points_choropleth."""
        warnings.warn(
            "add_points_cloropleth est déprécié, "
            "utiliser add_points_choropleth à la place.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.add_points_choropleth(*args, **kwargs)

    # ----------------------------------------------------------------------
    # ================Custom map appearence=================================
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
        Ajoute une grille de coordonnées avec cartopy.

        Paramètres:
        -----------
        draw_labels : bool
            Afficher les étiquettes de coordonnées
        dms : bool
            Format degrés-minutes-secondes au lieu de degrés décimaux
        x_inline : bool
            Étiquettes X en ligne
        y_inline : bool
            Étiquettes Y en ligne
        xlocs : list
            Positions spécifiques pour les lignes de longitude
        ylocs : list
            Positions spécifiques pour les lignes de latitude
        color : str
            Couleur de la grille
        linestyle : str
            Style de ligne de la grille
        linewidth : float
            Épaisseur de la grille
        alpha : float
            Transparence de la grille
        fontsize : int
            Taille de police des étiquettes
        """
        # Mémorisation des paramètres pour pouvoir recréer la grille après
        # un ax.clear() (remove_layer/clear_layers/set_projection).
        self._gridline_kwargs = dict(
            draw_labels=draw_labels, top_right=top_right, dms=dms,
            x_inline=x_inline, y_inline=y_inline, xlocs=xlocs, ylocs=ylocs,
            color=color, linestyle=linestyle, linewidth=linewidth,
            alpha=alpha, fontsize=fontsize,
        )

        # Suppression de la grille existante si présente
        if self.gridlines:
            self.gridlines.remove()

        # Création de la grille
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

        # Configuration des étiquettes
        if draw_labels:
            gl.xlabel_style = {"size": fontsize}
            gl.ylabel_style = {"size": fontsize}

            # Positionnement des étiquettes
            if top_right:
                gl.top_labels = True
                gl.right_labels = True
            else:
                gl.top_labels = False
                gl.right_labels = False
            gl.bottom_labels = True
            gl.left_labels = True

            # Formatage des coordonnées
            if not dms:
                gl.xformatter = LONGITUDE_FORMATTER
                gl.yformatter = LATITUDE_FORMATTER

        # Configuration des positions de la grille
        if xlocs is not None:
            gl.xlocator = mticker.FixedLocator(xlocs)

        if ylocs is not None:
            gl.ylocator = mticker.FixedLocator(ylocs)

        self.gridlines = gl

        return self

    def set_extent(self, bounds, crs=None):
        """
        Définit les limites de la carte.

        Paramètres:
        -----------
        bounds : list or tuple
            Limites [minx, miny, maxx, maxy] ou (minx, miny, maxx, maxy)
        crs : cartopy.crs
            Système de coordonnées des limites (par défaut PlateCarree)
        """
        if crs is None:
            crs = ccrs.PlateCarree()

        self.bounds = bounds
        self.ax.set_extent(bounds, crs=crs)

        return self

    def set_projection(self, projection):
        """
        Change la projection de la carte (nécessite de recréer l'axe).

        Paramètres:
        -----------
        projection : cartopy.crs
            Nouvelle projection
        """
        # Sauvegarde des paramètres actuels
        title = self.title
        figsize = self.figsize

        # Recréation de l'axe avec la nouvelle projection
        self.fig.clear()
        self.ax = self.fig.add_subplot(111, projection=projection)
        self.projection = projection
        self.ax.set_title(title, fontsize=16, fontweight="bold")

        # Remise en place des caractéristiques par défaut
        if self.basemap:
            self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
            self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # fig.clear() détruit tous les artistes de la figure (grille,
        # flèche du Nord, scale bar, inset, colorbar) : les références
        # existantes sont désormais obsolètes.
        self.gridlines = None
        self._north_arrow_artist = None
        self._scale_bar_artist = None
        self._inset_ax = None
        self._colorbar = None

        # Recrée grille et flèche du Nord pour la nouvelle projection
        self._reapply_persistent_artists()

        # Marquer les couches pour re-rendu (dont la scale bar, qui est
        # gérée comme un layer et sera redessinée par _render())
        for layer in self.layers:
            layer["rendered"] = False

        return self
    
    def hide_gridline(self):
        """
        Masque toutes les bordures, ticks et labels de l'axe.

        Exemple :
            m = Map()
            m.hide_gridline()
            m.show()
        """
        ax=self.ax
        # Cacher les spines (bordures)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Cacher les ticks
        ax.set_xticks([])
        ax.set_yticks([])

        # Cacher les labels de ticks
        ax.set_xticklabels([])
        ax.set_yticklabels([])

        # Cacher la grille si activée
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
        Ajoute une annotation avec ou sans flèche sur un axe matplotlib.

        Args:
            ax: objet matplotlib.axes.Axes
            text (str): Texte de l'annotation.
            xy (tuple): Coordonnées du point à annoter (x, y).
            xytext (tuple, optionnel): Position du texte. Si None, utilise xy.
            arrow (bool): Si True, ajoute une flèche.
            arrow_kwargs (dict, optionnel): Dictionnaire des options de la flèche.
            text_kwargs (dict, optionnel): Dictionnaire des options du texte.

        Exemple:
            add_annotation(ax, "Ici", (3, 3), xytext=(2, 4))
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
        Ajoute des étiquettes de texte au centroïde des polygones OU à la position des points d'un GeoDataFrame.

        Parameters
        ----------
        gdf : gpd.GeoDataFrame
            Le GeoDataFrame contenant les entités.
        label_column : str, optional
            La colonne à afficher comme texte (inutile si label_func est fourni).
        custom_label : callable, optional
            Fonction qui prend une ligne (row) et retourne le texte de l'étiquette.
            Exemple : lambda row: f"{row['nom']}\n{row['pop']:,d}"
        filter_column : str, optional
            Nom de la colonne pour filtrer les entités à étiqueter.
        filter_values : list, optional
            Valeurs acceptées pour le filtre.
        fontsize : int
            Taille du texte.
        color : str
            Couleur du texte.
        outline_width : int or float
            Largeur du contour du texte.
        outline_color : str
            Couleur du contour du texte.
        format_str : str, optional
            Chaîne de format pour afficher la valeur (ex: '{:,d}' pour nombre entier).
        **text_kwargs : autres options de texte Matplotlib.
        """

        # Filtrage si demandé
        if filter_column and filter_values is not None:
            gdf = gdf[gdf[filter_column].isin(filter_values)]

        for idx, row in gdf.iterrows():
            geom = row.geometry

            # Pour Points/MultiPoints
            if geom.geom_type == "Point":
                coords = [(geom.x, geom.y)]
            elif geom.geom_type == "MultiPoint":
                coords = [(pt.x, pt.y) for pt in geom.geoms]
            # Pour Polygones/MultiPolygones
            elif geom.geom_type == "Polygon":
                coords = [(geom.centroid.x, geom.centroid.y)]
            elif geom.geom_type == "MultiPolygon":
                coords = [(poly.centroid.x, poly.centroid.y) for poly in geom.geoms]
            else:
                # Ignorer les LineString/GeometryCollection/etc.
                continue

            # Génération du label
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

            # Affichage du texte à chaque coordonnée trouvée
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
        Ajoute un titre à la carte.

        Paramètres:
        -----------
        title : str
            Titre de la carte
        fontsize : int
            Taille de la police
        pad : int
            Espacement
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
        Ajoute du texte personnalisé à la carte.

        Paramètres:
        -----------
        text : str
            Le texte à afficher
        xy : tuple
            Position du texte (x, y) en coordonnées géographiques
        fontsize : int
            Taille de la police (défaut: 12)
        color : str
            Couleur du texte (défaut: "black")
        outline_width : float
            Largeur du contour du texte (défaut: 0 = pas de contour)
        outline_color : str
            Couleur du contour du texte (défaut: "white")
        **kwargs : dict
            Autres paramètres pour matplotlib.text()
            (ha, va, rotation, alpha, weight, style, etc.)

        Returns:
        --------
        Map : self pour le chaînage de méthodes

        Example:
        --------
        >>> map_obj.add_text("Paris", (2.3522, 48.8566), 
        ...                   fontsize=14, color="red", 
        ...                   ha="center", va="center")
        """
        # Paramètres par défaut pour le texte
        text_params = {
            'fontsize': fontsize,
            'color': color,
            'ha': 'left',  # alignement horizontal par défaut
            'va': 'bottom',  # alignement vertical par défaut
            'transform': ccrs.PlateCarree(),  # utilise les coordonnées géographiques
        }
        
        # Mise à jour avec les paramètres personnalisés
        text_params.update(kwargs)
        
        # Ajout du contour si spécifié
        if outline_width > 0:
            from matplotlib import patheffects
            text_params['path_effects'] = [
                patheffects.withStroke(
                    linewidth=outline_width, 
                    foreground=outline_color
                )
            ]
        
        # Ajout du texte à la carte
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
        Ajoute du texte avec des segments <mis en évidence> (police/couleur
        différente, ex. gras) via la librairie `highlight_text`.

        Paramètres:
        -----------
        text : str
            Texte à afficher. Les segments à mettre en évidence sont
            entourés de `<...>` (ex: "<Paris>: 48.85").
        xy : tuple
            Position du texte (x, y) en coordonnées géographiques.
        fontsize : int
            Taille de police par défaut (défaut: 12).
        color : str
            Couleur par défaut (défaut: "black").
        highlight_textprops : list of dict, optional
            Un dict de propriétés matplotlib.text par segment `<...>`,
            dans l'ordre d'apparition (ex: [{"font": bold_font}]).
        **kwargs : dict
            Autres paramètres pour highlight_text.ax_text()
            (ha, va, font, transform, etc.)

        Returns:
        --------
        Map : self pour le chaînage de méthodes

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
        Ajoute du texte hors-carte (titre, sous-titre) avec des segments
        <mis en évidence>, positionné en coordonnées figure (0-1), via la
        librairie `highlight_text`.

        Paramètres:
        -----------
        text : str
            Texte à afficher. Les segments à mettre en évidence sont
            entourés de `<...>` (ex: "<Unit>: metric tons").
        x, y : float
            Position en coordonnées figure (0-1, comme fig.text()).
        fontsize : int
            Taille de police par défaut (défaut: 12).
        color : str
            Couleur par défaut (défaut: "black").
        highlight_textprops : list of dict, optional
            Un dict de propriétés matplotlib.text par segment `<...>`,
            dans l'ordre d'apparition (ex: [{"font": bold_font}]).
        **kwargs : dict
            Autres paramètres pour highlight_text.fig_text()
            (ha, va, font, etc.)

        Returns:
        --------
        Map : self pour le chaînage de méthodes

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
        Ajoute du texte avec segments <mis en évidence>, sur la carte
        (``to="ax"``, coordonnées géographiques) ou hors-carte
        (``to="fig"``, coordonnées figure 0-1). Dispatch vers
        `add_highlight_text()` / `add_highlight_fig_text()` — voir leur
        docstring pour le détail des paramètres.

        Paramètres:
        -----------
        text : str
            Texte à afficher, segments `<...>` mis en évidence.
        xy : tuple
            Position (x, y).
        to : str
            ``"ax"`` (défaut, coordonnées carte) ou ``"fig"`` (coordonnées
            figure 0-1, pour titre/sous-titre).
        **kwargs : dict
            Transmis à la méthode ciblée (fontsize, color,
            highlight_textprops, ha, va, font, etc.)

        Returns:
        --------
        Map : self pour le chaînage de méthodes
        """
        if to == "ax":
            return self.add_highlight_text(text, xy, **kwargs)
        elif to == "fig":
            return self.add_highlight_fig_text(text, xy[0], xy[1], **kwargs)
        raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

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
        Ajoute une flèche hors-carte en coordonnées figure (0-1), via la
        librairie `drawarrow`. Utile pour pointer une entité trop petite
        pour être annotée directement dessus (ex: micro-état).

        Paramètres:
        -----------
        tail_position, head_position : tuple
            Positions (x, y) en coordonnées figure (0-1) du départ et de
            la pointe de la flèche.
        radius : float
            Courbure de la flèche (0 = droite).
        color : str
            Couleur de la flèche (défaut: "black").
        width, head_width, head_length : float
            Épaisseur du trait / largeur et longueur de la pointe.
        **kwargs : dict
            Autres paramètres pour drawarrow.fig_arrow()
            (double_headed, fill_head, invert, shadow_style, etc.)

        Returns:
        --------
        Map : self pour le chaînage de méthodes

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
        """Définit le titre de la carte avec des options de personnalisation."""
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
                self._log(f"❌ Impossible de retrouver le dossier : {e}")
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
        Ajoute une image (logo, photo, illustration) à un endroit précis de
        la carte, via `OffsetImage` + `AnnotationBbox`.

        Paramètres:
        -----------
        image : str, array-like ou PIL.Image
            Chemin vers un fichier image (png, jpg, svg...) ou image déjà
            chargée (tableau numpy / `PIL.Image`).
        xy : tuple
            Position (x, y).
        to : str
            ``"fig"`` (défaut, coordonnées figure 0-1 — pour un logo/watermark
            hors-carte) ou ``"ax"`` (coordonnées géographiques de la carte).
            Même convention que `add_custom_text`.
        zoom : float
            Facteur d'échelle de l'image (défaut 1).
        alpha : float
            Transparence (0-1).
        zorder : int
            Ordre d'empilement (défaut 100, au-dessus des couches).
        frameon : bool
            Afficher un cadre autour de l'image.
        color : str, optional
            Recolore les SVG (voir `read_image`), ignoré pour les autres
            formats.
        **kwargs : dict
            Autres paramètres pour `AnnotationBbox` (pad, box_alignment,
            bboxprops, etc.)

        Returns:
        --------
        Map : self pour le chaînage de méthodes

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
        Ajoute une image de fond (texture, fond de carte statique, etc.)
        derrière toutes les couches, sur l'étendue de la carte.

        Paramètres:
        -----------
        image : str, array-like ou PIL.Image
            Chemin vers un fichier image ou image déjà chargée.
        extent : tuple, optional
            ``(minx, miny, maxx, maxy)`` couverts par l'image (coordonnées
            géographiques). Par défaut, utilise l'étendue actuelle de la
            carte (`self.bounds`, mis à jour par les couches déjà ajoutées
            ou par `set_extent()`).
        zoom : float
            Facteur de zoom (> 0) appliqué à `extent`, autour de son centre
            (défaut 1 = pas de changement). > 1 recadre sur une zone plus
            petite (image agrandie) ; < 1 couvre une zone plus grande
            (image réduite).
        aspect : str
            ``"equal"`` (défaut) : les unités géographiques x/y restent à
            échelle égale, cohérent avec le reste de la carte — l'image
            n'est pas déformée par un axe étiré. ``"auto"`` : étire l'image
            pour remplir tout `extent` (peut la déformer).
        alpha : float
            Transparence (0-1).
        zorder : int
            Ordre d'empilement (défaut -100, sous toutes les autres
            couches).
        color : str, optional
            Recolore les SVG (voir `read_image`), ignoré pour les autres
            formats.
        **kwargs : dict
            Autres paramètres pour `Axes.imshow()`.

        Returns:
        --------
        Map : self pour le chaînage de méthodes

        Example:
        --------
        >>> map_obj.set_extent([-11, 32, 41, 73])
        >>> map_obj.add_background_image("texture.jpg")
        """
        img = read_image(image, color) if isinstance(image, str) else image
        img_arr = np.asarray(img)

        if extent is None:
            if not getattr(self, "bounds", None):
                raise ValueError(
                    "Aucune étendue disponible : passez extent=... ou "
                    "appelez set_extent() / ajoutez une couche d'abord."
                )
            minx, miny, maxx, maxy = self.bounds
            extent = (minx, maxx, miny, maxy)
        else:
            minx, miny, maxx, maxy = extent
            extent = (minx, maxx, miny, maxy)

        if zoom <= 0:
            raise ValueError(f"zoom doit être > 0, reçu: {zoom!r}")

        if zoom != 1:
            cx, cy = (extent[0] + extent[1]) / 2, (extent[2] + extent[3]) / 2
            half_w = (extent[1] - extent[0]) / 2 / zoom
            half_h = (extent[3] - extent[2]) / 2 / zoom
            extent = (cx - half_w, cx + half_w, cy - half_h, cy + half_h)

        # `aspect="equal"` seul ne suffit pas : imshow() étire toujours le
        # contenu de l'image pour remplir exactement `extent`, quel que
        # soit `aspect`. Pour ne pas déformer l'image, on réduit `extent`
        # (centré) à son propre ratio largeur/hauteur en pixels — le reste
        # de la boîte reste vide plutôt que d'étirer l'image.
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

        # imshow() peut ré-ajuster automatiquement la vue de l'axe à son
        # propre extent : on restaure explicitement l'étendue courante
        # pour que l'appelant ne la voie pas changer.
        try:
            current_view = self.ax.get_extent(crs=ccrs.PlateCarree())
        except Exception:
            current_view = None

        self.ax.imshow(
            img_arr, extent=extent, transform=ccrs.PlateCarree(),
            aspect=aspect, alpha=alpha, zorder=zorder, **kwargs,
        )

        if current_view is not None:
            self.ax.set_extent(current_view, crs=ccrs.PlateCarree())

        self._log("🖼️ Image de fond ajoutée")
        return self

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
        Ajoute une flèche du Nord sur la carte.

        Utilise automatiquement ``matplotlib-map-utils`` si installé pour un
        rendu professionnel (NorthArrow), sinon les SVG embarquées.

        Parameters
        ----------
        arrow : int
            Numéro de la flèche SVG (mode svg, 1-based).
        position : tuple (x, y)
            Position en coordonnées axes fraction 0-1 (mode svg).
        zoom : float
            Facteur de zoom (mode svg), appliqué après une normalisation
            automatique qui ramène chaque icône à une taille de référence
            commune — les 17 SVG embarquées ont des résolutions natives
            très différentes (de 5x16 à 580x580 px), sans quoi `zoom=1`
            produirait des tailles incohérentes d'une flèche à l'autre.
        color : str
            Couleur de la flèche.
        style : str
            Mode de rendu :
            - ``"auto"`` : matplotlib-map-utils si disponible, sinon SVG.
            - ``"svg"`` : flèches vectorielles embarquées.
            - ``"fancy"`` : flèche 3D avec ombre (matplotlib-map-utils).
            - ``"simple"`` : flèche plate (matplotlib-map-utils).
        location : str
            Position ("upper left", "upper right", etc.) — mode map-utils.
        scale : float, optional
            Hauteur en pouces (mode map-utils). Auto si None.
        rotation : float, dict ou "auto"
            - ``"auto"`` : calculée d'après la projection.
            - ``float`` : degrés manuels.
            - ``dict`` : passé directement (ex. {"crs": ..., "reference": ...}).
        label : str or dict
            Texte de la flèche (défaut "N"). Peut être un dict complet :
            ``{"text": "N", "fontsize": 14, "color": "black"}``.
        fancy : bool or dict
            Style fancy avec ombre (mode map-utils). Peut être un dict pour
            configurer les couleurs : ``{"facecolor": "black", "edgecolor": "k"}``.
        shadow : bool or dict
            Ombre portée (mode map-utils). Peut être un dict :
            ``{"facecolor": "gray", "alpha": 0.5}``.
        size : str, optional
            Taille prédéfinie ("xs", "sm", "md", "lg", "xl") — mode map-utils.
            Appelle ``NorthArrow.set_size()`` pour ajuster les défauts globaux
            **avant** la création de l'artiste.
        base : dict, optional
            Configuration de la base de la flèche (mode map-utils).
        pack : dict, optional
            Configuration du packing (mode map-utils).
        aob : dict, optional
            Configuration de l'AnnotationBbox (mode map-utils).
        zorder : int
            Z-order de l'artiste (défaut 99).
        to : str
            ``"ax"`` (défaut, ``location``/``position`` relatifs à l'axe
            carte) ou ``"fig"`` (relatifs à la figure entière — utilise
            alors ``position`` comme point d'ancrage, dans les deux modes
            de rendu). Même convention que `add_custom_text`.
        **kwargs
            Paramètres supplémentaires pour ``NorthArrow``.

        Returns
        -------
        Map : Instance de la carte pour chaînage.
        """
        if to not in ("ax", "fig"):
            raise ValueError(f"to doit être 'ax' ou 'fig', reçu: {to!r}")

        # Mémorisation des paramètres pour pouvoir recréer la flèche après
        # un ax.clear() (remove_layer/clear_layers/set_projection).
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
                # Appliquer set_size() sur les défauts globaux AVANT création
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

                # fancy / shadow : accepte bool ou dict
                if style == "simple":
                    na_kwargs["fancy"] = False
                    na_kwargs["shadow"] = False
                else:
                    na_kwargs["fancy"] = fancy
                    na_kwargs["shadow"] = shadow

                # label : accepte str ou dict
                if isinstance(label, dict):
                    na_kwargs["label"] = label
                elif label:
                    na_kwargs["label"] = {"text": label}

                # `color` pilote le remplissage/contour de la flèche (mode
                # map-utils) via `base` — sans ça le paramètre `color` était
                # ignoré, la flèche restait toujours noire.
                base_style = {"facecolor": color, "edgecolor": color}
                if base is not None:
                    base_style.update(base)
                na_kwargs["base"] = base_style
                if pack is not None:
                    na_kwargs["pack"] = pack
                # to="fig" : ancre la flèche sur la figure entière plutôt
                # que sur l'axe carte, via bbox_to_anchor/bbox_transform.
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

        # Mode SVG (ancien comportement)
        arrow_path = self.get_north_arrows()[arrow - 1]
        img = read_image(arrow_path, color)
        # Les SVG embarquées ont des dimensions natives très hétérogènes une
        # fois rastérisées (de 5x16 à 580x580 px selon l'icône) : sans
        # normalisation, un même zoom=1 produit des flèches de tailles
        # radicalement différentes selon l'icône choisie. On ramène le plus
        # grand côté de chaque image à une taille de référence commune avant
        # d'appliquer le zoom demandé par l'utilisateur.
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

    # Alias pour compatibilité
    add_arrow = add_north_arrow

    def set_north_arrow(self, **kwargs) -> "Map":
        """
        Modifie la flèche du Nord existante créée par ``add_north_arrow``.

        Fonctionne uniquement si la flèche a été créée avec le mode
        ``map-utils`` (objet ``NorthArrow``). Chaque paramètre passé est
        directement appliqué via les property-setters de ``NorthArrow``.

        Parameters
        ----------
        location : str, optional
            Nouvelle position ("upper left", "lower right", …).
        scale : float, optional
            Nouvelle hauteur en pouces.
        rotation : dict or float, optional
            Nouvelle rotation (dict ou degrés).
        fancy : bool or dict, optional
            Activer/configurer le style fancy.
        shadow : bool or dict, optional
            Activer/configurer l'ombre.
        label : dict, optional
            Configuration du texte (ex. {"text": "N", "fontsize": 14}).
        base : dict, optional
            Configuration de la base de la flèche.
        pack : dict, optional
            Configuration du packing.
        aob : dict, optional
            Configuration de l'AnnotationBbox.
        zorder : int, optional
            Z-order.
        size : str, optional
            Taille prédéfinie ("xs", "sm", "md", "lg", "xl").
            Applique ``NorthArrow.set_size()`` sur les défauts globaux,
            supprime l'ancienne flèche et en recrée une nouvelle.

        Returns
        -------
        Map : Instance de la carte pour chaînage.
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
            # set_size modifie les défauts globaux, il faut recréer l'artiste
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
                self._log(f"⚠️  Propriété inconnue : {key}")

        self._log("🧭 Flèche du Nord mise à jour")
        return self

    def set_scale_bar(self, **kwargs) -> "Map":
        """
        Modifie la barre d'échelle existante créée par ``add_scale_bar``.

        Fonctionne avec les artistes ``MmuScaleBar`` ou ``MplScaleBar``.
        Pour ``MmuScaleBar``, chaque paramètre est appliqué via ses
        property-setters.

        Parameters
        ----------
        style : str, optional
            Style de barre ("ticks" ou "boxes") — MmuScaleBar seulement.
        location : str, optional
            Nouvelle position.
        bar : dict, optional
            Paramètres de barre (projection, unit, length, major_div, etc.).
        labels : dict, optional
            Paramètres d'étiquettes (style, loc, fontsize, etc.).
        units : dict, optional
            Paramètres d'unités (loc, label, fontsize, etc.).
        text : dict, optional
            Paramètres de texte.
        aob : dict, optional
            Configuration de l'AnnotationBbox.
        zorder : int, optional
            Z-order.
        size : str, optional
            Taille prédéfinie ("xs", "sm", "md", "lg", "xl").
            Applique ``ScaleBar.set_size()`` sur les défauts globaux,
            supprime l'ancienne barre et en recrée une nouvelle.

        Returns
        -------
        Map : Instance de la carte pour chaînage.
        """
        if self._scale_bar_artist is None:
            raise RuntimeError(
                "Aucune barre d'échelle n'a été ajoutée. "
                "Utilisez add_scale_bar() d'abord."
            )

        sb = self._scale_bar_artist

        if HAS_MAP_UTILS and isinstance(sb, MmuScaleBar):
            if "size" in kwargs:
                # set_size modifie les défauts globaux, il faut recréer
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
                    self._log(f"⚠️  Propriété inconnue : {key}")
        elif HAS_MPL_SCALEBAR and isinstance(sb, MplScaleBar):
            for key, value in kwargs.items():
                if hasattr(sb, key):
                    setattr(sb, key, value)
                else:
                    self._log(f"⚠️  Propriété inconnue : {key}")
        else:
            raise RuntimeError(
                "set_scale_bar() nécessite une barre d'échelle créée avec "
                "matplotlib-map-utils ou matplotlib-scalebar."
            )

        self._log("📏 Barre d'échelle mise à jour")
        return self

    def set_inset(self, **kwargs) -> "Map":
        """
        Modifie la mini-carte de situation (inset map) existante.

        Paramètres:
        -----------
        facecolor : str, optional
            Nouvelle couleur de fond.
        edgecolor : str, optional
            Nouvelle couleur de bordure.
        linewidth : float, optional
            Nouvelle épaisseur de bordure.
        alpha : float, optional
            Nouvelle transparence.
        land_color : str, optional
            Nouvelle couleur des terres (re-dessine la feature).
        ocean_color : str, optional
            Nouvelle couleur des océans (re-dessine la feature).
        global_view : bool, optional
            Si True, affiche la carte globale via set_global().
        extent : list, optional
            [x0, x1, y0, y1] pour restreindre l'étendue de l'inset.

        Retourne:
        ---------
        Map : Instance de la carte pour chaînage.
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
        Crée une palette de couleurs personnalisée.

        Paramètres:
        -----------
        name : str
            Nom de la palette personnalisée
        colors : List[str]
            Liste de valeurs de couleurs (codes hex, noms de couleurs, etc.)
        save_palette : bool
            Sauvegarder la palette pour une utilisation future

        Retourne:
        ---------
        Map : self pour le chaînage de méthodes

        Exemple:
            carte.create_custom_palette(name='ma_palette',
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
                self._log(f"Warning: Invalid color '{color}' ignored")

        if not valid_colors:
            self._log("Error: No valid colors provided")
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
        Récupère toutes les palettes de couleurs disponibles.
        Délègue à styling.get_available_palettes() et y ajoute
        les palettes personnalisées de cette instance.
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
        Affiche les palettes de couleurs disponibles de manière formatée.

        Paramètres:
        -----------
        category : str
            Catégorie à afficher ('all', 'custom', 'seaborn', 'matplotlib', ou une catégorie spécifique)
        limit : int
            Limite le nombre de palettes par catégorie

        Exemple:
            Map.print_available_palettes(category='seaborn', limit=5)
        """
        # Récupération directe des palettes sans créer une instance Map
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
            logger.info(f"Unknown category: {category}")
            logger.info("Available categories:", list(palettes.keys()))
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
        Prévisualise une palette de couleurs sous forme de barre colorée.

        Paramètres:
        -----------
        palette_name : str
            Nom de la palette à prévisualiser
        n_colors : int
            Nombre de couleurs à afficher

        Retourne:
        ---------
        Map : self pour le chaînage de méthodes

        Exemple:
            carte.preview_palette('Set1', n_colors=5)
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
                    self._log(f"Palette '{palette_name}' not found")
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
        Génère une palette en dégradé entre deux couleurs.

        Paramètres:
        -----------
        name : str
            Nom de la palette
        start_color : str
            Couleur de départ
        end_color : str
            Couleur d'arrivée
        n_colors : int
            Nombre de couleurs dans le dégradé
        save_palette : bool
            Sauvegarder la palette

        Retourne:
        ---------
        Map : self pour le chaînage de méthodes

        Exemple:
            carte.generate_gradient_palette(name='mon_degrade',
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
            self._log(f"Error creating gradient: {e}")
            return self

    # ----------------------------------------------------------------------
    # ================Custom font===========================================
    # ----------------------------------------------------------------------

    def get_available_fonts(self, pattern: str = None, sort: bool = True) -> List[str]:
        """
        Récupère la liste des polices disponibles sur le système.

        Paramètres:
        -----------
        pattern : str, optional
            Filtre les polices contenant ce motif (insensible à la casse)
        sort : bool
            Trier les noms par ordre alphabétique

        Retourne:
        ---------
        List[str] : Liste des noms de polices disponibles

        Exemple:
            carte.get_available_fonts(pattern='Arial', sort=True)
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
        Affiche les polices disponibles dans la console de manière formatée.

        Paramètres:
        -----------
        pattern : str, optional
            Filtre les polices contenant ce motif
        limit : int, optional
            Limite le nombre de polices affichées

        Exemple:
            Map.print_available_fonts(pattern='Arial', limit=10)
        """
        # Récupération directe des polices sans créer une instance Map
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
        Définit les propriétés globales de la police.

        Paramètres:
        -----------
        family : str
            Nom de la famille de police (utiliser get_available_fonts() pour voir les options)
        size : int
            Taille de la police
        weight : str
            Poids de la police ('normal', 'bold', 'light', etc.)

        Exemple:
            carte.set_font(family='Arial', size=12, weight='bold')
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
        """Mise à jour automatique des limites basée sur les données ajoutées."""
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
        Applique un centrage intelligent basé sur les dimensions du papier et les données.
        """
        # Calcul des dimensions des données
        data_width = self.bounds[2] - self.bounds[0]
        data_height = self.bounds[3] - self.bounds[1]
        data_center_x = (self.bounds[0] + self.bounds[2]) / 2
        data_center_y = (self.bounds[1] + self.bounds[3]) / 2

        # Cas dégénéré : un point unique (ou des entités parfaitement
        # alignées horizontalement/verticalement) donne une largeur et/ou
        # une hauteur nulles. Sans ce garde-fou, set_extent() reçoit un
        # extent de taille nulle sur cet axe ; cartopy élargit alors tout
        # seul avec un UserWarning, mais le centrage "intelligent" ne fait
        # plus rien d'intelligent. Vue de repli arbitraire d'1° autour du
        # centre — l'utilisateur peut toujours affiner via set_extent().
        _fallback_span = 1.0  # degrés
        if data_width == 0:
            data_width = _fallback_span
        if data_height == 0:
            data_height = _fallback_span

        # Récupération des dimensions de la figure
        fig_width_inches, fig_height_inches = self.figsize

        # Calcul du ratio d'aspect de la figure
        fig_aspect_ratio = fig_width_inches / fig_height_inches

        # Calcul du ratio d'aspect des données
        data_aspect_ratio = data_width / data_height if data_height > 0 else 1

        # Détermination de la marge adaptée au format de papier
        if self.paper_info:
            paper_format = self.paper_info["format"]
            orientation = self.paper_info["orientation"]

            # Marges adaptées selon le format
            if paper_format in ["A4", "A5"]:
                base_margin = 0.1  # Marge plus importante pour petits formats
            elif paper_format in ["A3", "A2"]:
                base_margin = 0.08  # Marge moyenne pour formats moyens
            elif paper_format in ["A1", "A0"]:
                base_margin = 0.05  # Marge réduite pour grands formats
            else:
                base_margin = 0.07  # Marge par défaut

            # Ajustement selon l'orientation
            if orientation == "portrait":
                margin_x = base_margin
                margin_y = base_margin * 0.8  # Marge verticale réduite en portrait
            else:  # landscape
                margin_x = base_margin * 0.8  # Marge horizontale réduite en paysage
                margin_y = base_margin
        else:
            # Valeurs par défaut si pas d'info papier
            margin_x = margin_y = 0.07

        # Calcul des dimensions d'affichage optimales
        if fig_aspect_ratio > data_aspect_ratio:
            # La figure est plus large que les données
            # On ajuste la hauteur d'abord
            display_height = data_height * (1 + 2 * margin_y)
            display_width = display_height * fig_aspect_ratio
        else:
            # La figure est plus haute que les données
            # On ajuste la largeur d'abord
            display_width = data_width * (1 + 2 * margin_x)
            display_height = display_width / fig_aspect_ratio

        # Calcul de l'étendue finale centrée
        extent = [
            data_center_x - display_width / 2,
            data_center_x + display_width / 2,
            data_center_y - display_height / 2,
            data_center_y + display_height / 2,
        ]

        # Application de l'étendue
        self.ax.set_extent(extent, crs=ccrs.PlateCarree())

        # Affichage d'informations de débogage
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
        Centre la carte sur des limites spécifiques avec marges adaptées.

        Paramètres:
        -----------
        bounds : list or tuple
            Limites [minx, miny, maxx, maxy] sur lesquelles centrer
        margin : str, float, or dict
            'auto' pour marge automatique, float pour marge uniforme,
            ou dict {'x': float, 'y': float} pour marges différenciées
        """
        # Mise à jour des limites des données
        self.bounds = bounds

        # Calcul des dimensions
        data_width = bounds[2] - bounds[0]
        data_height = bounds[3] - bounds[1]
        data_center_x = (bounds[0] + bounds[2]) / 2
        data_center_y = (bounds[1] + bounds[3]) / 2

        # Gestion des marges
        if margin == "auto":
            # Marge automatique basée sur le format papier
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

        # Calcul de l'étendue avec marges
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
        Retourne les marges optimales pour le format de papier actuel.

        Returns:
        --------
        dict: Marges recommandées {'x': float, 'y': float}
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
        Crée une légende personnalisée avec contrôle total sur l'apparence.

        Paramètres:
        -----------
        elements : list, optional
            Liste d'éléments de légende personnalisés. Si None, utilise self.legend_elements
        title : str, optional
            Titre de la légende
        loc : str or int
            Position de la légende ('best', 'upper right', 'lower left', etc.)
        bbox_to_anchor : tuple, optional
            Position absolue (x, y) ou (x, y, width, height)
        ncol : int
            Nombre de colonnes dans la légende
        fontsize : int or str
            Taille de police du texte
        title_fontsize : int or str
            Taille de police du titre
        frameon : bool
            Afficher le cadre de la légende
        fancybox : bool
            Coins arrondis pour le cadre
        shadow : bool
            Ombre portée
        framealpha : float
            Transparence du cadre (0-1)
        facecolor : str
            Couleur de fond du cadre
        edgecolor : str
            Couleur du contour du cadre
        linewidth : float
            Épaisseur du contour
        columnspacing : float
            Espacement entre les colonnes
        handlelength : float
            Longueur des symboles
        handletextpad : float
            Espacement entre symbole et texte
        borderpad : float
            Espacement interne du cadre
        markerscale : float
            Échelle des marqueurs
        markerfirst : bool
            Marqueur avant ou après le texte
        numpoints : int
            Nombre de points pour les lignes
        scatterpoints : int
            Nombre de points pour les scatter
        replace : bool
            Remplacer la légende existante ou ajouter
        **kwargs : dict
            Autres paramètres pour matplotlib.legend()

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        self._log("🛑Element de légende ajouté", elements)
        # Utilisation des éléments fournis ou de ceux stockés
        if elements is None:
            self.legend_elements = self.legend_elements
        else:
            self.legend_elements = self.legend_elements + elements
        legend_elements = self.legend_elements

        if not legend_elements:
            self._log("⚠️  Aucun élément de légende disponible")
            return self

        # Préparation des paramètres de la légende
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
        # Ajout du titre si fourni
        if title:
            legend_params["title"] = title
            legend_params["title_fontsize"] = title_fontsize

        # Ajout de bbox_to_anchor si fourni
        if bbox_to_anchor:
            legend_params["bbox_to_anchor"] = bbox_to_anchor

        legend_params.pop("linewidth", None)

        # Suppression ou remplacement de la légende existante
        if replace and hasattr(self.ax, "legend_") and self.ax.legend_:
            self.ax.legend_.remove()

        # Création de la légende
        legend = self.ax.legend(**legend_params)

        # Stockage de la référence pour modifications ultérieures
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
        Ajoute un élément personnalisé à la légende.

        Paramètres:
        -----------
        element_type : str
            Type d'élément ('point', 'line', 'patch', 'text')
        label : str
            Texte de l'élément
        color : str
            Couleur de l'élément
        marker : str
            Type de marqueur pour les points
        linestyle : str
            Style de ligne ('-', '--', '-.', ':')
        linewidth : float
            Épaisseur de ligne
        markersize : float
            Taille du marqueur
        alpha : float
            Transparence (0-1)
        **kwargs : dict
            Autres paramètres spécifiques au type d'élément

        Returns:
        --------
        Map: Instance de la carte pour chaînage
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
            # Élément texte simple (utilise un patch transparent)
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
        Crée automatiquement une légende basée sur une colonne d'un GeoDataFrame.

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame source
        column : str
            Nom de la colonne pour la légende
        element_type : str
            Type d'élément de légende ('patch', 'point', 'line')
        color_scheme : str or list
            Schéma de couleurs ou liste de couleurs
        title : str
            Titre de la légende (utilise le nom de colonne par défaut)
        max_items : int
            Nombre maximum d'éléments dans la légende
        sort_by : str
            Tri par 'value', 'alphabetical', ou 'frequency'
        **legend_kwargs : dict
            Paramètres pour custom_legend()

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        if cmap is not None:
            color_scheme = cmap
        if column not in gdf.columns:
            raise ValueError(f"Colonne '{column}' non trouvée dans le GeoDataFrame")

        # Extraction des valeurs uniques
        unique_values = gdf[column].dropna().unique()

        # Tri selon la méthode spécifiée
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

        # Limitation du nombre d'éléments
        if len(unique_values) > max_items:
            self._log(
                f"Il y a plus de 25 éléments uniques dans la colonne {column} ({len(unique_values)} valeurs exactement). Modifiez la valeur de max_items à {len(unique_values)} pour afficher tous les éléments."
            )
            unique_values = unique_values[: max_items - 1]
            show_others = True
        else:
            show_others = False

        # Génération des couleurs
        if isinstance(color_scheme, str):
            # Utilisation d'une palette matplotlib
            cmap = load_cmap(color_scheme)
            colors = [cmap(i / len(unique_values)) for i in range(len(unique_values))]
        elif isinstance(color_scheme, list):
            # Liste de couleurs fournie
            colors = color_scheme[: len(unique_values)]
            if len(colors) < len(unique_values):
                # Répétition des couleurs si nécessaire
                colors = (colors * (len(unique_values) // len(colors) + 1))[
                    : len(unique_values)
                ]
        else:
            raise ValueError("color_scheme doit être une chaîne ou une liste")

        # Création des éléments de légende
        legend_elements = []
        for value, color in zip(unique_values, colors):
            # Conversion de la couleur si nécessaire
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

        # Ajout d'un élément "Autres" si nécessaire
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

        # Création de la légende
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
        Ajoute une légende "faite main" : rectangles de couleur empilés
        verticalement à une position donnée (comme sur une carte
        imprimée), au lieu d'un coin d'axe via `custom_legend()`.

        Paramètres:
        -----------
        items : list of (label, color)
            Paires (texte, couleur) à afficher, du haut vers le bas.
        xy : tuple
            Position (x, y) du coin supérieur gauche du premier rectangle.
        rect_width, rect_height : float
            Dimensions des rectangles (mêmes unités que xy).
        y_step : float
            Espacement vertical entre rectangles successifs.
        label_dx, label_dy : float
            Décalage du texte par rapport au coin du rectangle.
        fontsize : int
            Taille du texte.
        color : str
            Couleur du texte.
        edge_color, linewidth :
            Contour des rectangles.
        font : FontProperties, optional
            Police du texte (via google_font/local_font/path_font).
        ha, va : str
            Alignement du texte.
        to : str
            ``"ax"`` (défaut, coordonnées géographiques) ou ``"fig"``
            (coordonnées figure 0-1, comme avec `add_custom_text`).

        Returns:
        --------
        Map : self pour le chaînage de méthodes

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
        Applique des préréglages de légende.

        Paramètres:
        -----------
        preset : str
            Nom du préréglage ('default', 'minimal', 'fancy', 'academic', 'poster,'simple')
        **override_kwargs : dict
            Paramètres pour surcharger le préréglage

        Returns:
        --------
        Map: Instance de la carte pour chaînage
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

        # Fusion des paramètres du préréglage avec les surcharges
        params = {**presets[preset], **override_kwargs}
        self._log(params)

        self.custom_legend(**params)

        self._log(f"🎨 Préréglage '{preset}' appliqué à la légende")

        return self

    def remove_legend(self):
        """
        Supprime la légende actuelle.

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        if hasattr(self.ax, "legend_") and self.ax.legend_:
            self.ax.legend_.remove()
            self._log("🗑️  Légende supprimée")
        else:
            self._log("⚠️  Aucune légende à supprimer")

        return self

    def clear_legend_elements(self):
        """
        Vide la liste des éléments de légende.

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        self.legend_elements = []
        self._log("🧹 Éléments de légende effacés")

        return self

    # ----------------------------------------------------------------------
    # ================Layer management======================================
    # ----------------------------------------------------------------------

    def list_layers(self) -> List[Dict[str, Any]]:
        """
        Liste toutes les couches ajoutées à la carte.

        Retourne:
        ---------
        List[Dict]: Liste de dictionnaires avec les infos de chaque couche
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
        Supprime une couche par son index ou son label.

        Paramètres:
        -----------
        index : int, optional
            Index de la couche à supprimer (voir list_layers())
        label : str, optional
            Label de la couche à supprimer. Si plusieurs couches ont le même
            label, seule la première trouvée est supprimée.

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage

        Exemple:
        --------
        >>> m = Map()
        >>> m.add_polygons(gdf, label="Régions")
        >>> m.list_layers()
        >>> m.remove_layer(label="Régions")   # par label
        >>> m.remove_layer(index=0)            # par index
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
                self._log(f"⚠️  Aucune couche avec le label '{label}' trouvée")

        self._invalidate_render()
        return self

    def clear_layers(self) -> "Map":
        """
        Supprime toutes les couches de la carte.

        Retourne:
        ---------
        Map: Instance de la carte pour chaînage
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
        Ajoute une barre d'échelle sur la carte.

        Sélectionne automatiquement le meilleur moteur disponible :
        ``matplotlib-map-utils`` > ``matplotlib-scalebar`` > tracé manuel.

        Parameters
        ----------
        length : float, optional
            Longueur souhaitée (en *units*). Auto-calculée si None.
        location : str or tuple
            Position : chaîne matplotlib ("lower left", "upper right", …)
            ou tuple (x, y) en coordonnées relatives 0-1 (mode manuel).
        linewidth : float
            Épaisseur du trait.
        units : str
            Unité d'affichage : "km", "m", "mi", "ft", "nmi".
        color : str
            Couleur principale.
        fontsize : int
            Taille de police.
        pad : float
            Espacement texte / barre (mode manuel uniquement).
        alpha : float
            Transparence.
        label : str, optional
            Étiquette personnalisée.
        style : str
            Mode de rendu :
            - ``"auto"`` : meilleure bibliothèque disponible
              (map-utils > scalebar > manual).
            - ``"map-utils"`` / ``"ticks"`` / ``"boxes"`` :
              force matplotlib-map-utils.
            - ``"scalebar"`` : force matplotlib-scalebar.
            - ``"manual"`` : tracé à la main (ancien comportement).
        box_color : str
            Couleur de fond (mode scalebar).
        box_alpha : float
            Transparence du fond (mode scalebar).
        scale_loc : str
            Position du trait ("top", "bottom") — mode scalebar.
        label_loc : str
            Position du texte ("top", "bottom", "left", "right") —
            mode scalebar.
        add_as_layer : bool
            Si True, rendu différé lors de show()/save().
        bar_style : str
            Style de barre pour map-utils : "boxes" ou "ticks".
        major_div : int, optional
            Nombre de divisions majeures (mode map-utils). Auto-calculé si
            None (comportement par défaut de matplotlib-map-utils).
        minor_div : int, optional
            Nombre de divisions mineures (mode map-utils). Auto-calculé si
            None (comportement par défaut de matplotlib-map-utils).
        size : str, optional
            Taille prédéfinie ("sm", "md", "lg", "xl") — mode map-utils.
        bar : dict, optional
            Dictionnaire de paramètres de barre (mode map-utils).
            Clés : projection, unit, max, length, major_div, minor_div, etc.
        labels : dict, optional
            Dictionnaire de paramètres d'étiquettes (mode map-utils).
            Clés : style, loc, format, fontsize, textcolors, etc.
        text : dict, optional
            Dictionnaire de paramètres de texte (mode map-utils).
        to : str
            ``"ax"`` (défaut, ``location`` relatif à l'axe de la carte
            principale) ou ``"fig"`` (relatif à la figure entière — ex.
            placer la barre d'échelle dans la marge, hors de l'axe). Même
            convention que ``add_north_arrow``. Modes ``"map-utils"`` et
            ``"scalebar"`` uniquement — sans effet (avec avertissement) en
            mode ``"manual"``, intrinsèquement ancré aux coordonnées
            géographiques de l'axe.
        position : tuple (x, y)
            Point d'ancrage exact en coordonnées figure (0-1), utilisé
            uniquement si ``to="fig"`` (ignoré sinon). ``location`` reste
            utilisé pour déterminer quel coin de la barre touche ce point.
        aob : dict, optional
            Configuration de l'AnchoredOffsetBox sous-jacent (mode
            map-utils) — fusionné avec, et prioritaire sur, celle déduite
            de ``to``.
        font : matplotlib.font_manager.FontProperties, optional
            Police précise pour le texte (ex. via ``google_font()``).
            matplotlib-map-utils ne supporte qu'une famille CSS générique
            (``fontfamily`` dans ``labels``/``text`` : "serif",
            "sans-serif", "cursive", "fantasy", "monospace") — si ce style
            est actif et ``font`` est fourni, bascule automatiquement vers
            ``style="scalebar"`` (avec avertissement) pour l'appliquer
            réellement. Fonctionne nativement en modes ``"scalebar"`` et
            ``"manual"``.
        **kwargs
            Paramètres supplémentaires passés à la bibliothèque.
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
        """Calcule *dx* (mètres par unité d'axe) pour matplotlib-scalebar."""
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
        """Trace la barre d'échelle sur self.ax."""
        if kwargs is None:
            kwargs = {}

        # ------- résolution du style -------
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

        # matplotlib-map-utils ne peut pas appliquer une police précise
        # (FontProperties) : son paramètre fontfamily n'accepte que les 5
        # familles CSS génériques ("serif", "sans-serif", "cursive",
        # "fantasy", "monospace"), pas un nom de police ni un objet
        # FontProperties. Si l'appelant demande explicitement `font`, on
        # bascule vers matplotlib-scalebar (qui l'accepte nativement) plutôt
        # que de l'ignorer silencieusement.
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
                # Appliquer set_size() sur les défauts globaux AVANT création
                if size is not None:
                    MmuScaleBar.set_size(size)

                loc = location if isinstance(location, str) else "lower left"
                # matplotlib-map-utils résout les unités d'axe via
                # pyproj.CRS(projection).axis_info[...].unit_name ; les CRS
                # géographiques de cartopy (PlateCarree, Geodetic) ne portent
                # pas les métadonnées pyproj reconnaît comme "degree" (elles
                # ressortent "unknown"), ce qui fait planter le calcul auto
                # de la barre. On substitue EPSG:4326, équivalent en degrés.
                bar_projection = (
                    "EPSG:4326"
                    if isinstance(self.projection, (ccrs.PlateCarree, ccrs.Geodetic))
                    else self.projection
                )
                bar_dict = dict(projection=bar_projection)
                # major_div nécessite major_mult pour être valide côté
                # matplotlib-map-utils ; sans major_mult (non exposé ici),
                # le passer seul fait échouer le calcul auto de la barre.
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
                # to="fig" : ancre la barre à un point de la figure entière
                # plutôt qu'à l'axe carte, via bbox_to_anchor/bbox_transform
                # — même convention que add_north_arrow(..., to="fig").
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
                # matplotlib-scalebar valide font_properties comme un dict
                # (kwargs de FontProperties) ou une chaîne fontconfig — pas
                # un objet FontProperties malgré ce que suggère sa docstring
                # (vérifié sur la version installée : lève ValueError sinon).
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
                # to="fig" : matplotlib-scalebar accepte bbox_to_anchor/
                # bbox_transform directement (pas de dict "aob" imbriqué).
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

        # ------- mode manuel (fallback) -------
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
            self._log(f"Erreur calcul géodésique : {e}")
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

        # **kwargs ne sert qu'à styler le texte du label (ex. font=,
        # fontstyle=) — la ligne elle-même n'a pas de kwargs libres, ses
        # seules options sont color/linewidth/alpha (déjà explicites).
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
        # Le poids "bold" par défaut n'est appliqué que si aucune police
        # spécifique n'est fournie (celle-ci porte son propre poids, ex.
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
        Affiche la carte avec tous les layers ajoutés.

        Paramètres:
        -----------
        legend : bool
            Afficher la légende
        auto_extent : bool
            Ajuster automatiquement l'étendue aux données
        tight_layout : bool
            Ajuster automatiquement la mise en page
        smart_centering : bool
            Centrage intelligent adapté aux dimensions du papier
        title : str
            Titre de la carte
        """
        self._render(legend=legend, auto_extent=auto_extent, tight_layout=tight_layout, smart_centering=smart_centering, title=title, **kwargs)
        plt.show()

        return self

    def _render(self, legend=True, auto_extent=True, tight_layout=True, smart_centering=True, title=None, **kwargs):
        """
        Rendu interne de la carte (layers, extent, légende) sans appeler plt.show().
        Utilisé par show() et save() pour éviter le double rendu.
        """
        # Rendu de tous les layers
        for layer in self.layers:
            # Ignorer les layers déjà rendus (choroplèthe, raster)
            if layer.get("rendered"):
                continue

            layer_type = layer.get("type")

            if layer_type in ("point", "line", "polygon"):
                gdf = layer["gdf"]
                style = layer["style"].copy()
                style.pop("ax", None)
                style.pop("transform", None)
                # Ré-rendu des couches choroplèthes avec column_to_plot
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

        if title is not None:
            self.ax.set_title(title)

        # Ajustement automatique de l'étendue
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
        Corrige `bbox_inches="tight"` quand une flèche du Nord ancrée à la
        figure (`add_north_arrow(..., to="fig")`) est présente : l'artiste
        `NorthArrow` de `matplotlib-map-utils` ne rapporte pas correctement
        son étendue via `get_window_extent()` (bbox toujours nul), donc le
        calcul "tight" standard peut la rogner si elle sort de l'axe carte
        (ex: position dans la marge de la figure). On étend manuellement le
        bbox calculé pour couvrir sa position connue.
        """
        na_kwargs = self._north_arrow_kwargs
        if bbox_inches != "tight" or not na_kwargs or na_kwargs.get("to") != "fig":
            return bbox_inches

        renderer = self.fig.canvas.get_renderer()
        tight_bbox = self.fig.get_tightbbox(renderer)
        x, y = na_kwargs["position"]
        fig_w, fig_h = self.fig.get_size_inches()
        pad = 0.6  # pouces, marge généreuse pour couvrir flèche + label "N"
        arrow_bbox = Bbox.from_extents(
            x * fig_w - pad, y * fig_h - pad,
            x * fig_w + pad, y * fig_h + pad,
        )
        return Bbox.union([tight_bbox, arrow_bbox])

    def save(self, filename, dpi=300, bbox_inches="tight", legend=True, auto_extent=True, tight_layout=True, smart_centering=True, title=None, **kwargs):
        """
        Sauvegarde la carte dans un fichier.

        Paramètres:
        -----------
        filename : str
            Nom du fichier (avec extension)
        dpi : int
            Résolution
        bbox_inches : str
            Ajustement des marges
        legend : bool
            Afficher la légende
        auto_extent : bool
            Ajuster automatiquement l'étendue
        tight_layout : bool
            Ajuster automatiquement la mise en page
        smart_centering : bool
            Centrage intelligent
        title : str
            Titre de la carte
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
        Exporte la carte en objet PIL.Image (en mémoire, sans fichier).

        Paramètres:
        -----------
        format : str
            Format d'image ('png', 'jpeg', etc.)
        dpi : int
            Résolution
        legend : bool
            Afficher la légende
        auto_extent : bool
            Ajuster l'étendue
        tight_layout : bool
            Ajuster la mise en page
        smart_centering : bool
            Centrage intelligent
        title : str
            Titre de la carte

        Retourne:
        ---------
        PIL.Image.Image : Image en mémoire
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
        Exporte la carte en BytesIO (en mémoire, sans fichier).
        Utile pour les notebooks Jupyter, applications web, etc.

        Paramètres:
        -----------
        format : str
            Format d'image ('png', 'jpeg', 'svg', 'pdf')
        dpi : int
            Résolution
        bbox_inches : str
            Ajustement des marges
        legend : bool
            Afficher la légende
        auto_extent : bool
            Ajuster l'étendue
        tight_layout : bool
            Ajuster la mise en page
        smart_centering : bool
            Centrage intelligent
        title : str
            Titre de la carte

        Retourne:
        ---------
        BytesIO : Buffer contenant l'image
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
