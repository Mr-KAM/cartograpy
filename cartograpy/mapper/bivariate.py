"""cartograpy.mapper.bivariate — cartes choroplèthes bivariées.

Croise deux variables continues sur une même carte via une palette de
couleurs n x n (méthode de Joshua Stevens :
https://www.joshuastevens.net/cartography/make-a-bivariate-choropleth-map/),
avec sa légende carrée dédiée.
"""

import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Palettes bivariées
# ---------------------------------------------------------------------------

BIVARIATE_PALETTES = {
    "blue_pink": [
        "#e8e8e8", "#ace4e4", "#5ac8c8",
        "#dfb0d6", "#a5add3", "#5698b9",
        "#be64ac", "#8c62aa", "#3b4994",
    ],
    "teal_orange": [
        "#e8e8e8", "#b8d6be", "#73ae80",
        "#e4acac", "#ad9ea5", "#5a9178",
        "#c85a5a", "#985356", "#414173",
    ],
    "green_purple": [
        "#f3f3f3", "#c4dbec", "#7ba4d0",
        "#e7d0c8", "#b6b3c9", "#5f7ab3",
        "#c68e79", "#8e6a94", "#4a3b6b",
    ],
}


def list_bivariate_palettes():
    """Liste les noms des palettes bivariées intégrées."""
    return list(BIVARIATE_PALETTES.keys())


def _interpolate_palette_grid(grid, n):
    """Interpole bilinéairement une grille de couleurs (m, m, 3) vers (n, n, 3)."""
    m = grid.shape[0]
    if m == n:
        return grid
    src = np.linspace(0, 1, m)
    dst = np.linspace(0, 1, n)
    step1 = np.empty((n, m, 3))
    for c in range(3):
        for j in range(m):
            step1[:, j, c] = np.interp(dst, src, grid[:, j, c])
    step2 = np.empty((n, n, 3))
    for c in range(3):
        for i in range(n):
            step2[i, :, c] = np.interp(dst, src, step1[i, :, c])
    return np.clip(step2, 0, 1)


def get_bivariate_palette(palette="blue_pink", n_classes=3):
    """
    Résout une palette bivariée en grille de couleurs RGB (n_classes, n_classes, 3).

    Paramètres:
    -----------
    palette : str | list[str] | array-like
        - str : nom d'une palette intégrée (voir `list_bivariate_palettes()`).
        - list[str] : n_classes**2 couleurs hex, en ligne par ligne, depuis
          (var1=bas, var2=bas) vers (var1=haut, var2=haut).
        - array-like (n_classes, n_classes, 3) : grille de couleurs RGB déjà
          construite (ex. sortie d'un appel précédent à cette fonction).
    n_classes : int
        Nombre de classes par variable (grille n_classes x n_classes). Pour
        une palette intégrée d'une autre taille native, elle est interpolée
        bilinéairement.

    Retourne:
    ---------
    numpy.ndarray : grille (n_classes, n_classes, 3), indexée [var2-1, var1-1].

    Exemples:
    ---------
        >>> get_bivariate_palette("blue_pink")
        >>> get_bivariate_palette("blue_pink", n_classes=4)  # interpolée
        >>> get_bivariate_palette(["#fff", "#aaa", "#000", "#f00"], n_classes=2)
    """
    if isinstance(palette, str):
        if palette not in BIVARIATE_PALETTES:
            raise ValueError(
                f"Palette bivariée '{palette}' inconnue. "
                f"Disponibles : {list_bivariate_palettes()}"
            )
        hex_colors = BIVARIATE_PALETTES[palette]
        native_n = int(round(len(hex_colors) ** 0.5))
        grid = np.array([mcolors.to_rgb(c) for c in hex_colors]).reshape(native_n, native_n, 3)
        return _interpolate_palette_grid(grid, n_classes)

    arr = np.asarray(palette, dtype=object)
    if arr.ndim == 1:
        expected = n_classes * n_classes
        if len(arr) != expected:
            raise ValueError(
                f"{expected} couleurs attendues pour n_classes={n_classes}, "
                f"{len(arr)} fournies."
            )
        grid = np.array([mcolors.to_rgb(c) for c in arr]).reshape(n_classes, n_classes, 3)
    else:
        grid = np.asarray(palette, dtype=float)

    if grid.shape != (n_classes, n_classes, 3):
        raise ValueError(
            f"La grille de couleurs doit être de forme ({n_classes}, {n_classes}, 3), "
            f"reçu {grid.shape}."
        )
    return grid


