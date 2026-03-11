#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
situation_map.py

Script Python (sans Cartopy) pour générer des cartes de situation :
- Carte principale : pays (zoom) ou continent (situation)
- Inset : situation inverse (continent) ou zoom pays
- Flèche du nord + barre d’échelle positionnées en coordonnées d’axe (axes fraction)
- Source : Natural Earth lowres (via geopandas.datasets), lecture robuste avec Fiona + Shapely

Exemples :
1) Carte principale = Côte d’Ivoire, inset = Afrique (inverse de la situation)
    python situation_map.py --country "Côte d'Ivoire" --main country --inset africa --out civ_map.png

2) Carte principale = Afrique, inset = Côte d’Ivoire
    python situation_map.py --country "Côte d'Ivoire" --main africa --inset country --out africa_civ.png

3) Utiliser le code ISO3 (CIV) et mettre un point centroïde sur l’inset :
    python situation_map.py --iso3 CIV --main country --inset africa --centroid --out civ_iso3.png
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List, Tuple, Optional

import fiona
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry


# -----------------------------
# Utilities
# -----------------------------
def _geom_to_patches(geom: BaseGeometry) -> List[MplPolygon]:
    """Convert Shapely (Multi)Polygon -> list of Matplotlib Polygon patches."""
    patches: List[MplPolygon] = []
    if isinstance(geom, Polygon):
        patches.append(MplPolygon(list(geom.exterior.coords), closed=True))
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            patches.append(MplPolygon(list(poly.exterior.coords), closed=True))
    return patches


def _read_naturalearth_lowres() -> List[Tuple[dict, BaseGeometry]]:
    """
    Read Natural Earth lowres using Fiona to avoid GeoPandas/Shapely array-interface issues.
    Returns list of (properties, shapely_geometry).
    """
    shp_path = gpd.datasets.get_path("naturalearth_lowres")
    feats: List[Tuple[dict, BaseGeometry]] = []
    with fiona.open(shp_path) as src:
        for feat in src:
            if not feat.get("geometry"):
                continue
            geom = shape(feat["geometry"])
            props = feat.get("properties", {})
            feats.append((props, geom))
    return feats


def _find_country(
    feats: List[Tuple[dict, BaseGeometry]],
    country_name: Optional[str] = None,
    iso3: Optional[str] = None,
) -> Tuple[dict, BaseGeometry]:
    """
    Find a country feature by ISO3 (preferred) or name (contains match).
    Natural Earth lowres uses props: 'iso_a3', 'name', 'continent'
    """
    if iso3:
        iso3_u = iso3.strip().upper()
        hits = [(p, g) for (p, g) in feats if (p.get("iso_a3") or "").upper() == iso3_u]
        if hits:
            return hits[0]

    if not country_name:
        raise ValueError("Veuillez fournir --country ou --iso3.")

    key = country_name.strip().lower()
    hits = [(p, g) for (p, g) in feats if key in (p.get("name") or "").lower()]
    if hits:
        return hits[0]

    # fallback common variants
    variants = ["côte d'ivoire", "cote d'ivoire", "ivory coast"]
    if any(v in key for v in variants):
        hits = [(p, g) for (p, g) in feats if "ivoire" in (p.get("name") or "").lower()]
        if hits:
            return hits[0]

    raise ValueError(f"Pays introuvable dans NaturalEarth lowres : {country_name or iso3}")


def _filter_continent(feats: List[Tuple[dict, BaseGeometry]], continent: str) -> List[Tuple[dict, BaseGeometry]]:
    c = continent.strip().lower()
    return [(p, g) for (p, g) in feats if (p.get("continent") or "").lower() == c]


def _add_north_arrow(ax, x: float = 0.92, y_top: float = 0.84, y_bottom: float = 0.74) -> None:
    """Add a north arrow using axes-fraction coordinates."""
    ax.annotate(
        "N",
        xy=(x, y_top),
        xytext=(x, y_bottom),
        xycoords="axes fraction",
        textcoords="axes fraction",
        arrowprops=dict(facecolor="black", width=3, headwidth=10),
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        zorder=50,
    )


