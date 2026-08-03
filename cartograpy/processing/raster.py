import geopandas as gpd
import os
import numpy as np
from shapely.geometry import MultiPolygon, Polygon, LineString, Point, box
import warnings
import rasterio
import logging

logger = logging.getLogger(__name__)


class RasterTools:
    """
    Boîte à outils pour le traitement de données raster.

    Encapsule un fichier raster (via rasterio) et fournit des méthodes
    chaînables pour :
    1. Prétraitements (validation, harmonisation CRS/résolution,
       découpage, nettoyage radiométrique, prétraitements satellitaires)
    2. Traitements / analyses (calcul de bandes, reclassement,
       statistiques, voisinage, terrain, classification, détection
       de changement, analyse multicritère)
    3. Post-traitements (nettoyage résultats, conversion raster-vecteur,
       cartographie, export)

    Usage::

        rt = RasterTools("chemin/vers/raster.tif")
        info = rt.get_raster_info()

        # Chaînable via résultat en mémoire
        rt2 = (rt
            .reproject_raster("EPSG:32630")
            .resample_raster(10)
            .clip_raster(geodf))
        rt2.export_geotiff("resultat.tif")
    """

    def __init__(self, source):
        """
        Initialise RasterTools.

        Args:
            source: Chemin vers un fichier raster (str / Path),
                    ou un tuple (data, profile) où data est un np.ndarray
                    et profile un dict rasterio-compatible.
        """
        if isinstance(source, (str, os.PathLike)):
            self.path = str(source)
            with rasterio.open(self.path) as src:
                self.data = src.read()
                self.profile = dict(src.profile)
        elif isinstance(source, tuple) and len(source) == 2:
            self.data, self.profile = source[0].copy(), dict(source[1])
            self.path = None
        else:
            raise TypeError(
                "source doit être un chemin ou un tuple (ndarray, profile)"
            )

    def _wrap(self, data, profile=None):
        """Construit un nouveau RasterTools à partir de données en mémoire."""
        p = dict(profile) if profile else dict(self.profile)
        if data.ndim == 2:
            data = data[np.newaxis, ...]
        p.update(count=data.shape[0], height=data.shape[1], width=data.shape[2])
        return RasterTools((data, p))

    def _write_tmp(self, data=None, profile=None):
        """Écrit dans un fichier temporaire et renvoie le chemin."""
        import tempfile
        d = data if data is not None else self.data
        p = profile if profile is not None else self.profile
        if d.ndim == 2:
            d = d[np.newaxis, ...]
        p = dict(p)
        p.update(count=d.shape[0], height=d.shape[1], width=d.shape[2])
        tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        tmp.close()
        with rasterio.open(tmp.name, "w", **p) as dst:
            dst.write(d)
        return tmp.name

    # ────────────────────────────────────────────────────────────────
    #  1. PRÉTRAITEMENTS
    # ────────────────────────────────────────────────────────────────

    # --- Contrôle et validation ----------------------------------- #

    def get_raster_info(self) -> dict:
        """Retourne les métadonnées essentielles du raster."""
        p = self.profile
        return {
            "driver": p.get("driver"),
            "dtype": str(p.get("dtype")),
            "width": p.get("width"),
            "height": p.get("height"),
            "count": p.get("count"),
            "crs": str(p.get("crs")),
            "transform": p.get("transform"),
            "nodata": p.get("nodata"),
            "resolution": (p["transform"].a, abs(p["transform"].e))
            if p.get("transform") else None,
            "bounds": rasterio.transform.array_bounds(
                p["height"], p["width"], p["transform"]
            ) if p.get("transform") else None,
        }

    def check_raster_metadata(self) -> dict:
        """Vérifie les métadonnées critiques et signale les anomalies."""
        info = self.get_raster_info()
        issues = []
        if info["crs"] is None or info["crs"] == "None":
            issues.append("CRS manquant")
        if info["nodata"] is None:
            issues.append("Valeur NoData non définie")
        if info["resolution"] and info["resolution"][0] != abs(info["resolution"][1]):
            issues.append("Pixels non carrés")
        if self.data.size == 0:
            issues.append("Raster vide")
        return {"info": info, "issues": issues, "valid": len(issues) == 0}

    def validate_raster(self) -> bool:
        """Retourne True si le raster n'a aucun problème critique."""
        return self.check_raster_metadata()["valid"]

    def check_nodata(self) -> dict:
        """Analyse les valeurs NoData du raster."""
        nodata = self.profile.get("nodata")
        total = int(self.data.size)
        if nodata is not None:
            count = int(np.sum(self.data == nodata))
        else:
            count = int(np.sum(np.isnan(self.data))) if np.issubdtype(self.data.dtype, np.floating) else 0
        return {
            "nodata_value": nodata,
            "nodata_count": count,
            "total_pixels": total,
            "nodata_pct": round(count / total * 100, 2) if total > 0 else 0,
        }

    def check_band_count(self) -> int:
        """Retourne le nombre de bandes."""
        return self.data.shape[0]

    def check_resolution(self) -> tuple:
        """Retourne la résolution (pixel_x, pixel_y)."""
        t = self.profile.get("transform")
        if t:
            return (t.a, abs(t.e))
        return (None, None)

    def check_alignment(self, other) -> dict:
        """Vérifie la compatibilité (CRS, résolution, grille) avec un autre raster."""
        if isinstance(other, RasterTools):
            other_profile = other.profile
        else:
            with rasterio.open(other) as src:
                other_profile = dict(src.profile)
        crs_match = str(self.profile.get("crs")) == str(other_profile.get("crs"))
        t1, t2 = self.profile.get("transform"), other_profile.get("transform")
        res_match = False
        grid_aligned = False
        if t1 and t2:
            res_match = (abs(t1.a - t2.a) < 1e-10 and abs(t1.e - t2.e) < 1e-10)
            if res_match:
                dx = (t1.c - t2.c) % t1.a
                dy = (t1.f - t2.f) % abs(t1.e)
                grid_aligned = (abs(dx) < 1e-10 and abs(dy) < 1e-10)
        return {
            "crs_match": crs_match,
            "resolution_match": res_match,
            "grid_aligned": grid_aligned,
            "compatible": crs_match and res_match and grid_aligned,
        }

    # --- Harmonisation spatiale ----------------------------------- #

    def set_crs(self, crs):
        """Attribue un CRS au raster (sans reprojection)."""
        from rasterio.crs import CRS
        profile = dict(self.profile)
        profile["crs"] = CRS.from_user_input(crs)
        return self._wrap(self.data, profile)

    def reproject_raster(self, target_crs, resampling="nearest"):
        """Reprojette le raster vers un autre CRS."""
        from rasterio.warp import calculate_default_transform, reproject
        from rasterio.enums import Resampling

        resamp = getattr(Resampling, resampling, Resampling.nearest)
        src_crs = self.profile["crs"]
        t, w, h = calculate_default_transform(
            src_crs, target_crs,
            self.profile["width"], self.profile["height"],
            *rasterio.transform.array_bounds(
                self.profile["height"], self.profile["width"],
                self.profile["transform"]
            ),
        )
        profile = dict(self.profile)
        profile.update(crs=target_crs, transform=t, width=w, height=h)
        dst_data = np.zeros((self.data.shape[0], h, w), dtype=self.data.dtype)
        for i in range(self.data.shape[0]):
            reproject(
                source=self.data[i],
                destination=dst_data[i],
                src_transform=self.profile["transform"],
                src_crs=src_crs,
                dst_transform=t,
                dst_crs=target_crs,
                resampling=resamp,
            )
        return self._wrap(dst_data, profile)

    def resample_raster(self, target_resolution, resampling="nearest"):
        """Rééchantillonne le raster à une résolution cible (en unités du CRS)."""
        from rasterio.enums import Resampling as Resamp
        resamp = getattr(Resamp, resampling, Resamp.nearest)
        t = self.profile["transform"]
        scale_x = t.a / target_resolution
        scale_y = abs(t.e) / target_resolution
        new_w = int(self.profile["width"] * scale_x)
        new_h = int(self.profile["height"] * scale_y)
        if new_w < 1 or new_h < 1:
            raise ValueError("Résolution cible trop grande par rapport à l'emprise.")
        new_t = rasterio.transform.from_bounds(
            *rasterio.transform.array_bounds(
                self.profile["height"], self.profile["width"], t
            ),
            new_w, new_h,
        )
        from rasterio.warp import reproject
        profile = dict(self.profile)
        profile.update(transform=new_t, width=new_w, height=new_h)
        dst = np.zeros((self.data.shape[0], new_h, new_w), dtype=self.data.dtype)
        for i in range(self.data.shape[0]):
            reproject(
                source=self.data[i],
                destination=dst[i],
                src_transform=t,
                src_crs=self.profile["crs"],
                dst_transform=new_t,
                dst_crs=self.profile["crs"],
                resampling=resamp,
            )
        return self._wrap(dst, profile)

    def align_rasters(self, reference):
        """Aligne ce raster sur la grille d'un raster de référence."""
        if isinstance(reference, RasterTools):
            ref_profile = reference.profile
        else:
            with rasterio.open(reference) as src:
                ref_profile = dict(src.profile)
        from rasterio.warp import reproject
        from rasterio.enums import Resampling
        dst = np.zeros(
            (self.data.shape[0], ref_profile["height"], ref_profile["width"]),
            dtype=self.data.dtype,
        )
        for i in range(self.data.shape[0]):
            reproject(
                source=self.data[i],
                destination=dst[i],
                src_transform=self.profile["transform"],
                src_crs=self.profile["crs"],
                dst_transform=ref_profile["transform"],
                dst_crs=ref_profile["crs"],
                resampling=Resampling.nearest,
            )
        profile = dict(ref_profile)
        profile.update(count=self.data.shape[0], dtype=str(self.data.dtype))
        return self._wrap(dst, profile)

    def snap_raster_grid(self, reference):
        """Alias de align_rasters – accroche la grille sur une référence."""
        return self.align_rasters(reference)

    # --- Découpage et réduction de l'emprise ---------------------- #

    def clip_raster(self, geodf, crop=True, all_touched=False):
        """Découpe le raster par un GeoDataFrame (ou géométrie shapely)."""
        from rasterio.mask import mask as rio_mask
        if isinstance(geodf, gpd.GeoDataFrame):
            shapes = geodf.geometry.values
        elif isinstance(geodf, (Polygon, MultiPolygon)):
            shapes = [geodf]
        else:
            shapes = list(geodf)
        tmp = self._write_tmp()
        try:
            with rasterio.open(tmp) as src:
                out_data, out_transform = rio_mask(
                    src, shapes, crop=crop, all_touched=all_touched,
                )
            profile = dict(self.profile)
            profile.update(
                transform=out_transform,
                height=out_data.shape[1],
                width=out_data.shape[2],
            )
            return self._wrap(out_data, profile)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def crop_raster(self, bbox):
        """Découpe le raster par une emprise (xmin, ymin, xmax, ymax)."""
        clip_geom = box(*bbox)
        return self.clip_raster(clip_geom)

    def mask_raster(self, geodf, invert=False):
        """Masque les pixels hors du GeoDataFrame (met NoData)."""
        from rasterio.mask import mask as rio_mask
        if isinstance(geodf, gpd.GeoDataFrame):
            shapes = geodf.geometry.values
        elif isinstance(geodf, (Polygon, MultiPolygon)):
            shapes = [geodf]
        else:
            shapes = list(geodf)
        tmp = self._write_tmp()
        try:
            with rasterio.open(tmp) as src:
                out_data, out_transform = rio_mask(
                    src, shapes, crop=False, invert=invert,
                )
            profile = dict(self.profile)
            profile.update(transform=out_transform)
            return self._wrap(out_data, profile)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def extract_by_extent(self, bbox):
        """Alias de crop_raster."""
        return self.crop_raster(bbox)

    # --- Nettoyage radiométrique et numérique --------------------- #

    def replace_nodata(self, old_nodata, new_nodata):
        """Remplace une valeur NoData par une autre."""
        data = self.data.copy()
        if old_nodata is not None:
            data[data == old_nodata] = new_nodata
        profile = dict(self.profile)
        profile["nodata"] = new_nodata
        return self._wrap(data, profile)

    def fill_nodata(self, max_search_distance=100, smoothing_iterations=0):
        """Interpole les pixels NoData à partir des voisins valides."""
        from rasterio.fill import fillnodata
        data = self.data.copy().astype("float32")
        nodata = self.profile.get("nodata")
        for i in range(data.shape[0]):
            band = data[i]
            if nodata is not None:
                mask_arr = (band != nodata).astype(np.uint8)
            else:
                mask_arr = (~np.isnan(band)).astype(np.uint8)
            fillnodata(band, mask=mask_arr,
                       max_search_distance=max_search_distance,
                       smoothing_iterations=smoothing_iterations)
            data[i] = band
        profile = dict(self.profile)
        profile["dtype"] = "float32"
        return self._wrap(data, profile)

    def scale_raster_values(self, factor=1.0, offset=0.0):
        """Applique une transformation linéaire : pixel = pixel * factor + offset."""
        data = self.data.astype("float64") * factor + offset
        return self._wrap(data.astype(self.data.dtype))

    def convert_dtype(self, target_dtype):
        """Convertit le type de données du raster."""
        data = self.data.astype(target_dtype)
        profile = dict(self.profile)
        profile["dtype"] = str(np.dtype(target_dtype))
        return self._wrap(data, profile)

    def normalize_raster(self, band_index=None, vmin=0.0, vmax=1.0):
        """Normalise les valeurs entre vmin et vmax (min-max scaling)."""
        data = self.data.astype("float64").copy()
        nodata = self.profile.get("nodata")
        bands = [band_index] if band_index is not None else range(data.shape[0])
        for b in bands:
            band = data[b]
            if nodata is not None:
                valid = band[band != nodata]
            else:
                valid = band[~np.isnan(band)]
            if valid.size == 0:
                continue
            bmin, bmax = valid.min(), valid.max()
            if bmax - bmin > 0:
                band_norm = (band - bmin) / (bmax - bmin) * (vmax - vmin) + vmin
                if nodata is not None:
                    band_norm[band == nodata] = nodata
                data[b] = band_norm
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(data, profile)

    # --- Prétraitements d'images satellitaires -------------------- #

    def cloud_masking(self, cloud_band_index, cloud_values, replace_with=None):
        """
        Masque les pixels nuageux.

        Args:
            cloud_band_index: Index de la bande de masque nuage (QA).
            cloud_values: Liste des valeurs considérées comme nuages.
            replace_with: Valeur de remplacement (défaut: nodata).
        """
        data = self.data.copy().astype("float64")
        nodata = self.profile.get("nodata", np.nan)
        fill = replace_with if replace_with is not None else nodata
        cloud_mask = np.isin(self.data[cloud_band_index], cloud_values)
        for i in range(data.shape[0]):
            data[i][cloud_mask] = fill
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        profile["nodata"] = nodata if replace_with is None else profile.get("nodata")
        return self._wrap(data, profile)

    def shadow_masking(self, nir_band, threshold=0.1, replace_with=None):
        """
        Masque les ombres via un seuil sur la bande proche infrarouge.

        Args:
            nir_band: Index de la bande NIR.
            threshold: Seuil en dessous duquel un pixel est considéré ombre.
            replace_with: Valeur de remplacement (défaut: nodata).
        """
        data = self.data.copy().astype("float64")
        nodata = self.profile.get("nodata", np.nan)
        fill = replace_with if replace_with is not None else nodata
        shadow_mask = self.data[nir_band].astype("float64") < threshold
        for i in range(data.shape[0]):
            data[i][shadow_mask] = fill
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(data, profile)

    def band_selection(self, band_indices):
        """Sélectionne un sous-ensemble de bandes."""
        data = self.data[band_indices]
        if data.ndim == 2:
            data = data[np.newaxis, ...]
        return self._wrap(data)

    def band_stacking(self, others):
        """Empile les bandes de plusieurs rasters."""
        all_data = [self.data]
        for other in others:
            if isinstance(other, RasterTools):
                all_data.append(other.data)
            else:
                with rasterio.open(other) as src:
                    all_data.append(src.read())
        stacked = np.concatenate(all_data, axis=0)
        return self._wrap(stacked)

    def mosaic_rasters(self, others, method="first"):
        """
        Mosaïque de plusieurs rasters.

        Args:
            others: Liste de RasterTools ou chemins.
            method: 'first', 'last', 'min', 'max', 'mean'.
        """
        from rasterio.merge import merge
        tmp_paths = [self._write_tmp()]
        for other in others:
            if isinstance(other, RasterTools):
                tmp_paths.append(other._write_tmp())
            else:
                tmp_paths.append(str(other))
        try:
            datasets = [rasterio.open(p) for p in tmp_paths]
            mosaic, out_transform = merge(datasets, method=method)
            for ds in datasets:
                ds.close()
            profile = dict(self.profile)
            profile.update(
                transform=out_transform,
                height=mosaic.shape[1],
                width=mosaic.shape[2],
            )
            return self._wrap(mosaic, profile)
        finally:
            for p in tmp_paths:
                if p != self.path and os.path.exists(p):
                    os.remove(p)

    # ────────────────────────────────────────────────────────────────
    #  2. TRAITEMENTS ET ANALYSES
    # ────────────────────────────────────────────────────────────────

    # --- Calculs raster ------------------------------------------- #

    def raster_calculator(self, expression, band_vars=None):
        """
        Applique une expression mathématique sur les bandes.

        Args:
            expression: Expression NumPy, ex. "(B4 - B3) / (B4 + B3)".
            band_vars: Dict {nom_de_variable: index_de_bande}.
                       Défaut: B1=bande 0, B2=bande 1, etc.
        """
        if band_vars is None:
            band_vars = {f"B{i+1}": i for i in range(self.data.shape[0])}
        local_ns = {}
        for name, idx in band_vars.items():
            local_ns[name] = self.data[idx].astype("float64")
        local_ns["np"] = np
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result = eval(expression, {"__builtins__": {}}, local_ns)  # noqa: S307
        if isinstance(result, (int, float)):
            result = np.full_like(self.data[0], result, dtype="float64")
        result = result.astype("float64")
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def apply_formula(self, expression, band_vars=None):
        """Alias de raster_calculator."""
        return self.raster_calculator(expression, band_vars)

    def band_math(self, expression, band_vars=None):
        """Alias de raster_calculator."""
        return self.raster_calculator(expression, band_vars)

    def ndvi(self, red_band=0, nir_band=1):
        """Calcule le NDVI = (NIR - Red) / (NIR + Red)."""
        red = self.data[red_band].astype("float64")
        nir = self.data[nir_band].astype("float64")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result = np.where(
                (nir + red) != 0, (nir - red) / (nir + red), 0
            )
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def ndwi(self, green_band=0, nir_band=1):
        """Calcule le NDWI = (Green - NIR) / (Green + NIR)."""
        green = self.data[green_band].astype("float64")
        nir = self.data[nir_band].astype("float64")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result = np.where(
                (green + nir) != 0, (green - nir) / (green + nir), 0
            )
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def ndbi(self, swir_band=0, nir_band=1):
        """Calcule le NDBI = (SWIR - NIR) / (SWIR + NIR)."""
        swir = self.data[swir_band].astype("float64")
        nir = self.data[nir_band].astype("float64")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result = np.where(
                (swir + nir) != 0, (swir - nir) / (swir + nir), 0
            )
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def spectral_index(self, band_a, band_b):
        """Calcule un indice spectral normalisé générique = (A - B) / (A + B)."""
        a = self.data[band_a].astype("float64")
        b = self.data[band_b].astype("float64")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            result = np.where((a + b) != 0, (a - b) / (a + b), 0)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    # --- Reclassement --------------------------------------------- #

    def reclassify_raster(self, rules, band_index=0):
        """
        Reclasse un raster selon des règles.

        Args:
            rules: Liste de tuples (min, max, nouvelle_valeur) ou dict {ancienne: nouvelle}.
            band_index: Index de la bande à reclasser.
        """
        band = self.data[band_index].copy().astype("float64")
        result = np.full_like(band, self.profile.get("nodata", 0), dtype="float64")
        if isinstance(rules, dict):
            for old_val, new_val in rules.items():
                result[band == old_val] = new_val
        else:
            for vmin, vmax, new_val in rules:
                result[(band >= vmin) & (band < vmax)] = new_val
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def remap_values(self, mapping, band_index=0):
        """Remappe les valeurs via un dictionnaire {ancien: nouveau}."""
        return self.reclassify_raster(mapping, band_index=band_index)

    def threshold_raster(self, threshold, band_index=0, above=1, below=0):
        """Binarise un raster autour d'un seuil."""
        band = self.data[band_index].astype("float64")
        result = np.where(band >= threshold, above, below).astype("float64")
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    # --- Statistiques raster -------------------------------------- #

    def raster_statistics(self, band_index=0) -> dict:
        """Statistiques descriptives d'une bande."""
        band = self.data[band_index].astype("float64")
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid = band[band != nodata]
        else:
            valid = band[~np.isnan(band)]
        if valid.size == 0:
            return {"min": None, "max": None, "mean": None, "std": None,
                    "median": None, "valid_pixels": 0, "total_pixels": int(band.size)}
        return {
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "mean": float(np.mean(valid)),
            "std": float(np.std(valid)),
            "median": float(np.median(valid)),
            "valid_pixels": int(valid.size),
            "total_pixels": int(band.size),
        }

    def band_statistics(self) -> list:
        """Statistiques pour chaque bande."""
        return [self.raster_statistics(i) for i in range(self.data.shape[0])]

    def histogram_raster(self, band_index=0, bins=256) -> dict:
        """Histogramme d'une bande."""
        band = self.data[band_index].astype("float64").ravel()
        nodata = self.profile.get("nodata")
        if nodata is not None:
            band = band[band != nodata]
        else:
            band = band[~np.isnan(band)]
        counts, edges = np.histogram(band, bins=bins)
        return {"counts": counts, "edges": edges}

    def zonal_statistics(self, geodf, stats=None, band_index=0) -> gpd.GeoDataFrame:
        """
        Statistiques zonales par polygone.

        Args:
            geodf: GeoDataFrame de polygones.
            stats: Liste de statistiques ('min','max','mean','std','median','sum','count').
            band_index: Index de la bande.
        """
        if stats is None:
            stats = ["min", "max", "mean", "std", "count"]
        from rasterio.features import geometry_mask
        band = self.data[band_index].astype("float64")
        nodata = self.profile.get("nodata")
        t = self.profile["transform"]
        results = []
        for _, row in geodf.iterrows():
            geom = row.geometry
            try:
                mask_arr = geometry_mask(
                    [geom], out_shape=band.shape, transform=t, invert=True,
                )
                pixels = band[mask_arr]
                if nodata is not None:
                    pixels = pixels[pixels != nodata]
                pixels = pixels[~np.isnan(pixels)]
            except Exception:
                pixels = np.array([])
            stat_row = {}
            for s in stats:
                if pixels.size == 0:
                    stat_row[s] = None
                elif s == "min":
                    stat_row[s] = float(np.min(pixels))
                elif s == "max":
                    stat_row[s] = float(np.max(pixels))
                elif s == "mean":
                    stat_row[s] = float(np.mean(pixels))
                elif s == "std":
                    stat_row[s] = float(np.std(pixels))
                elif s == "median":
                    stat_row[s] = float(np.median(pixels))
                elif s == "sum":
                    stat_row[s] = float(np.sum(pixels))
                elif s == "count":
                    stat_row[s] = int(pixels.size)
            results.append(stat_row)
        result_gdf = geodf.copy()
        for s in stats:
            result_gdf[s] = [r[s] for r in results]
        return result_gdf

    # --- Analyse de voisinage ------------------------------------- #

    def _focal(self, func, size=3, band_index=0):
        """Applique un filtre focal générique."""
        from scipy.ndimage import generic_filter
        band = self.data[band_index].astype("float64")
        result = generic_filter(band, func, size=size)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def focal_mean(self, size=3, band_index=0):
        """Filtre moyen (moyenne mobile)."""
        from scipy.ndimage import uniform_filter
        band = self.data[band_index].astype("float64")
        result = uniform_filter(band, size=size)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def focal_median(self, size=3, band_index=0):
        """Filtre médian."""
        from scipy.ndimage import median_filter
        band = self.data[band_index].astype("float64")
        result = median_filter(band, size=size)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def focal_max(self, size=3, band_index=0):
        """Filtre maximum."""
        from scipy.ndimage import maximum_filter
        band = self.data[band_index].astype("float64")
        result = maximum_filter(band, size=size)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def focal_min(self, size=3, band_index=0):
        """Filtre minimum."""
        from scipy.ndimage import minimum_filter
        band = self.data[band_index].astype("float64")
        result = minimum_filter(band, size=size)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def moving_window_analysis(self, func, size=3, band_index=0):
        """Applique une fonction personnalisée via fenêtre glissante."""
        return self._focal(func, size=size, band_index=band_index)

    # --- Analyse morphologique et terrain ------------------------- #

    def compute_slope(self, band_index=0, degrees=True):
        """Calcule la pente à partir d'un MNT."""
        dem = self.data[band_index].astype("float64")
        res_x, res_y = self.check_resolution()
        dy, dx = np.gradient(dem, res_y, res_x)
        slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
        result = np.degrees(slope_rad) if degrees else slope_rad
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def compute_aspect(self, band_index=0, degrees=True):
        """Calcule l'exposition (aspect) à partir d'un MNT."""
        dem = self.data[band_index].astype("float64")
        res_x, res_y = self.check_resolution()
        dy, dx = np.gradient(dem, res_y, res_x)
        aspect = np.arctan2(-dy, dx)
        if degrees:
            aspect = np.degrees(aspect)
            aspect = (aspect + 360) % 360
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(aspect[np.newaxis, ...], profile)

    def compute_hillshade(self, band_index=0, azimuth=315, altitude=45):
        """Calcule l'ombrage du relief (hillshade)."""
        dem = self.data[band_index].astype("float64")
        res_x, res_y = self.check_resolution()
        dy, dx = np.gradient(dem, res_y, res_x)
        slope = np.arctan(np.sqrt(dx**2 + dy**2))
        aspect = np.arctan2(-dy, dx)
        az_rad = np.radians(azimuth)
        alt_rad = np.radians(altitude)
        hillshade = (
            np.sin(alt_rad) * np.cos(slope)
            + np.cos(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect)
        )
        hillshade = np.clip(hillshade * 255, 0, 255).astype("float64")
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(hillshade[np.newaxis, ...], profile)

    def compute_curvature(self, band_index=0):
        """Calcule la courbure du terrain."""
        dem = self.data[band_index].astype("float64")
        res_x, res_y = self.check_resolution()
        dy, dx = np.gradient(dem, res_y, res_x)
        dyy, dyx = np.gradient(dy, res_y, res_x)
        dxy, dxx = np.gradient(dx, res_y, res_x)
        curvature = -2 * (dxx + dyy)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(curvature[np.newaxis, ...], profile)

    def compute_tpi(self, size=3, band_index=0):
        """
        Calcule le Topographic Position Index.
        TPI = élévation – moyenne locale.
        """
        from scipy.ndimage import uniform_filter
        dem = self.data[band_index].astype("float64")
        mean_elev = uniform_filter(dem, size=size)
        tpi = dem - mean_elev
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(tpi[np.newaxis, ...], profile)

    def compute_tri(self, size=3, band_index=0):
        """
        Calcule le Terrain Ruggedness Index.
        TRI = moyenne des différences absolues avec les voisins.
        """
        from scipy.ndimage import generic_filter
        dem = self.data[band_index].astype("float64")
        def _tri_func(window):
            center = window[len(window) // 2]
            return np.mean(np.abs(window - center))
        tri = generic_filter(dem, _tri_func, size=size)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(tri[np.newaxis, ...], profile)

    def flow_direction(self, band_index=0):
        """
        Calcule la direction d'écoulement (D8).
        Convention : 1=E, 2=SE, 4=S, 8=SW, 16=W, 32=NW, 64=N, 128=NE.
        """
        dem = self.data[band_index].astype("float64")
        h, w = dem.shape
        directions = np.zeros_like(dem, dtype="int32")
        d8_codes = [1, 2, 4, 8, 16, 32, 64, 128]
        d8_offsets = [(0, 1), (1, 1), (1, 0), (1, -1),
                      (0, -1), (-1, -1), (-1, 0), (-1, 1)]
        d8_dist = [1, np.sqrt(2), 1, np.sqrt(2),
                   1, np.sqrt(2), 1, np.sqrt(2)]
        padded = np.pad(dem, 1, mode="edge")
        for i in range(h):
            for j in range(w):
                pi, pj = i + 1, j + 1
                max_drop = -np.inf
                best_dir = 0
                for k in range(8):
                    di, dj = d8_offsets[k]
                    ni, nj = pi + di, pj + dj
                    drop = (padded[pi, pj] - padded[ni, nj]) / d8_dist[k]
                    if drop > max_drop:
                        max_drop = drop
                        best_dir = d8_codes[k]
                directions[i, j] = best_dir if max_drop > 0 else 0
        profile = dict(self.profile)
        profile["dtype"] = "int32"
        return self._wrap(directions[np.newaxis, ...], profile)

    def flow_accumulation(self, band_index=0):
        """Calcule l'accumulation de flux à partir d'un MNT."""
        fdir = self.flow_direction(band_index)
        fdir_data = fdir.data[0]
        h, w = fdir_data.shape
        accum = np.ones((h, w), dtype="float64")
        d8_codes = [1, 2, 4, 8, 16, 32, 64, 128]
        d8_offsets = [(0, 1), (1, 1), (1, 0), (1, -1),
                      (0, -1), (-1, -1), (-1, 0), (-1, 1)]
        reverse_map = {}
        for k, code in enumerate(d8_codes):
            di, dj = d8_offsets[k]
            reverse_map[code] = (-di, -dj)
        in_degree = np.zeros((h, w), dtype="int32")
        for i in range(h):
            for j in range(w):
                code = fdir_data[i, j]
                if code in reverse_map:
                    continue
                for k, c in enumerate(d8_codes):
                    di, dj = d8_offsets[k]
                    ni, nj = i + di, j + dj
                    if 0 <= ni < h and 0 <= nj < w and fdir_data[ni, nj] == c:
                        pass
        # Simplified flow accumulation using topological sort
        from collections import deque
        for i in range(h):
            for j in range(w):
                code = fdir_data[i, j]
                idx = None
                for k, c in enumerate(d8_codes):
                    if c == code:
                        idx = k
                        break
                if idx is not None:
                    di, dj = d8_offsets[idx]
                    ni, nj = i + di, j + dj
                    if 0 <= ni < h and 0 <= nj < w:
                        in_degree[ni, nj] += 1
        queue = deque()
        for i in range(h):
            for j in range(w):
                if in_degree[i, j] == 0:
                    queue.append((i, j))
        while queue:
            ci, cj = queue.popleft()
            code = fdir_data[ci, cj]
            idx = None
            for k, c in enumerate(d8_codes):
                if c == code:
                    idx = k
                    break
            if idx is not None:
                di, dj = d8_offsets[idx]
                ni, nj = ci + di, cj + dj
                if 0 <= ni < h and 0 <= nj < w:
                    accum[ni, nj] += accum[ci, cj]
                    in_degree[ni, nj] -= 1
                    if in_degree[ni, nj] == 0:
                        queue.append((ni, nj))
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(accum[np.newaxis, ...], profile)

    def watershed_analysis(self, band_index=0, threshold=100):
        """
        Délimite les bassins versants simplifiés.

        Args:
            band_index: Bande du MNT.
            threshold: Seuil d'accumulation pour définir le réseau.
        """
        accum = self.flow_accumulation(band_index)
        from scipy.ndimage import label
        stream = (accum.data[0] >= threshold).astype("int32")
        non_stream = (stream == 0).astype("int32")
        basins, num_basins = label(non_stream)
        profile = dict(self.profile)
        profile["dtype"] = "int32"
        return self._wrap(basins[np.newaxis, ...], profile)

    # --- Classification raster ------------------------------------ #

    def unsupervised_classification(self, n_classes=5, band_indices=None, method="kmeans"):
        """
        Classification non supervisée (KMeans / MiniBatchKMeans).

        Args:
            n_classes: Nombre de classes.
            band_indices: Bandes à utiliser (défaut: toutes).
            method: 'kmeans' ou 'minibatch'.
        """
        try:
            from sklearn.cluster import KMeans, MiniBatchKMeans
        except ImportError:
            raise ImportError("scikit-learn est requis : pip install scikit-learn")
        indices = band_indices if band_indices is not None else list(range(self.data.shape[0]))
        bands = np.stack([self.data[i].astype("float64") for i in indices], axis=-1)
        h, w, nb = bands.shape
        pixels = bands.reshape(-1, nb)
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid_mask = ~np.any(pixels == nodata, axis=1)
        else:
            valid_mask = ~np.any(np.isnan(pixels), axis=1)
        valid_pixels = pixels[valid_mask]
        if valid_pixels.size == 0:
            result = np.zeros((h, w), dtype="int32")
        else:
            clf = MiniBatchKMeans(n_clusters=n_classes, n_init=3) if method == "minibatch" else KMeans(n_clusters=n_classes, n_init=10)
            labels = clf.fit_predict(valid_pixels)
            result = np.full(pixels.shape[0], -1, dtype="int32")
            result[valid_mask] = labels
            result = result.reshape(h, w)
        profile = dict(self.profile)
        profile["dtype"] = "int32"
        profile["nodata"] = -1
        return self._wrap(result[np.newaxis, ...], profile)

    def supervised_classification(self, training_data, label_column, band_indices=None, method="random_forest", **kwargs):
        """
        Classification supervisée.

        Args:
            training_data: GeoDataFrame avec les échantillons d'entraînement.
            label_column: Colonne contenant les classes.
            band_indices: Bandes à utiliser (défaut: toutes).
            method: 'random_forest', 'svm', 'gradient_boosting'.
        """
        try:
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from sklearn.svm import SVC
        except ImportError:
            raise ImportError("scikit-learn est requis : pip install scikit-learn")
        from rasterio.features import geometry_mask
        indices = band_indices if band_indices is not None else list(range(self.data.shape[0]))
        bands = np.stack([self.data[i].astype("float64") for i in indices], axis=-1)
        h, w, nb = bands.shape
        t = self.profile["transform"]
        X_train, y_train = [], []
        for _, row in training_data.iterrows():
            geom = row.geometry
            label_val = row[label_column]
            try:
                mask_arr = geometry_mask([geom], out_shape=(h, w), transform=t, invert=True)
                pixels = bands[mask_arr]
                X_train.extend(pixels.tolist())
                y_train.extend([label_val] * len(pixels))
            except Exception:
                continue
        if len(X_train) == 0:
            raise ValueError("Aucun pixel d'entraînement extrait.")
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        if method == "svm":
            clf = SVC(**kwargs)
        elif method == "gradient_boosting":
            clf = GradientBoostingClassifier(**kwargs)
        else:
            clf = RandomForestClassifier(n_estimators=kwargs.get("n_estimators", 100), **{k: v for k, v in kwargs.items() if k != "n_estimators"})
        clf.fit(X_train, y_train)
        pixels_all = bands.reshape(-1, nb)
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid_mask = ~np.any(pixels_all == nodata, axis=1)
        else:
            valid_mask = ~np.any(np.isnan(pixels_all), axis=1)
        result = np.full(pixels_all.shape[0], -1, dtype="int32")
        if valid_mask.any():
            result[valid_mask] = clf.predict(pixels_all[valid_mask])
        result = result.reshape(h, w)
        profile = dict(self.profile)
        profile["dtype"] = "int32"
        profile["nodata"] = -1
        return self._wrap(result[np.newaxis, ...], profile)

    def train_classifier(self, training_data, label_column, band_indices=None, method="random_forest", **kwargs):
        """
        Entraîne un classificateur et le retourne (sans prédire sur le raster).

        Returns:
            Modèle scikit-learn entraîné.
        """
        try:
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from sklearn.svm import SVC
        except ImportError:
            raise ImportError("scikit-learn est requis : pip install scikit-learn")
        from rasterio.features import geometry_mask
        indices = band_indices if band_indices is not None else list(range(self.data.shape[0]))
        bands = np.stack([self.data[i].astype("float64") for i in indices], axis=-1)
        h, w, nb = bands.shape
        t = self.profile["transform"]
        X_train, y_train = [], []
        for _, row in training_data.iterrows():
            geom = row.geometry
            label_val = row[label_column]
            try:
                mask_arr = geometry_mask([geom], out_shape=(h, w), transform=t, invert=True)
                pixels = bands[mask_arr]
                X_train.extend(pixels.tolist())
                y_train.extend([label_val] * len(pixels))
            except Exception:
                continue
        if len(X_train) == 0:
            raise ValueError("Aucun pixel d'entraînement extrait.")
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        if method == "svm":
            clf = SVC(**kwargs)
        elif method == "gradient_boosting":
            clf = GradientBoostingClassifier(**kwargs)
        else:
            clf = RandomForestClassifier(n_estimators=kwargs.get("n_estimators", 100), **{k: v for k, v in kwargs.items() if k != "n_estimators"})
        clf.fit(X_train, y_train)
        return clf

    def predict_raster_classes(self, classifier, band_indices=None):
        """Prédit les classes sur tout le raster avec un classificateur entraîné."""
        indices = band_indices if band_indices is not None else list(range(self.data.shape[0]))
        bands = np.stack([self.data[i].astype("float64") for i in indices], axis=-1)
        h, w, nb = bands.shape
        pixels = bands.reshape(-1, nb)
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid_mask = ~np.any(pixels == nodata, axis=1)
        else:
            valid_mask = ~np.any(np.isnan(pixels), axis=1)
        result = np.full(pixels.shape[0], -1, dtype="int32")
        if valid_mask.any():
            result[valid_mask] = classifier.predict(pixels[valid_mask])
        result = result.reshape(h, w)
        profile = dict(self.profile)
        profile["dtype"] = "int32"
        profile["nodata"] = -1
        return self._wrap(result[np.newaxis, ...], profile)

    def accuracy_assessment(self, classified, reference_data, label_column, band_index=0):
        """
        Évaluation de la précision d'une classification.

        Args:
            classified: RasterTools classifié (ou self).
            reference_data: GeoDataFrame de points de validation.
            label_column: Colonne des classes de référence.
            band_index: Bande du raster classifié.

        Returns:
            dict: overall_accuracy, kappa, confusion_matrix, per_class_accuracy
        """
        try:
            from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix as cm
        except ImportError:
            raise ImportError("scikit-learn est requis : pip install scikit-learn")
        if isinstance(classified, RasterTools):
            cls_data = classified.data[band_index]
            cls_transform = classified.profile["transform"]
        else:
            cls_data = self.data[band_index]
            cls_transform = self.profile["transform"]
        y_true, y_pred = [], []
        for _, row in reference_data.iterrows():
            pt = row.geometry
            col_idx, row_idx = ~cls_transform * (pt.x, pt.y)
            r, c = int(row_idx), int(col_idx)
            if 0 <= r < cls_data.shape[0] and 0 <= c < cls_data.shape[1]:
                y_true.append(row[label_column])
                y_pred.append(int(cls_data[r, c]))
        if len(y_true) == 0:
            return {"overall_accuracy": None, "kappa": None,
                    "confusion_matrix": None, "per_class_accuracy": {}}
        y_true, y_pred = np.array(y_true), np.array(y_pred)
        conf = cm(y_true, y_pred)
        classes = np.unique(np.concatenate([y_true, y_pred]))
        per_class = {}
        for i, cls in enumerate(classes):
            mask_cls = y_true == cls
            if mask_cls.sum() > 0:
                per_class[int(cls)] = float(np.sum(y_pred[mask_cls] == cls) / mask_cls.sum())
        return {
            "overall_accuracy": float(accuracy_score(y_true, y_pred)),
            "kappa": float(cohen_kappa_score(y_true, y_pred)),
            "confusion_matrix": conf,
            "per_class_accuracy": per_class,
        }

    # --- Détection de changement ---------------------------------- #

    def change_detection(self, other, band_index=0):
        """Détection de changement par différence de rasters."""
        if isinstance(other, RasterTools):
            other_data = other.data
        else:
            other = RasterTools(other)
            other_data = other.data
        diff = self.data[band_index].astype("float64") - other_data[band_index].astype("float64")
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(diff[np.newaxis, ...], profile)

    def raster_difference(self, other, band_index=0):
        """Alias de change_detection."""
        return self.change_detection(other, band_index)

    def post_classification_comparison(self, other, band_index=0):
        """
        Comparaison post-classification entre deux rasters classifiés.

        Returns:
            RasterTools avec le code de transition (class_t1 * 100 + class_t2).
        """
        if isinstance(other, RasterTools):
            other_data = other.data
        else:
            other = RasterTools(other)
            other_data = other.data
        t1 = self.data[band_index].astype("int32")
        t2 = other_data[band_index].astype("int32")
        transition = t1 * 100 + t2
        profile = dict(self.profile)
        profile["dtype"] = "int32"
        return self._wrap(transition[np.newaxis, ...], profile)

    def time_series_analysis(self, others, band_index=0, stat="mean"):
        """
        Analyse de série temporelle sur plusieurs rasters.

        Args:
            others: Liste de RasterTools ou chemins.
            band_index: Bande à analyser.
            stat: 'mean', 'std', 'min', 'max', 'trend'.
        """
        all_bands = [self.data[band_index].astype("float64")]
        for other in others:
            if isinstance(other, RasterTools):
                all_bands.append(other.data[band_index].astype("float64"))
            else:
                with rasterio.open(other) as src:
                    all_bands.append(src.read(band_index + 1).astype("float64"))
        stack = np.stack(all_bands, axis=0)
        if stat == "mean":
            result = np.nanmean(stack, axis=0)
        elif stat == "std":
            result = np.nanstd(stack, axis=0)
        elif stat == "min":
            result = np.nanmin(stack, axis=0)
        elif stat == "max":
            result = np.nanmax(stack, axis=0)
        elif stat == "trend":
            t_vals = np.arange(len(all_bands), dtype="float64")
            result = np.zeros_like(all_bands[0])
            for i in range(stack.shape[1]):
                for j in range(stack.shape[2]):
                    vals = stack[:, i, j]
                    if np.all(np.isnan(vals)):
                        result[i, j] = np.nan
                    else:
                        valid = ~np.isnan(vals)
                        if valid.sum() >= 2:
                            coeffs = np.polyfit(t_vals[valid], vals[valid], 1)
                            result[i, j] = coeffs[0]
                        else:
                            result[i, j] = 0
        else:
            raise ValueError(f"Statistique inconnue : {stat}")
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    # --- Analyse multicritère ------------------------------------- #

    def weighted_overlay(self, others, weights):
        """
        Superposition pondérée de plusieurs rasters critères.

        Args:
            others: Liste de RasterTools ou chemins.
            weights: Liste de poids (même longueur que [self] + others).
        """
        all_rasters = [self]
        for other in others:
            if not isinstance(other, RasterTools):
                other = RasterTools(other)
            all_rasters.append(other)
        if len(weights) != len(all_rasters):
            raise ValueError("Le nombre de poids doit correspondre au nombre de rasters.")
        total_weight = sum(weights)
        result = np.zeros_like(all_rasters[0].data[0], dtype="float64")
        for rt, w in zip(all_rasters, weights):
            result += rt.data[0].astype("float64") * (w / total_weight)
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def suitability_analysis(self, criteria_rasters, weights, thresholds=None):
        """
        Analyse d'aptitude multicritère.

        Args:
            criteria_rasters: Liste de RasterTools (critères).
            weights: Liste de poids pour chaque critère.
            thresholds: Dict optionnel {index: (min, max)} pour filtrage.
        """
        all_rasters = criteria_rasters
        if len(weights) != len(all_rasters):
            raise ValueError("Le nombre de poids doit correspondre au nombre de critères.")
        total_weight = sum(weights)
        result = np.zeros_like(all_rasters[0].data[0], dtype="float64")
        valid_mask = np.ones_like(result, dtype=bool)
        for idx, (rt, w) in enumerate(zip(all_rasters, weights)):
            band = rt.data[0].astype("float64")
            bmin, bmax = np.nanmin(band), np.nanmax(band)
            if bmax - bmin > 0:
                normalized = (band - bmin) / (bmax - bmin)
            else:
                normalized = np.zeros_like(band)
            if thresholds and idx in thresholds:
                tmin, tmax = thresholds[idx]
                valid_mask &= (band >= tmin) & (band <= tmax)
            result += normalized * (w / total_weight)
        result[~valid_mask] = 0
        profile = dict(all_rasters[0].profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def normalize_criteria(self, band_index=0, method="minmax"):
        """
        Normalise un critère pour l'analyse multicritère.

        Args:
            band_index: Bande à normaliser.
            method: 'minmax' ou 'zscore'.
        """
        band = self.data[band_index].astype("float64")
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid = band != nodata
        else:
            valid = ~np.isnan(band)
        if method == "minmax":
            bmin = np.min(band[valid]) if valid.any() else 0
            bmax = np.max(band[valid]) if valid.any() else 1
            if bmax - bmin > 0:
                result = np.where(valid, (band - bmin) / (bmax - bmin), band)
            else:
                result = np.where(valid, 0, band)
        elif method == "zscore":
            bmean = np.mean(band[valid]) if valid.any() else 0
            bstd = np.std(band[valid]) if valid.any() else 1
            if bstd > 0:
                result = np.where(valid, (band - bmean) / bstd, band)
            else:
                result = np.where(valid, 0, band)
        else:
            raise ValueError(f"Méthode inconnue : {method}")
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(result[np.newaxis, ...], profile)

    def combine_weighted_layers(self, others, weights):
        """Alias de weighted_overlay."""
        return self.weighted_overlay(others, weights)

    # ────────────────────────────────────────────────────────────────
    #  3. POST-TRAITEMENTS
    # ────────────────────────────────────────────────────────────────

    # --- Nettoyage des résultats ---------------------------------- #

    def remove_small_patches(self, min_size, band_index=0, connectivity=1):
        """Supprime les petites taches (< min_size pixels)."""
        from scipy.ndimage import label as ndlabel
        band = self.data[band_index].copy()
        unique_vals = np.unique(band)
        for val in unique_vals:
            if val == self.profile.get("nodata"):
                continue
            binary = (band == val).astype("int32")
            labeled, n_features = ndlabel(binary)
            for i in range(1, n_features + 1):
                patch = labeled == i
                if patch.sum() < min_size:
                    band[patch] = self.profile.get("nodata", 0)
        return self._wrap(band[np.newaxis, ...])

    def majority_filter(self, size=3, band_index=0):
        """Filtre majoritaire (remplace chaque pixel par la valeur la plus fréquente dans le voisinage)."""
        from scipy.ndimage import generic_filter
        from scipy.stats import mode as scipy_mode
        band = self.data[band_index].astype("float64")
        def _majority(window):
            result = scipy_mode(window, keepdims=False)
            return result.mode
        result = generic_filter(band, _majority, size=size)
        return self._wrap(result[np.newaxis, ...])

    def sieve_raster(self, threshold, band_index=0, connectivity=4):
        """
        Filtre de tamisage (sieve) – supprime les groupes < threshold pixels.
        Utilise rasterio.features.sieve.
        """
        from rasterio.features import sieve
        band = self.data[band_index].astype("int32").copy()
        sieved = sieve(band, size=threshold, connectivity=connectivity)
        return self._wrap(sieved[np.newaxis, ...])

    def smooth_classes(self, size=3, band_index=0):
        """Alias de majority_filter pour lisser une classification."""
        return self.majority_filter(size=size, band_index=band_index)

    # --- Conversion raster-vecteur -------------------------------- #

    def polygonize_raster(self, band_index=0) -> gpd.GeoDataFrame:
        """Convertit un raster classifié en polygones."""
        from rasterio.features import shapes
        band = self.data[band_index].astype("int32")
        t = self.profile["transform"]
        crs = self.profile.get("crs")
        results = []
        for geom, value in shapes(band, transform=t):
            from shapely.geometry import shape
            results.append({"geometry": shape(geom), "value": int(value)})
        if results:
            return gpd.GeoDataFrame(results, crs=crs)
        return gpd.GeoDataFrame(columns=["geometry", "value"], crs=crs)

    def raster_to_points(self, band_index=0, skip_nodata=True) -> gpd.GeoDataFrame:
        """Convertit chaque pixel en point."""
        band = self.data[band_index]
        t = self.profile["transform"]
        nodata = self.profile.get("nodata")
        crs = self.profile.get("crs")
        rows = []
        for i in range(band.shape[0]):
            for j in range(band.shape[1]):
                val = band[i, j]
                if skip_nodata and nodata is not None and val == nodata:
                    continue
                if skip_nodata and np.isnan(val):
                    continue
                x, y = rasterio.transform.xy(t, i, j)
                rows.append({"geometry": Point(x, y), "value": float(val)})
        if rows:
            return gpd.GeoDataFrame(rows, crs=crs)
        return gpd.GeoDataFrame(columns=["geometry", "value"], crs=crs)

    def contours_from_raster(self, band_index=0, levels=10) -> gpd.GeoDataFrame:
        """Extrait des courbes de niveau à partir d'un raster."""
        import matplotlib.pyplot as plt
        band = self.data[band_index].astype("float64")
        t = self.profile["transform"]
        crs = self.profile.get("crs")
        h, w = band.shape
        cols = np.arange(w)
        rows_arr = np.arange(h)
        xs = t.c + cols * t.a + 0.5 * t.a
        ys = t.f + rows_arr * t.e + 0.5 * t.e
        fig, ax = plt.subplots()
        cs = ax.contour(xs, ys, band, levels=levels)
        plt.close(fig)
        features = []
        for level_val, segs in zip(cs.levels, cs.allsegs):
            for seg in segs:
                if len(seg) >= 2:
                    features.append({
                        "level": float(level_val),
                        "geometry": LineString(seg),
                    })
        if features:
            return gpd.GeoDataFrame(features, crs=crs)
        return gpd.GeoDataFrame(columns=["level", "geometry"], crs=crs)

    # --- Généralisation et cartographie --------------------------- #

    def apply_colormap(self, colormap="viridis", band_index=0):
        """
        Applique une colormap matplotlib et retourne un raster RGB (3 bandes, uint8).

        Args:
            colormap: Nom de la colormap matplotlib.
            band_index: Bande source.
        """
        import matplotlib.pyplot as plt
        band = self.data[band_index].astype("float64")
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid = band[band != nodata]
        else:
            valid = band[~np.isnan(band)]
        bmin = valid.min() if valid.size > 0 else 0
        bmax = valid.max() if valid.size > 0 else 1
        if bmax - bmin > 0:
            normalized = (band - bmin) / (bmax - bmin)
        else:
            normalized = np.zeros_like(band)
        cmap = plt.get_cmap(colormap)
        rgba = cmap(normalized)
        rgb = (rgba[:, :, :3] * 255).astype("uint8")
        rgb_data = np.moveaxis(rgb, -1, 0)
        profile = dict(self.profile)
        profile.update(dtype="uint8", count=3, nodata=None)
        return self._wrap(rgb_data, profile)

    def stretch_contrast(self, band_index=0, percentile_low=2, percentile_high=98):
        """Étirement de contraste par percentiles."""
        band = self.data[band_index].astype("float64")
        nodata = self.profile.get("nodata")
        if nodata is not None:
            valid = band[band != nodata]
        else:
            valid = band[~np.isnan(band)]
        if valid.size == 0:
            return self._wrap(band[np.newaxis, ...])
        low = np.percentile(valid, percentile_low)
        high = np.percentile(valid, percentile_high)
        stretched = np.clip((band - low) / (high - low) * 255, 0, 255)
        if nodata is not None:
            stretched[band == nodata] = 0
        profile = dict(self.profile)
        profile["dtype"] = "float64"
        return self._wrap(stretched[np.newaxis, ...], profile)

    def build_pyramids(self, factors=None):
        """
        Construit des pyramides (overviews) pour l'affichage rapide.
        Nécessite un fichier sur disque.

        Args:
            factors: Liste de facteurs de réduction. Défaut: [2, 4, 8, 16].
        """
        if factors is None:
            factors = [2, 4, 8, 16]
        path = self.path or self._write_tmp()
        with rasterio.open(path, "r+") as ds:
            ds.build_overviews(factors, rasterio.enums.Resampling.nearest)
            ds.update_tags(ns="rio_overview", resampling="nearest")
        return path

    def create_overview(self, factor=4):
        """Crée un raster à résolution réduite (aperçu)."""
        from rasterio.enums import Resampling
        from rasterio.warp import reproject
        new_h = max(1, self.profile["height"] // factor)
        new_w = max(1, self.profile["width"] // factor)
        new_t = rasterio.transform.from_bounds(
            *rasterio.transform.array_bounds(
                self.profile["height"], self.profile["width"],
                self.profile["transform"],
            ),
            new_w, new_h,
        )
        dst = np.zeros((self.data.shape[0], new_h, new_w), dtype=self.data.dtype)
        for i in range(self.data.shape[0]):
            reproject(
                source=self.data[i],
                destination=dst[i],
                src_transform=self.profile["transform"],
                src_crs=self.profile["crs"],
                dst_transform=new_t,
                dst_crs=self.profile["crs"],
                resampling=Resampling.average,
            )
        profile = dict(self.profile)
        profile.update(height=new_h, width=new_w, transform=new_t)
        return self._wrap(dst, profile)

    # --- Export --------------------------------------------------- #

    def export_geotiff(self, path, compress="lzw"):
        """Exporte en GeoTIFF."""
        profile = dict(self.profile)
        profile.update(driver="GTiff", compress=compress)
        data = self.data
        if data.ndim == 2:
            data = data[np.newaxis, ...]
        profile.update(count=data.shape[0], height=data.shape[1], width=data.shape[2])
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data)
        return path

    def export_cog(self, path):
        """Exporte en Cloud Optimized GeoTIFF (COG)."""
        profile = dict(self.profile)
        profile.update(driver="GTiff", tiled=True, blockxsize=256, blockysize=256, compress="deflate")
        data = self.data
        if data.ndim == 2:
            data = data[np.newaxis, ...]
        profile.update(count=data.shape[0], height=data.shape[1], width=data.shape[2])
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data)
            dst.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.nearest)
            dst.update_tags(ns="rio_overview", resampling="nearest")
        return path

    def export_ascii_grid(self, path, band_index=0):
        """Exporte en ASCII Grid (.asc)."""
        band = self.data[band_index]
        t = self.profile["transform"]
        nodata = self.profile.get("nodata", -9999)
        h, w = band.shape
        with open(path, "w") as f:
            f.write(f"ncols         {w}\n")
            f.write(f"nrows         {h}\n")
            f.write(f"xllcorner     {t.c}\n")
            f.write(f"yllcorner     {t.f + h * t.e}\n")
            f.write(f"cellsize      {t.a}\n")
            f.write(f"NODATA_value  {nodata}\n")
            for i in range(h):
                row_str = " ".join(str(band[i, j]) for j in range(w))
                f.write(row_str + "\n")
        return path

    def export_png_map(self, path, colormap="viridis", band_index=0, dpi=150):
        """Exporte une image PNG colorisée."""
        import matplotlib.pyplot as plt
        band = self.data[band_index].astype("float64")
        nodata = self.profile.get("nodata")
        if nodata is not None:
            band = np.where(band == nodata, np.nan, band)
        fig, ax = plt.subplots(figsize=(10, 10))
        im = ax.imshow(band, cmap=colormap)
        plt.colorbar(im, ax=ax, shrink=0.7)
        ax.set_axis_off()
        fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.1)
        plt.close(fig)
        return path

    # --- Représentation ------------------------------------------- #

    def __repr__(self):
        shape = self.data.shape if self.data is not None else "N/A"
        crs = self.profile.get("crs", "N/A")
        return f"RasterTools(shape={shape}, CRS={crs})"

    def __len__(self):
        return self.data.shape[0] if self.data is not None else 0