def _resolve_color_ramp(spec, n):
    """Échantillonne `spec` en n couleurs RGB (n, 3), du bas (valeur faible)
    au haut (valeur forte) de la variable.

    `spec` accepte : nom de colormap matplotlib (str), Colormap, ou liste/
    tuple d'au moins 2 couleurs (dégradé linéaire entre elles)."""
    if isinstance(spec, mcolors.Colormap):
        cmap = spec
    elif isinstance(spec, str):
        cmap = plt.get_cmap(spec)
    elif isinstance(spec, (list, tuple)):
        if len(spec) < 2:
            raise ValueError("Un dégradé de couleurs nécessite au moins 2 couleurs.")
        cmap = mcolors.LinearSegmentedColormap.from_list("_bivariate_ramp", spec)
    else:
        raise TypeError(
            "Une rampe de couleurs doit être un nom de colormap, une "
            f"Colormap, ou une liste de couleurs — reçu {type(spec).__name__}."
        )
    return np.array([cmap(x)[:3] for x in np.linspace(0, 1, n)])


def generate_bivariate_palette(var1_colors, var2_colors, n_classes=3, blend="multiply"):
    """
    Génère une palette bivariée n x n en croisant deux rampes de couleurs
    (une par variable), au lieu de choisir parmi les palettes intégrées ou
    de fournir une grille complète à la main.

    Paramètres:
    -----------
    var1_colors, var2_colors : str | Colormap | list[str]
        Rampe de couleurs pour chaque variable, du niveau bas au niveau
        haut : nom d'un colormap matplotlib (ex. `"Blues"`), objet
        `Colormap`, ou liste d'au moins 2 couleurs (dégradé linéaire entre
        elles, ex. `["#f0f0f0", "#08519c"]`).
    n_classes : int
        Taille de la grille n x n (nombre de classes par variable).
    blend : str
        Comment combiner les deux rampes à chaque cellule de la grille :
        - `"multiply"` (défaut) : produit terme à terme — assombrit le
          coin où les deux variables sont hautes, cohérent avec l'esprit
          des palettes intégrées (`blue_pink`, etc.).
        - `"mean"` : moyenne simple des deux couleurs.
        - `"screen"` : `1 - (1-a)(1-b)` — éclaircit au lieu d'assombrir.

    Retourne:
    ---------
    numpy.ndarray : grille (n_classes, n_classes, 3), utilisable directement
    comme `palette=` dans `plot_bivariate_choropleth`/`get_bivariate_palette`.

    Exemples:
    ---------
        >>> grid = generate_bivariate_palette("Blues", "Reds")
        >>> fig, ax, gdf_bi = plot_bivariate_choropleth(
        ...     regions, "densite", "revenu", palette=grid,
        ... )
        >>> generate_bivariate_palette(["#f7fbff", "#08306b"], ["#fff5f0", "#67000d"])
    """
    ramp1 = _resolve_color_ramp(var1_colors, n_classes)
    ramp2 = _resolve_color_ramp(var2_colors, n_classes)

    a = ramp1[np.newaxis, :, :]   # (1, n, 3) — varie selon var1 (colonnes)
    b = ramp2[:, np.newaxis, :]   # (n, 1, 3) — varie selon var2 (lignes)
    a, b = np.broadcast_to(a, (n_classes, n_classes, 3)), np.broadcast_to(b, (n_classes, n_classes, 3))

    if blend == "multiply":
        grid = a * b
    elif blend == "mean":
        grid = (a + b) / 2
    elif blend == "screen":
        grid = 1 - (1 - a) * (1 - b)
    else:
        raise ValueError(f"blend doit être 'multiply', 'mean' ou 'screen', reçu: {blend!r}")

    return np.clip(grid, 0, 1)


def preview_bivariate_palette(palette="blue_pink", n_classes=3, ax=None):
    """
    Aperçu rapide d'une palette bivariée sous forme de grille n x n.

    Paramètres:
    -----------
    palette : str | list[str] | array-like
        Voir `get_bivariate_palette`.
    n_classes : int
        Nombre de classes par variable.
    ax : matplotlib.axes.Axes, optionnel
        Axe existant à réutiliser ; un nouveau est créé si None.

    Exemples:
    ---------
        >>> preview_bivariate_palette("teal_orange")
    """
    grid = get_bivariate_palette(palette, n_classes)
    if ax is None:
        _, ax = plt.subplots(figsize=(3, 3))
    for i in range(n_classes):
        for j in range(n_classes):
            ax.add_patch(Rectangle((i, j), 1, 1, facecolor=grid[j, i], edgecolor="white"))
    ax.set_xlim(0, n_classes)
    ax.set_ylim(0, n_classes)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return ax


# ---------------------------------------------------------------------------
# Classification et attribution des couleurs
# ---------------------------------------------------------------------------

