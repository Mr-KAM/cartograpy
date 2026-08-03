"""cartograpy.processing — traitement de données vectorielles et raster.

Réexporte la même surface publique qu'avant le découpage en sous-modules.
"""

from .vector import (
    centroids,
    join,
    fusion,
    add_column,
    split_multipolygon,
    split_multipolygon_from_gdf,
    get_multipolygon_info,
    get_geometry_types,
    clip_gdf_by_mask,
    clip_gdf_by_bbox,
    VectorTools,
)
from .raster import RasterTools

__all__ = [
    "centroids", "join", "fusion", "add_column",
    "split_multipolygon", "split_multipolygon_from_gdf",
    "get_multipolygon_info", "get_geometry_types",
    "clip_gdf_by_mask", "clip_gdf_by_bbox",
    "VectorTools", "RasterTools",
]
