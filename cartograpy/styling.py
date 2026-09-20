import pypalettes
from pypalettes import create_cmap, show_cmap, load_palette, load_cmap
from pyfonts import load_google_font, load_font
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from typing import Optional, Union, List, Tuple, Dict, Any
import matplotlib.font_manager as fm
import logging

logger = logging.getLogger(__name__)
# ----------------------------------------------------------------------
# ================ font style management ================================
# ----------------------------------------------------------------------

def _sanitize_font(fp: fm.FontProperties) -> fm.FontProperties:
    """Removes non-hashable attributes set by pyfonts >=1.3 on
    FontProperties (e.g. ``_pyfonts_provider_metadata``), which crash
    ``FontProperties.__hash__`` with matplotlib >=3.11 (hashing __dict__)."""
    for key, val in list(vars(fp).items()):
        if getattr(type(val), "__hash__", None) is None:
            delattr(fp, key)
    return fp


def google_font(family: str, weight: Union[int, str, None] = None, italic: Optional[bool] = None) -> fm.FontProperties:
    """
    Loads a font from Google Fonts.

    Parameters:
    -----------
    family : str
        Font family name (e.g.: "Roboto", "Open Sans", "Cascadia Mono")
    weight : int or str, optional
        Font weight (e.g.: 400, 700, "bold", "light", "regular")
    italic : bool, optional
        Use the italic variant

    Returns:
    ---------
    FontProperties: matplotlib font object usable with the `font` parameter

    Example:
        font = google_font("Roboto", weight="bold")
        ax.text(0.5, 0.5, "Hello", font=font, fontsize=20)
    """
    return _sanitize_font(load_google_font(family, weight=weight, italic=italic))


def path_font(font_url: str) -> fm.FontProperties:
    """
    Loads a font from a URL (e.g.: .ttf/.otf file on GitHub).

    Parameters:
    -----------
    font_url : str
        URL to the font file (add ?raw=true for GitHub files)

    Returns:
    ---------
    FontProperties: matplotlib font object usable with the `font` parameter

    Example:
        font = path_font("https://github.com/google/fonts/blob/main/ofl/amaranth/Amaranth-Bold.ttf?raw=true")
        ax.text(0.5, 0.5, "Hello", font=font, fontsize=20)
    """
    return _sanitize_font(load_font(font_url=font_url))


def local_font(font_path: str) -> fm.FontProperties:
    """
    Loads a font from a local file on your computer.

    Parameters:
    -----------
    font_path : str
        Path to the local font file (e.g.: "C:/Fonts/MyFont.ttf")

    Returns:
    ---------
    FontProperties: matplotlib font object usable with the `font` parameter

    Example:
        font = local_font("path/to/myfont/Ultra-Regular.ttf")
        ax.text(0.5, 0.5, "Hello", font=font, fontsize=20)
    """
    return _sanitize_font(load_font(font_path=font_path))


def get_fonts(pattern: str = None, sort: bool = True) -> List[str]:
    """
    Retrieves the list of all fonts available on the system.

    Parameters:
    -----------
    pattern : str, optional
        Filters fonts containing this pattern (case-insensitive)
    sort : bool
        Sort the names alphabetically

    Returns:
    ---------
    List[str]: List of available font names

    Example:
        get_fonts(pattern='Arial', sort=True)
    """
    # Retrieve every font
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

# ----------------------------------------------------------------------
# ================ color palette management =============================
# ----------------------------------------------------------------------

