import os
import shutil
import glob
from pathlib import Path

from pyproj import CRS
from pyproj.database import query_crs_info
import rasterio
from cartograpy.data import load as _load_data, save


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

# Familles de fichiers multi-composants (sidecars)
SHAPEFILE_SIDECARS = {".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix"}
TAB_SIDECARS = {".dat", ".map", ".id"}


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

    def add_data(self, data, file_extension=None, filename="output", timestamp=False, raster_meta=None):
        """
        Ajoute des données dans le dossier data du projet.

        Utilise la fonction save() de cartograpy.data pour sauvegarder
        les données directement dans le dossier data du projet.
        Si data est un chemin vers un fichier existant, le fichier est copié
        directement dans le dossier data du projet.

        Args:
            data: Données à sauvegarder (GeoDataFrame, DataFrame, DatasetReader,
                  numpy array) ou chemin (str/Path) vers un fichier existant.
            file_extension: Extension du fichier de sortie (ex: 'geojson', 'shp', 'tif').
                            Optionnel si data est un chemin (l'extension est déduite).
            filename: Nom de base du fichier (sans extension). Par défaut "output".
            timestamp: Si True, ajoute un horodatage au nom. Par défaut False.
            raster_meta: Métadonnées raster si data est un numpy array.

        Returns:
            str: Chemin absolu vers le fichier sauvegardé ou copié.
        """
        os.makedirs(self.data_dir, exist_ok=True)

        # Si data est un chemin vers un fichier existant, le copier
        if isinstance(data, (str, os.PathLike)):
            src = os.path.abspath(str(data))
            if not os.path.isfile(src):
                raise FileNotFoundError(f"Fichier introuvable : {src}")

            # Déduire le nom et l'extension depuis le fichier source
            src_basename = os.path.basename(src)
            src_name, src_ext = os.path.splitext(src_basename)

            if filename == "output":
                filename = src_name
            if file_extension is None:
                file_extension = src_ext.lstrip(".")

            dest_name = f"{filename}.{file_extension}"
            dest = os.path.join(self.data_dir, dest_name)
            shutil.copy2(src, dest)

            # Copier les fichiers secondaires (sidecars) pour les formats multi-fichiers
            copied_sidecars = []
            if src_ext.lower() == ".shp":
                sidecars = SHAPEFILE_SIDECARS
            elif src_ext.lower() == ".tab":
                sidecars = TAB_SIDECARS
            else:
                sidecars = set()

            src_dir = os.path.dirname(src)
            for sidecar_ext in sidecars:
                sidecar_src = os.path.join(src_dir, src_name + sidecar_ext)
                if os.path.isfile(sidecar_src):
                    sidecar_dest = os.path.join(self.data_dir, f"{filename}{sidecar_ext}")
                    shutil.copy2(sidecar_src, sidecar_dest)
                    copied_sidecars.append(sidecar_ext)

            if copied_sidecars:
                print(f"✅ Données copiées : {dest} (+ {', '.join(copied_sidecars)})")
            else:
                print(f"✅ Données copiées : {dest}")
            return dest

        if file_extension is None:
            raise ValueError("file_extension est requis quand data n'est pas un chemin de fichier.")

        # Réouvrir le DatasetReader s'il est fermé
        if isinstance(data, rasterio.io.DatasetReader) and data.closed:
            data = rasterio.open(data.name)

        filepath = os.path.join(self.data_dir, filename)
        result = save(data, file_extension, filename=filepath, timestamp=timestamp, raster_meta=raster_meta)
        print(f"✅ Données ajoutées : {result}")
        return result

    def infos(self):
        """
        Affiche un résumé du projet : chemins, CRS et inventaire des fichiers.

        Returns:
            dict: Dictionnaire contenant les informations du projet.
        """
        data_exists = os.path.isdir(self.data_dir)
        output_exists = os.path.isdir(self.output_dir)

        # Compter les fichiers par catégorie dans data_dir
        vector_count = 0
        raster_count = 0
        tabular_count = 0
        other_count = 0

        if data_exists:
            for root, _dirs, files in os.walk(self.data_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in VECTOR_EXTENSIONS:
                        vector_count += 1
                    elif ext in RASTER_EXTENSIONS:
                        raster_count += 1
                    elif ext in TABULAR_EXTENSIONS:
                        tabular_count += 1
                    else:
                        other_count += 1

        total = vector_count + raster_count + tabular_count + other_count

        # Compter les fichiers dans output_dir
        output_count = 0
        if output_exists:
            for _root, _dirs, files in os.walk(self.output_dir):
                output_count += len(files)

        info = {
            "path": self.path,
            "crs": str(self.crs),
            "data_dir": self.data_dir,
            "output_dir": self.output_dir,
            "data_exists": data_exists,
            "output_exists": output_exists,
            "vector_files": vector_count,
            "raster_files": raster_count,
            "tabular_files": tabular_count,
            "other_files": other_count,
            "total_data_files": total,
            "output_files": output_count,
        }

        print(f"📋 Projet : {self.path}")
        print(f"   🌐 CRS : {self.crs}")
        print(f"   📁 data/   : {'✅' if data_exists else '❌'} ({total} fichier(s))")
        if total > 0:
            print(f"      ├── vectoriel : {vector_count}")
            print(f"      ├── raster    : {raster_count}")
            print(f"      ├── tabulaire : {tabular_count}")
            print(f"      └── autre     : {other_count}")
        print(f"   📁 output/ : {'✅' if output_exists else '❌'} ({output_count} fichier(s))")

        return info

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

    def list_data(self, type_filter=None):
        """
        Liste les fichiers présents dans le dossier data du projet.

        Args:
            type_filter: Filtrer par type ("vector", "raster", "tabular").
                         None pour tout retourner.

        Returns:
            list[dict]: Liste de fichiers avec name, extension, type, size, path.
        """
        if not os.path.isdir(self.data_dir):
            return []

        results = []
        for root, _dirs, files in os.walk(self.data_dir):
            for f in files:
                full_path = os.path.join(root, f)
                name, ext = os.path.splitext(f)
                ext_lower = ext.lower()

                if ext_lower in VECTOR_EXTENSIONS:
                    ftype = "vector"
                elif ext_lower in RASTER_EXTENSIONS:
                    ftype = "raster"
                elif ext_lower in TABULAR_EXTENSIONS:
                    ftype = "tabular"
                else:
                    ftype = "other"

                if type_filter and ftype != type_filter:
                    continue

                results.append({
                    "name": name,
                    "extension": ext_lower,
                    "type": ftype,
                    "size": os.path.getsize(full_path),
                    "path": full_path,
                    "relative_path": os.path.relpath(full_path, self.data_dir),
                })

        return results

    def load_data(self, name, layer=None):
        """
        Charge un fichier depuis le dossier data du projet.

        Args:
            name: Nom du fichier (avec ou sans extension) ou chemin relatif
                  dans le dossier data.
            layer: Couche à charger pour les fichiers multi-couches (ex: GPX).

        Returns:
            GeoDataFrame, DataFrame ou DatasetReader selon le type de fichier.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas dans le dossier data.
        """
        # Chemin direct
        candidate = os.path.join(self.data_dir, name)
        if os.path.isfile(candidate):
            return _load_data(candidate, layer=layer)

        # Recherche récursive
        if not os.path.isdir(self.data_dir):
            raise FileNotFoundError(f"Le dossier data n'existe pas : {self.data_dir}")

        for root, _dirs, files in os.walk(self.data_dir):
            for f in files:
                if f == name or os.path.splitext(f)[0] == name:
                    return _load_data(os.path.join(root, f), layer=layer)

        raise FileNotFoundError(
            f"Fichier '{name}' introuvable dans {self.data_dir}"
        )

    def remove_data(self, name):
        """
        Supprime un fichier (et ses sidecars) du dossier data du projet.

        Args:
            name: Nom du fichier (avec extension) à supprimer.

        Returns:
            list[str]: Liste des fichiers supprimés.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
        """
        target = None
        for root, _dirs, files in os.walk(self.data_dir):
            if name in files:
                target = os.path.join(root, name)
                break

        if target is None:
            raise FileNotFoundError(f"Fichier '{name}' introuvable dans {self.data_dir}")

        removed = []
        base_name, ext = os.path.splitext(name)
        target_dir = os.path.dirname(target)

        # Déterminer les sidecars à supprimer
        if ext.lower() == ".shp":
            sidecars = SHAPEFILE_SIDECARS
        elif ext.lower() == ".tab":
            sidecars = TAB_SIDECARS
        else:
            sidecars = set()

        # Supprimer le fichier principal
        os.remove(target)
        removed.append(target)

        # Supprimer les sidecars
        for sidecar_ext in sidecars:
            sidecar_path = os.path.join(target_dir, base_name + sidecar_ext)
            if os.path.isfile(sidecar_path):
                os.remove(sidecar_path)
                removed.append(sidecar_path)

        print(f"🗑️ {len(removed)} fichier(s) supprimé(s) : {name}"
              + (" (+ sidecars)" if len(removed) > 1 else ""))
        return removed

    def get_path(self, name, folder="data"):
        """
        Retourne le chemin absolu d'un fichier dans le projet.

        Args:
            name: Nom du fichier ou chemin relatif.
            folder: "data" ou "output". Par défaut "data".

        Returns:
            str: Chemin absolu du fichier.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
        """
        base = self.data_dir if folder == "data" else self.output_dir

        # Chemin direct
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate):
            return candidate

        # Recherche récursive
        if os.path.isdir(base):
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if f == name or os.path.splitext(f)[0] == name:
                        return os.path.join(root, f)

        raise FileNotFoundError(f"Fichier '{name}' introuvable dans {base}")

    def set_crs(self, crs):
        """
        Change le CRS du projet.

        Args:
            crs: Nouveau CRS (code EPSG, chaîne WKT, etc.).

        Returns:
            pyproj.CRS: Le nouveau CRS.
        """
        self.crs = CRS.from_user_input(crs)
        print(f"🌐 CRS mis à jour : {self.crs}")
        return self.crs

    def clean_output(self):
        """
        Supprime tous les fichiers du dossier output.

        Returns:
            int: Nombre de fichiers supprimés.
        """
        if not os.path.isdir(self.output_dir):
            print("📁 Le dossier output n'existe pas.")
            return 0

        count = 0
        for root, dirs, files in os.walk(self.output_dir, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
                count += 1
            for d in dirs:
                os.rmdir(os.path.join(root, d))

        print(f"🧹 {count} fichier(s) supprimé(s) du dossier output.")
        return count

    def validate(self):
        """
        Vérifie l'intégrité du projet : existence des dossiers, lisibilité
        des fichiers et cohérence des sidecars shapefile.

        Returns:
            dict: Rapport de validation avec les statuts et éventuels avertissements.
        """
        report = {
            "valid": True,
            "data_dir_exists": os.path.isdir(self.data_dir),
            "output_dir_exists": os.path.isdir(self.output_dir),
            "warnings": [],
            "errors": [],
        }

        if not report["data_dir_exists"]:
            report["errors"].append(f"Dossier data introuvable : {self.data_dir}")
            report["valid"] = False

        if not report["output_dir_exists"]:
            report["warnings"].append(f"Dossier output introuvable : {self.output_dir}")

        # Vérifier les fichiers dans data_dir
        if report["data_dir_exists"]:
            for root, _dirs, files in os.walk(self.data_dir):
                shp_basenames = set()
                all_files = set(files)

                for f in files:
                    full_path = os.path.join(root, f)

                    # Vérifier la lisibilité
                    if not os.access(full_path, os.R_OK):
                        report["warnings"].append(f"Fichier non lisible : {full_path}")

                    name, ext = os.path.splitext(f)
                    if ext.lower() == ".shp":
                        shp_basenames.add(name)

                # Vérifier les sidecars obligatoires pour chaque shapefile
                for basename in shp_basenames:
                    for required_ext in (".shx", ".dbf"):
                        if basename + required_ext not in all_files:
                            report["warnings"].append(
                                f"Sidecar manquant : {basename}{required_ext} "
                                f"(requis pour {basename}.shp)"
                            )

        status = "✅ valide" if report["valid"] else "❌ invalide"
        print(f"🔍 Validation du projet : {status}")
        for w in report["warnings"]:
            print(f"   ⚠️ {w}")
        for e in report["errors"]:
            print(f"   ❌ {e}")
        if not report["warnings"] and not report["errors"]:
            print("   Aucun problème détecté.")

        return report


def init_project(path=None):
    """Raccourci pour créer et initialiser un projet rapidement."""
    project = Project(path)
    return project.init()