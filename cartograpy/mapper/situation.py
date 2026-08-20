import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.patches as mpatches
from io import BytesIO
from pyproj import Geod
from ._optional_deps import *  # noqa: F401,F403
import logging

logger = logging.getLogger(__name__)


class SituationMap:
    """
    Crée une figure composite avec une carte principale et une mini-carte
    de situation (inset map) montrant où se situe la zone d'étude dans un
    contexte géographique plus large.

    Utilise automatiquement ``matplotlib-map-utils`` si installé pour un
    positionnement intelligent et des indicateurs d'étendue/détail, sinon
    revient au placement manuel classique.

    Paramètres:
    -----------
    figsize : tuple
        Taille de la figure
    title : str
        Titre de la carte principale
    projection : cartopy.crs
        Projection de la carte principale
    inset_position : tuple (x, y, w, h)
        Position et taille de la mini-carte (coordonnées relatives 0-1,
        mode classique uniquement).
    inset_projection : cartopy.crs, optional
        Projection de la mini-carte (par défaut PlateCarree)
    inset_location : str
        Position de l'inset (mode map-utils) : "upper left", "upper right",
        "lower left", "lower right", etc.
    inset_size : float or tuple, optional
        Taille de l'inset en pouces (mode map-utils).
    inset_pad : float or tuple, optional
        Espacement en pouces (mode map-utils).
    style : str
        Mode de rendu : "auto", "map-utils", "classic".
    dpi : int
        Résolution
    verbose : bool
        Afficher les messages d'information

    Exemple:
    --------
    >>> sm = SituationMap(title="Côte d'Ivoire")
    >>> sm.add_main_layer(gdf_civ, facecolor="khaki")
    >>> sm.set_inset_box_from_gdf(gdf_civ)
    >>> sm.show()
    """

    def __init__(
        self,
        figsize=(14, 10),
        title="Carte",
        projection=None,
        inset_position=(0.65, 0.02, 0.33, 0.33),
        inset_projection=None,
        inset_location="lower right",
        inset_size=None,
        inset_pad=None,
        style="auto",
        dpi=200,
        verbose=True,
    ):
        if projection is None:
            projection = ccrs.PlateCarree()
        if inset_projection is None:
            inset_projection = ccrs.PlateCarree()

        self.verbose = verbose
        self.figsize = figsize
        self.dpi = dpi
        self.projection = projection
        self.inset_projection = inset_projection
        self._style = style

        # carte principale
        self.fig = plt.figure(figsize=figsize, dpi=dpi)
        self.ax = self.fig.add_subplot(111, projection=projection)
        self.ax.set_title(title, fontsize=16, fontweight="bold")
        self.ax.coastlines(resolution="50m", linewidth=0.5)
        self.ax.add_feature(cfeature.BORDERS, linewidth=0.5)

        # Résolution du style
        resolved = style
        if resolved == "auto":
            resolved = "map-utils" if HAS_MAP_UTILS else "classic"

        self._inset_map_obj = None
        self._box_patch = None

        if resolved == "map-utils" and HAS_MAP_UTILS:
            # Création différée : l'inset sera créé après le premier
            # add_main_layer pour que l'axe principal soit correctement
            # dimensionné. On stocke les paramètres.
            self._inset_params = dict(
                location=inset_location,
                projection=inset_projection,
            )
            if inset_size is not None:
                self._inset_params["size"] = inset_size
            if inset_pad is not None:
                self._inset_params["pad"] = inset_pad
            self.inset_ax = None
            self._resolved_style = "map-utils"
        else:
            # mode classique : créer l'inset immédiatement
            self.inset_ax = self.fig.add_axes(
                inset_position, projection=inset_projection, frameon=True,
            )
            self.inset_ax.set_global()
            self.inset_ax.add_feature(cfeature.LAND, facecolor="lightgray")
            self.inset_ax.add_feature(cfeature.OCEAN, facecolor="lightblue")
            self.inset_ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor="gray")
            self.inset_ax.coastlines(resolution="110m", linewidth=0.4)
            self._inset_params = None
            self._resolved_style = "classic"

    def _ensure_inset_ax(self):
        """Crée l'axe inset map-utils s'il n'existe pas encore."""
        if self.inset_ax is not None:
            return
        if self._inset_params is None:
            return

        params = self._inset_params
        proj = params.pop("projection", ccrs.PlateCarree())
        im_kwargs = {k: v for k, v in params.items() if k != "projection"}

        im = MmuInsetMap(**im_kwargs)
        self.inset_ax = im.create(self.ax, projection=proj)
        self.inset_ax.set_global()
        self.inset_ax.add_feature(cfeature.LAND, facecolor="lightgray")
        self.inset_ax.add_feature(cfeature.OCEAN, facecolor="lightblue")
        self.inset_ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor="gray")
        self.inset_ax.coastlines(resolution="110m", linewidth=0.4)
        self._inset_map_obj = im

    def _log(self, *args, **kwargs):
        if self.verbose:
            logger.info(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        plt.close(self.fig)
        return False

    # -- couche principale -------------------------------------------------

    def add_main_layer(self, gdf, facecolor="green", edgecolor="black",
                       linewidth=0.5, alpha=0.7, column=None, cmap="viridis",
                       **kwargs):
        """
        Ajoute un GeoDataFrame à la carte principale.
        """
        plot_kwargs = dict(
            ax=self.ax, transform=ccrs.PlateCarree(),
            edgecolor=edgecolor, linewidth=linewidth, alpha=alpha,
            **kwargs,
        )
        if column and column in gdf.columns:
            plot_kwargs["column"] = column
            plot_kwargs["cmap"] = cmap
        else:
            plot_kwargs["facecolor"] = facecolor

        gdf.plot(**plot_kwargs)

        # auto-zoom sur la couche
        bounds = gdf.total_bounds
        margin = 0.05
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        self.ax.set_extent(
            [bounds[0] - w * margin, bounds[2] + w * margin,
             bounds[1] - h * margin, bounds[3] + h * margin],
            crs=ccrs.PlateCarree(),
        )

        # Créer l'inset si mode map-utils (différé)
        self._ensure_inset_ax()

        return self

    # -- rectangle de situation --------------------------------------------

    def set_inset_box(self, bounds, box_color="red", box_linewidth=2,
                      indicator="extent", indicator_facecolor="red",
                      indicator_linecolor="red", indicator_alpha=0.5,
                      indicator_linewidth=1):
        """
        Dessine un rectangle sur la mini-carte délimitant la zone d'étude.

        En mode map-utils, utilise ``indicate_extent`` pour un indicateur
        automatique et précis. Sinon, dessine un rectangle manuellement.

        Paramètres:
        -----------
        bounds : list
            [minx, miny, maxx, maxy] en coordonnées géographiques
        box_color : str
            Couleur du rectangle (mode classique)
        box_linewidth : float
            Épaisseur du trait (mode classique)
        indicator : str
            Type d'indicateur : "extent", "detail", ou "none" (mode map-utils)
        indicator_facecolor : str
            Couleur de remplissage de l'indicateur
        indicator_linecolor : str
            Couleur de bordure de l'indicateur
        indicator_alpha : float
            Transparence de l'indicateur
        indicator_linewidth : float
            Épaisseur de trait de l'indicateur
        """
        self._ensure_inset_ax()

        if self._box_patch is not None:
            self._box_patch.remove()
            self._box_patch = None

        if (self._resolved_style == "map-utils" and HAS_MAP_UTILS
                and indicator != "none"):
            pcrs = self.inset_projection
            bcrs = self.projection
            try:
                if indicator == "extent":
                    mmu_indicate_extent(
                        pax=self.inset_ax, bax=self.ax,
                        pcrs=pcrs, bcrs=bcrs,
                        facecolor=indicator_facecolor,
                        linecolor=indicator_linecolor,
                        alpha=indicator_alpha,
                        linewidth=indicator_linewidth,
                    )
                elif indicator == "detail":
                    mmu_indicate_detail(
                        pax=self.ax, iax=self.inset_ax,
                        pcrs=bcrs, icrs=pcrs,
                        facecolor=indicator_facecolor,
                        linecolor=indicator_linecolor,
                        alpha=indicator_alpha,
                        linewidth=indicator_linewidth,
                    )
                return self
            except (ValueError, TypeError) as e:
                self._log(f"⚠️  Indicateur {indicator} échoué : {e}, "
                          "utilisation du rectangle classique")

        # Fallback : rectangle classique
        minx, miny, maxx, maxy = bounds
        rect = mpatches.Rectangle(
            (minx, miny), maxx - minx, maxy - miny,
            linewidth=box_linewidth, edgecolor=box_color,
            facecolor="none", transform=ccrs.PlateCarree(), zorder=10,
        )
        self.inset_ax.add_patch(rect)
        self._box_patch = rect
        return self

    def set_inset_box_from_gdf(self, gdf, **kwargs):
        """
        Place le rectangle de situation à partir de l'étendue d'un GeoDataFrame.
        """
        bounds = gdf.total_bounds.tolist()
        return self.set_inset_box(bounds, **kwargs)

    # -- flèche du Nord & barre d'échelle ---------------------------------

    def add_north_arrow(self, style="auto", location="upper right", **kwargs):
        """
        Ajoute une flèche du Nord à la carte principale.

        Utilise ``matplotlib-map-utils`` si disponible.
        """
        resolved = style
        if resolved == "auto":
            resolved = "map-utils" if HAS_MAP_UTILS else "svg"

        if resolved in ("map-utils", "fancy", "simple") and HAS_MAP_UTILS:
            rot = kwargs.pop("rotation", {"crs": self.projection, "reference": "center"})
            if isinstance(rot, (int, float)):
                rot = {"degrees": rot}
            na_kwargs = dict(location=location, rotation=rot)
            na_kwargs["fancy"] = kwargs.pop("fancy", resolved != "simple")
            na_kwargs["shadow"] = kwargs.pop("shadow", True)
            label = kwargs.pop("label", "N")
            if isinstance(label, dict):
                na_kwargs["label"] = label
            elif label:
                na_kwargs["label"] = {"text": label}
            na_kwargs.update(kwargs)
            na = MmuNorthArrow(**na_kwargs)
            self.ax.add_artist(na)
            return self

        # Fallback simplifié : pas de SVG dans SituationMap
        self._log("⚠️  Flèche du Nord nécessite matplotlib-map-utils "
                  "ou utilisez Map.add_north_arrow() pour les SVG")
        return self

    def add_scale_bar(self, length=None, location="lower left", units="km",
                      color="black", fontsize=11, linewidth=2,
                      style="auto", bar_style="boxes",
                      major_div=None, minor_div=None,
                      box_color="white", box_alpha=0.8,
                      scale_loc="bottom", label_loc="top", **kwargs):
        """
        Ajoute une barre d'échelle à la carte principale.

        Utilise ``matplotlib-map-utils`` > ``matplotlib-scalebar`` > manuel.
        """
        resolved = style
        if resolved == "auto":
            if HAS_MAP_UTILS:
                resolved = "map-utils"
            elif HAS_MPL_SCALEBAR:
                resolved = "scalebar"
            else:
                resolved = "manual"

        if resolved in ("map-utils", "ticks", "boxes") and HAS_MAP_UTILS:
            if resolved in ("ticks", "boxes"):
                bar_style = resolved
            loc = location if isinstance(location, str) else "lower left"
            # Voir Map._draw_scale_bar pour le détail de ces deux points :
            # major_div nécessite major_mult (non exposé ici) pour être
            # valide côté matplotlib-map-utils, et PlateCarree/Geodetic ne
            # sont pas résolues en unités "degree" par pyproj.
            bar_projection = (
                "EPSG:4326"
                if isinstance(self.projection, (ccrs.PlateCarree, ccrs.Geodetic))
                else self.projection
            )
            bar_dict = dict(projection=bar_projection)
            if major_div is not None:
                bar_dict["major_div"] = major_div
            if minor_div is not None:
                bar_dict["minor_div"] = minor_div
            if length is not None:
                bar_dict["length"] = length
                bar_dict["unit"] = units
            labels_dict = dict(fontsize=fontsize)
            sb_kwargs = dict(
                style=bar_style, location=loc,
                bar=bar_dict, labels=labels_dict,
            )
            sb_kwargs.update(kwargs)
            try:
                sb = MmuScaleBar(**sb_kwargs)
                self.ax.add_artist(sb)
                return self
            except (TypeError, ValueError) as e:
                self._log(f"⚠️  ScaleBar map-utils échoué : {e}, "
                          "utilisation de la méthode alternative")
                resolved = "scalebar" if HAS_MPL_SCALEBAR else "manual"

        if resolved == "scalebar" and HAS_MPL_SCALEBAR:
            is_geo = isinstance(self.projection, (ccrs.PlateCarree, ccrs.Geodetic))
            if is_geo:
                x0, x1 = self.ax.get_xlim()
                y0, y1 = self.ax.get_ylim()
                mid_lat = float(np.clip((y0 + y1) / 2, -89, 89))
                mid_lon = float((x0 + x1) / 2)
                geod = Geod(ellps="WGS84")
                _, _, dist = geod.inv(mid_lon, mid_lat, mid_lon + 1, mid_lat)
                dx = abs(dist)
            else:
                dx = 1
            loc = location if isinstance(location, str) else "lower left"
            dimension = (
                "imperial-length" if units in ("mi", "ft", "yd")
                else "si-length"
            )
            sb_kwargs = dict(
                location=loc, color=color,
                box_color=box_color, box_alpha=box_alpha,
                scale_loc=scale_loc, label_loc=label_loc,
                font_properties={"size": fontsize},
                length_fraction=0.2,
            )
            if length is not None:
                sb_kwargs["fixed_value"] = length
                sb_kwargs["fixed_units"] = units
            sb_kwargs.update(kwargs)
            sb = MplScaleBar(dx, units="m", dimension=dimension, **sb_kwargs)
            self.ax.add_artist(sb)
            return self

        # ------- mode manuel (fallback) -------
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        geod = Geod(ellps="WGS84")
        mid_lat = (y0 + y1) / 2
        try:
            map_width_m, _, _ = geod.inv(x0, mid_lat, x1, mid_lat)
            map_width_km = abs(map_width_m) / 1000
        except Exception:
            map_width_km = 100

        if length is None:
            raw = map_width_km / 5
            if raw <= 0:
                raw = 10
            pow10 = 10 ** int(np.floor(np.log10(raw)))
            length = int(raw / pow10) * pow10
            if length == 0:
                length = max(1, int(raw))

        if isinstance(location, str):
            _loc_map = {
                "lower left": (0.1, 0.05), "lower right": (0.7, 0.05),
                "upper left": (0.1, 0.9), "upper right": (0.7, 0.9),
                "lower center": (0.4, 0.05), "upper center": (0.4, 0.9),
            }
            location = _loc_map.get(location, (0.1, 0.05))

        x_ax, y_ax = location
        start_x = x0 + x_ax * (x1 - x0)
        start_y = y0 + y_ax * (y1 - y0)
        try:
            lon_end, _, _ = geod.fwd(start_x, start_y, 90, length * 1000)
            bar_len = lon_end - start_x
        except Exception:
            bar_len = length * 1000 / (111320 * np.cos(np.radians(start_y)))

        self.ax.plot(
            [start_x, start_x + bar_len], [start_y, start_y],
            color=color, linewidth=linewidth, solid_capstyle="butt",
        )
        self.ax.text(
            start_x + bar_len / 2, start_y + 0.05,
            f"{length} {units}", ha="center", va="bottom",
            color=color, fontsize=fontsize, fontweight="bold",
        )
        return self

    # -- grille et apparence -----------------------------------------------

    def add_gridlines(self, **kwargs):
        """Ajoute des lignes de grille à la carte principale."""
        defaults = dict(draw_labels=True, dms=True, x_inline=False, y_inline=False,
                        color="gray", linestyle="--", linewidth=0.5, alpha=0.7)
        defaults.update(kwargs)
        self.ax.gridlines(**defaults)
        return self

    # -- sortie ------------------------------------------------------------

    def show(self):
        self.fig.tight_layout()
        plt.show()
        return self

    def save(self, filename, dpi=300, bbox_inches="tight"):
        self.fig.tight_layout()
        self.fig.savefig(filename, dpi=dpi, bbox_inches=bbox_inches)
        self._log(f"Carte sauvegardée : {filename}")
        return self

    def to_bytes(self, format="png", dpi=300) -> BytesIO:
        self.fig.tight_layout()
        buf = BytesIO()
        self.fig.savefig(buf, format=format, dpi=dpi, bbox_inches="tight")
        buf.seek(0)
        return buf
