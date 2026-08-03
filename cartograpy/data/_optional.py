from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Union, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def _import_optional_dependency(module_name: str, package_name: Optional[str] = None):
    """Importe une dépendance optionnelle avec un message d'erreur explicite."""
    try:
        return import_module(module_name)
    except ImportError as e:
        install_name = package_name or module_name
        raise ImportError(
            f"Cette fonctionnalité nécessite le paquet optionnel '{install_name}'. "
            f"Installez-le avec: pip install {install_name}"
        ) from e


def _require_wbdata():
    return _import_optional_dependency("wbdata")


def _require_osmnx():
    return _import_optional_dependency("osmnx")


def _require_ee():
    return _import_optional_dependency("ee", "earthengine-api")


def _require_geemap():
    return _import_optional_dependency("geemap")
