"""cartograpy.mapper.hexgrid — grilles hexagonales et cartes hexbin.

Génère une grille hexagonale régulière sur une zone d'étude (via le paquet
`geohexgrid`), y agrège des données ponctuelles ou polygonales, et trace le
résultat en carte choroplèthe. Le GeoDataFrame produit est standard et
réutilisable tel quel avec `cartograpy.mapper.bivariate` pour une carte
hexagonale bivariée (deux variables croisées par hexagone).
"""

import logging

import geopandas as gpd
import matplotlib.pyplot as plt
import geohexgrid as ghg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Génération de la grille hexagonale
# ---------------------------------------------------------------------------

def make_hex_grid(source, hex_size, crs=None, trim_mode="intersect"):
    """
    Génère une grille d'hexagones réguliers (sommet plat) couvrant une zone.

    Paramètres:
    -----------
    source : geopandas.GeoDataFrame | tuple (minx, miny, maxx, maxy)
        Zone à couvrir : un GeoDataFrame (son étendue et son CRS sont
        utilisés, et les hexagones hors zone sont écartés selon
        `trim_mode`), ou un tuple de bornes brut (ex. `gdf.total_bounds`)
        — dans ce cas `crs` doit être fourni et tous les hexagones de
        l'étendue rectangulaire sont conservés.
    hex_size : float
        Rayon (circumradius) de l'hexagone, dans l'unité du CRS. Utiliser
        un CRS projeté (mètres) pour un maillage régulier réel — un CRS
        géographique (degrés) donne des hexagones déformés selon la
        latitude.
    crs : str, optionnel
        CRS de la grille. Requis si `source` est un tuple de bornes ;
        ignoré (repris de `source.crs`) si `source` est un GeoDataFrame.
    trim_mode : str
        Si `source` est un GeoDataFrame : `"intersect"` (défaut, ne garde
        que les hexagones qui touchent les géométries) ou `"clip"`
        (découpe les hexagones aux géométries, peut créer des fragments).
        Ignoré si `source` est un tuple de bornes.

    Retourne:
    ---------
    geopandas.GeoDataFrame : colonnes `cell_id`, `geometry`.

    Raises:
    -------
        ValueError : si `source` est un GeoDataFrame sans CRS, ou un tuple
            de bornes sans `crs` fourni.

    Exemples:
    ---------
        >>> grid = make_hex_grid(civ_regions, hex_size=25_000)  # 25 km, CRS projeté
        >>> grid = make_hex_grid(points.total_bounds, hex_size=250, crs="EPSG:32630")
    """
    if isinstance(source, gpd.GeoDataFrame):
        if source.crs is None:
            raise ValueError("`source` doit avoir un CRS défini.")
        return ghg.make_grid_from_gdf(source, R=hex_size, trim_mode=trim_mode)

    minx, miny, maxx, maxy = source
    if crs is None:
        raise ValueError("`crs` est requis quand `source` est un tuple de bornes.")
    return ghg.make_grid_from_bounds(minx, miny, maxx, maxy, R=hex_size, crs=crs)


# ---------------------------------------------------------------------------
# 2. Agrégation de données dans la grille hexagonale
# ---------------------------------------------------------------------------

def aggregate_to_hex(source_gdf, hex_grid, value_cols, agg_funcs=None,
                      count_col="n_points", predicate="within"):
    """
    Agrège des données ponctuelles (ou polygonales) dans chaque hexagone.

    Paramètres:
    -----------
    source_gdf : geopandas.GeoDataFrame
        Données source (points d'occurrence, placettes, etc.). Reprojeté
        automatiquement sur le CRS de `hex_grid` si besoin.
    hex_grid : geopandas.GeoDataFrame
        Grille produite par `make_hex_grid()`.
    value_cols : list[str]
        Colonnes numériques à agréger (ex. `["richesse_especes", "biomasse"]`).
    agg_funcs : dict, optionnel
        Fonction d'agrégation par colonne (ex. `{"richesse_especes": "mean"}`).
        Par défaut : `"mean"` pour toutes les colonnes.
    count_col : str
        Nom de la colonne comptant le nombre d'entités par hexagone.
    predicate : str
        Prédicat spatial pour la jointure (`geopandas.sjoin`), `"within"`
        par défaut (adapté aux points) — utiliser `"intersects"` pour des
        polygones à cheval sur plusieurs hexagones.

    Retourne:
    ---------
    geopandas.GeoDataFrame : `hex_grid` enrichi des colonnes agrégées et de
    `count_col`. Les hexagones sans donnée sont conservés avec NaN (et
    `count_col` à 0) — à filtrer si besoin (ex. `result[result.n_points >= 3]`).

    Exemples:
    ---------
        >>> hex_data = aggregate_to_hex(
        ...     points, grid, value_cols=["richesse_especes", "indice_structure"],
        ... )
        >>> hex_data = hex_data[hex_data["n_points"] >= 3]
    """
    if source_gdf.crs != hex_grid.crs:
        source_gdf = source_gdf.to_crs(hex_grid.crs)

    if agg_funcs is None:
        agg_funcs = {col: "mean" for col in value_cols}

    joined = gpd.sjoin(
        source_gdf, hex_grid[["cell_id", "geometry"]],
        how="inner", predicate=predicate,
    )

    agg_dict = {col: agg_funcs.get(col, "mean") for col in value_cols}
    grouped = joined.groupby("cell_id").agg(agg_dict)
    counts = joined.groupby("cell_id").size().rename(count_col)

    result = hex_grid.merge(grouped, on="cell_id", how="left")
    result = result.merge(counts, on="cell_id", how="left")
    result[count_col] = result[count_col].fillna(0).astype(int)

    return result


