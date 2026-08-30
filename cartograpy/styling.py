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
# ================gestion des styles de polices ========================
# ----------------------------------------------------------------------

def google_font(family: str, weight: Union[int, str, None] = None, italic: Optional[bool] = None) -> fm.FontProperties:
    """
    Charge une police depuis Google Fonts.

    Paramètres:
    -----------
    family : str
        Nom de la famille de police (ex: "Roboto", "Open Sans", "Cascadia Mono")
    weight : int ou str, optional
        Poids de la police (ex: 400, 700, "bold", "light", "regular")
    italic : bool, optional
        Utiliser la variante italique

    Retourne:
    ---------
    FontProperties : Objet police matplotlib utilisable avec le paramètre `font`

    Exemple:
        font = google_font("Roboto", weight="bold")
        ax.text(0.5, 0.5, "Hello", font=font, fontsize=20)
    """
    return load_google_font(family, weight=weight, italic=italic)


def path_font(font_url: str) -> fm.FontProperties:
    """
    Charge une police depuis une URL (ex: fichier .ttf/.otf sur GitHub).

    Paramètres:
    -----------
    font_url : str
        URL vers le fichier de police (ajouter ?raw=true pour les fichiers GitHub)

    Retourne:
    ---------
    FontProperties : Objet police matplotlib utilisable avec le paramètre `font`

    Exemple:
        font = path_font("https://github.com/google/fonts/blob/main/ofl/amaranth/Amaranth-Bold.ttf?raw=true")
        ax.text(0.5, 0.5, "Hello", font=font, fontsize=20)
    """
    return load_font(font_url=font_url)


def local_font(font_path: str) -> fm.FontProperties:
    """
    Charge une police depuis un fichier local sur votre ordinateur.

    Paramètres:
    -----------
    font_path : str
        Chemin vers le fichier de police local (ex: "C:/Fonts/MaPolice.ttf")

    Retourne:
    ---------
    FontProperties : Objet police matplotlib utilisable avec le paramètre `font`

    Exemple:
        font = local_font("chemin/vers/mapolice/Ultra-Regular.ttf")
        ax.text(0.5, 0.5, "Hello", font=font, fontsize=20)
    """
    return load_font(font_path=font_path)


def get_fonts(pattern: str = None, sort: bool = True) -> List[str]:
    """
    Récupère la liste de toutes les polices disponibles sur le système.

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
        get_fonts(pattern='Arial', sort=True)
    """
    # Récupération de toutes les polices
    fonts = [f.name for f in fm.fontManager.ttflist]

    # Suppression des doublons
    fonts = list(set(fonts))

    # Filtrage par motif si fourni
    if pattern:
        fonts = [font for font in fonts if pattern.lower() in font.lower()]

    # Tri si demandé
    if sort:
        fonts.sort()

    return fonts

# ----------------------------------------------------------------------
# ================gestion des palettes de couleurs =====================
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
    """Charge un colormap depuis pypalettes."""
    return pypalettes.load_cmap(cmap)

# Fonction pour afficher une palette
def show_palette_details(nom_palette):
    """Affiche les informations d'une palette spécifique"""
    if nom_palette in color_palettes:
        palette = color_palettes[nom_palette]
        logger.info(f"Palette: {palette['nom']}")
        logger.info(f"Likes: {palette['likes']}")
        logger.info(f"Couleurs: {palette['couleurs']}")
        logger.info("-" * 40)
    else:
        logger.info(f"Palette '{nom_palette}' non trouvée")

# Fonction pour rechercher par nombre de likes
def palettes_by_popularity(min_likes=0):
    """Retourne les palettes triées par popularité"""
    palettes_triees = []
    for key, palette in color_palettes.items():
        likes_num = float(palette['likes'].replace('K', '')) * 1000
        if likes_num >= min_likes:
            palettes_triees.append((key, palette, likes_num))
    
    return sorted(palettes_triees, key=lambda x: x[2], reverse=True)

