# Packages pour les données vectorelles
import pandas as pd
import geopandas as gpd
import geojson
from typing import *

# Packages pour les boundaries
from cartograpy.iso_code import *
from requests_cache import CachedSession
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from shapely.geometry import *

# Packages pour les données hydrographiques
import time
import requests
import zipfile
import io
import os
from pathlib import Path

# Packages pour les données de la worldbank
import wbdata

# Package pour les données de OSM 
import osmnx as ox

# Packages pour la lecture des données Rasters
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
import tempfile
from urllib.parse import urlencode
import warnings
import datetime



# import os
# import time
# import requests
import math
from typing import Optional, Tuple
from pathlib import Path
from tqdm import tqdm

def load(filepath):
    """
    Charge un fichier vectoriel ou raster selon son extension.

    Paramètres :
        filepath : str
            Chemin complet vers le fichier à charger. L'extension détermine le type de données.

    Retourne :
        - geopandas.GeoDataFrame : Pour les fichiers vectoriels (.shp, .geojson, .gpkg, .kml, .gpx)
        - pandas.DataFrame : Pour les fichiers tabulaires (.csv, .parquet)
        - rasterio.io.DatasetReader : Pour les fichiers raster (.tif, .tiff)

    Formats supportés :
        Vectoriels : shp, geojson, gpkg, kml, gpx, csv, parquet
        Rasters : tif, tiff

    Exemples :
        >>> # Charger un fichier shapefile
        >>> gdf = load("data/ma_carte.shp")
        
        >>> # Charger un fichier GeoJSON
        >>> gdf = load("data/ma_carte.geojson")
        
        >>> # Charger un fichier raster
        >>> raster = load("data/elevation.tif")

    Raises :
        ValueError : Si le format de fichier n'est pas supporté
        RuntimeError : Si une erreur survient lors de la lecture du fichier
    """
    ext = filepath.split('.')[-1].lower()

    # Vector formats
    vector_exts = ['shp', 'geojson', 'gpkg', 'kml', 'gpx', 'csv', 'parquet']
    raster_exts = ['tif', 'tiff']

    if ext in vector_exts:
        if ext in ['shp', 'geojson', 'gpkg']:
            return gpd.read_file(filepath)
        elif ext == 'kml':
            try:
                return gpd.read_file(filepath, driver="LIBKML")
            except Exception as e:
                raise RuntimeError(f"Erreur lors de la lecture KML : {e}")
        elif ext == 'gpx':
            try:
                return gpd.read_file(filepath, layer="tracks")
            except Exception as e:
                raise RuntimeError(f"Erreur lors de la lecture GPX : {e}")
        elif ext == 'csv':
            return pd.read_csv(filepath)
        elif ext == 'parquet':
            return pd.read_parquet(filepath)
    elif ext in raster_exts:
        try:
            return rasterio.open(filepath)
        except Exception as e:
            raise RuntimeError(f"Erreur lors de la lecture raster : {e}")
    else:
        raise ValueError(f"Format '{ext}' non supporté pour le chargement.")


def save(data, file_extension, filename="output", timestamp=False, raster_meta=None):
    """
    Sauvegarde un fichier raster ou vectoriel selon le type.

    Paramètres :
        data : Données à sauvegarder.
            - Pour les données vectorielles : GeoDataFrame ou DataFrame pandas.
            - Pour les données raster : DatasetReader rasterio ou tableau numpy.
        file_extension : str
            Extension du fichier de sortie (ex: 'geojson', 'shp', 'tif').
        filename : str, optionnel
            Nom de base du fichier (sans extension). Par défaut "output".
        timestamp : bool, optionnel
            Si True, ajoute un horodatage au nom du fichier. Par défaut False.
        raster_meta : dict, optionnel
            Métadonnées raster nécessaires si `data` est un tableau numpy.
            Doit contenir au minimum : crs, transform, width, height, dtype, count.

    Retour :
        str : Chemin complet vers le fichier sauvegardé.

    Exemples :
        >>> # Sauvegarder un GeoDataFrame en GeoJSON
        >>> gdf = gpd.GeoDataFrame(...)
        >>> save(gdf, 'geojson', 'ma_carte')

        >>> # Sauvegarder un tableau numpy en TIFF avec métadonnées
        >>> import rasterio
        >>> meta = {'crs': 'EPSG:4326', 'transform': affine_transform, ...}
        >>> save(array, 'tif', 'mon_raster', raster_meta=meta)
    """
    file_extension = file_extension.lower()
    if timestamp:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{now}"
    output_path = f"{filename}.{file_extension}"

    # VECTOR
    if isinstance(data, (gpd.GeoDataFrame, pd.DataFrame)):
        if file_extension == 'geojson':
            data.to_file(output_path, driver='GeoJSON')
        elif file_extension == 'shp':
            data.to_file(output_path, driver='ESRI Shapefile')
        elif file_extension == 'gpkg':
            data.to_file(output_path, driver='GPKG')
        elif file_extension == 'kml':
            try:
                data.to_file(output_path, driver='KML')
            except Exception as e:
                print(f"❌ Impossible d'écrire un fichier KML ici : {e}")
        elif file_extension == 'csv':
            if isinstance(data, gpd.GeoDataFrame):
                data = data.drop(columns='geometry', errors='ignore')
            data.to_csv(output_path, index=False)
        elif file_extension == 'parquet':
            if isinstance(data, gpd.GeoDataFrame):
                data = data.drop(columns='geometry', errors='ignore')
            data.to_parquet(output_path, index=False)
        elif file_extension == 'xlsx':
            if isinstance(data, gpd.GeoDataFrame):
                data = data.drop(columns='geometry', errors='ignore')
            data.to_excel(output_path, index=False)
        elif file_extension == 'feather':
            if isinstance(data, gpd.GeoDataFrame):
                data = data.drop(columns='geometry', errors='ignore')
            data.to_feather(output_path)

    # RASTER
    elif isinstance(data, rasterio.io.DatasetReader):
        with rasterio.open(output_path, 'w', **data.meta) as dst:
            dst.write(data.read())
    elif isinstance(data, np.ndarray):
        if raster_meta is None:
            raise ValueError("raster_meta est requis pour enregistrer un tableau numpy raster.")
        with rasterio.open(output_path, 'w', **raster_meta) as dst:
            dst.write(data)

    else:
        raise TypeError("Type de données non pris en charge pour la sauvegarde.")

    print(f"✅ Fichier sauvegardé : {os.path.abspath(output_path)}")
    return output_path


