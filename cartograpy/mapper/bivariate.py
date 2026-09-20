"""cartograpy.mapper.bivariate — bivariate choropleth maps.

Crosses two continuous variables on a single map via an n x n color
palette (Joshua Stevens' method:
https://www.joshuastevens.net/cartography/make-a-bivariate-choropleth-map/),
with its dedicated square legend.
"""

import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bivariate palettes
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
    """Lists the names of the built-in bivariate palettes."""
    return list(BIVARIATE_PALETTES.keys())


def _interpolate_palette_grid(grid, n):
    """Bilinearly interpolates a color grid (m, m, 3) to (n, n, 3)."""
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
    Resolves a bivariate palette into an RGB color grid (n_classes, n_classes, 3).

    Parameters:
    -----------
    palette : str | list[str] | array-like
        - str: name of a built-in palette (see `list_bivariate_palettes()`).
        - list[str]: n_classes**2 hex colors, row by row, from
          (var1=low, var2=low) to (var1=high, var2=high).
        - array-like (n_classes, n_classes, 3): an already-built RGB color
          grid (e.g. output of a previous call to this function).
    n_classes : int
        Number of classes per variable (n_classes x n_classes grid). For a
        built-in palette with a different native size, it is bilinearly
        interpolated.

    Returns:
    ---------
    numpy.ndarray: grid (n_classes, n_classes, 3), indexed [var2-1, var1-1].

    Examples:
    ---------
        >>> get_bivariate_palette("blue_pink")
        >>> get_bivariate_palette("blue_pink", n_classes=4)  # interpolated
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
    """Samples `spec` into n RGB colors (n, 3), from the low end to the
    high end of the variable.

    `spec` accepts: a matplotlib colormap name (str), a Colormap, or a
    list/tuple of at least 2 colors (linear gradient between them)."""
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
    Generates an n x n bivariate palette by crossing two color ramps (one
    per variable), instead of picking from the built-in palettes or
    providing a full grid by hand.

    Parameters:
    -----------
    var1_colors, var2_colors : str | Colormap | list[str]
        Color ramp for each variable, from low to high: a matplotlib
        colormap name (e.g. `"Blues"`), a `Colormap` object, or a list of
        at least 2 colors (linear gradient between them, e.g.
        `["#f0f0f0", "#08519c"]`).
    n_classes : int
        Size of the n x n grid (number of classes per variable).
    blend : str
        How to combine the two ramps at each grid cell:
        - `"multiply"` (default): element-wise product — darkens the
          corner where both variables are high, consistent with the
          spirit of the built-in palettes (`blue_pink`, etc.).
        - `"mean"`: simple average of the two colors.
        - `"screen"`: `1 - (1-a)(1-b)` — lightens instead of darkening.

    Returns:
    ---------
    numpy.ndarray: grid (n_classes, n_classes, 3), directly usable as
    `palette=` in `plot_bivariate_choropleth`/`get_bivariate_palette`.

    Examples:
    ---------
        >>> grid = generate_bivariate_palette("Blues", "Reds")
        >>> fig, ax, gdf_bi = plot_bivariate_choropleth(
        ...     regions, "densite", "revenu", palette=grid,
        ... )
        >>> generate_bivariate_palette(["#f7fbff", "#08306b"], ["#fff5f0", "#67000d"])
    """
    ramp1 = _resolve_color_ramp(var1_colors, n_classes)
    ramp2 = _resolve_color_ramp(var2_colors, n_classes)

    a = ramp1[np.newaxis, :, :]   # (1, n, 3) — varies along var1 (columns)
    b = ramp2[:, np.newaxis, :]   # (n, 1, 3) — varies along var2 (rows)
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
    Quick preview of a bivariate palette as an n x n grid.

    Parameters:
    -----------
    palette : str | list[str] | array-like
        See `get_bivariate_palette`.
    n_classes : int
        Number of classes per variable.
    ax : matplotlib.axes.Axes, optional
        Existing axes to reuse; a new one is created if None.

    Examples:
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
# Classification and color assignment
# ---------------------------------------------------------------------------

def classify_variable(series, n_classes=3, method="quantiles"):
    """
    Classifies a continuous series into n_classes classes (1..n_classes).

    Parameters:
    -----------
    series : pandas.Series
        Values to classify.
    n_classes : int
        Number of classes.
    method : str
        "quantiles" (equal counts) or "equal" (equal intervals).

    Returns:
    ---------
    pandas.Series: classes 1..n_classes (float, NaN if not classifiable).
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
    Classifies two variables and assigns a bivariate color to each feature.

    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        Source data (not modified, a copy is returned).
    var1, var2 : str
        Numeric columns to cross. `var1` drives the palette/legend's
        horizontal axis, `var2` the vertical axis.
    palette : str | list[str] | array-like
        See `get_bivariate_palette`.
    n_classes : int
        Number of classes per variable.
    method : str
        "quantiles" (default) or "equal".

    Returns:
    ---------
    tuple:
        - geopandas.GeoDataFrame: copy of `gdf` with the `var1_class`,
          `var2_class`, `bi_class` (e.g. "2-3") and `bi_color` columns
          added.
        - numpy.ndarray: color grid (n_classes, n_classes, 3).

    Raises:
    -------
        ValueError: if `var1`/`var2` contain values that can't be
            classified (NaN, or too few distinct values).

    Examples:
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
# Plotting: map + legend
# ---------------------------------------------------------------------------