# Fonction pour rechercher par couleur dominante
def palettes_with_color(couleur_recherchee):
    """Trouve les palettes contenant une couleur similaire"""
    palettes_trouvees = []
    for key, palette in color_palettes.items():
        if couleur_recherchee.upper() in [c.upper() for c in palette['couleurs']]:
            palettes_trouvees.append((key, palette))
    return palettes_trouvees


def to_cmap(colors,cmap_type="continuous"):
    """Convertit une liste de couleurs en colormap matplotlib."""
    return create_cmap(colors,cmap_type)


def custom_palettes():
    """Retourne les palettes personnalisées"""
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
    Récupère toutes les palettes de couleurs disponibles.

    Paramètres:
    -----------
    include_custom : bool
        Inclure les palettes personnalisées
    include_seaborn : bool
        Inclure les palettes seaborn
    include_matplotlib : bool
        Inclure les colormaps matplotlib

    Retourne:
    ---------
    Dict[str, List[str]] : Dictionnaire des noms de palettes par catégorie

    Exemple:
        palettes = get_available_palettes(include_custom=True,
                                          include_seaborn=True,
                                          include_matplotlib=True)
    """
    # liste des palettes personnalisées
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

    # Palettes Seaborn
    if include_seaborn:
        # Palettes qualitatives
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

        # Palettes séquentielles
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

        # Palettes divergentes
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

    # Colormaps Matplotlib
    if include_matplotlib:
        # Séquentielles
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

        # Divergentes
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

        # Cycliques
        palettes["matplotlib_cyclic"] = ["twilight", "twilight_shifted", "hsv"]

        # Qualitatives
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
    Aperçu de plusieurs palettes de couleurs dans une grille.

    Paramètres:
    -----------
    palette_names : list
        Liste des noms de palettes à prévisualiser
    n_colors : int
        Nombre de couleurs à afficher par palette
    custom_palettes : dict
        Dictionnaire de palettes personnalisées (optionnel)

    Retourne:
    ---------
    tuple : Objets (figure, axes)

    Exemple:
        preview_multiple_palettes(['p1', 'p2', 'p3'], custom_palettes=color_palettes)
    """
    n_palettes = len(palette_names)
    fig, axes = plt.subplots(n_palettes, 1, figsize=(10, 2 * n_palettes))
    
    # Cas d'une seule palette
    if n_palettes == 1:
        axes = [axes]
    
    for i, palette_name in enumerate(palette_names):
        show_palette(palette_name, n_colors, custom_palettes, axes[i])
    
    plt.tight_layout()
    return fig, axes

def show_palette(palette, n_colors: int = 8, custom_palettes: dict = None, ax=None):
    """
    Aperçu d'une palette de couleurs sous forme de barre colorée.

    Paramètres:
    -----------
    palette : str, list ou objet colormap
        Nom de la palette, liste de couleurs ou objet colormap
    n_colors : int
        Nombre de couleurs à afficher
    custom_palettes : dict
        Dictionnaire de palettes personnalisées (optionnel)
    ax : matplotlib.axes.Axes
        Objet axes matplotlib (optionnel, en crée un nouveau si None)

    Retourne:
    ---------
    matplotlib.axes.Axes : L'objet axes avec l'aperçu de la palette
    """
    import matplotlib.colors as mcolors

    # Création des axes si non fournis
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 2), dpi=300)
    else:
        ax.clear()

    if custom_palettes is None:
        custom_palettes = {}

    colors = []

    # 1. Liste de couleurs (list ou tuple)
    if isinstance(palette, (list, tuple)):
        colors = palette[:n_colors]
    # 2. Objet colormap matplotlib
    elif hasattr(palette, "__call__") and hasattr(palette, "colors") is False:
        # Génère n_colors à partir du colormap
        colors = [mcolors.to_hex(palette(i / (n_colors - 1))) for i in range(n_colors)]
    # 3. Palette personnalisée par nom (str)
    elif isinstance(palette, str) and palette in custom_palettes:
        val = custom_palettes[palette]
        if isinstance(val, dict) and 'couleurs' in val:
            colors = val['couleurs'][:n_colors]
        else:
            colors = val[:n_colors]
    # 4. Nom de palette seaborn ou matplotlib
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
                    logger.info(f"Palette '{palette}' introuvable")
                    return None
    else:
        logger.info("Format de palette non reconnu. Fournir un nom, une liste de couleurs ou un colormap.")
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
# ================ gestion des styles  =================================
# ----------------------------------------------------------------------