color_palettes = {
    "p1": {
        "nom": "Dégradé Pastel",
        "likes": "71.7K",
        "couleurs": ["#B19CD9", "#FFB6C1", "#FFC0CB", "#87CEEB", "#6BB6FF"]
    },
    
    "p2": {
        "nom": "Océan et Chaleur",
        "likes": "54.9K", 
        "couleurs": ["#4A90E2", "#17A2B8", "#1E3A8A", "#FFA500", "#FF6B35"]
    },
    
    "p3": {
        "nom": "Tons Terreux",
        "likes": "77.1K",
        "couleurs": ["#4A5D23", "#2F4F2F", "#FFF8DC", "#D2691E", "#8B4513"]
    },
    
    "p4": {
        "nom": "Coucher de Soleil Marine",
        "likes": "42.9K",
        "couleurs": ["#1E3A8A", "#DC143C", "#FFA500", "#FFD700", "#F5F5DC"]
    },
    
    "p5": {
        "nom": "Sauge et Crème",
        "likes": "70.9K",
        "couleurs": ["#9CAF88", "#F5F5DC", "#F0E68C", "#DEB887", "#CD853F"]
    },
    
    "p6": {
        "nom": "Vert Forêt",
        "likes": "37.9K",
        "couleurs": ["#D3D3D3", "#8FBC8F", "#6B8E23", "#2F4F2F", "#1C3A1C"]
    },
    
    "p7": {
        "nom": "Marine et Or",
        "likes": "19.9K",
        "couleurs": ["#001F3F", "#003366", "#4169E1", "#FFD700", "#FFA500"]
    },
    
    "p8": {
        "nom": "Dégradé Bleu",
        "likes": "22.2K",
        "couleurs": ["#191970", "#4169E1", "#1E90FF", "#00CED1", "#E0FFFF"]
    },
    
    "p9": {
        "nom": "Mélange Vibrant",
        "likes": "114.3K",
        "couleurs": ["#2F4F4F", "#20B2AA", "#DAA520", "#FF8C00", "#FF6347"]
    },
    
    "p10": {
        "nom": "Sombre Minimaliste",
        "likes": "31K",
        "couleurs": ["#2F2F2F", "#4A4A4A", "#DC143C", "#8B0000"]
    },
    
    "p11": {
        "nom": "Bordeaux et Marine",
        "likes": "19.8K",
        "couleurs": ["#8B0000", "#A0522D", "#F5F5DC", "#1E3A8A", "#4682B4"]
    },
    
    "p12": {
        "nom": "Corail et Sarcelle",
        "likes": "72.9K",
        "couleurs": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#2C3E50", "#34495E"]
    },
    
    "p13": {
        "nom": "Bleu Océan",
        "likes": "39.9K",
        "couleurs": ["#000080", "#0000FF", "#4169E1", "#00CED1", "#87CEEB", "#E6F3FF"]
    },
    
    "p14": {
        "nom": "Contraste Moderne",
        "likes": "48.1K",
        "couleurs": ["#000000", "#1A1A1A", "#FF8C00", "#D3D3D3", "#F5F5F5"]
    },
    
    "p15": {
        "nom": "Sauge Chaleureux",
        "likes": "41.3K",
        "couleurs": ["#DEB887", "#F0E68C", "#FFB6C1", "#8FBC8F", "#FF6B6B"]
    },
    
    "p16": {
        "nom": "Beige Neutre",
        "likes": "35.4K",
        "couleurs": ["#F5F5DC", "#DDD5C7", "#D2B48C", "#C0A080", "#A0826D"]
    }
}


def load_cmap(cmap):
    """Loads a colormap from pypalettes."""
    return pypalettes.load_cmap(cmap)

# Function to display a palette
def show_palette_details(nom_palette):
    """Displays the information for a specific palette"""
    if nom_palette in color_palettes:
        palette = color_palettes[nom_palette]
        logger.info(f"Palette: {palette['nom']}")
        logger.info(f"Likes: {palette['likes']}")
        logger.info(f"Couleurs: {palette['couleurs']}")
        logger.info("-" * 40)
    else:
        logger.info(f"Palette '{nom_palette}' non trouvée")

# Function to search by number of likes
def palettes_by_popularity(min_likes=0):
    """Returns the palettes sorted by popularity"""
    palettes_triees = []
    for key, palette in color_palettes.items():
        likes_num = float(palette['likes'].replace('K', '')) * 1000
        if likes_num >= min_likes:
            palettes_triees.append((key, palette, likes_num))
    
    return sorted(palettes_triees, key=lambda x: x[2], reverse=True)

# Function to search by dominant color
def palettes_with_color(couleur_recherchee):
    """Finds palettes containing a similar color"""
    palettes_trouvees = []
    for key, palette in color_palettes.items():
        if couleur_recherchee.upper() in [c.upper() for c in palette['couleurs']]:
            palettes_trouvees.append((key, palette))
    return palettes_trouvees


def to_cmap(colors,cmap_type="continuous"):
    """Converts a list of colors into a matplotlib colormap."""
    return create_cmap(colors,cmap_type)


