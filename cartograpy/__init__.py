# cartograpy – Python cartography toolkit
# Public API

from .iso_code import countries_iso3 as COUNTRY_ISO3

from .data import load, save, list_geofiles, GeoBoundaries, Bound, WorldBank, OSM, Hydro, DEM

from .processing import (
    centroids,
    join,
    fusion,
    add_column,
    split_multipolygon,
)

from .mapper import (
    Map,
    Map2D,
    WebMap,
    SituationMap,
    plot_choropleth,
    read_image,
)

from .styling import (
    get_fonts,
    get_available_palettes,
    color_palettes,
    custom_palettes,
    load_cmap,
    to_cmap,
    show_palette,
    show_palette_details,
    palettes_by_popularity,
    palettes_with_color,
    preview_multiple_palettes,
    set_style,
    list_all_styles,
)

from .geocoder import (
    GeocodingProvider,
    NominatimProvider,
    OpenCageProvider,
    GeocodingResult,
)

from .converter import converter, extract_gpx_data

import os


__all__ = [
    # data
    "load", "save", "list_geofiles", "GeoBoundaries", "Bound", "WorldBank", "OSM", "Hydro", "DEM",
    # processing
    "centroids", "join", "fusion", "add_column", "split_multipolygon",
    # mapper
    "Map", "Map2D", "WebMap", "SituationMap",
    "plot_choropleth", "read_image",
    # styling
    "get_fonts", "get_available_palettes",
    "color_palettes", "custom_palettes", "load_cmap", "to_cmap",
    "show_palette", "show_palette_details", "palettes_by_popularity",
    "palettes_with_color", "preview_multiple_palettes",
    "set_style", "list_all_styles",
    # geocoder
    "GeocodingProvider", "NominatimProvider", "OpenCageProvider", "GeocodingResult",
    # converter
    "converter", "extract_gpx_data",
    # iso
    "COUNTRY_ISO3",
    # project
    "init_project",
]

def init_project(path=None):
    """
    Initialise un projet cartograpy en créant les dossiers 'data' et 'output'.

    Args:
        path: Chemin du répertoire où créer les dossiers.
              Si None, utilise le répertoire courant.

    Returns:
        str: Chemin du projet initialisé.
    """
    if path is None:
        path = os.getcwd()

    data_dir = os.path.join(path, "data")
    output_dir = os.path.join(path, "output")

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    print(f"✅ Projet initialisé dans : {os.path.abspath(path)}")
    print(f"   📁 {data_dir}")
    print(f"   📁 {output_dir}")

    return os.path.abspath(path)


