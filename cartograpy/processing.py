import geopandas as gpd
import pandas as pd
import os
import random
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely import wkt
from typing import List, Union, Optional
import warnings
import datetime
import numpy as np
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


def add_column(df, column_name, expression,globals_dict=None):
    """
    Ajoute une nouvelle colonne à un DataFrame/GeoDataFrame selon une expression.

    Paramètres
    ----------
    df : DataFrame ou GeoDataFrame
        Tableau de données d'entrée.
    column_name : str
        Nom de la nouvelle colonne à créer.
    expression : str
        Expression à évaluer, utilisant 'row' (ex: "row['col1'] + row['col2']").
    global_dic : Liste de package à importer
    
    Retourne
    -------
    Le DataFrame/GeoDataFrame modifié (avec la nouvelle colonne).
    """

    _globals = {"random": random, "np":np}
    if globals_dict:
        _globals.update(globals_dict)
    df[column_name] = df.apply(lambda row: eval(expression, _globals, {'row': row}), axis=1)
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
    emprise_totale = gdf_emprise.geometry.unary_union
    
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