def classify_variable(series, n_classes=3, method="quantiles"):
    """
    Classe une série continue en n_classes classes (1..n_classes).

    Paramètres:
    -----------
    series : pandas.Series
        Valeurs à classer.
    n_classes : int
        Nombre de classes.
    method : str
        "quantiles" (effectifs égaux) ou "equal" (intervalles égaux).

    Retourne:
    ---------
    pandas.Series : classes 1..n_classes (float, NaN si non classable).
    """
    if method == "quantiles":
        try:
            classes = pd.qcut(series, n_classes, labels=False, duplicates="drop") + 1
        except ValueError:
            classes = pd.cut(series, n_classes, labels=False) + 1
    elif method == "equal":
        classes = pd.cut(series, n_classes, labels=False) + 1
    else:
        raise ValueError(f"method doit être 'quantiles' ou 'equal', reçu: {method!r}")
    return classes


def assign_bivariate_classes(gdf, var1, var2, palette="blue_pink", n_classes=3,
                              method="quantiles"):
    """
    Classe deux variables et associe une couleur bivariée à chaque entité.

    Paramètres:
    -----------
    gdf : geopandas.GeoDataFrame
        Données source (n'est pas modifié, une copie est retournée).
    var1, var2 : str
        Colonnes numériques à croiser. `var1` pilote l'axe horizontal de la
        palette/légende, `var2` l'axe vertical.
    palette : str | list[str] | array-like
        Voir `get_bivariate_palette`.
    n_classes : int
        Nombre de classes par variable.
    method : str
        "quantiles" (défaut) ou "equal".

    Retourne:
    ---------
    tuple :
        - geopandas.GeoDataFrame : copie de `gdf` avec les colonnes
          `var1_class`, `var2_class`, `bi_class` (ex. "2-3") et `bi_color`.
        - numpy.ndarray : grille de couleurs (n_classes, n_classes, 3).

    Raises:
    -------
        ValueError : si `var1`/`var2` contiennent des valeurs non classables
            (NaN, ou trop peu de valeurs distinctes).

    Exemples:
    ---------
        >>> gdf_bi, grid = assign_bivariate_classes(
        ...     regions, "densite_pop", "revenu_median", palette="teal_orange"
        ... )
    """
    gdf = gdf.copy()
    color_grid = get_bivariate_palette(palette, n_classes)

    v1_class = classify_variable(gdf[var1], n_classes, method)
    v2_class = classify_variable(gdf[var2], n_classes, method)
    if v1_class.isna().any() or v2_class.isna().any():
        raise ValueError(
            f"'{var1}' ou '{var2}' contient des valeurs non classables "
            "(NaN, ou trop peu de valeurs distinctes pour n_classes)."
        )

    gdf["var1_class"] = v1_class.astype(int)
    gdf["var2_class"] = v2_class.astype(int)
    gdf["bi_class"] = gdf["var1_class"].astype(str) + "-" + gdf["var2_class"].astype(str)
    gdf["bi_color"] = [
        tuple(color_grid[v2 - 1, v1 - 1])
        for v1, v2 in zip(gdf["var1_class"], gdf["var2_class"])
    ]
    return gdf, color_grid


# ---------------------------------------------------------------------------
# Tracé : carte + légende
# ---------------------------------------------------------------------------

def plot_bivariate_legend(
    target, color_grid,
    var1_label="Variable 1", var2_label="Variable 2",
    position=None, fontsize=8, arrow_color="black",
):
    """
    Dessine la légende carrée n x n d'une palette bivariée, avec des flèches
    indiquant le sens croissant de chaque variable.

    Paramètres:
    -----------
    target : matplotlib.axes.Axes ou matplotlib.figure.Figure
        Un axe existant (la légende y est dessinée directement), ou une
        figure (un nouvel axe y est créé à `position`).
    color_grid : array-like (n, n, 3)
        Grille de couleurs, ex. sortie de `assign_bivariate_classes`.
    var1_label, var2_label : str
        Étiquettes des axes horizontal (var1) et vertical (var2).
    position : tuple (x, y, w, h), optionnel
        Position/taille de la légende en coordonnées figure (0-1). Requis
        si `target` est une Figure ; ignoré si `target` est déjà un Axes.
    fontsize : int
        Taille des étiquettes.
    arrow_color : str
        Couleur des flèches d'axe.

    Retourne:
    ---------
    matplotlib.axes.Axes : l'axe de la légende.

    Exemples:
    ---------
        >>> plot_bivariate_legend(fig, grid, "Densité", "Revenu",
        ...                       position=(0.72, 0.08, 0.22, 0.22))
    """
    if hasattr(target, "add_axes"):
        if position is None:
            raise ValueError("`position` est requis quand `target` est une Figure.")
        ax = target.add_axes(position)
    else:
        ax = target

    grid = np.asarray(color_grid)
    n = grid.shape[0]
    for i in range(n):
        for j in range(n):
            ax.add_patch(
                Rectangle((i, j), 1, 1, facecolor=grid[j, i], edgecolor="white", linewidth=1)
            )

    ax.set_xlim(0, n)
    ax.set_ylim(0, n)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    pad = 0.08 * n
    ax.annotate(
        "", xy=(n + pad, -pad), xytext=(-pad, -pad),
        arrowprops=dict(arrowstyle="->", color=arrow_color, lw=1),
    )
    ax.annotate(
        "", xy=(-pad, n + pad), xytext=(-pad, -pad),
        arrowprops=dict(arrowstyle="->", color=arrow_color, lw=1),
    )
    ax.text(n / 2, -pad * 2.2, var1_label, ha="center", va="top", fontsize=fontsize)
    ax.text(-pad * 2.2, n / 2, var2_label, ha="right", va="center",
            fontsize=fontsize, rotation=90)
    return ax


