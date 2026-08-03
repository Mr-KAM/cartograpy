from __future__ import annotations

import geopandas as gpd
import requests
import zipfile
import io
import os
import logging

logger = logging.getLogger(__name__)


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
            logger.info(f"Téléchargement des données HydroRIVERS pour la région : {region.upper()} ...")
            try:
                response = requests.get(url)
                response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    z.extractall(region_dir)
                logger.info("Téléchargement et extraction terminés.")
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Erreur lors du téléchargement : {e}")
        else:
            logger.info(f"Les données pour la région {region.upper()} sont déjà présentes.")

        # Chargement du shapefile
        
        shapefile_path = os.path.join(region_dir, f'HydroRIVERS_v10_{region}_shp', f'HydroRIVERS_v10_{region}.shp')
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