def list_geofiles(folder_path):
    """
    Liste tous les fichiers géospatiaux (vecteurs et rasters) dans un dossier.
    """
    geospatial_extensions = ['.shp', '.geojson', '.gpkg', '.kml', '.csv', '.parquet', '.gpx', '.tif', '.tiff']

    files = []
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in geospatial_extensions):
                files.append(os.path.join(root, filename))
    return files



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
        
        try:
            # Charger les données des pays du monde depuis naturalearth (URL directe)
            naturalearth_url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            world = gpd.read_file(naturalearth_url)
            
            # Mapping des continents pour normaliser les noms
            continent_mapping = {
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
            
            # Créer un GeoDataFrame des continents en dissolvant les géométries par continent
            # Le nom de la colonne peut varier selon la version des données
            continent_col = 'CONTINENT' if 'CONTINENT' in world.columns else 'continent'
            
            continents_gdf = world.dissolve(by=continent_col, as_index=False)
            continents_gdf = continents_gdf[[continent_col, 'geometry']]
            continents_gdf = continents_gdf.rename(columns={continent_col: 'continent'})
            
            # Si aucun continent spécifié, retourner tous les continents
            if continents is None:
                return continents_gdf
            
            # Si un seul continent (string)
            if isinstance(continents, str):
                continent_name = continent_mapping.get(continents.lower(), continents)
                filtered_gdf = continents_gdf[continents_gdf['continent'].str.contains(continent_name, case=False, na=False)]
                
                if filtered_gdf.empty:
                    available_continents = ', '.join(continents_gdf['continent'].unique())
                    raise ValueError(f"Continent '{continents}' non trouvé. Continents disponibles: {available_continents}")
                
                return filtered_gdf
            
            # Si une liste de continents
            elif isinstance(continents, list):
                # Normaliser les noms des continents
                normalized_continents = []
                for cont in continents:
                    normalized_name = continent_mapping.get(cont.lower(), cont)
                    normalized_continents.append(normalized_name)
                
                # Filtrer le GeoDataFrame
                mask = continents_gdf['continent'].str.lower().isin([c.lower() for c in normalized_continents])
                filtered_gdf = continents_gdf[mask]
                
                if filtered_gdf.empty:
                    available_continents = ', '.join(continents_gdf['continent'].unique())
                    raise ValueError(f"Aucun continent trouvé dans la liste. Continents disponibles: {available_continents}")
                
                # Vérifier si tous les continents demandés ont été trouvés
                found_continents = filtered_gdf['continent'].str.lower().tolist()
                missing = [c for c in continents if continent_mapping.get(c.lower(), c).lower() not in found_continents]
                
                if missing:
                    print(f"Attention: Continents non trouvés: {', '.join(missing)}")
                
                return filtered_gdf
            
            else:
                raise TypeError("Le paramètre 'continents' doit être une chaîne, une liste ou None")
        
        except Exception as e:
            print(f"Erreur lors du chargement des données: {e}")
            raise

    def list_continents_names(self):
        return {
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

class WorldBank:
    def __init__(self):
        self.api_key = "_si_necessite_se_presente"
    
    def get_sources(self):
        # Renvoie une liste de sources de données disponibles sur le site de la Banque mondiale.
        return wbdata.get_sources()
    
    def get_indicators(self,source=1,query=None):
        return wbdata.get_indicators(source=source)
    
    def get_countries(self,query):
        return wbdata.get_countries(query= query)
    
    def get_data(self,indicators,country='all',**kwrargs):
        return wbdata.get_dataframe(indicators,country,**kwrargs)


class OSM :
    def __init__(self):
        self.api_key = "api_key_si_necessaire"
    
    def get_data(self,place, tags, data_type="points"):
        """
        Récupère des données OpenStreetMap pour un lieu donné (str, bbox ou GeoDataFrame)
        et des tags OSM personnalisés.
        
        Args:
            place (str, tuple, list, GeoDataFrame): Nom de la zone, bbox (minx, miny, maxx, maxy), ou GeoDataFrame polygonal.
            tags (dict): Dictionnaire des tags OSM à filtrer, ex: {"amenity": "school"}.
            data_type (str): 'points' pour POIs, 'polygons' pour surfaces, 'lines' pour lignes, 'all' pour tous types.
            
        Returns:
            geopandas.GeoDataFrame : Les objets OSM correspondant à la requête.
        """
        
        def filter_by_geometry_type(gdf, data_type):
            """Filtre le GeoDataFrame selon le type de géométrie souhaité."""
            if data_type == "points":
                return gdf[gdf.geometry.type.isin(['Point', 'MultiPoint'])]
            elif data_type == "polygons":
                return gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            elif data_type == "lines":
                return gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            elif data_type == "all":
                return gdf  # Retourne tous les types de géométries
            else:
                raise ValueError("data_type doit être 'points', 'polygons', 'lines' ou 'all'.")
        
        def handle_osm_request(request_func, *args, **kwargs):
            """Gère les requêtes OSM avec gestion d'erreurs."""
            try:
                gdf = request_func(*args, **kwargs)
                if gdf.empty:
                    print(f"Aucune donnée trouvée avec les tags {tags}")
                    return gpd.GeoDataFrame()
                return filter_by_geometry_type(gdf, data_type)
            except Exception as e:
                print(f"Erreur lors de la récupération des données : {e}")
                return gpd.GeoDataFrame()
        
        # Cas 1 : Nom de lieu (str)
        if isinstance(place, str):
            return handle_osm_request(ox.features_from_place, place, tags)
        
        # Cas 2 : Bounding box (tuple/list de 4 valeurs)
        elif isinstance(place, (tuple, list)) and len(place) == 4:
            minx, miny, maxx, maxy = place
            # bbox = (maxy, minx, miny, maxx)
            # OSMnx attend : north, south, east, west
            return handle_osm_request(ox.features_from_bbox, place, tags)
        
        # Cas 3 : GeoDataFrame (on prend l'enveloppe extérieure)
        elif isinstance(place, gpd.GeoDataFrame):
            try:
                # Utilise unary_union pour garder la forme exacte (sans convex_hull)
                polygon = place.union_all()
                return handle_osm_request(ox.features_from_polygon, polygon, tags)
            except Exception as e:
                print(f"Erreur lors du traitement du GeoDataFrame : {e}")
                return gpd.GeoDataFrame()
        
        else:
            raise ValueError(
                "L'argument 'place' doit être un nom de lieu (str), "
                "une bbox (tuple/list de 4 valeurs) ou un GeoDataFrame."
            )
    
    def list_tags(self,category=None, show_examples=False):
        """
        Retourne une liste de tags OSM courants, ou ceux d'une catégorie donnée.
        
        Args:
            category (str): Catégorie de tags OSM ('building', 'highway', 'amenity', 'water', 
                        'landuse', 'natural', 'leisure', 'shop', 'tourism', 'transport', 'barrier')
                        Si None, retourne toutes les catégories.
            show_examples (bool): Si True, inclut des exemples d'utilisation pour chaque catégorie.
            
        Returns:
            dict ou list: Dictionnaire de catégories avec leurs tags, ou liste des tags de la catégorie demandée.
        """
        
        # Tags organisés par catégorie avec valeurs courantes
        tags = {
            "building": {
                "description": "Bâtiments et structures",
                "tags": {
                    "building": ["yes", "house", "apartment", "commercial", "industrial", "school", "hospital", "church"],
                    "building:levels": "Nombre d'étages (valeur numérique)",
                    "building:use": ["residential", "commercial", "industrial", "retail", "office"],
                    "building:material": ["brick", "concrete", "wood", "stone", "glass"]
                },
                "example": {"building": "house", "building:levels": "2"}
            },
            
            "highway": {
                "description": "Routes, chemins et voies de circulation",
                "tags": {
                    "highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "footway", "cycleway"],
                    "lanes": "Nombre de voies (valeur numérique)",
                    "surface": ["asphalt", "concrete", "paved", "unpaved", "gravel", "dirt"],
                    "maxspeed": "Vitesse maximale (ex: 50, 90, 130)",
                    "oneway": ["yes", "no", "-1"]
                },
                "example": {"highway": "primary", "lanes": "2", "maxspeed": "50"}
            },
            
            "amenity": {
                "description": "Services publics et commodités",
                "tags": {
                    "amenity": ["school", "hospital", "bank", "cafe", "restaurant", "police", "post_office", 
                            "pharmacy", "fuel", "parking", "library", "fire_station", "place_of_worship"]
                },
                "example": {"amenity": "restaurant", "cuisine": "french"}
            },
            
            "water": {
                "description": "Cours d'eau et éléments hydrauliques",
                "tags": {
                    "waterway": ["river", "stream", "canal", "drain", "ditch"],
                    "natural": ["water", "bay", "coastline"],
                    "water": ["lake", "pond", "reservoir", "river"],
                    "dam": ["yes", "weir"]
                },
                "example": {"waterway": "river", "name": "Seine"}
            },
            
            "landuse": {
                "description": "Utilisation du sol et zonage",
                "tags": {
                    "landuse": ["residential", "commercial", "industrial", "forest", "farmland", 
                            "meadow", "cemetery", "military", "recreation_ground"],
                    "natural": ["forest", "grassland", "scrub", "heath"]
                },
                "example": {"landuse": "residential", "residential": "urban"}
            },
            
            "natural": {
                "description": "Éléments naturels",
                "tags": {
                    "natural": ["tree", "peak", "water", "wood", "beach", "cliff", "hill", "valley", "cave"],
                    "tree": ["deciduous", "coniferous", "palm"],
                    "leaf_type": ["broadleaved", "needleleaved"],
                    "ele": "Altitude en mètres (valeur numérique)"
                },
                "example": {"natural": "peak", "name": "Mont Blanc", "ele": "4809"}
            },
            
            "leisure": {
                "description": "Loisirs et activités récréatives",
                "tags": {
                    "leisure": ["park", "pitch", "stadium", "swimming_pool", "playground", "golf_course", 
                            "sports_centre", "garden", "marina", "beach_resort"]
                },
                "example": {"leisure": "park", "name": "Central Park"}
            },
            
            "shop": {
                "description": "Commerces et magasins",
                "tags": {
                    "shop": ["supermarket", "bakery", "butcher", "clothes", "shoes", "books", "pharmacy", 
                            "electronics", "furniture", "car", "bicycle", "hairdresser"]
                },
                "example": {"shop": "bakery", "name": "La Boulangerie"}
            },
            
            "tourism": {
                "description": "Sites touristiques et hébergements",
                "tags": {
                    "tourism": ["hotel", "museum", "attraction", "viewpoint", "information", "camp_site", 
                            "guest_house", "hostel", "monument", "artwork"],
                    "historic": ["castle", "monument", "memorial", "archaeological_site"]
                },
                "example": {"tourism": "museum", "name": "Louvre"}
            },
            
            "transport": {
                "description": "Transport public et infrastructure",
                "tags": {
                    "railway": ["rail", "subway", "tram", "light_rail", "station", "platform"],
                    "public_transport": ["platform", "station", "stop_position"],
                    "aeroway": ["runway", "taxiway", "terminal", "gate"],
                    "route": ["bus", "tram", "subway", "train"]
                },
                "example": {"railway": "station", "name": "Gare du Nord"}
            },
            
            "barrier": {
                "description": "Barrières et obstacles",
                "tags": {
                    "barrier": ["fence", "wall", "hedge", "gate", "bollard", "kerb"],
                    "access": ["yes", "no", "private", "permissive"]
                },
                "example": {"barrier": "fence", "material": "wood"}
            }
        }
        
        def format_category_info(cat_name, cat_data):
            """Formate les informations d'une catégorie."""
            if show_examples:
                return {
                    "description": cat_data["description"],
                    "tags": cat_data["tags"],
                    "example": cat_data.get("example", {})
                }
            else:
                return list(cat_data["tags"].keys())
        
        if category is None:
            if show_examples:
                return {cat: format_category_info(cat, data) for cat, data in tags.items()}
            else:
                return {cat: list(data["tags"].keys()) for cat, data in tags.items()}
        else:
            category = category.lower()
            if category in tags:
                return format_category_info(category, tags[category])
            else:
                available_categories = list(tags.keys())
                raise ValueError(f"Catégorie '{category}' non trouvée. Catégories disponibles : {available_categories}")


    def search_tags(self,keyword):
        """
        Recherche des tags OSM contenant un mot-clé.
        
        Args:
            keyword (str): Mot-clé à rechercher dans les tags
            
        Returns:
            dict: Dictionnaire avec les catégories et tags correspondants
        """
        all_tags = self.list_tags(show_examples=True)
        results = {}
        
        keyword = keyword.lower()
        
        for category, data in all_tags.items():
            matching_tags = {}
            
            # Recherche dans les tags
            for tag_key, tag_values in data["tags"].items():
                if keyword in tag_key.lower():
                    matching_tags[tag_key] = tag_values
                elif isinstance(tag_values, list):
                    matching_values = [v for v in tag_values if keyword in v.lower()]
                    if matching_values:
                        matching_tags[tag_key] = matching_values
                elif isinstance(tag_values, str) and keyword in tag_values.lower():
                    matching_tags[tag_key] = tag_values
            
            if matching_tags:
                results[category] = {
                    "description": data["description"],
                    "matching_tags": matching_tags,
                    "example": data.get("example", {})
                }
        
        return results


    def get_common_tag_combinations(self):
        """
        Retourne des combinaisons de tags couramment utilisées ensemble.
        
        Returns:
            dict: Dictionnaire avec des exemples de requêtes courantes
        """
        return {
            "restaurants": {"amenity": "restaurant"},
            "schools": {"amenity": "school"},
            "hospitals": {"amenity": "hospital"},
            "parks": {"leisure": "park"},
            "supermarkets": {"shop": "supermarket"},
            "hotels": {"tourism": "hotel"},
            "gas_stations": {"amenity": "fuel"},
            "pharmacies": {"amenity": "pharmacy"},
            "banks": {"amenity": "bank"},
            "cafes": {"amenity": "cafe"},
            "museums": {"tourism": "museum"},
            "primary_roads": {"highway": ["primary", "trunk", "motorway"]},
            "residential_buildings": {"building": "residential"},
            "commercial_buildings": {"building": "commercial"},
            "rivers": {"waterway": "river"},
            "forests": {"landuse": "forest"},
            "beaches": {"natural": "beach"},
            "train_stations": {"railway": "station"},
            "bus_stops": {"highway": "bus_stop"},
            "parking": {"amenity": "parking"}
        }



class Hydro :
    def __init__(self,output_dir="data/hydro"):
        
        self.output_dir=output_dir
        self.valid_regions=['af', 'as', 'au', 'eu', 'na', 'sa']


    def download(self,region: str, output_dir: str = "hydrorivers_data") -> gpd.GeoDataFrame:
        """
        Télécharge et charge les données HydroRIVERS pour une région donnée.

        Paramètres :
            region (str): Code de la région (ex: 'af', 'as', 'eu', 'na', 'sa', 'au').
            output_dir (str): Dossier local où les fichiers seront extraits.

        Retour :
            gpd.GeoDataFrame: Les données HydroRIVERS sous forme de GeoDataFrame.
        """
        self.output_dir=output_dir
        region = region.lower()
        valid_regions = self.valid_regions
        
        if region not in valid_regions:
            raise ValueError(f"Région invalide. Utilisez l’un de ces codes : {valid_regions}")
        
        url = f"https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{region}_shp.zip"
        region_dir = os.path.join(output_dir, region)

        if not os.path.exists(region_dir):
            os.makedirs(region_dir, exist_ok=True)
            print(f"Téléchargement des données HydroRIVERS pour la région : {region.upper()} ...")
            try:
                response = requests.get(url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(region_dir)
                print("Téléchargement et extraction terminés.")
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Erreur lors du téléchargement : {e}")
        else:
            print(f"Les données pour la région {region.upper()} sont déjà présentes.")

        # Chargement du shapefile
        
        shapefile_path = os.path.join(region_dir, f'HydroRIVERS_v10_{region}_shp\HydroRIVERS_v10_{region}.shp')
        if not os.path.exists(shapefile_path):
            raise FileNotFoundError(f"Fichier {shapefile_path} introuvable après extraction.")

        rivers = gpd.read_file(shapefile_path)
        self.rivers=rivers
        return rivers
    
    def describe_variables(self) -> str:
        """
        Retourne une description textuelle des principales variables contenues dans les données HydroRIVERS.
        """
        description = """
    📘 Description des variables HydroRIVERS :
| Nom          | Signification                    | Unité / Type         |
| ------------ | -------------------------------- | -------------------- |
| `HYRIV_ID`   | ID du tronçon                    | entier               |
| `NEXT_DOWN`  | ID du tronçon aval               | entier               |
| `MAIN_RIV`   | ID du fleuve principal           | entier               |
| `LENGTH_KM`  | Longueur du segment              | km (float)           |
| `DIST_DN_KM` | Distance jusqu'à l'embouchure    | km (float)           |
| `DIST_UP_KM` | Distance depuis la source        | km (float)           |
| `CATCH_SKM`  | Surface locale du bassin versant | km² (float)          |
| `UPLAND_SKM` | Surface totale en amont          | km² (float)          |
| `ENDORHEIC`  | 1 = bassin fermé, 0 = ouvert     | booléen (int)        |
| `DIS_AV_CMS` | Débit moyen                      | m³/s (float)         |
| `ORD_STRA`   | Ordre de Strahler                | entier               |
| `ORD_CLAS`   | Classe hiérarchique simplifiée   | entier               |
| `ORD_FLOW`   | Ordre de flux                    | entier               |
| `HYBAS_L12`  | Code du bassin de niveau 12      | entier (catégorique) |
  """
        return description





class DEM:
    """
    Classe pour télécharger des données numériques de terrain (DEM) en utilisant
    des packages Python existants spécialisés.
    
    Sources de données supportées:
    - SRTM via le package 'elevation'
    - USGS 3DEP via le package 'py3dep' 
    - ALOS World 3D via 'elevation'
    - ASTER GDEM via 'elevation'
    """
    
    def __init__(self, output_dir: str = "./dem_data"):
        """
        Initialise le téléchargeur DEM.
        
        Args:
            output_dir (str): Répertoire de sortie pour sauvegarder les fichiers DEM
        """
        self.output_dir = Path(output_dir)
        self.downloaded_list = []  # Liste des DEMs téléchargés
        
        # Créer le répertoire de sortie s'il n'existe pas
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # print("Packages requis: pip install elevation py3dep geopandas rasterio")
    
    def download_srtm_elevation(self, 
                               bbox: Tuple[float, float, float, float],
                               resolution: int = 1) -> str:
        """
        Télécharge des données SRTM via le package 'elevation'.
        
        Args:
            bbox (tuple): Bounding box (west, south, east, north) en degrés décimaux
            resolution (int): Résolution en arc-seconds (1 ou 3)
        
        Returns:
            str: Chemin vers le fichier téléchargé
        """
        try:
            import elevation
        except ImportError:
            raise ImportError("Le package 'elevation' est requis: pip install elevation")
        
        west, south, east, north = bbox
        
        # Validation de la bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Bounding box invalide. Vérifiez les coordonnées.")
        
        print(f"Téléchargement SRTM (resolution: {resolution}s) pour la zone: {bbox}")
        
        # Nom du fichier de sortie
        filename = f"srtm_{resolution}s_{west}_{south}_{east}_{north}.tif"
        filepath = self.output_dir / filename
        
        try:
            # Télécharger avec le package elevation
            elevation.clip(
                bounds=(west, south, east, north),
                output=str(filepath),
                product=f'SRTM{resolution}'  # SRTM1 (30m) ou SRTM3 (90m)
            )
            
            # Ajouter à la liste des téléchargements
            dem_info = {
                'path': str(filepath),
                'bbox': bbox,
                'source': f'SRTM{resolution}',
                'resolution': f'{resolution} arc-second',
                'package': 'elevation'
            }
            self.downloaded_list.append(dem_info)
            
            print(f"DEM SRTM téléchargé: {filepath}")
            return str(filepath)
            
        except Exception as e:
            raise Exception(f"Erreur lors du téléchargement SRTM: {e}")
    
    def download_alos_elevation(self, 
                               bbox: Tuple[float, float, float, float]) -> str:
        """
        Télécharge des données ALOS World 3D-30m via le package 'elevation'.
        
        Args:
            bbox (tuple): Bounding box (west, south, east, north) en degrés décimaux
        
        Returns:
            str: Chemin vers le fichier téléchargé
        """
        try:
            import elevation
        except ImportError:
            raise ImportError("Le package 'elevation' est requis: pip install elevation")
        
        west, south, east, north = bbox
        
        print(f"Téléchargement ALOS World 3D-30m pour la zone: {bbox}")
        
        # Nom du fichier de sortie
        filename = f"alos_30m_{west}_{south}_{east}_{north}.tif"
        filepath = self.output_dir / filename
        
        try:
            # Télécharger ALOS World 3D-30m
            elevation.clip(
                bounds=(west, south, east, north),
                output=str(filepath),
                product='ALOS30'  # ALOS World 3D 30m
            )
            
            # Ajouter à la liste des téléchargements
            dem_info = {
                'path': str(filepath),
                'bbox': bbox,
                'source': 'ALOS World 3D-30m',
                'resolution': '30 meters',
                'package': 'elevation'
            }
            self.downloaded_list.append(dem_info)
            
            print(f"DEM ALOS téléchargé: {filepath}")
            return str(filepath)
            
        except Exception as e:
            raise Exception(f"Erreur lors du téléchargement ALOS: {e}")
    
    def download_usgs_3dep(self, 
                          bbox: Tuple[float, float, float, float],
                          resolution: int = 30,
                          crs: str = "EPSG:4326") -> str:
        """
        Télécharge des données USGS 3DEP via le package 'py3dep'.
        
        Args:
            bbox (tuple): Bounding box (west, south, east, north) en degrés décimaux
            resolution (int): Résolution en mètres (10, 30, 60)
            crs (str): Système de coordonnées de référence
        
        Returns:
            str: Chemin vers le fichier téléchargé
        """
        try:
            import py3dep
        except ImportError:
            raise ImportError("Le package 'py3dep' est requis: pip install py3dep")
        
        west, south, east, north = bbox
        
        print(f"Téléchargement USGS 3DEP (résolution: {resolution}m) pour la zone: {bbox}")
        
        try:
            # Créer un GeoDataFrame avec la bbox
            geometry = [box(west, south, east, north)]
            gdf = gpd.GeoDataFrame(geometry=geometry, crs="EPSG:4326")
            
            # Si CRS différent, reprojeter
            if crs != "EPSG:4326":
                gdf = gdf.to_crs(crs)
            
            # Télécharger les données 3DEP
            dem = py3dep.get_map(
                gdf.bounds.iloc[0].values,  # [minx, miny, maxx, maxy]
                resolution=resolution,
                geo_crs=crs,
                crs=crs
            )
            
            # Nom du fichier de sortie
            filename = f"usgs_3dep_{resolution}m_{west}_{south}_{east}_{north}.tif"
            filepath = self.output_dir / filename
            
            # Sauvegarder le DEM
            dem.rio.to_raster(str(filepath))
            
            # Ajouter à la liste des téléchargements
            dem_info = {
                'path': str(filepath),
                'bbox': bbox,
                'source': 'USGS 3DEP',
                'resolution': f'{resolution} meters',
                'crs': crs,
                'package': 'py3dep'
            }
            self.downloaded_list.append(dem_info)
            
            print(f"DEM USGS 3DEP téléchargé: {filepath}")
            return str(filepath)
            
        except Exception as e:
            # Fallback pour les zones hors USA
            if "outside" in str(e).lower() or "usa" in str(e).lower():
                print("Zone hors USA, USGS 3DEP non disponible pour cette région")
                return None
            raise Exception(f"Erreur lors du téléchargement USGS 3DEP: {e}")
    
    def download_nasadem(self, 
                        bbox: Tuple[float, float, float, float]) -> str:
        """
        Télécharge des données NASADEM via le package 'elevation'.
        
        Args:
            bbox (tuple): Bounding box (west, south, east, north) en degrés décimaux
        
        Returns:
            str: Chemin vers le fichier téléchargé
        """
        try:
            import elevation
        except ImportError:
            raise ImportError("Le package 'elevation' est requis: pip install elevation")
        
        west, south, east, north = bbox
        
        print(f"Téléchargement NASADEM pour la zone: {bbox}")
        
        # Nom du fichier de sortie
        filename = f"nasadem_{west}_{south}_{east}_{north}.tif"
        filepath = self.output_dir / filename
        
        try:
            # Télécharger NASADEM
            elevation.clip(
                bounds=(west, south, east, north),
                output=str(filepath),
                product='NASADEM'  # NASADEM ~30m
            )
            
            # Ajouter à la liste des téléchargements
            dem_info = {
                'path': str(filepath),
                'bbox': bbox,
                'source': 'NASADEM',
                'resolution': '~30 meters',
                'package': 'elevation'
            }
            self.downloaded_list.append(dem_info)
            
            print(f"DEM NASADEM téléchargé: {filepath}")
            return str(filepath)
            
        except Exception as e:
            raise Exception(f"Erreur lors du téléchargement NASADEM: {e}")
    
    def get_elevation_point(self, lat: float, lon: float, source: str = "srtm") -> Optional[float]:
        """
        Obtient l'élévation pour un point spécifique.
        
        Args:
            lat (float): Latitude en degrés décimaux
            lon (float): Longitude en degrés décimaux
            source (str): Source de données ("srtm", "alos", "nasadem")
        
        Returns:
            float: Élévation en mètres, ou None si erreur
        """
        try:
            # Créer une petite bbox autour du point
            buffer = 0.01  # ~1km
            bbox = (lon - buffer, lat - buffer, lon + buffer, lat + buffer)
            
            # Télécharger temporairement
            if source.lower() == "srtm":
                temp_dem = self.download_srtm_elevation(bbox, resolution=1)
            elif source.lower() == "alos":
                temp_dem = self.download_alos_elevation(bbox)
            elif source.lower() == "nasadem":
                temp_dem = self.download_nasadem(bbox)
            else:
                temp_dem = self.download_srtm_elevation(bbox, resolution=1)
            
            if not temp_dem:
                return None
            
            # Lire la valeur au point
            with rasterio.open(temp_dem) as dataset:
                row, col = dataset.index(lon, lat)
                if 0 <= row < dataset.height and 0 <= col < dataset.width:
                    elevation = dataset.read(1)[row, col]
                    return float(elevation) if elevation != dataset.nodata else None
                else:
                    return None
                    
        except Exception as e:
            print(f"Erreur pour obtenir l'élévation au point ({lat}, {lon}): {e}")
            return None
    
    def analyze_dem(self, dem_path: str) -> dict:
        """
        Analyse un fichier DEM et retourne des statistiques.
        
        Args:
            dem_path (str): Chemin vers le fichier DEM
        
        Returns:
            dict: Statistiques du DEM
        """
        try:
            with rasterio.open(dem_path) as dataset:
                data = dataset.read(1)
                
                # Masquer les valeurs NoData
                if dataset.nodata is not None:
                    data = np.ma.masked_equal(data, dataset.nodata)
                
                stats = {
                    'chemin': dem_path,
                    'crs': str(dataset.crs),
                    'dimensions': (dataset.width, dataset.height),
                    'resolution_x': abs(dataset.transform[0]),
                    'resolution_y': abs(dataset.transform[4]),
                    'bbox': dataset.bounds,
                    'elevation_min': float(np.min(data)),
                    'elevation_max': float(np.max(data)),
                    'elevation_mean': float(np.mean(data)),
                    'elevation_std': float(np.std(data)),
                    'nodata_value': dataset.nodata,
                    'size_mb': os.path.getsize(dem_path) / (1024*1024)
                }
                
                return stats
                
        except Exception as e:
            return {'erreur': str(e)}
    
    def create_hillshade(self, 
                        dem_path: str, 
                        azimuth: float = 315.0, 
                        altitude: float = 45.0) -> str:
        """
        Crée un ombrage (hillshade) à partir d'un DEM.
        
        Args:
            dem_path (str): Chemin vers le DEM
            azimuth (float): Azimut de la source lumineuse (0-360°)
            altitude (float): Altitude de la source lumineuse (0-90°)
        
        Returns:
            str: Chemin vers le fichier hillshade
        """
        try:
            import richdem as rd
            
            # Charger le DEM
            dem = rd.LoadGDAL(dem_path)
            
            # Calculer le hillshade
            hillshade = rd.TerrainAttribute(dem, attrib='hillshade', azimuth=azimuth, angle=altitude)
            
            # Nom du fichier de sortie
            output_path = dem_path.replace('.tif', '_hillshade.tif')
            
            # Sauvegarder
            rd.SaveGDAL(output_path, hillshade)
            
            print(f"Hillshade créé: {output_path}")
            return output_path
            
        except ImportError:
            print("Le package 'richdem' est recommandé pour le hillshade: pip install richdem")
            # Fallback avec numpy/scipy
            return self._create_hillshade_numpy(dem_path, azimuth, altitude)
        except Exception as e:
            print(f"Erreur lors de la création du hillshade: {e}")
            return None
    
    def _create_hillshade_numpy(self, dem_path: str, azimuth: float, altitude: float) -> str:
        """
        Version fallback du hillshade avec numpy.
        """
        try:
            output_path = dem_path.replace('.tif', '_hillshade.tif')
            
            with rasterio.open(dem_path) as src:
                elevation = src.read(1).astype(np.float64)
                
                # Calculer les gradients
                x, y = np.gradient(elevation)
                
                # Convertir les angles en radians
                azimuth_rad = np.radians(360.0 - azimuth + 90.0)
                altitude_rad = np.radians(altitude)
                
                # Calculer la pente et l'aspect
                slope = np.pi/2. - np.arctan(np.sqrt(x*x + y*y))
                aspect = np.arctan2(-x, y)
                
                # Calculer l'ombrage
                hillshade = np.sin(altitude_rad) * np.sin(slope) + \
                           np.cos(altitude_rad) * np.cos(slope) * \
                           np.cos(azimuth_rad - aspect)
                
                # Normaliser entre 0 et 255
                hillshade = np.clip((hillshade * 255), 0, 255).astype(np.uint8)
                
                # Sauvegarder
                profile = src.profile.copy()
                profile.update(dtype=rasterio.uint8, count=1)
                
                with rasterio.open(output_path, 'w', **profile) as dst:
                    dst.write(hillshade, 1)
            
            print(f"Hillshade créé: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Erreur lors de la création du hillshade: {e}")
            return None
    
    def reproject_dem(self, 
                     input_path: str, 
                     output_crs: str = 'EPSG:3857',
                     resampling_method: Resampling = Resampling.bilinear) -> str:
        """
        Reprojette un DEM vers un autre système de coordonnées.
        
        Args:
            input_path (str): Chemin vers le DEM d'entrée
            output_crs (str): CRS de sortie (ex: 'EPSG:3857', 'EPSG:4326')
            resampling_method: Méthode de rééchantillonnage
        
        Returns:
            str: Chemin vers le fichier reprojeté
        """
        output_path = input_path.replace('.tif', f'_{output_crs.replace(":", "_")}.tif')
        
        with rasterio.open(input_path) as src:
            dst_crs = CRS.from_string(output_crs)
            
            # Calculer la transformation
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )
            
            # Métadonnées pour le fichier de sortie
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': dst_crs,
                'transform': transform,
                'width': width,
                'height': height
            })
            
            with rasterio.open(output_path, 'w', **kwargs) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=resampling_method
                )
        
        print(f"DEM reprojeté sauvegardé: {output_path}")
        return output_path
    
    def get_downloaded_list(self) -> List[dict]:
        """
        Retourne la liste des DEMs téléchargés.
        
        Returns:
            List[dict]: Liste des informations sur les DEMs téléchargés
        """
        return self.downloaded_list
    
    def clear_downloaded_list(self):
        """
        Vide la liste des DEMs téléchargés.
        """
        self.downloaded_list.clear()
        print("Liste des téléchargements vidée.")
    
    def print_downloaded_summary(self):
        """
        Affiche un résumé des DEMs téléchargés.
        """
        if not self.downloaded_list:
            print("Aucun DEM téléchargé.")
            return
        
        print(f"\n=== Résumé des {len(self.downloaded_list)} DEM(s) téléchargé(s) ===")
        for i, dem in enumerate(self.downloaded_list, 1):
            print(f"\n{i}. Source: {dem['source']} (via {dem['package']})")
            print(f"   Fichier: {Path(dem['path']).name}")
            print(f"   Zone: {dem['bbox']}")
            print(f"   Résolution: {dem['resolution']}")
            if 'crs' in dem:
                print(f"   CRS: {dem['crs']}")
    
    def auto_download(self, 
                     bbox: Tuple[float, float, float, float],
                     prefer_high_res: bool = True) -> str:
        """
        Télécharge automatiquement le meilleur DEM disponible pour la zone.
        
        Args:
            bbox (tuple): Bounding box (west, south, east, north)
            prefer_high_res (bool): Préférer la haute résolution
        
        Returns:
            str: Chemin vers le DEM téléchargé
        """
        west, south, east, north = bbox
        
        print(f"Téléchargement automatique pour la zone: {bbox}")
        
        # Détecter si c'est aux USA pour 3DEP
        is_usa = (-180 <= west <= -65 and 15 <= south <= 72 and 
                  -180 <= east <= -65 and 15 <= north <= 72)
        
        # Ordre de priorité selon les préférences
        if prefer_high_res:
            methods = [
                ('USGS 3DEP 10m', lambda: self.download_usgs_3dep(bbox, resolution=10) if is_usa else None),
                ('USGS 3DEP 30m', lambda: self.download_usgs_3dep(bbox, resolution=30) if is_usa else None),
                ('ALOS World 3D', lambda: self.download_alos_elevation(bbox)),
                ('SRTM 1s', lambda: self.download_srtm_elevation(bbox, resolution=1)),
                ('NASADEM', lambda: self.download_nasadem(bbox))
            ]
        else:
            methods = [
                ('SRTM 1s', lambda: self.download_srtm_elevation(bbox, resolution=1)),
                ('ALOS World 3D', lambda: self.download_alos_elevation(bbox)),
                ('NASADEM', lambda: self.download_nasadem(bbox)),
                ('USGS 3DEP 30m', lambda: self.download_usgs_3dep(bbox, resolution=30) if is_usa else None)
            ]
        
        # Essayer chaque méthode
        for method_name, method_func in methods:
            try:
                print(f"Tentative avec {method_name}...")
                result = method_func()
                if result:
                    print(f"Succès avec {method_name}")
                    return result
            except Exception as e:
                print(f"Échec avec {method_name}: {e}")
                continue
        
        raise Exception("Impossible de télécharger des données DEM pour cette zone")

    def download(self, 
                bbox: Tuple[float, float, float, float],
                source: Optional[str] = None,
                resolution: Optional[Union[str, float]] = None) -> str:
        """
        Télécharge un DEM depuis une source priorisée (API → fallback local).
        
        Args:
            bbox (tuple): (west, south, east, north)
            source (str, optional): 'srtm', 'etopo', 'openelevation', 'fallback'
            resolution (str|float, optional): résolution selon source
        
        Returns:
            str: chemin vers le fichier DEM
        """
        try_sources = [source] if source else ['srtm', 'etopo', 'openelevation']
        
        for src in try_sources:
            try:
                print(f"👉 Tentative avec la source '{src}'...")
                if src == 'srtm':
                    res = resolution if resolution else 0.000277777778
                    return self.download_srtm_opentopography(bbox, resolution=res)
                elif src == 'etopo':
                    res = resolution if resolution else '1m'
                    return self.download_etopo_noaa(bbox, resolution=res)
                elif src in ['open-elevation', 'openelevation']:
                    res = resolution if resolution else 1000
                    return self.download_elevation_api(bbox, samples=int(res))
            except Exception as e:
                print(f"⚠️ Échec avec la source '{src}': {e}")
                continue

        # 🛟 Fallback avec `elevation` (basé sur SRTM)
        try:
            print("🚨 Aucune source API n'a fonctionné. Fallback avec le package Python 'elevation'...")
            import elevation
            from rasterio import transform as rtransform

            bounds = {'left': bbox[0], 'bottom': bbox[1], 'right': bbox[2], 'top': bbox[3]}
            filename = f"fallback_srtm_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}.tif"
            filepath = os.path.join(self.output_dir, filename)

            elevation.clip(bounds=bounds, output=filepath, product='SRTM1')
            elevation.clean()

            print(f"✅ Fichier DEM téléchargé avec fallback (elevation): {filepath}")
            return filepath
        
        except Exception as e:
            print(f"⚠️ Échec du fallback avec 'elevation': {e}")


    def download_elevation_api(self, 
                             bbox: Tuple[float, float, float, float],
                             samples: int = 1500) -> str:
        """
        Télécharge des données d'élévation via Open-Elevation API (gratuit, sans clé).
        
        Args:
            bbox (tuple): Bounding box (west, south, east, north) en degrés décimaux
            samples (int): Nombre d'échantillons par dimension (max 100x100 recommandé)
        
        Returns:
            str: Chemin vers le fichier téléchargé
        """
        west, south, east, north = bbox
        
        # Validation
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Bounding box invalide. Vérifiez les coordonnées.")
        
        if samples > 100:
            print("Attention: samples > 100 peut causer des timeouts")
            samples = 100
        
        print(f"Téléchargement via Open-Elevation API pour la zone: {bbox}")
        print(f"Résolution: {samples}x{samples} points")
        
        # Créer une grille de points
        lats = np.linspace(south, north, samples)
        lons = np.linspace(west, east, samples)
        
        # Initialiser la matrice d'élévation
        elevation_data = np.zeros((samples, samples))
        
        # API Open-Elevation (limite: 100 points par requête)
        base_url = "https://api.open-elevation.com/api/v1/lookup"
        
        batch_size = 100
        total_points = samples * samples
        processed = 0
        
        for i, lat in enumerate(lats):
            for j in range(0, len(lons), batch_size):
                batch_lons = lons[j:j+batch_size]
                
                # Préparer les locations pour cette batch
                locations = []
                for lon in batch_lons:
                    locations.append({"latitude": lat, "longitude": lon})
                
                try:
                    response = self.session.post(
                        base_url,
                        json={"locations": locations},
                        timeout=30
                    )
                    response.raise_for_status()
                    
                    results = response.json()['results']
                    
                    # Remplir la matrice d'élévation
                    for k, result in enumerate(results):
                        col_idx = j + k
                        if col_idx < len(lons):
                            elevation_data[i, col_idx] = result['elevation']
                    
                    processed += len(results)
                    if processed % 500 == 0:
                        print(f"Progression: {processed}/{total_points} points")
                
                except requests.exceptions.RequestException as e:
                    print(f"Erreur pour la batch lat={lat:.4f}: {e}")
                    # Remplir avec des valeurs par défaut en cas d'erreur
                    try :
                        response = self.session.post(
                            base_url,
                            json={"locations": locations},
                            timeout=30
                        )
                        response.raise_for_status()
                        
                        results = response.json()['results']
                        
                        # Remplir la matrice d'élévation
                        for k, result in enumerate(results):
                            col_idx = j + k
                            if col_idx < len(lons):
                                elevation_data[i, col_idx] = result['elevation']
                        
                        processed += len(results)
                        if processed % 500 == 0:
                            print(f"Progression: {processed}/{total_points} points")
                    except :
                        try :
                            response = self.session.post(
                                base_url,
                                json={"locations": locations},
                                timeout=30
                            )
                            response.raise_for_status()
                            
                            results = response.json()['results']
                            
                            # Remplir la matrice d'élévation
                            for k, result in enumerate(results):
                                col_idx = j + k
                                if col_idx < len(lons):
                                    elevation_data[i, col_idx] = result['elevation']
                            
                            processed += len(results)
                            if processed % 500 == 0:
                                print(f"Progression: {processed}/{total_points} points")
                        except :

                            response = self.session.post(
                                base_url,
                                json={"locations": locations},
                                timeout=30
                            )
                            response.raise_for_status()
                            
                            results = response.json()['results']
                            
                            # Remplir la matrice d'élévation
                            for k, result in enumerate(results):
                                col_idx = j + k
                                if col_idx < len(lons):
                                    elevation_data[i, col_idx] = result['elevation']
                            
                            processed += len(results)
                            if processed % 500 == 0:
                                print(f"Progression: {processed}/{total_points} points")
                            # except :
                            #     # Remplir avec des valeurs par défaut en cas d'erreur
                            #     for k in range(len(batch_lons)):
                            #         col_idx = j + k
                            #         if col_idx < len(lons):
                            #             elevation_data[i, col_idx] = -9999
        
        # Créer le GeoTIFF
        filename = f"open_elevation_{west}_{south}_{east}_{north}_{samples}x{samples}.tif"
        filepath = os.path.join(self.output_dir, filename)
        
        # Transformation géospatiale
        transform = rasterio.transform.from_bounds(west, south, east, north, samples, samples)
        
        # Sauvegarder
        with rasterio.open(
            filepath, 'w',
            driver='GTiff',
            height=samples,
            width=samples,
            count=1,
            dtype=np.float32,
            crs='EPSG:4326',
            transform=transform,
            nodata=-9999
        ) as dst:
            dst.write(elevation_data.astype(np.float32), 1)
        
        # Ajouter à la liste des téléchargements
        dem_info = {
            'path': filepath,
            'bbox': bbox,
            'source': 'Open-Elevation API',
            'resolution': f"{samples}x{samples}"
        }
        self.downloaded_list.append(dem_info)
        
        print(f"DEM Open-Elevation téléchargé: {filepath}")
        return filepath