def custom_palettes():
    """Returns the custom palettes"""
    colors={}
    for key,valur in color_palettes.items():
        colors[key]=to_cmap(valur['couleurs'])
    
    return colors


def get_available_palettes(
    include_custom: bool = True,
    include_seaborn: bool = True,
    include_matplotlib: bool = True,
) -> Dict[str, List[str]]:
    """
    Retrieves every available color palette.

    Parameters:
    -----------
    include_custom : bool
        Include custom palettes
    include_seaborn : bool
        Include seaborn palettes
    include_matplotlib : bool
        Include matplotlib colormaps

    Returns:
    ---------
    Dict[str, List[str]]: Dictionary of palette names by category

    Example:
        palettes = get_available_palettes(include_custom=True,
                                          include_seaborn=True,
                                          include_matplotlib=True)
    """
    # list of custom palettes
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


def preview_multiple_palettes(palette_names: list, n_colors: int = 8, custom_palettes= get_available_palettes()):
    """
    Preview of several color palettes in a grid.

    Parameters:
    -----------
    palette_names : list
        List of palette names to preview
    n_colors : int
        Number of colors to display per palette
    custom_palettes : dict
        Dictionary of custom palettes (optional)

    Returns:
    ---------
    tuple: (figure, axes) objects

    Example:
        preview_multiple_palettes(['p1', 'p2', 'p3'], custom_palettes=color_palettes)
    """
    n_palettes = len(palette_names)
    fig, axes = plt.subplots(n_palettes, 1, figsize=(10, 2 * n_palettes))

    # Case of a single palette
    if n_palettes == 1:
        axes = [axes]
    
    for i, palette_name in enumerate(palette_names):
        show_palette(palette_name, n_colors, custom_palettes, axes[i])
    
    plt.tight_layout()
    return fig, axes

