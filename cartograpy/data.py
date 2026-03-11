from __future__ import annotations

# Packages pour les données vectorelles
import pandas as pd
import geopandas as gpd
import geojson
from typing import *
import math
import numpy as np

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

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
try:
    from rasterio.transform import Affine
    from rasterio.merge import merge as rio_merge
    from rasterio.windows import from_bounds
except ImportError as e:
    raise ImportError(
        """Cette classe nécessite rasterio. 
        Installez-le avec: pip install rasterio"""
    ) from e
import tempfile
from urllib.parse import urlencode
import warnings
import datetime
from tqdm import tqdm
import gzip
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, as_completed
import struct



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
    # Convertir filepath en string s'il s'agit d'un objet Path
    filepath_str = str(filepath)
    ext = filepath_str.split('.')[-1].lower()

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
    # Chargement de données raster
    elif ext in raster_exts:
        try:
            with rasterio.open(filepath) as src:
                arr = src.read(1)           # bande 1
                nodata = src.nodata
            # Masquer les NoData pour un rendu propre
            if nodata is not None:
                import numpy as np
                arr = np.ma.masked_equal(arr, nodata)
            return arr
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
        str : Chemin absolu vers le fichier sauvegardé.

    Raises :
        ValueError : Si le format n'est pas supporté ou si raster_meta est manquant/incomplet.
        TypeError  : Si le type de données n'est pas pris en charge.

    Exemples :
        >>> save(gdf, 'geojson', 'ma_carte')
        >>> save(array, 'tif', 'mon_raster', raster_meta=meta)
    """
    # -- Mapping des formats supportés ----------------------------------------
    _VECTOR_DRIVERS = {
        'geojson': 'GeoJSON',
        'shp': 'ESRI Shapefile',
        'gpkg': 'GPKG',
        'kml': 'KML',
    }
    _TABULAR_EXTS = {'csv', 'parquet', 'geoparquet', 'xlsx', 'feather'}
    _RASTER_EXTS = {'tif', 'tiff'}
    _ALL_SUPPORTED = set(_VECTOR_DRIVERS) | _TABULAR_EXTS | _RASTER_EXTS

    # -- Normalisation / validation -------------------------------------------
    file_extension = file_extension.lower().lstrip('.')
    if file_extension not in _ALL_SUPPORTED:
        raise ValueError(
            f"Format '{file_extension}' non supporté. "
            f"Formats acceptés : {sorted(_ALL_SUPPORTED)}"
        )

    # S1 : empêcher le path traversal (on ne garde que le basename)
    filename = os.path.basename(str(filename))

    if timestamp:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{now}"
    output_path = f"{filename}.{file_extension}"

    # R1 : créer le répertoire parent si nécessaire
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # ── VECTOR / TABULAR ────────────────────────────────────────────────────
    if isinstance(data, (gpd.GeoDataFrame, pd.DataFrame)):
        # Formats vectoriels natifs (via fiona/GDAL)
        if file_extension in _VECTOR_DRIVERS:
            data.to_file(output_path, driver=_VECTOR_DRIVERS[file_extension])

        # Formats tabulaires (géométrie retirée sauf geoparquet)
        elif file_extension in _TABULAR_EXTS:
            # GeoParquet conserve la géométrie
            if file_extension == 'geoparquet':
                if isinstance(data, gpd.GeoDataFrame):
                    data.to_parquet(output_path, index=False)
                else:
                    raise TypeError(
                        "geoparquet nécessite un GeoDataFrame (pas un DataFrame)."
                    )
            else:
                # Retirer la géométrie une seule fois
                if isinstance(data, gpd.GeoDataFrame):
                    data = data.drop(columns='geometry', errors='ignore')
                if file_extension == 'csv':
                    data.to_csv(output_path, index=False)
                elif file_extension == 'parquet':
                    data.to_parquet(output_path, index=False)
                elif file_extension == 'xlsx':
                    data.to_excel(output_path, index=False)
                elif file_extension == 'feather':
                    data.to_feather(output_path)
        else:
            raise ValueError(
                f"Le format '{file_extension}' n'est pas un format vectoriel/tabulaire. "
                f"Type de données reçu : {type(data).__name__}"
            )

    # ── RASTER ──────────────────────────────────────────────────────────────
    elif isinstance(data, rasterio.io.DatasetReader):
        if file_extension not in _RASTER_EXTS:
            raise ValueError(
                f"Un DatasetReader ne peut être sauvegardé qu'en TIFF, "
                f"pas en '{file_extension}'."
            )
        with rasterio.open(output_path, 'w', **data.meta) as dst:
            dst.write(data.read())

    elif isinstance(data, np.ndarray):
        if file_extension not in _RASTER_EXTS:
            raise ValueError(
                f"Un ndarray raster ne peut être sauvegardé qu'en TIFF, "
                f"pas en '{file_extension}'."
            )
        if raster_meta is None:
            raise ValueError("raster_meta est requis pour enregistrer un ndarray.")
        _required_keys = {'crs', 'transform', 'width', 'height', 'dtype', 'count'}
        missing = _required_keys - set(raster_meta)
        if missing:
            raise ValueError(
                f"Clés manquantes dans raster_meta : {sorted(missing)}"
            )
        # B4 : ndarray 2D → 3D automatiquement
        if data.ndim == 2:
            data = data[np.newaxis, :, :]
        with rasterio.open(output_path, 'w', **raster_meta) as dst:
            dst.write(data)

    else:
        raise TypeError(
            f"Type de données non pris en charge : {type(data).__name__}. "
            f"Attendu : GeoDataFrame, DataFrame, DatasetReader ou ndarray."
        )

    abs_path = os.path.abspath(output_path)
    print(f"✅ Fichier sauvegardé : {abs_path}")
    return abs_path


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



class Bound:
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

    def get_admin(self, territories: Union[str, List[str]], adm: Union[str, int], simplified: bool = True) -> dict:
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

        return pd.concat(geojsons_dic,axis=0,ignore_index=True)


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

    def get_country(self, name: Union[str, List[str]]) -> gpd.GeoDataFrame:
        """
        Récupère les frontières (ADM0) d'un ou plusieurs pays.

        Args:
            name: Nom du pays, code ISO2/ISO3, ou une liste de noms/codes.
                  Exemples : "France", "FRA", ["France", "SEN", "Mali"]

        Returns:
            gpd.GeoDataFrame: GeoDataFrame contenant la/les géométrie(s) du/des pays (niveau ADM0).
                Si un seul pays est fourni, retourne un GeoDataFrame.
                Si une liste est fournie, retourne un GeoDataFrame concaténé de tous les pays.

        Raises:
            KeyError: Si un pays n'est pas trouvé.

        Exemples:
            >>> b = bound()
            >>> france = b.get_country("France")
            >>> pays = b.get_country(["France", "SEN", "Mali"])
        """
        if isinstance(name, str):
            return self.get_admin(name, adm=0, simplified=True)
        
        gdfs = []
        for country in name:
            gdf = self.get_admin(country, adm=0, simplified=True)
            gdfs.append(gdf)
        return pd.concat(gdfs, ignore_index=True)


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
            >>> b = bound()
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
            >>> b = bound()
            >>> continents = b.get_world("continent")
            >>> pays = b.get_world("country")
        """
        level = level.strip().lower()
        if level == "continent":
            return self.continents()
        elif level == "country":
            naturalearth_url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
            return gpd.read_file(naturalearth_url)
        else:
            raise ValueError(
                f"Niveau '{level}' non supporté. Utilisez 'continent' ou 'country'."
            )



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

    def bbox(self,localitie):
        import osmnx as ox
        gdf = ox.geocode_to_gdf(localitie)
        west, south, east, north = gdf.total_bounds
        return (west, south, east, north)



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
        self.api_key = ""
    
    def get_data(self,place, tags, data_type="all"):
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


    def get_common_tag(self):
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



