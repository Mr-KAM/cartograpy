from __future__ import annotations

from typing import Union

BBox = Union[list[float], tuple[float, float, float, float]]
"""Bounding box in [xmin, ymin, xmax, ymax] format (WGS-84 / EPSG:4326)."""
