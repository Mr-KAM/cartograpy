import geopandas as gpd
import pandas as pd
import os

def load(filepath):
    """
    Charge un fichier vectoriel quel que soit son format (.shp, .geojson, .gpkg, .kml, .csv, .parquet).

    Paramètres:
    -----------
    filepath : str
        Chemin vers le fichier à charger.

    Retourne:
    ---------
    GeoDataFrame ou DataFrame
    """
    ext = filepath.split('.')[-1].lower()

    if ext in ['shp', 'geojson', 'gpkg', 'kml']:
        return gpd.read_file(filepath)
    elif ext == 'csv':
        return pd.read_csv(filepath)
    elif ext == 'parquet':
        return pd.read_parquet(filepath)
    else:
        raise ValueError(f"Format '{ext}' non supporté pour le chargement.")

import os

def save(geodf, file_extension, filename="output", timestamp=False):
    """
    Sauvegarde un GeoDataFrame/DataFrame dans différents formats avec option timestamp.

    Paramètres:
    -----------
    geodf : GeoDataFrame ou DataFrame
        Données à sauvegarder.

    file_extension : str
        Format de sortie (shp, geojson, gpkg, kml, csv, parquet, xlsx, feather).

    filename : str, optional
        Nom de base du fichier sans extension.

    timestamp : bool, optional
        Ajouter un timestamp pour historiser les versions.

    Retourne:
    ---------
    str
        Chemin du fichier sauvegardé.
    """
    import datetime

    if not isinstance(geodf, (gpd.GeoDataFrame, pd.DataFrame)):
        raise TypeError("geodf doit être un GeoDataFrame ou un DataFrame.")

    file_extension = file_extension.lower()
    supported_formats = ['geojson', 'shp', 'gpkg', 'kml', 'csv', 'parquet', 'xlsx', 'feather']

    if file_extension not in supported_formats:
        raise ValueError(f"Extension '{file_extension}' non supportée. Choisissez parmi {supported_formats}.")

    if timestamp:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename}_{now}"

    output_path = f"{filename}.{file_extension}"

    if file_extension == 'geojson':
        geodf.to_file(output_path, driver='GeoJSON')
    elif file_extension == 'shp':
        geodf.to_file(output_path, driver='ESRI Shapefile')
    elif file_extension == 'gpkg':
        geodf.to_file(output_path, driver='GPKG')
    elif file_extension == 'kml':
        geodf.to_file(output_path, driver='KML')
    elif file_extension == 'csv':
        if isinstance(geodf, gpd.GeoDataFrame):
            geodf = geodf.drop(columns='geometry', errors='ignore')
        geodf.to_csv(output_path, index=False)
    elif file_extension == 'parquet':
        if isinstance(geodf, gpd.GeoDataFrame):
            geodf = geodf.drop(columns='geometry', errors='ignore')
        geodf.to_parquet(output_path, index=False)
    elif file_extension == 'xlsx':
        if isinstance(geodf, gpd.GeoDataFrame):
            geodf = geodf.drop(columns='geometry', errors='ignore')
        geodf.to_excel(output_path, index=False)
    elif file_extension == 'feather':
        if isinstance(geodf, gpd.GeoDataFrame):
            geodf = geodf.drop(columns='geometry', errors='ignore')
        geodf.to_feather(output_path)

    print(f"✅ Fichier sauvegardé : {os.path.abspath(output_path)}")
    return output_path


import os

def list_geofiles(folder_path):
    """
    Liste tous les fichiers géospatiaux présents dans un dossier.

    Paramètres:
    -----------
    folder_path : str
        Chemin du dossier à explorer.

    Retourne:
    ---------
    list
        Liste des chemins relatifs aux fichiers géospatiaux trouvés.
    """
    geospatial_extensions = ['.shp', '.geojson', '.gpkg', '.kml', '.csv', '.parquet',".gpx"]

    files = []
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in geospatial_extensions):
                files.append(os.path.join(root, filename))

    return files