class SRTM:
    """
    Classe pour télécharger des tuiles SRTM depuis les serveurs NASA.
    """
    
    BASE_URL = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/"
    AUTH_URL = "https://urs.earthdata.nasa.gov"
    
    def __init__(self, username: str, password: str, resolution: str = "1arc"):
        """
        Initialise le téléchargeur SRTM.
        
        Args:
            username: Nom d'utilisateur NASA Earthdata
            password: Mot de passe NASA Earthdata
            resolution: Résolution des données ('1arc' pour ~30m, '3arc' pour ~90m)
        """
        self.username = username
        self.password = password
        self.resolution = resolution
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """Configure la session avec authentification."""
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({
            'User-Agent': 'SRTM-Downloader/3.2.3'
        })
    
    def _get_tile_name(self, lat: float, lon: float) -> str:
        """
        Génère le nom de la tuile SRTM pour des coordonnées données.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Nom du fichier de la tuile (ex: N48E002.hgt.zip)
        """
        # Latitude
        if lat >= 0:
            lat_str = f"N{int(math.floor(lat)):02d}"
        else:
            lat_str = f"S{int(math.ceil(abs(lat))):02d}"
        
        # Longitude
        if lon >= 0:
            lon_str = f"E{int(math.floor(lon)):03d}"
        else:
            lon_str = f"W{int(math.ceil(abs(lon))):03d}"
        
        return f"{lat_str}{lon_str}.SRTMGL1.hgt.zip"
    
    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """
        Valide que les coordonnées sont dans la zone de couverture SRTM.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            True si valide, False sinon
        """
        if lat < -56 or lat > 60:
            return False
        if lon < -180 or lon > 180:
            return False
        return True
    
    def download_tile(
        self, 
        latitude: float, 
        longitude: float, 
        output_dir: str = ".",
        overwrite: bool = False
    ) -> Optional[str]:
        """
        Télécharge une tuile SRTM individuelle.
        
        Args:
            latitude: Latitude du point
            longitude: Longitude du point
            output_dir: Répertoire de sortie
            overwrite: Si True, télécharge même si le fichier existe
            
        Returns:
            Chemin du fichier téléchargé ou None en cas d'erreur
        """
        if not self._validate_coordinates(latitude, longitude):
            print(f"❌ Coordonnées invalides ou hors zone de couverture SRTM: ({latitude}, {longitude})")
            return None
        
        # Créer le répertoire de sortie
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Nom de la tuile
        tile_name = self._get_tile_name(latitude, longitude)
        output_file = output_path / tile_name
        
        # Vérifier si le fichier existe déjà
        if output_file.exists() and not overwrite:
            print(f"⏭️  Tuile déjà téléchargée: {tile_name}")
            return str(output_file)
        
        # URL de téléchargement
        url = f"{self.BASE_URL}{tile_name}"
        
        print(f"📥 Téléchargement: {tile_name}")
        
        try:
            # Effectuer la requête
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Taille du fichier
            total_size = int(response.headers.get('content-length', 0))
            
            # Télécharger avec barre de progression
            with open(output_file, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=tile_name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            print(f"✅ Téléchargé: {output_file}")
            return str(output_file)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"❌ Erreur d'authentification. Vérifiez vos identifiants NASA Earthdata.")
            elif e.response.status_code == 404:
                print(f"❌ Tuile non trouvée: {tile_name}")
            else:
                print(f"❌ Erreur HTTP {e.response.status_code}: {e}")
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur de téléchargement: {e}")
            return None
        
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            return None
    
    def download_area(
        self,
        west: float,
        east: float,
        south: float,
        north: float,
        output_dir: str = ".",
        overwrite: bool = False
    ) -> list:
        """
        Télécharge toutes les tuiles SRTM couvrant une zone géographique.
        
        Args:
            west: Longitude ouest (min)
            east: Longitude est (max)
            south: Latitude sud (min)
            north: Latitude nord (max)
            output_dir: Répertoire de sortie
            overwrite: Si True, télécharge même si les fichiers existent
            
        Returns:
            Liste des chemins des fichiers téléchargés
        """
        # Validation
        if west >= east:
            print("❌ Erreur: west doit être inférieur à east")
            return []
        
        if south >= north:
            print("❌ Erreur: south doit être inférieur à north")
            return []
        
        # Calculer les tuiles nécessaires
        lat_start = int(math.floor(south))
        lat_end = int(math.floor(north))
        lon_start = int(math.floor(west))
        lon_end = int(math.floor(east))
        
        tiles = []
        for lat in range(lat_start, lat_end + 1):
            for lon in range(lon_start, lon_end + 1):
                tiles.append((lat, lon))
        
        print(f"\n🌍 Zone de téléchargement:")
        print(f"   Ouest: {west}°, Est: {east}°")
        print(f"   Sud: {south}°, Nord: {north}°")
        print(f"   Nombre de tuiles: {len(tiles)}\n")
        
        # Télécharger toutes les tuiles
        downloaded_files = []
        for i, (lat, lon) in enumerate(tiles, 1):
            print(f"\n[{i}/{len(tiles)}]", end=" ")
            file_path = self.download_tile(lat, lon, output_dir, overwrite)
            if file_path:
                downloaded_files.append(file_path)
            
            # Petit délai pour éviter de surcharger le serveur
            if i < len(tiles):
                time.sleep(0.5)
        
        print(f"\n\n✅ Téléchargement terminé: {len(downloaded_files)}/{len(tiles)} tuiles")
        return downloaded_files
