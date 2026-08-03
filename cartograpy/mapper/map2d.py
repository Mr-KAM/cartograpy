import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.patheffects as patheffects
from .map import Map
import logging

logger = logging.getLogger(__name__)


class Map2D(Map):
    """
    Carte 2D sans projection cartographique (axes matplotlib classiques).
    Hérite de Map pour réutiliser la gestion des formats de papier, la
    légende, les palettes, les polices, l'export, etc.

    Utile pour des traitements locaux où la projection n'est pas nécessaire,
    par exemple des plans urbains, des parcelles cadastrales ou des
    visualisations rapides de GeoDataFrames.

    Paramètres:
    -----------
    figsize : tuple
        Taille de la figure (largeur, hauteur) en pouces
    title : str
        Titre de la carte
    dpi : int
        Résolution
    verbose : bool
        Afficher les messages d'information
    """

    def __init__(
        self,
        figsize=(12, 8),
        title="Carte 2D",
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

        self.ax.set_title(title, fontsize=14, fontweight="bold")
        self.ax.set_aspect("equal")

        if self.paper_info:
            self._log(
                f"📄 Format de papier: {self.paper_info['format']} "
                f"({self.paper_info['orientation']}) - "
                f"Dimensions: {self.paper_info['dimensions_mm']} mm - "
                f'Figure: {self.figsize[0]:.1f}" x {self.figsize[1]:.1f}"'
            )

    # -- rendu interne (sans cartopy) --------------------------------------

    def _render(self, legend=True, auto_extent=True, tight_layout=True,
                smart_centering=False, title=None, **kwargs):
        """Rendu simplifié sans projection cartographique."""
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

        if title is not None:
            self.ax.set_title(title)

        legend_params = self.legend_params
        if legend and self.legend_elements:
            self.custom_legend(**legend_params, **kwargs)

        if tight_layout:
            plt.tight_layout()

    # -- couche vectorielle (sans transform cartopy) -----------------------

    def add_layer(self, gdf, column=None, cmap="viridis", label=None,
                  edgecolor="black", linewidth=0.5, alpha=0.8, **kwargs):
        """
        Ajoute un GeoDataFrame comme couche.

        Note : la signature diffère volontairement de Map.add_layer()
        car Map2D ne gère que des GeoDataFrames (pas de rasters ni de
        détection automatique de type).

        Paramètres:
        -----------
        gdf : gpd.GeoDataFrame
            Données géographiques
        column : str, optional
            Colonne pour la coloration
        cmap : str
            Palette de couleurs
        label : str
            Étiquette pour la légende
        edgecolor : str
            Couleur des contours
        linewidth : float
            Largeur des contours
        alpha : float
            Transparence (0-1)
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

    # -- étiquettes --------------------------------------------------------

    def add_labels(self, gdf, label_column, fontsize=9, color="black",
                   outline_width=2, outline_color="white", **text_kwargs):
        """
        Ajoute des étiquettes au centroïde / position des géométries.
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

    # -- apparence ---------------------------------------------------------

    def hide_axes(self):
        """Masque les axes."""
        self.ax.axis("off")
        return self
