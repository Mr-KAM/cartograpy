from __future__ import annotations

import pandas as pd
import geopandas as gpd
import requests
import zipfile
import io
import os
import glob
import logging

logger = logging.getLogger(__name__)


class Hydro :
    def __init__(self,output_dir="data/hydro"):
        
        self.output_dir=output_dir
        self.valid_regions=['af', 'as', 'au', 'eu', 'na', 'sa']


    def download(self,region: str, output_dir: str = "hydrorivers_data") -> gpd.GeoDataFrame:
        """
        Downloads and loads the HydroRIVERS data for a given region.

        Parameters:
            region (str): Region code (e.g. 'af', 'as', 'eu', 'na', 'sa', 'au').
            output_dir (str): Local folder where the files will be extracted.

        Returns:
            gpd.GeoDataFrame: The HydroRIVERS data as a GeoDataFrame.
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
            try:
                response = requests.get(url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(region_dir)
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Erreur lors du téléchargement : {e}")

        # Load the shapefile

        shapefile_path = os.path.join(region_dir, f'HydroRIVERS_v10_{region}_shp', f'HydroRIVERS_v10_{region}.shp')
        if not os.path.exists(shapefile_path):
            raise FileNotFoundError(f"Fichier {shapefile_path} introuvable après extraction.")

        rivers = gpd.read_file(shapefile_path)
        self.rivers_data = rivers
        return rivers
    
    def rivers(self, region: str, resolution: int = 15, output_dir: str = "hydrorivers_data") -> gpd.GeoDataFrame:
        """
        Downloads and loads the HydroSHEDS basins for a given region.

        Parameters:
            region (str): Region code (e.g. 'af', 'as', 'eu', 'na', 'sa', 'au').
            resolution (int): Data resolution, 15 or 30 (arc-seconds).
            output_dir (str): Local folder where the files will be extracted.

        Returns:
            gpd.GeoDataFrame: The basins data as a GeoDataFrame.
        """
        if resolution not in (15, 30):
            raise ValueError("La résolution doit être 15 ou 30.")

        region = region.lower()
        valid_regions = self.valid_regions

        if region not in valid_regions:
            raise ValueError(f"Région invalide. Utilisez l’un de ces codes : {valid_regions}")

        url = (
            f"https://data.hydrosheds.org/file/hydrosheds-v1-archive/SHP/"
            f"bas_{resolution}s_shp/{region}_bas_{resolution}s_beta.zip"
        )
        region_dir = os.path.join(output_dir, f"{region}_bas_{resolution}s")

        if not os.path.exists(region_dir):
            os.makedirs(region_dir, exist_ok=True)
            try:
                response = requests.get(url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(region_dir)
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Erreur lors du téléchargement : {e}")

        shapefiles = glob.glob(os.path.join(region_dir, "**", "*.shp"), recursive=True)
        if not shapefiles:
            raise FileNotFoundError(f"Aucun fichier .shp trouvé dans {region_dir} après extraction.")

        basins = gpd.read_file(shapefiles[0])
        self.basins_data = basins
        return basins

    def basins(self, region: str, level: str = "01", output_dir: str = "hydrorivers_data") -> gpd.GeoDataFrame:
        """
        Downloads and loads the HydroBASINS watersheds for a given region.

        Parameters:
            region (str): Region code (e.g. 'af', 'as', 'eu', 'na', 'sa', 'au').
            level (str): Basin delineation level, from "01" to "12".
            output_dir (str): Local folder where the files will be extracted.

        Returns:
            gpd.GeoDataFrame: The watershed data as a GeoDataFrame.
        """
        try:
            level_int = int(level)
        except (TypeError, ValueError):
            raise ValueError("Le niveau doit être un nombre entre 01 et 12.")
        if not 1 <= level_int <= 12:
            raise ValueError("Le niveau doit être compris entre 01 et 12.")
        level = f"{level_int:02d}"

        region = region.lower()
        valid_regions = self.valid_regions

        if region not in valid_regions:
            raise ValueError(f"Région invalide. Utilisez l’un de ces codes : {valid_regions}")

        url = f"https://data.hydrosheds.org/file/HydroBASINS/standard/hybas_{region}_lev{level}_v1c.zip"
        region_dir = os.path.join(output_dir, f"{region}_hybas_lev{level}")

        if not os.path.exists(region_dir):
            os.makedirs(region_dir, exist_ok=True)
            try:
                response = requests.get(url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(region_dir)
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Erreur lors du téléchargement : {e}")

        shapefiles = glob.glob(os.path.join(region_dir, "**", "*.shp"), recursive=True)
        if not shapefiles:
            raise FileNotFoundError(f"Aucun fichier .shp trouvé dans {region_dir} après extraction.")

        basins = gpd.read_file(shapefiles[0])
        self.hydrobasins_data = basins
        return basins

    def sources(self) -> pd.DataFrame:
        """
        Returns a table of the data sources used by this class.

        Returns:
            pd.DataFrame: Columns 'name', 'url', 'description'.
        """
        return pd.DataFrame([
            {
                "name": "HydroRIVERS",
                "url": "https://www.hydrosheds.org/products/hydrorivers",
                "description": "Global river network (used by download()).",
            },
            {
                "name": "HydroSHEDS - basins (v1 archive)",
                "url": "https://www.hydrosheds.org/hydrosheds-core-downloads",
                "description": "Hydrographic basins, beta archive (used by rivers()).",
            },
            {
                "name": "HydroBASINS",
                "url": "https://www.hydrosheds.org/products/hydrobasins",
                "description": "Hierarchical watersheds by level (used by basins()).",
            },
        ])

    def describe_variables(self) -> str:
        """
        Returns a text description of the main variables in the HydroRIVERS data.
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