def _add_scale_bar_km(
    ax,
    scale_km: float,
    x_frac: float = 0.08,
    y_frac: float = 0.12,
    label_offset: float = 0.03,
) -> None:
    """
    Add an approximate scale bar in km on geographic (lon/lat) axes.

    Approximation: 1 degree longitude ~ 111 km (near equator).
    Converts km -> degrees -> fraction of data width, then plots in axes coords.
    """
    # Data extent:
    xmin, xmax = ax.get_xlim()
    data_width = float(xmax - xmin)
    if data_width <= 0:
        return

    deg_len = float(scale_km) / 111.0
    frac_len = deg_len / data_width

    ax.plot(
        [x_frac, x_frac + frac_len],
        [y_frac, y_frac],
        transform=ax.transAxes,
        color="black",
        linewidth=3,
        zorder=50,
    )
    ax.text(
        x_frac + frac_len / 2,
        y_frac - label_offset,
        f"{int(scale_km)} km" if float(scale_km).is_integer() else f"{scale_km:g} km",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        zorder=50,
    )


@dataclass
class Style:
    land_face: str = "0.92"
    land_edge: str = "0.6"
    land_lw: float = 0.4

    country_face: str = "#d73027"  # rouge
    country_edge: str = "black"
    country_lw: float = 1.5

    inset_face: str = "0.9"
    inset_edge: str = "0.6"
    inset_lw: float = 0.3

    highlight_hatch: str = "///"


# -----------------------------
# Core plotting
# -----------------------------
def plot_situation_map(
    country_name: Optional[str] = None,
    iso3: Optional[str] = None,
    *,
    main: str = "country",          # "country" or "africa"
    inset: str = "africa",          # "africa" or "country"
    continent: str = "Africa",
    neighbors_buffer_deg: float = 3.0,
    main_margin_deg: float = 1.5,
    inset_position: Tuple[float, float, float, float] = (0.73, 0.15, 0.25, 0.25),  # (left,bottom,width,height)
    fig_size: Tuple[float, float] = (10, 7),
    dpi: int = 200,
    title: Optional[str] = None,
    show_centroid_on_inset: bool = True,
    add_north: bool = True,
    add_scale: bool = True,
    scale_km_main: float = 200,
    style: Style = Style(),
    out_path: str = "situation_map.png",
) -> str:
    """
    Generate a situation map and save to out_path.
    Returns out_path.
    """
    feats = _read_naturalearth_lowres()
    cont = _filter_continent(feats, continent)
    c_props, c_geom = _find_country(cont, country_name=country_name, iso3=iso3)
    c_label = c_props.get("name", country_name or iso3 or "Pays")

    # Prepare Africa patches (continent)
    continent_patches: List[MplPolygon] = []
    for _, g in cont:
        continent_patches.extend(_geom_to_patches(g))

    # Country geometry bounds
    minx, miny, maxx, maxy = c_geom.bounds
    c_centroid = c_geom.centroid

    # Figure + main axis
    fig = plt.figure(figsize=fig_size, dpi=dpi)

    ax = fig.add_axes([0.05, 0.08, 0.65, 0.85])

    # MAIN
    if main.lower() == "africa":
        # Main = continent extent
        ax.set_title(title or f"Carte de situation : {c_label} en {continent}", fontsize=14, pad=12)
        ax.add_collection(PatchCollection(continent_patches, facecolor=style.land_face, edgecolor=style.land_edge, linewidth=style.inset_lw))

        # highlight country with hatch (outline + hatch)
        ax.add_collection(
            PatchCollection(
                _geom_to_patches(c_geom),
                facecolor="none",
                edgecolor=style.country_edge,
                linewidth=1.5,
                hatch=style.highlight_hatch,
                zorder=10,
            )
        )
        try:
            ax.text(c_centroid.x + 1, c_centroid.y + 1, c_label, fontsize=10, fontweight="bold", zorder=20)
        except Exception:
            pass

        ax.set_xlim(-25, 60)
        ax.set_ylim(-40, 40)

        # Scale suited to continent
        scale_km_main = 1000 if scale_km_main == 200 else scale_km_main

    else:
        # Main = country zoom with neighbors
        ax.set_title(title or f"Carte de situation : {c_label}", fontsize=14, pad=12)

        # neighbors = geometries intersecting buffered bbox
        neighbors: List[MplPolygon] = []
        for _, g in cont:
            gx0, gy0, gx1, gy1 = g.bounds
            if (gx0 < maxx + neighbors_buffer_deg and gx1 > minx - neighbors_buffer_deg
                and gy0 < maxy + neighbors_buffer_deg and gy1 > miny - neighbors_buffer_deg):
                neighbors.extend(_geom_to_patches(g))

        ax.add_collection(PatchCollection(neighbors, facecolor=style.land_face, edgecolor=style.land_edge, linewidth=style.land_lw))
        ax.add_collection(
            PatchCollection(
                _geom_to_patches(c_geom),
                facecolor=style.country_face,
                edgecolor=style.country_edge,
                linewidth=style.country_lw,
                zorder=10,
            )
        )

        ax.set_xlim(minx - main_margin_deg, maxx + main_margin_deg)
        ax.set_ylim(miny - main_margin_deg, maxy + main_margin_deg)

    # Axes + grid
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, linestyle="--", linewidth=0.3, color="0.7")

    # North + scale (placed in axes coords to avoid covering the polygon)
    if add_north:
        _add_north_arrow(ax, x=0.92, y_top=0.84, y_bottom=0.74)

    if add_scale:
        _add_scale_bar_km(ax, scale_km=scale_km_main, x_frac=0.08, y_frac=0.12)

    # INSET
    if inset.lower() in ("africa", "continent"):
        ax_in = fig.add_axes(inset_position)
        ax_in.set_title(continent, fontsize=9)
        ax_in.add_collection(PatchCollection(continent_patches, facecolor=style.inset_face, edgecolor=style.inset_edge, linewidth=style.inset_lw))

        # highlight country outline + hatch
        ax_in.add_collection(
            PatchCollection(
                _geom_to_patches(c_geom),
                facecolor="none",
                edgecolor="black",
                linewidth=1.2,
                hatch=style.highlight_hatch,
                zorder=10,
            )
        )

        # centroid point (red)
        if show_centroid_on_inset:
            ax_in.plot(c_centroid.x, c_centroid.y, marker="o", color="red", markersize=6, zorder=20)

        ax_in.set_xlim(-25, 60)
        ax_in.set_ylim(-40, 40)
        ax_in.set_xticks([])
        ax_in.set_yticks([])

    elif inset.lower() == "country":
        ax_in = fig.add_axes(inset_position)
        ax_in.set_title(f"Zoom {c_label}", fontsize=9)

        # draw neighbors around the country bounds
        neighbors: List[MplPolygon] = []
        for _, g in cont:
            gx0, gy0, gx1, gy1 = g.bounds
            if (gx0 < maxx + 5 and gx1 > minx - 5 and gy0 < maxy + 5 and gy1 > miny - 5):
                neighbors.extend(_geom_to_patches(g))

        ax_in.add_collection(PatchCollection(neighbors, facecolor=style.inset_face, edgecolor=style.inset_edge, linewidth=0.4))
        ax_in.add_collection(PatchCollection(_geom_to_patches(c_geom), facecolor=style.country_face, edgecolor="black", linewidth=1.0, zorder=10))

        ax_in.set_xlim(minx - 2, maxx + 2)
        ax_in.set_ylim(miny - 2, maxy + 2)
        ax_in.set_xticks([])
        ax_in.set_yticks([])
        ax_in.set_aspect("equal")

    else:
        raise ValueError("--inset doit être 'africa' ou 'country'.")

    # Save
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


