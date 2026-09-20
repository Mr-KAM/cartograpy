from __future__ import annotations

from cartograpy.iso_code import *
import pandas as pd
import geopandas as gpd
import geojson
from typing import TYPE_CHECKING, Union, List, Optional, Tuple
from requests_cache import CachedSession
from shapely.geometry import Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, box, shape, mapping
import logging

logger = logging.getLogger(__name__)


class GeoBoundaries:
    """
    Client to interact with the GeoBoundaries API.
    Allows retrieving administrative boundaries for territories.
    """

    _CONTINENT_MAPPING = {
        'africa': 'Africa',
        'afrique': 'Africa',
        'asia': 'Asia',
        'asie': 'Asia',
        'europe': 'Europe',
        'north america': 'North America',
        'amérique du nord': 'North America',
        'south america': 'South America',
        'amérique du sud': 'South America',
        'oceania': 'Oceania',
        'océanie': 'Oceania',
        'antarctica': 'Antarctica',
        'antarctique': 'Antarctica'
    }

    def __init__(self, cache_expire_seconds: int = 604800):
        """
        Initializes the GeoBoundaries client.

        Args:
            cache_expire_seconds: Cache expiration duration in seconds (default: 1 week)
        """
        self._session = CachedSession(expire_after=cache_expire_seconds)
        self._base_url = "https://www.geoboundaries.org/api/current/gbOpen"
        self._continents_gdf = None
        self._countries_gdf = None

    def clear_cache(self):
        """Clears the request cache."""
        self._session.cache.clear()

    def set_cache_expire_time(self, seconds: int):
        """
        Updates the cache expiration time without clearing the existing cache.

        Args:
            seconds: New expiration duration in seconds
        """
        self._session = CachedSession(expire_after=seconds)

    def disable_cache(self):
        """Disables the request cache."""
        self._session = CachedSession(expire_after=-1)

    def is_valid_adm(self, iso3: str, adm: str) -> bool:
        """
        Checks whether an ADM level is valid for a given country.

        Args:
            iso3: ISO3 code of the country
            adm: Administrative level (e.g.: 'ADM0', 'ADM1', etc.)

        Returns:
            bool: True if the ADM level is valid
        """
        url = f"{self._base_url}/{iso3}/{adm}/"
        resp = self._session.get(url, verify=True)
        if resp.status_code != 200:
            return False
        try:
            data = resp.json()
            # The API returns a dict (or list) with data if the level exists
            if isinstance(data, list):
                return len(data) > 0
            return bool(data and not data.get("error"))
        except (ValueError, AttributeError):
            return False

    def _validate_adm(self, adm: Union[str, int]) -> str:
        """
        Validates and normalizes an ADM level.

        Args:
            adm: Administrative level (int or str)

        Returns:
            str: Validated and normalized ADM level

        Raises:
            KeyError: If the ADM level is invalid
        """
        if isinstance(adm, int) or len(str(adm)) == 1:
            adm = f'ADM{adm}'

        valid_adms = [f'ADM{i}' for i in range(6)] + ['ALL']
        if str.upper(adm) in valid_adms:
            return str.upper(adm)

        raise KeyError(f"Niveau ADM invalide: {adm}")

    def _get_smallest_adm(self, iso3: str) -> str:
        """
        Finds the smallest ADM level available for a country.

        Args:
            iso3: ISO3 code of the country

        Returns:
            str: Smallest available ADM level
        """
        for current_adm in range(5, -1, -1):
            adm_level = f'ADM{current_adm}'
            if self.is_valid_adm(iso3, adm_level):
                return adm_level

        return 'ADM0'  # Fallback

    def _is_valid_iso3_code(self, territory: str) -> bool:
        """
        Checks whether an ISO3 code is valid.

        Args:
            territory: Territory code or name

        Returns:
            bool: True if the ISO3 code is valid
        """
        return str.lower(territory) in iso_codes

    def _get_iso3_from_name_or_iso2(self, name: str) -> str:
        """
        Converts a country name or ISO2 code into an ISO3 code.

        Args:
            name: Country name or ISO2 code

        Returns:
            str: Corresponding ISO3 code

        Raises:
            KeyError: If the country isn't found
        """
        try:
            list_iso3 = self.get_iso3(name)
            if isinstance(list_iso3, str):
                return list_iso3.upper()
            # If several countries match, return the list
            elif isinstance(list_iso3, list) and len(list_iso3) >= 1:
                # If only one country matches, return its ISO3 code
                return list_iso3[0][1].upper()
            else:
                raise KeyError(f"{name} non trouvé")

        except KeyError as e:
            logger.error(f"KeyError : Couldn't find country named {e}")
            raise KeyError(f"Pays non trouvé: {name}")

    def get_iso3(self, territory: str) -> Union[str, List[tuple], None]:
        """
        Retrieves the ISO3 code of a territory.

        Args:
            territory: Territory name or ISO2/ISO3 code

        Returns:
            str: ISO3 code of the territory

        Raises:
            KeyError: If the territory isn't found
        """
        if self._is_valid_iso3_code(territory):
            return str.upper(territory)
        else:
            list_iso3 = [(countrie_name,iso) for countrie_name, iso in countries_iso3.items() if str.lower(territory) in str.lower(countrie_name)]
            # If no country matches, return None
            if list_iso3 == []:
                return None
            # If only one country matches, return its ISO3 code
            elif len(list_iso3) == 1:
                return list_iso3[0][1].upper()
            else : # If several countries match, with the same ISO3, return that ISO3 code
                if len(set([iso for _, iso in list_iso3])) == 1:
                    return list_iso3[0][1].upper()
                else :# Otherwise, return the list of matching countries
                    return list_iso3


    def list_countries(self) -> List[str]:
        """
        Retrieves the list of valid countries.

        Returns:
            List[str]: List of countries' ISO3 codes
        """
        return list(countries_iso3.keys())

    def _generate_url(self, territory: str, adm: Union[str, int]) -> str:
        """
        Generates the API URL for a given territory and ADM level.

        Args:
            territory: Territory name or ISO code
            adm: Administrative level

        Returns:
            str: API URL

        Raises:
            KeyError: If the territory or ADM level is invalid
        """
        iso3 = (str.upper(territory) if self._is_valid_iso3_code(territory)
                else self._get_iso3_from_name_or_iso2(territory))

        if adm != -1:
            adm = self._validate_adm(adm)
        else:
            adm = self._get_smallest_adm(iso3)

        if not self.is_valid_adm(iso3, adm):
            error_msg = f"ADM level '{adm}' doesn't exist for country '{territory}' ({iso3})"
            logger.error(f"KeyError : {error_msg}")
            raise KeyError(error_msg)

        return f"{self._base_url}/{iso3}/{adm}/"

    def adminLevels(self) -> str:
        return """
| Niveau GeoBoundaries | Nom commun (FR)           | Nom commun (EN)       |
| -------------------- | ------------------------- | --------------------- |
| ADM0                 | Pays                      | Country               |
| ADM1                 | Région / État / Province  | State / Region        |
| ADM2                 | Département / District    | District / County     |
| ADM3                 | Sous-préfecture / Commune | Subdistrict / Commune |
| ADM4                 | Village / Localité        | Village / Locality    |
| ADM5                 | Quartier / Secteur        | Neighborhood / Sector |
        """


    def metadata(self, territory: str, adm: Union[str, int]) -> dict:
        """
        Retrieves the metadata of a territory.

        Args:
            territory: Territory name or ISO code
            adm: Administrative level (use 'ALL' for every level)

        Returns:
            dict: Metadata of the territory
        """
        url = self._generate_url(territory, adm)
        return self._session.get(url, verify=True).json()

    def _get_data(self, territory: str, adm: Union[str, int], simplified: bool) -> str:
        """
        Retrieves the geographic data of a territory.

        Args:
            territory: Territory name or ISO code
            adm: Administrative level
            simplified: If True, uses simplified geometry

        Returns:
            str: GeoJSON data as a string
        """
        geom_complexity = 'simplifiedGeometryGeoJSON' if simplified else 'gjDownloadURL'

        try:
            json_uri = self.metadata(territory, adm)[geom_complexity]
        except Exception as e:
            error_msg = f"Error while requesting geoboudaries API\n URL : {self._generate_url(territory, adm)}\n"
            logger.error(error_msg)
            raise e

        return self._session.get(json_uri).text

    def adm(self, territories: Union[str, List[str]], adm: Union[str, int], simplified: bool = True) -> gpd.GeoDataFrame:
        """
        Retrieves the administrative boundaries of the specified territories.

        Args:
            territories: Territory(ies) to retrieve. Can be:
                - A single string: "Senegal", "SEN", "เซเนกัล"
                - A list of strings: ["SEN", "Mali"], ["セネガル", "մալի"]
            adm: Administrative level:
                - 'ADM0' to 'ADM5' (if it exists for the country)
                - int from 0 to 5
                - int -1 (returns the smallest available ADM level)
            simplified: If True, uses simplified geometry (default: True)

        Returns:
            gpd.GeoDataFrame: GeoDataFrame of the requested territories

        Note:
            Allowed values for territories:
            - ISO 3166-1 (alpha2): AFG, QAT, YEM, etc.
            - ISO 3166-1 (alpha3): AF, QA, YE, etc.
            - Country name in several supported languages
        """
        if isinstance(territories, str):
            territories = [territories]

        gdfs = []
        for territory in territories:
            gdf = gpd.GeoDataFrame.from_features(
                geojson.loads(self._get_data(territory, adm, simplified))
            )
            gdfs.append(gdf)

        return pd.concat(gdfs, ignore_index=True) if len(gdfs) > 1 else gdfs[0]


    def continents(self,continents: Optional[Union[str, List[str]]] = None) -> gpd.GeoDataFrame:
        """
        Returns a GeoDataFrame of the world's continents.

        Parameters:
        -----------
        continents : str, list of str, or None, optional
            - If str: returns the GeoDataFrame of the specified continent
            - If list: returns the GeoDataFrame of the continents in the list
            - If None: returns every continent

        Returns:
        --------
        gpd.GeoDataFrame
            GeoDataFrame containing the geometries of the requested continents

        Raises:
        -------
        ValueError
            If a specified continent doesn't exist in the data
        """

        # Load and cache the naturalearth data
        if self._continents_gdf is None:
            naturalearth_url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            world = gpd.read_file(naturalearth_url)
            continent_col = 'CONTINENT' if 'CONTINENT' in world.columns else 'continent'
            continents_gdf = world.dissolve(by=continent_col, as_index=False)
            continents_gdf = continents_gdf[[continent_col, 'geometry']]
            self._continents_gdf = continents_gdf.rename(columns={continent_col: 'continent'})

        # If no continent specified, return every continent
        if continents is None:
            return self._continents_gdf.copy()

        mapping = self._CONTINENT_MAPPING

        # If a single continent (string)
        if isinstance(continents, str):
            continent_name = mapping.get(continents.lower(), continents)
            filtered_gdf = self._continents_gdf[self._continents_gdf['continent'].str.contains(continent_name, case=False, na=False)]

            if filtered_gdf.empty:
                available_continents = ', '.join(self._continents_gdf['continent'].unique())
                raise ValueError(f"Continent '{continents}' non trouvé. Continents disponibles: {available_continents}")

            return filtered_gdf

        # If a list of continents
        elif isinstance(continents, list):
            normalized_continents = [mapping.get(c.lower(), c) for c in continents]
            mask = self._continents_gdf['continent'].str.lower().isin([c.lower() for c in normalized_continents])
            filtered_gdf = self._continents_gdf[mask]

            if filtered_gdf.empty:
                available_continents = ', '.join(self._continents_gdf['continent'].unique())
                raise ValueError(f"Aucun continent trouvé dans la liste. Continents disponibles: {available_continents}")

            found_continents = filtered_gdf['continent'].str.lower().tolist()
            missing = [c for c in continents if mapping.get(c.lower(), c).lower() not in found_continents]
            if missing:
                logger.warning(f"Attention: Continents non trouvés: {', '.join(missing)}")

            return filtered_gdf

        else:
            raise TypeError("Le paramètre 'continents' doit être une chaîne, une liste ou None")

    def list_continents_names(self) -> dict:
        return dict(self._CONTINENT_MAPPING)

    def sources(self) -> pd.DataFrame:
        """Returns a table of the data sources used by this class."""
        return pd.DataFrame([
            {
                "name": "geoBoundaries",
                "url": "https://www.geoboundaries.org/",
                "description": "Official administrative boundaries by country and ADM level.",
            },
        ])

