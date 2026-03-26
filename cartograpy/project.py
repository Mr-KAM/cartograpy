import os
import shutil
import glob

from pyproj import CRS
from pyproj.database import query_crs_info


VECTOR_EXTENSIONS = {
    ".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix",
    ".geojson", ".gpkg", ".kml", ".kmz", ".gml", ".gpx", ".fgb",
    ".topojson", ".tab", ".dat", ".map", ".id",
}

RASTER_EXTENSIONS = {
    ".tif", ".tiff", ".geotiff", ".img", ".hgt", ".nc", ".grib",
    ".grib2", ".jp2", ".ecw", ".adf", ".dem", ".dt0", ".dt1", ".dt2",
    ".asc", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
}

TABULAR_EXTENSIONS = {
    ".csv", ".tsv", ".xls", ".xlsx", ".ods", ".txt", ".json",
    ".parquet", ".feather", ".dbf",
}


class Project:
    """Gestionnaire de projet cartograpy."""

    def __init__(self, path=None, data_dir="data", output_dir="output", crs="EPSG:4326"):
        """
        Crée un objet Project.

        Args:
            path: Répertoire racine du projet. Si None, utilise le répertoire courant.
            data_dir: Nom du dossier de données (par défaut "data").
            output_dir: Nom du dossier de sortie (par défaut "output").
            crs: Système de coordonnées de référence (par défaut "EPSG:4326" / WGS 84).
        """
        self.path = os.path.abspath(path) if path else os.getcwd()
        self.data_dir = os.path.join(self.path, data_dir)
        self.output_dir = os.path.join(self.path, output_dir)
        self.crs = CRS.from_user_input(crs)

        self.vector_files: list[str] = []
        self.raster_files: list[str] = []
        self.tabular_files: list[str] = []

    def init(self):
        """
        Initialise le projet en créant les dossiers data et output.

        Returns:
            str: Chemin absolu du projet initialisé.
        """
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        print(f"✅ Projet initialisé dans : {self.path}")
        print(f"   📁 {self.data_dir}")
        print(f"   📁 {self.output_dir}")

        return self.path

    @staticmethod
    def available_crs(auth_name="EPSG", crs_type=None, contains=""):
        """
        Liste les CRS disponibles.

        Args:
            auth_name: Autorité (par défaut "EPSG"). Mettre None pour toutes.
            crs_type: Type de CRS à filtrer (ex: "GEOGRAPHIC_2D", "PROJECTED").
                      None pour tous les types.
            contains: Filtre textuel sur le nom du CRS.

        Returns:
            list[dict]: Liste de dictionnaires {code, name, type, area}.
        """
        results = []
        crs_infos = query_crs_info(
            auth_name=auth_name,
            pj_types=crs_type,
            contains=contains,
        )
        for info in crs_infos:
            results.append({
                "authority": info.auth_name,
                "code": info.code,
                "name": info.name,
                "type": info.type.name if hasattr(info.type, "name") else str(info.type),
                "area": info.area_of_use,
            })
        return results

    def organize_project(self):
        """
        Parcourt data_dir, classe chaque fichier dans un sous-dossier
        vector/, raster/ ou tabular/ et met à jour les listes correspondantes.
        """
        vector_dir = os.path.join(self.data_dir, "vector")
        raster_dir = os.path.join(self.data_dir, "raster")
        tabular_dir = os.path.join(self.data_dir, "tabular")

        os.makedirs(vector_dir, exist_ok=True)
        os.makedirs(raster_dir, exist_ok=True)
        os.makedirs(tabular_dir, exist_ok=True)

        for entry in os.listdir(self.data_dir):
            full_path = os.path.join(self.data_dir, entry)
            if not os.path.isfile(full_path):
                continue

            ext = os.path.splitext(entry)[1].lower()

            if ext in VECTOR_EXTENSIONS:
                dest = os.path.join(vector_dir, entry)
                shutil.move(full_path, dest)
            elif ext in RASTER_EXTENSIONS:
                dest = os.path.join(raster_dir, entry)
                shutil.move(full_path, dest)
            elif ext in TABULAR_EXTENSIONS:
                dest = os.path.join(tabular_dir, entry)
                shutil.move(full_path, dest)

        self.vector_files = os.listdir(vector_dir)
        self.raster_files = os.listdir(raster_dir)
        self.tabular_files = os.listdir(tabular_dir)

        print(f"📂 Organisation terminée dans : {self.data_dir}")
        print(f"   vector/  → {len(self.vector_files)} fichier(s)")
        print(f"   raster/  → {len(self.raster_files)} fichier(s)")
        print(f"   tabular/ → {len(self.tabular_files)} fichier(s)")


def init_project(path=None):
    """Raccourci pour créer et initialiser un projet rapidement."""
    project = Project(path)
    return project.init()