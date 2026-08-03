from __future__ import annotations

import pandas as pd
import geopandas as gpd
from typing import TYPE_CHECKING, Union, List, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from geopy.location import Location
from shapely.geometry import Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, box, shape, mapping
import time
from ._optional import _require_osmnx
import logging

logger = logging.getLogger(__name__)


class Geocoder:
    """
    Un objet Python pour géocoder une ou plusieurs localités en utilisant geopy
    et renvoyer les résultats dans une GeoDataFrame.

    Attributes:
        geolocator (Nominatim): L'instance du géocodeur Nominatim.
        user_agent (str): L'agent utilisateur pour les requêtes Nominatim.
        delay (float): Délai en secondes entre les requêtes pour éviter de surcharger l'API.
    """

    def __init__(self, user_agent="mon_geocoder_geopandas_cartograpy", delay=1.0):
        """
        Initialise l'objet Geocoder.

        Args:
            user_agent (str): Un identifiant unique pour votre application lors de l'utilisation
                              de Nominatim. Fortement recommandé.
            delay (float): Le délai en secondes entre chaque requête de géocodage.
                           Ajustez-le en fonction des limites du service.
        """
        self.user_agent = user_agent
        self.geolocator = Nominatim(user_agent=self.user_agent)
        self.delay = delay

    def _geocode_single(self, location_str):
        """ 
        Méthode interne pour géocoder une seule localité.

        Args:
            location_str (str): La localité à géocoder.

        Returns:
            tuple: Un tuple contenant (location_info, None) si réussi,
                   ou (None, location_str) si la localité n'est pas trouvée ou en cas d'erreur.
        """
        try:
            time.sleep(self.delay)
            location = self.geolocator.geocode(location_str)  # type: ignore[union-attr]
            if location:
                loc: Location = location  # type: ignore[assignment]
                return {
                    'query': location_str,
                    'address': loc.address,
                    'latitude': loc.latitude,
                    'longitude': loc.longitude,
                    'altitude': loc.altitude,
                    'raw': loc.raw
                }, None
            else:
                return None, location_str
        except GeocoderTimedOut:
            logger.info(f"Avertissement : Délai d'attente dépassé pour '{location_str}'.")
            return None, location_str
        except GeocoderServiceError as e:
            logger.info(f"Erreur du service de géocodage pour '{location_str}': {e}")
            return None, location_str
        except Exception as e:
            logger.info(f"Une erreur inattendue est survenue lors du géocodage de '{location_str}': {e}")
            return None, location_str

    def geocode(self, places):
        """
        Géocode une ou plusieurs localités et renvoie une GeoDataFrame.

        Args:
            places (str or list): Une seule chaîne de caractères représentant une localité,
                                      ou une liste de chaînes de caractères de localités.

        Returns:
            tuple: Un tuple contenant :
                   - geopandas.GeoDataFrame: Une GeoDataFrame avec les informations des localités trouvées
                                            et une colonne 'geometry' contenant des objets Point.
                   - list: Une liste de chaînes de caractères des localités non trouvées.
        """
        if isinstance(places, str):
            places = [places]

        found_locations_data = []
        not_found_places = []

        logger.info(f"Début du géocodage de {len(places)} localité(s)...")

        for place in places:
            location_info, not_found_place = self._geocode_single(place)
            if location_info:
                found_locations_data.append(location_info)
            else:
                not_found_places.append(not_found_place)
            
        logger.info("Géocodage terminé.")

        # Crée une GeoDataFrame
        if found_locations_data:
            # Crée un DataFrame pandas initial
            df = pd.DataFrame(found_locations_data)
            # Crée la colonne 'geometry' à partir des longitudes et latitudes
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            # Convertit en GeoDataFrame, en spécifiant la colonne de géométrie et le CRS
            geodataframe = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326") # EPSG:4326 est le CRS pour les lat/lon (WGS84)
        else:
            # Crée une GeoDataFrame vide avec les colonnes attendues
            geodataframe = gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'altitude', 'raw', 'geometry'], geometry=[], crs="EPSG:4326")

        return geodataframe, not_found_places


    def _reverse_geocode_single(self, coordinates_tuple):
        """
        Méthode interne pour géocoder inversement un seul ensemble de coordonnées.

        Args:
            coordinates_tuple (tuple): Un tuple de (latitude, longitude).

        Returns:
            tuple: Un tuple contenant (location_info, None) si réussi,
                   ou (None, coordinates_tuple) si l'adresse n'est pas trouvée ou en cas d'erreur.
        """
        lat, lon = coordinates_tuple
        query_str = f"{lat}, {lon}" # Pour affichage et enregistrement dans 'query'

        try:
            time.sleep(self.delay)
            location = self.geolocator.reverse(query_str)  # type: ignore[union-attr]
            if location:
                loc: Location = location  # type: ignore[assignment]
                return {
                    'query': query_str,
                    'address': loc.address,
                    'latitude': loc.latitude,
                    'longitude': loc.longitude,
                    'altitude': loc.altitude,
                    'raw': loc.raw
                }, None
            else:
                return None, coordinates_tuple
        except GeocoderTimedOut:
            logger.info(f"Avertissement : Délai d'attente dépassé pour les coordonnées '{query_str}'.")
            return None, coordinates_tuple
        except GeocoderServiceError as e:
            logger.info(f"Erreur du service de géocodage inverse pour les coordonnées '{query_str}': {e}")
            return None, coordinates_tuple
        except Exception as e:
            logger.info(f"Une erreur inattendue est survenue lors du géocodage inverse de '{query_str}': {e}")
            return None, coordinates_tuple


    def reverse_geocode(self, coordinates):
        """
        Géocode inversement une ou plusieurs coordonnées (coordonnées -> adresse) et renvoie une GeoDataFrame.

        Args:
            coordinates (tuple or list): Un tuple (latitude, longitude) unique,
                                         ou une liste de tuples (latitude, longitude).

        Returns:
            tuple: Un tuple contenant :
                   - geopandas.GeoDataFrame: Une GeoDataFrame avec les informations des adresses trouvées
                                            et une colonne 'geometry' contenant des objets Point.
                   - list: Une liste de tuples (latitude, longitude) des coordonnées non trouvées.
        """
        if isinstance(coordinates, tuple) and len(coordinates) == 2:
            coordinates = [coordinates] # Convertit un tuple unique en liste

        found_locations_data = []
        not_found_coordinates = []

        logger.info(f"Début du géocodage inverse (coordonnées -> adresse) de {len(coordinates)} point(s)...")

        for coord_tuple in coordinates:
            location_info, not_found_coord = self._reverse_geocode_single(coord_tuple)
            if location_info:
                found_locations_data.append(location_info)
            else:
                not_found_coordinates.append(not_found_coord)
            
        logger.info("Géocodage inverse (coordonnées -> adresse) terminé.")

        if found_locations_data:
            df = pd.DataFrame(found_locations_data)
            # Pour le géocodage inversé, les coordonnées d'entrée sont déjà lat/lon,
            # et les résultats retournés par geopy sont également lat/lon.
            # On utilise les latitude/longitude des résultats pour la géométrie.
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            geodataframe = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        else:
            geodataframe = gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'altitude', 'raw', 'geometry'], geometry=[], crs="EPSG:4326")

        return geodataframe, not_found_coordinates

    def bbox(self, place: str) -> tuple:
        ox = _require_osmnx()
        gdf = ox.geocode_to_gdf(place)
        west, south, east, north = gdf.total_bounds
        return (west, south, east, north)

    def search(self, place: str, limit: int = 5,
               country_codes: Optional[Union[str, List[str]]] = None,
               viewbox: Optional[tuple] = None,
               bounded: bool = False) -> gpd.GeoDataFrame:
        """
        Recherche plusieurs candidats pour un lieu et retourne une GeoDataFrame.

        Args:
            place: Nom du lieu à rechercher.
            limit: Nombre maximum de résultats (défaut : 5).
            country_codes: Code(s) pays ISO alpha-2 pour limiter la recherche.
                           Exemples : "fr", ["fr", "de"]
            viewbox: Tuple (west, south, east, north) pour limiter la zone de recherche.
            bounded: Si True et viewbox fourni, restreint strictement la recherche à la viewbox.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame des candidats trouvés.
        """
        try:
            time.sleep(self.delay)
            locations = self.geolocator.geocode(
                place,
                exactly_one=False,
                limit=limit,
                country_codes=country_codes,
                viewbox=viewbox,
                bounded=bounded,
            )
        except GeocoderTimedOut:
            logger.info(f"Avertissement : Délai d'attente dépassé pour '{place}'.")
            return gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'geometry'], crs="EPSG:4326")
        except GeocoderServiceError as e:
            logger.info(f"Erreur du service de géocodage pour '{place}': {e}")
            return gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'geometry'], crs="EPSG:4326")

        if not locations:
            logger.info(f"Aucun résultat pour '{place}'.")
            return gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'geometry'], crs="EPSG:4326")

        rows = []
        for loc in locations:
            l: Location = loc
            rows.append({
                'query': place,
                'address': l.address,
                'latitude': l.latitude,
                'longitude': l.longitude,
                'raw': l.raw,
            })
        df = pd.DataFrame(rows)
        geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
        return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    def geocode_in_country(self, places: Union[str, List[str]],
                           country_codes: Union[str, List[str]]) -> tuple:
        """
        Géocode en contraignant la recherche à un ou plusieurs pays.

        Args:
            places: Localité ou liste de localités.
            country_codes: Code(s) pays ISO alpha-2. Exemples : "ci", ["fr", "de"]

        Returns:
            tuple: (GeoDataFrame des résultats, liste des localités non trouvées).
        """
        if isinstance(places, str):
            places = [places]

        found_data = []
        not_found: List[str] = []
        for place in places:
            try:
                time.sleep(self.delay)
                location = self.geolocator.geocode(place, country_codes=country_codes)
                if location:
                    l: Location = location
                    found_data.append({
                        'query': place,
                        'address': l.address,
                        'latitude': l.latitude,
                        'longitude': l.longitude,
                        'altitude': l.altitude,
                        'raw': l.raw,
                    })
                else:
                    not_found.append(place)
            except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
                logger.info(f"Erreur pour '{place}': {e}")
                not_found.append(place)

        if found_data:
            df = pd.DataFrame(found_data)
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        else:
            gdf = gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'altitude', 'raw', 'geometry'], crs="EPSG:4326")
        return gdf, not_found

    def geocode_in_bbox(self, places: Union[str, List[str]],
                        bbox: tuple,
                        bounded: bool = True) -> tuple:
        """
        Géocode en contraignant la recherche à une bounding box.

        Args:
            places: Localité ou liste de localités.
            bbox: Tuple (west, south, east, north) définissant la zone.
            bounded: Si True (défaut), restreint strictement à la bbox.

        Returns:
            tuple: (GeoDataFrame des résultats, liste des localités non trouvées).
        """
        if isinstance(places, str):
            places = [places]

        found_data = []
        not_found: List[str] = []
        for place in places:
            try:
                time.sleep(self.delay)
                location = self.geolocator.geocode(place, viewbox=bbox, bounded=bounded)
                if location:
                    l: Location = location
                    found_data.append({
                        'query': place,
                        'address': l.address,
                        'latitude': l.latitude,
                        'longitude': l.longitude,
                        'altitude': l.altitude,
                        'raw': l.raw,
                    })
                else:
                    not_found.append(place)
            except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
                logger.info(f"Erreur pour '{place}': {e}")
                not_found.append(place)

        if found_data:
            df = pd.DataFrame(found_data)
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        else:
            gdf = gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'altitude', 'raw', 'geometry'], crs="EPSG:4326")
        return gdf, not_found

    def boundary(self, place: str) -> gpd.GeoDataFrame:
        """
        Retourne la géométrie polygonale (contour) d'un lieu via osmnx.

        Args:
            place: Nom du lieu (ville, commune, pays, région…).

        Returns:
            gpd.GeoDataFrame: GeoDataFrame avec la géométrie du lieu.
        """
        ox = _require_osmnx()
        return ox.geocode_to_gdf(place)

    def geocode_dataframe(self, df: pd.DataFrame, column: str) -> gpd.GeoDataFrame:
        """
        Enrichit un DataFrame pandas avec les coordonnées géocodées d'une colonne de noms de lieux.

        Args:
            df: DataFrame pandas contenant une colonne de noms de lieux.
            column: Nom de la colonne contenant les lieux à géocoder.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame avec les colonnes latitude, longitude et geometry ajoutées.
                             Les lignes non trouvées ont des valeurs NaN pour ces colonnes.

        Raises:
            ValueError: Si la colonne spécifiée n'existe pas dans le DataFrame.
        """
        if column not in df.columns:
            raise ValueError(f"La colonne '{column}' n'existe pas dans le DataFrame.")

        result = df.copy()
        latitudes = []
        longitudes = []
        logger.info(f"Géocodage de {len(result)} ligne(s) depuis la colonne '{column}'...")
        for place in result[column]:
            loc_info, _ = self._geocode_single(str(place))
            if loc_info:
                latitudes.append(loc_info['latitude'])
                longitudes.append(loc_info['longitude'])
            else:
                latitudes.append(None)
                longitudes.append(None)

        result['latitude'] = latitudes
        result['longitude'] = longitudes
        geometry = [
            Point(lon, lat) if lon is not None and lat is not None else None
            for lon, lat in zip(result['longitude'], result['latitude'])
        ]
        return gpd.GeoDataFrame(result, geometry=geometry, crs="EPSG:4326")

    def components(self, place: str) -> dict:
        """
        Extrait les composants d'adresse (pays, région, ville, code postal…) d'un lieu.

        Args:
            place: Nom du lieu ou adresse à analyser.

        Returns:
            dict: Dictionnaire des composants d'adresse (country, state, city, postcode, road, etc.).
                  Retourne un dict vide si le lieu n'est pas trouvé.
        """
        loc_info, _ = self._geocode_single(place)
        if loc_info is None:
            return {}
        raw = loc_info.get('raw', {})
        return raw.get('address', {})

    def distance(self, place_a: str, place_b: str, unit: str = "km") -> float:
        """
        Calcule la distance géodésique entre deux lieux géocodés.

        Args:
            place_a: Premier lieu.
            place_b: Deuxième lieu.
            unit: Unité de distance : "km" (défaut), "m", "mi".

        Returns:
            float: Distance géodésique entre les deux lieux.

        Raises:
            ValueError: Si l'un des lieux n'est pas trouvé ou si l'unité est invalide.
        """
        from geopy.distance import geodesic

        valid_units = {"km", "m", "mi"}
        if unit not in valid_units:
            raise ValueError(f"Unité '{unit}' non supportée. Utilisez : {valid_units}")

        loc_a, _ = self._geocode_single(place_a)
        if loc_a is None:
            raise ValueError(f"Lieu non trouvé : '{place_a}'.")
        loc_b, _ = self._geocode_single(place_b)
        if loc_b is None:
            raise ValueError(f"Lieu non trouvé : '{place_b}'.")

        coords_a = (loc_a['latitude'], loc_a['longitude'])
        coords_b = (loc_b['latitude'], loc_b['longitude'])
        dist = geodesic(coords_a, coords_b)
        if unit == "km":
            return dist.km
        elif unit == "m":
            return dist.m
        else:
            return dist.miles

    def within(self, place: str, point: Union[tuple, list]) -> bool:
        """
        Vérifie si un point (latitude, longitude) est à l'intérieur du polygone d'un lieu.

        Args:
            place: Nom du lieu (ville, pays, région…).
            point: Tuple ou liste (latitude, longitude).

        Returns:
            bool: True si le point est dans le polygone du lieu.

        Raises:
            ImportError: Si osmnx n'est pas installé.
        """
        ox = _require_osmnx()
        gdf = ox.geocode_to_gdf(place)
        lat, lon = point
        pt = Point(lon, lat)
        return bool(gdf.union_all().contains(pt))