def centroids(geodf):
    """
    Crée un nouveau GeoDataFrame contenant les centroïdes des géométries
    tout en conservant tous les attributs du GeoDataFrame initial.

    Paramètres:
    -----------
    geodf : GeoDataFrame
        Le GeoDataFrame source dont on veut extraire les centroïdes

    Retourne:
    ---------
    GeoDataFrame
        Un nouveau GeoDataFrame contenant les centroïdes et tous les attributs originaux
    """
    # Créer une copie du GeoDataFrame original pour éviter de le modifier
    centroids_gdf = geodf.copy()

    # Calculer les centroïdes de chaque géométrie
    centroids_gdf['geometry'] = centroids_gdf['geometry'].centroid

    # Conserver le même système de coordonnées
    centroids_gdf.crs = geodf.crs

    return centroids_gdf


def join(from_tuple, to_tuple, columns_to_join=None, how='left', suffixes=('_from', '_to')):
    """
    Réalise une jointure entre deux GeoDataFrames sur des colonnes spécifiées.

    Paramètres:
    -----------
    from_tuple : tuple (GeoDataFrame, str)
        Tuple contenant le GeoDataFrame source et la colonne de jointure
        Format: (geodataframe_source, colonne_jointure)

    to_tuple : tuple (GeoDataFrame, str)
        Tuple contenant le GeoDataFrame cible et la colonne de jointure
        Format: (geodataframe_cible, colonne_jointure)

    columns_to_join : list, optional
        Liste des colonnes à conserver du second GeoDataFrame (to_tuple).
        Si None, toutes les colonnes seront conservées.

    how : str, optional
        Type de jointure ('left', 'right', 'inner', 'outer').
        Par défaut: 'left'

    suffixes : tuple, optional
        Suffixes à ajouter aux noms des colonnes en cas de doublon.
        Par défaut: ('_from', '_to')

    Retourne:
    ---------
    GeoDataFrame
        Un nouveau GeoDataFrame contenant les données jointes
    """
    # Extraction des éléments des tuples
    source_gdf, source_column = from_tuple
    target_gdf, target_column = to_tuple

    # Vérification des entrées
    if not isinstance(source_gdf, gpd.GeoDataFrame) or not isinstance(target_gdf, gpd.GeoDataFrame):
        raise TypeError("Les deux premiers éléments des tuples doivent être des GeoDataFrames")

    if source_column not in source_gdf.columns:
        raise ValueError(f"La colonne '{source_column}' n'existe pas dans le GeoDataFrame source")

    if target_column not in target_gdf.columns:
        raise ValueError(f"La colonne '{target_column}' n'existe pas dans le GeoDataFrame cible")

    # Préparation du GeoDataFrame cible pour la jointure
    target_copy = target_gdf.copy()

    # Si columns_to_join est spécifié, ne conserver que ces colonnes + la colonne de jointure
    if columns_to_join is not None:
        # S'assurer que la colonne de jointure est incluse
        if target_column not in columns_to_join:
            columns_to_keep = [target_column] + columns_to_join
        else:
            columns_to_keep = columns_to_join

        # Vérifier que toutes les colonnes existent
        missing_columns = [col for col in columns_to_keep if col not in target_copy.columns]
        if missing_columns:
            raise ValueError(f"Colonnes non trouvées dans le GeoDataFrame cible: {missing_columns}")

        # Ne garder que les colonnes spécifiées
        target_copy = target_copy[columns_to_keep]

    # Réaliser la jointure
    joined_gdf = source_gdf.merge(
        target_copy,
        left_on=source_column,
        right_on=target_column,
        how=how,
        suffixes=suffixes
    )

    # S'assurer que le résultat est bien un GeoDataFrame avec la géométrie du GeoDataFrame source
    if not isinstance(joined_gdf, gpd.GeoDataFrame):
        joined_gdf = gpd.GeoDataFrame(joined_gdf, geometry=source_gdf.geometry.name)

    # Conserver le CRS du GeoDataFrame source
    joined_gdf.crs = source_gdf.crs

    return joined_gdf
