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
    VectorTools,
    RasterTools,
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
    google_font,
    path_font,
    local_font,
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

from .project import Project, init_project


__all__ = [
    # data
    "load", "save", "list_geofiles", "GeoBoundaries", "Bound", "WorldBank", "OSM", "Hydro", "DEM",
    # processing
    "centroids", "join", "fusion", "add_column", "split_multipolygon", "VectorTools", "RasterTools",
    # mapper
    "Map", "Map2D", "WebMap", "SituationMap",
    "plot_choropleth", "read_image",
    # styling
    "get_fonts", "get_available_palettes",
    "color_palettes", "custom_palettes", "load_cmap", "to_cmap",
    "show_palette", "show_palette_details", "palettes_by_popularity",
    "palettes_with_color", "preview_multiple_palettes",
    "set_style", "list_all_styles",
    # iso
    "COUNTRY_ISO3",
    # project
    "Project", "init_project",
]

