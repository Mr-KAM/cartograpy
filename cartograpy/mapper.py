# ----------------------------------------------------------------------
# ================package importation ==================================
# ----------------------------------------------------------------------

import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiPoint
from matplotlib.patches import Patch
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.patheffects as patheffects
import importlib.resources
import os
from typing import Optional, Union, List, Tuple, Dict, Any
import matplotlib.font_manager as fm
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from io import BytesIO
from PIL import Image
import matplotlib.transforms as mtransforms
from pyproj import Geod
import rasterio
from rasterio.plot import show as rasterio_show
from cartograpy.styling import *
# ----------------------------------------------------------------------
# ================global methodes ======================================
# ----------------------------------------------------------------------


def get_fonts(pattern: str = None, sort: bool = True) -> List[str]:
    """
    Get list of all available font names in the system.

    Args:
        pattern (str, optional): Filter fonts containing this pattern (case-insensitive)
        sort (bool): Whether to sort the font names alphabetically

    Returns:
        List[str]: List of available font names
    example:
        get_fonts(pattern='Arial', sort=True)
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


def get_available_palettes(
    include_custom: bool = True,
    include_seaborn: bool = True,
    include_matplotlib: bool = True,
) -> Dict[str, List[str]]:
    """
    Get all available color palettes.

    Args:
        include_custom (bool): Include custom palettes
        include_seaborn (bool): Include seaborn palettes
        include_matplotlib (bool): Include matplotlib colormaps

    Returns:
        Dict[str, List[str]]: Dictionary of palette names and their categories
    example:
        palettes = get_available_palettes(include_custom=True,
                                                    include_seaborn=True,
                                                    include_matplotlib=True)
    """
    # list_custom=list(custom_palettes().keys)
    custom_color_list=list(custom_palettes().keys())
    palettes = {
        "custom": [],
        "seaborn_qualitative": [],
        "seaborn_sequential": [],
        "seaborn_diverging": [],
        "matplotlib_sequential": [],
        "matplotlib_diverging": [],
        "matplotlib_cyclic": [],
        "matplotlib_qualitative": [],
    }
    if include_custom:
        palettes["custom"] = custom_color_list

    # Seaborn palettes
    if include_seaborn:
        # Qualitative palettes
        palettes["seaborn_qualitative"] = [
            "deep",
            "muted",
            "bright",
            "pastel",
            "dark",
            "colorblind",
            "Set1",
            "Set2",
            "Set3",
            "Paired",
            "tab10",
            "tab20",
        ]

        # Sequential palettes
        palettes["seaborn_sequential"] = [
            "Blues",
            "BuGn",
            "BuPu",
            "GnBu",
            "Greens",
            "Greys",
            "Oranges",
            "OrRd",
            "PuBu",
            "PuBuGn",
            "PuRd",
            "Purples",
            "RdPu",
            "Reds",
            "YlGn",
            "YlGnBu",
            "YlOrBr",
            "YlOrRd",
            "rocket",
            "mako",
            "flare",
            "crest",
        ]

        # Diverging palettes
        palettes["seaborn_diverging"] = [
            "BrBG",
            "PiYG",
            "PRGn",
            "PuOr",
            "RdBu",
            "RdGy",
            "RdYlBu",
            "RdYlGn",
            "Spectral",
            "coolwarm",
            "bwr",
            "seismic",
            "icefire",
            "vlag",
        ]

    # Matplotlib colormaps
    if include_matplotlib:
        # Sequential
        palettes["matplotlib_sequential"] = [
            "viridis",
            "plasma",
            "inferno",
            "magma",
            "cividis",
            "Greys",
            "Purples",
            "Blues",
            "Greens",
            "Oranges",
            "Reds",
            "YlOrBr",
            "YlOrRd",
            "OrRd",
            "PuRd",
            "RdPu",
            "BuPu",
            "GnBu",
            "PuBu",
            "YlGnBu",
            "PuBuGn",
            "BuGn",
            "YlGn",
        ]

        # Diverging
        palettes["matplotlib_diverging"] = [
            "PiYG",
            "PRGn",
            "BrBG",
            "PuOr",
            "RdGy",
            "RdBu",
            "RdYlBu",
            "RdYlGn",
            "Spectral",
            "coolwarm",
            "bwr",
            "seismic",
        ]

        # Cyclic
        palettes["matplotlib_cyclic"] = ["twilight", "twilight_shifted", "hsv"]

        # Qualitative
        palettes["matplotlib_qualitative"] = [
            "Pastel1",
            "Pastel2",
            "Paired",
            "Accent",
            "Dark2",
            "Set1",
            "Set2",
            "Set3",
            "tab10",
            "tab20",
            "tab20b",
            "tab20c",
        ]

    return palettes


def read_image(path, color=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".svg":
        # On lit le SVG comme texte
        with open(path, "r", encoding="utf-8") as f:
            svg_content = f.read()

        # Si une couleur est spécifiée, on modifie tous les "fill"
        if color:
            import re

            # Change tous les attributs fill="..." par la nouvelle couleur
            svg_content = re.sub(r'fill="[^"]*"', f'fill="{color}"', svg_content)

        # On transforme la chaîne SVG en image
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(
            "w+", suffix=".svg", delete=False, encoding="utf-8"
        ) as tmp_svg:
            tmp_svg.write(svg_content)
            tmp_svg_path = tmp_svg.name

        drawing = svg2rlg(tmp_svg_path)
        buf = BytesIO()
        renderPM.drawToFile(drawing, buf, fmt="PNG")
        buf.seek(0)
        img = Image.open(buf)

        # Nettoyage temporaire
        os.remove(tmp_svg_path)
    else:
        img = Image.open(path)
    return img


def plot_choropleth(
    geodf,
    column_to_plot,
    label_column,
    label_title=None,
    title=None,
    cmap="rainbow",
    size=1.8,
    text_outline_color="white",
    text_outline_width=0,
    axes=True,
    grid=True,
    show_legend=True,
):
    """
    Crée une carte choroplèthe avec des étiquettes possédant un contour coloré.

    Paramètres:
    -----------
    geodf : GeoDataFrame
        Le GeoDataFrame à afficher
    column_to_plot : str
        Colonne numérique pour la colorisation
    label_column : str
        Colonne des étiquettes
    label_title : str, optional
        Titre de la barre de couleur
    title : str, optional
        Titre de la carte
    cmap : str, optional
        Palette de couleurs
    size : float, optional
        Taille de la figure
    text_outline_color : str, optional
        Couleur du contour des étiquettes
    text_outline_width : float, optional
        Largeur du contour des étiquettes

    Retourne:
    --------
    BytesIO
        L'image générée au format PNG
    """

    # Création du graphique
    fig, ax = plt.subplots(figsize=(10 * size, 8.5 * size))
    if axes:
        if grid:
            ax.set_facecolor("#f8f9fa")
            ax.grid(True)
        else:
            ax.grid(False)
        ax.axis("off")
        ax = plt.axes(projection=ccrs.PlateCarree())
        # ax.set_global()
        # ax.coastlines(resolution='50m')
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)
    else:
        ax.grid(False)
        ax.axis("off")
    # Normalisation des valeurs pour la colorisation
    vmin = geodf[column_to_plot].min()
    vmax = geodf[column_to_plot].max()
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = load_cmap(cmap)  # Correction ici

    # Ajout des labels ou étiquettes (avec contour) au centre des polygones
    for idx, row in geodf.iterrows():
        polygons = (
            [row.geometry]
            if row.geometry.geom_type == "Polygon"
            else list(row.geometry.geoms)
        )

        for poly in polygons:
            x, y = poly.exterior.xy
            ax.fill(
                x,
                y,
                color=cmap(norm(row[column_to_plot])),
                edgecolor="black",
                linewidth=0.5,
            )

            centroid = poly.centroid
            label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"

            # Ajout du contour au texte
            ax.text(
                centroid.x,
                centroid.y,
                label_text,
                fontsize=10,
                ha="center",
                va="center",
                color="#0f172a",
                path_effects=[
                    patheffects.withStroke(  # Correction ici
                        linewidth=text_outline_width, foreground=text_outline_color
                    )
                ],
            )

    if show_legend:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(label_title or column_to_plot)

    plt.title(title, fontsize=20)
    plt.tight_layout()

    img_bytes = BytesIO()
    plt.savefig(img_bytes, format="png")
    img_bytes.seek(0)
    return img_bytes


# ----------------------------------------------------------------------
# ================Definition of the Map object==========================
# ----------------------------------------------------------------------


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
        title="Carte",
        projection=ccrs.PlateCarree(),
        data_crs="EPSG:4326",
        dpi=300,

    ):
        """
        Initialise une nouvelle carte avec cartopy.

        Parameters:
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
        """
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
        self.custom_palettes={}

        # Configuration de base
        self.ax.set_title(title, fontsize=16, fontweight="bold")

        # Limites par défaut (monde entier)
        self.bounds = [-180, -90, 180, 90]  # [minx, miny, maxx, maxy]

        # Ajout des caractéristiques par défaut
        self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
        self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # Affichage des informations sur le format de papier
        if self.paper_info:
            print(
                f"📄 Format de papier: {self.paper_info['format']} "
                f"({self.paper_info['orientation']}) - "
                f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
                f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
            )

    # ----------------------------------------------------------------------
    # ================Custom paper size ====================================
    # ----------------------------------------------------------------------

    def _process_figsize(self, figsize):
        """
        Traite le paramètre figsize pour déterminer la taille de la figure.

        Parameters:
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

        Parameters:
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
            dimensions = self.PAPER_SIZES[paper]
            return {
                "format": paper,
                "orientation": orientation,
                "dimensions_mm": f"{dimensions[0]} x {dimensions[1]}",
                "dimensions_inches": f"{dimensions[0]/25.4:.1f} x {dimensions[1]/25.4:.1f}",
            }
        return None

    def _paper_to_inches(self, paper_format, orientation="landscape"):
        """
        Convertit un format de papier en dimensions en pouces pour matplotlib.

        Parameters:
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

        Parameters:
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

        # Mise à jour des informations
        self.figsize = new_figsize
        self.paper_info = {
            "format": paper_format.upper(),
            "orientation": orientation,
            "dimensions_mm": f"{self.PAPER_SIZES[paper_format.upper()][0]} x {self.PAPER_SIZES[paper_format.upper()][1]}",
            "dimensions_inches": f"{new_figsize[0]:.1f} x {new_figsize[1]:.1f}",
        }

        # Redimensionnement de la figure
        self.fig.set_size_inches(new_figsize[0], new_figsize[1])

        # Affichage des informations
        print(
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
        print("📋 Formats de papier disponibles:")
        print("=" * 50)

        # Série A
        print("🅰️  Série A (ISO 216):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("A") or format_name.endswith("A0"):
                print(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        # Série B
        print("\n🅱️  Série B (ISO 216):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("B"):
                print(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        # Série C
        print("\n🅲  Série C (ISO 269 - Enveloppes):")
        for format_name, (width, height) in self.PAPER_SIZES.items():
            if format_name.startswith("C"):
                print(
                    f"   {format_name:4s}: {width:4d} x {height:4d} mm "
                    f'({width/25.4:4.1f}" x {height/25.4:4.1f}")'
                )

        print("\n💡 Utilisations courantes:")
        print("   A4: Documents, lettres")
        print("   A3: Dessins, plans, affiches")
        print("   A2: Grandes affiches, plans")
        print("   A1: Affiches, plans architecturaux")
        print("   A0: Très grandes affiches, plans")
        print("   B series: Livres, affiches, dépliants")
        print("   C series: Enveloppes")

        return self

    # ----------------------------------------------------------------------
    # ================Add map layer=========================================
    # ----------------------------------------------------------------------

    def _validate_geodataframe(self, gdf, expected_geom_type=None):
        """
        Valide et prépare un GeoDataFrame pour l'affichage.

        Parameters:
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
            print(
                "⚠️  Attention: Le GeoDataFrame contient des géométries nulles qui seront ignorées"
            )
            gdf = gdf.dropna(subset=["geometry"])

        # Vérification du CRS
        if gdf.crs is None:
            print(
                f"⚠️  Attention: Aucun CRS défini. Attribution du CRS par défaut: {self.data_crs}"
            )
            gdf = gdf.set_crs(self.data_crs)

        # Vérification du type de géométrie si spécifié
        if expected_geom_type:
            geom_types = gdf.geometry.geom_type.unique()
            if not all(geom_type == expected_geom_type for geom_type in geom_types):
                print(
                    f"⚠️  Attention: Types de géométries trouvés: {geom_types}. "
                    f"Type attendu: {expected_geom_type}"
                )

        return gdf

    def add_layer(self, gdf, layer_type="auto", label=None, **style_kwargs):
        """
        Ajoute une couche générique à partir d'un GeoDataFrame.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame à ajouter
        layer_type : str
            Type de couche ('auto', 'point', 'line', 'polygon')
        label : str
            Étiquette pour la légende
        **style_kwargs : dict
            Paramètres de style spécifiques au type de géométrie
        """
        # Validation du GeoDataFrame
        gdf = self._validate_geodataframe(gdf)

        # Détection automatique du type de géométrie
        if layer_type == "auto":
            geom_types = gdf.geometry.geom_type.unique()
            print(geom_types)
            if len(geom_types) == 1:
                geom_type = geom_types[0]
                if geom_type in ["Point", "MultiPoint"] :
                    layer_type = "point"
                elif geom_type in ["LineString", "MultiLineString"]:
                    layer_type = "line"
                elif geom_type in ["Polygon", "MultiPolygon"]:
                    layer_type = "polygon"
                else:
                    raise ValueError(f"Type de géométrie non supporté: {geom_type}")
            elif len(geom_types) > 1:
                if "Polygon" in geom_types or "MultiPolygon" in geom_types:
                    layer_type = "polygon"
                elif "LineString" in geom_types or "MultiLineString" in geom_types:
                    layer_type = "line"
                elif "Point" in geom_types or "MultiPoint" in geom_types:
                    layer_type = "point"
            else:
                raise ValueError(
                    f"Géométries mixtes détectées: {geom_types}. "
                    f"Spécifiez explicitement le layer_type."
                )

        # Ajout de la couche selon le type
        if layer_type == "point":
            return self.add_points(gdf, label=label, **style_kwargs)
        elif layer_type == "line":
            return self.add_lines(gdf, label=label, **style_kwargs)
        elif layer_type == "polygon":
            return self.add_polygons(gdf, label=label, **style_kwargs)
        else:
            raise ValueError(f"Type de couche non supporté: {layer_type}")
        return self

    def add_points(
        self,
        gdf,
        label=None,
        color="red",
        size=50,
        marker="o",
        alpha=1.0,
        edgecolor="black",
        linewidth=0.5,
        column=None,
        scheme=None,
        cmap="viridis",
        **kwargs,
    ):
        """
        Ajoute des points à partir d'un GeoDataFrame.

        Parameters:
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
        edgecolor : str
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
        # Validation
        gdf = self._validate_geodataframe(gdf)

        # Préparation des paramètres de style
        plot_kwargs = {
            "ax": self.ax,
            "color": color,
            "markersize": size,
            "marker": marker,
            "alpha": alpha,
            "edgecolor": edgecolor,
            "linewidth": linewidth,
            "transform": ccrs.PlateCarree(),
            **kwargs,
        }

        # Gestion de la coloration par colonne
        if column and column in gdf.columns:
            plot_kwargs["column"] = column
            if scheme:
                plot_kwargs["scheme"] = scheme
            plot_kwargs["cmap"] = cmap
            plot_kwargs.pop("color", None)  # Retirer color si on utilise column

        # Ajout du layer
        layer_info = {"type": "point", "gdf": gdf, "style": plot_kwargs, "label": label}
        self.layers.append(layer_info)

        # Ajout à la légende si label fourni
        if label:
            legend_element = plt.scatter(
                [],
                [],
                c=color if not column else "gray",
                s=size,
                marker=marker,
                alpha=alpha,
                edgecolors=edgecolor,
                linewidth=linewidth,
                label=label,
            )
            self.legend_elements.append(legend_element)

        # Mise à jour des limites
        self._update_bounds(gdf)

        return self

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

        Parameters:
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
        # Validation
        gdf = self._validate_geodataframe(gdf)

        # Préparation des paramètres de style
        plot_kwargs = {
            "ax": self.ax,
            "color": color,
            "linewidth": linewidth,
            "linestyle": linestyle,
            "alpha": alpha,
            "transform": ccrs.PlateCarree(),
            **kwargs,
        }

        # Gestion de la coloration par colonne
        if column and column in gdf.columns:
            plot_kwargs["column"] = column
            if scheme:
                plot_kwargs["scheme"] = scheme
            plot_kwargs["cmap"] = cmap
            plot_kwargs.pop("color", None)  # Retirer color si on utilise column

        # Ajout du layer
        layer_info = {"type": "line", "gdf": gdf, "style": plot_kwargs, "label": label}
        self.layers.append(layer_info)

        # Ajout à la légende si label fourni
        if label:
            legend_element = plt.Line2D(
                [0],
                [0],
                color=color if not column else "gray",
                linewidth=linewidth,
                linestyle=linestyle,
                alpha=alpha,
                label=label,
            )
            self.legend_elements.append(legend_element)

        # Mise à jour des limites
        self._update_bounds(gdf)

        return self

    def add_polygons(
        self,
        gdf,
        label=None,
        facecolor="green",
        alpha=0.5,
        edgecolor="black",
        linewidth=1,
        column=None,
        scheme=None,
        cmap="viridis",
        **kwargs,
    ):
        """
        Ajoute des polygones à partir d'un GeoDataFrame.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            GeoDataFrame contenant des géométries Polygon
        label : str
            Étiquette pour la légende
        facecolor : str, list, or column name
            Couleur(s) de remplissage ou nom de colonne pour coloration
        alpha : float
            Transparence (0-1)
        edgecolor : str
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
        # Validation
        gdf = self._validate_geodataframe(gdf)

        # Préparation des paramètres de style
        plot_kwargs = {
            "ax": self.ax,
            "facecolor": facecolor,
            "alpha": alpha,
            "edgecolor": edgecolor,
            "linewidth": linewidth,
            "transform": ccrs.PlateCarree(),
            **kwargs,
        }

        # Gestion de la coloration par colonne
        if column and column in gdf.columns:
            plot_kwargs["column"] = column
            if scheme:
                plot_kwargs["scheme"] = scheme
            plot_kwargs["cmap"] = cmap
            plot_kwargs.pop("facecolor", None)  # Retirer facecolor si on utilise column

        # Ajout du layer
        layer_info = {
            "type": "polygon",
            "gdf": gdf,
            "style": plot_kwargs,
            "label": label,
        }
        self.layers.append(layer_info)

        # Ajout à la légende si label fourni
        if label:
            legend_element = Patch(
                facecolor=facecolor if not column else "gray",
                edgecolor=edgecolor,
                linewidth=linewidth,
                alpha=alpha,
                label=label,
            )
            self.legend_elements.append(legend_element)

        # Mise à jour des limites
        self._update_bounds(gdf)

        return self

    def add_point(
        self,
        coordinates,
        label=None,
        color="red",
        size=50,
        marker="o",
        alpha=1.0,
        edge_color="black",
        edge_width=0.5,
        transform=None,
    ):
        """
        Ajoute un ou plusieurs points à la carte.

        Parameters:
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
        edge_width : float
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

        # Création du GeoDataFrame
        gdf = gpd.GeoDataFrame(geometry=points, crs=self.data_crs)

        # Transformation si nécessaire
        if transform is None:
            transform = ccrs.PlateCarree()

        # Ajout du layer
        layer_info = {
            "type": "point",
            "gdf": gdf,
            "style": {
                "color": color,
                "markersize": size,
                "marker": marker,
                "alpha": alpha,
                "edgecolor": edge_color,
                "linewidth": edge_width,
                "transform": transform,
            },
            "label": label,
        }
        self.layers.append(layer_info)

        # Ajout à la légende si label fourni
        if label:
            legend_element = plt.scatter(
                [],
                [],
                c=color,
                s=size,
                marker=marker,
                alpha=alpha,
                edgecolors=edge_color,
                linewidth=edge_width,
                label=label,
            )
            self.legend_elements.append(legend_element)

        # Mise à jour des limites
        self._update_bounds(gdf)

        return self

    def add_line(
        self,
        coordinates,
        label=None,
        color="blue",
        width=2,
        style="-",
        alpha=1.0,
        transform=None,
    ):
        """
        Ajoute une ou plusieurs lignes à la carte.

        Parameters:
        -----------
        coordinates : list of tuples or list of lists
            Coordonnées de la ligne. Format: [(lon1, lat1), (lon2, lat2), ...]
            Ou [[(lon1, lat1), (lon2, lat2)], [(lon3, lat3), (lon4, lat4)]] pour plusieurs lignes
        label : str
            Étiquette pour la légende
        color : str
            Couleur de la ligne
        width : float
            Épaisseur de la ligne
        style : str
            Style de ligne ('-', '--', '-.', ':')
        alpha : float
            Transparence (0-1)
        transform : cartopy.crs
            Projection des données (par défaut utilise data_crs)
        """
        # Vérification du format des coordonnées
        if isinstance(coordinates[0][0], (int, float)):
            # Une seule ligne
            lines = [LineString(coordinates)]
        else:
            # Plusieurs lignes
            lines = [LineString(coord) for coord in coordinates]

        # Création du GeoDataFrame
        gdf = gpd.GeoDataFrame(geometry=lines, crs=self.data_crs)

        # Transformation si nécessaire
        if transform is None:
            transform = ccrs.PlateCarree()

        # Ajout du layer
        layer_info = {
            "type": "line",
            "gdf": gdf,
            "style": {
                "color": color,
                "linewidth": width,
                "linestyle": style,
                "alpha": alpha,
                "transform": transform,
            },
            "label": label,
        }
        self.layers.append(layer_info)

        # Ajout à la légende si label fourni
        if label:
            legend_element = plt.Line2D(
                [0],
                [0],
                color=color,
                linewidth=width,
                linestyle=style,
                alpha=alpha,
                label=label,
            )
            self.legend_elements.append(legend_element)

        # Mise à jour des limites
        self._update_bounds(gdf)

        return self

    def add_polygon(
        self,
        coordinates,
        label=None,
        color="green",
        alpha=0.5,
        edge_color="black",
        edge_width=1,
        fill=True,
        transform=None,
    ):
        """
        Ajoute un ou plusieurs polygones à la carte.

        Parameters:
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
        edge_width : float
            Épaisseur du contour
        fill : bool
            Si True, remplit le polygone
        transform : cartopy.crs
            Projection des données (par défaut utilise data_crs)
        """
        # Vérification du format des coordonnées
        if isinstance(coordinates[0][0], (int, float)):
            # Un seul polygone
            polygons = [Polygon(coordinates)]
        else:
            # Plusieurs polygones
            polygons = [Polygon(coord) for coord in coordinates]

        # Création du GeoDataFrame
        gdf = gpd.GeoDataFrame(geometry=polygons, crs=self.data_crs)

        # Transformation si nécessaire
        if transform is None:
            transform = ccrs.PlateCarree()

        # Ajout du layer
        layer_info = {
            "type": "polygon",
            "gdf": gdf,
            "style": {
                "color": color if fill else "none",
                "edgecolor": edge_color,
                "linewidth": edge_width,
                "alpha": alpha,
                "transform": transform,
            },
            "label": label,
        }
        self.layers.append(layer_info)

        # Ajout à la légende si label fourni
        if label:
            legend_element = Patch(
                facecolor=color if fill else "none",
                edgecolor=edge_color,
                linewidth=edge_width,
                alpha=alpha,
                label=label,
            )
            self.legend_elements.append(legend_element)

        # Mise à jour des limites
        self._update_bounds(gdf)

        return self

    def add_natural_features(
        self,
        features=["coastline", "borders"],
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

        Parameters:
        -----------
        features : list
            Liste des caractéristiques à ajouter ('coastline', 'borders', 'land', 'ocean')
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
        if raster_path:
            with rasterio.open(raster_path) as src:
                raster_data = src.read(1)
                extent = [
                    src.bounds.left,
                    src.bounds.right,
                    src.bounds.bottom,
                    src.bounds.top,
                ]
                transform = src.transform
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

        # Affichage du raster
        im = self.ax.imshow(
            raster_data,
            extent=extent,
            transform=self.projection,
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

        # Stockage des informations de la couche
        layer_info = {
            "type": "raster",
            "data": raster_data,
            "style":
            {
            "extent": extent,
            "cmap": cmap,
            "alpha": alpha,
            "vmin": vmin,
            "vmax": vmax,
            "origin":"upper"
            }
        }
        self.layers.append(layer_info)

        return im

    def add_polygons_cloropleth(
        self,
        gdf,
        column_to_plot,
        label_column=None,
        cmap="viridis",
        alpha=0.7,
        edgecolor="black",
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
        edgecolor : str
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
        geodf=gdf
        if geodf.crs is None:
            print(
                f"Warning: No CRS defined for geodf. Setting default CRS to {default_crs}"
            )
            geodf = geodf.set_crs(default_crs)

        # Projection des données si nécessaire
        if geodf.crs != self.projection:
            try:
                geodf = geodf.to_crs(self.projection)
            except Exception as e:
                print(f"Error transforming CRS: {e}")
                print("Trying to use original coordinates...")

        # Vérifier que la colonne existe
        if column_to_plot not in geodf.columns:
            raise ValueError(f"Column '{column_to_plot}' not found in geodf")

        # Normalisation des valeurs
        vmin = geodf[column_to_plot].min()
        vmax = geodf[column_to_plot].max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        cmap_obj = load_cmap(cmap)

        # Tracé des polygones
        for idx, row in geodf.iterrows():
            geom = row.geometry

            # Vérifier que la géométrie est valide
            if geom is None or geom.is_empty:
                continue

            color = cmap_obj(norm(row[column_to_plot]))

            if geom.geom_type == "Polygon":
                polygons = [geom]
            elif geom.geom_type == "MultiPolygon":
                polygons = list(geom.geoms)
            else:
                continue

            for poly in polygons:
                if poly.is_empty:
                    continue

                x, y = poly.exterior.xy
                self.ax.fill(
                    x,
                    y,
                    color=color,
                    alpha=alpha,
                    edgecolor=edgecolor,
                    linewidth=linewidth,
                    transform=self.projection,
                )

                # Ajout des étiquettes
                if show_labels and label_column and label_column in geodf.columns:
                    try:
                        centroid = poly.centroid
                        label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"

                        self.ax.text(
                            centroid.x,
                            centroid.y,
                            label_text,
                            fontsize=label_size,
                            ha="center",
                            va="center",
                            color="#0f172a",
                            transform=self.projection,
                            path_effects=[
                                patheffects.withStroke(
                                    linewidth=text_outline_width,
                                    foreground=text_outline_color,
                                )
                            ],
                        )
                    except Exception as e:
                        print(
                            f"Warning: Could not add label for {row.get(label_column, 'unknown')}: {e}"
                        )

        # Barre de couleur
        if show_colorbar:
            sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)

        # Stockage des informations
        layer_info = {
            "type": "polygon",
            "gdf": geodf,
            "column_to_plot": column_to_plot,
            "style":{
            "cmap": cmap,
            "alpha": alpha,
            }

        }
        # self.layers.append(layer_info)
        self._update_bounds(geodf)
        self._apply_smart_centering()
        

    def add_points_cloropleth(
        self,
        gdf,
        column_to_plot,
        label_column=None,
        point_size_column=None,
        cmap="viridis",
        alpha=0.7,
        min_point_size=40,
        max_point_size=200,
        edgecolor="black",
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
        edgecolor : str
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
        geodf=gdf
        if geodf.crs is None:
            print(
                f"Warning: No CRS defined for geodf. Setting default CRS to {default_crs}"
            )
            geodf = geodf.set_crs(default_crs)

        # Projection des données si nécessaire
        if geodf.crs != self.projection:
            try:
                geodf = geodf.to_crs(self.projection)
            except Exception as e:
                print(f"Error transforming CRS: {e}")
                print("Trying to use original coordinates...")

        # Vérifier que la colonne existe
        if column_to_plot not in geodf.columns:
            raise ValueError(f"Column '{column_to_plot}' not found in geodf")

        # Normalisation des couleurs
        vmin = geodf[column_to_plot].min()
        vmax = geodf[column_to_plot].max()
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
        cmap_obj = load_cmap(cmap)

        # Normalisation des tailles
        if point_size_column:
            if point_size_column not in geodf.columns:
                print(
                    f"Warning: Column '{point_size_column}' not found. Using default point size."
                )
                point_size_column = None
            else:
                size_min = geodf[point_size_column].min()
                size_max = geodf[point_size_column].max()
                size_norm = plt.Normalize(vmin=size_min, vmax=size_max)

        # Tracé des points
        for idx, row in geodf.iterrows():
            geom = row.geometry

            # Vérifier que la géométrie est valide
            if geom is None or geom.is_empty:
                continue

            color = cmap_obj(norm(row[column_to_plot]))

            # Calcul de la taille du point
            if point_size_column:
                normalized_size = size_norm(row[point_size_column])
                point_size = min_point_size + normalized_size * (
                    max_point_size - min_point_size
                )
            else:
                point_size = min_point_size

            # Obtention des coordonnées
            if geom.geom_type == "Point":
                x, y = geom.x, geom.y
            else:
                # Utilisation du centroïde pour les autres géométries
                centroid = geom.centroid
                x, y = centroid.x, centroid.y

            # Tracé du point
            self.ax.scatter(
                x,
                y,
                s=point_size,
                color=color,
                alpha=alpha,
                edgecolor=edgecolor,
                linewidth=linewidth,
                transform=self.projection,
            )

            # Ajout des étiquettes
            if show_labels and label_column and label_column in geodf.columns:
                try:
                    # label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"
                    label_text = f"{row[label_column]}"

                    self.ax.text(
                        x,
                        y,
                        label_text,
                        fontsize=label_size,
                        ha="center",
                        va="center",
                        color="#0f172a",
                        transform=self.projection,
                        path_effects=[
                            patheffects.withStroke(
                                linewidth=text_outline_width,
                                foreground=text_outline_color,
                            )
                        ],
                    )
                except Exception as e:
                    print(
                        f"Warning: Could not add label for {row.get(label_column, 'unknown')}: {e}"
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
        self._update_bounds(geodf)
        self._apply_smart_centering()
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

        Parameters:
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

        Parameters:
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

        Parameters:
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
        self.ax.coastlines(resolution="50m", color="black", linewidth=0.5)
        self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # Réinitialisation de la grille
        self.gridlines = None

        return self
    
    def hide_grideline(self):
        """
        Masque toutes les bordures, ticks et labels de l'axe matplotlib donné.

        Args:
            ax: Un objet matplotlib.axes.Axes

        Exemple :
            fig, ax = plt.subplots()
            # ... ton code de tracé ...
            hide_grideline(ax)
            plt.show()
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
        custom_label : function, optional
            Expression qui prend une ligne (row) et retourne le texte de l'étiquette.
            Exemple : f"{row['nom']}\n{row['pop']:,d}"
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
                label_func = lambda row: eval(f'f"""{custom_label}"""')
                label = label_func(row)
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

    def set_title(
        self,
        title: str,
        fontsize: int = 14,
        fontweight: str = "bold",
        color: str = "black",
        pad: float = 20,
    ) -> "ChartBuilder":
        """Set the chart title with customization options."""
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
                print(f"❌ Impossible de retrouver le dossier : {e}")
        return files

    def add_arrow(
        self,
        arrow: 1,
        position: Tuple[float, float],
        zoom: float = 1,
        color: str = "black",
    ):

        arrow_path = self.get_north_arrows()[arrow - 1]
        img = read_image(arrow_path, color)
        imagebox = OffsetImage(img, zoom=zoom)
        ab = AnnotationBbox(imagebox, position, frameon=False)
        self.ax.add_artist(ab)
        return self

    # ----------------------------------------------------------------------
    # ================Custom color palette==================================
    # ----------------------------------------------------------------------

    def create_custom_palette(
        self, name: str, colors: List[str], save_palette: bool = True
    ) -> "ChartBuilder":
        """
        Create a custom color palette.

        Args:
            name (str): Name for the custom palette
            colors (List[str]): List of color values (hex codes, named colors, etc.)
            save_palette (bool): Whether to save the palette for future use

        Returns:
            ChartBuilder: Self for method chaining
        example:
            chart.create_custom_palette(name='my_palette',
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
                print(f"Warning: Invalid color '{color}' ignored")

        if not valid_colors:
            print("Error: No valid colors provided")
            return self

        if save_palette:
            self.custom_palettes[name] = valid_colors

        self.current_palette = valid_colors
        plt.rcParams["axes.prop_cycle"] = plt.cycler(color=valid_colors)

        print(f"Custom palette '{name}' created with {len(valid_colors)} colors")
        return self

    def get_available_palettes(
        self,
        include_custom: bool = True,
        include_seaborn: bool = True,
        include_matplotlib: bool = True,
    ) -> Dict[str, List[str]]:
        """
        Get all available color palettes.

        Args:
            include_custom (bool): Include custom palettes
            include_seaborn (bool): Include seaborn palettes
            include_matplotlib (bool): Include matplotlib colormaps

        Returns:
            Dict[str, List[str]]: Dictionary of palette names and their categories
        example:
            palettes = chart.get_available_palettes(include_custom=True,
                                                     include_seaborn=True,
                                                     include_matplotlib=True)
        """
        palettes = {
            "custom": [],
            "seaborn_qualitative": [],
            "seaborn_sequential": [],
            "seaborn_diverging": [],
            "matplotlib_sequential": [],
            "matplotlib_diverging": [],
            "matplotlib_cyclic": [],
            "matplotlib_qualitative": [],
        }

        # Custom palettes
        if include_custom:
            palettes["custom"] = list(self.custom_palettes.keys())

        # Seaborn palettes
        if include_seaborn:
            # Qualitative palettes
            palettes["seaborn_qualitative"] = [
                "deep",
                "muted",
                "bright",
                "pastel",
                "dark",
                "colorblind",
                "Set1",
                "Set2",
                "Set3",
                "Paired",
                "tab10",
                "tab20",
            ]

            # Sequential palettes
            palettes["seaborn_sequential"] = [
                "Blues",
                "BuGn",
                "BuPu",
                "GnBu",
                "Greens",
                "Greys",
                "Oranges",
                "OrRd",
                "PuBu",
                "PuBuGn",
                "PuRd",
                "Purples",
                "RdPu",
                "Reds",
                "YlGn",
                "YlGnBu",
                "YlOrBr",
                "YlOrRd",
                "rocket",
                "mako",
                "flare",
                "crest",
            ]

            # Diverging palettes
            palettes["seaborn_diverging"] = [
                "BrBG",
                "PiYG",
                "PRGn",
                "PuOr",
                "RdBu",
                "RdGy",
                "RdYlBu",
                "RdYlGn",
                "Spectral",
                "coolwarm",
                "bwr",
                "seismic",
                "icefire",
                "vlag",
            ]

        # Matplotlib colormaps
        if include_matplotlib:
            # Sequential
            palettes["matplotlib_sequential"] = [
                "viridis",
                "plasma",
                "inferno",
                "magma",
                "cividis",
                "Greys",
                "Purples",
                "Blues",
                "Greens",
                "Oranges",
                "Reds",
                "YlOrBr",
                "YlOrRd",
                "OrRd",
                "PuRd",
                "RdPu",
                "BuPu",
                "GnBu",
                "PuBu",
                "YlGnBu",
                "PuBuGn",
                "BuGn",
                "YlGn",
            ]

            # Diverging
            palettes["matplotlib_diverging"] = [
                "PiYG",
                "PRGn",
                "BrBG",
                "PuOr",
                "RdGy",
                "RdBu",
                "RdYlBu",
                "RdYlGn",
                "Spectral",
                "coolwarm",
                "bwr",
                "seismic",
            ]

            # Cyclic
            palettes["matplotlib_cyclic"] = ["twilight", "twilight_shifted", "hsv"]

            # Qualitative
            palettes["matplotlib_qualitative"] = [
                "Pastel1",
                "Pastel2",
                "Paired",
                "Accent",
                "Dark2",
                "Set1",
                "Set2",
                "Set3",
                "tab10",
                "tab20",
                "tab20b",
                "tab20c",
            ]

        return palettes

    @staticmethod
    def print_available_palettes(category: str = "all", limit: int = None) -> None:
        """
        Print available color palettes in a formatted way.

        Args:
            category (str): Category to display ('all', 'custom', 'seaborn', 'matplotlib', or specific category)
            limit (int): Limit number of palettes per category
        Returns: None
        example:
            ChartBuilder.print_available_palettes(category='seaborn', limit=5)
        """
        # Create temporary instance to access palettes
        temp_df = pd.DataFrame({"x": [1], "y": [1]})
        temp_chart = ChartBuilder(temp_df)
        palettes = temp_chart.get_available_palettes()

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
            print(f"Unknown category: {category}")
            print("Available categories:", list(palettes.keys()))
            return

        print("Available Color Palettes:")
        print("=" * 50)

        for cat in categories_to_show:
            if palettes[cat]:  # Only show non-empty categories
                print(f"\n{cat.replace('_', ' ').title()}:")
                print("-" * 30)

                palette_list = palettes[cat][:limit] if limit else palettes[cat]

                for i, palette in enumerate(palette_list, 1):
                    print(f"{i:3d}. {palette}")

                if limit and len(palettes[cat]) > limit:
                    remaining = len(palettes[cat]) - limit
                    print(f"    ... and {remaining} more")

    def preview_palette(self, palette_name: str, n_colors: int = 8) -> "ChartBuilder":
        """
        Preview a color palette by creating a simple color bar.

        Args:
            palette_name (str): Name of the palette to preview
            n_colors (int): Number of colors to show
        Returns:
            ChartBuilder: Self for method chaining
        example:
            chart.preview_palette('Set1', n_colors=5)
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
            except:
                try:
                    # Try matplotlib colormap
                    cmap = load_cmap(palette_name)
                    colors = [cmap(i / (n_colors - 1)) for i in range(n_colors)]
                except:
                    print(f"Palette '{palette_name}' not found")
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
    ):
        """
        Generate a gradient palette between two colors.

        Args:
            name (str): Name for the palette
            start_color (str): Starting color
            end_color (str): Ending color
            n_colors (int): Number of colors in the gradient
            save_palette (bool): Whether to save the palette
        Returns:
            ChartBuilder: Self for method chaining
        example:
            chart.generate_gradient_palette(name='my_gradient',
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

            print(f"Gradient palette '{name}' created: {start_color} → {end_color}")
            return self

        except ValueError as e:
            print(f"Error creating gradient: {e}")
            return self

    # ----------------------------------------------------------------------
    # ================Custom font===========================================
    # ----------------------------------------------------------------------

    def get_available_fonts(self, pattern: str = None, sort: bool = True) -> List[str]:
        """
        Get list of all available font names in the system.

        Args:
            pattern (str, optional): Filter fonts containing this pattern (case-insensitive)
            sort (bool): Whether to sort the font names alphabetically

        Returns:
            List[str]: List of available font names
        example:
            ChartBuilder.get_available_fonts(pattern='Arial', sort=True)
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
        Print available fonts to console in a formatted way.

        Args:
            pattern (str, optional): Filter fonts containing this pattern
            limit (int, optional): Limit number of fonts to display
        example:
            ChartBuilder.print_available_fonts(pattern='Arial', limit=10)
        """
        # Create a temporary instance to use the method
        temp_df = pd.DataFrame({"x": [1], "y": [1]})
        temp_chart = ChartBuilder(temp_df)
        fonts = temp_chart.get_available_fonts(pattern)

        if limit:
            fonts = fonts[:limit]

        print(
            f"Available fonts{f' (filtered by \"{pattern}\")' if pattern else ''}: {len(fonts)} found"
        )
        print("-" * 50)

        # Print in columns for better readability
        for i, font in enumerate(fonts, 1):
            print(f"{i:3d}. {font}")

        if limit and len(temp_chart.get_available_fonts(pattern)) > limit:
            remaining = len(temp_chart.get_available_fonts(pattern)) - limit
            print(f"\n... and {remaining} more fonts")

    def set_font(
        self, family: str = "sans-serif", size: int = 10, weight: str = "normal"
    ):
        """
        Set global font properties.

        Args:
            family (str): Font family name (use get_available_fonts() to see options)
            size (int): Font size
            weight (str): Font weight ('normal', 'bold', 'light', etc.)
        example:
            chart.set_font(family='Arial', size=12, weight='bold')
        """
        # Validate font exists
        available_fonts = self.get_available_fonts()
        if (
            family not in ["sans-serif", "serif", "monospace", "fantasy", "cursive"]
            and family not in available_fonts
        ):
            print(
                f"Warning: Font '{family}' not found. Available fonts can be checked with get_available_fonts()"
            )
            print(f"Using default font instead.")
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
        if hasattr(self, "_first_layer"):
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
        print(f"📊 Centrage intelligent appliqué:")
        print(
            f"   Format: {self.paper_info['format'] if self.paper_info else 'Personnalisé'} "
            f"({self.paper_info['orientation'] if self.paper_info else 'N/A'})"
        )
        print(f"   Ratio figure: {fig_aspect_ratio:.2f}")
        print(f"   Ratio données: {data_aspect_ratio:.2f}")
        print(
            f"   Étendue: [{extent[0]:.2f}, {extent[1]:.2f}, {extent[2]:.2f}, {extent[3]:.2f}]"
        )

    def center_on_bounds(self, bounds, margin="auto"):
        """
        Centre la carte sur des limites spécifiques avec marges adaptées.

        Parameters:
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

        Parameters:
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
        print("🛑Element de légende ajouté", elements)
        # Utilisation des éléments fournis ou de ceux stockés
        if elements is None:
            self.legend_elements = self.legend_elements
        else:
            self.legend_elements = self.legend_elements + elements
        legend_elements = self.legend_elements

        if not legend_elements:
            print("⚠️  Aucun élément de légende disponible")
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

        print(f"✅ Légende personnalisée créée avec {len(legend_elements)} éléments")

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

        Parameters:
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
        print(f"➕ Élément '{label}' ajouté à la légende")

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

        Parameters:
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
            print(
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

        print(
            f"📊 Légende créée pour la colonne '{column}' avec {len(legend_elements)} éléments"
        )

        return self

    def legend_presets(self, preset="default", **override_kwargs):
        """
        Applique des préréglages de légende.

        Parameters:
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
        print(params)

        self.custom_legend(**params)

        print(f"🎨 Préréglage '{preset}' appliqué à la légende")

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
            print("🗑️  Légende supprimée")
        else:
            print("⚠️  Aucune légende à supprimer")

        return self

    def clear_legend_elements(self):
        """
        Vide la liste des éléments de légende.

        Returns:
        --------
        Map: Instance de la carte pour chaînage
        """
        self.legend_elements = []
        print("🧹 Éléments de légende effacés")

        return self

    # ----------------------------------------------------------------------
    # ================custom scale bar======================================
    # ----------------------------------------------------------------------


    def add_scale_bar(self, length=None, location=(0.1, 0.05), linewidth=2,
                    units="km", color="black", fontsize=11,
                    pad=0.1, alpha=1, label=None, add_as_layer=True, **kwargs):
        """
        Ajoute une barre d'échelle (scale bar) sur la carte, et peut l'ajouter comme un layer.
        """
        # Stocke les paramètres pour affichage différé
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
            "kwargs": kwargs
        }
        if add_as_layer:
            self.layers.append({"type": "scalebar", "params": scale_bar_info})
        else:
            self._draw_scale_bar(**scale_bar_info)
        return self

    def _draw_scale_bar(self, length=None, location=(0, 0), linewidth=2,
                        units="km", color="black", fontsize=11,
                        pad=0.05, alpha=1, label=None, kwargs=None):
        """
        Trace la barre d'échelle sur self.ax (mêmes paramètres que add_scale_bar)
        """

        x0, x1 = self.ax.get_xlim()
        # print("x0:{} x1:{}".format(x0, x1))
        y0, y1 = self.ax.get_ylim()
        # print("y0:{} y1:{}".format(y0, y1))

        geod = Geod(ellps="WGS84")
        mid_lat = (y0 + y1) / 2

        try:
            map_width_m, _, _ = geod.inv(x0, mid_lat, x1, mid_lat)
            map_width_km = abs(map_width_m) / 1000
        except Exception as e:
            print(f"Erreur dans le calcul géodésique: {e}")
            map_width_km = 100

        if length is None:
            raw = map_width_km / 5
            if raw <= 0:
                raw = 10
            pow10 = 10 ** int(np.floor(np.log10(raw)))
            length = int(raw / pow10) * pow10
            if length == 0:
                length = max(1, int(raw))

        x_ax, y_ax = location
        start_x = x0 + x_ax * (x1 - x0)
        start_y = y0 + y_ax * (y1 - y0)
        print(f"Location est : ({x_ax}, {y_ax}). La bare d'échelle est placé à {x_ax*100} % de la longeur et à {y_ax*100} % de la hauteur)")
        try:
            lon_end, lat_end, _ = geod.fwd(start_x, start_y, 90, length * 1000)
            bar_length_deg = lon_end - start_x
        except Exception as e:
            print(f"Erreur dans le calcul géodésique forward: {e}")
            bar_length_deg = length * 1000 / (111320 * np.cos(np.radians(start_y)))

        scale_bar_start = (start_x, start_y)
        scale_bar_end = (start_x + bar_length_deg, start_y)

        # Filtrer les kwargs
        if kwargs is None:
            kwargs = {}
        line_kwargs = {k: v for k, v in kwargs.items() if k not in ['ha', 'va', 'fontweight']}
        text_kwargs = {k: v for k, v in kwargs.items() if k not in ['solid_capstyle']}

        self.ax.plot(
            [scale_bar_start[0], scale_bar_end[0]],
            [scale_bar_start[1], scale_bar_end[1]],
            color=color,
            linewidth=linewidth,
            solid_capstyle="butt",
            alpha=alpha,
            **line_kwargs
        )

        if label is None:
            label = f"{length} {units}"
        text_y = start_y + pad

        self.ax.text(
            (scale_bar_start[0] + scale_bar_end[0]) / 2,
            text_y,
            label,
            ha="center",
            va="bottom",
            color=color,
            fontsize=fontsize,
            alpha=alpha,
            fontweight="bold",
            **text_kwargs
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

        Parameters:
        -----------
        legend : bool
            Afficher la légende
        auto_extent : bool
            Ajuster automatiquement l'étendue aux données
        tight_layout : bool
            Ajuster automatiquement la mise en page
        smart_centering : bool
            Centrage intelligent adapté aux dimensions du papier
        """
        # Rendu de tous les layers
        for layer in self.layers:
            if layer.get("type") != "scalebar" and layer.get("type") !="raster":
                gdf = layer["gdf"]
                style = layer["style"].copy()  # Copie pour éviter les modifications

                # Retirer 'ax' et 'transform' des paramètres de style pour éviter les conflits
                style.pop("ax", None)
                style.pop("transform", None)
            if layer["type"] == "point":
                gdf = layer["gdf"]
                gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
            elif layer["type"] == "line":
                gdf = layer["gdf"]
                gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
            elif layer["type"] == "polygon":
                gdf = layer["gdf"] 
                gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
            elif layer["type"] == "raster":
                self.ax.imshow(img=layer["data"], **layer["style"])
            
        if title is not None:
            self.ax.set_title(title)

        # Ajustement automatique de l'étendue avec centrage intelligent
        if auto_extent and hasattr(self, "_first_layer"):
            if smart_centering:
                self._apply_smart_centering()
            else:
                # Ancien comportement par défaut
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
        # Légende
        if legend and self.legend_elements:
            self.custom_legend(**legend_params, **kwargs)

        for layer in self.layers:
            if layer.get("type") == "scalebar":
                self._draw_scale_bar(**layer["params"])
        # Mise en page
        if tight_layout:
            plt.tight_layout()

        plt.show()

        return self

    def save(self, filename, dpi=300, bbox_inches="tight"):
        """
        Sauvegarde la carte dans un fichier.

        Parameters:
        -----------
        filename : str
            Nom du fichier (avec extension)
        dpi : int
            Résolution
        bbox_inches : str
            Ajustement des marges
        """
        # Rendu de tous les layers avant sauvegarde
        # for layer in self.layers:
        #     gdf = layer["gdf"]
        #     style = layer["style"].copy()  # Copie pour éviter les modifications

        #     # Retirer 'ax' et 'transform' des paramètres de style pour éviter les conflits
        #     style.pop("ax", None)
        #     style.pop("transform", None)

        #     if layer["type"] == "point":
        #         gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
        #     elif layer["type"] == "line":
        #         gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
        #     elif layer["type"] == "polygon":
        #         gdf.plot(ax=self.ax, transform=ccrs.PlateCarree(), **style)
        self.show()
        plt.savefig(filename, dpi=dpi, bbox_inches=bbox_inches)
        print(f"Carte sauvegardée: {filename}")

        return self
