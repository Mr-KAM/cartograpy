"""
Geocoder - Classe pour le géocodage de lieux
Permet de convertir des adresses en coordonnées géographiques et vice versa
"""

from typing import List, Union, Dict, Optional, Tuple
import requests
import time
from dataclasses import dataclass
from abc import ABC, abstractmethod
from requests_cache import CachedSession
import json


@dataclass
class GeocodingResult:
    """Résultat d'un géocodage"""
    query: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    display_name: Optional[str] = None
    address: Optional[Dict] = None
    confidence: Optional[float] = None
    place_id: Optional[str] = None
    bbox: Optional[List[float]] = None
    error: Optional[str] = None
    
    @property
    def coordinates(self) -> Optional[Tuple[float, float]]:
        """Retourne les coordonnées sous forme de tuple (lat, lon)"""
        if self.latitude is not None and self.longitude is not None:
            return (self.latitude, self.longitude)
        return None
    
    @property
    def is_valid(self) -> bool:
        """Vérifie si le géocodage a réussi"""
        return self.error is None and self.coordinates is not None


class GeocodingProvider(ABC):
    """Interface abstraite pour les fournisseurs de géocodage"""
    
    @abstractmethod
    def geocode(self, query: str) -> GeocodingResult:
        """Géocode une adresse"""
        pass
    
    @abstractmethod
    def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """Géocodage inverse (coordonnées vers adresse)"""
        pass


