"""cartograpy.mapper.hexgrid — hexagonal grids and hexbin maps.

Generates a regular hexagonal grid over a study area (via the
`geohexgrid` package), aggregates point or polygon data into it, and
plots the result as a choropleth map. The resulting GeoDataFrame is
standard and can be reused as-is with `cartograpy.mapper.bivariate` for
a bivariate hexagonal map (two variables crossed per hexagon).
"""

import logging

import geopandas as gpd
import matplotlib.pyplot as plt
import geohexgrid as ghg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Hexagonal grid generation
# ---------------------------------------------------------------------------

def make_hex_grid(source, hex_size, crs=None, trim_mode="intersect"):
    """
    Generates a grid of regular (flat-top) hexagons covering an area.

    Parameters:
    -----------
    source : geopandas.GeoDataFrame | tuple (minx, miny, maxx, maxy)
        Area to cover: a GeoDataFrame (its extent and CRS are used, and
        hexagons outside the area are discarded according to
        `trim_mode`), or a raw bounds tuple (e.g. `gdf.total_bounds`)
        — in that case `crs` must be provided and every hexagon in the
        rectangular extent is kept.
    hex_size : float
        Hexagon radius (circumradius), in the CRS unit. Use a projected
        CRS (meters) for a true regular mesh — a geographic CRS
        (degrees) yields hexagons distorted by latitude.
    crs : str, optional
        Grid CRS. Required if `source` is a bounds tuple; ignored
        (taken from `source.crs`) if `source` is a GeoDataFrame.
    trim_mode : str
        If `source` is a GeoDataFrame: `"intersect"` (default, keeps
        only hexagons touching the geometries) or `"clip"` (clips
        hexagons to the geometries, may create fragments). Ignored if
        `source` is a bounds tuple.

    Returns:
    ---------
    geopandas.GeoDataFrame: columns `cell_id`, `geometry`.

    Raises:
    -------
        ValueError: if `source` is a GeoDataFrame with no CRS, or a
            bounds tuple with no `crs` provided.

    Examples:
    ---------
        >>> grid = make_hex_grid(civ_regions, hex_size=25_000)  # 25 km, projected CRS
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
# 2. Aggregating data into the hexagonal grid
# ---------------------------------------------------------------------------

def aggregate_to_hex(source_gdf, hex_grid, value_cols, agg_funcs=None,
                      count_col="n_points", predicate="within"):
    """
    Aggregates point (or polygon) data into each hexagon.

    Parameters:
    -----------
    source_gdf : geopandas.GeoDataFrame
        Source data (occurrence points, plots, etc.). Automatically
        reprojected to `hex_grid`'s CRS if needed.
    hex_grid : geopandas.GeoDataFrame
        Grid produced by `make_hex_grid()`.
    value_cols : list[str]
        Numeric columns to aggregate (e.g. `["species_richness", "biomass"]`).
    agg_funcs : dict, optional
        Aggregation function per column (e.g. `{"species_richness": "mean"}`).
        Default: `"mean"` for every column.
    count_col : str
        Name of the column counting the number of features per hexagon.
    predicate : str
        Spatial predicate for the join (`geopandas.sjoin`), `"within"`
        by default (suited to points) — use `"intersects"` for polygons
        straddling several hexagons.

    Returns:
    ---------
    geopandas.GeoDataFrame: `hex_grid` enriched with the aggregated
    columns and `count_col`. Hexagons with no data are kept with NaN
    (and `count_col` at 0) — filter them out if needed (e.g.
    `result[result.n_points >= 3]`).

    Examples:
    ---------
        >>> hex_data = aggregate_to_hex(
        ...     points, grid, value_cols=["species_richness", "structure_index"],
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
# 3. Plotting: hexagonal choropleth map
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
    Plots a choropleth map on a hexagonal grid (single variable).

    For a bivariate hexagonal map (two variables crossed per hexagon),
    pass the GeoDataFrame produced by `aggregate_to_hex()` directly to
    `cartograpy.mapper.plot_bivariate_choropleth()`.

    Parameters:
    -----------
    hex_gdf : geopandas.GeoDataFrame
        Aggregated hexagonal grid, e.g. output of `aggregate_to_hex()`.
    column : str
        Numeric column to map.
    cmap : str | Colormap
        Color palette.
    min_count : int, optional
        If provided and `count_col` is present in `hex_gdf`, only plots
        hexagons where `count_col >= min_count` (filters out
        under-sampled cells).
    count_col : str
        Name of the count column (see `aggregate_to_hex`).
    edgecolor, linewidth :
        Hexagon outline style.
    title : str, optional
        Map title.
    figsize : tuple
        Figure size, ignored if `ax_map` is provided.
    show_colorbar : bool
        Whether to show the colorbar.
    colorbar_label : str, optional
        Colorbar label (defaults to `column`).
    ax_map : matplotlib.axes.Axes, optional
        Existing axes to draw on (e.g. the `Map.ax` of an already
        configured `cartograpy.mapper.Map` object) instead of creating
        a new one. In that case `figsize` is ignored.
    transform : cartopy.crs.CRS, optional
        Transform passed to `GeoDataFrame.plot()` — useful if `ax_map`
        is a cartopy GeoAxes with a projection.
    save_path : str, optional
        If provided, saves the figure to this path.
    dpi : int
        Save resolution.
    **plot_kwargs
        Additional parameters passed to `GeoDataFrame.plot()`.

    Returns:
    ---------
    tuple: (figure, axes).

    Examples:
    ---------
        >>> fig, ax = plot_hexgrid_choropleth(
        ...     hex_data, "species_richness", cmap="YlGn", min_count=3,
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

    return fig, ax_map
