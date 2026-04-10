import geopandas as gpd
import pandas as pd
import os
import random
import numpy as np
from shapely.geometry import MultiPolygon, Polygon, LineString, Point, box
from shapely.validation import make_valid
from shapely.ops import unary_union, snap, polygonize
from shapely import wkt
from typing import List, Union, Optional
import warnings
import datetime
import rasterio

# Réutilisation des fonctions définies dans data.py (source unique)
from cartograpy.data import load, save, list_geofiles


def centroids(geodf):
    """
    Crée un nouveau GeoDataFrame contenant les centroïdes.
    """
    if "geometry" not in geodf.columns:
        raise ValueError("Aucune colonne 'geometry' trouvée.")
    centroids_gdf = geodf.copy()
    centroids_gdf['geometry'] = centroids_gdf['geometry'].centroid
    centroids_gdf.crs = geodf.crs
    return centroids_gdf

def join(from_tuple, to_tuple, columns_to_join=None, how='left', suffixes=('_from', '_to')):
    """
    Réalise une jointure entre deux GeoDataFrames sur des colonnes spécifiées.
    """
    source_gdf, source_column = from_tuple
    target_gdf, target_column = to_tuple
    if not isinstance(source_gdf, gpd.GeoDataFrame) or not isinstance(target_gdf, gpd.GeoDataFrame):
        raise TypeError("Les deux premiers éléments des tuples doivent être des GeoDataFrames")
    if source_column not in source_gdf.columns:
        raise ValueError(f"La colonne '{source_column}' n'existe pas dans le GeoDataFrame source")
    if target_column not in target_gdf.columns:
        raise ValueError(f"La colonne '{target_column}' n'existe pas dans le GeoDataFrame cible")
    target_copy = target_gdf.copy()
    if columns_to_join is not None:
        if target_column not in columns_to_join:
            columns_to_keep = [target_column] + columns_to_join
        else:
            columns_to_keep = columns_to_join
        missing_columns = [col for col in columns_to_keep if col not in target_copy.columns]
        if missing_columns:
            raise ValueError(f"Colonnes non trouvées dans le GeoDataFrame cible: {missing_columns}")
        target_copy = target_copy[columns_to_keep]
    joined_gdf = source_gdf.merge(
        target_copy,
        left_on=source_column,
        right_on=target_column,
        how=how,
        suffixes=suffixes
    )
    if not isinstance(joined_gdf, gpd.GeoDataFrame):
        joined_gdf = gpd.GeoDataFrame(joined_gdf, geometry=source_gdf.geometry.name)
    joined_gdf.crs = source_gdf.crs
    return joined_gdf


def fusion(dataframes_list, reset_index=True, ignore_crs=True):
    """
    Fusionne (concatène verticalement) une liste de DataFrames ou GeoDataFrames.

    Paramètres
    ----------
    dataframes_list : list
        Liste de DataFrame ou GeoDataFrame à empiler.
    reset_index : bool
        Si True, réinitialise l'index du DataFrame fusionné.
    ignore_crs : bool
        Si True, ignore les éventuels conflits de CRS (pour GeoDataFrame).
        Si False, lève une erreur si les CRS sont différents.

    Retourne
    --------
    DataFrame ou GeoDataFrame fusionné.
    """
    # Gestion du CRS pour GeoDataFrames
    is_geo = any(isinstance(df, gpd.GeoDataFrame) for df in dataframes_list)
    if is_geo:
        crs_set = set(str(df.crs) for df in dataframes_list if hasattr(df, 'crs'))
        if not ignore_crs and len(crs_set) > 1:
            raise ValueError(f"Conflit de CRS détecté : {crs_set}")
        # On force le CRS du premier GeoDataFrame pour le résultat
        result = gpd.GeoDataFrame(pd.concat(dataframes_list, ignore_index=True), crs=dataframes_list[0].crs)
    else:
        result = pd.concat(dataframes_list, ignore_index=True)

    if reset_index:
        result = result.reset_index(drop=True)
    return result


def add_column(df, column_name, expression, globals_dict=None):
    """
    Ajoute une nouvelle colonne à un DataFrame/GeoDataFrame selon une expression.

    Paramètres
    ----------
    df : DataFrame ou GeoDataFrame
        Tableau de données d'entrée.
    column_name : str
        Nom de la nouvelle colonne à créer.
    expression : callable ou str
        - callable : fonction prenant une ligne (row) et retournant la valeur.
          Exemple : lambda row: row['col1'] + row['col2']
        - str : Expression pandas passée à df.eval().
          Exemple : "col1 + col2"
    globals_dict : dict, optional
        Dictionnaire de variables supplémentaires accessibles dans l'expression.

    Retourne
    -------
    Le DataFrame/GeoDataFrame modifié (avec la nouvelle colonne).
    """
    if callable(expression):
        df[column_name] = df.apply(expression, axis=1)
    elif isinstance(expression, str):
        local_dict = {"random": random, "np": np}
        if globals_dict:
            local_dict.update(globals_dict)
        df[column_name] = df.eval(expression, local_dict=local_dict)
    else:
        raise TypeError("expression doit être un callable ou une chaîne (str)")
    return df

def split_multipolygon(multipolygon: Union[MultiPolygon, str,gpd.GeoDataFrame], 
                         return_type: str = 'geodataframe') -> Union[List[Polygon], gpd.GeoDataFrame]:
    """
    Sépare un MultiPolygon en polygones individuels.
    
    Args:
        multipolygon (MultiPolygon ou str): Le MultiPolygon à séparer ou sa représentation WKT
        return_type (str): Format de retour ('list' ou 'geodataframe')
    
    Returns:
        List[Polygon] ou GeoDataFrame: Liste des polygones ou GeoDataFrame avec les polygones séparés
    
    Examples:
        # Avec objet MultiPolygon
        polygons = separate_multipolygon(multipolygon_obj)
        
        # Avec WKT string
        polygons = separate_multipolygon(wkt_string)
        
        # Retour en GeoDataFrame
        gdf = separate_multipolygon(multipolygon_obj, return_type='geodataframe')
    """
    try:
        # Convertir WKT en MultiPolygon si nécessaire
        if isinstance(multipolygon, str):
            try:
                multipolygon = wkt.loads(multipolygon)
            except Exception as e:
                raise ValueError(f"Erreur lors du parsing WKT: {e}")
        
        # Vérifier que c'est bien un MultiPolygon
        if not isinstance(multipolygon, MultiPolygon):
            if isinstance(multipolygon, Polygon):
                print("Warning: L'objet fourni est déjà un Polygon simple")
                return [multipolygon] if return_type == 'list' else gpd.GeoDataFrame({'geometry': [multipolygon]})
            else:
                raise TypeError("L'objet fourni n'est pas un MultiPolygon ou Polygon")
        
        # Extraire les polygones individuels
        polygons = list(multipolygon.geoms)
        
        if return_type == 'list':
            return polygons
        elif return_type == 'geodataframe':
            # Créer un GeoDataFrame avec les polygones séparés
            gdf = gpd.GeoDataFrame({
                'polygon_id': range(len(polygons)),
                'area': [poly.area for poly in polygons],
                'geometry': polygons
            })
            return gdf
        else:
            raise ValueError("return_type doit être 'list' ou 'geodataframe'")
    except:
        return split_multipolygon_from_gdf(multipolygon)


def split_multipolygon_from_gdf(gdf: gpd.GeoDataFrame, 
                                          multipolygon_column: str = 'geometry',
                                          preserve_attributes: bool = True) -> gpd.GeoDataFrame:
    """
    Sépare tous les MultiPolygons d'un GeoDataFrame en polygones individuels.
    
    Args:
        gdf (GeoDataFrame): GeoDataFrame contenant des MultiPolygons
        multipolygon_column (str): Nom de la colonne contenant les géométries
        preserve_attributes (bool): Si True, préserve les attributs pour chaque polygone
    
    Returns:
        GeoDataFrame: Nouveau GeoDataFrame avec les polygones séparés
    
    Example:
        gdf_separated = split_multipolygon_from_geodataframe(gdf)
    """
    
    new_rows = []
    
    for idx, row in gdf.iterrows():
        geom = row[multipolygon_column]
        
        if isinstance(geom, MultiPolygon):
            # Séparer le MultiPolygon
            polygons = list(geom.geoms)
            
            for i, poly in enumerate(polygons):
                if preserve_attributes:
                    new_row = row.copy()
                    new_row[multipolygon_column] = poly
                    new_row['original_index'] = idx
                    new_row['polygon_part'] = i
                    new_rows.append(new_row)
                else:
                    new_rows.append({
                        multipolygon_column: poly,
                        'original_index': idx,
                        'polygon_part': i
                    })
        else:
            # Conserver les Polygons simples
            if preserve_attributes:
                new_row = row.copy()
                new_row['original_index'] = idx
                new_row['polygon_part'] = 0
                new_rows.append(new_row)
            else:
                new_rows.append({
                    multipolygon_column: geom,
                    'original_index': idx,
                    'polygon_part': 0
                })
    
    return gpd.GeoDataFrame(new_rows)


