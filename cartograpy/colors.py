from pypalettes import create_cmap
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from typing import Optional, Union, List, Tuple, Dict, Any

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

# Fonction pour afficher une palette
def show_palette(nom_palette):
    """Affiche les informations d'une palette spécifique"""
    if nom_palette in color_palettes:
        palette = color_palettes[nom_palette]
        print(f"Palette: {palette['nom']}")
        print(f"Likes: {palette['likes']}")
        print(f"Couleurs: {palette['couleurs']}")
        print("-" * 40)
    else:
        print(f"Palette '{nom_palette}' non trouvée")

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
def palettes_avec_couleur(couleur_recherchee):
    """Trouve les palettes contenant une couleur similaire"""
    palettes_trouvees = []
    for key, palette in color_palettes.items():
        if couleur_recherchee.upper() in [c.upper() for c in palette['couleurs']]:
            palettes_trouvees.append((key, palette))
    return palettes_trouvees


def to_cmap(colors,cmap_type="continuous"):
    """Convertit une liste de couleurs en cmap matplotlib"""
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
    list_custom=list(custom_palettes().keys)
    palettes = {
        "custom": list_custom,
        "seaborn_qualitative": [],
        "seaborn_sequential": [],
        "seaborn_diverging": [],
        "matplotlib_sequential": [],
        "matplotlib_diverging": [],
        "matplotlib_cyclic": [],
        "matplotlib_qualitative": [],
    }

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


def preview_multiple_palettes(palette_names: list, n_colors: int = 8, custom_palettes: dict = None):
    """
    Preview multiple color palettes in a grid layout.

    Args:
        palette_names (list): List of palette names to preview
        n_colors (int): Number of colors to show per palette
        custom_palettes (dict): Dictionary of custom palettes (optional)
    
    Returns:
        tuple: (figure, axes) objects
    
    Example:
        preview_multiple_palettes(['p1', 'p2', 'p3'], custom_palettes=color_palettes)
    """
    n_palettes = len(palette_names)
    fig, axes = plt.subplots(n_palettes, 1, figsize=(10, 2 * n_palettes))
    
    # Handle single palette case
    if n_palettes == 1:
        axes = [axes]
    
    for i, palette_name in enumerate(palette_names):
        preview_palette(palette_name, n_colors, custom_palettes, axes[i])
    
    plt.tight_layout()
    return fig, axes

def preview_palette(palette_name: str, n_colors: int = 8, custom_palettes: dict = None, ax=None):
    """
    Preview a color palette by creating a simple color bar.

    Args:
        palette_name (str): Name of the palette to preview
        n_colors (int): Number of colors to show
        custom_palettes (dict): Dictionary of custom palettes (optional)
        ax: Matplotlib axes object (optional, creates new if None)
    
    Returns:
        matplotlib.axes.Axes: The axes object with the palette preview
    
    Example:
        preview_palette('Set1', n_colors=5)
        preview_palette('p1', n_colors=4, custom_palettes=color_palettes)
    """
    
    # Create axes if not provided
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 2))
    else:
        # Clear current plot
        ax.clear()

    # Initialize custom_palettes if not provided
    if custom_palettes is None:
        custom_palettes = {}

    # Get colors
    colors = []
    if palette_name in custom_palettes:
        # For custom palettes, extract colors from the dictionary structure
        if isinstance(custom_palettes[palette_name], dict) and 'couleurs' in custom_palettes[palette_name]:
            colors = custom_palettes[palette_name]['couleurs'][:n_colors]
        else:
            colors = custom_palettes[palette_name][:n_colors]
    else:
        try:
            # Try seaborn palette
            colors = sns.color_palette(palette_name, n_colors)
        except:
            try:
                # Try matplotlib colormap
                cmap = plt.get_cmap(palette_name)
                colors = [cmap(i / (n_colors - 1)) for i in range(n_colors)]
            except:
                print(f"Palette '{palette_name}' not found")
                return ax

    # Create color preview
    for i, color in enumerate(colors):
        ax.barh(0, 1, left=i, color=color, edgecolor="white", linewidth=0.5)

    ax.set_xlim(0, len(colors))
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xticks(range(len(colors)))
    ax.set_xticklabels([f"C{i+1}" for i in range(len(colors))])
    ax.set_title(f"Palette Preview: {palette_name}")

    # Add color codes as text
    for i, color in enumerate(colors):
        if isinstance(color, str):
            color_text = color
        else:
            # Convert to hex
            color_text = mcolors.to_hex(color)
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
