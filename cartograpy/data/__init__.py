"""cartograpy.data — chargement/sauvegarde et récupération de données géospatiales.

Réexporte la même surface publique qu'avant le découpage en sous-modules.
"""

from .io import load, save, describe, list_geofiles
from .boundaries import GeoBoundaries, Bound
from .geocoding import Geocoder
from .osm import OSM
from .hydro import Hydro
from .dem import DEMDownloadError, DEM
from .worldbank import WorldBank
from .climate import Climate
from .gee import Gee

__all__ = [
    "load", "save", "describe", "list_geofiles",
    "GeoBoundaries", "Bound",
    "Geocoder",
    "OSM",
    "Hydro",
    "DEMDownloadError", "DEM",
    "WorldBank",
    "Climate",
    "Gee",
]
