import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, box
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import numpy as np

def _is_projected_meters(crs) -> bool:
    """Heuristique: CRS projeté avec unités proches du mètre."""
    if crs is None:
        return False
    try:
        return crs.is_projected  # pyproj.CRS
    except Exception:
        return False

def _add_north_arrow(ax, xy=(0.92, 0.12), size=0.10, text="N", lw=1.2):
    """
    Flèche Nord simple en coordonnées d'axes (0-1).
    xy: position du bas de la flèche.
    size: longueur relative (fraction de l'axe).
    """
    x, y = xy
    ax.annotate(
        "", xy=(x, y + size), xytext=(x, y),
        xycoords=ax.transAxes, textcoords=ax.transAxes,
        arrowprops=dict(arrowstyle="-|>", lw=lw),
        zorder=100
    )
    ax.text(x, y + size + 0.02, text, transform=ax.transAxes,
            ha="center", va="bottom", fontsize=10, zorder=101)

def _nice_scale_length(x):
    """Arrondit une longueur à 1-2-5 * 10^n."""
    if x <= 0:
        return 0
    exp = np.floor(np.log10(x))
    base = x / (10**exp)
    nice = 1 if base < 1.5 else 2 if base < 3.5 else 5 if base < 7.5 else 10
    return nice * (10**exp)

def _add_scale_bar(ax, length_m=None, location=(0.08, 0.06), linewidth=2.0, text_offset=0.01):
    """
    Barre d'échelle simple.
    length_m: longueur en mètres. Si None, auto basé sur l'étendue.
    location: position (x,y) en coords d'axes du début de la barre.
    """
    x0, y0 = location

    # Convertir coords d'axes -> coords data pour dessiner à l'échelle
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    width = xmax - xmin
    if length_m is None:
        length_m = _nice_scale_length(width * 0.25)

    # Point de départ en data
    x_start = xmin + x0 * width
    y_start = ymin + y0 * (ymax - ymin)

    ax.plot([x_start, x_start + length_m], [y_start, y_start], lw=linewidth, solid_capstyle="butt", zorder=100)
    ax.plot([x_start, x_start], [y_start - (ymax - ymin) * 0.005, y_start + (ymax - ymin) * 0.005],
            lw=linewidth, zorder=100)
    ax.plot([x_start + length_m, x_start + length_m],
            [y_start - (ymax - ymin) * 0.005, y_start + (ymax - ymin) * 0.005],
            lw=linewidth, zorder=100)

    # Texte
    if length_m >= 1000:
        label = f"{length_m/1000:g} km"
    else:
        label = f"{length_m:g} m"

    ax.text(x_start + length_m / 2, y_start + (ymax - ymin) * (text_offset * 5),
            label, ha="center", va="bottom", fontsize=9, zorder=101)