def get_multipolygon_info(multipolygon: Union[MultiPolygon, str]) -> dict:
    """
    Obtient des informations sur un MultiPolygon.
    
    Args:
        multipolygon (MultiPolygon ou str): Le MultiPolygon à analyser
    
    Returns:
        dict: Informations sur le MultiPolygon
    
    Example:
        info = get_multipolygon_info(multipolygon_obj)
        print(f"Nombre de polygones: {info['num_polygons']}")
    """
    
    # Convertir WKT si nécessaire
    if isinstance(multipolygon, str):
        multipolygon = wkt.loads(multipolygon)
    
    if not isinstance(multipolygon, MultiPolygon):
        if isinstance(multipolygon, Polygon):
            return {
                'type': 'Polygon',
                'num_polygons': 1,
                'total_area': multipolygon.area,
                'bounds': multipolygon.bounds,
                'areas': [multipolygon.area]
            }
        else:
            raise TypeError("L'objet fourni n'est pas un MultiPolygon ou Polygon")
    
    polygons = list(multipolygon.geoms)
    areas = [poly.area for poly in polygons]
    
    return {
        'type': 'MultiPolygon',
        'num_polygons': len(polygons),
        'total_area': sum(areas),
        'bounds': multipolygon.bounds,
        'areas': areas,
        'largest_polygon_area': max(areas),
        'smallest_polygon_area': min(areas)
    }

def get_geometry_types(df: gpd.GeoDataFrame) -> str:
    types = df.geometry.geom_type.value_counts()
    output={}
    for geom_type, count in types.items():
        percentage = (count / len(df)) * 100
        output[geom_type] = {"count":count,"percentage":percentage}
        print(f"{geom_type}: {count} ({percentage:.1f}%)")


def clip_gdf_by_mask(gdf_source, gdf_emprise, buffer_distance=0, crs="EPSG:4326"):
    """
    Découpe une GeoDataFrame selon l'emprise d'une seconde GeoDataFrame.
    
    Parameters:
    -----------
    gdf_source : geopandas.GeoDataFrame
        La GeoDataFrame à découper
    gdf_emprise : geopandas.GeoDataFrame
        La GeoDataFrame servant de masque de découpage
    buffer_distance : float, optional
        Distance de buffer à appliquer à l'emprise (défaut: 0)
    crs : str, optional
        CRS par défaut à utiliser si les GeoDataFrames n'en ont pas (défaut: "EPSG:4326")
        
    Returns:
    --------
    geopandas.GeoDataFrame
        La GeoDataFrame découpée selon l'emprise
        
    Raises:
    -------
    ValueError
        Si les GeoDataFrames ont des CRS différents
    """
    
    # Vérification des paramètres
    if not isinstance(gdf_source, gpd.GeoDataFrame):
        raise TypeError("gdf_source doit être une GeoDataFrame")
    
    if not isinstance(gdf_emprise, gpd.GeoDataFrame):
        raise TypeError("gdf_emprise doit être une GeoDataFrame")
    
    if gdf_source.empty:
        warnings.warn("La GeoDataFrame source est vide")
        return gdf_source.copy()
    
    if gdf_emprise.empty:
        warnings.warn("La GeoDataFrame d'emprise est vide")
        return gpd.GeoDataFrame(columns=gdf_source.columns, crs=gdf_source.crs)
    
    # Vérification et harmonisation des CRS
    # Attribution d'un CRS par défaut si manquant
    if gdf_source.crs is None:
        warnings.warn(f"gdf_source n'a pas de CRS défini. Attribution du CRS par défaut: {crs}")
        gdf_source = gdf_source.set_crs(crs)
    
    if gdf_emprise.crs is None:
        warnings.warn(f"gdf_emprise n'a pas de CRS défini. Attribution du CRS par défaut: {crs}")
        gdf_emprise = gdf_emprise.set_crs(crs)
    
    # Reprojeter gdf_emprise dans le CRS de gdf_source si différent
    if gdf_source.crs != gdf_emprise.crs:
        gdf_emprise = gdf_emprise.to_crs(gdf_source.crs)
    
    # Création de l'emprise totale (union de toutes les géométries)
    emprise_totale = gdf_emprise.geometry.union_all()
    
    # Application d'un buffer si spécifié
    if buffer_distance != 0:
        emprise_totale = emprise_totale.buffer(buffer_distance)
    
    # Sélection des géométries qui intersectent l'emprise
    mask = gdf_source.geometry.intersects(emprise_totale)
    gdf_intersect = gdf_source[mask].copy()
    
    if gdf_intersect.empty:
        warnings.warn("Aucune géométrie ne intersecte avec l'emprise")
        return gpd.GeoDataFrame(columns=gdf_source.columns, crs=gdf_source.crs)
    
    # Découpage des géométries
    try:
        gdf_intersect.loc[:, 'geometry'] = gdf_intersect.geometry.intersection(emprise_totale)
        
        # Suppression des géométries vides après découpage
        gdf_result = gdf_intersect[~gdf_intersect.geometry.is_empty].copy()
        
        return gdf_result
        
    except Exception as e:
        raise RuntimeError(f"Erreur lors du découpage : {str(e)}")


def clip_gdf_by_bbox(gdf_source, gdf_emprise, crs="EPSG:4326"):
    """
    Version alternative qui utilise la bounding box de l'emprise.
    Plus rapide mais moins précise que le découpage géométrique.
    
    Parameters:
    -----------
    gdf_source : geopandas.GeoDataFrame
        La GeoDataFrame à découper
    gdf_emprise : geopandas.GeoDataFrame
        La GeoDataFrame servant de référence pour la bbox
    crs : str, optional
        CRS par défaut à utiliser si les GeoDataFrames n'en ont pas (défaut: "EPSG:4326")
        
    Returns:
    --------
    geopandas.GeoDataFrame
        La GeoDataFrame découpée selon la bounding box
    """
    
    # Harmonisation des CRS
    # Attribution d'un CRS par défaut si manquant
    if gdf_source.crs is None:
        gdf_source = gdf_source.set_crs(crs)
        
    if gdf_emprise.crs is None:
        gdf_emprise = gdf_emprise.set_crs(crs)
    
    # Reprojeter gdf_emprise dans le CRS de gdf_source si différent
    if gdf_source.crs != gdf_emprise.crs:
        gdf_emprise = gdf_emprise.to_crs(gdf_source.crs)
    
    # Récupération des bounds
    bounds = gdf_emprise.total_bounds  # [minx, miny, maxx, maxy]
    
    # Création d'un polygon de la bbox
    bbox_polygon = box(bounds[0], bounds[1], bounds[2], bounds[3])
    
    # Sélection et découpage
    mask = gdf_source.geometry.intersects(bbox_polygon)
    gdf_clipped = gdf_source[mask].copy()
    
    if not gdf_clipped.empty:
        gdf_clipped.loc[:, 'geometry'] = gdf_clipped.geometry.intersection(bbox_polygon)
        gdf_clipped = gdf_clipped[~gdf_clipped.geometry.is_empty].copy()
    
    return gdf_clipped


# ════════════════════════════════════════════════════════════════════
#  VectorTools – boîte à outils complète pour données vectorielles
# ════════════════════════════════════════════════════════════════════