def set_style(style_name, source="matplotlib"):
    """
    Applique un style graphique depuis Matplotlib, Seaborn, mplcyberpunk ou SciencePlots.

    Paramètres:
    -----------
    style_name : str
        Nom du style à appliquer
    source : str
        Source du style : "matplotlib", "seaborn", "mplcyberpunk", "SciencePlots"
    """
    import matplotlib.pyplot as plt
    
    if source.lower() == "matplotlib":
        if style_name in plt.style.available:
            plt.style.use(style_name)
            logger.info(f"✅ Style Matplotlib appliqué : {style_name}")
        else:
            logger.info(f"❌ Style '{style_name}' non trouvé dans Matplotlib.")
    
    elif source.lower() == "seaborn":
        try:
            import seaborn as sns
            seaborn_styles = ["darkgrid", "whitegrid", "dark", "white", "ticks"]
            if style_name in seaborn_styles:
                sns.set_style(style_name)
                logger.info(f"✅ Style Seaborn appliqué : {style_name}")
            else:
                logger.info(f"❌ Style '{style_name}' non trouvé dans Seaborn.")
        except ImportError:
            logger.info("❌ Seaborn n'est pas installé.")
    
    elif source.lower() == "mplcyberpunk":
        try:
            import mplcyberpunk  # just to ensure it is installed
            if style_name == "cyberpunk":
                plt.style.use("cyberpunk")
                logger.info("✅ Style mplcyberpunk appliqué : cyberpunk")
            else:
                logger.info("❌ Seul le style 'cyberpunk' est disponible pour mplcyberpunk.")
        except ImportError:
            logger.info("❌ mplcyberpunk n'est pas installé.")
    
    elif source.lower() == "scienceplots":
        import scienceplots
        # Les styles SciencePlots apparaissent dans plt.style.available
        if style_name in plt.style.available:
            # plt.style.use(style_name)
            plt.style.use([style_name,'no-latex'])
            logger.info(f"✅ Style SciencePlots appliqué : {style_name}")
        else:
            logger.info(f"❌ Style '{style_name}' non trouvé dans SciencePlots.")
    else:
        logger.info("❌ Source inconnue. Choisis parmi : matplotlib, seaborn, mplcyberpunk, SciencePlots.")


def list_all_styles():
    """
    Liste tous les styles graphiques disponibles par source.

    Retourne:
    ---------
    dict : Dictionnaire des styles disponibles par source
    """
    import matplotlib.pyplot as plt
    styles = {}
    
    # 1. Styles Matplotlib
    styles['matplotlib'] = plt.style.available
    
    # 2. Styles Seaborn
    try:
        import seaborn as sns
        # Les styles Seaborn sont bien définis ici :
        seaborn_styles = ["darkgrid", "whitegrid", "dark", "white", "ticks"]
        styles['seaborn'] = seaborn_styles
    except ImportError:
        styles['seaborn'] = []
    
    # 3. Styles mplcyberpunk
    try:
        import mplcyberpunk
        # Le style "cyberpunk" n'apparaît dans plt.style.available qu'après
        # un premier plt.style.use("cyberpunk") (enregistrement paresseux de
        # matplotlib) : on ne peut donc pas s'y fier pour la détection.
        styles['mplcyberpunk'] = list(mplcyberpunk.cyberpunk_stylesheets.keys())
    except ImportError:
        styles['mplcyberpunk'] = []
    
    # 4. Styles SciencePlots
    try:
        import scienceplots

        # Les styles SciencePlots sont ajoutés à Matplotlib lors de l'installation
        # Liste classique, filtrée via plt.style.available
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


    