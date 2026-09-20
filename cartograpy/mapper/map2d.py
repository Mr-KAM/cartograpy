import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.patheffects as patheffects
from .map import Map
import logging

logger = logging.getLogger(__name__)


class Map2D(Map):
    """
    2D map without a cartographic projection (classic matplotlib axes).
    Inherits from Map to reuse paper-format handling, legend, palettes,
    fonts, export, etc.

    Useful for local processing where projection isn't needed, e.g.
    city plans, cadastral parcels, or quick visualizations of
    GeoDataFrames.

    Parameters:
    -----------
    figsize : tuple
        Figure size (width, height) in inches
    title : str
        Map title
    dpi : int
        Resolution
    verbose : bool
        Display information messages
    """

    def __init__(
        self,
        figsize=(12, 8),
        title="Map 2D",
        dpi=150,
        verbose=True,
    ):
        self.verbose = verbose
        self.figsize = self._process_figsize(figsize)
        self.paper_info = self._get_paper_info(figsize)
        self.dpi = dpi
        self.fig, self.ax = plt.subplots(figsize=self.figsize, dpi=dpi)
        self.title = title
        self.projection = None
        self.data_crs = None
        self.layers = []
        self.legend_elements = []
        self.gridlines = None
        self.legend_params = {}
        self.custom_palettes = {}
        self.bounds = None
        self._background_image_kwargs = None
        self._background_image_artist = None

        self.ax.set_title(title, fontsize=14, fontweight="bold")
        self.ax.set_aspect("equal")

        if self.paper_info:
            self._log(
                f"📄 Paper format: {self.paper_info['format']} "
                f"({self.paper_info['orientation']}) - "
                f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
                f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
            )

    # -- internal rendering (no cartopy) ------------------------------------

    def _render(self, legend=True, auto_extent=True, tight_layout=True,
                smart_centering=False, title=None, **kwargs):
        """Simplified rendering without a cartographic projection."""
        for layer in self.layers:
            if layer.get("rendered"):
                continue
            layer_type = layer.get("type")
            if layer_type in ("point", "line", "polygon"):
                gdf = layer["gdf"]
                style = layer["style"].copy()
                style.pop("ax", None)
                style.pop("transform", None)
                gdf.plot(ax=self.ax, **style)
                layer["rendered"] = True

        if title is not None:
            self.ax.set_title(title)

        legend_params = self.legend_params
        if legend and self.legend_elements:
            self.custom_legend(**legend_params, **kwargs)

        if tight_layout:
            self.fig.tight_layout()

    # -- vector layer (no cartopy transform) --------------------------------

    def add_layer(self, gdf, column=None, cmap="viridis", label=None,
                  edgecolor="black", linewidth=0.5, alpha=0.8, **kwargs):
        """
        Adds a GeoDataFrame as a layer.

        Note: the signature intentionally differs from Map.add_layer()
        because Map2D only handles GeoDataFrames (no rasters or
        automatic type detection).

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            Geographic data
        column : str, optional
            Column used for coloring
        cmap : str
            Color palette
        label : str
            Legend label
        edgecolor : str
            Outline color
        linewidth : float
            Outline width
        alpha : float
            Transparency (0-1)
        """
        plot_kwargs = dict(
            ax=self.ax, edgecolor=edgecolor, linewidth=linewidth,
            alpha=alpha, **kwargs,
        )
        if column:
            plot_kwargs["column"] = column
            plot_kwargs["cmap"] = cmap
            plot_kwargs["legend"] = True
        else:
            plot_kwargs["color"] = kwargs.pop("color", "steelblue")

        gdf.plot(**plot_kwargs)
        self.layers.append({"gdf": gdf, "label": label, "rendered": True})
        if label:
            self.legend_elements.append(
                Patch(facecolor="steelblue", edgecolor=edgecolor,
                      alpha=alpha, label=label)
            )
        return self

    # -- labels --------------------------------------------------------------

    def add_labels(self, gdf, label_column, fontsize=9, color="black",
                   outline_width=2, outline_color="white", **text_kwargs):
        """
        Adds labels at the centroid / position of each geometry.
        """
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            pt = geom.centroid if geom.geom_type not in ("Point",) else geom
            self.ax.text(
                pt.x, pt.y, str(row[label_column]),
                fontsize=fontsize, ha="center", va="center", color=color,
                path_effects=[
                    patheffects.withStroke(
                        linewidth=outline_width, foreground=outline_color
                    )
                ],
                **text_kwargs,
            )
        return self

    # -- appearance ------------------------------------------------------------

    def hide_axes(self):
        """Hides the axes."""
        self.ax.axis("off")
        return self