def show_palette(palette, n_colors: int = 8, custom_palettes: dict = None, ax=None):
    """
    Preview of a color palette as a colored bar.

    Parameters:
    -----------
    palette : str, list, or colormap object
        Palette name, list of colors, or colormap object
    n_colors : int
        Number of colors to display
    custom_palettes : dict
        Dictionary of custom palettes (optional)
    ax : matplotlib.axes.Axes
        matplotlib axes object (optional, creates a new one if None)

    Returns:
    ---------
    matplotlib.axes.Axes: the axes object with the palette preview
    """
    import matplotlib.colors as mcolors

    # Create the axes if not provided
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 2), dpi=300)
    else:
        ax.clear()

    if custom_palettes is None:
        custom_palettes = {}

    colors = []

    # 1. List of colors (list or tuple)
    if isinstance(palette, (list, tuple)):
        colors = palette[:n_colors]
    # 2. matplotlib colormap object
    elif hasattr(palette, "__call__") and hasattr(palette, "colors") is False:
        # Generate n_colors from the colormap
        colors = [mcolors.to_hex(palette(i / (n_colors - 1))) for i in range(n_colors)]
    # 3. Custom palette by name (str)
    elif isinstance(palette, str) and palette in custom_palettes:
        val = custom_palettes[palette]
        if isinstance(val, dict) and 'couleurs' in val:
            colors = val['couleurs'][:n_colors]
        else:
            colors = val[:n_colors]
    # 4. Seaborn or matplotlib palette name
    elif isinstance(palette, str):
        try:
            colors = sns.color_palette(palette, n_colors)
        except Exception:
            try:
                cmap = plt.get_cmap(palette)
                colors = [mcolors.to_hex(cmap(i / (n_colors - 1))) for i in range(n_colors)]
            except Exception:
                try:
                    show_cmap(palette)
                    return
                except Exception:
                    logger.warning(f"Palette '{palette}' introuvable")
                    return None
    else:
        logger.warning("Format de palette non reconnu. Fournir un nom, une liste de couleurs ou un colormap.")
        return None

    # Création de l'aperçu des couleurs
    for i, color in enumerate(colors):
        ax.barh(0, 1, left=i, color=color, edgecolor="white", linewidth=0.5)

    ax.set_xlim(0, len(colors))
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xticks(range(len(colors)))
    ax.set_xticklabels([f"C{i+1}" for i in range(len(colors))])
    ax.set_title(f"Aperçu palette : {getattr(palette, 'name', palette) if not isinstance(palette, (list, tuple)) else 'Liste personnalisée'}")

    # Ajout des codes couleurs en texte
    for i, color in enumerate(colors):
        color_text = color if isinstance(color, str) else mcolors.to_hex(color)
        ax.text(
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

    return ax


# ----------------------------------------------------------------------
# ================ style management =====================================
# ----------------------------------------------------------------------

def set_style(style_name, source="matplotlib"):
    """
    Applies a graphical style from Matplotlib, Seaborn, mplcyberpunk, or SciencePlots.

    Parameters:
    -----------
    style_name : str
        Name of the style to apply
    source : str
        Style source: "matplotlib", "seaborn", "mplcyberpunk", "SciencePlots"
    """
    import matplotlib.pyplot as plt
    
    if source.lower() == "matplotlib":
        if style_name in plt.style.available:
            plt.style.use(style_name)
        else:
            logger.warning(f"Style '{style_name}' non trouvé dans Matplotlib.")

    elif source.lower() == "seaborn":
        try:
            import seaborn as sns
            seaborn_styles = ["darkgrid", "whitegrid", "dark", "white", "ticks"]
            if style_name in seaborn_styles:
                sns.set_style(style_name)
            else:
                logger.warning(f"Style '{style_name}' non trouvé dans Seaborn.")
        except ImportError:
            logger.warning("Seaborn n'est pas installé.")

    elif source.lower() == "mplcyberpunk":
        try:
            import mplcyberpunk  # just to ensure it is installed
            if style_name == "cyberpunk":
                plt.style.use("cyberpunk")
            else:
                logger.warning("Seul le style 'cyberpunk' est disponible pour mplcyberpunk.")
        except (ImportError, AttributeError):
            logger.warning("mplcyberpunk n'est pas installé ou incompatible avec cette version de matplotlib.")

    elif source.lower() == "scienceplots":
        import scienceplots
        # SciencePlots styles show up in plt.style.available
        if style_name in plt.style.available:
            # plt.style.use(style_name)
            plt.style.use([style_name,'no-latex'])
        else:
            logger.warning(f"Style '{style_name}' non trouvé dans SciencePlots.")
    else:
        logger.warning("Source inconnue. Choisis parmi : matplotlib, seaborn, mplcyberpunk, SciencePlots.")


def list_all_styles():
    """
    Lists every available graphical style by source.

    Returns:
    ---------
    dict: Dictionary of available styles by source
    """
    import matplotlib.pyplot as plt
    styles = {}

    # 1. Matplotlib styles
    styles['matplotlib'] = plt.style.available

    # 2. Seaborn styles
    try:
        import seaborn as sns
        # Seaborn styles are well defined here:
        seaborn_styles = ["darkgrid", "whitegrid", "dark", "white", "ticks"]
        styles['seaborn'] = seaborn_styles
    except ImportError:
        styles['seaborn'] = []

    # 3. mplcyberpunk styles
    try:
        import mplcyberpunk
        # The "cyberpunk" style only appears in plt.style.available after
        # a first plt.style.use("cyberpunk") call (matplotlib's lazy
        # registration): so it can't be relied on for detection.
        styles['mplcyberpunk'] = list(mplcyberpunk.cyberpunk_stylesheets.keys())
    except (ImportError, AttributeError):
        styles['mplcyberpunk'] = []

    # 4. SciencePlots styles
    try:
        import scienceplots

        # SciencePlots styles are added to Matplotlib upon installation
        # Classic list, filtered through plt.style.available
        scienceplot_styles = [
            "science", "nature", "ieee", "acm", "vibrant", "bright", "muted", 
            "retro", "notebook", "scatter", "grid", "ieee_trans", "seaborn-v0_8"
        ]
        installed = [s for s in scienceplot_styles if s in plt.style.available]
        styles['SciencePlots'] = installed
    except ImportError:
        styles['SciencePlots'] = []
    
    return styles


def create_palette(colors,mode="continuous"):
    cmap = create_cmap(
    colors=colors,
    cmap_type=mode,
    )
    return cmap

def palette(name,mode="continuous"):
    cmap = load_cmap(name, cmap_type=mode)
    return cmap


    