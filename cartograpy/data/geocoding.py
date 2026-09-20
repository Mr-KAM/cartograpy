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
    A Python object to geocode one or more places using geopy
    and return the results in a GeoDataFrame.

    Attributes:
        geolocator (Nominatim): The Nominatim geocoder instance.
        user_agent (str): The user agent for Nominatim requests.
        delay (float): Delay in seconds between requests to avoid overloading the API.
    """

    def __init__(self, user_agent="mon_geocoder_geopandas_cartograpy", delay=1.0):
        """
        Initializes the Geocoder object.

        Args:
            user_agent (str): A unique identifier for your application when using
                              Nominatim. Strongly recommended.
            delay (float): The delay in seconds between each geocoding request.
                           Adjust it based on the service's rate limits.
        """
        self.user_agent = user_agent
        self.geolocator = Nominatim(user_agent=self.user_agent)
        self.delay = delay

    def _geocode_single(self, location_str):
        """
        Internal method to geocode a single place.

        Args:
            location_str (str): The place to geocode.

        Returns:
            tuple: A tuple containing (location_info, None) on success,
                   or (None, location_str) if the place isn't found or on error.
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
            logger.warning(f"Délai d'attente dépassé pour '{location_str}'.")
            return None, location_str
        except GeocoderServiceError as e:
            logger.error(f"Erreur du service de géocodage pour '{location_str}': {e}")
            return None, location_str
        except Exception as e:
            logger.error(f"Une erreur inattendue est survenue lors du géocodage de '{location_str}': {e}")
            return None, location_str

    def geocode(self, places):
        """
        Geocodes one or more places and returns a GeoDataFrame.

        Args:
            places (str or list): A single string representing a place,
                                      or a list of place strings.

        Returns:
            tuple: A tuple containing:
                   - geopandas.GeoDataFrame: A GeoDataFrame with the information of the places found
                                            and a 'geometry' column containing Point objects.
                   - list: A list of strings of the places that weren't found.
        """
        if isinstance(places, str):
            places = [places]

        found_locations_data = []
        not_found_places = []

        for place in places:
            location_info, not_found_place = self._geocode_single(place)
            if location_info:
                found_locations_data.append(location_info)
            else:
                not_found_places.append(not_found_place)

        # Build a GeoDataFrame
        if found_locations_data:
            # Build an initial pandas DataFrame
            df = pd.DataFrame(found_locations_data)
            # Build the 'geometry' column from the longitudes and latitudes
            geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
            # Convert to a GeoDataFrame, specifying the geometry column and CRS
            geodataframe = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326") # EPSG:4326 is the CRS for lat/lon (WGS84)
        else:
            # Build an empty GeoDataFrame with the expected columns
            geodataframe = gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'altitude', 'raw', 'geometry'], geometry=[], crs="EPSG:4326")

        return geodataframe, not_found_places


    def _reverse_geocode_single(self, coordinates_tuple):
        """
        Internal method to reverse-geocode a single set of coordinates.

        Args:
            coordinates_tuple (tuple): A (latitude, longitude) tuple.

        Returns:
            tuple: A tuple containing (location_info, None) on success,
                   or (None, coordinates_tuple) if the address isn't found or on error.
        """
        lat, lon = coordinates_tuple
        query_str = f"{lat}, {lon}" # For display and storage in 'query'

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
            logger.warning(f"Délai d'attente dépassé pour les coordonnées '{query_str}'.")
            return None, coordinates_tuple
        except GeocoderServiceError as e:
            logger.error(f"Erreur du service de géocodage inverse pour les coordonnées '{query_str}': {e}")
            return None, coordinates_tuple
        except Exception as e:
            logger.error(f"Une erreur inattendue est survenue lors du géocodage inverse de '{query_str}': {e}")
            return None, coordinates_tuple


    def reverse_geocode(self, coordinates):
        """
        Reverse-geocodes one or more coordinates (coordinates -> address) and returns a GeoDataFrame.

        Args:
            coordinates (tuple or list): A single (latitude, longitude) tuple,
                                         or a list of (latitude, longitude) tuples.

        Returns:
            tuple: A tuple containing:
                   - geopandas.GeoDataFrame: A GeoDataFrame with the information of the addresses found
                                            and a 'geometry' column containing Point objects.
                   - list: A list of (latitude, longitude) tuples for coordinates not found.
        """
        if isinstance(coordinates, tuple) and len(coordinates) == 2:
            coordinates = [coordinates] # Convert a single tuple into a list

        found_locations_data = []
        not_found_coordinates = []

        for coord_tuple in coordinates:
            location_info, not_found_coord = self._reverse_geocode_single(coord_tuple)
            if location_info:
                found_locations_data.append(location_info)
            else:
                not_found_coordinates.append(not_found_coord)

        if found_locations_data:
            df = pd.DataFrame(found_locations_data)
            # For reverse geocoding, the input coordinates are already lat/lon,
            # and the results returned by geopy are also lat/lon.
            # We use the results' latitude/longitude for the geometry.
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
        Searches for several candidates for a place and returns a GeoDataFrame.

        Args:
            place: Name of the place to search for.
            limit: Maximum number of results (default: 5).
            country_codes: ISO alpha-2 country code(s) to restrict the search.
                           Examples: "fr", ["fr", "de"]
            viewbox: Tuple (west, south, east, north) to restrict the search area.
            bounded: If True and viewbox is provided, strictly restricts the search to the viewbox.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame of the candidates found.
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
            logger.warning(f"Délai d'attente dépassé pour '{place}'.")
            return gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'geometry'], crs="EPSG:4326")
        except GeocoderServiceError as e:
            logger.error(f"Erreur du service de géocodage pour '{place}': {e}")
            return gpd.GeoDataFrame(columns=['query', 'address', 'latitude', 'longitude', 'geometry'], crs="EPSG:4326")

        if not locations:
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
        Geocodes while restricting the search to one or more countries.

        Args:
            places: A place or a list of places.
            country_codes: ISO alpha-2 country code(s). Examples: "ci", ["fr", "de"]

        Returns:
            tuple: (GeoDataFrame of results, list of places not found).
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
                logger.error(f"Erreur pour '{place}': {e}")
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
        Geocodes while restricting the search to a bounding box.

        Args:
            places: A place or a list of places.
            bbox: Tuple (west, south, east, north) defining the area.
            bounded: If True (default), strictly restricts to the bbox.

        Returns:
            tuple: (GeoDataFrame of results, list of places not found).
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
                logger.error(f"Erreur pour '{place}': {e}")
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
        Returns the polygonal geometry (outline) of a place via osmnx.

        Args:
            place: Name of the place (city, town, country, region...).

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with the place's geometry.
        """
        ox = _require_osmnx()
        return ox.geocode_to_gdf(place)

    def geocode_dataframe(self, df: pd.DataFrame, column: str) -> gpd.GeoDataFrame:
        """
        Enriches a pandas DataFrame with the geocoded coordinates of a column of place names.

        Args:
            df: pandas DataFrame containing a column of place names.
            column: Name of the column containing the places to geocode.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with latitude, longitude, and geometry columns added.
                             Rows not found have NaN values for these columns.

        Raises:
            ValueError: If the specified column doesn't exist in the DataFrame.
        """
        if column not in df.columns:
            raise ValueError(f"La colonne '{column}' n'existe pas dans le DataFrame.")

        result = df.copy()
        latitudes = []
        longitudes = []
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
        Extracts the address components (country, region, city, postal code...) of a place.

        Args:
            place: Name of the place or address to analyze.

        Returns:
            dict: Dictionary of address components (country, state, city, postcode, road, etc.).
                  Returns an empty dict if the place isn't found.
        """
        loc_info, _ = self._geocode_single(place)
        if loc_info is None:
            return {}
        raw = loc_info.get('raw', {})
        return raw.get('address', {})

    def distance(self, place_a: str, place_b: str, unit: str = "km") -> float:
        """
        Computes the geodesic distance between two geocoded places.

        Args:
            place_a: First place.
            place_b: Second place.
            unit: Distance unit: "km" (default), "m", "mi".

        Returns:
            float: Geodesic distance between the two places.

        Raises:
            ValueError: If one of the places isn't found or the unit is invalid.
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

    def sources(self) -> pd.DataFrame:
        """
        Returns a table of the data sources used by this class.

        Returns:
            pd.DataFrame: Columns 'name', 'url', 'description'.
        """
        return pd.DataFrame([
            {
                "name": "OpenStreetMap Nominatim",
                "url": "https://nominatim.openstreetmap.org/",
                "description": "Geocoding and reverse geocoding (geocode, search, reverse_geocode...).",
            },
            {
                "name": "OpenStreetMap (via osmnx)",
                "url": "https://www.openstreetmap.org/",
                "description": "Place outlines (used by bbox() and boundary()).",
            },
        ])

    def within(self, place: str, point: Union[tuple, list]) -> bool:
        """
        Checks whether a point (latitude, longitude) lies within a place's polygon.

        Args:
            place: Name of the place (city, country, region...).
            point: Tuple or list (latitude, longitude).

        Returns:
            bool: True if the point is inside the place's polygon.

        Raises:
            ImportError: If osmnx is not installed.
        """
        ox = _require_osmnx()
        gdf = ox.geocode_to_gdf(place)
        lat, lon = point
        pt = Point(lon, lat)
        return bool(gdf.union_all().contains(pt))
