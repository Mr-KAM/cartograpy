"""cartograpy.processing — vector and raster data processing.

Re-exports the same public surface as before the split into sub-modules.
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
