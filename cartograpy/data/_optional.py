from __future__ import annotations

from importlib import import_module
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def _import_optional_dependency(module_name: str, extra: str, package_name: Optional[str] = None):
    """Imports an optional dependency with an explicit error message."""
    try:
        return import_module(module_name)
    except ImportError as e:
        install_name = package_name or module_name
        raise ImportError(
            f"Cette fonctionnalité nécessite le paquet optionnel '{install_name}'. "
            f"Installez-le avec: pip install cartograpy[{extra}]"
        ) from e


def _require_wbdata():
    return _import_optional_dependency("wbdata", "worldbank")


def _require_osmnx():
    return _import_optional_dependency("osmnx", "osm")


def _require_ee():
    return _import_optional_dependency("ee", "gee", "earthengine-api")


def _require_geemap():
    return _import_optional_dependency("geemap", "gee")


def _require_pystac_client():
    return _import_optional_dependency("pystac_client", "stac", "pystac-client")


def _require_planetary_computer():
    return _import_optional_dependency("planetary_computer", "stac", "planetary-computer")