# ---------------------------------------------------------------------------
# 3. Tracé : carte choroplèthe hexagonale
# ---------------------------------------------------------------------------

def plot_hexgrid_choropleth(
    hex_gdf, column,
    cmap="viridis",
    min_count=None, count_col="n_points",
    edgecolor="white", linewidth=0.3,
    title=None, figsize=(10, 8),
    show_colorbar=True, colorbar_label=None,
    ax_map=None, transform=None,
    save_path=None, dpi=300,
    **plot_kwargs,
):
    """
    Trace une carte choroplèthe sur une grille hexagonale (une variable).

    Pour une carte hexagonale bivariée (deux variables croisées par
    hexagone), passer le GeoDataFrame résultant de `aggregate_to_hex()`
    directement à `cartograpy.mapper.plot_bivariate_choropleth()`.

    Paramètres:
    -----------
    hex_gdf : geopandas.GeoDataFrame
        Grille hexagonale agrégée, ex. sortie de `aggregate_to_hex()`.
    column : str
        Colonne numérique à cartographier.
    cmap : str | Colormap
        Palette de couleurs.
    min_count : int, optionnel
        Si fourni avec `count_col` présent dans `hex_gdf`, ne trace que les
        hexagones où `count_col >= min_count` (filtre les cellules peu
        échantillonnées).
    count_col : str
        Nom de la colonne de comptage (voir `aggregate_to_hex`).
    edgecolor, linewidth :
        Style des contours des hexagones.
    title : str, optionnel
        Titre de la carte.
    figsize : tuple
        Taille de la figure, ignorée si `ax_map` est fourni.
    show_colorbar : bool
        Afficher la barre de couleur.
    colorbar_label : str, optionnel
        Étiquette de la barre de couleur (par défaut : `column`).
    ax_map : matplotlib.axes.Axes, optionnel
        Axe existant sur lequel dessiner (ex. `Map.ax` d'un objet
        `cartograpy.mapper.Map` déjà configuré) au lieu d'en créer un
        nouveau. Dans ce cas `figsize` est ignoré.
    transform : cartopy.crs.CRS, optionnel
        Transform à passer à `GeoDataFrame.plot()` — utile si `ax_map` est
        une GeoAxes cartopy avec une projection.
    save_path : str, optionnel
        Si fourni, sauvegarde la figure à ce chemin.
    dpi : int
        Résolution de sauvegarde.
    **plot_kwargs
        Paramètres additionnels passés à `GeoDataFrame.plot()`.

    Retourne:
    ---------
    tuple : (figure, axe).

    Exemples:
    ---------
        >>> fig, ax = plot_hexgrid_choropleth(
        ...     hex_data, "richesse_especes", cmap="YlGn", min_count=3,
        ... )
    """
    data = hex_gdf
    if min_count is not None and count_col in hex_gdf.columns:
        data = data[data[count_col] >= min_count]

    if ax_map is None:
        fig, ax_map = plt.subplots(figsize=figsize)
    else:
        fig = ax_map.get_figure()

    plot_kw = dict(
        column=column, cmap=cmap, edgecolor=edgecolor, linewidth=linewidth,
        legend=show_colorbar,
        legend_kwds={"label": colorbar_label or column} if show_colorbar else None,
    )
    if transform is not None:
        plot_kw["transform"] = transform
    plot_kw.update(plot_kwargs)
    data.plot(ax=ax_map, **plot_kw)

    ax_map.set_axis_off()
    if title:
        ax_map.set_title(title, fontsize=14, fontweight="bold")

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
        logger.info(f"✅ Carte hexagonale sauvegardée : {save_path}")

    return fig, ax_map
