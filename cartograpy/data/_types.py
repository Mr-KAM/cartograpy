from __future__ import annotations

from typing import Union

BBox = Union[list[float], tuple[float, float, float, float]]
"""Bounding box au format [xmin, ymin, xmax, ymax] (WGS-84 / EPSG:4326)."""
