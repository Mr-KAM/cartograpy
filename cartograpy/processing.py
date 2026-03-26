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
    types = gdf.geometry.geom_type.value_counts()
    output={}
    for geom_type, count in types.items():
        percentage = (count / len(gdf)) * 100
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
