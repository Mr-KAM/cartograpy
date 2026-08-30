"""cartograpy.mapper — rendu cartographique (statique et interactif).

Réexporte la même surface publique qu'avant le découpage en sous-modules.
"""

from .helpers import read_image, plot_choropleth
from .map import Map
from .map2d import Map2D
from .webmap import WebMap
from .situation import SituationMap
from .bivariate import (
    plot_bivariate_choropleth,
    plot_bivariate_legend,
    assign_bivariate_classes,
    classify_variable,
    get_bivariate_palette,
    generate_bivariate_palette,
    list_bivariate_palettes,
    preview_bivariate_palette,
    BIVARIATE_PALETTES,
)
from .hexgrid import (
    make_hex_grid,
    aggregate_to_hex,
    plot_hexgrid_choropleth,
)

__all__ = [
    "Map", "Map2D", "WebMap", "SituationMap",
    "plot_choropleth", "read_image",
    "plot_bivariate_choropleth", "plot_bivariate_legend",
    "assign_bivariate_classes", "classify_variable",
    "get_bivariate_palette", "generate_bivariate_palette",
    "list_bivariate_palettes",
    "preview_bivariate_palette", "BIVARIATE_PALETTES",
    "make_hex_grid", "aggregate_to_hex", "plot_hexgrid_choropleth",
]