class VectorTools:
    """
    Boîte à outils pour le traitement de données vectorielles.

    Encapsule un GeoDataFrame et fournit des méthodes chaînables pour :
    1. Prétraitements (validation, CRS, nettoyage, filtrage, découpage, topologie)
    2. Traitements / analyses (géométrie, mesures, superposition, jointures,
       agrégation, proximité, réseau, densité, topologie)
    3. Post-traitements (reclassement, généralisation, export)

    Usage::

        vt = VectorTools(gdf)
        result = (vt
            .fix_invalid()
            .remove_empty()
            .reproject_layer("EPSG:32630")
            .buffer(500)
            .gdf)
    """

    def __init__(self, gdf: gpd.GeoDataFrame):
        if not isinstance(gdf, gpd.GeoDataFrame):
            raise TypeError("L'entrée doit être un GeoDataFrame")
        self.gdf = gdf.copy()

    def _wrap(self, gdf):
        return VectorTools(gdf)

    # ────────────────────────────────────────────────────────────────
    #  1. PRÉTRAITEMENTS
    # ────────────────────────────────────────────────────────────────

    # --- Contrôle et validation ----------------------------------- #

    def validity(self) -> pd.Series:
        """Retourne une Series indiquant la validité de chaque géométrie."""
        return self.gdf.geometry.is_valid

    def fix_invalid(self):
        """Corrige les géométries invalides (make_valid)."""
        gdf = self.gdf.copy()
        invalid = ~gdf.geometry.is_valid
        if invalid.any():
            gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].apply(
                make_valid
            )
        return self._wrap(gdf)

    def remove_empty(self):
        """Supprime les géométries vides ou nulles."""
        gdf = self.gdf[
            ~(self.gdf.geometry.is_empty | self.gdf.geometry.isna())
        ].copy()
        return self._wrap(gdf)

    def duplicates(self) -> gpd.GeoDataFrame:
        """Retourne les entités dupliquées."""
        return self.gdf[self.gdf.duplicated(keep=False)]

    def drop_duplicates(self, subset=None):
        """Supprime les doublons."""
        gdf = self.gdf.drop_duplicates(subset=subset).copy()
        return self._wrap(gdf)

    # --- Harmonisation des systèmes de coordonnées ---------------- #

    def get_crs(self):
        """Retourne le CRS du GeoDataFrame."""
        return self.gdf.crs

    def set_crs(self, crs, allow_override=False):
        """Attribue un CRS au GeoDataFrame."""
        gdf = self.gdf.set_crs(crs, allow_override=allow_override)
        return self._wrap(gdf)

    def reproject_layer(self, target_crs):
        """Re-projette la couche vers un autre CRS."""
        gdf = self.gdf.to_crs(target_crs)
        return self._wrap(gdf)

    # --- Nettoyage attributaire ----------------------------------- #

    def rename_fields(self, mapping: dict):
        """Renomme des colonnes selon un dictionnaire {ancien: nouveau}."""
        gdf = self.gdf.rename(columns=mapping)
        return self._wrap(gdf)

    def select_fields(self, columns: list):
        """Ne conserve que les colonnes listées (+ géométrie)."""
        geom_col = self.gdf.geometry.name
        cols = list(dict.fromkeys([geom_col] + columns))
        gdf = self.gdf[cols].copy()
        return self._wrap(gdf)

    def drop_fields(self, columns: list):
        """Supprime les colonnes listées."""
        gdf = self.gdf.drop(columns=columns, errors="ignore")
        return self._wrap(gdf)

    def cast_field_types(self, type_mapping: dict):
        """Convertit les types de colonnes : {"col": float, ...}."""
        gdf = self.gdf.copy()
        for col, dtype in type_mapping.items():
            gdf[col] = gdf[col].astype(dtype)
        return self._wrap(gdf)

    def fill_missing_values(self, value=None, method=None, columns=None):
        """Remplit les valeurs manquantes (value, 'ffill' ou 'bfill')."""
        gdf = self.gdf.copy()
        cols = columns if columns else [
            c for c in gdf.columns if c != gdf.geometry.name
        ]
        if method == "ffill":
            gdf[cols] = gdf[cols].ffill()
        elif method == "bfill":
            gdf[cols] = gdf[cols].bfill()
        else:
            gdf[cols] = gdf[cols].fillna(value if value is not None else 0)
        return self._wrap(gdf)

    def normalize_text_fields(self, columns=None):
        """Normalise les champs texte (strip, Title Case)."""
        gdf = self.gdf.copy()
        text_cols = columns or gdf.select_dtypes(include="object").columns.tolist()
        for col in text_cols:
            if col != gdf.geometry.name:
                gdf[col] = (
                    gdf[col].astype(str).str.strip().str.lower().str.title()
                )
        return self._wrap(gdf)

    # --- Filtrage et sélection ------------------------------------ #

    def filter_by_attribute(self, column, values):
        """Filtre par valeurs d'attribut."""
        if not isinstance(values, (list, tuple)):
            values = [values]
        gdf = self.gdf[self.gdf[column].isin(values)].copy()
        return self._wrap(gdf)

    def filter_by_expression(self, expression: str):
        """Filtre via une expression pandas (df.query)."""
        gdf = self.gdf.query(expression).copy()
        return self._wrap(gdf)

    def filter_by_location(self, mask_gdf, predicate="intersects"):
        """Conserve les entités qui satisfont le prédicat spatial avec le masque."""
        if isinstance(mask_gdf, VectorTools):
            mask_gdf = mask_gdf.gdf
        mask_geom = mask_gdf[[mask_gdf.geometry.name]].copy()
        joined = gpd.sjoin(self.gdf, mask_geom, how="inner", predicate=predicate)
        gdf = self.gdf.loc[joined.index.unique()].copy()
        return self._wrap(gdf)

    def select_by_bbox(self, bbox):
        """Sélectionne les entités dans une bbox (xmin, ymin, xmax, ymax)."""
        xmin, ymin, xmax, ymax = bbox
        gdf = self.gdf.cx[xmin:xmax, ymin:ymax].copy()
        return self._wrap(gdf)

    # --- Découpage et emprise ------------------------------------- #

    def clip(self, mask):
        """Découpe le GeoDataFrame par un masque (GeoDataFrame ou géométrie)."""
        if isinstance(mask, VectorTools):
            mask = mask.gdf
        gdf = gpd.clip(self.gdf, mask)
        return self._wrap(gdf)

    def extract_by_mask(self, mask):
        """Alias de clip()."""
        return self.clip(mask)

    def crop_to_extent(self, bbox):
        """Découpe selon une bbox (xmin, ymin, xmax, ymax)."""
        xmin, ymin, xmax, ymax = bbox
        clip_geom = gpd.GeoDataFrame(
            geometry=[box(xmin, ymin, xmax, ymax)], crs=self.gdf.crs
        )
        return self.clip(clip_geom)

    # --- Structuration géométrique -------------------------------- #

    def multipart_to_singlepart(self):
        """Éclate les multi-géométries en géométries simples."""
        gdf = self.gdf.explode(index_parts=False).reset_index(drop=True)
        return self._wrap(gdf)

    def singlepart_to_multipart(self, by):
        """Regroupe les géométries par champ en multi-géométries (dissolve)."""
        gdf = self.gdf.dissolve(by=by).reset_index()
        return self._wrap(gdf)

    def explode_geometries(self):
        """Alias de multipart_to_singlepart()."""
        return self.multipart_to_singlepart()

    def convert_geometry_type(self, target_type: str):
        """Convertit vers 'point', 'line' ou 'polygon'."""
        gdf = self.gdf.copy()
        t = target_type.lower()
        if t == "point":
            gdf["geometry"] = gdf.geometry.centroid
        elif t in ("line", "linestring"):
            gdf["geometry"] = gdf.geometry.boundary
        elif t == "polygon":
            polys = []
            for geom in gdf.geometry:
                result = list(polygonize(geom))
                polys.append(result[0] if result else Polygon())
            gdf["geometry"] = polys
        return self._wrap(gdf)

    def line_to_polygon(self):
        """Convertit des lignes fermées en polygones."""
        gdf = self.gdf.copy()
        polys = []
        for geom in gdf.geometry:
            result = list(polygonize(geom))
            polys.append(result[0] if result else Polygon())
        gdf["geometry"] = polys
        return self._wrap(gdf)

    def polygon_to_line(self):
        """Convertit des polygones en lignes (contour)."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.boundary
        return self._wrap(gdf)

    # --- Nettoyage topologique ------------------------------------ #

    def snap_geometries(self, tolerance: float):
        """Accroche les géométries entre elles selon une tolérance."""
        gdf = self.gdf.copy()
        union_geom = gdf.geometry.union_all()
        gdf["geometry"] = gdf.geometry.apply(
            lambda g: snap(g, union_geom, tolerance)
        )
        return self._wrap(gdf)

    def remove_slivers(self, min_area: float):
        """Supprime les polygones dont la surface < min_area."""
        gdf = self.gdf[self.gdf.geometry.area >= min_area].copy()
        return self._wrap(gdf)

    def close_gaps(self, min_area: float):
        """Ferme les petits trous (< min_area) en les fusionnant au voisin."""
        gdf = self.gdf.copy()
        total_union = unary_union(gdf.geometry)
        hull = total_union.convex_hull
        gaps = hull.difference(total_union)
        if gaps.is_empty:
            return self._wrap(gdf)
        gap_list = list(gaps.geoms) if hasattr(gaps, "geoms") else [gaps]
        small_gaps = [g for g in gap_list if g.area < min_area]
        for gap in small_gaps:
            best_idx, best_length = None, 0
            for idx, row in gdf.iterrows():
                shared = row.geometry.intersection(gap.boundary)
                if not shared.is_empty and shared.length > best_length:
                    best_length = shared.length
                    best_idx = idx
            if best_idx is not None:
                gdf.at[best_idx, "geometry"] = unary_union(
                    [gdf.at[best_idx, "geometry"], gap]
                )
        return self._wrap(gdf)

    def resolve_overlaps(self):
        """Résout les chevauchements en soustrayant du plus petit polygone."""
        gdf = self.gdf.copy()
        geom_col = gdf.columns.get_loc("geometry")
        for i in range(len(gdf)):
            for j in range(i + 1, len(gdf)):
                gi, gj = gdf.geometry.iloc[i], gdf.geometry.iloc[j]
                if gi.intersects(gj):
                    overlap = gi.intersection(gj)
                    if not overlap.is_empty and overlap.area > 0:
                        if gi.area >= gj.area:
                            gdf.iloc[j, geom_col] = gj.difference(overlap)
                        else:
                            gdf.iloc[i, geom_col] = gi.difference(overlap)
        return self._wrap(gdf)

    def enforce_topology_rules(self):
        """Applique les règles de base : fix_invalid + remove_empty."""
        return self.fix_invalid().remove_empty()

    # ────────────────────────────────────────────────────────────────
    #  2. TRAITEMENTS ET ANALYSES
    # ────────────────────────────────────────────────────────────────

    # --- Opérations géométriques ---------------------------------- #

    def buffer(self, distance: float):
        """Crée une zone tampon autour de chaque géométrie."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.buffer(distance)
        return self._wrap(gdf)

    def centroid(self):
        """Remplace les géométries par leurs centroïdes."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.centroid
        return self._wrap(gdf)

    def convex_hull(self):
        """Remplace les géométries par leur enveloppe convexe."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.convex_hull
        return self._wrap(gdf)

    def minimum_bounding_box(self):
        """Remplace les géométries par leur rectangle englobant."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.envelope
        return self._wrap(gdf)

    def simplify_geometry(self, tolerance: float, preserve_topology=True):
        """Simplifie les géométries selon une tolérance."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.simplify(
            tolerance, preserve_topology=preserve_topology
        )
        return self._wrap(gdf)

    def densify_geometry(self, max_segment_length: float):
        """Densifie les géométries (segmentize)."""
        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.segmentize(max_segment_length)
        return self._wrap(gdf)

    # --- Mesures géométriques ------------------------------------- #

    def area(self, column_name="area"):
        """Ajoute une colonne de surface."""
        gdf = self.gdf.copy()
        gdf[column_name] = gdf.geometry.area
        return self._wrap(gdf)

    def perimeter(self, column_name="perimeter"):
        """Ajoute une colonne de périmètre."""
        gdf = self.gdf.copy()
        gdf[column_name] = gdf.geometry.length
        return self._wrap(gdf)

    def length(self, column_name="length"):
        """Ajoute une colonne de longueur."""
        gdf = self.gdf.copy()
        gdf[column_name] = gdf.geometry.length
        return self._wrap(gdf)

    def compactness(self, column_name="compactness"):
        """Ajoute un indice de compacité (4πA/P²)."""
        gdf = self.gdf.copy()
        a = gdf.geometry.area
        p = gdf.geometry.length
        gdf[column_name] = np.where(p > 0, (4 * np.pi * a) / (p ** 2), 0)
        return self._wrap(gdf)

    def shape_index(self, column_name="shape_index"):
        """Ajoute un indice de forme (P/√A)."""
        gdf = self.gdf.copy()
        a = gdf.geometry.area
        p = gdf.geometry.length
        gdf[column_name] = np.where(a > 0, p / np.sqrt(a), 0)
        return self._wrap(gdf)

    # --- Superposition spatiale ----------------------------------- #

    def intersection(self, other):
        """Intersection spatiale avec une autre couche."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.overlay(self.gdf, other_gdf, how="intersection")
        return self._wrap(gdf)

    def union(self, other):
        """Union spatiale avec une autre couche."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.overlay(self.gdf, other_gdf, how="union")
        return self._wrap(gdf)

    def difference(self, other):
        """Différence spatiale avec une autre couche."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.overlay(self.gdf, other_gdf, how="difference")
        return self._wrap(gdf)

    def symmetric_difference(self, other):
        """Différence symétrique avec une autre couche."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.overlay(self.gdf, other_gdf, how="symmetric_difference")
        return self._wrap(gdf)

    def identity(self, other):
        """Identité spatiale (conserve tout de self + attributs de other)."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.overlay(self.gdf, other_gdf, how="identity")
        return self._wrap(gdf)

    # --- Jointures spatiales -------------------------------------- #

    def spatial_join(self, other, how="inner", predicate="intersects"):
        """Jointure spatiale."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.sjoin(self.gdf, other_gdf, how=how, predicate=predicate)
        return self._wrap(gdf)

    def join_by_nearest(self, other, max_distance=None):
        """Jointure au plus proche voisin."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        gdf = gpd.sjoin_nearest(self.gdf, other_gdf, max_distance=max_distance)
        return self._wrap(gdf)

    def point_in_polygon_join(self, polygons):
        """Jointure points-dans-polygones."""
        poly_gdf = polygons.gdf if isinstance(polygons, VectorTools) else polygons
        gdf = gpd.sjoin(self.gdf, poly_gdf, how="left", predicate="within")
        return self._wrap(gdf)

    # --- Agrégation et regroupement ------------------------------- #

    def dissolve(self, by, aggfunc="first"):
        """Fusionne les géométries par champ."""
        gdf = self.gdf.dissolve(by=by, aggfunc=aggfunc).reset_index()
        return self._wrap(gdf)

    def aggregate_by_field(self, by, aggfunc):
        """Agrège par champ avec une fonction choisie."""
        gdf = self.gdf.dissolve(by=by, aggfunc=aggfunc).reset_index()
        return self._wrap(gdf)

    def group_and_summarize(self, by, summary: dict):
        """Regroupe + résume : summary = {'col': 'sum', ...}."""
        stats = (
            self.gdf.drop(columns=[self.gdf.geometry.name])
            .groupby(by)
            .agg(summary)
        )
        # Aplatir les colonnes multi-index éventuels
        if isinstance(stats.columns, pd.MultiIndex):
            stats.columns = ["_".join(c).strip("_") for c in stats.columns]
        stats = stats.reset_index()
        gdf = self.gdf.dissolve(by=by).reset_index()
        for col in stats.columns:
            if col not in gdf.columns:
                gdf[col] = stats[col].values
        return self._wrap(gdf)

    # --- Analyse de proximité ------------------------------------- #

    def distance_to_nearest(self, other, column_name="dist_nearest"):
        """Calcule la distance au plus proche élément d'une autre couche."""
        from scipy.spatial import cKDTree

        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        src = np.array(
            list(self.gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        tgt = np.array(
            list(other_gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        tree = cKDTree(tgt)
        distances, _ = tree.query(src)
        gdf = self.gdf.copy()
        gdf[column_name] = distances
        return self._wrap(gdf)

    def nearest_neighbor_analysis(self):
        """Analyse du plus proche voisin (indice R de Clark-Evans)."""
        from scipy.spatial import cKDTree

        points = np.array(
            list(self.gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        tree = cKDTree(points)
        distances, indices = tree.query(points, k=2)
        nn_distances = distances[:, 1]
        n = len(points)
        total_area = self.gdf.geometry.union_all().convex_hull.area
        density = n / total_area if total_area > 0 else 0
        expected = 0.5 / np.sqrt(density) if density > 0 else 0
        mean_nn = float(np.mean(nn_distances))
        r_index = mean_nn / expected if expected > 0 else 0
        return {
            "mean_nearest_distance": mean_nn,
            "expected_distance": expected,
            "r_index": r_index,
            "nn_distances": nn_distances,
            "nn_indices": indices[:, 1],
        }

    def within_distance(self, other, distance: float):
        """Conserve les entités à moins de *distance* d'une autre couche."""
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        buffered = other_gdf.geometry.union_all().buffer(distance)
        gdf = self.gdf[self.gdf.geometry.intersects(buffered)].copy()
        return self._wrap(gdf)

    def distance_matrix(self, other=None, label_field=None,
                        method="centroid"):
        """Calcule la matrice de distance entre les entités.

        Parameters
        ----------
        other : VectorTools | GeoDataFrame | None
            Seconde couche. Si *None*, la matrice est calculée entre les
            entités de la couche courante (matrice carrée).
        label_field : str | None
            Champ à utiliser comme étiquette (index/colonnes).
            Si *None*, l'index du GeoDataFrame est utilisé.
        method : str
            ``"centroid"`` (défaut) utilise le centroïde de chaque géométrie.
            ``"boundary"`` utilise la distance minimale entre géométries
            (plus lent mais plus précis pour les polygones).

        Returns
        -------
        pd.DataFrame
            Matrice de distance symétrique (ou rectangulaire si *other*
            est fourni et différent de *self*).
        """
        from scipy.spatial import distance as sp_distance

        src_gdf = self.gdf
        if other is None:
            tgt_gdf = src_gdf
        else:
            tgt_gdf = other.gdf if isinstance(other, VectorTools) else other

        if method == "centroid":
            src_pts = np.array(
                list(src_gdf.geometry.centroid.apply(
                    lambda g: (g.x, g.y)))
            )
            tgt_pts = np.array(
                list(tgt_gdf.geometry.centroid.apply(
                    lambda g: (g.x, g.y)))
            )
            mat = sp_distance.cdist(src_pts, tgt_pts)
        elif method == "boundary":
            n_src = len(src_gdf)
            n_tgt = len(tgt_gdf)
            mat = np.zeros((n_src, n_tgt))
            for i in range(n_src):
                for j in range(n_tgt):
                    mat[i, j] = src_gdf.geometry.iloc[i].distance(
                        tgt_gdf.geometry.iloc[j]
                    )
        else:
            raise ValueError(
                f"method doit être 'centroid' ou 'boundary', reçu '{method}'"
            )

        src_labels = (
            src_gdf[label_field].values if label_field else src_gdf.index
        )
        tgt_labels = (
            tgt_gdf[label_field].values if label_field else tgt_gdf.index
        )
        return pd.DataFrame(mat, index=src_labels, columns=tgt_labels)

    # --- Analyse de réseau ---------------------------------------- #

    def build_network(self):
        """Construit un graphe networkx à partir de lignes."""
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx est requis : pip install networkx")
        G = nx.Graph()
        for idx, row in self.gdf.iterrows():
            geom = row.geometry
            lines = []
            if geom.geom_type == "LineString":
                lines = [geom]
            elif geom.geom_type == "MultiLineString":
                lines = list(geom.geoms)
            for line in lines:
                coords = list(line.coords)
                for i in range(len(coords) - 1):
                    seg_len = Point(coords[i]).distance(Point(coords[i + 1]))
                    G.add_edge(coords[i], coords[i + 1], weight=seg_len, fid=idx)
        return G

    def shortest_path(self, source: tuple, target: tuple):
        """Plus court chemin entre deux points (snap aux nœuds)."""
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx est requis : pip install networkx")
        G = self.build_network()
        nodes = list(G.nodes)
        src_node = min(nodes, key=lambda n: Point(source).distance(Point(n)))
        tgt_node = min(nodes, key=lambda n: Point(target).distance(Point(n)))
        path = nx.shortest_path(G, src_node, tgt_node, weight="weight")
        cost = nx.shortest_path_length(G, src_node, tgt_node, weight="weight")
        return {"path": path, "geometry": LineString(path), "cost": cost}

    def service_area(self, source: tuple, max_cost: float):
        """Zone de desserte autour d'un point source."""
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx est requis : pip install networkx")
        G = self.build_network()
        nodes = list(G.nodes)
        src_node = min(nodes, key=lambda n: Point(source).distance(Point(n)))
        lengths = nx.single_source_dijkstra_path_length(
            G, src_node, cutoff=max_cost, weight="weight"
        )
        reachable = [Point(n) for n in lengths]
        if reachable:
            hull = gpd.GeoSeries(reachable).union_all().convex_hull
            return gpd.GeoDataFrame(geometry=[hull], crs=self.gdf.crs)
        return gpd.GeoDataFrame(geometry=[], crs=self.gdf.crs)

    def network_distance(self, source: tuple, target: tuple) -> float:
        """Distance réseau entre deux points."""
        return self.shortest_path(source, target)["cost"]

    # --- Analyse de densité et répartition ------------------------ #

    def point_density(self, radius: float, column_name="density"):
        """Densité de points dans un rayon donné."""
        from scipy.spatial import cKDTree

        gdf = self.gdf.copy()
        pts = np.array(
            list(gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        tree = cKDTree(pts)
        area = np.pi * radius ** 2
        counts = tree.query_ball_point(pts, radius)
        gdf[column_name] = [len(c) / area for c in counts]
        return self._wrap(gdf)

    def kernel_density_from_points(self, bandwidth: float, resolution: int = 100):
        """Estimation de densité par noyau (retourne grille numpy)."""
        from scipy.stats import gaussian_kde

        pts = np.array(
            list(self.gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        kde = gaussian_kde(pts.T, bw_method=bandwidth)
        xmin, ymin, xmax, ymax = self.gdf.total_bounds
        xi = np.linspace(xmin, xmax, resolution)
        yi = np.linspace(ymin, ymax, resolution)
        xx, yy = np.meshgrid(xi, yi)
        density = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
        return {"density": density, "x": xi, "y": yi, "extent": (xmin, xmax, ymin, ymax)}

    def spatial_clustering(self, eps: float, min_samples: int = 5, column_name="cluster"):
        """Clustering DBSCAN (nécessite scikit-learn)."""
        try:
            from sklearn.cluster import DBSCAN
        except ImportError:
            raise ImportError("scikit-learn est requis : pip install scikit-learn")
        gdf = self.gdf.copy()
        pts = np.array(
            list(gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        gdf[column_name] = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(pts)
        return self._wrap(gdf)

    def hotspot_analysis(self, column: str = None, k: int = 8):
        """Analyse de points chauds (z-score sur voisinage k-NN)."""
        from scipy.spatial import cKDTree

        gdf = self.gdf.copy()
        pts = np.array(
            list(gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        tree = cKDTree(pts)
        values = (
            gdf[column].values.astype(float)
            if column and column in gdf.columns
            else np.ones(len(gdf))
        )
        global_mean = np.mean(values)
        global_std = np.std(values)
        _, indices = tree.query(pts, k=k + 1)
        z_scores = np.zeros(len(gdf))
        for i in range(len(gdf)):
            local_mean = np.mean(values[indices[i, 1:]])
            z_scores[i] = (
                (local_mean - global_mean) / global_std if global_std > 0 else 0
            )
        gdf["z_score"] = z_scores
        gdf["hotspot"] = pd.cut(
            z_scores,
            bins=[-np.inf, -2.58, -1.96, -1.65, 1.65, 1.96, 2.58, np.inf],
            labels=[
                "cold_99", "cold_95", "cold_90",
                "not_significant",
                "hot_90", "hot_95", "hot_99",
            ],
        )
        return self._wrap(gdf)

    # --- Analyse topologique -------------------------------------- #

    def check_adjacency(self) -> pd.DataFrame:
        """Matrice d'adjacence binaire (touches)."""
        n = len(self.gdf)
        matrix = np.zeros((n, n), dtype=int)
        for i in range(n):
            for j in range(i + 1, n):
                if self.gdf.geometry.iloc[i].touches(self.gdf.geometry.iloc[j]):
                    matrix[i][j] = matrix[j][i] = 1
        return pd.DataFrame(matrix, index=self.gdf.index, columns=self.gdf.index)

    def find_touching_features(self) -> list:
        """Liste de paires (i, j) d'entités qui se touchent."""
        pairs = []
        for i in range(len(self.gdf)):
            for j in range(i + 1, len(self.gdf)):
                if self.gdf.geometry.iloc[i].touches(self.gdf.geometry.iloc[j]):
                    pairs.append((self.gdf.index[i], self.gdf.index[j]))
        return pairs

    def detect_overlaps(self) -> gpd.GeoDataFrame:
        """Détecte les chevauchements entre entités."""
        rows = []
        for i in range(len(self.gdf)):
            for j in range(i + 1, len(self.gdf)):
                inter = self.gdf.geometry.iloc[i].intersection(
                    self.gdf.geometry.iloc[j]
                )
                if not inter.is_empty and inter.area > 0:
                    rows.append({
                        "feature_1": self.gdf.index[i],
                        "feature_2": self.gdf.index[j],
                        "overlap_area": inter.area,
                        "geometry": inter,
                    })
        if rows:
            return gpd.GeoDataFrame(rows, crs=self.gdf.crs)
        return gpd.GeoDataFrame(
            columns=["feature_1", "feature_2", "overlap_area", "geometry"]
        )

    def detect_gaps(self) -> gpd.GeoDataFrame:
        """Détecte les trous entre polygones."""
        total = unary_union(self.gdf.geometry)
        hull = total.convex_hull
        gaps = hull.difference(total)
        if gaps.is_empty:
            return gpd.GeoDataFrame(columns=["geometry", "area"], crs=self.gdf.crs)
        gap_list = list(gaps.geoms) if hasattr(gaps, "geoms") else [gaps]
        rows = [{"geometry": g, "area": g.area} for g in gap_list]
        return gpd.GeoDataFrame(rows, crs=self.gdf.crs)

    def build_contiguity_matrix(self, method="queen") -> pd.DataFrame:
        """Matrice de contiguïté ('queen' ou 'rook')."""
        n = len(self.gdf)
        matrix = np.zeros((n, n), dtype=int)
        for i in range(n):
            for j in range(i + 1, n):
                gi, gj = self.gdf.geometry.iloc[i], self.gdf.geometry.iloc[j]
                inter = gi.intersection(gj)
                if method == "queen":
                    adjacent = not inter.is_empty
                else:  # rook
                    adjacent = not inter.is_empty and inter.length > 0
                if adjacent:
                    matrix[i][j] = matrix[j][i] = 1
        return pd.DataFrame(matrix, index=self.gdf.index, columns=self.gdf.index)

    # ────────────────────────────────────────────────────────────────
    #  3. POST-TRAITEMENTS
    # ────────────────────────────────────────────────────────────────

    # --- Reclassement et enrichissement --------------------------- #

    def reclassify_attributes(self, column: str, mapping: dict):
        """Reclasse les valeurs d'une colonne selon un dictionnaire."""
        gdf = self.gdf.copy()
        gdf[column] = gdf[column].map(mapping).fillna(gdf[column])
        return self._wrap(gdf)

    def create_indicator_fields(self, rules: dict):
        """Crée des colonnes indicatrices : {'nom': expression_ou_callable}."""
        gdf = self.gdf.copy()
        for col_name, expression in rules.items():
            if callable(expression):
                gdf[col_name] = gdf.apply(expression, axis=1).astype(int)
            elif isinstance(expression, str):
                gdf[col_name] = gdf.eval(expression).astype(int)
        return self._wrap(gdf)

    def calculate_scores(self, weights: dict, score_column="score"):
        """Score pondéré normalisé : weights = {'col': poids, ...}."""
        gdf = self.gdf.copy()
        score = pd.Series(0.0, index=gdf.index)
        for col, weight in weights.items():
            col_range = gdf[col].max() - gdf[col].min()
            if col_range > 0:
                normalized = (gdf[col] - gdf[col].min()) / col_range
            else:
                normalized = pd.Series(0.0, index=gdf.index)
            score += normalized * weight
        gdf[score_column] = score
        return self._wrap(gdf)

    def rank_features(self, column: str, ascending=True, rank_column="rank"):
        """Classe les entités par rang sur une colonne."""
        gdf = self.gdf.copy()
        gdf[rank_column] = gdf[column].rank(ascending=ascending).astype(int)
        return self._wrap(gdf)

    # --- Généralisation cartographique ---------------------------- #

    def smooth_geometry(self, iterations: int = 3):
        """Lisse les géométries (algorithme de Chaikin)."""

        def _chaikin(coords, n):
            coords = list(coords)
            for _ in range(n):
                new = []
                for i in range(len(coords) - 1):
                    p1, p2 = coords[i], coords[i + 1]
                    new.append((0.75 * p1[0] + 0.25 * p2[0], 0.75 * p1[1] + 0.25 * p2[1]))
                    new.append((0.25 * p1[0] + 0.75 * p2[0], 0.25 * p1[1] + 0.75 * p2[1]))
                coords = new
            return coords

        def _smooth(geom):
            if geom.geom_type == "Polygon":
                ext = _chaikin(geom.exterior.coords, iterations)
                holes = [_chaikin(h.coords, iterations) for h in geom.interiors]
                return Polygon(ext, holes)
            if geom.geom_type == "MultiPolygon":
                return MultiPolygon([_smooth(p) for p in geom.geoms])
            if geom.geom_type == "LineString":
                return LineString(_chaikin(geom.coords, iterations))
            return geom

        gdf = self.gdf.copy()
        gdf["geometry"] = gdf.geometry.apply(_smooth)
        return self._wrap(gdf)

    def eliminate_small_polygons(self, min_area: float):
        """Fusionne les petits polygones avec leur plus grand voisin."""
        gdf = self.gdf.copy()
        small = gdf[gdf.geometry.area < min_area]
        large = gdf[gdf.geometry.area >= min_area].copy()
        for _, row in small.iterrows():
            best_idx, best_length = None, 0
            for lidx, lrow in large.iterrows():
                shared = row.geometry.intersection(lrow.geometry.boundary)
                if not shared.is_empty and shared.length > best_length:
                    best_length = shared.length
                    best_idx = lidx
            if best_idx is not None:
                large.at[best_idx, "geometry"] = unary_union(
                    [large.at[best_idx, "geometry"], row.geometry]
                )
        return self._wrap(large)

    # --- Conversion et export ------------------------------------- #

    def to_gpkg(self, path: str, layer: str = None):
        """Exporte en GeoPackage."""
        self.gdf.to_file(path, driver="GPKG", layer=layer)
        return path

    def to_shp(self, path: str):
        """Exporte en Shapefile."""
        self.gdf.to_file(path, driver="ESRI Shapefile")
        return path

    def to_geojson(self, path: str):
        """Exporte en GeoJSON."""
        self.gdf.to_file(path, driver="GeoJSON")
        return path

    def to_csv(self, path: str, include_geometry=True):
        """Exporte en CSV (géométrie en WKT si demandé)."""
        df = self.gdf.copy()
        if include_geometry:
            df["wkt_geometry"] = df.geometry.to_wkt()
        df = pd.DataFrame(df.drop(columns=[self.gdf.geometry.name]))
        df.to_csv(path, index=False)
        return path

    # ────────────────────────────────────────────────────────────────
    #  4. ANALYSE SPATIALE AVANCÉE (STATISTIQUES SPATIALES)
    # ────────────────────────────────────────────────────────────────

    def spatial_weights(self, method="queen", k=4, distance=None):
        """
        Construit une matrice de poids spatiaux.

        Args:
            method: 'queen', 'rook', 'knn' ou 'distance'.
            k: Nombre de voisins pour knn.
            distance: Seuil de distance pour method='distance'.

        Returns:
            libpysal.weights.W
        """
        try:
            from libpysal.weights import Queen, Rook, KNN, DistanceBand
        except ImportError:
            raise ImportError("libpysal est requis : pip install libpysal")
        m = method.lower()
        if m == "queen":
            return Queen.from_dataframe(self.gdf)
        elif m == "rook":
            return Rook.from_dataframe(self.gdf)
        elif m == "knn":
            return KNN.from_dataframe(self.gdf, k=k)
        elif m == "distance":
            if distance is None:
                raise ValueError("distance est requis pour method='distance'")
            return DistanceBand.from_dataframe(self.gdf, threshold=distance)
        raise ValueError(f"Méthode inconnue : {method}")

    def morans_i(self, column, method="queen", **kwargs):
        """
        Autocorrélation spatiale globale (I de Moran).

        Returns:
            dict: I, expected_I, p_value, z_score
        """
        try:
            from esda.moran import Moran
        except ImportError:
            raise ImportError("esda est requis : pip install esda")
        w = self.spatial_weights(method=method, **kwargs)
        y = self.gdf[column].values.astype(float)
        mi = Moran(y, w)
        return {
            "I": mi.I,
            "expected_I": mi.EI,
            "p_value": mi.p_sim,
            "z_score": mi.z_sim,
            "interpretation": (
                "regroupés (cluster)" if mi.I > mi.EI and mi.p_sim < 0.05
                else "dispersés" if mi.I < mi.EI and mi.p_sim < 0.05
                else "aléatoire"
            ),
        }

    def local_morans(self, column, method="queen", significance=0.05, **kwargs):
        """
        LISA – indicateurs locaux d'association spatiale.

        Ajoute les colonnes : lisa_I, lisa_p, lisa_q (quadrant), lisa_cluster.

        Returns:
            VectorTools avec colonnes LISA ajoutées.
        """
        try:
            from esda.moran import Moran_Local
        except ImportError:
            raise ImportError("esda est requis : pip install esda")
        w = self.spatial_weights(method=method, **kwargs)
        y = self.gdf[column].values.astype(float)
        lisa = Moran_Local(y, w)
        gdf = self.gdf.copy()
        gdf["lisa_I"] = lisa.Is
        gdf["lisa_p"] = lisa.p_sim
        gdf["lisa_q"] = lisa.q
        labels = {1: "High-High", 2: "Low-High", 3: "Low-Low", 4: "High-Low"}
        gdf["lisa_cluster"] = gdf.apply(
            lambda r: labels.get(r["lisa_q"], "ns")
            if r["lisa_p"] < significance else "Not significant",
            axis=1,
        )
        return self._wrap(gdf)

    def gearys_c(self, column, method="queen", **kwargs):
        """
        Indice C de Geary (autocorrélation spatiale).

        Returns:
            dict: C, expected_C, p_value, z_score
        """
        try:
            from esda.geary import Geary
        except ImportError:
            raise ImportError("esda est requis : pip install esda")
        w = self.spatial_weights(method=method, **kwargs)
        y = self.gdf[column].values.astype(float)
        gc = Geary(y, w)
        return {
            "C": gc.C,
            "expected_C": gc.EC,
            "p_value": gc.p_sim,
            "z_score": gc.z_sim,
            "interpretation": (
                "regroupés (cluster)" if gc.C < 1 and gc.p_sim < 0.05
                else "dispersés" if gc.C > 1 and gc.p_sim < 0.05
                else "aléatoire"
            ),
        }

    def spatial_autocorrelation_report(self, column, method="queen", **kwargs):
        """
        Rapport complet d'autocorrélation spatiale (Moran + Geary + LISA).

        Returns:
            dict: moran, geary, lisa_gdf (GeoDataFrame avec clusters LISA)
        """
        moran = self.morans_i(column, method=method, **kwargs)
        geary = self.gearys_c(column, method=method, **kwargs)
        lisa_vt = self.local_morans(column, method=method, **kwargs)
        cluster_counts = lisa_vt.gdf["lisa_cluster"].value_counts().to_dict()
        return {
            "moran": moran,
            "geary": geary,
            "lisa_clusters": cluster_counts,
            "lisa_gdf": lisa_vt.gdf,
        }

    # ────────────────────────────────────────────────────────────────
    #  5. ANALYSE DE CHANGEMENT ET TEMPORALITÉ
    # ────────────────────────────────────────────────────────────────

    def spatial_diff(self, other, key_column):
        """
        Compare deux couches d'une même zone et détecte les changements.

        Args:
            other: VectorTools ou GeoDataFrame (état T2).
            key_column: Colonne identifiant unique.

        Returns:
            dict: added, removed, modified (GeoDataFrames)
        """
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        keys_t1 = set(self.gdf[key_column])
        keys_t2 = set(other_gdf[key_column])
        added_keys = keys_t2 - keys_t1
        removed_keys = keys_t1 - keys_t2
        common_keys = keys_t1 & keys_t2
        added = other_gdf[other_gdf[key_column].isin(added_keys)].copy()
        removed = self.gdf[self.gdf[key_column].isin(removed_keys)].copy()
        t1_common = self.gdf[self.gdf[key_column].isin(common_keys)].set_index(key_column)
        t2_common = other_gdf[other_gdf[key_column].isin(common_keys)].set_index(key_column)
        modified_keys = []
        for k in common_keys:
            if not t1_common.loc[k, "geometry"].equals(t2_common.loc[k, "geometry"]):
                modified_keys.append(k)
        modified = other_gdf[other_gdf[key_column].isin(modified_keys)].copy()
        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged_count": len(common_keys) - len(modified_keys),
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "modified": len(modified),
                "unchanged": len(common_keys) - len(modified_keys),
            },
        }

    def track_changes(self, other, key_column, geom_tolerance=0.0):
        """
        Suit les évolutions géométriques entre deux états.

        Returns:
            GeoDataFrame avec colonnes : change_type, area_change, area_pct_change
        """
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        t1 = self.gdf.set_index(key_column)
        t2 = other_gdf.set_index(key_column)
        common = t1.index.intersection(t2.index)
        rows = []
        for k in common:
            g1, g2 = t1.loc[k, "geometry"], t2.loc[k, "geometry"]
            a1, a2 = g1.area, g2.area
            hausdorff = g1.hausdorff_distance(g2)
            if hausdorff <= geom_tolerance:
                change_type = "stable"
            elif a2 > a1:
                change_type = "extension"
            elif a2 < a1:
                change_type = "reduction"
            else:
                change_type = "deformation"
            rows.append({
                key_column: k,
                "geometry_t1": g1,
                "geometry_t2": g2,
                "geometry": g2,
                "area_t1": a1,
                "area_t2": a2,
                "area_change": a2 - a1,
                "area_pct_change": ((a2 - a1) / a1 * 100) if a1 > 0 else 0,
                "hausdorff_distance": hausdorff,
                "change_type": change_type,
            })
        result = gpd.GeoDataFrame(rows, crs=self.gdf.crs) if rows else gpd.GeoDataFrame()
        return self._wrap(result)

    def temporal_filter(self, date_column, start=None, end=None):
        """Filtre par plage temporelle."""
        gdf = self.gdf.copy()
        gdf[date_column] = pd.to_datetime(gdf[date_column])
        if start is not None:
            gdf = gdf[gdf[date_column] >= pd.to_datetime(start)]
        if end is not None:
            gdf = gdf[gdf[date_column] <= pd.to_datetime(end)]
        return self._wrap(gdf)

    def evolution_stats(self, other, key_column, measure_cols):
        """
        Statistiques de variation entre deux états.

        Args:
            other: VectorTools ou GeoDataFrame (état T2).
            key_column: Colonne identifiant unique.
            measure_cols: Liste de colonnes numériques à comparer.

        Returns:
            DataFrame avec variation absolue et pourcentage par colonne.
        """
        other_gdf = other.gdf if isinstance(other, VectorTools) else other
        t1 = self.gdf.set_index(key_column)
        t2 = other_gdf.set_index(key_column)
        common = t1.index.intersection(t2.index)
        if not isinstance(measure_cols, list):
            measure_cols = [measure_cols]
        rows = []
        for k in common:
            row = {key_column: k}
            for col in measure_cols:
                v1 = float(t1.loc[k, col]) if col in t1.columns else 0
                v2 = float(t2.loc[k, col]) if col in t2.columns else 0
                row[f"{col}_t1"] = v1
                row[f"{col}_t2"] = v2
                row[f"{col}_diff"] = v2 - v1
                row[f"{col}_pct"] = ((v2 - v1) / v1 * 100) if v1 != 0 else 0
                row[f"{col}_status"] = (
                    "increase" if v2 > v1 else "decrease" if v2 < v1 else "stable"
                )
            rows.append(row)
        return pd.DataFrame(rows)

    # ────────────────────────────────────────────────────────────────
    #  6. ANALYSE DE FRAGMENTATION ET PAYSAGE
    # ────────────────────────────────────────────────────────────────

    def landscape_metrics(self, class_column):
        """
        Calcule les métriques paysagères par classe.

        Returns:
            DataFrame : class, num_patches, total_area, mean_area, std_area,
                        largest_patch, smallest_patch, shannon_diversity
        """
        gdf = self.gdf.copy()
        classes = gdf[class_column].unique()
        rows = []
        total_landscape_area = gdf.geometry.area.sum()
        proportions = []
        for cls in classes:
            patches = gdf[gdf[class_column] == cls]
            areas = patches.geometry.area
            cls_area = areas.sum()
            proportion = cls_area / total_landscape_area if total_landscape_area > 0 else 0
            proportions.append(proportion)
            rows.append({
                "class": cls,
                "num_patches": len(patches),
                "total_area": cls_area,
                "mean_area": areas.mean(),
                "std_area": areas.std(),
                "largest_patch": areas.max(),
                "smallest_patch": areas.min(),
                "proportion": proportion,
            })
        # Shannon diversity
        proportions = np.array([p for p in proportions if p > 0])
        shannon = -np.sum(proportions * np.log(proportions)) if len(proportions) > 0 else 0
        result = pd.DataFrame(rows)
        result.attrs["shannon_diversity"] = shannon
        result.attrs["num_classes"] = len(classes)
        result.attrs["total_landscape_area"] = total_landscape_area
        return result

    def fragmentation_index(self, class_column):
        """
        Indice de fragmentation par classe.
        F = 1 − (plus grand patch / surface totale de la classe)

        Returns:
            DataFrame : class, num_patches, total_area, largest_patch, fragmentation
        """
        gdf = self.gdf.copy()
        rows = []
        for cls in gdf[class_column].unique():
            patches = gdf[gdf[class_column] == cls]
            areas = patches.geometry.area
            total = areas.sum()
            largest = areas.max()
            frag = 1 - (largest / total) if total > 0 else 0
            rows.append({
                "class": cls,
                "num_patches": len(patches),
                "total_area": total,
                "largest_patch": largest,
                "fragmentation": frag,
            })
        return pd.DataFrame(rows)

    def patch_connectivity(self, max_distance, class_column=None):
        """
        Graphe de connectivité entre patches à portée de max_distance.

        Returns:
            dict: graph (networkx), connected_components, connectivity_index
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx est requis : pip install networkx")
        from scipy.spatial import cKDTree

        gdf = self.gdf.copy()
        if class_column:
            gdf = gdf.sort_values(class_column)
        centroids_arr = np.array(
            list(gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        tree = cKDTree(centroids_arr)
        G = nx.Graph()
        for i in range(len(gdf)):
            G.add_node(i, **{
                "index": gdf.index[i],
                "class": gdf.iloc[i][class_column] if class_column else None,
            })
        pairs = tree.query_pairs(max_distance)
        for i, j in pairs:
            dist = np.linalg.norm(centroids_arr[i] - centroids_arr[j])
            G.add_edge(i, j, weight=dist)
        components = list(nx.connected_components(G))
        n = len(gdf)
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        connectivity = G.number_of_edges() / max_edges
        return {
            "graph": G,
            "num_nodes": n,
            "num_edges": G.number_of_edges(),
            "connected_components": len(components),
            "connectivity_index": connectivity,
        }

    def edge_density(self, class_column):
        """
        Densité de lisières (périmètre total / surface totale) par classe.

        Returns:
            DataFrame : class, total_perimeter, total_area, edge_density
        """
        gdf = self.gdf.copy()
        rows = []
        for cls in gdf[class_column].unique():
            patches = gdf[gdf[class_column] == cls]
            total_perim = patches.geometry.length.sum()
            total_area = patches.geometry.area.sum()
            rows.append({
                "class": cls,
                "total_perimeter": total_perim,
                "total_area": total_area,
                "edge_density": total_perim / total_area if total_area > 0 else 0,
            })
        return pd.DataFrame(rows)

    def isolation_index(self, class_column=None):
        """
        Indice d'isolement : distance au plus proche patch de même classe.

        Returns:
            VectorTools avec colonne 'isolation_distance' ajoutée.
        """
        from scipy.spatial import cKDTree

        gdf = self.gdf.copy()
        centroids_arr = np.array(
            list(gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        isolation = np.full(len(gdf), np.inf)
        if class_column:
            for cls in gdf[class_column].unique():
                mask = gdf[class_column] == cls
                idx_cls = np.where(mask.values)[0]
                if len(idx_cls) < 2:
                    continue
                pts = centroids_arr[idx_cls]
                tree = cKDTree(pts)
                dists, _ = tree.query(pts, k=2)
                for local_i, global_i in enumerate(idx_cls):
                    isolation[global_i] = dists[local_i, 1]
        else:
            tree = cKDTree(centroids_arr)
            dists, _ = tree.query(centroids_arr, k=2)
            isolation = dists[:, 1]
        gdf["isolation_distance"] = isolation
        return self._wrap(gdf)

    # ────────────────────────────────────────────────────────────────
    #  7. ACCESSIBILITÉ ET DESSERTE
    # ────────────────────────────────────────────────────────────────

    def isochrone(self, source: tuple, time_breaks: list, speed: float):
        """
        Zones isochrones autour d'un point source sur le réseau.

        Args:
            source: (x, y) du point de départ.
            time_breaks: Liste de durées en minutes (ex: [5, 15, 30]).
            speed: Vitesse en unités de carte par minute.

        Returns:
            GeoDataFrame avec une zone par isochrone.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx est requis : pip install networkx")
        G = self.build_network()
        nodes = list(G.nodes)
        src_node = min(nodes, key=lambda n: Point(source).distance(Point(n)))
        sorted_breaks = sorted(time_breaks)
        rows = []
        for t in sorted_breaks:
            max_dist = speed * t
            lengths = nx.single_source_dijkstra_path_length(
                G, src_node, cutoff=max_dist, weight="weight"
            )
            reachable = [Point(n) for n in lengths]
            if len(reachable) >= 3:
                hull = gpd.GeoSeries(reachable).union_all().convex_hull
            elif reachable:
                hull = gpd.GeoSeries(reachable).union_all().buffer(max_dist * 0.1)
            else:
                continue
            rows.append({"time_min": t, "distance": max_dist, "geometry": hull})
        return gpd.GeoDataFrame(rows, crs=self.gdf.crs) if rows else gpd.GeoDataFrame()

    def coverage_analysis(self, facilities, population_col, radius):
        """
        Taux de couverture : % de population à portée d'un équipement.

        Args:
            facilities: VectorTools ou GeoDataFrame des équipements (points).
            population_col: Colonne de population dans self.gdf.
            radius: Rayon de couverture.

        Returns:
            dict: total_pop, covered_pop, coverage_pct, covered_gdf
        """
        fac_gdf = facilities.gdf if isinstance(facilities, VectorTools) else facilities
        buffered = fac_gdf.geometry.buffer(radius).union_all()
        covered_mask = self.gdf.geometry.intersects(buffered)
        covered = self.gdf[covered_mask]
        total_pop = float(self.gdf[population_col].sum())
        covered_pop = float(covered[population_col].sum())
        return {
            "total_population": total_pop,
            "covered_population": covered_pop,
            "coverage_pct": (covered_pop / total_pop * 100) if total_pop > 0 else 0,
            "not_covered_population": total_pop - covered_pop,
            "covered_features": len(covered),
            "total_features": len(self.gdf),
            "covered_gdf": covered,
        }

    def voronoi_allocation(self, facilities=None):
        """
        Polygones de Voronoï (Thiessen) pour l'allocation spatiale.

        Args:
            facilities: VectorTools ou GeoDataFrame de points.
                        Si None, utilise self.gdf comme points.

        Returns:
            GeoDataFrame des polygones de Voronoï.
        """
        from scipy.spatial import Voronoi

        fac_gdf = self.gdf if facilities is None else (
            facilities.gdf if isinstance(facilities, VectorTools) else facilities
        )
        pts = np.array(
            list(fac_gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        if len(pts) < 3:
            raise ValueError("Au moins 3 points sont nécessaires pour Voronoï")
        # Extend bounding box to clip infinite regions
        xmin, ymin, xmax, ymax = fac_gdf.total_bounds
        dx, dy = xmax - xmin, ymax - ymin
        margin = max(dx, dy) * 2
        bbox = box(xmin - margin, ymin - margin, xmax + margin, ymax + margin)
        vor = Voronoi(pts)
        polygons = []
        for i, reg_idx in enumerate(vor.point_region):
            region = vor.regions[reg_idx]
            if not region or -1 in region:
                # Build polygon from finite + projected infinite vertices
                vertices = []
                for v_idx in region:
                    if v_idx >= 0:
                        vertices.append(vor.vertices[v_idx])
                if len(vertices) >= 3:
                    poly = Polygon(vertices).intersection(bbox)
                else:
                    poly = Point(pts[i]).buffer(margin).intersection(bbox)
            else:
                poly = Polygon([vor.vertices[v] for v in region]).intersection(bbox)
            polygons.append(poly)
        result = gpd.GeoDataFrame(
            fac_gdf.drop(columns=[fac_gdf.geometry.name]).reset_index(drop=True),
            geometry=polygons,
            crs=fac_gdf.crs,
        )
        # Clip to convex hull of original data
        hull = self.gdf.geometry.union_all().convex_hull.buffer(dx * 0.05)
        result["geometry"] = result.geometry.intersection(hull)
        return result

    def gravity_model(self, destinations, weight_col, beta=1.0):
        """
        Modèle gravitaire d'interaction spatiale.

        interaction(i,j) = (W_i * W_j) / distance(i,j)^beta

        Args:
            destinations: VectorTools ou GeoDataFrame.
            weight_col: Colonne de poids (masse) dans les deux couches.
            beta: Exposant de friction (défaut 1.0).

        Returns:
            DataFrame : origin, destination, weight_o, weight_d, distance, interaction
        """
        dest_gdf = destinations.gdf if isinstance(destinations, VectorTools) else destinations
        rows = []
        for i, row_o in self.gdf.iterrows():
            for j, row_d in dest_gdf.iterrows():
                dist = row_o.geometry.centroid.distance(row_d.geometry.centroid)
                if dist > 0:
                    w_o = float(row_o[weight_col])
                    w_d = float(row_d[weight_col])
                    interaction = (w_o * w_d) / (dist ** beta)
                    rows.append({
                        "origin": i,
                        "destination": j,
                        "weight_origin": w_o,
                        "weight_destination": w_d,
                        "distance": dist,
                        "interaction": interaction,
                    })
        return pd.DataFrame(rows)

    def market_area(self, centers, demand_col, friction=2.0):
        """
        Zones de chalandise (Huff model).

        Chaque entité est assignée au centre ayant la plus forte attraction.
        attraction(j) = weight_j / distance(i,j)^friction

        Args:
            centers: VectorTools ou GeoDataFrame des centres (avec demand_col).
            demand_col: Colonne de poids/attractivité des centres.
            friction: Exposant de friction distance.

        Returns:
            VectorTools avec colonnes assignation et probabilités.
        """
        centers_gdf = centers.gdf if isinstance(centers, VectorTools) else centers
        gdf = self.gdf.copy()
        best_center = []
        best_prob = []
        for _, row in gdf.iterrows():
            attractions = []
            for cidx, crow in centers_gdf.iterrows():
                dist = row.geometry.centroid.distance(crow.geometry.centroid)
                w = float(crow[demand_col])
                a = w / (dist ** friction) if dist > 0 else float("inf")
                attractions.append((cidx, a))
            total = sum(a for _, a in attractions)
            if total > 0:
                attractions = [(c, a / total) for c, a in attractions]
            best = max(attractions, key=lambda x: x[1])
            best_center.append(best[0])
            best_prob.append(best[1])
        gdf["assigned_center"] = best_center
        gdf["attraction_prob"] = best_prob
        return self._wrap(gdf)

    # ────────────────────────────────────────────────────────────────
    #  8. INTERPOLATION ET ESTIMATION SURFACIQUE
    # ────────────────────────────────────────────────────────────────

    def idw_interpolation(self, value_col, resolution=100, power=2):
        """
        Interpolation par pondération inverse de la distance (IDW).

        Args:
            value_col: Colonne de valeurs à interpoler.
            resolution: Nombre de cellules par axe.
            power: Exposant de distance (défaut 2).

        Returns:
            dict: grid (2D array), x, y, extent
        """
        pts = np.array(
            list(self.gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        values = self.gdf[value_col].values.astype(float)
        xmin, ymin, xmax, ymax = self.gdf.total_bounds
        xi = np.linspace(xmin, xmax, resolution)
        yi = np.linspace(ymin, ymax, resolution)
        xx, yy = np.meshgrid(xi, yi)
        grid = np.zeros_like(xx)
        for i in range(resolution):
            for j in range(resolution):
                dists = np.sqrt((pts[:, 0] - xx[i, j]) ** 2 + (pts[:, 1] - yy[i, j]) ** 2)
                zero_mask = dists == 0
                if zero_mask.any():
                    grid[i, j] = values[zero_mask][0]
                else:
                    weights = 1.0 / (dists ** power)
                    grid[i, j] = np.sum(weights * values) / np.sum(weights)
        return {"grid": grid, "x": xi, "y": yi, "extent": (xmin, xmax, ymin, ymax)}

    def thiessen_polygons(self):
        """
        Diagramme de Voronoï / polygones de Thiessen.

        Returns:
            GeoDataFrame des polygones de Thiessen.
        """
        return self.voronoi_allocation(facilities=None)

    def kriging(self, value_col, variogram_model="linear", resolution=100):
        """
        Krigeage ordinaire (estimation géostatistique).

        Args:
            value_col: Colonne de valeurs.
            variogram_model: Modèle de variogramme ('linear', 'power', 'gaussian', 'spherical', 'exponential').
            resolution: Nombre de cellules par axe.

        Returns:
            dict: grid, variance, x, y, extent
        """
        try:
            from pykrige.ok import OrdinaryKriging
        except ImportError:
            raise ImportError("pykrige est requis : pip install pykrige")
        pts = np.array(
            list(self.gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        values = self.gdf[value_col].values.astype(float)
        xmin, ymin, xmax, ymax = self.gdf.total_bounds
        xi = np.linspace(xmin, xmax, resolution)
        yi = np.linspace(ymin, ymax, resolution)
        ok = OrdinaryKriging(
            pts[:, 0], pts[:, 1], values,
            variogram_model=variogram_model,
            verbose=False, enable_plotting=False,
        )
        grid, variance = ok.execute("grid", xi, yi)
        return {
            "grid": grid,
            "variance": variance,
            "x": xi,
            "y": yi,
            "extent": (xmin, xmax, ymin, ymax),
        }

    def tin_surface(self, value_col):
        """
        Triangulation de Delaunay → surface TIN.

        Returns:
            dict: triangulation (Delaunay), vertices, values, GeoDataFrame des triangles
        """
        from scipy.spatial import Delaunay

        pts = np.array(
            list(self.gdf.geometry.centroid.apply(lambda g: (g.x, g.y)))
        )
        values = self.gdf[value_col].values.astype(float)
        tri = Delaunay(pts)
        triangles = []
        tri_values = []
        for simplex in tri.simplices:
            coords = [tuple(pts[s]) for s in simplex]
            coords.append(coords[0])  # close ring
            triangles.append(Polygon(coords))
            tri_values.append(float(np.mean(values[simplex])))
        result = gpd.GeoDataFrame(
            {value_col: tri_values, "geometry": triangles},
            crs=self.gdf.crs,
        )
        return {
            "triangulation": tri,
            "vertices": pts,
            "values": values,
            "gdf": result,
        }

    def contour_lines(self, value_col, levels=10, resolution=100):
        """
        Lignes d'isovaleurs (isolignes) à partir de points.

        Args:
            value_col: Colonne de valeurs.
            levels: Nombre de niveaux ou liste de valeurs.
            resolution: Résolution de la grille d'interpolation.

        Returns:
            GeoDataFrame : level, geometry (LineString)
        """
        import matplotlib.pyplot as plt
        from matplotlib.contour import QuadContourSet

        interp = self.idw_interpolation(value_col, resolution=resolution)
        fig, ax = plt.subplots()
        cs = ax.contour(interp["x"], interp["y"], interp["grid"], levels=levels)
        plt.close(fig)
        rows = []
        for level_val, paths in zip(cs.levels, cs.allsegs):
            for seg in paths:
                if len(seg) >= 2:
                    rows.append({
                        "level": float(level_val),
                        "geometry": LineString(seg),
                    })
        if rows:
            return gpd.GeoDataFrame(rows, crs=self.gdf.crs)
        return gpd.GeoDataFrame(columns=["level", "geometry"], crs=self.gdf.crs)

    # --- Représentation ------------------------------------------- #

    def __repr__(self):
        return f"VectorTools({len(self.gdf)} features, CRS={self.gdf.crs})"

    def __len__(self):
        return len(self.gdf)


# ════════════════════════════════════════════════════════════════════
#  RasterTools – boîte à outils complète pour données raster
# ════════════════════════════════════════════════════════════════════

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