class NominatimProvider(GeocodingProvider):
    """Fournisseur de géocodage utilisant Nominatim (OpenStreetMap)"""
    
    def __init__(self, user_agent: str = "GeocodeClient/1.0", timeout: int = 10):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.user_agent = user_agent
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
    
    def geocode(self, query: str) -> GeocodingResult:
        """Géocode une adresse avec Nominatim"""
        try:
            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            response = self.session.get(
                f"{self.base_url}/search",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return GeocodingResult(
                    query=query,
                    error="Aucun résultat trouvé"
                )
            
            result = data[0]
            
            return GeocodingResult(
                query=query,
                latitude=float(result['lat']),
                longitude=float(result['lon']),
                display_name=result.get('display_name'),
                address=result.get('address'),
                confidence=float(result.get('importance', 0)),
                place_id=result.get('place_id'),
                bbox=[float(x) for x in result.get('boundingbox', [])] if result.get('boundingbox') else None
            )
            
        except Exception as e:
            return GeocodingResult(
                query=query,
                error=f"Erreur lors du géocodage: {str(e)}"
            )
    
    def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """Géocodage inverse avec Nominatim"""
        try:
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1
            }
            
            response = self.session.get(
                f"{self.base_url}/reverse",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                return GeocodingResult(
                    query=f"{lat},{lon}",
                    error=data['error']
                )
            
            return GeocodingResult(
                query=f"{lat},{lon}",
                latitude=lat,
                longitude=lon,
                display_name=data.get('display_name'),
                address=data.get('address'),
                place_id=data.get('place_id')
            )
            
        except Exception as e:
            return GeocodingResult(
                query=f"{lat},{lon}",
                error=f"Erreur lors du géocodage inverse: {str(e)}"
            )


class OpenCageProvider(GeocodingProvider):
    """Fournisseur de géocodage utilisant OpenCage API"""
    
    def __init__(self, api_key: str, timeout: int = 10):
        self.api_key = api_key
        self.base_url = "https://api.opencagedata.com/geocode/v1/json"
        self.timeout = timeout
        self.session = requests.Session()
    
    def geocode(self, query: str) -> GeocodingResult:
        """Géocode une adresse avec OpenCage"""
        try:
            params = {
                'q': query,
                'key': self.api_key,
                'limit': 1,
                'no_annotations': 0
            }
            
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data['results']:
                return GeocodingResult(
                    query=query,
                    error="Aucun résultat trouvé"
                )
            
            result = data['results'][0]
            geometry = result['geometry']
            
            return GeocodingResult(
                query=query,
                latitude=geometry['lat'],
                longitude=geometry['lng'],
                display_name=result.get('formatted'),
                address=result.get('components'),
                confidence=result.get('confidence', 0) / 10.0,  # Normaliser sur 1
                bbox=result.get('bounds', {}).values() if result.get('bounds') else None
            )
            
        except Exception as e:
            return GeocodingResult(
                query=query,
                error=f"Erreur lors du géocodage: {str(e)}"
            )
    
    def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """Géocodage inverse avec OpenCage"""
        try:
            params = {
                'q': f"{lat},{lon}",
                'key': self.api_key,
                'limit': 1,
                'no_annotations': 0
            }
            
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data['results']:
                return GeocodingResult(
                    query=f"{lat},{lon}",
                    error="Aucun résultat trouvé"
                )
            
            result = data['results'][0]
            
            return GeocodingResult(
                query=f"{lat},{lon}",
                latitude=lat,
                longitude=lon,
                display_name=result.get('formatted'),
                address=result.get('components'),
                confidence=result.get('confidence', 0) / 10.0
            )
            
        except Exception as e:
            return GeocodingResult(
                query=f"{lat},{lon}",
                error=f"Erreur lors du géocodage inverse: {str(e)}"
            )


class Geocoder:
    """
    Classe principale pour le géocodage de lieux.
    Supporte plusieurs fournisseurs et la mise en cache.
    """
    
    def __init__(self, 
                 provider: GeocodingProvider = None,
                 cache_expire_seconds: int = 86400,  # 24 heures
                 rate_limit_delay: float = 1.0):
        """
        Initialise le géocodeur.
        
        Args:
            provider: Fournisseur de géocodage à utiliser (défaut: Nominatim)
            cache_expire_seconds: Durée d'expiration du cache en secondes
            rate_limit_delay: Délai entre les requêtes pour éviter le rate limiting
        """
        self.provider = provider or NominatimProvider()
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.geolocator = Nominatim(user_agent="mon_application_de_geocodage")
        
        # Configuration du cache
        self._session = CachedSession(expire_after=cache_expire_seconds)
    
    def _respect_rate_limit(self):
        """Respecte les limites de taux de requêtes"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        
        self.last_request_time = time.time()
    
    def geocode(self, query: str) -> GeocodingResult:
        """
        Géocode une adresse unique.
        
        Args:
            query: Adresse ou lieu à géocoder
            
        Returns:
            GeocodingResult: Résultat du géocodage
        """
        self._respect_rate_limit()
        return self.provider.geocode(query)
    
    def geocode_batch(self, queries: List[str], 
                     stop_on_error: bool = False,
                     progress_callback: Optional[callable] = None) -> List[GeocodingResult]:
        """
        Géocode une liste d'adresses.
        
        Args:
            queries: Liste d'adresses à géocoder
            stop_on_error: Si True, arrête au premier échec
            progress_callback: Fonction appelée pour chaque résultat (optionnel)
            
        Returns:
            List[GeocodingResult]: Liste des résultats de géocodage
        """
        results = []
        
        for i, query in enumerate(queries):
            result = self.geocode(query)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, len(queries), result)
            
            if stop_on_error and not result.is_valid:
                print(f"Erreur lors du géocodage de '{query}': {result.error}")
                break
        
        return results
    
    def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """
        Géocodage inverse (coordonnées vers adresse).
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            GeocodingResult: Résultat du géocodage inverse
        """
        self._respect_rate_limit()
        return self.provider.reverse_geocode(lat, lon)
    
    def reverse_geocode_batch(self, coordinates: List[Tuple[float, float]],
                             stop_on_error: bool = False,
                             progress_callback: Optional[callable] = None) -> List[GeocodingResult]:
        """
        Géocodage inverse pour une liste de coordonnées.
        
        Args:
            coordinates: Liste de tuples (lat, lon)
            stop_on_error: Si True, arrête au premier échec
            progress_callback: Fonction appelée pour chaque résultat
            
        Returns:
            List[GeocodingResult]: Liste des résultats
        """
        results = []
        
        for i, (lat, lon) in enumerate(coordinates):
            result = self.reverse_geocode(lat, lon)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, len(coordinates), result)
            
            if stop_on_error and not result.is_valid:
                print(f"Erreur lors du géocodage inverse de ({lat}, {lon}): {result.error}")
                break
        
        return results
    
    def clear_cache(self):
        """Vide le cache des requêtes"""
        self._session.cache.clear()
    
    def set_provider(self, provider: GeocodingProvider):
        """Change le fournisseur de géocodage"""
        self.provider = provider
    
    def export_results(self, results: List[GeocodingResult], 
                      filename: str, format: str = 'json'):
        """
        Exporte les résultats vers un fichier.
        
        Args:
            results: Liste des résultats à exporter
            filename: Nom du fichier de sortie
            format: Format d'export ('json', 'csv', 'geojson')
        """
        if format.lower() == 'json':
            self._export_json(results, filename)
        elif format.lower() == 'csv':
            self._export_csv(results, filename)
        elif format.lower() == 'geojson':
            self._export_geojson(results, filename)
        else:
            raise ValueError(f"Format non supporté: {format}")
    
    def _export_json(self, results: List[GeocodingResult], filename: str):
        """Exporte en JSON"""
        data = []
        for result in results:
            data.append({
                'query': result.query,
                'latitude': result.latitude,
                'longitude': result.longitude,
                'display_name': result.display_name,
                'address': result.address,
                'confidence': result.confidence,
                'error': result.error
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _export_csv(self, results: List[GeocodingResult], filename: str):
        """Exporte en CSV"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['query', 'latitude', 'longitude', 'display_name', 'confidence', 'error'])
            
            for result in results:
                writer.writerow([
                    result.query,
                    result.latitude,
                    result.longitude,
                    result.display_name,
                    result.confidence,
                    result.error
                ])
    
    def _export_geojson(self, results: List[GeocodingResult], filename: str):
        """Exporte en GeoJSON"""
        features = []
        
        for result in results:
            if result.is_valid:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [result.longitude, result.latitude]
                    },
                    "properties": {
                        "query": result.query,
                        "display_name": result.display_name,
                        "confidence": result.confidence,
                        "address": result.address
                    }
                }
                features.append(feature)
        
        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, indent=2, ensure_ascii=False)
