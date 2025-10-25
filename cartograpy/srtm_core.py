"""
SRTM Downloader - Module principal
Télécharge des tuiles SRTM depuis les serveurs de la NASA
"""

import os
import math
import time
import requests
from typing import Optional, Tuple
from pathlib import Path
from tqdm import tqdm


class SRTMDownloader:
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