def situation_map(
    data: gpd.GeoDataFrame,
    from_,
    position: str = "TR",
    *,
    geocode=None,
    auto_project: bool = True,
    metric_crs: str | None = None,
    figsize=(9, 6),
    inset_frac=0.33,
    inset_pad=0.02,
    show_bbox_on_inset: bool = True,
    show_scale: bool = True,
    show_north: bool = True,
    title: str | None = None,
    subtitle: str | None = None,
    data_style=None,
    from_style=None,
    bbox_style=None,
    point_style=None,
    frame_inset: bool = True,
):
    """
    Carte de situation : grande carte = `data`, petite carte (inset) = `from_`.

    - `data`: GeoDataFrame de la zone d’étude / couches principales.
    - `from_`: GeoDataFrame OU str (nom à géocoder via `geocode`).
    - Ajoute sur la petite carte le centroïde de la bbox de `data`.
    - Optionnel: bbox de `data` sur la petite carte.
    - Optionnel: flèche Nord + barre d'échelle (fiable si CRS métrique).
    """

    # ------------------ Validations ------------------
    if data is None or len(data) == 0:
        raise ValueError("`data` doit être une GeoDataFrame non vide.")
    if data.crs is None:
        raise ValueError("`data` doit avoir un CRS défini (data.crs != None).")

    # Résoudre from_
    if isinstance(from_, str):
        if geocode is None:
            raise ValueError(
                "`from_` est un texte (str) mais `geocode` est absent. "
                "Fournis geocode(text)->GeoDataFrame/GeoSeries/geometry, ou passe un GeoDataFrame."
            )
        from_g = geocode(from_)
        if isinstance(from_g, gpd.GeoSeries):
            from_gdf = gpd.GeoDataFrame(geometry=from_g, crs=from_g.crs)
        elif isinstance(from_g, gpd.GeoDataFrame):
            from_gdf = from_g.copy()
        else:
            # shapely geometry
            from_gdf = gpd.GeoDataFrame(geometry=[from_g], crs=getattr(from_g, "crs", None))
    else:
        if not isinstance(from_, gpd.GeoDataFrame):
            raise TypeError("`from_` doit être une GeoDataFrame ou un texte (str).")
        from_gdf = from_.copy()

    if from_gdf.crs is None:
        raise ValueError("`from_` (ou le résultat de geocode) doit avoir un CRS défini.")

    # ------------------ Projection métrique (optionnel) ------------------
    data_gdf = data.copy()

    if auto_project:
        # Si metric_crs fourni, on l'utilise. Sinon, estimation UTM via estimate_utm_crs.
        if metric_crs is not None:
            target_crs = metric_crs
        else:
            try:
                target_crs = data_gdf.estimate_utm_crs()
            except Exception:
                target_crs = None

        if target_crs is not None:
            data_gdf = data_gdf.to_crs(target_crs)
            from_gdf = from_gdf.to_crs(target_crs)

    # Harmoniser CRS si besoin
    if from_gdf.crs != data_gdf.crs:
        from_gdf = from_gdf.to_crs(data_gdf.crs)

    # ------------------ Géométries de repérage ------------------
    xmin, ymin, xmax, ymax = data_gdf.total_bounds
    bbox_geom = box(xmin, ymin, xmax, ymax)
    bbox_centroid = Point((xmin + xmax) / 2.0, (ymin + ymax) / 2.0)

    # ------------------ Styles par défaut ------------------
    if data_style is None:
        data_style = dict(facecolor="none", edgecolor="#1a1a1a", linewidth=1.2, zorder=3)
    if from_style is None:
        from_style = dict(facecolor="none", edgecolor="#1a1a1a", linewidth=1.0, alpha=0.95, zorder=2)
    if bbox_style is None:
        bbox_style = dict(facecolor="none", edgecolor="#1a1a1a", linewidth=1.0, zorder=4)
    if point_style is None:
        point_style = dict(color="#1a1a1a", markersize=35, marker="o", zorder=5)

    # ------------------ Figure & axes ------------------
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")

    # Grande carte
    data_gdf.plot(ax=ax, **data_style)

    # Zoom confortable sur data
    dx = (xmax - xmin) if (xmax - xmin) != 0 else 1.0
    dy = (ymax - ymin) if (ymax - ymin) != 0 else 1.0
    padx = dx * 0.06
    pady = dy * 0.06
    ax.set_xlim(xmin - padx, xmax + padx)
    ax.set_ylim(ymin - pady, ymax + pady)
    ax.set_axis_off()

    # Titres (optionnels)
    if title:
        ax.text(0.02, 0.98, title, transform=ax.transAxes,
                ha="left", va="top", fontsize=14, fontweight="bold")
    if subtitle:
        ax.text(0.02, 0.935, subtitle, transform=ax.transAxes,
                ha="left", va="top", fontsize=10)

    # Flèche nord
    if show_north:
        _add_north_arrow(ax, xy=(0.94, 0.12), size=0.12)

    # Barre d'échelle (si CRS projeté)
    if show_scale:
        if _is_projected_meters(data_gdf.crs):
            _add_scale_bar(ax)
        else:
            # Pas de crash : on indique juste la limitation
            ax.text(0.08, 0.03, "Échelle désactivée (CRS non métrique)",
                    transform=ax.transAxes, ha="left", va="bottom", fontsize=8)

    # ------------------ Inset (petite carte) ------------------
    pos = position.upper()
    if pos not in {"TR", "TL", "BR", "BL"}:
        raise ValueError("`position` doit être parmi {'TR','TL','BR','BL'}.")

    anchors = {
        "TR": (1 - inset_pad - inset_frac, 1 - inset_pad - inset_frac),
        "TL": (inset_pad,               1 - inset_pad - inset_frac),
        "BR": (1 - inset_pad - inset_frac, inset_pad),
        "BL": (inset_pad,               inset_pad),
    }
    x0, y0 = anchors[pos]

    ax_in = inset_axes(
        ax,
        width=f"{inset_frac*100:.1f}%",
        height=f"{inset_frac*100:.1f}%",
        bbox_to_anchor=(x0, y0, inset_frac, inset_frac),
        bbox_transform=ax.transAxes,
        loc="lower left",
        borderpad=0,
    )

    # Fond inset
    from_gdf.plot(ax=ax_in, **from_style)

    # bbox de data sur inset
    if show_bbox_on_inset:
        gpd.GeoSeries([bbox_geom], crs=data_gdf.crs).plot(ax=ax_in, **bbox_style)

    # centroïde bbox sur inset
    gpd.GeoSeries([bbox_centroid], crs=data_gdf.crs).plot(ax=ax_in, **point_style)

    # Ajuster extent inset pour contenir from_ correctement
    fxmin, fymin, fxmax, fymax = from_gdf.total_bounds
    fdx = (fxmax - fxmin) if (fxmax - fxmin) != 0 else 1.0
    fdy = (fymax - fymin) if (fymax - fymin) != 0 else 1.0
    ax_in.set_xlim(fxmin - fdx * 0.04, fxmax + fdx * 0.04)
    ax_in.set_ylim(fymin - fdy * 0.04, fymax + fdy * 0.04)

    ax_in.set_axis_off()

    # Cadre inset (propre)
    if frame_inset:
        for spine in ax_in.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1.0)
            spine.set_edgecolor("#1a1a1a")

    return fig, ax, ax_in
