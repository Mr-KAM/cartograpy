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
    Client pour interagir avec l'API GeoBoundaries.
    Permet de récupérer les limites administratives des territoires.
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
        Initialise le client GeoBoundaries.
        
        Args:
            cache_expire_seconds: Durée d'expiration du cache en secondes (défaut: 1 semaine)
        """
        self._session = CachedSession(expire_after=cache_expire_seconds)
        self._base_url = "https://www.geoboundaries.org/api/current/gbOpen"
        self._continents_gdf = None
        self._countries_gdf = None
    
    def clear_cache(self):
        """Vide le cache des requêtes."""
        self._session.cache.clear()
    
    def set_cache_expire_time(self, seconds: int):
        """
        Met à jour le temps d'expiration du cache sans vider le cache existant.
        
        Args:
            seconds: Nouvelle durée d'expiration en secondes
        """
        self._session = CachedSession(expire_after=seconds)
    
    def disable_cache(self):
        """Désactive le cache des requêtes."""
        self._session = CachedSession(expire_after=-1)
    
    def is_valid_adm(self, iso3: str, adm: str) -> bool:
        """
        Vérifie si un niveau ADM est valide pour un pays donné.
        
        Args:
            iso3: Code ISO3 du pays
            adm: Niveau administratif (ex: 'ADM0', 'ADM1', etc.)
            
        Returns:
            bool: True si le niveau ADM est valide
        """
        url = f"{self._base_url}/{iso3}/{adm}/"
        resp = self._session.get(url, verify=True)
        if resp.status_code != 200:
            return False
        try:
            data = resp.json()
            # L'API retourne un dict (ou liste) avec des données si le niveau existe
            if isinstance(data, list):
                return len(data) > 0
            return bool(data and not data.get("error"))
        except (ValueError, AttributeError):
            return False
    
    def _validate_adm(self, adm: Union[str, int]) -> str:
        """
        Valide et normalise un niveau ADM.
        
        Args:
            adm: Niveau administratif (int ou str)
            
        Returns:
            str: Niveau ADM validé et normalisé
            
        Raises:
            KeyError: Si le niveau ADM n'est pas valide
        """
        if isinstance(adm, int) or len(str(adm)) == 1:
            adm = f'ADM{adm}'
        
        valid_adms = [f'ADM{i}' for i in range(6)] + ['ALL']
        if str.upper(adm) in valid_adms:
            return str.upper(adm)
        
        raise KeyError(f"Niveau ADM invalide: {adm}")
    
    def _get_smallest_adm(self, iso3: str) -> str:
        """
        Trouve le plus petit niveau ADM disponible pour un pays.
        
        Args:
            iso3: Code ISO3 du pays
            
        Returns:
            str: Plus petit niveau ADM disponible
        """
        for current_adm in range(5, -1, -1):
            adm_level = f'ADM{current_adm}'
            if self.is_valid_adm(iso3, adm_level):
                logger.info(f'Smallest ADM level found for {iso3} : {adm_level}')
                return adm_level
        
        return 'ADM0'  # Fallback
    
    def _is_valid_iso3_code(self, territory: str) -> bool:
        """
        Vérifie si un code ISO3 est valide.
        
        Args:
            territory: Code ou nom du territoire
            
        Returns:
            bool: True si le code ISO3 est valide
        """
        return str.lower(territory) in iso_codes
    
    def _get_iso3_from_name_or_iso2(self, name: str) -> str:
        """
        Convertit un nom de pays ou code ISO2 en code ISO3.
        
        Args:
            name: Nom du pays ou code ISO2
            
        Returns:
            str: Code ISO3 correspondant
            
        Raises:
            KeyError: Si le pays n'est pas trouvé
        """
        try:
            list_iso3 = self.get_iso3(name)
            if isinstance(list_iso3, str):
                return list_iso3.upper()
            # Si plusieurs pays correspondent, on retourne la liste
            elif isinstance(list_iso3, list) and len(list_iso3) >= 1:
                # Si un seul pays correspond, on retourne son code ISO3
                return list_iso3[0][1].upper()
            else:
                raise KeyError(f"{name} non trouvé")
        
        except KeyError as e:
            logger.info(f"KeyError : Couldn't find country named {e}")
            raise KeyError(f"Pays non trouvé: {name}")
        
    def get_iso3(self, territory: str) -> Union[str, List[tuple], None]:
        """
        Récupère le code ISO3 d'un territoire.
        
        Args:
            territory: Nom du territoire ou code ISO2/ISO3
            
        Returns:
            str: Code ISO3 du territoire
            
        Raises:
            KeyError: Si le territoire n'est pas trouvé
        """
        if self._is_valid_iso3_code(territory):
            return str.upper(territory)
        else:
            list_iso3 = [(countrie_name,iso) for countrie_name, iso in countries_iso3.items() if str.lower(territory) in str.lower(countrie_name)]
            # Si aucun pays ne correspond, on retourne None
            if list_iso3 == []:
                return None
            # Si un seul pays correspond, on retourne son code ISO3
            elif len(list_iso3) == 1:
                return list_iso3[0][1].upper()
            else : # Si plusieurs pays correspondent, avec le même ISO3, on retourne le code ISO3 correspondant
                if len(set([iso for _, iso in list_iso3])) == 1:
                    return list_iso3[0][1].upper()
                else :# Sinon, on retourne la liste des pays correspondants
                    return list_iso3
    
    
    def list_countries(self) -> List[str]:
        """
        Récupère la liste des pays valides.
        
        Returns:
            List[str]: Liste des codes ISO3 des pays
        """
        return list(countries_iso3.keys())
    
    def _generate_url(self, territory: str, adm: Union[str, int]) -> str:
        """
        Génère l'URL de l'API pour un territoire et niveau ADM donnés.
        
        Args:
            territory: Nom du territoire ou code ISO
            adm: Niveau administratif
            
        Returns:
            str: URL de l'API
            
        Raises:
            KeyError: Si le territoire ou niveau ADM n'est pas valide
        """
        iso3 = (str.upper(territory) if self._is_valid_iso3_code(territory) 
                else self._get_iso3_from_name_or_iso2(territory))
        
        if adm != -1:
            adm = self._validate_adm(adm)
        else:
            adm = self._get_smallest_adm(iso3)
        
        if not self.is_valid_adm(iso3, adm):
            error_msg = f"ADM level '{adm}' doesn't exist for country '{territory}' ({iso3})"
            logger.info(f"KeyError : {error_msg}")
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
        Récupère les métadonnées d'un territoire.
        
        Args:
            territory: Nom du territoire ou code ISO
            adm: Niveau administratif (utiliser 'ALL' pour tous les niveaux)
            
        Returns:
            dict: Métadonnées du territoire
        """
        url = self._generate_url(territory, adm)
        return self._session.get(url, verify=True).json()
    
    def _get_data(self, territory: str, adm: Union[str, int], simplified: bool) -> str:
        """
        Récupère les données géographiques d'un territoire.
        
        Args:
            territory: Nom du territoire ou code ISO
            adm: Niveau administratif
            simplified: Si True, utilise la géométrie simplifiée
            
        Returns:
            str: Données GeoJSON sous forme de chaîne
        """
        geom_complexity = 'simplifiedGeometryGeoJSON' if simplified else 'gjDownloadURL'
        
        try:
            json_uri = self.metadata(territory, adm)[geom_complexity]
        except Exception as e:
            error_msg = f"Error while requesting geoboudaries API\n URL : {self._generate_url(territory, adm)}\n"
            logger.info(error_msg)
            raise e
        
        return self._session.get(json_uri).text
    
    def adm(self, territories: Union[str, List[str]], adm: Union[str, int], simplified: bool = True) -> gpd.GeoDataFrame:
        """
        Récupère les limites administratives des territoires spécifiés.
        
        Args:
            territories: Territoire(s) à récupérer. Peut être :
                - Un string unique : "Senegal", "SEN", "เซเนกัล"
                - Une liste de strings : ["SEN", "Mali"], ["セネガル", "մալი"]
            adm: Niveau administratif :
                - 'ADM0' à 'ADM5' (si existant pour le pays)
                - int de 0 à 5
                - int -1 (retourne le plus petit niveau ADM disponible)
            simplified: Si True, utilise la géométrie simplifiée (défaut: True)
            
        Returns:
            gpd.GeoDataFrame: GeoDataFrame des territoires demandés
            
        Note:
            Valeurs autorisées pour territories :
            - ISO 3166-1 (alpha2) : AFG, QAT, YEM, etc.
            - ISO 3166-1 (alpha3) : AF, QA, YE, etc.
            - Nom du pays en plusieurs langues supportées
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
        Retourne un GeoDataFrame des continents du monde.
        
        Parameters:
        -----------
        continents : str, list of str, or None, optional
            - Si str : retourne le GeoDataFrame du continent spécifié
            - Si list : retourne le GeoDataFrame des continents dans la liste
            - Si None : retourne tous les continents
        
        Returns:
        --------
        gpd.GeoDataFrame
            GeoDataFrame contenant les géométries des continents demandés
        
        Raises:
        -------
        ValueError
            Si un continent spécifié n'existe pas dans les données
        """
        
        # Charger et mettre en cache les données naturalearth
        if self._continents_gdf is None:
            naturalearth_url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            world = gpd.read_file(naturalearth_url)
            continent_col = 'CONTINENT' if 'CONTINENT' in world.columns else 'continent'
            continents_gdf = world.dissolve(by=continent_col, as_index=False)
            continents_gdf = continents_gdf[[continent_col, 'geometry']]
            self._continents_gdf = continents_gdf.rename(columns={continent_col: 'continent'})

        # Si aucun continent spécifié, retourner tous les continents
        if continents is None:
            return self._continents_gdf.copy()

        mapping = self._CONTINENT_MAPPING

        # Si un seul continent (string)
        if isinstance(continents, str):
            continent_name = mapping.get(continents.lower(), continents)
            filtered_gdf = self._continents_gdf[self._continents_gdf['continent'].str.contains(continent_name, case=False, na=False)]

            if filtered_gdf.empty:
                available_continents = ', '.join(self._continents_gdf['continent'].unique())
                raise ValueError(f"Continent '{continents}' non trouvé. Continents disponibles: {available_continents}")

            return filtered_gdf

        # Si une liste de continents
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
                logger.info(f"Attention: Continents non trouvés: {', '.join(missing)}")

            return filtered_gdf

        else:
            raise TypeError("Le paramètre 'continents' doit être une chaîne, une liste ou None")

    def list_continents_names(self) -> dict:
        return dict(self._CONTINENT_MAPPING)

