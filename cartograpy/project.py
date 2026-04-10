import os
import shutil
import glob
import json
from datetime import datetime, timezone
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

# Extensions principales des formats multi-fichiers (celles qu'on charge)
_PRIMARY_EXTENSIONS = {".shp", ".tab"}

# Familles de fichiers multi-composants (sidecars)
SHAPEFILE_SIDECARS = {".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix"}
TAB_SIDECARS = {".dat", ".map", ".id"}

# Toutes les extensions sidecar (jamais des fichiers principaux à charger)
_ALL_SIDECAR_EXTENSIONS = SHAPEFILE_SIDECARS | TAB_SIDECARS


def _classify_extension(ext):
    """Retourne le type ('vector', 'raster', 'tabular', 'other') d'une extension."""
    ext = ext.lower()
    if ext in VECTOR_EXTENSIONS:
        return "vector"
    if ext in RASTER_EXTENSIONS:
        return "raster"
    if ext in TABULAR_EXTENSIONS:
        return "tabular"
    return "other"


def _get_sidecars_for(ext):
    """Retourne le set de sidecars associé à une extension principale."""
    ext = ext.lower()
    if ext == ".shp":
        return SHAPEFILE_SIDECARS
    if ext == ".tab":
        return TAB_SIDECARS
    return set()


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
    def available_crs(auth_name="EPSG", crs_type=None, name_contains=""):
        """
        Liste les CRS disponibles.

        Args:
            auth_name: Autorité (par défaut "EPSG"). Mettre None pour toutes.
            crs_type: Type de CRS à filtrer (ex: "GEOGRAPHIC_2D", "PROJECTED").
                      None pour tous les types.
            name_contains: Filtre textuel sur le nom du CRS (insensible à la casse).

        Returns:
            list[dict]: Liste de dictionnaires {authority, code, name, type, area}.
        """
        results = []
        crs_infos = query_crs_info(
            auth_name=auth_name,
            pj_types=crs_type,
        )
        filter_text = name_contains.lower()
        for info in crs_infos:
            if filter_text and filter_text not in info.name.lower():
                continue
            results.append({
                "authority": info.auth_name,
                "code": info.code,
                "name": info.name,
                "type": info.type.name if hasattr(info.type, "name") else str(info.type),
                "area": info.area_of_use,
            })
        return results

    def add_data(self, data, file_extension=None, filename="output",
                 timestamp=False, raster_meta=None,
                 overwrite=False, mode="copy", category=None):
        """
        Ajoute des données dans le dossier data du projet.

        Args:
            data: Données à sauvegarder (GeoDataFrame, DataFrame, DatasetReader,
                  numpy array) ou chemin (str/Path) vers un fichier existant.
            file_extension: Extension du fichier de sortie (ex: 'geojson', 'shp', 'tif').
                            Optionnel si data est un chemin (l'extension est déduite).
            filename: Nom de base du fichier (sans extension). Par défaut "output".
            timestamp: Si True, ajoute un horodatage au nom. Par défaut False.
            raster_meta: Métadonnées raster si data est un numpy array.
            overwrite: Si True, écrase un fichier existant. Par défaut False.
            mode: "copy" (défaut), "move" ou "link" (lien symbolique).
                  N'a d'effet que si data est un chemin de fichier.
            category: Sous-dossier cible dans data/ ("vector", "raster", "tabular").
                      Si None, écrit directement dans data/.

        Returns:
            str: Chemin absolu vers le fichier sauvegardé ou copié.

        Raises:
            FileNotFoundError: Si data est un chemin et que le fichier n'existe pas.
            FileExistsError: Si le fichier existe déjà et overwrite=False.
            ValueError: Si file_extension manque pour un objet en mémoire
                        ou si mode est invalide.
        """
        target_dir = self.data_dir
        if category:
            target_dir = os.path.join(self.data_dir, category)
        os.makedirs(target_dir, exist_ok=True)

        # Si data est un chemin vers un fichier existant
        if isinstance(data, (str, os.PathLike)):
            src = os.path.abspath(str(data))
            if not os.path.isfile(src):
                raise FileNotFoundError(f"Fichier introuvable : {src}")

            src_basename = os.path.basename(src)
            src_name, src_ext = os.path.splitext(src_basename)

            if filename == "output":
                filename = src_name
            if file_extension is None:
                file_extension = src_ext.lstrip(".")

            dest_name = f"{filename}.{file_extension}"
            dest = os.path.join(target_dir, dest_name)

            if os.path.isfile(dest) and not overwrite:
                raise FileExistsError(
                    f"Le fichier existe déjà : {dest}. "
                    "Utilisez overwrite=True pour écraser."
                )

            _transfer = {
                "copy": shutil.copy2,
                "move": shutil.move,
                "link": os.symlink,
            }
            if mode not in _transfer:
                raise ValueError(f"mode invalide : {mode!r}. Attendu : 'copy', 'move' ou 'link'.")
            transfer_fn = _transfer[mode]
            transfer_fn(src, dest)

            # Transférer les sidecars
            copied_sidecars = []
            sidecars = _get_sidecars_for(src_ext)
            src_dir = os.path.dirname(src)
            for sidecar_ext in sidecars:
                sidecar_src = os.path.join(src_dir, src_name + sidecar_ext)
                if os.path.isfile(sidecar_src):
                    sidecar_dest = os.path.join(target_dir, f"{filename}{sidecar_ext}")
                    transfer_fn(sidecar_src, sidecar_dest)
                    copied_sidecars.append(sidecar_ext)

            verb = {"copy": "copiées", "move": "déplacées", "link": "liées"}[mode]
            if copied_sidecars:
                print(f"✅ Données {verb} : {dest} (+ {', '.join(copied_sidecars)})")
            else:
                print(f"✅ Données {verb} : {dest}")
            return dest

        if file_extension is None:
            raise ValueError("file_extension est requis quand data n'est pas un chemin de fichier.")

        # Réouvrir le DatasetReader s'il est fermé
        if isinstance(data, rasterio.DatasetReader) and data.closed:
            data = rasterio.open(data.name)

        filepath = os.path.join(target_dir, filename)

        expected_dest = f"{filepath}.{file_extension}"
        if os.path.isfile(expected_dest) and not overwrite:
            raise FileExistsError(
                f"Le fichier existe déjà : {expected_dest}. "
                "Utilisez overwrite=True pour écraser."
            )

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

    def _resolve_data(self, name, base_dir=None, strict=True):
        """
        Résout le chemin d'un fichier dans un dossier du projet.

        Cherche par nom exact, puis par nom de base (sans extension).
        Ignore les fichiers sidecar (.shx, .dbf, .prj…) lors d'une
        recherche par nom de base pour éviter les ambiguïtés.

        Args:
            name: Nom du fichier (avec ou sans extension).
            base_dir: Dossier de recherche. Par défaut self.data_dir.
            strict: Si True et que plusieurs fichiers correspondent au
                    nom de base, lève une ValueError.

        Returns:
            str: Chemin absolu vers le fichier trouvé.

        Raises:
            FileNotFoundError: Si aucun fichier ne correspond.
            ValueError: Si strict=True et plusieurs correspondances.
        """
        if base_dir is None:
            base_dir = self.data_dir

        # 1. Chemin direct
        candidate = os.path.join(base_dir, name)
        if os.path.isfile(candidate):
            return candidate

        if not os.path.isdir(base_dir):
            raise FileNotFoundError(f"Dossier introuvable : {base_dir}")

        # 2. Recherche par nom exact
        for root, _dirs, files in os.walk(base_dir):
            for f in files:
                if f == name:
                    return os.path.join(root, f)

        # 3. Recherche par nom de base (ignore les sidecars)
        matches = []
        for root, _dirs, files in os.walk(base_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in _ALL_SIDECAR_EXTENSIONS:
                    continue
                if os.path.splitext(f)[0] == name:
                    matches.append(os.path.join(root, f))

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            if strict:
                raise ValueError(
                    f"Nom ambigu '{name}' : {len(matches)} fichiers correspondent. "
                    f"Précisez l'extension. Fichiers : {matches}"
                )
            return matches[0]

        raise FileNotFoundError(
            f"Fichier '{name}' introuvable dans {base_dir}"
        )

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
                ftype = _classify_extension(ext_lower)

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

    def list_datasets(self, type_filter=None):
        """
        Liste les jeux de données logiques (un shapefile + ses sidecars = 1 entrée).

        Args:
            type_filter: Filtrer par type ("vector", "raster", "tabular").
                         None pour tout retourner.

        Returns:
            list[dict]: Jeux de données avec name, type, main_file, sidecars,
                        total_size, path.
        """
        all_files = self.list_data()
        if not all_files:
            return []

        # Indexer par (répertoire, nom de base)
        groups: dict[tuple[str, str], list[dict]] = {}
        for entry in all_files:
            key = (os.path.dirname(entry["path"]), entry["name"])
            groups.setdefault(key, []).append(entry)

        datasets = []
        seen_keys: set[tuple[str, str]] = set()

        for (dirpath, basename), entries in groups.items():
            if (dirpath, basename) in seen_keys:
                continue

            # Séparer principal / sidecars
            primary = []
            sidecars = []
            for e in entries:
                if e["extension"] in _ALL_SIDECAR_EXTENSIONS:
                    sidecars.append(e)
                else:
                    primary.append(e)

            if not primary:
                # Sidecars orphelins : les rattacher s'il y a un fichier principal
                # avec le même basename dans le même dossier
                continue

            for p in primary:
                ftype = p["type"]
                if type_filter and ftype != type_filter:
                    continue

                ds = {
                    "name": basename,
                    "type": ftype,
                    "main_file": p["path"],
                    "extension": p["extension"],
                    "sidecars": [s["path"] for s in sidecars],
                    "total_size": p["size"] + sum(s["size"] for s in sidecars),
                    "path": dirpath,
                }
                datasets.append(ds)
                seen_keys.add((dirpath, basename))

        return datasets

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
        path = self._resolve_data(name)
        return _load_data(path, layer=layer)

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
        target = self._resolve_data(name)

        removed = []
        base_name, ext = os.path.splitext(os.path.basename(target))
        target_dir = os.path.dirname(target)

        # Supprimer le fichier principal
        os.remove(target)
        removed.append(target)

        # Supprimer les sidecars
        for sidecar_ext in _get_sidecars_for(ext):
            sidecar_path = os.path.join(target_dir, base_name + sidecar_ext)
            if os.path.isfile(sidecar_path):
                os.remove(sidecar_path)
                removed.append(sidecar_path)

        print(f"🗑️ {len(removed)} fichier(s) supprimé(s) : {os.path.basename(target)}"
              + (" (+ sidecars)" if len(removed) > 1 else ""))
        return removed

    def rename_data(self, old, new):
        """
        Renomme un jeu de données (fichier principal + sidecars).

        Args:
            old: Nom actuel du fichier (avec ou sans extension).
            new: Nouveau nom de base (sans extension).

        Returns:
            list[tuple[str, str]]: Paires (ancien chemin, nouveau chemin).

        Raises:
            FileNotFoundError: Si le fichier source n'existe pas.
        """
        target = self._resolve_data(old)
        target_dir = os.path.dirname(target)
        old_base, ext = os.path.splitext(os.path.basename(target))

        renamed = []

        # Renommer le fichier principal
        new_path = os.path.join(target_dir, new + ext)
        os.rename(target, new_path)
        renamed.append((target, new_path))

        # Renommer les sidecars
        for sidecar_ext in _get_sidecars_for(ext):
            sidecar_old = os.path.join(target_dir, old_base + sidecar_ext)
            if os.path.isfile(sidecar_old):
                sidecar_new = os.path.join(target_dir, new + sidecar_ext)
                os.rename(sidecar_old, sidecar_new)
                renamed.append((sidecar_old, sidecar_new))

        print(f"✏️ {len(renamed)} fichier(s) renommé(s) : {old_base} → {new}")
        return renamed

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
        return self._resolve_data(name, base_dir=base)

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

    def save_output(self, data, file_extension, filename="output",
                    timestamp=False, raster_meta=None, overwrite=False):
        """
        Sauvegarde des données dans le dossier output du projet.

        Pendant de add_data mais ciblant output_dir.

        Args:
            data: Données à sauvegarder (GeoDataFrame, DataFrame, DatasetReader,
                  numpy array).
            file_extension: Extension du fichier de sortie.
            filename: Nom de base du fichier (sans extension).
            timestamp: Si True, ajoute un horodatage au nom.
            raster_meta: Métadonnées raster si data est un numpy array.
            overwrite: Si True, écrase un fichier existant.

        Returns:
            str: Chemin absolu vers le fichier sauvegardé.

        Raises:
            FileExistsError: Si le fichier existe déjà et overwrite=False.
        """
        os.makedirs(self.output_dir, exist_ok=True)

        filepath = os.path.join(self.output_dir, filename)
        expected_dest = f"{filepath}.{file_extension}"
        if os.path.isfile(expected_dest) and not overwrite:
            raise FileExistsError(
                f"Le fichier existe déjà : {expected_dest}. "
                "Utilisez overwrite=True pour écraser."
            )

        if isinstance(data, rasterio.DatasetReader) and data.closed:
            data = rasterio.open(data.name)

        result = save(data, file_extension, filename=filepath,
                      timestamp=timestamp, raster_meta=raster_meta)
        print(f"✅ Sortie sauvegardée : {result}")
        return result

    def save_manifest(self):
        """
        Sauvegarde un fichier project.json décrivant le projet.

        Le manifeste contient le CRS, les dates, l'inventaire des données
        et les métadonnées du projet.

        Returns:
            str: Chemin vers le fichier project.json.
        """
        manifest_path = os.path.join(self.path, "project.json")

        datasets_info = []
        for ds in self.list_datasets():
            datasets_info.append({
                "name": ds["name"],
                "type": ds["type"],
                "extension": ds["extension"],
                "main_file": os.path.relpath(ds["main_file"], self.path),
                "sidecars": [os.path.relpath(s, self.path) for s in ds["sidecars"]],
                "total_size": ds["total_size"],
            })

        manifest = {
            "project_path": self.path,
            "crs": str(self.crs),
            "data_dir": os.path.relpath(self.data_dir, self.path),
            "output_dir": os.path.relpath(self.output_dir, self.path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "datasets": datasets_info,
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"📄 Manifeste sauvegardé : {manifest_path}")
        return manifest_path

    def load_manifest(self):
        """
        Charge le fichier project.json et retourne son contenu.

        Returns:
            dict: Contenu du manifeste.

        Raises:
            FileNotFoundError: Si project.json n'existe pas.
        """
        manifest_path = os.path.join(self.path, "project.json")
        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(
                f"Manifeste introuvable : {manifest_path}. "
                "Utilisez save_manifest() pour le créer."
            )

        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

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

    def validate(self, deep=False):
        """
        Vérifie l'intégrité du projet.

        Args:
            deep: Si True, effectue des vérifications approfondies :
                  orphelins sidecars, noms de base ambigus, lisibilité
                  réelle des fichiers géospatiaux.

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

                # Collecter des infos pour la validation approfondie
                basenames: dict[str, list[str]] = {}

                for f in files:
                    full_path = os.path.join(root, f)

                    # Vérifier la lisibilité
                    if not os.access(full_path, os.R_OK):
                        report["warnings"].append(f"Fichier non lisible : {full_path}")

                    name, ext = os.path.splitext(f)
                    ext_lower = ext.lower()

                    if ext_lower == ".shp":
                        shp_basenames.add(name)

                    if deep:
                        basenames.setdefault(name, []).append(ext_lower)

                # Vérifier les sidecars obligatoires pour chaque shapefile
                for basename in shp_basenames:
                    for required_ext in (".shx", ".dbf"):
                        if basename + required_ext not in all_files:
                            report["warnings"].append(
                                f"Sidecar manquant : {basename}{required_ext} "
                                f"(requis pour {basename}.shp)"
                            )

                if deep:
                    # Sidecars orphelins
                    for f in files:
                        name, ext = os.path.splitext(f)
                        if ext.lower() in _ALL_SIDECAR_EXTENSIONS:
                            # Vérifier qu'un fichier principal existe
                            primary_ext = ".shp" if ext.lower() in SHAPEFILE_SIDECARS else ".tab"
                            if name + primary_ext not in all_files:
                                report["warnings"].append(
                                    f"Sidecar orphelin : {f} "
                                    f"(pas de {name}{primary_ext} trouvé)"
                                )

                    # Noms de base ambigus (même nom, extensions différentes
                    # qui sont toutes des primaires)
                    for name, exts in basenames.items():
                        primary_exts = [
                            e for e in exts
                            if e not in _ALL_SIDECAR_EXTENSIONS
                        ]
                        if len(primary_exts) > 1:
                            report["warnings"].append(
                                f"Nom ambigu : '{name}' existe avec les extensions "
                                f"{primary_exts}"
                            )

                    # Tenter d'ouvrir les fichiers géospatiaux
                    for f in files:
                        full_path = os.path.join(root, f)
                        _name, ext = os.path.splitext(f)
                        ext_lower = ext.lower()

                        if ext_lower in _ALL_SIDECAR_EXTENSIONS:
                            continue

                        if ext_lower in VECTOR_EXTENSIONS:
                            try:
                                import geopandas as gpd
                                gpd.read_file(full_path, rows=0)
                            except Exception as exc:
                                report["warnings"].append(
                                    f"Fichier vectoriel illisible : {f} ({exc})"
                                )
                        elif ext_lower in RASTER_EXTENSIONS:
                            try:
                                with rasterio.open(full_path) as src:
                                    _ = src.meta
                            except Exception as exc:
                                report["warnings"].append(
                                    f"Fichier raster illisible : {f} ({exc})"
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