def plot_bivariate_legend(
    target, color_grid,
    var1_label="Variable 1", var2_label="Variable 2",
    position=None, fontsize=8, arrow_color="black",
):
    """
    Draws the n x n square legend for a bivariate palette, with arrows
    showing the increasing direction of each variable.

    Parameters:
    -----------
    target : matplotlib.axes.Axes or matplotlib.figure.Figure
        An existing axes (the legend is drawn directly on it), or a
        figure (a new axes is created at `position`).
    color_grid : array-like (n, n, 3)
        Color grid, e.g. output of `assign_bivariate_classes`.
    var1_label, var2_label : str
        Labels for the horizontal (var1) and vertical (var2) axes.
    position : tuple (x, y, w, h), optional
        Legend position/size in figure coordinates (0-1). Required if
        `target` is a Figure; ignored if `target` is already an Axes.
    fontsize : int
        Label size.
    arrow_color : str
        Axis arrow color.

    Returns:
    ---------
    matplotlib.axes.Axes: the legend's axes.

    Examples:
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
    Creates a bivariate choropleth map (two variables crossed via an n x n
    palette) with its legend.

    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        Source data.
    var1, var2 : str
        Numeric columns to cross (`var1` -> legend's horizontal axis,
        `var2` -> vertical axis).
    var1_label, var2_label : str
        Labels shown on the legend.
    palette : str | list[str] | array-like
        Bivariate palette — see `get_bivariate_palette`.
    n_classes : int
        Number of classes per variable (default 3).
    method : str
        Classification method: "quantiles" (default) or "equal".
    title : str, optional
        Map title.
    figsize : tuple
        Figure size, ignored if `ax_map` is provided.
    map_position : tuple (x, y, w, h)
        Map position/size in figure coordinates (0-1), ignored if
        `ax_map` is provided.
    legend_position : tuple (x, y, w, h)
        Legend position/size in figure coordinates (0-1) — customizable
        to avoid it overlapping the map.
    edgecolor, linewidth :
        Feature outline style.
    legend_fontsize : int
        Legend label size.
    ax_map : matplotlib.axes.Axes, optional
        Existing axes to draw the map on (e.g. the `Map.ax` of an already
        configured `cartograpy.mapper.Map` object) instead of creating a
        new one. In that case `figsize`/`map_position` are ignored.
    transform : cartopy.crs.CRS, optional
        Transform passed to `GeoDataFrame.plot()` — useful if `ax_map` is
        a cartopy GeoAxes with a projection.
    save_path : str, optional
        If provided, saves the figure to this path.
    dpi : int
        Save resolution.
    **plot_kwargs
        Additional parameters passed to `GeoDataFrame.plot()`.

    Returns:
    ---------
    tuple: (figure, map axes, GeoDataFrame enriched with the bivariate
    columns — see `assign_bivariate_classes`).

    Examples:
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

    return fig, ax_map, gdf_bi