class Bound(GeoBoundaries):
    """
    Client étendu pour l'API GeoBoundaries.
    Hérite de GeoBoundaries et ajoute des méthodes utilitaires :
    get_admin, get_country, get_continent, get_world.
    """

    def get_admin(self, territories: Union[str, List[str]], adm: Union[str, int], simplified: bool = True) -> gpd.GeoDataFrame:
        """
        Récupère les limites administratives des territoires spécifiés.
        Délègue à ``adm()`` de la classe parente.

        Args:
            territories: Territoire(s) à récupérer. Peut être :
                - Un string unique : "Senegal", "SEN", "เซเนกัล"
                - Une liste de strings : ["SEN", "Mali"], ["セネガル", "մալి"]
            adm: Niveau administratif :
                - 'ADM0' à 'ADM5' (si existant pour le pays)
                - int de 0 à 5
                - int -1 (retourne le plus petit niveau ADM disponible)
            simplified: Si True, utilise la géométrie simplifiée (défaut: True)

        Returns:
            gpd.GeoDataFrame: GeoDataFrame des territoires
        """
        return self.adm(territories, adm, simplified)

    def get_country(self, name: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Récupère les frontières (ADM0) d'un ou plusieurs pays.

        Args:
            name: Nom du pays, code ISO2/ISO3, ou une liste de noms/codes.
                  Exemples : "France", "FRA", ["France", "SEN", "Mali"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame contenant la/les géométrie(s) du/des pays (niveau ADM0).

        Raises:
            KeyError: Si un pays n'est pas trouvé.

        Exemples:
            >>> b = Bound()
            >>> france = b.get_country("France")
            >>> pays = b.get_country(["France", "SEN", "Mali"])
        """
        return self.get_admin(name, adm=0, simplified=True)

    def get_continent(self, name: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Récupère la géométrie d'un ou plusieurs continents à partir de leur nom.

        Args:
            name: Nom du continent ou liste de noms (français ou anglais).
                  Exemples : "Africa", "Afrique", ["Europe", "Afrique"], ["Asia", "Amérique du Sud"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame contenant la/les géométrie(s) du/des continent(s).

        Raises:
            ValueError: Si un continent n'est pas trouvé.

        Exemples:
            >>> b = Bound()
            >>> afrique = b.get_continent("Afrique")
            >>> europe = b.get_continent("Europe")
            >>> plusieurs = b.get_continent(["Afrique", "Europe", "Asia"])
        """
        return self.continents(name)

    def get_world(self, level: str = "continent") -> gpd.GeoDataFrame:
        """
        Retourne un GeoDataFrame du monde entier, agrégé par continent ou par pays.

        Args:
            level: Niveau d'agrégation. Valeurs possibles :
                - "continent" : retourne les géométries de tous les continents (par défaut)
                - "country" : retourne les géométries de tous les pays

        Returns:
            gpd.GeoDataFrame: GeoDataFrame contenant les géométries du monde.

        Raises:
            ValueError: Si le niveau spécifié n'est pas "continent" ou "country".

        Exemples:
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
        """Charge et met en cache les pays Natural Earth."""
        if self._countries_gdf is None:
            naturalearth_url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            world = gpd.read_file(naturalearth_url)
            self._countries_gdf = world[['NAME', 'ISO_A3', 'CONTINENT', 'geometry']].rename(
                columns={'NAME': 'name', 'ISO_A3': 'iso3', 'CONTINENT': 'continent'}
            )
        return self._countries_gdf.copy()

    def get_neighbors(self, territory: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Retourne les pays voisins (adjacents) d'un ou plusieurs territoires.

        Args:
            territory: Nom du pays, code ISO2/ISO3, ou liste de noms/codes.
                       Exemples : "France", "CIV", ["SEN", "Mali"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame des pays voisins (sans le pays lui-même).

        Exemples:
            >>> b = Bound()
            >>> voisins = b.get_neighbors("CIV")
            >>> voisins = b.get_neighbors(["SEN", "Mali"])
        """
        target = self.get_country(territory)
        all_countries = self._load_countries()

        # Union des géométries du territoire cible
        target_union = target.union_all()

        # Filtrer les pays qui touchent la géométrie cible
        mask = all_countries.geometry.intersects(target_union)
        neighbors = all_countries[mask].copy()

        # Retirer le(s) pays cible(s) eux-mêmes (par intersection > 95% de la surface)
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
        Retourne tous les pays d'un continent via GeoBoundaries.

        Args:
            continent: Nom du continent (français ou anglais).
                       Exemples : "Africa", "Afrique", "Europe"
            adm: Niveau administratif (défaut: 0 = frontières nationales).
            simplified: Si True, utilise la géométrie simplifiée.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame de tous les pays du continent.

        Exemples:
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
        # Filtrer les codes invalides (-99, etc.)
        iso_codes_list = [c for c in iso_codes_list if len(c) == 3 and c != '-99']

        return self.get_admin(iso_codes_list, adm=adm, simplified=simplified)

    def get_bbox(self, territory: Union[str, List[str]]) -> tuple:
        """
        Retourne la bounding box d'un ou plusieurs territoires.

        Args:
            territory: Nom du pays, code ISO2/ISO3, ou liste de noms/codes.

        Returns:
            tuple: (west, south, east, north) en WGS-84.

        Exemples:
            >>> b = Bound()
            >>> b.get_bbox("CIV")
            (-8.599..., 4.357..., -2.494..., 10.740...)
        """
        gdf = self.get_country(territory)
        west, south, east, north = gdf.total_bounds
        return (west, south, east, north)

    def get_centroid(self, territory: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Retourne le centroïde d'un ou plusieurs territoires.

        Args:
            territory: Nom du pays, code ISO2/ISO3, ou liste de noms/codes.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame avec les centroïdes (Point) comme géométrie.

        Exemples:
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
        Découpe un GeoDataFrame selon les frontières d'un territoire.

        Args:
            gdf: GeoDataFrame à découper.
            territory: Nom du pays, code ISO, ou liste de noms/codes.
            adm: Niveau administratif pour les frontières de découpe (défaut: 0).

        Returns:
            gpd.GeoDataFrame: GeoDataFrame découpé.

        Exemples:
            >>> b = Bound()
            >>> routes_civ = b.clip(routes_gdf, "CIV")
        """
        mask_gdf = self.get_admin(territory, adm=adm, simplified=False)
        return gpd.clip(gdf, mask_gdf)

    def contains(self, territory: str, point: Union[tuple, list]) -> bool:
        """
        Vérifie si un point (latitude, longitude) est à l'intérieur d'un territoire.

        Args:
            territory: Nom du pays ou code ISO.
            point: Tuple ou liste (latitude, longitude).

        Returns:
            bool: True si le point est dans le territoire.

        Exemples:
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
        Recherche floue dans les noms de pays.

        Args:
            keyword: Mot-clé à rechercher (insensible à la casse).

        Returns:
            List[tuple]: Liste de tuples (nom_pays, code_iso3) correspondants.

        Exemples:
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
        if not results:
            logger.info(f"Aucun pays trouvé pour '{keyword}'.")
        return results

    def get_area(self, territory: Union[str, List[str]], unit: str = "km2") -> Union[float, gpd.GeoDataFrame]:
        """
        Retourne la superficie d'un ou plusieurs territoires.

        Args:
            territory: Nom du pays, code ISO, ou liste de noms/codes.
            unit: Unité de surface. "km2" (défaut), "m2", ou "ha".

        Returns:
            float: Superficie si un seul territoire.
            gpd.GeoDataFrame: GeoDataFrame avec colonne 'area' si plusieurs territoires.

        Raises:
            ValueError: Si l'unité n'est pas supportée.

        Exemples:
            >>> b = Bound()
            >>> b.get_area("CIV")
            322460.0  # approximatif
            >>> b.get_area(["SEN", "Mali"])
        """
        divisors = {"m2": 1, "km2": 1e6, "ha": 1e4}
        if unit not in divisors:
            raise ValueError(f"Unité '{unit}' non supportée. Utilisez : {list(divisors.keys())}")

        gdf = self.get_country(territory)
        # Projeter en Equal Area (Mollweide) pour un calcul de surface correct
        gdf_proj = gdf.to_crs("ESRI:54009")
        gdf['area'] = gdf_proj.geometry.area / divisors[unit]

        if isinstance(territory, str):
            return float(gdf['area'].sum())
        return gdf