class Bound(GeoBoundaries):
    """
    Extended client for the GeoBoundaries API.
    Inherits from GeoBoundaries and adds utility methods:
    get_admin, get_country, get_continent, get_world.
    """

    def get_admin(self, territories: Union[str, List[str]], adm: Union[str, int], simplified: bool = True) -> gpd.GeoDataFrame:
        """
        Retrieves the administrative boundaries of the specified territories.
        Delegates to the parent class's ``adm()``.

        Args:
            territories: Territory(ies) to retrieve. Can be:
                - A single string: "Senegal", "SEN", "เซเนกัล"
                - A list of strings: ["SEN", "Mali"], ["セネガル", "մալի"]
            adm: Administrative level:
                - 'ADM0' to 'ADM5' (if it exists for the country)
                - int from 0 to 5
                - int -1 (returns the smallest available ADM level)
            simplified: If True, uses simplified geometry (default: True)

        Returns:
            gpd.GeoDataFrame: GeoDataFrame of the territories
        """
        return self.adm(territories, adm, simplified)

    def get_country(self, name: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Retrieves the boundaries (ADM0) of one or more countries.

        Args:
            name: Country name, ISO2/ISO3 code, or a list of names/codes.
                  Examples: "France", "FRA", ["France", "SEN", "Mali"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame containing the geometry/geometries of the country/countries (ADM0 level).

        Raises:
            KeyError: If a country isn't found.

        Examples:
            >>> b = Bound()
            >>> france = b.get_country("France")
            >>> pays = b.get_country(["France", "SEN", "Mali"])
        """
        return self.get_admin(name, adm=0, simplified=True)

    def get_continent(self, name: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Retrieves the geometry of one or more continents from their name.

        Args:
            name: Continent name or list of names (French or English).
                  Examples: "Africa", "Afrique", ["Europe", "Afrique"], ["Asia", "Amérique du Sud"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame containing the geometry/geometries of the continent(s).

        Raises:
            ValueError: If a continent isn't found.

        Examples:
            >>> b = Bound()
            >>> afrique = b.get_continent("Afrique")
            >>> europe = b.get_continent("Europe")
            >>> plusieurs = b.get_continent(["Afrique", "Europe", "Asia"])
        """
        return self.continents(name)

    def get_world(self, level: str = "continent") -> gpd.GeoDataFrame:
        """
        Returns a GeoDataFrame of the whole world, aggregated by continent or by country.

        Args:
            level: Aggregation level. Possible values:
                - "continent": returns the geometries of every continent (default)
                - "country": returns the geometries of every country

        Returns:
            gpd.GeoDataFrame: GeoDataFrame containing the world's geometries.

        Raises:
            ValueError: If the specified level isn't "continent" or "country".

        Examples:
            >>> b = Bound()
            >>> continents = b.get_world("continent")
            >>> pays = b.get_world("country")
        """
        level = level.strip().lower()
        if level == "continent":
            return self.continents()
        elif level == "country":
            return self._load_countries()
        else:
            raise ValueError(
                f"Niveau '{level}' non supporté. Utilisez 'continent' ou 'country'."
            )

    def _load_countries(self) -> gpd.GeoDataFrame:
        """Loads and caches the Natural Earth countries."""
        if self._countries_gdf is None:
            naturalearth_url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            world = gpd.read_file(naturalearth_url)
            self._countries_gdf = world[['NAME', 'ISO_A3', 'CONTINENT', 'geometry']].rename(
                columns={'NAME': 'name', 'ISO_A3': 'iso3', 'CONTINENT': 'continent'}
            )
        return self._countries_gdf.copy()

    def get_neighbors(self, territory: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Returns the neighboring (adjacent) countries of one or more territories.

        Args:
            territory: Country name, ISO2/ISO3 code, or list of names/codes.
                       Examples: "France", "CIV", ["SEN", "Mali"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame of the neighboring countries (excluding the country itself).

        Examples:
            >>> b = Bound()
            >>> voisins = b.get_neighbors("CIV")
            >>> voisins = b.get_neighbors(["SEN", "Mali"])
        """
        target = self.get_country(territory)
        all_countries = self._load_countries()

        # Union of the target territory's geometries
        target_union = target.union_all()

        # Filter the countries that touch the target geometry
        mask = all_countries.geometry.intersects(target_union)
        neighbors = all_countries[mask].copy()

        # Remove the target country/countries itself/themselves (via >95% area intersection)
        target_iso_codes = set()
        if isinstance(territory, str):
            iso3 = self.get_iso3(territory)
            if isinstance(iso3, str):
                target_iso_codes.add(iso3)
        else:
            for t in territory:
                iso3 = self.get_iso3(t)
                if isinstance(iso3, str):
                    target_iso_codes.add(iso3)

        if target_iso_codes:
            neighbors = neighbors[~neighbors['iso3'].isin(target_iso_codes)]

        return neighbors.reset_index(drop=True)

    def get_countries_by_continent(self, continent: str, adm: Union[str, int] = 0,
                                    simplified: bool = True) -> gpd.GeoDataFrame:
        """
        Returns every country of a continent via GeoBoundaries.

        Args:
            continent: Continent name (French or English).
                       Examples: "Africa", "Afrique", "Europe"
            adm: Administrative level (default: 0 = national boundaries).
            simplified: If True, uses simplified geometry.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame of every country in the continent.

        Examples:
            >>> b = Bound()
            >>> afrique = b.get_countries_by_continent("Afrique")
        """
        all_countries = self._load_countries()
        mapping = self._CONTINENT_MAPPING
        continent_name = mapping.get(continent.lower(), continent)

        mask = all_countries['continent'].str.contains(continent_name, case=False, na=False)
        countries_in_continent = all_countries[mask]

        if countries_in_continent.empty:
            available = ', '.join(all_countries['continent'].unique())
            raise ValueError(f"Continent '{continent}' non trouvé. Disponibles : {available}")

        iso_codes_list = countries_in_continent['iso3'].tolist()
        # Filter out invalid codes (-99, etc.)
        iso_codes_list = [c for c in iso_codes_list if len(c) == 3 and c != '-99']

        return self.get_admin(iso_codes_list, adm=adm, simplified=simplified)

    def get_bbox(self, territory: Union[str, List[str]]) -> tuple:
        """
        Returns the bounding box of one or more territories.

        Args:
            territory: Country name, ISO2/ISO3 code, or list of names/codes.

        Returns:
            tuple: (west, south, east, north) in WGS-84.

        Examples:
            >>> b = Bound()
            >>> b.get_bbox("CIV")
            (-8.599..., 4.357..., -2.494..., 10.740...)
        """
        gdf = self.get_country(territory)
        west, south, east, north = gdf.total_bounds
        return (west, south, east, north)

    def get_centroid(self, territory: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Returns the centroid of one or more territories.

        Args:
            territory: Country name, ISO2/ISO3 code, or list of names/codes.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with the centroids (Point) as geometry.

        Examples:
            >>> b = Bound()
            >>> centre = b.get_centroid("CIV")
        """
        gdf = self.get_country(territory)
        centroids = gdf.copy()
        centroids['geometry'] = centroids.geometry.centroid
        return centroids

    def clip(self, gdf: gpd.GeoDataFrame, territory: Union[str, List[str]],
             adm: Union[str, int] = 0) -> gpd.GeoDataFrame:
        """
        Clips a GeoDataFrame to a territory's boundaries.

        Args:
            gdf: GeoDataFrame to clip.
            territory: Country name, ISO code, or list of names/codes.
            adm: Administrative level for the clipping boundaries (default: 0).

        Returns:
            gpd.GeoDataFrame: Clipped GeoDataFrame.

        Examples:
            >>> b = Bound()
            >>> routes_civ = b.clip(routes_gdf, "CIV")
        """
        mask_gdf = self.get_admin(territory, adm=adm, simplified=False)
        return gpd.clip(gdf, mask_gdf)

    def contains(self, territory: str, point: Union[tuple, list]) -> bool:
        """
        Checks whether a point (latitude, longitude) lies within a territory.

        Args:
            territory: Country name or ISO code.
            point: Tuple or list (latitude, longitude).

        Returns:
            bool: True if the point is within the territory.

        Examples:
            >>> b = Bound()
            >>> b.contains("CIV", (6.85, -5.28))
            True
        """
        gdf = self.get_country(territory)
        lat, lon = point
        pt = Point(lon, lat)
        return bool(gdf.union_all().contains(pt))

    def search_country(self, keyword: str) -> List[tuple]:
        """
        Fuzzy search over country names.

        Args:
            keyword: Keyword to search for (case-insensitive).

        Returns:
            List[tuple]: List of matching (country_name, iso3_code) tuples.

        Examples:
            >>> b = Bound()
            >>> b.search_country("ivo")
            [("Côte d'Ivoire", 'CIV')]
        """
        keyword_lower = keyword.lower()
        results = [
            (name, iso)
            for name, iso in countries_iso3.items()
            if keyword_lower in name.lower()
        ]
        return results

    def get_area(self, territory: Union[str, List[str]], unit: str = "km2") -> Union[float, gpd.GeoDataFrame]:
        """
        Returns the area of one or more territories.

        Args:
            territory: Country name, ISO code, or list of names/codes.
            unit: Area unit. "km2" (default), "m2", or "ha".

        Returns:
            float: Area if a single territory.
            gpd.GeoDataFrame: GeoDataFrame with an 'area' column if several territories.

        Raises:
            ValueError: If the unit isn't supported.

        Examples:
            >>> b = Bound()
            >>> b.get_area("CIV")
            322460.0  # approximate
            >>> b.get_area(["SEN", "Mali"])
        """
        divisors = {"m2": 1, "km2": 1e6, "ha": 1e4}
        if unit not in divisors:
            raise ValueError(f"Unité '{unit}' non supportée. Utilisez : {list(divisors.keys())}")

        gdf = self.get_country(territory)
        # Project to Equal Area (Mollweide) for a correct area calculation
        gdf_proj = gdf.to_crs("ESRI:54009")
        gdf['area'] = gdf_proj.geometry.area / divisors[unit]

        if isinstance(territory, str):
            return float(gdf['area'].sum())
        return gdf
