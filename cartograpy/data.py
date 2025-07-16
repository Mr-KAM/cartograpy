"""
Runfola, Daniel, Community Contributors, and [v4.0: Lindsey Rogers, Joshua Habib, Sidonie Horn, Sean Murphy, Dorian Miller, Hadley Day, Lydia Troup, Dominic Fornatora, Natalie Spage, Kristina Pupkiewicz, Michael Roth, Carolina Rivera, Charlie Altman, Isabel Schruer, Tara McLaughlin, Russ Biddle, Renee Ritchey, Emily Topness, James Turner, Sam Updike, Helena Buckman, Neel Simpson, Jason Lin], [v2.0: Austin Anderson, Heather Baier, Matt Crittenden, Elizabeth Dowker, Sydney Fuhrig, Seth Goodman, Grace Grimsley, Rachel Layko, Graham Melville, Maddy Mulder, Rachel Oberman, Joshua Panganiban, Andrew Peck, Leigh Seitz, Sylvia Shea, Hannah Slevin, Rebecca Yougerman, Lauren Hobbs]. "geoBoundaries: A global database of political administrative boundaries." Plos one 15, no. 4 (2020): e0231866.
"""
import pandas as pd
import geopandas as gpd

from typing import List, Union
import geojson
import requests
import cartograpy.countries_iso3 as countries_iso3
import cartograpy.iso3_codes as iso3_codes
from requests_cache import CachedSession

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from shapely.geometry import Point # Nécessaire pour créer des objets Point
import time

import wbdata


class GeoBoundaries:
    """
    Client pour interagir avec l'API GeoBoundaries.
    Permet de récupérer les limites administratives des territoires.
    """
    
    def __init__(self, cache_expire_seconds: int = 604800):
        """
        Initialise le client GeoBoundaries.
        
        Args:
            cache_expire_seconds: Durée d'expiration du cache en secondes (défaut: 1 semaine)
        """
        self._session = CachedSession(expire_after=cache_expire_seconds)
        self._base_url = "https://www.geoboundaries.org/api/current/gbOpen"
    
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
        self._session = requests
    
    def is_valid_adm(self, iso3: str, adm: str) -> bool:
        """
        Vérifie si un niveau ADM est valide pour un pays donné.
        
        Args:
            iso3: Code ISO3 du pays
            adm: Niveau administratif (ex: 'ADM0', 'ADM1', etc.)
            
        Returns:
            bool: True si le niveau ADM est valide
        """
        url = f"{self._base_url}/{iso3}/"
        html = self._session.get(url, verify=True).text
        return adm in html
    
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
                print(f'Smallest ADM level found for {iso3} : {adm_level}')
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
        return str.lower(territory) in iso3_codes.iso_codes
    
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
            print(f"KeyError : Couldn't find country named {e}")
            raise KeyError(f"Pays non trouvé: {name}")
        
    def get_iso3(self, territory: str):
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
    
    
    def countries(self) -> List[str]:
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
            print(f"KeyError : {error_msg}")
            raise KeyError(error_msg)
        
        return f"{self._base_url}/{iso3}/{adm}/"
    
    def adminLevels(self):
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
    
    def _get_data(self, territory: str, adm: str, simplified: bool) -> str:
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
            print(error_msg)
            raise e
        
        return self._session.get(json_uri).text
    
    def adm(self, territories: Union[str, List[str]], adm: Union[str, int], simplified: bool = True) -> dict:
        """
        Récupère les limites administratives des territoires spécifiés.
        
        Args:
            territories: Territoire(s) à récupérer. Peut être :
                - Un string unique : "Senegal", "SEN", "เซเนกัล"
                - Une liste de strings : ["SEN", "Mali"], ["セネガル", "մալի"]
            adm: Niveau administratif :
                - 'ADM0' à 'ADM5' (si existant pour le pays)
                - int de 0 à 5
                - int -1 (retourne le plus petit niveau ADM disponible)
            simplified: Si True, utilise la géométrie simplifiée (défaut: True)
            
        Returns:
            dict: Données GeoJSON des territoires
            
        Note:
            Valeurs autorisées pour territories :
            - ISO 3166-1 (alpha2) : AFG, QAT, YEM, etc.
            - ISO 3166-1 (alpha3) : AF, QA, YE, etc.
            - Nom du pays en plusieurs langues supportées
        """
        if isinstance(territories, str):
            geo_df=gpd.GeoDataFrame.from_features(geojson.loads(self._get_data(territories, adm, simplified)))
            return geo_df
        
        # Traitement pour une liste de territoires
        geojsons_dic = {}
        for territory in territories:
            data = gpd.GeoDataFrame.from_features(geojson.loads(self._get_data(territory, adm, simplified)))
            geojsons_dic[territory]=data

        return geojsons_dic





