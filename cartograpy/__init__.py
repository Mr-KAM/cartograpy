# cartograpy – Python cartography toolkit
# Public API

import logging
import sys

# Messages visibles par défaut (comme print()), sans configuration requise.
# `logging.getLogger("cartograpy").setLevel(logging.WARNING)` (ou plus haut)
# pour les couper ; retirer le handler pour les rediriger ailleurs.
_logger = logging.getLogger(__name__)
if not _logger.handlers:
    _handler = logging.StreamHandler(stream=sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

from .iso_code import countries_iso3 as COUNTRY_ISO3

from .data import (
    load, save, describe, list_geofiles,
    GeoBoundaries, Bound, Geocoder,
    OSM, Hydro, DEM, DEMDownloadError,
    WorldBank, Gee,
)

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
    plot_bivariate_choropleth,
    plot_bivariate_legend,
    assign_bivariate_classes,
    classify_variable,
    get_bivariate_palette,
    generate_bivariate_palette,
    list_bivariate_palettes,
    preview_bivariate_palette,
    BIVARIATE_PALETTES,
    make_hex_grid,
    aggregate_to_hex,
    plot_hexgrid_choropleth,
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
    "load", "save", "describe", "list_geofiles", "GeoBoundaries", "Bound",
    "Geocoder", "OSM", "Hydro", "DEM", "DEMDownloadError", "WorldBank", "Gee",
    # processing
    "centroids", "join", "fusion", "add_column", "split_multipolygon", "VectorTools", "RasterTools",
    # mapper
    "Map", "Map2D", "WebMap", "SituationMap",
    "plot_choropleth", "read_image",
    "plot_bivariate_choropleth", "plot_bivariate_legend",
    "assign_bivariate_classes", "classify_variable", "get_bivariate_palette",
    "generate_bivariate_palette",
    "list_bivariate_palettes", "preview_bivariate_palette",
    "BIVARIATE_PALETTES",
    "make_hex_grid", "aggregate_to_hex", "plot_hexgrid_choropleth",
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

