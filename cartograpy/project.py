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
import logging

logger = logging.getLogger(__name__)


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

# Primary extensions of multi-file formats (the ones we load)
_PRIMARY_EXTENSIONS = {".shp", ".tab"}

# Multi-component file families (sidecars)
SHAPEFILE_SIDECARS = {".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix"}
TAB_SIDECARS = {".dat", ".map", ".id"}

# Every sidecar extension (never a primary file to load)
_ALL_SIDECAR_EXTENSIONS = SHAPEFILE_SIDECARS | TAB_SIDECARS


def _classify_extension(ext):
    """Returns the type ('vector', 'raster', 'tabular', 'other') of an extension."""
    ext = ext.lower()
    if ext in VECTOR_EXTENSIONS:
        return "vector"
    if ext in RASTER_EXTENSIONS:
        return "raster"
    if ext in TABULAR_EXTENSIONS:
        return "tabular"
    return "other"


def _get_sidecars_for(ext):
    """Returns the set of sidecars associated with a primary extension."""
    ext = ext.lower()
    if ext == ".shp":
        return SHAPEFILE_SIDECARS
    if ext == ".tab":
        return TAB_SIDECARS
    return set()


class Project:
    """cartograpy project manager."""

    def __init__(self, path=None, data_dir="data", output_dir="output", crs="EPSG:4326"):
        """
        Creates a Project object.

        Args:
            path: Project root directory. If None, uses the current directory.
            data_dir: Name of the data folder (default "data").
            output_dir: Name of the output folder (default "output").
            crs: Coordinate reference system (default "EPSG:4326" / WGS 84).
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
        Initializes the project by creating the data and output folders.

        Returns:
            str: Absolute path of the initialized project.
        """
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        return self.path

    @staticmethod
    def available_crs(auth_name="EPSG", crs_type=None, name_contains=""):
        """
        Lists the available CRSs.

        Args:
            auth_name: Authority (default "EPSG"). Set to None for every authority.
            crs_type: CRS type to filter on (e.g.: "GEOGRAPHIC_2D", "PROJECTED").
                      None for every type.
            name_contains: Text filter on the CRS name (case-insensitive).

        Returns:
            list[dict]: List of {authority, code, name, type, area} dictionaries.
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
        Adds data to the project's data folder.

        Args:
            data: Data to save (GeoDataFrame, DataFrame, DatasetReader,
                  numpy array) or path (str/Path) to an existing file.
            file_extension: Output file extension (e.g.: 'geojson', 'shp', 'tif').
                            Optional if data is a path (the extension is inferred).
            filename: Base file name (without extension). Defaults to "output".
            timestamp: If True, adds a timestamp to the name. Defaults to False.
            raster_meta: Raster metadata if data is a numpy array.
            overwrite: If True, overwrites an existing file. Defaults to False.
            mode: "copy" (default), "move", or "link" (symlink).
                  Only has an effect if data is a file path.
            category: Target subfolder within data/ ("vector", "raster", "tabular").
                      If None, writes directly into data/.

        Returns:
            str: Absolute path to the saved or copied file.

        Raises:
            FileNotFoundError: If data is a path and the file doesn't exist.
            FileExistsError: If the file already exists and overwrite=False.
            ValueError: If file_extension is missing for an in-memory object
                        or if mode is invalid.
        """
        target_dir = self.data_dir
        if category:
            target_dir = os.path.join(self.data_dir, category)
        os.makedirs(target_dir, exist_ok=True)

        # If data is a path to an existing file
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

            # Transfer the sidecars
            copied_sidecars = []
            sidecars = _get_sidecars_for(src_ext)
            src_dir = os.path.dirname(src)
            for sidecar_ext in sidecars:
                sidecar_src = os.path.join(src_dir, src_name + sidecar_ext)
                if os.path.isfile(sidecar_src):
                    sidecar_dest = os.path.join(target_dir, f"{filename}{sidecar_ext}")
                    transfer_fn(sidecar_src, sidecar_dest)
                    copied_sidecars.append(sidecar_ext)

            return dest

        if file_extension is None:
            raise ValueError("file_extension est requis quand data n'est pas un chemin de fichier.")

        # Reopen the DatasetReader if it's closed
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
        return result

    def infos(self):
        """
        Displays a summary of the project: paths, CRS, and file inventory.

        Returns:
            dict: Dictionary containing the project's information.
        """
        data_exists = os.path.isdir(self.data_dir)
        output_exists = os.path.isdir(self.output_dir)

        # Count files by category in data_dir
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

        # Count files in output_dir
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

        logger.info(f"📋 Projet : {self.path}")
        logger.info(f"   🌐 CRS : {self.crs}")
        logger.info(f"   📁 data/   : {'✅' if data_exists else '❌'} ({total} fichier(s))")
        if total > 0:
            logger.info(f"      ├── vectoriel : {vector_count}")
            logger.info(f"      ├── raster    : {raster_count}")
            logger.info(f"      ├── tabulaire : {tabular_count}")
            logger.info(f"      └── autre     : {other_count}")
        logger.info(f"   📁 output/ : {'✅' if output_exists else '❌'} ({output_count} fichier(s))")

        return info

    def organize_project(self):
        """
        Walks data_dir, sorts each file into a vector/, raster/, or
        tabular/ subfolder, and updates the corresponding lists.
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

    def _resolve_data(self, name, base_dir=None, strict=True):
        """
        Resolves the path of a file within a project folder.

        Looks up by exact name, then by base name (without extension).
        Ignores sidecar files (.shx, .dbf, .prj...) during a base-name
        search to avoid ambiguity.

        Args:
            name: File name (with or without extension).
            base_dir: Search folder. Defaults to self.data_dir.
            strict: If True and several files match the base name,
                    raises a ValueError.

        Returns:
            str: Absolute path to the file found.

        Raises:
            FileNotFoundError: If no file matches.
            ValueError: If strict=True and there are several matches.
        """
        if base_dir is None:
            base_dir = self.data_dir

        # 1. Direct path
        candidate = os.path.join(base_dir, name)
        if os.path.isfile(candidate):
            return candidate

        if not os.path.isdir(base_dir):
            raise FileNotFoundError(f"Dossier introuvable : {base_dir}")

        # 2. Exact name search
        for root, _dirs, files in os.walk(base_dir):
            for f in files:
                if f == name:
                    return os.path.join(root, f)

        # 3. Base name search (ignores sidecars)
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
        Lists the files present in the project's data folder.

        Args:
            type_filter: Filter by type ("vector", "raster", "tabular").
                         None to return everything.

        Returns:
            list[dict]: List of files with name, extension, type, size, path.
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
        Lists the logical datasets (a shapefile + its sidecars = 1 entry).

        Args:
            type_filter: Filter by type ("vector", "raster", "tabular").
                         None to return everything.

        Returns:
            list[dict]: Datasets with name, type, main_file, sidecars,
                        total_size, path.
        """
        all_files = self.list_data()
        if not all_files:
            return []

        # Index by (directory, base name)
        groups: dict[tuple[str, str], list[dict]] = {}
        for entry in all_files:
            key = (os.path.dirname(entry["path"]), entry["name"])
            groups.setdefault(key, []).append(entry)

        datasets = []
        seen_keys: set[tuple[str, str]] = set()

        for (dirpath, basename), entries in groups.items():
            if (dirpath, basename) in seen_keys:
                continue

            # Separate primary files from sidecars
            primary = []
            sidecars = []
            for e in entries:
                if e["extension"] in _ALL_SIDECAR_EXTENSIONS:
                    sidecars.append(e)
                else:
                    primary.append(e)

            if not primary:
                # Orphan sidecars: attach them if there's a primary file
                # with the same basename in the same folder
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
        Loads a file from the project's data folder.

        Args:
            name: File name (with or without extension) or relative path
                  within the data folder.
            layer: Layer to load for multi-layer files (e.g.: GPX).

        Returns:
            GeoDataFrame, DataFrame, or DatasetReader depending on the file type.

        Raises:
            FileNotFoundError: If the file doesn't exist in the data folder.
        """
        path = self._resolve_data(name)
        return _load_data(path, layer=layer)

    def remove_data(self, name):
        """
        Removes a file (and its sidecars) from the project's data folder.

        Args:
            name: Name of the file (with extension) to remove.

        Returns:
            list[str]: List of removed files.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        target = self._resolve_data(name)

        removed = []
        base_name, ext = os.path.splitext(os.path.basename(target))
        target_dir = os.path.dirname(target)

        # Remove the primary file
        os.remove(target)
        removed.append(target)

        # Remove the sidecars
        for sidecar_ext in _get_sidecars_for(ext):
            sidecar_path = os.path.join(target_dir, base_name + sidecar_ext)
            if os.path.isfile(sidecar_path):
                os.remove(sidecar_path)
                removed.append(sidecar_path)

        return removed

    def rename_data(self, old, new):
        """
        Renames a dataset (primary file + sidecars).

        Args:
            old: Current file name (with or without extension).
            new: New base name (without extension).

        Returns:
            list[tuple[str, str]]: (old path, new path) pairs.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
        """
        target = self._resolve_data(old)
        target_dir = os.path.dirname(target)
        old_base, ext = os.path.splitext(os.path.basename(target))

        renamed = []

        # Rename the primary file
        new_path = os.path.join(target_dir, new + ext)
        os.rename(target, new_path)
        renamed.append((target, new_path))

        # Rename the sidecars
        for sidecar_ext in _get_sidecars_for(ext):
            sidecar_old = os.path.join(target_dir, old_base + sidecar_ext)
            if os.path.isfile(sidecar_old):
                sidecar_new = os.path.join(target_dir, new + sidecar_ext)
                os.rename(sidecar_old, sidecar_new)
                renamed.append((sidecar_old, sidecar_new))

        return renamed

    def get_path(self, name, folder="data"):
        """
        Returns the absolute path of a file in the project.

        Args:
            name: File name or relative path.
            folder: "data" or "output". Defaults to "data".

        Returns:
            str: Absolute path of the file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        base = self.data_dir if folder == "data" else self.output_dir
        return self._resolve_data(name, base_dir=base)

    def set_crs(self, crs):
        """
        Changes the project's CRS.

        Args:
            crs: New CRS (EPSG code, WKT string, etc.).

        Returns:
            pyproj.CRS: The new CRS.
        """
        self.crs = CRS.from_user_input(crs)
        return self.crs

    def save_output(self, data, file_extension, filename="output",
                    timestamp=False, raster_meta=None, overwrite=False):
        """
        Saves data to the project's output folder.

        Counterpart to add_data but targeting output_dir.

        Args:
            data: Data to save (GeoDataFrame, DataFrame, DatasetReader,
                  numpy array).
            file_extension: Output file extension.
            filename: Base file name (without extension).
            timestamp: If True, adds a timestamp to the name.
            raster_meta: Raster metadata if data is a numpy array.
            overwrite: If True, overwrites an existing file.

        Returns:
            str: Absolute path to the saved file.

        Raises:
            FileExistsError: If the file already exists and overwrite=False.
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
        return result

    def save_manifest(self):
        """
        Saves a project.json file describing the project.

        The manifest contains the CRS, dates, data inventory, and the
        project's metadata.

        Returns:
            str: Path to the project.json file.
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

        return manifest_path

    def load_manifest(self):
        """
        Loads the project.json file and returns its contents.

        Returns:
            dict: Contents of the manifest.

        Raises:
            FileNotFoundError: If project.json doesn't exist.
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
        Removes every file from the output folder.

        Returns:
            int: Number of files removed.
        """
        if not os.path.isdir(self.output_dir):
            return 0

        count = 0
        for root, dirs, files in os.walk(self.output_dir, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
                count += 1
            for d in dirs:
                os.rmdir(os.path.join(root, d))

        return count

    def validate(self, deep=False):
        """
        Checks the project's integrity.

        Args:
            deep: If True, performs thorough checks: orphan sidecars,
                  ambiguous base names, actual readability of geospatial
                  files.

        Returns:
            dict: Validation report with statuses and any warnings.
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

        # Check the files in data_dir
        if report["data_dir_exists"]:
            for root, _dirs, files in os.walk(self.data_dir):
                shp_basenames = set()
                all_files = set(files)

                # Collect info for the thorough validation
                basenames: dict[str, list[str]] = {}

                for f in files:
                    full_path = os.path.join(root, f)

                    # Check readability
                    if not os.access(full_path, os.R_OK):
                        report["warnings"].append(f"Fichier non lisible : {full_path}")

                    name, ext = os.path.splitext(f)
                    ext_lower = ext.lower()

                    if ext_lower == ".shp":
                        shp_basenames.add(name)

                    if deep:
                        basenames.setdefault(name, []).append(ext_lower)

                # Check the required sidecars for each shapefile
                for basename in shp_basenames:
                    for required_ext in (".shx", ".dbf"):
                        if basename + required_ext not in all_files:
                            report["warnings"].append(
                                f"Sidecar manquant : {basename}{required_ext} "
                                f"(requis pour {basename}.shp)"
                            )

                if deep:
                    # Orphan sidecars
                    for f in files:
                        name, ext = os.path.splitext(f)
                        if ext.lower() in _ALL_SIDECAR_EXTENSIONS:
                            # Check that a primary file exists
                            primary_ext = ".shp" if ext.lower() in SHAPEFILE_SIDECARS else ".tab"
                            if name + primary_ext not in all_files:
                                report["warnings"].append(
                                    f"Sidecar orphelin : {f} "
                                    f"(pas de {name}{primary_ext} trouvé)"
                                )

                    # Ambiguous base names (same name, different extensions
                    # that are all primary)
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

                    # Try to open the geospatial files
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
        logger.info(f"🔍 Validation du projet : {status}")
        for w in report["warnings"]:
            logger.info(f"   ⚠️ {w}")
        for e in report["errors"]:
            logger.info(f"   ❌ {e}")
        if not report["warnings"] and not report["errors"]:
            logger.info("   Aucun problème détecté.")

        return report


def init_project(path=None):
    """Shortcut to quickly create and initialize a project."""
    project = Project(path)
    return project.init()