BBox = Tuple[float, float, float, float]  # (west, south, east, north)

class DEMDownloadError(RuntimeError):
    """Erreur de téléchargement/traitement DEM."""
    pass


class DEM:
    """
    Télécharge un MNT (Modèle Numérique de Terrain) SRTM (~30 m) sans clé API
    via les tuiles Skadi hébergées sur AWS, puis mosaïque et découpe selon
    une emprise (EPSG:4326).

    Paramètres
    ----------
    work_dir : répertoire de travail pour les fichiers intermédiaires.
    timeout : délai maximal (en secondes) par requête HTTP.
    keep_intermediate : si True, conserve les tuiles .hgt.gz et .tif.
    output_dir : alias déprécié de work_dir (rétrocompatibilité).

    Exemple
    -------
    >>> dem = DEM(work_dir="_dem_tiles", timeout=180)
    >>> chemin = dem.download(bbox=(-8, 4, -2, 11), out_tif="srtm_ci.tif")
    """

    def __init__(
        self,
        work_dir: Union[str, Path] = "_dem_tiles",
        timeout: int = 180,
        keep_intermediate: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if output_dir is not None:
            if work_dir != "_dem_tiles":
                warnings.warn(
                    "Les paramètres 'work_dir' et 'output_dir' sont tous deux fournis. "
                    "'output_dir' est prioritaire.",
                    UserWarning,
                    stacklevel=2,
                )
            work_dir = output_dir

        self.work_dir = Path(work_dir)
        self.timeout = int(timeout)
        self.keep_intermediate = bool(keep_intermediate)

        self.gz_dir = self.work_dir / "hgt_gz"
        self.tif_dir = self.work_dir / "tile_tif"
        self.gz_dir.mkdir(parents=True, exist_ok=True)
        self.tif_dir.mkdir(parents=True, exist_ok=True)

        # Endpoint public (pas de clé)
        self._base_url = "https://s3.amazonaws.com/elevation-tiles-prod/skadi"

        # P3 : cache HTTP pour éviter re-téléchargements
        self._session = CachedSession(
            cache_name=str(self.work_dir / ".http_cache"),
            backend="filesystem",
            expire_after=datetime.timedelta(days=30),
        )

    # -----------------------
    # Helpers (private)
    # -----------------------
    @staticmethod
    def _lat_code(lat: int) -> str:
        return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"

    @staticmethod
    def _lon_code(lon: int) -> str:
        return f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"

    def _skadi_url(self, lat_ll: int, lon_ll: int) -> str:
        latc = self._lat_code(lat_ll)
        lonc = self._lon_code(lon_ll)
        return f"{self._base_url}/{latc}/{latc}{lonc}.hgt.gz"

    # Taille attendue d'un fichier .hgt.gz SRTM 1-arc-seconde (3601×3601 × 2 octets)
    _HGT_RAW_SIZE = 3601 * 3601 * 2  # 25 934 402 octets non compressés
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 2  # secondes, sera doublé à chaque tentative

    @staticmethod
    def _validate_bbox(bbox: BBox) -> None:
        west, south, east, north = bbox
        if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
            raise ValueError("Longitude hors limites [-180, 180].")
        if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
            raise ValueError("Latitude hors limites [-90, 90].")
        if south >= north:
            raise ValueError("BBox invalide: 'south' doit être < 'north'.")

    @staticmethod
    def _split_antimeridian_bbox(bbox: BBox) -> List[BBox]:
        """Découpe une bbox traversant l'antiméridien en deux bbox valides."""
        west, south, east, north = bbox
        if west <= east:
            return [bbox]
        # west > east → traverse l'antiméridien
        return [
            (west, south, 180.0, north),   # partie est
            (-180.0, south, east, north),  # partie ouest
        ]

    @staticmethod
    def _iter_degree_tiles_for_bbox(bbox: BBox) -> List[Tuple[int, int]]:
        """
        Retourne la liste des tuiles 1°x1° (lat_ll, lon_ll) couvrant la bbox.
        """
        west, south, east, north = bbox

        lat_start = math.floor(south)
        lat_end = math.ceil(north) - 1
        lon_start = math.floor(west)
        lon_end = math.ceil(east) - 1

        tiles: List[Tuple[int, int]] = []
        for lat_ll in range(lat_start, lat_end + 1):
            for lon_ll in range(lon_start, lon_end + 1):
                tiles.append((lat_ll, lon_ll))
        return tiles

    def _download_file(self, url: str, dst: Path, allow_missing: bool = False) -> bool:
        """Télécharge un fichier avec retry et écriture atomique.

        Retourne True si le fichier a été téléchargé (ou existait déjà),
        False si la tuile n'existe pas sur le serveur (HTTP 403/404)
        et que allow_missing=True.
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size > 0:
            return True

        tmp_dst = dst.with_suffix(dst.suffix + ".part")
        try:
            if tmp_dst.exists():
                tmp_dst.unlink()
        except OSError:
            pass

        last_exc: Optional[Exception] = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                with self._session.get(url, stream=True, timeout=self.timeout) as r:
                    # R4 : tuile manquante (océan) → ne pas lever d'erreur
                    if r.status_code in (403, 404) and allow_missing:
                        return False
                    if not r.ok:
                        raise DEMDownloadError(
                            f"Échec téléchargement {url} (HTTP {r.status_code})."
                        )
                    with open(tmp_dst, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)

                if not tmp_dst.exists() or tmp_dst.stat().st_size == 0:
                    raise DEMDownloadError(f"Téléchargement incomplet ou vide: {url}")

                # R3 : vérification d'intégrité — le .hgt.gz décompressé
                # doit contenir exactement _HGT_RAW_SIZE octets
                try:
                    with gzip.open(tmp_dst, "rb") as gz:
                        raw = gz.read()
                    if len(raw) != self._HGT_RAW_SIZE:
                        raise DEMDownloadError(
                            f"Intégrité : {dst.name} → {len(raw)} octets "
                            f"(attendu {self._HGT_RAW_SIZE})."
                        )
                except (gzip.BadGzipFile, OSError) as e:
                    raise DEMDownloadError(
                        f"Fichier corrompu (décompression échouée) : {dst.name}"
                    ) from e

                tmp_dst.replace(dst)
                return True

            except DEMDownloadError:
                last_exc = None
                # Ne pas retry les erreurs non récupérables
                try:
                    if tmp_dst.exists():
                        tmp_dst.unlink()
                except OSError:
                    pass
                raise
            except (requests.RequestException, OSError) as exc:
                last_exc = exc
                wait = self._RETRY_BACKOFF * (2 ** (attempt - 1))
                warnings.warn(
                    f"Tentative {attempt}/{self._MAX_RETRIES} échouée pour {url} "
                    f"({exc}). Nouvel essai dans {wait}s…",
                    UserWarning,
                    stacklevel=2,
                )
                time.sleep(wait)
                try:
                    if tmp_dst.exists():
                        tmp_dst.unlink()
                except OSError:
                    pass

        # Toutes les tentatives épuisées
        try:
            if tmp_dst.exists():
                tmp_dst.unlink()
        except OSError:
            pass
        raise DEMDownloadError(
            f"Échec après {self._MAX_RETRIES} tentatives pour {url}"
        ) from last_exc

    @staticmethod
    def _make_nodata_geotiff(tif_path: Path, lat_ll: int, lon_ll: int) -> None:
        """Crée une tuile GeoTIFF remplie de nodata (tuile océan manquante)."""
        arr = np.full((3601, 3601), -32768, dtype=np.int16)
        res = 1.0 / 3600.0
        transform = Affine(
            res, 0.0, lon_ll - res / 2.0,
            0.0, -res, (lat_ll + 1) + res / 2.0,
        )
        profile = {
            "driver": "GTiff", "height": 3601, "width": 3601,
            "count": 1, "dtype": np.int16, "crs": "EPSG:4326",
            "transform": transform, "compress": "deflate",
            "predictor": 2, "tiled": True,
            "blockxsize": 256, "blockysize": 256, "nodata": -32768,
        }
        tif_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(tif_path, "w", **profile) as dst:
            dst.write(arr, 1)

    @staticmethod
    def _hgt_gz_to_geotiff(hgt_gz: Path, tif_path: Path, lat_ll: int, lon_ll: int) -> None:
        """
        Convertit une tuile .hgt.gz (3601×3601, int16 big-endian) en GeoTIFF (EPSG:4326).
        """
        with gzip.open(hgt_gz, "rb") as gz:
            raw = gz.read()

        arr = np.frombuffer(raw, dtype=">i2")
        if arr.size != 3601 * 3601:
            raise DEMDownloadError(
                f"Taille inattendue pour {hgt_gz.name}: {arr.size} valeurs."
            )

        arr = arr.reshape((3601, 3601)).astype(np.int16)

        res = 1.0 / 3600.0  # 1 arc-second en degrés

        transform = Affine(
            res, 0.0, lon_ll - res / 2.0,
            0.0, -res, (lat_ll + 1) + res / 2.0
        )

        profile = {
            "driver": "GTiff",
            "height": arr.shape[0],
            "width": arr.shape[1],
            "count": 1,
            "dtype": arr.dtype,
            "crs": "EPSG:4326",
            "transform": transform,
            "compress": "deflate",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
            "nodata": -32768,
        }

        tif_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(tif_path, "w", **profile) as dst:
            dst.write(arr, 1)

    def _cleanup(self) -> None:
        if self.keep_intermediate:
            return

        for p in self.gz_dir.glob("*.hgt.gz"):
            try:
                p.unlink()
            except OSError:
                pass
        for p in self.tif_dir.glob("*.tif"):
            try:
                p.unlink()
            except OSError:
                pass

    # -----------------------
    # Public API
    # -----------------------
    def _download_and_convert_tile(
        self, lat_ll: int, lon_ll: int
    ) -> Path:
        """Télécharge et convertit une tuile unique. Retourne le chemin du GeoTIFF."""
        url = self._skadi_url(lat_ll, lon_ll)
        gz_path = self.gz_dir / f"{self._lat_code(lat_ll)}{self._lon_code(lon_ll)}.hgt.gz"

        downloaded = self._download_file(url, gz_path, allow_missing=True)

        tif_path = self.tif_dir / f"{self._lat_code(lat_ll)}{self._lon_code(lon_ll)}.tif"
        if not tif_path.exists() or tif_path.stat().st_size == 0:
            if downloaded:
                self._hgt_gz_to_geotiff(gz_path, tif_path, lat_ll, lon_ll)
            else:
                self._make_nodata_geotiff(tif_path, lat_ll, lon_ll)

        return tif_path

    def download(
        self,
        bbox: BBox,
        out_tif: Union[str, Path],
        verbose: bool = True,
        max_workers: int = 4,
    ) -> Path:
        """
        Télécharge un MNT SRTM (~30 m) pour une emprise (EPSG:4326),
        sans clé API, via Skadi.

        Paramètres
        ----------
        bbox : (west, south, east, north) ou GeoDataFrame.
               Si west > east, la bbox est automatiquement découpée
               en deux parties de part et d'autre de l'antiméridien.
        out_tif : chemin du GeoTIFF final (mosaïque + clip bbox).
        verbose : si True, affiche une barre de progression tqdm.
        max_workers : nombre de threads pour le téléchargement parallèle.
                      Mettre 1 pour un téléchargement séquentiel.

        Retour
        ------
        Path vers le GeoTIFF final.
        """
        if isinstance(bbox, gpd.GeoDataFrame):
            bbox = tuple(bbox.total_bounds)

        west, south, east, north = bbox
        sub_bboxes = self._split_antimeridian_bbox(bbox)
        for sb in sub_bboxes:
            self._validate_bbox(sb)

        out_tif = Path(out_tif)

        # Collecter toutes les tuiles de toutes les sous-bbox
        all_tiles: List[Tuple[int, int]] = []
        for sb in sub_bboxes:
            all_tiles.extend(self._iter_degree_tiles_for_bbox(sb))
        all_tiles = list(dict.fromkeys(all_tiles))

        # F5 + P1 : téléchargement parallèle
        tile_tifs: List[Path] = []
        n_workers = max(1, min(max_workers, len(all_tiles)))

        if n_workers == 1:
            # Séquentiel (rétrocompatibilité / debug)
            iterator = (
                tqdm(all_tiles, desc="Téléchargement DEM", unit="tuile")
                if verbose else all_tiles
            )
            for lat_ll, lon_ll in iterator:
                tile_tifs.append(self._download_and_convert_tile(lat_ll, lon_ll))
        else:
            # Parallèle
            futures = {}
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                for lat_ll, lon_ll in all_tiles:
                    fut = pool.submit(self._download_and_convert_tile, lat_ll, lon_ll)
                    futures[fut] = (lat_ll, lon_ll)

                pbar = tqdm(
                    total=len(futures), desc="Téléchargement DEM", unit="tuile",
                    disable=not verbose,
                )
                for fut in as_completed(futures):
                    fut.result()  # propage les exceptions
                    pbar.update(1)
                pbar.close()

            # Reconstituer l'ordre des tuiles (important pour la mosaïque)
            for lat_ll, lon_ll in all_tiles:
                tif_path = self.tif_dir / f"{self._lat_code(lat_ll)}{self._lon_code(lon_ll)}.tif"
                tile_tifs.append(tif_path)

        # P2 : mosaïque — rio_merge accepte des datasets ouverts,
        # on les ferme proprement via ExitStack
        with ExitStack() as stack:
            srcs = [stack.enter_context(rasterio.open(p)) for p in tile_tifs]
            mosaic, mosaic_transform = rio_merge(srcs)
            mosaic = mosaic[0]  # bande 1
            crs = srcs[0].crs

        # Découpage bbox — pour l'antiméridien on utilise la bbox englobante
        # de la mosaïque (qui couvre déjà les bonnes tuiles) puis on clip
        # normalement sur chaque sous-bbox.
        if len(sub_bboxes) == 1:
            clip_bounds = sub_bboxes[0]
        else:
            # Antiméridien : on clip sur l'emprise totale de la mosaïque
            clip_bounds = (
                min(sb[0] for sb in sub_bboxes),
                south,
                max(sb[2] for sb in sub_bboxes),
                north,
            )

        cw, cs, ce, cn = clip_bounds
        window = from_bounds(cw, cs, ce, cn, transform=mosaic_transform)
        row_off = max(0, int(math.floor(window.row_off)))
        col_off = max(0, int(math.floor(window.col_off)))
        row_end = min(mosaic.shape[0], int(math.ceil(window.row_off + window.height)))
        col_end = min(mosaic.shape[1], int(math.ceil(window.col_off + window.width)))

        if row_end <= row_off or col_end <= col_off:
            raise DEMDownloadError("Fenêtre de découpe invalide pour la bbox demandée.")

        height, width = row_end - row_off, col_end - col_off
        clipped = mosaic[row_off: row_off + height, col_off: col_off + width]

        new_transform = mosaic_transform * Affine.translation(col_off, row_off)

        profile = {
            "driver": "GTiff",
            "height": clipped.shape[0],
            "width": clipped.shape[1],
            "count": 1,
            "dtype": clipped.dtype,
            "crs": crs,
            "transform": new_transform,
            "compress": "deflate",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256,
            "nodata": -32768,
        }

        out_tif.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_tif, "w", **profile) as dst:
            dst.write(clipped, 1)

        self._cleanup()
        return out_tif

    # -----------------------
    # Analyse & visualisation
    # -----------------------

    @staticmethod
    def info(tif_path: Union[str, Path]) -> dict:
        """
        Affiche et retourne les métadonnées d'un GeoTIFF MNT.

        Paramètres
        ----------
        tif_path : chemin vers un GeoTIFF.

        Retour
        ------
        dict avec clés : crs, transform, resolution, bounds, shape, nodata,
                         dtype, stats (min, max, mean, std).
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            arr = ds.read(1, masked=True)
            res_x, res_y = ds.res
            meta = {
                "chemin": str(tif_path),
                "crs": str(ds.crs),
                "transform": ds.transform,
                "résolution": (res_x, abs(res_y)),
                "emprise": ds.bounds,
                "dimensions": (ds.height, ds.width),
                "nodata": ds.nodata,
                "dtype": str(ds.dtypes[0]),
                "stats": {
                    "min": float(arr.min()) if arr.count() > 0 else None,
                    "max": float(arr.max()) if arr.count() > 0 else None,
                    "moyenne": float(arr.mean()) if arr.count() > 0 else None,
                    "écart-type": float(arr.std()) if arr.count() > 0 else None,
                },
            }
        # Affichage lisible
        print(f"── Informations MNT : {tif_path.name} ──")
        print(f"  CRS           : {meta['crs']}")
        print(f"  Dimensions    : {meta['dimensions'][0]} × {meta['dimensions'][1]} pixels")
        print(f"  Résolution    : {meta['résolution'][0]:.6f}° × {meta['résolution'][1]:.6f}°")
        print(f"  Emprise       : {meta['emprise']}")
        print(f"  Nodata        : {meta['nodata']}")
        stats = meta["stats"]
        if stats["min"] is not None:
            print(f"  Altitude      : {stats['min']:.1f} m → {stats['max']:.1f} m "
                  f"(moy. {stats['moyenne']:.1f} m, σ {stats['écart-type']:.1f} m)")
        return meta

    @staticmethod
    def hillshade(
        tif_path: Union[str, Path],
        out_path: Optional[Union[str, Path]] = None,
        azimuth: float = 315.0,
        altitude: float = 45.0,
    ) -> np.ndarray:
        """
        Calcule un ombrage (hillshade) à partir d'un GeoTIFF MNT.

        Paramètres
        ----------
        tif_path  : chemin vers le GeoTIFF source.
        out_path  : si fourni, sauvegarde le hillshade en GeoTIFF.
        azimuth   : azimut solaire en degrés (défaut 315 = nord-ouest).
        altitude  : élévation solaire en degrés (défaut 45).

        Retour
        ------
        ndarray (float32) du hillshade (0–255).
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            transform = ds.transform
            profile = ds.profile.copy()

        # Masquer nodata
        if nodata is not None:
            elev[elev == nodata] = np.nan

        # Résolution en mètres (approximation pour EPSG:4326)
        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)
        # Conversion deg → m (approximation latitude moyenne)
        lat_center = transform.f - (elev.shape[0] / 2) * cellsize_y
        m_per_deg = 111_320 * math.cos(math.radians(lat_center))
        dx = cellsize_x * m_per_deg
        dy = cellsize_y * m_per_deg

        # Gradients
        dzdx = (
            np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)
        ) / (2 * dx)
        dzdy = (
            np.roll(elev, 1, axis=0) - np.roll(elev, -1, axis=0)
        ) / (2 * dy)

        # Angles solaires
        az_rad = math.radians(360 - azimuth + 90)
        alt_rad = math.radians(altitude)

        slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        aspect_rad = np.arctan2(-dzdy, dzdx)

        hs = (
            np.sin(alt_rad) * np.cos(slope_rad)
            + np.cos(alt_rad) * np.sin(slope_rad)
            * np.cos(az_rad - aspect_rad)
        )
        hs = np.clip(hs * 255, 0, 255).astype(np.float32)
        hs = np.nan_to_num(hs, nan=0.0)

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            profile.update(dtype="float32", count=1, nodata=0, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(hs, 1)

        return hs

    @staticmethod
    def slope(
        tif_path: Union[str, Path],
        out_path: Optional[Union[str, Path]] = None,
        degrees: bool = True,
    ) -> np.ndarray:
        """
        Calcule la pente à partir d'un GeoTIFF MNT.

        Paramètres
        ----------
        tif_path : chemin vers le GeoTIFF source.
        out_path : si fourni, sauvegarde en GeoTIFF.
        degrees  : si True, retourne en degrés ; sinon en radians.

        Retour
        ------
        ndarray (float32) de la pente.
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            transform = ds.transform
            profile = ds.profile.copy()

        if nodata is not None:
            elev[elev == nodata] = np.nan

        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)
        lat_center = transform.f - (elev.shape[0] / 2) * cellsize_y
        m_per_deg = 111_320 * math.cos(math.radians(lat_center))
        dx = cellsize_x * m_per_deg
        dy = cellsize_y * m_per_deg

        dzdx = (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)) / (2 * dx)
        dzdy = (np.roll(elev, 1, axis=0) - np.roll(elev, -1, axis=0)) / (2 * dy)

        slp = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
        if degrees:
            slp = np.degrees(slp)
        slp = np.nan_to_num(slp, nan=0.0).astype(np.float32)

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            profile.update(dtype="float32", count=1, nodata=0, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(slp, 1)

        return slp

    @staticmethod
    def aspect(
        tif_path: Union[str, Path],
        out_path: Optional[Union[str, Path]] = None,
    ) -> np.ndarray:
        """
        Calcule l'orientation (aspect) à partir d'un GeoTIFF MNT.

        Paramètres
        ----------
        tif_path : chemin vers le GeoTIFF source.
        out_path : si fourni, sauvegarde en GeoTIFF.

        Retour
        ------
        ndarray (float32) de l'orientation en degrés (0–360, 0 = nord, sens horaire).
        """
        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            transform = ds.transform
            profile = ds.profile.copy()

        if nodata is not None:
            elev[elev == nodata] = np.nan

        cellsize_x = abs(transform.a)
        cellsize_y = abs(transform.e)
        lat_center = transform.f - (elev.shape[0] / 2) * cellsize_y
        m_per_deg = 111_320 * math.cos(math.radians(lat_center))
        dx = cellsize_x * m_per_deg
        dy = cellsize_y * m_per_deg

        dzdx = (np.roll(elev, -1, axis=1) - np.roll(elev, 1, axis=1)) / (2 * dx)
        dzdy = (np.roll(elev, 1, axis=0) - np.roll(elev, -1, axis=0)) / (2 * dy)

        # Convention : 0 = nord, 90 = est, 180 = sud, 270 = ouest
        asp = np.degrees(np.arctan2(-dzdx, dzdy))
        asp = np.where(asp < 0, asp + 360, asp)
        asp = np.nan_to_num(asp, nan=-1.0).astype(np.float32)

        if out_path is not None:
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            profile.update(dtype="float32", count=1, nodata=-1, compress="deflate")
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(asp, 1)

        return asp

    @staticmethod
    def plot(
        tif_path: Union[str, Path],
        cmap: str = "terrain",
        title: Optional[str] = None,
        figsize: Tuple[int, int] = (10, 8),
        hillshade_alpha: float = 0.35,
        colorbar: bool = True,
    ) -> None:
        """
        Affiche un aperçu rapide du MNT avec ombrage superposé.

        Paramètres
        ----------
        tif_path        : chemin vers le GeoTIFF.
        cmap            : palette de couleurs matplotlib (défaut 'terrain').
        title           : titre optionnel de la figure.
        figsize         : taille de la figure (largeur, hauteur).
        hillshade_alpha : transparence de l'ombrage (0 = invisible, 1 = opaque).
        colorbar        : si True, ajoute une barre de couleurs.
        """
        import matplotlib.pyplot as plt

        tif_path = Path(tif_path)
        with rasterio.open(tif_path) as ds:
            elev = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            bounds = ds.bounds

        if nodata is not None:
            elev[elev == nodata] = np.nan

        hs = DEM.hillshade(tif_path)

        extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

        fig, ax = plt.subplots(1, 1, figsize=figsize)
        im = ax.imshow(
            elev, cmap=cmap, extent=extent, origin="upper", aspect="auto",
        )
        ax.imshow(
            hs, cmap="gray", extent=extent, origin="upper",
            alpha=hillshade_alpha, aspect="auto",
        )
        if colorbar:
            cbar = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
            cbar.set_label("Altitude (m)")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        if title:
            ax.set_title(title)
        else:
            ax.set_title(f"MNT — {tif_path.name}")
        plt.tight_layout()
        plt.show()

    @staticmethod
    def reproject(
        tif_path: Union[str, Path],
        out_path: Union[str, Path],
        dst_crs: str = "EPSG:3857",
        resampling: str = "bilinear",
    ) -> Path:
        """
        Reprojette un GeoTIFF MNT vers un autre CRS.

        Paramètres
        ----------
        tif_path   : chemin vers le GeoTIFF source (EPSG:4326).
        out_path   : chemin du GeoTIFF reprojeté.
        dst_crs    : CRS cible (défaut 'EPSG:3857').
        resampling : méthode de rééchantillonnage ('nearest', 'bilinear',
                     'cubic', 'lanczos'…). Défaut 'bilinear'.

        Retour
        ------
        Path vers le GeoTIFF reprojeté.
        """
        resampling_methods = {
            "nearest": Resampling.nearest,
            "bilinear": Resampling.bilinear,
            "cubic": Resampling.cubic,
            "lanczos": Resampling.lanczos,
        }
        if resampling not in resampling_methods:
            raise ValueError(
                f"Méthode de rééchantillonnage inconnue : '{resampling}'. "
                f"Valeurs possibles : {list(resampling_methods.keys())}"
            )

        tif_path = Path(tif_path)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(tif_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds,
            )
            profile = src.profile.copy()
            profile.update(
                crs=dst_crs,
                transform=transform,
                width=width,
                height=height,
                compress="deflate",
                predictor=2,
                tiled=True,
                blockxsize=256,
                blockysize=256,
            )

            with rasterio.open(out_path, "w", **profile) as dst:
                for band in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band),
                        destination=rasterio.band(dst, band),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=resampling_methods[resampling],
                    )
        return out_path


