import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects
from io import BytesIO
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from pyfonts import load_google_font
from typing import Optional, Union, List, Tuple, Dict, Any
import matplotlib.font_manager as fm
import mpl_fontkit as fk
import numpy as np
import rasterio
from rasterio.plot import show as rasterio_show
from matplotlib.colors import LinearSegmentedColormap
import geopandas as gpd
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from io import BytesIO
from PIL import Image
import os

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

def read_image(path, color=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.svg':
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
        with NamedTemporaryFile("w+", suffix=".svg", delete=False, encoding="utf-8") as tmp_svg:
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

class Map:
    """
    Classe pour créer des cartes avec des données vectorielles et raster.
    """
    
    def __init__(self, figsize=(10, 8.5), projection=ccrs.PlateCarree(), 
                 background_color='#f8f9fa', show_coastlines=True, 
                 show_borders=True, show_grid=True,dpi=300):
        """
        Initialise la carte.
        
        Paramètres:
        -----------
        figsize : tuple
            Taille de la figure (largeur, hauteur)
        projection : cartopy.crs projection
            Projection cartographique
        background_color : str
            Couleur de fond
        show_coastlines : bool
            Afficher les côtes
        show_borders : bool
            Afficher les frontières
        show_grid : bool
            Afficher la grille
        """
        self.figsize = figsize
        self.projection = projection
        self.background_color = background_color
        self.show_coastlines = show_coastlines
        self.show_borders = show_borders
        self.show_grid = show_grid
        self.dpi=dpi
        
        # Initialisation de la figure
        self.fig, self.ax = plt.subplots(figsize=self.figsize, 
                                        subplot_kw={'projection': self.projection},dpi=self.dpi)
        self._setup_base_map()
        
        # Stockage des couches
        self.layers = []
        
    def _setup_base_map(self):
        """Configure la carte de base."""
        self.ax.set_facecolor(self.background_color)
        
        if self.show_coastlines:
            self.ax.coastlines(resolution='50m', color='#2d3748', linewidth=0.8)
            
        if self.show_borders:
            self.ax.add_feature(cfeature.BORDERS, color='#4a5568', linewidth=0.5)
            
        if self.show_grid:
            self.ax.gridlines(draw_labels=True, dms=True, x_inline=False, 
                             y_inline=False, alpha=0.5)
    
    def add_raster(self, raster_path=None, raster_array=None, extent=None, 
                   cmap='viridis', alpha=0.7, vmin=None, vmax=None, 
                   transform=None, title=None, show_colorbar=True):
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
                extent = [src.bounds.left, src.bounds.right, 
                         src.bounds.bottom, src.bounds.top]
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
        im = self.ax.imshow(raster_data, extent=extent, transform=self.projection,
                           cmap=cmap, alpha=alpha, vmin=vmin, vmax=vmax,
                           origin='upper')
        
        # Ajout de la barre de couleur
        if show_colorbar:
            cbar = plt.colorbar(im, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)
        
        # Stockage des informations de la couche
        layer_info = {
            'type': 'raster',
            'data': raster_data,
            'extent': extent,
            'cmap': cmap,
            'alpha': alpha,
            'vmin': vmin,
            'vmax': vmax
        }
        self.layers.append(layer_info)
        
        return im
    
    def add_vector_choropleth(self, geodf, column_to_plot, label_column=None,
                             cmap='viridis', alpha=0.7, edgecolor='black',
                             linewidth=0.5, show_labels=True, label_size=10,
                             text_outline_color='white', text_outline_width=2,
                             show_colorbar=True, title=None, default_crs='EPSG:4326'):
        """
        Ajoute une couche vectorielle choroplèthe.
        
        Paramètres:
        -----------
        geodf : GeoDataFrame
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
        if geodf.crs is None:
            print(f"Warning: No CRS defined for geodf. Setting default CRS to {default_crs}")
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
        cmap_obj = plt.cm.get_cmap(cmap)
        
        # Tracé des polygones
        for idx, row in geodf.iterrows():
            geom = row.geometry
            
            # Vérifier que la géométrie est valide
            if geom is None or geom.is_empty:
                continue
                
            color = cmap_obj(norm(row[column_to_plot]))
            
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            for poly in polygons:
                if poly.is_empty:
                    continue
                    
                x, y = poly.exterior.xy
                self.ax.fill(x, y, color=color, alpha=alpha,
                           edgecolor=edgecolor, linewidth=linewidth,
                           transform=self.projection)
                
                # Ajout des étiquettes
                if show_labels and label_column and label_column in geodf.columns:
                    try:
                        centroid = poly.centroid
                        label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"
                        
                        self.ax.text(centroid.x, centroid.y, label_text,
                                   fontsize=label_size, ha='center', va='center',
                                   color='#0f172a', transform=self.projection,
                                   path_effects=[patheffects.withStroke(
                                       linewidth=text_outline_width,
                                       foreground=text_outline_color)])
                    except Exception as e:
                        print(f"Warning: Could not add label for {row.get(label_column, 'unknown')}: {e}")
        
        # Barre de couleur
        if show_colorbar:
            sm = plt.cm.ScalarMappable(cmap=cmap_obj, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=self.ax, shrink=0.6, pad=0.05)
            if title:
                cbar.set_label(title, rotation=270, labelpad=20)
        
        # Stockage des informations
        layer_info = {
            'type': 'vector_choropleth',
            'geodf': geodf,
            'column_to_plot': column_to_plot,
            'cmap': cmap,
            'alpha': alpha
        }
        self.layers.append(layer_info)
    
    def add_vector_points(self, geodf, column_to_plot, label_column=None,
                         point_size_column=None, cmap='viridis', alpha=0.7,
                         min_point_size=40, max_point_size=200,
                         edgecolor='black', linewidth=0.5, show_labels=True,
                         label_size=10, text_outline_color='white',
                         text_outline_width=2, show_colorbar=True,
                         show_size_legend=True, title=None, default_crs='EPSG:4326'):
        """
        Ajoute une couche de points vectoriels.
        
        Paramètres:
        -----------
        geodf : GeoDataFrame
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
        if geodf.crs is None:
            print(f"Warning: No CRS defined for geodf. Setting default CRS to {default_crs}")
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
        cmap_obj = plt.cm.get_cmap(cmap)
        
        # Normalisation des tailles
        if point_size_column:
            if point_size_column not in geodf.columns:
                print(f"Warning: Column '{point_size_column}' not found. Using default point size.")
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
                point_size = min_point_size + normalized_size * (max_point_size - min_point_size)
            else:
                point_size = min_point_size
            
            # Obtention des coordonnées
            if geom.geom_type == 'Point':
                x, y = geom.x, geom.y
            else:
                # Utilisation du centroïde pour les autres géométries
                centroid = geom.centroid
                x, y = centroid.x, centroid.y
            
            # Tracé du point
            self.ax.scatter(x, y, s=point_size, color=color, alpha=alpha,
                           edgecolor=edgecolor, linewidth=linewidth,
                           transform=self.projection)
            
            # Ajout des étiquettes
            if show_labels and label_column and label_column in geodf.columns:
                try:
                    # label_text = f"{row[label_column]}\n{row[column_to_plot]:,.0f}"
                    label_text = f"{row[label_column]}"
                    
                    self.ax.text(x, y, label_text,
                               fontsize=label_size, ha='center', va='center',
                               color='#0f172a', transform=self.projection,
                               path_effects=[patheffects.withStroke(
                                   linewidth=text_outline_width,
                                   foreground=text_outline_color)])
                except Exception as e:
                    print(f"Warning: Could not add label for {row.get(label_column, 'unknown')}: {e}")
        
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
                display_size = min_point_size + normalized_size * (max_point_size - min_point_size)
                handles.append(plt.scatter([], [], s=display_size, color='gray',
                                         edgecolor='black', alpha=0.7))
                labels.append(f"{size_value:,.0f}")
            
            legend = self.ax.legend(handles, labels, title=point_size_column,
                                  loc='lower right', frameon=True, framealpha=0.9)
        
        # Stockage des informations
        layer_info = {
            'type': 'vector_points',
            'geodf': geodf,
            'column_to_plot': column_to_plot,
            'point_size_column': point_size_column,
            'cmap': cmap,
            'alpha': alpha
        }
        self.layers.append(layer_info)
    
    def set_extent(self, extent):
        """
        Définit l'étendue de la carte.
        
        Paramètres:
        -----------
        extent : tuple
            Étendue (xmin, xmax, ymin, ymax)
        """
        self.ax.set_extent(extent, crs=self.projection)
    
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

    def set_title(self, title: str, fontsize: int = 14, fontweight: str = 'bold', 
                  color: str = 'black', pad: float = 20) -> 'Map':
        """Set the chart title with customization options."""
        self.ax.set_title(title, fontsize=fontsize, fontweight=fontweight, 
                         color=color, pad=pad)
        return self
    
    def add_arrow(self, arrow:'svg/arrows/NorthArrow_03.svg', position: Tuple[float, float], zoom: float = 1, color: str = 'black'):
        img = read_image(arrow, color)
        imagebox = OffsetImage(img, zoom=zoom)
        ab = AnnotationBbox(imagebox, position, frameon=False)
        self.ax.add_artist(ab)
        return self
    
    def set_limits(self, xlim: Tuple[float, float] = None, 
                   ylim: Tuple[float, float] = None) -> 'Map':
        """Set axis limits.
        Args:
            xlim (Tuple[float, float], optional): Limits for the x-axis
            ylim (Tuple[float, float], optional): Limits for the y-axis
        """
        if xlim:
            self.ax.set_xlim(xlim)
        if ylim:
            self.ax.set_ylim(ylim)
        return self
    
    def save(self, filename=None, dpi=300, bbox_inches='tight'):
        """
        Sauvegarde la carte.
        
        Paramètres:
        -----------
        filename : str
            Nom du fichier (si None, retourne BytesIO)
        dpi : int
            Résolution
        bbox_inches : str
            Ajustement des marges
        
        Retourne:
        --------
        BytesIO si filename est None
        """
        plt.tight_layout()
        
        if filename:
            plt.savefig(filename, dpi=dpi, bbox_inches=bbox_inches)
            return filename
        else:
            img_bytes = BytesIO()
            plt.savefig(img_bytes, format='png', dpi=dpi, bbox_inches=bbox_inches)
            img_bytes.seek(0)
            return img_bytes
    
    def show(self):
        """Affiche la carte."""
        plt.show()
    
    def clear_layers(self):
        """Supprime toutes les couches."""
        self.ax.clear()
        self._setup_base_map()
        self.layers = []
    def create_custom_palette(self, name: str, colors: List[str], 
                            save_palette: bool = True) -> 'ChartBuilder':
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
        plt.rcParams['axes.prop_cycle'] = plt.cycler(color=valid_colors)
        
        print(f"Custom palette '{name}' created with {len(valid_colors)} colors")
        return self
    
    def get_available_palettes(self, include_custom: bool = True, 
                             include_seaborn: bool = True, 
                             include_matplotlib: bool = True) -> Dict[str, List[str]]:
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
            'custom': [],
            'seaborn_qualitative': [],
            'seaborn_sequential': [],
            'seaborn_diverging': [],
            'matplotlib_sequential': [],
            'matplotlib_diverging': [],
            'matplotlib_cyclic': [],
            'matplotlib_qualitative': []
        }
        
        # # Custom palettes
        # if include_custom:
        #     palettes['custom'] = list(self.custom_palettes.keys())
        
        # Seaborn palettes
        if include_seaborn:
            # Qualitative palettes
            palettes['seaborn_qualitative'] = [
                'deep', 'muted', 'bright', 'pastel', 'dark', 'colorblind',
                'Set1', 'Set2', 'Set3', 'Paired', 'tab10', 'tab20'
            ]
            
            # Sequential palettes
            palettes['seaborn_sequential'] = [
                'Blues', 'BuGn', 'BuPu', 'GnBu', 'Greens', 'Greys', 'Oranges',
                'OrRd', 'PuBu', 'PuBuGn', 'PuRd', 'Purples', 'RdPu', 'Reds',
                'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd', 'rocket', 'mako', 'flare', 'crest'
            ]
            
            # Diverging palettes
            palettes['seaborn_diverging'] = [
                'BrBG', 'PiYG', 'PRGn', 'PuOr', 'RdBu', 'RdGy', 'RdYlBu',
                'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'icefire', 'vlag'
            ]
        
        # Matplotlib colormaps
        if include_matplotlib:
            # Sequential
            palettes['matplotlib_sequential'] = [
                'viridis', 'plasma', 'inferno', 'magma', 'cividis',
                'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
                'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
                'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn'
            ]
            
            # Diverging
            palettes['matplotlib_diverging'] = [
                'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
                'RdYlBu', 'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic'
            ]
            
            # Cyclic
            palettes['matplotlib_cyclic'] = ['twilight', 'twilight_shifted', 'hsv']
            
            # Qualitative
            palettes['matplotlib_qualitative'] = [
                'Pastel1', 'Pastel2', 'Paired', 'Accent', 'Dark2',
                'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b', 'tab20c'
            ]
        
        return palettes
    
    @staticmethod
    def print_available_palettes(category: str = 'all', limit: int = None) -> None:
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
        temp_df = pd.DataFrame({'x': [1], 'y': [1]})
        temp_chart = ChartBuilder(temp_df)
        palettes = temp_chart.get_available_palettes()
        
        categories_to_show = []
        if category == 'all':
            categories_to_show = list(palettes.keys())
        elif category == 'seaborn':
            categories_to_show = [k for k in palettes.keys() if k.startswith('seaborn')]
        elif category == 'matplotlib':
            categories_to_show = [k for k in palettes.keys() if k.startswith('matplotlib')]
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
    
    def preview_palette(self, palette_name: str, n_colors: int = 8) -> 'ChartBuilder':
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
                    cmap = plt.cm.get_cmap(palette_name)
                    colors = [cmap(i / (n_colors - 1)) for i in range(n_colors)]
                except:
                    print(f"Palette '{palette_name}' not found")
                    return self
        
        # Create color preview
        y_pos = [0] * len(colors)
        x_pos = range(len(colors))
        
        for i, color in enumerate(colors):
            self.ax.barh(0, 1, left=i, color=color, edgecolor='white', linewidth=0.5)
        
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
            self.ax.text(i + 0.5, 0, color_text, ha='center', va='center', 
                        rotation=90, fontsize=8, color='white', weight='bold')
        
        return self
    
    def generate_gradient_palette(self, name: str, start_color: str, end_color: str, 
                                n_colors: int = 10, save_palette: bool = True) -> 'ChartBuilder':
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
            plt.rcParams['axes.prop_cycle'] = plt.cycler(color=colors)
            
            print(f"Gradient palette '{name}' created: {start_color} → {end_color}")
            return self
            
        except ValueError as e:
            print(f"Error creating gradient: {e}")
            return self
    
    
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
        temp_df = pd.DataFrame({'x': [1], 'y': [1]})
        temp_chart = ChartBuilder(temp_df)
        fonts = temp_chart.get_available_fonts(pattern)
        
        if limit:
            fonts = fonts[:limit]
            
        print(f"Available fonts{f' (filtered by \"{pattern}\")' if pattern else ''}: {len(fonts)} found")
        print("-" * 50)
        
        # Print in columns for better readability
        for i, font in enumerate(fonts, 1):
            print(f"{i:3d}. {font}")
            
        if limit and len(temp_chart.get_available_fonts(pattern)) > limit:
            remaining = len(temp_chart.get_available_fonts(pattern)) - limit
            print(f"\n... and {remaining} more fonts")
    
    def set_font(self, family: str = 'sans-serif', size: int = 10, 
                 weight: str = 'normal') -> 'ChartBuilder':
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
        if family not in ['sans-serif', 'serif', 'monospace', 'fantasy', 'cursive'] and family not in available_fonts:
            print(f"Warning: Font '{family}' not found. Available fonts can be checked with get_available_fonts()")
            print(f"Using default font instead.")
            family = 'sans-serif'
            
        plt.rcParams.update({
            'font.family': family,
            'font.size': size,
            'font.weight': weight
        })
        return self

# Exemple d'utilisation
if __name__ == "__main__":
    # Création d'une carte
    carte = Map(figsize=(12, 8), show_grid=True)
    
    # Exemple avec des données vectorielles (nécessite un GeoDataFrame)
    # carte.add_vector_choropleth(geodf, 'population', 'nom_region', 
    #                            cmap='Blues', title='Population par région')
    
    # Exemple avec des données raster (nécessite un fichier raster)
    # carte.add_raster('elevation.tif', cmap='terrain', title='Élévation (m)')
    
    # Ajout d'un titre
    carte.add_title('Ma carte personnalisée')
    
    # Sauvegarde
    # carte.save('ma_carte.png')
    
    # Affichage
    # carte.show()