class Geocoder:
    """
    Un objet Python pour géocoder une ou plusieurs localités en utilisant geopy
    et renvoyer les résultats dans une GeoDataFrame.

    Attributes:
        geolocator (Nominatim): L'instance du géocodeur Nominatim.
        user_agent (str): L'agent utilisateur pour les requêtes Nominatim.
        delay (float): Délai en secondes entre les requêtes pour éviter de surcharger l'API.
    """

    def __init__(self, user_agent="mon_geocoder_geopandas", delay=1.0):
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
            location = self.geolocator.geocode(location_str)
            if location:
                return {
                    'query': location_str,
                    'address': location.address,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'altitude': location.altitude,
                    'raw': location.raw # Données brutes de l'API
                }, None
            else:
                return None, location_str
        except GeocoderTimedOut:
            print(f"Avertissement : Délai d'attente dépassé pour '{location_str}'.")
            return None, location_str
        except GeocoderServiceError as e:
            print(f"Erreur du service de géocodage pour '{location_str}': {e}")
            return None, location_str
        except Exception as e:
            print(f"Une erreur inattendue est survenue lors du géocodage de '{location_str}': {e}")
            return None, location_str

    def geocode(self, localities):
        """
        Géocode une ou plusieurs localités et renvoie une GeoDataFrame.

        Args:
            localities (str or list): Une seule chaîne de caractères représentant une localité,
                                      ou une liste de chaînes de caractères de localités.

        Returns:
            tuple: Un tuple contenant :
                   - geopandas.GeoDataFrame: Une GeoDataFrame avec les informations des localités trouvées
                                            et une colonne 'geometry' contenant des objets Point.
                   - list: Une liste de chaînes de caractères des localités non trouvées.
        """
        if isinstance(localities, str):
            localities = [localities]

        found_locations_data = []
        not_found_localities = []

        print(f"Début du géocodage de {len(localities)} localité(s)...")

        for locality in localities:
            location_info, not_found_locality = self._geocode_single(locality)
            if location_info:
                found_locations_data.append(location_info)
            else:
                not_found_localities.append(not_found_locality)
            
        print("Géocodage terminé.")

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

        return geodataframe, not_found_localities


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
            location = self.geolocator.reverse(query_str)
            if location:
                return {
                    'query': query_str,
                    'address': location.address,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'altitude': location.altitude,
                    'raw': location.raw # Données brutes de l'API
                }, None
            else:
                return None, coordinates_tuple
        except GeocoderTimedOut:
            print(f"Avertissement : Délai d'attente dépassé pour les coordonnées '{query_str}'.")
            return None, coordinates_tuple
        except GeocoderServiceError as e:
            print(f"Erreur du service de géocodage inverse pour les coordonnées '{query_str}': {e}")
            return None, coordinates_tuple
        except Exception as e:
            print(f"Une erreur inattendue est survenue lors du géocodage inverse de '{query_str}': {e}")
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

        print(f"Début du géocodage inverse (coordonnées -> adresse) de {len(coordinates)} point(s)...")

        for coord_tuple in coordinates:
            location_info, not_found_coord = self._reverse_geocode_single(coord_tuple)
            if location_info:
                found_locations_data.append(location_info)
            else:
                not_found_coordinates.append(not_found_coord)
            
        print("Géocodage inverse (coordonnées -> adresse) terminé.")

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

class WorldBankData:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def get_sources(self):
        # Renvoie une liste de sources de données disponibles sur le site de la Banque mondiale.
        return wbdata.get_sources()
    
    def get_indicators(self,source=1,query=None):
        return wbdata.get_indicators(source=source)
    
    def get_countries(self,query):
        return wbdata.get_countries(query= query)
    
    def get_data(indicators,country,date):
        return wbdata.get_data(indicators=indicators,country=country,date=date)

# Exemple d'utilisation
if __name__ == "__main__":
    # Créer une instance du client
    client = GeoBoundaries()
    
    # Exemple 1: Récupérer les limites d'un pays
    senegal_data = client.adm("Senegal", "ADM0")
    print("Données du Sénégal récupérées")
    
    # Exemple 2: Récupérer les métadonnées
    metadata = client.metadata("France", "ADM1")
    print(f"Métadonnées France: {metadata.keys()}")
    
    # Exemple 3: Récupérer plusieurs pays
    countries_data = client.adm(["SEN", "MLI"], "ADM0")
    print(f"Nombre de pays récupérés: {len(countries_data['features'])}")

    # Exemple 4: Géocodage d'une adresse
        # Exemple avec Nominatim (gratuit)
    geocoder = Geocoder()
    
    # Géocodage simple
    result = geocoder.geocode("Paris, France")
    print(f"Paris: {result.coordinates}")