def plot_bivariate_choropleth(
    gdf, var1, var2,
    var1_label="Variable 1", var2_label="Variable 2",
    palette="blue_pink", n_classes=3, method="quantiles",
    title=None, figsize=(10, 8),
    map_position=(0.05, 0.05, 0.75, 0.9),
    legend_position=(0.72, 0.08, 0.22, 0.22),
    edgecolor="white", linewidth=0.3,
    legend_fontsize=8,
    ax_map=None, transform=None,
    save_path=None, dpi=300,
    **plot_kwargs,
):
    """
    Crée une carte choroplèthe bivariée (deux variables croisées via une
    palette n x n) avec sa légende.

    Paramètres:
    -----------
    gdf : geopandas.GeoDataFrame
        Données source.
    var1, var2 : str
        Colonnes numériques à croiser (`var1` -> axe horizontal de la
        légende, `var2` -> axe vertical).
    var1_label, var2_label : str
        Étiquettes affichées sur la légende.
    palette : str | list[str] | array-like
        Palette bivariée — voir `get_bivariate_palette`.
    n_classes : int
        Nombre de classes par variable (défaut 3).
    method : str
        Méthode de classification : "quantiles" (défaut) ou "equal".
    title : str, optionnel
        Titre de la carte.
    figsize : tuple
        Taille de la figure, ignorée si `ax_map` est fourni.
    map_position : tuple (x, y, w, h)
        Position/taille de la carte en coordonnées figure (0-1), ignorée si
        `ax_map` est fourni.
    legend_position : tuple (x, y, w, h)
        Position/taille de la légende en coordonnées figure (0-1) —
        personnalisable pour éviter qu'elle recouvre la carte.
    edgecolor, linewidth :
        Style des contours des entités.
    legend_fontsize : int
        Taille des étiquettes de la légende.
    ax_map : matplotlib.axes.Axes, optionnel
        Axe existant sur lequel dessiner la carte (ex. `Map.ax` d'un objet
        `cartograpy.mapper.Map` déjà configuré) au lieu d'en créer un
        nouveau. Dans ce cas `figsize`/`map_position` sont ignorés.
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
    tuple : (figure, axe de la carte, GeoDataFrame enrichi des colonnes
    bivariées — voir `assign_bivariate_classes`).

    Exemples:
    ---------
        >>> fig, ax, gdf_bi = plot_bivariate_choropleth(
        ...     regions, "densite_pop", "revenu_median",
        ...     var1_label="Densité de population",
        ...     var2_label="Revenu médian",
        ...     palette="teal_orange",
        ...     legend_position=(0.05, 0.05, 0.22, 0.22),
        ... )
    """
    gdf_bi, color_grid = assign_bivariate_classes(gdf, var1, var2, palette, n_classes, method)

    if ax_map is None:
        fig = plt.figure(figsize=figsize)
        ax_map = fig.add_axes(map_position)
    else:
        fig = ax_map.get_figure()

    plot_kw = dict(color=list(gdf_bi["bi_color"]), edgecolor=edgecolor, linewidth=linewidth)
    if transform is not None:
        plot_kw["transform"] = transform
    plot_kw.update(plot_kwargs)
    gdf_bi.plot(ax=ax_map, **plot_kw)

    ax_map.set_axis_off()
    if title:
        ax_map.set_title(title, fontsize=14, fontweight="bold")

    plot_bivariate_legend(
        fig, color_grid, var1_label, var2_label,
        position=legend_position, fontsize=legend_fontsize,
    )

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
        logger.info(f"✅ Carte bivariée sauvegardée : {save_path}")

    return fig, ax_map, gdf_bi