# -----------------------------
# CLI
# -----------------------------
def main_cli() -> None:
    parser = argparse.ArgumentParser(description="Générer une carte de situation (pays + inset).")
    parser.add_argument("--country", type=str, default=None, help="Nom du pays (ex: \"Côte d'Ivoire\").")
    parser.add_argument("--iso3", type=str, default=None, help="Code ISO3 (ex: CIV). Recommandé.")
    parser.add_argument("--main", type=str, default="country", choices=["country", "africa"], help="Contenu de la carte principale.")
    parser.add_argument("--inset", type=str, default="africa", choices=["africa", "country"], help="Contenu de l'inset.")
    parser.add_argument("--centroid", action="store_true", help="Afficher le centroïde sur l'inset Afrique.")
    parser.add_argument("--no-north", action="store_true", help="Désactiver la flèche du nord.")
    parser.add_argument("--no-scale", action="store_true", help="Désactiver la barre d’échelle.")
    parser.add_argument("--scale-km", type=float, default=200, help="Longueur de la barre d’échelle (km) sur la carte principale.")
    parser.add_argument("--out", type=str, default="situation_map.png", help="Chemin de sortie (PNG).")

    args = parser.parse_args()

    plot_situation_map(
        country_name=args.country,
        iso3=args.iso3,
        main=args.main,
        inset=args.inset,
        show_centroid_on_inset=bool(args.centroid),
        add_north=not args.no_north,
        add_scale=not args.no_scale,
        scale_km_main=args.scale_km,
        out_path=args.out,
    )

    print(f"OK: {args.out}")


if __name__ == "__main__":
    main_cli()
